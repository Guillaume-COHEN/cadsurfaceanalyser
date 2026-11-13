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

"""Accélération optionnelle par numpy.

numpy n'est pas obligatoire : s'il est absent (ou avec --sans-numpy), tout le
calcul passe par le code Python pur, avec les mêmes résultats. numpy n'est
importé que lorsqu'il sert réellement (le module vectoriel.py l'importe).
"""

import importlib.util

try:
    DISPONIBLE = importlib.util.find_spec("numpy") is not None
except (ValueError, ImportError, AttributeError):      # numpy absent ou masqué
    DISPONIBLE = False
UTILISER = DISPONIBLE
REPLIS = 0              # arêtes recalculées en scalaire après un échec vectorisé


def activer(oui):
    """Active ou désactive numpy (sans effet s'il n'est pas installé).
    Retourne l'état effectif."""
    global UTILISER
    UTILISER = bool(oui) and DISPONIBLE
    return UTILISER


def version():
    """Version de numpy installée (sans l'importer), ou None."""
    if not DISPONIBLE:
        return None
    try:
        from importlib.metadata import version as v
        return v("numpy")
    except Exception:
        return "?"
