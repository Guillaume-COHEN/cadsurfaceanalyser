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
CADSurfaceGUI.py : interface graphique de CADSurfaceAnalyser.

    python CADSurfaceGUI.py

(Windows : CADSurfaceGUI.pyw, identique, s'ouvre sans fenêtre de console.)

La fenêtre permet de choisir le fichier STEP (par défaut le dernier traité), les
STEP colorés à écrire par groupe de faces, les sorties CSV et JSON, le
répertoire de sortie (par défaut celui du STEP), la précision numérique, et
l'utilisation de numpy. Le déroulement du traitement s'affiche comme dans un
terminal. Les réglages sont mémorisés dans ~/.cadsurfaceanalyser_gui.json.
La fenêtre s'adapte à la taille de l'écran ; si son contenu est plus haut que la
fenêtre, un ascenseur vertical apparaît à droite (la molette de la souris fait
défiler la page).

Les tolérances de tangence et des familles restent celles de
CADSurfaceAnalyser.py (section CONFIGURATION).
"""

import sys

from cadsurf.interface import lancer_interface

if __name__ == "__main__":
    sys.exit(lancer_interface())
