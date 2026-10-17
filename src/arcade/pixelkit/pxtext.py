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


def text(x, y, s, col):
    """como pyxel.text pero entendiendo tildes, diéresis, la ñ y el punto medio."""
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
        else:
            base.append(ch)
    pyxel.text(x, y, "".join(base), col)
    for i, kind in marks:
        gx = x + i * CW
        if kind == "acute":
            pyxel.pset(gx + 2, y - 3, col)
            pyxel.pset(gx + 1, y - 2, col)
        elif kind == "dier":
            pyxel.pset(gx, y - 2, col)
            pyxel.pset(gx + 2, y - 2, col)
        elif kind == "middot":
            pyxel.pset(gx + 1, y + 2, col)
        else:  # tilde de la ñ
            pyxel.pset(gx, y - 2, col)
            pyxel.pset(gx + 1, y - 3, col)
            pyxel.pset(gx + 2, y - 2, col)


def text_width(s):
    """ancho en px de una cadena con esta fuente."""
    return len(s) * CW


def ctext(cx, y, s, col):
    """texto centrado en cx."""
    text(int(cx - len(s) * CW / 2), y, s, col)
