# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Aires et barycentres comparés à des valeurs exactes (formules analytiques).

Chaque cas est une face construite exprès, dont l'aire et le barycentre se
calculent à la main (voir docs : section « Validation »).
"""

import math
import os
import tempfile
import unittest

import _support as S

PI = math.pi

# nom du cas : (générateur de la face, aire exacte, barycentre exact ou None)
# Les faces refermées sur un pôle (sphère) ou un sommet (cône) sont calculées
# exactement mais signalées « à contrôler » (aire_fiable = faux) : voir CAS_A_CONTROLER.
CAS = {
    "plan percé : 400 − 9π": (
        lambda sc: sc.plan_perce(),
        400.0 - 9.0 * PI, (0.0, 0.0, 0.0)),
    "bande de cylindre : 2π R L (R=10, L=20)": (
        lambda sc: sc.bande_cylindre("cyl", r=10.0, z0=0.0, z1=20.0),
        2 * PI * 10 * 20, (0.0, 0.0, 10.0)),
    "calotte de sphère : 2π R (R − z) (R=10, z=6)": (
        lambda sc: sc.calotte_sphere("sphère", R=10.0, zc=6.0),
        2 * PI * 10 * (10 - 6), (0.0, 0.0, 8.0)),
    "cône plein : π r l": (
        lambda sc: sc.cone_plein(),
        PI * 10 * math.hypot(10, 20), (0.0, 0.0, 10 - 20 / 3.0)),
    "patch de tore (TOROIDAL_SURFACE)": (
        lambda sc: sc.patch_tore("tore", genre="tore"),
        3 * (PI / 3) * (10 * (PI / 2 + PI / 4) + 3 * (1 + math.sin(PI / 4))), None),
    "patch de tore (révolution d'un cercle)": (
        lambda sc: sc.patch_tore("rév", genre="revolution"),
        3 * (PI / 3) * (10 * (PI / 2 + PI / 4) + 3 * (1 + math.sin(PI / 4))), None),
    "quart de cylindre (extrusion) : R (π/2) L": (
        lambda sc: sc.quart_cylindre("ext", R=5.0, L=10.0, genre="extrusion"),
        5 * (PI / 2) * 10, (2 * 5 / PI, 2 * 5 / PI, 5.0)),
    "quart de cylindre (analytique) : R (π/2) L": (
        lambda sc: sc.quart_cylindre("ana", R=5.0, L=10.0, genre="analytique"),
        5 * (PI / 2) * 10, (2 * 5 / PI, 2 * 5 / PI, 5.0)),
    "quart de cylindre (NURBS rationnelle)": (
        lambda sc: sc.quart_cylindre("nurbs", R=2.0, L=5.0, genre="nurbs"),
        2 * (PI / 2) * 5, (2 * 2 / PI, 2 * 2 / PI, 2.5)),
}

CAS_A_CONTROLER = (
    "calotte de sphère : 2π R (R − z) (R=10, z=6)",
    "cône plein : π r l",
)


def analyser_scene(scene, **options):
    with tempfile.TemporaryDirectory() as dossier:
        return S.analyser_fichier(scene.ecrire(os.path.join(dossier, "f.stp")), **options)


class AiresAnalytiques(unittest.TestCase):
    def test_cas_exacts(self):
        for nom, (generateur, aire, barycentre) in CAS.items():
            with self.subTest(nom):
                scene = S.Scene()
                generateur(scene)
                (info,) = analyser_scene(scene).infos.values()
                if nom in CAS_A_CONTROLER:
                    self.assertFalse(info["aire_fiable"])
                    self.assertIn("pôle", info["aire_remarque"])
                else:
                    self.assertTrue(info["aire_fiable"], info["aire_remarque"])
                self.assertAlmostEqual(info["aire"] / aire, 1.0, delta=1e-8)
                if barycentre is not None:
                    for obtenu, attendu in zip(info["barycentre"], barycentre):
                        self.assertAlmostEqual(obtenu, attendu, delta=1e-6)

    def test_tore_et_revolution_identiques(self):
        """TOROIDAL_SURFACE et révolution d'un cercle décrivent la même face."""
        resultats = []
        for genre in ("tore", "revolution"):
            scene = S.Scene()
            scene.patch_tore("t", genre=genre)
            (info,) = analyser_scene(scene).infos.values()
            resultats.append((info["aire"], info["barycentre"], info["courbure"]))
        self.assertAlmostEqual(resultats[0][0] / resultats[1][0], 1.0, delta=1e-9)
        for a, b in zip(resultats[0][1], resultats[1][1]):
            self.assertAlmostEqual(a, b, delta=1e-7)
        self.assertEqual(resultats[0][2], resultats[1][2])

    def test_revolution_circulaire_reconnue_comme_tore(self):
        scene = S.Scene()
        scene.patch_tore("rév", genre="revolution")
        (info,) = analyser_scene(scene).infos.values()
        self.assertEqual(info["type"], "SURFACE_OF_REVOLUTION")
        self.assertEqual(info["type_equivalent"], "TOROIDAL_SURFACE")
        equivalent = info["parametres"]["equivalent"]
        self.assertAlmostEqual(equivalent["rayon_majeur"], 10.0, delta=1e-6)
        self.assertAlmostEqual(equivalent["rayon_mineur"], 3.0, delta=1e-6)

    def test_cylindre_equivalent_par_extrusion(self):
        scene = S.Scene()
        scene.quart_cylindre("ext", R=5.0, genre="extrusion")
        (info,) = analyser_scene(scene).infos.values()
        self.assertEqual(info["type_equivalent"], "CYLINDRICAL_SURFACE")
        self.assertAlmostEqual(info["parametres"]["equivalent"]["rayon"], 5.0, delta=1e-9)

    def test_courbure_convexe_concave(self):
        """same_sense vrai : matière côté axe (convexe) ; faux : concave."""
        for meme_sens, attendu in ((True, "convexe"), (False, "concave")):
            scene = S.Scene()
            s = scene.ajouter("CYLINDRICAL_SURFACE('',%s,3.)" % scene.axe())
            v = scene.sommet((3, 0, 5))
            e = scene.arete(v, v, scene.cercle(scene.axe((0, 0, 5)), 3.0))
            w = scene.sommet((3, 0, 0))
            f = scene.arete(w, w, scene.cercle(scene.axe(), 3.0))
            scene.face("c", [scene.boucle([scene.oriente(e, False)]),
                             scene.boucle([scene.oriente(f, True)], exterieure=False)], s, meme_sens)
            (info,) = analyser_scene(scene, geometrie=False).infos.values()
            self.assertEqual(info["courbure"], attendu)


if __name__ == "__main__":
    unittest.main()
