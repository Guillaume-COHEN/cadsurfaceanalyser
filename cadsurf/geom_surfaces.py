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

"""Paramétrage (u, v) des surfaces : S(u,v), dérivées, inversion, intégrales
intérieures (théorème de Green).
"""

import math

from .config import TWO_PI, _GL6, _KINDS_PERIODIQUES_U, _KINDS_TORE
from .vecteurs import add, cross, dist, dot, mul, norm, sub


class SurfParam(object):
    """Paramétrage (u, v) d'une surface : S(u,v), dérivées, inversion."""

    def __init__(self, surf):
        self.surf = surf
        self.kind = surf.kind
        self.f = getattr(surf, "frame", None)
        self.period_u = TWO_PI if self.kind in _KINDS_PERIODIQUES_U else None
        self.period_v = TWO_PI if self.kind in _KINDS_TORE else None
        self.is_bspline = (self.kind == "B_SPLINE_SURFACE")
        self.vstep = None
        self.vknots = None          # noeuds où couper l'intégrale intérieure
        self.vref0 = None           # v_ref imposé (sinon : v du premier point)
        self.numeric = self.is_bspline
        self.rev = None
        self.ext = None
        if self.kind == "SPHERICAL_SURFACE" or self.kind in _KINDS_TORE:
            self.vstep = math.pi / 2.0
        if self.is_bspline:
            self.bs = surf.bs
            self.ru = max(self.bs.u1 - self.bs.u0, 1e-12)
            self.rv = max(self.bs.v1 - self.bs.v0, 1e-12)
            self.vknots = sorted(set(self.bs.kv))
            self.vref0 = self.bs.v0
        if self.kind == "SURFACE_OF_REVOLUTION":
            self.rev = surf.rev
            self.numeric = True
            self.period_u = TWO_PI
            c = self.rev.curve
            self.vref0 = c.t0
            if c.knots is not None:
                self.vknots = c.knots
            else:
                self.vstep = math.pi / 2.0
        if self.kind == "SURFACE_OF_LINEAR_EXTRUSION":
            self.ext = surf.ext
            self.numeric = True
            if self.ext.curve.periodic:
                self.period_u = TWO_PI
        if self.kind == "CONICAL_SURFACE":
            self.tana = math.tan(surf.angle)

    # ---- S, Su, Sv --------------------------------------------------------
    def derivs(self, u, v):
        k, f = self.kind, self.f
        if self.rev is not None:
            return self.rev.derivs(u, v)
        if self.ext is not None:
            return self.ext.derivs(u, v)
        if k == "PLANE":
            S = add(f.o, add(mul(f.x, u), mul(f.y, v)))
            return S, f.x, f.y
        if self.is_bspline:
            return self.bs.eval_derivs(u, v)
        cu, su = math.cos(u), math.sin(u)
        er = add(mul(f.x, cu), mul(f.y, su))            # direction radiale
        et = add(mul(f.x, -su), mul(f.y, cu))           # direction tangentielle
        if k == "CYLINDRICAL_SURFACE":
            R = self.surf.radius
            return add(add(f.o, mul(er, R)), mul(f.z, v)), mul(et, R), f.z
        if k == "CONICAL_SURFACE":
            r = self.surf.radius + v * self.tana
            S = add(add(f.o, mul(er, r)), mul(f.z, v))
            return S, mul(et, r), add(mul(er, self.tana), f.z)
        if k == "SPHERICAL_SURFACE":
            R = self.surf.radius
            cv, sv = math.cos(v), math.sin(v)
            S = add(f.o, add(mul(er, R * cv), mul(f.z, R * sv)))
            Su = mul(et, R * cv)
            Sv = add(mul(er, -R * sv), mul(f.z, R * cv))
            return S, Su, Sv
        # tore
        R, r = self.surf.major_radius, self.surf.minor_radius
        cv, sv = math.cos(v), math.sin(v)
        rho = R + r * cv
        S = add(f.o, add(mul(er, rho), mul(f.z, r * sv)))
        Su = mul(et, rho)
        Sv = add(mul(er, -r * sv), mul(f.z, r * cv))
        return S, Su, Sv

    # ---- inversion --------------------------------------------------------
    def inverse(self, p, hint=None):
        k, f = self.kind, self.f
        if self.rev is not None:
            th = self.rev._polar(p)[0]
            return (th, self.rev.project(p, hint[1] if hint else None))
        if self.ext is not None:
            t = self.ext.project(p, hint[0] if hint else None)
            return (t, dot(sub(p, self.ext.curve.eval(t)), self.ext.d))
        if self.is_bspline:
            return self._bspline_inverse(p, hint)
        d = sub(p, f.o)
        if k == "PLANE":
            return (dot(d, f.x), dot(d, f.y))
        dx, dy, dz = dot(d, f.x), dot(d, f.y), dot(d, f.z)
        u = math.atan2(dy, dx)
        if k in ("CYLINDRICAL_SURFACE", "CONICAL_SURFACE"):
            return (u, dz)
        rho = math.hypot(dx, dy)
        if k == "SPHERICAL_SURFACE":
            return (u, math.atan2(dz, rho))
        return (u, math.atan2(dz, rho - self.surf.major_radius))

    def _bspline_inverse(self, p, hint):
        b = self.bs
        if hint is None:
            u, v = b.project(p)
        else:
            u, v = hint
        for _ in range(14):
            S, Su, Sv = self.derivs(u, v)
            r = sub(S, p)
            a11, a12, a22 = dot(Su, Su), dot(Su, Sv), dot(Sv, Sv)
            b1, b2 = -dot(Su, r), -dot(Sv, r)
            det = a11 * a22 - a12 * a12
            if abs(det) < 1e-30:
                break
            du = (b1 * a22 - b2 * a12) / det
            dv = (a11 * b2 - a12 * b1) / det
            u, v = b.clamp(u + du, v + dv)
            if abs(du) < 1e-12 * self.ru and abs(dv) < 1e-12 * self.rv:
                break
        if hint is not None and dist(self.derivs(u, v)[0], p) > 1e-3:
            u, v = b.project(p)                 # Newton perdu : reprise globale
        return (u, v)

    def param_velocity(self, uv, dP):
        """(du/dt, dv/dt) d'un point qui se déplace sur la surface avec la
        vitesse 3D `dP` : moindres carrés  [Su Sv] (du, dv) = dP.
        None si le paramétrage est dégénéré (le calcul par différences
        d'inversions prend alors le relais)."""
        S, Su, Sv = self.derivs(uv[0], uv[1])
        a11, a12, a22 = dot(Su, Su), dot(Su, Sv), dot(Sv, Sv)
        det = a11 * a22 - a12 * a12
        if det <= 1e-12 * a11 * a22 or a11 * a22 == 0.0:
            return None
        b1, b2 = dot(Su, dP), dot(Sv, dP)
        return ((b1 * a22 - b2 * a12) / det, (a11 * b2 - a12 * b1) / det)

    def unwrap(self, uv, ref):
        u, v = uv
        if ref is not None:
            if self.period_u:
                u += TWO_PI * round((ref[0] - u) / TWO_PI)
            if self.period_v:
                v += TWO_PI * round((ref[1] - v) / TWO_PI)
        return (u, v)

    def default_vref(self, uv):
        return self.vref0 if self.vref0 is not None else uv[1]

    # ---- intégrandes ------------------------------------------------------
    def channels(self, u, v):
        return self._canaux(*self.derivs(u, v))

    def _canaux(self, S, Su, Sv):
        N = cross(Su, Sv)
        w = norm(N)
        return (w, w * S[0], w * S[1], w * S[2], N[0], N[1], N[2], dot(S, N) / 3.0)

    def inner(self, u, v, vref):
        """G(u, v) = integrale de g(u, v') dv' de vref à v (8 canaux)."""
        if v == vref:
            return [0.0] * 8
        lo, hi, sign = vref, v, 1.0
        if hi < lo:
            lo, hi, sign = hi, lo, -1.0
        if self.vknots is not None:
            ks = [x for x in self.vknots if lo < x < hi]
            br = [lo] + ks + [hi]
        elif self.vstep:
            n = max(1, int(math.ceil((hi - lo) / self.vstep)))
            br = [lo + (hi - lo) * i / n for i in range(n + 1)]
        else:
            br = [lo, hi]
        acc = [0.0] * 8
        ctx_u = self.bs.prepare_u(u) if self.is_bspline else None
        for a, b in zip(br, br[1:]):
            half, mid = (b - a) / 2.0, (a + b) / 2.0
            for x, w in _GL6:
                if ctx_u is not None:
                    # u fixé : base en u calculée une seule fois
                    ch = self._canaux(*self.bs.eval_derivs_u(ctx_u, mid + half * x))
                else:
                    ch = self.channels(u, mid + half * x)
                wt = w * half
                for i in range(8):
                    acc[i] += ch[i] * wt
        return [sign * c for c in acc]
