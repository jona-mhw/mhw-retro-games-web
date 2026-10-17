"""el jugo: lo que hace que un golpe se sienta como un golpe.

chispas, números que suben, temblor de pantalla y destellos. es la diferencia
entre "la nave tocó el bloque y el score cambió" y que se sienta un choque.
como se repite en los cinco juegos, vive acá y no en cada uno.

    self.fx = Fx()                       # en el World
    ...
    self.fx.burst(x, y, (ROJO, NARANJA, AMARILLO), n=14)
    self.fx.popup(x, y, "+50", ORO)
    self.fx.shake(4)
    ...
    self.fx.update()                     # un frame
    dx, dy = self.fx.offset()            # el temblor, para la cámara
    ...
    self.fx.draw(camx, camy)             # al final del draw del mundo

**nada de esto toca la paleta.** el crt se arma una vez contra la paleta del
juego y la cachea: cambiar `pyxel.colors` en caliente le deja la tabla vieja y
las dos intensidades se rompen. por eso el destello se dibuja (un rect con
dither encima) y el temblor se hace corriendo el origen de dibujo con
`pyxel.camera`, nunca moviendo el framebuffer ya pintado.

la lógica (posiciones, vidas, decaimiento) no importa pyxel: se testea sin
ventana. sólo `draw()` dibuja.
"""
import math

import pyxel

from pixelkit.pxtext import ctext

# el temblor recorre esta vuelta de direcciones: siempre la misma, así una
# prueba puede predecir el offset. al ojo se lee igual de aleatorio.
_JITTER = ((1, 0), (-1, 1), (0, -1), (1, 1), (-1, -1), (0, 1), (1, -1), (-1, 0))

# el destello: corto y flojo, y hay motivo. `pyxel.dither` sortea los píxeles
# con una matriz de Bayer y el escalón más chico ya pinta uno de cada ocho: un
# color vivo al 12% sobre un fondo oscuro NO se lee como un fogonazo, se lee
# como si el juego entero hubiera cambiado de color. la primera versión teñía
# al 30% durante 12 frames y la ciudad de autos quedaba roja media pantalla.
# lo que funciona es al revés: 4 frames, apenas, y que el golpe lo pongan las
# chispas y el temblor.
FLASH_ALPHA = 0.12
FLASH_FRAMES = 4


class Fx:
    """el jugo de un juego: chispas, carteles y temblor, todo junto."""

    def __init__(self, gravity=0.12, max_parts=220):
        self.parts = []        # [x, y, vx, vy, vida, vida0, rampa]
        self.pops = []         # [x, y, vy, texto, col, vida, vida0]
        self.mag = 0.0         # cuánto tiembla ahora mismo
        self.t = 0
        self.gravity = gravity
        self.max_parts = max_parts
        self.fl = 0            # frames que le quedan al destello
        self.fl0 = 1
        self.fl_col = 0

    # --- pedir efectos ---------------------------------------------------
    def burst(self, x, y, ramp, n=10, speed=1.6, life=22, spread=math.tau,
              angle=0.0, gravity=None):
        """un estallido de chispas desde (x, y).

        `ramp` son los colores del más vivo al más apagado: la chispa los va
        recorriendo mientras se muere, que es lo que la hace parecer una brasa
        y no un cuadrado de color fijo. `spread`/`angle` acotan el abanico (un
        chorro de escape sale hacia atrás, una explosión sale para todos lados).
        """
        ramp = tuple(ramp)
        if not ramp:
            return
        libre = self.max_parts - len(self.parts)
        for i in range(min(n, max(0, libre))):
            a = angle + (i / max(1, n) - 0.5) * spread
            v = speed * (0.45 + 0.55 * ((i * 37) % 11) / 10.0)   # velocidades variadas
            self.parts.append([float(x), float(y), math.cos(a) * v,
                               math.sin(a) * v, life, life, ramp,
                               self.gravity if gravity is None else gravity])

    def popup(self, x, y, s, col, life=38, vy=-0.55):
        """un cartelito que sube y se desvanece: "+50", "¡COMBO x3!"."""
        self.pops.append([float(x), float(y), vy, s, col, life, life])

    def shake(self, mag):
        """sacude la pantalla. se queda con el golpe más fuerte pendiente."""
        self.mag = max(self.mag, float(mag))

    def destello(self, col, frames=FLASH_FRAMES):
        """tiñe la pantalla un instante. corto a propósito, ver `flash()`."""
        if frames >= self.fl:
            self.fl = self.fl0 = max(1, frames)
            self.fl_col = col

    def clear(self):
        self.parts.clear()
        self.pops.clear()
        self.mag = 0.0
        self.fl = 0

    # --- avanzar ---------------------------------------------------------
    def update(self):
        self.t += 1
        vivos = []
        for p in self.parts:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += p[7]
            p[2] *= 0.96
            p[4] -= 1
            if p[4] > 0:
                vivos.append(p)
        self.parts = vivos
        vivas = []
        for q in self.pops:
            q[1] += q[2]
            q[2] *= 0.94
            q[5] -= 1
            if q[5] > 0:
                vivas.append(q)
        self.pops = vivas
        self.mag *= 0.82
        if self.mag < 0.35:
            self.mag = 0.0
        if self.fl:
            self.fl -= 1

    def offset(self):
        """el desplazamiento del temblor, en píxeles enteros."""
        if not self.mag:
            return 0, 0
        jx, jy = _JITTER[self.t % len(_JITTER)]
        m = int(round(self.mag))
        return jx * m, jy * m

    # --- dibujar ---------------------------------------------------------
    def draw_flash(self, x=0, y=0, w=None, h=None):
        """el destello pendiente, si lo hay. va al final, sobre todo lo demás."""
        if self.fl:
            flash(self.fl_col, FLASH_ALPHA * self.fl / self.fl0, x, y, w, h)

    def draw(self, camx=0, camy=0):
        """chispas y carteles, en coordenadas de mundo menos la cámara."""
        for x, y, _, _, vida, vida0, ramp, _ in self.parts:
            i = int((1.0 - vida / vida0) * len(ramp))
            pyxel.pset(int(x - camx), int(y - camy), ramp[min(i, len(ramp) - 1)])
        for x, y, _, s, col, vida, vida0 in self.pops:
            if vida < vida0 * 0.35 and (self.t // 3) % 2:
                continue                       # titila justo antes de irse
            ctext(x - camx, int(y - camy), s, col)


def flash(col, alpha=0.5, x=0, y=0, w=None, h=None):
    """tiñe la pantalla (o un rectángulo) sin tocar la paleta.

    `pyxel.dither` sortea qué píxeles se pintan, así que un rect encima del
    frame ya dibujado tiñe de a poco en vez de taparlo. hay que devolver el
    dither a 1.0 o todo lo que se dibuje después sale agujereado.
    """
    w = pyxel.width if w is None else w
    h = pyxel.height if h is None else h
    pyxel.dither(max(0.0, min(1.0, alpha)))
    pyxel.rect(x, y, w, h, col)
    pyxel.dither(1.0)


def bar(x, y, w, h, frac, col, bg, border=None):
    """una barra de progreso: vida, turbo, tiempo. `frac` va de 0 a 1."""
    frac = max(0.0, min(1.0, frac))
    pyxel.rect(x, y, w, h, bg)
    if frac > 0:
        pyxel.rect(x, y, max(1, int(w * frac)), h, col)
    if border is not None:
        pyxel.rectb(x, y, w, h, border)
