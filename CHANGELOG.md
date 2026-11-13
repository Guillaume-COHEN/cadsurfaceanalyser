# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les
versions suivent la numérotation historique du projet (11.x). Les dates sont à
compléter lors de la publication de chaque version.

## [11.8.0] — première version publique

### Ajouté
- Famille **Groupe_Cylindre** : faces cylindriques regroupées par rayon identique (à
  `--tol-lin` près), avec son STEP complet coloré (même rayon, même couleur) ; cylindres
  exportés par extrusion de cercle reconnus ; colonnes et clés correspondantes dans les
  CSV et le JSON ; case dédiée dans l'interface.
- Suite de tests (`unittest`) : aires et barycentres comparés à des formules exactes,
  tangence, familles, B-splines, lecture STEP, équivalence numpy / Python pur, ligne de
  commande, interface (faux tkinter), non-régression sur fichiers réels.
- Intégration continue (GitHub Actions), `pyproject.toml`, documentation technique,
  modèles de tickets et de pull requests, outil `tools/configurer_depot.py`.

### Corrigé
- Lecture STEP : une instance placée juste après un commentaire `/* … */` était
  ignorée.
- Interface : le tube de sortie du sous-processus n'était pas fermé après chaque
  traitement.
- Un fichier STEP introuvable affiche un message clair, sans trace Python (code de
  retour 1).

### Modifié
- Le fichier traité par défaut est `data/stp_tests/TestAnalyseSurf.stp`.

## [11.7.1]
- Interface : la fenêtre s'adapte à la taille de l'écran ; ascenseur vertical (molette
  comprise) quand elle ne tient pas en hauteur.

## [11.7]
- Interface graphique `CADSurfaceGUI.py` : choix du fichier, des STEP par famille, des
  sorties CSV/JSON, du répertoire de sortie, de la précision numérique et de numpy ;
  déroulement en direct ; réglages mémorisés.
- Options `--sorties` et `--dossier-sortie`.

## [11.6.1]
- Réglages permanents dans la section CONFIGURATION : `PRECISION_NUMERIQUE_DEFAUT`,
  `UTILISER_NUMPY_DEFAUT`, `PROCESSUS_DEFAUT` ; option `--avec-numpy`.

## [11.6]
- Calcul vectorisé avec numpy (optionnel, détecté automatiquement, repli en Python
  pur, option `--sans-numpy`) : environ 3 à 4 fois plus rapide que la 11.5.

## [11.5]
- Calcul des caractéristiques des faces environ 8 fois plus rapide : évaluation locale
  des B-splines, dérivées analytiques, grille de projection en cache.
- Calcul parallèle optionnel (`--processus`), précision réglable
  (`--precision-numerique`), outil de mesure `CADSurfaceProfil.py`.

## [11.4]
- Le STEP complet où les faces B_SPLINE_SURFACE sont en violet est écrit par défaut
  (`--sans-stp-bspline` pour le désactiver).

## [11.3]
- `Groupe_Tangent` traité comme les autres familles ; nouvelle famille `Groupe_Plan` ;
  un STEP complet coloré par famille ; colonnes de CSV renommées.

## [11.2]
- `main()` redécoupé en étapes (`options.py`, `pipeline.py`) ; sorties identiques.

## [11.1]
- Les faces B_SPLINE_SURFACE entrent dans les groupes tangents (leur normale était
  rejetée à tort par un seuil `EPS` trop strict).

## [11.0]
- Découpage du fichier unique en modules (`cadsurf/`), sorties identiques vérifiées
  octet par octet.
