"""bloques — tetris blitz: 100 segundos para hacer el mayor puntaje posible.

el tetris de siempre no se acaba nunca: si eres bueno, la partida dura lo que
aguantes. acá el reloj manda — son 100 segundos y el puntaje es todo. eso cambia
cómo se juega: ya no conviene sobrevivir, conviene arriesgar.

lo que le sumamos al tetris clásico:

- **combo**: líneas en jugadas seguidas multiplican. cortar la cadena duele.
- **hold**: guardas una pieza para después (una vez por pieza), como en los
  tetris modernos. es lo que hace que una I no se desperdicie.
- **ítems**, que se ganan cada 4 líneas y se guardan hasta 3: la **bomba**
  vuela las dos filas de abajo y el **freno** apaga la gravedad 4 segundos.
  son la salida cuando la pila te ganó.
- **tres próximas a la vista**, no una: se puede planear la I.
- **tetris seguidos** (back-to-back) pagan una vez y media, y un **tablero
  limpio** después de una línea — el perfect clear — paga un bono grande.
- **la pieza dorada**: una de cada diez viene de oro. la línea que se lleve un
  bloque dorado paga doble y regala un ítem. es una carnada: conviene
  enterrarla donde se pueda limpiar rápido.
- **la fiebre**: los últimos 20 segundos todo paga doble. el final del blitz
  tiene que ser lo más emocionante, no un trámite.
- **lock delay**: la pieza que toca el piso espera medio segundo antes de
  quedar fija, y moverla o girarla le da otro respiro (con techo). sin esto,
  en nivel alto la pieza se clavaba apenas tocaba y en el celular, con el dedo,
  era imposible acomodarla.

en el celular se juega sobre la pantalla misma: **arrastrar** mueve la pieza
columna por columna, **tocar** la gira, **deslizar rápido hacia abajo** la deja
caer y **hacia arriba** la guarda. los cuadros de GUARDAR e ÍTEM del panel
también se tocan. la cruceta y los botones siguen valiendo.

la lógica (piezas, rotación, colisión, líneas, reloj) vive en la clase Tetris,
sin pyxel: `frame()` avanza un frame y devuelve qué pasó.
"""
import math
import random

import pyxel

from pixelkit import fx, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import ctext, text

COLS, ROWS = 10, 20
CELL = 10
BX, BY = 8, 10
W, H = 220, 220

TIME = 100 * 60                  # el blitz entero: nada lo estira
ITEM_CADA = 4                    # líneas por ítem
ITEMS_MAX = 3
FRENO_TTL = 4 * 60
COMBO_TTL = 3 * 60               # lo que tienes para encadenar la próxima línea
COMBO_MAX = 8                    # techo del multiplicador por cadena
BASURA_GAP = 13 * 60             # cada cuánto sube una fila desde abajo
BASURA_MIN = 6 * 60              # y lo más seguido que puede llegar a subir
NIVEL_MAX = 15
COLA = 3                         # cuántas próximas se ven
B2B_FACTOR = 1.5                 # tetris atrás de tetris
PERFECTO_VALE = 1000             # el tablero vacío tras una línea, por nivel
# los dos techos existen por lo mismo: sin ellos el puntaje es exponencial.
# un bot que encadenaba líneas sin parar llegó a 14 millones — con la cadena
# multiplicando sin límite, el récord deja de medir habilidad y mide suerte.

FIEBRE = 20 * 60                 # los últimos 20 s pagan doble
FIEBRE_X = 2
ORO_CADA = 10                    # una de cada tantas piezas viene dorada
ORO_X = 2                        # la línea con oro paga doble (una vez por jugada)
LOCK_DELAY = 30                  # frames que espera una pieza apoyada
LOCK_SOFT = 8                    # y si la estás bajando a mano, menos
LOCK_RESETS = 14                 # cuántas veces se puede estirar moviéndola

BOMBA, FRENO = range(2)
ITEM_NOMBRE = {BOMBA: "¡BOMBA!", FRENO: "¡FRENO!"}

(BG, EMPTY, FRAME, TXT, DIM, ACCENT, C_I, C_O, C_T, C_S, C_Z, C_J, C_L,
 BEVEL, SHADOW, GHOST,
 GOLD, MAGENTA, FLASHC, BOMBC, FREEZEC, HOLDC, WHITE, HOT,
 GARBAGE, GARBAGE2,
 ORO, ORO2, ORO3, LABEL, ROJO_OSC, PANEL) = range(32)
PAL = [
    0x0C0E14, 0x161C2A, 0x2A3350, 0xE8ECF5, 0x5A6480, 0x8AC52F, 0x3AC6D8,
    0xE7C13B, 0xA85FD0, 0x5FB84A, 0xD8483A, 0x4A78D8, 0xE0842E, 0xD8E0EE,
    0x070810, 0x39435E,
    0xFFD24A, 0xD84AB8, 0xFFF3B0, 0xFF8A3A, 0x7ADCFF, 0x9BB0D8, 0xF2F5FB,
    0xFF5A3A, 0x6E7898, 0x39435E,
    0xFFC21A, 0xFFF4B8, 0xA8720A, 0xB4BED8, 0x4A1620, 0x131828,
]

# un tablero distinto por nivel: (cuadro claro, cuadro oscuro, marco). el
# cambio de colores es lo que hace que subir de nivel se sienta como llegar a
# otro lugar y no sólo como que el número cambió.
TEMAS_RGB = [
    (0x0C0E14, 0x161C2A, 0x3A4670),     # noche
    (0x110B1C, 0x1D1430, 0x5A3A8E),     # violeta
    (0x071313, 0x0E2326, 0x23727A),     # laguna
    (0x150A0E, 0x27121A, 0x8A2E42),     # carmín
    (0x09130B, 0x112417, 0x357A3C),     # bosque
    (0x15100A, 0x281D10, 0x8A6A26),     # bronce
]
TEMAS = []
for _a, _b, _m in TEMAS_RGB:
    i = len(PAL)
    PAL += [_a, _b, _m]
    TEMAS.append((i, i + 1, i + 2))
FIEBRE_A, FIEBRE_B = len(PAL), len(PAL) + 1
PAL += [0x1C0906, 0x2E1208]
PAL += [0] * (256 - len(PAL))

SHAPES = {
    "I": ["....", "XXXX", "....", "...."],
    "O": ["XX", "XX"],
    "T": [".X.", "XXX", "..."],
    "S": [".XX", "XX.", "..."],
    "Z": ["XX.", ".XX", "..."],
    "J": ["X..", "XXX", "..."],
    "L": ["..X", "XXX", "..."],
}
COLOR = {"I": C_I, "O": C_O, "T": C_T, "S": C_S, "Z": C_Z, "J": C_J, "L": C_L}
SCORE_LINES = (0, 100, 300, 500, 800)


def rotate_cw(shape):
    n = len(shape)
    return ["".join(shape[n - 1 - x][y] for x in range(n)) for y in range(n)]


class Tetris:
    """estado y reglas del tetris blitz. sin pyxel: testeable de a de veras."""

    def __init__(self, cols=COLS, rows=ROWS, rng=None):
        self.cols, self.rows = cols, rows
        self.rng = rng or random
        self.reset()

    def reset(self):
        self.board = [[0] * self.cols for _ in range(self.rows)]
        self.score = self.lines = 0
        self.level = 1
        self.over = False
        self.time = TIME
        self.bag = []
        self.combo = 0
        self.combo_t = 0
        self.items = []
        self.item_deuda = 0          # líneas hechas desde el último ítem
        self.freno = 0
        self.fall = 0
        self.lock_t = 0              # frames que lleva apoyada la pieza
        self.lock_resets = 0
        self.basura_t = BASURA_GAP
        self.basuras = 0
        self.hold = None
        self.hold_oro = False
        self.hold_usado = False
        self.b2b = False             # ¿la última línea fue un tetris?
        self.perfectos = 0
        self.sacadas = 0             # piezas sacadas de la bolsa (para el oro)
        self.oro = False             # ¿la pieza en juego es dorada?
        self.oros = 0                # líneas con oro limpiadas
        self.cola = []
        self.cola_oro = []
        for _ in range(COLA):
            self._encolar()
        self._spawn()

    @property
    def nxt(self):
        """la próxima de la cola, para el panel y el que la mira de a una."""
        return self.cola[0]

    def fiebre(self):
        """¿estamos en los últimos segundos, donde todo paga doble?"""
        return 0 < self.time <= FIEBRE

    # --- piezas ----------------------------------------------------------
    def _from_bag(self):
        if not self.bag:
            self.bag = list(SHAPES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def _encolar(self):
        self.sacadas += 1
        self.cola.append(self._from_bag())
        self.cola_oro.append(self.sacadas % ORO_CADA == 0)

    def _spawn(self, pieza=None, oro=False):
        if pieza is None:
            self.pk = self.cola.pop(0)
            self.oro = self.cola_oro.pop(0)
            self._encolar()
        else:
            self.pk = pieza
            self.oro = oro
        self.shape = SHAPES[self.pk]
        self.px = (self.cols - len(self.shape)) // 2
        self.py = 0
        self.hold_usado = False
        self.lock_t = 0
        self.lock_resets = 0
        self.fall = 0
        if self._collide(self.shape, self.px, self.py):
            self.over = True

    def guardar(self):
        """el hold: cambia la pieza actual por la guardada. una vez por pieza."""
        if self.over or self.hold_usado:
            return False
        actual, actual_oro = self.pk, self.oro
        if self.hold is None:
            self.hold, self.hold_oro = actual, actual_oro
            self._spawn()
        else:
            guardada, g_oro = self.hold, self.hold_oro
            self.hold, self.hold_oro = actual, actual_oro
            self._spawn(guardada, g_oro)
        self.hold_usado = True       # después de _spawn, que lo pone en False
        return True

    def _cells(self, shape, px, py):
        return [(px + x, py + y)
                for y, row in enumerate(shape)
                for x, ch in enumerate(row) if ch == "X"]

    def _collide(self, shape, px, py):
        for x, y in self._cells(shape, px, py):
            if x < 0 or x >= self.cols or y >= self.rows:
                return True
            if y >= 0 and self.board[y][x]:
                return True
        return False

    def apoyada(self):
        return self._collide(self.shape, self.px, self.py + 1)

    def _respiro(self):
        """moverla apoyada le da otro rato antes de fijarse, con techo: si no,
        se podría girar una pieza en el piso para siempre (y el reloj igual
        corre, pero la pila no)."""
        if self.lock_t and self.lock_resets < LOCK_RESETS:
            self.lock_t = 0
            self.lock_resets += 1

    def move(self, dx):
        if not self.over and not self._collide(self.shape, self.px + dx, self.py):
            self.px += dx
            self._respiro()
            return True
        return False

    def rotate(self):
        if self.over:
            return False
        r = rotate_cw(self.shape)
        for kick in (0, -1, 1, -2, 2):
            if not self._collide(r, self.px + kick, self.py):
                self.shape, self.px = r, self.px + kick
                self._respiro()
                return True
        return False

    def bajar(self):
        """una fila hacia abajo a mano (arrastrar el dedo). paga un punto."""
        if self.over or self.apoyada():
            return False
        self.py += 1
        self.score += 1
        self.fall = 0
        return True

    def ghost_y(self):
        y = self.py
        while not self._collide(self.shape, self.px, y + 1):
            y += 1
        return y

    # --- ítems -----------------------------------------------------------
    def _regalar_item(self, ev, tipo=None):
        if len(self.items) < ITEMS_MAX:
            self.items.append(self.rng.randrange(2) if tipo is None else tipo)
            ev.append(("item_gana", self.items[-1]))

    def _dar_item(self, ev):
        while self.item_deuda >= ITEM_CADA:
            self.item_deuda -= ITEM_CADA
            self._regalar_item(ev)

    def usar_item(self, ev=None):
        """gasta el primer ítem de la fila. devuelve cuál usó, o None."""
        ev = ev if ev is not None else []
        if self.over or not self.items:
            return None
        tipo = self.items.pop(0)
        if tipo == BOMBA:
            volados = 0
            for _ in range(2):
                if any(self.board[self.rows - 1]):
                    del self.board[self.rows - 1]
                    self.board.insert(0, [0] * self.cols)
                    volados += 1
            ev.append(("bomba", volados))
        else:
            self.freno = FRENO_TTL
            ev.append(("freno", 0))
        return tipo

    # --- caída y líneas ---------------------------------------------------
    def tick(self):
        """baja una fila. devuelve True si la pieza se apoyó."""
        if self.over:
            return False
        if self._collide(self.shape, self.px, self.py + 1):
            return True
        self.py += 1
        return False

    def hard_drop(self, ev=None):
        ev = ev if ev is not None else []
        if self.over:
            return ev
        caida = self.ghost_y() - self.py
        celdas = self._cells(self.shape, self.px, self.ghost_y())
        self.py = self.ghost_y()
        self.score += caida * 2                  # premia decidirse rápido
        ev.append(("drop", caida, celdas, COLOR[self.pk] if not self.oro else ORO))
        self._lock(ev)
        return ev

    def _lock(self, ev):
        col = ORO if self.oro else COLOR[self.pk]
        for x, y in self._cells(self.shape, self.px, self.py):
            if 0 <= y < self.rows and 0 <= x < self.cols:
                self.board[y][x] = col
        n, filas, con_oro = self._clear_lines()
        if n:
            self.combo += 1
            self.combo_t = COMBO_TTL
            ganado = SCORE_LINES[n] * self.level * min(COMBO_MAX, self.combo)
            if n == 4 and self.b2b:                  # tetris atrás de tetris
                ganado = int(ganado * B2B_FACTOR)
                ev.append(("b2b", ganado))
            self.b2b = n == 4
            if con_oro:
                ganado *= ORO_X
                self.oros += con_oro
                ev.append(("oro", con_oro))
                self._regalar_item(ev)
            if self.fiebre():
                ganado *= FIEBRE_X
            self.score += ganado
            self.item_deuda += n
            ev.append(("lineas", n, filas, ganado, self.combo))
            if not any(any(fila) for fila in self.board):
                bono = PERFECTO_VALE * self.level
                if self.fiebre():
                    bono *= FIEBRE_X
                self.score += bono
                self.perfectos += 1
                ev.append(("perfecto", bono))
            self._dar_item(ev)
        elif self.combo:
            ev.append(("combo_roto", self.combo))
            self.combo = 0
        self._spawn()
        if self.over:
            ev.append(("tope",))
        elif self.oro:
            ev.append(("dorada",))

    def _clear_lines(self):
        full = [y for y in range(self.rows) if all(self.board[y])]
        con_oro = sum(1 for y in full if ORO in self.board[y])
        for y in full:
            del self.board[y]
            self.board.insert(0, [0] * self.cols)
        if full:
            self.lines += len(full)
            self.level = min(NIVEL_MAX, 1 + self.lines // 10)
        return len(full), full, con_oro

    def basura_gap(self):
        """el intervalo se acorta con el nivel: la presión sube sola."""
        return max(BASURA_MIN, BASURA_GAP - (self.level - 1) * 45)

    def subir_basura(self, ev):
        """sube una fila desde abajo, con un hueco. la pieza en juego sube con
        ella para que no quede enterrada.

        es lo que cambia el blitz de "acomoda tranquilo" a "sácate esto de
        encima": la pila crece aunque juegues perfecto, así que hay que hacer
        líneas para bajarla, no sólo para puntuar.
        """
        if self.over:
            return
        hueco = self.rng.randrange(self.cols)
        fila = [GARBAGE] * self.cols
        fila[hueco] = 0
        if any(self.board[0]):                   # ya no entra: se acabó
            self.over = True
            ev.append(("tope",))
            return
        del self.board[0]
        self.board.append(fila)
        self.basuras += 1
        self.py = max(0, self.py - 1)            # la pieza sube con el tablero
        ev.append(("basura", hueco))
        if self._collide(self.shape, self.px, self.py):
            self.over = True
            ev.append(("tope",))

    def fall_frames(self):
        return max(3, 46 - (self.level - 1) * 4)

    def frame(self, soft=False):
        """un frame de reloj: baja el tiempo, hace caer la pieza, devuelve todo."""
        ev = []
        if self.over:
            return ev
        if self.combo_t:
            self.combo_t -= 1
            if not self.combo_t and self.combo:
                ev.append(("combo_roto", self.combo))
                self.combo = 0
        if self.freno:
            self.freno -= 1
        elif self.apoyada():
            # apoyada: espera el lock delay antes de fijarse
            self.fall = 0
            self.lock_t += 1
            if self.lock_t >= (LOCK_SOFT if soft else LOCK_DELAY):
                self._lock(ev)
        else:
            self.lock_t = 0
            self.fall += 1
            if self.fall >= (3 if soft else self.fall_frames()):
                self.fall = 0
                self.py += 1
        self.basura_t -= 1
        if self.basura_t <= 0:
            self.basura_t = self.basura_gap()
            self.subir_basura(ev)
        antes = self.time
        self.time -= 1
        if antes > FIEBRE >= self.time:
            ev.append(("fiebre",))
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("tiempo",))
        return ev


# --- texto grande ------------------------------------------------------------
# la fuente de pyxel tiene 4x6 px: a 1.2x en el teléfono, un "¡TETRIS!" de ese
# tamaño pasa desapercibido. lo dibujamos en una imagen aparte (con tildes,
# igual que pxtext) y la estampamos escalada con blt. sirve para los carteles
# que tienen que pegar: combos, niveles, la fiebre, la cuenta final.
_ACUTE = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
          "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}
_IMG = None


def _img():
    global _IMG
    if _IMG is None:
        _IMG = pyxel.Image(256, 10)
    return _IMG


def big(cx, cy, s, col, scale=2, sombra=SHADOW):
    """texto centrado en (cx, cy), agrandado `scale` veces, con sombra."""
    img = _img()
    base = "".join(" " if ch == "¡" else _ACUTE.get(ch, ch) for ch in s)
    w = len(s) * 4
    for c, off in ((sombra, max(1, int(scale))), (col, 0)):
        if c is None:
            continue
        img.rect(0, 0, 256, 10, 0)
        img.text(0, 3, base, c)
        for i, ch in enumerate(s):
            if ch in _ACUTE:
                img.pset(i * 4 + 2, 0, c)
                img.pset(i * 4 + 1, 1, c)
            elif ch == "¡":                    # la fuente no la trae: a mano
                img.pset(i * 4 + 1, 3, c)
                img.rect(i * 4 + 1, 5, 1, 3, c)
        # blt escala alrededor del centro del rectángulo de destino
        pyxel.blt(int(cx - w / 2) + off, int(cy - 5) + off, img, 0, 0, w, 10,
                  0, None, scale)


def dentro(mx, my, caja):
    x, y, w, h = caja
    return x <= mx < x + w and y <= my < y + h


# zonas del panel que se tocan con el dedo
PX0 = BX + COLS * CELL + 8                     # 116: donde empieza el panel
HOLD_BOX = (PX0, 112, 46, 34)
ITEM_BOX = (PX0 + 50, 112, 48, 34)
# los gestos sobre la pantalla, en píxeles de juego. a ~1.8x en el teléfono, 8
# px de juego son ~14 px de pantalla: una columna por cada medio dedo.
PASO_X = 8
PASO_Y = 9
FLICK = 16                       # px en 4 frames = deslizar rápido (~400 px/s)
TAP_PX = 4
TAP_FRAMES = 16


class World:
    """el tetris jugándose: input, dibujo y chispas. el Cabinet lo envuelve."""

    def __init__(self):
        self.t = Tetris()
        self.fx = fx.Fx(gravity=0.18)
        self.lvl = 1
        self.fx.destello(WHITE)
        self.barridos = []           # [fila, frames, ancho] líneas que estallan
        self.banner = None           # [texto, col, sub, subcol, frames, frames0]
        self.golpe = 0               # el tablero salta cuando sube la basura
        self.score_pop = 0
        self.score_vis = 0           # el puntaje del hud corre hacia el real
        self.gesto = None
        self.tocado = []             # [caja, frames]: el cuadro del panel que tocaste
        self.cuenta = -1
        self.touch = web.is_touch()
        self.f = 0                   # reloj propio de la piel (titileos, brillos)

    @property
    def over(self):
        return self.t.over

    @property
    def score(self):
        return self.t.score

    # --- input -----------------------------------------------------------
    def update(self):
        t = self.t
        self.f += 1
        ev = []
        if pyxel.btnp(pyxel.KEY_LEFT, 12, 2) or pyxel.btnp(pyxel.KEY_A, 12, 2):
            t.move(-1)
        if pyxel.btnp(pyxel.KEY_RIGHT, 12, 2) or pyxel.btnp(pyxel.KEY_D, 12, 2):
            t.move(1)
        if pyxel.btnp(pyxel.KEY_UP, 14, 6) or pyxel.btnp(pyxel.KEY_X) \
                or pyxel.btnp(pyxel.KEY_W):
            t.rotate()
        if pyxel.btnp(pyxel.KEY_C) or pyxel.btnp(pyxel.KEY_LSHIFT):
            self._guardar()
        if pyxel.btnp(pyxel.KEY_Z):
            t.usar_item(ev)
        soltada = self._tactil(ev)
        if pyxel.btnp(pyxel.KEY_SPACE) or soltada:
            t.hard_drop(ev)
            ev += t.frame(soft=False)
        else:
            soft = pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S)
            ev += t.frame(soft=soft)
        for e in ev:
            self._efecto(e)
        if t.level != self.lvl:
            self.lvl = t.level
            self._cartel("NIVEL %d" % t.level, TXT, "¡MÁS RÁPIDO!", ACCENT, 70)
            for k in range(14):
                self.fx.burst(BX + k * 7 + 4, BY + ROWS * CELL, (WHITE, ACCENT, C_S),
                              n=2, speed=2.2, life=26, angle=-math.pi / 2,
                              spread=0.7)
        # la fiebre: brasas que suben desde el fondo del tablero
        if t.fiebre() and self.f % 3 == 0:
            x = BX + 4 + (self.f * 37) % (COLS * CELL - 8)
            self.fx.burst(x, BY + ROWS * CELL - 2, (FLASHC, HOT, BOMBC, C_Z), n=1,
                          speed=0.9, life=46, angle=-math.pi / 2, spread=0.5,
                          gravity=-0.01)
        s = (t.time + 59) // 60
        if s != self.cuenta:
            self.cuenta = s
            if 0 < s <= 5 and not t.over:
                self.fx.shake(1)
        self.barridos = [[f, n - 1] for f, n in self.barridos if n > 1]
        self.tocado = [[c, n - 1] for c, n in self.tocado if n > 1]
        if self.banner:
            self.banner[4] -= 1
            if self.banner[4] <= 0:
                self.banner = None
        self.golpe = max(0, self.golpe - 1)
        self.score_pop = max(0, self.score_pop - 1)
        if self.score_vis < t.score:            # el contador corre, no salta
            self.score_vis += max(1, (t.score - self.score_vis) // 6)
        self.fx.update()

    def _guardar(self):
        t = self.t
        if t.guardar():
            self.tocado.append([HOLD_BOX, 8])
            x, y, w, h = HOLD_BOX
            self.fx.burst(x + w / 2, y + h / 2, (WHITE, HOLDC, FRAME), n=8,
                          speed=1.2, life=14, gravity=0)

    def _tactil(self, ev):
        """los gestos sobre la pantalla. devuelve True si pidió caer de golpe.

        el dedo no aprieta teclas acá: el juego lee el mouse de pyxel (que en el
        celular es el dedo sobre la pantalla) y arma los gestos él mismo. así un
        arrastre mueve exactamente una columna por cada PASO_X, que es lo que
        hace que se pueda apuntar, y el toque corto se distingue del arrastre.
        """
        t = self.t
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.gesto = None
            if dentro(mx, my, HOLD_BOX):
                self._guardar()
                return False
            if dentro(mx, my, ITEM_BOX):
                if t.usar_item(ev) is not None:
                    self.tocado.append([ITEM_BOX, 8])
                return False
            self.gesto = {"x0": mx, "y0": my, "ax": mx, "ay": my, "f": 0,
                          "movio": False, "listo": False, "hist": [(mx, my)],
                          "eje": None}
            return False
        g = self.gesto
        if g is None:
            return False
        if not pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            # se levantó el dedo: si casi no se movió y fue corto, es un toque
            if not g["movio"] and not g["listo"] and g["f"] <= TAP_FRAMES \
                    and abs(mx - g["x0"]) + abs(my - g["y0"]) <= TAP_PX:
                t.rotate()
            self.gesto = None
            return False
        g["f"] += 1
        if g["listo"]:
            return False                       # ya cayó: el resto no cuenta
        hist = g["hist"]
        hist.append((mx, my))
        if len(hist) > 5:
            hist.pop(0)
        vy = my - hist[0][1]
        if vy >= FLICK and my - g["y0"] >= FLICK:
            g["listo"] = True
            return True
        if vy <= -FLICK and g["y0"] - my >= FLICK:
            g["listo"] = True
            self._guardar()
            return False
        dx, dy = mx - g["ax"], my - g["ay"]
        if g["eje"] is None and max(abs(dx), abs(dy)) >= 5:
            g["eje"] = "x" if abs(dx) >= abs(dy) else "y"
        # en el eje vertical se baja de a fila; lo horizontal pide el doble de
        # recorrido para no mover la pieza sin querer mientras la bajas
        paso_x = PASO_X if g["eje"] != "y" else PASO_X * 2
        while dx >= paso_x:
            t.move(1)
            g["ax"] += paso_x
            dx -= paso_x
            g["movio"] = True
        while dx <= -paso_x:
            t.move(-1)
            g["ax"] -= paso_x
            dx += paso_x
            g["movio"] = True
        if g["eje"] == "y":
            while dy >= PASO_Y:
                t.bajar()
                g["ay"] += PASO_Y
                dy -= PASO_Y
                g["movio"] = True
        elif g["eje"] == "x":
            g["ay"] = my                       # moviendo de lado no se baja
        if abs(mx - g["x0"]) + abs(my - g["y0"]) > 2 * TAP_PX:
            g["movio"] = True                  # ya no cuenta como toque
        return False

    # --- efectos ---------------------------------------------------------
    def _px(self, cx, cy):
        return BX + cx * CELL + CELL / 2, BY + cy * CELL + CELL / 2

    def _cartel(self, s, col, sub=None, subcol=WHITE, frames=55):
        self.banner = [s, col, sub, subcol, frames, frames]

    def _efecto(self, e):
        kind = e[0]
        cx = BX + COLS * CELL / 2
        if kind == "lineas":
            _, n, filas, ganado, combo = e
            for f in filas:
                self.barridos.append([f, 14])
                for c in range(COLS):
                    x, y = self._px(c, f)
                    self.fx.burst(x, y, (WHITE, FLASHC, GOLD, HOT), n=3 + n // 2,
                                  speed=1.5 + 0.4 * n, life=22)
            nombre = ("", "", "DOBLE", "TRIPLE", "¡TETRIS!")[n]
            sub = "COMBO x%d" % combo if combo > 1 else None
            if n == 4:
                self._cartel(nombre, GOLD, sub, HOT, 70)
            elif nombre or sub:
                self._cartel(nombre or sub, WHITE if nombre else HOT,
                             sub if nombre else None, HOT)
            self.fx.popup(cx, BY + filas[0] * CELL + 2, "+%d" % ganado,
                          GOLD if self.t.fiebre() else WHITE, life=44)
            self.fx.shake(2 + n)
            self.fx.destello(FLASHC if n < 4 else GOLD)
            self.score_pop = 12
        elif kind == "b2b":
            self.fx.popup(cx, BY + 52, "SEGUIDO x1.5", HOT, life=60)
        elif kind == "oro":
            self.fx.popup(cx, BY + 64, "ORO x2 +ÍTEM", ORO, life=60)
            for _ in range(2):
                self.fx.burst(cx, BY + 100, (WHITE, ORO2, ORO, ORO3), n=16,
                              speed=2.6, life=32)
        elif kind == "dorada":
            self.fx.popup(cx, BY + 26, "PIEZA DORADA", ORO, life=50)
        elif kind == "perfecto":
            for cy in range(0, ROWS, 2):
                for c in range(0, COLS, 3):
                    x, y = self._px(c, cy)
                    self.fx.burst(x, y, (WHITE, GOLD, FLASHC, C_I), n=2,
                                  speed=1.4, life=30)
            self._cartel("¡PERFECTO!", GOLD, "+%d" % e[1], WHITE, 90)
            self.fx.shake(6)
            self.fx.destello(GOLD)
        elif kind == "drop":
            caida, celdas, col = e[1], e[2], e[3]
            if caida > 0:
                # una estela que baja con la pieza y un polvo donde aterriza
                for x, y in celdas[-2:]:
                    px, py = self._px(x, y)
                    self.fx.burst(px, py + CELL / 2, (WHITE, col, FRAME), n=5,
                                  speed=1.3, life=12, angle=-math.pi / 2,
                                  spread=2.6, gravity=0.05)
            if caida > 2:
                self.fx.shake(2)
        elif kind == "bomba":
            for f in range(ROWS - max(1, e[1]), ROWS):
                self.barridos.append([f, 14])
                for c in range(COLS):
                    x, y = self._px(c, f)
                    self.fx.burst(x, y, (WHITE, BOMBC, HOT, C_Z), n=4, speed=2.4,
                                  life=26)
            self._cartel(ITEM_NOMBRE[BOMBA], BOMBC, None, WHITE, 45)
            self.fx.shake(7)
            self.fx.destello(BOMBC)
        elif kind == "freno":
            self._cartel(ITEM_NOMBRE[FRENO], FREEZEC, "4 SEGUNDOS", WHITE, 45)
            self.fx.destello(FREEZEC)
        elif kind == "item_gana":
            x, y, w, h = ITEM_BOX
            self.fx.popup(x + w / 2, y - 2, "+ÍTEM", ACCENT, life=40)
            self.fx.burst(x + w / 2, y + h / 2, (WHITE, ACCENT, C_S), n=10,
                          speed=1.4, life=18, gravity=0)
        elif kind == "basura":
            self.golpe = 8
            for c in range(COLS):
                x, y = self._px(c, ROWS - 1)
                self.fx.burst(x, y + 4, (WHITE, GARBAGE, FRAME), n=2, speed=1.8,
                              life=16, angle=-math.pi / 2, spread=1.2)
            self.fx.popup(cx, BY + (ROWS - 3) * CELL, "SUBE LA BASURA", HOT,
                          life=40)
            self.fx.shake(4)
            self.fx.destello(GARBAGE)
        elif kind == "fiebre":
            self._cartel("¡FIEBRE!", HOT, "TODO PAGA x2", GOLD, 100)
            self.fx.shake(5)
            self.fx.destello(HOT, 8)
        elif kind == "tope":
            self.fx.shake(8)
            self.fx.destello(C_Z)
        elif kind == "tiempo":
            self.fx.destello(WHITE, 8)

    # --- dibujo ----------------------------------------------------------
    def _block(self, px, py, col, size=CELL):
        if col == ORO:
            # el oro no lleva el bisel de las demás: marco oscuro y una gema
            # clara al centro, para que no se confunda con la O amarilla
            pyxel.rect(px, py, size, size, ORO3)
            pyxel.rect(px + 1, py + 1, size - 2, size - 2, ORO)
            m = size // 2
            pyxel.rect(px + m - 2, py + m - 1, 4, 2, ORO2)
            pyxel.rect(px + m - 1, py + m - 2, 2, 4, ORO2)
            # un brillo que recorre el oro, para que se lea aunque esté quieto
            k = (self.f // 3 + px // 2 + py // 3) % 24
            if k < size - 2:
                pyxel.pset(px + 1 + k, py + 1, WHITE)
                pyxel.pset(px + 1, py + 1 + k, WHITE)
            return
        pyxel.rect(px, py, size, size, col)
        pyxel.rect(px, py, size, 1, BEVEL)
        pyxel.rect(px, py, 1, size, BEVEL)
        pyxel.rect(px, py + size - 1, size, 1, SHADOW)
        pyxel.rect(px + size - 1, py, 1, size, SHADOW)

    def _tema(self):
        t = self.t
        if t.fiebre():
            m = HOT if (self.f // 6) % 2 else BOMBC
            return FIEBRE_A, FIEBRE_B, m
        return TEMAS[(t.level - 1) % len(TEMAS)]

    def draw(self):
        t = self.t
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        a, b, marco = self._tema()
        if t.freno:
            marco = FREEZEC
        pyxel.camera(-sx, -sy + (self.golpe // 2))
        pyxel.rect(BX - 2, BY - 2, COLS * CELL + 4, ROWS * CELL + 4, marco)
        pyxel.rect(BX, BY, COLS * CELL, ROWS * CELL, a)
        for y in range(ROWS):                   # el damero, una fila de cada dos
            for x in range((y & 1) ^ 1, COLS, 2):
                pyxel.rect(BX + x * CELL, BY + y * CELL, CELL, CELL, b)
        # los últimos 10 segundos, enormes detrás de las piezas
        s = (t.time + 59) // 60
        if 0 < s <= 10 and not t.over:
            big(BX + COLS * CELL / 2 + 1, BY + ROWS * CELL / 2, "%d" % s,
                ROJO_OSC, 9, None)
        for y in range(ROWS):
            row = t.board[y]
            for x in range(COLS):
                v = row[x]
                if v:
                    self._block(BX + x * CELL, BY + y * CELL, v)
        if not t.over:
            col = ORO if t.oro else COLOR[t.pk]
            gy = t.ghost_y()
            if gy != t.py:
                cel = t._cells(t.shape, t.px, gy)
                pyxel.dither(0.3)
                for x, y in cel:
                    pyxel.rect(BX + x * CELL, BY + y * CELL, CELL, CELL, col)
                pyxel.dither(1.0)
                for x, y in cel:
                    pyxel.rectb(BX + x * CELL, BY + y * CELL, CELL, CELL, col)
            for x, y in t._cells(t.shape, t.px, t.py):
                if y >= 0:
                    self._block(BX + x * CELL, BY + y * CELL, col)
            # apoyada: un borde blanco que avisa que está por fijarse
            if t.lock_t and (self.f // 3) % 2:
                for x, y in t._cells(t.shape, t.px, t.py):
                    if y >= 0:
                        pyxel.rectb(BX + x * CELL, BY + y * CELL, CELL, CELL, WHITE)
        for f, n in self.barridos:              # la línea que estalla: un fogonazo
            w = int(COLS * CELL * min(1.0, n / 8))
            pyxel.rect(BX + (COLS * CELL - w) // 2, BY + f * CELL + 1, w, CELL - 2,
                       WHITE if n > 9 else FLASHC)
        # la basura que viene: una franja roja que titila bajo el tablero
        if not t.over and t.basura_t <= 120 and (self.f // 5) % 2:
            for k in range(0, COLS * CELL, 10):
                xx = BX + k + 5
                yy = BY + ROWS * CELL + 4
                pyxel.tri(xx - 3, yy + 3, xx + 3, yy + 3, xx, yy, HOT)
        self.fx.draw(0, 0)
        if self.banner:
            self._draw_banner()
        if t.over:
            if t.time == 0:
                big(BX + COLS * CELL / 2, BY + 30, "¡TIEMPO!", GOLD, 2)
            else:
                big(BX + COLS * CELL / 2, BY + 30, "¡LLENO!", C_Z, 2)
        pyxel.camera()
        self.fx.draw_flash(BX - 1, BY - 1, COLS * CELL + 2, ROWS * CELL + 2)
        self._panel()

    def _draw_banner(self):
        s, col, sub, subcol, n, n0 = self.banner
        edad = n0 - n
        # entra grande y se asienta: el "golpe" del cartel
        esc = 2 + max(0.0, 1.5 - edad * 0.25)
        if n < 12 and (n // 2) % 2:
            return                               # titila al irse
        cx = BX + COLS * CELL / 2
        cy = BY + 78
        big(cx, cy, s, col, esc)
        if sub:
            big(cx, cy + 22, sub, subcol, 2 if len(sub) <= 12 else 1)

    def _mini(self, pieza, ox, oy, col, s=7):
        for cy, row in enumerate(SHAPES[pieza]):
            for cx, ch in enumerate(row):
                if ch == "X":
                    self._block(ox + cx * s, oy + cy * s, col, s)

    def _mini_centrada(self, pieza, cx, cy, col, s):
        sh = SHAPES[pieza]
        xs = [x for row in sh for x, ch in enumerate(row) if ch == "X"]
        ys = [y for y, row in enumerate(sh) if "X" in row]
        w = (max(xs) - min(xs) + 1) * s
        h = (max(ys) - min(ys) + 1) * s
        self._mini(pieza, int(cx - w / 2 - min(xs) * s),
                   int(cy - h / 2 - min(ys) * s), col, s)

    def _caja(self, caja, titulo, activo=True):
        x, y, w, h = caja
        tocado = any(c == caja for c, _ in self.tocado)
        pyxel.rect(x, y, w, h, WHITE if tocado else PANEL)
        pyxel.rectb(x, y, w, h, ACCENT if activo else FRAME)
        pyxel.rect(x, y, w, 8, ACCENT if activo else FRAME)
        text(x + 2, y + 2, titulo, BG)

    def _panel(self):
        t = self.t
        px = PX0
        pw = W - px - 4
        fiebre = t.fiebre()
        s = (t.time + 59) // 60
        # el reloj manda: grande arriba de todo, y rojo al final
        urge = s <= 10 and self.f % 30 < 15
        col = C_Z if urge else (HOT if fiebre else WHITE)
        ss = "%d" % s
        big(px + len(ss) * 4, 9, ss, col, 2, SHADOW)
        text(px + len(ss) * 8 + 3, 9, "seg", LABEL)
        if fiebre:
            fcol = GOLD if (self.f // 8) % 2 else HOT
            text(px + 48, 3, "FIEBRE", fcol)
            text(px + 56, 11, "x2", fcol)
        fx.bar(px, 18, pw, 4, t.time / TIME,
               C_Z if s <= 10 else (HOT if fiebre else ACCENT), EMPTY, None)
        # la fiebre se ve venir: una marca en la barra
        mx = px + int(pw * FIEBRE / TIME)
        pyxel.rect(mx, 17, 1, 6, GOLD)

        text(px, 27, "PUNTOS", LABEL)
        esc = 2 + (0.4 if self.score_pop > 6 else 0)
        sc = "%d" % self.score_vis
        big(px + len(sc) * 4, 40, sc, GOLD if self.score_pop else WHITE, esc)
        text(px, 51, "NIVEL %d" % t.level, TXT)
        text(px + 44, 51, "%d LÍN" % t.lines, LABEL)

        # el combo, con su mecha: cuánto falta para que se enfríe
        if t.combo > 1 or (t.combo and t.combo_t):
            ccol = HOT if t.combo > 1 else LABEL
            text(px, 60, "COMBO x%d" % t.combo, ccol)
            fx.bar(px + 50, 61, pw - 50, 3, t.combo_t / COMBO_TTL, ccol, EMPTY)
        elif t.b2b:
            text(px, 60, "TETRIS: SIGUE x1.5",
                 HOT if (self.f // 8) % 2 else GOLD)

        text(px, 70, "PRÓXIMAS", LABEL)
        pyxel.rect(px, 78, 34, 28, PANEL)
        pyxel.rectb(px, 78, 34, 28, FRAME)
        c0 = ORO if t.cola_oro[0] else COLOR[t.cola[0]]
        self._mini_centrada(t.cola[0], px + 17, 92, c0, 7)
        for k, pk in enumerate(t.cola[1:]):          # las que siguen, más chicas
            ck = ORO if t.cola_oro[k + 1] else COLOR[pk]
            self._mini_centrada(pk, px + 50 + k * 26, 92, ck, 5)

        self._caja(HOLD_BOX, "GUARDAR", not t.hold_usado)
        x, y, w, h = HOLD_BOX
        if t.hold:
            hc = (ORO if t.hold_oro else COLOR[t.hold]) if not t.hold_usado else HOLDC
            self._mini_centrada(t.hold, x + w / 2, y + 21, hc, 6)
        else:
            ctext(x + w / 2, y + 18, "toca" if self.touch else "c", LABEL)

        self._caja(ITEM_BOX, "ÍTEM", bool(t.items))
        x, y, w, h = ITEM_BOX
        for i in range(ITEMS_MAX):
            bx_, by_ = x + 3 + i * 15, y + 14
            if i < len(t.items):
                tipo = t.items[i]
                c = BOMBC if tipo == BOMBA else FREEZEC
                pyxel.rect(bx_, by_, 12, 12, SHADOW)
                pyxel.rectb(bx_, by_, 12, 12, c if i == 0 else FRAME)
                if tipo == BOMBA:
                    pyxel.circ(bx_ + 6, by_ + 7, 3, c)
                    pyxel.line(bx_ + 7, by_ + 3, bx_ + 9, by_ + 1, LABEL)
                    if (self.f // 6) % 2:
                        pyxel.pset(bx_ + 9, by_ + 1, HOT)
                else:
                    pyxel.line(bx_ + 2, by_ + 6, bx_ + 10, by_ + 6, c)
                    pyxel.line(bx_ + 6, by_ + 2, bx_ + 6, by_ + 10, c)
                    pyxel.line(bx_ + 3, by_ + 3, bx_ + 9, by_ + 9, c)
                    pyxel.line(bx_ + 9, by_ + 3, bx_ + 3, by_ + 9, c)
            else:
                pyxel.rectb(bx_, by_, 12, 12, FRAME)
        if t.items:
            nombre = "bomba" if t.items[0] == BOMBA else "freno"
            ctext(x + w / 2, y + h - 6, nombre, LABEL)

        # la basura: cuánto falta para la próxima fila
        y = 152
        gap = t.basura_gap()
        frac = 1 - t.basura_t / gap
        cerca = t.basura_t <= 120
        bcol = HOT if cerca and (self.f // 5) % 2 else GARBAGE
        if cerca:
            text(px, y, "BASURA EN %ds" % ((t.basura_t + 59) // 60), HOT)
        else:
            text(px, y, "SUBE BASURA", LABEL)
        fx.bar(px, y + 8, pw, 4, frac, bcol, EMPTY, None)
        if t.freno:
            text(px, y + 16, "FRENO %ds" % ((t.freno + 59) // 60), FREEZEC)

        y = 178
        if self.touch:
            ayuda = ("toca: gira", "arrastra: mueve", "desliza abajo: cae",
                     "desliza arriba: guarda")
        else:
            ayuda = ("arriba gira", "espacio cae", "c guarda", "z usa ítem")
        for i, linea in enumerate(ayuda):
            text(px, y + i * 9, linea, LABEL)


class Game:
    def __init__(self):
        Cabinet(
            game_id="bloques", title="BLOQUES",
            subtitle="100 segundos, el puntaje es todo",
            howto=["toca gira · arrastra mueve · desliza abajo cae",
                   "líneas seguidas multiplican · tetris seguidos, más",
                   "la pieza dorada paga doble y da un ítem",
                   "los últimos 20 s: fiebre, todo paga x2",
                   "teclado: flechas · espacio cae · c guarda · z ítem"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=LABEL, accent=ACCENT,
                        warn=C_Z, shadow=SHADOW, panel=EMPTY),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
