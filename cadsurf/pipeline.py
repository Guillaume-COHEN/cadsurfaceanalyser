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

"""Étapes du traitement, appelées dans l'ordre par le script principal :
lecture, analyse, géométrie, familles de groupes, colorations, exports.

Chaque fonction affiche sa progression sur la console ; les résultats
intermédiaires sont transmis dans des SimpleNamespace.
"""

import os
from types import SimpleNamespace

from . import accel, geom_faces
from .config import GRIS, PRECISIONS_NUMERIQUES, VIOLET
from .couleurs import create_group_colors
from .export_csv import (
    write_csv,
    write_faces_csv,
    write_families_csv,
    write_groups_csv
)
from .export_json import write_json
from .export_step import write_colored_step
from .familles import (
    FAMILLE_TANGENT,
    FAMILLES_A_GROUPES_ISOLES,
    FAMILLES_GEO,
    TOUTES_LES_FAMILLES,
    build_geometric_families,
    build_tangent_family,
    family_partition
)
from .geom_faces import build_edge_infos, build_group_infos, compute_face_geometry
from .options import familles_step_choisies, sorties_choisies
from .parallele import integrales_lourdes_en_parallele
from .rapports import print_families_report, print_geometry_report, print_report
from .step_parser import StepFile
from .tangence import analyse


# ============================================================================
# ENTETE ET LECTURE
# ============================================================================

def afficher_entete(input_path):
    print("=" * 78)
    print("ANALYSE STEP - SANS PYTHONOCC-CORE")
    print("=" * 78)
    print("Fichier d'entrée :")
    print("  %s" % input_path)
    print()


def lire_step(input_path):
    print("Lecture du fichier STEP...")
    step = StepFile(input_path)
    print("Entités STEP lues : %d" % len(step.ents))
    return step


def afficher_fin():
    print()
    print("=" * 78)
    print("TERMINE")
    print("=" * 78)


# ============================================================================
# ANALYSE (tangence, groupes tangents, couleurs)
# ============================================================================

def analyser(step, args):
    """Faces, jonctions, groupes tangents et couleurs des groupes."""
    print()
    print("Analyse des faces et des tangences...")
    faces, results, groups, group_by_face = analyse(step, args.tol_deg)
    colors = create_group_colors(groups, args.color_singletons)
    print_report(faces, results, groups, group_by_face, colors, args.tol_deg)
    return SimpleNamespace(
        faces=faces,
        results=results,
        groups=groups,
        group_by_face=group_by_face,
        colors=colors,
    )


# ============================================================================
# GEOMETRIE DES FACES
# ============================================================================

def calculer_geometrie(step, a, args):
    """Aire, barycentre et caractéristiques de chaque face."""
    print()
    print("Calcul des caractéristiques des faces...")
    geom_faces.K_NUMERIQUE = PRECISIONS_NUMERIQUES[args.precision_numerique]
    accel.REPLIS = 0
    accel.activer(not args.sans_numpy)
    if accel.UTILISER:
        print("Accélération numpy %s : activée" % accel.version())
    elif not accel.DISPONIBLE:
        print("numpy non installé : calcul en Python pur (plus lent)")
    else:
        print("numpy désactivé : calcul en Python pur")
    precalcules = None
    if not args.sans_geometrie:
        precalcules = integrales_lourdes_en_parallele(
            step, a.faces, args.processus, k_numerique=geom_faces.K_NUMERIQUE,
            numpy_actif=accel.UTILISER
        )
    infos, edge_cache, resume = compute_face_geometry(
        step,
        a.faces,
        a.results,
        a.group_by_face,
        a.colors,
        calcul_integrales=not args.sans_geometrie,
        precalcules=precalcules
    )
    if accel.REPLIS:
        print(
            "Note : %d arête(s) recalculée(s) en mode scalaire "
            "(cas dégénérés pour le calcul vectorisé)." % accel.REPLIS
        )
    group_infos = build_group_infos(a.groups, infos, a.colors)
    edge_infos = build_edge_infos(edge_cache, a.faces, a.results)
    if not args.sans_geometrie:
        print_geometry_report(infos, resume, group_infos)
    return SimpleNamespace(
        infos=infos,
        edge_cache=edge_cache,
        resume=resume,
        group_infos=group_infos,
        edge_infos=edge_infos,
    )


# ============================================================================
# FAMILLES DE GROUPES (Famille_Groupe)
# ============================================================================

def calculer_familles(a, g, args):
    """Toutes les familles : Groupe_Tangent en tête (au même format que les
    autres), puis coaxial, parallèle, concentrique, géométrie identique,
    coplanaire et plan."""
    print()
    print("Calcul des familles de groupes...")
    geo = build_geometric_families(
        a.faces,
        g.infos,
        args.tol_lin,
        args.tol_angle_geo
    )
    familles = {"tangent": build_tangent_family(a.groups, g.infos, args.tol_deg)}
    familles.update(geo)
    print_families_report(familles)
    return familles


# ============================================================================
# COLORATIONS (une par famille)
# ============================================================================

def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb)


def _couleur_fiche(rgb):
    return (
        [round(c, 6) for c in rgb],
        [int(round(c * 255)) for c in rgb],
        _hex(rgb),
    )


def calculer_colorations(a, g, familles, args):
    """Partition des faces et couleurs pour chaque famille.

    Retourne un dict famille -> SimpleNamespace(nom, groups, by_face,
    color_map). Les fiches des faces reçoivent `couleurs_hex` (une couleur par
    famille) et les groupes de chaque famille reçoivent leur couleur.

    Règles :
      * Groupe_Tangent : couleurs des groupes tangents, faces isolées en gris
        (sauf --color-singletons) ;
      * autres familles : faces hors groupe en gris (sauf --color-singletons) ;
      * Groupe_Plan et Groupe_Cylindre : tout groupe est coloré, même réduit à
        une face ; les faces hors famille (non planes, non cylindriques) sont
        en gris. Pour les cylindres : même couleur = même rayon.
    """
    cols = {}
    cols["tangent"] = SimpleNamespace(
        nom=FAMILLE_TANGENT[1],
        groups=a.groups,
        by_face=a.group_by_face,
        color_map=a.colors,
        index_of={i: i for i in range(1, len(a.groups) + 1)},
    )
    for cle, nom, _, _ in FAMILLES_GEO:
        partition, by_face, index_of = family_partition(familles, cle, a.faces)
        if cle in FAMILLES_A_GROUPES_ISOLES:
            color_map = create_group_colors(partition, True)
            if not args.color_singletons:
                membres = set(index_of.values())
                for idx in range(1, len(partition) + 1):
                    if idx not in membres:
                        color_map[idx] = GRIS
        else:
            color_map = create_group_colors(partition, args.color_singletons)
        cols[cle] = SimpleNamespace(
            nom=nom,
            groups=partition,
            by_face=by_face,
            color_map=color_map,
            index_of=index_of,
        )

    # couleur de chaque face et de chaque groupe, famille par famille
    for info in g.infos.values():
        info["couleurs_hex"] = {}
    for cle, nom, _, _ in TOUTES_LES_FAMILLES:
        col = cols[cle]
        for fid, info in g.infos.items():
            info["couleurs_hex"][nom] = _hex(col.color_map[col.by_face[fid]])
        for grp in familles[cle]["groupes"]:
            idx = col.index_of.get(grp["groupe"])
            if idx:
                (
                    grp["couleur_rgb"],
                    grp["couleur_rgb_255"],
                    grp["couleur_hex"]
                ) = _couleur_fiche(col.color_map[idx])
    return cols


# ============================================================================
# EXPORTS STEP (complets, colorés)
# ============================================================================

def _relatif(chemin, chemins):
    return os.path.relpath(chemin, os.path.dirname(chemins.base) or ".")


def ecrire_steps_familles(step, a, colorations, args, chemins):
    """Un STEP complet coloré par famille (--familles-step)."""
    cles = familles_step_choisies(args)
    print()
    print("Génération des STEP AP214 colorés par famille de groupes...")
    ecrits = {}
    for cle in cles:
        col = colorations[cle]
        chemin = chemins.step[cle]
        write_colored_step(
            step,
            chemin,
            a.faces,
            col.groups,
            col.by_face,
            col.color_map
        )
        if not os.path.isfile(chemin):
            raise RuntimeError(
                "Le fichier STEP de sortie "
                "n'a pas été créé : %s" % chemin
            )
        print("STEP %s : %s" % (col.nom, chemin))
        ecrits[col.nom] = _relatif(chemin, chemins)
    if not cles:
        print("Aucun STEP de famille demandé (--familles-step aucune).")
    return ecrits


def ecrire_step_bspline(step, a, chemins):
    """STEP complet où les faces B_SPLINE_SURFACE sont en violet (les autres
    faces en gris clair). Retourne le chemin relatif, ou None."""
    bspl = sorted(
        f for f, fc in a.faces.items()
        if fc.surface is not None and fc.surface.kind == "B_SPLINE_SURFACE"
    )
    print()
    print("Génération du STEP des faces B_SPLINE_SURFACE (violet)...")
    if not bspl:
        print("Aucune face B_SPLINE_SURFACE : STEP violet non créé.")
        return None
    autres = sorted(set(a.faces) - set(bspl))
    groupes = [bspl] + ([autres] if autres else [])
    write_colored_step(
        step,
        chemins.bspline,
        a.faces,
        groupes,
        {f: (1 if f in bspl else 2) for f in a.faces},
        {1: VIOLET, 2: GRIS}
    )
    print(
        "STEP B-spline en violet (%d face(s)) : %s"
        % (len(bspl), chemins.bspline)
    )
    return {
        "faces_bspline": bspl,
        "couleur_hex": _hex(VIOLET),
        "fichier": _relatif(chemins.bspline, chemins),
    }


def ecrire_steps(step, a, colorations, args, chemins):
    """STEP des familles + STEP des faces B_SPLINE_SURFACE (sauf
    --sans-stp-bspline). Retourne la liste des fichiers écrits pour le JSON."""
    fichiers = {"familles": ecrire_steps_familles(step, a, colorations, args, chemins)}
    if not args.sans_stp_bspline:
        fichiers["bspline_violet"] = ecrire_step_bspline(step, a, chemins)
    return fichiers


# ============================================================================
# EXPORTS JSON ET CSV
# ============================================================================

def ecrire_json(input_path, a, g, familles, args, chemins, fichiers_stp=None):
    if "json" not in sorties_choisies(args):
        return
    print("Génération du JSON...")
    write_json(
        chemins.json,
        input_path,
        args.tol_deg,
        a.faces,
        a.results,
        a.groups,
        a.group_by_face,
        a.colors,
        infos=g.infos,
        resume=g.resume,
        group_infos=g.group_infos,
        edge_infos=g.edge_infos,
        familles=familles,
        coloration=None,
        fichiers_stp=fichiers_stp
    )
    print("JSON : %s" % chemins.json)


def ecrire_csv(a, g, familles, args, chemins):
    sorties = sorties_choisies(args)
    if "csv_jonctions" in sorties:
        print("Génération du CSV...")
        write_csv(chemins.csv, a.results, a.group_by_face)
        print("CSV : %s" % chemins.csv)
    if any(k in sorties for k in ("csv_faces", "csv_groupes", "csv_familles")):
        print("Génération des CSV faces et groupes...")
    if "csv_faces" in sorties:
        write_faces_csv(chemins.csv_faces, g.infos, args.virgule_decimale)
        print("CSV faces : %s" % chemins.csv_faces)
    if "csv_groupes" in sorties:
        write_groups_csv(chemins.csv_groupes, g.group_infos, args.virgule_decimale)
        print("CSV groupes : %s" % chemins.csv_groupes)
    if "csv_familles" in sorties:
        write_families_csv(chemins.csv_familles, familles, args.virgule_decimale)
        print("CSV familles : %s" % chemins.csv_familles)
