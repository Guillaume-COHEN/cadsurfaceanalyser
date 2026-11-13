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

"""Familles de groupes (Famille_Groupe) : tangent, coaxial, parallèle,
concentrique, géométrie identique, coplanaire et plan.

Un « groupe » regroupe des faces selon une relation ; une « famille » est un
type de relation. Le groupe tangent (calculé par tangence.py) est traité de la
même manière que les autres familles dans les exports.
"""

import json
import math
from collections import defaultdict

from .config import _KINDS_TORE
from .utilitaires import _rnd
from .vecteurs import add, cross, dist, dot, mul, norm, sub, unit


# ============================================================================
# FAMILLES DE GROUPES (Famille_Groupe)
# ============================================================================
#
#  Famille       Relation entre deux faces (A, B)
#  -----------   ---------------------------------------------------------------
#  tangent       (voir tangence.py) A et B sont tangentes le long d'une arête
#                commune, directement ou de proche en proche.
#  coaxiales     A et B sont des surfaces à axe (cylindre, cône, tore, surface
#                de révolution) et leurs axes sont la même droite.
#  parallèles    plans dont les normales sont parallèles (coplanaires inclus) ;
#                OU surfaces à axe dont les axes sont parallèles. Les deux types
#                ne sont jamais mélangés dans un même groupe.
#  concentriques A et B ont le même centre (sphère : centre ; tore : centre ;
#                cône : sommet), et leurs axes sont parallèles quand ils en ont.
#  identiques    même surface infinie : même équation de plan, même cylindre
#                (axe + rayon), même cône, même sphère, même tore.
#  cylindres     toutes les faces cylindriques, regroupées par rayon identique
#                (à --tol-lin près) : même groupe, donc même couleur, pour les
#                cylindres de même rayon, quels que soient leurs axes. Comme
#                pour les plans, un rayon unique forme un groupe d'une face.
#  coplanaires   A et B ont un plan de référence commun. Plan de référence :
#                plan -> son plan ; tore -> son plan médian (plan du cercle des
#                centres) et ses deux plans tangents (à +/- r du plan médian).
#  plans         toutes les faces PLANE, regroupées par vecteur normal identique
#                (normale matière sortante : sens compris, donc +Z et -Z sont
#                deux groupes). Contrairement aux autres familles, un plan à
#                normale unique forme un groupe d'une face.
#
# Une surface de révolution à génératrice circulaire (tore exporté en
# SURFACE_OF_REVOLUTION) est comparée à travers son tore équivalent ajusté.
# Les groupes (sauf Groupe_Tangent et Groupe_Plan) ont au moins 2 faces.
# Tolérances : --tol-lin (longueurs, unité du fichier) et --tol-angle-geo (degrés).
# ============================================================================

FAMILLE_TANGENT = (
    "tangent", "Groupe_Tangent", "groupe",
    "Faces tangentes le long d'une arête commune, de proche en proche.",
)

FAMILLES_GEO = (
    (
        "coaxiales", "Groupe_Coaxial", "groupe_coaxial",
        "Surfaces à axe (cylindre, cône, tore, révolution) ayant le même axe.",
    ),
    (
        "paralleles", "Groupe_Parallele", "groupe_parallele",
        "Plans de normales parallèles, ou surfaces à axe d'axes parallèles.",
    ),
    (
        "concentriques", "Groupe_Concentrique", "groupe_concentrique",
        "Même centre (sphère, tore) ou même sommet (cône), axes parallèles.",
    ),
    (
        "identiques", "Groupe_Geometrique_Identique", "groupe_geometrie_identique",
        "Même surface infinie : même plan, cylindre, cône, sphère ou tore.",
    ),
    (
        "coplanaires", "Groupe_Coplanaire", "groupes_coplanaires",
        "Plan de référence commun (plan, ou plan médian/tangent d'un tore).",
    ),
    (
        "plans", "Groupe_Plan", "groupe_plan",
        "Faces planes de même vecteur normal (normale matière sortante).",
    ),
    (
        "cylindres", "Groupe_Cylindre", "groupe_cylindre",
        "Faces cylindriques de même rayon (à la tolérance linéaire près).",
    ),
)

# Familles dont les groupes d'une seule face sont colorés dans le STEP
# (les faces hors famille restent grises).
FAMILLES_A_GROUPES_ISOLES = ("plans", "cylindres")

# Toutes les familles dans l'ordre d'affichage (tangent en tête)
TOUTES_LES_FAMILLES = (FAMILLE_TANGENT,) + FAMILLES_GEO

_GENRES_A_AXE = ("CYLINDRE", "CONE", "TORE", "REVOLUTION")


def _unit_sign(d):
    """Direction normalisée dont la première composante non nulle est > 0."""
    d = unit(d)
    for c in d:
        if abs(c) > 1e-9:
            return d if c > 0 else (-d[0], -d[1], -d[2])
    return d


def _face_anchor(info):
    if info.get("barycentre"):
        return tuple(info["barycentre"])
    b = info.get("boite_englobante")
    if b:
        return tuple(0.5 * (b["min"][i] + b["max"][i]) for i in range(3))
    return None


def geometric_descriptor(face, info):
    """Surface infinie portée par la face (None si non décrite)."""
    surf = face.surface
    if surf is None or not surf.supported:
        return None
    k, f = surf.kind, getattr(surf, "frame", None)
    anchor = _face_anchor(info)
    D = {"genre": None, "dir": None, "pt": None, "center": None,
         "via_equivalent": False, "json": None}
    if k == "PLANE":
        n = _unit_sign(f.z)
        D.update(genre="PLAN", dir=n, pt=anchor if anchor else f.o)
        D["d"] = dot(n, f.o)
        D["n_out"] = mul(f.z, 1.0 if face.same_sense else -1.0)
        D["json"] = {"genre": "PLAN", "normale": list(n), "d": D["d"],
                     "equation": "n.x = d"}
    elif k == "CYLINDRICAL_SURFACE":
        D.update(genre="CYLINDRE", dir=f.z, pt=f.o, radius=surf.radius)
        D["json"] = {"genre": "CYLINDRE", "axe_point": list(f.o),
                     "axe_direction": list(f.z), "rayon": surf.radius}
    elif k == "CONICAL_SURFACE":
        t = math.tan(surf.angle)
        if abs(t) < 1e-12:
            D.update(genre="CYLINDRE", dir=f.z, pt=f.o, radius=surf.radius)
            D["json"] = {"genre": "CYLINDRE", "axe_point": list(f.o),
                         "axe_direction": list(f.z), "rayon": surf.radius}
        else:
            apex = sub(f.o, mul(f.z, surf.radius / t))
            D.update(genre="CONE", dir=f.z, pt=apex, center=apex,
                     half_angle=abs(math.degrees(surf.angle)))
            D["json"] = {"genre": "CONE", "sommet": list(apex),
                         "axe_direction": list(f.z),
                         "demi_angle_deg": D["half_angle"]}
    elif k == "SPHERICAL_SURFACE":
        D.update(genre="SPHERE", pt=f.o, center=f.o, radius=surf.radius)
        D["json"] = {"genre": "SPHERE", "centre": list(f.o), "rayon": surf.radius}
    elif k in _KINDS_TORE:
        D.update(genre="TORE", dir=f.z, pt=f.o, center=f.o,
                 R=surf.major_radius, r=surf.minor_radius)
        D["json"] = {"genre": "TORE", "centre": list(f.o),
                     "axe_direction": list(f.z),
                     "rayon_majeur": surf.major_radius,
                     "rayon_mineur": surf.minor_radius}
    elif k == "SURFACE_OF_REVOLUTION":
        rev = surf.rev
        eq = (info.get("parametres") or {}).get("equivalent")
        if eq and "rayon_majeur" in eq:
            c = tuple(eq["centre_sur_axe"])
            D.update(genre="TORE", dir=rev.z, pt=c, center=c,
                     R=eq["rayon_majeur"], r=eq["rayon_mineur"], via_equivalent=True)
            D["json"] = {"genre": "TORE", "via_equivalent": True,
                         "centre": list(c), "axe_direction": list(rev.z),
                         "rayon_majeur": eq["rayon_majeur"],
                         "rayon_mineur": eq["rayon_mineur"]}
        elif eq and "rayon" in eq:
            c = tuple(eq["centre_sur_axe"])
            D.update(genre="SPHERE", pt=c, center=c, radius=eq["rayon"],
                     via_equivalent=True)
            D["json"] = {"genre": "SPHERE", "via_equivalent": True,
                         "centre": list(c), "rayon": eq["rayon"]}
        else:
            D.update(genre="REVOLUTION", dir=rev.z, pt=rev.o)
            D["json"] = {"genre": "REVOLUTION", "axe_point": list(rev.o),
                         "axe_direction": list(rev.z)}
    elif k == "SURFACE_OF_LINEAR_EXTRUSION":
        e = surf.ext
        c = e.curve
        if (c.kind == "CIRCLE" and getattr(c, "radius", None)
                and abs(dot(c.normal, e.d)) > 1.0 - 1e-9):
            D.update(genre="CYLINDRE", dir=e.d, pt=c.center, radius=c.radius,
                     via_equivalent=True)
            D["json"] = {"genre": "CYLINDRE", "via_equivalent": True,
                         "axe_point": list(c.center), "axe_direction": list(e.d),
                         "rayon": c.radius}
        else:
            D.update(genre="EXTRUSION", dir=e.d)
            D["json"] = {"genre": "EXTRUSION", "direction": list(e.d)}
    else:
        return None
    return D


def _components(keys, related):
    """Composantes connexes de la relation `related` (union-find)."""
    parent = list(range(len(keys)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if related(keys[i], keys[j]):
                a, b = find(i), find(j)
                if a != b:
                    parent[b] = a
    comp = defaultdict(list)
    for i, key in enumerate(keys):
        comp[find(i)].append(key)
    return list(comp.values())


def _type_label(info):
    t = info["type_fr"]
    if info.get("type_equivalent_fr"):
        t += " ≈ " + info["type_equivalent_fr"].split(" ")[0]
    return t


def build_geometric_families(faces, infos, tol_lin=0.005, tol_angle_deg=0.05):
    """Calcule les cinq familles ; ajoute les champs de groupe dans `infos`."""
    sin_tol = math.sin(math.radians(tol_angle_deg))
    D = {}
    for fid, face in faces.items():
        D[fid] = geometric_descriptor(face, infos[fid])
        infos[fid]["geometrie_infinie"] = D[fid]["json"] if D[fid] else None
        for _, _, champ, _ in FAMILLES_GEO:
            infos[fid][champ] = [] if champ == "groupes_coplanaires" else None

    def par(a, b):
        return norm(cross(a, b)) <= sin_tol

    def dist_line(p, a, d):
        return norm(cross(sub(p, a), d))

    def same_axis(a, b):
        return (par(a["dir"], b["dir"])
                and dist_line(b["pt"], a["pt"], a["dir"]) <= tol_lin
                and dist_line(a["pt"], b["pt"], b["dir"]) <= tol_lin)

    def same_plane(n1, p1, n2, p2):
        return (par(n1, n2)
                and abs(dot(n2, sub(p1, p2))) <= tol_lin
                and abs(dot(n1, sub(p2, p1))) <= tol_lin)

    def same_surface(a, b):
        if a["genre"] != b["genre"]:
            return False
        g = a["genre"]
        if g == "PLAN":
            return same_plane(a["dir"], a["pt"], b["dir"], b["pt"])
        if g == "SPHERE":
            return (dist(a["center"], b["center"]) <= tol_lin
                    and abs(a["radius"] - b["radius"]) <= tol_lin)
        if not same_axis(a, b):
            return False
        if g == "CYLINDRE":
            return abs(a["radius"] - b["radius"]) <= tol_lin
        if g == "CONE":
            return (dist(a["center"], b["center"]) <= tol_lin
                    and abs(a["half_angle"] - b["half_angle"]) <= max(tol_angle_deg, 0.01))
        if g == "TORE":
            return (dist(a["center"], b["center"]) <= tol_lin
                    and abs(a["R"] - b["R"]) <= tol_lin
                    and abs(a["r"] - b["r"]) <= tol_lin)
        return False

    # ---- composantes brutes pour chaque famille --------------------------
    brut = {}

    ids = [f for f in sorted(D) if D[f] and D[f]["genre"] in _GENRES_A_AXE]
    brut["coaxiales"] = [
        (c, {"type": "axe"}) for c in
        _components(ids, lambda a, b: same_axis(D[a], D[b]))
    ]

    plans = [f for f in sorted(D) if D[f] and D[f]["genre"] == "PLAN"]
    axes = [f for f in sorted(D) if D[f] and D[f]["genre"] in _GENRES_A_AXE + ("EXTRUSION",)]
    brut["paralleles"] = (
        [(c, {"type": "normales de plans"}) for c in
         _components(plans, lambda a, b: par(D[a]["dir"], D[b]["dir"]))]
        + [(c, {"type": "axes"}) for c in
           _components(axes, lambda a, b: par(D[a]["dir"], D[b]["dir"]))]
    )

    ids = [f for f in sorted(D) if D[f] and D[f]["center"] is not None]
    brut["concentriques"] = [
        (c, {}) for c in _components(
            ids,
            lambda a, b: dist(D[a]["center"], D[b]["center"]) <= tol_lin
            and (D[a]["dir"] is None or D[b]["dir"] is None
                 or par(D[a]["dir"], D[b]["dir"])),
        )
    ]

    ids = [f for f in sorted(D) if D[f] and D[f]["genre"] in
           ("PLAN", "CYLINDRE", "CONE", "SPHERE", "TORE")]
    brut["identiques"] = [
        (c, {}) for c in _components(ids, lambda a, b: same_surface(D[a], D[b]))
    ]

    # Groupe_Plan : faces planes de même vecteur normal (sens compris)
    def meme_vecteur(a, b):
        na, nb = D[a]["n_out"], D[b]["n_out"]
        return dot(na, nb) > 0 and norm(cross(na, nb)) <= sin_tol

    brut["plans"] = [
        (c, {}) for c in _components(plans, meme_vecteur)
    ]

    # Groupe_Cylindre : cylindres classés par rayon croissant, un nouveau groupe
    # dès que l'écart de rayon dépasse la tolérance linéaire
    cylindres = sorted(
        (f for f in D if D[f] and D[f]["genre"] == "CYLINDRE"),
        key=lambda f: (D[f]["radius"], f),
    )
    amas_cyl = []
    for f in cylindres:
        if amas_cyl and D[f]["radius"] - D[amas_cyl[-1][-1]]["radius"] <= tol_lin:
            amas_cyl[-1].append(f)
        else:
            amas_cyl.append([f])
    brut["cylindres"] = [(c, {}) for c in amas_cyl]

    entrees = []     # (fid, role, normale, point du plan)
    for f in sorted(D):
        d = D[f]
        if not d:
            continue
        if d["genre"] == "PLAN":
            entrees.append((f, "plan de la face", d["dir"], d["pt"]))
        elif d["genre"] == "TORE":
            n = _unit_sign(d["dir"])
            c = d["center"]
            entrees.append((f, "plan médian", n, c))
            entrees.append((f, "plan tangent", n, add(c, mul(n, d["r"]))))
            entrees.append((f, "plan tangent", n, sub(c, mul(n, d["r"]))))
    idx = list(range(len(entrees)))
    comps = _components(
        idx,
        lambda i, j: same_plane(entrees[i][2], entrees[i][3], entrees[j][2], entrees[j][3]),
    )
    brut["coplanaires"] = []
    for c in comps:
        facs = sorted(set(entrees[i][0] for i in c))
        if len(facs) >= 2:
            roles = defaultdict(set)
            for i in c:
                roles[entrees[i][0]].add(entrees[i][1])
            i0 = c[0]
            n = _unit_sign(entrees[i0][2])
            brut["coplanaires"].append((facs, {
                "plan": {"normale": list(n),
                         "d": dot(n, entrees[i0][3]),
                         "equation": "n.x = d"},
                "roles": {str(f): sorted(r) for f, r in roles.items()},
            }))

    # ---- mise en forme des groupes ----------------------------------------
    familles = {}
    for cle, nom, champ, definition in FAMILLES_GEO:
        minimum = 1 if cle in FAMILLES_A_GROUPES_ISOLES else 2   # un plan / rayon seul est un groupe
        groupes = [
            (sorted(set(c)), extra) for c, extra in brut[cle]
            if len(set(c)) >= minimum
        ]
        if cle == "cylindres":
            groupes.sort(key=lambda t: (D[t[0][0]]["radius"], t[0][0]))   # rayon croissant
        else:
            groupes.sort(key=lambda t: (-len(t[0]), t[0][0]))
        out = []
        for gid, (facs, extra) in enumerate(groupes, start=1):
            aire = sum(infos[f]["aire"] for f in facs if infos[f]["aire"] is not None)
            types = defaultdict(int)
            for f in facs:
                types[_type_label(infos[f])] += 1
            g = {"groupe": gid, "nombre_faces": len(facs), "faces": facs,
                 "types_faces": dict(types),
                 "aire_totale": aire if aire > 0 else None}
            d0 = D[facs[0]]
            if cle == "coaxiales":
                n = _unit_sign(d0["dir"])
                g["axe"] = {"point": list(d0["pt"]), "direction": list(n)}
                g["rayons"] = sorted(set(
                    round(D[f].get("radius", D[f].get("r", 0.0)) or 0.0, 4)
                    for f in facs if D[f]["genre"] in ("CYLINDRE", "TORE")))
            elif cle == "paralleles":
                g["type_direction"] = extra["type"]
                g["direction"] = list(_unit_sign(d0["dir"]))
            elif cle == "concentriques":
                g["centre"] = list(d0["center"])
            elif cle == "identiques":
                g["geometrie"] = d0["json"]
                g["contient_equivalents"] = any(D[f]["via_equivalent"] for f in facs)
            elif cle == "cylindres":
                rayons = [D[f]["radius"] for f in facs]
                moyen = sum(rayons) / len(rayons)
                g["rayon"] = round(moyen, 6)
                g["diametre"] = round(2.0 * moyen, 6)
                g["rayon_min"] = round(min(rayons), 6)
                g["rayon_max"] = round(max(rayons), 6)
                g["axes_distincts"] = len(_axes_distincts(
                    [D[f] for f in facs], tol_lin, sin_tol))
                g["contient_equivalents"] = any(D[f]["via_equivalent"] for f in facs)
            elif cle == "plans":
                n_ref = d0["n_out"]
                g["normale"] = list(n_ref)
                g["niveaux"] = _niveaux(
                    sorted(dot(n_ref, D[f]["pt"]) for f in facs), tol_lin
                )
            else:
                g.update(extra)
            out.append(g)
            for f in facs:
                if champ == "groupes_coplanaires":
                    infos[f][champ].append({"groupe": gid,
                                            "role": extra["roles"][str(f)]})
                else:
                    infos[f][champ] = gid
        familles[cle] = {"nom": nom, "definition": definition, "groupes": out}
    return familles


def _axes_distincts(descripteurs, tol_lin, sin_tol):
    """Axes distincts (droites) d'une liste de cylindres."""
    axes = []
    for d in descripteurs:
        for a in axes:
            if (norm(cross(a["dir"], d["dir"])) <= sin_tol
                    and norm(cross(sub(d["pt"], a["pt"]), a["dir"])) <= tol_lin):
                break
        else:
            axes.append(d)
    return axes


def _niveaux(valeurs, tol):
    """Niveaux distincts (à `tol` près) d'une liste triée de valeurs n.x = d ;
    chaque niveau est la moyenne des valeurs qui le composent."""
    amas = []
    for v in valeurs:
        if amas and v - amas[-1][-1] <= tol:
            amas[-1].append(v)
        else:
            amas.append([v])
    return [round(sum(a) / len(a), 4) + 0.0 for a in amas]


def build_tangent_family(groups, infos, tol_deg):
    """Groupe_Tangent au même format que les autres familles.

    Les faces sans voisine tangente forment des groupes d'une face (comme dans
    la numérotation des groupes tangents de tout le programme).
    """
    out = []
    for gid, grp in enumerate(groups, start=1):
        facs = sorted(grp)
        aire = sum(infos[f]["aire"] for f in facs if infos[f]["aire"] is not None)
        types = defaultdict(int)
        for f in facs:
            types[_type_label(infos[f])] += 1
        out.append({
            "groupe": gid,
            "nombre_faces": len(facs),
            "faces": facs,
            "types_faces": dict(types),
            "aire_totale": aire if aire > 0 else None,
            "tolerance_deg": tol_deg,
        })
    return {
        "nom": FAMILLE_TANGENT[1],
        "definition": FAMILLE_TANGENT[3],
        "groupes": out,
    }


def family_partition(familles, cle, faces):
    """Partition des faces (1 groupe par face) pour colorer le STEP.

    Une face présente dans plusieurs groupes (coplanaires) prend son plus
    grand groupe. Les faces hors groupe forment des groupes d'une face.
    """
    primary = {}
    for g in familles[cle]["groupes"]:
        for f in g["faces"]:
            primary.setdefault(f, g["groupe"])
    partition, index_of = [], {}
    for g in familles[cle]["groupes"]:
        membres = [f for f in g["faces"] if primary[f] == g["groupe"]]
        if membres:
            partition.append(membres)
            index_of[g["groupe"]] = len(partition)
    partition += [[f] for f in sorted(faces) if f not in primary]
    group_by_face = {}
    for i, part in enumerate(partition, start=1):
        for f in part:
            group_by_face[f] = i
    return partition, group_by_face, index_of


def _caracteristique_texte(cle, g):
    def z(v):                       # évite l'affichage de « -0.0000 »
        return tuple(round(c, 6) + 0.0 for c in v)

    if cle == "coaxiales":
        a = g["axe"]
        return "axe point=(%.3f, %.3f, %.3f) dir=(%.4f, %.4f, %.4f)" % (
            z(a["point"]) + z(a["direction"]))
    if cle == "paralleles":
        return "%s, direction=(%.4f, %.4f, %.4f)" % ((g["type_direction"],) + z(g["direction"]))
    if cle == "tangent":
        return "tolérance %.3f deg" % g["tolerance_deg"]
    if cle == "cylindres":
        return "rayon=%.4f (diametre %.4f), %d axe(s)" % (
            g["rayon"], g["diametre"], g["axes_distincts"])
    if cle == "plans":
        return "normale=(%.4f, %.4f, %.4f) niveaux=%s" % (
            z(g["normale"]) + (g["niveaux"],))
    if cle == "concentriques":
        return "centre=(%.3f, %.3f, %.3f)" % z(g["centre"])
    if cle == "identiques":
        return json.dumps(_rnd(g["geometrie"]), ensure_ascii=False, separators=(",", ":"))
    p = g["plan"]
    return "plan n=(%.4f, %.4f, %.4f) d=%.4f" % (z(p["normale"]) + (round(p["d"], 6) + 0.0,))
