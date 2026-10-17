"""culebra — el snake, pero con hambre, presas, arañas y un final a toda prisa.

lo de siempre: comes, creces, aceleras y no te muerdes. lo que le agregamos:

- **hambre**: hay un reloj que baja siempre. cada fruta te da aire, pero el
  aire total que puedes recuperar está acotado (la **reserva**), así que la
  partida entra en el minuto y medio pase lo que pase. deja de ser "a ver
  cuánto aguanto" y pasa a ser "cuánto junto antes de que se acabe".
- **frenesí final**: cuando la reserva se vacía, la comida ya no da aire, pero
  todo vale doble y el tablero se llena de bayas. son los últimos segundos y
  hay que juntar lo más posible antes de que el hambre llegue a cero. es el
  clímax de la partida: el final no se apaga, se acelera.
- **la dorada**: una fruta que aparece lejos, vale por cinco y se va sola.
- **el ratón**: desde el nivel 2 aparece una presa que **arranca** cuando te
  acercas. vale por cuatro y te hace crecer dos. hay que acorralarlo.
- **arañas**: desde el nivel 4 caminan por el tablero. chocarlas con la cabeza
  te mata; con el fantasma puesto, te las comes.
- **poderes**: el fantasma te deja atravesarte (y comer arañas) unos segundos;
  la tijera te corta la cola por la mitad cuando ya eres demasiado larga.
- **muros y portales**: desde el nivel 3 el tablero se ensucia; desde el 2 se
  abre un par de portales que se muda cada tanto.
- **racha**: comer poco después de la comida anterior la encadena. cada tres
  seguidas la manzana vale una más (hasta x3). dejar pasar el tiempo la enfría.
- **el ají**: vale por tres y te mete turbo cuatro segundos.
- **escenarios**: cada nivel cambia el tablero (pradera, desierto, cueva...).

el nivel sale de cuánto comiste (no del puntaje): si saliera del puntaje, el
frenesí x2 dispararía niveles, muros y velocidad justo en el final.

los giros van **en cola** (hasta tres): si deslizas dos veces rápido dentro del
mismo paso, se hacen los dos giros, uno por paso. antes el segundo pisaba al
primero y, si era el contrario del rumbo, se perdía — en el celular, con swipe,
eso era morir en una esquina por un giro que sí hiciste.

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

HAMBRE = 30 * 60                 # con lo que arrancas
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
COMIDAS_NIVEL = 4                # cuántas comidas por nivel
COLA_GIROS = 3                   # giros que se pueden dejar anotados

FANTASMA, TIJERA = range(2)
PODER_NOMBRE = {FANTASMA: "¡FANTASMA!", TIJERA: "¡TIJERA!"}

# la racha: comidas encadenadas. techo en x3.
RACHA_TTL = 4 * 60
RACHA_CADA = 3
RACHA_MAX = 3

# el ají: vale por tres y te acelera un rato. aparece menos que el poder.
AJI_GAP = 13 * 60
AJI_TTL = 7 * 60
AJI_VALE = 3
AJI_TURBO = 4 * 60

# el ratón: una presa que se escapa. más lento que tú, pero no se deja.
RATON_DESDE = 2
RATON_GAP = 9 * 60
RATON_TTL = 10 * 60
RATON_PASO = 13                  # frames por paso del ratón
RATON_VALE = 4
RATON_AIRE = 3 * 60
RATON_CRECE = 2
RATON_MIEDO = 7                  # a esta distancia de tu cabeza, arranca

# las arañas: el peligro que se mueve. nacen avisando y no te persiguen: sólo
# matan si tú las chocas, así que siempre se pueden esquivar.
ARANA_DESDE = 4
ARANA_DOS = 7                    # desde acá, dos a la vez
ARANA_PASO = 15
ARANA_NACE = 90                  # frames que titila antes de ser peligrosa
ARANA_VALE = 5                   # comida con el fantasma

# el frenesí: sin reserva, todo vale doble y llueven bayas
FRENESI_X = 2
BAYAS = 4

(BG, GRID, FRAME, BODY0, BODY1, HEAD, APPLE, APPLE2, TXT, DIM, TEAL,
 AMBER, SHADOW, GREEN, RED, WHITE,
 GOLD, GOLD2, GHOST1, GHOST2, WALL, WALL2, MAGENTA, ORANGE,
 SPIDER, SPIDER2, MOUSE, MOUSE2, BERRY, BERRY2, LABEL, DARKRED,
 BELLY, PANEL) = range(34)
PAL = [
    0x0C0E14, 0x141926, 0x2A3350, 0x4B7A18, 0x8AC52F, 0xB6F03C, 0xE0402A,
    0xFF7A54, 0xE8ECF5, 0x5A6480, 0x27969E, 0xFFC24A, 0x070810, 0x8AC52F,
    0xE0402A, 0xF2F5FB,
    0xFFD24A, 0xFFF3B0, 0x7ADCFF, 0x2E7FBF, 0x6E6A82, 0x39435E, 0xD84AB8,
    0xE0842E,
    0x9A4FE0, 0xD4A8FF, 0xC8C2D8, 0xFF9AB8, 0x5A6CFF, 0xB0B8FF, 0xB4BED8,
    0x6E1E2C, 0xD8F08A, 0x111522,
]

# un escenario por nivel: (nombre, cuadro A, cuadro B, muro, muro sombra).
# cambiar de lugar al subir de nivel es lo que hace que se sienta un avance.
ESCENAS_RGB = [
    ("PRADERA", 0x0B130B, 0x111D10, 0x6E7A5A, 0x3A4630),
    ("DESIERTO", 0x16100A, 0x21180C, 0x9A7A46, 0x5A4426),
    ("CUEVA", 0x0F0A17, 0x191124, 0x6A5A8E, 0x3A2E54),
    ("GLACIAR", 0x09111A, 0x0F1B28, 0x7AA6C4, 0x3E5E78),
    ("VOLCÁN", 0x160908, 0x240F0B, 0x9A4632, 0x52221A),
    ("NOCHE", 0x0C0E14, 0x141926, 0x6E6A82, 0x39435E),
]
ESCENAS = []
for _n, _a, _b, _m, _m2 in ESCENAS_RGB:
    i = len(PAL)
    PAL += [_a, _b, _m, _m2]
    ESCENAS.append((_n, i, i + 1, i + 2, i + 3))
FRENESI_A, FRENESI_B = len(PAL), len(PAL) + 1
PAL += [0x1A0A1C, 0x2A1030]
PAL += [0] * (256 - len(PAL))

CHISPA_MANZANA = (WHITE, APPLE2, APPLE, BODY0)
CHISPA_DORADA = (WHITE, GOLD2, GOLD, AMBER)
CHISPA_PODER = (WHITE, GHOST1, GHOST2, TEAL)
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Culebra:
    """estado y reglas del snake. sin pyxel: testeable de a de veras.

    `step()` es un movimiento de celda (como siempre) y `frame()` es un frame
    de reloj: baja el hambre, hace aparecer y caducar las frutas, mueve los
    bichos y llama a `step()` cuando toca. los tests de duración corren
    `frame()`.
    """

    def __init__(self, cols=COLS, rows=ROWS, rng=None):
        self.cols, self.rows = cols, rows
        self.rng = rng or random
        self.reset()

    def reset(self):
        cx, cy = self.cols // 2, self.rows // 2
        self.body = [(cx - i, cy) for i in range(3)]   # cabeza primero
        self.dir = (1, 0)
        self.cola_dir = []          # los giros anotados, en orden
        self.dead = False
        self.score = 0
        self.comidas = 0            # lo que sube el nivel
        self.ate = False
        self.crecer = 0             # celdas que faltan por crecer
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
        self.raton = None           # [x, y, ttl, paso]
        self.raton_t = RATON_GAP // 2
        self.aranas = []            # [x, y, dx, dy, nace, paso]
        self.frenesi = False
        self.bayas = []
        self.hambre = HAMBRE
        self.extra = EXTRA_MAX
        self.niv = 1
        self.t = 0
        self.porto = False
        self._place_apple()

    # --- la cola de giros -------------------------------------------------
    @property
    def pending(self):
        """hacia dónde va a ir: el último giro anotado, o el rumbo actual."""
        return self.cola_dir[-1] if self.cola_dir else self.dir

    @pending.setter
    def pending(self, d):
        self.cola_dir = [] if d == self.dir else [d]

    def set_dir(self, d):
        """anota un giro. se compara contra el ÚLTIMO anotado, no contra el
        rumbo actual: así arriba-izquierda rápido, yendo a la derecha, son dos
        giros válidos y no una reversa."""
        ref = self.pending
        if d == (0, 0) or d == ref or (d[0] == -ref[0] and d[1] == -ref[1]):
            return
        if len(self.cola_dir) < COLA_GIROS:
            self.cola_dir.append(d)

    # --- tablero ---------------------------------------------------------
    def _ocupado(self):
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
        if self.raton:
            ocupado.add((self.raton[0], self.raton[1]))
        for a in self.aranas:
            ocupado.add((a[0], a[1]))
        ocupado.update(self.bayas)
        ap = getattr(self, "apple", None)
        if ap:
            ocupado.add(ap)
        return ocupado

    def _libres(self, margen=0):
        """celdas donde se puede poner algo: ni cuerpo, ni muro, ni otra cosa."""
        ocupado = self._ocupado()
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

    def _place_raton(self):
        libres = self._libres(margen=9) or self._libres(margen=4)
        if libres:
            x, y = self.rng.choice(libres)
            self.raton = [x, y, RATON_TTL, RATON_PASO]

    def _place_arana(self):
        libres = self._libres(margen=10) or self._libres(margen=6)
        if libres:
            x, y = self.rng.choice(libres)
            dx, dy = self.rng.choice(DIRS)
            self.aranas.append([x, y, dx, dy, ARANA_NACE, ARANA_PASO])

    def _sube_racha(self):
        """¿esta comida acaba de subir el multiplicador? (y no sólo lo mantuvo:
        avisar "racha x3" cada tres bayas era ruido)."""
        return (self.racha % RACHA_CADA == 0 and self.mult() > 1
                and self.racha <= (RACHA_MAX - 1) * RACHA_CADA)

    def mult(self):
        """cuánto vale una manzana ahora: 1, y sube cada tres encadenadas."""
        return min(RACHA_MAX, 1 + self.racha // RACHA_CADA)

    def _abrir_portales(self):
        """un par de bocas ligadas, lejos una de la otra.

        es el atajo del tablero: con muros por todos lados, meterse por un
        portal es la diferencia entre llegar a la dorada o quedarse mirándola.
        y también la forma más tonta de morir, porque sales mirando para el
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
    def _comer(self, cuanto, aire):
        """suma puntos y devuelve aire, descontándolo del presupuesto común.

        ojo con el `HAMBRE - self.hambre`: el aire que **no cabe** no se cobra.
        sin eso, comer con el estómago lleno quemaba presupuesto a cambio de
        nada y el que jugaba mejor terminaba antes — al revés de lo que tiene
        que premiar el juego.
        """
        if self.frenesi:
            cuanto *= FRENESI_X
        self.score += cuanto
        dar = min(aire, self.extra, HAMBRE - self.hambre)
        self.extra -= dar
        self.hambre += dar
        return cuanto

    def step(self):
        """avanza una celda. devuelve 'eat', 'dead' o None."""
        if self.dead:
            return None
        if self.cola_dir:
            self.dir = self.cola_dir.pop(0)
        hx, hy = self.body[0]
        nx, ny = hx + self.dir[0], hy + self.dir[1]
        self.ate = False
        self.porto = False
        salida = self._salida((nx, ny))
        if salida is not None:
            # entrar por una boca te deja en la otra, con el mismo rumbo. se
            # comprueba ANTES de mirar el cuerpo: el portal no te salva de
            # morderte, sólo te cambia de lugar
            nx, ny = salida
            self.porto = True
        eating = (nx, ny) == self.apple
        crece = eating or self.crecer > 0
        ocupado = set(self.body)
        if not crece:
            ocupado.discard(self.body[-1])
        fuera = not (0 <= nx < self.cols and 0 <= ny < self.rows)
        chocado = (nx, ny) in self.walls or ((nx, ny) in ocupado and not self.ghost)
        if fuera or chocado:
            self.dead = True
            return 'dead'
        self.body.insert(0, (nx, ny))
        if eating:
            self.ultimo = self._comer(self.mult(), MANZANA_AIRE)
            self.racha += 1
            self.racha_t = RACHA_TTL
            self.comidas += 1
            self.ate = True
            self._place_apple()
        elif self.crecer > 0:
            self.crecer -= 1
        else:
            self.body.pop()
        return 'eat' if eating else None

    def _tomar_poder(self, tipo, ev):
        if tipo == FANTASMA:
            self.ghost = FANTASMA_TTL
        else:                                 # tijera: te saca media cola
            if len(self.body) > 4:
                self.body = self.body[:max(3, len(self.body) // 2)]
            self.crecer = 0
        ev.append(("poder", self.body[0][0], self.body[0][1], tipo))

    def _libre_bicho(self, x, y, ocupado):
        return 0 <= x < self.cols and 0 <= y < self.rows and (x, y) not in ocupado

    def _mover_raton(self):
        """un paso del ratón. si la cabeza está cerca, se aleja; si no, pasea."""
        r = self.raton
        ocupado = set(self.body) | self.walls
        if self.portales:
            ocupado.update(self.portales[:2])
        hx, hy = self.body[0]
        opciones = [(r[0] + dx, r[1] + dy) for dx, dy in DIRS
                    if self._libre_bicho(r[0] + dx, r[1] + dy, ocupado)]
        if not opciones:
            return
        dist = abs(r[0] - hx) + abs(r[1] - hy)
        if dist <= RATON_MIEDO and self.rng.random() < 0.8:
            r[0], r[1] = max(opciones, key=lambda c: abs(c[0] - hx) + abs(c[1] - hy))
        elif self.rng.random() < 0.6:
            r[0], r[1] = self.rng.choice(opciones)

    def _mover_arana(self, a):
        """las arañas van derecho y doblan cuando chocan (o por capricho).
        tu cuerpo es una pared para ellas: nunca se te meten encima."""
        ocupado = set(self.body) | self.walls
        for b in self.aranas:
            if b is not a:
                ocupado.add((b[0], b[1]))
        if self.portales:
            ocupado.update(self.portales[:2])
        if self.rng.random() < 0.18 or not self._libre_bicho(a[0] + a[2], a[1] + a[3],
                                                             ocupado):
            dirs = [d for d in DIRS if self._libre_bicho(a[0] + d[0], a[1] + d[1],
                                                         ocupado)]
            if not dirs:
                return
            a[2], a[3] = self.rng.choice(dirs)
        a[0] += a[2]
        a[1] += a[3]

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

        # sin reserva: el frenesí final
        if not self.frenesi and self.extra <= 0:
            self.frenesi = True
            ev.append(("frenesi",))
        if self.frenesi and len(self.bayas) < BAYAS:
            libres = self._libres(margen=3)       # una sola pasada por el tablero
            while len(self.bayas) < BAYAS and libres:
                c = self.rng.choice(libres)
                libres.remove(c)
                self.bayas.append(c)

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

        # el ratón: aparece, arranca y, si no lo atrapas, se va
        if self.raton:
            self.raton[2] -= 1
            self.raton[3] -= 1
            if self.raton[2] <= 0:
                ev.append(("raton_ido", self.raton[0], self.raton[1]))
                self.raton = None
                self.raton_t = RATON_GAP
            elif self.raton[3] <= 0:
                self.raton[3] = RATON_PASO
                self._mover_raton()
        elif self.niv >= RATON_DESDE:
            self.raton_t -= 1
            if self.raton_t <= 0:
                self._place_raton()
                if self.raton:
                    ev.append(("raton", self.raton[0], self.raton[1]))

        # las arañas
        cuantas = 0 if self.niv < ARANA_DESDE else (1 if self.niv < ARANA_DOS else 2)
        if len(self.aranas) < cuantas and self.t % 60 == 0:
            self._place_arana()
            if self.aranas:
                ev.append(("arana", self.aranas[-1][0], self.aranas[-1][1]))
        for a in self.aranas:
            if a[4]:
                a[4] -= 1
                continue
            a[5] -= 1
            if a[5] <= 0:
                a[5] = ARANA_PASO
                self._mover_arana(a)

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
                           self.ultimo))
                if self._sube_racha():
                    ev.append(("racha", self.body[0][0], self.body[0][1],
                               self.mult()))
            if self.porto:
                ev.append(("portal", self.body[0][0], self.body[0][1]))
            hx, hy = self.body[0]
            if self.gold and (hx, hy) == (self.gold[0], self.gold[1]):
                v = self._comer(DORADA_VALE, DORADA_AIRE)
                self.comidas += 1
                ev.append(("dorada", hx, hy, v))
                self.gold = None
                self.gold_t = DORADA_GAP
            if self.power and (hx, hy) == (self.power[0], self.power[1]):
                self._tomar_poder(self.power[2], ev)
                self.power = None
                self.power_t = PODER_GAP
            if self.aji and (hx, hy) == (self.aji[0], self.aji[1]):
                v = self._comer(AJI_VALE, 0)
                self.comidas += 1
                self.turbo = AJI_TURBO
                ev.append(("aji", hx, hy, v))
                self.aji = None
                self.aji_t = AJI_GAP
            if self.raton and (hx, hy) == (self.raton[0], self.raton[1]):
                v = self._comer(RATON_VALE, RATON_AIRE)
                self.comidas += 1
                self.crecer += RATON_CRECE
                ev.append(("raton_comido", hx, hy, v))
                self.raton = None
                self.raton_t = RATON_GAP
            if (hx, hy) in self.bayas:
                self.bayas.remove((hx, hy))
                v = self._comer(self.mult(), 0)
                self.racha += 1
                self.racha_t = RACHA_TTL
                ev.append(("baya", hx, hy, v))
                if self._sube_racha():
                    ev.append(("racha", hx, hy, self.mult()))
            for a in list(self.aranas):
                if (hx, hy) == (a[0], a[1]) and not a[4]:
                    if self.ghost:
                        v = self._comer(ARANA_VALE, 0)
                        self.aranas.remove(a)
                        ev.append(("arana_comida", hx, hy, v))
                    else:
                        self.dead = True
                        ev.append(("picada", hx, hy))
                        return ev
            if self.level() != self.niv:
                self.niv = self.level()
                if self.niv >= MUROS_DESDE:
                    self._ensuciar()
                ev.append(("nivel", self.niv))
        return ev

    def level(self):
        return self.comidas // COMIDAS_NIVEL + 1

    def speed(self):
        """frames por paso: arranca lento y acelera con el nivel. el ají le
        saca tres frames más, con piso en 2."""
        base = max(3, 10 - self.level())
        return max(2, base - 3) if self.turbo else base


# --- texto grande ------------------------------------------------------------
# la fuente de pyxel es de 4x6: a 1.5x en el teléfono un "¡RACHA!" de ese
# tamaño no se ve. se dibuja en una imagen aparte (con tildes, ñ y ¡) y se
# estampa escalada con blt.
_ACUTE = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
          "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}
_IMG = None


def big(cx, cy, s, col, scale=2, sombra=SHADOW):
    """texto centrado en (cx, cy), agrandado `scale` veces, con sombra."""
    global _IMG
    if _IMG is None:
        _IMG = pyxel.Image(256, 10)
    img = _IMG
    base = "".join(" " if ch == "¡" else ("n" if ch == "ñ" else
                   ("N" if ch == "Ñ" else _ACUTE.get(ch, ch))) for ch in s)
    w = len(s) * 4
    for c, off in ((sombra, max(1, int(scale))), (col, 0)):
        if c is None:
            continue
        img.rect(0, 0, 256, 10, 0)
        img.text(0, 3, base, c)
        for i, ch in enumerate(s):
            x = i * 4
            if ch in _ACUTE:
                img.pset(x + 2, 0, c)
                img.pset(x + 1, 1, c)
            elif ch in "ñÑ":
                img.pset(x, 1, c)
                img.pset(x + 1, 0, c)
                img.pset(x + 2, 1, c)
            elif ch == "¡":
                img.pset(x + 1, 3, c)
                img.rect(x + 1, 5, 1, 3, c)
        pyxel.blt(int(cx - w / 2) + off, int(cy - 5) + off, img, 0, 0, w, 10,
                  0, None, scale)


class World:
    """la culebra jugándose: input, dibujo y chispas. el Cabinet la envuelve."""

    def __init__(self):
        self.g = Culebra()
        self.fx = fx.Fx(gravity=0.0)
        self.fx.destello(WHITE)
        self.f = 0                   # reloj propio de la piel
        self.eatflash = 0
        self.banner = None           # [texto, col, sub, subcol, frames, frames0]
        self.escena = 0              # índice del escenario que se ve
        self.escena_vieja = 0
        self.barrido = 0             # el telón al cambiar de escenario
        self.bultos = []             # bocados que bajan por el cuerpo
        self.cabeza = self.g.body[0]
        self.score_pop = 0
        self.cuenta = -1

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
        self.f += 1
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
        if g.body[0] != self.cabeza:            # dio un paso: los bocados bajan
            self.cabeza = g.body[0]
            self.bultos = [b + 1 for b in self.bultos if b + 1 < len(g.body)]
            if g.turbo:                         # con el ají, la cola echa fuego
                x, y = self._px(*g.body[-1])
                self.fx.burst(x, y, (WHITE, AMBER, ORANGE, RED), n=3, speed=0.8,
                              life=14)
        # la cuenta final del hambre: un latido por segundo
        s = (g.hambre + 59) // 60
        if s != self.cuenta:
            if s == 5 and self.cuenta > 5 and not g.dead:
                if g.frenesi:
                    self._cartel("¡ÚLTIMOS 5!", RED, "JUNTA TODO", WHITE, 50)
                else:
                    self._cartel("¡HAMBRE!", RED, "COME ALGO YA", WHITE, 50)
            self.cuenta = s
            if s <= 5 and not g.dead:
                self.fx.shake(2 if s > 2 else 3)
        if g.frenesi and self.f % 4 == 0:       # chispas de frenesí en los bordes
            x = (self.f * 53) % W
            self.fx.burst(x, HUD + 2, (WHITE, MAGENTA, BERRY2), n=1, speed=0.7,
                          life=30, angle=math.pi / 2, spread=0.6)
        self.eatflash = max(0, self.eatflash - 1)
        self.barrido = max(0, self.barrido - 1)
        self.score_pop = max(0, self.score_pop - 1)
        if self.banner:
            self.banner[4] -= 1
            if self.banner[4] <= 0:
                self.banner = None
        self.fx.update()

    def _cartel(self, s, col, sub=None, subcol=WHITE, frames=60):
        self.banner = [s, col, sub, subcol, frames, frames]

    def _efecto(self, e):
        kind = e[0]
        if kind == "manzana":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_MANZANA, n=12, speed=1.4, life=18)
            self.eatflash = 4
            self.bultos.append(0)
            self.score_pop = 8
            if e[3] > 1:
                self.fx.popup(x, y - 6, "+%d" % e[3], AMBER, life=28)
        elif kind == "baya":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, BERRY2, BERRY, MAGENTA), n=10, speed=1.4,
                          life=16)
            self.fx.popup(x, y - 6, "+%d" % e[3], BERRY2, life=24)
            self.score_pop = 8
        elif kind == "racha":
            self._cartel("RACHA x%d" % e[3], GOLD, "¡SIGUE COMIENDO!", AMBER, 55)
            self.fx.destello(AMBER)
            self.fx.shake(2)
        elif kind == "racha_fria":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 10, "racha fría", LABEL)
        elif kind == "aji":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, ORANGE, RED, APPLE), n=22, speed=2.2,
                          life=26)
            self._cartel("¡AJÍ!", ORANGE, "TURBO +%d" % e[3], WHITE, 45)
            self.fx.destello(ORANGE)
            self.fx.shake(3)
            self.bultos.append(0)
        elif kind == "dorada":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_DORADA, n=26, speed=2.4, life=30)
            self._cartel("¡DORADA!", GOLD, "+%d" % e[3], WHITE, 45)
            self.fx.destello(GOLD)
            self.fx.shake(2)
            self.bultos.append(0)
        elif kind == "dorada_ida":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (GOLD2, GOLD, AMBER), n=8, speed=0.8, life=16)
        elif kind == "poder":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_PODER, n=20, speed=2.0, life=28)
            sub = "COME ARAÑAS" if e[3] == FANTASMA and self.g.aranas else None
            self._cartel(PODER_NOMBRE[e[3]], GHOST1 if e[3] == FANTASMA else MAGENTA,
                         sub, WHITE, 45)
            self.fx.destello(GHOST1)
        elif kind == "portal":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, MAGENTA, GHOST1, GHOST2), n=12,
                          speed=1.6, life=18)
        elif kind == "raton":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 8, "un ratón", MOUSE, life=40)
        elif kind == "raton_comido":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, MOUSE2, MOUSE, DIM), n=20, speed=2.0,
                          life=24)
            self._cartel("¡ÑAM!", MOUSE2, "RATÓN +%d" % e[3], WHITE, 45)
            self.fx.shake(3)
            self.bultos += [0, 1]
        elif kind == "raton_ido":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 6, "se escapó", LABEL)
            self.fx.burst(x, y, (MOUSE, DIM), n=6, speed=1.0, life=12)
        elif kind == "arana":
            x, y = self._px(e[1], e[2])
            if len(self.g.aranas) == 1 and self.g.niv == ARANA_DESDE:
                self._cartel("¡ARAÑA!", SPIDER2, "NO LA CHOQUES", WHITE, 60)
        elif kind == "arana_comida":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, SPIDER2, SPIDER, GHOST1), n=24, speed=2.2,
                          life=26)
            self._cartel("¡CRUNCH!", SPIDER2, "+%d" % e[3], WHITE, 45)
            self.fx.shake(4)
        elif kind == "frenesi":
            self._cartel("¡FRENESÍ!", MAGENTA, "TODO VALE x2", GOLD, 110)
            self.fx.popup(W / 2, HUD + 120, "se acabó la reserva: junta todo",
                          WHITE, life=110, vy=-0.2)
            self.fx.shake(5)
            self.fx.destello(MAGENTA, 8)
        elif kind == "nivel":
            n = e[1]
            self.escena_vieja = self.escena
            self.escena = (n - 1) % len(ESCENAS)
            self.barrido = 24
            sub = ESCENAS[self.escena][0]
            if n == ARANA_DESDE:
                sub = "¡ARAÑAS!"
            elif n == MUROS_DESDE:
                sub = "¡MUROS!"
            elif n == RATON_DESDE:
                sub = "¡RATONES Y PORTALES!"
            self._cartel("NIVEL %d" % n, WHITE, sub, AMBER, 70)
        elif kind in ("muerte", "hambre", "picada"):
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, RED, APPLE2, BODY0), n=34, speed=2.6,
                          life=34)
            self.fx.shake(6)
            self.fx.destello(RED, 6)

    # --- dibujo ----------------------------------------------------------
    def _cell(self, cx, cy, col):
        pyxel.rect(cx * CELL, HUD + cy * CELL, CELL, CELL, col)

    def _fondo(self):
        """el damero del escenario. al cambiar de nivel, el nuevo entra como
        un telón de izquierda a derecha."""
        g = self.g
        if g.frenesi:
            pulso = (self.f // 10) % 2
            a, b = (FRENESI_A, FRENESI_B) if pulso else (FRENESI_B, FRENESI_A)
            nuevo = viejo = (a, b)
        else:
            nuevo = ESCENAS[self.escena][1:3]
            viejo = ESCENAS[self.escena_vieja][1:3]
        corte = W if not self.barrido else int(W * (1 - self.barrido / 24))
        pyxel.rect(0, HUD, corte, H - HUD, nuevo[0])
        if corte < W:
            pyxel.rect(corte, HUD, W - corte, H - HUD, viejo[0])
        for y in range(ROWS):
            py = HUD + y * CELL
            for x in range((y & 1) ^ 1, COLS, 2):
                px = x * CELL
                pyxel.rect(px, py, CELL, CELL, nuevo[1] if px < corte else viejo[1])
        if self.barrido:
            pyxel.rect(corte - 1, HUD, 2, H - HUD, WHITE)

    def draw(self):
        g = self.g
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)                    # el temblor, sin tocar el frame
        self._fondo()
        _, _, _, muro, muro2 = ESCENAS[self.escena]
        for wx, wy in g.walls:                    # los muros, con relieve
            px, py = wx * CELL, HUD + wy * CELL
            pyxel.rect(px, py, CELL, CELL, muro)
            pyxel.rect(px, py, CELL, 1, WHITE if self.barrido else muro2)
            pyxel.rect(px + 1, py + 3, 3, 1, muro2)
            pyxel.rect(px + 4, py + 6, 3, 1, muro2)
            pyxel.rect(px, py + CELL - 1, CELL, 1, SHADOW)
        # la cuenta final, enorme y oscura detrás de todo
        s = (g.hambre + 59) // 60
        if s <= 5 and not g.dead:
            big(W / 2, HUD + ROWS * CELL / 2, "%d" % s, DARKRED, 12, None)
        if g.apple:
            self._manzana(*g.apple)
        for bx, by in g.bayas:
            self._baya(bx, by)
        if g.portales:
            self._portales(g.portales)
        if g.gold:
            self._dorada(g.gold)
        if g.power:
            self._poder(g.power)
        if g.aji:
            self._aji(g.aji)
        if g.raton:
            self._raton(g.raton)
        for a in g.aranas:
            self._arana(a)
        self._culebra(g)
        self.fx.draw(0, 0)
        if self.banner:
            self._draw_banner()
        pyxel.camera()
        # el hambre que se acaba: el borde del tablero late en rojo
        if s <= 5 and not g.dead and (self.f // 8) % 2:
            for k in range(2):
                pyxel.rectb(k, HUD + k, W - 2 * k, H - HUD - 2 * k, RED)
        self.fx.draw_flash(0, HUD, W, H - HUD)
        self._hud()

    def _draw_banner(self):
        s, col, sub, subcol, n, n0 = self.banner
        edad = n0 - n
        esc = 3 + max(0.0, 1.5 - edad * 0.25)    # entra grande y se asienta
        if n < 12 and (n // 2) % 2:
            return
        cy = HUD + 70
        big(W / 2, cy, s, col, esc)
        if sub:
            big(W / 2, cy + 26, sub, subcol, 2 if len(sub) <= 28 else 1)

    def _manzana(self, ax, ay):
        px, py = ax * CELL, HUD + ay * CELL
        c = APPLE if self.eatflash == 0 else APPLE2
        pyxel.circ(px + 4, py + 4, 3, c)
        pyxel.rect(px + 2, py + 2, 2, 2, APPLE2)
        if (self.f // 6) % 8 == 0:               # un brillo cada tanto
            pyxel.pset(px + 2, py + 2, WHITE)
        pyxel.rect(px + 4, py, 1, 2, BODY0)      # el cabito
        pyxel.pset(px + 5, py, BODY1)

    def _baya(self, bx, by):
        px, py = bx * CELL, HUD + by * CELL
        for dx, dy in ((2, 2), (5, 3), (3, 5)):
            pyxel.circ(px + dx, py + dy + ((self.f // 8 + bx) % 2), 1, BERRY)
            pyxel.pset(px + dx, py + dy - 1 + ((self.f // 8 + bx) % 2), BERRY2)

    def _portales(self, portales):
        """las dos bocas, girando en sentidos opuestos para que se lean ligadas."""
        a, b, ttl = portales
        for k, (px_, py_) in enumerate((a, b)):
            if ttl < 120 and (self.f // 4) % 2:
                return
            cx, cy = px_ * CELL + CELL // 2, HUD + py_ * CELL + CELL // 2
            col = GHOST1 if k == 0 else MAGENTA
            pyxel.circb(cx, cy, 3, GHOST2 if k == 0 else SPIDER)
            for i in range(4):
                ang = self.f * (0.14 if k == 0 else -0.14) + i * math.pi / 2
                pyxel.pset(int(cx + math.cos(ang) * 3), int(cy + math.sin(ang) * 3),
                           col)
            pyxel.pset(cx, cy, WHITE)

    def _dorada(self, gold):
        gx, gy, ttl = gold
        px, py = gx * CELL + CELL // 2, HUD + gy * CELL + CELL // 2
        if ttl < 90 and (self.f // 4) % 2:      # titila antes de irse
            return
        r = 3 + (self.f // 6) % 2
        pyxel.circ(px, py, r, GOLD)
        pyxel.circ(px, py, r - 2, GOLD2)
        for i in range(4):                                  # destellos en cruz
            a = self.f * 0.1 + i * math.pi / 2
            pyxel.pset(int(px + 6 * math.cos(a)), int(py + 6 * math.sin(a)), GOLD2)

    def _poder(self, power):
        px_, py_, tipo, ttl = power
        px, py = px_ * CELL, HUD + py_ * CELL
        if ttl < 90 and (self.f // 4) % 2:
            return
        col = GHOST1 if tipo == FANTASMA else MAGENTA
        pyxel.rect(px, py, CELL, CELL, SHADOW)
        pyxel.rectb(px, py, CELL, CELL, col)
        if tipo == FANTASMA:                                # una sabanita
            pyxel.rect(px + 2, py + 2, 4, 3, col)
            pyxel.pset(px + 2, py + 5, col)
            pyxel.pset(px + 4, py + 5, col)
            pyxel.pset(px + 3, py + 3, SHADOW)
        else:                                               # una tijera
            pyxel.line(px + 2, py + 2, px + 5, py + 5, col)
            pyxel.line(px + 5, py + 2, px + 2, py + 5, col)

    def _aji(self, aji):
        ax, ay, ttl = aji
        px, py = ax * CELL, HUD + ay * CELL
        if ttl < 90 and (self.f // 4) % 2:
            return
        # un ají: rojo, curvo, con el cabito verde arriba
        pyxel.rect(px + 2, py + 2, 3, 3, RED)
        pyxel.rect(px + 3, py + 4, 3, 2, RED)
        pyxel.rect(px + 5, py + 5, 2, 2, RED)
        pyxel.pset(px + 7, py + 7, RED)
        pyxel.pset(px + 2, py + 2, ORANGE)
        pyxel.pset(px + 3, py + 3, ORANGE)
        pyxel.rect(px + 1, py, 2, 2, GREEN)
        pyxel.pset(px + 3, py + 1, BODY1)

    def _raton(self, r):
        rx, ry, ttl, _ = r
        if ttl < 90 and (self.f // 4) % 2:
            return
        px, py = rx * CELL, HUD + ry * CELL
        pata = (self.f // 5) % 2
        pyxel.rect(px + 1, py + 3, 5, 3, MOUSE)             # el cuerpo
        pyxel.rect(px + 5, py + 2, 2, 2, MOUSE)             # la cabeza
        pyxel.pset(px + 5, py + 1, MOUSE2)                  # la oreja
        pyxel.pset(px + 7, py + 3, MOUSE2)                  # la nariz
        pyxel.pset(px + 6, py + 2, SHADOW)                  # el ojo
        pyxel.line(px, py + 4, px - 1, py + 3 - pata, MOUSE2)   # la cola
        pyxel.pset(px + 2 + pata, py + 6, MOUSE)
        pyxel.pset(px + 4 - pata, py + 6, MOUSE)

    def _arana(self, a):
        ax, ay, _, _, nace, _ = a
        if nace and (self.f // 4) % 2:
            return                                          # está naciendo
        cx, cy = ax * CELL + 4, HUD + ay * CELL + 4
        leg = SPIDER2 if not nace else LABEL
        p = (self.f // 6) % 2
        for k in (-1, 1):                                   # ocho patas
            pyxel.line(cx, cy, cx + 4 * k, cy - 3 + p, leg)
            pyxel.line(cx, cy, cx + 4 * k, cy + 3 - p, leg)
            pyxel.line(cx, cy, cx + 4 * k, cy - 1 - p, leg)
            pyxel.line(cx, cy, cx + 4 * k, cy + 1 + p, leg)
        pyxel.circ(cx, cy, 2, SPIDER if not nace else DIM)
        pyxel.pset(cx - 1, cy - 1, RED)
        pyxel.pset(cx + 1, cy - 1, RED)

    def _culebra(self, g):
        n = len(g.body)
        fantasma = bool(g.ghost)
        hambre = g.hambre < 5 * 60 and (self.f // 6) % 2
        bultos = set(self.bultos)
        if fantasma:
            pyxel.dither(0.6 if (self.f // 3) % 2 else 0.8)
        # de la cola a la cabeza, así la cabeza queda encima
        for i in range(n - 1, 0, -1):
            cx, cy = g.body[i]
            px, py = cx * CELL, HUD + cy * CELL
            # la cola se afina: las últimas tres celdas, cada vez más chicas
            desde_cola = n - 1 - i
            if n > 5:
                ins = 3 if desde_cola == 0 else (2 if desde_cola == 1 else 1)
            else:
                ins = 2 if desde_cola == 0 else 1
            if i in bultos:
                ins = 0
            if fantasma:
                col, col2 = (GHOST1, GHOST2)
            elif g.turbo and (self.f // 2 + i) % 4 == 0:
                col, col2 = ORANGE, RED
            else:
                col, col2 = (BODY1, BODY0) if (i // 2) % 2 == 0 else (BODY0, BODY1)
            # el puente hacia el segmento de adelante: así se ve un cuerpo y no
            # una fila de cuadraditos
            nx, ny = g.body[i - 1]
            qx, qy = nx * CELL, HUD + ny * CELL
            if abs(nx - cx) + abs(ny - cy) == 1:
                x0, x1 = min(px, qx) + ins, max(px, qx) + CELL - ins
                y0, y1 = min(py, qy) + ins, max(py, qy) + CELL - ins
                if nx != cx:
                    pyxel.rect(x0, py + ins, x1 - x0, CELL - 2 * ins, col)
                else:
                    pyxel.rect(px + ins, y0, CELL - 2 * ins, y1 - y0, col)
            pyxel.rect(px + ins, py + ins, CELL - 2 * ins, CELL - 2 * ins, col)
            if CELL - 2 * ins >= 4:                # las escamas: un punto claro
                pyxel.pset(px + 3, py + 3, col2 if not fantasma else WHITE)
        self._cabeza(g, hambre)
        if fantasma:
            pyxel.dither(1.0)

    def _cabeza(self, g, hambre):
        hx, hy = g.body[0]
        px, py = hx * CELL, HUD + hy * CELL
        dx, dy = g.dir
        if g.ghost:
            col = GHOST1
        elif hambre:
            col = RED
        elif g.turbo and (self.f // 2) % 2:
            col = ORANGE
        else:
            col = HEAD
        # cabeza redondeada: dos rectángulos en cruz
        pyxel.rect(px + 1, py, 6, 8, col)
        pyxel.rect(px, py + 1, 8, 6, col)
        # el lado de atrás se pega al cuello (sin redondear)
        if dx == 1:
            pyxel.rect(px, py, 2, 8, col)
        elif dx == -1:
            pyxel.rect(px + 6, py, 2, 8, col)
        elif dy == 1:
            pyxel.rect(px, py, 8, 2, col)
        else:
            pyxel.rect(px, py + 6, 8, 2, col)
        # los ojos miran hacia donde va; muerta, son dos cruces
        if dx:
            ex = px + (4 if dx > 0 else 2)
            ojos = ((ex, py + 1), (ex, py + 5))
        else:
            ey = py + (4 if dy > 0 else 2)
            ojos = ((px + 1, ey), (px + 5, ey))
        for k, (ox, oy) in enumerate(ojos):
            if g.dead:
                pyxel.line(ox, oy, ox + 1, oy + 1, SHADOW)
                pyxel.line(ox + 1, oy, ox, oy + 1, SHADOW)
                continue
            pyxel.rect(ox, oy, 2, 2, WHITE)
            # la pupila, del lado hacia donde mira
            if dx:
                pyxel.pset(ox + (dx > 0), oy + k, SHADOW)
            else:
                pyxel.pset(ox + k, oy + (dy > 0), SHADOW)
        # la lengua sale cada tanto, bífida
        if not g.dead and (self.f % 70) < 8:
            if dx:
                fx_ = px + (8 if dx > 0 else -1)
                pyxel.pset(fx_, py + 4, RED)
                pyxel.pset(fx_ + dx, py + 3, RED)
                pyxel.pset(fx_ + dx, py + 5, RED)
            else:
                fy_ = py + (8 if dy > 0 else -1)
                pyxel.pset(px + 4, fy_, RED)
                pyxel.pset(px + 3, fy_ + dy, RED)
                pyxel.pset(px + 5, fy_ + dy, RED)

    def _hud(self):
        g = self.g
        pyxel.rect(0, 0, W, HUD, PANEL)
        pyxel.rect(0, HUD - 1, W, 1, FRAME)
        # el puntaje, grande
        sc = "%d" % g.score
        esc = 2.4 if self.score_pop > 4 else 2
        big(3 + len(sc) * 4, 7, sc, GOLD if self.score_pop else WHITE, esc)
        x = 6 + len(sc) * 8
        m = g.mult()
        if m > 1 or g.frenesi:
            t = "x%d" % (m * (FRENESI_X if g.frenesi else 1))
            col = GOLD if (self.f // 6) % 2 else AMBER
            big(x + len(t) * 4 + 1, 7, t, MAGENTA if g.frenesi else col, 2)
            x += len(t) * 8 + 4
        # la mecha de la racha, bajo el multiplicador
        if g.racha:
            fx.bar(3, HUD - 3, 40, 1, g.racha_t / RACHA_TTL, AMBER, PANEL)
        # el hambre, con su manzana: es el reloj de la partida y manda
        hx0 = 98
        frac = g.hambre / HAMBRE
        urge = g.hambre < 5 * 60
        col = RED if (frac < 0.25 and (self.f // 8) % 2) else (
            AMBER if not g.frenesi else MAGENTA)
        pyxel.circ(hx0 - 7, 7, 3, APPLE)
        pyxel.rect(hx0 - 7, 2, 1, 2, BODY1)
        fx.bar(hx0, 3, 76, 6, frac, col, GRID, FRAME if not urge else RED)
        # la reserva: cuánto aire más pueden dar las frutas (la barrita de
        # abajo). cuando se vacía arranca el frenesí
        if g.frenesi:
            if (self.f // 10) % 2:
                text(hx0 + 2, 10, "FRENESÍ x2", MAGENTA)
        else:
            fx.bar(hx0, 11, 76, 2, g.extra / EXTRA_MAX, TEAL, GRID)
        segs = "%ds" % ((g.hambre + 59) // 60)
        text(hx0 + 80, 5, segs, RED if urge else TXT)
        # lo que tienes puesto
        if g.ghost:
            text(198, 2, "FANTASMA", GHOST1)
            fx.bar(198, 9, 30, 2, g.ghost / FANTASMA_TTL, GHOST1, GRID)
        elif g.turbo:
            text(198, 2, "TURBO", ORANGE if (self.f // 4) % 2 else RED)
            fx.bar(198, 9, 30, 2, g.turbo / AJI_TURBO, ORANGE, GRID)
        r = "NV%d" % g.level()
        text(W - len(r) * 4 - 3, 5, r, AMBER)


class Game:
    def __init__(self):
        Cabinet(
            game_id="culebra", title="CULEBRA",
            subtitle="come antes de que se acabe",
            howto=["flechas, wasd o desliza el dedo",
                   "el hambre baja: cada fruta te da aire",
                   "caza al ratón · esquiva las arañas",
                   "sin reserva: frenesí final, todo vale x2"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=LABEL, accent=GREEN,
                        warn=RED, shadow=SHADOW, panel=GRID),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
