#!/usr/bin/env bash
# empaqueta el cabinet (src/arcade) en arcade.pyxapp, que es lo que carga
# index.html. hay que correrlo cada vez que se toca algo de src/.
# los tests (test_*.py) viven en el repo pero no viajan al navegador.
#
#   ./build.sh            (necesita pyxel: pip install pyxel)
set -e
cd "$(dirname "$0")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/arcade"
(cd src/arcade && tar cf - --exclude="__pycache__" --exclude="test_*.py" --exclude="*.png" .) \
  | (cd "$tmp/arcade" && tar xf -)
pyxel package "$tmp/arcade" "$tmp/arcade/main.py"
echo "listo: arcade.pyxapp"
