"""pruebas de asteroides, sin ventana:

    PYTHONPATH=. python -m games.asteroides.test_asteroides

toda la mecánica vive en la clase Espacio, sin pyxel.
"""
import math
import random

from games.asteroides.game import (CAZADOR_VALE, CHICA, COMBO_CADA, COMBO_MAX,
                                   COMBO_TTL, COMETA_AVISO, COMETA_VALE,
                                   Cazador, Cometa, DISPARO_GAP, DORADA_TTL,
                                   DORADA_VALE, ESCUDO, Espacio, FIELD_TOP,
                                   GRANDE, H, LIMPIA_VALE, MAXV, MEDIANA,
                                   MINA_ONDA,
                                   MINA_VALE, Mina, NOVA, OLEADA_GAP, RAFAGA,
                                   RAFAGA_GAP, RESPIRO, Roca, TIME, TORMENTA,
                                   TRIPLE, VALE, VIDAS, W, dist2, envolver)

FALLAS = []
DOS_MIN = 2 * 60 * 60


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def nuevo(seed=3):
    return Espacio(rng=random.Random(seed))


def limpio(seed=3):
    """un campo sin piedras ni cazador, para probar una cosa a la vez."""
    e = nuevo(seed)
    e.rocas = []
    e.minas = []
    e.caza_t = 10 ** 6
    e.cometa_t = 10 ** 6
    e.oleada_t = 10 ** 6
    e.respiro = 10 ** 6              # y sin oleada nueva por limpiar
    return e


# --- el campo se envuelve -----------------------------------------------------
def test_el_campo_da_la_vuelta():
    x, y = envolver(W + 3, FIELD_TOP + 5)
    chk(x == 3, "salir por la derecha te devuelve por la izquierda")
    x, y = envolver(-2, H + 2)
    chk(x == W - 2, "y al revés")
    chk(y == FIELD_TOP + 2, "por abajo vuelves por arriba")


def test_la_distancia_cuenta_la_vuelta():
    """dos cosas en bordes opuestos están CERCA, no en las antípodas."""
    d_borde = dist2(2, 100, W - 2, 100)
    chk(d_borde == 16, "cruzando el borde son 4 px (dio %.0f)" % math.sqrt(d_borde))
    chk(dist2(10, 100, 40, 100) == 900, "y adentro se mide normal")


# --- la nave ------------------------------------------------------------------
def test_la_nave_empuja_hacia_donde_mira():
    e = limpio()
    e.a = 0.0                                   # mirando a la derecha
    x0 = e.x
    for _ in range(10):
        e.step(0, True, False)
    chk(e.x > x0, "empujando mirando a la derecha, se va a la derecha")
    chk(e.vx > 0, "y toma velocidad")


def test_la_inercia_no_se_frena_sola_rapido():
    e = limpio()
    e.vx = 2.0
    for _ in range(30):
        e.step(0, False, False)
    chk(e.vx > 1.0, "en el espacio la nave sigue derecho (quedó en %.2f)" % e.vx)


def test_los_frenos():
    e = limpio()
    e.vx, e.vy = 2.0, 2.0
    e.frenar()
    chk(abs(e.vx) < 2.0 and abs(e.vy) < 2.0, "los frenos te paran de golpe")


def test_la_velocidad_tiene_tope():
    e = limpio()
    e.a = 0.0
    for _ in range(400):
        e.step(0, True, False)
    chk(math.hypot(e.vx, e.vy) <= MAXV + 0.05, "la nave no acelera para siempre "
        "(%.2f)" % math.hypot(e.vx, e.vy))


# --- romper piedra ------------------------------------------------------------
def test_la_grande_se_parte_en_dos():
    e = limpio()
    roca = Roca(100, 100, GRANDE, 0.0, e.rng)
    e.rocas = [roca]
    ev = []
    e._romper(roca, ev)
    chk(len(e.rocas) == 2, "una grande da dos medianas (dio %d)" % len(e.rocas))
    chk(all(r.tam == MEDIANA for r in e.rocas), "y son medianas")
    chk(e.score == VALE[GRANDE], "y paga lo suyo")
    chk(any(x[0] == "rompe" for x in ev), "y se avisa")


def test_la_chica_no_se_parte():
    e = limpio()
    roca = Roca(100, 100, CHICA, 0.0, e.rng)
    e.rocas = [roca]
    e._romper(roca, [])
    chk(not e.rocas, "una chica desaparece")
    chk(VALE[CHICA] > VALE[GRANDE], "y vale más que una grande (%d vs %d)"
        % (VALE[CHICA], VALE[GRANDE]))


def test_desarmar_entera_paga_mas_que_reventar_la_grande():
    """la regla que hace interesante el puntaje: 1 grande -> 2 med -> 4 chicas."""
    entera = VALE[GRANDE] + 2 * VALE[MEDIANA] + 4 * VALE[CHICA]
    chk(entera > VALE[GRANDE] * 4, "desarmar toda la cadena paga %d" % entera)


def test_las_roturas_seguidas_hacen_combo():
    e = limpio()
    e.gracia = 10 ** 6
    for i in range(COMBO_CADA):
        roca = Roca(100, 100, CHICA, 0.0, e.rng)
        e.rocas = [roca]
        ev = []
        e._romper(roca, ev)
    chk(e.combo == COMBO_CADA, "tres seguidas hacen combo")
    chk(e.mult() == 2, "y la próxima vale por dos")
    chk(any(x[0] == "combo" for x in ev), "y se avisa")
    s0 = e.score
    roca = Roca(100, 100, CHICA, 0.0, e.rng)
    e.rocas = [roca]
    e._romper(roca, [])
    chk(e.score == s0 + VALE[CHICA] * 2, "de verdad (%d)" % (e.score - s0))
    e.combo = 999
    chk(e.mult() == COMBO_MAX, "con techo en x%d" % COMBO_MAX)
    e.combo, e.combo_t = COMBO_CADA, 1
    ev = e.step(0, False, False)
    chk(e.combo == 0 and e.mult() == 1, "sin romper nada un segundo, se enfría")
    chk(any(x[0] == "combo_frio" for x in ev), "y avisa")


def test_la_dorada_entra_vale_y_se_va():
    e = limpio()
    e.dorada_t = 1
    ev = e.step(0, False, False)
    chk(any(x[0] == "dorada_entra" for x in ev), "a su tiempo entra la dorada")
    dor = [r for r in e.rocas if r.dorada]
    chk(len(dor) == 1, "y es una piedra más en el campo")
    roca = dor[0]
    chk(roca.ttl == DORADA_TTL - 0 or roca.ttl > 0, "con fecha de vencimiento")
    ev = []
    e._romper(roca, ev)
    chk(any(x[0] == "dorada" for x in ev), "romperla se avisa")
    chk(e.score == DORADA_VALE, "y paga %d (dio %d)" % (DORADA_VALE, e.score))
    chk(not e.rocas, "y no se parte en dos")
    e.dorada_t = 1
    e.step(0, False, False)
    roca = [r for r in e.rocas if r.dorada][0]
    roca.ttl = 2
    ev = e.step(0, False, False)
    ev += e.step(0, False, False)
    chk(roca not in e.rocas, "si nadie la caza, se va sola")
    chk(any(x[0] == "dorada_ida" for x in ev), "y avisa")


def test_el_tiro_rompe():
    e = limpio()
    e.rocas = [Roca(120, 100, GRANDE, 0.0, e.rng)]
    e.tiros = [[120, 100, 0.0, 0.0, 30, 1]]
    ev = []
    e._mover_tiros(ev)
    chk(any(x[0] == "rompe" for x in ev), "el tiro parte la piedra")
    chk(not e.tiros, "y el tiro se consume")


def test_disparar_tiene_cadencia():
    e = limpio()
    chk(e.disparar([]), "el primer tiro sale")
    chk(not e.disparar([]), "el segundo no: hay cadencia")
    for _ in range(20):
        e.step(0, False, False)
    chk(e.disparar([]), "y después sí")


def test_mantener_fuego_dispara_parejo():
    """mantener FUEGO toda la partida dispara siempre al mismo ritmo: sin
    munición, sin tope de tiros en pantalla, sin trabarse nunca."""
    e = nuevo(seed=21)
    tiros = []
    n0 = 0
    f = 0
    while not e.over:
        e.gracia = 10                     # que no se muera, para medir todo
        e.rafaga = 0
        e.step(1, f % 50 < 20, True)
        f += 1
        if f % 600 == 0:
            tiros.append(e.disparos - n0)
            n0 = e.disparos
    esperado = 600 // DISPARO_GAP
    chk(all(abs(t - esperado) <= 1 for t in tiros),
        "cada 10 s salen ~%d tiros, siempre (%s)" % (esperado, tiros))


def test_la_rafaga_dobla_la_cadencia():
    e = limpio()
    e._tomar(RAFAGA, [])
    n = 0
    for _ in range(60):
        e.step(0, False, True)
    chk(e.disparos >= 60 // RAFAGA_GAP - 1, "con ráfaga dispara el doble (%d)"
        % e.disparos)

def test_el_triple_dispara_tres():
    e = limpio()
    e._tomar(TRIPLE, [])
    e.tiros = []
    e.cool = 0
    e.disparar([])
    chk(len(e.tiros) == 3, "con el triple salen tres tiros (salieron %d)"
        % len(e.tiros))


def test_la_mina_estalla_y_arrastra():
    e = limpio()
    e.gracia = 10 ** 6
    m = Mina(120, 100, e.rng)
    m.vx = m.vy = 0
    cerca = Roca(120 + MINA_ONDA - 8, 100, CHICA, 0.0, e.rng)
    lejos = Roca(30, 60, CHICA, 0.0, e.rng)
    otra = Mina(120 - MINA_ONDA + 6, 100, e.rng)
    e.minas = [m, otra]
    e.rocas = [cerca, lejos]
    e.tiros = [[120, 100, 0.0, 0.0, 30, 1]]
    ev = []
    e._mover_tiros(ev)
    chk(any(x[0] == "mina" for x in ev), "un tiro hace estallar la mina")
    chk(cerca not in e.rocas, "y la onda rompe lo que está cerca")
    chk(lejos in e.rocas, "pero no lo lejano")
    chk(not e.minas, "y la mina vecina revienta en cadena")
    chk(e.score >= MINA_VALE * 2 + VALE[CHICA], "y todo paga (%d)" % e.score)
    chk(e.combo >= 3, "y suma combo (%d)" % e.combo)


def test_tocar_una_mina_duele():
    e = limpio()
    e.gracia = 0
    e.minas = [Mina(e.x, e.y, e.rng)]
    ev = e.step(0, False, False)
    chk(any(x[0] == "golpe" for x in ev), "chocar una mina cuesta una vida")
    chk(not e.minas, "y la mina se va")


def test_el_cometa_avisa_cruza_y_paga():
    e = limpio()
    e.gracia = 0
    c = Cometa(-8.0, e.y, 0.0)
    e.cometas = [c]
    x0 = c.x
    for _ in range(COMETA_AVISO - 1):
        e.step(0, False, False)
    chk(c.x == x0, "durante el aviso no se mueve")
    for _ in range(10):
        e.step(0, False, False)
    chk(c.x > x0, "después cruza")
    for _ in range(200):
        e.gracia = 10
        e.step(0, False, False)
    chk(not e.cometas, "y se va: no da la vuelta")
    e = limpio()
    c = Cometa(100.0, 100.0, 0.0)
    c.aviso = 0
    e.cometas = [c]
    e.tiros = [[100, 100, 0.0, 0.0, 30, 1]]
    ev = []
    e._mover_tiros(ev)
    chk(any(x[0] == "cometa" for x in ev) and e.score == COMETA_VALE,
        "pegarle paga %d (%d)" % (COMETA_VALE, e.score))


def test_las_oleadas_se_limpian_y_vuelven():
    e = nuevo(seed=4)
    chk(e.oleada == 1, "arranca en la oleada 1")
    e.respiro = 0
    e.rocas = []
    e.minas = []
    e.gracia = 10
    ev = e.step(0, False, False)
    chk(any(x[0] == "oleada_limpia" for x in ev), "limpiar el campo se avisa")
    chk(e.score >= LIMPIA_VALE, "y paga un bono (%d)" % e.score)
    for _ in range(RESPIRO):
        e.gracia = 10
        ev = e.step(0, False, False)
    chk(e.oleada == 2, "y después del respiro viene la 2")
    chk(e.minas, "que trae minas")
    e.oleada_t = 1
    e.gracia = 10
    ev = e.step(0, False, False)
    chk(e.oleada == 3, "si no la limpias, la siguiente entra igual")
    chk(any(x[0] == "oleada" for x in ev), "anunciada")


def test_la_nova_revienta_alrededor():
    e = limpio()
    e.gracia = 10 ** 6
    e.rocas = [Roca(e.x + 30, e.y, GRANDE, 0.0, e.rng),
               Roca(e.x - 20, e.y + 10, CHICA, 0.0, e.rng)]
    ev = []
    e._tomar(NOVA, ev)
    chk(any(x[0] == "onda" for x in ev), "la nova hace una onda")
    chk(all(r.tam < GRANDE for r in e.rocas), "y rompe lo que tienes cerca")


def test_la_tormenta_vale_doble():
    e = limpio()
    e.time = TORMENTA - 1
    roca = Roca(100, 100, CHICA, 0.0, e.rng)
    e.rocas = [roca]
    e._romper(roca, [])
    chk(e.score == VALE[CHICA] * 2, "en la tormenta todo vale doble (%d)"
        % e.score)
    ev = e.step(0, False, False)
    chk(any(x[0] == "tormenta" for x in ev), "y se anuncia")


# --- daño ---------------------------------------------------------------------
def test_chocar_una_piedra_cuesta_una_vida():
    e = limpio()
    e.gracia = 0
    e.rocas = [Roca(e.x, e.y, GRANDE, 0.0, e.rng)]
    ev = e.step(0, False, False)
    chk(any(x[0] == "golpe" for x in ev), "chocar se avisa")
    chk(e.lives == VIDAS - 1, "y cuesta una vida")
    chk(not e.over, "pero la partida sigue")
    chk(e.gracia > 0, "y quedas intocable un rato")


def test_el_escudo_aguanta_el_primero():
    e = limpio()
    e.gracia = 0
    e._tomar(ESCUDO, [])
    e.rocas = [Roca(e.x, e.y, GRANDE, 0.0, e.rng)]
    ev = e.step(0, False, False)
    chk(any(x[0] == "escudo_roto" for x in ev), "el escudo se lleva el golpe")
    chk(e.lives == VIDAS, "y no pierdes vida")
    chk(not e.escudo, "pero se gasta")


def test_sin_vidas_se_acaba():
    e = limpio()
    for _ in range(VIDAS):
        e.gracia = 0
        e.escudo = 0
        e.rocas = [Roca(e.x, e.y, GRANDE, 0.0, e.rng)]
        e.step(0, False, False)
    chk(e.lives == 0 and e.over, "sin vidas, se termina")


# --- el cazador ---------------------------------------------------------------
def test_el_cazador_te_sigue_y_te_tira():
    e = limpio()
    e.cazador = Cazador(10, 100, e.rng)
    e.x, e.y = 200, 100
    x0 = e.cazador.x
    for _ in range(30):
        e._cazador([])
    chk(e.cazador.x != x0, "el cazador se mueve")
    e.cazador.t = 1
    ev = []
    e._cazador(ev)
    chk(any(x[0] == "caza_tira" for x in ev), "y te dispara")
    chk(any(not t[5] for t in e.tiros), "con un tiro que no es tuyo")


def test_el_cazador_aguanta_dos_tiros_y_paga_bien():
    e = limpio()
    e.cazador = Cazador(120, 100, e.rng)
    e.tiros = [[120, 100, 0.0, 0.0, 30, 1]]
    e._mover_tiros([])
    chk(e.cazador is not None, "el primer tiro no lo baja")
    e.tiros = [[120, 100, 0.0, 0.0, 30, 1]]
    ev = []
    e._mover_tiros(ev)
    chk(e.cazador is None, "el segundo sí")
    chk(e.score == CAZADOR_VALE, "y paga %d" % CAZADOR_VALE)


def test_el_cazador_llega_con_la_oleada_4():
    e = nuevo(seed=8)
    e.caza_t = 1
    for _ in range(5):
        e.gracia = 10
        e.step(0, False, False)
    chk(e.cazador is None, "antes de la oleada 4 no hay cazador")
    e.oleada = 3
    e.respiro = 0
    e.oleada_t = 1
    e.gracia = 10
    e.step(0, False, False)
    for _ in range(100):
        e.gracia = 10
        e.step(0, False, False)
    chk(e.cazador is not None, "con la 4, llega")


def test_el_tiro_del_cazador_te_pega():
    e = limpio()
    e.gracia = 0
    e.tiros = [[e.x, e.y, 0.0, 0.0, 30, 0]]      # tiro ajeno, encima tuyo
    ev = e.step(0, False, False)
    chk(any(x[0] == "golpe" for x in ev), "el tiro del cazador te pega")


# --- la cota de los dos minutos ----------------------------------------------
def test_la_partida_cabe_en_dos_minutos():
    """el que no toca nada y el que no se deja tocar nunca."""
    quieto = nuevo(seed=11)
    f = 0
    while not quieto.over and f < DOS_MIN + 600:
        quieto.step(0, False, False)
        f += 1
    chk(quieto.over, "sin tocar nada, la partida termina")
    chk(f <= DOS_MIN, "a tiempo (%d frames)" % f)

    # el intocable: se teletransporta lejos de todo cada frame
    dios = nuevo(seed=12)
    f = 0
    while not dios.over and f < DOS_MIN + 600:
        dios.x, dios.y = dios._lejos(60)
        dios.vx = dios.vy = 0.0
        dios.gracia = 10
        dios.step(0, False, True)
        f += 1
    chk(dios.over, "y el intocable tampoco juega para siempre")
    chk(f <= TIME + 2, "termina cuando se acaba el reloj (%d de %d)" % (f, TIME))
    chk(f <= DOS_MIN, "y cabe en dos minutos (%d frames)" % f)


def test_nada_se_acumula_sin_control():
    e = nuevo(seed=13)
    for _ in range(TIME):
        e.step(1, True, True)
        if e.over:
            break
    chk(len(e.rocas) < 60, "las piedras no se multiplican sin freno (%d)"
        % len(e.rocas))
    chk(len(e.tiros) < 40, "ni los tiros (%d)" % len(e.tiros))
    chk(len(e.powers) < 20, "ni los poderes (%d)" % len(e.powers))
    chk(len(e.minas) < 12, "ni las minas (%d)" % len(e.minas))
    chk(len(e.cometas) < 6, "ni los cometas (%d)" % len(e.cometas))


def test_un_buen_jugador_no_acumula_piedras():
    """el que no se muere y dispara siempre (lo peor para el rendimiento:
    juega los 90 s y llegan todas las oleadas y la tormenta)."""
    e = nuevo(seed=15)
    pico = 0
    while not e.over:
        e.gracia = 10
        e.step(1, False, True)
        pico = max(pico, len(e.rocas) + len(e.minas))
    chk(pico < 60, "el campo no se desborda (pico %d)" % pico)


def test_el_campo_nunca_queda_vacio():
    e = limpio(seed=14)
    e.respiro = 0
    e.oleada_t = 5
    for _ in range(400):
        e.step(0, False, False)
    chk(e.rocas, "siempre entra piedra nueva: el campo no se vacía")


def test_la_pantalla_va_parada():
    """en el celular vertical llena la pantalla: ancho de 216 a 256 px y alto
    entre 1,45 y 1,6 veces el ancho (y el game.toml dice lo mismo)."""
    import os
    import tomllib
    chk(216 <= W <= 256 and 1.45 <= H / W <= 1.6, "%dx%d va parada" % (W, H))
    with open(os.path.join(os.path.dirname(__file__), "game.toml"), "rb") as f:
        g = tomllib.load(f)["game"]
    chk((g["width"], g["height"]) == (W, H), "y el game.toml lo sabe (%sx%s)"
        % (g["width"], g["height"]))


if __name__ == "__main__":
    for fn in (test_la_pantalla_va_parada, test_el_campo_da_la_vuelta, test_la_distancia_cuenta_la_vuelta,
               test_la_nave_empuja_hacia_donde_mira,
               test_la_inercia_no_se_frena_sola_rapido, test_los_frenos,
               test_la_velocidad_tiene_tope, test_la_grande_se_parte_en_dos,
               test_la_chica_no_se_parte,
               test_desarmar_entera_paga_mas_que_reventar_la_grande,
               test_las_roturas_seguidas_hacen_combo,
               test_la_dorada_entra_vale_y_se_va,
               test_el_tiro_rompe, test_disparar_tiene_cadencia,
               test_mantener_fuego_dispara_parejo,
               test_la_rafaga_dobla_la_cadencia,
               test_la_mina_estalla_y_arrastra, test_tocar_una_mina_duele,
               test_el_cometa_avisa_cruza_y_paga,
               test_las_oleadas_se_limpian_y_vuelven,
               test_la_nova_revienta_alrededor, test_la_tormenta_vale_doble,
               test_el_triple_dispara_tres,
               test_chocar_una_piedra_cuesta_una_vida,
               test_el_escudo_aguanta_el_primero, test_sin_vidas_se_acaba,
               test_el_cazador_te_sigue_y_te_tira,
               test_el_cazador_aguanta_dos_tiros_y_paga_bien,
               test_el_cazador_llega_con_la_oleada_4,
               test_el_tiro_del_cazador_te_pega,
               test_la_partida_cabe_en_dos_minutos,
               test_nada_se_acumula_sin_control,
               test_un_buen_jugador_no_acumula_piedras,
               test_el_campo_nunca_queda_vacio):
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
