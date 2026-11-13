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

"""Interface graphique (tkinter) de CADSurfaceAnalyser.

tkinter est livré avec Python (Windows, macOS). Sous Linux Debian/Ubuntu :
    sudo apt install python3-tk

La fenêtre ne fait que régler les options et afficher le déroulement ; le
calcul est celui de CADSurfaceAnalyser.py, lancé dans un sous-processus (voir
interface_logique.py).
"""

import os
import queue
import sys

from . import accel
from .familles import TOUTES_LES_FAMILLES
from .interface_logique import (
    CLES_FAMILLES,
    FICHIER_REGLAGES,
    LIBELLES_SORTIES,
    PRECISIONS,
    Parametres,
    Traitement,
    charger_parametres,
    commande_affichable,
    construire_commande,
    dossier_effectif,
    enregistrer_parametres,
    lancer_dossier,
    valider,
)
from .options import SORTIES_DISPONIBLES

# Taille souhaitée de la fenêtre ; réduite pour tenir dans l'écran (la page est
# alors défilable grâce à l'ascenseur vertical).
LARGEUR_SOUHAITEE = 920
HAUTEUR_SOUHAITEE = 900
MARGE_ECRAN_LARGEUR = 80        # bordures
MARGE_ECRAN_HAUTEUR = 140       # barre de titre, barre des tâches

_LIBELLE_BSPLINE = "B_SPLINE_SURFACE en violet"
_DEFINITION_BSPLINE = (
    "Pièce complète : faces B_SPLINE_SURFACE en violet, autres faces en gris clair."
)


class Application(object):
    """Fenêtre principale. Les modules tkinter sont passés en paramètres (ce
    qui permet de la tester sans écran)."""

    def __init__(
        self,
        racine,
        tk,
        ttk,
        filedialog,
        messagebox,
        fichier_reglages=FICHIER_REGLAGES,
    ):
        self.racine = racine
        self.tk, self.ttk = tk, ttk
        self.filedialog, self.messagebox = filedialog, messagebox
        self.fichier_reglages = fichier_reglages
        self.traitement = None
        self.file = None
        self.parametres_lances = None
        self._dossier_perso = ""
        self._construire(charger_parametres(fichier_reglages))

    # ------------------------------------------------------------------
    # construction de la fenêtre
    # ------------------------------------------------------------------
    def _construire(self, p):
        tk, ttk, r = self.tk, self.ttk, self.racine
        r.title("CADSurfaceAnalyser - analyse des surfaces d'un fichier STEP")
        self._geometrie_initiale()
        r.protocol("WM_DELETE_WINDOW", self.fermer)

        # Page défilable : un canvas contient tout le contenu ; l'ascenseur
        # vertical, à droite, n'apparaît que si le contenu dépasse la fenêtre.
        r.columnconfigure(0, weight=1)
        r.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(r, highlightthickness=0, borderwidth=0)
        self.ascenseur = ttk.Scrollbar(r, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.ascenseur.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.ascenseur.grid(row=0, column=1, sticky="ns")
        corps = ttk.Frame(self.canvas)
        self.contenu = corps
        self._fenetre_canvas = self.canvas.create_window((0, 0), window=corps, anchor="nw")
        corps.columnconfigure(0, weight=1)
        corps.rowconfigure(6, weight=1)
        self._taille_canvas = None
        self._ascenseur_visible = True
        corps.bind("<Configure>", lambda e: self._ajuster_defilement())
        self.canvas.bind("<Configure>", lambda e: self._ajuster_defilement())
        r.bind_all("<MouseWheel>", self._roulette)       # Windows, macOS
        r.bind_all("<Button-4>", self._roulette)         # Linux : haut
        r.bind_all("<Button-5>", self._roulette)         # Linux : bas

        # variables
        self.v_fichier = tk.StringVar(value=p.fichier)
        self.v_identique = tk.BooleanVar(value=p.dossier_identique)
        self.v_dossier = tk.StringVar(value=p.dossier_sortie)
        self._dossier_perso = p.dossier_sortie
        self.v_familles = {
            c: tk.BooleanVar(value=c in p.familles) for c in CLES_FAMILLES
        }
        self.v_bspline = tk.BooleanVar(value=p.bspline)
        self.v_sorties = {
            c: tk.BooleanVar(value=c in p.sorties) for c in SORTIES_DISPONIBLES
        }
        self._libelles_precision = [lib for _, lib in PRECISIONS]
        self.v_precision = tk.StringVar(value=self._libelle_precision(p.precision))
        self.v_numpy = tk.BooleanVar(value=bool(p.numpy and accel.DISPONIBLE))
        self.v_statut = tk.StringVar(value="Prêt.")

        # 1. fichier STEP
        c1 = ttk.LabelFrame(corps, text="1. Fichier STEP à traiter", padding=8)
        c1.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        c1.columnconfigure(0, weight=1)
        self.e_fichier = ttk.Entry(c1, textvariable=self.v_fichier)
        self.e_fichier.grid(row=0, column=0, sticky="ew")
        ttk.Button(c1, text="Parcourir...", command=self.parcourir_fichier).grid(
            row=0, column=1, padx=(6, 0)
        )

        # 2. STEP par famille de groupes
        c2 = ttk.LabelFrame(
            corps, text="2. Fichiers STEP colorés à écrire (un par groupe de faces)", padding=8
        )
        c2.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        c2.columnconfigure(1, weight=1)
        ligne = 0
        for cle, nom, _, definition in TOUTES_LES_FAMILLES:
            ttk.Checkbutton(c2, text=nom, variable=self.v_familles[cle]).grid(
                row=ligne, column=0, sticky="w", padx=(0, 12)
            )
            ttk.Label(c2, text=definition, foreground="gray").grid(
                row=ligne, column=1, sticky="w"
            )
            ligne += 1
        ttk.Checkbutton(c2, text=_LIBELLE_BSPLINE, variable=self.v_bspline).grid(
            row=ligne, column=0, sticky="w", padx=(0, 12)
        )
        ttk.Label(c2, text=_DEFINITION_BSPLINE, foreground="gray").grid(
            row=ligne, column=1, sticky="w"
        )
        boutons2 = ttk.Frame(c2)
        boutons2.grid(row=ligne + 1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(
            boutons2, text="Tout sélectionner", command=lambda: self.cocher_step(True)
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(
            boutons2, text="Tout désélectionner", command=lambda: self.cocher_step(False)
        ).grid(row=0, column=1)

        # 3. CSV et JSON
        c3 = ttk.LabelFrame(corps, text="3. Sorties CSV et JSON", padding=8)
        c3.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        for i, cle in enumerate(SORTIES_DISPONIBLES):
            ttk.Checkbutton(c3, text=LIBELLES_SORTIES[cle], variable=self.v_sorties[cle]).grid(
                row=i, column=0, sticky="w"
            )
        boutons3 = ttk.Frame(c3)
        boutons3.grid(row=len(SORTIES_DISPONIBLES), column=0, sticky="w", pady=(6, 0))
        ttk.Button(
            boutons3, text="Tout sélectionner", command=lambda: self.cocher_sorties(True)
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(
            boutons3, text="Tout désélectionner", command=lambda: self.cocher_sorties(False)
        ).grid(row=0, column=1)

        # 4. répertoire de sortie
        c4 = ttk.LabelFrame(corps, text="4. Répertoire de sortie", padding=8)
        c4.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        c4.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            c4,
            text="Identique au dossier du fichier STEP d'entrée",
            variable=self.v_identique,
            command=self._maj_dossier,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.e_dossier = ttk.Entry(c4, textvariable=self.v_dossier)
        self.e_dossier.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.b_dossier = ttk.Button(c4, text="Parcourir...", command=self.parcourir_dossier)
        self.b_dossier.grid(row=1, column=1, padx=(6, 0), pady=(4, 0))

        # 5. calcul
        c5 = ttk.LabelFrame(corps, text="5. Calcul", padding=8)
        c5.grid(row=4, column=0, sticky="ew", padx=10, pady=4)
        c5.columnconfigure(1, weight=1)
        ttk.Label(c5, text="Précision numérique :").grid(row=0, column=0, sticky="w")
        self.c_precision = ttk.Combobox(
            c5,
            textvariable=self.v_precision,
            values=self._libelles_precision,
            state="readonly",
            width=62,
        )
        self.c_precision.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.k_numpy = ttk.Checkbutton(
            c5, text="Utiliser numpy (accélère fortement le calcul)", variable=self.v_numpy
        )
        self.k_numpy.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        if not accel.DISPONIBLE:
            self.k_numpy.configure(state="disabled")
            ttk.Label(
                c5,
                text="numpy n'est pas installé : calcul en Python pur (plus lent).",
                foreground="gray",
            ).grid(row=2, column=0, columnspan=2, sticky="w")

        # commandes
        c6 = ttk.Frame(corps)
        c6.grid(row=5, column=0, sticky="ew", padx=10, pady=(6, 2))
        c6.columnconfigure(4, weight=1)
        self.b_lancer = ttk.Button(c6, text="Lancer le traitement", command=self.lancer)
        self.b_lancer.grid(row=0, column=0, padx=(0, 6))
        self.b_arreter = ttk.Button(c6, text="Arrêter", command=self.arreter)
        self.b_arreter.grid(row=0, column=1, padx=(0, 6))
        self.b_arreter.configure(state="disabled")
        self.b_ouvrir = ttk.Button(
            c6, text="Ouvrir le dossier de sortie", command=self.ouvrir_dossier
        )
        self.b_ouvrir.grid(row=0, column=2, padx=(0, 6))
        self.b_ouvrir.configure(state="disabled")
        ttk.Button(c6, text="Quitter", command=self.fermer).grid(row=0, column=3)
        self.progression = ttk.Progressbar(c6, mode="indeterminate", length=160)
        self.progression.grid(row=0, column=5, sticky="e")
        ttk.Label(c6, textvariable=self.v_statut).grid(
            row=1, column=0, columnspan=6, sticky="w", pady=(4, 0)
        )

        # journal
        c7 = ttk.LabelFrame(corps, text="Déroulement du traitement", padding=6)
        c7.grid(row=6, column=0, sticky="nsew", padx=10, pady=(4, 10))
        c7.columnconfigure(0, weight=1)
        c7.rowconfigure(0, weight=1)
        self.texte = tk.Text(c7, wrap="none", height=12, state="disabled", font="TkFixedFont")
        self.texte.grid(row=0, column=0, sticky="nsew")
        ascenseur_y = ttk.Scrollbar(c7, orient="vertical", command=self.texte.yview)
        ascenseur_y.grid(row=0, column=1, sticky="ns")
        ascenseur_x = ttk.Scrollbar(c7, orient="horizontal", command=self.texte.xview)
        ascenseur_x.grid(row=1, column=0, sticky="ew")
        self.texte.configure(
            yscrollcommand=ascenseur_y.set, xscrollcommand=ascenseur_x.set
        )

        self.v_fichier.trace_add("write", lambda *a: self._maj_dossier_affiche())
        self._maj_dossier()

    # ------------------------------------------------------------------
    # utilitaires
    # ------------------------------------------------------------------
    def _geometrie_initiale(self):
        """Taille et position de départ : celles souhaitées, réduites pour
        tenir dans l'écran, fenêtre centrée."""
        r = self.racine
        ecran_l, ecran_h = r.winfo_screenwidth(), r.winfo_screenheight()
        largeur = max(420, min(LARGEUR_SOUHAITEE, ecran_l - MARGE_ECRAN_LARGEUR))
        hauteur = max(360, min(HAUTEUR_SOUHAITEE, ecran_h - MARGE_ECRAN_HAUTEUR))
        x = max(0, (ecran_l - largeur) // 2)
        y = max(0, (ecran_h - hauteur) // 2 - 30)
        r.geometry("%dx%d+%d+%d" % (largeur, hauteur, x, y))
        r.minsize(min(780, largeur), min(680, hauteur))

    def defilement_necessaire(self):
        """Vrai si le contenu est plus haut que la zone visible."""
        return self.contenu.winfo_reqheight() > self.canvas.winfo_height()

    def _ajuster_defilement(self):
        """Adapte le contenu au canvas et affiche l'ascenseur seulement si le
        contenu dépasse la fenêtre."""
        largeur = self.canvas.winfo_width()
        hauteur = self.canvas.winfo_height()
        requis = self.contenu.winfo_reqheight()
        haut_contenu = max(requis, hauteur)     # le journal occupe la place libre
        if (largeur, hauteur, requis) != self._taille_canvas:
            self._taille_canvas = (largeur, hauteur, requis)
            self.canvas.itemconfigure(self._fenetre_canvas, width=largeur, height=haut_contenu)
            self.canvas.configure(scrollregion=(0, 0, largeur, haut_contenu))
        necessaire = requis > hauteur
        if necessaire and not self._ascenseur_visible:
            self.ascenseur.grid()
            self._ascenseur_visible = True
        elif not necessaire and self._ascenseur_visible:
            self.ascenseur.grid_remove()
            self._ascenseur_visible = False
            self.canvas.yview_moveto(0)

    def _roulette(self, evenement):
        """Molette de la souris : fait défiler la page (sauf sur le journal,
        qui défile seul, et sur la liste de précision)."""
        if not self.defilement_necessaire():
            return
        if evenement.widget in (self.texte, self.c_precision):
            return
        if evenement.num == 4:
            pas = -1
        elif evenement.num == 5:
            pas = 1
        else:
            delta = evenement.delta
            pas = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        self.canvas.yview_scroll(pas, "units")

    def _libelle_precision(self, cle):
        for c, libelle in PRECISIONS:
            if c == cle:
                return libelle
        return PRECISIONS[1][1]

    def _cle_precision(self, texte):
        for c, libelle in PRECISIONS:
            if texte == libelle or texte.startswith(c):
                return c
        return "standard"

    def _dossier_du_fichier(self):
        f = self.v_fichier.get().strip()
        return os.path.dirname(os.path.abspath(f)) if f else ""

    def _maj_dossier_affiche(self):
        if self.v_identique.get():
            self.v_dossier.set(self._dossier_du_fichier())

    def _maj_dossier(self):
        """Dossier de sortie : identique au STEP (champ grisé) ou personnalisé."""
        if self.v_identique.get():
            actuel = self.v_dossier.get().strip()
            if actuel and actuel != self._dossier_du_fichier():
                self._dossier_perso = actuel
            self.v_dossier.set(self._dossier_du_fichier())
            self.e_dossier.configure(state="disabled")
            self.b_dossier.configure(state="disabled")
        else:
            self.e_dossier.configure(state="normal")
            self.b_dossier.configure(state="normal")
            self.v_dossier.set(self._dossier_perso or self._dossier_du_fichier())

    def cocher_step(self, valeur):
        for v in self.v_familles.values():
            v.set(valeur)
        self.v_bspline.set(valeur)

    def cocher_sorties(self, valeur):
        for v in self.v_sorties.values():
            v.set(valeur)

    def lire_parametres(self):
        """Réglages actuellement affichés dans la fenêtre."""
        p = Parametres()
        p.fichier = self.v_fichier.get().strip()
        p.dossier_identique = bool(self.v_identique.get())
        p.dossier_sortie = (
            self._dossier_perso if p.dossier_identique else self.v_dossier.get().strip()
        )
        p.familles = [c for c in CLES_FAMILLES if self.v_familles[c].get()]
        p.bspline = bool(self.v_bspline.get())
        p.sorties = [c for c in SORTIES_DISPONIBLES if self.v_sorties[c].get()]
        p.precision = self._cle_precision(self.v_precision.get())
        p.numpy = bool(self.v_numpy.get() and accel.DISPONIBLE)
        return p

    def ajouter_texte(self, texte):
        self.texte.configure(state="normal")
        self.texte.insert("end", texte)
        self.texte.see("end")
        self.texte.configure(state="disabled")

    def vider_journal(self):
        self.texte.configure(state="normal")
        self.texte.delete("1.0", "end")
        self.texte.configure(state="disabled")

    def _etat_en_cours(self, en_cours):
        self.b_lancer.configure(state="disabled" if en_cours else "normal")
        self.b_arreter.configure(state="normal" if en_cours else "disabled")
        if en_cours:
            self.b_ouvrir.configure(state="disabled")
            self.progression.start(12)
        else:
            self.progression.stop()

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def parcourir_fichier(self):
        courant = self.v_fichier.get().strip()
        depart = os.path.dirname(os.path.abspath(courant)) if courant else os.path.expanduser("~")
        choix = self.filedialog.askopenfilename(
            title="Choisir le fichier STEP à traiter",
            initialdir=depart if os.path.isdir(depart) else os.path.expanduser("~"),
            filetypes=[
                ("Fichiers STEP", "*.stp *.step *.STP *.STEP *.p21"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if choix:
            self.v_fichier.set(choix)

    def parcourir_dossier(self):
        courant = self.v_dossier.get().strip()
        depart = courant if courant and os.path.isdir(courant) else self._dossier_du_fichier()
        choix = self.filedialog.askdirectory(
            title="Choisir le répertoire de sortie",
            initialdir=depart if depart and os.path.isdir(depart) else os.path.expanduser("~"),
        )
        if choix:
            self._dossier_perso = choix
            self.v_dossier.set(choix)

    def lancer(self):
        if self.traitement is not None and self.traitement.en_cours():
            return
        p = self.lire_parametres()
        erreurs = valider(p)
        if erreurs:
            self.messagebox.showerror("Réglages incomplets", "\n\n".join(erreurs))
            return
        enregistrer_parametres(p, self.fichier_reglages)       # dernier fichier traité
        commande = construire_commande(p)
        self.parametres_lances = p
        self.vider_journal()
        self.ajouter_texte("$ %s\n\n" % commande_affichable(commande))
        self.file = queue.Queue()
        self.traitement = Traitement(commande, self.file)
        try:
            self.traitement.demarrer()
        except OSError as erreur:
            self.messagebox.showerror("Lancement impossible", str(erreur))
            return
        self._etat_en_cours(True)
        self.v_statut.set("Traitement en cours...")
        self.racine.after(100, self._interroger)

    def arreter(self):
        if self.traitement is not None and self.traitement.en_cours():
            self.v_statut.set("Arrêt en cours...")
            self.traitement.arreter()

    def _interroger(self):
        """Affiche la sortie du calcul au fur et à mesure (toutes les 100 ms)."""
        morceaux, fin = [], None
        try:
            while True:
                genre, donnee = self.file.get_nowait()
                if genre == "texte":
                    morceaux.append(donnee)
                else:
                    fin = donnee
        except queue.Empty:
            pass
        if morceaux:
            self.ajouter_texte("".join(morceaux))
        if fin is None:
            self.racine.after(100, self._interroger)
        else:
            self._terminer(fin)

    def _terminer(self, info):
        self._etat_en_cours(False)
        if info["arrete"]:
            self.ajouter_texte("\n--- Traitement arrêté par l'utilisateur ---\n")
            self.v_statut.set("Traitement arrêté.")
        elif info["code"] == 0:
            self.v_statut.set("Terminé en %.1f s." % info["duree"])
            dossier = dossier_effectif(self.parametres_lances)
            if dossier and os.path.isdir(dossier):
                self.b_ouvrir.configure(state="normal")
        else:
            self.v_statut.set(
                "Erreur (code %s) : voir le déroulement ci-dessus." % info["code"]
            )

    def ouvrir_dossier(self):
        if self.parametres_lances is None:
            return
        dossier = dossier_effectif(self.parametres_lances)
        if dossier and os.path.isdir(dossier):
            try:
                lancer_dossier(dossier)
            except OSError as erreur:
                self.messagebox.showerror("Ouverture impossible", str(erreur))

    def fermer(self):
        if self.traitement is not None and self.traitement.en_cours():
            if not self.messagebox.askyesno(
                "Quitter", "Un traitement est en cours. L'arrêter et quitter ?"
            ):
                return
            self.traitement.arreter()
        enregistrer_parametres(self.lire_parametres(), self.fichier_reglages)
        self.racine.destroy()


def lancer_interface():
    """Ouvre la fenêtre. Retourne 1 si tkinter n'est pas disponible."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print(
            "tkinter n'est pas installé : l'interface graphique est indisponible.\n"
            "  Windows / macOS : réinstaller Python avec l'option « tcl/tk ».\n"
            "  Linux (Debian, Ubuntu) : sudo apt install python3-tk\n"
            "La ligne de commande reste utilisable : python CADSurfaceAnalyser.py"
        )
        return 1
    racine = tk.Tk()
    Application(racine, tk, ttk, filedialog, messagebox)
    racine.mainloop()
    return 0
