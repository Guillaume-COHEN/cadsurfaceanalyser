#!/usr/bin/env python3
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

"""Renseigne les informations propres à votre dépôt GitHub.

Le dépôt est livré avec deux marqueurs à remplacer :

    TITULAIRE_A_COMPLETER   votre nom (ou celui de votre organisation)
    OWNER/REPO              l'adresse GitHub : nom d'utilisateur/nom du dépôt

Usage :
    python tools/configurer_depot.py --titulaire "Prénom Nom" --depot utilisateur/nom-du-depot
    python tools/configurer_depot.py --verifier      # liste ce qui reste à compléter

Les fichiers modifiés sont : NOTICE, CITATION.cff, pyproject.toml, README.md,
README.en.md, CONTRIBUTING.md, SECURITY.md et le dossier .github/.
"""

import argparse
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JETON_TITULAIRE = "TITULAIRE_A_COMPLETER"
JETON_DEPOT = "OWNER/REPO"

DOSSIERS_IGNORES = {".git", "__pycache__", "data", "tests", "build", "dist", ".venv", "venv"}
FICHIERS_IGNORES = {"LICENSE", os.path.join("tools", "configurer_depot.py")}
EXTENSIONS = {".md", ".toml", ".yml", ".yaml", ".cff", ".txt", ".cfg", ".ini", ""}


def fichiers_texte():
    for dossier, sous_dossiers, fichiers in os.walk(RACINE):
        sous_dossiers[:] = [d for d in sous_dossiers if d not in DOSSIERS_IGNORES]
        for nom in sorted(fichiers):
            chemin = os.path.join(dossier, nom)
            relatif = os.path.relpath(chemin, RACINE)
            if relatif in FICHIERS_IGNORES or nom.startswith(".git"):
                continue
            if os.path.splitext(nom)[1].lower() in EXTENSIONS:
                yield chemin, relatif


def lire(chemin):
    try:
        with open(chemin, encoding="utf-8", newline="") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def occurrences():
    """[(fichier, numéro de ligne, texte)] des marqueurs encore présents."""
    trouves = []
    for chemin, relatif in fichiers_texte():
        texte = lire(chemin)
        if texte is None:
            continue
        for i, ligne in enumerate(texte.split("\n"), 1):
            if JETON_TITULAIRE in ligne or JETON_DEPOT in ligne:
                trouves.append((relatif, i, ligne.strip()))
    return trouves


def verifier():
    restes = occurrences()
    if not restes:
        print("Rien à compléter : tous les marqueurs sont renseignés.")
        return 0
    print("%d marqueur(s) à compléter :" % len(restes))
    for relatif, i, ligne in restes:
        print("  %s:%d  %s" % (relatif, i, ligne[:90]))
    print("\nLancez : python tools/configurer_depot.py --titulaire \"Prénom Nom\" "
          "--depot utilisateur/nom-du-depot")
    return 1


def configurer(titulaire, depot):
    titulaire = titulaire.strip()
    if not titulaire or any(c in titulaire for c in '"\\\n\r'):
        print("Erreur : --titulaire doit être non vide et ne pas contenir de guillemet, "
              "de barre oblique inverse ni de retour à la ligne.")
        return 2
    if not re.match(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*)/[A-Za-z0-9._-]+$", depot):
        print("Erreur : --depot doit avoir la forme utilisateur/nom-du-depot "
              "(lettres, chiffres, tirets, points, soulignés).")
        return 2
    modifies = []
    for chemin, relatif in fichiers_texte():
        texte = lire(chemin)
        if texte is None or (JETON_TITULAIRE not in texte and JETON_DEPOT not in texte):
            continue
        nouveau = texte.replace(JETON_TITULAIRE, titulaire).replace(JETON_DEPOT, depot)
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            f.write(nouveau)
        modifies.append(relatif)
    print("%d fichier(s) modifié(s) :" % len(modifies))
    for relatif in modifies:
        print("  " + relatif)
    restes = occurrences()
    if restes:
        print("Attention : %d marqueur(s) subsistent." % len(restes))
        return 1
    print("Terminé : titulaire = %r, dépôt = %s" % (titulaire, depot))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Renseigne le titulaire du copyright et l'adresse GitHub du dépôt."
    )
    parser.add_argument("--titulaire", help="votre nom ou celui de votre organisation")
    parser.add_argument("--depot", help="utilisateur/nom-du-depot (adresse GitHub)")
    parser.add_argument("--verifier", action="store_true",
                        help="liste les marqueurs encore à compléter, sans rien modifier")
    args = parser.parse_args()
    if args.verifier:
        return verifier()
    if not args.titulaire or not args.depot:
        parser.error("--titulaire et --depot sont obligatoires (ou utilisez --verifier)")
    return configurer(args.titulaire, args.depot)


if __name__ == "__main__":
    sys.exit(main())
