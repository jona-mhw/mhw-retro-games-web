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
- **escenarios**: cada nivel cambia el tablero (pradera, desierto, cueva...),
  cada uno con su piso, su borde y su decoración.

el nivel sale de cuánto comiste (no del puntaje): si saliera del puntaje, el
frenesí x2 dispararía niveles, muros y velocidad justo en el final.

los giros van **en cola** (hasta tres): si deslizas dos veces rápido dentro del
mismo paso, se hacen los dos giros, uno por paso. antes el segundo pisaba al
primero y, si era el contrario del rumbo, se perdía — en el celular, con swipe,
eso era morir en una esquina por un giro que sí hiciste.

la pantalla es vertical (252x368) para el celular parado: un campo de 20x26
celdas de 12 px (en el teléfono, ~18 px de pantalla cada una), con el HUD
arriba en números grandes. los escenarios se hornean una vez en imágenes (piso,
borde, decoración y viñeta) y las frutas y bichos son sprites horneados: un
frame es un blt de fondo, un blt por cosa y la culebra con sus capas.

toda la mecánica vive en la clase Culebra, sin pyxel: `frame()` avanza un frame
y devuelve qué pasó. World la juega y la dibuja; el Cabinet le pone título,
attract y récords.
"""
import math
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import big_ctext, big_text, big_width, text

CELL = 12
COLS, ROWS = 20, 26
HUD = 44
BORDE = 6
FX, FY = BORDE, HUD + BORDE                # la esquina del campo
FW, FH = COLS * CELL, ROWS * CELL          # 240 x 312
W, H = FW + 2 * BORDE, HUD + FH + 2 * BORDE  # 252 x 368

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

# --- paleta --------------------------------------------------------------
# rampas de 4-5 tonos por cosa (contorno, sombra, medio, luz, brillo): con eso
# la culebra, las frutas y los muros se pintan con volumen — luz arriba a la
# izquierda, sombra abajo a la derecha — y se despegan del piso.
PAL = []


def _c(*rgb):
    i = len(PAL)
    PAL.extend(rgb)
    return i if len(rgb) == 1 else tuple(range(i, i + len(rgb)))


BG = _c(0x0A0C14)
GRID = _c(0x161C2C)              # fondo de barras
FRAME = _c(0x2C3656)
FRAME2 = _c(0x48557E)
PANEL = _c(0x10162A)
PANEL2 = _c(0x1A2240)
TXT = _c(0xE8ECF5)
DIM = _c(0x5A6480)
LABEL = _c(0x9AA6C8)
SHADOW = _c(0x04050A)
WHITE = _c(0xF6F8FF)
TEAL = _c(0x27969E)
AMBER = _c(0xFFC24A)
GREEN = _c(0x8AC52F)
RED = _c(0xE8383A)
DARKRED = _c(0x561424)
MAGENTA = _c(0xD84AB8)
ORANGE = _c(0xF0882E)

# la culebra: contorno, sombra, medio, cuerpo, luz, brillo, panza
SNAKE = _c(0x0C2606, 0x2A5410, 0x45821A, 0x6CB42A, 0xA6E24A, 0xE2FFA0)
S_O, S_S, S_M, S_C, S_L, S_H = SNAKE
BELLY = _c(0xD8F08A)
HEAD = _c(0x8ED636)
GHOSTR = _c(0x0E2A5E, 0x2E6FB0, 0x5AAEE6, 0x9AE0FF, 0xE6FAFF)
TURBOR = _c(0x4A1006, 0xA83416, 0xE0602A, 0xFFA04A, 0xFFE0A8)
HAMBRER = _c(0x4A0A10, 0x9A1C22, 0xD83434, 0xFF7A6A, 0xFFD8D0)
GHOST1, GHOST2 = GHOSTR[3], GHOSTR[1]

APPLER = _c(0x3A0608, 0x8E1A16, 0xD8382A, 0xFF7A5A, 0xFFE0D0)
APPLE, APPLE2 = APPLER[2], APPLER[3]
LEAF = _c(0x1E5A14, 0x48A02A, 0x8AD84A)
STEM = _c(0x5A3A1A)
GOLDR = _c(0x5A3A00, 0xB07A08, 0xFFC21A, 0xFFE47A, 0xFFFBE0)
GOLD, GOLD2 = GOLDR[2], GOLDR[3]
BERRYR = _c(0x14104A, 0x2E36B0, 0x5A6CFF, 0xB0B8FF, 0xF0F2FF)
BERRY, BERRY2 = BERRYR[2], BERRYR[3]
MOUSER = _c(0x2A2636, 0x6E6880, 0xA8A2B8, 0xDCD8E8, 0xFF9AB8)
MOUSE, MOUSE2 = MOUSER[2], MOUSER[4]
SPIDERR = _c(0x12081E, 0x6A3AB0, 0x8E4EDA, 0xC89AF8, 0xFF3A4A)
SPIDER, SPIDER2 = SPIDERR[2], SPIDERR[3]
CHILIR = _c(0x40080A, 0x9A1A16, 0xE8382A, 0xFF8A6A)

# un escenario por nivel: nombre y sus colores. el piso va oscuro y con poco
# contraste (la textura y la decoración se sienten, pero no compiten con las
# frutas); el borde y los muros sí tienen volumen.
#   piso: hondo, base, alterno, mota  · deco: tres tonos
#   borde/muro: contorno, sombra, medio, luz
ESCENAS_DEF = [
    ("PRADERA", "pasto",
     (0x0A1508, 0x0E1C0C, 0x11210E, 0x1A3014), (0x2A4A1C, 0x6A6898, 0xA8A8C8),
     (0x0A1406, 0x22441A, 0x3A6A26, 0x6A9A44)),
    ("DESIERTO", "arena",
     (0x150E06, 0x1C1409, 0x21180C, 0x2C2112), (0x3A2C16, 0x2E4A22, 0x5A4A30),
     (0x24160A, 0x6A4A22, 0x9A7A46, 0xD2B07A)),
    ("CUEVA", "piedra",
     (0x0A0612, 0x110B1C, 0x150E22, 0x1E1630), (0x2A2040, 0x3AA6B8, 0x8A7AE0),
     (0x08060E, 0x2E2446, 0x4C3E6E, 0x7A6AA0)),
    ("GLACIAR", "hielo",
     (0x081220, 0x0C1828, 0x0F1E30, 0x16283C), (0x22405A, 0x5A8AB0, 0x9AC4E0),
     (0x0A1A2C, 0x3E6E92, 0x7AA8C8, 0xCAEAFA)),
    ("VOLCÁN", "lava",
     (0x120606, 0x190A08, 0x1F0D0A, 0x2A1410), (0x5A1608, 0xC8481A, 0x3A2420),
     (0x100605, 0x3A1C16, 0x5E3024, 0xA04A30)),
    ("NOCHE", "baldosa",
     (0x080A10, 0x0C0E18, 0x10131E, 0x171B2A), (0x1E2A20, 0x3A4060, 0xD8F08A),
     (0x07080D, 0x2A2E40, 0x484E68, 0x7C7E98)),
]
ESCENAS = []
for _n, _k, _piso, _deco, _muro in ESCENAS_DEF:
    ESCENAS.append((_n, _k, _c(*_piso), _c(*_deco), _c(*_muro)))
# en la pradera el borde es un seto, pero los muros son piedras con musgo: si
# fueran verdes se confundirían con la culebra
MURO_PRADERA = _c(0x1A1C16, 0x464C3C, 0x6A7258, 0x9AA482)
FRENESI_PISO = (_c(0x12051A, 0x1A0924, 0x1F0B2B, 0x2E1240),
                _c(0x12051A, 0x1F0B2B, 0x1A0924, 0x3A1650))
FRENESI_DECO = _c(0x5A1E6A, 0xD84AB8, 0xFF9AE0)
FRENESI_BORDE = _c(0x1A0620, 0x5A1A6A, 0xA83AB8, 0xFF8AE8)
KEY = 255                        # el transparente de los sprites
PAL += [0] * (256 - len(PAL))

CHISPA_MANZANA = (WHITE, APPLE2, APPLE, S_M)
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


# --- el arte horneado ----------------------------------------------------------
# los sprites (frutas, bichos, íconos) están escritos como texto, una letra por
# píxel, y se hornean una vez en una hoja. los escenarios (piso con textura,
# borde, decoración y viñeta) también se hornean una vez cada uno: dibujar el
# fondo de un frame es un solo blt.
APPLE_S = [
    "......bG....",
    "......bhgG..",
    "...kkkbkkk..",
    "..kllmmmmmk.",
    ".klwwlmmmmdk",
    ".klwlmmmmmdk",
    ".kllmmmmmmdk",
    ".kmmmmmmmddk",
    ".kmmmmmmmddk",
    "..kmmmmmddk.",
    "..kdddddddk.",
    "...kkk.kkk..",
]
AJI_S = [
    "..Gg........",
    ".GggG.......",
    "..kGkk......",
    "..kmlwk.....",
    "..kmllmk....",
    "...kmmlmk...",
    "....kmmmmk..",
    ".....kmmmdk.",
    "......kmmdk.",
    ".......kmdk.",
    "........kdk.",
    ".........k..",
]
MOUSE_S = [
    "........kk..",
    ".......kppk.",
    "...kkkkkkpk.",
    "..kllllllkk.",
    ".kllmmmmmlk.",
    ".klmmmmmmlek",
    "kllmmmmmmmmp",
    "kdmmmmmmmmk.",
    ".kdmmmmmddk.",
    "..kddddddk..",
    "...k...k....",
    "............",
]
MOUSE_S2 = MOUSE_S[:10] + ["....k...k...", "............"]
BAYA6 = [".kkkk.", "kwlmmk", "klmmmk", "kmmmdk", "kmmddk", ".kkkk."]
GHOST_S = [
    "...kkkk...",
    "..kllllk..",
    ".kllllllk.",
    ".klkllkmk.",
    ".klkllkmk.",
    ".kllllmmk.",
    ".klmmmmdk.",
    ".kmmmmmdk.",
    ".kmkmmkdk.",
    ".kk.kk.kk.",
]
TIJERA_S = [
    "l.......l.",
    "kl.....lk.",
    ".kl...lk..",
    "..kl.lk...",
    "...klk....",
    "...rkr....",
    "..rr.rr...",
    ".r..r..r..",
    ".r..r..r..",
    "..rr.rr...",
]
C = CELL
SP = {"apple": 0, "gold": C, "aji": 2 * C, "mouse": 3 * C, "mouse2": 4 * C,
      "baya": 5 * C, "ghost": 6 * C, "tijera": 6 * C + 10}
MURO_V = C                                    # fila de los muros, uno por escena

_SHEET = None
_ESCENAS_IMG = {}


def _stamp(img, u, v, rows, cmap):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = cmap.get(ch)
            if c is not None:
                img.pset(u + x, v + y, c)


def _muro(img, u, v, kind, r):
    """un bloque de muro con volumen: tapa clara arriba, cara, sombra."""
    o, s, m, l = r
    img.rect(u, v, C, C, o)
    img.rect(u + 1, v + 1, C - 2, C - 2, m)
    img.rect(u + 1, v + 1, C - 2, 3, l)
    img.rect(u + 1, v + C - 3, C - 2, 2, s)
    img.rect(u + C - 2, v + 4, 1, C - 7, s)
    img.pset(u + 1, v + 1, WHITE if kind == "hielo" else l)
    if kind in ("arena", "baldosa"):         # ladrillos
        img.rect(u + 1, v + 6, C - 2, 1, s)
        img.rect(u + 5, v + 4, 1, 2, s)
        img.rect(u + 3, v + 7, 1, 2, s)
        img.rect(u + 8, v + 7, 1, 2, s)
    elif kind == "hielo":                    # brillo de hielo
        img.line(u + 2, v + 8, u + 6, v + 4, l)
        img.line(u + 5, v + 8, u + 8, v + 5, l)
    elif kind == "lava":                     # basalto con una grieta encendida
        img.line(u + 3, v + 4, u + 5, v + 6, CHILIR[2])
        img.line(u + 5, v + 6, u + 8, v + 7, CHILIR[2])
        img.pset(u + 5, v + 6, AMBER)
    else:                                    # piedra: motas
        img.pset(u + 3, v + 6, s)
        img.pset(u + 7, v + 7, l)
        img.pset(u + 6, v + 5, s)
        img.pset(u + 4, v + 8, s)


def sheet():
    global _SHEET
    if _SHEET is None:
        img = pyxel.Image(128, 2 * C)
        img.cls(KEY)
        ar = APPLER
        _stamp(img, SP["apple"], 0, APPLE_S,
               {"k": ar[0], "d": ar[1], "m": ar[2], "l": ar[3], "w": ar[4],
                "g": LEAF[1], "G": LEAF[0], "h": LEAF[2], "b": STEM})
        gr = GOLDR
        _stamp(img, SP["gold"], 0, APPLE_S,
               {"k": gr[0], "d": gr[1], "m": gr[2], "l": gr[3], "w": gr[4],
                "g": gr[3], "G": gr[1], "h": gr[4], "b": gr[1]})
        cr = CHILIR
        _stamp(img, SP["aji"], 0, AJI_S,
               {"k": cr[0], "d": cr[1], "m": cr[2], "l": cr[3], "w": WHITE,
                "g": LEAF[1], "G": LEAF[0]})
        mr = MOUSER
        mm = {"k": mr[0], "d": mr[1], "m": mr[2], "l": mr[3], "p": mr[4],
              "e": SHADOW}
        _stamp(img, SP["mouse"], 0, MOUSE_S, mm)
        _stamp(img, SP["mouse2"], 0, MOUSE_S2, mm)
        br = BERRYR
        bm = {"k": br[0], "d": br[1], "m": br[2], "l": br[3], "w": br[4]}
        for ox, oy in ((0, 1), (6, 2), (3, 6)):
            _stamp(img, SP["baya"] + ox, oy, BAYA6, bm)
        img.pset(SP["baya"] + 5, 0, LEAF[2])
        img.pset(SP["baya"] + 6, 0, LEAF[1])
        gh = GHOSTR
        _stamp(img, SP["ghost"], 0, GHOST_S,
               {"k": gh[0], "d": gh[1], "m": gh[3], "l": gh[4]})
        _stamp(img, SP["tijera"], 0, TIJERA_S,
               {"k": MOUSER[1], "l": MOUSER[3], "r": MAGENTA})
        for i, (_, kind, _, _, muro) in enumerate(ESCENAS):
            _muro(img, i * C, MURO_V, "piedra" if i == 0 else kind,
                  MURO_PRADERA if i == 0 else muro)
        _SHEET = img
    return _SHEET


def _ladrillos(img, x, y, w, h, bw, bh, mortero, luz):
    """ladrillos trabados en el rectángulo (para los bordes de piedra)."""
    for k, yy in enumerate(range(y, y + h, bh)):
        img.rect(x, yy, w, 1, mortero)
        if luz is not None:
            img.rect(x, yy + 1, w, 1, luz)
        off = (bw // 2) * (k % 2)
        for xx in range(x - off, x + w, bw):
            if x <= xx < x + w:
                img.rect(xx, yy, 1, bh, mortero)


def _borde(img, kind, r, rng):
    """el marco del campo, con la textura del escenario."""
    o, s, m, l = r
    w, h = W, H - HUD
    img.rect(0, 0, w, h, m)
    zonas = ((0, 0, w, BORDE), (0, h - BORDE, w, BORDE),
             (0, 0, BORDE, h), (w - BORDE, 0, BORDE, h))
    if kind == "pasto":                      # un seto: hojas en dos tonos
        for zx, zy, zw, zh in zonas:
            for _ in range(zw * zh // 3):
                img.pset(zx + rng.randrange(zw), zy + rng.randrange(zh),
                         l if rng.random() < 0.4 else s)
    elif kind in ("arena", "baldosa"):
        for zx, zy, zw, zh in zonas:
            _ladrillos(img, zx, zy, zw, zh, 10 if kind == "arena" else 8, 3, s, None)
    elif kind == "hielo":
        for zx, zy, zw, zh in zonas:
            _ladrillos(img, zx, zy, zw, zh, 14, 6, s, l)
            for _ in range(zw * zh // 40):
                img.pset(zx + rng.randrange(zw), zy + rng.randrange(zh), WHITE)
    else:                                    # roca (cueva, volcán, frenesí)
        for zx, zy, zw, zh in zonas:
            for _ in range(zw * zh // 14):
                cx, cy = zx + rng.randrange(zw), zy + rng.randrange(zh)
                img.rect(cx, cy, 2, 2, s if rng.random() < 0.6 else l)
            if kind == "lava":
                for _ in range(zw * zh // 90):
                    cx, cy = zx + rng.randrange(zw), zy + rng.randrange(zh)
                    img.line(cx, cy, cx + rng.randrange(-3, 4), cy + rng.randrange(-3, 4),
                             CHILIR[2])
    # el filo: luz arriba-izquierda, sombra abajo-derecha, contorno afuera y
    # adentro (el campo queda hundido)
    img.rect(0, 0, w, 1, l)
    img.rect(0, 0, 1, h, l)
    img.rect(0, h - 1, w, 1, o)
    img.rect(w - 1, 0, 1, h, o)
    img.rectb(BORDE - 1, BORDE - 1, FW + 2, FH + 2, o)


def _decorar(img, kind, deco, piso, rng):
    """la decoración del piso: tenue, nunca del color de una fruta."""
    d1, d2, d3 = deco
    hondo, base, alt, mota = piso

    def celda():
        return (BORDE + rng.randrange(COLS) * CELL + rng.randrange(4),
                BORDE + rng.randrange(ROWS) * CELL + rng.randrange(4))

    if kind == "pasto":
        for _ in range(70):                  # matas de pasto
            x, y = celda()
            for dx, dy in ((0, 2), (1, 1), (2, 3), (3, 0), (4, 2), (5, 1)):
                if rng.random() < 0.8:
                    img.pset(x + dx, y + dy + 3, d1)
        for _ in range(18):                  # florcitas lila con centro claro
            x, y = celda()
            x, y = x + 3, y + 3
            for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                img.pset(x + dx, y + dy, d2)
            img.pset(x, y, d3)
    elif kind == "arena":
        for _ in range(60):                  # ondas de la arena
            x, y = celda()
            for k in range(8):
                img.pset(x + k, y + 4 + (1 if k in (2, 3, 4) else 0), mota)
        for _ in range(7):                   # cactus chicos
            x, y = celda()
            img.rect(x + 4, y + 1, 2, 7, d2)
            img.rect(x + 2, y + 3, 1, 3, d2)
            img.rect(x + 2, y + 5, 2, 1, d2)
            img.rect(x + 7, y + 2, 1, 3, d2)
            img.rect(x + 6, y + 4, 1, 1, d2)
        for _ in range(26):                  # piedritas
            x, y = celda()
            img.rect(x + 3, y + 5, 2, 1, d3)
            img.pset(x + 3, y + 4, mota)
    elif kind == "piedra":
        for _ in range(40):                  # piedras del piso
            x, y = celda()
            img.elli(x + 1, y + 3, 6, 4, d1)
            img.pset(x + 2, y + 3, mota)
        for _ in range(12):                  # cristales que brillan apenas
            x, y = celda()
            c = d2 if rng.random() < 0.5 else d3
            img.line(x + 4, y + 1, x + 4, y + 7, c)
            img.line(x + 3, y + 3, x + 3, y + 6, c)
            img.pset(x + 5, y + 4, c)
            img.pset(x + 4, y + 1, WHITE)
    elif kind == "hielo":
        for _ in range(26):                  # grietas
            x, y = celda()
            for _k in range(10):
                nx, ny = x + rng.randrange(-1, 3), y + rng.randrange(-1, 3)
                img.line(x, y, nx, ny, d1)
                x, y = nx, ny
        for _ in range(110):                 # escarcha
            x, y = celda()
            img.pset(x + rng.randrange(8), y + rng.randrange(8), d2)
        for _ in range(10):
            x, y = celda()
            img.pset(x + 4, y + 4, d3)
            img.pset(x + 3, y + 4, d2)
            img.pset(x + 5, y + 4, d2)
            img.pset(x + 4, y + 3, d2)
            img.pset(x + 4, y + 5, d2)
    elif kind == "lava":
        for _ in range(18):                  # grietas con brasa adentro
            x, y = celda()
            pts = [(x, y)]
            for _k in range(9):
                x, y = x + rng.randrange(-1, 3), y + rng.randrange(-1, 3)
                pts.append((x, y))
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                img.line(ax, ay, bx, by, d1)
            for ax, ay in pts[2:-2:2]:
                img.pset(ax, ay, d2)
        for _ in range(26):                  # rocas de ceniza
            x, y = celda()
            img.elli(x + 2, y + 3, 5, 3, d3)
            img.pset(x + 3, y + 3, mota)
    elif kind == "baldosa":
        for y in range(0, ROWS, 2):          # un patio de baldosas grandes
            for x in range((y // 2) % 2, COLS, 2):
                img.rectb(BORDE + x * CELL, BORDE + y * CELL, 2 * CELL, 2 * CELL, hondo)
        for _ in range(60):                  # musgo entre las baldosas
            x, y = celda()
            img.pset(x, y, d1)
            img.pset(x + 1, y, d1)
    else:                                    # frenesí: destellitos
        for _ in range(40):
            x, y = celda()
            x, y = x + 4, y + 4
            img.pset(x, y, d2)
            img.pset(x - 1, y, d1)
            img.pset(x + 1, y, d1)
            img.pset(x, y - 1, d1)
            img.pset(x, y + 1, d1)


def _hornear(kind, piso, deco, borde, seed):
    hondo, base, alt, mota = piso
    rng = random.Random(seed * 7919 + 13)
    img = pyxel.Image(W, H - HUD)
    _borde(img, kind, borde, rng)
    img.rect(BORDE, BORDE, FW, FH, base)
    for y in range(ROWS):                     # el damero, apenas
        for x in range(y & 1, COLS, 2):
            img.rect(BORDE + x * CELL, BORDE + y * CELL, CELL, CELL, alt)
    for _ in range(900):                      # motas: el piso tiene grano
        img.pset(BORDE + rng.randrange(FW), BORDE + rng.randrange(FH),
                 mota if rng.random() < 0.6 else hondo)
    _decorar(img, kind, deco, piso, rng)
    # viñeta: el piso se oscurece hacia las orillas, y la sombra del borde cae
    # adentro arriba y a la izquierda (el campo está hundido)
    for k, a in enumerate((0.5, 0.25, 0.125)):
        img.dither(a)
        for j in range(3):
            d = k * 3 + j
            img.rectb(BORDE + d, BORDE + d, FW - 2 * d, FH - 2 * d, hondo)
    img.dither(0.5)
    img.rect(BORDE, BORDE, FW, 3, SHADOW)
    img.rect(BORDE, BORDE, 3, FH, SHADOW)
    img.dither(1.0)
    img.rect(BORDE, BORDE, FW, 1, SHADOW)
    img.rect(BORDE, BORDE, 1, FH, SHADOW)
    return img


def escena_img(k):
    """el escenario k (0..5), o el frenesí ("f0", "f1"), horneado y en caché."""
    img = _ESCENAS_IMG.get(k)
    if img is None:
        if k in ("f0", "f1"):
            piso = FRENESI_PISO[0 if k == "f0" else 1]
            img = _hornear("frenesi", piso, FRENESI_DECO, FRENESI_BORDE, 99)
        else:
            _, kind, piso, deco, muro = ESCENAS[k]
            img = _hornear(kind, piso, deco, muro, k)
        _ESCENAS_IMG[k] = img
    return img


class World:
    """la culebra jugándose: input, dibujo y chispas. el Cabinet la envuelve."""

    def __init__(self):
        self.g = Culebra()
        self.fx = fx.Fx(gravity=0.0, max_parts=320)
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
        self.raton_mira = 1          # para dónde mira el ratón (1 der, -1 izq)
        self.raton_x = None
        sheet()
        for k in list(range(len(ESCENAS))) + ["f0", "f1"]:
            escena_img(k)            # todo horneado antes de la cuenta 3-2-1

    @property
    def over(self):
        return self.g.dead

    @property
    def score(self):
        return self.g.score

    def _px(self, cx, cy):
        return FX + cx * CELL + CELL / 2, FY + cy * CELL + CELL / 2

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
                self.fx.burst(x, y, (WHITE, AMBER, ORANGE, RED), n=4, speed=1.0,
                              life=16)
        if g.raton:
            if self.raton_x is not None and g.raton[0] != self.raton_x:
                self.raton_mira = 1 if g.raton[0] > self.raton_x else -1
            self.raton_x = g.raton[0]
        else:
            self.raton_x = None
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
        if g.frenesi and self.f % 3 == 0:       # chispas de frenesí desde arriba
            x = FX + (self.f * 53) % FW
            self.fx.burst(x, FY + 2, (WHITE, MAGENTA, BERRY2), n=1, speed=0.9,
                          life=40, angle=math.pi / 2, spread=0.6)
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
            self.fx.burst(x, y, CHISPA_MANZANA, n=14, speed=1.7, life=20)
            self.eatflash = 4
            self.bultos.append(0)
            self.score_pop = 8
            if e[3] > 1:
                self.fx.popup(x, y - 8, "+%d" % e[3], AMBER, life=30)
        elif kind == "baya":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, BERRY2, BERRY, MAGENTA), n=12, speed=1.7,
                          life=18)
            self.fx.popup(x, y - 8, "+%d" % e[3], BERRY2, life=26)
            self.score_pop = 8
        elif kind == "racha":
            self._cartel("RACHA x%d" % e[3], GOLD, "¡SIGUE COMIENDO!", AMBER, 55)
            self.fx.destello(AMBER)
            self.fx.shake(2)
        elif kind == "racha_fria":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 12, "racha fría", LABEL)
        elif kind == "aji":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, ORANGE, RED, APPLE), n=24, speed=2.6,
                          life=28)
            self._cartel("¡AJÍ!", ORANGE, "TURBO +%d" % e[3], WHITE, 45)
            self.fx.destello(ORANGE)
            self.fx.shake(3)
            self.bultos.append(0)
        elif kind == "dorada":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_DORADA, n=28, speed=2.8, life=32)
            self._cartel("¡DORADA!", GOLD, "+%d" % e[3], WHITE, 45)
            self.fx.destello(GOLD)
            self.fx.shake(2)
            self.bultos.append(0)
        elif kind == "dorada_ida":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (GOLD2, GOLD, AMBER), n=10, speed=1.0, life=18)
        elif kind == "poder":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, CHISPA_PODER, n=22, speed=2.4, life=30)
            sub = "COME ARAÑAS" if e[3] == FANTASMA and self.g.aranas else None
            self._cartel(PODER_NOMBRE[e[3]], GHOST1 if e[3] == FANTASMA else MAGENTA,
                         sub, WHITE, 45)
            self.fx.destello(GHOST1)
        elif kind == "portal":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, MAGENTA, GHOST1, GHOST2), n=14,
                          speed=1.9, life=20)
        elif kind == "raton":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 10, "un ratón", MOUSE, life=40)
        elif kind == "raton_comido":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, MOUSER[3], MOUSE, DIM), n=22, speed=2.4,
                          life=26)
            self._cartel("¡ÑAM!", MOUSE2, "RATÓN +%d" % e[3], WHITE, 45)
            self.fx.shake(3)
            self.bultos += [0, 1]
        elif kind == "raton_ido":
            x, y = self._px(e[1], e[2])
            self.fx.popup(x, y - 8, "se escapó", LABEL)
            self.fx.burst(x, y, (MOUSE, DIM), n=8, speed=1.2, life=14)
        elif kind == "arana":
            if len(self.g.aranas) == 1 and self.g.niv == ARANA_DESDE:
                self._cartel("¡ARAÑA!", SPIDER2, "NO LA CHOQUES", WHITE, 60)
        elif kind == "arana_comida":
            x, y = self._px(e[1], e[2])
            self.fx.burst(x, y, (WHITE, SPIDER2, SPIDER, GHOST1), n=26, speed=2.6,
                          life=28)
            self._cartel("¡CRUNCH!", SPIDER2, "+%d" % e[3], WHITE, 45)
            self.fx.shake(4)
        elif kind == "frenesi":
            self._cartel("¡FRENESÍ!", MAGENTA, "TODO VALE x2", GOLD, 110)
            self.fx.popup(W / 2, FY + 190, "se acabó la reserva: junta todo",
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
            self.fx.burst(x, y, (WHITE, RED, APPLE2, S_M), n=36, speed=3.0,
                          life=36)
            self.fx.shake(6)
            self.fx.destello(RED, 6)

    # --- dibujo ----------------------------------------------------------
    def _fondo(self):
        """el escenario horneado. al cambiar de nivel, el nuevo entra como un
        telón de izquierda a derecha."""
        g = self.g
        if g.frenesi:
            pyxel.blt(0, HUD, escena_img("f0" if (self.f // 10) % 2 else "f1"),
                      0, 0, W, H - HUD)
            return
        nuevo = escena_img(self.escena)
        if not self.barrido:
            pyxel.blt(0, HUD, nuevo, 0, 0, W, H - HUD)
            return
        corte = int(W * (1 - self.barrido / 24))
        if corte > 0:
            pyxel.blt(0, HUD, nuevo, 0, 0, corte, H - HUD)
        pyxel.blt(corte, HUD, escena_img(self.escena_vieja), corte, 0, W - corte,
                  H - HUD)
        pyxel.rect(corte - 1, HUD, 2, H - HUD, WHITE)

    def _ambiente(self):
        """lo que se mueve en el escenario: luciérnagas de noche, brasas en el
        volcán, copos en el glaciar. pocos píxeles, detrás de todo."""
        g = self.g
        if g.frenesi:
            return
        kind = ESCENAS[self.escena][1]
        f = self.f
        if kind == "baldosa":
            for i in range(7):
                x = FX + (i * 71 + int(18 * math.sin(f / 50 + i * 2))) % FW
                y = FY + (i * 113 + int(14 * math.cos(f / 60 + i))) % FH
                if (f // 20 + i) % 5:
                    pyxel.pset(x, y, ESCENAS_DECO_LUZ)
                    pyxel.dither(0.3)
                    pyxel.rect(x - 1, y - 1, 3, 3, ESCENAS_DECO_LUZ)
                    pyxel.dither(1.0)
        elif kind == "lava":
            for i in range(6):
                x = FX + (i * 41 + f // 3) % FW
                y = FY + FH - ((f * (1 + i % 3) // 2 + i * 57) % FH)
                pyxel.pset(x, y, ORANGE if i % 2 else AMBER)
        elif kind == "hielo":
            for i in range(8):
                x = FX + (i * 31 + int(6 * math.sin(f / 40 + i))) % FW
                y = FY + ((f // 2 + i * 41) % FH)
                pyxel.pset(x, y, WHITE)

    def draw(self):
        g = self.g
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)                    # el temblor, sin tocar el HUD
        self._fondo()
        self._ambiente()
        self._muros()
        # la cuenta final, enorme y oscura detrás de todo
        s = (g.hambre + 59) // 60
        if s <= 5 and not g.dead:
            big_ctext(W / 2, FY + FH / 2 - 42, "%d" % s, DARKRED, 14)
        if g.portales:
            self._portales(g.portales)
        if g.apple:
            self._fruta("apple", g.apple[0], g.apple[1])
        for bx, by in g.bayas:
            self._fruta("baya", bx, by, fase=bx + by)
        if g.gold:
            self._dorada(g.gold)
        if g.power:
            self._poder(g.power)
        if g.aji:
            if not (g.aji[2] < 90 and (self.f // 4) % 2):
                self._fruta("aji", g.aji[0], g.aji[1])
        if g.raton:
            self._raton(g.raton)
        for a in g.aranas:
            self._arana(a)
        self._culebra(g)
        self._chispas()
        if self.banner:
            self._draw_banner()
        pyxel.camera()
        # el hambre que se acaba: el borde del campo late en rojo
        if s <= 5 and not g.dead and (self.f // 8) % 2:
            for k in range(3):
                pyxel.rectb(FX - BORDE + k, FY - BORDE + k, W - 2 * k,
                            FH + 2 * BORDE - 2 * k, RED)
        self.fx.draw_flash(FX, FY, FW, FH)
        self._hud()

    def _chispas(self):
        """las chispas de fx de 2x2 mientras están vivas, y los carteles que
        suben con texto grande."""
        rect = pyxel.rect
        for x, y, _, _, vida, vida0, ramp, _ in self.fx.parts:
            i = int((1.0 - vida / vida0) * len(ramp))
            c = ramp[min(i, len(ramp) - 1)]
            if vida * 2 > vida0:
                rect(int(x), int(y), 2, 2, c)
            else:
                pyxel.pset(int(x), int(y), c)
        t = self.fx.t
        for x, y, _, s, col, vida, vida0 in self.fx.pops:
            if vida < vida0 * 0.35 and (t // 3) % 2:
                continue
            sc = 2 if len(s) <= 12 else 1
            hw = big_width(s, sc) / 2
            x = min(max(x, FX + hw + 2), FX + FW - hw - 2)   # que no se salga
            big_ctext(x, int(y) - 6, s, col, sc, SHADOW)

    def _draw_banner(self):
        s, col, sub, subcol, n, n0 = self.banner
        edad = n0 - n
        if n < 12 and (n // 2) % 2:
            return
        tope = 5 if big_width(s, 5) <= FW - 10 else (4 if big_width(s, 4) <= FW else 3)
        esc = tope + (1 if edad < 5 and big_width(s, tope + 1) <= W else 0)
        cy = FY + 96
        big_ctext(W / 2 + 2, cy + 2, s, SHADOW, esc)
        big_ctext(W / 2, cy, s, col, esc)
        if sub:
            sc = 2 if big_width(sub, 2) <= FW else 1
            yy = cy + 6 * esc + 10
            big_ctext(W / 2 + 1, yy + 1, sub, SHADOW, sc)
            big_ctext(W / 2, yy, sub, subcol, sc)

    def _sombra(self, px, py, w=9):
        """la sombra de una cosa sobre el piso: una mancha oscura."""
        pyxel.elli(px + (C - w) // 2 + 1, py + C - 4, w, 4, SHADOW)

    def _fruta(self, nombre, cx, cy, fase=0):
        px, py = FX + cx * C, FY + cy * C
        bob = 1 if (self.f // 12 + fase) % 2 else 0     # flota apenas
        self._sombra(px, py)
        pyxel.blt(px, py - 1 - bob, _SHEET, SP[nombre], 0, C, C, KEY)
        if nombre == "apple":
            if self.eatflash:
                pyxel.rect(px + 2, py + 3 - bob, 3, 3, WHITE)
            elif (self.f // 6) % 10 == 0:              # un brillo cada tanto
                pyxel.pset(px + 3, py + 3 - bob, WHITE)

    def _muros(self):
        g = self.g
        if not g.walls:
            return
        u = self.escena * C
        for wx, wy in g.walls:                    # la sombra proyectada
            pyxel.rect(FX + wx * C + 2, FY + wy * C + 3, C, C, SHADOW)
        for wx, wy in g.walls:
            px, py = FX + wx * C, FY + wy * C
            pyxel.blt(px, py, _SHEET, u, MURO_V, C, C)
            if self.barrido:
                pyxel.rect(px + 1, py + 1, C - 2, 1, WHITE)

    def _portales(self, portales):
        """las dos bocas, girando en sentidos opuestos para que se lean ligadas."""
        a, b, ttl = portales
        if ttl < 120 and (self.f // 4) % 2:
            return
        for k, (cx_, cy_) in enumerate((a, b)):
            cx, cy = FX + cx_ * C + C // 2, FY + cy_ * C + C // 2
            col, col2 = (GHOST1, GHOST2) if k == 0 else (MAGENTA, SPIDERR[1])
            pyxel.circ(cx, cy, 6, SHADOW)
            pyxel.circb(cx, cy, 6, col2)
            pyxel.circb(cx, cy, 3 + (self.f // 8) % 2, col)
            for i in range(4):
                ang = self.f * (0.14 if k == 0 else -0.14) + i * math.pi / 2
                pyxel.rect(int(cx + math.cos(ang) * 5), int(cy + math.sin(ang) * 5),
                           1 + (i == 0), 1 + (i == 0), WHITE)
            pyxel.rect(cx - 1, cy - 1, 2, 2, WHITE)

    def _dorada(self, gold):
        gx, gy, ttl = gold
        if ttl < 90 and (self.f // 4) % 2:      # titila antes de irse
            return
        px, py = FX + gx * C, FY + gy * C
        self._sombra(px, py)
        bob = 1 if (self.f // 10) % 2 else 0
        pyxel.blt(px, py - 1 - bob, _SHEET, SP["gold"], 0, C, C, KEY)
        cx, cy = px + 6, py + 6 - bob
        for i in range(4):                                  # destellos que giran
            a = self.f * 0.08 + i * math.pi / 2
            x, y = int(cx + 10 * math.cos(a)), int(cy + 10 * math.sin(a))
            pyxel.pset(x, y, GOLD2)
            if (self.f // 4 + i) % 3 == 0:
                pyxel.pset(x + 1, y, WHITE)
                pyxel.pset(x - 1, y, WHITE)
                pyxel.pset(x, y + 1, WHITE)
                pyxel.pset(x, y - 1, WHITE)

    def _poder(self, power):
        px_, py_, tipo, ttl = power
        if ttl < 90 and (self.f // 4) % 2:
            return
        px, py = FX + px_ * C, FY + py_ * C
        self._sombra(px, py, 11)
        col = GHOST1 if tipo == FANTASMA else MAGENTA
        bob = 1 if (self.f // 12) % 2 else 0
        cx, cy = px + 6, py + 5 - bob
        pyxel.circ(cx, cy, 7, SHADOW)
        pyxel.circ(cx, cy, 6, PANEL2)
        pyxel.circb(cx, cy, 7, col if (self.f // 10) % 2 else FRAME2)
        pyxel.pset(cx - 4, cy - 4, WHITE)
        pyxel.blt(cx - 5, cy - 5, _SHEET, SP["ghost" if tipo == FANTASMA else "tijera"],
                  0, 10, 10, KEY)

    def _raton(self, r):
        rx, ry, ttl, _ = r
        if ttl < 90 and (self.f // 4) % 2:
            return
        px, py = FX + rx * C, FY + ry * C
        self._sombra(px, py, 11)
        m = self.raton_mira
        u = SP["mouse2" if (self.f // 5) % 2 else "mouse"]
        pyxel.blt(px, py - 1, _SHEET, u, 0, C * m, C, KEY)
        cola = 1 if (self.f // 6) % 2 else -1               # la cola se menea
        if m > 0:
            pyxel.line(px, py + 6, px - 2, py + 5, MOUSER[1])
            pyxel.line(px - 2, py + 5, px - 4, py + 5 + cola, MOUSER[1])
        else:
            pyxel.line(px + 11, py + 6, px + 13, py + 5, MOUSER[1])
            pyxel.line(px + 13, py + 5, px + 15, py + 5 + cola, MOUSER[1])

    def _arana(self, a):
        ax, ay, _, _, nace, _ = a
        if nace and (self.f // 4) % 2:
            return                                          # está naciendo
        px, py = FX + ax * C, FY + ay * C
        cx, cy = px + 6, py + 6
        o, s, m, l, ojo = SPIDERR
        if nace:
            s, m, l = DIM, LABEL, TXT
        self._sombra(px, py, 12)
        p = (self.f // 6) % 2
        for k in (-1, 1):                                   # ocho patas
            for dy0, dy1 in ((-2, -5 + p), (0, -2 - p), (1, 3 + p), (2, 6 - p)):
                pyxel.line(cx, cy + dy0, cx + 3 * k, cy + dy0 - 2, o)
                pyxel.line(cx + 3 * k, cy + dy0 - 2, cx + 6 * k, cy + dy1, s)
        pyxel.circ(cx, cy + 1, 4, o)                        # el abdomen
        pyxel.circ(cx, cy + 1, 3, m)
        pyxel.rect(cx - 2, cy - 1, 2, 2, l)
        pyxel.rect(cx - 1, cy + 2, 2, 2, o)                 # una marca
        pyxel.rect(cx - 2, cy - 5, 5, 3, o)                 # la cabeza
        pyxel.rect(cx - 1, cy - 5, 1, 1, ojo)
        pyxel.rect(cx + 1, cy - 5, 1, 1, ojo)

    def _culebra(self, g):
        """la culebra por capas: sombra en el piso, contorno, cuerpo, anillos y
        un bisel de luz y sombra sólo en los lados que no se pegan a otro
        segmento: así un tramo recto se ve como un tubo continuo."""
        body = g.body
        n = len(body)
        fantasma = bool(g.ghost)
        bultos = set(self.bultos)
        if fantasma:
            O, S, M, Cc, L = GHOSTR
        else:
            O, S, M, Cc, L = S_O, S_S, S_M, S_C, S_L
        piezas = []
        for i in range(n):
            cx, cy = body[i]
            px, py = FX + cx * C, FY + cy * C
            desde_cola = n - 1 - i
            if i == 0:
                ins = 0
            elif n > 5:
                ins = 4 if desde_cola == 0 else (3 if desde_cola == 1 else
                                                 (2 if desde_cola == 2 else 1))
            else:
                ins = 3 if desde_cola == 0 else 1
            if i in bultos and i:
                ins = 0
            x0, y0, x1, y1 = px + ins, py + ins, px + C - ins, py + C - ins
            conn = 0                                        # bits: der izq aba arr
            for j in (i - 1, i + 1):
                if 0 <= j < n:
                    qx, qy = body[j]
                    dx, dy = qx - cx, qy - cy
                    if abs(dx) + abs(dy) != 1:
                        continue                            # salto de portal
                    if dx == 1:
                        x1 = px + C
                        conn |= 1
                    elif dx == -1:
                        x0 = px
                        conn |= 2
                    elif dy == 1:
                        y1 = py + C
                        conn |= 4
                    else:
                        y0 = py
                        conn |= 8
            piezas.append((x0, y0, x1 - x0, y1 - y0, conn, i))
        rect = pyxel.rect
        if fantasma:
            pyxel.dither(0.65 if (self.f // 3) % 2 else 0.85)
        else:
            for x, y, w, h, _, _ in piezas:                 # la sombra en el piso
                rect(x + 2, y + 3, w, h, SHADOW)
        for x, y, w, h, _, i in piezas[1:]:
            rect(x - 1, y - 1, w + 2, h + 2, O)
        turbo = g.turbo
        for x, y, w, h, conn, i in reversed(piezas[1:]):
            if turbo and (self.f // 2 + i) % 4 == 0:
                c, l, s, m = TURBOR[2], TURBOR[3], TURBOR[1], TURBOR[1]
            else:
                c, l, s, m = Cc, L, S, M
            rect(x, y, w, h, c)
            b = 1 if min(w, h) <= 6 else 2
            # los anillos: uno de cada dos segmentos lleva una franja oscura
            # de través; el otro, una mancha clara de panza
            if min(w, h) >= 6:
                cx = FX + body[i][0] * C + C // 2 - 1
                cy = FY + body[i][1] * C + C // 2 - 1
                if i % 2 == 0:
                    if conn & 12 and not conn & 3:          # va vertical
                        rect(x, cy, w, 2, m)
                    else:
                        rect(cx, y, 2, h, m)
                else:
                    rect(cx, cy, 2, 2, BELLY if not fantasma else l)
            if not conn & 8:
                rect(x, y, w, b, l)
            if not conn & 2:
                rect(x, y, b, h, l)
            if not conn & 4:
                rect(x, y + h - b, w, b, s)
            if not conn & 1:
                rect(x + w - b, y, b, h, s)
        self._cabeza(g, piezas[0][4], O, S, L)
        if fantasma:
            pyxel.dither(1.0)

    def _cabeza(self, g, conn, O, S, L):
        hx, hy = g.body[0]
        px, py = FX + hx * C, FY + hy * C
        dx, dy = g.dir
        hambre = g.hambre < 5 * 60 and (self.f // 6) % 2
        if g.ghost:
            col = GHOSTR[3]
        elif hambre:
            O, S, col, L = HAMBRER[0], HAMBRER[1], HAMBRER[2], HAMBRER[3]
        elif g.turbo and (self.f // 2) % 2:
            O, S, col, L = TURBOR[0], TURBOR[1], TURBOR[2], TURBOR[3]
        else:
            col = HEAD
        rect = pyxel.rect
        h = C // 2
        # cabeza redondeada (contorno y relleno en cruz), pegada al cuello
        rect(px - 1, py + 1, C + 2, C - 2, O)
        rect(px + 1, py - 1, C - 2, C + 2, O)
        rect(px, py, C, C, O)
        rect(px, py + 1, C, C - 2, col)
        rect(px + 1, py, C - 2, C, col)
        if conn & 1:
            rect(px + h, py, h, C, col)
        if conn & 2:
            rect(px, py, h, C, col)
        if conn & 4:
            rect(px, py + h, C, h, col)
        if conn & 8:
            rect(px, py, C, h, col)
        # bisel: luz arriba-izquierda, sombra abajo-derecha
        if not conn & 8:
            rect(px + 2, py, C - 4, 1, L)
            rect(px + 1, py + 1, 3, 1, L)
        if not conn & 2:
            rect(px, py + 2, 1, C - 4, L)
        if not conn & 4:
            rect(px + 2, py + C - 1, C - 4, 1, S)
        if not conn & 1:
            rect(px + C - 1, py + 2, 1, C - 4, S)
        # dos manchas oscuras en la nuca, del lado del cuello
        if dx:
            mx_ = px + (1 if dx > 0 else C - 3)
            rect(mx_, py + h - 1, 2, 2, S)
        else:
            my_ = py + (1 if dy > 0 else C - 3)
            rect(px + h - 1, my_, 2, 2, S)
        # los ojos miran hacia donde va; muerta, son dos cruces
        if dx:
            ex = px + (6 if dx > 0 else 3)
            ojos = ((ex, py + 1), (ex, py + C - 4))
        else:
            ey = py + (6 if dy > 0 else 3)
            ojos = ((px + 1, ey), (px + C - 4, ey))
        for ox, oy in ojos:
            if g.dead:
                pyxel.line(ox, oy, ox + 2, oy + 2, SHADOW)
                pyxel.line(ox + 2, oy, ox, oy + 2, SHADOW)
                continue
            rect(ox, oy, 3, 3, WHITE)
            # la pupila, una rayita del lado hacia donde mira
            if dx:
                rect(ox + (2 if dx > 0 else 0), oy, 1, 3, SHADOW)
            else:
                rect(ox, oy + (2 if dy > 0 else 0), 3, 1, SHADOW)
        # las narices, al frente
        if dx:
            nx = px + (C - 1 if dx > 0 else 0)
            pyxel.pset(nx, py + h - 2, O)
            pyxel.pset(nx, py + h + 1, O)
        else:
            ny = py + (C - 1 if dy > 0 else 0)
            pyxel.pset(px + h - 2, ny, O)
            pyxel.pset(px + h + 1, ny, O)
        # la lengua sale cada tanto, bífida
        if not g.dead and (self.f % 70) < 8:
            if dx:
                fx_ = px + (C + 1 if dx > 0 else -2)
                pyxel.line(fx_, py + h, fx_ + 2 * dx, py + h, RED)
                pyxel.pset(fx_ + 3 * dx, py + h - 1, RED)
                pyxel.pset(fx_ + 3 * dx, py + h + 1, RED)
            else:
                fy_ = py + (C + 1 if dy > 0 else -2)
                pyxel.line(px + h, fy_, px + h, fy_ + 2 * dy, RED)
                pyxel.pset(px + h - 1, fy_ + 3 * dy, RED)
                pyxel.pset(px + h + 1, fy_ + 3 * dy, RED)

    def _hud(self):
        g = self.g
        rect = pyxel.rect
        rect(0, 0, W, HUD, PANEL)
        pyxel.dither(0.5)
        rect(0, 0, W, 8, PANEL2)
        pyxel.dither(1.0)
        rect(0, HUD - 2, W, 1, FRAME2)
        rect(0, HUD - 1, W, 1, SHADOW)
        # el puntaje, grande
        sc = "%d" % g.score
        big_text(6, 6, sc, GOLD if self.score_pop else WHITE, 3, SHADOW)
        x = 9 + big_width(sc, 3)
        m = g.mult()
        if m > 1 or g.frenesi:
            t = "x%d" % (m * (FRENESI_X if g.frenesi else 1))
            col = MAGENTA if g.frenesi else (GOLD if (self.f // 6) % 2 else AMBER)
            big_text(x, 12, t, col, 2, SHADOW)
            x += big_width(t, 2) + 4
        # la mecha de la racha, bajo el puntaje
        if g.racha:
            fx.bar(6, 25, max(24, x - 10), 2, g.racha_t / RACHA_TTL, AMBER, GRID)
        # a la derecha: el nivel y el escenario
        nv = "NV%d" % g.level()
        big_text(W - 6 - big_width(nv, 2), 12, nv, AMBER, 2, SHADOW)
        nombre = "FRENESÍ" if g.frenesi else ESCENAS[self.escena][0]
        text(W - 6 - len(nombre) * 4, 3, nombre,
             MAGENTA if g.frenesi else LABEL)
        # al medio: lo que tienes puesto
        mx = max(x + 4, 96)
        if g.ghost:
            pyxel.blt(mx, 4, _SHEET, SP["ghost"], 0, 10, 10, KEY)
            text(mx + 13, 7, "FANTASMA", GHOST1)
            fx.bar(mx, 17, 54, 3, g.ghost / FANTASMA_TTL, GHOST1, GRID)
        elif g.turbo:
            pyxel.blt(mx, 3, _SHEET, SP["aji"], 0, C, C, KEY)
            text(mx + 14, 7, "TURBO", ORANGE if (self.f // 4) % 2 else RED)
            fx.bar(mx, 17, 54, 3, g.turbo / AJI_TURBO, ORANGE, GRID)
        elif g.frenesi and (self.f // 10) % 2:
            big_text(mx, 12, "¡x2!", MAGENTA, 2, SHADOW)
        # el hambre, con su manzana: es el reloj de la partida y manda
        frac = g.hambre / HAMBRE
        urge = g.hambre < 5 * 60
        col = RED if (frac < 0.25 and (self.f // 8) % 2) else (
            AMBER if not g.frenesi else MAGENTA)
        pyxel.blt(4, 27, _SHEET, SP["apple"], 0, C, C, KEY)
        bw = W - 20 - 46
        fx.bar(19, 30, bw, 7, frac, col, GRID, RED if urge else FRAME2)
        rect(20, 31, max(0, int((bw - 2) * frac)), 1, WHITE if not urge else AMBER)
        # la reserva: cuánto aire más pueden dar las frutas (la barrita de
        # abajo). cuando se vacía arranca el frenesí
        if not g.frenesi:
            fx.bar(19, 39, bw, 2, g.extra / EXTRA_MAX, TEAL, GRID)
        segs = "%d" % ((g.hambre + 59) // 60)
        big_text(W - 14 - big_width(segs, 2), 28, segs, RED if urge else TXT, 2,
                 SHADOW)
        text(W - 10, 34, "s", LABEL)


ESCENAS_DECO_LUZ = ESCENAS[5][3][2]          # el verde de las luciérnagas


class Game:
    def __init__(self):
        Cabinet(
            game_id="culebra", title="CULEBRA",
            subtitle="come antes de que se acabe",
            howto=["desliza el dedo, flechas o wasd",
                   "el hambre baja: cada fruta te da aire",
                   "encadena comidas: la racha sube a x3",
                   "caza al ratón · esquiva las arañas",
                   "el fantasma te deja comer arañas",
                   "sin reserva: frenesí final, todo vale x2"],
            width=W, height=H, palette=PAL, scale=2,
            ui=UIColors(bg=BG, text=TXT, dim=LABEL, accent=GREEN,
                        warn=RED, shadow=SHADOW, panel=GRID),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
