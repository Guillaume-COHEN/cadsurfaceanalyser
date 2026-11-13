# Copyright 2026 The CADSurfaceAnalyser authors.
# Licensed under the Apache License, Version 2.0 (voir le fichier LICENSE).
"""Simule une machine sans numpy : l'import de numpy est interdit.

Utilisé par les tests avec CADSURF_TEST_SANS_NUMPY=1 (en processus et, via
PYTHONPATH, dans les sous-processus lancés par les tests).
"""

import sys


class _BloqueNumpy(object):
    def find_spec(self, nom, chemin=None, cible=None):
        if nom == "numpy" or nom.startswith("numpy."):
            raise ModuleNotFoundError("numpy absent (simulation de test)")
        return None


if not any(isinstance(f, _BloqueNumpy) for f in sys.meta_path):
    sys.meta_path.insert(0, _BloqueNumpy())
