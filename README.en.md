# CADSurfaceAnalyser

[![tests](https://github.com/Guillaume-COHEN/cadsurfaceanalyser/actions/workflows/ci.yml/badge.svg)](https://github.com/Guillaume-COHEN/cadsurfaceanalyser/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)

Analyses the surfaces of a **STEP AP214** file (B-Rep solid) **without OpenCASCADE**:
groups of tangent faces, area and centroid of every face, families of faces with the
same geometry, and exports to **coloured STEP**, **JSON** and **CSV**. A graphical
interface is included.

*The main documentation is in French: see [README.md](README.md).*

## Features

- Reads STEP (ISO 10303-21 / AP214) with a purpose-built reader: planes, cylinders,
  cones, spheres, tori, surfaces of revolution and linear extrusion, B-spline and NURBS
  surfaces.
- Detects tangency (G1 continuity, adjustable tolerance) between neighbouring faces and
  builds groups of tangent faces.
- Computes for each face: area (Green's theorem and Gauss-Legendre quadrature),
  centroid, perimeter, bounding box, normal, convex/concave character, type-specific
  parameters, and the solid's volume.
- Sorts faces into eight families of groups: tangent, coaxial, parallel, concentric,
  identical geometry, coplanar, plane (same normal vector), cylinder (same radius).
- Writes one fully coloured STEP per family, a STEP with B-spline faces in violet, a
  JSON file and four CSV files.

## Quick start

```bash
git clone https://github.com/Guillaume-COHEN/cadsurfaceanalyser.git && cd REPO
python CADSurfaceAnalyser.py MyPart.stp          # command line
python CADSurfaceGUI.py                          # graphical interface (needs tkinter)
python -m pip install -r requirements.txt        # optional: numpy, 3-4x faster
python -m unittest discover -s tests -v          # run the tests
```

Python 3.8+, no mandatory dependency. numpy is optional and detected automatically
(`--sans-numpy` forces pure Python). Options: `--tol-deg`, `--tol-lin`,
`--tol-angle-geo`, `--familles-step`, `--sorties`, `--dossier-sortie`,
`--precision-numerique rapide|standard|fine`, `--processus N`; see `--help`.

## Test data

Put STEP test files in [`data/stp_tests/`](data/stp_tests/README.md). Only add files
whose content you are allowed to publish.

## Known limitations

Tangency is sampled at three points per edge and ignores normal orientation; offset
surfaces and closed/periodic B-spline surfaces are not supported; tolerances for
families are absolute (in file units); the shell is assumed to be oriented outward.

## License

Apache License 2.0: see [LICENSE](LICENSE) and [NOTICE](NOTICE).
