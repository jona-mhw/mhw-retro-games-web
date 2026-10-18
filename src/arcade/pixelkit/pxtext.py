"""texto con tildes en la fuente de pyxel, que sólo trae ASCII.

la fuente bitmap de pyxel no tiene á é í ó ú ñ ü: escribís "crédito" y sale
"cr dito". acá dibujamos la letra base y le estampamos el acento como pixeles
encima. así el español queda con sus tildes sin cambiar de fuente. es una
técnica de siempre en el pixel art; cualquier juego en español la necesita.
"""
import pyxel

CW = 4  # la fuente de pyxel avanza 4 px por carácter

_ACUTE = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
          "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}
_DIER = {"ü": "u", "Ü": "U"}
_TILDE = {"ñ": "n", "Ñ": "N"}
_MIDDOT = "·"     # punto medio: tampoco está en la fuente, lo dibujamos suelto
# los signos de apertura, que la fuente tampoco trae: se dibujan enteros, el
# "!" y el "?" de pyxel dados vuelta (3x5, una fila por cadena)
_GLYPHS = {
    "¡": (".X.", "...", ".X.", ".X.", ".X."),
    "¿": (".X.", "...", ".X.", "X..", ".XX"),
}


def text(x, y, s, col, target=pyxel):
    """como pyxel.text pero entendiendo tildes, diéresis, la ñ, ¡ ¿ y el punto
    medio. `target` puede ser una pyxel.Image (dibuja ahí en vez de la pantalla)."""
    base = []
    marks = []
    for i, ch in enumerate(s):
        if ch in _ACUTE:
            base.append(_ACUTE[ch]); marks.append((i, "acute"))
        elif ch in _TILDE:
            base.append(_TILDE[ch]); marks.append((i, "tilde"))
        elif ch in _DIER:
            base.append(_DIER[ch]); marks.append((i, "dier"))
        elif ch == _MIDDOT:
            base.append(" "); marks.append((i, "middot"))
        elif ch in _GLYPHS:
            base.append(" "); marks.append((i, ch))
        else:
            base.append(ch)
    target.text(x, y, "".join(base), col)
    for i, kind in marks:
        gx = x + i * CW
        if kind == "acute":
            target.pset(gx + 2, y - 3, col)
            target.pset(gx + 1, y - 2, col)
        elif kind == "dier":
            target.pset(gx, y - 2, col)
            target.pset(gx + 2, y - 2, col)
        elif kind == "middot":
            target.pset(gx + 1, y + 2, col)
        elif kind in _GLYPHS:
            for gy, row in enumerate(_GLYPHS[kind]):
                for dx, px in enumerate(row):
                    if px == "X":
                        target.pset(gx + dx, y + gy, col)
        else:  # tilde de la ñ
            target.pset(gx, y - 2, col)
            target.pset(gx + 1, y - 3, col)
            target.pset(gx + 2, y - 2, col)


def text_width(s):
    """ancho en px de una cadena con esta fuente."""
    return len(s) * CW


def ctext(cx, y, s, col):
    """texto centrado en cx."""
    text(int(cx - len(s) * CW / 2), y, s, col)


# --- texto grande ----------------------------------------------------------
# la fuente de pyxel mide 4x6: en el celular un número de 6 px se lee mal. el
# texto grande se escribe una vez en una imagen chica y se estampa agrandado
# con blt(scale=...), que es un solo dibujo por cadena. se guarda en caché
# por (texto, color), así un marcador que cambia poco no cuesta nada.
_BIG = {}
_BIG_MAX = 96


def _big_image(s, col):
    """(imagen, color transparente) con la cadena escrita."""
    hit = _BIG.get((s, col))
    if hit is None:
        if len(_BIG) >= _BIG_MAX:
            _BIG.clear()
        # 3 filas extra arriba: los acentos y la tilde de la ñ suben 3 px. el
        # alto par deja el estampado alineado a píxeles enteros
        img = pyxel.Image(max(1, len(s) * CW), 10)
        key = 1 if col == 0 else 0
        img.cls(key)
        text(0, 3, s, col, target=img)
        hit = _BIG[(s, col)] = (img, key)
    return hit


def big_text(x, y, s, col, scale=2, shadow=None):
    """texto `scale` veces más grande, con su esquina de arriba en (x, y) (la
    línea de base queda donde la dejaría text(); los acentos asoman encima).
    `shadow`: color de una sombra corrida 1 píxel de pantalla abajo a la derecha."""
    if not s:
        return
    if shadow is not None:
        _stamp(x + 1, y + 1, _big_image(s, shadow), scale)
    _stamp(x, y, _big_image(s, col), scale)


def _stamp(x, y, hit, scale):
    # blt escala alrededor del centro de la región: se corre para que la
    # esquina de arriba quede en (x, y). la imagen tiene 3 filas de margen
    # arriba para los acentos.
    img, key = hit
    w, h = img.width, img.height
    bx = x + w * (scale - 1) // 2
    by = y - 3 * scale + h * (scale - 1) // 2
    pyxel.blt(bx, by, img, 0, 0, w, h, key, scale=scale)


def big_width(s, scale=2):
    """ancho en px de big_text(s, scale)."""
    return len(s) * CW * scale


def big_ctext(cx, y, s, col, scale=2, shadow=None):
    """big_text centrado en cx."""
    big_text(int(cx - len(s) * CW * scale / 2), y, s, col, scale, shadow)
