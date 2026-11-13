# Contribuer à CADSurfaceAnalyser

Merci de votre intérêt ! Ce document explique comment proposer une modification.

## Avant de commencer

- Pour un bug ou une idée, ouvrez d'abord un ticket (modèles fournis) en décrivant le
  problème. Joignez si possible un **STEP minimal** qui le reproduit.
- **Ne publiez jamais de fichier STEP confidentiel.** Réduisez la pièce à quelques
  faces, ou construisez un cas synthétique (voir `tests/_support.py`).

## Mettre en place l'environnement

```bash
git clone https://github.com/Guillaume-COHEN/cadsurfaceanalyser.git
cd REPO
python -m pip install -r requirements.txt     # numpy, optionnel
python -m unittest discover -s tests -v
CADSURF_TEST_SANS_NUMPY=1 python -m unittest discover -s tests   # sans numpy
```

Aucune autre dépendance n'est nécessaire (les tests utilisent `unittest`).

## Règles de développement

- **Python 3.8 minimum** : pas d'opérateur `|` sur les types, pas de `match`, pas de
  `str.removeprefix`... La CI teste 3.8, 3.9 et 3.12.
- **Aucune dépendance obligatoire.** numpy reste optionnel : tout code qui l'utilise doit
  avoir son repli en Python pur, et les deux chemins doivent donner les mêmes résultats.
- **Couches** : un module n'importe que des modules de couches inférieures (aucun import
  circulaire). Voir `docs/ARCHITECTURE.md`.
- Le code, les commentaires et la documentation sont en **français** (identifiants
  compris, comme dans le code existant).
- Chaque fichier Python commence par l'en-tête de licence Apache 2.0 (copier celui d'un
  fichier existant).

## Ajouter une fonctionnalité

- **Nouveau type de surface** : `surfaces.py` (normale), `geom_surfaces.py` (aire),
  `familles.py` (descripteur), `config.py` (libellé).
- **Nouvelle famille de groupes** : `familles.py` (`FAMILLES_GEO` et
  `build_geometric_families`). Les CSV, le JSON, les couleurs, les STEP par famille et
  l'interface la prennent en compte automatiquement.
- **Nouvelle option** : `options.py`, puis l'étape concernée de `pipeline.py` ; si elle
  concerne l'interface, `interface_logique.py`.
- **Dans tous les cas** : ajoutez un test. Pour une géométrie, comparez à une valeur
  exacte (formule analytique) plutôt qu'à une valeur relevée sur le programme lui-même.

## Proposer une pull request

1. Créez une branche à partir de `main`.
2. Faites des commits clairs, en français ou en anglais.
3. Vérifiez que `python -m unittest discover -s tests` passe, avec et sans numpy.
4. Mettez à jour `CHANGELOG.md` et la documentation concernée.
5. Ouvrez la pull request en remplissant le modèle.

Si un changement modifie des résultats (aire, groupes...), expliquez pourquoi dans la
description et indiquez de combien ils changent.

## Licence des contributions

Sauf mention contraire, toute contribution soumise est publiée sous la licence Apache 2.0
du projet (article 5 de la licence).
