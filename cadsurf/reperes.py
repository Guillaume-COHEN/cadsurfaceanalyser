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

"""Points et repères (AXIS2_PLACEMENT_3D) lus dans le fichier STEP.
"""

from .step_parser import Ref
from .vecteurs import cross, dot, mul, sub, unit


# ============================================================================
# POINTS STEP
# ============================================================================

def _point(step, ref):

    a = step.get(
        ref,
        "CARTESIAN_POINT",
        "DIRECTION"
    )

    if a is None:
        raise ValueError(
            "Point/direction introuvable #%s"
            % ref
        )

    c = a[1]

    return (
        float(c[0]),
        float(c[1]),
        float(c[2])
        if len(c) > 2
        else 0.0
    )


# ============================================================================
# REPERE
# ============================================================================

class Frame(object):

    def __init__(
        self,
        step,
        ref
    ):

        a = step.get(
            ref,
            "AXIS2_PLACEMENT_3D"
        )

        if a is None:
            raise ValueError(
                "AXIS2_PLACEMENT_3D introuvable"
            )

        self.o = _point(
            step,
            a[1]
        )

        self.z = unit(
            _point(
                step,
                a[2]
            )
        )

        if self.z is None:
            self.z = (
                0.0,
                0.0,
                1.0
            )

        if (
            len(a) > 3
            and isinstance(a[3], Ref)
        ):

            xr = _point(
                step,
                a[3]
            )

        else:

            xr = (
                1.0,
                0.0,
                0.0
            )

            if abs(
                dot(xr, self.z)
            ) > 0.9:
                xr = (
                    0.0,
                    1.0,
                    0.0
                )

        x = sub(
            xr,
            mul(
                self.z,
                dot(xr, self.z)
            )
        )

        self.x = unit(x)

        if self.x is None:
            self.x = (
                1.0,
                0.0,
                0.0
            )

        self.y = unit(
            cross(
                self.z,
                self.x
            )
        )
