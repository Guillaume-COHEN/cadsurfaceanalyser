# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Détection de tangence : angle mesuré entre une face courbe et un plan voisin."""

import os
import tempfile
import unittest

import _support as S


class TangenceCourbePlan(unittest.TestCase):
    """Quart de cylindre (analytique, extrusion ou NURBS) contre un plan
    incliné de 0°, 0,3° ou 10° autour de leur arête commune."""

    def _jonction(self, genre, inclinaison):
        scene = S.Scene()
        fc, fp = scene.quart_cylindre(
            "cyl", R=2.0, L=5.0, genre=genre, plan="plan", inclinaison_deg=inclinaison
        )
        with tempfile.TemporaryDirectory() as dossier:
            analyse = S.analyser_fichier(
                scene.ecrire(os.path.join(dossier, "f.stp")), geometrie=False
            )
        (j,) = [j for j in analyse.jonctions if {j["face_a"], j["face_b"]} == {fc, fp}]
        return j, analyse.groupe_de_face[fc] == analyse.groupe_de_face[fp]

    def test_angle_mesure_et_tangence(self):
        for genre in ("analytique", "extrusion", "nurbs"):
            for inclinaison, tangente in ((0.0, True), (0.3, True), (10.0, False)):
                with self.subTest(genre=genre, inclinaison=inclinaison):
                    j, meme_groupe = self._jonction(genre, inclinaison)
                    self.assertEqual(j["status"], "TANGENTE" if tangente else "non tangente")
                    self.assertAlmostEqual(j["max_angle_deg"], inclinaison, delta=0.01)
                    self.assertEqual(j["tangent"], tangente)
                    self.assertEqual(meme_groupe, tangente)

    def test_surface_bspline_comparable_a_un_voisin(self):
        """Régression : les normales des surfaces B-spline étaient rejetées à
        tort (statut « normale impossible »), ce qui les excluait des groupes."""
        j, _ = self._jonction("nurbs", 0.0)
        self.assertNotEqual(j["status"], "normale impossible")
        self.assertIsNotNone(j["max_angle_deg"])

    def test_tolerance_angulaire(self):
        """Avec une tolérance de 0,1°, un écart de 0,3° n'est plus tangent."""
        scene = S.Scene()
        fc, fp = scene.quart_cylindre("cyl", genre="analytique", plan="plan", inclinaison_deg=0.3)
        with tempfile.TemporaryDirectory() as dossier:
            chemin = scene.ecrire(os.path.join(dossier, "f.stp"))
            large = S.analyser_fichier(chemin, tol_deg=1.0, geometrie=False)
            serree = S.analyser_fichier(chemin, tol_deg=0.1, geometrie=False)
        self.assertEqual(large.groupe_de_face[fc], large.groupe_de_face[fp])
        self.assertNotEqual(serree.groupe_de_face[fc], serree.groupe_de_face[fp])


if __name__ == "__main__":
    unittest.main()
