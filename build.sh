#!/usr/bin/env bash
# empaqueta el cabinet (src/arcade) en arcade.pyxapp, que es lo que carga
# index.html. hay que correrlo cada vez que se toca algo de src/.
#
#   ./build.sh            (necesita pyxel: pip install pyxel)
set -e
cd "$(dirname "$0")"
find src -name "__pycache__" -prune -exec rm -rf {} +
pyxel package src/arcade src/arcade/main.py
rm -f src/arcade/.pyxapp_startup_script
echo "listo: arcade.pyxapp"
