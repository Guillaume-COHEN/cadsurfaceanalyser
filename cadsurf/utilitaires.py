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

"""Petites fonctions utilitaires communes aux exports (arrondis, formats).
"""



def _rnd(x, nd=6):
    if isinstance(x, float):
        return round(x, nd) + 0.0
    if isinstance(x, (list, tuple)):
        return [_rnd(y, nd) for y in x]
    if isinstance(x, dict):
        return {k: _rnd(y, nd) for k, y in x.items()}
    return x


def _round_list(v, nd=6):
    return None if v is None else [round(x, nd) + 0.0 for x in v]


def _make_formatter(virgule):
    def fmt(x, nd=6):
        if x is None:
            return ""
        if isinstance(x, bool):
            return "OUI" if x else "NON"
        if isinstance(x, float):
            s = "%.*f" % (nd, x + 0.0)
            if s.startswith("-") and float(s) == 0.0:
                s = s[1:]
            return s.replace(".", ",") if virgule else s
        return str(x)
    return fmt


def _xyz(v):
    return list(v) if v is not None else [None, None, None]
