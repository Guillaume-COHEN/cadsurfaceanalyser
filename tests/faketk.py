# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Faux tkinter pour tester l'interface sans écran.

Reproduit le sous-ensemble d'API utilisé par cadsurf/interface.py et REFUSE les
options inconnues (comme le vrai Tk lève TclError), pour attraper les fautes
de frappe. Simule la boucle `after`, les clics, la taille de l'écran et celle
des widgets. Ne remplace pas un essai sur un vrai écran (apparence, polices).
"""
import re
from types import SimpleNamespace


class TclError(Exception):
    pass


OPTIONS = {
    "Frame": {"padding", "relief", "borderwidth", "width", "height", "style", "class", "cursor", "takefocus"},
    "LabelFrame": {"text", "padding", "labelanchor", "labelwidget", "relief", "borderwidth", "width", "height", "style", "underline", "class", "cursor", "takefocus"},
    "Label": {"text", "textvariable", "foreground", "background", "font", "anchor", "justify", "wraplength", "padding", "image", "compound", "relief", "width", "style", "state", "underline", "takefocus", "cursor", "borderwidth"},
    "Entry": {"textvariable", "width", "state", "show", "justify", "font", "exportselection", "validate", "validatecommand", "invalidcommand", "style", "takefocus", "cursor", "xscrollcommand", "foreground", "background"},
    "Button": {"text", "command", "state", "width", "style", "image", "compound", "takefocus", "cursor", "default", "underline", "padding", "textvariable"},
    "Checkbutton": {"text", "variable", "command", "state", "onvalue", "offvalue", "width", "style", "image", "compound", "takefocus", "cursor", "underline", "padding", "textvariable"},
    "Combobox": {"textvariable", "values", "state", "width", "height", "postcommand", "justify", "font", "exportselection", "style", "takefocus", "cursor", "foreground", "background", "validate", "xscrollcommand"},
    "Progressbar": {"mode", "length", "orient", "maximum", "value", "variable", "style", "phase", "takefocus", "cursor"},
    "Scrollbar": {"orient", "command", "style", "takefocus", "cursor"},
    "Text": {"wrap", "height", "width", "state", "font", "yscrollcommand", "xscrollcommand", "bg", "fg", "background", "foreground", "padx", "pady", "relief", "borderwidth", "highlightthickness", "undo", "takefocus", "cursor"},
    "Canvas": {"highlightthickness", "borderwidth", "yscrollcommand", "xscrollcommand", "scrollregion", "width", "height", "background", "bg", "cursor", "relief", "takefocus", "confine", "yscrollincrement"},
}
GRID = {"row", "column", "sticky", "padx", "pady", "columnspan", "rowspan", "ipadx", "ipady", "in_"}
SEQUENCES = {"<Configure>", "<MouseWheel>", "<Button-4>", "<Button-5>"}


class Variable(object):
    defaut = ""

    def __init__(self, master=None, value=None, name=None):
        self._v = self.defaut if value is None else value
        self._traces = []

    def get(self):
        return self._v

    def set(self, v):
        self._v = v
        for cb in list(self._traces):
            cb("var", "", "write")

    def trace_add(self, mode, cb):
        if mode not in ("write", "read", "unset", "array"):
            raise TclError("mode de trace invalide : %r" % mode)
        self._traces.append(cb)
        return "trace%d" % len(self._traces)


class StringVar(Variable):
    defaut = ""


class BooleanVar(Variable):
    defaut = False


class Widget(object):
    classe = "Frame"
    toutes = []

    def __init__(self, master=None, **kw):
        self.master = master
        self.opts = {}
        self.grid_opts = None
        self.visible = False             # placé par grid() et non retiré
        self.liaisons = {}
        self.larg, self.haut = 1, 1      # winfo_width / winfo_height simulés
        self.req_larg, self.req_haut = 1, 1
        self._controler(kw)
        self.opts.update(kw)
        self.opts.setdefault("state", "normal")
        Widget.toutes.append(self)

    def _controler(self, kw):
        valides = OPTIONS[self.classe]
        for k in kw:
            if k not in valides:
                raise TclError('unknown option "-%s" pour %s' % (k, self.classe))

    def configure(self, **kw):
        self._controler(kw)
        self.opts.update(kw)

    config = configure

    def cget(self, k):
        return self.opts[k]

    def grid(self, **kw):
        for k in kw:
            if k not in GRID:
                raise TclError('option grid inconnue "-%s"' % k)
        if kw or self.grid_opts is None:
            self.grid_opts = kw
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def bind(self, sequence, fonction):
        if sequence not in SEQUENCES:
            raise TclError("séquence inconnue : %r" % sequence)
        self.liaisons[sequence] = fonction
        return "bind"

    def declencher(self, sequence, evenement=None):
        if sequence in self.liaisons:
            self.liaisons[sequence](evenement)

    def winfo_width(self):
        return self.larg

    def winfo_height(self):
        return self.haut

    def winfo_reqwidth(self):
        return self.req_larg

    def winfo_reqheight(self):
        return self.req_haut

    def columnconfigure(self, i, **kw):
        pass

    def rowconfigure(self, i, **kw):
        pass

    def invoke(self):
        if self.opts.get("state") == "disabled":
            return
        cmd = self.opts.get("command")
        if cmd:
            cmd()


class Frame(Widget):
    classe = "Frame"


class LabelFrame(Widget):
    classe = "LabelFrame"


class Label(Widget):
    classe = "Label"


class Entry(Widget):
    classe = "Entry"


class Button(Widget):
    classe = "Button"


class Checkbutton(Widget):
    classe = "Checkbutton"

    def invoke(self):
        if self.opts.get("state") == "disabled":
            return
        v = self.opts.get("variable")
        if v is not None:
            v.set(not v.get())
        cmd = self.opts.get("command")
        if cmd:
            cmd()


class Combobox(Widget):
    classe = "Combobox"


class Progressbar(Widget):
    classe = "Progressbar"

    def __init__(self, master=None, **kw):
        Widget.__init__(self, master, **kw)
        self.actif = False

    def start(self, interval=50):
        self.actif = True

    def stop(self):
        self.actif = False


class Scrollbar(Widget):
    classe = "Scrollbar"

    def set(self, a, b):
        pass


class Canvas(Widget):
    classe = "Canvas"

    def __init__(self, master=None, **kw):
        Widget.__init__(self, master, **kw)
        self.fenetres = {}
        self.journal = []                       # appels de défilement
        self.position = 0.0

    def create_window(self, position, **kw):
        for k in kw:
            if k not in ("window", "anchor", "width", "height", "tags", "state"):
                raise TclError('option create_window inconnue "-%s"' % k)
        ident = len(self.fenetres) + 1
        self.fenetres[ident] = dict(kw)
        return ident

    def itemconfigure(self, ident, **kw):
        for k in kw:
            if k not in ("window", "anchor", "width", "height", "tags", "state"):
                raise TclError('option itemconfigure inconnue "-%s"' % k)
        self.fenetres[ident].update(kw)

    def bbox(self, *a):
        return (0, 0, self.larg, self.haut)

    def yview(self, *a):
        self.journal.append(("yview",) + a)

    def yview_moveto(self, f):
        self.position = f
        self.journal.append(("moveto", f))

    def yview_scroll(self, n, quoi):
        if quoi not in ("units", "pages"):
            raise TclError("unité invalide : %r" % quoi)
        self.journal.append(("scroll", n, quoi))


class Text(Widget):
    classe = "Text"

    def __init__(self, master=None, **kw):
        Widget.__init__(self, master, **kw)
        self.contenu = ""

    def _ecriture(self):
        if self.opts.get("state") == "disabled":
            raise TclError("le widget Text est désactivé : insertion refusée")

    def insert(self, index, texte, *tags):
        self._ecriture()
        self.contenu += texte

    def delete(self, debut, fin=None):
        self._ecriture()
        self.contenu = ""

    def see(self, index):
        pass

    def yview(self, *a):
        pass

    def xview(self, *a):
        pass

    def get(self, debut, fin=None):
        return self.contenu


class Tk(Widget):
    classe = "Frame"

    def __init__(self):
        Widget.__init__(self, None)
        self.titre = ""
        self.geom = None
        self.min = None
        self.afters = []
        self.protocoles = {}
        self.liaisons_globales = {}
        self.detruit = False
        self.ecran = (1920, 1080)

    def title(self, t):
        self.titre = t

    def geometry(self, g):
        if not re.match(r"^\d+x\d+(\+\d+\+\d+)?$", g):
            raise TclError("géométrie invalide : %r" % g)
        self.geom = g

    def minsize(self, w, h):
        self.min = (w, h)

    def protocol(self, nom, cmd):
        self.protocoles[nom] = cmd

    def winfo_screenwidth(self):
        return self.ecran[0]

    def winfo_screenheight(self):
        return self.ecran[1]

    def bind_all(self, sequence, fonction):
        if sequence not in SEQUENCES:
            raise TclError("séquence inconnue : %r" % sequence)
        self.liaisons_globales[sequence] = fonction
        return "bindall"

    def after(self, ms, fn=None, *args):
        self.afters.append(fn)
        return "after%d" % len(self.afters)

    def mainloop(self):
        pass

    def destroy(self):
        self.detruit = True

    def echeances(self):
        a, self.afters = self.afters, []
        return a


class FileDialog(object):
    def __init__(self):
        self.resultat_fichier = ""
        self.resultat_dossier = ""
        self.appels = []

    def askopenfilename(self, **kw):
        for k in kw:
            assert k in ("title", "initialdir", "filetypes", "parent", "defaultextension", "initialfile"), k
        self.appels.append(("fichier", kw))
        return self.resultat_fichier

    def askdirectory(self, **kw):
        for k in kw:
            assert k in ("title", "initialdir", "parent", "mustexist"), k
        self.appels.append(("dossier", kw))
        return self.resultat_dossier


class MessageBox(object):
    def __init__(self):
        self.appels = []
        self.reponse_oui_non = True

    def showerror(self, titre, message, **kw):
        self.appels.append(("erreur", titre, message))

    def showwarning(self, titre, message, **kw):
        self.appels.append(("avertissement", titre, message))

    def askyesno(self, titre, message, **kw):
        self.appels.append(("question", titre, message))
        return self.reponse_oui_non


def creer(ecran=(1920, 1080)):
    """(tk, ttk, filedialog, messagebox) factices ; `ecran` = taille simulée."""
    Widget.toutes = []
    taille = ecran

    class TkEcran(Tk):
        def __init__(self):
            Tk.__init__(self)
            self.ecran = taille

    tk = SimpleNamespace(Tk=TkEcran, StringVar=StringVar, BooleanVar=BooleanVar, Text=Text, Canvas=Canvas, TclError=TclError)
    ttk = SimpleNamespace(Frame=Frame, LabelFrame=LabelFrame, Label=Label, Entry=Entry, Button=Button,
                          Checkbutton=Checkbutton, Combobox=Combobox, Progressbar=Progressbar, Scrollbar=Scrollbar)
    return tk, ttk, FileDialog(), MessageBox()


class Evt(object):
    """Événement souris simulé."""
    def __init__(self, widget, delta=0, num="??"):
        self.widget, self.delta, self.num = widget, delta, num
