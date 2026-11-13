# Fichiers STEP de test

Ce dossier accueille les fichiers STEP utilisés comme exemples et pour les tests de
non-régression sur données réelles.

## Fichiers attendus

| Fichier | Rôle |
|---|---|
| `TestAnalyseSurf.stp` | traité par défaut par `CADSurfaceAnalyser.py` ; plans, cylindres et tores ; 18 faces |
| `PocheS5_Coin.stp` | coin de poche avec surfaces B-spline et de révolution ; 17 faces |

Les tests `tests/test_donnees_reelles.py` vérifient pour ces deux fichiers les aires,
volumes, groupes tangents et familles. Ils sont **ignorés** tant que les fichiers ne sont
pas présents.

Tout autre fichier `.stp` / `.step` déposé ici est traité par un test générique (aucun
plantage, aire totale positive).

## Avant de déposer un fichier

- **Vérifiez que vous avez le droit de le publier.** Un modèle de pièce industrielle peut
  être confidentiel ou protégé : ne déposez que des pièces d'essai, des pièces dont vous
  détenez les droits, ou des modèles anonymisés.
- **Taille** : GitHub refuse les fichiers de plus de 100 Mo et avertit au-delà de 50 Mo.
  Pour de gros fichiers, utilisez [Git LFS](https://git-lfs.com) (voir `.gitattributes`).

## Fichiers générés

Le programme écrit ses résultats (`*_Groupe_*.stp`, `*.json`, `*.csv`) à côté du fichier
d'entrée. Le `.gitignore` les écarte pour qu'ils ne soient pas ajoutés par erreur.
