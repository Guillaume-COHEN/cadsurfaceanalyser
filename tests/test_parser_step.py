# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Lecture du format STEP (ISO 10303-21)."""

import os
import tempfile
import unittest

import _support as S

from cadsurf.step_parser import Enum, Ref, StepFile

CONTENU = """ISO-10303-21;
HEADER;
ENDSEC;
DATA;
/* commentaire ; avec point-virgule */
#1=CARTESIAN_POINT('l''apostrophe ; et un point-virgule',(1.5,-2.E-1,3.));
#2=AXIS2_PLACEMENT_3D('',#1,$,*);
#3=LINE('',#1,#4);
#4=VECTOR('',#5,1.);
#5=DIRECTION('',(0.,0.,1.));
#6=(BOUNDED_CURVE()B_SPLINE_CURVE(1,(#1,#1),.UNSPECIFIED.,.F.,.F.)
B_SPLINE_CURVE_WITH_KNOTS((2,2),(0.,1.),.UNSPECIFIED.)CURVE()
RATIONAL_B_SPLINE_CURVE((1.,2.))REPRESENTATION_ITEM('courbe'));
#7=ADVANCED_FACE('',(#8),#9,.T.);
ENDSEC;
END-ISO-10303-21;
"""


class Parseur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.TemporaryDirectory()
        chemin = os.path.join(cls.dossier.name, "p.stp")
        with open(chemin, "w", encoding="latin-1") as f:
            f.write(CONTENU)
        cls.step = StepFile(chemin)

    @classmethod
    def tearDownClass(cls):
        cls.dossier.cleanup()

    def test_instances_lues(self):
        self.assertEqual(sorted(self.step.ents), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(self.step.type_of(3), "LINE")

    def test_chaines_nombres_et_commentaires(self):
        nom, coordonnees = self.step.get(1, "CARTESIAN_POINT")
        self.assertEqual(nom, "l'apostrophe ; et un point-virgule")   # '' -> ' ; ';' dans une chaîne
        self.assertEqual(coordonnees, [1.5, -0.2, 3.0])

    def test_references_valeurs_omises_et_enumerations(self):
        a = self.step.get(2, "AXIS2_PLACEMENT_3D")
        self.assertIsInstance(a[1], Ref)
        self.assertEqual(int(a[1]), 1)
        self.assertIsNone(a[2])                                      # $
        self.assertEqual(a[3], "*")                                  # *
        face = self.step.get(7, "ADVANCED_FACE")
        self.assertIsInstance(face[3], Enum)
        self.assertEqual(str(face[3]), "T")

    def test_entite_complexe_normalisee(self):
        """Les parties d'une NURBS rationnelle sont ramenées à la disposition
        des entités simples (nom en tête, nœuds dans la même liste)."""
        types = self.step.types_of(6)
        self.assertIn("B_SPLINE_CURVE_WITH_KNOTS", types)
        self.assertIn("RATIONAL_B_SPLINE_CURVE", types)
        avec_noeuds = self.step.get(6, "B_SPLINE_CURVE_WITH_KNOTS")
        self.assertEqual(avec_noeuds[0], "courbe")                   # nom repris de REPRESENTATION_ITEM
        self.assertEqual(avec_noeuds[1], 1.0)                        # degré
        self.assertEqual(avec_noeuds[6], [2.0, 2.0])                 # multiplicités
        self.assertEqual(avec_noeuds[7], [0.0, 1.0])                 # nœuds
        self.assertEqual(self.step.get(6, "RATIONAL_B_SPLINE_CURVE")[0], [1.0, 2.0])

    def test_section_data_absente(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "vide.stp")
            with open(chemin, "w") as f:
                f.write("pas un fichier STEP\n")
            with self.assertRaises(ValueError):
                StepFile(chemin)


if __name__ == "__main__":
    unittest.main()
