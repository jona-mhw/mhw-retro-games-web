"""bloques — tetris blitz: 100 segundos para hacer el mayor puntaje posible.

el tetris de siempre no se acaba nunca: si sos bueno, la partida dura lo que
aguantes. acá el reloj manda — son 100 segundos y el puntaje es todo. eso cambia
cómo se juega: ya no conviene sobrevivir, conviene arriesgar.

lo que le sumamos al tetris clásico:

- **combo**: líneas en jugadas seguidas multiplican. cortar la cadena duele.
- **hold**: guardás una pieza para después (una vez por pieza), como en los
  tetris modernos. es lo que hace que una I no se desperdicie.
- **ítems**, que se ganan cada 4 líneas y se guardan hasta 3: la **bomba**
  vuela las dos filas de abajo y el **freno** apaga la gravedad 4 segundos.
  son la salida cuando la pila te ganó.
- las líneas **estallan** en vez de desaparecer, y el hard drop **sacude**.
- **tres próximas a la vista**, no una: se puede planear la I y el hold deja
  de ser adivinanza.
- **tetris seguidos** (back-to-back) pagan una vez y media. y un **tablero
  limpio** después de una línea — el perfect clear — paga un bono grande. es la
  jugada de riesgo del blitz: vaciar todo en vez de sólo bajar la pila.

la lógica (piezas, rotación, colisión, líneas, reloj) vive en la clase Tetris,
sin pyxel: `frame()` avanza un frame y devuelve qué pasó.
"""
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

COLS, ROWS = 10, 20
CELL = 10
BX, BY = 8, 10
W, H = 220, 220

TIME = 100 * 60                  # el blitz entero: nada lo estira
ITEM_CADA = 4                    # líneas por ítem
ITEMS_MAX = 3
FRENO_TTL = 4 * 60
COMBO_TTL = 3 * 60               # lo que tenés para encadenar la próxima línea
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

BOMBA, FRENO = range(2)
ITEM_NOMBRE = {BOMBA: "¡BOMBA!", FRENO: "¡FRENO!"}

(BG, EMPTY, FRAME, TXT, DIM, ACCENT, C_I, C_O, C_T, C_S, C_Z, C_J, C_L,
 BEVEL, SHADOW, GHOST,
 GOLD, MAGENTA, FLASHC, BOMBC, FREEZEC, HOLDC, WHITE, HOT,
 GARBAGE, GARBAGE2) = range(26)
PAL = [
    0x0C0E14, 0x161C2A, 0x2A3350, 0xE8ECF5, 0x5A6480, 0x8AC52F, 0x3AC6D8,
    0xE7C13B, 0xA85FD0, 0x5FB84A, 0xD8483A, 0x4A78D8, 0xE0842E, 0xD8E0EE,
    0x070810, 0x39435E,
    0xFFD24A, 0xD84AB8, 0xFFF3B0, 0xFF8A3A, 0x7ADCFF, 0x9BB0D8, 0xF2F5FB,
    0xFF5A3A, 0x5A6480, 0x39435E,
] + [0] * (256 - 26)

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
        self.basura_t = BASURA_GAP
        self.basuras = 0
        self.hold = None
        self.hold_usado = False
        self.b2b = False             # ¿la última línea fue un tetris?
        self.perfectos = 0
        self.cola = [self._from_bag() for _ in range(COLA)]
        self._spawn()

    @property
    def nxt(self):
        """la próxima de la cola, para el panel y el que la mira de a una."""
        return self.cola[0]

    # --- piezas ----------------------------------------------------------
    def _from_bag(self):
        if not self.bag:
            self.bag = list(SHAPES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def _spawn(self, pieza=None):
        if pieza is None:
            self.pk = self.cola.pop(0)
            self.cola.append(self._from_bag())
        else:
            self.pk = pieza
        self.shape = SHAPES[self.pk]
        self.px = (self.cols - len(self.shape)) // 2
        self.py = 0
        self.hold_usado = False
        if self._collide(self.shape, self.px, self.py):
            self.over = True

    def guardar(self):
        """el hold: cambia la pieza actual por la guardada. una vez por pieza."""
        if self.over or self.hold_usado:
            return False
        actual = self.pk
        if self.hold is None:
            self.hold = actual
            self._spawn()
        else:
            guardada, self.hold = self.hold, actual
            self._spawn(guardada)
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

    def move(self, dx):
        if not self.over and not self._collide(self.shape, self.px + dx, self.py):
            self.px += dx
            return True
        return False

    def rotate(self):
        if self.over:
            return False
        r = rotate_cw(self.shape)
        for kick in (0, -1, 1, -2, 2):
            if not self._collide(r, self.px + kick, self.py):
                self.shape, self.px = r, self.px + kick
                return True
        return False

    def ghost_y(self):
        y = self.py
        while not self._collide(self.shape, self.px, y + 1):
            y += 1
        return y

    # --- ítems -----------------------------------------------------------
    def _dar_item(self, ev):
        while self.item_deuda >= ITEM_CADA:
            self.item_deuda -= ITEM_CADA
            if len(self.items) < ITEMS_MAX:
                self.items.append(self.rng.randrange(2))
                ev.append(("item_gana", self.items[-1]))

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
        caida = self.ghost_y() - self.py
        self.py = self.ghost_y()
        self.score += caida * 2                  # premia decidirse rápido
        ev.append(("drop", caida))
        self._lock(ev)
        return ev

    def _lock(self, ev):
        col = COLOR[self.pk]
        for x, y in self._cells(self.shape, self.px, self.py):
            if 0 <= y < self.rows and 0 <= x < self.cols:
                self.board[y][x] = col
        n, filas = self._clear_lines()
        if n:
            self.combo += 1
            self.combo_t = COMBO_TTL
            ganado = SCORE_LINES[n] * self.level * min(COMBO_MAX, self.combo)
            if n == 4 and self.b2b:                  # tetris atrás de tetris
                ganado = int(ganado * B2B_FACTOR)
                ev.append(("b2b", ganado))
            self.b2b = n == 4
            self.score += ganado
            self.item_deuda += n
            ev.append(("lineas", n, filas, ganado, self.combo))
            if not any(any(fila) for fila in self.board):
                bono = PERFECTO_VALE * self.level
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

    def _clear_lines(self):
        full = [y for y in range(self.rows) if all(self.board[y])]
        for y in full:
            del self.board[y]
            self.board.insert(0, [0] * self.cols)
        if full:
            self.lines += len(full)
            self.level = min(NIVEL_MAX, 1 + self.lines // 10)
        return len(full), full

    def basura_gap(self):
        """el intervalo se acorta con el nivel: la presión sube sola."""
        return max(BASURA_MIN, BASURA_GAP - (self.level - 1) * 45)

    def subir_basura(self, ev):
        """sube una fila desde abajo, con un hueco. la pieza en juego sube con
        ella para que no quede enterrada.

        es lo que cambia el blitz de "acomodá tranquilo" a "sacate esto de
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
        else:
            self.fall += 1
            if self.fall >= (3 if soft else self.fall_frames()):
                self.fall = 0
                if self.tick():
                    self._lock(ev)
        self.basura_t -= 1
        if self.basura_t <= 0:
            self.basura_t = self.basura_gap()
            self.subir_basura(ev)
        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("tiempo",))
        return ev


class World:
    """el tetris jugándose: input, dibujo y chispas. el Cabinet lo envuelve."""

    def __init__(self):
        self.t = Tetris()
        self.fx = fx.Fx(gravity=0.18)
        self.lvl = 1
        self.levelflash = 0
        self.fx.destello(WHITE)
        self.filas_flash = []        # [fila, frames] para que estallen

    @property
    def over(self):
        return self.t.over

    @property
    def score(self):
        return self.t.score

    def update(self):
        t = self.t
        if pyxel.btnp(pyxel.KEY_LEFT, 12, 2) or pyxel.btnp(pyxel.KEY_A, 12, 2):
            t.move(-1)
        if pyxel.btnp(pyxel.KEY_RIGHT, 12, 2) or pyxel.btnp(pyxel.KEY_D, 12, 2):
            t.move(1)
        if pyxel.btnp(pyxel.KEY_UP, 14, 6) or pyxel.btnp(pyxel.KEY_X) \
                or pyxel.btnp(pyxel.KEY_W):
            t.rotate()
        if pyxel.btnp(pyxel.KEY_C) or pyxel.btnp(pyxel.KEY_LSHIFT):
            t.guardar()
        ev = []
        if pyxel.btnp(pyxel.KEY_Z):
            t.usar_item(ev)
        if pyxel.btnp(pyxel.KEY_SPACE):
            t.hard_drop(ev)
            t.fall = 0
            ev += t.frame(soft=False)
        else:
            soft = pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S)
            ev += t.frame(soft=soft)
        for e in ev:
            self._efecto(e)
        if t.level != self.lvl:
            self.lvl = t.level
            self.levelflash = 24
        self.levelflash = max(0, self.levelflash - 1)
        self.filas_flash = [[f, n - 1] for f, n in self.filas_flash if n > 1]
        self.fx.update()

    def _px(self, cx, cy):
        return BX + cx * CELL + CELL / 2, BY + cy * CELL + CELL / 2

    def _efecto(self, e):
        kind = e[0]
        if kind == "lineas":
            _, n, filas, ganado, combo = e
            for f in filas:
                self.filas_flash.append([f, 10])
                for cx in range(COLS):
                    x, y = self._px(cx, f)
                    self.fx.burst(x, y, (WHITE, FLASHC, GOLD, HOT), n=3,
                                  speed=1.6, life=20)
            etiqueta = ("", "", "DOBLE", "TRIPLE", "¡TETRIS!")[n]
            if combo > 1:
                etiqueta = (etiqueta + " x%d" % combo).strip()
            if etiqueta:
                self.fx.popup(BX + COLS * CELL / 2, BY + filas[0] * CELL - 6,
                              etiqueta, GOLD)
            self.fx.popup(BX + COLS * CELL / 2, BY + filas[0] * CELL + 6,
                          "+%d" % ganado, WHITE)
            self.fx.shake(2 + n)
            self.fx.destello(FLASHC if n < 4 else GOLD)
        elif kind == "b2b":
            self.fx.popup(BX + COLS * CELL / 2, BY + 30, "¡SEGUIDO x1.5!", HOT)
        elif kind == "perfecto":
            for cy in range(0, ROWS, 2):
                for cx in range(0, COLS, 3):
                    x, y = self._px(cx, cy)
                    self.fx.burst(x, y, (WHITE, GOLD, FLASHC, C_I), n=2,
                                  speed=1.4, life=30)
            self.fx.popup(BX + COLS * CELL / 2, BY + ROWS * CELL / 2 - 8,
                          "¡PERFECTO!", GOLD, life=60)
            self.fx.popup(BX + COLS * CELL / 2, BY + ROWS * CELL / 2 + 6,
                          "+%d" % e[1], WHITE, life=60)
            self.fx.shake(6)
            self.fx.destello(GOLD)
        elif kind == "drop":
            if e[1] > 2:
                self.fx.shake(2)
        elif kind == "bomba":
            for f in range(ROWS - e[1], ROWS):
                self.filas_flash.append([f, 12])
                for cx in range(COLS):
                    x, y = self._px(cx, f)
                    self.fx.burst(x, y, (WHITE, BOMBC, HOT, C_Z), n=4, speed=2.2,
                                  life=24)
            self.fx.popup(BX + COLS * CELL / 2, BY + (ROWS - 3) * CELL,
                          ITEM_NOMBRE[BOMBA], BOMBC)
            self.fx.shake(6)
            self.fx.destello(BOMBC)
        elif kind == "freno":
            self.fx.popup(BX + COLS * CELL / 2, BY + ROWS * CELL / 2,
                          ITEM_NOMBRE[FRENO], FREEZEC)
            self.fx.destello(FREEZEC)
        elif kind == "item_gana":
            self.fx.popup(BX + COLS * CELL + 26, 150, "+ítem", ACCENT)
        elif kind == "basura":
            self.fx.popup(BX + COLS * CELL / 2, BY + (ROWS - 4) * CELL,
                          "¡SUBE!", GARBAGE)
            self.fx.shake(4)
            self.fx.destello(GARBAGE)
        elif kind == "tope":
            self.fx.shake(8)
            self.fx.destello(C_Z)

    # --- dibujo ----------------------------------------------------------
    def _block(self, px, py, col, size=CELL):
        pyxel.rect(px, py, size, size, col)
        pyxel.rect(px, py, size, 1, BEVEL)
        pyxel.rect(px, py, 1, size, BEVEL)
        pyxel.rect(px, py + size - 1, size, 1, SHADOW)
        pyxel.rect(px + size - 1, py, 1, size, SHADOW)

    def draw(self):
        t = self.t
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        pyxel.rectb(BX - 1, BY - 1, COLS * CELL + 2, ROWS * CELL + 2,
                    FREEZEC if t.freno else FRAME)
        flash = {f for f, _ in self.filas_flash}
        for y in range(ROWS):
            for x in range(COLS):
                px, py = BX + x * CELL, BY + y * CELL
                if y in flash:
                    pyxel.rect(px, py, CELL, CELL, FLASHC)
                    continue
                v = t.board[y][x]
                if v:
                    self._block(px, py, v)
                else:
                    pyxel.rect(px, py, CELL, CELL, EMPTY if (x + y) & 1 else BG)
        if not t.over:
            gy = t.ghost_y()
            for x, y in t._cells(t.shape, t.px, gy):
                pyxel.rectb(BX + x * CELL, BY + y * CELL, CELL, CELL, GHOST)
            for x, y in t._cells(t.shape, t.px, t.py):
                if y >= 0:
                    self._block(BX + x * CELL, BY + y * CELL, COLOR[t.pk])
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(BX - 1, BY - 1, COLS * CELL + 2, ROWS * CELL + 2)
        self._panel()

    def _mini(self, pieza, ox, oy, col, s=7):
        for cy, row in enumerate(SHAPES[pieza]):
            for cx, ch in enumerate(row):
                if ch == "X":
                    self._block(ox + cx * s, oy + cy * s, col, s)

    def _panel(self):
        t = self.t
        px = BX + COLS * CELL + 8
        s = t.time // 60
        # el reloj manda: va arriba de todo y se pone rojo en los últimos 10 s
        col = C_Z if s <= 10 and pyxel.frame_count % 30 < 15 else TXT
        text(px, 6, "%ds" % s, col)
        fx.bar(px + 26, 7, 56, 5, t.time / TIME, ACCENT if s > 10 else C_Z,
               EMPTY, FRAME)
        text(px, 20, "%d" % t.score, ACCENT)
        if t.combo > 1:
            text(px + 52, 20, "x%d" % t.combo, GOLD)
        text(px, 32, "nv %d" % t.level, BEVEL if self.levelflash else DIM)
        text(px + 40, 32, "%d líneas" % t.lines, DIM)

        text(px, 44, "PRÓXIMAS", ACCENT)
        self._mini(t.cola[0], px + 4, 54, COLOR[t.cola[0]])
        for k, pk in enumerate(t.cola[1:]):          # las que siguen, más chicas
            self._mini(pk, px + 4 + k * 24, 78, COLOR[pk], s=5)
        text(px, 100, "GUARDADA", ACCENT)
        if t.hold:
            self._mini(t.hold, px + 4, 110, COLOR[t.hold] if not t.hold_usado
                       else HOLDC, s=6)
        else:
            text(px + 4, 112, "c", DIM)
        if t.b2b:
            text(px + 44, 110, "b2b", HOT if (pyxel.frame_count // 8) % 2 else DIM)

        text(px, 140, "ÍTEMS", ACCENT)
        for i in range(ITEMS_MAX):
            bx_, by_ = px + 4 + i * 14, 150
            if i < len(t.items):
                tipo = t.items[i]
                c = BOMBC if tipo == BOMBA else FREEZEC
                pyxel.rectb(bx_, by_, 11, 11, c)
                if tipo == BOMBA:
                    pyxel.circ(bx_ + 5, by_ + 6, 3, c)
                    pyxel.pset(bx_ + 7, by_ + 2, HOT)
                else:
                    pyxel.rect(bx_ + 2, by_ + 5, 7, 2, c)
                    pyxel.rect(bx_ + 5, by_ + 2, 1, 7, c)
            else:
                pyxel.rectb(bx_, by_, 11, 11, EMPTY)
        text(px, H - 46, "espacio cae", DIM)
        text(px, H - 36, "c guarda", DIM)
        text(px, H - 26, "z usa ítem", DIM)


class Game:
    def __init__(self):
        Cabinet(
            game_id="bloques", title="BLOQUES",
            subtitle="100 segundos, el puntaje es todo",
            howto=["flechas mueven · arriba gira · espacio cae",
                   "c guarda una pieza · z usa un ítem",
                   "líneas seguidas multiplican · tetris seguidos, más",
                   "vaciar el tablero paga un bono"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=C_Z, shadow=SHADOW, panel=EMPTY),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
