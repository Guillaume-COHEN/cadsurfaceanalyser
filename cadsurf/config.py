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

"""Constantes partagées : échantillonnage, tolérances, gris, quadrature de Gauss,
libellés des types de surface.
"""

import math


# Points utilisés sur chaque arête :
# P1 et P5 sont volontairement exclus.
POSITIONS_ECHANTILLONNAGE = (0.25, 0.50, 0.75)


# Tolérance géométrique générale
EPS = 1.0e-4


# Gris pour les faces isolées
GRIS = (0.72, 0.72, 0.72)

# Sous-intervalles de l'intégration le long d'une arête, surfaces numériques
# (B-spline, révolution, extrusion). Plus petit = plus rapide, moins précis.
K_NUMERIQUE = 24

# Choix de précision (--precision-numerique) : nombre de sous-intervalles et
# erreur relative typique sur l'aire des faces B-spline (mesurée sur le coin) :
#   rapide   12   ~4e-6      standard 24   ~1e-6      fine 48   ~2e-9
PRECISIONS_NUMERIQUES = {"rapide": 12, "standard": 24, "fine": 48}

# Violet des faces B_SPLINE_SURFACE (--stp-bspline) : #8A2BE2
VIOLET = (0.541, 0.169, 0.886)


TWO_PI = 2.0 * math.pi


# Noeuds et poids de Gauss-Legendre à 6 points sur [-1, 1]
_GL6 = (
    (-0.9324695142031521, 0.1713244923791704),
    (-0.6612093864662645, 0.3607615730481386),
    (-0.2386191860831969, 0.4679139345726910),
    (0.2386191860831969, 0.4679139345726910),
    (0.6612093864662645, 0.3607615730481386),
    (0.9324695142031521, 0.1713244923791704),
)


LIBELLES_TYPES = {
    "PLANE": "Plan",
    "CYLINDRICAL_SURFACE": "Cylindre",
    "CONICAL_SURFACE": "Cône",
    "SPHERICAL_SURFACE": "Sphère",
    "TOROIDAL_SURFACE": "Tore",
    "DEGENERATE_TOROIDAL_SURFACE": "Tore dégénéré",
    "B_SPLINE_SURFACE": "Surface B-spline",
    "SURFACE_OF_REVOLUTION": "Surface de révolution",
    "SURFACE_OF_LINEAR_EXTRUSION": "Surface d'extrusion",
}


_KINDS_PERIODIQUES_U = (
    "CYLINDRICAL_SURFACE",
    "CONICAL_SURFACE",
    "SPHERICAL_SURFACE",
    "TOROIDAL_SURFACE",
    "DEGENERATE_TOROIDAL_SURFACE",
)


_KINDS_TORE = ("TOROIDAL_SURFACE", "DEGENERATE_TOROIDAL_SURFACE")
