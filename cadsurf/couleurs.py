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

"""Génération des couleurs des groupes.
"""

import colorsys
import math
import random

from .config import GRIS


# ============================================================================
# COULEURS
# ============================================================================

def random_light_color(
    used,
    rng
):

    # On utilise la roue HSV afin d'obtenir
    # beaucoup de couleurs différentes.
    for _ in range(100):

        h = rng.random()

        # Saturation raisonnable
        s = rng.uniform(
            0.45,
            0.72
        )

        # Luminosité élevée
        v = rng.uniform(
            0.88,
            0.98
        )

        rgb = colorsys.hsv_to_rgb(
            h,
            s,
            v
        )

        # Evite les couleurs trop proches
        good = True

        for c in used:

            d = math.sqrt(
                sum(
                    (
                        rgb[i]
                        - c[i]
                    ) ** 2
                    for i in range(3)
                )
            )

            if d < 0.12:

                good = False
                break

        if good:
            return rgb

    # Fallback déterministe
    h = (
        len(used)
        * 0.61803398875
    ) % 1.0

    return colorsys.hsv_to_rgb(
        h,
        0.55,
        0.95
    )


def create_group_colors(
    groups,
    color_singletons=False
):

    rng = random.Random(
        20261009
    )

    colors = {}

    used = []

    for index, group in enumerate(
        groups,
        start=1
    ):

        if (
            len(group) == 1
            and not color_singletons
        ):

            colors[index] = GRIS

        else:

            rgb = random_light_color(
                used,
                rng
            )

            colors[index] = rgb

            used.append(
                rgb
            )

    return colors
