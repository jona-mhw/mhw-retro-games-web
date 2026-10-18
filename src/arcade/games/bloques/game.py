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

la pantalla es vertical (240x380), pensada para el celular parado: el tablero
ocupa el centro con celdas de 16 px (en el teléfono, ~25 px de pantalla cada
una), el reloj y el puntaje van en una franja arriba con números grandes, y a
los lados quedan dos columnas: GUARDA e ÍTEM a la izquierda (se tocan), las
próximas y la basura a la derecha.

en el celular se juega sobre la pantalla misma: **arrastrar** mueve la pieza
columna por columna, **tocar** la gira, **deslizar rápido hacia abajo** la deja
caer y **hacia arriba** la guarda. los cuadros de GUARDA e ÍTEM también se
tocan. la cruceta y los botones siguen valiendo.

la lógica (piezas, rotación, colisión, líneas, reloj) vive en la clase Tetris,
sin pyxel: `frame()` avanza un frame y devuelve qué pasó. la piel (World) hornea
una vez los bloques con bisel y el fondo de cada tablero en imágenes, así un
frame es un `blt` de fondo más un `blt` por bloque.
"""
import math
import random

import pyxel

from pixelkit import fx, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import big_ctext, big_text, big_width, ctext, text

COLS, ROWS = 10, 20
CELL = 16
W, H = 240, 380
BW, BH = COLS * CELL, ROWS * CELL          # 160 x 320
BX, BY = (W - BW) // 2, 54                 # el tablero, centrado bajo la franja
HUD_H = 47                                 # la franja de arriba

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

# --- paleta --------------------------------------------------------------
# cada pieza tiene su rampa de seis tonos (contorno, sombra, medio oscuro,
# medio, luz, brillo): con eso el bloque se hornea con bisel — luz arriba a la
# izquierda, sombra abajo a la derecha — y se lee como una pieza con volumen y
# no como un cuadrado plano.
PAL = []


def _c(*rgb):
    i = len(PAL)
    PAL.extend(rgb)
    return i if len(rgb) == 1 else tuple(range(i, i + len(rgb)))


BG = _c(0x080A12)
EMPTY = _c(0x161C2C)             # el fondo de las barras
PANEL = _c(0x10162A)
PANEL2 = _c(0x1A2240)
FRAME = _c(0x2C3656)
FRAME2 = _c(0x48557E)
TXT = _c(0xE8ECF5)
LABEL = _c(0x9AA6C8)
DIM = _c(0x5A6480)
SHADOW = _c(0x04050A)
WHITE = _c(0xF6F8FF)
ACCENT = _c(0x8AC52F)
ACCENT_D = _c(0x3E6A14)
GOLD = _c(0xFFD24A)
HOT = _c(0xFF5A3A)
FLASHC = _c(0xFFF3B0)
BOMBC = _c(0xFF8A3A)
BOMB_D = _c(0x8A3410)
FREEZEC = _c(0x7ADCFF)
FREEZE_D = _c(0x2A7AA8)
FREEZE_O = _c(0x123A5A)
HOLDC = _c(0x6A7898)
ROJO_OSC = _c(0x3A1018)
ROJO = _c(0xE8383A)
MAGENTA = _c(0xD84AB8)

RAMPAS = {   # contorno, sombra, medio oscuro, medio, luz, brillo
    "I": _c(0x0A2E3C, 0x157A90, 0x26A6BC, 0x3AC6D8, 0x8AE8F2, 0xE6FDFF),
    "O": _c(0x4A3004, 0xA87A0C, 0xD4A620, 0xEDC73C, 0xFFE586, 0xFFF9DC),
    "T": _c(0x260C3C, 0x5E2E8A, 0x8846B4, 0xA862D2, 0xD29CF0, 0xF6E6FF),
    "S": _c(0x0E3210, 0x2E7A26, 0x48A03A, 0x62BC4C, 0x9EE07A, 0xE8FFD8),
    "Z": _c(0x420C10, 0x962424, 0xBE3630, 0xDC4A3C, 0xF68C74, 0xFFE4DC),
    "J": _c(0x0C1A4A, 0x26469C, 0x3A60C0, 0x4E7CDC, 0x8EB2F6, 0xE4EEFF),
    "L": _c(0x421E06, 0x9A5014, 0xC46A20, 0xE4882E, 0xF8B868, 0xFFF2DC),
    "oro": _c(0x4A2E00, 0x9A6A06, 0xD89A0E, 0xFFC21A, 0xFFE47A, 0xFFFDE8),
    "basura": _c(0x141824, 0x2E364A, 0x404A62, 0x535D78, 0x78829E, 0xA4ACC4),
    "usada": _c(0x1A2030, 0x343E52, 0x444E62, 0x566074, 0x768096, 0x9AA2B4),
}
C_I, C_O, C_T, C_S, C_Z, C_J, C_L = (RAMPAS[k][3] for k in "IOTSZJL")
ORO = RAMPAS["oro"][3]
ORO2, ORO3 = RAMPAS["oro"][4], RAMPAS["oro"][1]
GARBAGE = RAMPAS["basura"][3]
USADA = RAMPAS["usada"][3]
TILE = {RAMPAS[k][3]: i for i, k in enumerate(RAMPAS)}   # medio -> n° de baldosa

# un tablero distinto por nivel: (fondo hondo, fondo, línea, y el marco en tres
# tonos). el cambio de colores es lo que hace que subir de nivel se sienta como
# llegar a otro lugar y no sólo como que el número cambió.
TEMAS_RGB = [   # hondo, fondo, columna alterna, línea, marco (3)
    (0x05070E, 0x0C1020, 0x0F1426, 0x1C2442, 0x141C38, 0x3A4670, 0x7484BC),  # noche
    (0x08050F, 0x130C24, 0x170F2C, 0x2A1C48, 0x22143E, 0x5A3A8E, 0x9C7CD4),  # violeta
    (0x030C0D, 0x081C1E, 0x0A2225, 0x14383C, 0x0C3238, 0x23727A, 0x60BAC0),  # laguna
    (0x0C0408, 0x1E0C14, 0x241018, 0x3A1A2A, 0x3A1220, 0x8A2E42, 0xD26C7E),  # carmín
    (0x030A05, 0x0A1C10, 0x0D2214, 0x18361F, 0x143618, 0x357A3C, 0x76BC6C),  # bosque
    (0x0A0704, 0x20160A, 0x261B0D, 0x3E2E16, 0x42300E, 0x8A6A26, 0xD2AA5C),  # bronce
]
TEMAS = [_c(*rgb) for rgb in TEMAS_RGB]
TEMA_FIEBRE = _c(0x100403, 0x260C06, 0x2E1008, 0x48200E, 0x5A1406, 0xC8401A, 0xFF9450)
MARCO_FRENO = (FREEZE_O, FREEZE_D, FREEZEC)
KEY = 255                         # el transparente de las baldosas: nunca se pinta
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



# --- el arte horneado ----------------------------------------------------------
# las baldosas (bloques con bisel de 16, 8 y 6 px, y la fantasma) y el fondo de
# cada tablero se dibujan una sola vez en imágenes propias. después, un frame es
# un blt de fondo y un blt por bloque: barato aunque el tablero esté lleno.
_TILES = None
_FONDOS = {}
GHOST_V, MINI8_V, MINI6_V = 16, 32, 40


def _bisel(img, u, v, r, nombre):
    o, s, m2, m, l, h = r
    img.rect(u, v, 16, 16, o)
    img.rect(u + 1, v + 1, 14, 14, m)
    img.rect(u + 3, v + 9, 10, 4, m2)           # la cara se oscurece abajo
    img.rect(u + 1, v + 1, 14, 2, l)            # bisel de luz arriba
    img.rect(u + 1, v + 1, 2, 14, l)            # y a la izquierda
    img.rect(u + 1, v + 13, 14, 2, s)           # sombra abajo
    img.rect(u + 13, v + 1, 2, 14, s)           # y a la derecha
    img.pset(u + 14, v + 1, m)                  # las esquinas, en diagonal
    img.pset(u + 13, v + 2, m)
    img.pset(u + 14, v + 2, s)
    img.pset(u + 1, v + 14, m)
    img.pset(u + 2, v + 13, m)
    img.pset(u + 2, v + 14, s)
    img.rect(u + 3, v + 3, 10, 1, l)            # el filo de la cara
    for x, y in ((2, 2), (3, 2), (4, 2), (2, 3), (2, 4), (4, 4)):
        img.pset(u + x, v + y, h)               # el brillo, arriba a la izquierda
    if nombre == "oro":
        # una gema al centro, para que no se confunda con la O amarilla
        img.rect(u + 5, v + 5, 6, 6, o)
        img.rect(u + 6, v + 6, 4, 4, l)
        img.rect(u + 7, v + 6, 2, 1, h)
        img.pset(u + 6, v + 6, h)
        img.rect(u + 8, v + 8, 2, 2, s)
    elif nombre == "basura":
        # remaches y una grieta: es chatarra, no una pieza
        for x, y in ((4, 4), (11, 4), (4, 11), (11, 11)):
            img.pset(u + x, v + y, o)
            img.pset(u + x - 1, v + y - 1, h)
        img.line(u + 6, v + 10, u + 9, v + 6, s)


def _mini(img, u, v, n, r):
    o, s, m2, m, l, h = r
    img.rect(u, v, n, n, o)
    img.rect(u + 1, v + 1, n - 2, n - 2, m)
    img.rect(u + 1, v + 1, n - 2, 1, l)
    img.rect(u + 1, v + 1, 1, n - 2, l)
    img.rect(u + 1, v + n - 2, n - 2, 1, s)
    img.rect(u + n - 2, v + 1, 1, n - 2, s)
    img.pset(u + 1, v + 1, h)


def _fantasma(img, u, v, r):
    """la pieza fantasma: un contorno claro y un tramado ralo. se ve dónde cae
    sin tapar lo que hay debajo."""
    o, s, m2, m, l, h = r
    img.rectb(u + 1, v + 1, 14, 14, l)
    img.rectb(u + 2, v + 2, 12, 12, s)
    for x, y in ((1, 1), (14, 1), (1, 14), (14, 14)):
        img.pset(u + x, v + y, h)
    for y in range(4, 12):
        for x in range(4, 12):
            if (x + y) % 4 == 0:
                img.pset(u + x, v + y, m2)


def tiles():
    global _TILES
    if _TILES is None:
        img = pyxel.Image(256, 48)
        img.cls(KEY)
        for k, nombre in enumerate(RAMPAS):
            r = RAMPAS[nombre]
            _bisel(img, k * 16, 0, r, nombre)
            _fantasma(img, k * 16, GHOST_V, r)
            _mini(img, k * 8, MINI8_V, 8, r)
            _mini(img, 128 + k * 8, MINI6_V, 6, r)
        _TILES = img
    return _TILES


# zonas de la pantalla. los cuadros de GUARDA e ÍTEM se tocan con el dedo
COL_W = BX - 5                                 # 35: el ancho de cada columna
CL, CR = 2, BX + BW + 3                        # x de la columna izq. y der.
HOLD_BOX = (CL, BY, COL_W, 50)
ITEM_BOX = (CL, BY + 56, COL_W, 88)
NEXT_BOX = (CR, BY, COL_W, 104)
BASURA_BOX = (CR, BY + 110, COL_W, 122)


def _caja_fija(img, caja):
    x, y, w, h = caja
    img.rect(x + 2, y + 2, w, h, SHADOW)
    img.rect(x, y, w, h, PANEL)
    img.rectb(x, y, w, h, FRAME)
    img.rect(x + 1, y + 1, w - 2, 8, PANEL2)


def fondo(tema):
    """la pantalla de fondo de un tema: textura de afuera, franja del HUD,
    cajas de las columnas y el pozo del tablero con su degradé. se hornea la
    primera vez que se pide y queda en caché."""
    img = _FONDOS.get(tema)
    if img is not None:
        return img
    deep, base, alt, line, fo, fm, fl = tema
    img = pyxel.Image(W, H)
    img.cls(BG)
    # afuera: diagonales tenues del color del tema y una viñeta
    for i in range(-H, W, 10):
        img.line(i, 0, i + H, H, deep)
    img.dither(0.5)
    for i in range(-H, W, 10):
        img.line(i + 1, 0, i + 1 + H, H, deep)
    for k, a in enumerate((0.75, 0.5, 0.25)):
        img.dither(a)
        img.rect(k * 4, 0, 4, H, SHADOW)
        img.rect(W - 4 - k * 4, 0, 4, H, SHADOW)
        img.rect(0, H - 4 - k * 4, W, 4, SHADOW)
    img.dither(1.0)
    # la franja del HUD
    img.rect(0, 0, W, HUD_H, PANEL)
    img.dither(0.5)
    img.rect(0, 0, W, 10, PANEL2)
    img.dither(1.0)
    img.rect(0, HUD_H, W, 1, FRAME2)
    img.rect(0, HUD_H + 1, W, 1, SHADOW)
    for caja in (HOLD_BOX, ITEM_BOX, NEXT_BOX, BASURA_BOX):
        _caja_fija(img, caja)
    # el pozo: columnas alternas (para apuntar), hondo arriba y un resplandor
    # de piso abajo
    img.rect(BX, BY, BW, BH, base)
    for c in range(1, COLS, 2):
        img.rect(BX + c * CELL, BY, CELL, BH, alt)
    for k, a in enumerate((0.75, 0.5, 0.25)):
        img.dither(a)
        img.rect(BX, BY + k * 16, BW, 16, deep)
    img.dither(0.25)
    img.rect(BX, BY + BH - 48, BW, 48, line)
    img.dither(0.5)
    img.rect(BX, BY + BH - 16, BW, 16, line)
    img.dither(1.0)
    for y in range(1, ROWS):                    # puntitos en las esquinas de celda
        for x in range(1, COLS):
            img.pset(BX + x * CELL, BY + y * CELL, line)
    _FONDOS[tema] = img
    return img


def dentro(mx, my, caja):
    x, y, w, h = caja
    return x <= mx < x + w and y <= my < y + h


# los gestos sobre la pantalla, en píxeles de juego. en el teléfono el juego se
# ve a ~1.5x: 10 px de juego son ~15 px de pantalla por columna, lo mismo que
# antes, pero ahora el tablero mide el doble y hay más lugar para el dedo.
PASO_X = 10
PASO_Y = 11
FLICK = 18                       # px en 4 frames = deslizar rápido (~400 px/s)
TAP_PX = 5
TAP_FRAMES = 16


class World:
    """el tetris jugándose: input, dibujo y chispas. el Cabinet lo envuelve."""

    def __init__(self):
        self.t = Tetris()
        self.fx = fx.Fx(gravity=0.2, max_parts=320)
        self.lvl = 1
        self.fx.destello(WHITE)
        self.barridos = []           # [fila, frames] líneas que estallan
        self.banner = None           # [texto, col, sub, subcol, frames, frames0]
        self.golpe = 0               # el tablero salta cuando sube la basura
        self.score_pop = 0
        self.score_vis = 0           # el puntaje del hud corre hacia el real
        self.gesto = None
        self.tocado = []             # [caja, frames]: el cuadro que tocaste
        self.cuenta = -1
        self.touch = web.is_touch()
        self.f = 0                   # reloj propio de la piel (titileos, brillos)
        self.aterriza = []           # [celdas, frames]: el destello al apoyarse
        tiles()
        fondo(TEMAS[0])

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
            self._usar_item(ev)
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
            for k in range(16):
                self.fx.burst(BX + k * 10 + 5, BY + BH, (WHITE, ACCENT, C_S),
                              n=2, speed=3.0, life=30, angle=-math.pi / 2,
                              spread=0.7)
        # la fiebre: brasas que suben desde el fondo del tablero
        if t.fiebre() and self.f % 2 == 0:
            x = BX + 4 + (self.f * 37) % (BW - 8)
            self.fx.burst(x, BY + BH - 2, (FLASHC, HOT, BOMBC, C_Z), n=1,
                          speed=1.2, life=60, angle=-math.pi / 2, spread=0.5,
                          gravity=-0.01)
        s = (t.time + 59) // 60
        if s != self.cuenta:
            self.cuenta = s
            if 0 < s <= 5 and not t.over:
                self.fx.shake(1)
        self.barridos = [[f, n - 1] for f, n in self.barridos if n > 1]
        self.tocado = [[c, n - 1] for c, n in self.tocado if n > 1]
        self.aterriza = [[c, n - 1] for c, n in self.aterriza if n > 1]
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
            self.fx.burst(x + w / 2, y + h / 2, (WHITE, HOLDC, FRAME), n=10,
                          speed=1.5, life=16, gravity=0)

    def _usar_item(self, ev):
        if self.t.usar_item(ev) is not None:
            self.tocado.append([ITEM_BOX, 8])

    def _tactil(self, ev):
        """los gestos sobre la pantalla. devuelve True si pidió caer de golpe.

        el dedo no aprieta teclas acá: el juego lee el mouse de pyxel (que en el
        celular es el dedo sobre la pantalla) y arma los gestos él mismo. así un
        arrastre mueve exactamente una columna por cada PASO_X, que es lo que
        hace que se pueda apuntar, y el toque corto se distingue del arrastre.
        el gesto vale en cualquier parte de la pantalla, no sólo en el tablero:
        las columnas de los lados también sirven para arrastrar.
        """
        t = self.t
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.gesto = None
            if dentro(mx, my, HOLD_BOX):
                self._guardar()
                return False
            if dentro(mx, my, ITEM_BOX):
                self._usar_item(ev)
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
        if g["eje"] is None and max(abs(dx), abs(dy)) >= 6:
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
        cx = BX + BW / 2
        if kind == "lineas":
            _, n, filas, ganado, combo = e
            for f in filas:
                self.barridos.append([f, 16])
                for c in range(COLS):
                    x, y = self._px(c, f)
                    self.fx.burst(x, y, (WHITE, FLASHC, GOLD, HOT), n=3 + n // 2,
                                  speed=1.9 + 0.5 * n, life=26)
            nombre = ("", "", "DOBLE", "TRIPLE", "¡TETRIS!")[n]
            sub = "COMBO x%d" % combo if combo > 1 else None
            if n == 4:
                self._cartel(nombre, GOLD, sub, HOT, 70)
            elif nombre or sub:
                self._cartel(nombre or sub, WHITE if nombre else HOT,
                             sub if nombre else None, HOT)
            self.fx.popup(cx, BY + filas[0] * CELL - 4, "+%d" % ganado,
                          GOLD if self.t.fiebre() else WHITE, life=48)
            self.fx.shake(2 + n)
            self.fx.destello(FLASHC if n < 4 else GOLD)
            self.score_pop = 12
        elif kind == "b2b":
            self.fx.popup(cx, BY + 80, "SEGUIDO x1.5", HOT, life=60)
        elif kind == "oro":
            self.fx.popup(cx, BY + 98, "ORO x2 +ÍTEM", ORO, life=60)
            for _ in range(2):
                self.fx.burst(cx, BY + 160, (WHITE, ORO2, ORO, ORO3), n=18,
                              speed=3.2, life=36)
        elif kind == "dorada":
            self.fx.popup(cx, BY + 44, "PIEZA DORADA", ORO, life=50)
        elif kind == "perfecto":
            for cy in range(0, ROWS, 2):
                for c in range(0, COLS, 3):
                    x, y = self._px(c, cy)
                    self.fx.burst(x, y, (WHITE, GOLD, FLASHC, C_I), n=2,
                                  speed=1.8, life=34)
            self._cartel("¡PERFECTO!", GOLD, "+%d" % e[1], WHITE, 90)
            self.fx.shake(6)
            self.fx.destello(GOLD)
        elif kind == "drop":
            caida, celdas, col = e[1], e[2], e[3]
            self.aterriza.append([celdas, 8])
            if caida > 0:
                # polvo donde aterriza y una estela que sube por donde bajó
                for x, y in celdas:
                    px, py = self._px(x, y)
                    self.fx.burst(px, py + CELL / 2, (WHITE, col, FRAME), n=3,
                                  speed=1.6, life=14, angle=-math.pi / 2,
                                  spread=2.6, gravity=0.06)
            if caida > 2:
                self.fx.shake(2)
                self.golpe = 4
        elif kind == "bomba":
            for f in range(ROWS - max(1, e[1]), ROWS):
                self.barridos.append([f, 16])
                for c in range(COLS):
                    x, y = self._px(c, f)
                    self.fx.burst(x, y, (WHITE, BOMBC, HOT, C_Z), n=4, speed=3.0,
                                  life=30)
            self._cartel(ITEM_NOMBRE[BOMBA], BOMBC, None, WHITE, 45)
            self.fx.shake(7)
            self.fx.destello(BOMBC)
        elif kind == "freno":
            self._cartel(ITEM_NOMBRE[FRENO], FREEZEC, "4 SEGUNDOS", WHITE, 45)
            self.fx.destello(FREEZEC)
            for k in range(12):
                self.fx.burst(BX + k * 14 + 7, BY + 2, (WHITE, FREEZEC, FREEZE_D),
                              n=2, speed=1.2, life=40, angle=math.pi / 2,
                              spread=1.0, gravity=0.02)
        elif kind == "item_gana":
            x, y, w, h = ITEM_BOX
            self.fx.popup(x + w / 2 + 2, y + 2, "+ÍTEM", ACCENT, life=40)
            self.fx.burst(x + w / 2, y + h / 2, (WHITE, ACCENT, C_S), n=12,
                          speed=1.8, life=20, gravity=0)
        elif kind == "basura":
            self.golpe = 8
            for c in range(COLS):
                x, y = self._px(c, ROWS - 1)
                self.fx.burst(x, y + 6, (WHITE, GARBAGE, FRAME), n=2, speed=2.2,
                              life=18, angle=-math.pi / 2, spread=1.2)
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
    def _block(self, px, py, col):
        pyxel.blt(px, py, _TILES, TILE[col] * 16, 0, 16, 16)
        if col == ORO:
            # un brillo que recorre el oro, para que se lea aunque esté quieto
            k = (self.f // 2 + px // 2 + py // 3) % 30
            if k < 13:
                pyxel.pset(px + 2 + k, py + 2, WHITE)
                pyxel.pset(px + 2, py + 2 + k, WHITE)

    def _tema(self):
        t = self.t
        if t.fiebre():
            return TEMA_FIEBRE
        return TEMAS[(t.level - 1) % len(TEMAS)]

    def _marco(self, fo, fm, fl):
        """el marco del pozo, con volumen: luz arriba-izquierda, sombra abajo."""
        x, y, w, h = BX - 4, BY - 4, BW + 8, BH + 8
        pyxel.rectb(x, y, w, h, fo)
        pyxel.rectb(x + 1, y + 1, w - 2, h - 2, fm)
        pyxel.rect(x + 1, y + 1, w - 2, 1, fl)
        pyxel.rect(x + 1, y + 1, 1, h - 2, fl)
        pyxel.rectb(x + 2, y + 2, w - 4, h - 4, fm)
        pyxel.rectb(x + 3, y + 3, w - 6, h - 6, SHADOW)

    def draw(self):
        t = self.t
        sx, sy = self.fx.offset()
        tema = self._tema()
        pyxel.blt(0, 0, fondo(tema), 0, 0, W, H)
        fo, fm, fl = tema[4:]
        if t.fiebre():
            if (self.f // 6) % 2:
                fm, fl = HOT, FLASHC
        if t.freno:
            fo, fm, fl = MARCO_FRENO
        pyxel.camera(-sx, -sy + (self.golpe // 2))
        self._marco(fo, fm, fl)
        pyxel.clip(BX + sx, BY + sy - self.golpe // 2, BW, BH)   # clip va en pantalla
        # los últimos 10 segundos, enormes detrás de las piezas
        s = (t.time + 59) // 60
        if 0 < s <= 10 and not t.over:
            big_ctext(BX + BW / 2, BY + BH / 2 - 30, "%d" % s, ROJO_OSC, 10)
        # la zona de peligro: si la pila llega arriba, el techo late en rojo
        alto = next((y for y in range(ROWS) if any(t.board[y])), ROWS)
        if alto <= 5 and not t.over and (self.f // 8) % 2:
            pyxel.dither(0.25)
            pyxel.rect(BX, BY, BW, CELL * 3, ROJO)
            pyxel.dither(1.0)
        blt = pyxel.blt
        tl = _TILES
        for y in range(alto, ROWS):
            row = t.board[y]
            py = BY + y * CELL
            for x in range(COLS):
                v = row[x]
                if v:
                    if v == ORO:
                        self._block(BX + x * CELL, py, v)
                    else:
                        blt(BX + x * CELL, py, tl, TILE[v] * 16, 0, 16, 16)
        for celdas, n in self.aterriza:         # la pieza recién puesta, blanca
            pyxel.dither(n / 10)
            for x, y in celdas:
                if 0 <= y < ROWS:
                    pyxel.rect(BX + x * CELL, BY + y * CELL, CELL, CELL, WHITE)
            pyxel.dither(1.0)
        if not t.over:
            col = ORO if t.oro else COLOR[t.pk]
            gy = t.ghost_y()
            cel = t._cells(t.shape, t.px, t.py)
            if gy != t.py:
                u = TILE[col] * 16
                for x, y in t._cells(t.shape, t.px, gy):
                    blt(BX + x * CELL, BY + y * CELL, tl, u, GHOST_V, 16, 16, KEY)
            for x, y in cel:
                if y >= 0:
                    self._block(BX + x * CELL, BY + y * CELL, col)
            # apoyada: un borde blanco que avisa que está por fijarse
            if t.lock_t and (self.f // 3) % 2:
                for x, y in cel:
                    if y >= 0:
                        pyxel.rectb(BX + x * CELL, BY + y * CELL, CELL, CELL, WHITE)
        for f, n in self.barridos:              # la línea que estalla: un fogonazo
            w = int(BW * min(1.0, n / 9))
            pyxel.rect(BX + (BW - w) // 2, BY + f * CELL + 1, w, CELL - 2,
                       WHITE if n > 10 else FLASHC)
            if n > 10:
                pyxel.rect(BX, BY + f * CELL + 6, BW, 4, WHITE)
        # la basura que viene: flechas rojas que suben por el fondo del pozo
        if not t.over and t.basura_t <= 120 and (self.f // 5) % 2:
            yy = BY + BH - 7 - (self.f // 5) % 2
            for k in range(COLS):
                xx = BX + k * CELL + 8
                pyxel.tri(xx - 5, yy + 5, xx + 5, yy + 5, xx, yy, HOT)
        if t.freno:                             # escarcha en las orillas
            pyxel.dither(0.25 + 0.1 * ((self.f // 10) % 2))
            pyxel.rect(BX, BY, BW, 6, FREEZEC)
            pyxel.rect(BX, BY, 4, BH, FREEZEC)
            pyxel.rect(BX + BW - 4, BY, 4, BH, FREEZEC)
            pyxel.dither(1.0)
        pyxel.clip()
        self._chispas()
        if self.banner and not t.over:
            self._draw_banner()
        if t.over:
            pyxel.rect(BX, BY + 90, BW, 36, PANEL)
            pyxel.rect(BX, BY + 90, BW, 1, FRAME2)
            pyxel.rect(BX, BY + 125, BW, 1, FRAME2)
            if t.time == 0:
                big_ctext(BX + BW / 2, BY + 100, "¡TIEMPO!", GOLD, 3, SHADOW)
            else:
                big_ctext(BX + BW / 2, BY + 100, "¡LLENO!", C_Z, 3, SHADOW)
        pyxel.camera()
        self.fx.draw_flash(BX, BY, BW, BH)
        self._hud()
        self._columnas()

    def _chispas(self):
        """las chispas de fx, pero de 2x2 mientras están vivas (a esta escala un
        píxel suelto no se ve), y los "+puntos" con texto grande."""
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
            sc = 2 if len(s) <= 12 and BX < x < BX + BW else 1
            big_ctext(x, int(y) - 6, s, col, sc, SHADOW)

    def _draw_banner(self):
        s, col, sub, subcol, n, n0 = self.banner
        edad = n0 - n
        if n < 12 and (n // 2) % 2:
            return                               # titila al irse
        # entra grande y se asienta: el "golpe" del cartel
        tope = 4 if big_width(s, 4) <= BW + 8 else 3
        esc = tope + (1 if edad < 5 else 0)
        cx = BX + BW / 2
        cy = BY + 112
        # sombra honda (2 px) en vez de una franja de fondo: el cartel se lee
        # sobre los bloques sin tapar la pila
        big_ctext(cx + 2, cy + 2, s, SHADOW, esc)
        big_ctext(cx, cy, s, col, esc)
        if sub:
            sc = 2 if len(sub) <= 18 else 1
            big_ctext(cx + 1, cy + 6 * esc + 9, sub, SHADOW, sc)
            big_ctext(cx, cy + 6 * esc + 8, sub, subcol, sc)

    def _mini(self, pieza, cx, cy, col, n):
        """una pieza chica centrada en (cx, cy), con baldosas de n px."""
        sh = SHAPES[pieza]
        cel = [(x, y) for y, row in enumerate(sh) for x, ch in enumerate(row)
               if ch == "X"]
        x0 = min(x for x, _ in cel)
        y0 = min(y for _, y in cel)
        w = (max(x for x, _ in cel) - x0 + 1) * n
        h = (max(y for _, y in cel) - y0 + 1) * n
        ox, oy = int(cx - w / 2), int(cy - h / 2)
        if n == 8:
            u0, v = TILE[col] * 8, MINI8_V
        else:
            u0, v = 128 + TILE[col] * 8, MINI6_V
        for x, y in cel:
            pyxel.blt(ox + (x - x0) * n, oy + (y - y0) * n, _TILES, u0, v, n, n)

    def _caja(self, caja, titulo, activo=True):
        """encima de la caja horneada: el título y, si está activa, su borde."""
        x, y, w, h = caja
        if any(c == caja for c, _ in self.tocado):
            pyxel.rect(x + 1, y + 1, w - 2, h - 2, FRAME2)
        borde = ACCENT if activo else FRAME
        pyxel.rectb(x, y, w, h, borde)
        pyxel.rect(x + 1, y + 1, w - 2, 8, ACCENT_D if activo else PANEL2)
        ctext(x + w / 2, y + 2, titulo, WHITE if activo else LABEL)

    def _hud(self):
        """la franja de arriba: reloj, puntaje y lo que está pasando."""
        t = self.t
        fiebre = t.fiebre()
        s = (t.time + 59) // 60
        urge = 0 < s <= 10 and self.f % 30 < 15
        col = ROJO if urge else (HOT if fiebre else WHITE)
        text(6, 4, "TIEMPO", LABEL)
        ss = "%d" % s
        big_text(6, 13, ss, col, 3, SHADOW)
        text(8 + big_width(ss, 3), 25, "s", LABEL)
        sc = "%d" % self.score_vis
        text(W - 6 - 24, 4, "PUNTOS", LABEL)
        big_text(W - 6 - big_width(sc, 3), 13, sc,
                 GOLD if self.score_pop else WHITE, 3, SHADOW)
        # al medio: lo que paga ahora (fiebre, combo o el tetris que sigue)
        cx = 104
        if fiebre:
            fcol = GOLD if (self.f // 8) % 2 else HOT
            big_ctext(cx, 13, "FIEBRE", fcol, 2, SHADOW)
            ctext(cx, 29, "todo paga x2", fcol)
        elif t.combo > 1 or (t.combo and t.combo_t):
            ccol = HOT if t.combo > 1 else LABEL
            big_ctext(cx, 13, "COMBO x%d" % t.combo, ccol, 2, SHADOW)
            fx.bar(cx - 30, 29, 60, 3, t.combo_t / COMBO_TTL, ccol, EMPTY)
        elif t.b2b:
            bcol = HOT if (self.f // 8) % 2 else GOLD
            big_ctext(cx, 13, "x1.5", bcol, 2, SHADOW)
            ctext(cx, 29, "otro tetris", bcol)
        else:
            ctext(cx, 15, "NIVEL %d" % t.level, LABEL)
            ctext(cx, 24, "%d líneas" % t.lines, DIM)
        # la barra del blitz, con la marca de dónde empieza la fiebre
        bcol = ROJO if s <= 10 else (HOT if fiebre else ACCENT)
        fx.bar(6, 37, W - 12, 5, t.time / TIME, bcol, EMPTY, None)
        mx = 6 + int((W - 12) * FIEBRE / TIME)
        pyxel.rect(mx, 35, 1, 9, GOLD)

    def _columnas(self):
        t = self.t
        # --- izquierda: guardar, ítems, nivel
        self._caja(HOLD_BOX, "GUARDA", not t.hold_usado)
        x, y, w, h = HOLD_BOX
        if t.hold:
            hc = (ORO if t.hold_oro else COLOR[t.hold]) if not t.hold_usado \
                else USADA
            self._mini(t.hold, x + w / 2, y + 29, hc, 8)
        else:
            ctext(x + w / 2, y + 27, "toca" if self.touch else "c", DIM)

        self._caja(ITEM_BOX, "ÍTEM", bool(t.items))
        x, y, w, h = ITEM_BOX
        for i in range(ITEMS_MAX):
            bx_, by_ = x + 7, y + 13 + i * 25
            self._item(bx_, by_, t.items[i] if i < len(t.items) else None, i == 0)

        x = CL + COL_W / 2
        y = ITEM_BOX[1] + ITEM_BOX[3] + 10
        ctext(x, y, "NIVEL", LABEL)
        big_ctext(x, y + 10, "%d" % t.level, TXT, 3, SHADOW)
        y += 36
        ctext(x, y, "LÍNEAS", LABEL)
        big_ctext(x, y + 10, "%d" % t.lines, TXT, 2, SHADOW)
        y += 30
        if t.oros or t.perfectos:
            ctext(x, y, "ORO %d" % t.oros, ORO)
            if t.perfectos:
                ctext(x, y + 9, "PERF %d" % t.perfectos, GOLD)
        # la ayuda, abajo: corta, de a dos palabras (con flechita si hace falta)
        if self.touch:
            ayuda = (("toca", "gira", 0), ("arrastra", "mueve", 0),
                     ("desliza", "cae", 1), ("desliza", "guarda", -1))
        else:
            ayuda = (("arriba", "gira", 0), ("espacio", "cae", 0),
                     ("c", "guarda", 0), ("z", "ítem", 0))
        y = H - 6 - len(ayuda) * 16
        for a, b, flecha in ayuda:
            ctext(x, y, a, DIM)
            if flecha:
                w = len(b) * 4 + 6
                x0 = int(x - w / 2)
                if flecha > 0:
                    pyxel.tri(x0, y + 8, x0 + 4, y + 8, x0 + 2, y + 11, LABEL)
                else:
                    pyxel.tri(x0, y + 11, x0 + 4, y + 11, x0 + 2, y + 8, LABEL)
                text(x0 + 6, y + 7, b, LABEL)
            else:
                ctext(x, y + 7, b, LABEL)
            y += 16

        # --- derecha: las próximas y la basura
        self._caja(NEXT_BOX, "SIGUE", True)
        x, y, w, h = NEXT_BOX
        cx = x + w / 2
        c0 = ORO if t.cola_oro[0] else COLOR[t.cola[0]]
        self._mini(t.cola[0], cx, y + 30, c0, 8)
        pyxel.rect(x + 5, y + 50, w - 10, 1, FRAME)
        for k, pk in enumerate(t.cola[1:]):          # las que siguen, más chicas
            ck = ORO if t.cola_oro[k + 1] else COLOR[pk]
            self._mini(pk, cx, y + 66 + k * 24, ck, 6)

        gap = t.basura_gap()
        frac = 1 - t.basura_t / gap
        cerca = t.basura_t <= 120
        self._caja(BASURA_BOX, "BASURA", cerca)
        x, y, w, h = BASURA_BOX
        bx_, by_, bw_, bh_ = x + 9, y + 14, w - 18, h - 42
        pyxel.rect(bx_, by_, bw_, bh_, EMPTY)
        lleno = int(bh_ * max(0.0, min(1.0, frac)))
        bcol = HOT if cerca and (self.f // 5) % 2 else GARBAGE
        pyxel.rect(bx_, by_ + bh_ - lleno, bw_, lleno, bcol)
        for k in range(by_ + bh_ - 4, by_ + bh_ - lleno, -6):   # la chatarra apilada
            pyxel.rect(bx_, k, bw_, 1, SHADOW)
        pyxel.rectb(bx_ - 1, by_ - 1, bw_ + 2, bh_ + 2, FRAME2)
        seg = (t.basura_t + 59) // 60
        big_ctext(x + w / 2, y + h - 22, "%d" % seg, HOT if cerca else LABEL, 2,
                  SHADOW)
        ctext(x + w / 2, y + h - 8, "seg", DIM)

        # el freno, si está puesto: copo y segundos
        if t.freno:
            x, y = CR + COL_W / 2, BASURA_BOX[1] + BASURA_BOX[3] + 12
            self._copo(int(x), y + 8, FREEZEC, 7)
            big_ctext(x, y + 20, "%d" % ((t.freno + 59) // 60), FREEZEC, 2, SHADOW)
            ctext(x, y + 36, "freno", FREEZEC)

    def _copo(self, cx, cy, c, r):
        pyxel.line(cx - r, cy, cx + r, cy, c)
        pyxel.line(cx, cy - r, cx, cy + r, c)
        d = int(r * 0.7)
        pyxel.line(cx - d, cy - d, cx + d, cy + d, c)
        pyxel.line(cx + d, cy - d, cx - d, cy + d, c)

    def _item(self, x, y, tipo, primero):
        """una ranura de ítem de 21x21: vacía, bomba o freno."""
        n = 21
        if tipo is None:
            pyxel.rectb(x, y, n, n, FRAME)
            return
        c = BOMBC if tipo == BOMBA else FREEZEC
        pyxel.rect(x, y, n, n, SHADOW)
        pyxel.rectb(x, y, n, n, c if primero else FRAME2)
        cx, cy = x + n // 2, y + n // 2
        if tipo == BOMBA:
            pyxel.circ(cx, cy + 2, 6, BOMB_D)
            pyxel.circ(cx - 1, cy + 1, 5, BOMBC)
            pyxel.rect(cx - 3, cy - 1, 2, 2, FLASHC)       # el brillo
            pyxel.rect(cx + 2, cy - 6, 3, 3, LABEL)        # la boquilla
            pyxel.line(cx + 4, cy - 6, cx + 6, cy - 8, LABEL)
            if (self.f // 6) % 2:
                pyxel.rect(cx + 6, cy - 9, 2, 2, HOT)
        else:
            self._copo(cx, cy, FREEZE_D, 7)
            self._copo(cx, cy, FREEZEC, 6)
            pyxel.rect(cx - 1, cy - 1, 3, 3, WHITE)


class Game:
    def __init__(self):
        Cabinet(
            game_id="bloques", title="BLOQUES",
            subtitle="100 segundos, el puntaje es todo",
            howto=["toca gira · arrastra mueve",
                   "desliza abajo cae · arriba guarda",
                   "líneas seguidas multiplican el puntaje",
                   "la pieza dorada paga doble y da un ítem",
                   "los últimos 20 s: fiebre, todo paga x2",
                   "teclado: flechas · espacio cae · c · z"],
            width=W, height=H, palette=PAL, scale=2,
            ui=UIColors(bg=BG, text=TXT, dim=LABEL, accent=ACCENT,
                        warn=C_Z, shadow=SHADOW, panel=EMPTY),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
