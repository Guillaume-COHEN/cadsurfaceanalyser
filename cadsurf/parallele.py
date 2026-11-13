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

"""Calcul parallèle des intégrales (aire, barycentre...) des faces lourdes.

Les faces à surface B-spline, de révolution ou d'extrusion concentrent
presque tout le temps de calcul et sont indépendantes les unes des autres :
elles sont réparties sur plusieurs processus. Chaque processus relit le
fichier STEP une fois (initialiseur) puis traite les faces qu'on lui confie ;
les résultats sont exactement ceux du calcul séquentiel.

Le parallélisme n'est utilisé que si cela en vaut la peine (assez de faces
lourdes et plusieurs cœurs) ; en cas de problème, le calcul séquentiel prend
le relais.
"""

import os
from concurrent.futures import ProcessPoolExecutor

from .geom_aretes import EdgeGeom
from . import accel, geom_faces
from .geom_faces import _resolve_face_integrals, face_loops
from .geom_surfaces import SurfParam
from .step_parser import StepFile
from .surfaces import Surface
from .topologie import Face

KINDS_LOURDS = (
    "B_SPLINE_SURFACE",
    "SURFACE_OF_REVOLUTION",
    "SURFACE_OF_LINEAR_EXTRUSION",
)
SEUIL_AUTO = 12          # faces lourdes minimales pour le mode automatique
MAX_AUTO = 8             # nombre maximal de processus en mode automatique

_ETAT = {}


def _init_worker(chemin, k_numerique, numpy_actif):
    geom_faces.K_NUMERIQUE = k_numerique          # (processus lancés par « spawn »)
    accel.activer(numpy_actif)
    _ETAT["step"] = StepFile(chemin)
    _ETAT["surfaces"] = {}
    _ETAT["aretes"] = {}


def _get_edge(ref):
    cache = _ETAT["aretes"]
    if ref not in cache:
        try:
            cache[ref] = EdgeGeom(_ETAT["step"], ref)
        except Exception:
            cache[ref] = None
    return cache[ref]


def _travail(fid):
    step = _ETAT["step"]
    face = Face(step, fid)
    surfaces = _ETAT["surfaces"]
    if face.surf_ref not in surfaces:
        surfaces[face.surf_ref] = Surface(step, face.surf_ref)
    sp = SurfParam(surfaces[face.surf_ref])
    return fid, _resolve_face_integrals(sp, face_loops(step, face), _get_edge)


def nombre_processus(demande, nb_lourdes, cpu=None):
    """Nombre de processus à utiliser.

    demande = 1 : séquentiel ; demande >= 2 : ce nombre (au plus une face
    lourde par processus) ; demande = 0 : automatique.
    """
    cpu = cpu or os.cpu_count() or 1
    if demande == 1 or nb_lourdes < 2:
        return 1
    if demande > 1:
        return min(demande, nb_lourdes)
    if nb_lourdes < SEUIL_AUTO or cpu < 2:
        return 1
    return min(cpu, MAX_AUTO, nb_lourdes)


def integrales_lourdes_en_parallele(
    step, faces, demande=0, log=print, k_numerique=None, numpy_actif=False
):
    """Intégrales des faces lourdes, calculées en parallèle.

    Retourne {face: (res, fiable, remarques)} ; dictionnaire vide si le calcul
    doit se faire de façon séquentielle."""
    lourdes = [
        f for f, fc in faces.items()
        if fc.surface is not None
        and fc.surface.supported
        and fc.surface.kind in KINDS_LOURDS
    ]
    n = nombre_processus(demande, len(lourdes))
    if n <= 1:
        return {}
    lourdes.sort(key=lambda f: -len(faces[f].edges))
    log(
        "Calcul parallèle : %d processus pour %d faces à surface numérique..."
        % (n, len(lourdes))
    )
    try:
        with ProcessPoolExecutor(
            max_workers=n,
            initializer=_init_worker,
            initargs=(
                os.path.abspath(step.path),
                k_numerique or geom_faces.K_NUMERIQUE,
                numpy_actif,
            ),
        ) as pool:
            return dict(pool.map(_travail, lourdes, chunksize=1))
    except Exception as exc:
        log("Calcul parallèle impossible (%s) : calcul séquentiel." % exc)
        return {}
