"""los carteles chicos del jugo (+15, ¡DEVUELTO!, ¿llega?), en letra grande.

el Fx de pixelkit escribe sus popups con la fuente de 4x6, que en el celular
se lee apenas. acá se dibujan con el texto grande de `pixelkit.pxtext` (al
doble, con sombra), y sin cortarse contra el borde de la pantalla. las
chispas las sigue dibujando pixelkit.
"""
import pyxel

from pixelkit import fx as _fx
from pixelkit.pxtext import big_ctext, big_width


class Fx(_fx.Fx):
    def __init__(self, *a, sombra=0, escala=2, **kw):
        super().__init__(*a, **kw)
        self.sombra = sombra
        self.escala = escala

    def draw(self, camx=0, camy=0):
        pops, self.pops = self.pops, []
        try:
            super().draw(camx, camy)
        finally:
            self.pops = pops
        for q in pops:
            x, y, s, col, vida, vida0 = q[0], q[1], q[3], q[4], q[5], q[6]
            if vida < vida0 * 0.35 and (self.t // 3) % 2:
                continue                       # titila justo antes de irse
            k = self.escala if len(s) * 4 * self.escala <= pyxel.width - 8 else 1
            half = big_width(s, k) // 2 + 2
            x = max(camx + half, min(camx + pyxel.width - half, x))
            big_ctext(x - camx, int(y - camy), s, col, scale=k,
                      shadow=self.sombra)
