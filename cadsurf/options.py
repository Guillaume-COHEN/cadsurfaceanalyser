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

"""Options de la ligne de commande et chemins des fichiers de sortie."""

import argparse
import os
from types import SimpleNamespace

from .familles import TOUTES_LES_FAMILLES


# Sorties JSON / CSV sélectionnables (--sorties)
SORTIES_DISPONIBLES = (
    "json",
    "csv_jonctions",
    "csv_faces",
    "csv_groupes",
    "csv_familles",
)


def construire_parser(
    fichier_defaut,
    tolerance_defaut,
    precision_defaut="standard",
    processus_defaut=0
):
    """Construit l'analyseur d'arguments (valeurs par défaut fournies par le
    script principal)."""
    parser = argparse.ArgumentParser(
        description=(
            "Analyse des tangences de faces STEP "
            "sans pythonocc-core."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=fichier_defaut,
        help=(
            "Fichier STEP d'entrée "
            "(défaut : %s)"
            % fichier_defaut
        )
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "STEP coloré du Groupe_Tangent ; les STEP des autres familles "
            "en dérivent (même nom suivi de _Groupe_X)"
        )
    )
    parser.add_argument(
        "--tol-deg",
        type=float,
        default=tolerance_defaut,
        help=(
            "Tolérance de tangence en degrés "
            "(défaut : %.3f)"
            % tolerance_defaut
        )
    )
    parser.add_argument(
        "--color-singletons",
        action="store_true",
        help=(
            "Attribue aussi une couleur aux faces isolées"
        )
    )
    parser.add_argument(
        "--json",
        help=(
            "Nom du fichier JSON"
        )
    )
    parser.add_argument(
        "--csv",
        help=(
            "Nom du fichier CSV des jonctions entre faces"
        )
    )
    parser.add_argument(
        "--csv-faces",
        help=(
            "Nom du fichier CSV des faces (une ligne par face)"
        )
    )
    parser.add_argument(
        "--csv-groupes",
        help=(
            "Nom du fichier CSV des groupes (une ligne par groupe)"
        )
    )
    parser.add_argument(
        "--virgule-decimale",
        action="store_true",
        help=(
            "Ecrit les nombres des CSV faces/groupes avec une virgule decimale"
        )
    )
    parser.add_argument(
        "--sans-geometrie",
        action="store_true",
        help=(
            "Ne calcule pas aire/barycentre (plus rapide, surtout avec des B-splines)"
        )
    )
    parser.add_argument(
        "--csv-familles",
        help=(
            "Nom du fichier CSV des familles geometriques "
            "(Groupe_Tangent, Groupe_Coaxial, ..., Groupe_Plan)"
        )
    )
    parser.add_argument(
        "--tol-lin",
        type=float,
        default=0.005,
        help=(
            "Tolerance lineaire des familles geometriques, en unite du "
            "fichier (defaut : 0.005)"
        )
    )
    parser.add_argument(
        "--tol-angle-geo",
        type=float,
        default=0.05,
        help=(
            "Tolerance angulaire des familles geometriques, en degres "
            "(defaut : 0.05)"
        )
    )
    parser.add_argument(
        "--sans-numpy",
        action="store_true",
        help=(
            "N'utilise pas numpy (calcul en Python pur, plus lent) ; numpy "
            "est utilise automatiquement s'il est installe"
        )
    )
    parser.add_argument(
        "--avec-numpy",
        action="store_true",
        help=(
            "Utilise numpy meme si UTILISER_NUMPY_DEFAUT vaut False dans le "
            "script (sans effet si numpy n'est pas installe)"
        )
    )
    parser.add_argument(
        "--processus",
        type=int,
        default=processus_defaut,
        help=(
            "Nombre de processus pour le calcul des faces B-spline / revolution "
            "/ extrusion : 0 = automatique (defaut, seulement si assez de "
            "faces et de coeurs), 1 = sequentiel, N = N processus"
        )
    )
    parser.add_argument(
        "--precision-numerique",
        choices=["rapide", "standard", "fine"],
        default=precision_defaut,
        help=(
            "Precision de l'integration des faces B-spline / revolution / "
            "extrusion : rapide (erreur ~4e-6), standard (~1e-6), fine "
            "(~2e-9) ; defaut du script : %s" % precision_defaut
        )
    )
    parser.add_argument(
        "--sorties",
        default="toutes",
        help=(
            "Sorties JSON/CSV a ecrire : 'toutes' (defaut), 'aucune', ou une "
            "liste separee par des virgules parmi "
            + ", ".join(SORTIES_DISPONIBLES)
        )
    )
    parser.add_argument(
        "--dossier-sortie",
        help=(
            "Dossier de tous les fichiers de sortie "
            "(defaut : dossier du fichier STEP d'entree)"
        )
    )
    parser.add_argument(
        "--familles-step",
        default="toutes",
        help=(
            "STEP complets colores a ecrire, un par famille : 'toutes' "
            "(defaut), 'aucune', ou une liste separee par des virgules parmi "
            + ", ".join(c for c, _, _, _ in TOUTES_LES_FAMILLES)
        )
    )
    parser.add_argument(
        "--sans-stp-bspline",
        action="store_true",
        help=(
            "N'ecrit pas le STEP complet ou les faces B_SPLINE_SURFACE sont "
            "en violet (les autres en gris clair), ecrit par defaut"
        )
    )
    parser.add_argument(                  # ancienne option : sans effet
        "--stp-bspline",
        action="store_true",
        help=argparse.SUPPRESS
    )
    return parser


def resoudre_numpy(args, numpy_defaut=True):
    """Décide si numpy est utilisé : --sans-numpy l'emporte, puis --avec-numpy,
    puis la valeur par défaut du script (UTILISER_NUMPY_DEFAUT).
    Positionne args.sans_numpy et retourne le choix."""
    if args.sans_numpy:
        utiliser = False
    elif args.avec_numpy:
        utiliser = True
    else:
        utiliser = bool(numpy_defaut)
    args.sans_numpy = not utiliser
    return utiliser


def familles_step_choisies(args):
    """Clés des familles dont le STEP coloré doit être écrit."""
    cles = [c for c, _, _, _ in TOUTES_LES_FAMILLES]
    choix = (args.familles_step or "toutes").strip().lower()
    if choix == "toutes":
        return cles
    if choix == "aucune":
        return []
    voulues = [x.strip() for x in choix.split(",") if x.strip()]
    inconnues = [x for x in voulues if x not in cles]
    if inconnues:
        raise ValueError(
            "--familles-step : famille inconnue %s (valeurs : %s)"
            % (", ".join(inconnues), ", ".join(cles))
        )
    return [c for c in cles if c in voulues]


def sorties_choisies(args):
    """Sorties JSON/CSV demandées (clés de SORTIES_DISPONIBLES)."""
    choix = (args.sorties or "toutes").strip().lower()
    if choix == "toutes":
        return list(SORTIES_DISPONIBLES)
    if choix == "aucune":
        return []
    voulues = [x.strip() for x in choix.split(",") if x.strip()]
    inconnues = [x for x in voulues if x not in SORTIES_DISPONIBLES]
    if inconnues:
        raise ValueError(
            "--sorties : sortie inconnue %s (valeurs : %s)"
            % (", ".join(inconnues), ", ".join(SORTIES_DISPONIBLES))
        )
    return [x for x in SORTIES_DISPONIBLES if x in voulues]


def chemins_sortie(args, input_path):
    """Chemins de tous les fichiers de sortie."""
    base, _ = os.path.splitext(input_path)
    if getattr(args, "dossier_sortie", None):
        os.makedirs(args.dossier_sortie, exist_ok=True)
        base = os.path.join(args.dossier_sortie, os.path.basename(base))
    racine_step = os.path.splitext(args.output)[0] if args.output else base
    step = {}
    for cle, nom, _, _ in TOUTES_LES_FAMILLES:
        if cle == "tangent" and args.output:
            step[cle] = args.output
        else:
            step[cle] = racine_step + "_" + nom + ".stp"
    return SimpleNamespace(
        base=base,
        step=step,
        json=args.json or base + "_groupes_tangents.json",
        csv=args.csv or base + "_groupes_tangents.csv",
        csv_faces=args.csv_faces or base + "_faces.csv",
        csv_groupes=args.csv_groupes or base + "_groupes.csv",
        csv_familles=args.csv_familles or base + "_familles.csv",
        bspline=base + "_bspline_violet.stp",
    )
