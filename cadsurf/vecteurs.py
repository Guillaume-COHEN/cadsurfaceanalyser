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

"""Algèbre vectorielle 3D élémentaire (tuples de 3 flottants).
"""

import math

from .config import EPS


# ============================================================================
# VECTEURS
# ============================================================================

def add(a, b):
    return (
        a[0] + b[0],
        a[1] + b[1],
        a[2] + b[2]
    )


def sub(a, b):
    return (
        a[0] - b[0],
        a[1] - b[1],
        a[2] - b[2]
    )


def mul(a, k):
    return (
        a[0] * k,
        a[1] * k,
        a[2] * k
    )


def dot(a, b):
    return (
        a[0] * b[0]
        + a[1] * b[1]
        + a[2] * b[2]
    )


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    )


def norm(a):
    return math.sqrt(
        dot(a, a)
    )


def unit(a):

    n = norm(a)

    if n < EPS:
        return None

    return (
        a[0] / n,
        a[1] / n,
        a[2] / n
    )


def unit_robuste(a, relatif=1.0):
    """Normalise `a` sans seuil absolu (contrairement à `unit`, qui rejette
    toute norme < EPS). `relatif` est l'échelle de référence : le vecteur est
    rejeté seulement s'il est négligeable devant elle (parametrisation
    dégénérée), jamais parce que les unités du paramètre sont petites."""
    n = norm(a)
    if n == 0.0 or n != n or n < 1e-12 * relatif:
        return None
    return (a[0] / n, a[1] / n, a[2] / n)


def dist(a, b):
    return norm(
        sub(a, b)
    )


def angle_deg(a, b):

    if a is None or b is None:
        return None

    d = dot(a, b)

    d = max(
        -1.0,
        min(1.0, d)
    )

    return math.degrees(
        math.acos(d)
    )
