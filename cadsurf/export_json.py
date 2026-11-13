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

"""Export JSON.
"""

import json

from .utilitaires import _rnd, _round_list


def _clean_info(info):
    """Version JSON d'une fiche face (sans champs internes)."""
    d = {k: v for k, v in info.items() if not k.startswith("_")}
    for key in ("aire", "perimetre", "volume_signe"):
        if d.get(key) is not None:
            d[key] = round(d[key], 6)
    d["barycentre"] = _round_list(d.get("barycentre"))
    d["normale_moyenne"] = _round_list(d.get("normale_moyenne"))
    b = d.get("boite_englobante")
    if b:
        d["boite_englobante"] = {k: _round_list(v) for k, v in b.items()}

    def rnd(x):
        if isinstance(x, float):
            return round(x, 6)
        if isinstance(x, (list, tuple)):
            return [rnd(y) for y in x]
        if isinstance(x, dict):
            return {k: rnd(y) for k, y in x.items()}
        return x

    d["parametres"] = rnd(d.get("parametres", {}))
    d["geometrie_infinie"] = rnd(d.get("geometrie_infinie"))
    return d


def write_json(
    path,
    input_path,
    tolerance,
    faces,
    results,
    groups,
    group_by_face,
    colors,
    infos=None,
    resume=None,
    group_infos=None,
    edge_infos=None,
    familles=None,
    coloration="tangent",
    fichiers_stp=None
):
    data = {
        "fichier_entree": input_path,
        "tolerance_angulaire_deg": tolerance,
        "echantillonnage": ["P2", "P3", "P4"],
        "nombre_faces": len(faces),
        "nombre_groupes": len(groups),
    }
    if resume:
        u = resume["unite_longueur"]
        data["unites"] = {
            "longueur": u, "aire": u + "²", "volume": u + "³"
        }
        data["resume"] = {
            k: (round(v, 6) if isinstance(v, float) else v)
            for k, v in resume.items()
            if k != "unite_longueur"
        }
    if coloration is not None:
        data["coloration_step"] = coloration
    data["faces"] = {}
    data["groupes"] = []
    data["aretes"] = []

    for fid in sorted(faces):
        face = faces[fid]
        if infos is not None:
            data["faces"][str(fid)] = _clean_info(infos[fid])
        else:
            rgb = colors[group_by_face[fid]]
            data["faces"][str(fid)] = {
                "type": face.surface.kind if face.surface else None,
                "surface_ref": face.surf_ref,
                "groupe": group_by_face[fid],
                "nombre_aretes": len(face.edges),
                "couleur_rgb": [round(c, 6) for c in rgb],
            }

    if group_infos is not None:
        for g in group_infos:
            g = dict(g)
            for key in ("aire_totale",):
                if g.get(key) is not None:
                    g[key] = round(g[key], 6)
            g["barycentre"] = _round_list(g.get("barycentre"))
            if g.get("boite_englobante"):
                g["boite_englobante"] = {
                    k: _round_list(v) for k, v in g["boite_englobante"].items()
                }
            data["groupes"].append(g)
    else:
        for index, group in enumerate(groups, start=1):
            data["groupes"].append({
                "groupe": index,
                "nombre_faces": len(group),
                "faces": sorted(group),
                "couleur_rgb": [round(c, 6) for c in colors[index]],
            })

    for r in results:
        data["aretes"].append({
            "arete": r["edge"],
            "face_a": r["face_a"],
            "face_b": r["face_b"],
            "angles_deg": [round(x, 6) for x in r["angles"]],
            "angle_max_deg": (
                round(r["max_angle_deg"], 6)
                if r["max_angle_deg"] is not None else None
            ),
            "tangente": r["tangent"],
            "statut": r["status"],
        })

    if familles is not None:
        data["familles_geometriques"] = {
            cle: {
                "nom": fam["nom"],
                "definition": fam["definition"],
                "groupes": _rnd(fam["groupes"]),
            }
            for cle, fam in familles.items()
        }

    if fichiers_stp:
        data["fichiers_stp"] = fichiers_stp

    if edge_infos is not None:
        data["aretes_detail"] = {
            k: {
                kk: (
                    round(vv, 6) if isinstance(vv, float)
                    else _round_list(vv) if kk in ("sommet_debut", "sommet_fin")
                    else vv
                )
                for kk, vv in v.items()
            }
            for k, v in edge_infos.items()
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
