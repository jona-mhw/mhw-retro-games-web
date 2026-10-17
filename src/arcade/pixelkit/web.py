"""el cabinet en el navegador: lo que cambia cuando pyxel corre en pyodide.

en el escritorio cada juego es un proceso y el disco los une. en la web no hay
procesos ni disco que sobreviva a un reload, así que:

- **lanzar un juego es navegar**: `?game=<id>` en la misma página. el arranque
  (main.py) lee la url y bootea el juego o el menú. salir de un juego vuelve al
  menú, que es la página sin parámetros.
- **lo persistente va a localStorage**: config y récords se guardan con la misma
  clave que el archivo json del escritorio, así el resto de pixelkit no se entera.
- **el gamepad cuenta como teclado**: en el celular pyxel dibuja una cruceta y
  botones virtuales, pero los juegos leen flechas y espacio. acá se envuelven
  btn/btnp para que la cruceta valga por flechas y los botones por las teclas
  que usa cada juego. también sirve con un joystick de verdad.

fuera del navegador (ACTIVE False) todo esto no hace nada.
"""
import sys

import pyxel

ACTIVE = sys.platform == "emscripten"
PREFIX = "mhw-arcade:"

if ACTIVE:
    import js


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


def launch(game_id):
    """bootea un juego: recarga la página apuntando a él."""
    js.window.location.search = "?game=" + game_id


def to_menu():
    """vuelve al menú del cabinet: la misma página, sin parámetros."""
    loc = js.window.location
    loc.href = loc.pathname


def quit():
    """lo que en el escritorio es pyxel.quit(): en la web, volver al menú."""
    if ACTIVE:
        to_menu()
    else:
        pyxel.quit()


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
