# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Ligne de commande : fichiers produits, options, STEP colorés, JSON et CSV."""

import csv
import json
import math
import os
import tempfile
import unittest

import _support as S

FAMILLES = ["Tangent", "Coaxial", "Parallele", "Concentrique", "Geometrique_Identique",
            "Coplanaire", "Plan", "Cylindre"]
PI = math.pi
AIRE_TORE = 3 * (PI / 3) * (10 * (PI / 2 + PI / 4) + 3 * (1 + math.sin(PI / 4)))


def scene_mixte():
    sc = S.Scene()
    sc.plan_perce("plan percé")
    sc.bande_cylindre("cylindre", cx=50, r=10.0, z0=0, z1=20)
    sc.patch_tore("tore", centre=(100, 0, 0), genre="tore")
    sc.patch_tore("révolution", centre=(160, 0, 0), genre="revolution")
    sc.quart_cylindre("nurbs", ox=220, R=2.0, L=5.0, genre="nurbs")
    return sc


AIRE_TOTALE = (400 - 9 * PI) + 2 * PI * 10 * 20 + 2 * AIRE_TORE + 2 * (PI / 2) * 5


class CommandeBase(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory()
        self.dossier = self._dossier.name
        self.scene = scene_mixte()
        self.entree = self.scene.ecrire(os.path.join(self.dossier, "piece.stp"))

    def tearDown(self):
        self._dossier.cleanup()

    def sorties(self, dossier=None):
        dossier = dossier or self.dossier
        return sorted(f for f in os.listdir(dossier) if f != "piece.stp" and os.path.isfile(os.path.join(dossier, f)))

    def lancer(self, *options):
        return S.lancer_cli(self.entree, *options)


class FichiersProduits(CommandeBase):
    def test_sorties_par_defaut(self):
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        attendus = sorted(
            ["piece_Groupe_%s.stp" % f for f in FAMILLES]
            + ["piece_bspline_violet.stp", "piece_groupes_tangents.json", "piece_faces.csv",
               "piece_familles.csv", "piece_groupes.csv", "piece_groupes_tangents.csv"])
        self.assertEqual(self.sorties(), attendus)
        self.assertIn("TERMINE", r.stdout)

    def test_selection_des_sorties_et_dossier(self):
        cible = os.path.join(self.dossier, "sous", "dossier")
        r = self.lancer("--sorties", "json,csv_faces", "--familles-step", "tangent,plans",
                        "--sans-stp-bspline", "--dossier-sortie", cible)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        self.assertEqual(self.sorties(cible), sorted([
            "piece_Groupe_Tangent.stp", "piece_Groupe_Plan.stp",
            "piece_groupes_tangents.json", "piece_faces.csv"]))
        self.assertEqual(self.sorties(), [])                        # rien à côté de l'entrée

    def test_aucune_sortie(self):
        r = self.lancer("--sorties", "aucune", "--familles-step", "aucune", "--sans-stp-bspline")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.sorties(), [])

    def test_sortie_inconnue(self):
        r = self.lancer("--sorties", "truc")
        self.assertEqual(r.returncode, 1)
        self.assertIn("sortie inconnue", r.stdout)

    def test_famille_inconnue(self):
        r = self.lancer("--familles-step", "truc")
        self.assertEqual(r.returncode, 1)
        self.assertIn("famille inconnue", r.stdout)

    def test_nom_du_step_tangent_impose(self):
        cible = os.path.join(self.dossier, "mon_tangent.stp")
        r = self.lancer("-o", cible, "--familles-step", "tangent,plans", "--sorties", "aucune",
                        "--sans-stp-bspline")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.sorties(), ["mon_tangent.stp", "mon_tangent_Groupe_Plan.stp"])

    def test_fichier_introuvable(self):
        r = S.lancer_cli(os.path.join(self.dossier, "absent.stp"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("introuvable", r.stdout)
        self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_stp_bspline_absent_sans_surface_bspline(self):
        sc = S.Scene()
        sc.plan_perce()
        chemin = sc.ecrire(os.path.join(self.dossier, "plan.stp"))
        r = S.lancer_cli(chemin, "--familles-step", "aucune", "--sorties", "aucune")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Aucune face B_SPLINE_SURFACE", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.dossier, "plan_bspline_violet.stp")))


class ContenuDesFichiers(CommandeBase):
    @classmethod
    def lire_csv(cls, chemin):
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            lignes = list(csv.reader(f, delimiter=";"))
        return lignes[0], lignes[1:]

    def test_json_coherent(self):
        r = self.lancer("--familles-step", "aucune", "--sans-stp-bspline")
        self.assertEqual(r.returncode, 0)
        with open(os.path.join(self.dossier, "piece_groupes_tangents.json"), encoding="utf-8") as f:
            j = json.load(f)
        self.assertEqual(len(j["faces"]), 5)
        self.assertAlmostEqual(j["resume"]["aire_totale"] / AIRE_TOTALE, 1.0, delta=1e-7)
        self.assertEqual(set(j["familles_geometriques"]),
                         {"tangent", "coaxiales", "paralleles", "concentriques",
                          "identiques", "coplanaires", "plans", "cylindres"})
        for fiche in j["faces"].values():
            self.assertIn("couleurs_hex", fiche)
            self.assertEqual(len(fiche["couleurs_hex"]), 8)

    def test_csv_faces_et_familles(self):
        r = self.lancer("--familles-step", "aucune", "--sans-stp-bspline")
        self.assertEqual(r.returncode, 0)
        entete, lignes = self.lire_csv(os.path.join(self.dossier, "piece_faces.csv"))
        for colonne in ("Face_ID", "Type", "Groupe_Tangent", "Nb_Faces_Groupe_Tangent", "Groupe_Coaxial",
                        "Groupe_Parallele", "Groupe_Concentrique", "Groupe_Geometrique_Identique",
                        "Groupe_Coplanaire", "Groupe_Plan", "Groupe_Cylindre", "Aire", "Aire_Fiable",
                        "Couleur_Hex", "Couleur_Hex_Groupe_Cylindre", "Parametres_JSON"):
            self.assertIn(colonne, entete)
        self.assertEqual(len(lignes), 5)
        types = sorted(l[entete.index("Type")] for l in lignes)
        self.assertEqual(types, sorted(["Plan", "Cylindre", "Tore", "Surface de révolution",
                                        "Surface B-spline"]))
        aires = sum(float(l[entete.index("Aire")]) for l in lignes)
        self.assertAlmostEqual(aires / AIRE_TOTALE, 1.0, delta=1e-6)
        ent2, lignes2 = self.lire_csv(os.path.join(self.dossier, "piece_familles.csv"))
        self.assertEqual(ent2[:3], ["Famille", "Groupe", "Nb_Faces"])
        self.assertIn("Groupe_Tangent", {l[0] for l in lignes2})
        self.assertIn("Groupe_Cylindre", {l[0] for l in lignes2})

    def test_virgule_decimale(self):
        r = self.lancer("--familles-step", "aucune", "--sans-stp-bspline", "--virgule-decimale")
        self.assertEqual(r.returncode, 0)
        entete, lignes = self.lire_csv(os.path.join(self.dossier, "piece_faces.csv"))
        aire = lignes[0][entete.index("Aire")]
        self.assertIn(",", aire)
        self.assertNotIn(".", aire)

    def test_resultats_identiques_sans_numpy(self):
        """--sans-numpy ne change pas les résultats (aux arrondis près)."""
        resultats = {}
        for nom, options in (("numpy", ["--avec-numpy"]), ("pur", ["--sans-numpy"])):
            cible = os.path.join(self.dossier, nom)
            r = self.lancer(*(options + ["--familles-step", "aucune", "--sans-stp-bspline",
                                         "--sorties", "json", "--dossier-sortie", cible]))
            self.assertEqual(r.returncode, 0, r.stdout[-500:])
            with open(os.path.join(cible, "piece_groupes_tangents.json"), encoding="utf-8") as f:
                resultats[nom] = json.load(f)
        for cle, fiche in resultats["pur"]["faces"].items():
            self.assertAlmostEqual(resultats["numpy"]["faces"][cle]["aire"] / fiche["aire"], 1.0, delta=1e-7)

    def test_step_colore_valide(self):
        """Le STEP coloré garde toutes les faces, ajoute un style par face et
        colore de la même façon les cylindres de même rayon."""
        sc = S.Scene()
        sc.bande_cylindre("A r=3.000", cx=0, r=3.000)
        sc.bande_cylindre("B r=3.002", cx=50, r=3.002)
        sc.bande_cylindre("C r=3.010", cx=100, r=3.010)
        sc.bande_cylindre("D r=5", cx=150, r=5.0)
        sc.quart_cylindre("E extrusion r=3", ox=300, R=3.0, genre="extrusion")
        sc.calotte_sphere("S sphère", centre=(400, 0, 0), R=10.0, zc=6.0)
        sc.plan_rect("P plan", 500)
        chemin = sc.ecrire(os.path.join(self.dossier, "cyl.stp"))
        r = S.lancer_cli(chemin, "--familles-step", "cylindres", "--sorties", "aucune",
                         "--sans-stp-bspline")
        self.assertEqual(r.returncode, 0, r.stdout[-500:])
        colore = os.path.join(self.dossier, "cyl_Groupe_Cylindre.stp")
        from cadsurf.step_parser import StepFile
        original, ecrit = StepFile(chemin), StepFile(colore)
        self.assertEqual(sorted(ecrit.ids_of("ADVANCED_FACE")), sorted(original.ids_of("ADVANCED_FACE")))
        self.assertEqual(len(ecrit.ids_of("STYLED_ITEM")), 7)       # un style par face
        couleur = {sc.noms[f]: c for f, c in S.couleurs_des_faces(colore).items()}
        self.assertEqual(len(couleur), 7)
        # rayons 3,000 / 3,002 / extrusion de rayon 3 : même couleur (tolérance 0,005)
        self.assertEqual(couleur["A r=3.000"], couleur["B r=3.002"])
        self.assertEqual(couleur["A r=3.000"], couleur["E extrusion r=3"])
        # rayons différents : couleurs différentes
        self.assertEqual(len({couleur["A r=3.000"], couleur["C r=3.010"], couleur["D r=5"]}), 3)
        # faces non cylindriques : gris
        self.assertEqual(couleur["S sphère"], S.GRIS)
        self.assertEqual(couleur["P plan"], S.GRIS)

    def test_step_colore_relisible_par_famille(self):
        r = self.lancer("--sorties", "aucune", "--sans-stp-bspline")
        self.assertEqual(r.returncode, 0)
        from cadsurf.step_parser import StepFile
        nb_faces = len(StepFile(self.entree).ids_of("ADVANCED_FACE"))
        for famille in FAMILLES:
            with self.subTest(famille):
                sortie = os.path.join(self.dossier, "piece_Groupe_%s.stp" % famille)
                self.assertEqual(len(S.couleurs_des_faces(sortie)), nb_faces)


if __name__ == "__main__":
    unittest.main()
