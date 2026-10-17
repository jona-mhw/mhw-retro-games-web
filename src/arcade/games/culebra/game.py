"""culebra — el snake, pero con hambre, poderes y un tablero que se ensucia.

lo de siempre: comés, crecés, acelerás y no te mordés. lo que le agregamos:

- **hambre**: hay un reloj que baja siempre. cada manzana te da aire, pero el
  aire total que podés recuperar está acotado, así que la partida entra en el
  minuto y medio pase lo que pase. deja de ser "a ver cuánto aguanto" y pasa a
  ser "cuánto junto antes de que se acabe".
- **la dorada**: una fruta que aparece lejos, vale por cinco y se va sola. es la
  decisión de cada partida: ¿la voy a buscar o me quedo con lo seguro?
- **poderes**: el fantasma te deja atravesarte unos segundos; la tijera te corta
  la cola por la mitad cuando ya sos demasiado larga.
- **muros**: desde el nivel 3, el tablero empieza a ensuciarse con bloques.
- **racha**: comer una manzana poco después de la anterior la encadena. cada
  tres seguidas la manzana vale una más (hasta x3). dejar pasar el tiempo la
  enfría. comer rápido paga, pero sube de nivel antes — y el nivel acelera.
- **el ají**: aparece cada tanto, vale por tres y te mete turbo cuatro
  segundos. es plata fácil con un precio: ir más rápido de lo que querés.

toda la mecánica vive en la clase Culebra, sin pyxel: `frame()` avanza un frame
y devuelve qué pasó. World la juega y la dibuja; el Cabinet le pone título,
attract y récords.
"""
import math
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

CELL = 8
COLS, ROWS = 32, 26
HUD = 16
W, H = COLS * CELL, HUD + ROWS * CELL   # 256 x 224

HAMBRE = 30 * 60                 # con lo que arrancás
EXTRA_MAX = 60 * 60              # y lo máximo que te pueden devolver las frutas
MANZANA_AIRE = 3 * 60
DORADA_AIRE = 2 * 60
DORADA_VALE = 5
DORADA_TTL = 6 * 60              # lo que se queda antes de irse
DORADA_GAP = 8 * 60              # cada cuánto vuelve a asomar
PODER_GAP = 11 * 60
PODER_TTL = 8 * 60
FANTASMA_TTL = 6 * 60
MUROS_DESDE = 3                  # nivel en que el tablero empieza a ensuciarse
PORTALES_DESDE = 2               # y en que se abre el par de portales
PORTAL_TTL = 14 * 60             # lo que dura un par antes de mudarse

FANTASMA, TIJERA = range(2)
PODER_NOMBRE = {FANTASMA: "¡FANTASMA!", TIJERA: "¡TIJERA!"}

# la racha: manzanas encadenadas. techo en x3, que con manzanas de a uno ya
# dispara el nivel (y la velocidad) bastante más rápido que jugando tranquilo.
RACHA_TTL = 4 * 60
RACHA_CADA = 3
RACHA_MAX = 3

# el ají: vale por tres y te acelera un rato. aparece menos que el poder.
AJI_GAP = 13 * 60
AJI_TTL = 7 * 60
AJI_VALE = 3
AJI_TURBO = 4 * 60

(BG, GRID, FRAME, BODY0, BODY1, HEAD, APPLE, APPLE2, TXT, DIM, TEAL,
 AMBER, SHADOW, GREEN, RED, WHITE,
 GOLD, GOLD2, GHOST1, GHOST2, WALL, WALL2, MAGENTA, ORANGE) = range(24)
PAL = [
    0x0C0E14, 0x141926, 0x2A3350, 0x4B7A18, 0x8AC52F, 0xB6F03C, 0xE0402A,
    0xFF7A54, 0xE8ECF5, 0x5A6480, 0x27969E, 0xFFC24A, 0x070810, 0x8AC52F,
    0xE0402A, 0xF2F5FB,
    0xFFD24A, 0xFFF3B0, 0x7ADCFF, 0x2E7FBF, 0x6E6A82, 0x39435E, 0xD84AB8,
    0xE0842E,
] + [0] * (256 - 24)

CHISPA_MANZANA = (WHITE, APPLE2, APPLE, BODY0)
CHISPA_DORADA = (WHITE, GOLD2, GOLD, AMBER)
CHISPA_PODER = (WHITE, GHOST1, GHOST2, TEAL)


class Culebra:
    """estado y reglas del snake. sin pyxel: testeable de a de veras.

    `step()` es un movimiento de celda (como siempre) y `frame()` es un frame
    de reloj: baja el hambre, hace aparecer y caducar las frutas, y llama a
    `step()` cuando toca. los tests de duración corren `frame()`.
    """

    def __init__(self, cols=COLS, rows=ROWS, rng=None):
        self.cols, self.rows = cols, rows
        self.rng = rng or random
        self.reset()

    def reset(self):
        cx, cy = self.cols // 2, self.rows // 2
        self.body = [(cx - i, cy) for i in range(3)]   # cabeza primero
        self.dir = (1, 0)
        self.pending = (1, 0)
        self.dead = False
        self.score = 0
        self.ate = False
        self.walls = set()
        self.gold = None            # [x, y, ttl]
        self.gold_t = DORADA_GAP
        self.power = None           # [x, y, tipo, ttl]
        self.power_t = PODER_GAP
        self.ghost = 0
        self.portales = None        # [(x1,y1), (x2,y2), ttl]
        self.racha = 0
        self.racha_t = 0
        self.aji = None             # [x, y, ttl]
        self.aji_t = AJI_GAP
        self.turbo = 0
        self.hambre = HAMBRE
        self.extra = EXTRA_MAX
        self.niv = 1
        self.t = 0
        self._place_apple()

    # --- tablero ---------------------------------------------------------
    def _libres(self, margen=0):
        """celdas donde se puede poner algo: ni cuerpo, ni muro, ni otra fruta."""
        ocupado = set(self.body) | self.walls
        if self.portales:
            ocupado.add(self.portales[0])
            ocupado.add(self.portales[1])
        if self.gold:
            ocupado.add((self.gold[0], self.gold[1]))
        if self.power:
            ocupado.add((self.power[0], self.power[1]))
        if self.aji:
            ocupado.add((self.aji[0], self.aji[1]))
        ap = getattr(self, "apple", None)
        if ap:
            ocupado.add(ap)
        hx, hy = self.body[0]
        return [(x, y) for y in range(self.rows) for x in range(self.cols)
                if (x, y) not in ocupado
                and abs(x - hx) + abs(y - hy) >= margen]

    def _place_apple(self):
        libres = self._libres()
        self.apple = self.rng.choice(libres) if libres else None

    def _place_gold(self):
        """la dorada nace lejos: si estuviera al lado no sería una decisión."""
        libres = self._libres(margen=8) or self._libres()
        if libres:
            x, y = self.rng.choice(libres)
            self.gold = [x, y, DORADA_TTL]

    def _place_power(self):
        libres = self._libres(margen=4) or self._libres()
        if libres:
            x, y = self.rng.choice(libres)
            self.power = [x, y, self.rng.randrange(2), PODER_TTL]

    def _place_aji(self):
        libres = self._libres(margen=5) or self._libres()
        if libres:
            x, y = self.rng.choice(libres)
            self.aji = [x, y, AJI_TTL]

    def mult(self):
        """cuánto vale una manzana ahora: 1, y sube cada tres encadenadas."""
        return min(RACHA_MAX, 1 + self.racha // RACHA_CADA)

    def _abrir_portales(self):
        """un par de bocas ligadas, lejos una de la otra.

        es el atajo del tablero: con muros por todos lados, meterse por un
        portal es la diferencia entre llegar a la dorada o quedarse mirándola.
        y también la forma más tonta de morir, porque salís mirando para el
        mismo lado en un rincón que no viste.
        """
        libres = self._libres(margen=5)
        if len(libres) < 2:
            return
        a = self.rng.choice(libres)
        lejos = [c for c in libres
                 if abs(c[0] - a[0]) + abs(c[1] - a[1]) > (self.cols + self.rows) // 3]
        if not lejos:
            return
        self.portales = [a, self.rng.choice(lejos), PORTAL_TTL]

    def _salida(self, celda):
        """si la celda es un portal, la boca de enfrente. si no, None."""
        if not self.portales:
            return None
        a, b, _ = self.portales
        if celda == a:
            return b
        if celda == b:
            return a
        return None

    def _ensuciar(self):
        """al subir de nivel caen dos bloques nuevos, lejos de la cabeza."""
        for _ in range(2):
            libres = self._libres(margen=6)
            if libres:
                self.walls.add(self.rng.choice(libres))

    # --- reglas ----------------------------------------------------------
    def set_dir(self, d):
        if d == (0, 0) or (d[0] == -self.dir[0] and d[1] == -self.dir[1]):
            return
        self.pending = d

    def _comer(self, cuanto, aire):
        """suma puntos y devuelve aire, descontándolo del presupuesto común.

        ojo con el `HAMBRE - self.hambre`: el aire que **no cabe** no se cobra.
        sin eso, comer con el estómago lleno quemaba presupuesto a cambio de
        nada y el que jugaba mejor terminaba antes — al revés de lo que tiene
        que premiar el juego.
        """
        self.score += cuanto
        dar = min(aire, self.extra, HAMBRE - self.hambre)
        self.extra -= dar
        self.hambre += dar

    def step(self):
        """avanza una celda. devuelve 'eat', 'dead' o None."""
        if self.dead:
            return None
        self.dir = self.pending
        hx, hy = self.body[0]
        nx, ny = hx + self.dir[0], hy + self.dir[1]
        self.ate = False
        self.porto = False
        eating = (nx, ny) == self.apple
        ocupado = set(self.body)
        if not eating:
            ocupado.discard(self.body[-1])
        salida = self._salida((nx, ny))
        if salida is not None:
            # entrar por una boca te deja en la otra, con el mismo rumbo. se
            # comprueba DESPUÉS de mirar la pared y ANTES de mirar el cuerpo:
            # el portal no te salva de morderte, sólo te cambia de lugar
            nx, ny = salida
            self.porto = True
        fuera = not (0 <= nx < self.cols and 0 <= ny < self.rows)
        chocado = (nx, ny) in self.walls or ((nx, ny) in ocupado and not self.ghost)
        if fuera or chocado:
            self.dead = True
            return 'dead'
        self.body.insert(0, (nx, ny))
        if eating:
            self._comer(self.mult(), MANZANA_AIRE)
            self.racha += 1
            self.racha_t = RACHA_TTL
            self.ate = True
            self._place_apple()
        else:
            self.body.pop()
        return 'eat' if eating else None

    def _tomar_poder(self, tipo, ev):
        if tipo == FANTASMA:
            self.ghost = FANTASMA_TTL
        else:                                 # tijera: te saca media cola
            if len(self.body) > 4:
                self.body = self.body[:max(3, len(self.body) // 2)]
        ev.append(("poder", self.body[0][0], self.body[0][1], tipo))

    def frame(self):
        """un frame de reloj. devuelve la lista de lo que pasó."""
        ev = []
        if self.dead:
            return ev
        self.t += 1
        if self.ghost:
            self.ghost -= 1
        if self.turbo:
            self.turbo -= 1
        if self.racha:
            self.racha_t -= 1
            if self.racha_t <= 0:
                if self.racha >= RACHA_CADA:
                    ev.append(("racha_fria", self.body[0][0], self.body[0][1]))
                self.racha = 0

        # el hambre no perdona
        self.hambre -= 1
        if self.hambre <= 0:
            self.hambre = 0
            self.dead = True
            ev.append(("hambre", self.body[0][0], self.body[0][1]))
            return ev

        # la dorada va y viene
        if self.gold:
            self.gold[2] -= 1
            if self.gold[2] <= 0:
                ev.append(("dorada_ida", self.gold[0], self.gold[1]))
                self.gold = None
                self.gold_t = DORADA_GAP
        else:
            self.gold_t -= 1
            if self.gold_t <= 0:
                self._place_gold()
        if self.power:
            self.power[3] -= 1
            if self.power[3] <= 0:
                self.power = None
                self.power_t = PODER_GAP
        else:
            self.power_t -= 1
            if self.power_t <= 0:
                self._place_power()
        if self.aji:
            self.aji[2] -= 1
            if self.aji[2] <= 0:
                self.aji = None
                self.aji_t = AJI_GAP
        else:
            self.aji_t -= 1
            if self.aji_t <= 0:
                self._place_aji()

        # los portales se mudan cada tanto: si fueran fijos, la ruta óptima
        # sería siempre la misma y dejarían de ser una decisión
        if self.niv >= PORTALES_DESDE:
            if self.portales:
                self.portales[2] -= 1
                if self.portales[2] <= 0:
                    self.portales = None
            else:
                self._abrir_portales()

        if self.t % self.speed() == 0:
            r = self.step()
            if r == 'dead':
                ev.append(("muerte", self.body[0][0], self.body[0][1]))
                return ev
            if r == 'eat':
                ev.append(("manzana", self.body[0][0], self.body[0][1],
                           self.mult()))
                if self.racha % RACHA_CADA == 0 and self.mult() > 1:
                    ev.append(("racha", self.body[0][0], self.body[0][1],
                               self.mult()))
            if self.porto:
                ev.append(("portal", self.body[0][0], self.body[0][1]))
            hx, hy = self.body[0]
            if self.gold and (hx, hy) == (self.gold[0], self.gold[1]):
                self._comer(DORADA_VALE, DORADA_AIRE)
                ev.append(("dorada", hx, hy))
                self.gold = None
                self.gold_t = DORADA_GAP
            if self.power and (hx, hy) == (self.power[0], self.power[1]):
                self._tomar_poder(self.power[2], ev)
                self.power = None
                self.power_t = PODER_GAP
            if self.aji and (hx, hy) == (self.aji[0], self.aji[1]):
                self.score += AJI_VALE
                self.turbo = AJI_TURBO
                ev.append(("aji", hx, hy))
                self.aji = None
                self.aji_t = AJI_GAP
            if self.level() != self.niv:
                self.niv = self.level()
                if self.niv >= MUROS_DESDE:
                    self._ensuciar()
                ev.append(("nivel", self.niv))
        return ev

    def level(self):
        return self.score // 4 + 1

    def speed(self):
        """frames por paso: arranca lento y acelera con el nivel. el ají le
        saca tres frames más, con piso en 2."""
        base = max(3, 10 - self.level())
        return max(2, base - 3) if self.turbo else base


class World:
    """la culebra jugándose: input, dibujo y chispas. el Cabinet la envuelve."""

    def __init__(self):
        self.g = Culebra()
        self.fx = fx.Fx(gravity=0.0)
        self.fx.destello(WHITE)
        self.levelflash = 0
        self.eatflash = 0

    @property
    def over(self):
        return self.g.dead

    @property
    def score(self):
        return self.g.score

    def _px(self, cx, cy):
        return cx * CELL + CELL / 2, HUD + cy * CELL + CELL / 2

    def update(self):
        g = self.g
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            g.set_dir((0, -1))
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            g.set_dir((0, 1))
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A):
            g.set_dir((-1, 0))
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D):
            g.set_dir((1, 0))
        for e in g.frame():
            self._efecto(e)
        self.levelflash = max(0, self.levelflash - 1)
        self.eatflash = max(0, self.eatflash - 1)
        self.fx.update()

    def _efecto(self, e):
        kind = e[0]
        if kind == "manzana":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_MANZANA, n=10, speed=1.3, life=18)
            self.eatflash = 4
            if len(e) > 3 and e[3] > 1:
                self.fx.popup(x, y - 6, "+%d" % e[3], AMBER, life=24)
        elif kind == "racha":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 14, "¡RACHA x%d!" % e[3], GOLD)
            self.fx.destello(AMBER)
        elif kind == "racha_fria":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 10, "racha fría", DIM)
        elif kind == "aji":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, ORANGE, RED, APPLE), n=22, speed=2.2,
                          life=26)
            self.fx.popup(x, y - 8, "¡AJÍ! +%d" % AJI_VALE, ORANGE)
            self.fx.destello(ORANGE)
            self.fx.shake(3)
        elif kind == "dorada":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_DORADA, n=24, speed=2.2, life=30)
            self.fx.popup(x, y - 8, "+%d" % DORADA_VALE, GOLD)
            self.fx.destello(GOLD)
            self.fx.shake(2)
        elif kind == "poder":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_PODER, n=20, speed=2.0, life=28)
            self.fx.popup(x, y - 8, PODER_NOMBRE[e[3]], GHOST1)
            self.fx.destello(GHOST1)
        elif kind == "portal":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, MAGENTA, GHOST1, GHOST2), n=12,
                          speed=1.6, life=18)
        elif kind == "nivel":
            self.levelflash = 24
            if e[1] >= MUROS_DESDE:
                self.fx.popup(W / 2, H / 2, "¡MUROS!", MAGENTA)
        elif kind in ("muerte", "hambre"):
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, RED, APPLE2, BODY0), n=30, speed=2.4,
                          life=34)
            self.fx.shake(5)
            self.fx.destello(RED)

    def _cell(self, cx, cy, col):
        pyxel.rect(cx * CELL, HUD + cy * CELL, CELL, CELL, col)

    def draw(self):
        g = self.g
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)                    # el temblor, sin tocar el frame
        for y in range(ROWS):
            for x in range(COLS):
                if (x + y) & 1:
                    pyxel.rect(x * CELL, HUD + y * CELL, CELL, CELL, GRID)
        for wx, wy in g.walls:                    # los muros, con relieve
            px, py = wx * CELL, HUD + wy * CELL
            pyxel.rect(px, py, CELL, CELL, WALL)
            pyxel.rect(px, py, CELL, 1, WALL2)
            pyxel.rect(px, py + CELL - 1, CELL, 1, SHADOW)
        if g.apple:
            ax, ay = g.apple
            self._cell(ax, ay, APPLE if self.eatflash == 0 else APPLE2)
            pyxel.rect(ax * CELL + 2, HUD + ay * CELL + 1, 2, 2, APPLE2)
        if g.portales:
            self._portales(g.portales)
        if g.gold:
            self._dorada(g.gold)
        if g.power:
            self._poder(g.power)
        if g.aji:
            self._aji(g.aji)
        self._culebra(g)
        self.fx.draw(0, HUD)
        pyxel.camera()
        self.fx.draw_flash(0, HUD, W, H - HUD)
        self._hud()

    def _portales(self, portales):
        """las dos bocas, girando en sentidos opuestos para que se lean ligadas."""
        a, b, ttl = portales
        for k, (px_, py_) in enumerate((a, b)):
            if ttl < 120 and (pyxel.frame_count // 4) % 2:
                return
            cx, cy = px_ * CELL + CELL // 2, HUD + py_ * CELL + CELL // 2
            col = GHOST1 if k == 0 else MAGENTA
            for i in range(4):
                ang = pyxel.frame_count * (0.14 if k == 0 else -0.14) + i * math.pi / 2
                pyxel.pset(int(cx + math.cos(ang) * 3), int(cy + math.sin(ang) * 3),
                           col)
            pyxel.pset(cx, cy, WHITE)

    def _dorada(self, gold):
        gx, gy, ttl = gold
        px, py = gx * CELL + CELL // 2, HUD + gy * CELL + CELL // 2
        if ttl < 90 and (pyxel.frame_count // 4) % 2:      # titila antes de irse
            return
        r = 3 + (pyxel.frame_count // 6) % 2
        pyxel.circ(px, py, r, GOLD)
        pyxel.circ(px, py, r - 2, GOLD2)
        for i in range(4):                                  # destellos en cruz
            a = pyxel.frame_count * 0.1 + i * math.pi / 2
            pyxel.pset(int(px + 5 * math.cos(a)), int(py + 5 * math.sin(a)), GOLD2)

    def _poder(self, power):
        px_, py_, tipo, ttl = power
        px, py = px_ * CELL, HUD + py_ * CELL
        if ttl < 90 and (pyxel.frame_count // 4) % 2:
            return
        col = GHOST1 if tipo == FANTASMA else MAGENTA
        pyxel.rectb(px, py, CELL, CELL, col)
        if tipo == FANTASMA:                                # una sabanita
            pyxel.rect(px + 2, py + 2, 4, 3, col)
            pyxel.pset(px + 2, py + 5, col)
            pyxel.pset(px + 4, py + 5, col)
        else:                                               # una tijera
            pyxel.line(px + 2, py + 2, px + 5, py + 5, col)
            pyxel.line(px + 5, py + 2, px + 2, py + 5, col)

    def _aji(self, aji):
        ax, ay, ttl = aji
        px, py = ax * CELL, HUD + ay * CELL
        if ttl < 90 and (pyxel.frame_count // 4) % 2:
            return
        # un ají: rojo, curvo, con el cabito verde arriba
        pyxel.rect(px + 3, py + 2, 2, 5, RED)
        pyxel.rect(px + 4, py + 5, 2, 2, RED)
        pyxel.pset(px + 3, py + 2, ORANGE)
        pyxel.pset(px + 4, py + 1, GREEN)
        pyxel.pset(px + 3, py + 1, BODY1)

    def _culebra(self, g):
        n = len(g.body)
        fantasma = g.ghost and (pyxel.frame_count // 3) % 2
        for i, (cx, cy) in enumerate(g.body):
            col = HEAD if i == 0 else (BODY1 if i < n * 0.5 else BODY0)
            if g.ghost:
                col = GHOST1 if fantasma else GHOST2
            elif g.turbo and (pyxel.frame_count // 2) % 2:
                col = ORANGE if i else RED          # con el ají, arde
            px, py = cx * CELL, HUD + cy * CELL
            pyxel.rect(px, py, CELL, CELL, col)
            pyxel.rect(px, py, CELL, 1, WHITE if i == 0 else BODY1)
        hx, hy = g.body[0]
        ex, ey = hx * CELL, HUD + hy * CELL
        dx, dy = g.dir
        pyxel.rect(ex + 2 + dx, ey + 2 + dy, 2, 2, SHADOW)
        pyxel.rect(ex + CELL - 4 + dx, ey + 2 + dy, 2, 2, SHADOW)

    def _hud(self):
        g = self.g
        pyxel.rect(0, 0, W, HUD, SHADOW)
        pyxel.rect(0, HUD, W, 1, FRAME)
        text(4, 5, "%d" % g.score, GREEN)
        # la barra de hambre: es el reloj de la partida, así que manda en el hud
        frac = g.hambre / HAMBRE
        col = RED if frac < 0.25 and (pyxel.frame_count // 8) % 2 else AMBER
        text(30, 5, "hambre", DIM)
        fx.bar(62, 6, 60, 5, frac, col, GRID, FRAME)
        if g.ghost:
            text(130, 5, "fantasma", GHOST1)
        elif g.turbo:
            text(130, 5, "turbo", ORANGE if (pyxel.frame_count // 4) % 2 else RED)
        m = g.mult()
        if m > 1:
            col = GOLD if (pyxel.frame_count // 6) % 2 else AMBER
            text(14 + len("%d" % g.score) * 4, 5, "x%d" % m, col)
        r = "nivel %d" % g.level()
        text(W - len(r) * 4 - 4, 5, r, WHITE if self.levelflash > 0 else AMBER)


class Game:
    def __init__(self):
        Cabinet(
            game_id="culebra", title="CULEBRA",
            subtitle="comé antes de que se acabe",
            howto=["flechas o wasd mueven", "el hambre baja: cada fruta te da aire",
                   "la dorada vale por cinco · agarrá los poderes",
                   "manzanas seguidas hacen racha · el ají te acelera"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=GREEN,
                        warn=RED, shadow=SHADOW, panel=GRID),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
