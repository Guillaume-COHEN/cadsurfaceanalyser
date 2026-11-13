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

"""B-splines (courbes et surfaces, rationnelles ou non) : évaluation de Boor,
projection de points.
"""

from . import accel
from .config import EPS
from .reperes import _point
from .vecteurs import cross, dist, dot, mul, norm, sub, unit, unit_robuste


# ============================================================================
# B-SPLINE CURVES
# ============================================================================

def expand_knots(
    multiplicities,
    knots
):

    out = []

    for m, k in zip(
        multiplicities,
        knots
    ):

        out.extend(
            [float(k)] * int(m)
        )

    return out


def clamped_knots(
    n_ctrl,
    degree
):

    inner = (
        n_ctrl
        - degree
        - 1
    )

    knots = (
        [0.0] * (degree + 1)
    )

    knots += [
        float(i)
        for i in range(
            1,
            inner + 1
        )
    ]

    knots += [
        float(inner + 1)
    ] * (degree + 1)

    return knots


def find_span(
    degree,
    knots,
    t
):

    n = (
        len(knots)
        - degree
        - 2
    )

    if t >= knots[n + 1]:
        return n

    if t <= knots[degree]:
        return degree

    lo = degree
    hi = n + 1

    while True:

        mid = (
            lo + hi
        ) // 2

        if (
            t < knots[mid]
        ):
            hi = mid

        elif (
            t >= knots[mid + 1]
        ):
            lo = mid

        else:
            return mid


def basis_funs(span, t, degree, knots):
    """Valeurs des degree+1 fonctions de base non nulles en t
    (NURBS Book, algorithme A2.2). Seuls les points de contrôle d'indices
    span-degree .. span interviennent."""
    N = [0.0] * (degree + 1)
    left = [0.0] * (degree + 1)
    right = [0.0] * (degree + 1)
    N[0] = 1.0
    for j in range(1, degree + 1):
        left[j] = t - knots[span + 1 - j]
        right[j] = knots[span + j] - t
        saved = 0.0
        for r in range(j):
            temp = N[r] / (right[r + 1] + left[j - r])
            N[r] = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        N[j] = saved
    return N


def basis_funs_d1(span, t, degree, knots):
    """Fonctions de base et leurs dérivées premières en t."""
    N = basis_funs(span, t, degree, knots)
    dN = [0.0] * (degree + 1)
    if degree == 0:
        return N, dN
    Nm = basis_funs(span, t, degree - 1, knots)      # degré - 1
    for j in range(degree + 1):
        i = span - degree + j
        a = 0.0
        if j >= 1:
            den = knots[i + degree] - knots[i]
            if den != 0.0:
                a = Nm[j - 1] / den
        b = 0.0
        if j <= degree - 1:
            den = knots[i + degree + 1] - knots[i + 1]
            if den != 0.0:
                b = Nm[j] / den
        dN[j] = degree * (a - b)
    return N, dN


def deboor(
    degree,
    knots,
    ctrl,
    t
):

    k = find_span(
        degree,
        knots,
        t
    )

    d = [
        list(
            ctrl[
                j + k - degree
            ]
        )
        for j in range(
            degree + 1
        )
    ]

    for r in range(
        1,
        degree + 1
    ):

        for j in range(
            degree,
            r - 1,
            -1
        ):

            i = (
                j
                + k
                - degree
            )

            den = (
                knots[
                    i + degree - r + 1
                ]
                - knots[i]
            )

            if abs(den) < EPS:
                alpha = 0.0
            else:
                alpha = (
                    t
                    - knots[i]
                ) / den

            d[j] = [
                (
                    1.0 - alpha
                ) * d[j - 1][c]
                + alpha * d[j][c]
                for c in range(
                    len(d[j])
                )
            ]

    return d[degree]


def _dehomog4(x, y, z, w):
    """Comme dehomog, sur quatre composantes déjà séparées."""
    if abs(w) < EPS:
        return (x, y, z)
    return (x / w, y / w, z / w)


def homog(p, w):

    return [
        p[0] * w,
        p[1] * w,
        p[2] * w,
        w
    ]


def dehomog(p):

    w = p[3]

    if abs(w) < EPS:
        return (
            p[0],
            p[1],
            p[2]
        )

    return (
        p[0] / w,
        p[1] / w,
        p[2] / w
    )


class BSplineCurve(object):

    def __init__(
        self,
        step,
        ref
    ):

        a = step.get(
            ref,
            "B_SPLINE_CURVE",
            "B_SPLINE_CURVE_WITH_KNOTS"
        )

        self.degree = int(
            a[1]
        )

        pts = [
            _point(
                step,
                r
            )
            for r in a[2]
        ]

        rational = step.get(
            ref,
            "RATIONAL_B_SPLINE_CURVE"
        )

        weights = (
            list(rational[0])
            if rational
            else [1.0] * len(pts)
        )

        self.ctrl = [
            homog(
                p,
                w
            )
            for p, w in zip(
                pts,
                weights
            )
        ]

        k = step.get(
            ref,
            "B_SPLINE_CURVE_WITH_KNOTS"
        )

        if (
            k is not None
            and len(k) >= 8
        ):

            try:

                self.knots = expand_knots(
                    k[6],
                    k[7]
                )

            except Exception:

                self.knots = clamped_knots(
                    len(self.ctrl),
                    self.degree
                )

        else:

            self.knots = clamped_knots(
                len(self.ctrl),
                self.degree
            )

        self.t0 = self.knots[
            self.degree
        ]

        self.t1 = self.knots[
            -self.degree - 1
        ]

    def eval(self, t):
        p = self.degree
        k = find_span(p, self.knots, t)
        N = basis_funs(k, t, p, self.knots)
        ctrl, base = self.ctrl, k - p
        x = y = z = w = 0.0
        for j in range(p + 1):
            c = ctrl[base + j]
            f = N[j]
            x += f * c[0]
            y += f * c[1]
            z += f * c[2]
            w += f * c[3]
        return _dehomog4(x, y, z, w)

    def eval_d(self, t):
        """Dérivée dP/dt (analytique)."""
        p = self.degree
        k = find_span(p, self.knots, t)
        N, dN = basis_funs_d1(k, t, p, self.knots)
        ctrl, base = self.ctrl, k - p
        ax = ay = az = aw = 0.0
        bx = by = bz = bw = 0.0
        for j in range(p + 1):
            c = ctrl[base + j]
            f, g = N[j], dN[j]
            ax += f * c[0]
            ay += f * c[1]
            az += f * c[2]
            aw += f * c[3]
            bx += g * c[0]
            by += g * c[1]
            bz += g * c[2]
            bw += g * c[3]
        if abs(aw) < EPS:
            return (bx, by, bz)
        S = (ax / aw, ay / aw, az / aw)
        return (
            (bx - bw * S[0]) / aw,
            (by - bw * S[1]) / aw,
            (bz - bw * S[2]) / aw,
        )

    def param_of(
        self,
        p,
        n=200
    ):
        if accel.UTILISER:
            try:
                from . import vectoriel
                vc = getattr(self, "_vec_np", None)
                if vc is None:
                    vc = self._vec_np = vectoriel.CourbeBS(self)
                t = self.t0 + (self.t1 - self.t0) * vectoriel.np.arange(n + 1) / n
                d2 = ((vc.eval(t) - vectoriel.np.asarray(p, float)) ** 2).sum(axis=1)
                return float(t[int(d2.argmin())])
            except Exception:
                accel.REPLIS += 1

        best = float("inf")

        best_t = self.t0

        for i in range(n + 1):

            t = (
                self.t0
                + (
                    self.t1
                    - self.t0
                )
                * i
                / n
            )

            d = dist(
                self.eval(t),
                p
            )

            if d < best:

                best = d
                best_t = t

        return best_t


# ============================================================================
# B-SPLINE SURFACES
# ============================================================================

class BSplineSurface(object):

    GRID = 12

    def __init__(
        self,
        step,
        ref
    ):

        a = step.get(
            ref,
            "B_SPLINE_SURFACE",
            "B_SPLINE_SURFACE_WITH_KNOTS"
        )

        self.du = int(a[1])
        self.dv = int(a[2])

        grid = [
            [
                _point(step, r)
                for r in row
            ]
            for row in a[3]
        ]

        rational = step.get(
            ref,
            "RATIONAL_B_SPLINE_SURFACE"
        )

        if rational:

            weights = rational[0]

        else:

            weights = [
                [1.0] * len(row)
                for row in grid
            ]

        self.ctrl = [
            [
                homog(p, w)
                for p, w in zip(
                    row,
                    wrow
                )
            ]
            for row, wrow in zip(
                grid,
                weights
            )
        ]

        k = step.get(
            ref,
            "B_SPLINE_SURFACE_WITH_KNOTS"
        )

        if (
            k is not None
            and len(k) >= 12
        ):

            try:

                um = k[8]
                vm = k[9]
                uk = k[10]
                vk = k[11]

                self.ku = expand_knots(
                    um,
                    uk
                )

                self.kv = expand_knots(
                    vm,
                    vk
                )

            except Exception:

                self.ku = clamped_knots(
                    len(self.ctrl),
                    self.du
                )

                self.kv = clamped_knots(
                    len(self.ctrl[0]),
                    self.dv
                )

        else:

            self.ku = clamped_knots(
                len(self.ctrl),
                self.du
            )

            self.kv = clamped_knots(
                len(self.ctrl[0]),
                self.dv
            )

        self.u0 = self.ku[
            self.du
        ]

        self.u1 = self.ku[
            -self.du - 1
        ]

        self.v0 = self.kv[
            self.dv
        ]

        self.v1 = self.kv[
            -self.dv - 1
        ]

    def eval(
        self,
        u,
        v
    ):
        pu, pv = self.du, self.dv
        ku = find_span(pu, self.ku, u)
        kv = find_span(pv, self.kv, v)
        Nu = basis_funs(ku, u, pu, self.ku)
        Nv = basis_funs(kv, v, pv, self.kv)
        ctrl = self.ctrl
        bu, bv = ku - pu, kv - pv
        x = y = z = w = 0.0
        for a in range(pu + 1):
            row = ctrl[bu + a]
            na = Nu[a]
            for b in range(pv + 1):
                c = row[bv + b]
                f = na * Nv[b]
                x += f * c[0]
                y += f * c[1]
                z += f * c[2]
                w += f * c[3]
        return _dehomog4(x, y, z, w)

    def prepare_u(self, u):
        """Partie « u » de l'évaluation (intervalle, fonctions de base et
        dérivées), réutilisable pour plusieurs valeurs de v à u fixé."""
        pu = self.du
        ku = find_span(pu, self.ku, u)
        Nu, dNu = basis_funs_d1(ku, u, pu, self.ku)
        return ku, Nu, dNu

    def eval_derivs(
        self,
        u,
        v
    ):
        """(S, Su, Sv) : point et dérivées partielles analytiques (surface
        rationnelle ou non), en un seul passage."""
        return self.eval_derivs_u(self.prepare_u(u), v)

    def eval_derivs_u(self, ctx_u, v):
        """Comme eval_derivs, avec la partie « u » déjà préparée."""
        ku, Nu, dNu = ctx_u
        pu, pv = self.du, self.dv
        kv = find_span(pv, self.kv, v)
        Nv, dNv = basis_funs_d1(kv, v, pv, self.kv)
        ctrl = self.ctrl
        bu, bv = ku - pu, kv - pv
        A = [0.0, 0.0, 0.0, 0.0]
        Au = [0.0, 0.0, 0.0, 0.0]
        Av = [0.0, 0.0, 0.0, 0.0]
        for a in range(pu + 1):
            row = ctrl[bu + a]
            na, dna = Nu[a], dNu[a]
            for b in range(pv + 1):
                c = row[bv + b]
                f = na * Nv[b]
                fu = dna * Nv[b]
                fv = na * dNv[b]
                for q in range(4):
                    cq = c[q]
                    A[q] += f * cq
                    Au[q] += fu * cq
                    Av[q] += fv * cq
        w = A[3]
        if abs(w) < EPS:
            return (A[0], A[1], A[2]), (Au[0], Au[1], Au[2]), (Av[0], Av[1], Av[2])
        S = (A[0] / w, A[1] / w, A[2] / w)
        Su = tuple((Au[q] - Au[3] * S[q]) / w for q in range(3))
        Sv = tuple((Av[q] - Av[3] * S[q]) / w for q in range(3))
        return S, Su, Sv

    def clamp(
        self,
        u,
        v
    ):

        return (
            min(
                max(u, self.u0),
                self.u1
            ),
            min(
                max(v, self.v0),
                self.v1
            )
        )

    def _grille(self):
        """Points d'échantillonnage de la surface (calculés une seule fois)."""
        g = getattr(self, "_grille_cache", None)
        if g is None:
            G = self.GRID
            g = []
            for i in range(G + 1):
                u = self.u0 + (self.u1 - self.u0) * i / G
                for j in range(G + 1):
                    v = self.v0 + (self.v1 - self.v0) * j / G
                    x, y, z = self.eval(u, v)
                    g.append((u, v, x, y, z))
            self._grille_cache = g
        return g

    def project(
        self,
        p
    ):
        """Paramètres (u, v) du point de la surface le plus proche de p.

        Meilleur point de la grille (en cache), puis Gauss-Newton. Si le
        Newton ne converge pas, l'ancienne recherche par motifs reprend
        depuis le meilleur point de la grille."""
        px, py, pz = p
        best = float("inf")
        bu, bv = self.u0, self.v0
        for u, v, x, y, z in self._grille():
            d = (x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2
            if d < best:
                best, bu, bv = d, u, v
        u, v = bu, bv
        ru, rv = self.u1 - self.u0, self.v1 - self.v0
        for _ in range(40):
            S, Su, Sv = self.eval_derivs(u, v)
            r = (S[0] - px, S[1] - py, S[2] - pz)
            a11, a12, a22 = dot(Su, Su), dot(Su, Sv), dot(Sv, Sv)
            det = a11 * a22 - a12 * a12
            if a11 * a22 == 0.0 or det <= 1e-20 * a11 * a22:
                break
            b1, b2 = -dot(Su, r), -dot(Sv, r)
            nu, nv = self.clamp(
                u + (b1 * a22 - b2 * a12) / det,
                v + (a11 * b2 - a12 * b1) / det
            )
            fini = abs(nu - u) < 1e-11 * ru and abs(nv - v) < 1e-11 * rv
            u, v = nu, nv
            if fini:
                x, y, z = self.eval(u, v)
                if (x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2 <= best * (1.0 + 1e-9) + 1e-24:
                    return u, v
                break
        return self._project_motifs(p, bu, bv)

    def _project_motifs(self, p, bu, bv):
        """Ancienne recherche par motifs (repli), depuis (bu, bv)."""
        G = self.GRID
        best = dist(self.eval(bu, bv), p)
        su = (
            self.u1
            - self.u0
        ) / G

        sv = (
            self.v1
            - self.v0
        ) / G

        for _ in range(60):

            moved = False

            for du, dv in (
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1)
            ):

                u, v = self.clamp(
                    bu + du * su,
                    bv + dv * sv
                )

                d = dist(
                    self.eval(u, v),
                    p
                )

                if d < best:

                    best = d
                    bu = u
                    bv = v
                    moved = True

            if not moved:

                su *= 0.5
                sv *= 0.5

                if (
                    su < 1e-9
                    and sv < 1e-9
                ):
                    break

        return bu, bv

    def normal(
        self,
        p
    ):

        u, v = self.project(p)
        S, Su, Sv = self.eval_derivs(u, v)
        return unit_robuste(
            cross(Su, Sv),
            norm(Su) * norm(Sv)
        )
