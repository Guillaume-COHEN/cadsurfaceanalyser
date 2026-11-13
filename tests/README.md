# Tests

```bash
python -m unittest discover -s tests -v                          # tout
python -m unittest tests.test_geometrie -v                       # un fichier (depuis la racine)
CADSURF_TEST_SANS_NUMPY=1 python -m unittest discover -s tests   # simule l'absence de numpy
```

Les tests n'utilisent que la bibliothèque standard ; `pytest tests/` les exécute aussi.

| Fichier | Ce qu'il vérifie |
|---|---|
| `test_geometrie.py` | aires et barycentres de faces construites exprès, comparés à des **formules exactes** (plan percé, cylindre, sphère, cône, tore, extrusion, NURBS) |
| `test_tangence.py` | angle mesuré entre une face courbe et un plan incliné de 0°, 0,3° et 10° |
| `test_familles.py` | groupes de chaque famille sur des scènes dont les groupes sont connus d'avance |
| `test_bsplines.py` | partition de l'unité, dérivées, cercle exact par NURBS rationnelle, projection |
| `test_parser_step.py` | lecture du format STEP : chaînes, commentaires, entités complexes |
| `test_numpy_equivalence.py` | numpy et Python pur donnent les mêmes résultats (ignoré sans numpy) |
| `test_cli.py` | fichiers produits, options, STEP colorés relus, JSON et CSV |
| `test_interface.py` | interface graphique avec un faux `tkinter` (traitements réels, arrêt, réglages, ascenseur) |
| `test_donnees_reelles.py` | non-régression sur `data/stp_tests/` (ignoré si les fichiers sont absents) |

## Outils

- `_support.py` : `Scene` construit des fichiers STEP synthétiques dont la géométrie est
  connue exactement ; `analyser_fichier` exécute la chaîne sans passer par la ligne de
  commande ; `couleurs_des_faces` relit les couleurs d'un STEP coloré.
- `faketk.py` : faux `tkinter` qui refuse les options inconnues (comme le vrai Tk lève
  `TclError`), simule les clics, la boucle d'événements et la taille de l'écran.
  **Il ne remplace pas un essai sur un vrai écran** (apparence, polices).
- `_sans_numpy/` : simule une machine sans numpy.

## Écrire un test

Pour une géométrie, construisez la face avec `Scene` et comparez à une formule exacte.
Pour une valeur relevée sur le programme lui-même (non-régression), dites-le dans le
commentaire : elle détecte un changement, pas une erreur.
