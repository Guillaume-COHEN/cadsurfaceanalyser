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

"""Lecture du format STEP (ISO 10303-21) : types de valeurs, parseur d'arguments,
classe StepFile (entités, accès par type).
"""

import re


# ============================================================================
# TYPES DU PARSEUR STEP
# ============================================================================

class Ref(int):
    pass


class Enum(str):
    pass


class Typed(object):

    def __init__(self, name, args):
        self.name = name
        self.args = args


# ============================================================================
# PARSEUR STEP
# ============================================================================

class _Parser(object):

    NUM = re.compile(
        r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?'
    )

    IDENT = re.compile(
        r'[A-Za-z_][A-Za-z0-9_]*'
    )

    def __init__(self, text):
        self.s = text
        self.i = 0
        self.n = len(text)

    def ws(self):

        while self.i < self.n:

            if self.s[self.i] in " \t\r\n":
                self.i += 1
                continue

            if self.s.startswith("/*", self.i):

                j = self.s.find(
                    "*/",
                    self.i + 2
                )

                if j < 0:
                    self.i = self.n
                else:
                    self.i = j + 2

                continue

            break

    def value(self):

        self.ws()

        if self.i >= self.n:
            raise ValueError("Fin inattendue")

        s = self.s
        c = s[self.i]

        # Référence
        if c == "#":

            m = re.compile(r"#(\d+)").match(
                s,
                self.i
            )

            if not m:
                raise ValueError("Référence invalide")

            self.i = m.end()

            return Ref(
                int(m.group(1))
            )

        # Chaîne
        if c == "'":

            j = self.i + 1
            buf = []

            while j < self.n:

                if s[j] == "'":

                    if (
                        j + 1 < self.n
                        and s[j + 1] == "'"
                    ):
                        buf.append("'")
                        j += 2
                        continue

                    break

                buf.append(s[j])
                j += 1

            if j >= self.n:
                raise ValueError(
                    "Chaîne non terminée"
                )

            self.i = j + 1

            return "".join(buf)

        # Enum
        if c == ".":

            j = s.find(
                ".",
                self.i + 1
            )

            if j < 0:
                raise ValueError(
                    "Enum invalide"
                )

            v = s[
                self.i + 1:j
            ]

            self.i = j + 1

            return Enum(v)

        # Liste
        if c == "(":
            return self.lst()

        # Indéfini
        if c == "$":
            self.i += 1
            return None

        # Wildcard
        if c == "*":
            self.i += 1
            return "*"

        # Nombre
        m = self.NUM.match(
            s,
            self.i
        )

        if m:

            self.i = m.end()

            return float(
                m.group(0)
            )

        # Identifiant / type
        m = self.IDENT.match(
            s,
            self.i
        )

        if m:

            name = m.group(0)

            self.i = m.end()

            self.ws()

            if (
                self.i < self.n
                and s[self.i] == "("
            ):
                return Typed(
                    name.upper(),
                    self.lst()
                )

            return name.upper()

        raise ValueError(
            "Caractère inattendu %r position %d"
            % (c, self.i)
        )

    def lst(self):

        self.ws()

        if (
            self.i >= self.n
            or self.s[self.i] != "("
        ):
            raise ValueError(
                "Liste attendue"
            )

        self.i += 1

        result = []

        while True:

            self.ws()

            if self.i >= self.n:
                raise ValueError(
                    "Liste non terminée"
                )

            if self.s[self.i] == ")":
                self.i += 1
                return result

            result.append(
                self.value()
            )

            self.ws()

            if (
                self.i < self.n
                and self.s[self.i] == ","
            ):
                self.i += 1

    def typed(self):

        self.ws()

        m = self.IDENT.match(
            self.s,
            self.i
        )

        if not m:
            raise ValueError(
                "Type STEP attendu"
            )

        name = m.group(0).upper()

        self.i = m.end()

        self.ws()

        return (
            name,
            self.lst()
        )


# ============================================================================
# FICHIER STEP
# ============================================================================

def normalise_complex_bspline(parts):
    """Entités complexes B-spline (courbes/surfaces rationnelles notamment).

    Dans une entité complexe, les parties B_SPLINE_* n'ont pas de nom en
    premier argument et les noeuds sont dans une partie séparée. On les
    ramène à la disposition des entités simples :
        B_SPLINE_CURVE_WITH_KNOTS   : (nom, degre, points, forme, ferme,
                                       auto_inter, multiplicites, noeuds, spec)
        B_SPLINE_SURFACE_WITH_KNOTS : (nom, deg_u, deg_v, points, forme,
                                       ferme_u, ferme_v, auto_inter,
                                       mult_u, mult_v, noeuds_u, noeuds_v, spec)
    """
    if len(parts) < 2:
        return parts
    d = {t: a for t, a in parts}
    name = ""
    if "REPRESENTATION_ITEM" in d and d["REPRESENTATION_ITEM"]:
        name = d["REPRESENTATION_ITEM"][0]
    for base, knots in (
        ("B_SPLINE_CURVE", "B_SPLINE_CURVE_WITH_KNOTS"),
        ("B_SPLINE_SURFACE", "B_SPLINE_SURFACE_WITH_KNOTS"),
    ):
        if base not in d:
            continue
        head = [name] + list(d[base])
        merged = {base: head}
        if knots in d:
            merged[knots] = head + list(d[knots])
        parts = [
            (t, merged[t] if t in merged else a)
            for t, a in parts
        ]
        d = {t: a for t, a in parts}
    return parts


def _sans_commentaires_initiaux(texte):
    """Retire les commentaires /* ... */ placés en tête d'une instruction (le
    format STEP les autorise n'importe où, par exemple juste avant une instance)."""
    while True:
        t = texte.lstrip()
        if not t.startswith("/*"):
            return t
        j = t.find("*/", 2)
        if j < 0:
            return ""
        texte = t[j + 2:]


class StepFile(object):

    def __init__(self, path):
        self.path = path

        with open(
            path,
            "r",
            encoding="latin-1",
            newline=""
        ) as f:
            self.text = f.read()

        self.nl = (
            "\r\n"
            if "\r\n" in self.text
            else "\n"
        )

        self.ents = {}

        self.spans = {}

        self.endsec = None

        self._scan()

    def _scan(self):

        text = self.text

        m = re.search(
            r"\bDATA\s*;",
            text,
            re.I
        )

        if not m:
            raise ValueError(
                "Section DATA introuvable"
            )

        i = m.end()

        n = len(text)

        in_quote = False

        start = i

        while i < n:

            c = text[i]

            if in_quote:

                if c == "'":

                    if (
                        i + 1 < n
                        and text[i + 1] == "'"
                    ):
                        i += 2
                        continue

                    in_quote = False

            else:

                if c == "'":
                    in_quote = True

                elif (
                    c == "/"
                    and i + 1 < n
                    and text[i + 1] == "*"
                ):

                    j = text.find(
                        "*/",
                        i + 2
                    )

                    if j < 0:
                        i = n
                        break

                    i = j + 2
                    continue

                elif c == ";":

                    stmt = text[
                        start:i
                    ]

                    if _sans_commentaires_initiaux(stmt).strip().upper() == "ENDSEC":

                        self.endsec = start

                        break

                    self._add(
                        start,
                        i + 1,
                        stmt
                    )

                    start = i + 1

            i += 1

    def _add(
        self,
        start,
        end,
        stmt
    ):

        m = re.match(
            r"\s*#(\d+)\s*=\s*(.*)\Z",
            _sans_commentaires_initiaux(stmt),
            re.S
        )

        if not m:
            return

        eid = int(
            m.group(1)
        )

        body = m.group(2)

        try:

            p = _Parser(body)

            p.ws()

            if (
                p.i < p.n
                and body[p.i] == "("
            ):

                p.i += 1

                parts = []

                while True:

                    p.ws()

                    if (
                        p.i < p.n
                        and body[p.i] == ")"
                    ):
                        p.i += 1
                        break

                    parts.append(
                        p.typed()
                    )

            else:

                parts = [
                    p.typed()
                ]

            parts = normalise_complex_bspline(parts)
            self.ents[eid] = parts

            self.spans[eid] = (
                start,
                end
            )

        except Exception:
            # Entité STEP non comprise.
            # On ne bloque pas l'analyse globale.
            return

    def type_of(self, ref):

        parts = self.ents.get(
            int(ref),
            []
        )

        if not parts:
            return None

        return parts[0][0]

    def types_of(self, ref):

        return [
            t
            for t, _ in self.ents.get(
                int(ref),
                []
            )
        ]

    def get(
        self,
        ref,
        *types
    ):

        for t, args in self.ents.get(
            int(ref),
            []
        ):

            if not types or t in types:
                return args

        return None

    def ids_of(self, *types):

        result = []

        wanted = set(types)

        for eid, parts in self.ents.items():

            if any(
                t in wanted
                for t, _ in parts
            ):
                result.append(eid)

        return result
