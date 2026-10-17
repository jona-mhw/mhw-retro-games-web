"""letras grandes: la fuente de pyxel escalada, para carteles y números del HUD.

la fuente de pyxel mide 3x5 por letra y en un teléfono (~1.2-1.7x) se lee
apenas. los carteles que importan (¡SMASH!, el tanteo, la cuenta final) van
al doble o al triple. cada glifo se lee una sola vez de la fuente de pyxel
(dibujándolo en una imagen chica y mirando qué píxeles prendió) y queda en
caché como lista de puntos; después dibujar es un rect por punto.

entiende tildes, la ñ y los signos de apertura ¡ ¿, que la fuente no trae.
vive en la carpeta del juego (no en pixelkit) a propósito: pixelkit lo edita
otro y esto es chico.
"""
import pyxel

from pixelkit import fx as _fx
from pixelkit.pxtext import text

_BASE = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "Á": "A", "É": "E",
         "Í": "I", "Ó": "O", "Ú": "U", "ñ": "n", "Ñ": "N", "ü": "u", "Ü": "U"}
_TILDE = set("ñÑ")
_DIER = set("üÜ")
_CACHE = {}
_IMG = None


def _glifo(ch):
    g = _CACHE.get(ch)
    if g is not None:
        return g
    global _IMG
    if _IMG is None:
        _IMG = pyxel.Image(4, 6)
    if ch in "¡¿":                       # el signo de cierre, dado vuelta
        _IMG.cls(0)
        _IMG.text(0, 0, "!" if ch == "¡" else "?", 1)
        pts = [(x, 4 - y) for y in range(5) for x in range(4)
               if _IMG.pget(x, y) == 1]
        if ch == "¿":
            pts = [(2 - x, y) for x, y in pts]
    else:
        _IMG.cls(0)
        _IMG.text(0, 0, _BASE.get(ch, ch), 1)
        pts = [(x, y) for y in range(6) for x in range(4)
               if _IMG.pget(x, y) == 1]
        if ch in _BASE:
            if ch in _TILDE:
                pts += [(0, -2), (1, -2), (2, -2)]
            elif ch in _DIER:
                pts += [(0, -2), (2, -2)]
            else:
                pts += [(1, -2), (2, -2)]
    _CACHE[ch] = pts
    return pts


def ancho(s, k=2):
    return len(s) * 4 * k - k


def big(x, y, s, col, k=2, sombra=None):
    """`s` a escala k desde (x, y). con `sombra`, un calco corrido abajo a la
    derecha: sobre la cancha es lo que lo despega del fondo."""
    rect = pyxel.rect
    x, y = int(x), int(y)
    if k == 1:
        # a escala 1 la fuente de pyxel ya sirve (y es mucho más barata): sólo
        # los signos de apertura van a mano
        llano = s.replace("¡", " ").replace("¿", " ")
        for capa, c in ((1, sombra), (0, col)):
            if c is None:
                continue
            text(x + capa, y + capa, llano, c)
            if llano != s:
                for i, ch in enumerate(s):
                    if ch in "¡¿":
                        for gx, gy in _glifo(ch):
                            pyxel.pset(x + capa + i * 4 + gx, y + capa + gy, c)
        return
    for capa, c in ((1, sombra), (0, col)):
        if c is None:
            continue
        cx = x + capa * max(1, k // 2)
        cy = y + capa * max(1, k // 2)
        for ch in s:
            if ch != " ":
                for gx, gy in _glifo(ch):
                    rect(cx + gx * k, cy + gy * k, k, k, c)
            cx += 4 * k


def cbig(cx, y, s, col, k=2, sombra=None):
    """centrado en cx."""
    big(cx - ancho(s, k) / 2, y, s, col, k, sombra)


class Fx(_fx.Fx):
    """el Fx de pixelkit, con los carteles chicos dibujados acá: con sombra
    (sobre la cancha se despegan del fondo) y con ¡ ¿, que la fuente no trae."""

    def __init__(self, *a, sombra=0, **kw):
        super().__init__(*a, **kw)
        self.sombra = sombra

    def draw(self, camx=0, camy=0):
        # las chispas las dibuja pixelkit; los carteles, acá. si algún día
        # cambia la forma de `pops`, se cae al dibujo de siempre.
        pops, self.pops = self.pops, []
        try:
            super().draw(camx, camy)
        finally:
            self.pops = pops
        try:
            for q in pops:
                x, y, s, col, vida, vida0 = q[0], q[1], q[3], q[4], q[5], q[6]
                if vida < vida0 * 0.35 and (self.t // 3) % 2:
                    continue                   # titila justo antes de irse
                # que no se corte contra el borde de la pantalla
                half = len(s) * 2 + 1
                x = max(camx + half, min(camx + pyxel.width - half, x))
                cbig(x - camx, int(y - camy), s, col, k=1, sombra=self.sombra)
        except (TypeError, ValueError, IndexError):
            parts, self.parts = self.parts, []
            super().draw(camx, camy)
            self.parts = parts
