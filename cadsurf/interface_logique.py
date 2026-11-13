# Copyright 2026 The CADSurfaceAnalyser authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Logique de l'interface graphique, indépendante de tkinter (donc testable).

L'interface ne recalcule rien : elle construit une ligne de commande pour
CADSurfaceAnalyser.py, la lance dans un sous-processus et affiche sa sortie en
direct, exactement comme dans un terminal. Avantages : même résultat que la
ligne de commande, fenêtre toujours réactive, bouton « Arrêter » fiable, et un
éventuel plantage du calcul ne ferme pas la fenêtre.
"""

import json
import os
import queue
import shlex
import signal
import subprocess
import sys
import threading
import time

from .familles import TOUTES_LES_FAMILLES
from .options import SORTIES_DISPONIBLES

CLES_FAMILLES = tuple(c for c, _, _, _ in TOUTES_LES_FAMILLES)

# Familles apparues après la première version du fichier de réglages (qui ne
# mémorisait pas la liste des familles connues) : pour d'anciens réglages, elles
# sont considérées comme nouvelles, donc cochées par défaut.
FAMILLES_RECENTES = ("cylindres",)

PRECISIONS = (
    ("rapide", "rapide : erreur sur l'aire ~4e-6, le plus rapide"),
    ("standard", "standard : erreur ~1e-6 (par défaut)"),
    ("fine", "fine : erreur ~2e-9 (avec numpy, environ 35 % plus lent)"),
)

LIBELLES_SORTIES = {
    "json": "JSON (faces, familles, arêtes, résumé)",
    "csv_faces": "CSV des faces (une ligne par face)",
    "csv_familles": "CSV des familles de groupes (une ligne par groupe)",
    "csv_groupes": "CSV des groupes tangents (barycentre, boîte englobante)",
    "csv_jonctions": "CSV des jonctions entre faces",
}

FICHIER_REGLAGES = os.path.join(
    os.path.expanduser("~"), ".cadsurfaceanalyser_gui.json"
)
DOSSIER_PROGRAMME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# REGLAGES
# ============================================================================

class Parametres(object):
    """Ce que l'utilisateur règle dans la fenêtre (valeurs par défaut incluses)."""

    def __init__(self):
        self.fichier = ""                          # dernier fichier traité
        self.dossier_identique = True              # sortie = dossier du STEP
        self.dossier_sortie = ""
        self.familles = list(CLES_FAMILLES)        # tous les groupes cochés
        self.bspline = True                        # STEP B-spline en violet
        self.sorties = list(SORTIES_DISPONIBLES)   # tout JSON / CSV coché
        self.precision = "standard"
        self.numpy = True

    def vers_dict(self):
        d = dict(self.__dict__)
        d["familles"] = list(self.familles)
        d["sorties"] = list(self.sorties)
        d["familles_connues"] = list(CLES_FAMILLES)   # pour cocher les futures familles
        return d

    @classmethod
    def depuis_dict(cls, d):
        """Réglages relus d'un fichier : toute valeur invalide est ignorée."""
        p = cls()
        if not isinstance(d, dict):
            return p
        if isinstance(d.get("fichier"), str):
            p.fichier = d["fichier"]
        if isinstance(d.get("dossier_identique"), bool):
            p.dossier_identique = d["dossier_identique"]
        if isinstance(d.get("dossier_sortie"), str):
            p.dossier_sortie = d["dossier_sortie"]
        if isinstance(d.get("familles"), list):
            connues = d.get("familles_connues")
            if not isinstance(connues, list):
                connues = [c for c in CLES_FAMILLES if c not in FAMILLES_RECENTES]
            nouvelles = [c for c in CLES_FAMILLES if c not in connues]
            p.familles = [
                c for c in CLES_FAMILLES if c in d["familles"] or c in nouvelles
            ]
        if isinstance(d.get("bspline"), bool):
            p.bspline = d["bspline"]
        if isinstance(d.get("sorties"), list):
            p.sorties = [c for c in SORTIES_DISPONIBLES if c in d["sorties"]]
        if d.get("precision") in [c for c, _ in PRECISIONS]:
            p.precision = d["precision"]
        if isinstance(d.get("numpy"), bool):
            p.numpy = d["numpy"]
        return p


def charger_parametres(chemin=None):
    """Réglages mémorisés (ou valeurs par défaut s'il n'y en a pas)."""
    try:
        with open(chemin or FICHIER_REGLAGES, encoding="utf-8") as f:
            return Parametres.depuis_dict(json.load(f))
    except (OSError, ValueError):
        return Parametres()


def enregistrer_parametres(p, chemin=None):
    """Mémorise les réglages (dernier fichier traité compris). Silencieux en
    cas d'impossibilité d'écrire."""
    try:
        with open(chemin or FICHIER_REGLAGES, "w", encoding="utf-8") as f:
            json.dump(p.vers_dict(), f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def dossier_effectif(p):
    """Dossier où seront écrits les fichiers."""
    if p.dossier_identique:
        return os.path.dirname(os.path.abspath(p.fichier)) if p.fichier else ""
    return p.dossier_sortie


def valider(p):
    """Liste des problèmes empêchant le lancement (vide si tout va bien)."""
    erreurs = []
    if not p.fichier.strip():
        erreurs.append("Choisissez un fichier STEP à traiter.")
    elif not os.path.isfile(p.fichier):
        erreurs.append("Le fichier STEP n'existe pas :\n%s" % p.fichier)
    if not p.dossier_identique:
        if not p.dossier_sortie.strip():
            erreurs.append("Choisissez un répertoire de sortie.")
        elif os.path.isfile(p.dossier_sortie):
            erreurs.append("Le répertoire de sortie est un fichier :\n%s" % p.dossier_sortie)
    if not p.familles and not p.bspline and not p.sorties:
        erreurs.append("Aucune sortie n'est sélectionnée.")
    return erreurs


# ============================================================================
# COMMANDE
# ============================================================================

def interpreteur_console():
    """Interpréteur Python à lancer. Sous Windows, pythonw.exe (sans console)
    est remplacé par python.exe pour que la sortie texte soit disponible."""
    exe = sys.executable
    if os.name == "nt" and os.path.basename(exe).lower() == "pythonw.exe":
        candidat = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(candidat):
            return candidat
    return exe


def construire_commande(p, interpreteur=None, script=None):
    """Commande équivalente aux réglages (liste d'arguments)."""
    script = script or os.path.join(DOSSIER_PROGRAMME, "CADSurfaceAnalyser.py")
    familles = [c for c in CLES_FAMILLES if c in p.familles]
    sorties = [c for c in SORTIES_DISPONIBLES if c in p.sorties]
    cmd = [
        interpreteur or interpreteur_console(),
        "-u",
        script,
        os.path.abspath(p.fichier),
        "--precision-numerique", p.precision,
        "--avec-numpy" if p.numpy else "--sans-numpy",
        "--familles-step", ",".join(familles) if familles else "aucune",
        "--sorties", ",".join(sorties) if sorties else "aucune",
    ]
    if not p.bspline:
        cmd.append("--sans-stp-bspline")
    if not p.dossier_identique:
        cmd += ["--dossier-sortie", os.path.abspath(p.dossier_sortie)]
    return cmd


def commande_affichable(cmd):
    """Commande lisible pour le journal (sans l'option -u)."""
    cmd = [c for c in cmd if c != "-u"]
    cmd[0] = "python"
    if os.name == "nt":
        return subprocess.list2cmdline(cmd)
    return " ".join(shlex.quote(c) for c in cmd)


# ============================================================================
# EXECUTION
# ============================================================================

class Traitement(object):
    """Lance la commande dans un sous-processus et envoie sa sortie, ligne par
    ligne, dans une file : ("texte", ligne) puis, à la fin,
    ("fin", {"code", "duree", "arrete"})."""

    def __init__(self, commande, file, cwd=None):
        self.commande = commande
        self.file = file
        self.cwd = cwd or DOSSIER_PROGRAMME
        self.proc = None
        self.debut = None
        self._arrete = False

    def demarrer(self):
        env = dict(os.environ)
        env.update(PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", PYTHONUTF8="1")
        options = dict(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=self.cwd,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True      # pour pouvoir tout arrêter
        self.debut = time.time()
        self.proc = subprocess.Popen(self.commande, **options)
        threading.Thread(target=self._lire, daemon=True).start()

    def _lire(self):
        try:
            for ligne in self.proc.stdout:
                self.file.put(("texte", ligne))
        finally:
            code = self.proc.wait()
            try:
                self.proc.stdout.close()          # libère le tube (sinon fuite à chaque traitement)
            except Exception:
                pass
            self.file.put((
                "fin",
                {"code": code, "duree": time.time() - self.debut, "arrete": self._arrete},
            ))

    def en_cours(self):
        return self.proc is not None and self.proc.poll() is None

    def arreter(self):
        """Arrête le traitement et tous ses processus de calcul."""
        self._arrete = True
        if not self.en_cours():
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            try:
                self.proc.terminate()
            except Exception:
                pass


def lancer_dossier(chemin):
    """Ouvre un dossier dans l'explorateur de fichiers du système."""
    if os.name == "nt":
        os.startfile(chemin)                                  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", chemin])
    else:
        subprocess.Popen(["xdg-open", chemin])
