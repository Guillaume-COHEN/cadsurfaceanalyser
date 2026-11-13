# CADSurfaceAnalyser

[![tests](https://github.com/Guillaume-COHEN/cadsurfaceanalyser/actions/workflows/ci.yml/badge.svg)](https://github.com/Guillaume-COHEN/cadsurfaceanalyser/actions/workflows/ci.yml)
[![Licence : Apache 2.0](https://img.shields.io/badge/licence-Apache%202.0-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)

Analyse les surfaces d'un fichier **STEP AP214** (solide B-Rep) **sans OpenCASCADE** :
groupes de faces tangentes, aire et barycentre de chaque face, familles de faces de
même géométrie, et exports en **STEP colorés**, **JSON** et **CSV**. Une interface
graphique est fournie.

*English summary: see [README.en.md](README.en.md).*

## Ce que fait le programme

- **Lit** le STEP (ISO 10303-21 / AP214) avec un lecteur écrit pour le projet :
  plans, cylindres, cônes, sphères, tores, surfaces de révolution et d'extrusion,
  surfaces B-spline et NURBS (rationnelles comprises).
- **Détecte la tangence** entre faces voisines (continuité G1, tolérance réglable)
  et forme les **groupes de faces tangentes**.
- **Calcule pour chaque face** l'aire, le barycentre, le périmètre, la boîte
  englobante, la normale, le caractère convexe ou concave, les paramètres propres au
  type de surface (rayon, axe, demi-angle...), et le volume du solide.
- **Classe les faces en huit familles de groupes** (voir plus bas).
- **Écrit** un STEP complet coloré par famille, un STEP où les surfaces B-spline sont
  en violet, un JSON et quatre CSV.

Toutes les équations utilisées (B-splines, théorème de Green, quadrature, familles...)
sont décrites dans la documentation technique ([docs/](docs/README.md)).

## Installation

Python 3.8 ou plus récent. **Aucune dépendance obligatoire.**

```bash
git clone https://github.com/Guillaume-COHEN/cadsurfaceanalyser.git
cd REPO
python CADSurfaceAnalyser.py --help
```

Recommandé : [numpy](https://numpy.org) accélère fortement le calcul des faces à
surface B-spline, de révolution ou d'extrusion (3 à 4 fois, voir plus bas). Il est
détecté automatiquement ; sans lui, le programme fonctionne en Python pur.

```bash
python -m pip install -r requirements.txt    # installe numpy (optionnel)
```

L'interface graphique utilise `tkinter`, livré avec Python sous Windows et macOS.
Sous Linux Debian/Ubuntu : `sudo apt install python3-tk`.

Installation comme paquet (facultative) : `python -m pip install .` crée les commandes
`cadsurface`, `cadsurface-gui` et `cadsurface-profil`.

## Utilisation

```bash
python CADSurfaceAnalyser.py MaPiece.stp                       # tout, avec les réglages par défaut
python CADSurfaceAnalyser.py MaPiece.stp --tol-deg 0.5         # tolérance de tangence (degrés)
python CADSurfaceAnalyser.py MaPiece.stp --tol-lin 0.01 --tol-angle-geo 0.1
python CADSurfaceAnalyser.py MaPiece.stp --familles-step tangent,plans,cylindres
python CADSurfaceAnalyser.py MaPiece.stp --sorties json,csv_faces --dossier-sortie resultats/
python CADSurfaceAnalyser.py MaPiece.stp --precision-numerique fine
python CADSurfaceAnalyser.py MaPiece.stp --sans-numpy          # force le Python pur
python CADSurfaceProfil.py MaPiece.stp --fonctions 15          # où le temps est-il passé ?
python CADSurfaceGUI.py                                        # interface graphique
```

Sans argument, le programme traite `data/stp_tests/TestAnalyseSurf.stp`
(constante `FICHIER_ENTREE` en tête de `CADSurfaceAnalyser.py`, où se règlent aussi
la tolérance de tangence, la précision numérique, numpy et le parallélisme).

### Interface graphique

`python CADSurfaceGUI.py` (Windows : `CADSurfaceGUI.pyw`, sans fenêtre de console)
permet de choisir le fichier STEP (par défaut le dernier traité), les STEP colorés à
écrire par groupe de faces, les sorties CSV et JSON, le répertoire de sortie (par
défaut celui du STEP), la précision numérique et l'usage de numpy. Le déroulement
s'affiche en direct, comme dans un terminal ; un ascenseur apparaît si la fenêtre ne
tient pas dans l'écran. Les réglages sont mémorisés dans
`~/.cadsurfaceanalyser_gui.json`.

## Fichiers produits

Pour `piece.stp`, dans le dossier du STEP (ou `--dossier-sortie`) :

| Fichier | Contenu |
|---|---|
| `piece_Groupe_Tangent.stp` … `piece_Groupe_Cylindre.stp` | un STEP complet coloré par famille (`--familles-step` pour choisir) |
| `piece_bspline_violet.stp` | faces B-spline en violet, autres en gris clair (`--sans-stp-bspline` pour l'éviter) |
| `piece_groupes_tangents.json` | faces, groupes, familles, jonctions, résumé |
| `piece_faces.csv` | une ligne par face (classification et caractéristiques) |
| `piece_familles.csv` | une ligne par groupe et par famille |
| `piece_groupes.csv` | groupes tangents : barycentre, boîte englobante |
| `piece_groupes_tangents.csv` | jonctions entre faces : angles, tangence |

`--sorties` choisit les JSON/CSV (`json`, `csv_faces`, `csv_familles`, `csv_groupes`,
`csv_jonctions`, `toutes`, `aucune`).

## Familles de groupes

| Famille | Faces regroupées |
|---|---|
| `Groupe_Tangent` | faces tangentes de proche en proche |
| `Groupe_Coaxial` | surfaces de même axe |
| `Groupe_Parallele` | plans de normales parallèles, ou surfaces d'axes parallèles |
| `Groupe_Concentrique` | surfaces de même centre (ou sommet) |
| `Groupe_Geometrique_Identique` | même surface infinie (même plan, même cylindre...) |
| `Groupe_Coplanaire` | plan de référence commun (un tore a un plan médian et deux plans tangents) |
| `Groupe_Plan` | faces planes de même vecteur normal, sens compris |
| `Groupe_Cylindre` | faces cylindriques de même rayon (à `--tol-lin` près) |

Dans chaque STEP, les faces d'un même groupe ont la même couleur ; les faces hors
groupe sont grises. Pour `Groupe_Plan` et `Groupe_Cylindre`, un groupe d'une seule
face est lui aussi coloré (même rayon = même couleur, rayons différents = couleurs
différentes).

## Précision et performances

Le temps est presque entièrement passé dans l'étape « géométrie des faces ».
Mesures sur un coin de pièce de 17 faces et sur un banc d'essai de 204 faces :

| Version | Coin (17 faces) | Banc d'essai (204 faces) |
|---|---|---|
| 11.4, avant optimisations | 9,3 s | 119 s |
| 11.5, Python pur | 1,1 s | 13 s |
| 11.6 et suivantes, avec numpy | 0,4 s | 2,8 s |

`--precision-numerique rapide | standard | fine` règle l'intégration des faces
numériques (erreur relative typique sur l'aire : environ 4·10⁻⁶ / 10⁻⁶ / 2·10⁻⁹).
Avec numpy, `fine` ne coûte qu'environ 35 % de temps en plus. Le gain du calcul
parallèle (`--processus N`) sur machine multicœur n'a pas été mesuré.

## Fichiers de test

Le dossier [`data/stp_tests/`](data/stp_tests/README.md) accueille les fichiers STEP de
test. Les tests de non-régression sur fichiers réels
(`tests/test_donnees_reelles.py`) s'activent quand `TestAnalyseSurf.stp` et
`PocheS5_Coin.stp` y sont présents, et un test générique vérifie que tout STEP déposé
dans ce dossier se traite sans erreur. **Ne déposez que des fichiers dont vous pouvez
publier le contenu** (voir le README du dossier).

## Tests

```bash
python -m unittest discover -s tests -v
CADSURF_TEST_SANS_NUMPY=1 python -m unittest discover -s tests   # simule l'absence de numpy
```

Les tests utilisent uniquement la bibliothèque standard (pytest les découvre aussi) :
aires et barycentres comparés à des formules exactes, tangence, familles, B-splines,
lecture STEP, équivalence numpy/Python pur, ligne de commande, et interface avec un
faux `tkinter`. Voir [tests/README.md](tests/README.md).

## Structure du dépôt

```text
CADSurfaceAnalyser.py     programme principal (configuration + main)
CADSurfaceProfil.py       mesure des temps par étape
CADSurfaceGUI.py/.pyw     interface graphique
cadsurf/                  le paquet : lecture STEP, surfaces, tangence, géométrie, familles, exports, interface
tests/                    suite de tests (unittest)
data/stp_tests/           fichiers STEP de test (à déposer)
docs/                     architecture et documentation technique
tools/                    outils de maintenance du dépôt
.github/                  intégration continue, modèles de tickets et de pull requests
```

L'organisation détaillée des modules est dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Limites connues

- La tangence est mesurée en trois points par arête, et ignore le sens des normales
  (un rebroussement à 180° est vu comme tangent).
- Surfaces non gérées : surfaces décalées (offset), surfaces B-spline fermées ou
  périodiques, génératrices droites de surfaces de révolution.
- Une face qui entoure un pôle ou un sommet (hors sphère et cône) est calculée mais
  marquée `aire_fiable = faux`.
- Les tolérances des familles sont absolues, dans l'unité du fichier.
- Le programme suppose une coque orientée vers l'extérieur de la matière.
- La CI vérifie Python 3.8, 3.9 et 3.12 sous Linux et Windows. macOS n'est pas testé.

## Contribuer

Les contributions sont bienvenues : voir [CONTRIBUTING.md](CONTRIBUTING.md). Pour
signaler un problème de sécurité, voir [SECURITY.md](SECURITY.md).

## Licence

Distribué sous licence **Apache 2.0** : voir [LICENSE](LICENSE) et [NOTICE](NOTICE).

Pour citer ce logiciel, voir [CITATION.cff](CITATION.cff).
