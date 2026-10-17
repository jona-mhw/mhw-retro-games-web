"""el cabinet en el navegador: lo que cambia cuando pyxel corre en pyodide.

en el escritorio cada juego es un proceso y el disco los une. en la web no hay
procesos ni disco que sobreviva a un reload, así que:

- **lanzar un juego es cambiar la url**: `?game=<id>`. el arranque (main.py) lee
  la url y bootea el juego o el menú. index.html reinicia pyxel sin recargar la
  página (así no se pierde la pantalla completa ni hay que bajar pyodide otra
  vez); si eso no está, recarga y listo.
- **lo persistente va a localStorage**: config y récords se guardan con la misma
  clave que el archivo json del escritorio, así el resto de pixelkit no se entera.
- **los controles táctiles los dibuja index.html**, bajo la pantalla. cada juego
  los declara en `[game.touch]` de su game.toml y acá se le avisa a la página
  cuál mostrar: "nav" (cruceta + OK, para título, récords e iniciales) o
  "play" (los del juego). los botones aprietan teclas de verdad, así que los
  juegos no se enteran de que hay un dedo.
- **un gamepad físico cuenta como teclado**: se envuelven btn/btnp para que la
  cruceta valga por flechas y los botones por las teclas que usa cada juego.

fuera del navegador (ACTIVE False) todo esto no hace nada.
"""
import json
import sys

import pyxel

ACTIVE = sys.platform == "emscripten"
PREFIX = "mhw-arcade:"

if ACTIVE:
    import js

# los controles de navegación: título, game over, iniciales, menú
NAV = {"pad": "4", "buttons": [["OK", "enter"]],
       "hint": "toca la pantalla o OK para seguir"}
MENU = dict(NAV, hint="toca un juego para ver su ficha, otra vez para jugar")
PAUSE = dict(NAV, hint="OK sigue · volver sale al título")
# si un juego no declara [game.touch], cruceta + acción
DEFAULT_PLAY = {"pad": "4", "buttons": [["acción", "space"]]}

_screen = {"w": 320, "h": 240}
_touch = None        # is_touch() lo averigua una vez
_play = DEFAULT_PLAY


def load_text(name):
    """el texto guardado bajo `name`, o None."""
    try:
        v = js.window.localStorage.getItem(PREFIX + name)
    except Exception:
        return None
    # pyodide trae el null de js como JsNull, no como None
    return v if isinstance(v, str) else None


def save_text(name, text):
    try:
        js.window.localStorage.setItem(PREFIX + name, text)
    except Exception:
        pass


def current_game():
    """el id que pide la url (?game=<id>), o None para el menú."""
    try:
        return js.URLSearchParams.new(js.window.location.search).get("game")
    except Exception:
        return None


def _go(query):
    """cambia de cartucho. index.html sabe reiniciar pyxel sin recargar."""
    go = getattr(js.window, "mhwGo", None)
    if go:
        go(query)
    elif query:
        js.window.location.search = query
    else:
        js.window.location.href = js.window.location.pathname


def launch(game_id):
    """bootea un juego."""
    _go("?game=" + game_id)


def to_menu():
    """vuelve al menú del cabinet: la misma página, sin parámetros."""
    _go("")


def quit():
    """lo que en el escritorio es pyxel.quit(): en la web, volver al menú."""
    if ACTIVE:
        to_menu()
    else:
        pyxel.quit()


# --- controles táctiles ---------------------------------------------------
def configure(width, height, play=None):
    """qué se está corriendo: el tamaño de pantalla (para repartir el espacio
    entre juego y controles) y los controles de juego. llamar antes de init."""
    global _play
    _screen.update(w=width, h=height)
    _play = play or DEFAULT_PLAY


def touch(scene):
    """muestra los controles de "menu", "nav" o "play". fuera de la web, nada."""
    if not ACTIVE:
        return
    spec = dict({"menu": MENU, "nav": NAV, "pause": PAUSE}.get(scene, _play))
    spec.update(_screen, scene=scene)
    try:
        if is_touch():
            pyxel.mouse(False)    # con el dedo, la flechita quedaba donde tocaste
        js.window.mhwTouch(json.dumps(spec))
    except Exception:
        pass


def is_touch():
    """¿se juega con el dedo? (celular o tablet). sirve para elegir textos:
    "toca para jugar" en vez de "enter para jugar"."""
    global _touch
    if _touch is None:
        try:
            _touch = ACTIVE and bool(js.window.matchMedia("(pointer: coarse)").matches)
        except Exception:
            _touch = False
    return _touch


def portrait():
    """¿la pantalla está parada? (más alta que ancha)."""
    if not ACTIVE:
        return False
    try:
        return js.window.innerHeight > js.window.innerWidth
    except Exception:
        return False


def page_hidden():
    """¿la página está escondida? (cambiaste de app o de pestaña): el Cabinet
    pausa solo, para que una llamada no te cueste la partida."""
    if not ACTIVE:
        return False
    try:
        return bool(js.document.hidden)
    except Exception:
        return False


def drag():
    """(dx, dy) en píxeles de juego que se arrastró el trackpad (pad = "drag"
    en [game.touch]) desde la última llamada. llamar una vez por frame. fuera
    de la web, o sin dedo, es (0, 0)."""
    if not ACTIVE:
        return (0.0, 0.0)
    try:
        dx, dy = str(js.window.mhwDrag()).split(",")
        return (float(dx), float(dy))
    except Exception:
        return (0.0, 0.0)


# --- gamepad -> teclado ---------------------------------------------------
# A confirma y dispara (espacio y enter valen para eso en todos lados), B y X
# son las teclas secundarias (guardar/ítem en bloques, disparo alterno en
# asteroides), START confirma y BACK es el esc.
_PAD = {
    pyxel.KEY_UP: (pyxel.GAMEPAD1_BUTTON_DPAD_UP,),
    pyxel.KEY_DOWN: (pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,),
    pyxel.KEY_LEFT: (pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,),
    pyxel.KEY_RIGHT: (pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT,),
    pyxel.KEY_SPACE: (pyxel.GAMEPAD1_BUTTON_A,),
    pyxel.KEY_RETURN: (pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_START),
    pyxel.KEY_X: (pyxel.GAMEPAD1_BUTTON_B,),
    pyxel.KEY_C: (pyxel.GAMEPAD1_BUTTON_X,),
    pyxel.KEY_Z: (pyxel.GAMEPAD1_BUTTON_Y,),
    pyxel.KEY_ESCAPE: (pyxel.GAMEPAD1_BUTTON_BACK,),
}


def _wrap(fn):
    def wrapped(key, *args, **kwargs):
        if fn(key, *args, **kwargs):
            return True
        return any(fn(b, *args, **kwargs) for b in _PAD.get(key, ()))
    return wrapped


def install_gamepad():
    """envuelve btn/btnp una sola vez. llamar antes de que corra el juego."""
    if getattr(pyxel, "_mhw_pad", False):
        return
    pyxel.btn = _wrap(pyxel.btn)
    pyxel.btnp = _wrap(pyxel.btnp)
    pyxel._mhw_pad = True
