"""pruebas de bloques (tetris blitz), sin ventana:

    PYTHONPATH=. python -m games.bloques.test_bloques

la lógica vive en la clase Tetris, sin pyxel. lo que más importa acá: que el
blitz termine sí o sí — antes el tetris podía durar lo que aguantaras.
"""
import random

import pyxel

from games.bloques import game as G
from games.bloques.game import (B2B_FACTOR, BASURA_MIN, BOMBA, COLA, COLOR,
                                COLS, FIEBRE, FIEBRE_X, FRENO, FRENO_TTL,
                                ITEM_CADA, ITEMS_MAX, LOCK_DELAY, LOCK_RESETS,
                                LOCK_SOFT, ORO, ORO_CADA, ORO_X, PERFECTO_VALE,
                                ROWS, SCORE_LINES, SHAPES, TIME, Tetris,
                                rotate_cw)

FALLAS = []
DOS_MIN = 2 * 60 * 60


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def nueva(seed=42):
    return Tetris(rng=random.Random(seed))


def llenar(t, y, salvo=(0,)):
    """deja la fila `y` llena menos las columnas de `salvo`."""
    for x in range(COLS):
        t.board[y][x] = 0 if x in salvo else COLOR["O"]


# --- lo de siempre -----------------------------------------------------------
def test_rotacion():
    chk(rotate_cw(["XX", "XX"]) == ["XX", "XX"], "la O gira sobre sí misma")
    chk(rotate_cw([".X.", "XXX", "..."]) == ["...", "XX.", ".X."]
        or len(rotate_cw([".X.", "XXX", "..."])) == 3,
        "la T gira a una forma de 3 filas")


def test_inicio():
    t = nueva()
    chk(not t.over, "arranca viva")
    chk(t.time == TIME, "y con el blitz entero por delante")
    chk(t.pk in SHAPES and t.nxt in SHAPES, "hay pieza actual y próxima")
    chk(t.hold is None, "y nada guardado")


def test_mover_y_chocar_los_bordes():
    t = nueva()
    for _ in range(20):
        t.move(-1)
    chk(t.px >= 0, "no se sale por la izquierda")
    chk(not t.move(-1), "y avisa que ya no puede")
    for _ in range(20):
        t.move(1)
    chk(all(x < COLS for x, _ in t._cells(t.shape, t.px, t.py)),
        "ni por la derecha")


def test_la_linea_se_borra_y_paga():
    t = nueva()
    llenar(t, ROWS - 1, salvo=())
    n, filas, _ = t._clear_lines()
    chk(n == 1 and filas == [ROWS - 1], "la fila llena se borra")
    chk(not any(t.board[ROWS - 1]), "y queda vacía arriba")
    chk(t.lines == 1, "y suma a la cuenta de líneas")


def test_el_ghost_cae_hasta_el_fondo():
    t = nueva()
    t.py = 0
    gy = t.ghost_y()
    chk(gy > t.py, "la fantasma marca más abajo que la pieza")
    chk(t._collide(t.shape, t.px, gy + 1), "y justo antes de chocar")


def test_hard_drop_apoya_y_paga_la_caida():
    t = nueva()
    s0 = t.score
    t.hard_drop()
    chk(t.score > s0, "el hard drop premia decidirse rápido")
    chk(any(any(f) for f in t.board), "y la pieza queda apoyada en el tablero")


def test_perder_por_arriba():
    t = nueva()
    for y in range(ROWS):
        llenar(t, y, salvo=())
    t._spawn()
    chk(t.over, "si no entra la pieza nueva, se acabó")


# --- lo nuevo: combo, hold, ítems --------------------------------------------
def test_el_combo_multiplica():
    t = nueva()
    t.level = 1
    llenar(t, ROWS - 1, salvo=())
    ev = []
    t._lock(ev)
    l1 = [e for e in ev if e[0] == "lineas"][0]
    chk(t.combo == 1, "la primera línea arranca el combo")
    primera = l1[3]
    llenar(t, ROWS - 1, salvo=())
    ev = []
    t._lock(ev)
    l2 = [e for e in ev if e[0] == "lineas"][0]
    chk(t.combo == 2, "la segunda seguida lo sube")
    chk(l2[3] > primera, "y paga más (%d vs %d)" % (l2[3], primera))


def test_el_combo_se_corta():
    t = nueva()
    llenar(t, ROWS - 1, salvo=())
    t._lock([])
    chk(t.combo == 1, "hay combo")
    ev = []
    t._lock(ev)                              # una jugada sin línea
    chk(t.combo == 0, "una jugada sin línea corta el combo")
    chk(any(e[0] == "combo_roto" for e in ev), "y se avisa")


def test_el_combo_se_enfria_con_el_tiempo():
    t = nueva()
    llenar(t, ROWS - 1, salvo=())
    t._lock([])
    t.board = [[0] * COLS for _ in range(ROWS)]   # tablero limpio: que no pierda
    t.over = False
    t.combo_t = 2
    t.frame()
    t.frame()
    chk(t.combo == 0, "si tardas demasiado, el combo se enfría solo")


def test_el_hold_guarda_y_cambia():
    t = nueva()
    primera = t.pk
    chk(t.guardar(), "se puede guardar")
    chk(t.hold == primera, "la pieza queda en el hold")
    chk(t.pk != primera or t.nxt != primera, "y entra otra a jugar")
    chk(not t.guardar(), "pero no dos veces con la misma pieza")
    t.hard_drop()                            # pieza nueva: el hold se libera
    tercera = t.pk
    chk(t.guardar(), "con la pieza siguiente sí se puede de nuevo")
    chk(t.pk == primera, "y vuelve la que estaba guardada")
    chk(t.hold == tercera, "quedando guardada la que estaba en juego")


def test_los_items_se_ganan_cada_n_lineas():
    t = nueva()
    for i in range(ITEM_CADA):
        llenar(t, ROWS - 1, salvo=())
        t._lock([])
    chk(len(t.items) == 1, "cada %d líneas dan un ítem (hay %d)"
        % (ITEM_CADA, len(t.items)))
    for _ in range(ITEM_CADA * (ITEMS_MAX + 3)):
        llenar(t, ROWS - 1, salvo=())
        t._lock([])
    chk(len(t.items) == ITEMS_MAX, "pero no se acumulan más de %d" % ITEMS_MAX)


def test_la_bomba_vuela_las_de_abajo():
    t = nueva()
    llenar(t, ROWS - 1, salvo=(3,))
    llenar(t, ROWS - 2, salvo=(5,))
    t.items = [BOMBA]
    ev = []
    t.usar_item(ev)
    chk(not any(t.board[ROWS - 1]), "la bomba limpia la fila de abajo")
    chk(not any(t.board[ROWS - 2]), "y la de arriba también")
    chk(any(e[0] == "bomba" for e in ev), "y se avisa")
    chk(not t.items, "y se gastó")


def test_el_freno_apaga_la_gravedad():
    t = nueva()
    t.items = [FRENO]
    t.usar_item()
    chk(t.freno == FRENO_TTL, "el freno arranca con su cuerda")
    y0 = t.py
    for _ in range(t.fall_frames() * 3):
        t.frame()
    chk(t.py == y0, "mientras dura, la pieza no cae sola")
    t.freno = 0
    for _ in range(t.fall_frames() + 1):
        t.frame()
    chk(t.py > y0, "y cuando se acaba, vuelve a caer")


def test_la_basura_sube_con_un_hueco():
    t = nueva()
    t.board = [[0] * COLS for _ in range(ROWS)]
    ev = []
    t.subir_basura(ev)
    abajo = t.board[ROWS - 1]
    chk(sum(1 for c in abajo if c) == COLS - 1,
        "la fila que sube trae exactamente un hueco")
    chk(any(e[0] == "basura" for e in ev), "y se avisa")
    chk(t.basuras == 1, "y se cuenta")


def test_la_basura_empuja_lo_de_arriba():
    t = nueva()
    t.board = [[0] * COLS for _ in range(ROWS)]
    t.board[ROWS - 1][3] = COLOR["O"]          # una marca en el piso
    t.subir_basura([])
    chk(t.board[ROWS - 2][3] == COLOR["O"], "lo que había sube una fila")


def test_la_basura_te_puede_matar():
    t = nueva()
    for y in range(ROWS):
        llenar(t, y, salvo=(2,))
    ev = []
    t.subir_basura(ev)
    chk(t.over, "si la pila ya llega arriba, la basura te tapa")
    chk(any(e[0] == "tope" for e in ev), "y se avisa")


def test_la_basura_aprieta_con_el_nivel():
    t = nueva()
    t.level = 1
    lento = t.basura_gap()
    t.level = 8
    chk(t.basura_gap() < lento, "en nivel alto sube más seguido (%d vs %d)"
        % (t.basura_gap(), lento))
    t.level = 40
    chk(t.basura_gap() >= BASURA_MIN, "pero no más seguido que el piso")


def test_la_basura_no_estira_la_partida():
    """sube presión, no tiempo: el blitz sigue durando lo mismo."""
    t = nueva(seed=9)
    frames = 0
    while not t.over and frames < DOS_MIN + 600:
        t.basura_t = 1                          # basura sin parar, el peor caso
        t.frame()
        frames += 1
    chk(t.over, "con basura constante la partida se acaba (antes, no después)")
    chk(frames <= TIME + 2, "y nunca dura más que el reloj (%d de %d)"
        % (frames, TIME))


def test_sin_items_no_pasa_nada():
    t = nueva()
    t.items = []
    chk(t.usar_item() is None, "sin ítems, la tecla no hace nada")


# --- la cota de los dos minutos ----------------------------------------------
def test_el_blitz_cabe_en_dos_minutos():
    """el caso que rompía el tetris: alguien que juega perfecto.

    acá lo simulamos al extremo — cada vez que la pieza se apoya, le limpiamos
    el tablero entero. sin el reloj, este bucle no terminaría nunca.
    """
    t = nueva(seed=5)
    frames = 0
    while not t.over and frames < DOS_MIN + 600:
        if frames % 6 == 0:
            t.hard_drop()
            t.board = [[0] * COLS for _ in range(ROWS)]   # jugador infalible
        t.frame()
        frames += 1
    chk(t.over, "hasta el que no pierde nunca se queda sin tiempo")
    chk(t.time == 0, "y termina por reloj, no por otra cosa")
    chk(frames <= TIME + 2, "justo cuando suena (%d de %d)" % (frames, TIME))
    chk(frames <= DOS_MIN, "y cabe en dos minutos (%d frames)" % frames)

    torpe = nueva(seed=6)
    frames = 0
    while not torpe.over and frames < DOS_MIN + 600:
        torpe.frame()
        frames += 1
    chk(torpe.over, "y sin tocar nada también termina")
    chk(frames <= DOS_MIN, "a tiempo (%d frames)" % frames)


def test_el_freno_no_estira_la_partida():
    """el freno apaga la gravedad, no el reloj: no se puede usar para durar más."""
    t = nueva(seed=8)
    frames = 0
    while not t.over and frames < DOS_MIN + 600:
        t.items = [FRENO]                    # freno infinito, el peor caso
        t.usar_item()
        t.frame()
        frames += 1
    chk(t.over, "con el freno puesto siempre, la partida igual se acaba")
    chk(frames <= TIME + 2, "el reloj no se detiene (%d de %d)" % (frames, TIME))


def test_la_cola_muestra_tres():
    t = nueva()
    chk(len(t.cola) == COLA, "se ven %d próximas" % COLA)
    chk(t.nxt == t.cola[0], "y la 'próxima' es la primera de la cola")
    siguiente = t.cola[0]
    t.hard_drop()
    chk(t.pk == siguiente, "al apoyar entra la que estaba primera")
    chk(len(t.cola) == COLA, "y la cola se rellena")


def _tetris(t, resto=()):
    """cuatro filas llenas abajo y una I vertical que las cierra. `resto` son
    celdas (x, y) que quedan ocupadas además."""
    t.board = [[0] * COLS for _ in range(ROWS)]
    for y in range(ROWS - 4, ROWS):
        llenar(t, y, salvo=(0,))
    for x, y in resto:
        t.board[y][x] = COLOR["O"]
    t.shape = ["X...", "X...", "X...", "X..."]
    t.pk = "I"
    t.px, t.py = 0, ROWS - 4
    ev = []
    t._lock(ev)
    return ev


def test_los_tetris_seguidos_pagan_mas():
    t = nueva()
    t.combo_t = 0
    ev1 = _tetris(t)
    l1 = [e for e in ev1 if e[0] == "lineas"][0]
    chk(l1[1] == 4, "la I cierra cuatro (%d)" % l1[1])
    chk(not any(e[0] == "b2b" for e in ev1), "el primer tetris paga lo normal")
    chk(t.b2b, "y deja la puerta abierta para el siguiente")
    t.combo = 0
    ev2 = _tetris(t)
    l2 = [e for e in ev2 if e[0] == "lineas"][0]
    chk(any(e[0] == "b2b" for e in ev2), "el segundo seguido se avisa")
    chk(l2[3] == int(l1[3] * B2B_FACTOR), "y paga x%.1f (%d vs %d)"
        % (B2B_FACTOR, l2[3], l1[3]))
    # una línea simple en el medio corta la cadena
    t.board = [[0] * COLS for _ in range(ROWS)]
    llenar(t, ROWS - 1, salvo=())
    t.shape, t.pk, t.px, t.py = SHAPES["O"], "O", 0, 0
    t._lock([])
    chk(not t.b2b, "una línea simple corta el seguido")


def test_el_tablero_limpio_paga_bono():
    t = nueva()
    t.lines = 10                          # el nivel sale de las líneas: 14 → 2
    s0 = t.score
    ev = _tetris(t)                       # deja el tablero vacío
    chk(t.level == 2, "(nivel 2)")
    chk(not any(any(f) for f in t.board), "(el tablero quedó vacío)")
    chk(any(e[0] == "perfecto" for e in ev), "vaciarlo se avisa")
    bono = [e for e in ev if e[0] == "perfecto"][0][1]
    chk(bono == PERFECTO_VALE * 2, "y paga %d por nivel (%d)" % (PERFECTO_VALE, bono))
    lineas = [e for e in ev if e[0] == "lineas"][0][3]
    chk(t.score == s0 + lineas + bono, "sumado a las líneas")
    chk(t.perfectos == 1, "y se cuenta")
    # con algo que queda arriba no hay bono
    t2 = nueva()
    ev = _tetris(t2, resto=((3, 0),))
    chk(not any(e[0] == "perfecto" for e in ev),
        "si queda un bloque, no es perfecto")


def test_el_puntaje_crece_con_el_nivel():
    t = nueva()
    t.level = 1
    llenar(t, ROWS - 1, salvo=())
    ev = []
    t._lock(ev)
    base = [e for e in ev if e[0] == "lineas"][0][3]
    t2 = nueva()
    t2.lines = 39                # el nivel sale de las líneas: con 40 va a 5
    t2.combo = 0
    llenar(t2, ROWS - 1, salvo=())
    ev = []
    t2._lock(ev)
    chk(t2.level == 5, "40 líneas son nivel 5 (dio %d)" % t2.level)
    alto = [e for e in ev if e[0] == "lineas"][0][3]
    chk(alto > base, "la misma línea paga más en nivel alto (%d vs %d)"
        % (alto, base))
    chk(base == SCORE_LINES[1] * 1 * 1, "y la tabla de siempre sigue mandando")


# --- lo nuevo: fiebre, oro, lock delay, gestos --------------------------------
def test_la_fiebre_paga_doble_al_final():
    t = nueva()
    llenar(t, ROWS - 1, salvo=())
    ev = []
    t._lock(ev)
    normal = [e for e in ev if e[0] == "lineas"][0][3]
    t2 = nueva()
    t2.time = FIEBRE - 10
    chk(t2.fiebre(), "en los últimos %d s hay fiebre" % (FIEBRE // 60))
    llenar(t2, ROWS - 1, salvo=())
    ev = []
    t2._lock(ev)
    caliente = [e for e in ev if e[0] == "lineas"][0][3]
    chk(caliente == normal * FIEBRE_X, "y la misma línea paga x%d (%d vs %d)"
        % (FIEBRE_X, caliente, normal))
    t3 = nueva()
    t3.time = FIEBRE + 3
    avisos = []
    for _ in range(10):
        avisos += [e for e in t3.frame() if e[0] == "fiebre"]
    chk(len(avisos) == 1, "la fiebre se anuncia una sola vez (%d)" % len(avisos))
    chk(not nueva().fiebre(), "y al principio no hay")


def test_la_pieza_dorada_llega_y_paga():
    t = nueva()
    vistas = 0
    for _ in range(ORO_CADA * 3):
        vistas += t.oro
        t.board = [[0] * COLS for _ in range(ROWS)]
        t.hard_drop()
    chk(vistas == 3, "una de cada %d piezas es dorada (vi %d en %d)"
        % (ORO_CADA, vistas, ORO_CADA * 3))
    chk(len(t.cola_oro) == len(t.cola), "y la cola sabe cuáles vienen doradas")
    # una línea que se lleva oro paga doble y regala un ítem
    t = nueva()
    llenar(t, ROWS - 1, salvo=())
    ev = []
    t._lock(ev)
    normal = [e for e in ev if e[0] == "lineas"][0][3]
    t = nueva()
    llenar(t, ROWS - 1, salvo=())
    t.board[ROWS - 1][4] = ORO
    t.items = []
    ev = []
    t._lock(ev)
    dorada = [e for e in ev if e[0] == "lineas"][0][3]
    chk(dorada == normal * ORO_X, "la línea con oro paga x%d (%d vs %d)"
        % (ORO_X, dorada, normal))
    chk(len(t.items) == 1, "y regala un ítem")
    chk(any(e[0] == "oro" for e in ev), "y se avisa")


def test_el_oro_se_guarda_con_la_pieza():
    t = nueva()
    t.oro = True
    pieza = t.pk
    t.guardar()
    chk(t.hold == pieza and t.hold_oro, "guardar una dorada la guarda dorada")
    t.hard_drop()
    t.guardar()
    chk(t.pk == pieza and t.oro, "y vuelve dorada")


def test_el_lock_delay_da_un_respiro():
    t = nueva()
    t.py = t.ghost_y()                      # apoyada en el piso
    for _ in range(LOCK_DELAY - 2):
        t.frame()
    chk(t.py == t.ghost_y() and t.lock_t > 0,
        "apoyada no se fija enseguida (espera %d frames)" % LOCK_DELAY)

    t.move(1) or t.move(-1)
    chk(t.lock_t == 0, "moverla le da otro respiro")
    for _ in range(LOCK_DELAY + 1):
        t.frame()
    chk(any(any(f) for f in t.board), "pero al final se fija")
    # el respiro tiene techo: no se puede girar en el piso para siempre
    t = nueva()
    t.py = t.ghost_y()
    frames = 0
    while not any(any(f) for f in t.board) and frames < 2000:
        t.frame()
        t.move(1) or t.move(-1)
        frames += 1
    chk(frames <= (LOCK_RESETS + 2) * LOCK_DELAY,
        "con techo de %d respiros (se fijó a los %d frames)" % (LOCK_RESETS, frames))
    # bajándola a mano se fija más rápido
    t = nueva()
    t.py = t.ghost_y()
    for _ in range(LOCK_SOFT + 1):
        t.frame(soft=True)
    chk(any(any(f) for f in t.board), "bajando a mano se fija en %d frames" % LOCK_SOFT)


def test_bajar_a_mano():
    t = nueva()
    y0, s0 = t.py, t.score
    chk(t.bajar(), "se puede bajar una fila con el dedo")
    chk(t.py == y0 + 1 and t.score == s0 + 1, "y paga un punto")
    t.py = t.ghost_y()
    chk(not t.bajar(), "pero no atraviesa el piso")


def test_el_que_estira_el_lock_no_estira_la_partida():
    """el peor caso del lock delay: alguien que mueve la pieza apoyada cada
    frame. el techo de respiros la fija igual, y el reloj corre siempre."""
    t = nueva(seed=11)
    frames = 0
    while not t.over and frames < DOS_MIN + 600:
        t.move(1) or t.move(-1)
        t.rotate()
        t.frame()
        frames += 1
    chk(t.over, "girando sin parar, la partida igual se acaba")
    chk(frames <= TIME + 2, "a tiempo (%d de %d)" % (frames, TIME))


class _Dedo:
    """el mouse de pyxel, falso: para probar los gestos sin ventana."""

    def __init__(self):
        self.x = self.y = 0
        self.down = self.was = False

    def instalar(self):
        self._orig = (pyxel.btn, pyxel.btnp)
        pyxel.btn = lambda k, *a, **kw: self.down if k == pyxel.MOUSE_BUTTON_LEFT else False
        pyxel.btnp = lambda k, *a, **kw: (self.down and not self.was) \
            if k == pyxel.MOUSE_BUTTON_LEFT else False

    def quitar(self):
        pyxel.btn, pyxel.btnp = self._orig

    def frame(self, w, x, y, down):
        self.x, self.y, self.down = x, y, down
        pyxel.mouse_x, pyxel.mouse_y = x, y
        w.update()
        self.was = down


def test_los_gestos_del_dedo():
    dedo = _Dedo()
    dedo.instalar()
    try:
        w = G.World()
        w.t = nueva(seed=3)
        t = w.t
        x0 = t.px
        dedo.frame(w, 50, 60, True)
        for k in range(1, 6):
            dedo.frame(w, 50 + k * 5, 60, True)       # arrastra 25 px a la derecha
        dedo.frame(w, 75, 60, False)
        chk(t.px == x0 + 25 // G.PASO_X, "arrastrar mueve una columna cada %d px "
            "(se movió %d)" % (G.PASO_X, t.px - x0))
        forma = t.shape
        dedo.frame(w, 40, 80, True)
        dedo.frame(w, 41, 80, True)
        dedo.frame(w, 41, 80, False)
        chk(t.shape != forma or t.pk == "O", "un toque corto gira la pieza")
        puestas = sum(1 for f in t.board for c in f if c)
        dedo.frame(w, 40, 40, True)
        for k in range(1, 5):
            dedo.frame(w, 40, 40 + k * 7, True)       # desliza rápido hacia abajo
        dedo.frame(w, 40, 68, False)
        chk(sum(1 for f in t.board for c in f if c) == puestas + 4,
            "deslizar rápido hacia abajo la deja caer")
        actual = t.pk
        dedo.frame(w, 40, 120, True)
        for k in range(1, 5):
            dedo.frame(w, 40, 120 - k * 7, True)      # y hacia arriba la guarda
        dedo.frame(w, 40, 92, False)
        chk(t.hold == actual, "deslizar rápido hacia arriba la guarda")
        t.items = [G.FRENO]
        x, y, ww, hh = G.ITEM_BOX
        dedo.frame(w, x + 5, y + 5, True)
        dedo.frame(w, x + 5, y + 5, False)
        chk(t.freno > 0 and not t.items, "tocar el cuadro de ítem lo usa")
        forma = t.shape
        dedo.frame(w, 40, 60, True)
        for k in range(1, 4):
            dedo.frame(w, 40, 60 + k * 3, True)       # arrastre lento hacia abajo
        dedo.frame(w, 40, 69, False)
        chk(t.shape == forma, "un arrastre no se confunde con un toque")
    finally:
        dedo.quitar()


if __name__ == "__main__":
    for fn in (test_rotacion, test_inicio, test_mover_y_chocar_los_bordes,
               test_la_linea_se_borra_y_paga, test_el_ghost_cae_hasta_el_fondo,
               test_hard_drop_apoya_y_paga_la_caida, test_perder_por_arriba,
               test_el_combo_multiplica, test_el_combo_se_corta,
               test_el_combo_se_enfria_con_el_tiempo,
               test_el_hold_guarda_y_cambia,
               test_los_items_se_ganan_cada_n_lineas,
               test_la_bomba_vuela_las_de_abajo,
               test_el_freno_apaga_la_gravedad,
               test_la_basura_sube_con_un_hueco,
               test_la_basura_empuja_lo_de_arriba,
               test_la_basura_te_puede_matar,
               test_la_basura_aprieta_con_el_nivel,
               test_la_basura_no_estira_la_partida,
               test_sin_items_no_pasa_nada,
               test_el_blitz_cabe_en_dos_minutos,
               test_el_freno_no_estira_la_partida,
               test_la_cola_muestra_tres, test_los_tetris_seguidos_pagan_mas,
               test_el_tablero_limpio_paga_bono,
               test_el_puntaje_crece_con_el_nivel,
               test_la_fiebre_paga_doble_al_final,
               test_la_pieza_dorada_llega_y_paga,
               test_el_oro_se_guarda_con_la_pieza,
               test_el_lock_delay_da_un_respiro, test_bajar_a_mano,
               test_el_que_estira_el_lock_no_estira_la_partida,
               test_los_gestos_del_dedo):
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
