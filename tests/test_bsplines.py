# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Propriétés mathématiques des B-splines et NURBS (Piegl et Tiller, NURBS Book)."""

import math
import os
import tempfile
import unittest

import _support as S

from cadsurf.bsplines import (
    BSplineCurve, BSplineSurface, basis_funs, basis_funs_d1, find_span,
)
from cadsurf.step_parser import StepFile
from cadsurf.vecteurs import norm, sub

# vecteur nodal ouvert de degré 3 avec un nœud interne double
NOEUDS = [0, 0, 0, 0, 1, 2, 2, 3, 4, 4, 4, 4]
DEGRE = 3


class FonctionsDeBase(unittest.TestCase):
    def test_partition_de_l_unite(self):
        """Σ_i N_{i,p}(t) = 1 sur tout le domaine."""
        for k in range(401):
            t = 4.0 * k / 400
            span = find_span(DEGRE, NOEUDS, t)
            self.assertAlmostEqual(sum(basis_funs(span, t, DEGRE, NOEUDS)), 1.0, delta=1e-13)

    def test_derivees_somme_nulle_et_differences_finies(self):
        for t in (0.13, 0.9, 1.5, 2.4, 3.77):
            span = find_span(DEGRE, NOEUDS, t)
            N, dN = basis_funs_d1(span, t, DEGRE, NOEUDS)
            self.assertAlmostEqual(sum(dN), 0.0, delta=1e-12)         # dérivée de la somme = 0
            h = 1e-6
            Np = basis_funs(find_span(DEGRE, NOEUDS, t + h), t + h, DEGRE, NOEUDS)
            Nm = basis_funs(find_span(DEGRE, NOEUDS, t - h), t - h, DEGRE, NOEUDS)
            for i in range(DEGRE + 1):
                if find_span(DEGRE, NOEUDS, t + h) == span == find_span(DEGRE, NOEUDS, t - h):
                    self.assertAlmostEqual(dN[i], (Np[i] - Nm[i]) / (2 * h), delta=1e-6)

    def test_intervalle(self):
        self.assertEqual(find_span(DEGRE, NOEUDS, 0.0), DEGRE)
        self.assertEqual(find_span(DEGRE, NOEUDS, 1.5), 4)
        self.assertEqual(find_span(DEGRE, NOEUDS, 4.0), len(NOEUDS) - DEGRE - 2)   # fin : dernier intervalle


def etape_nurbs():
    """STEP minimal : quart de cercle NURBS rationnel (rayon 2) et quart de cylindre."""
    scene = S.Scene()
    scene.quart_cylindre("cyl", R=2.0, L=5.0, genre="nurbs")
    c = math.sqrt(2) / 2
    a, b, d = scene.pt(2, 0, 0), scene.pt(2, 2, 0), scene.pt(0, 2, 0)
    courbe = scene.ajouter(
        "(BOUNDED_CURVE()B_SPLINE_CURVE(2,(%s,%s,%s),.UNSPECIFIED.,.F.,.F.)"
        "B_SPLINE_CURVE_WITH_KNOTS((3,3),(0.,1.),.UNSPECIFIED.)CURVE()"
        "GEOMETRIC_REPRESENTATION_ITEM()RATIONAL_B_SPLINE_CURVE((1.,%r,1.))"
        "REPRESENTATION_ITEM(''))" % (a, b, d, c))
    return scene, courbe


class Nurbs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.TemporaryDirectory()
        scene, cls.courbe = etape_nurbs()
        cls.step = StepFile(scene.ecrire(os.path.join(cls.dossier.name, "n.stp")))
        cls.ref_courbe = int(cls.courbe[1:])
        surfaces = [e for e in cls.step.ents if "B_SPLINE_SURFACE" in cls.step.types_of(e)]
        cls.ref_surface = surfaces[0]

    @classmethod
    def tearDownClass(cls):
        cls.dossier.cleanup()

    def test_quart_de_cercle_exact(self):
        """Une NURBS rationnelle de degré 2 représente exactement un cercle."""
        courbe = BSplineCurve(self.step, self.ref_courbe)
        for k in range(21):
            t = k / 20.0
            P = courbe.eval(t)
            self.assertAlmostEqual(norm((P[0], P[1], 0.0)), 2.0, delta=1e-12)
            self.assertAlmostEqual(P[2], 0.0, delta=1e-14)

    def test_derivee_de_courbe_analytique(self):
        courbe = BSplineCurve(self.step, self.ref_courbe)
        for t in (0.1, 0.37, 0.8):
            h = 1e-6
            fd = tuple((a - b) / (2 * h) for a, b in zip(courbe.eval(t + h), courbe.eval(t - h)))
            exacte = courbe.eval_d(t)
            self.assertLess(norm(sub(fd, exacte)) / norm(exacte), 1e-7)

    def test_surface_cylindrique_exacte(self):
        surface = BSplineSurface(self.step, self.ref_surface)
        for i in range(9):
            for j in range(5):
                u, v = i / 8.0, j / 4.0
                S_, Su, Sv = surface.eval_derivs(u, v)
                self.assertAlmostEqual(math.hypot(S_[0], S_[1]), 2.0, delta=1e-12)
                self.assertAlmostEqual(S_[2], 5.0 * v, delta=1e-12)
                # normale radiale : Su × Sv est colinéaire à (x, y, 0)
                nx = Su[1] * Sv[2] - Su[2] * Sv[1]
                ny = Su[2] * Sv[0] - Su[0] * Sv[2]
                nz = Su[0] * Sv[1] - Su[1] * Sv[0]
                self.assertAlmostEqual(nz, 0.0, delta=1e-10)
                self.assertAlmostEqual(nx * S_[1] - ny * S_[0], 0.0, delta=1e-10)

    def test_projection_d_un_point(self):
        surface = BSplineSurface(self.step, self.ref_surface)
        P = (2 * math.cos(0.7), 2 * math.sin(0.7), 3.3)
        u, v = surface.project(P)
        S_ = surface.eval(u, v)
        self.assertLess(norm(sub(S_, P)), 1e-9)
        # point hors surface : projection radiale
        Q = (3 * math.cos(0.7), 3 * math.sin(0.7), 3.3)
        u, v = surface.project(Q)
        self.assertLess(norm(sub(surface.eval(u, v), P)), 1e-8)

    def test_normale_non_rejetee(self):
        """Régression : le produit vectoriel (~1e-8) ne doit pas être rejeté par EPS."""
        surface = BSplineSurface(self.step, self.ref_surface)
        n = surface.normal((2 * math.cos(0.7), 2 * math.sin(0.7), 3.3))
        self.assertIsNotNone(n)
        self.assertAlmostEqual(n[0], math.cos(0.7), delta=1e-8)
        self.assertAlmostEqual(n[1], math.sin(0.7), delta=1e-8)


if __name__ == "__main__":
    unittest.main()
