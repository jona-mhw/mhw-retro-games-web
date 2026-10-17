"""pixelkit — lo que sirve para CUALQUIER juego pixel art del arcade.

no es un motor: es el puñado de cosas que de verdad se repiten entre juegos de
pyxel con framebuffer indexado. tres piezas y un descubridor:

    palette   paletas de 256 colores donde el byte de cada celda ES el color
    blit      copiar ese bytearray al framebuffer de una sola vez + medir fps
    capture   volcar el framebuffer a PNG sin abrir ventana (para mirar bugs)
    registry  encontrar los juegos de games/ leyendo su game.toml

lo específico de un juego (su física, sus materiales, su lógica) vive en
games/<id>/, no acá. si algo sólo le sirve a un juego, no es de pixelkit.
"""

from pixelkit.palette import Palette, shades
from pixelkit.blit import FpsMeter, blit_slow, fast_blit

__all__ = ["Palette", "shades", "FpsMeter", "fast_blit", "blit_slow"]
