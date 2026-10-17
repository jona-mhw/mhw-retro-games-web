"""pruebas de cruzar, sin ventana:

    PYTHONPATH=. python -m games.cruzar.test_cruzar

toda la mecánica vive en la clase Cruce, sin pyxel.
"""
import random

from games.cruzar.game import (BOTTOM, CINTA, CLIMAX_T, CLIMAX_X, CRUCE_VALE,
                               Cruce, ESCUDO, HIELO, HIELO_TTL, HUNDE_ABAJO,
                               HUNDE_CICLO, ITEM_VALE, LANES, LANE_H, MOTO,
                               MONEDA_VALE, MULT_MAX, PASO_X, PW, RIO,
                               RITMO_MAX, SEMAFORO_TTL, TIME, TOP, TRAFICO,
                               TRAMOS, TREN, TREN_AVISO, VEREDA, VIDAS, W,
                               armar_tramo)

FALLAS = []
DOS_MIN = 2 * 60 * 60


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def nuevo(seed=5):
    return Cruce(rng=random.Random(seed))


def despejar(c):
    """saca todo el tráfico: para probar el movimiento sin que te pisen."""
    for carril in c.carriles:
        carril.cosas = []
    return c


# --- el tablero ---------------------------------------------------------------
def test_hay_de_los_dos_tipos():
    c = nuevo()
    tipos = {carril.tipo for carril in c.carriles}
    chk(TRAFICO in tipos and CINTA in tipos,
        "hay carriles de tráfico y de cinta")
    chk(len(c.carriles) == LANES, "y son %d en total" % LANES)
    chk(all(carril.tipo == CINTA for carril in c.carriles[:3]),
        "las cintas están arriba, que es donde cambia la lectura")


def test_el_carril_se_ubica_por_la_y():
    c = nuevo()
    chk(c.carril_en(TOP) is c.carriles[0], "la y de arriba cae en el primero")
    chk(c.carril_en(BOTTOM - 1) is c.carriles[LANES - 1], "y la de abajo en el último")
    chk(c.carril_en(BOTTOM) is None, "la orilla de abajo no es un carril")
    chk(c.carril_en(TOP - LANE_H) is None, "ni la meta")


def test_el_trafico_da_la_vuelta():
    c = nuevo()
    carril = next(x for x in c.carriles if x.tipo == TRAFICO and x.v > 0)
    for _ in range(2000):
        carril.step()
    chk(all(-carril.ancho <= x <= W + carril.ancho for x in carril.cosas),
        "el tráfico reaparece por el otro lado en vez de irse para siempre")


# --- moverse ------------------------------------------------------------------
def test_moverse_y_los_bordes():
    c = despejar(nuevo())
    c.px = 0
    c.mover(-1, 0, [])
    chk(c.px == 0, "no te sales por la izquierda")
    c.px = W - PW
    c.mover(1, 0, [])
    chk(c.px == W - PW, "ni por la derecha")
    y0 = c.py
    c.mover(0, -1, [])
    chk(c.py == y0 - LANE_H, "arriba subes un carril entero")
    c.px = 100
    c.mover(1, 0, [])
    chk(c.px == 100 + PASO_X, "y al costado, un paso que se ve (%d px)" % PASO_X)


def test_llegar_arriba_suma_y_te_devuelve():
    c = despejar(nuevo())
    c.py = TOP
    ev = []
    c.mover(0, -1, ev)
    chk(any(x[0] == "cruce" for x in ev), "llegar arriba se avisa")
    chk(c.score == CRUCE_VALE, "y paga %d" % CRUCE_VALE)
    chk(c.py == BOTTOM, "y vuelves abajo para la próxima")
    chk(c.cruces == 1, "y cuenta el cruce")


def test_la_racha_multiplica():
    c = despejar(nuevo())
    chk(c.mult() == 1, "sin racha, vale de a uno")
    c.racha = 2
    chk(c.mult() == 2, "cada dos cruces limpios sube")
    c.racha = 99
    chk(c.mult() == MULT_MAX, "con techo en %d" % MULT_MAX)


def test_la_racha_se_enfria():
    c = despejar(nuevo())
    c.racha, c.vuelta_t = 4, 2
    c.step(0, 0)
    ev = c.step(0, 0)
    chk(c.racha == 0, "tardar demasiado en cruzar enfría la racha")
    chk(any(x[0] == "racha_fria" for x in ev), "y se avisa")


# --- que te toquen ------------------------------------------------------------
def test_el_trafico_te_atropella():
    c = despejar(nuevo())
    carril = next(x for x in c.carriles if x.tipo == TRAFICO)
    c.py = carril.y
    c.px = 100
    carril.cosas = [100.0]                    # un auto justo encima
    ev = c.step(0, 0)
    chk(any(x[0] == "golpe" for x in ev), "el auto te atropella")
    chk(c.lives == VIDAS - 1, "y cuesta una vida")
    chk(c.py == BOTTOM, "y vuelves a la orilla")
    chk(not c.over, "pero la partida sigue")


def test_la_gracia_te_protege():
    c = despejar(nuevo())
    carril = next(x for x in c.carriles if x.tipo == TRAFICO)
    c.py, c.px = carril.y, 100
    carril.cosas = [100.0]
    c.step(0, 0)
    vidas = c.lives
    for _ in range(12):
        c.py, c.px = carril.y, 100
        c.step(0, 0)
    chk(c.lives == vidas, "durante la gracia no te vuelven a pisar")


def test_atropellarte_corta_la_racha():
    c = despejar(nuevo())
    c.racha = 6
    carril = next(x for x in c.carriles if x.tipo == TRAFICO)
    c.py, c.px = carril.y, 100
    carril.cosas = [100.0]
    c.step(0, 0)
    chk(c.racha == 0, "que te pisen te deja sin racha")


def test_sin_vidas_se_acaba():
    c = despejar(nuevo())
    carril = next(x for x in c.carriles if x.tipo == TRAFICO)
    for _ in range(VIDAS):
        c.gracia = 0
        c.py, c.px = carril.y, 100
        carril.cosas = [100.0]
        c.step(0, 0)
    chk(c.lives == 0 and c.over, "sin vidas, se termina")


# --- la cinta -----------------------------------------------------------------
def test_la_cinta_te_arrastra():
    c = despejar(nuevo())
    carril = next(x for x in c.carriles if x.tipo == CINTA)
    carril.v = 1.2
    carril.rojo = 0
    c.py = carril.y
    c.px = 100
    carril.cosas = [96.0]                     # una plataforma bajo tus pies
    x0 = c.px
    c.step(0, 0)
    chk(c.px > x0, "parado en la cinta, te lleva (de %.0f a %.0f)" % (x0, c.px))


def test_la_cinta_no_te_mata_por_estar_ahi():
    """el carril de cinta no atropella: la diferencia con el tráfico es el punto."""
    c = despejar(nuevo())
    carril = next(x for x in c.carriles if x.tipo == CINTA)
    c.py, c.px = carril.y, 100
    carril.cosas = [96.0]
    c.step(0, 0)
    chk(c.lives == VIDAS, "pisar una plataforma no te hace nada")


def test_caerse_del_borde_en_la_cinta():
    c = despejar(nuevo())
    carril = next(x for x in c.carriles if x.tipo == CINTA)
    carril.v, carril.rojo = 2.5, 0
    c.py = carril.y
    c.px = W - PW - 1
    carril.cosas = [float(W - PW - 4)]
    ev = []
    for _ in range(20):
        ev += c.step(0, 0)
        if c.lives < VIDAS:
            break
    chk(any(x[0] == "golpe" for x in ev),
        "si la cinta te lleva hasta el borde, te caes")


# --- el semáforo --------------------------------------------------------------
def test_el_semaforo_frena_un_carril():
    c = nuevo()
    c.sem_t = 1
    c._semaforo()
    rojos = [x for x in c.carriles if x.rojo]
    chk(len(rojos) == 1, "el semáforo pone en rojo un carril (puso %d)"
        % len(rojos))
    carril = rojos[0]
    chk(carril.tipo == TRAFICO, "y es uno de tráfico")
    chk(carril.vel() == 0.0, "que queda frenado")
    xs = list(carril.cosas)
    carril.step()
    chk(carril.cosas == xs, "y no se mueve mientras dura")
    carril.rojo = 0
    carril.step()
    chk(carril.cosas != xs, "cuando pasa a verde, arranca de nuevo")


def test_el_semaforo_se_le_pasa():
    c = nuevo()
    c.sem_t = 1
    c._semaforo()
    carril = next(x for x in c.carriles if x.rojo)
    for _ in range(SEMAFORO_TTL + 5):
        carril.step()
    chk(not carril.rojo, "el rojo no dura para siempre")


# --- el ritmo y las monedas -------------------------------------------------
def test_el_trafico_acelera_con_los_cruces():
    c = despejar(nuevo())
    chk(c.ritmo() == 1.0, "al empezar el tráfico va a su ritmo")
    c.cruces = 5
    r5 = c.ritmo()
    chk(r5 > 1.0, "a los 5 cruces ya va más rápido (%.2f)" % r5)
    c.cruces = 500
    chk(c.ritmo() == RITMO_MAX, "con techo en %.1f" % RITMO_MAX)
    carril = next(x for x in c.carriles if x.tipo == TRAFICO)
    carril.cosas = [50.0]
    carril.rojo = 0
    carril.step(1.0)
    lento = carril.cosas[0] - 50.0
    carril.cosas = [50.0]
    carril.step(RITMO_MAX)
    rapido = carril.cosas[0] - 50.0
    chk(abs(rapido) > abs(lento), "y el carril de verdad se mueve más por frame")


def test_la_moneda_nace_entre_autos_y_se_levanta():
    c = despejar(nuevo(seed=31))
    c.moneda_t = 1
    c.step(0, 0)
    chk(len(c.monedas) == 1, "a su tiempo aparece una moneda")
    ci, mx, ttl = c.monedas[0]
    chk(c.carriles[ci].tipo == TRAFICO, "en un carril de tráfico")
    # la pisamos: nos paramos en su carril, encima
    c.py = c.carriles[ci].y
    c.px = mx - PW / 2
    c.racha = 2                              # x2, para ver que multiplica
    ev = c.step(0, 0)
    chk(any(x[0] == "moneda" for x in ev), "pisarla la levanta")
    chk(c.score == MONEDA_VALE * 2, "y paga por el multiplicador (%d)" % c.score)
    chk(not c.monedas, "y desaparece")


def test_la_moneda_viaja_con_el_carril_y_caduca():
    c = despejar(nuevo(seed=32))
    c.moneda_t = 1
    c.step(0, 0)
    ci, x0, ttl0 = c.monedas[0]
    c.carriles[ci].rojo = 0
    c.step(0, 0)
    chk(c.monedas[0][1] != x0, "la moneda se mueve con su carril")
    c.monedas[0][2] = 1
    c.step(0, 0)
    chk(not c.monedas, "y si nadie la levanta, se va sola")


# --- la cota de los dos minutos ----------------------------------------------
def test_la_partida_cabe_en_dos_minutos():
    quieto = nuevo(seed=21)
    f = 0
    while not quieto.over and f < DOS_MIN + 600:
        quieto.step(0, 0)
        f += 1
    chk(quieto.over, "quieto en la orilla, la partida igual termina")
    chk(f <= DOS_MIN, "a tiempo (%d frames)" % f)

    # el que cruza sin parar: nada de lo que gana le devuelve tiempo
    corredor = nuevo(seed=22)
    f = 0
    while not corredor.over and f < DOS_MIN + 600:
        corredor.gracia = 999                   # intocable, para ver el techo
        corredor.step(0, -1)
        f += 1
    chk(corredor.over, "y el que cruza sin parar tampoco juega para siempre")
    chk(f <= TIME + 2, "termina con el reloj (%d de %d)" % (f, TIME))
    chk(corredor.cruces > 20, "(y cruzó de verdad: %d veces)" % corredor.cruces)


def test_el_puntaje_no_se_dispara():
    """con el multiplicador acotado, el techo del puntaje es calculable."""
    c = nuevo(seed=23)
    f = 0
    while not c.over and f < DOS_MIN:
        c.gracia = 1
        c.step(0, -1)
        f += 1
    techo = (c.cruces * CRUCE_VALE + c.monedas_tomadas * MONEDA_VALE) * \
        MULT_MAX * CLIMAX_X
    techo += ITEM_VALE * (TIME // (7 * 60) + 1)       # a lo más un ítem por tanda
    chk(c.score <= techo, "el puntaje no puede pasar de (cruces × %d + monedas "
        "× %d) × %d × %d + ítems (%d de %d)" % (CRUCE_VALE, MONEDA_VALE,
                                                MULT_MAX, CLIMAX_X, c.score,
                                                techo))


# --- los tramos ---------------------------------------------------------------
def test_cada_cruce_cambia_el_tramo():
    c = nuevo()
    vistos = [c.tramo]
    for _ in range(len(TRAMOS) + 2):
        despejar(c)
        c.py = TOP
        ev = []
        c.mover(0, -1, ev)
        chk(any(e[0] == "tramo" for e in ev), "cruzar avisa el tramo nuevo")
        vistos.append(c.tramo)
        chk(len(c.carriles) == LANES, "que trae sus %d carriles" % LANES)
        chk(all(k.i == i for i, k in enumerate(c.carriles)), "bien numerados")
    chk(set(vistos) == {t[0] for t in TRAMOS},
        "en pocos cruces se ven todos los tramos (%s)" % sorted(set(vistos)))
    chk(vistos[0] == "BARRIO", "y se empieza por el barrio")


def test_todos_los_tramos_tienen_salida():
    """ningún tramo es imposible: hay piso para pararse en cada fila en algún
    momento (la vereda, el hueco entre autos, un tronco a flote)."""
    for n in range(len(TRAMOS)):
        for seed in range(5):
            nombre, cs = armar_tramo(n, random.Random(seed))
            for k in cs:
                if k.tipo == RIO:
                    chk(k.cosas, "%s: el río trae troncos" % nombre)
                    hueco = k.hueco - k.ancho
                    chk(hueco < 60, "%s: y no tan separados (%d)" % (nombre, hueco))
                elif k.tipo == TRAFICO:
                    chk(k.hueco - k.ancho >= 34, "%s: entre auto y auto cabes "
                        "(%d px)" % (nombre, k.hueco - k.ancho))


def test_las_motos_pegan_acelerones():
    _, cs = armar_tramo(1, random.Random(3))
    moto = next(k for k in cs if k.tipo == TRAFICO and k.vehiculo == MOTO)
    vs = set()
    for _ in range(300):
        moto.step()
        vs.add(round(abs(moto.vel()), 2))
    chk(max(vs) > 1.4 * min(vs), "la moto no anda siempre igual (%.2f a %.2f)"
        % (min(vs), max(vs)))


def test_la_vereda_es_segura():
    c = nuevo()
    c.cruces = 1
    c.tramo, c.carriles = armar_tramo(1, c.rng)
    v = next(k for k in c.carriles if k.tipo == VEREDA)
    c.py = v.y
    for _ in range(300):
        c.gracia = 0
        c.step(0, 0)
    chk(c.lives == VIDAS, "en la vereda no te pasa nada")


# --- el tren ------------------------------------------------------------------
def _via(c):
    c.cruces = 2
    c.tramo, c.carriles = armar_tramo(2, c.rng)
    return next(k for k in c.carriles if k.tipo == TREN)


def test_el_tren_avisa_antes_de_pasar():
    c = nuevo()
    via = _via(c)
    chk(not via.cosas, "la vía arranca vacía")
    via.tren_t = 1
    ev = c.step(0, 0)
    chk(via.aviso == TREN_AVISO or any(e[0] == "aviso_tren" for e in ev),
        "primero suenan las luces")
    f = 0
    while not via.cosas and f < 500:
        c.step(0, 0)
        f += 1
    chk(TREN_AVISO - 3 <= f <= TREN_AVISO + 1,
        "el aviso dura lo que tiene que durar (%d frames)" % f)
    f = 0
    while via.cosas and f < 500:
        c.step(0, 0)
        f += 1
    chk(f < 80, "y el tren pasa rápido (%d frames)" % f)
    chk(not via.cosas and via.tren_t > 0, "y la vía vuelve a quedar vacía")


def test_el_tren_atropella():
    c = nuevo()
    via = _via(c)
    c.py, c.px = via.y, 100
    via.cosas = [60.0]
    ev = c.step(0, 0)
    chk(any(e[0] == "golpe" and e[4] == "tren" for e in ev), "el tren no perdona")


def test_la_via_vacia_se_cruza():
    c = nuevo()
    via = _via(c)
    via.tren_t = 10 ** 6
    c.py = via.y
    for _ in range(60):
        c.step(0, 0)
    chk(c.lives == VIDAS, "sin tren, la vía es piso")


# --- el río -------------------------------------------------------------------
def _rio(c):
    c.cruces = 3
    c.tramo, c.carriles = armar_tramo(3, c.rng)
    return [k for k in c.carriles if k.tipo == RIO]


def test_el_agua_te_hunde_y_el_tronco_te_lleva():
    c = nuevo()
    rio = _rio(c)[0]
    rio.hunde = None
    rio.cosas = [150.0]
    c.py, c.px = rio.y, 20
    ev = c.step(0, 0)
    chk(any(e[0] == "golpe" and e[4] == "agua" for e in ev), "caer al agua es golpe")
    c = nuevo()
    rio = _rio(c)[0]
    rio.hunde = None
    rio.v = 0.8
    rio.cosas = [90.0]
    c.py, c.px = rio.y, 100
    c.step(0, 0)
    chk(c.lives == VIDAS and c.px > 100, "sobre el tronco, flotas y te lleva")


def test_algunos_troncos_se_hunden():
    c = nuevo()
    rios = _rio(c)
    chk(any(k.hunde for k in rios), "en el río hay troncos que se hunden")
    rio = next(k for k in rios if k.hunde)
    rio.cosas = [90.0]
    rio.hunde = [0]
    rio.v = 0.0
    estados = []
    for _ in range(HUNDE_CICLO):
        rio.step()
        estados.append(rio.estado_tronco(0))
    chk(1 in estados and 2 in estados, "titila antes de hundirse, y se hunde")
    chk(estados.index(1) < estados.index(2), "(el aviso va primero)")
    chk(estados.count(2) == HUNDE_ABAJO, "y abajo dura %d frames" % HUNDE_ABAJO)
    rio.hunde = [HUNDE_CICLO - 5]
    c.py, c.px = rio.y, 100
    ev = c.step(0, 0)
    chk(any(e[0] == "golpe" and e[4] == "agua" for e in ev),
        "parado en un tronco hundido, te mojas")


# --- ítems --------------------------------------------------------------------
def test_el_escudo_aguanta_un_golpe():
    c = despejar(nuevo())
    c.escudo = True
    carril = next(x for x in c.carriles if x.tipo == TRAFICO)
    c.py, c.px = carril.y, 100
    carril.cosas = [100.0]
    ev = c.step(0, 0)
    chk(any(e[0] == "escudo_roto" for e in ev), "el escudo se come el golpe")
    chk(c.lives == VIDAS and not c.escudo, "no pierdes vida, pero se gasta")
    chk(c.py == carril.y, "y te quedas donde estabas")
    c.gracia = 0
    ev = c.step(0, 0)
    chk(c.lives == VIDAS - 1, "el segundo golpe sí duele")


def test_el_reloj_congela_el_trafico_no_la_partida():
    c = despejar(nuevo())
    carril = next(x for x in c.carriles if x.tipo == TRAFICO)
    carril.cosas = [50.0]
    carril.rojo = 0
    c.items = [[carril.i, c.px + PW / 2, 100, HIELO]]
    c.py = carril.y
    c.carriles[carril.i].cosas = [200.0]
    ev = c.step(0, 0)
    chk(any(e[0] == "item" and e[3] == HIELO for e in ev), "pisar el reloj lo toma")
    chk(c.hielo > 0, "y congela")
    x0, t0 = carril.cosas[0], c.time
    c.py = BOTTOM
    c.step(0, 0)
    lento = abs(carril.cosas[0] - x0)
    chk(c.time == t0 - 1, "el reloj de la partida sigue bajando")
    c.hielo = 0
    x0 = carril.cosas[0]
    c.step(0, 0)
    chk(lento < abs(carril.cosas[0] - x0) * 0.5, "y el tráfico va mucho más lento")


def test_los_items_aparecen_en_la_vereda():
    c = nuevo()
    c.cruces = 1
    c.tramo, c.carriles = armar_tramo(1, c.rng)
    c.item_t = 1
    c.step(0, 0)
    chk(len(c.items) == 1, "a su tiempo aparece un ítem")
    chk(c.carriles[c.items[0][0]].tipo == VEREDA, "en la vereda, si la hay")
    chk(c.items[0][3] in (ESCUDO, HIELO), "y es escudo o reloj")


# --- la hora punta -------------------------------------------------------------
def test_la_hora_punta_paga_doble():
    c = despejar(nuevo())
    c.time = CLIMAX_T + 1
    ev = c.step(0, 0)
    chk(c.climax and any(e[0] == "climax" for e in ev), "los últimos 15 s son hora punta")
    despejar(c)
    c.py = TOP
    s0 = c.score
    c.mover(0, -1, [])
    chk(c.score - s0 == CRUCE_VALE * CLIMAX_X, "y el cruce vale doble (%d)"
        % (c.score - s0))


def test_ningun_tramo_estira_el_reloj():
    """un corredor intocable que cruza todos los tramos: el congelado, los
    trenes y los tramos nuevos no le agregan ni un frame a la partida."""
    c = nuevo(seed=40)
    f = 0
    while not c.over and f < DOS_MIN + 600:
        c.gracia = 999
        if f % 400 == 0:
            c.hielo = HIELO_TTL
        c.step(0, -1 if f % 3 == 0 else 0)
        f += 1
    chk(c.over and f <= TIME + 2, "termina con el reloj (%d de %d)" % (f, TIME))
    chk(c.cruces >= len(TRAMOS), "(y pasó por todos los tramos: %d cruces)"
        % c.cruces)


if __name__ == "__main__":
    for fn in (test_hay_de_los_dos_tipos, test_el_carril_se_ubica_por_la_y,
               test_el_trafico_da_la_vuelta, test_moverse_y_los_bordes,
               test_llegar_arriba_suma_y_te_devuelve, test_la_racha_multiplica,
               test_la_racha_se_enfria, test_el_trafico_te_atropella,
               test_la_gracia_te_protege, test_atropellarte_corta_la_racha,
               test_sin_vidas_se_acaba, test_la_cinta_te_arrastra,
               test_la_cinta_no_te_mata_por_estar_ahi,
               test_caerse_del_borde_en_la_cinta,
               test_el_semaforo_frena_un_carril, test_el_semaforo_se_le_pasa,
               test_el_trafico_acelera_con_los_cruces,
               test_la_moneda_nace_entre_autos_y_se_levanta,
               test_la_moneda_viaja_con_el_carril_y_caduca,
               test_la_partida_cabe_en_dos_minutos,
               test_el_puntaje_no_se_dispara,
               test_cada_cruce_cambia_el_tramo,
               test_todos_los_tramos_tienen_salida,
               test_las_motos_pegan_acelerones, test_la_vereda_es_segura,
               test_el_tren_avisa_antes_de_pasar, test_el_tren_atropella,
               test_la_via_vacia_se_cruza,
               test_el_agua_te_hunde_y_el_tronco_te_lleva,
               test_algunos_troncos_se_hunden,
               test_el_escudo_aguanta_un_golpe,
               test_el_reloj_congela_el_trafico_no_la_partida,
               test_los_items_aparecen_en_la_vereda,
               test_la_hora_punta_paga_doble,
               test_ningun_tramo_estira_el_reloj):
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
