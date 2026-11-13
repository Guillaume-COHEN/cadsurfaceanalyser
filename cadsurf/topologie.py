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

"""Topologie : faces (boucles, arêtes), sommets, union-find.
"""

from .reperes import _point


# ============================================================================
# FACES
# ============================================================================

class Face(object):

    def __init__(
        self,
        step,
        fid
    ):

        self.id = fid

        a = step.get(
            fid,
            "ADVANCED_FACE",
            "FACE_SURFACE"
        )

        if a is None:
            raise ValueError(
                "Face invalide #%d" % fid
            )

        self.name = a[0]

        self.bounds = a[1]

        self.surf_ref = a[2]

        self.same_sense = (
            str(a[3]).upper() == "T"
        )

        self.edges = []

        for bref in self.bounds:

            ba = step.get(
                bref,
                "FACE_OUTER_BOUND",
                "FACE_BOUND"
            )

            if ba is None:
                continue

            loop = step.get(
                ba[1],
                "EDGE_LOOP"
            )

            if loop is None:
                continue

            for oriented_edge in loop[1]:

                oa = step.get(
                    oriented_edge,
                    "ORIENTED_EDGE"
                )

                if oa is None:
                    continue

                edge_ref = oa[3]

                self.edges.append(
                    edge_ref
                )


# ============================================================================
# VERTICES / EDGES
# ============================================================================

def vertex_point(
    step,
    vref
):

    a = step.get(
        vref,
        "VERTEX_POINT"
    )

    if a is None:
        raise ValueError(
            "VERTEX_POINT #%s introuvable"
            % vref
        )

    return _point(
        step,
        a[1]
    )


# ============================================================================
# UNION-FIND
# ============================================================================

class UnionFind(object):

    def __init__(
        self,
        items
    ):

        self.parent = {
            x: x
            for x in items
        }

        self.rank = {
            x: 0
            for x in items
        }

    def find(self, x):

        p = self.parent[x]

        if p != x:

            self.parent[x] = (
                self.find(p)
            )

        return self.parent[x]

    def union(
        self,
        a,
        b
    ):

        ra = self.find(a)
        rb = self.find(b)

        if ra == rb:
            return

        if (
            self.rank[ra]
            < self.rank[rb]
        ):

            self.parent[ra] = rb

        elif (
            self.rank[ra]
            > self.rank[rb]
        ):

            self.parent[rb] = ra

        else:

            self.parent[rb] = ra
            self.rank[ra] += 1
