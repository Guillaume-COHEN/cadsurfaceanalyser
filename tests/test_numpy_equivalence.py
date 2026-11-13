# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Le calcul vectorisé (numpy) doit donner les mêmes résultats que le calcul
en Python pur. Ces tests sont ignorés si numpy n'est pas installé."""

import os
import tempfile
import unittest

import _support as S

from cadsurf import accel


def scene_numerique():
    """Une face de chaque type à surface numérique, et des faces analytiques
    bordées d'arcs (celles que le calcul vectorisé traite aussi)."""
    sc = S.Scene()
    sc.quart_cylindre("nurbs", ox=0, R=2.0, L=5.0, genre="nurbs")
    sc.quart_cylindre("extrusion", ox=30, R=5.0, L=10.0, genre="extrusion")
    sc.patch_tore("révolution", centre=(60, 0, 0), genre="revolution")
    sc.patch_tore("tore", centre=(120, 0, 0), genre="tore")
    sc.bande_cylindre("bande", cx=200, r=4.0, z0=0, z1=9)
    sc.plan_perce("plan percé")
    sc.calotte_sphere("calotte", centre=(300, 0, 0), R=10.0, zc=6.0)
    sc.cone_plein("cône")
    return sc


@unittest.skipUnless(accel.DISPONIBLE, "numpy non installé")
class EquivalenceNumpy(unittest.TestCase):
    def tearDown(self):
        accel.activer(True)

    def calculer(self, chemin, utiliser_numpy):
        accel.activer(utiliser_numpy)
        accel.REPLIS = 0
        analyse = S.analyser_fichier(chemin)
        return analyse, accel.REPLIS

    def test_aires_barycentres_et_volume(self):
        scene = scene_numerique()
        with tempfile.TemporaryDirectory() as dossier:
            chemin = scene.ecrire(os.path.join(dossier, "n.stp"))
            pur, _ = self.calculer(chemin, False)
            vec, replis = self.calculer(chemin, True)
        self.assertEqual(replis, 0, "aucune arête ne doit retomber sur le calcul scalaire")
        self.assertEqual(sorted(pur.infos), sorted(vec.infos))
        for fid in pur.infos:
            nom = scene.noms[fid]
            a, b = pur.infos[fid], vec.infos[fid]
            with self.subTest(nom):
                self.assertAlmostEqual(b["aire"] / a["aire"], 1.0, delta=1e-9)
                for p, q in zip(a["barycentre"], b["barycentre"]):
                    self.assertAlmostEqual(p, q, delta=1e-7)
                self.assertAlmostEqual(b["volume_signe"], a["volume_signe"],
                                       delta=1e-8 * max(1.0, abs(a["volume_signe"])))
                self.assertEqual(a["aire_fiable"], b["aire_fiable"])

    def test_groupes_identiques(self):
        scene = scene_numerique()
        with tempfile.TemporaryDirectory() as dossier:
            chemin = scene.ecrire(os.path.join(dossier, "n.stp"))
            pur, _ = self.calculer(chemin, False)
            vec, _ = self.calculer(chemin, True)
        for cle in ("coaxiales", "paralleles", "concentriques", "identiques",
                    "coplanaires", "plans", "cylindres"):
            self.assertEqual(S.groupes_par_nom(scene, pur, cle),
                             S.groupes_par_nom(scene, vec, cle), cle)

    def test_precision_numerique(self):
        """K = 48 (fine) rapproche l'aire de la valeur exacte du NURBS."""
        from cadsurf import geom_faces
        scene = S.Scene()
        scene.quart_cylindre("nurbs", R=2.0, L=5.0, genre="nurbs")
        exacte = 2 * 3.141592653589793 / 2 * 5
        ancien = geom_faces.K_NUMERIQUE
        try:
            with tempfile.TemporaryDirectory() as dossier:
                chemin = scene.ecrire(os.path.join(dossier, "n.stp"))
                erreurs = {}
                for k in (12, 24, 48):
                    geom_faces.K_NUMERIQUE = k
                    (info,) = S.analyser_fichier(chemin).infos.values()
                    erreurs[k] = abs(info["aire"] - exacte) / exacte
        finally:
            geom_faces.K_NUMERIQUE = ancien
        self.assertLess(erreurs[48], 1e-8)
        self.assertLess(erreurs[24], 1e-5)
        self.assertLess(erreurs[12], 1e-3)


if __name__ == "__main__":
    unittest.main()
