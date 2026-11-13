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

"""Exports CSV : jonctions, faces, groupes et familles.
"""

import csv
import json

from .familles import FAMILLES_GEO, TOUTES_LES_FAMILLES, _caracteristique_texte
from .utilitaires import _make_formatter, _xyz


def write_families_csv(path, familles, virgule_decimale=False):
    """Un enregistrement par groupe et par famille."""
    fmt = _make_formatter(virgule_decimale)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Famille", "Groupe", "Nb_Faces", "Faces", "Types",
                    "Aire_Totale", "Caracteristique", "Couleur_Hex"])
        for cle, nom, champ, definition in TOUTES_LES_FAMILLES:
            for g in familles[cle]["groupes"]:
                w.writerow([
                    nom, g["groupe"], g["nombre_faces"],
                    ",".join(str(x) for x in g["faces"]),
                    ", ".join("%s x%d" % (k, v) for k, v in g["types_faces"].items()),
                    fmt(g["aire_totale"]),
                    _caracteristique_texte(cle, g),
                    g.get("couleur_hex") or "",
                ])


# ============================================================================
# EXPORT CSV
# ============================================================================

def write_csv(
    path,
    results,
    group_by_face
):

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.writer(
            f,
            delimiter=";"
        )

        writer.writerow([
            "Arete",
            "Face_A",
            "Face_B",
            "Groupe_A",
            "Groupe_B",
            "P2_angle_deg",
            "P3_angle_deg",
            "P4_angle_deg",
            "Angle_max_deg",
            "Tangente",
            "Statut"
        ])

        for r in sorted(
            results,
            key=lambda x: (
                x["edge"],
                x["face_a"],
                x["face_b"]
            )
        ):

            angles = r[
                "angles"
            ]

            writer.writerow([

                r["edge"],

                r["face_a"],

                r["face_b"],

                group_by_face.get(
                    r["face_a"]
                ),

                group_by_face.get(
                    r["face_b"]
                ),

                (
                    "%.6f"
                    % angles[0]
                    if len(angles) > 0
                    else ""
                ),

                (
                    "%.6f"
                    % angles[1]
                    if len(angles) > 1
                    else ""
                ),

                (
                    "%.6f"
                    % angles[2]
                    if len(angles) > 2
                    else ""
                ),

                (
                    "%.6f"
                    % r[
                        "max_angle_deg"
                    ]
                    if r[
                        "max_angle_deg"
                    ] is not None
                    else ""
                ),

                "OUI"
                if r["tangent"]
                else "NON",

                r["status"]
            ])


def write_faces_csv(path, infos, virgule_decimale=False):
    """Un enregistrement par face : classification et caractéristiques."""
    fmt = _make_formatter(virgule_decimale)
    entetes = [
        "Face_ID", "Nom", "Type", "Type_STEP", "Type_Equivalent", "Surface_Ref",
        "Groupe_Tangent", "Nb_Faces_Groupe_Tangent", "Groupe_Coaxial",
        "Groupe_Parallele", "Groupe_Concentrique", "Groupe_Geometrique_Identique",
        "Groupe_Coplanaire", "Groupe_Plan", "Groupe_Cylindre",
        "Aire", "Aire_Fiable", "Aire_Remarque",
        "Barycentre_X", "Barycentre_Y", "Barycentre_Z",
        "Normale_X", "Normale_Y", "Normale_Z", "Courbure",
        "Rayon", "Rayon_Majeur", "Rayon_Mineur", "Demi_Angle_deg",
        "Axe_Origine_X", "Axe_Origine_Y", "Axe_Origine_Z",
        "Axe_Dir_X", "Axe_Dir_Y", "Axe_Dir_Z",
        "Longueur_Axiale", "Etendue_Angulaire_deg",
        "Perimetre", "Nb_Boucles", "Nb_Trous", "Nb_Aretes", "Aretes",
        "Faces_Voisines", "Faces_Voisines_Tangentes",
        "BBox_Min_X", "BBox_Min_Y", "BBox_Min_Z",
        "BBox_Max_X", "BBox_Max_Y", "BBox_Max_Z",
        "Couleur_R", "Couleur_G", "Couleur_B", "Couleur_Hex",
    ] + ["Couleur_Hex_" + nom for _, nom, _, _ in FAMILLES_GEO] + [
        "Parametres_JSON",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(entetes)
        for fid in sorted(infos):
            i = infos[fid]
            b = i.get("boite_englobante")
            bmin = _xyz(b["min"] if b else None)
            bmax = _xyz(b["max"] if b else None)
            params = json.dumps(i.get("parametres", {}), ensure_ascii=False,
                                separators=(",", ":"))
            row = [
                i["id"], i["nom"], i["type_fr"], i["type"], i.get("type_equivalent_fr") or "", i["surface_ref"],
                i["groupe"], i["groupe_nb_faces"],
                i.get("groupe_coaxial") or "", i.get("groupe_parallele") or "",
                i.get("groupe_concentrique") or "",
                i.get("groupe_geometrie_identique") or "",
                ",".join("%d" % c["groupe"] for c in i.get("groupes_coplanaires") or []),
                i.get("groupe_plan") or "",
                i.get("groupe_cylindre") or "",
                fmt(i["aire"]), fmt(i["aire_fiable"]), i["aire_remarque"],
            ]
            row += [fmt(c) for c in _xyz(i["barycentre"])]
            row += [fmt(c) for c in _xyz(i.get("_normale"))]
            row += [i["courbure"] or ""]
            row += [fmt(i.get("_rayon")), fmt(i.get("_rayon_majeur")),
                    fmt(i.get("_rayon_mineur")), fmt(i.get("_demi_angle_deg"))]
            row += [fmt(c) for c in _xyz(i.get("_axe_origine"))]
            row += [fmt(c) for c in _xyz(i.get("_axe_direction"))]
            row += [fmt(i.get("_longueur_axiale")),
                    fmt(i.get("_etendue_angulaire_deg"))]
            row += [fmt(i["perimetre"]), i["nb_boucles"], i["nb_trous"],
                    i.get("nb_aretes", len(i["aretes"])),
                    ",".join(str(e) for e in i["aretes"]),
                    ",".join(str(x) for x in i["faces_voisines"]),
                    ",".join(str(x) for x in i["faces_voisines_tangentes"])]
            row += [fmt(c) for c in bmin] + [fmt(c) for c in bmax]
            row += list(i["couleur_rgb_255"] or ["", "", ""]) + [i["couleur_hex"] or ""]
            row += [
                (i.get("couleurs_hex") or {}).get(nom, "")
                for _, nom, _, _ in FAMILLES_GEO
            ]
            row += [params]
            w.writerow(row)


def write_groups_csv(path, group_infos, virgule_decimale=False):
    """Un enregistrement par groupe de faces tangentes."""
    fmt = _make_formatter(virgule_decimale)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "Groupe", "Nb_Faces", "Faces", "Types", "Aire_Totale",
            "Aire_Complete", "Barycentre_X", "Barycentre_Y", "Barycentre_Z",
            "BBox_Min_X", "BBox_Min_Y", "BBox_Min_Z",
            "BBox_Max_X", "BBox_Max_Y", "BBox_Max_Z",
            "Couleur_R", "Couleur_G", "Couleur_B", "Couleur_Hex",
        ])
        for g in group_infos:
            b = g.get("boite_englobante")
            row = [
                g["groupe"], g["nombre_faces"],
                ",".join(str(x) for x in g["faces"]),
                ", ".join("%s x%d" % (k, v) for k, v in g["types_faces"].items()),
                fmt(g["aire_totale"]), fmt(g["aire_complete"]),
            ]
            row += [fmt(c) for c in _xyz(g["barycentre"])]
            row += [fmt(c) for c in _xyz(b["min"] if b else None)]
            row += [fmt(c) for c in _xyz(b["max"] if b else None)]
            row += list(g["couleur_rgb_255"] or ["", "", ""]) + [g["couleur_hex"] or ""]
            w.writerow(row)
