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

"""Affichage console des rapports.
"""

from .familles import FAMILLES_GEO, _caracteristique_texte


def print_families_report(familles):
    print()
    print("=" * 78)
    print("FAMILLES GEOMETRIQUES")
    print("=" * 78)
    for cle, nom, champ, definition in FAMILLES_GEO:
        fam = familles[cle]
        print()
        print("--- %s (%d groupe(s)) ---" % (nom, len(fam["groupes"])))
        print("    %s" % definition)
        if not fam["groupes"]:
            print("    aucun groupe")
        for g in fam["groupes"]:
            print("  Groupe %3d : %3d faces | %s" % (
                g["groupe"], g["nombre_faces"],
                ", ".join("#%d" % x for x in g["faces"])))
            print("               %s" % _caracteristique_texte(cle, g))


def print_geometry_report(infos, resume, group_infos):
    u = resume["unite_longueur"]
    print()
    print("=" * 78)
    print("CARACTERISTIQUES DES FACES")
    print("=" * 78)
    print("  %-6s %-28s %-6s %14s  %s" % ("Face", "Type", "Groupe", "Aire (%s2)" % u, "Barycentre"))
    for fid in sorted(infos):
        i = infos[fid]
        bar = (
            "(%.4f, %.4f, %.4f)" % tuple(i["barycentre"])
            if i["barycentre"] else "-"
        )
        print("  #%-5d %-28s %-6d %14s  %s%s" % (
            fid,
            i["type_fr"] + (" ~ " + i["type_equivalent_fr"].split(" ")[0] if i.get("type_equivalent_fr") else ""),
            i["groupe"],
            ("%.6f" % i["aire"]) if i["aire"] is not None else "-",
            bar, "" if i["aire_fiable"] else "   [A VERIFIER]"))
    print()
    if resume["aire_totale"] is not None:
        print("Aire totale          : %.6f %s2" % (resume["aire_totale"], u))
    if resume["volume_estime"] is not None:
        print("Volume estime        : %.6f %s3" % (resume["volume_estime"], u))
    if resume["controle_fermeture_aire_vectorielle"] is not None:
        print("Controle de fermeture: %.3e  (0 = coque fermee et aires coherentes)"
              % resume["controle_fermeture_aire_vectorielle"])
    if resume["faces_aire_non_fiable"]:
        print("Faces a verifier     : %s" % ", ".join("#%d" % x for x in resume["faces_aire_non_fiable"]))
    print("Temps de calcul      : %.2f s" % resume["temps_calcul_s"])
    print()
    print("--- GROUPES (aire / barycentre) ---")
    for g in group_infos:
        print("  Groupe %3d : %3d faces | aire = %s | barycentre = %s" % (
            g["groupe"], g["nombre_faces"],
            ("%.4f" % g["aire_totale"]) if g["aire_totale"] is not None else "-",
            ("(%.3f, %.3f, %.3f)" % tuple(g["barycentre"])) if g["barycentre"] else "-"))


# ============================================================================
# AFFICHAGE
# ============================================================================

def print_report(
    faces,
    results,
    groups,
    group_by_face,
    colors,
    tolerance
):

    print()
    print("=" * 78)
    print("RESULTAT DE L'ANALYSE")
    print("=" * 78)

    print(
        "Faces détectées       : %d"
        % len(faces)
    )

    print(
        "Arêtes communes testées : %d"
        % len(results)
    )

    tangent_count = sum(
        1
        for r in results
        if r["tangent"]
    )

    print(
        "Jonctions tangentes   : %d"
        % tangent_count
    )

    print(
        "Groupes de faces      : %d"
        % len(groups)
    )

    print(
        "Tolérance angulaire   : %.4f°"
        % tolerance
    )

    print(
        "Points testés         : P2 / P3 / P4"
    )

    print()
    print(
        "--- JONCTIONS TANGENTES ---"
    )

    if tangent_count == 0:

        print(
            "Aucune tangence détectée."
        )

    else:

        for r in results:

            if r["tangent"]:

                print(
                    "  arête #%d : faces #%d / #%d"
                    " | angles = %s°"
                    % (
                        r["edge"],
                        r["face_a"],
                        r["face_b"],
                        ", ".join(
                            "%.4f"
                            % a
                            for a in r[
                                "angles"
                            ]
                        )
                    )
                )

    print()
    print(
        "--- GROUPES ---"
    )

    for i, group in enumerate(
        groups,
        start=1
    ):

        rgb = colors[
            i
        ]

        print(
            "  Groupe %3d : %3d faces | "
            "RGB = (%3d,%3d,%3d) | %s"
            % (
                i,
                len(group),
                int(
                    rgb[0] * 255
                ),
                int(
                    rgb[1] * 255
                ),
                int(
                    rgb[2] * 255
                ),
                ", ".join(
                    "#%d" % f
                    for f in sorted(group)
                )
            )
        )
