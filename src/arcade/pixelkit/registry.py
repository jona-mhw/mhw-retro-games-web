"""descubre los juegos del arcade.

cada juego es una carpeta games/<id>/ con un game.toml adentro. el id ES el
nombre de la carpeta: no es un campo del manifiesto, así hay una cosa menos que
se puede desincronizar. el emulador (arcade.py) y el menú (pixelkit.menu) leen
de acá; para sumar un juego alcanza con dejar su carpeta y su game.toml.
"""
import os

try:
    import tomllib
except ModuleNotFoundError as e:  # pragma: no cover
    raise RuntimeError(
        "pixelkit necesita Python 3.11+ (tomllib) para leer los game.toml"
    ) from e

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES_DIR = os.path.join(ROOT, "games")


class Game:
    """un juego del arcade, tal como lo declara su game.toml."""

    def __init__(self, gid, meta):
        self.id = gid
        self.module = meta.get("module", "games.%s" % gid)
        self.title = meta.get("title", gid)
        self.author = meta.get("author", "")
        self.year = meta.get("year", "")
        self.blurb = meta.get("blurb", "")
        self.controls = meta.get("controls", "")
        self.width = int(meta.get("width", 256))
        self.height = int(meta.get("height", 240))

    def __repr__(self):
        return "Game(%r)" % self.id


def load_manifest(path):
    with open(path, "rb") as f:
        data = tomllib.load(f)
    # aceptamos tanto [game] como la raíz, para no ser quisquillosos
    return data.get("game", data)


def discover_games(games_dir=GAMES_DIR):
    """lista los juegos, ordenados por id. ignora carpetas sin game.toml."""
    games = []
    if not os.path.isdir(games_dir):
        return games
    for name in sorted(os.listdir(games_dir)):
        manifest = os.path.join(games_dir, name, "game.toml")
        if os.path.isfile(manifest):
            games.append(Game(name, load_manifest(manifest)))
    return games
