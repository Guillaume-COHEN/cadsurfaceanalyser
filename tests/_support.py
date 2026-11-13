# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Outils communs aux tests.

* chemins et simulation d'absence de numpy (CADSURF_TEST_SANS_NUMPY=1) ;
* constructeur de fichiers STEP synthétiques dont la géométrie est connue
  exactement (aires et barycentres calculables à la main) ;
* lecture des couleurs réellement écrites dans un STEP ;
* analyse d'un fichier sans passer par la ligne de commande.
"""

import contextlib
import importlib.util
import io
import math
import os
import subprocess
import sys
from types import SimpleNamespace

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

SANS_NUMPY = os.environ.get("CADSURF_TEST_SANS_NUMPY") == "1"
DOSSIER_SANS_NUMPY = os.path.join(DOSSIER_TESTS, "_sans_numpy")
if SANS_NUMPY:
    _spec = importlib.util.spec_from_file_location(
        "_bloc_numpy", os.path.join(DOSSIER_SANS_NUMPY, "sitecustomize.py")
    )
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"       # sorties des sous-processus lisibles sous Windows
os.environ["PYTHONUTF8"] = "1"
if SANS_NUMPY:                      # hérité par tous les sous-processus (dont ceux de l'interface)
    os.environ["PYTHONPATH"] = DOSSIER_SANS_NUMPY + os.pathsep + os.environ.get("PYTHONPATH", "")

SCRIPT = os.path.join(RACINE, "CADSurfaceAnalyser.py")
GRIS = (0.72, 0.72, 0.72)


def environnement():
    """Environnement des sous-processus (propage la simulation sans numpy)."""
    return dict(os.environ)


def lancer_cli(*arguments, **options):
    """Lance CADSurfaceAnalyser.py ; retourne le processus terminé."""
    return subprocess.run(
        [sys.executable, SCRIPT] + [str(a) for a in arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environnement(),
        **options
    )


# ============================================================================
# CONSTRUCTEUR DE STEP SYNTHETIQUES
# ============================================================================

class Scene(object):
    """Fichier STEP synthétique : une coque dont chaque face est nommée."""

    def __init__(self):
        self.lignes = []
        self.n = 0
        self.noms = {}                      # numéro d'instance de la face -> nom

    # ---- entités élémentaires --------------------------------------------
    def ajouter(self, texte):
        self.n += 1
        self.lignes.append("#%d=%s;" % (self.n, texte))
        return "#%d" % self.n

    def pt(self, x, y, z):
        return self.ajouter("CARTESIAN_POINT('',(%r,%r,%r))" % (x, y, z))

    def dr(self, x, y, z):
        return self.ajouter("DIRECTION('',(%r,%r,%r))" % (x, y, z))

    def axe(self, origine=(0, 0, 0), z=(0, 0, 1), x=(1, 0, 0)):
        return self.ajouter(
            "AXIS2_PLACEMENT_3D('',%s,%s,%s)"
            % (self.pt(*origine), self.dr(*z), self.dr(*x))
        )

    def sommet(self, p):
        return self.ajouter("VERTEX_POINT('',%s)" % self.pt(*p))

    def cercle(self, axe, rayon):
        return self.ajouter("CIRCLE('',%s,%r)" % (axe, rayon))

    def droite(self, p, d):
        vecteur = self.ajouter("VECTOR('',%s,1.)" % self.dr(*d))
        return self.ajouter("LINE('',%s,%s)" % (self.pt(*p), vecteur))

    def arete(self, v1, v2, courbe, meme_sens=True):
        return self.ajouter(
            "EDGE_CURVE('',%s,%s,%s,.%s.)" % (v1, v2, courbe, "T" if meme_sens else "F")
        )

    def oriente(self, arete, orientation=True):
        return self.ajouter(
            "ORIENTED_EDGE('',*,*,%s,.%s.)" % (arete, "T" if orientation else "F")
        )

    def boucle(self, aretes_orientees, exterieure=True):
        b = self.ajouter("EDGE_LOOP('',(%s))" % ",".join(aretes_orientees))
        return self.ajouter(
            "%s('',%s,.T.)" % ("FACE_OUTER_BOUND" if exterieure else "FACE_BOUND", b)
        )

    def face(self, nom, bornes, surface, meme_sens=True):
        f = self.ajouter(
            "ADVANCED_FACE('',(%s),%s,.%s.)"
            % (",".join(bornes), surface, "T" if meme_sens else "F")
        )
        ident = int(f[1:])
        self.noms[ident] = nom
        return ident

    def _rectangle(self, nom, surface, points, meme_sens=True):
        sommets = [self.sommet(p) for p in points]
        aretes = []
        for i in range(4):
            p, q = points[i], points[(i + 1) % 4]
            d = tuple(q[k] - p[k] for k in range(3))
            n = math.sqrt(sum(c * c for c in d))
            aretes.append(self.arete(sommets[i], sommets[(i + 1) % 4],
                                     self.droite(p, tuple(c / n for c in d))))
        return self.face(nom, [self.boucle([self.oriente(a) for a in aretes])], surface, meme_sens)

    # ---- faces à géométrie connue ----------------------------------------
    def plan_perce(self, nom="plan percé", demi=10.0, rayon_trou=3.0):
        """Carré de côté 2*demi percé d'un disque : A = 4 demi² − π r²."""
        s = self.ajouter("PLANE('',%s)" % self.axe())
        P = [(-demi, -demi, 0), (demi, -demi, 0), (demi, demi, 0), (-demi, demi, 0)]
        sommets = [self.sommet(p) for p in P]
        aretes = []
        for i in range(4):
            p, q = P[i], P[(i + 1) % 4]
            d = tuple(q[k] - p[k] for k in range(3))
            n = math.sqrt(sum(c * c for c in d))
            aretes.append(self.arete(sommets[i], sommets[(i + 1) % 4],
                                     self.droite(p, tuple(c / n for c in d))))
        exterieur = self.boucle([self.oriente(a) for a in aretes])
        v = self.sommet((rayon_trou, 0, 0))
        trou = self.boucle(
            [self.oriente(self.arete(v, v, self.cercle(self.axe(), rayon_trou)), False)],
            exterieure=False,
        )
        return self.face(nom, [exterieur, trou], s)

    def plan_rect(self, nom, x0, z=0.0, normale=(0, 0, 1), xdir=(1, 0, 0),
                  meme_sens=True, inclinaison_deg=0.0):
        """Rectangle 1 x 1 de plan donné ; `inclinaison_deg` penche la normale
        +Z de cet angle autour de l'axe X ; `meme_sens=False` retourne la face."""
        a = math.radians(inclinaison_deg)
        if tuple(normale) == (0, 0, 1):
            n = (0.0, math.sin(a), math.cos(a))
        else:
            n = tuple(normale)
        s = self.ajouter("PLANE('',%s)" % self.axe((x0, 0, z), z=n, x=xdir))
        X = xdir
        Y = (n[1] * X[2] - n[2] * X[1], n[2] * X[0] - n[0] * X[2], n[0] * X[1] - n[1] * X[0])
        P = [
            (x0, 0, z),
            (x0 + X[0], X[1], z + X[2]),
            (x0 + X[0] + Y[0], X[1] + Y[1], z + X[2] + Y[2]),
            (x0 + Y[0], Y[1], z + Y[2]),
        ]
        return self._rectangle(nom, s, P, meme_sens)

    def bande_cylindre(self, nom, cx=0.0, cy=0.0, r=10.0, z0=0.0, z1=20.0):
        """Cylindre complet entre deux cercles : A = 2 π r (z1 − z0)."""
        s = self.ajouter("CYLINDRICAL_SURFACE('',%s,%r)" % (self.axe((cx, cy, 0)), r))
        sh, sb = self.sommet((cx + r, cy, z1)), self.sommet((cx + r, cy, z0))
        haut = self.arete(sh, sh, self.cercle(self.axe((cx, cy, z1)), r))
        bas = self.arete(sb, sb, self.cercle(self.axe((cx, cy, z0)), r))
        return self.face(nom, [
            self.boucle([self.oriente(haut, False)]),
            self.boucle([self.oriente(bas, True)], exterieure=False),
        ], s)

    def calotte_sphere(self, nom, centre=(0.0, 0.0, 0.0), R=10.0, zc=6.0):
        """Calotte au-dessus du plan z = zc : A = 2 π R (R − zc)."""
        cx, cy, cz = centre
        rc = math.sqrt(R * R - zc * zc)
        s = self.ajouter("SPHERICAL_SURFACE('',%s,%r)" % (self.axe(centre), R))
        v = self.sommet((cx + rc, cy, cz + zc))
        e = self.arete(v, v, self.cercle(self.axe((cx, cy, cz + zc)), rc))
        return self.face(nom, [self.boucle([self.oriente(e)])], s)

    def cone_plein(self, nom="cône"):
        """Cône de sommet z = −10 jusqu'au cercle de rayon 10 en z = 10."""
        angle = math.atan(0.5)
        s = self.ajouter("CONICAL_SURFACE('',%s,5.,%r)" % (self.axe(), angle))
        v = self.sommet((10, 0, 10))
        e = self.arete(v, v, self.cercle(self.axe((0, 0, 10)), 10.0))
        return self.face(nom, [self.boucle([self.oriente(e)])], s)

    def patch_tore(self, nom, centre=(0.0, 0.0, 0.0), R=10.0, r=3.0, genre="tore"):
        """Morceau de tore : θ ∈ [0, π/3], φ ∈ [−π/4, π/2].
        `genre` : 'tore' (TOROIDAL_SURFACE) ou 'revolution' (révolution d'un
        cercle). A = r Δθ [R Δφ + r (sin φ2 − sin φ1)]."""
        cx, cy, cz = centre
        th1, ph1, ph2 = math.pi / 3, -math.pi / 4, math.pi / 2

        def P(th, ph):
            rho = R + r * math.cos(ph)
            return (cx + rho * math.cos(th), cy + rho * math.sin(th), cz + r * math.sin(ph))

        profil = self.cercle(self.axe((cx + R, cy, cz), z=(0, -1, 0), x=(1, 0, 0)), r)
        if genre == "tore":
            s = self.ajouter("TOROIDAL_SURFACE('',%s,%r,%r)" % (self.axe(centre), R, r))
        else:
            s = self.ajouter("SURFACE_OF_REVOLUTION('',%s,%s)" % (
                profil,
                self.ajouter("AXIS1_PLACEMENT('',%s,%s)" % (self.pt(cx, cy, cz), self.dr(0, 0, 1))),
            ))
        v00, v10 = self.sommet(P(0, ph1)), self.sommet(P(th1, ph1))
        v01, v11 = self.sommet(P(0, ph2)), self.sommet(P(th1, ph2))
        e_b = self.arete(v00, v10, self.cercle(self.axe((cx, cy, cz + r * math.sin(ph1))), R + r * math.cos(ph1)))
        e_t = self.arete(v01, v11, self.cercle(self.axe((cx, cy, cz + r * math.sin(ph2))), R + r * math.cos(ph2)))
        e_0 = self.arete(v00, v01, self.cercle(self.axe((cx + R, cy, cz), z=(0, -1, 0), x=(1, 0, 0)), r))
        e_1 = self.arete(v10, v11, self.cercle(self.axe(
            (cx + R * math.cos(th1), cy + R * math.sin(th1), cz),
            z=(math.sin(th1), -math.cos(th1), 0), x=(math.cos(th1), math.sin(th1), 0)), r))
        return self.face(nom, [self.boucle([
            self.oriente(e_b, True), self.oriente(e_1, True),
            self.oriente(e_t, False), self.oriente(e_0, False)])], s)

    def quart_cylindre(self, nom, ox=0.0, R=5.0, L=10.0, genre="extrusion",
                       plan=None, inclinaison_deg=0.0):
        """Quart de cylindre (θ ∈ [0, π/2], z ∈ [0, L]) de surface
        'analytique' (CYLINDRICAL_SURFACE), 'extrusion' (extrusion d'un cercle)
        ou 'nurbs' (NURBS rationnelle). A = R (π/2) L.

        Si `plan` est un nom, une seconde face plane est ajoutée contre
        l'arête θ = 0 : tangente au cylindre si inclinaison_deg = 0, sinon
        inclinée de cet angle. Retourne l'identifiant de la face cylindrique
        (et celui du plan s'il est demandé)."""
        if genre == "analytique":
            s = self.ajouter("CYLINDRICAL_SURFACE('',%s,%r)" % (self.axe((ox, 0, 0)), R))
        elif genre == "extrusion":
            cercle = self.cercle(self.axe((ox, 0, 0)), R)
            s = self.ajouter("SURFACE_OF_LINEAR_EXTRUSION('',%s,%s)" % (
                cercle, self.ajouter("VECTOR('',%s,%r)" % (self.dr(0, 0, 1), L))))
        else:
            c = math.sqrt(2) / 2
            lignes, poids = [], []
            for (x, y), w in zip([(R, 0), (R, R), (0, R)], [1, c, 1]):
                lignes.append("(%s,%s)" % (self.pt(ox + x, y, 0), self.pt(ox + x, y, L)))
                poids.append("(%r,%r)" % (w, w))
            s = self.ajouter(
                "(BOUNDED_SURFACE()B_SPLINE_SURFACE(2,1,(%s),.UNSPECIFIED.,.F.,.F.,.F.)"
                "B_SPLINE_SURFACE_WITH_KNOTS((3,3),(2,2),(0.,1.),(0.,1.),.UNSPECIFIED.)"
                "GEOMETRIC_REPRESENTATION_ITEM()RATIONAL_B_SPLINE_SURFACE((%s))"
                "REPRESENTATION_ITEM('')SURFACE())" % (",".join(lignes), ",".join(poids)))
        v00, v10 = self.sommet((ox + R, 0, 0)), self.sommet((ox, R, 0))
        v01, v11 = self.sommet((ox + R, 0, L)), self.sommet((ox, R, L))
        e_b = self.arete(v00, v10, self.cercle(self.axe((ox, 0, 0)), R))
        e_t = self.arete(v01, v11, self.cercle(self.axe((ox, 0, L)), R))
        e_r = self.arete(v00, v01, self.droite((ox + R, 0, 0), (0, 0, 1)))
        e_l = self.arete(v10, v11, self.droite((ox, R, 0), (0, 0, 1)))
        fc = self.face(nom, [self.boucle([
            self.oriente(e_b, True), self.oriente(e_l, True),
            self.oriente(e_t, False), self.oriente(e_r, False)])], s)
        if plan is None:
            return fc
        a = math.radians(inclinaison_deg)
        n = (math.cos(a), -math.sin(a), 0.0)
        d = (math.sin(a), math.cos(a), 0.0)
        largeur = 10.0
        q = (ox + R + d[0] * largeur, d[1] * largeur)
        sp = self.ajouter("PLANE('',%s)" % self.axe((ox + R, 0, 0), z=n, x=d))
        v20, v21 = self.sommet((q[0], q[1], 0)), self.sommet((q[0], q[1], L))
        e1 = self.arete(v01, v21, self.droite((ox + R, 0, L), (d[0], d[1], 0)))
        e2 = self.arete(v20, v21, self.droite((q[0], q[1], 0), (0, 0, 1)))
        e3 = self.arete(v00, v20, self.droite((ox + R, 0, 0), (d[0], d[1], 0)))
        fp = self.face(plan, [self.boucle([
            self.oriente(e_r, True), self.oriente(e1, True),
            self.oriente(e2, False), self.oriente(e3, False)])], sp)
        return fc, fp

    # ---- écriture -----------------------------------------------------------
    def ecrire(self, chemin):
        """Écrit le STEP (coque, solide et représentation compris, pour que les
        STEP colorés puissent être écrits)."""
        lignes = list(self.lignes)
        n = self.n

        def ajout(texte):
            nonlocal n
            n += 1
            lignes.append("#%d=%s;" % (n, texte))
            return "#%d" % n

        ctx = ajout("(GEOMETRIC_REPRESENTATION_CONTEXT(3)REPRESENTATION_CONTEXT('',''))")
        coque = ajout("CLOSED_SHELL('Closed Shell',(%s))" % ",".join("#%d" % k for k in sorted(self.noms)))
        solide = ajout("MANIFOLD_SOLID_BREP('piece',%s)" % coque)
        ajout("ADVANCED_BREP_SHAPE_REPRESENTATION('NONE',(%s),%s)" % (solide, ctx))
        with open(chemin, "w", encoding="latin-1", newline="\n") as f:
            f.write("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n" + "\n".join(lignes)
                    + "\nENDSEC;\nEND-ISO-10303-21;\n")
        return chemin

    def nom(self, ident):
        return self.noms[int(str(ident).lstrip("#"))]


# ============================================================================
# ANALYSE EN PROCESSUS
# ============================================================================

def analyser_fichier(chemin, tol_deg=1.0, tol_lin=0.005, tol_angle=0.05, geometrie=True):
    """Chaîne complète sans la ligne de commande ; retourne un espace de noms."""
    from cadsurf.couleurs import create_group_colors
    from cadsurf.familles import build_geometric_families, build_tangent_family
    from cadsurf.geom_faces import compute_face_geometry
    from cadsurf.step_parser import StepFile
    from cadsurf.tangence import analyse

    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        step = StepFile(chemin)
        faces, jonctions, groupes, groupe_de_face = analyse(step, tol_deg)
        couleurs = create_group_colors(groupes, False)
        infos, cache_aretes, resume = compute_face_geometry(
            step, faces, jonctions, groupe_de_face, couleurs, calcul_integrales=geometrie
        )
        familles = {"tangent": build_tangent_family(groupes, infos, tol_deg)}
        familles.update(build_geometric_families(faces, infos, tol_lin, tol_angle))
    return SimpleNamespace(
        step=step, faces=faces, jonctions=jonctions, groupes=groupes,
        groupe_de_face=groupe_de_face, couleurs=couleurs, infos=infos,
        resume=resume, familles=familles,
    )


def groupes_par_nom(scene, analyse, cle):
    """Groupes d'une famille sous forme de listes triées de noms de faces."""
    return sorted(sorted(scene.noms[f] for f in g["faces"]) for g in analyse.familles[cle]["groupes"])


# ============================================================================
# LECTURE DES COULEURS D'UN STEP COLORE
# ============================================================================

def couleurs_des_faces(chemin):
    """{numéro de face: (r, v, b)} lu en suivant la chaîne de styles du STEP."""
    from cadsurf.step_parser import Ref, StepFile

    step = StepFile(chemin)

    def premiere_ref(args):
        for a in args:
            if isinstance(a, Ref):
                return int(a)
            if isinstance(a, list):
                r = premiere_ref(a)
                if r is not None:
                    return r
        return None

    resultat = {}
    for sid in step.ids_of("STYLED_ITEM"):
        a = step.get(sid, "STYLED_ITEM")
        if len(a) < 3 or not isinstance(a[2], Ref) or step.type_of(int(a[2])) != "ADVANCED_FACE":
            continue
        courant = premiere_ref(a[1])                         # PRESENTATION_STYLE_ASSIGNMENT
        while step.type_of(courant) != "COLOUR_RGB":
            courant = premiere_ref(step.ents[courant][0][1])
        rgb = step.get(courant, "COLOUR_RGB")
        resultat[int(a[2])] = tuple(round(float(x), 3) for x in rgb[1:4])
    return resultat
