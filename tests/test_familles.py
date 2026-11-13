# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Familles de groupes sur des scènes dont les groupes sont connus d'avance."""

import os
import tempfile
import unittest

import _support as S


def analyser(scene, **options):
    with tempfile.TemporaryDirectory() as dossier:
        return S.analyser_fichier(scene.ecrire(os.path.join(dossier, "f.stp")), **options)


def trier(groupes):
    return sorted(sorted(g) for g in groupes)


def scene_familles():
    """Plans A, B (même plan), C (plan parallèle, z = 5), D (plan ⟂) ; cylindres
    C1, C4 (même cylindre), C2 (coaxial, rayon 5), C3 (axe parallèle) ; sphères
    concentriques S1, S2 ; tores T1, T2 (concentriques), T3, T4."""
    sc = S.Scene()
    sc.plan_rect("A", 0, z=0.0)
    sc.plan_rect("B", 20, z=0.0)
    sc.plan_rect("C", 40, z=5.0)
    sc.plan_rect("D", 80, normale=(1, 0, 0), xdir=(0, 1, 0))
    sc.bande_cylindre("C1", cx=50, cy=0, r=3.0, z0=0, z1=10)
    sc.bande_cylindre("C2", cx=50, cy=0, r=5.0, z0=0, z1=10)
    sc.bande_cylindre("C3", cx=60, cy=0, r=3.0, z0=0, z1=10)
    sc.bande_cylindre("C4", cx=50, cy=0, r=3.0, z0=20, z1=30)
    sc.calotte_sphere("S1", centre=(0, 50, 0), R=4.0, zc=2.0)
    sc.calotte_sphere("S2", centre=(0, 50, 0), R=6.0, zc=3.0)
    sc.patch_tore("T1", centre=(100, 0, 0), R=10.0, r=2.0)
    sc.patch_tore("T2", centre=(100, 0, 0), R=15.0, r=2.0)
    sc.patch_tore("T3", centre=(200, 0, 5), R=10.0, r=2.0)
    sc.patch_tore("T4", centre=(300, 0, 2), R=10.0, r=2.0)
    return sc


class FamillesGeometriques(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = scene_familles()
        cls.analyse = analyser(cls.scene)

    def groupes(self, cle):
        return S.groupes_par_nom(self.scene, self.analyse, cle)

    def test_coaxiales(self):
        self.assertEqual(self.groupes("coaxiales"), trier([["C1", "C2", "C4"], ["T1", "T2"]]))

    def test_paralleles(self):
        self.assertEqual(self.groupes("paralleles"), trier([
            ["A", "B", "C"], ["C1", "C2", "C3", "C4", "T1", "T2", "T3", "T4"]]))

    def test_concentriques(self):
        self.assertEqual(self.groupes("concentriques"), trier([["S1", "S2"], ["T1", "T2"]]))

    def test_geometries_identiques(self):
        self.assertEqual(self.groupes("identiques"), trier([["A", "B"], ["C1", "C4"]]))

    def test_coplanaires(self):
        """Plans de référence : plan, plan médian et plans tangents d'un tore."""
        self.assertEqual(self.groupes("coplanaires"), trier([
            ["A", "B", "T1", "T2", "T4"], ["T1", "T2", "T4"], ["T1", "T2"], ["C", "T3"]]))

    def test_plans_par_vecteur_normal(self):
        self.assertEqual(self.groupes("plans"), trier([["A", "B", "C"], ["D"]]))

    def test_cylindres_par_rayon(self):
        self.assertEqual(self.groupes("cylindres"), trier([["C1", "C3", "C4"], ["C2"]]))

    def test_champs_des_fiches(self):
        infos = {self.scene.noms[f]: i for f, i in self.analyse.infos.items()}
        self.assertIsNotNone(infos["C1"]["groupe_cylindre"])
        self.assertEqual(infos["C1"]["groupe_cylindre"], infos["C3"]["groupe_cylindre"])
        self.assertNotEqual(infos["C1"]["groupe_cylindre"], infos["C2"]["groupe_cylindre"])
        self.assertIsNone(infos["A"]["groupe_cylindre"])
        self.assertIsNone(infos["C1"]["groupe_plan"])
        self.assertEqual(infos["A"]["groupe_plan"], infos["C"]["groupe_plan"])


class GroupePlan(unittest.TestCase):
    def test_normales_opposees_et_tolerance(self):
        sc = S.Scene()
        sc.plan_rect("A", 0)
        sc.plan_rect("B", 20)
        sc.plan_rect("C", 40, z=5.0)
        sc.plan_rect("E", 60, meme_sens=False)                  # même plan, face retournée
        sc.plan_rect("D", 80, normale=(1, 0, 0), xdir=(0, 1, 0))
        sc.plan_rect("F", 100, inclinaison_deg=0.01)            # dans la tolérance (0,05°)
        sc.plan_rect("G", 120, inclinaison_deg=0.2)             # hors tolérance
        sc.bande_cylindre("H", cx=200, r=3.0, z0=0, z1=10)      # hors famille
        analyse = analyser(sc)
        self.assertEqual(S.groupes_par_nom(sc, analyse, "plans"),
                         trier([["A", "B", "C", "F"], ["D"], ["E"], ["G"]]))
        infos = {sc.noms[f]: i for f, i in analyse.infos.items()}
        self.assertIsNone(infos["H"]["groupe_plan"])
        groupes = {g["groupe"]: g for g in analyse.familles["plans"]["groupes"]}
        grand = groupes[infos["A"]["groupe_plan"]]
        self.assertEqual(len(grand["niveaux"]), 2)               # z = 0 et z = 5
        self.assertAlmostEqual(grand["niveaux"][0], 0.0, delta=1e-3)
        self.assertAlmostEqual(grand["niveaux"][1], 5.0, delta=1e-3)
        inverse = groupes[infos["E"]["groupe_plan"]]
        self.assertAlmostEqual(inverse["normale"][2], -1.0, delta=1e-9)   # normale sortante −Z


class GroupeCylindre(unittest.TestCase):
    def scene(self):
        sc = S.Scene()
        sc.bande_cylindre("A r=3.000", cx=0, r=3.000)
        sc.bande_cylindre("B r=3.002", cx=50, r=3.002)
        sc.bande_cylindre("C r=3.010", cx=100, r=3.010)
        sc.bande_cylindre("D r=5", cx=150, r=5.0)
        sc.bande_cylindre("E r=5", cx=200, r=5.0, z0=20, z1=30)
        sc.quart_cylindre("F extrusion r=3", ox=300, R=3.0, genre="extrusion")
        sc.calotte_sphere("S sphère", centre=(400, 0, 0), R=10.0, zc=6.0)
        sc.plan_rect("P plan", 500)
        return sc

    def test_regroupement_par_rayon(self):
        sc = self.scene()
        analyse = analyser(sc)
        self.assertEqual(S.groupes_par_nom(sc, analyse, "cylindres"), trier([
            ["A r=3.000", "B r=3.002", "F extrusion r=3"], ["C r=3.010"], ["D r=5", "E r=5"]]))
        groupes = analyse.familles["cylindres"]["groupes"]
        rayons = [g["rayon"] for g in groupes]
        self.assertEqual(rayons, sorted(rayons))                  # rayon croissant
        self.assertTrue(groupes[0]["contient_equivalents"])        # l'extrusion de cercle
        self.assertEqual([g["contient_equivalents"] for g in groupes[1:]], [False, False])

    def test_tolerance_lineaire(self):
        """Avec 0,02 de tolérance, le rayon 3,010 rejoint les rayons 3,000 et 3,002."""
        sc = self.scene()
        analyse = analyser(sc, tol_lin=0.02)
        self.assertEqual(S.groupes_par_nom(sc, analyse, "cylindres"), trier([
            ["A r=3.000", "B r=3.002", "C r=3.010", "F extrusion r=3"], ["D r=5", "E r=5"]]))


class FamilleTangente(unittest.TestCase):
    def test_groupe_tangent_au_format_des_familles(self):
        sc = S.Scene()
        fc, fp = sc.quart_cylindre("cyl", genre="analytique", plan="plan", inclinaison_deg=0.0)
        sc.plan_rect("isolé", 300)
        analyse = analyser(sc)
        fam = analyse.familles["tangent"]
        self.assertEqual(fam["nom"], "Groupe_Tangent")
        tailles = sorted(g["nombre_faces"] for g in fam["groupes"])
        self.assertEqual(tailles, [1, 2])                         # les faces isolées comptent
        for g in fam["groupes"]:
            self.assertEqual(g["groupe"], analyse.groupe_de_face[g["faces"][0]])


if __name__ == "__main__":
    unittest.main()
