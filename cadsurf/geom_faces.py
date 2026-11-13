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

"""Calcul des caractéristiques de chaque face : aire, barycentre, périmètre,
normale, paramètres propres au type, fiches des faces, groupes et arêtes.
"""

import math
import re
import time
from collections import defaultdict

from . import accel
from .config import K_NUMERIQUE, LIBELLES_TYPES, _GL6, _KINDS_TORE
from .geom_aretes import EdgeGeom
from .geom_surfaces import SurfParam
from .vecteurs import add, dot, mul, norm, sub, unit


# ============================================================================
# GEOMETRIE DES FACES : aire, barycentre, périmètre, caractéristiques
# ============================================================================
#
# Méthode (sans OpenCASCADE) :
#
#   * Chaque face est décrite par ses boucles d'arêtes orientées (EDGE_LOOP).
#   * Chaque arête est paramétrée par t dans [0, 1] (droite, cercle, ellipse,
#     B-spline) ; sa position dans l'espace (u, v) de la surface est obtenue par
#     inversion analytique (plan, cylindre, cône, sphère, tore) ou par
#     Gauss-Newton (B-spline).
#   * Le théorème de Green dans le plan (u, v) transforme chaque intégrale de
#     surface en intégrale curviligne sur les arêtes :
#
#         I = double integrale de g(u,v) du dv = - somme sur les arêtes de G du
#         avec G(u, v) = integrale de g(u, v') dv'  (de v_ref à v)
#
#     Les deux intégrales (G puis le long de l'arête) sont calculées par
#     quadrature de Gauss-Legendre à 6 points, par morceaux : le résultat est
#     exact (à l'arrondi près) pour les surfaces analytiques.
#   * Huit grandeurs sont intégrées en même temps :
#         aire, aire * position (3), aire vectorielle (3), volume (div. théorème)
#
# Limites connues (la face est alors marquée « aire_fiable = false ») :
#   * surfaces d'extrusion / de révolution / offset : non gérées ;
#   * face qui « fait le tour » d'une surface périodique sans arête de couture
#     (calotte sphérique, cône complet...) : gérée pour sphère et cône,
#     sinon signalée ;
#   * arête dont la courbe n'est ni droite, ni cercle, ni ellipse, ni B-spline.
# ============================================================================


def face_loops(step, face):
    """Boucles d'une face : liste de listes [(edge_ref, orientation_bool)]."""
    loops = []
    for bref in face.bounds:
        ba = step.get(bref, "FACE_OUTER_BOUND", "FACE_BOUND")
        if ba is None:
            continue
        loop = step.get(ba[1], "EDGE_LOOP")
        if loop is None:
            continue
        seq = []
        for oe in loop[1]:
            oa = step.get(oe, "ORIENTED_EDGE")
            if oa is not None:
                seq.append((oa[3], str(oa[4]).upper() == "T"))
        if len(ba) > 2 and str(ba[2]).upper() != "T":     # boucle inversée
            seq = [(e, not o) for e, o in reversed(seq)]
        loops.append(seq)
    return loops


def _integrate_edge(sp, eg, orient, vref, start_uv, ext):
    """Contribution de l'arête : somme de G(u,v) du (8 canaux) + UV début/fin."""
    h = 1e-4 if sp.numeric else 1e-6
    if sp.numeric or eg.kind in ("B_SPLINE_CURVE",) or hasattr(eg, "curve"):
        K = K_NUMERIQUE
    elif eg.kind == "LINE" and sp.kind in ("PLANE", "CYLINDRICAL_SURFACE", "CONICAL_SURFACE"):
        K = 1
    else:
        K = eg.n_sub

    if accel.UTILISER and (sp.numeric or K > 1):
        # calcul vectorisé (numpy) de tous les nœuds de l'arête ; en cas de
        # cas dégénéré, le calcul scalaire ci-dessous prend le relais
        try:
            from . import vectoriel
            return vectoriel.integrer_arete(sp, eg, orient, vref, start_uv, ext, K)
        except Exception:
            accel.REPLIS += 1

    def P(t):
        return eg.point_o(orient, min(1.0, max(0.0, t)))

    uv_start = sp.unwrap(sp.inverse(P(0.0), start_uv), start_uv)
    prev = uv_start
    acc = [0.0] * 8
    for k in range(K):
        a, b = k / float(K), (k + 1) / float(K)
        half, mid = (b - a) / 2.0, (a + b) / 2.0
        for x, w in _GL6:
            t = mid + half * x
            uv = sp.unwrap(sp.inverse(P(t), prev), prev)
            du = None
            if sp.numeric:
                # surfaces numériques : vitesse paramétrique directe
                # (évite deux inversions point-surface par nœud)
                dP = eg.tangent_o(orient, t)
                vit = sp.param_velocity(uv, dP)
                if vit is not None:
                    du = vit[0]
            if du is None:
                tp, tm = min(1.0, t + h), max(0.0, t - h)
                up = sp.unwrap(sp.inverse(P(tp), uv), uv)
                um = sp.unwrap(sp.inverse(P(tm), uv), uv)
                du = (up[0] - um[0]) / (tp - tm)
            if du != 0.0:
                G = sp.inner(uv[0], uv[1], vref)
                wt = w * half * du
                for i in range(8):
                    acc[i] += G[i] * wt
            prev = uv
            if uv[0] < ext[0]:
                ext[0] = uv[0]
            if uv[0] > ext[1]:
                ext[1] = uv[0]
            if uv[1] < ext[2]:
                ext[2] = uv[1]
            if uv[1] > ext[3]:
                ext[3] = uv[1]
    uv_end = sp.unwrap(sp.inverse(P(1.0), prev), prev)
    return acc, uv_start, uv_end


def _integrate_face(sp, loops, get_edge, vref=None):
    acc = [0.0] * 8
    net_du = net_dv = 0.0
    ext = [float("inf"), float("-inf"), float("inf"), float("-inf")]
    exact, closed_ok = True, True
    for seq in loops:
        prev, first = None, None
        for eref, orient in seq:
            eg = get_edge(eref)
            if eg is None:
                exact = False
                continue
            if not eg.exact:
                exact = False
            if eg.degenerate:
                continue
            if vref is None:
                if sp.vref0 is not None:
                    vref = sp.vref0
                else:
                    vref = sp.default_vref(sp.inverse(eg.point_o(orient, 0.0), None))
            a, uv0, uv1 = _integrate_edge(sp, eg, orient, vref, prev, ext)
            for i in range(8):
                acc[i] += a[i]
            if first is None:
                first = uv0
            prev = uv1
        if first is not None and prev is not None:
            du, dv = prev[0] - first[0], prev[1] - first[1]
            if sp.period_u is None and abs(du) > 1e-4 * (1.0 + abs(first[0])):
                closed_ok = False
            if sp.period_v is None and abs(dv) > 1e-4 * (1.0 + abs(first[1])):
                closed_ok = False
            net_du += du
            net_dv += dv
    return {
        "acc": acc, "net_du": net_du, "net_dv": net_dv, "ext": ext,
        "exact": exact, "closed_ok": closed_ok, "vref": vref,
    }


def _resolve_face_integrals(sp, loops, get_edge):
    """Intégrales de la face + gestion des surfaces périodiques refermées."""
    res = _integrate_face(sp, loops, get_edge)
    remark = []
    # Un vrai « tour complet » vaut 2*pi ; les petits écarts (~1e-6 rad)
    # viennent de la précision des sommets du fichier STEP.
    winding = (
        abs(res["net_du"]) > 0.5
        or (sp.period_v is not None and abs(res["net_dv"]) > 0.5)
    )
    fiable = res["exact"] and res["closed_ok"]
    if not res["exact"]:
        remark.append("arête de type non géré (corde utilisée)")
    if not res["closed_ok"]:
        remark.append("boucle non fermée dans l'espace paramétrique")
    if winding:
        cand = None
        if sp.kind == "SPHERICAL_SURFACE":
            cand = (math.pi / 2.0, -math.pi / 2.0)
        elif sp.kind == "CONICAL_SURFACE" and abs(sp.tana) > 1e-9:
            cand = (-sp.surf.radius / sp.tana,)
        if cand:
            best = None
            for vr in cand:
                r2 = _integrate_face(sp, loops, get_edge, vref=vr)
                if best is None or abs(r2["acc"][0]) < abs(best["acc"][0]):
                    best = r2
            res = best
            remark.append("face refermée sur un pôle/apex : aire à contrôler")
            fiable = False
        else:
            remark.append("face refermée sur une surface périodique : aire à contrôler")
            fiable = False
    return res, fiable, remark


def _surface_characteristics(face, surf, sp, ext, same_sense, n_out, bary=None):
    """Caractéristiques propres à la face selon le type de surface."""
    out = {"parametres": {}}
    if surf is None:
        return out
    k = surf.kind
    p = out["parametres"]
    f = getattr(surf, "frame", None)
    sgn = 1.0 if same_sense else -1.0
    ext_ok = all(math.isfinite(x) for x in ext)
    ang = math.degrees(ext[1] - ext[0]) if ext_ok and ext[1] > ext[0] else None

    def convexity(factor=1.0):
        return "convexe" if same_sense else "concave"

    if k == "PLANE":
        n = mul(f.z, sgn)
        p.update({"normale_matiere": list(n), "origine": list(f.o),
                  "distance_a_l_origine": dot(f.o, n)})
        out["normale"] = n
        out["courbure"] = "plane"
    elif k == "CYLINDRICAL_SURFACE":
        p.update({"rayon": surf.radius, "axe_origine": list(f.o), "axe_direction": list(f.z)})
        out.update(rayon=surf.radius, axe_origine=f.o, axe_direction=f.z)
        if ext_ok:
            p["longueur_axiale"] = ext[3] - ext[2]
            out["longueur_axiale"] = ext[3] - ext[2]
        if ang is not None:
            p["etendue_angulaire_deg"] = min(ang, 360.0)
            out["etendue_angulaire_deg"] = min(ang, 360.0)
        out["courbure"] = convexity()
    elif k == "CONICAL_SURFACE":
        a = surf.angle
        apex = sub(f.o, mul(f.z, surf.radius / math.tan(a))) if abs(math.tan(a)) > 1e-12 else None
        p.update({"rayon_reference": surf.radius, "demi_angle_deg": math.degrees(a),
                  "axe_origine": list(f.o), "axe_direction": list(f.z),
                  "apex": list(apex) if apex else None})
        out.update(rayon=surf.radius, demi_angle_deg=math.degrees(a),
                   axe_origine=f.o, axe_direction=f.z)
        if ext_ok:
            p["longueur_axiale"] = ext[3] - ext[2]
            out["longueur_axiale"] = ext[3] - ext[2]
        if ang is not None:
            p["etendue_angulaire_deg"] = min(ang, 360.0)
            out["etendue_angulaire_deg"] = min(ang, 360.0)
        out["courbure"] = convexity()
    elif k == "SPHERICAL_SURFACE":
        p.update({"centre": list(f.o), "rayon": surf.radius, "axe_direction": list(f.z)})
        out.update(rayon=surf.radius, axe_origine=f.o, axe_direction=f.z)
        if ang is not None:
            p["etendue_longitude_deg"] = min(ang, 360.0)
            out["etendue_angulaire_deg"] = min(ang, 360.0)
        if ext_ok:
            p["etendue_latitude_deg"] = math.degrees(ext[3] - ext[2])
        out["courbure"] = convexity()
    elif k in _KINDS_TORE:
        p.update({"centre": list(f.o), "axe_direction": list(f.z),
                  "rayon_majeur": surf.major_radius, "rayon_mineur": surf.minor_radius})
        out.update(rayon_majeur=surf.major_radius, rayon_mineur=surf.minor_radius,
                   rayon=surf.minor_radius, axe_origine=f.o, axe_direction=f.z)
        if ang is not None:
            p["etendue_angulaire_deg"] = min(ang, 360.0)
            out["etendue_angulaire_deg"] = min(ang, 360.0)
        zone = None
        if ext_ok:
            vm = 0.5 * (ext[2] + ext[3])
            zone = "externe" if math.cos(vm) > 0 else "interne"
            p["zone_du_tore"] = zone
        if zone == "interne":
            out["courbure"] = "selle"
        else:
            out["courbure"] = convexity()
    elif k == "SURFACE_OF_REVOLUTION":
        rev = surf.rev
        p.update({"axe_origine": list(rev.o), "axe_direction": list(rev.z),
                  "generatrice": rev.curve.kind})
        out.update(axe_origine=rev.o, axe_direction=rev.z)
        if ang is not None:
            p["etendue_angulaire_deg"] = min(ang, 360.0)
            out["etendue_angulaire_deg"] = min(ang, 360.0)
        out["courbure"] = "indéterminée"
        fit = rev.fit_circle(ext[2], ext[3]) if ext_ok else rev.fit_circle()
        if fit and fit["ecart_max"] <= 5e-4 * fit["rayon"]:
            r_t, rho_c = fit["rayon"], fit["rho_c"]
            centre_axe = add(rev.o, mul(rev.z, fit["z_c"]))
            eq = {"ecart_ajustement_max": fit["ecart_max"],
                  "rayon_mineur": r_t, "centre_sur_axe": list(centre_axe)}
            if abs(rho_c) <= 1e-3 * r_t:
                out["type_equivalent"] = "SPHERICAL_SURFACE"
                out["type_equivalent_fr"] = "Sphère (ajustée)"
                eq["rayon"] = r_t
                out["rayon"] = r_t
            else:
                out["type_equivalent"] = "TOROIDAL_SURFACE"
                out["type_equivalent_fr"] = "Tore (ajusté)"
                eq["rayon_majeur"] = abs(rho_c)
                out["rayon_majeur"] = abs(rho_c)
                out["rayon_mineur"] = r_t
                out["rayon"] = r_t
            p["equivalent"] = eq
            if bary is not None and n_out is not None:
                th = rev._polar(bary)[0]
                er = add(mul(rev.x, math.cos(th)), mul(rev.y, math.sin(th)))
                c_tube = add(centre_axe, mul(er, rho_c))
                dirv = unit(sub(bary, c_tube))
                if dirv is not None:
                    out["courbure"] = "convexe" if dot(n_out, dirv) > 0 else "concave"
    elif k == "SURFACE_OF_LINEAR_EXTRUSION":
        e = surf.ext
        p.update({"direction_extrusion": list(e.d), "generatrice": e.curve.kind})
        out.update(axe_direction=e.d)
        out["courbure"] = "indéterminée"
        if (e.curve.kind == "CIRCLE" and e.curve.radius
                and abs(dot(e.curve.normal, e.d)) > 1.0 - 1e-9):
            out["type_equivalent"] = "CYLINDRICAL_SURFACE"
            out["type_equivalent_fr"] = "Cylindre (équivalent)"
            out["rayon"] = e.curve.radius
            p["equivalent"] = {"rayon": e.curve.radius}
    elif k == "B_SPLINE_SURFACE":
        b = surf.bs
        p.update({
            "degre_u": b.du, "degre_v": b.dv,
            "points_controle_u": len(b.ctrl), "points_controle_v": len(b.ctrl[0]),
            "domaine_u": [b.u0, b.u1], "domaine_v": [b.v0, b.v1],
            "rationnelle": any(abs(row[3] - 1.0) > 1e-12 for r in b.ctrl for row in r),
        })
        out["courbure"] = "indéterminée"
    if "normale" not in out and n_out is not None:
        out["normale"] = n_out
    return out


def detect_unites(step):
    """Unité de longueur du fichier (mm, m, in...) d'après les SI_UNIT."""
    t = re.sub(r"\s+", "", step.text.upper())
    if "SI_UNIT(.MILLI.,.METRE.)" in t:
        return "mm"
    if "SI_UNIT(.CENTI.,.METRE.)" in t:
        return "cm"
    if "SI_UNIT($,.METRE.)" in t:
        return "m"
    if "INCH" in t:
        return "in"
    return "unité du fichier"


def compute_face_geometry(
    step, faces, results, group_by_face, colors, calcul_integrales=True,
    precalcules=None
):
    """Calcule pour chaque face toutes les caractéristiques exportées.

    `precalcules` : intégrales déjà calculées (voir parallele.py), sinon calcul
    séquentiel. Retourne (infos, edge_cache, resume).
    """
    t_start = time.time()
    edge_cache = {}

    def get_edge(ref):
        if ref not in edge_cache:
            try:
                edge_cache[ref] = EdgeGeom(step, ref)
            except Exception:
                edge_cache[ref] = None
        return edge_cache[ref]

    neighbors = defaultdict(set)
    tangent_neighbors = defaultdict(set)
    for r in results:
        neighbors[r["face_a"]].add(r["face_b"])
        neighbors[r["face_b"]].add(r["face_a"])
        if r["tangent"]:
            tangent_neighbors[r["face_a"]].add(r["face_b"])
            tangent_neighbors[r["face_b"]].add(r["face_a"])

    group_sizes = defaultdict(int)
    for g in group_by_face.values():
        group_sizes[g] += 1

    infos = {}
    total = len(faces)
    for count, fid in enumerate(sorted(faces), start=1):
        face = faces[fid]
        surf = face.surface
        gid = group_by_face[fid]
        rgb = colors[gid]
        info = {
            "id": fid,
            "nom": face.name,
            "type": surf.kind if surf else None,
            "type_fr": LIBELLES_TYPES.get(surf.kind if surf else "", "Inconnu"),
            "surface_ref": face.surf_ref,
            "sens_surface_conserve": face.same_sense,
            "groupe": gid,
            "groupe_nb_faces": group_sizes[gid],
            "couleur_rgb": [round(c, 6) for c in rgb],
            "couleur_rgb_255": [int(round(c * 255)) for c in rgb],
            "couleur_hex": "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb),
            "aretes": [],
            "faces_voisines": sorted(neighbors.get(fid, [])),
            "faces_voisines_tangentes": sorted(tangent_neighbors.get(fid, [])),
            "aire": None, "aire_fiable": False, "aire_methode": None,
            "aire_remarque": "", "barycentre": None, "normale_moyenne": None,
            "perimetre": None, "nb_boucles": 0, "nb_trous": 0,
            "boite_englobante": None, "volume_signe": None,
            "courbure": None, "parametres": {},
            "type_equivalent": None, "type_equivalent_fr": None,
        }
        try:
            seen, uniq = set(), []
            for e in face.edges:
                if e not in seen:
                    seen.add(e)
                    uniq.append(e)
            occurrences = defaultdict(int)
            for e in face.edges:
                occurrences[e] += 1
            info["aretes"] = uniq
            info["nb_aretes"] = len(uniq)

            loops = face_loops(step, face)
            info["nb_boucles"] = len(loops)
            info["nb_trous"] = max(0, len(loops) - 1)

            # périmètre et boîte englobante (arêtes)
            perim = 0.0
            lo = [float("inf")] * 3
            hi = [float("-inf")] * 3
            for e in uniq:
                eg = get_edge(e)
                if eg is None:
                    continue
                if occurrences[e] == 1:
                    perim += eg.length()
                a, b = eg.bbox()
                for i in range(3):
                    lo[i] = min(lo[i], a[i])
                    hi[i] = max(hi[i], b[i])
            info["perimetre"] = perim
            if lo[0] != float("inf"):
                info["boite_englobante"] = {
                    "min": list(lo), "max": list(hi),
                    "dimensions": [hi[i] - lo[i] for i in range(3)],
                }

            ext = [float("inf"), float("-inf"), float("inf"), float("-inf")]
            n_out = None
            if (
                calcul_integrales
                and surf is not None
                and surf.supported
                and surf.kind in LIBELLES_TYPES
            ):
                sp = SurfParam(surf)
                if precalcules and fid in precalcules:
                    res, fiable, remark = precalcules[fid]      # calcul parallèle
                else:
                    res, fiable, remark = _resolve_face_integrals(sp, loops, get_edge)
                R = [-c for c in res["acc"]]
                if R[0] < 0.0:
                    R = [-c for c in R]
                area = R[0]
                ext = res["ext"]
                if area > 0.0:
                    sgn = 1.0 if face.same_sense else -1.0
                    info["aire"] = area
                    info["barycentre"] = [R[1] / area, R[2] / area, R[3] / area]
                    nv = (sgn * R[4], sgn * R[5], sgn * R[6])
                    nn = norm(nv)
                    if nv is not None and nn > 1e-9 * area:
                        n_out = (nv[0] / nn, nv[1] / nn, nv[2] / nn)
                        info["normale_moyenne"] = list(n_out)
                    info["_vecteur_aire"] = nv
                    info["volume_signe"] = sgn * R[7]
                    info["aire_methode"] = (
                        "Green + Gauss-Legendre (analytique)"
                        if not sp.is_bspline
                        else "Green + Gauss-Legendre (B-spline, numérique)"
                    )
                else:
                    fiable = False
                    remark.append("aire nulle ou non calculable")
                info["aire_fiable"] = bool(fiable and area > 0.0)
                info["aire_remarque"] = " ; ".join(remark)
            elif calcul_integrales:
                info["aire_methode"] = "non supportée"
                info["aire_remarque"] = "type de surface non géré"
                sp = None

            carac = _surface_characteristics(
                face, surf, None, ext, face.same_sense, n_out,
                info["barycentre"],
            )
            info["type_equivalent"] = carac.get("type_equivalent")
            info["type_equivalent_fr"] = carac.get("type_equivalent_fr")
            info["parametres"] = carac.pop("parametres", {})
            info["courbure"] = carac.get("courbure")
            for key in (
                "rayon", "rayon_majeur", "rayon_mineur", "demi_angle_deg",
                "axe_origine", "axe_direction", "longueur_axiale",
                "etendue_angulaire_deg", "normale",
            ):
                if key in carac:
                    v = carac[key]
                    info["_" + key] = list(v) if isinstance(v, tuple) else v
        except Exception as exc:
            info["aire_remarque"] = "erreur de calcul : %s" % exc
        infos[fid] = info
        if calcul_integrales and (count % 10 == 0 or count == total):
            print("  faces traitées : %d / %d" % (count, total))

    # résumé global
    areas = [i["aire"] for i in infos.values() if i["aire"] is not None]
    aire_totale = sum(areas)
    vecteur = [0.0, 0.0, 0.0]
    volume = 0.0
    complet = all(i["aire"] is not None for i in infos.values())
    for i in infos.values():
        if i.get("_vecteur_aire") is not None:
            for c in range(3):
                vecteur[c] += i["_vecteur_aire"][c]
        if i["volume_signe"] is not None:
            volume += i["volume_signe"]
    resume = {
        "unite_longueur": detect_unites(step),
        "aire_totale": aire_totale if areas else None,
        "volume_estime": volume if (areas and complet) else None,
        "controle_fermeture_aire_vectorielle": (
            norm(vecteur) / aire_totale if (areas and aire_totale > 0) else None
        ),
        "faces_aire_non_fiable": sorted(
            i["id"] for i in infos.values() if not i["aire_fiable"]
        ),
        "temps_calcul_s": round(time.time() - t_start, 3),
    }
    return infos, edge_cache, resume


def build_group_infos(groups, infos, colors):
    """Synthèse par groupe de faces tangentes."""
    out = []
    for index, group in enumerate(groups, start=1):
        rgb = colors[index]
        aire = 0.0
        moment = [0.0, 0.0, 0.0]
        types = defaultdict(int)
        lo = [float("inf")] * 3
        hi = [float("-inf")] * 3
        complet = True
        for fid in sorted(group):
            i = infos[fid]
            types[i["type_fr"]] += 1
            if i["aire"] is None or i["barycentre"] is None:
                complet = False
            else:
                aire += i["aire"]
                for c in range(3):
                    moment[c] += i["aire"] * i["barycentre"][c]
            b = i["boite_englobante"]
            if b:
                for c in range(3):
                    lo[c] = min(lo[c], b["min"][c])
                    hi[c] = max(hi[c], b["max"][c])
        out.append({
            "groupe": index,
            "nombre_faces": len(group),
            "faces": sorted(group),
            "types_faces": dict(types),
            "aire_totale": aire if aire > 0 else None,
            "aire_complete": complet,
            "barycentre": (
                [m / aire for m in moment] if aire > 0 else None
            ),
            "boite_englobante": (
                {"min": lo, "max": hi, "dimensions": [hi[c] - lo[c] for c in range(3)]}
                if lo[0] != float("inf") else None
            ),
            "couleur_rgb": [round(c, 6) for c in rgb],
            "couleur_rgb_255": [int(round(c * 255)) for c in rgb],
            "couleur_hex": "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb),
        })
    return out


def build_edge_infos(edge_cache, faces, results):
    """Détail de toutes les arêtes (longueur, type, faces adjacentes, tangence)."""
    edge_faces = defaultdict(list)
    for f in faces.values():
        for e in set(f.edges):
            edge_faces[e].append(f.id)
    tang = defaultdict(bool)
    angle = {}
    for r in results:
        if r["tangent"]:
            tang[r["edge"]] = True
        if r["max_angle_deg"] is not None:
            angle[r["edge"]] = max(angle.get(r["edge"], 0.0), r["max_angle_deg"])
    out = {}
    for e in sorted(edge_faces):
        eg = edge_cache.get(e)
        d = {
            "faces_adjacentes": sorted(edge_faces[e]),
            "tangente": bool(tang[e]),
            "angle_max_deg": angle.get(e),
        }
        if eg is not None:
            d.update({
                "type_courbe": eg.kind,
                "longueur": eg.length(),
                "sommet_debut": list(eg.p1),
                "sommet_fin": list(eg.p2),
            })
        out[str(e)] = d
    return out
