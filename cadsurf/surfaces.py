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

"""Enveloppe Surface : type, paramètres et normale en un point pour chaque
surface STEP gérée.
"""

import math

from .bsplines import BSplineSurface
from .profils import ExtrusionProfile, RevolutionProfile
from .reperes import Frame
from .vecteurs import add, dot, mul, sub, unit


class Surface(object):

    def __init__(
        self,
        step,
        ref
    ):

        self.ref = ref

        self.kind = step.type_of(
            ref
        )

        self.params = {}

        self.supported = True

        if self.kind == "PLANE":

            a = step.get(
                ref,
                "PLANE"
            )

            self.frame = Frame(
                step,
                a[1]
            )

            self.nfun = (
                lambda p:
                self.frame.z
            )

        elif self.kind == "CYLINDRICAL_SURFACE":

            a = step.get(
                ref,
                "CYLINDRICAL_SURFACE"
            )

            self.frame = Frame(
                step,
                a[1]
            )

            self.radius = float(
                a[2]
            )

            self.params = {
                "rayon": self.radius
            }

            self.nfun = self.cylinder_normal

        elif self.kind == "CONICAL_SURFACE":

            a = step.get(
                ref,
                "CONICAL_SURFACE"
            )

            self.frame = Frame(
                step,
                a[1]
            )

            self.radius = float(
                a[2]
            )

            self.angle = float(
                a[3]
            )

            self.params = {
                "rayon": self.radius,
                "demi_angle_rad": self.angle
            }

            self.nfun = self.cone_normal

        elif self.kind == "SPHERICAL_SURFACE":

            a = step.get(
                ref,
                "SPHERICAL_SURFACE"
            )

            self.frame = Frame(
                step,
                a[1]
            )

            self.radius = float(
                a[2]
            )

            self.params = {
                "rayon": self.radius
            }

            self.nfun = self.sphere_normal

        elif self.kind in (
            "TOROIDAL_SURFACE",
            "DEGENERATE_TOROIDAL_SURFACE"
        ):

            a = step.get(
                ref,
                self.kind
            )

            self.frame = Frame(
                step,
                a[1]
            )

            self.major_radius = float(
                a[2]
            )

            self.minor_radius = float(
                a[3]
            )

            self.params = {
                "R_majeur":
                    self.major_radius,
                "r_mineur":
                    self.minor_radius
            }

            self.nfun = self.torus_normal

        elif self.kind == "SURFACE_OF_REVOLUTION":
            try:
                self.rev = RevolutionProfile(step, ref)
                self.frame = self.rev
                self.params = {
                    "axe_direction": list(self.rev.z)
                }
                self.nfun = self.rev.normal
            except Exception:
                self.supported = False
                self.nfun = lambda p: None
        elif self.kind == "SURFACE_OF_LINEAR_EXTRUSION":
            try:
                self.ext = ExtrusionProfile(step, ref)
                self.nfun = self.ext.normal
            except Exception:
                self.supported = False
                self.nfun = lambda p: None
        elif any(
            "B_SPLINE_SURFACE" in t
            for t in step.types_of(ref)
        ):

            self.kind = "B_SPLINE_SURFACE"

            try:

                self.bs = BSplineSurface(
                    step,
                    ref
                )

                self.nfun = (
                    self.bs.normal
                )

            except Exception:

                self.supported = False
                self.nfun = lambda p: None

        else:

            self.supported = False
            self.nfun = lambda p: None

    def radial(
        self,
        p
    ):

        v = sub(
            p,
            self.frame.o
        )

        return sub(
            v,
            mul(
                self.frame.z,
                dot(
                    v,
                    self.frame.z
                )
            )
        )

    def cylinder_normal(
        self,
        p
    ):

        return unit(
            self.radial(p)
        )

    def cone_normal(
        self,
        p
    ):

        r = unit(
            self.radial(p)
        )

        if r is None:
            return None

        return unit(
            sub(
                mul(
                    r,
                    math.cos(self.angle)
                ),
                mul(
                    self.frame.z,
                    math.sin(self.angle)
                )
            )
        )

    def sphere_normal(
        self,
        p
    ):

        return unit(
            sub(
                p,
                self.frame.o
            )
        )

    def torus_normal(
        self,
        p
    ):

        r = unit(
            self.radial(p)
        )

        if r is None:
            return None

        center = add(
            self.frame.o,
            mul(
                r,
                self.major_radius
            )
        )

        return unit(
            sub(
                p,
                center
            )
        )

    def normal(
        self,
        p
    ):

        if not self.supported:
            return None

        try:
            return self.nfun(p)
        except Exception:
            return None
