# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Non-régression sur les fichiers STEP réels déposés dans data/stp_tests/.

Ces tests sont ignorés tant que les fichiers ne sont pas présents. Les valeurs
de référence ont été relevées avec cette version du programme sur
TestAnalyseSurf.stp et PocheS5_Coin.stp ; elles ne prouvent pas l'exactitude
absolue (voir test_geometrie.py pour cela) mais détectent tout changement
involontaire des résultats.
"""

import glob
import json
import os
import shutil
import tempfile
import unittest

import _support as S

DONNEES = os.path.join(S.RACINE, "data", "stp_tests")


def chemin(nom):
    return os.path.join(DONNEES, nom)


def traiter(nom):
    """Lance le programme sur une copie du fichier ; retourne (processus, JSON)."""
    with tempfile.TemporaryDirectory() as dossier:
        copie = os.path.join(dossier, "piece.stp")
        shutil.copy(chemin(nom), copie)
        r = S.lancer_cli(copie, "--familles-step", "aucune", "--sans-stp-bspline", "--sorties", "json")
        j = None
        sortie = os.path.join(dossier, "piece_groupes_tangents.json")
        if os.path.exists(sortie):
            with open(sortie, encoding="utf-8") as f:
                j = json.load(f)
    return r, j


def groupes_tangents(j):
    return sorted(sorted(int(x) for x in g["faces"]) for g in j["groupes"] if len(g["faces"]) > 1)


def tailles(j, cle):
    return sorted(g["nombre_faces"] for g in j["familles_geometriques"][cle]["groupes"])


@unittest.skipUnless(os.path.isfile(chemin("TestAnalyseSurf.stp")),
                     "déposer TestAnalyseSurf.stp dans data/stp_tests/ pour activer ce test")
class TestAnalyseSurf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r, cls.j = traiter("TestAnalyseSurf.stp")

    def test_execution(self):
        self.assertEqual(self.r.returncode, 0, self.r.stdout[-800:])

    def test_totaux(self):
        res = self.j["resume"]
        self.assertEqual(len(self.j["faces"]), 18)
        self.assertAlmostEqual(res["aire_totale"] / 25475.568391, 1.0, delta=1e-7)
        self.assertAlmostEqual(res["volume_estime"] / 126914.0933, 1.0, delta=1e-7)
        self.assertLess(res["controle_fermeture_aire_vectorielle"], 1e-8)
        self.assertEqual(res["faces_aire_non_fiable"], [])

    def test_groupes_tangents(self):
        self.assertEqual(groupes_tangents(self.j), [[323, 347, 394, 418, 442, 459, 481, 498, 515, 527, 539]])
        self.assertEqual(tailles(self.j, "tangent"), [1] * 7 + [11])

    def test_familles(self):
        self.assertEqual(tailles(self.j, "coaxiales"), [2, 2])
        self.assertEqual(tailles(self.j, "paralleles"), [2, 3, 3, 4])
        self.assertEqual(tailles(self.j, "coplanaires"), [2, 2, 3])
        self.assertEqual(len(self.j["familles_geometriques"]["plans"]["groupes"]), 9)

    def test_cylindres_par_rayon(self):
        groupes = self.j["familles_geometriques"]["cylindres"]["groupes"]
        self.assertEqual([g["nombre_faces"] for g in groupes], [3, 1, 1])
        for obtenu, attendu in zip([g["rayon"] for g in groupes], [5.0, 10.365792, 15.845628]):
            self.assertAlmostEqual(obtenu, attendu, delta=1e-4)


@unittest.skipUnless(os.path.isfile(chemin("PocheS5_Coin.stp")),
                     "déposer PocheS5_Coin.stp dans data/stp_tests/ pour activer ce test")
class PocheCoin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r, cls.j = traiter("PocheS5_Coin.stp")

    def test_execution(self):
        self.assertEqual(self.r.returncode, 0, self.r.stdout[-800:])

    def test_totaux(self):
        res = self.j["resume"]
        self.assertEqual(len(self.j["faces"]), 17)
        self.assertAlmostEqual(res["aire_totale"] / 1261.451382, 1.0, delta=1e-7)
        self.assertAlmostEqual(res["volume_estime"] / 1496.7113, 1.0, delta=1e-6)
        self.assertLess(res["controle_fermeture_aire_vectorielle"], 1e-5)
        self.assertEqual(res["faces_aire_non_fiable"], [])

    def test_types_de_surfaces(self):
        types = {v["type"] for v in self.j["faces"].values()}
        self.assertEqual(types, {"B_SPLINE_SURFACE", "CYLINDRICAL_SURFACE", "PLANE",
                                 "SURFACE_OF_REVOLUTION", "TOROIDAL_SURFACE"})
        bsplines = sorted(int(k) for k, v in self.j["faces"].items() if v["type"] == "B_SPLINE_SURFACE")
        self.assertEqual(bsplines, [504, 590, 691])

    def test_les_bsplines_entrent_dans_les_groupes_tangents(self):
        """Régression : les faces B-spline étaient exclues des groupes tangents."""
        self.assertEqual(groupes_tangents(self.j),
                         [[145, 435, 467, 607, 691, 724, 754, 775], [371, 418]])
        self.assertEqual(tailles(self.j, "tangent"), [1] * 7 + [2, 8])

    def test_familles(self):
        self.assertEqual(tailles(self.j, "coaxiales"), [3])
        self.assertEqual(tailles(self.j, "paralleles"), [3, 4, 5])
        self.assertEqual(tailles(self.j, "concentriques"), [2])
        self.assertEqual(tailles(self.j, "identiques"), [2])
        self.assertEqual(tailles(self.j, "coplanaires"), [2, 2, 2, 3])
        self.assertEqual(tailles(self.j, "plans"), [1, 1, 1, 2, 3])

    def test_cylindres_par_rayon(self):
        groupes = self.j["familles_geometriques"]["cylindres"]["groupes"]
        for obtenu, attendu in zip([g["rayon"] for g in groupes], [4.0, 7.0, 15124.046829]):
            self.assertAlmostEqual(obtenu / attendu, 1.0, delta=1e-6)


class FichiersDuDossier(unittest.TestCase):
    """Tout fichier STEP déposé dans data/stp_tests/ doit se traiter sans erreur."""

    def test_aucun_plantage(self):
        fichiers = sorted(glob.glob(os.path.join(DONNEES, "*.stp")) + glob.glob(os.path.join(DONNEES, "*.step"))
                          + glob.glob(os.path.join(DONNEES, "*.STP")) + glob.glob(os.path.join(DONNEES, "*.STEP")))
        if not fichiers:
            self.skipTest("aucun fichier STEP dans data/stp_tests/")
        for fichier in fichiers:
            with self.subTest(os.path.basename(fichier)):
                r, j = traiter(os.path.basename(fichier))
                self.assertEqual(r.returncode, 0, r.stdout[-1000:])
                self.assertIn("TERMINE", r.stdout)
                self.assertGreater(j["resume"]["aire_totale"], 0.0)


if __name__ == "__main__":
    unittest.main()
