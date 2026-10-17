"""configuración del sistema del cabinet, persistente y compartida.

son los ajustes que valen para TODOS los juegos: cómo se ve la pantalla, la
escala entera y la pantalla completa. se guardan en un json al lado del repo. el
menú los edita; cada juego, al bootear, llama a apply() para respetarlos. como
cada juego es un proceso aparte, el disco es lo que los une.

la pantalla es el ajuste estrella y tiene cuatro modos:

    nítido      vecino más cercano, pixel perfecto (el default de siempre)
    suave       bilineal, los píxeles se difuminan al agrandar
    crt suave   tubo de sala recreativa, discreto
    crt fuerte  tubo con scanlines marcadas y rejilla de apertura

el modo del índice NO es el que espera pyxel: los dos crt son nítidos para
pyxel y el efecto lo pone pixelkit.crt sobre el framebuffer (ver ese módulo).
por eso la traducción es explícita — SCREEN para pyxel, CRT para el overlay.
"""
import json
import os

from pixelkit import web
from pixelkit.registry import ROOT

PATH = os.path.join(ROOT, "arcade.config.json")

MODES = ("crisp", "smooth", "crt-soft", "crt-hard")
MODE_LABEL = {0: "nítido", 1: "suave", 2: "crt suave", 3: "crt fuerte"}
# modo del cabinet -> pyxel.screen_mode (0 crisp, 1 smooth, 2 retro)
SCREEN = {0: 0, 1: 1, 2: 0, 3: 0}
# modo del cabinet -> nivel de pixelkit.crt (0 off, 1 suave, 2 fuerte)
CRT = {0: 0, 1: 0, 2: 1, 3: 2}

DEFAULT = {"screen_mode": 0, "integer_scale": False, "fullscreen": False}


def _read():
    """el json guardado: del disco, o de localStorage en el navegador."""
    if web.ACTIVE:
        raw = web.load_text(os.path.basename(PATH))
        if raw is None:
            raise FileNotFoundError(PATH)
        return json.loads(raw)
    with open(PATH) as f:
        return json.load(f)


def load():
    """lee la config del disco, cae al default si no existe o está corrupta."""
    cfg = dict(DEFAULT)
    try:
        data = _read()
        if isinstance(data, dict):
            cfg.update(data)
    except (FileNotFoundError, ValueError, OSError):
        pass
    cfg["screen_mode"] = int(cfg.get("screen_mode", 0)) % len(MODES)
    cfg["integer_scale"] = bool(cfg.get("integer_scale", False))
    cfg["fullscreen"] = bool(cfg.get("fullscreen", False))
    return cfg


def save(cfg):
    """graba la config. silencioso si el disco falla: no vale tirar el juego."""
    if web.ACTIVE:
        web.save_text(os.path.basename(PATH), json.dumps(cfg))
        return
    try:
        with open(PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


def crt_level(cfg=None):
    """el nivel de overlay crt que le toca a la config (0, 1 o 2)."""
    cfg = cfg or load()
    return CRT.get(int(cfg.get("screen_mode", 0)), 0)


def apply(cfg=None):
    """aplica la config a un pyxel ya inicializado. llamar tras pyxel.init.

    tolerante: si un backend no soporta algún ajuste (headless, por ejemplo),
    no revienta el juego. devuelve la config, para que el llamador saque de ahí
    el nivel de crt (esto no se puede aplicar acá: va al final de cada draw).
    """
    import pyxel
    cfg = cfg or load()
    mode = SCREEN.get(int(cfg.get("screen_mode", 0)), 0)
    for fn in (lambda: pyxel.screen_mode(mode),
               lambda: pyxel.integer_scale(cfg["integer_scale"]),
               lambda: pyxel.fullscreen(cfg["fullscreen"])):
        try:
            fn()
        except Exception:
            pass
    return cfg
