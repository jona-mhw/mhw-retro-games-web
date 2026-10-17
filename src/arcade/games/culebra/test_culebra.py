"""pruebas de la culebra, sin ventana: PYTHONPATH=. python -m games.culebra.test_culebra

toda la lógica vive en la clase Culebra, así que se testea directo — incluido
lo que no se puede comprobar jugando: que ninguna partida pase de dos minutos.
"""
import random

from games.culebra.game import (AJI_TTL, AJI_TURBO, AJI_VALE, ARANA_DESDE,
                                ARANA_NACE, ARANA_VALE, BAYAS, COLA_GIROS,
                                COMIDAS_NIVEL, Culebra, DORADA_TTL,
                                DORADA_VALE, EXTRA_MAX, FRENESI_X, HAMBRE,
                                MANZANA_AIRE, MUROS_DESDE, PORTALES_DESDE,
                                RACHA_CADA, RACHA_MAX, RATON_CRECE,
                                RATON_DESDE, RATON_TTL, RATON_VALE, TIJERA)

FALLAS = []
DOS_MIN = 2 * 60 * 60


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def nueva(cols=12, rows=12, seed=1234):
    return Culebra(cols=cols, rows=rows, rng=random.Random(seed))


# --- lo de siempre -----------------------------------------------------------
def test_inicio():
    g = nueva()
    chk(len(g.body) == 3, "arranca con 3 de largo")
    chk(g.dir == (1, 0), "arranca yendo a la derecha")
    chk(g.score == 0 and not g.dead, "arranca sin puntaje y viva")
    chk(g.apple not in g.body, "la manzana no nace sobre la culebra")
    chk(g.hambre == HAMBRE, "y con el estómago lleno")


def test_mueve():
    g = nueva()
    g.apple = (0, 0)
    hx, hy = g.body[0]
    g.step()
    chk(g.body[0] == (hx + 1, hy), "la cabeza avanza a la derecha")
    chk(len(g.body) == 3, "sin comer, el largo se mantiene")


def test_no_reversa():
    g = nueva()
    g.set_dir((-1, 0))
    chk(g.pending == (1, 0), "no acepta la reversa directa")
    g.set_dir((0, 1))
    chk(g.pending == (0, 1), "sí acepta doblar")


def test_come():
    g = nueva()
    hx, hy = g.body[0]
    g.apple = (hx + 1, hy)
    ev = g.step()
    chk(ev == 'eat', "detecta que comió")
    chk(g.score == 1, "suma un punto")
    chk(len(g.body) == 4, "crece uno al comer")
    chk(g.apple != (hx + 1, hy), "reubica la manzana")


def test_muere_pared():
    g = nueva()
    g.apple = (0, 0)
    for _ in range(20):
        if g.step() == 'dead':
            break
    chk(g.dead, "muere al chocar la pared")


def test_muere_mordida():
    g = nueva()
    g.body = [(5, 5), (5, 6), (5, 7), (6, 7), (6, 6), (6, 5), (6, 4)]
    g.dir = g.pending = (1, 0)
    g.apple = (0, 0)
    chk(g.step() == 'dead', "muere al morderse")


def test_acelera():
    g = nueva()
    s0 = g.speed()
    g.comidas = 40
    chk(g.speed() < s0, "acelera con el puntaje")
    chk(g.speed() >= 3, "pero no más rápido que el tope")


# --- el hambre, que es el reloj de la partida --------------------------------
def test_el_hambre_baja_y_mata():
    g = nueva()
    g.hambre = 3
    for _ in range(4):
        g.frame()
    chk(g.dead, "sin comer, el hambre te mata")


def test_comer_da_aire_pero_del_presupuesto():
    g = nueva()
    g.hambre = HAMBRE // 2
    g.extra = MANZANA_AIRE + 10          # queda poco en el presupuesto
    hx, hy = g.body[0]
    g.apple = (hx + 1, hy)
    g.step()
    chk(g.hambre > HAMBRE // 2, "la manzana te devuelve aire")
    chk(g.extra == 10, "y ese aire sale del presupuesto")
    g.hambre = 100
    g.apple = g.body[0][0] + 1, g.body[0][1]
    g.step()
    chk(g.extra == 0, "cuando el presupuesto se agota, no da más")
    chk(g.hambre <= 110, "y la manzana ya casi no alimenta")


def test_el_hambre_no_se_pasa_del_tope():
    g = nueva()
    g.hambre = HAMBRE - 10
    hx, hy = g.body[0]
    g.apple = (hx + 1, hy)
    g.step()
    chk(g.hambre == HAMBRE, "el hambre se llena, no se desborda")


# --- dorada, poderes y muros --------------------------------------------------
def test_la_dorada_aparece_y_se_va():
    g = nueva(cols=20, rows=20)
    g.gold_t = 1
    g.frame()
    chk(g.gold is not None, "la dorada asoma cuando le toca")
    g.gold[2] = 1
    ev = g.frame()
    chk(g.gold is None, "y se va sola si no la agarras")
    chk(any(e[0] == "dorada_ida" for e in ev), "avisando que se fue")


def test_la_dorada_vale_por_cinco():
    g = nueva(cols=20, rows=20)
    g.t = g.speed() - 1                      # el próximo frame mueve
    hx, hy = g.body[0]
    g.apple = (0, 0)
    g.gold = [hx + 1, hy, DORADA_TTL]
    ev = g.frame()
    chk(g.score == DORADA_VALE, "la dorada vale %d (dio %d)"
        % (DORADA_VALE, g.score))
    chk(any(e[0] == "dorada" for e in ev), "y se avisa")
    chk(g.gold is None, "y desaparece del tablero")


def test_el_fantasma_te_deja_atravesarte():
    g = nueva()
    g.body = [(5, 5), (5, 6), (5, 7), (6, 7), (6, 6), (6, 5), (6, 4)]
    g.dir = g.pending = (1, 0)
    g.apple = (0, 0)
    g.ghost = 100
    chk(g.step() != 'dead', "con el fantasma puedes atravesar tu propio cuerpo")
    g2 = nueva()
    g2.ghost = 100
    g2.apple = (0, 0)
    for _ in range(20):
        if g2.step() == 'dead':
            break
    chk(g2.dead, "pero la pared te sigue matando igual")


def test_la_tijera_corta_la_cola():
    g = nueva()
    g.body = [(x, 5) for x in range(10, 0, -1)]
    largo = len(g.body)
    g._tomar_poder(TIJERA, [])
    chk(len(g.body) < largo, "la tijera te corta la cola (%d -> %d)"
        % (largo, len(g.body)))
    chk(len(g.body) >= 3, "pero nunca te deja más corta que el mínimo")


def test_los_muros_matan_y_llegan_con_el_nivel():
    g = nueva()
    hx, hy = g.body[0]
    g.walls.add((hx + 1, hy))
    g.apple = (0, 0)
    chk(g.step() == 'dead', "chocar un muro te mata")
    g2 = nueva(cols=20, rows=20)
    chk(not g2.walls, "el tablero arranca limpio")
    g2.comidas = (MUROS_DESDE - 1) * 4         # justo para saltar al nivel
    g2.niv = MUROS_DESDE - 1
    g2.t = g2.speed() - 1
    g2.apple = (0, 0)
    g2.frame()
    chk(g2.walls, "desde el nivel %d empiezan a caer muros" % MUROS_DESDE)


def test_los_portales_te_mudan():
    g = nueva(cols=20, rows=20)
    hx, hy = g.body[0]
    g.apple = (0, 0)
    g.portales = [(hx + 1, hy), (15, 15), 999]
    g.step()
    chk(g.body[0] == (15, 15), "entrar por una boca te saca por la otra "
        "(quedaste en %s)" % (g.body[0],))
    chk(g.porto, "y se nota que pasaste")
    chk(g.dir == (1, 0), "el rumbo no cambia: sales mirando para el mismo lado")


def test_el_portal_no_te_salva_de_morderte():
    """el portal cambia de lugar, no de reglas."""
    g = nueva(cols=20, rows=20)
    g.body = [(5, 5), (5, 6), (5, 7), (6, 7), (7, 7), (7, 6)]
    g.dir = g.pending = (1, 0)
    g.apple = (0, 0)
    # la salida cae sobre el MEDIO del cuerpo. sobre la cola no sirve: esa
    # celda se libera en el mismo paso, y pisarla es legal
    g.portales = [(6, 5), (6, 7), 999]
    chk(g.step() == 'dead', "salir encima de tu propio cuerpo te mata igual")


def test_los_portales_se_mudan():
    g = nueva(cols=20, rows=20)
    g.niv = PORTALES_DESDE
    g.apple = (0, 0)
    g.frame()
    chk(g.portales is not None, "desde el nivel %d se abren" % PORTALES_DESDE)
    par = (g.portales[0], g.portales[1])
    chk(par[0] != par[1], "y son dos bocas distintas")
    g.portales[2] = 1
    g.frame()
    chk(g.portales is None, "se cierran solos cuando se les acaba la cuerda")


def test_nada_nace_encima_de_otra_cosa():
    g = nueva(cols=14, rows=14)
    for _ in range(400):
        g.frame()
        cosas = [g.apple] + \
            ([(g.gold[0], g.gold[1])] if g.gold else []) + \
            ([(g.power[0], g.power[1])] if g.power else [])
        cosas = [c for c in cosas if c]
        chk(len(set(cosas)) == len(cosas), "las frutas no se pisan entre sí")
        chk(not (set(cosas) & g.walls), "ni nacen sobre un muro")
        if g.dead or FALLAS:
            break


# --- la cota de los dos minutos ----------------------------------------------
def test_la_racha_encadena_manzanas():
    g = nueva()
    for i in range(RACHA_CADA):
        hx, hy = g.body[0]
        g.apple = (hx + g.dir[0], hy + g.dir[1])
        g.step()
    chk(g.racha == RACHA_CADA, "tres manzanas seguidas hacen racha")
    chk(g.mult() == 2, "y la próxima vale por dos")
    s0 = g.score
    hx, hy = g.body[0]
    g.apple = (hx + g.dir[0], hy + g.dir[1])
    g.step()
    chk(g.score == s0 + 2, "de verdad (%d -> %d)" % (s0, g.score))
    g.racha = 999
    chk(g.mult() == RACHA_MAX, "con techo en x%d" % RACHA_MAX)


def test_la_racha_se_enfria_sola():
    g = nueva()
    g.racha, g.racha_t = RACHA_CADA * 2, 2
    ev = g.frame()
    ev += g.frame()
    chk(g.racha == 0, "sin comer un rato, la racha vuelve a cero")
    chk(any(e[0] == "racha_fria" for e in ev), "y se avisa")
    chk(g.mult() == 1, "y la manzana vuelve a valer uno")


def test_el_aji_vale_y_acelera():
    g = nueva()
    g.aji_t = 1
    g.frame()
    chk(g.aji is not None, "a su tiempo aparece el ají")
    v0 = g.speed()
    hx, hy = g.body[0]
    g.aji = [hx + g.dir[0], hy + g.dir[1], AJI_TTL]
    g.apple = (0, 0) if (hx + g.dir[0], hy + g.dir[1]) != (0, 0) else (1, 1)
    ev = []
    for _ in range(g.speed()):
        ev += g.frame()
    chk(any(e[0] == "aji" for e in ev), "comerlo se avisa")
    chk(g.score == AJI_VALE, "vale por %d" % AJI_VALE)
    chk(g.turbo > 0 and g.speed() < v0, "y te mete turbo (%d -> %d frames/paso)"
        % (v0, g.speed()))
    for _ in range(AJI_TURBO + 1):
        g.turbo = max(0, g.turbo - 1)
    chk(g.speed() == v0, "que se pasa solo")
    g.aji = [1, 1, 1]
    g.frame()
    chk(g.aji is None, "y si nadie lo come, se va")


def test_la_partida_cabe_en_dos_minutos():
    """el peor caso posible: una culebra que come TODO lo que aparece.

    no se puede jugar para comprobarlo, así que se juega a mano: en cada frame
    le teletransportamos la manzana a la boca. si el aire de las manzanas no
    estuviera acotado, este bucle no terminaría nunca.
    """
    peor = nueva(cols=20, rows=20, seed=7)
    frames = 0
    while not peor.dead and frames < DOS_MIN + 600:
        hx, hy = peor.body[0]
        peor.apple = (hx + peor.dir[0], hy + peor.dir[1])   # comer sin parar
        peor.frame()
        frames += 1
    chk(peor.dead, "hasta la culebra que come todo se muere a tiempo")
    chk(frames <= HAMBRE + EXTRA_MAX + 5,
        "no dura más que el presupuesto (%d frames de %d)"
        % (frames, HAMBRE + EXTRA_MAX))
    chk(frames <= DOS_MIN, "y cabe en dos minutos (%d frames)" % frames)

    quieta = nueva()
    frames = 0
    while not quieta.dead and frames < DOS_MIN:
        quieta.frame()
        frames += 1
    chk(quieta.dead, "y sin tocar nada también termina")


# --- lo nuevo: giros en cola, ratón, arañas, frenesí --------------------------
def test_los_giros_van_en_cola():
    """el swipe doble: yendo a la derecha, arriba-izquierda rápido dentro del
    mismo paso. antes el segundo pisaba al primero y, siendo la reversa del
    rumbo, se perdía."""
    g = nueva()
    g.apple = (0, 0)
    hx, hy = g.body[0]
    g.set_dir((0, -1))
    g.set_dir((-1, 0))
    chk(g.cola_dir == [(0, -1), (-1, 0)], "los dos giros quedan anotados")
    g.step()
    chk(g.body[0] == (hx, hy - 1), "el primero se hace en el primer paso")
    g.step()
    chk(g.body[0] == (hx - 1, hy - 1) and not g.dead,
        "y el segundo en el siguiente, sin morir")
    g = nueva()
    g.set_dir((0, -1))
    g.set_dir((0, 1))
    chk(g.cola_dir == [(0, -1)], "la reversa del último giro anotado no entra")
    g.set_dir((0, -1))
    chk(g.cola_dir == [(0, -1)], "ni repetir el mismo")
    g = nueva()
    for d in ((0, -1), (-1, 0), (0, 1), (1, 0), (0, -1)):
        g.set_dir(d)
    chk(len(g.cola_dir) == COLA_GIROS, "la cola tiene techo de %d" % COLA_GIROS)


def test_el_nivel_sale_de_lo_que_comes():
    g = nueva()
    g.score = 999
    chk(g.level() == 1, "el puntaje solo no sube el nivel (el frenesí x2 no "
        "dispara la velocidad)")
    g.comidas = COMIDAS_NIVEL * 2
    chk(g.level() == 3, "las comidas sí")


def test_el_raton_aparece_y_arranca():
    g = nueva(cols=24, rows=24)
    g.niv = RATON_DESDE
    g.raton_t = 1
    g.apple = (0, 0)
    ev = g.frame()
    chk(g.raton is not None, "desde el nivel %d aparece un ratón" % RATON_DESDE)
    chk(any(e[0] == "raton" for e in ev), "y se avisa")
    hx, hy = g.body[0]
    g.raton = [hx + 3, hy, RATON_TTL, 1]
    antes = abs(g.raton[0] - hx) + abs(g.raton[1] - hy)
    g.t = 1                                   # que no mueva la culebra
    g.frame()
    hx, hy = g.body[0]
    despues = abs(g.raton[0] - hx) + abs(g.raton[1] - hy)
    chk(despues >= antes, "con la cabeza cerca, se aleja (%d -> %d)" % (antes, despues))
    g.raton[2] = 1
    ev = g.frame()
    chk(g.raton is None and any(e[0] == "raton_ido" for e in ev),
        "y si no lo atrapas, se escapa")


def test_comer_el_raton():
    g = nueva(cols=20, rows=20)
    g.niv = RATON_DESDE
    g.t = g.speed() - 1
    hx, hy = g.body[0]
    g.apple = (0, 0)
    g.raton = [hx + 1, hy, RATON_TTL, 999]
    g.hambre = HAMBRE // 2
    largo = len(g.body)
    ev = g.frame()
    chk(any(e[0] == "raton_comido" for e in ev), "atrapar el ratón se avisa")
    chk(g.score == RATON_VALE, "vale %d (dio %d)" % (RATON_VALE, g.score))
    chk(g.hambre > HAMBRE // 2 - 2, "y da aire")
    for _ in range(RATON_CRECE + 1):
        g.step()
    chk(len(g.body) == largo + RATON_CRECE, "y te hace crecer %d (%d -> %d)"
        % (RATON_CRECE, largo, len(g.body)))


def test_las_aranas_matan_y_se_esquivan():
    g = nueva(cols=20, rows=20)
    chk(not g.aranas, "al principio no hay arañas")
    g.niv = ARANA_DESDE
    g.comidas = (ARANA_DESDE - 1) * COMIDAS_NIVEL
    g.apple = (0, 0)
    for _ in range(61):
        g.frame()
        if g.aranas:
            break
    chk(g.aranas, "desde el nivel %d aparece una" % ARANA_DESDE)
    hx, hy = g.body[0]
    a = g.aranas[0]
    chk(abs(a[0] - hx) + abs(a[1] - hy) >= 6, "lejos de tu cabeza")
    chk(a[4] == ARANA_NACE or a[4] > 0, "y nace avisando, sin picar")
    # chocarla con la cabeza mata
    g = nueva(cols=20, rows=20)
    g.apple = (0, 0)
    hx, hy = g.body[0]
    g.aranas = [[hx + 1, hy, 0, 1, 0, 999]]
    g.t = g.speed() - 1
    ev = g.frame()
    chk(g.dead and any(e[0] == "picada" for e in ev), "chocar una araña te mata")
    # con el fantasma te la comes
    g = nueva(cols=20, rows=20)
    g.apple = (0, 0)
    hx, hy = g.body[0]
    g.aranas = [[hx + 1, hy, 0, 1, 0, 999]]
    g.ghost = 100
    g.t = g.speed() - 1
    ev = g.frame()
    chk(not g.dead and not g.aranas, "con el fantasma, te la comes")
    chk(g.score == ARANA_VALE, "y vale %d" % ARANA_VALE)
    # recién nacida no pica
    g = nueva(cols=20, rows=20)
    g.apple = (0, 0)
    hx, hy = g.body[0]
    g.aranas = [[hx + 1, hy, 0, 1, ARANA_NACE, 999]]
    g.t = g.speed() - 1
    g.frame()
    chk(not g.dead, "mientras nace no pica")


def test_las_aranas_no_se_te_meten_encima():
    """el peligro tiene que ser justo: la araña nunca camina sobre tu cuerpo."""
    g = nueva(cols=16, rows=16, seed=3)
    g.body = [(x, 8) for x in range(12, 2, -1)]
    g.dir = g.pending = (1, 0)
    g.aranas = [[7, 6, 0, 1, 0, 1]]           # va derecho hacia el cuerpo
    g.apple = (0, 0)
    for _ in range(200):
        a = g.aranas[0]
        a[5] = 1
        g._mover_arana(a)
        chk((a[0], a[1]) not in g.body, "la araña no pisa la culebra")
        if FALLAS:
            break


def test_el_frenesi_final():
    g = nueva(cols=20, rows=20)
    g.extra = 0
    g.apple = (0, 0)
    ev = g.frame()
    chk(g.frenesi and any(e[0] == "frenesi" for e in ev),
        "sin reserva, arranca el frenesí")
    chk(len(g.bayas) == BAYAS, "y llueven %d bayas" % BAYAS)
    ev = g.frame()
    chk(not any(e[0] == "frenesi" for e in ev), "se anuncia una sola vez")
    hx, hy = g.body[0]
    g.apple = (hx + 1, hy)
    h0 = g.hambre
    g.step()
    chk(g.score == FRENESI_X, "todo vale x%d (la manzana dio %d)" % (FRENESI_X, g.score))
    chk(g.hambre == h0, "pero ya no da aire")
    # comer una baya
    g.t = g.speed() - 1
    hx, hy = g.body[0]
    g.bayas[0] = (hx + 1, hy)
    s0 = g.score
    ev = g.frame()
    chk(any(e[0] == "baya" for e in ev) and g.score > s0, "las bayas suman")
    chk(len(g.bayas) == BAYAS or g.frame() is not None and len(g.bayas) == BAYAS,
        "y se reponen")


def pilotear(g):
    """un piloto tonto: si lo de adelante está ocupado, dobla a donde se pueda."""
    malo = set(g.body) | g.walls | {(a[0], a[1]) for a in g.aranas}
    if g.portales:
        malo |= {g.portales[0], g.portales[1]}
    hx, hy = g.body[0]
    for d in (g.pending, (0, 1), (1, 0), (0, -1), (-1, 0)):
        c = (hx + d[0], hy + d[1])
        if 0 <= c[0] < g.cols and 0 <= c[1] < g.rows and c not in malo \
                and d != (-g.dir[0], -g.dir[1]):
            g.cola_dir = [] if d == g.dir else [d]
            return


def test_nada_nace_encima_de_nada():
    g = nueva(cols=14, rows=14, seed=99)
    g.niv = ARANA_DESDE + 4
    g.comidas = (g.niv - 1) * COMIDAS_NIVEL
    g.raton_t = 1
    g.extra = 0
    vistos = set()
    for _ in range(900):
        pilotear(g)
        g.frame()
        vistos |= {"raton"} if g.raton else set()
        vistos |= {"arana"} if g.aranas else set()
        vistos |= {"baya"} if g.bayas else set()
        cosas = [g.apple] + \
            ([(g.gold[0], g.gold[1])] if g.gold else []) + \
            ([(g.power[0], g.power[1])] if g.power else []) + \
            ([(g.aji[0], g.aji[1])] if g.aji else []) + list(g.bayas)
        cosas = [c for c in cosas if c]
        chk(len(set(cosas)) == len(cosas), "las comidas no se pisan entre sí")
        chk(not (set(cosas) & g.walls), "ni nacen sobre un muro")
        bichos = [(a[0], a[1]) for a in g.aranas]
        chk(not (set(bichos) & g.walls), "las arañas no atraviesan muros")
        if g.dead or FALLAS:
            break
    chk(vistos == {"raton", "arana", "baya"}, "(se vieron ratón, arañas y bayas: %s)"
        % sorted(vistos))


def test_el_frenesi_no_estira_la_partida():
    """la peor culebra del frenesí: come todo (manzana, ratón y bayas) en cada
    paso. sin aire nuevo, igual se termina dentro del presupuesto."""
    g = nueva(cols=20, rows=20, seed=8)
    g.niv = RATON_DESDE
    g.comidas = (RATON_DESDE - 1) * COMIDAS_NIVEL
    # sin muros, portales ni arañas: que sólo la pueda matar el hambre
    g._abrir_portales = g._ensuciar = g._place_arana = lambda: None
    frames = 0
    vio_frenesi = False
    while not g.dead and frames < DOS_MIN + 600:
        hx, hy = g.body[0]
        frente = (hx + g.dir[0], hy + g.dir[1])
        if not (0 <= frente[0] < 20 and 0 <= frente[1] < 20) or frente in g.body:
            g.body = [(10, 10), (9, 10), (8, 10)]
            g.dir = g.pending = (1, 0)
            g.walls.clear()
            g.portales = None
            g.aranas = []
            frente = (11, 10)
        g.apple = frente
        g.raton = [frente[0], frente[1], 999, 999]
        if g.bayas:
            g.bayas[0] = frente
        g.crecer = 0
        g.frame()
        vio_frenesi = vio_frenesi or g.frenesi
        frames += 1
    chk(vio_frenesi, "(llegó al frenesí)")
    chk(g.dead and g.hambre == 0, "la culebra que come todo se muere de hambre a tiempo")
    chk(frames <= HAMBRE + EXTRA_MAX + 5, "dentro del presupuesto (%d de %d)"
        % (frames, HAMBRE + EXTRA_MAX))
    chk(frames <= DOS_MIN, "y en menos de dos minutos (%d)" % frames)


if __name__ == "__main__":
    for fn in (test_inicio, test_mueve, test_no_reversa, test_come,
               test_muere_pared, test_muere_mordida, test_acelera,
               test_el_hambre_baja_y_mata,
               test_comer_da_aire_pero_del_presupuesto,
               test_el_hambre_no_se_pasa_del_tope,
               test_la_dorada_aparece_y_se_va, test_la_dorada_vale_por_cinco,
               test_el_fantasma_te_deja_atravesarte, test_la_tijera_corta_la_cola,
               test_los_muros_matan_y_llegan_con_el_nivel,
               test_los_portales_te_mudan,
               test_el_portal_no_te_salva_de_morderte,
               test_los_portales_se_mudan,
               test_nada_nace_encima_de_otra_cosa,
               test_la_racha_encadena_manzanas, test_la_racha_se_enfria_sola,
               test_el_aji_vale_y_acelera,
               test_la_partida_cabe_en_dos_minutos,
               test_los_giros_van_en_cola, test_el_nivel_sale_de_lo_que_comes,
               test_el_raton_aparece_y_arranca, test_comer_el_raton,
               test_las_aranas_matan_y_se_esquivan,
               test_las_aranas_no_se_te_meten_encima, test_el_frenesi_final,
               test_nada_nace_encima_de_nada,
               test_el_frenesi_no_estira_la_partida):
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
