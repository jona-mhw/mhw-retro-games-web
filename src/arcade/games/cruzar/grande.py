"""los carteles que suben ("+100", "¡PLAF!"), con sombra y a dos tamaños.

el Fx de pixelkit dibuja sus carteles con la fuente chica, sin sombra: sobre
la calle se pierden y en el celular se leen mal. éste los dibuja con el texto
grande de pixelkit (`big_ctext`), con sombra, y deja elegir el tamaño por
cartel: `popup(..., k=2)` para lo que importa, `k=1` para lo de paso.

vive en la carpeta del juego a propósito: pixelkit lo edita otro y esto es
chico.
"""
import pyxel

from pixelkit import fx as _fx
from pixelkit.pxtext import big_ctext, ctext


class Fx(_fx.Fx):
    def __init__(self, *a, sombra=0, **kw):
        super().__init__(*a, **kw)
        self.sombra = sombra

    def popup(self, x, y, s, col, life=38, vy=-0.55, k=1):
        # el tamaño va como octavo campo: pixelkit sólo mira los siete primeros
        self.pops.append([float(x), float(y), vy, s, col, life, life, k])

    def draw(self, camx=0, camy=0):
        pops, self.pops = self.pops, []
        try:
            super().draw(camx, camy)          # las chispas
        finally:
            self.pops = pops
        for q in pops:
            x, y, s, col, vida, vida0 = q[0], q[1], q[3], q[4], q[5], q[6]
            k = q[7] if len(q) > 7 else 1
            if vida < vida0 * 0.35 and (self.t // 3) % 2:
                continue                       # titila justo antes de irse
            half = len(s) * 2 * k + 2          # que no se corte en el borde
            x = max(camx + half, min(camx + pyxel.width - half, x))
            if k == 1:
                ctext(x - camx + 1, int(y - camy) + 1, s, self.sombra)
                ctext(x - camx, int(y - camy), s, col)
            else:
                big_ctext(x - camx + 1, int(y - camy) + 1, s, self.sombra, k)
                big_ctext(x - camx, int(y - camy), s, col, k)
