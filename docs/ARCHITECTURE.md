# Architecture du code

Ce document décrit l'organisation du paquet `cadsurf/`, les couches de dépendances et
les points d'extension. Pour l'utilisation, voir le [README](../README.md) ; pour les
équations et leur justification, voir la [documentation technique](README.md).

## Performances

Le temps est presque entièrement passé dans l'étape « géométrie des faces »
(aire, barycentre...), et dedans dans les faces à surface B-spline, de
révolution ou d'extrusion (les plans, cylindres, tores... sont quasi
instantanés). Optimisations :

- B-splines évaluées avec les seules `degré+1` fonctions de base actives
  (avant : de Boor sur toutes les lignes de points de contrôle) ;
- dérivées analytiques (avant : 5 évaluations par différences finies) ;
- une seule projection point-surface par nœud d'intégration (avant : 3), grille
  de projection mise en cache puis Newton (avant : recherche par motifs) ;
- longueurs et boîtes englobantes d'arêtes mémorisées ;
- calcul parallèle des faces lourdes, `--processus N` (0 = automatique :
  seulement si au moins 12 faces lourdes et plusieurs cœurs ; 1 = séquentiel) ;
  les résultats sont identiques au calcul séquentiel.

- **numpy (optionnel)** : tous les nœuds d'intégration d'une arête sont traités
  en un seul appel (`vectoriel.py`) : fonctions de base B-spline, projection sur
  la surface (grille + Gauss-Newton), intégrale intérieure de Green. Le résultat
  est équivalent au calcul en Python pur (écart ≲ 1e-8 en relatif, bruit des
  différences finies du calcul scalaire). Si numpy est absent, ou avec
  `--sans-numpy`, ou si un cas dégénéré apparaît sur une arête, le code Python
  pur prend le relais (le programme indique alors le nombre de replis).

Mesures (coin de 17 faces ; banc d'essai de 204 faces, 60 faces lourdes) :

    version 11.4 (avant optimisations)        9,3 s        119 s
    11.5, Python pur                           1,1 s         13 s
    11.6, avec numpy                           0,4 s        2,8 s

`--precision-numerique rapide | standard | fine` règle l'intégration des faces
numériques (erreur relative typique sur l'aire : ~4e-6 / ~1e-6 / ~2e-9 ; temps
relatifs, Python pur : ~0,6 / 1 / 1,6 ; avec numpy : ~0,9 / 1 / 1,35).

`python CADSurfaceProfil.py MaPiece.stp --fonctions 15` donne la durée de chaque
étape et les fonctions les plus coûteuses, sans écrire de fichier.

## Familles de groupes (Famille_Groupe)

    Groupe_Tangent                faces tangentes (de proche en proche)
    Groupe_Coaxial                même axe
    Groupe_Parallele              normales de plans // ou axes //
    Groupe_Concentrique           même centre / sommet
    Groupe_Geometrique_Identique  même surface infinie
    Groupe_Coplanaire             plan de référence commun
    Groupe_Plan                   faces planes de même vecteur normal (sens compris)
    Groupe_Cylindre               faces cylindriques de même rayon (à --tol-lin près)

Un STEP complet coloré est écrit par famille : `<fichier>_Groupe_Tangent.stp`,
`..._Groupe_Coaxial.stp`, etc. Les faces hors groupe sont en gris (sauf
`--color-singletons`) ; dans Groupe_Plan, tout groupe de plans est coloré,
même réduit à une face, et les faces non planes sont en gris. Groupe_Cylindre
fonctionne de même : un groupe par rayon (cylindres de même rayon = même couleur,
rayons différents = couleurs différentes), faces non cylindriques en gris.
Les rayons sont classés par ordre croissant, et deux rayons sont regroupés si
leur écart ne dépasse pas `--tol-lin` (classement de proche en proche : des
rayons 7,000 / 7,004 / 7,008 avec la tolérance 0,005 forment un seul groupe).

Colonnes du CSV des faces : `Groupe_Tangent`, `Nb_Faces_Groupe_Tangent`,
`Groupe_Coaxial`, `Groupe_Parallele`, `Groupe_Concentrique`,
`Groupe_Geometrique_Identique`, `Groupe_Coplanaire`, `Groupe_Plan`, `Groupe_Cylindre`.
`Couleur_R/G/B/Hex` = couleur dans le STEP Groupe_Tangent ; les sept autres
couleurs sont dans `Couleur_Hex_Groupe_*`.

CSV des familles : une ligne par groupe et par famille, `Groupe_Tangent`
compris (les faces isolées y figurent comme groupes d'une face, pour que les
numéros correspondent à ceux du CSV des faces).

## Arborescence

    CADSurfaceAnalyser.py     programme principal : configuration + main() (~45 lignes)
    CADSurfaceProfil.py       mesure des temps par étape et fonctions coûteuses
    CADSurfaceGUI.py          interface graphique (CADSurfaceGUI.pyw : sans console)
    cadsurf/
        options.py            options de la ligne de commande, chemins de sortie
        pipeline.py           étapes : lire, analyser, géométrie, familles, coloration, exports
        parallele.py          calcul parallèle des faces à surface numérique
        accel.py              numpy optionnel : détection, activation
        vectoriel.py          calculs vectorisés numpy (B-splines, projections, intégrales)
        interface.py          fenêtre tkinter (widgets)
        interface_logique.py  réglages, commande, exécution (sans tkinter)
        config.py             constantes partagées (échantillonnage, EPS, gris, Gauss, libellés)
        step_parser.py        lecture ISO 10303-21 : StepFile, parseur d'arguments
        vecteurs.py           algèbre vectorielle 3D
        reperes.py            points et repères (AXIS2_PLACEMENT_3D)
        bsplines.py           B-splines (courbes, surfaces, rationnelles), de Boor
        profils.py            surfaces de révolution / d'extrusion, tore équivalent
        surfaces.py           classe Surface : type, paramètres, normale
        topologie.py          Face, sommets, union-find
        tangence.py           échantillonnage des arêtes, angles, groupes tangents
        couleurs.py           couleurs des groupes
        export_step.py        écriture du STEP AP214 coloré (pièce complète)
        geom_aretes.py        géométrie des arêtes (point(t), longueur, bbox)
        geom_surfaces.py      paramétrage (u,v), inversion, intégrales (Green)
        geom_faces.py         aire, barycentre, fiches des faces, groupes, arêtes
        familles.py           familles de groupes (tangent, coaxial, ..., plan)
        utilitaires.py        arrondis, formats
        export_json.py        export JSON
        export_csv.py         exports CSV (jonctions, faces, groupes, familles)
        rapports.py           affichage console

## Couches (un module n'importe que les modules des couches inférieures)

    1  accel, config, step_parser, utilitaires
    2  couleurs, export_json, export_step, vecteurs, vectoriel
    3  familles, geom_surfaces, reperes
    4  bsplines, export_csv, options, rapports, topologie
    5  geom_aretes, interface_logique, profils
    6  geom_faces, interface, surfaces
    7  parallele, tangence
    8  pipeline
    9  CADSurfaceAnalyser.py, CADSurfaceProfil.py, CADSurfaceGUI.py

Aucun import circulaire.

## Interface graphique

    python CADSurfaceGUI.py        (Windows : CADSurfaceGUI.pyw, sans fenêtre de console)

La fenêtre permet de régler :

1. le fichier STEP à traiter (par défaut : le dernier traité) ;
2. les STEP colorés à écrire, un par groupe de faces (par défaut : tous) ;
3. les sorties CSV et JSON (par défaut : toutes) ;
4. le répertoire de sortie (par défaut : celui du fichier STEP) ;
5. la précision numérique (par défaut : standard) et l'utilisation de numpy
   (par défaut : activée, grisée si numpy n'est pas installé).

La taille de la fenêtre s'adapte à l'écran ; si le contenu est plus haut que la
fenêtre, un ascenseur vertical apparaît à droite (la molette de la souris fait
défiler la page, sauf sur le journal qui défile seul).

Le déroulement s'affiche en direct, comme dans un terminal ; la première ligne
du journal est la commande équivalente en ligne de commande. Boutons : Lancer,
Arrêter (arrête aussi les processus de calcul), Ouvrir le dossier de sortie.

Les réglages sont mémorisés dans `~/.cadsurfaceanalyser_gui.json` (dernier
fichier traité compris). Les tolérances restent celles de
`CADSurfaceAnalyser.py` (section CONFIGURATION).

tkinter est livré avec Python (Windows, macOS). Linux Debian/Ubuntu :
`sudo apt install python3-tk`. Sans tkinter, le lanceur l'indique et la ligne de
commande reste utilisable.

Fonctionnement : `cadsurf/interface.py` (widgets) ne fait qu'afficher et régler ;
`cadsurf/interface_logique.py` (sans tkinter) construit la commande, la lance
dans un sous-processus et relaie sa sortie. Même résultat que la ligne de
commande, fenêtre toujours réactive. Nouvelles options correspondantes :
`--sorties json,csv_faces,...|toutes|aucune` et `--dossier-sortie DOSSIER`.

## Régler la précision, numpy et le parallélisme

Deux façons, la ligne de commande ayant toujours priorité :

1. **Dans le script** (réglage permanent, pratique depuis un éditeur) : section
   CONFIGURATION de `CADSurfaceAnalyser.py`, à côté de `FICHIER_ENTREE`.

       PRECISION_NUMERIQUE_DEFAUT = "standard"   # "rapide" | "standard" | "fine"
       UTILISER_NUMPY_DEFAUT = True              # False = Python pur
       PROCESSUS_DEFAUT = 0                      # 0 auto, 1 séquentiel, N processus

2. **En ligne de commande** (pour un essai) :

       --precision-numerique rapide|standard|fine
       --sans-numpy        (coupe numpy)      --avec-numpy  (le rétablit)
       --processus N

Priorité pour numpy : `--sans-numpy` > `--avec-numpy` > `UTILISER_NUMPY_DEFAUT`.
Les valeurs par défaut proposées par l'aide (`--help`) reprennent les constantes.

## Où modifier quoi

- Fichier d'entrée par défaut, tolérance angulaire par défaut :
  `CADSurfaceAnalyser.py` (section CONFIGURATION).
- Nouveau type de surface : `surfaces.py` (normale), `geom_surfaces.py`
  (aire), `familles.py` (descripteur géométrique), `config.py` (libellé).
- Nouvelle colonne CSV / champ JSON : `geom_faces.py` (fiche de la face) puis
  `export_csv.py` / `export_json.py`.
- Nouvelle famille de groupes : `familles.py` (FAMILLES_GEO et
  build_geometric_families) ; les CSV, le JSON, les couleurs et les STEP par
  famille la prennent en compte automatiquement.
- Couleurs : `couleurs.py` (VIOLET : `config.py`) et `pipeline.calculer_colorations`.
  Format du STEP de sortie : `export_step.py`.
- Nouvelle option : `options.py`, puis l'étape concernée dans `pipeline.py`.
