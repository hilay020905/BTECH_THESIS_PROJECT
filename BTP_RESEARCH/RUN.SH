#!/bin/bash
set -e
cd "$(dirname "$0")"
N=${1:-16}; WHICH=${2:-ALL}
if ! command -v g++ >/dev/null || ! command -v make >/dev/null || ! command -v git >/dev/null; then
  sudo apt-get update && sudo apt-get install -y build-essential git
fi
if [ ! -f CUDD_INST/lib/libcudd.a ]; then
  echo "Building CUDD library (first run only, a few minutes)..."
  rm -rf CUDD_SRC
  git clone -q --depth 1 https://github.com/ivmai/cudd.git CUDD_SRC
  ( cd CUDD_SRC
    touch aclocal.m4; sleep 1; touch configure config.h.in Makefile.in
    ./configure --prefix="$PWD/../CUDD_INST" > /dev/null 2>&1
    make -j"$(nproc)" > /dev/null 2>&1
    make install > /dev/null 2>&1 ) || { echo "CUDD build failed"; exit 1; }
fi
g++ -std=c++17 -O2 -I CUDD_INST/include ADDERS.CPP CUDD_INST/lib/libcudd.a -lm -o ADDERS
./ADDERS "$N" "$WHICH"
if command -v wslpath >/dev/null && command -v explorer.exe >/dev/null; then
  explorer.exe "$(wslpath -w "$PWD/RESULTS.HTML")" || true
fi
