#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

"""
CADSurfaceAnalyser.py
========================

Analyse d'un fichier STEP AP214 sans pythonocc-core.

Fonctions principales
--------------------
- Lecture d'un fichier STEP Part 21 avec un parseur Python.
- Extraction des faces ADVANCED_FACE / FACE_SURFACE.
- Identification des arêtes communes entre faces.
- Détection de tangence G1 le long des arêtes communes.
- Echantillonnage des points P2, P3 et P4 uniquement.
- Calcul des normales des surfaces :
    * PLAN
    * CYLINDRICAL_SURFACE
    * CONICAL_SURFACE
    * SPHERICAL_SURFACE
    * TOROIDAL_SURFACE
    * B-SPLINE_SURFACE
- Fusion des faces tangentes par composantes connexes.
- Surfaces gérées pour la tangence ET l'aire : plan, cylindre, cône, sphère,
  tore, B-spline (y compris rationnelles), SURFACE_OF_REVOLUTION et
  SURFACE_OF_LINEAR_EXTRUSION (génératrice B-spline, cercle ou ellipse).
  Une surface de révolution dont la génératrice est un arc de cercle est
  reconnue comme tore (ou sphère) équivalent : champ "type_equivalent".
- Calcul géométrique de chaque face : aire précise, barycentre, périmètre,
  boîte englobante, normale, caractéristiques propres au type (rayon, axe,
  demi-angle, etc.), courbure convexe/concave, voisines, voisines tangentes.
- Huit familles de groupes (Famille_Groupe) :
    Groupe_Tangent, Groupe_Coaxial, Groupe_Parallele, Groupe_Concentrique,
    Groupe_Geometrique_Identique, Groupe_Coplanaire, Groupe_Plan,
    Groupe_Cylindre.
  Groupe_Plan : toutes les faces planes, regroupées par vecteur normal
  identique (normale matière sortante, sens compris).
  Groupe_Cylindre : toutes les faces cylindriques, regroupées par rayon
  identique (même rayon = même groupe = même couleur, quels que soient les axes).
  Tolérances : --tol-deg (tangent), --tol-lin et --tol-angle-geo (autres).
- Un STEP complet coloré par famille : <fichier>_Groupe_Tangent.stp,
  <fichier>_Groupe_Coaxial.stp, ... <fichier>_Groupe_Cylindre.stp
  (--familles-step pour en choisir certaines, ou aucune ; -o pour le nom du
  STEP du Groupe_Tangent).
- Un STEP complet où les faces B_SPLINE_SURFACE sont en violet (les autres en
  gris clair) : <fichier>_bspline_violet.stp, écrit par défaut
  (--sans-stp-bspline pour le désactiver).
- Performances : évaluation B-spline par fonctions de base locales, dérivées
  analytiques, calcul vectorisé avec numpy s'il est installé (optionnel,
  --sans-numpy pour le couper), calcul parallèle des faces lourdes
  (--processus), précision réglable (--precision-numerique).
  CADSurfaceProfil.py mesure les temps.
  Interface graphique : python CADSurfaceGUI.py
  Réglages permanents : constantes PRECISION_NUMERIQUE_DEFAUT,
  UTILISER_NUMPY_DEFAUT et PROCESSUS_DEFAUT, section CONFIGURATION ci-dessous
  (la ligne de commande a la priorité).
- Export JSON (faces, familles de groupes, arêtes, résumé : aire, volume).
- Export CSV des familles, une ligne par groupe, Groupe_Tangent compris
  (--csv-familles)
- Export CSV des faces, une ligne par face     (--csv-faces)
- Export CSV des jonctions entre faces         (--csv)
- Export CSV des groupes tangents (barycentre, boîte)  (--csv-groupes)

Aucune dépendance externe.
Python standard uniquement.

Fichier d'entrée par défaut :
    TestAnalyseSurf.stp
"""

import os
import sys

from cadsurf.options import chemins_sortie, construire_parser, resoudre_numpy
from cadsurf.pipeline import (
    afficher_entete,
    afficher_fin,
    analyser,
    calculer_familles,
    calculer_geometrie,
    calculer_colorations,
    ecrire_csv,
    ecrire_json,
    ecrire_steps,
    lire_step
)


# ============================================================================
# CONFIGURATION
# ============================================================================

FICHIER_ENTREE = "data/stp_tests/TestAnalyseSurf.stp"   # fichier traité si aucun n'est donné en argument


TOLERANCE_ANGULAIRE_DEFAUT = 1

# --- Réglages de vitesse / précision (la ligne de commande a toujours priorité)
# Précision de l'intégration des faces B-spline / révolution / extrusion :
#   "rapide"   erreur sur l'aire ~4e-6   (le plus rapide)
#   "standard" erreur sur l'aire ~1e-6
#   "fine"     erreur sur l'aire ~2e-9   (avec numpy : seulement ~35 % plus lent)
# Équivalent en ligne de commande : --precision-numerique rapide|standard|fine
PRECISION_NUMERIQUE_DEFAUT = "standard"

# numpy (s'il est installé) accélère fortement le calcul. False = Python pur.
# Équivalent en ligne de commande : --sans-numpy (False) ou --avec-numpy (True)
UTILISER_NUMPY_DEFAUT = True

# Nombre de processus pour les faces lourdes : 0 = automatique, 1 = séquentiel,
# N = N processus. Équivalent en ligne de commande : --processus N
PROCESSUS_DEFAUT = 0


# ============================================================================
# RESOLUTION DU FICHIER
# ============================================================================

def resolve_input(path):
    candidates = [
        path,
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            path
        )
    ]

    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)

    raise FileNotFoundError(
        "Fichier STEP introuvable : %s" % path
    )


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Enchaîne les étapes du traitement (voir cadsurf/pipeline.py)."""
    args = construire_parser(
        FICHIER_ENTREE,
        TOLERANCE_ANGULAIRE_DEFAUT,
        PRECISION_NUMERIQUE_DEFAUT,
        PROCESSUS_DEFAUT
    ).parse_args()
    resoudre_numpy(args, UTILISER_NUMPY_DEFAUT)

    try:
        # 1. Entrée et chemins de sortie
        input_path = resolve_input(args.input)
        chemins = chemins_sortie(args, input_path)

        # 2. Lecture, analyse des tangences, géométrie des faces, familles
        afficher_entete(input_path)
        step = lire_step(input_path)
        analyse = analyser(step, args)
        geom = calculer_geometrie(step, analyse, args)
        familles = calculer_familles(analyse, geom, args)
        colorations = calculer_colorations(analyse, geom, familles, args)

        # 3. Sorties
        fichiers_stp = ecrire_steps(
            step, analyse, colorations, args, chemins
        )
        ecrire_json(
            input_path, analyse, geom, familles, args, chemins, fichiers_stp
        )
        ecrire_csv(analyse, geom, familles, args, chemins)

        afficher_fin()
        return 0

    except Exception as exc:
        print()
        print("=" * 78)
        print("ERREUR")
        print("=" * 78)
        print(
            str(exc)
        )
        if not isinstance(exc, FileNotFoundError):
            import traceback               # trace complète, sauf fichier introuvable
            traceback.print_exc()
        return 1


# ============================================================================
# POINT D'ENTREE
# ============================================================================

if __name__ == "__main__":
    sys.exit(
        main()
    )
