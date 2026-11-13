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

"""Géométrie des arêtes : point(t), longueur, boîte englobante.
"""

import math

from . import accel
from .bsplines import BSplineCurve
from .config import TWO_PI, _GL6
from .reperes import Frame
from .topologie import vertex_point
from .vecteurs import add, dist, dot, mul, sub


def _refine_bspline_param(curve, p):
    """Paramètre de la B-spline le plus proche du point p (précision ~1e-13).

    Balayage grossier de 401 échantillons (vectorisé si numpy), puis Newton
    dans la maille voisine ; l'ancienne recherche ternaire sert de repli."""
    n = 400
    t0, t1 = curve.t0, curve.t1
    bt, best = t0, float("inf")
    fait = False
    if accel.UTILISER:
        try:
            from . import vectoriel
            np = vectoriel.np
            vc = getattr(curve, "_vec_np", None)
            if vc is None:
                vc = curve._vec_np = vectoriel.CourbeBS(curve)
            ts = t0 + (t1 - t0) * np.arange(n + 1) / n
            d = np.linalg.norm(vc.eval(ts) - np.asarray(p, float), axis=1)
            i = int(d.argmin())
            bt, best, fait = float(ts[i]), float(d[i]), True
        except Exception:
            accel.REPLIS += 1
    if not fait:
        for i in range(n + 1):
            t = t0 + (t1 - t0) * i / n
            d = dist(curve.eval(t), p)
            if d < best:
                best, bt = d, t
    dt = (t1 - t0) / n
    lo, hi = max(t0, bt - dt), min(t1, bt + dt)
    t, converge = bt, False
    for _ in range(30):
        ecart = sub(curve.eval(t), p)
        dp = curve.eval_d(t)
        g = dot(dp, dp)
        if g < 1e-30:
            break
        nt = min(max(t - dot(ecart, dp) / g, lo), hi)
        if abs(nt - t) < 1e-14 * (t1 - t0):
            t, converge = nt, True
            break
        t = nt
    if converge and dist(curve.eval(t), p) <= best + 1e-12:
        return t
    for _ in range(80):                          # repli : recherche ternaire
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if dist(curve.eval(m1), p) < dist(curve.eval(m2), p):
            hi = m2
        else:
            lo = m1
    return 0.5 * (lo + hi)


class EdgeGeom(object):
    """Géométrie d'une EDGE_CURVE.

    point(t), t dans [0, 1], parcourt l'arête du sommet 1 vers le sommet 2.
    """

    def __init__(self, step, ref):
        self.ref = ref
        ea = step.get(ref, "EDGE_CURVE")
        if ea is None:
            raise ValueError("EDGE_CURVE #%s introuvable" % ref)
        self.p1 = vertex_point(step, ea[1])
        self.p2 = vertex_point(step, ea[2])
        cref = ea[3]
        for _ in range(5):          # SURFACE_CURVE -> courbe 3D
            if step.type_of(cref) in ("SURFACE_CURVE", "SEAM_CURVE", "INTERSECTION_CURVE"):
                cref = step.get(cref, step.type_of(cref))[1]
            else:
                break
        self.curve_ref = cref
        same = (str(ea[4]).upper() == "T")
        k = step.type_of(cref)
        self.kind = k
        self.exact = True
        self.degenerate = False
        self.n_sub = 12
        closed = dist(self.p1, self.p2) < 1e-7

        if k == "LINE":
            self.n_sub = 1
            self.degenerate = dist(self.p1, self.p2) < 1e-12
            self._pt = lambda t: add(mul(self.p1, 1.0 - t), mul(self.p2, t))
        elif k in ("CIRCLE", "ELLIPSE"):
            a = step.get(cref, k)
            f = Frame(step, a[1])
            ra = float(a[2])
            rb = float(a[3]) if k == "ELLIPSE" else ra
            self.frame, self.ra, self.rb = f, ra, rb

            def ang(p):
                v = sub(p, f.o)
                return math.atan2(dot(v, f.y) / rb, dot(v, f.x) / ra)

            a1, a2 = ang(self.p1), ang(self.p2)
            if same:                     # sens trigonométrique
                if closed:
                    a2 = a1 + TWO_PI
                else:
                    while a2 <= a1:
                        a2 += TWO_PI
            else:                        # sens horaire
                if closed:
                    a2 = a1 - TWO_PI
                else:
                    while a2 >= a1:
                        a2 -= TWO_PI
            self.a1, self.a2 = a1, a2
            self._pt = lambda t: add(
                f.o,
                add(
                    mul(f.x, ra * math.cos(a1 + (a2 - a1) * t)),
                    mul(f.y, rb * math.sin(a1 + (a2 - a1) * t)),
                ),
            )
        elif any("B_SPLINE_CURVE" in t for t in step.types_of(cref)):
            c = BSplineCurve(step, cref)
            self.curve = c
            if closed:
                ts, te = (c.t0, c.t1) if same else (c.t1, c.t0)
            else:
                ts, te = _refine_bspline_param(c, self.p1), _refine_bspline_param(c, self.p2)
            self.ts, self.te = ts, te
            self.n_sub = 24
            self._pt = lambda t: c.eval(ts + (te - ts) * t)
        else:                            # courbe non gérée : corde
            self.exact = False
            self._pt = lambda t: add(mul(self.p1, 1.0 - t), mul(self.p2, t))

    def point(self, t):
        return self._pt(t)

    def tangent(self, t):
        """dP/dt de l'arête du sommet 1 vers le sommet 2 (analytique)."""
        k = self.kind
        if k in ("CIRCLE", "ELLIPSE") and self.exact:
            da = self.a2 - self.a1
            a = self.a1 + da * t
            f = self.frame
            return add(
                mul(f.x, -self.ra * math.sin(a) * da),
                mul(f.y, self.rb * math.cos(a) * da),
            )
        if hasattr(self, "curve"):
            return mul(
                self.curve.eval_d(self.ts + (self.te - self.ts) * t),
                self.te - self.ts,
            )
        return sub(self.p2, self.p1)      # droite (ou corde d'une courbe non gérée)

    def tangent_o(self, orient, t):
        """Tangente de l'arête orientée (arête parcourue à l'envers si orient=False)."""
        if orient:
            return self.tangent(t)
        return mul(self.tangent(1.0 - t), -1.0)

    def point_o(self, orient, t):
        """Point de l'arête orientée (orient=False : parcourue à l'envers)."""
        return self._pt(t if orient else 1.0 - t)

    def length(self):
        if getattr(self, "_length_cache", None) is None:
            self._length_cache = self._length()
        return self._length_cache

    def _length(self):
        if self.kind == "LINE":
            return dist(self.p1, self.p2)
        if self.kind == "CIRCLE":
            return self.ra * abs(self.a2 - self.a1)
        if hasattr(self, "curve") and accel.UTILISER:
            try:
                from . import vectoriel
                return vectoriel.longueur_courbe_bs(self)
            except Exception:
                accel.REPLIS += 1
        K = 24 if self.kind != "B_SPLINE_CURVE" and not hasattr(self, "curve") else 64
        h, total = 1e-6, 0.0
        for k in range(K):
            a, b = k / float(K), (k + 1) / float(K)
            half, mid = (b - a) / 2.0, (a + b) / 2.0
            for x, w in _GL6:
                t = mid + half * x
                t0, t1 = max(0.0, t - h), min(1.0, t + h)
                total += w * half * dist(self._pt(t1), self._pt(t0)) / (t1 - t0)
        return total

    def bbox(self):
        if getattr(self, "_bbox_cache", None) is None:
            self._bbox_cache = self._bbox()
        return self._bbox_cache

    def _bbox(self):
        """Boîte englobante (exacte pour droites et cercles, dense sinon)."""
        pts = [self.p1, self.p2]
        if self.kind in ("CIRCLE", "ELLIPSE"):
            f = self.frame
            for c in range(3):
                astar = math.atan2(self.rb * f.y[c], self.ra * f.x[c])
                for a in (astar, astar + math.pi):
                    if self.a2 >= self.a1:
                        d, span = (a - self.a1) % TWO_PI, self.a2 - self.a1
                    else:
                        d, span = (self.a1 - a) % TWO_PI, self.a1 - self.a2
                    if d <= span + 1e-12:
                        pts.append(
                            add(
                                f.o,
                                add(
                                    mul(f.x, self.ra * math.cos(a)),
                                    mul(f.y, self.rb * math.sin(a)),
                                ),
                            )
                        )
        elif self.kind != "LINE":
            vec = None
            if hasattr(self, "curve") and accel.UTILISER:
                try:
                    from . import vectoriel
                    vec = [tuple(p) for p in vectoriel.echantillon_courbe_bs(self).tolist()]
                except Exception:
                    accel.REPLIS += 1
            pts += vec if vec is not None else [self._pt(i / 400.0) for i in range(401)]
        lo = tuple(min(p[i] for p in pts) for i in range(3))
        hi = tuple(max(p[i] for p in pts) for i in range(3))
        return lo, hi
