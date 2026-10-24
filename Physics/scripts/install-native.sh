#!/bin/sh
# Optional developer prerequisites. These Homebrew formulas are NOT a binary lock.
# Validated minimal profile uses pinned Eigen source and Python wheel lock instead.
set -eu
case "${1:-}" in
  base) brew install cmake ;;
  sofa) brew install boost tinyxml2 zlib ;;
  precice) brew install boost libxml2 pkgconf ;;
  meep) brew install autoconf automake libtool pkgconf fftw hdf5 guile libctl harminv swig ;;
  moose) echo 'Use the upstream MOOSE environment for the locked release; see docs/MODULES.md. Generic brew PETSc may be incompatible.' >&2; exit 2 ;;
  fers) echo 'Set VCPKG_ROOT to a pinned vcpkg checkout matching external/fers/vcpkg.json builtin-baseline.' >&2; exit 2 ;;
  *) echo 'usage: sh scripts/install-native.sh base|sofa|precice|meep|moose|fers' >&2; exit 2 ;;
esac
