#!/usr/bin/env bash
# Ballot Buddy home-screen icons from the chosen logo. Usage: bash buddy/make_icons.sh <logo-slug>   (default check-smile)
set -e
cd "$(dirname "$0")"
L="${1:-check-smile}"
mkdir -p icons
cp "logos/$L.svg" icons/logo.svg
node logos/render.cjs "logos/$L.svg" icons/icon-512.png 512 "logos/$L.svg" icons/icon-192.png 192 \
  "logos/$L.svg" icons/apple-touch-icon.png 180 "logos/$L.svg" icons/icon-64.png 64 "logos/$L.svg" icons/favicon-32.png 32
echo "$L" > icons/CHOSEN
