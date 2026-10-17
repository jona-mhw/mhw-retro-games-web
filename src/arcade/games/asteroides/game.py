"""asteroides — 90 segundos rompiendo piedra en órbita, para MHW RETRO FUTURE.

el clásico de vectores, con inercia de verdad: la nave gira sobre su eje y
empuja hacia donde mira, así que frenar es girar 180° y acelerar. la pantalla da
la vuelta por los cuatro lados, para vos y para las piedras.

lo que le sumamos al original:

- **las piedras se parten**: una grande da dos medianas, una mediana dos chicas,
  y las chicas valen más. reventar una grande de un tiro es peor negocio que
  desarmarla entera.
- **el cazador**: cada tanto entra un platillo que te apunta y dispara. vale
  mucho y es lo único que te persigue.
- **tres poderes** que dejan las piedras al romperse — triple (abanico de tres
  tiros), escudo (aguanta un golpe) y frenos (te para en seco, que es lo que
  más se extraña en un juego con inercia).
- **la munición es tiempo**: no hay límite de tiros, pero el reloj no para.
- **el combo**: piedras rotas una atrás de otra, sin dejar pasar más de un
  segundo, multiplican (hasta x4). desarmar una grande entera a ritmo es la
  jugada.
- **la dorada**: cada tanto cruza una piedra chica, dorada y rápida que no se
  parte, vale mucho y se va sola a los pocos segundos. o la perseguís o no.

la lógica vive en la clase Espacio, sin pyxel: `step()` avanza un frame con el
input ya leído y devuelve qué pasó.
"""
import math
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

W, H = 256, 208
HUD = 14
FIELD_TOP = HUD

TIME = 90 * 60                   # el round entero: nada lo estira
VIDAS = 3
GRACIA = 110

SHIP_R = 6                       # radio de choque de la nave
TURN = 0.098
THRUST = 0.135
DRAG = 0.988                     # el espacio casi no frena: eso es la gracia
MAXV = 3.2
SHOT_V = 4.4
SHOT_TTL = 46
DISPARO_GAP = 9                  # frames entre tiro y tiro

GRANDE, MEDIANA, CHICA = 2, 1, 0
RADIO = {GRANDE: 15, MEDIANA: 9, CHICA: 5}
VALE = {GRANDE: 20, MEDIANA: 30, CHICA: 50}
VEL = {GRANDE: 0.42, MEDIANA: 0.72, CHICA: 1.15}
OLEADA_GAP = 11 * 60             # cada cuánto entra piedra nueva

CAZADOR_GAP = 16 * 60
CAZADOR_VALE = 150
CAZADOR_V = 0.9
CAZADOR_TIRO = 90

TRIPLE, ESCUDO, FRENOS = range(3)
POWER_NOMBRE = {TRIPLE: "¡TRIPLE!", ESCUDO: "¡ESCUDO!", FRENOS: "¡FRENOS!"}
TRIPLE_TTL = 9 * 60
POWER_TTL = 9 * 60
POWER_CHANCE = 0.16              # probabilidad de que una piedra deje un poder

# el combo: roturas seguidas. si pasa más de COMBO_TTL entre una y otra, se
# enfría. el techo evita que un campo lleno de chicas valga una fortuna.
COMBO_TTL = 60
COMBO_CADA = 3
COMBO_MAX = 4

# la dorada: rápida, no se parte, se va sola
DORADA_GAP = 17 * 60
DORADA_TTL = 7 * 60
DORADA_VALE = 250
DORADA_V = 1.7

(BG, STAR1, STAR2, SHIP1, SHIP2, FLAME, ROCK1, ROCK2, ROCK3, SHOT, TXT, DIM,
 ACCENT, WARN, SHADOW, WHITE, NEON, NEON2, PINK, GOLD, HUNTER, HUNTER2,
 SHIELDC, GRID) = range(24)
PAL = [
    0x0B0A16, 0x1E1B3A, 0x2E2A55, 0x38E8E0, 0xA8FFF8, 0xFF8A3A, 0x8E86B0,
    0xC0B8DC, 0x5E5686, 0xFFF3B0, 0xE8ECF5, 0x6E6499, 0x38E8E0, 0xE04A2A,
    0x060512, 0xF2F5FB, 0xFF6EC7, 0xB03A8E, 0xE868C8, 0xFFD24A, 0x9AE84A,
    0x4E8E28, 0x7ADCFF, 0x171430,
] + [0] * (256 - 24)

CHISPA_ROCA = (WHITE, ROCK2, ROCK1, ROCK3)
CHISPA_NAVE = (WHITE, SHIP2, SHIP1, NEON)
CHISPA_CAZA = (WHITE, GOLD, HUNTER, HUNTER2)


def envolver(x, y):
    """el campo da la vuelta: salir por un borde es entrar por el otro."""
    if x < 0:
        x += W
    elif x >= W:
        x -= W
    if y < FIELD_TOP:
        y += H - FIELD_TOP
    elif y >= H:
        y -= H - FIELD_TOP
    return x, y


def dist2(ax, ay, bx, by):
    """distancia al cuadrado, contando que el campo se envuelve."""
    dx = abs(ax - bx)
    dy = abs(ay - by)
    if dx > W / 2:
        dx = W - dx
    alto = H - FIELD_TOP
    if dy > alto / 2:
        dy = alto - dy
    return dx * dx + dy * dy


class Roca:
    def __init__(self, x, y, tam, a, rng, dorada=False):
        self.x, self.y, self.tam = x, y, tam
        self.dorada = dorada
        self.ttl = DORADA_TTL if dorada else -1
        v = DORADA_V if dorada else VEL[tam] * rng.uniform(0.75, 1.3)
        self.vx, self.vy = math.cos(a) * v, math.sin(a) * v
        self.giro = rng.uniform(-0.05, 0.05) * (3 if dorada else 1)
        self.rot = rng.uniform(0, math.tau)
        self.forma = [rng.uniform(0.68, 1.25) for _ in range(9)]

    @property
    def r(self):
        return RADIO[self.tam]

    def step(self):
        self.x, self.y = envolver(self.x + self.vx, self.y + self.vy)
        self.rot += self.giro


class Cazador:
    """el platillo: te sigue de lejos y te tira. lo único que te busca."""

    def __init__(self, x, y, rng):
        self.x, self.y = x, y
        self.rng = rng
        self.t = CAZADOR_TIRO
        self.vida = 2
        self.vy = rng.choice((-0.35, 0.35))

    def step(self, tx, ty):
        dx = tx - self.x
        if abs(dx) > W / 2:
            dx = -dx
        self.x += CAZADOR_V * (1 if dx > 0 else -1)
        self.y += self.vy
        if self.y < FIELD_TOP + 8 or self.y > H - 8:
            self.vy = -self.vy
        self.x, self.y = envolver(self.x, self.y)
        self.t -= 1
        if self.t <= 0:
            self.t = CAZADOR_TIRO
            return math.atan2(ty - self.y, tx - self.x)   # dispara hacia vos
        return None


class Espacio:
    """el campo entero, sin pyxel: nave, piedras, tiros, poderes y reloj."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.reset()

    def reset(self):
        self.x, self.y = W / 2, (FIELD_TOP + H) / 2
        self.a = -math.pi / 2
        self.vx = self.vy = 0.0
        self.score = 0
        self.lives = VIDAS
        self.over = False
        self.time = TIME
        self.gracia = GRACIA
        self.triple = 0
        self.escudo = 0
        self.cool = 0
        self.rocas = []
        self.tiros = []              # [x, y, vx, vy, ttl, mio]
        self.powers = []             # [x, y, tipo, ttl]
        self.cazador = None
        self.caza_t = CAZADOR_GAP
        self.oleada_t = OLEADA_GAP
        self.rotas = 0
        self.combo = 0
        self.combo_t = 0
        self.dorada_t = DORADA_GAP
        self.doradas = 0
        for _ in range(4):
            self._soltar_roca(GRANDE)

    # --- poblar ----------------------------------------------------------
    def _lejos(self, minimo=70):
        for _ in range(30):
            x = self.rng.uniform(0, W)
            y = self.rng.uniform(FIELD_TOP, H)
            if dist2(x, y, self.x, self.y) > minimo * minimo:
                return x, y
        return 4.0, float(FIELD_TOP + 4)

    def _soltar_roca(self, tam, dorada=False):
        x, y = self._lejos(72)
        self.rocas.append(Roca(x, y, tam, self.rng.uniform(0, math.tau), self.rng,
                               dorada=dorada))

    def mult(self):
        """el combo en multiplicador: cada tres roturas seguidas suma uno."""
        return min(COMBO_MAX, 1 + self.combo // COMBO_CADA)

    # --- input ------------------------------------------------------------
    def disparar(self, ev):
        if self.cool > 0 or self.over:
            return False
        self.cool = DISPARO_GAP
        angulos = (self.a,) if not self.triple else (self.a - 0.26, self.a,
                                                     self.a + 0.26)
        for a in angulos:
            self.tiros.append([self.x + math.cos(a) * 8, self.y + math.sin(a) * 8,
                               math.cos(a) * SHOT_V + self.vx * 0.4,
                               math.sin(a) * SHOT_V + self.vy * 0.4,
                               SHOT_TTL, 1])
        ev.append(("tiro", self.x, self.y))
        return True

    def frenar(self):
        self.vx *= 0.72
        self.vy *= 0.72

    # --- un frame ----------------------------------------------------------
    def step(self, rot, thrust, fire):
        ev = []
        if self.over:
            return ev
        # ojo: el escudo NO va acá. es un flag de "aguanta un golpe", no un
        # temporizador — metido en esta lista se gastaba solo en el mismo frame
        # en que lo agarrabas.
        for campo in ("gracia", "triple", "cool"):
            v = getattr(self, campo)
            if v > 0:
                setattr(self, campo, v - 1)
        if self.combo_t > 0:
            self.combo_t -= 1
            if self.combo_t == 0 and self.combo:
                if self.combo >= COMBO_CADA:
                    ev.append(("combo_frio", self.combo))
                self.combo = 0

        self.a += rot * TURN
        if thrust:
            self.vx += math.cos(self.a) * THRUST
            self.vy += math.sin(self.a) * THRUST
        self.vx *= DRAG
        self.vy *= DRAG
        v = math.hypot(self.vx, self.vy)
        if v > MAXV:
            self.vx, self.vy = self.vx / v * MAXV, self.vy / v * MAXV
        self.x, self.y = envolver(self.x + self.vx, self.y + self.vy)
        if fire:
            self.disparar(ev)

        self._mover_tiros(ev)
        for roca in self.rocas:
            roca.step()
        # la dorada se va sola
        for roca in list(self.rocas):
            if roca.ttl > 0:
                roca.ttl -= 1
                if roca.ttl == 0:
                    self.rocas.remove(roca)
                    ev.append(("dorada_ida", roca.x, roca.y))
        self.dorada_t -= 1
        if self.dorada_t <= 0:
            self.dorada_t = DORADA_GAP
            self._soltar_roca(CHICA, dorada=True)
            ev.append(("dorada_entra",))
        self._cazador(ev)
        self._choques(ev)
        self._powers(ev)

        self.oleada_t -= 1
        if self.oleada_t <= 0 or not self.rocas:
            self.oleada_t = OLEADA_GAP
            self._soltar_roca(GRANDE)

        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("aguantaste",))
        return ev

    def _mover_tiros(self, ev):
        vivos = []
        for t in self.tiros:
            t[0], t[1] = envolver(t[0] + t[2], t[1] + t[3])
            t[4] -= 1
            if t[4] <= 0:
                continue
            if t[5]:                                   # tiro tuyo: pega piedra
                pegó = False
                for roca in list(self.rocas):
                    if dist2(t[0], t[1], roca.x, roca.y) < roca.r * roca.r:
                        self._romper(roca, ev)
                        pegó = True
                        break
                if not pegó and self.cazador and \
                        dist2(t[0], t[1], self.cazador.x, self.cazador.y) < 64:
                    self.cazador.vida -= 1
                    pegó = True
                    if self.cazador.vida <= 0:
                        self.score += CAZADOR_VALE
                        ev.append(("caza", self.cazador.x, self.cazador.y))
                        self.cazador = None
                        self.caza_t = CAZADOR_GAP
                    else:
                        ev.append(("chispa", t[0], t[1]))
                if pegó:
                    continue
            vivos.append(t)
        self.tiros = vivos

    def _romper(self, roca, ev):
        self.rocas.remove(roca)
        self.combo += 1
        self.combo_t = COMBO_TTL
        m = self.mult()
        self.rotas += 1
        if roca.dorada:
            self.score += DORADA_VALE * m
            self.doradas += 1
            ev.append(("dorada", roca.x, roca.y, DORADA_VALE * m))
            return
        self.score += VALE[roca.tam] * m
        ev.append(("rompe", roca.x, roca.y, roca.tam, VALE[roca.tam] * m))
        if self.combo % COMBO_CADA == 0 and m > 1:
            ev.append(("combo", roca.x, roca.y, m))
        if roca.tam > CHICA:
            for _ in range(2):
                a = self.rng.uniform(0, math.tau)
                self.rocas.append(Roca(roca.x, roca.y, roca.tam - 1, a, self.rng))
        elif self.rng.random() < POWER_CHANCE:
            self.powers.append([roca.x, roca.y, self.rng.randrange(3), POWER_TTL])

    def _cazador(self, ev):
        if self.cazador is None:
            self.caza_t -= 1
            if self.caza_t <= 0:
                x, y = self._lejos(90)
                self.cazador = Cazador(x, y, self.rng)
                ev.append(("caza_entra", x, y))
            return
        a = self.cazador.step(self.x, self.y)
        if a is not None:
            self.tiros.append([self.cazador.x, self.cazador.y,
                               math.cos(a) * 2.4, math.sin(a) * 2.4,
                               SHOT_TTL * 2, 0])
            ev.append(("caza_tira", self.cazador.x, self.cazador.y))

    def _golpe(self, ev, x, y):
        if self.gracia or self.over:
            return
        if self.escudo:
            self.escudo = 0
            self.gracia = GRACIA
            ev.append(("escudo_roto", x, y))
            return
        self.lives -= 1
        self.gracia = GRACIA
        self.vx = self.vy = 0.0
        ev.append(("golpe", x, y, self.lives))
        if self.lives <= 0:
            self.over = True
            ev.append(("fin", x, y))

    def _choques(self, ev):
        for roca in self.rocas:
            if dist2(self.x, self.y, roca.x, roca.y) < (roca.r + SHIP_R) ** 2:
                self._golpe(ev, self.x, self.y)
                return
        for t in list(self.tiros):
            if not t[5] and dist2(t[0], t[1], self.x, self.y) < SHIP_R * SHIP_R:
                self.tiros.remove(t)
                self._golpe(ev, self.x, self.y)
                return
        if self.cazador and dist2(self.x, self.y, self.cazador.x,
                                  self.cazador.y) < (SHIP_R + 7) ** 2:
            self._golpe(ev, self.x, self.y)

    def _powers(self, ev):
        quedan = []
        for p in self.powers:
            p[3] -= 1
            if p[3] <= 0:
                continue
            if dist2(self.x, self.y, p[0], p[1]) < (SHIP_R + 7) ** 2:
                self._tomar(p[2], ev)
            else:
                quedan.append(p)
        self.powers = quedan

    def _tomar(self, tipo, ev):
        if tipo == TRIPLE:
            self.triple = TRIPLE_TTL
        elif tipo == ESCUDO:
            self.escudo = 1
        else:
            self.frenar()
        ev.append(("power", self.x, self.y, tipo))


class World:
    def __init__(self):
        self.e = Espacio()
        self.fx = fx.Fx(gravity=0.0)
        self.thrust = False
        self.estrellas = [(i * 71 % W, FIELD_TOP + (i * 37) % (H - FIELD_TOP),
                           STAR1 if i % 3 else STAR2) for i in range(46)]

    @property
    def over(self):
        return self.e.over

    @property
    def score(self):
        return self.e.score

    def update(self):
        e = self.e
        rot = (1 if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D) else 0) \
            - (1 if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A) else 0)
        self.thrust = pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W)
        fire = pyxel.btn(pyxel.KEY_SPACE) or pyxel.btn(pyxel.KEY_X)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            e.frenar()
        for ev in e.step(rot, self.thrust, fire):
            self._efecto(ev)
        if self.thrust and pyxel.frame_count % 2 == 0:
            back = e.a + math.pi
            self.fx.burst(e.x + math.cos(back) * 7, e.y + math.sin(back) * 7,
                          (WHITE, FLAME, WARN), n=2, speed=0.8, life=12,
                          spread=0.8, angle=back)
        self.fx.update()

    def _efecto(self, ev):
        k = ev[0]
        if k == "rompe":
            x, y, tam = ev[1], ev[2], ev[3]
            vale = ev[4] if len(ev) > 4 else VALE[tam]
            self.fx.burst(x, y, CHISPA_ROCA, n=8 + tam * 6, speed=1.5 + tam * 0.4,
                          life=20 + tam * 4)
            self.fx.popup(x, y - 8, "+%d" % vale, NEON if tam else GOLD)
            self.fx.shake(1 + tam)
        elif k == "combo":
            self.fx.popup(ev[1], ev[2] - 18, "¡COMBO x%d!" % ev[3], PINK)
            self.fx.destello(PINK)
        elif k == "combo_frio":
            self.fx.popup(W / 2, FIELD_TOP + 22, "combo frío", DIM)
        elif k == "dorada_entra":
            self.fx.popup(W / 2, FIELD_TOP + 34, "¡DORADA!", GOLD)
            self.fx.destello(GOLD)
        elif k == "dorada":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, PINK, SHOT), n=36,
                          speed=3.0, life=36)
            self.fx.popup(ev[1], ev[2] - 10, "+%d" % ev[3], GOLD)
            self.fx.shake(5)
            self.fx.destello(GOLD)
        elif k == "dorada_ida":
            self.fx.burst(ev[1], ev[2], (GOLD, DIM), n=8, speed=1.0, life=14)
        elif k == "caza":
            self.fx.burst(ev[1], ev[2], CHISPA_CAZA, n=34, speed=2.8, life=34)
            self.fx.popup(ev[1], ev[2] - 10, "+%d" % CAZADOR_VALE, GOLD)
            self.fx.shake(6)
            self.fx.destello(GOLD)
        elif k == "caza_entra":
            self.fx.popup(W / 2, FIELD_TOP + 22, "¡CAZADOR!", HUNTER)
            self.fx.destello(HUNTER)
        elif k == "golpe":
            self.fx.burst(ev[1], ev[2], CHISPA_NAVE, n=32, speed=2.6, life=32)
            self.fx.shake(7)
            self.fx.destello(WARN)
        elif k == "escudo_roto":
            self.fx.burst(ev[1], ev[2], (WHITE, SHIELDC, NEON), n=22, speed=2.2,
                          life=26)
            self.fx.popup(ev[1], ev[2] - 12, "escudo", SHIELDC)
            self.fx.shake(3)
        elif k == "power":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, PINK), n=18, speed=2.0,
                          life=24)
            self.fx.popup(ev[1], ev[2] - 12, POWER_NOMBRE[ev[3]], GOLD)
            self.fx.destello(GOLD)
        elif k == "chispa":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, HUNTER), n=5, speed=1.2,
                          life=12)
        elif k == "aguantaste":
            self.fx.popup(W / 2, (FIELD_TOP + H) / 2, "¡SE ACABÓ EL AIRE!", ACCENT)

    # --- dibujo ------------------------------------------------------------
    def draw(self):
        e = self.e
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        for x, y, c in self.estrellas:
            pyxel.pset(x, y, c)
        for p in e.powers:
            self._power(p)
        for roca in e.rocas:
            self._roca(roca)
        for t in e.tiros:
            pyxel.rect(int(t[0]) - 1, int(t[1]) - 1, 2, 2,
                       SHOT if t[5] else HUNTER)
        if e.cazador:
            self._cazador(e.cazador)
        if e.lives > 0 and (not e.gracia or (pyxel.frame_count // 4) % 2):
            self._nave(e)
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(0, FIELD_TOP, W, H - FIELD_TOP)
        self._hud()

    def _roca(self, roca):
        """la piedra, como polígono irregular: vectorial, a tono con la casa."""
        pts = []
        n = len(roca.forma)
        for i, f in enumerate(roca.forma):
            a = roca.rot + i * math.tau / n
            pts.append((roca.x + math.cos(a) * roca.r * f,
                        roca.y + math.sin(a) * roca.r * f))
        col = (ROCK3, ROCK1, ROCK2)[roca.tam]
        if roca.dorada:
            if roca.ttl < 90 and (pyxel.frame_count // 4) % 2:
                return                                  # titila antes de irse
            col = GOLD if (pyxel.frame_count // 3) % 2 else SHOT
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if abs(x0 - x1) < W / 2 and abs(y0 - y1) < H / 2:
                pyxel.line(int(x0), int(y0), int(x1), int(y1), col)

    def _nave(self, e):
        cosa, sina = math.cos(e.a), math.sin(e.a)

        def p(f, s):
            return (int(e.x + f * cosa - s * sina), int(e.y + f * sina + s * cosa))

        morro, izq, der, cola = p(9, 0), p(-6, -5), p(-6, 5), p(-3, 0)
        col = SHIP2 if e.escudo else SHIP1
        pyxel.line(*morro, *izq, col)
        pyxel.line(*morro, *der, col)
        pyxel.line(*izq, *cola, col)
        pyxel.line(*der, *cola, col)
        if self.thrust and (pyxel.frame_count // 2) % 2:
            pyxel.line(*cola, *p(-11, 0), FLAME)
        if e.escudo:
            pyxel.circb(int(e.x), int(e.y), 11, SHIELDC)
        if e.triple:
            for s in (-4, 4):
                pyxel.pset(*p(7, s), NEON)

    def _cazador(self, c):
        x, y = int(c.x), int(c.y)
        pyxel.line(x - 8, y, x + 8, y, HUNTER)
        pyxel.line(x - 8, y, x - 3, y - 4, HUNTER)
        pyxel.line(x + 8, y, x + 3, y - 4, HUNTER)
        pyxel.line(x - 3, y - 4, x + 3, y - 4, HUNTER)
        pyxel.line(x - 5, y + 1, x + 5, y + 1, HUNTER2)
        if (pyxel.frame_count // 6) % 2:
            pyxel.pset(x, y - 5, WHITE)

    def _power(self, p):
        x, y, tipo, ttl = int(p[0]), int(p[1]), p[2], p[3]
        if ttl < 90 and (pyxel.frame_count // 4) % 2:
            return
        col = (NEON, SHIELDC, GOLD)[tipo]
        r = 5 + (pyxel.frame_count // 6) % 2
        pyxel.circb(x, y, r, col)
        if tipo == TRIPLE:
            for d in (-2, 0, 2):
                pyxel.pset(x + d, y - 1, col)
        elif tipo == ESCUDO:
            pyxel.circb(x, y, 2, col)
        else:
            pyxel.rect(x - 2, y - 1, 5, 2, col)

    def _hud(self):
        e = self.e
        pyxel.rect(0, 0, W, HUD, SHADOW)
        text(4, 4, "%d" % e.score, ACCENT)
        for i in range(VIDAS):                     # las vidas, como navecitas
            col = SHIP1 if i < e.lives else DIM
            bx = 52 + i * 9
            pyxel.line(bx + 3, 3, bx, 9, col)
            pyxel.line(bx + 3, 3, bx + 6, 9, col)
            pyxel.line(bx, 9, bx + 6, 9, col)
        m = e.mult()
        if m > 1:
            col = PINK if (pyxel.frame_count // 6) % 2 else GOLD
            text(82, 4, "x%d" % m, col)
            fx.bar(82, 10, 14, 2, e.combo_t / COMBO_TTL, PINK, GRID)
        if e.triple:
            fx.bar(100, 5, 22, 4, e.triple / TRIPLE_TTL, NEON, GRID)
        if e.escudo:
            pyxel.circb(132, 7, 4, SHIELDC)
        if e.cazador:
            col = HUNTER if (pyxel.frame_count // 8) % 2 else GOLD
            text(150, 4, "cazador", col)
        s = e.time // 60
        col = WHITE if s <= 10 and pyxel.frame_count % 30 < 15 else TXT
        r = "%ds" % s
        text(W - len(r) * 4 - 4, 4, r, col)
        fx.bar(W - 66, 5, 28, 4, e.time / TIME, ACCENT, GRID)


class Game:
    def __init__(self):
        Cabinet(
            game_id="asteroides", title="ASTEROIDES",
            subtitle="90 segundos de deriva",
            howto=["izq/der giran · arriba empuja",
                   "espacio dispara · abajo frena",
                   "las grandes se parten: las chicas valen más",
                   "roturas seguidas hacen combo · cazá la dorada"],
            width=W, height=H, palette=PAL, scale=3, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=GRID),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
