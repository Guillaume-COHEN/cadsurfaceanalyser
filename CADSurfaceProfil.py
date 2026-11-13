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
CADSurfaceProfil.py : où le temps est-il passé ?

Mesure la durée de chaque étape du traitement (lecture, tangence, géométrie des
faces, familles, colorations) et, avec --fonctions N, affiche les N fonctions
les plus coûteuses de l'étape « géométrie ». N'écrit aucun fichier de sortie.

Toutes les options de CADSurfaceAnalyser.py sont acceptées (--processus,
--precision-numerique, --tol-deg, ...), ce qui permet de comparer des réglages.

    python CADSurfaceProfil.py MaPiece.stp
    python CADSurfaceProfil.py MaPiece.stp --processus 4 --fonctions 15
    python CADSurfaceProfil.py MaPiece.stp --precision-numerique rapide
"""

import contextlib
import cProfile
import io
import pstats
import sys
import time

from cadsurf.options import construire_parser
from cadsurf import pipeline as P
from cadsurf.step_parser import StepFile


def main():
    parser = construire_parser("data/stp_tests/TestAnalyseSurf.stp", 1.0)
    parser.add_argument(
        "--fonctions",
        type=int,
        default=0,
        help="Affiche les N fonctions les plus coûteuses de l'étape géométrie"
    )
    args = parser.parse_args()
    args.sans_geometrie = False
    durees = []
    silence = contextlib.redirect_stdout(io.StringIO())

    def etape(nom, fonction, *a):
        t = time.time()
        with silence:
            resultat = fonction(*a)
        durees.append((nom, time.time() - t))
        return resultat

    step = etape("lecture du STEP", StepFile, args.input)
    analyse = etape("analyse des tangences", P.analyser, step, args)

    profil = cProfile.Profile() if args.fonctions else None
    if profil:
        profil.enable()
    geom = etape("géométrie des faces", P.calculer_geometrie, step, analyse, args)
    if profil:
        profil.disable()
    familles = etape("familles de groupes", P.calculer_familles, analyse, geom, args)
    etape("colorations", P.calculer_colorations, analyse, geom, familles, args)

    total = sum(d for _, d in durees)
    print("Fichier : %s  (%d entités, %d faces)" % (args.input, len(step.ents), len(analyse.faces)))
    print("Réglages : processus=%d  precision-numerique=%s" % (args.processus, args.precision_numerique))
    print()
    for nom, d in durees:
        print("  %-26s %8.2f s  %5.1f %%" % (nom, d, 100.0 * d / total))
    print("  %-26s %8.2f s" % ("TOTAL (hors écriture)", total))
    if profil:
        s = io.StringIO()
        pstats.Stats(profil, stream=s).sort_stats("tottime").print_stats(args.fonctions)
        texte = s.getvalue()
        print()
        print("Fonctions les plus coûteuses (étape géométrie, temps propre) :")
        print(texte[texte.index("ncalls"):])
    return 0


if __name__ == "__main__":
    sys.exit(main())
