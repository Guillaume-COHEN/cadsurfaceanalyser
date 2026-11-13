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

"""Surfaces de révolution et d'extrusion : génératrice (B-spline, cercle, ellipse),
normales, ajustement d'un tore équivalent.
"""

import math

from .bsplines import BSplineCurve
from .reperes import Frame, _point
from .step_parser import Ref
from .vecteurs import add, cross, dot, mul, norm, sub, unit, unit_robuste


# ============================================================================
# SURFACES DE REVOLUTION ET D'EXTRUSION (génératrice B-spline, cercle, ellipse)
# ============================================================================
#
# Beaucoup de CAD exportent les congés et raccords sous forme de
# SURFACE_OF_REVOLUTION dont la génératrice est une B-spline, même lorsque la
# forme est un tore. Ces surfaces sont traitées ici de façon générale :
#
#   revolution : S(theta, t) = O + rho(t) * e_r(theta) + z(t) * Z
#                normale = (z'(t) * e_r - rho'(t) * Z)   (= Su x Sv)
#   extrusion  : S(t, s) = C(t) + s * D          normale = C'(t) x D
#
# ============================================================================

class ProfileCurve(object):
    """Courbe génératrice : B-spline, cercle ou ellipse."""

    def __init__(self, step, cref):
        k = step.type_of(cref)
        self.periodic = False
        self.knots = None
        self._bs = None                 # B-spline (vectorisation numpy)
        self._cercle = None             # (repère, ra, rb) pour cercle/ellipse
        if any("B_SPLINE_CURVE" in t for t in step.types_of(cref)):
            c = BSplineCurve(step, cref)
            self.eval = c.eval
            self._bs = c
            self._derivee = c.eval_d
            self.t0, self.t1 = c.t0, c.t1
            self.knots = sorted(set(c.knots))
            self.kind = "B_SPLINE_CURVE"
        elif k in ("CIRCLE", "ELLIPSE"):
            a = step.get(cref, k)
            f = Frame(step, a[1])
            ra = float(a[2])
            rb = float(a[3]) if k == "ELLIPSE" else ra
            self.eval = lambda t: add(
                f.o,
                add(mul(f.x, ra * math.cos(t)), mul(f.y, rb * math.sin(t))),
            )
            self._derivee = lambda t: add(
                mul(f.x, -ra * math.sin(t)),
                mul(f.y, rb * math.cos(t)),
            )
            self.t0, self.t1 = 0.0, 2.0 * math.pi
            self.periodic = True
            self.kind = k
            self.radius = ra if k == "CIRCLE" else None
            self._cercle = (f, ra, rb)
            self.center = f.o
            self.normal = f.z
        else:
            raise ValueError("génératrice non gérée : %s" % k)

    def clamp(self, t):
        if self.periodic:
            return t
        return min(max(t, self.t0), self.t1)

    def d(self, t):
        """Dérivée dP/dt (analytique)."""
        return self._derivee(t)


class RevolutionProfile(object):
    """SURFACE_OF_REVOLUTION : u = angle theta, v = paramètre t de la génératrice."""

    def __init__(self, step, ref):
        a = step.get(ref, "SURFACE_OF_REVOLUTION")
        self.curve = ProfileCurve(step, a[1])
        ax = step.get(a[2], "AXIS1_PLACEMENT")
        self.o = _point(step, ax[1])
        z = _point(step, ax[2]) if len(ax) > 2 and isinstance(ax[2], Ref) else (0.0, 0.0, 1.0)
        self.z = unit(z)
        xr = (1.0, 0.0, 0.0) if abs(self.z[0]) < 0.9 else (0.0, 1.0, 0.0)
        self.x = unit(sub(xr, mul(self.z, dot(xr, self.z))))
        self.y = cross(self.z, self.x)
        n = 256
        self._table = []
        for i in range(n + 1):
            t = self.curve.t0 + (self.curve.t1 - self.curve.t0) * i / n
            r, zz, _, _ = self.rz(t)
            self._table.append((t, r, zz))

    def rz(self, t):
        """(rho, z, drho/dt, dz/dt) de la génératrice."""
        c = self.curve
        p = c.eval(t)
        d = sub(p, self.o)
        z = dot(d, self.z)
        rv = sub(d, mul(self.z, z))
        rho = norm(rv)
        dp = c.d(t)
        ur = unit(rv)
        drho = dot(ur, dp) if ur is not None else 0.0
        return rho, z, drho, dot(dp, self.z)

    def _polar(self, p):
        d = sub(p, self.o)
        return math.atan2(dot(d, self.y), dot(d, self.x)), dot(d, self.z), \
            norm(sub(d, mul(self.z, dot(d, self.z))))

    def project(self, p, hint=None):
        """Paramètre t de la génératrice le plus proche de (rho_p, z_p)."""
        _, zp, rp = self._polar(p)
        c = self.curve
        if hint is None:
            best, t = float("inf"), c.t0
            for tt, r, z in self._table:
                dd = (r - rp) ** 2 + (z - zp) ** 2
                if dd < best:
                    best, t = dd, tt
        else:
            t = hint
        span = c.t1 - c.t0
        for _ in range(40):
            r, z, dr, dz = self.rz(t)
            g = dr * dr + dz * dz
            if g < 1e-30:
                break
            dt = -((r - rp) * dr + (z - zp) * dz) / g
            t = c.clamp(t + dt)
            if abs(dt) < 1e-13 * span:
                break
        return t

    def derivs(self, u, t):
        rho, z, drho, dz = self.rz(t)
        cu, su = math.cos(u), math.sin(u)
        er = add(mul(self.x, cu), mul(self.y, su))
        et = add(mul(self.x, -su), mul(self.y, cu))
        S = add(self.o, add(mul(er, rho), mul(self.z, z)))
        return S, mul(et, rho), add(mul(er, drho), mul(self.z, dz))

    def normal(self, p):
        th, _, rp = self._polar(p)
        if rp < 1e-12:
            return None
        t = self.project(p)
        _, _, dr, dz = self.rz(t)
        er = add(mul(self.x, math.cos(th)), mul(self.y, math.sin(th)))
        return unit_robuste(sub(mul(er, dz), mul(self.z, dr)))

    def fit_circle(self, t_lo=None, t_hi=None, n=80):
        """Cercle (rho_c, z_c, r) ajusté sur la génératrice (moindres carrés).

        Permet de reconnaître un tore (ou une sphère) exporté en surface de
        révolution. Retourne None si l'ajustement est impossible.
        """
        c = self.curve
        lo = c.t0 if t_lo is None or not math.isfinite(t_lo) else max(c.t0, t_lo)
        hi = c.t1 if t_hi is None or not math.isfinite(t_hi) else min(c.t1, t_hi)
        if hi - lo < 1e-12:
            lo, hi = c.t0, c.t1
        pts = []
        for i in range(n + 1):
            t = lo + (hi - lo) * i / n
            r, z, _, _ = self.rz(t)
            pts.append((r, z))
        sx = sum(p[0] for p in pts)
        sy = sum(p[1] for p in pts)
        sxx = sum(p[0] ** 2 for p in pts)
        syy = sum(p[1] ** 2 for p in pts)
        sxy = sum(p[0] * p[1] for p in pts)
        q = [p[0] ** 2 + p[1] ** 2 for p in pts]
        b = [-sum(q[i] * pts[i][0] for i in range(len(pts))),
             -sum(q[i] * pts[i][1] for i in range(len(pts))),
             -sum(q)]
        A = [[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, float(len(pts))]]
        # résolution 3x3 (élimination de Gauss avec pivot)
        M = [A[i][:] + [b[i]] for i in range(3)]
        for i in range(3):
            piv = max(range(i, 3), key=lambda r_: abs(M[r_][i]))
            if abs(M[piv][i]) < 1e-14:
                return None
            M[i], M[piv] = M[piv], M[i]
            for r_ in range(i + 1, 3):
                f = M[r_][i] / M[i][i]
                for c_ in range(i, 4):
                    M[r_][c_] -= f * M[i][c_]
        sol = [0.0] * 3
        for i in (2, 1, 0):
            sol[i] = (M[i][3] - sum(M[i][j] * sol[j] for j in range(i + 1, 3))) / M[i][i]
        D, E, F = sol
        cx, cy = -D / 2.0, -E / 2.0
        r2 = cx * cx + cy * cy - F
        if r2 <= 0:
            return None
        rad = math.sqrt(r2)
        dev = max(abs(math.hypot(p[0] - cx, p[1] - cy) - rad) for p in pts)
        return {"rho_c": cx, "z_c": cy, "rayon": rad, "ecart_max": dev}


class ExtrusionProfile(object):
    """SURFACE_OF_LINEAR_EXTRUSION : u = t (génératrice), v = s (distance le long de D)."""

    def __init__(self, step, ref):
        a = step.get(ref, "SURFACE_OF_LINEAR_EXTRUSION")
        self.curve = ProfileCurve(step, a[1])
        v = step.get(a[2], "VECTOR")
        self.d = unit(_point(step, v[1]))
        n = 256
        self._table = [
            (self.curve.t0 + (self.curve.t1 - self.curve.t0) * i / n,
             self.curve.eval(self.curve.t0 + (self.curve.t1 - self.curve.t0) * i / n))
            for i in range(n + 1)
        ]

    def _perp(self, w):
        return sub(w, mul(self.d, dot(w, self.d)))

    def project(self, p, hint=None):
        c = self.curve
        if hint is None:
            best, t = float("inf"), c.t0
            for tt, q in self._table:
                w = self._perp(sub(q, p))
                dd = dot(w, w)
                if dd < best:
                    best, t = dd, tt
        else:
            t = hint
        span = c.t1 - c.t0
        for _ in range(40):
            w = self._perp(sub(c.eval(t), p))
            dw = self._perp(c.d(t))
            g = dot(dw, dw)
            if g < 1e-30:
                break
            dt = -dot(w, dw) / g
            t = c.clamp(t + dt)
            if abs(dt) < 1e-13 * span:
                break
        return t

    def derivs(self, t, s):
        c = self.curve
        return add(c.eval(t), mul(self.d, s)), c.d(t), self.d

    def normal(self, p):
        t = self.project(p)
        return unit_robuste(cross(self.curve.d(t), self.d))
