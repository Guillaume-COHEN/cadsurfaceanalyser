# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Interface graphique, avec un faux tkinter (voir faketk.py).

Les traitements lancés depuis la fenêtre sont réels (sous-processus) ; seul
l'affichage est simulé. Un essai sur un vrai écran reste nécessaire pour
juger de l'apparence."""

import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

import _support as S
import faketk

import cadsurf.interface as interface
from cadsurf import accel
from cadsurf import interface_logique as L
from cadsurf.familles import TOUTES_LES_FAMILLES
from cadsurf.interface import Application

IDENTIQUE = "Identique au dossier du fichier STEP d'entrée"
ATTENDUES = {"tangent", "coaxiales", "paralleles", "concentriques", "identiques",
             "coplanaires", "plans", "cylindres"}


class FenetreBase(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory()
        self.dossier = self._dossier.name
        self.reglages = os.path.join(self.dossier, "reglages.json")
        sc = S.Scene()
        sc.plan_perce("plan")
        sc.bande_cylindre("cylindre", cx=50, r=5.0, z0=0, z1=10)
        self.piece = sc.ecrire(os.path.join(self.dossier, "piece.stp"))
        self._numpy_dispo = accel.DISPONIBLE

    def tearDown(self):
        accel.DISPONIBLE = self._numpy_dispo
        self._dossier.cleanup()

    def nouvelle(self, ecran=(1920, 1080), numpy_dispo=None, reglages=None):
        if numpy_dispo is not None:
            accel.DISPONIBLE = numpy_dispo
        tk, ttk, fd, mb = faketk.creer(ecran)
        racine = tk.Tk()
        app = Application(racine, tk, ttk, fd, mb, fichier_reglages=reglages or self.reglages)
        return app, racine, fd, mb

    @staticmethod
    def widget(texte):
        for w in faketk.Widget.toutes:
            if w.opts.get("text") == texte:
                return w
        raise KeyError(texte)

    @staticmethod
    def widgets(texte):
        return [w for w in faketk.Widget.toutes if w.opts.get("text") == texte]

    @staticmethod
    def boucle(app, racine, max_s=60):
        """Fait tourner la boucle d'événements simulée jusqu'à la fin du traitement."""
        debut = time.time()
        while time.time() - debut < max_s:
            for cb in racine.echeances():
                cb()
            if app.traitement is not None and not app.traitement.en_cours() and not racine.afters:
                return True
            time.sleep(0.02)
        return False

    def sorties(self, dossier=None):
        dossier = dossier or self.dossier
        return sorted(os.path.basename(p) for p in glob.glob(dossier + "/*")
                      if os.path.isfile(p) and os.path.basename(p) not in ("piece.stp", "reglages.json"))


class EtatInitial(FenetreBase):
    def test_valeurs_par_defaut(self):
        app, racine, fd, mb = self.nouvelle()
        self.assertIn("CADSurfaceAnalyser", racine.titre)
        self.assertEqual(app.v_fichier.get(), "")
        self.assertEqual(set(app.v_familles), ATTENDUES)
        self.assertEqual(len(TOUTES_LES_FAMILLES), 8)
        self.assertTrue(all(v.get() for v in app.v_familles.values()))
        self.assertTrue(app.v_bspline.get())
        self.assertEqual(len(app.v_sorties), 5)
        self.assertTrue(all(v.get() for v in app.v_sorties.values()))
        self.assertTrue(app.v_identique.get())
        self.assertEqual(app.e_dossier.opts["state"], "disabled")
        self.assertEqual(app.lire_parametres().precision, "standard")
        self.assertEqual(app.v_numpy.get(), accel.DISPONIBLE)
        self.assertEqual(app.b_arreter.opts["state"], "disabled")
        self.assertEqual(app.b_ouvrir.opts["state"], "disabled")
        self.assertEqual(app.c_precision.opts["values"], [lib for _, lib in L.PRECISIONS])

    def test_case_groupe_cylindre_presente(self):
        app, *_ = self.nouvelle()
        self.assertIn("cylindres", app.v_familles)
        self.assertTrue(app.v_familles["cylindres"].get())
        self.widget("Groupe_Cylindre")
        self.assertTrue(any("de même rayon" in str(w.opts.get("text", "")) for w in faketk.Widget.toutes))

    def test_lancement_sans_fichier_refuse(self):
        app, racine, fd, mb = self.nouvelle()
        app.b_lancer.invoke()
        self.assertEqual(mb.appels[-1][0], "erreur")
        self.assertIsNone(app.traitement)


class ChoixFichierEtDossier(FenetreBase):
    def test_fichier_et_dossier(self):
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        self.assertEqual(app.v_fichier.get(), self.piece)
        self.assertEqual(app.v_dossier.get(), self.dossier)             # identique au STEP
        self.assertTrue(any("*.stp" in t[1] for t in fd.appels[-1][1]["filetypes"]))
        self.widget(IDENTIQUE).invoke()                                 # décoché
        self.assertEqual(app.e_dossier.opts["state"], "normal")
        self.assertEqual(app.b_dossier.opts["state"], "normal")
        fd.resultat_dossier = os.path.join(self.dossier, "res", "sous")
        app.parcourir_dossier()
        self.assertEqual(app.v_dossier.get(), fd.resultat_dossier)
        self.widget(IDENTIQUE).invoke()                                 # recoché
        self.assertEqual(app.v_dossier.get(), self.dossier)
        self.assertEqual(app.e_dossier.opts["state"], "disabled")
        self.widget(IDENTIQUE).invoke()                                 # redécoché : dossier retrouvé
        self.assertEqual(app.v_dossier.get(), fd.resultat_dossier)

    def test_boutons_tout_selectionner(self):
        app, *_ = self.nouvelle()
        tout_des, tout_sel = self.widgets("Tout désélectionner"), self.widgets("Tout sélectionner")
        tout_des[0].invoke()
        self.assertFalse(any(v.get() for v in app.v_familles.values()) or app.v_bspline.get())
        tout_sel[0].invoke()
        self.assertTrue(all(v.get() for v in app.v_familles.values()) and app.v_bspline.get())
        tout_des[1].invoke()
        self.assertFalse(any(v.get() for v in app.v_sorties.values()))
        tout_sel[1].invoke()
        self.assertTrue(all(v.get() for v in app.v_sorties.values()))

    def test_aucune_sortie_refusee(self):
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        self.widgets("Tout désélectionner")[0].invoke()
        self.widgets("Tout désélectionner")[1].invoke()
        app.b_lancer.invoke()
        self.assertIn("Aucune sortie", mb.appels[-1][2])
        self.assertIsNone(app.traitement)


class ParametresEtCommande(FenetreBase):
    def test_validation(self):
        p = L.Parametres()
        self.assertTrue(any("Choisissez un fichier" in e for e in L.valider(p)))
        p.fichier = os.path.join(self.dossier, "absent.stp")
        self.assertTrue(any("n'existe pas" in e for e in L.valider(p)))
        p.fichier = self.piece
        self.assertEqual(L.valider(p), [])
        p.dossier_identique, p.dossier_sortie = False, ""
        self.assertTrue(any("répertoire de sortie" in e for e in L.valider(p)))
        p.dossier_sortie = self.piece                                  # un fichier, pas un dossier
        self.assertTrue(any("est un fichier" in e for e in L.valider(p)))

    def test_commande_par_defaut(self):
        p = L.Parametres()
        p.fichier = self.piece
        cmd = L.construire_commande(p, interpreteur="python", script="CADSurfaceAnalyser.py")
        self.assertEqual(cmd[:3], ["python", "-u", "CADSurfaceAnalyser.py"])
        self.assertEqual(cmd[cmd.index("--precision-numerique") + 1], "standard")
        self.assertIn("--avec-numpy", cmd)
        self.assertEqual(cmd[cmd.index("--familles-step") + 1].split(","), list(L.CLES_FAMILLES))
        self.assertEqual(cmd[cmd.index("--sorties") + 1].split(","), list(L.SORTIES_DISPONIBLES))
        self.assertNotIn("--sans-stp-bspline", cmd)
        self.assertNotIn("--dossier-sortie", cmd)

    def test_commande_personnalisee(self):
        p = L.Parametres()
        p.fichier, p.precision, p.numpy, p.bspline = self.piece, "fine", False, False
        p.familles, p.sorties = [], []
        p.dossier_identique, p.dossier_sortie = False, os.path.join(self.dossier, "x")
        cmd = L.construire_commande(p, interpreteur="python", script="s.py")
        self.assertIn("--sans-numpy", cmd)
        self.assertIn("--sans-stp-bspline", cmd)
        self.assertEqual(cmd[cmd.index("--familles-step") + 1], "aucune")
        self.assertEqual(cmd[cmd.index("--sorties") + 1], "aucune")
        self.assertEqual(cmd[cmd.index("--precision-numerique") + 1], "fine")
        self.assertEqual(cmd[cmd.index("--dossier-sortie") + 1], os.path.abspath(p.dossier_sortie))

    def test_numpy_indisponible(self):
        app, racine, fd, mb = self.nouvelle(numpy_dispo=False)
        self.assertFalse(app.v_numpy.get())
        self.assertEqual(app.k_numpy.opts["state"], "disabled")
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        self.assertFalse(app.lire_parametres().numpy)


class TraitementsReels(FenetreBase):
    def lancer_et_attendre(self, app, racine):
        app.b_lancer.invoke()
        self.assertTrue(app.traitement.en_cours() or app.traitement.proc is not None)
        self.assertTrue(self.boucle(app, racine), "le traitement ne se termine pas")

    def test_selection_partielle_dossier_personnalise(self):
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        self.widget(IDENTIQUE).invoke()
        fd.resultat_dossier = os.path.join(self.dossier, "resultats")
        app.parcourir_dossier()
        for nom in ("Groupe_Coaxial", "Groupe_Parallele", "Groupe_Concentrique",
                    "Groupe_Coplanaire", "Groupe_Geometrique_Identique", "B_SPLINE_SURFACE en violet"):
            self.widget(nom).invoke()
        for cle in ("csv_jonctions", "csv_groupes"):
            self.widget(L.LIBELLES_SORTIES[cle]).invoke()
        app.v_precision.set(L.PRECISIONS[2][1])                         # fine
        app.b_lancer.invoke()
        self.assertTrue(app.traitement.en_cours())
        self.assertEqual(app.b_lancer.opts["state"], "disabled")
        self.assertEqual(app.b_arreter.opts["state"], "normal")
        self.assertTrue(app.progression.actif)
        self.assertTrue(self.boucle(app, racine))
        log = app.texte.contenu
        self.assertTrue(log.startswith("$ python "))
        self.assertIn("--precision-numerique fine", log.splitlines()[0])
        for etape in ("Lecture du fichier STEP", "Analyse des faces et des tangences",
                      "Calcul des caractéristiques des faces", "Calcul des familles de groupes", "TERMINE"):
            self.assertIn(etape, log)
        self.assertEqual(self.sorties(os.path.join(self.dossier, "resultats")), sorted([
            "piece_Groupe_Tangent.stp", "piece_Groupe_Plan.stp", "piece_Groupe_Cylindre.stp",
            "piece_groupes_tangents.json", "piece_faces.csv", "piece_familles.csv"]))
        self.assertEqual(self.sorties(), [])                            # rien à côté du STEP
        self.assertTrue(app.v_statut.get().startswith("Terminé"))
        self.assertEqual(app.b_lancer.opts["state"], "normal")
        self.assertEqual(app.b_arreter.opts["state"], "disabled")
        self.assertFalse(app.progression.actif)
        self.assertEqual(app.b_ouvrir.opts["state"], "normal")
        with open(self.reglages, encoding="utf-8") as f:
            mem = json.load(f)
        self.assertEqual(mem["fichier"], self.piece)
        self.assertEqual(mem["precision"], "fine")
        self.assertEqual(mem["familles"], ["tangent", "plans", "cylindres"])
        self.assertFalse(mem["dossier_identique"])

    def test_relance_reprend_le_dernier_traitement(self):
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        self.widget("Groupe_Coaxial").invoke()
        app.v_precision.set(L.PRECISIONS[0][1])
        self.lancer_et_attendre(app, racine)
        app2, *_ = self.nouvelle()
        self.assertEqual(app2.v_fichier.get(), self.piece)              # dernier fichier traité
        self.assertFalse(app2.v_familles["coaxiales"].get())
        self.assertTrue(app2.v_familles["tangent"].get())
        self.assertEqual(app2.lire_parametres().precision, "rapide")

    def test_log_sans_numpy(self):
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        app.v_numpy.set(False)
        self.lancer_et_attendre(app, racine)
        self.assertIn("--sans-numpy", app.texte.contenu.splitlines()[0])
        # numpy présent mais désactivé, ou numpy absent : dans les deux cas, calcul en Python pur
        self.assertTrue("numpy désactivé" in app.texte.contenu or "numpy non installé" in app.texte.contenu)
        self.assertIn("Python pur", app.texte.contenu)

    def test_erreur_de_traitement(self):
        invalide = os.path.join(self.dossier, "invalide.stp")
        with open(invalide, "w") as f:
            f.write("ceci n'est pas un fichier STEP\n")
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = invalide
        app.parcourir_fichier()
        self.lancer_et_attendre(app, racine)
        self.assertIn("ERREUR", app.texte.contenu)
        self.assertTrue(app.v_statut.get().startswith("Erreur"))
        self.assertEqual(app.b_lancer.opts["state"], "normal")          # la fenêtre reste utilisable

    def test_arret_du_traitement(self):
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        avant = interface.construire_commande
        interface.construire_commande = lambda p: [sys.executable, "-c", "import time; time.sleep(60)"]
        try:
            app.b_lancer.invoke()
            for cb in racine.echeances():
                cb()
            self.assertTrue(app.traitement.en_cours())
            app.b_arreter.invoke()
            debut = time.time()
            self.assertTrue(self.boucle(app, racine, 20))
            self.assertLess(time.time() - debut, 10)
        finally:
            interface.construire_commande = avant
        self.assertEqual(app.v_statut.get(), "Traitement arrêté.")
        self.assertIn("arrêté par l'utilisateur", app.texte.contenu)
        self.assertIsNotNone(app.traitement.proc.poll())                # processus terminé
        self.assertEqual(app.b_lancer.opts["state"], "normal")

    def test_fermeture(self):
        app, racine, fd, mb = self.nouvelle()
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        avant = interface.construire_commande
        interface.construire_commande = lambda p: [sys.executable, "-c", "import time; time.sleep(60)"]
        try:
            app.b_lancer.invoke()
            mb.reponse_oui_non = False
            app.fermer()
            self.assertFalse(racine.detruit)                            # refusée : traitement en cours
            self.assertTrue(app.traitement.en_cours())
            mb.reponse_oui_non = True
            app.fermer()
            self.assertTrue(racine.detruit)
            self.boucle(app, racine, 20)
        finally:
            interface.construire_commande = avant
        self.assertFalse(app.traitement.en_cours())

    def test_fermeture_simple_enregistre_les_reglages(self):
        reg = os.path.join(self.dossier, "autre.json")
        app, racine, fd, mb = self.nouvelle(reglages=reg)
        self.assertFalse(os.path.exists(reg))
        fd.resultat_fichier = self.piece
        app.parcourir_fichier()
        app.v_precision.set(L.PRECISIONS[0][1])
        app.fermer()
        self.assertTrue(racine.detruit)
        with open(reg, encoding="utf-8") as f:
            mem = json.load(f)
        self.assertEqual((mem["fichier"], mem["precision"]), (self.piece, "rapide"))


class ReglagesMemorises(FenetreBase):
    def test_fichier_corrompu_ou_absent(self):
        mauvais = os.path.join(self.dossier, "mauvais.json")
        with open(mauvais, "w") as f:
            f.write("{ ceci n'est pas du json")
        for chemin in (mauvais, os.path.join(self.dossier, "absent.json")):
            p = L.charger_parametres(chemin)
            self.assertEqual((p.precision, p.familles, p.numpy), ("standard", list(L.CLES_FAMILLES), True))

    def test_valeurs_invalides_ignorees(self):
        chemin = os.path.join(self.dossier, "r.json")
        with open(chemin, "w") as f:
            json.dump({"fichier": 12, "precision": "ultra", "familles": ["tangent", "inconnue"],
                       "numpy": "oui", "sorties": ["json", "x"]}, f)
        p = L.charger_parametres(chemin)
        self.assertEqual(p.precision, "standard")
        self.assertEqual(p.familles, ["tangent", "cylindres"])          # + famille récente cochée
        self.assertEqual(p.sorties, ["json"])
        self.assertTrue(p.numpy)
        self.assertEqual(p.fichier, "")

    def test_nouvelles_familles_cochees(self):
        chemin = os.path.join(self.dossier, "r.json")
        with open(chemin, "w") as f:                                    # anciens réglages
            json.dump({"familles": ["tangent", "plans"]}, f)
        self.assertEqual(L.charger_parametres(chemin).familles, ["tangent", "plans", "cylindres"])
        with open(chemin, "w") as f:                                    # famille décochée par l'utilisateur
            json.dump({"familles": ["tangent"], "familles_connues": list(L.CLES_FAMILLES)}, f)
        self.assertEqual(L.charger_parametres(chemin).familles, ["tangent"])
        with open(chemin, "w") as f:                                    # famille apparue depuis
            json.dump({"familles": ["tangent"], "familles_connues": [c for c in L.CLES_FAMILLES if c != "plans"]}, f)
        self.assertEqual(L.charger_parametres(chemin).familles, ["tangent", "plans"])
        self.assertEqual(set(L.Parametres().vers_dict()["familles_connues"]), set(L.CLES_FAMILLES))

    def test_ecriture_impossible_silencieuse(self):
        self.assertFalse(L.enregistrer_parametres(L.Parametres(), os.path.join(self.piece, "x", "r.json")))


class TailleEtAscenseur(FenetreBase):
    @staticmethod
    def dimensions(geometrie):
        dim, x, y = geometrie.split("+") if "+" in geometrie else (geometrie, "0", "0")
        l, h = dim.split("x")
        return int(l), int(h), int(x), int(y)

    def test_taille_selon_l_ecran(self):
        for ecran, dims, minimum in (((2560, 1440), (920, 900), (780, 680)),
                                     ((1366, 768), (920, 628), (780, 628)),
                                     ((800, 600), (720, 460), (720, 460)),
                                     ((300, 200), (420, 360), (420, 360))):
            with self.subTest(ecran=ecran):
                app, racine, *_ = self.nouvelle(ecran=ecran)
                l, h, x, y = self.dimensions(racine.geom)
                self.assertEqual((l, h), dims)
                self.assertEqual(racine.min, minimum)
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)

    def test_structure_du_conteneur_defilant(self):
        app, racine, *_ = self.nouvelle(ecran=(1366, 768))
        self.assertIs(self.widget("1. Fichier STEP à traiter").master, app.contenu)
        self.assertIs(app.contenu.master, app.canvas)
        o = app.ascenseur.opts
        self.assertEqual(o["orient"], "vertical")
        self.assertEqual(o["command"], app.canvas.yview)
        self.assertEqual(app.canvas.opts["yscrollcommand"], app.ascenseur.set)
        self.assertEqual(app.ascenseur.grid_opts["column"], 1)           # à droite
        self.assertEqual(app.canvas.grid_opts["column"], 0)
        self.assertEqual(set(racine.liaisons_globales), {"<MouseWheel>", "<Button-4>", "<Button-5>"})

    def test_ascenseur_visible_seulement_si_necessaire(self):
        app, racine, *_ = self.nouvelle(ecran=(1366, 768))
        app.canvas.larg, app.canvas.haut, app.contenu.req_haut = 920, 628, 860
        app.canvas.declencher("<Configure>")
        fen = app.canvas.fenetres[app._fenetre_canvas]
        self.assertTrue(app.ascenseur.visible and app.defilement_necessaire())
        self.assertEqual((fen["width"], fen["height"]), (920, 860))
        self.assertEqual(app.canvas.opts["scrollregion"], (0, 0, 920, 860))
        compte = []
        original = app.canvas.itemconfigure
        app.canvas.itemconfigure = lambda *a, **k: (compte.append(1), original(*a, **k))[1]
        app._ajuster_defilement()
        app._ajuster_defilement()
        self.assertEqual(compte, [])                                    # pas de boucle de redimensionnement
        app.canvas.itemconfigure = original
        app.canvas.haut = 1000
        app.canvas.declencher("<Configure>")
        self.assertFalse(app.ascenseur.visible)
        self.assertEqual(app.canvas.fenetres[app._fenetre_canvas]["height"], 1000)   # le journal s'étire
        self.assertIn(("moveto", 0), app.canvas.journal)
        app.canvas.haut = 500
        app.canvas.declencher("<Configure>")
        self.assertTrue(app.ascenseur.visible)

    def test_molette(self):
        app, racine, *_ = self.nouvelle(ecran=(1366, 768))
        app.canvas.larg, app.canvas.haut, app.contenu.req_haut = 920, 500, 860
        app.canvas.declencher("<Configure>")
        bouton = app.b_lancer
        for evt, attendu in ((faketk.Evt(bouton, delta=-120), 1), (faketk.Evt(bouton, delta=120), -1),
                             (faketk.Evt(bouton, delta=-240), 2), (faketk.Evt(bouton, delta=-1), 1),
                             (faketk.Evt(bouton, delta=3), -1), (faketk.Evt(bouton, num=4), -1),
                             (faketk.Evt(bouton, num=5), 1)):
            with self.subTest(delta=evt.delta, num=evt.num):
                app.canvas.journal.clear()
                app._roulette(evt)
                self.assertEqual(app.canvas.journal, [("scroll", attendu, "units")])
        app.canvas.journal.clear()
        app._roulette(faketk.Evt(app.texte, delta=-120))                # le journal défile seul
        app._roulette(faketk.Evt(app.c_precision, delta=-120))
        self.assertEqual(app.canvas.journal, [])
        app.canvas.haut = 1000
        app.canvas.declencher("<Configure>")
        app.canvas.journal.clear()
        app._roulette(faketk.Evt(bouton, delta=-120))                   # rien à défiler
        self.assertEqual(app.canvas.journal, [])


if __name__ == "__main__":
    unittest.main()
