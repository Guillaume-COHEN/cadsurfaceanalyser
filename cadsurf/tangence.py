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

"""Analyse de tangence entre faces voisines : échantillonnage des arêtes, angles
entre normales, regroupement en groupes tangents.
"""

import math
from collections import defaultdict

from .bsplines import BSplineCurve
from .config import POSITIONS_ECHANTILLONNAGE
from .reperes import Frame
from .surfaces import Surface
from .topologie import Face, UnionFind, vertex_point
from .vecteurs import add, angle_deg, dist, dot, mul, sub


# ============================================================================
# COURBES
# ============================================================================

def sample_curve(
    step,
    cref,
    p1,
    p2,
    same_sense,
    positions
):

    k = step.type_of(
        cref
    )

    # Courbe de surface
    if k in (
        "SURFACE_CURVE",
        "SEAM_CURVE",
        "INTERSECTION_CURVE"
    ):

        a = step.get(
            cref,
            k
        )

        if a is not None and len(a) > 1:

            return sample_curve(
                step,
                a[1],
                p1,
                p2,
                same_sense,
                positions
            )

    # Ligne
    if k == "LINE":

        return [
            add(
                mul(
                    p1,
                    1.0 - u
                ),
                mul(
                    p2,
                    u
                )
            )
            for u in positions
        ]

    # Cercle / ellipse
    if k in (
        "CIRCLE",
        "ELLIPSE"
    ):

        a = step.get(
            cref,
            k
        )

        if a is None:
            return []

        frame = Frame(
            step,
            a[1]
        )

        ra = float(a[2])

        if k == "ELLIPSE":
            rb = float(a[3])
        else:
            rb = ra

        def angle_of(p):

            v = sub(
                p,
                frame.o
            )

            return math.atan2(
                dot(v, frame.y) / rb,
                dot(v, frame.x) / ra
            )

        a1 = angle_of(p1)
        a2 = angle_of(p2)

        if not same_sense:
            a1, a2 = a2, a1

        if dist(p1, p2) < 1e-7:

            a2 = a1 + 2.0 * math.pi

        else:

            while a2 <= a1:
                a2 += 2.0 * math.pi

        result = []

        for u in positions:

            t = a1 + (
                a2 - a1
            ) * u

            result.append(
                add(
                    frame.o,
                    add(
                        mul(
                            frame.x,
                            ra * math.cos(t)
                        ),
                        mul(
                            frame.y,
                            rb * math.sin(t)
                        )
                    )
                )
            )

        return result

    # B-Spline
    if any(
        "B_SPLINE_CURVE" in t
        for t in step.types_of(cref)
    ):

        try:

            curve = BSplineCurve(
                step,
                cref
            )

            t1 = curve.param_of(
                p1
            )

            t2 = curve.param_of(
                p2
            )

            if not same_sense:
                t1, t2 = t2, t1

            return [
                curve.eval(
                    t1 + (
                        t2 - t1
                    ) * u
                )
                for u in positions
            ]

        except Exception:
            return []

    # Courbe non gérée :
    # on retourne au minimum une interpolation.
    return [
        add(
            mul(
                p1,
                1.0 - u
            ),
            mul(
                p2,
                u
            )
        )
        for u in positions
    ]


# ============================================================================
# ANALYSE PRINCIPALE
# ============================================================================

def analyse(
    step,
    tolerance_deg
):

    face_ids = step.ids_of(
        "ADVANCED_FACE",
        "FACE_SURFACE"
    )

    faces = {}

    for fid in face_ids:

        try:
            faces[fid] = Face(
                step,
                fid
            )
        except Exception as exc:

            print(
                "ATTENTION : face #%d ignorée : %s"
                % (fid, exc)
            )

    # Création des surfaces
    surfaces = {}

    for face in faces.values():

        if face.surf_ref not in surfaces:

            try:

                surfaces[
                    face.surf_ref
                ] = Surface(
                    step,
                    face.surf_ref
                )

            except Exception:

                surfaces[
                    face.surf_ref
                ] = None

        face.surface = surfaces[
            face.surf_ref
        ]

    # ----------------------------------------------------------------------
    # Arête -> faces
    # ----------------------------------------------------------------------

    edge_faces = defaultdict(list)

    for face in faces.values():

        for edge in face.edges:

            if face.id not in edge_faces[edge]:

                edge_faces[edge].append(
                    face.id
                )

    tolerance_rad = math.radians(
        tolerance_deg
    )

    results = []

    # ----------------------------------------------------------------------
    # Test de chaque arête commune
    # ----------------------------------------------------------------------

    for edge_ref, flist in sorted(
        edge_faces.items()
    ):

        if len(flist) < 2:
            continue

        edge = step.get(
            edge_ref,
            "EDGE_CURVE"
        )

        if edge is None:
            continue

        try:

            p1 = vertex_point(
                step,
                edge[1]
            )

            p2 = vertex_point(
                step,
                edge[2]
            )

        except Exception:

            continue

        curve_ref = edge[3]

        same_curve = (
            str(edge[4]).upper()
            == "T"
        )

        points = sample_curve(
            step,
            curve_ref,
            p1,
            p2,
            same_curve,
            POSITIONS_ECHANTILLONNAGE
        )

        if len(points) != 3:
            continue

        # Toutes les paires de faces partageant l'arête
        for i in range(
            len(flist)
        ):

            for j in range(
                i + 1,
                len(flist)
            ):

                fa = faces[
                    flist[i]
                ]

                fb = faces[
                    flist[j]
                ]

                if (
                    fa.surface is None
                    or fb.surface is None
                ):

                    results.append({
                        "edge": edge_ref,
                        "face_a": fa.id,
                        "face_b": fb.id,
                        "angles": [],
                        "max_angle_deg": None,
                        "tangent": False,
                        "status": "surface inconnue"
                    })

                    continue

                if (
                    not fa.surface.supported
                    or not fb.surface.supported
                ):

                    results.append({
                        "edge": edge_ref,
                        "face_a": fa.id,
                        "face_b": fb.id,
                        "angles": [],
                        "max_angle_deg": None,
                        "tangent": False,
                        "status": "surface non supportée"
                    })

                    continue

                angles = []

                valid = True

                for p in points:

                    na = fa.surface.normal(
                        p
                    )

                    nb = fb.surface.normal(
                        p
                    )

                    if (
                        na is None
                        or nb is None
                    ):

                        valid = False
                        break

                    # Orientation de la face
                    if not fa.same_sense:
                        na = mul(
                            na,
                            -1.0
                        )

                    if not fb.same_sense:
                        nb = mul(
                            nb,
                            -1.0
                        )

                    angle = angle_deg(
                        na,
                        nb
                    )

                    if angle is None:

                        valid = False
                        break

                    # ------------------------------------------------------------------
                    # Pour une jonction tangentielle de surfaces B-Rep, les normales
                    # orientées matière peuvent être dans le même sens ou opposées
                    # suivant la convention de représentation.
                    #
                    # On prend donc le plus petit angle entre nA/nB et nA/-nB.
                    # ------------------------------------------------------------------

                    angle = min(
                        angle,
                        abs(
                            180.0 - angle
                        )
                    )

                    angles.append(
                        angle
                    )

                if not valid:

                    results.append({
                        "edge": edge_ref,
                        "face_a": fa.id,
                        "face_b": fb.id,
                        "angles": angles,
                        "max_angle_deg": None,
                        "tangent": False,
                        "status": "normale impossible"
                    })

                    continue

                max_angle = max(
                    angles
                )

                tangent = (
                    max_angle
                    <= tolerance_deg
                )

                results.append({
                    "edge": edge_ref,
                    "face_a": fa.id,
                    "face_b": fb.id,
                    "angles": angles,
                    "max_angle_deg": max_angle,
                    "tangent": tangent,
                    "status":
                        "TANGENTE"
                        if tangent
                        else "non tangente"
                })

    # ----------------------------------------------------------------------
    # Union-Find
    # ----------------------------------------------------------------------

    uf = UnionFind(
        faces.keys()
    )

    for r in results:

        if r["tangent"]:

            uf.union(
                r["face_a"],
                r["face_b"]
            )

    groups_dict = defaultdict(list)

    for fid in faces:

        groups_dict[
            uf.find(fid)
        ].append(fid)

    groups = sorted(
        groups_dict.values(),
        key=lambda g: (
            -len(g),
            min(g)
        )
    )

    # Numérotation stable
    group_by_face = {}

    for index, group in enumerate(
        groups,
        start=1
    ):

        for fid in group:
            group_by_face[fid] = index

    return (
        faces,
        results,
        groups,
        group_by_face
    )
