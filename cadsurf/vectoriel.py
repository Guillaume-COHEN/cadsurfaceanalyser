# Copyright 2026 The CADSurfaceAnalyser authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Calculs vectorisés (numpy) pour les faces à surface numérique.

Au lieu de traiter les nœuds d'intégration un par un, tous les nœuds d'une
arête sont traités en un seul appel :

  * fonctions de base B-spline et dérivées pour des tableaux de paramètres ;
  * projection de tous les points de l'arête sur la surface (meilleur point
    d'une grille mise en cache, puis Gauss-Newton sur l'ensemble) ;
  * intégrale intérieure de Green pour tous les nœuds à la fois ;
  * vitesse paramétrique par moindres carrés, comme dans le calcul scalaire.

Le calcul est mathématiquement celui de geom_faces._integrate_edge ; si un cas
dégénéré apparaît (projection qui ne converge pas, paramétrage singulier),
l'exception Repli est levée et le calcul scalaire prend le relais pour l'arête.
Ce module exige numpy : il n'est importé que si accel.UTILISER est vrai.
"""

import math

import numpy as np

from .config import EPS, _GL6

_GLX = np.array([x for x, _ in _GL6])
_GLW = np.array([w for _, w in _GL6])
_DEUX_PI = 2.0 * math.pi


class Repli(Exception):
    """Le calcul vectorisé ne peut pas aboutir : calcul scalaire à utiliser."""


# ============================================================================
# B-SPLINES : intervalle, fonctions de base
# ============================================================================

def intervalle(knots, degre, t):
    """Intervalle de nœuds de chaque paramètre (même règle que find_span)."""
    n = len(knots) - degre - 2
    k = np.searchsorted(knots, t, side="right") - 1
    return np.clip(k, degre, n)


def base(k, t, degre, knots):
    """Fonctions de base non nulles : tableau (M, degre+1)."""
    M = t.shape[0]
    N = np.zeros((M, degre + 1))
    N[:, 0] = 1.0
    gauche = np.zeros((M, degre + 1))
    droite = np.zeros((M, degre + 1))
    for j in range(1, degre + 1):
        gauche[:, j] = t - knots[k + 1 - j]
        droite[:, j] = knots[k + j] - t
        saved = np.zeros(M)
        for r in range(j):
            temp = N[:, r] / (droite[:, r + 1] + gauche[:, j - r])
            N[:, r] = saved + droite[:, r + 1] * temp
            saved = gauche[:, j - r] * temp
        N[:, j] = saved
    return N


def base_d1(k, t, degre, knots):
    """Fonctions de base et dérivées premières : deux tableaux (M, degre+1)."""
    N = base(k, t, degre, knots)
    dN = np.zeros_like(N)
    if degre == 0:
        return N, dN
    Nm = base(k, t, degre - 1, knots)
    for j in range(degre + 1):
        i = k - degre + j
        a = 0.0
        if j >= 1:
            den = knots[i + degre] - knots[i]
            a = np.where(den != 0.0, Nm[:, j - 1] / np.where(den != 0.0, den, 1.0), 0.0)
        b = 0.0
        if j <= degre - 1:
            den = knots[i + degre + 1] - knots[i + 1]
            b = np.where(den != 0.0, Nm[:, j] / np.where(den != 0.0, den, 1.0), 0.0)
        dN[:, j] = degre * (a - b)
    return N, dN


def _dehomog(A, Ad=None):
    """Division par le poids (règle de dehomog : |w| < EPS -> brut)."""
    w = A[:, 3]
    mauvais = np.abs(w) < EPS
    ws = np.where(mauvais, 1.0, w)[:, None]
    S = A[:, :3] / ws
    if mauvais.any():
        S[mauvais] = A[mauvais, :3]
    return S, ws, mauvais


# ============================================================================
# COURBES
# ============================================================================

class CourbeBS(object):
    """B-spline (rationnelle ou non) évaluée sur des tableaux de paramètres."""

    def __init__(self, c):
        self.P = np.asarray(c.ctrl, dtype=float)
        self.k = np.asarray(c.knots, dtype=float)
        self.p = c.degree

    def _bloc(self, t, dn):
        p = self.p
        k = intervalle(self.k, p, t)
        if dn:
            N, dN = base_d1(k, t, p, self.k)
        else:
            N, dN = base(k, t, p, self.k), None
        idx = (k - p)[:, None] + np.arange(p + 1)[None, :]
        return N, dN, self.P[idx]

    def eval(self, t):
        N, _, blk = self._bloc(t, False)
        A = np.einsum("ma,maq->mq", N, blk)
        return _dehomog(A)[0]

    def d(self, t):
        N, dN, blk = self._bloc(t, True)
        A = np.einsum("ma,maq->mq", N, blk)
        B = np.einsum("ma,maq->mq", dN, blk)
        S, ws, mauvais = _dehomog(A)
        D = (B[:, :3] - B[:, 3:4] * S) / ws
        if mauvais.any():
            D[mauvais] = B[mauvais, :3]
        return D


class CercleVec(object):
    """Cercle / ellipse de paramètre angulaire t."""

    def __init__(self, f, ra, rb):
        self.o = np.asarray(f.o, float)
        self.x = np.asarray(f.x, float)
        self.y = np.asarray(f.y, float)
        self.ra, self.rb = ra, rb

    def eval(self, t):
        return (self.o + self.x * (self.ra * np.cos(t))[:, None]
                + self.y * (self.rb * np.sin(t))[:, None])

    def d(self, t):
        return (-self.x * (self.ra * np.sin(t))[:, None]
                + self.y * (self.rb * np.cos(t))[:, None])


def profil_vec(profil):
    """Version vectorisée d'une génératrice ProfileCurve."""
    if getattr(profil, "_bs", None) is not None:
        return CourbeBS(profil._bs)
    if getattr(profil, "_cercle", None) is not None:
        return CercleVec(*profil._cercle)
    raise Repli("génératrice non vectorisable")


def courbe_arete(eg):
    """Courbe B-spline vectorisée d'une arête (mise en cache)."""
    v = getattr(eg, "_vec_bs", None)
    if v is None:
        v = eg._vec_bs = CourbeBS(eg.curve)
    return v


def points_arete(eg, orient, t):
    """Points de l'arête orientée pour un tableau t de [0, 1]."""
    tt = t if orient else 1.0 - t
    if eg.exact and eg.kind in ("CIRCLE", "ELLIPSE"):
        f = eg.frame
        a = eg.a1 + (eg.a2 - eg.a1) * tt
        return (np.asarray(f.o, float)
                + np.asarray(f.x, float) * (eg.ra * np.cos(a))[:, None]
                + np.asarray(f.y, float) * (eg.rb * np.sin(a))[:, None])
    if hasattr(eg, "curve"):
        return courbe_arete(eg).eval(eg.ts + (eg.te - eg.ts) * tt)
    p1 = np.asarray(eg.p1, float)
    p2 = np.asarray(eg.p2, float)
    return p1 + (p2 - p1) * tt[:, None]                 # droite ou corde


def tangentes_arete(eg, orient, t):
    """Tangentes dP/dt de l'arête orientée (même convention que
    EdgeGeom.tangent_o)."""
    tt = t if orient else 1.0 - t
    if eg.exact and eg.kind in ("CIRCLE", "ELLIPSE"):
        f = eg.frame
        da = eg.a2 - eg.a1
        a = eg.a1 + da * tt
        T = (-np.asarray(f.x, float) * (eg.ra * np.sin(a) * da)[:, None]
             + np.asarray(f.y, float) * (eg.rb * np.cos(a) * da)[:, None])
    elif hasattr(eg, "curve"):
        T = courbe_arete(eg).d(eg.ts + (eg.te - eg.ts) * tt) * (eg.te - eg.ts)
    else:
        T = np.tile(np.asarray(eg.p2, float) - np.asarray(eg.p1, float), (len(tt), 1))
    return T if orient else -T


def longueur_courbe_bs(eg, K=64):
    """Longueur d'une arête B-spline (Gauss, dérivée analytique)."""
    a = np.arange(K) / K
    b = (np.arange(K) + 1) / K
    half = (b - a) / 2.0
    mid = (a + b) / 2.0
    t = (mid[:, None] + half[:, None] * _GLX[None, :]).ravel()
    w = (half[:, None] * _GLW[None, :]).ravel()
    vit = np.linalg.norm(
        courbe_arete(eg).d(eg.ts + (eg.te - eg.ts) * t), axis=1
    ) * abs(eg.te - eg.ts)
    return float((w * vit).sum())


def echantillon_courbe_bs(eg, n=400):
    """n+1 points régulièrement répartis sur une arête B-spline."""
    t = np.arange(n + 1) / float(n)
    return courbe_arete(eg).eval(eg.ts + (eg.te - eg.ts) * t)


# ============================================================================
# SURFACES : B-spline, révolution, extrusion
# ============================================================================

class SurfBS(object):
    def __init__(self, sp):
        bs = sp.bs
        self.bs = bs
        self.C = np.asarray(bs.ctrl, dtype=float)               # (nu, nv, 4)
        self.ku = np.asarray(bs.ku, dtype=float)
        self.kv = np.asarray(bs.kv, dtype=float)
        self.du, self.dv = bs.du, bs.dv
        self.ru, self.rv = bs.u1 - bs.u0, bs.v1 - bs.v0
        self.vk = np.unique(self.kv)
        self._grille = None

    def _blocs(self, u, v, dn):
        pu, pv = self.du, self.dv
        ku = intervalle(self.ku, pu, u)
        kv = intervalle(self.kv, pv, v)
        if dn:
            Nu, dNu = base_d1(ku, u, pu, self.ku)
            Nv, dNv = base_d1(kv, v, pv, self.kv)
        else:
            Nu, dNu = base(ku, u, pu, self.ku), None
            Nv, dNv = base(kv, v, pv, self.kv), None
        iu = (ku - pu)[:, None] + np.arange(pu + 1)[None, :]
        iv = (kv - pv)[:, None] + np.arange(pv + 1)[None, :]
        blk = self.C[iu[:, :, None], iv[:, None, :]]            # (M, pu+1, pv+1, 4)
        return Nu, dNu, Nv, dNv, blk

    def point(self, u, v):
        Nu, _, Nv, _, blk = self._blocs(u, v, False)
        T = np.einsum("mb,mabq->maq", Nv, blk)
        return _dehomog(np.einsum("ma,maq->mq", Nu, T))[0]

    def derivs(self, u, v):
        Nu, dNu, Nv, dNv, blk = self._blocs(u, v, True)
        T = np.einsum("mb,mabq->maq", Nv, blk)
        dT = np.einsum("mb,mabq->maq", dNv, blk)
        A = np.einsum("ma,maq->mq", Nu, T)
        Au = np.einsum("ma,maq->mq", dNu, T)
        Av = np.einsum("ma,maq->mq", Nu, dT)
        S, ws, mauvais = _dehomog(A)
        Su = (Au[:, :3] - Au[:, 3:4] * S) / ws
        Sv = (Av[:, :3] - Av[:, 3:4] * S) / ws
        if mauvais.any():
            Su[mauvais] = Au[mauvais, :3]
            Sv[mauvais] = Av[mauvais, :3]
        return S, Su, Sv

    def grille(self):
        if self._grille is None:
            G = self.bs.GRID
            gu = np.repeat(self.bs.u0 + self.ru * np.arange(G + 1) / G, G + 1)
            gv = np.tile(self.bs.v0 + self.rv * np.arange(G + 1) / G, G + 1)
            self._grille = (gu, gv, self.point(gu, gv))
        return self._grille

    def projeter(self, P):
        """(u, v, ok) : projection de tous les points (Gauss-Newton)."""
        gu, gv, gP = self.grille()
        d2 = ((gP[None, :, :] - P[:, None, :]) ** 2).sum(axis=2)
        i = d2.argmin(axis=1)
        best = d2[np.arange(len(P)), i]
        u, v = gu[i].copy(), gv[i].copy()
        ok = np.zeros(len(P), dtype=bool)
        actif = np.ones(len(P), dtype=bool)
        for _ in range(40):
            idx = np.nonzero(actif)[0]
            if idx.size == 0:
                break
            S, Su, Sv = self.derivs(u[idx], v[idx])
            r = S - P[idx]
            a11 = (Su * Su).sum(1)
            a12 = (Su * Sv).sum(1)
            a22 = (Sv * Sv).sum(1)
            det = a11 * a22 - a12 * a12
            degen = (a11 * a22 == 0.0) | (det <= 1e-20 * a11 * a22)
            b1 = -(Su * r).sum(1)
            b2 = -(Sv * r).sum(1)
            ds = np.where(degen, 1.0, det)
            nu = np.clip(u[idx] + np.where(degen, 0.0, (b1 * a22 - b2 * a12) / ds),
                         self.bs.u0, self.bs.u1)
            nv = np.clip(v[idx] + np.where(degen, 0.0, (a11 * b2 - a12 * b1) / ds),
                         self.bs.v0, self.bs.v1)
            fini = (np.abs(nu - u[idx]) < 1e-11 * self.ru) & (np.abs(nv - v[idx]) < 1e-11 * self.rv)
            u[idx], v[idx] = nu, nv
            ok[idx[fini]] = True
            actif[idx[fini | degen]] = False
        x = self.point(u, v)
        ok &= ((x - P) ** 2).sum(1) <= best * (1.0 + 1e-9) + 1e-24
        return u, v, ok

    def cassures(self, lo, hi):
        inte = self.vk[(self.vk > lo) & (self.vk < hi)]
        return np.concatenate(([lo], inte, [hi]))


class SurfRev(object):
    """Surface de révolution : u = angle, v = paramètre de la génératrice."""

    def __init__(self, sp):
        rev = sp.rev
        self.sp = sp
        self.o = np.asarray(rev.o, float)
        self.x = np.asarray(rev.x, float)
        self.y = np.asarray(rev.y, float)
        self.z = np.asarray(rev.z, float)
        self.profil = profil_vec(rev.curve)
        c = rev.curve
        self.t0, self.t1, self.periodique = c.t0, c.t1, c.periodic
        self.periodique_v = c.periodic
        tab = np.asarray(rev._table, dtype=float)               # (t, rho, z)
        self.tab_t, self.tab_r, self.tab_z = tab[:, 0], tab[:, 1], tab[:, 2]

    def rz(self, t):
        p = self.profil.eval(t)
        dp = self.profil.d(t)
        d = p - self.o
        z = d @ self.z
        rv = d - z[:, None] * self.z
        rho = np.linalg.norm(rv, axis=1)
        ok = rho >= EPS                          # règle de vecteurs.unit
        ur = rv / np.where(ok, rho, 1.0)[:, None]
        drho = np.where(ok, (ur * dp).sum(1), 0.0)
        return rho, z, drho, dp @ self.z

    def derivs(self, u, t):
        rho, z, drho, dz = self.rz(t)
        cu, su = np.cos(u)[:, None], np.sin(u)[:, None]
        er = self.x * cu + self.y * su
        et = -self.x * su + self.y * cu
        S = self.o + er * rho[:, None] + self.z * z[:, None]
        return S, et * rho[:, None], er * drho[:, None] + self.z * dz[:, None]

    def projeter(self, P):
        d = P - self.o
        zp = d @ self.z
        rp = np.linalg.norm(d - zp[:, None] * self.z, axis=1)
        theta = np.arctan2(d @ self.y, d @ self.x)
        d2 = (self.tab_r[None, :] - rp[:, None]) ** 2 + (self.tab_z[None, :] - zp[:, None]) ** 2
        t = self.tab_t[d2.argmin(axis=1)].copy()
        span = self.t1 - self.t0
        ok = np.zeros(len(P), dtype=bool)
        actif = np.ones(len(P), dtype=bool)
        for _ in range(40):
            idx = np.nonzero(actif)[0]
            if idx.size == 0:
                break
            r, z, dr, dz = self.rz(t[idx])
            g = dr * dr + dz * dz
            degen = g < 1e-30
            dt = -((r - rp[idx]) * dr + (z - zp[idx]) * dz) / np.where(degen, 1.0, g)
            dt = np.where(degen, 0.0, dt)
            nt = t[idx] + dt
            if not self.periodique:
                nt = np.clip(nt, self.t0, self.t1)
            t[idx] = nt
            fini = np.abs(dt) < 1e-12 * span
            ok[idx[fini]] = True
            actif[idx[fini | degen]] = False
        return theta, t, ok

    def cassures(self, lo, hi):
        sp = self.sp
        if sp.vknots is not None:
            vk = np.asarray(sp.vknots, float)
            return np.concatenate(([lo], vk[(vk > lo) & (vk < hi)], [hi]))
        pas = sp.vstep
        if hi <= lo:
            return np.array([lo, hi])
        vref = self.t0
        k0 = math.floor((lo - vref) / pas)
        k1 = math.ceil((hi - vref) / pas)
        B = vref + pas * np.arange(k0, k1 + 1)
        return np.concatenate(([lo], B[(B > lo) & (B < hi)], [hi]))


class SurfExt(object):
    """Extrusion linéaire : u = paramètre de la génératrice, v = distance."""

    def __init__(self, sp):
        e = sp.ext
        self.profil = profil_vec(e.curve)
        self.d = np.asarray(e.d, float)
        self.t0, self.t1, self.periodique = e.curve.t0, e.curve.t1, e.curve.periodic
        self.tab_t = np.array([t for t, _ in e._table])
        self.tab_q = np.array([q for _, q in e._table])

    def _perp(self, w):
        return w - (w @ self.d)[:, None] * self.d

    def derivs(self, t, s):
        S = self.profil.eval(t) + s[:, None] * self.d
        Su = self.profil.d(t)
        return S, Su, np.tile(self.d, (len(t), 1))

    def projeter(self, P):
        diff = self.tab_q[None, :, :] - P[:, None, :]
        diff = diff - (diff @ self.d)[:, :, None] * self.d
        t = self.tab_t[(diff ** 2).sum(axis=2).argmin(axis=1)].copy()
        span = self.t1 - self.t0
        ok = np.zeros(len(P), dtype=bool)
        actif = np.ones(len(P), dtype=bool)
        for _ in range(40):
            idx = np.nonzero(actif)[0]
            if idx.size == 0:
                break
            w = self._perp(self.profil.eval(t[idx]) - P[idx])
            dw = self._perp(self.profil.d(t[idx]))
            g = (dw * dw).sum(1)
            degen = g < 1e-30
            dt = np.where(degen, 0.0, -(w * dw).sum(1) / np.where(degen, 1.0, g))
            nt = t[idx] + dt
            if not self.periodique:
                nt = np.clip(nt, self.t0, self.t1)
            t[idx] = nt
            fini = np.abs(dt) < 1e-12 * span
            ok[idx[fini]] = True
            actif[idx[fini | degen]] = False
        s = ((P - self.profil.eval(t)) @ self.d)
        return t, s, ok

    def cassures(self, lo, hi):
        return np.array([lo, hi])


class SurfAnalytique(object):
    """Plan, cylindre, cône, sphère, tore : mêmes formules que SurfParam,
    sur des tableaux ; l'inversion est exacte (pas d'itération)."""

    def __init__(self, sp):
        s, f = sp.surf, sp.f
        self.sp = sp
        self.kind = sp.kind
        self.o = np.asarray(f.o, float)
        self.x = np.asarray(f.x, float)
        self.y = np.asarray(f.y, float)
        self.z = np.asarray(f.z, float)
        if self.kind in ("CYLINDRICAL_SURFACE", "CONICAL_SURFACE", "SPHERICAL_SURFACE"):
            self.R = s.radius
        if self.kind == "CONICAL_SURFACE":
            self.tana = sp.tana
        if self.kind in ("TOROIDAL_SURFACE", "DEGENERATE_TOROIDAL_SURFACE"):
            self.R, self.r = s.major_radius, s.minor_radius

    def derivs(self, u, v):
        k, M = self.kind, len(u)
        if k == "PLANE":
            S = self.o + self.x * u[:, None] + self.y * v[:, None]
            return S, np.tile(self.x, (M, 1)), np.tile(self.y, (M, 1))
        cu, su = np.cos(u)[:, None], np.sin(u)[:, None]
        er = self.x * cu + self.y * su
        et = -self.x * su + self.y * cu
        if k == "CYLINDRICAL_SURFACE":
            S = self.o + er * self.R + self.z * v[:, None]
            return S, et * self.R, np.tile(self.z, (M, 1))
        if k == "CONICAL_SURFACE":
            r = (self.R + v * self.tana)[:, None]
            S = self.o + er * r + self.z * v[:, None]
            return S, et * r, er * self.tana + self.z
        cv, sv = np.cos(v)[:, None], np.sin(v)[:, None]
        if k == "SPHERICAL_SURFACE":
            S = self.o + er * (self.R * cv) + self.z * (self.R * sv)
            return S, et * (self.R * cv), er * (-self.R * sv) + self.z * (self.R * cv)
        rho = self.R + self.r * cv                                  # tore
        S = self.o + er * rho + self.z * (self.r * sv)
        return S, et * rho, er * (-self.r * sv) + self.z * (self.r * cv)

    def projeter(self, P):
        d = P - self.o
        dx, dy, dz = d @ self.x, d @ self.y, d @ self.z
        ok = np.ones(len(P), dtype=bool)
        k = self.kind
        if k == "PLANE":
            return dx, dy, ok
        u = np.arctan2(dy, dx)
        if k in ("CYLINDRICAL_SURFACE", "CONICAL_SURFACE"):
            return u, dz, ok
        rho = np.hypot(dx, dy)
        if k == "SPHERICAL_SURFACE":
            return u, np.arctan2(dz, rho), ok
        return u, np.arctan2(dz, rho - self.R), ok

    def vitesse_u(self, P, dP):
        """du/dt exact de la projection de la courbe sur la surface (forme
        fermée : u = x_local ou u = atan2(y_local, x_local)). Plus fidèle que
        la projection de la tangente quand l'arête est à ~1e-4 de la surface."""
        if self.kind == "PLANE":
            return dP @ self.x
        d = P - self.o
        dx, dy = d @ self.x, d @ self.y
        r2 = dx * dx + dy * dy
        if (r2 < 1e-24).any():
            raise Repli("point sur l'axe")
        return (dx * (dP @ self.y) - dy * (dP @ self.x)) / r2

    def cassures(self, lo, hi):
        pas = self.sp.vstep
        if pas:                                  # sphère, tore : trigonométrique
            B = pas * np.arange(math.floor(lo / pas), math.ceil(hi / pas) + 1)
            return np.concatenate(([lo], B[(B > lo) & (B < hi)], [hi]))
        return np.array([lo, hi])                # polynôme en v : une seule maille


def _vue(sp):
    v = getattr(sp, "_vue_np", None)
    if v is None:
        if sp.is_bspline:
            v = SurfBS(sp)
        elif sp.rev is not None:
            v = SurfRev(sp)
        elif sp.ext is not None:
            v = SurfExt(sp)
        elif sp.kind in ("PLANE", "CYLINDRICAL_SURFACE", "CONICAL_SURFACE",
                         "SPHERICAL_SURFACE", "TOROIDAL_SURFACE",
                         "DEGENERATE_TOROIDAL_SURFACE"):
            v = SurfAnalytique(sp)
        else:
            raise Repli("surface non vectorisable")
        sp._vue_np = v
    return v


# ============================================================================
# INTEGRALES
# ============================================================================

def _derouler(x, ref):
    """Rend continue une suite d'angles / paramètres périodiques (période 2*pi),
    puis la recale sur `ref` (valeur de l'arête précédente) si elle existe."""
    d = np.diff(x)
    d = d - _DEUX_PI * np.round(d / _DEUX_PI)
    x = x[0] + np.concatenate(([0.0], np.cumsum(d)))
    if ref is not None:
        x = x + _DEUX_PI * round((ref - x[0]) / _DEUX_PI)
    return x


def _canaux(S, Su, Sv):
    """Les 8 intégrandes (aire, aire*S, aire vectorielle, volume/3)."""
    N = np.cross(Su, Sv)
    w = np.linalg.norm(N, axis=-1)
    return np.concatenate(
        [w[..., None], w[..., None] * S, N, (S * N).sum(-1)[..., None] / 3.0],
        axis=-1,
    )


def integrale_interieure(vue, u, v, vref):
    """G(u, v) = integrale de g(u, v') dv' de vref à v, pour tous les nœuds :
    tableau (M, 8)."""
    lo = np.minimum(v, vref)
    hi = np.maximum(v, vref)
    signe = np.where(v >= vref, 1.0, -1.0)
    L, H = float(lo.min()), float(hi.max())
    if H <= L:
        return np.zeros((len(u), 8))
    B = vue.cassures(L, H)
    a = np.clip(B[:-1][None, :], lo[:, None], hi[:, None])          # (M, J)
    b = np.clip(B[1:][None, :], lo[:, None], hi[:, None])
    garde = (b - a).max(axis=0) > 0.0
    a, b = a[:, garde], b[:, garde]
    half = (b - a) / 2.0
    mid = (a + b) / 2.0
    X = mid[:, :, None] + half[:, :, None] * _GLX[None, None, :]    # (M, J, 6)
    W = half[:, :, None] * _GLW[None, None, :]
    U = np.broadcast_to(u[:, None, None], X.shape)
    S, Su, Sv = vue.derivs(U.ravel(), X.ravel())
    ch = _canaux(S, Su, Sv).reshape(X.shape + (8,))
    return (W[..., None] * ch).sum(axis=(1, 2)) * signe[:, None]


def integrer_arete(sp, eg, orient, vref, start_uv, ext, K):
    """Équivalent vectorisé de geom_faces._integrate_edge pour les surfaces
    numériques. Retourne (acc, uv_debut, uv_fin) ; lève Repli si besoin."""
    vue = _vue(sp)
    kk = np.arange(K)
    a = kk / float(K)
    b = (kk + 1) / float(K)
    half = (b - a) / 2.0
    mid = (a + b) / 2.0
    tn = (mid[:, None] + half[:, None] * _GLX[None, :]).ravel()
    wn = (half[:, None] * _GLW[None, :]).ravel()
    tt = np.concatenate(([0.0], tn, [1.0]))

    P = points_arete(eg, orient, tt)
    u, v, ok = vue.projeter(P)
    if not ok.all():
        mauvais = np.nonzero(~ok)[0]
        if len(mauvais) > max(3, len(tt) // 10):
            raise Repli("projection non convergente")
        for i in mauvais:                           # rattrapage scalaire
            uu, vv = sp.inverse((float(P[i, 0]), float(P[i, 1]), float(P[i, 2])), None)
            u[i], v[i] = uu, vv
    if sp.period_u:
        u = _derouler(u, None if start_uv is None else start_uv[0])
    if sp.period_v or getattr(vue, "periodique_v", False):
        # génératrice périodique (cercle, ellipse) : paramètre continu le long
        # de la boucle, comme le calcul scalaire (départ « à chaud »)
        v = _derouler(v, None if start_uv is None else start_uv[1])

    un, vn = u[1:-1], v[1:-1]
    S, Su, Sv = vue.derivs(un, vn)
    dP = tangentes_arete(eg, orient, tn)
    if hasattr(vue, "vitesse_u"):
        du = vue.vitesse_u(P[1:-1], dP)               # surfaces analytiques
    else:                                              # moindres carrés
        a11 = (Su * Su).sum(1)
        a12 = (Su * Sv).sum(1)
        a22 = (Sv * Sv).sum(1)
        det = a11 * a22 - a12 * a12
        if (a11 * a22 == 0.0).any() or (det <= 1e-12 * a11 * a22).any():
            raise Repli("paramétrage dégénéré")
        du = ((Su * dP).sum(1) * a22 - (Sv * dP).sum(1) * a12) / det
    G = integrale_interieure(vue, un, vn, vref)
    acc = (G * (du * wn)[:, None]).sum(axis=0)

    ext[0] = min(ext[0], float(un.min()))
    ext[1] = max(ext[1], float(un.max()))
    ext[2] = min(ext[2], float(vn.min()))
    ext[3] = max(ext[3], float(vn.max()))
    return (
        [float(x) for x in acc],
        (float(u[0]), float(v[0])),
        (float(u[-1]), float(v[-1])),
    )
