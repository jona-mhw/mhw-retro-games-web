"""pruebas de pong, sin ventana: PYTHONPATH=. python -m games.pong.test_pong

la física vive en la clase Pong, sin pyxel. lo que más importa acá: que ni el
peloteo perfecto estire la partida más allá de dos minutos.
"""
import random

from games.pong.game import (BLINDADO, CORTA, COURT, CPU_TOPE, CX, ESCUDO,
                             GANADOR_VALE, H, LADRILLOS, LADRILLO_VALE, LARGA,
                             LENTO, MAQUINA, MAX_BALLS, MULTI, NUCLEO, ORO_T,
                             PH_CORTA, PH_LARGA, PHALF, PUNTO_VALE, PX, Pong,
                             RACHA_CADA, RACHA_VALE, RONDA_T, SAQUE,
                             SMASH_CARGA, SMASH_V, SMASH_VENTANA, TIME, TO_WIN,
                             TURBO, W, YO)

FALLAS = []
DOS_MIN = 2 * 60 * 60


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def nueva(seed=7):
    return Pong(rng=random.Random(seed))


# --- básicos -----------------------------------------------------------------
def test_inicio():
    p = nueva()
    chk(len(p.balls) == 1, "arranca con una pelota")
    chk(p.pscore == 0 and p.cscore == 0, "y el tanteo en cero")
    chk(p.time == TIME and not p.over, "y el round entero por delante")


def test_la_paleta_no_se_sale():
    p = nueva()
    p.set_player(-999)
    chk(p.py >= COURT + p.ph_p, "la paleta no se va por arriba")
    p.set_player(9999)
    chk(p.py <= H - p.ph_p, "ni por abajo")


def test_rebote_en_tu_paleta():
    p = nueva()
    p.py = 80
    p.balls = [[PX - 3, 80, 2.0, 0.0, 0]]
    p.step()
    chk(p.balls[0][2] < 0, "la pelota se vuelve para el otro lado")
    chk(p.rallies == 1, "y suma al peloteo")
    chk(p.balls[0][4] == YO, "la pelota queda 'tuya'")


def test_rebote_arriba_y_abajo():
    p = nueva()
    p.balls = [[W / 2, COURT + 2, 0.0, -2.0, 0]]
    p.step()
    chk(p.balls[0][3] > 0, "rebota contra el techo")
    p.balls = [[W / 2, H - 2, 0.0, 2.0, 0]]
    p.step()
    chk(p.balls[0][3] < 0, "y contra el piso")


def test_el_punto_se_anota():
    p = nueva()
    p.cy = H - 6                        # las paletas, lejos de la pelota, para
    p.py = H - 6                        # que no la salven por accidente
    p.balls = [[1, COURT + 4, -3.0, 0.0, 0]]
    p.step()
    chk(p.pscore == 1, "si se le pasa a la máquina, es tu punto")
    chk(p.score == PUNTO_VALE, "y el punto paga %d (%d)" % (PUNTO_VALE, p.score))
    p.saque = 0
    p.balls = [[W - 1, COURT + 4, 3.0, 0.0, 0]]
    p.step()
    chk(p.cscore == 1, "y al revés también")


def test_la_maquina_persigue_pero_se_le_puede_ganar():
    p = nueva()
    p.balls = [[W / 2, H - 6, -2.0, 0.0, 0]]
    p.cy = COURT + 20
    y0 = p.cy
    for _ in range(10):
        p._mover_cpu()
    chk(p.cy > y0, "la máquina va hacia la pelota")
    v0 = p.cpu_speed()
    p.rallies = 200
    chk(p.cpu_speed() > v0, "y se pone brava con el peloteo")
    chk(p.cpu_speed() <= CPU_TOPE, "pero tiene techo: siempre se le puede ganar")
    for t in (TIME, TIME - RONDA_T, TIME - 2 * RONDA_T, 1):
        p.time = t + 1
        p.balls = []
        p.step()
        chk(p.cpu_speed() <= CPU_TOPE, "el techo vale en todas las rondas")


def test_la_maquina_apunta_a_la_que_le_viene():
    """con multibola, seguir la equivocada es lo que la hace fallar."""
    p = nueva()
    p.cy = (COURT + H) / 2
    p.balls = [[W - 30, COURT + 5, 3.0, 0.0, 0],     # ésta se aleja
               [60, H - 10, -2.0, 0.0, 0]]           # ésta le viene
    y0 = p.cy
    for _ in range(6):
        p._mover_cpu()
    chk(p.cy > y0, "persigue la que se le viene encima, no la otra")


# --- poderes -----------------------------------------------------------------
def test_la_larga_y_la_corta():
    p = nueva()
    p._tomar(LARGA, YO, [])
    chk(p.ph_p == PH_LARGA // 2, "la larga te agranda la paleta")
    chk(p.ttl_p > 0, "y se le acaba sola")
    p2 = nueva()
    p2._tomar(CORTA, YO, [])
    chk(p2.ph_c == PH_CORTA // 2, "la corta le achica la del rival, no la tuya")
    chk(p2.ph_p == PHALF, "(la tuya queda igual)")
    p3 = nueva()
    p3._tomar(CORTA, MAQUINA, [])
    chk(p3.ph_p == PH_CORTA // 2, "si la agarra la máquina, la corta te toca a ti")


def test_el_efecto_caduca():
    p = nueva()
    p._tomar(LARGA, YO, [])
    p.ttl_p = 2
    p.balls = []
    p.step()
    p.step()
    chk(p.ph_p == PHALF, "cuando se acaba el efecto, la paleta vuelve a lo normal")


def test_multibola():
    p = nueva()
    n0 = len(p.balls)
    p._tomar(MULTI, YO, [])
    chk(len(p.balls) == n0 + 2, "la multibola mete dos más")
    for _ in range(5):
        p._tomar(MULTI, YO, [])
    chk(len(p.balls) <= MAX_BALLS, "pero no más de %d en la cancha" % MAX_BALLS)


def test_turbo():
    p = nueva()
    v0 = abs(p.balls[0][2])
    p._tomar(TURBO, YO, [])
    chk(abs(p.balls[0][2]) > v0, "el turbo acelera lo que hay en juego")


def test_la_pelota_activa_la_caja():
    p = nueva()
    p.powers = [[110, 90, LARGA, 300]]
    p.balls = [[110, 90, 1.0, 0.0, YO]]
    ev = p.step()
    chk(any(e[0] == "power" for e in ev), "pegarle a la caja la activa")
    chk(not p.powers, "y la caja desaparece")
    chk(p.ph_p == PH_LARGA // 2, "a favor de quien tocó la pelota último")


def test_la_caja_es_del_ultimo_que_toco():
    p = nueva()
    p.powers = [[110, 90, LARGA, 300]]
    p.balls = [[110, 90, -1.0, 0.0, MAQUINA]]
    p.step()
    chk(p.ph_c == PH_LARGA // 2, "si venía de la máquina, el poder es suyo")
    chk(p.ph_p == PHALF, "y a ti no te toca nada")


# --- el muro de ladrillos -----------------------------------------------------
def test_el_muro_arranca_entero():
    p = nueva()
    chk(len(p.muro) == LADRILLOS, "el muro trae %d ladrillos" % LADRILLOS)
    chk(all(l[2] for l in p.muro), "y arrancan todos enteros")
    chk(all(l[0] > CX for l in p.muro), "del lado de la máquina")


def test_la_pelota_rompe_un_ladrillo():
    p = nueva()
    l = p.muro[4]
    b = [l[0] + 1, l[1] + 3, -2.0, 0.0, YO]
    ev = []
    chk(p._pegar_muro(b, ev), "la pelota pega en el ladrillo")
    chk(not l[2], "y lo rompe")
    chk(b[2] > 0, "y sale rebotada hacia ti")
    chk(any(x[0] == "ladrillo" for x in ev), "avisando")
    chk(p.score >= LADRILLO_VALE, "y suma al puntaje (%d)" % p.score)


def test_el_ladrillo_roto_no_vuelve_a_pegar():
    p = nueva()
    l = p.muro[2]
    l[2] = 0
    b = [l[0] + 1, l[1] + 3, -2.0, 0.0, YO]
    chk(not p._pegar_muro(b, []), "un ladrillo ya roto deja pasar la pelota")


def test_el_muro_se_rearma():
    p = nueva()
    for l in p.muro[:-1]:
        l[2] = 0
    ultimo = p.muro[-1]
    b = [ultimo[0] + 1, ultimo[1] + 3, -2.0, 0.0, YO]
    ev = []
    p._pegar_muro(b, ev)
    chk(any(x[0] == "muro_nuevo" for x in ev), "al caer el último, se rearma")
    chk(all(l[2] for l in p.muro), "y vuelve entero")


def test_el_muro_suma_aparte_del_peloteo():
    p = nueva()
    r0, s0 = p.rallies, p.score
    l = p.muro[3]
    p._pegar_muro([l[0] + 1, l[1] + 3, -2.0, 0.0, YO], [])
    chk(p.rallies == r0 + 1, "romper un ladrillo cuenta como devolución")
    chk(p.score == s0 + LADRILLO_VALE, "y el ladrillo paga %d" % LADRILLO_VALE)


# --- el efecto y la racha -----------------------------------------------------
def test_la_paleta_en_movimiento_da_efecto():
    p = nueva()
    p.muro = []
    p.py = 80
    p.set_player(86)                              # viene bajando rápido
    p.balls = [[PX - 3, 84, 2.0, 0.0, 0]]
    p.step()
    b = p.balls[0]
    chk(len(b) > 5 and b[5] > 0, "pegarle bajando deja comba positiva (%.2f)"
        % (b[5] if len(b) > 5 else 0))
    vy0 = b[3]
    for _ in range(20):
        p.set_player(p.py)                        # quieta: no suma comba
        p.step()
    chk(b[3] > vy0, "y la pelota se va curvando hacia abajo (%.2f > %.2f)"
        % (b[3], vy0))
    comba = b[5]
    for _ in range(200):
        p.step()
        if not p.balls or p.balls[0] is not b:
            break
    chk(abs(b[5]) < abs(comba), "la comba se disipa sola")


def test_paleta_quieta_no_da_efecto():
    p = nueva()
    p.muro = []
    p.py = 80
    p.set_player(80)
    p.balls = [[PX - 3, 80, 2.0, 0.0, 0]]
    p.step()
    chk(p.balls[0][5] == 0.0, "sin moverte, la pelota sale derecha")


def test_la_racha_paga_cada_diez():
    p = nueva()
    p.muro = []
    ev = []
    for i in range(RACHA_CADA):
        p.balls = [[PX - 3, p.py, 2.0, 0.0, 0]]
        p.set_player(p.py)
        ev += p.step()
    chk(p.racha == RACHA_CADA, "diez devoluciones seguidas hacen racha")
    chk(any(e[0] == "racha" and e[2] == RACHA_VALE for e in ev),
        "y pagan %d, avisando" % RACHA_VALE)
    chk(p.score == RACHA_CADA + RACHA_VALE, "y entra al puntaje (%d)" % p.score)
    s_racha = p.score
    p.balls = [[W - 1, COURT + 4, 3.0, 0.0, 0]]  # la máquina te saca el punto
    ev = p.step()
    chk(p.racha == 0, "perder un punto corta la racha")
    chk(any(e[0] == "racha_rota" for e in ev), "y avisa que se cortó")
    chk(p.score == s_racha, "pero lo ganado no se pierde")


# --- la cota de los dos minutos ----------------------------------------------
def test_la_partida_cabe_en_dos_minutos():
    """el caso que rompía el pong clásico: dos jugadores perfectos peloteando.

    antes se jugaba a 5 puntos y listo: si nadie fallaba, no terminaba nunca.
    ahora el round tiene reloj, así que el peloteo eterno igual se corta.
    """
    p = nueva(seed=11)
    frames = 0
    while not p.over and frames < DOS_MIN + 600:
        if p.balls:                                # jugador perfecto: nunca falla
            objetivo = max(p.balls, key=lambda b: b[0])
            p.set_player(objetivo[1])
        p.cy = p.balls[0][1] if p.balls else p.cy  # y la máquina, tampoco
        p.step()
        frames += 1
    chk(p.over, "el peloteo perfecto también se termina")
    chk(frames <= TIME + 2, "justo cuando se acaba el reloj (%d de %d)"
        % (frames, TIME))
    chk(frames <= DOS_MIN, "y cabe en dos minutos (%d frames)" % frames)
    chk(p.rallies > 50, "y mientras tanto se peloteó de verdad (%d)" % p.rallies)


def test_tambien_termina_por_puntos():
    """la otra salida: si te golean, se acaba antes de que suene el reloj."""
    p = nueva(seed=12)
    frames = 0
    while not p.over and frames < DOS_MIN:
        p.py = COURT + p.ph_p                      # el jugador no juega
        p.step()
        frames += 1
    chk(p.over, "sin defender, la partida se acaba")
    chk(p.cscore >= TO_WIN or p.time == 0,
        "por goleada (%d) o por reloj" % p.cscore)


def test_siempre_hay_pelota():
    """si se van todas, saca de nuevo: la cancha no puede quedar muerta."""
    p = nueva(seed=13)
    for _ in range(600):
        p.step()
        if p.over:
            break
        chk(len(p.balls) >= 1, "siempre queda al menos una pelota en juego")
        if FALLAS:
            break


# --- el smash ----------------------------------------------------------------
def _devolver(p, n):
    """n devoluciones limpias, sin muro ni cajas que molesten."""
    for _ in range(n):
        p.balls = [[PX - 3, p.py, 2.0, 0.0, 0]]
        p.set_player(p.py)
        p.step()


def test_el_smash_se_carga_y_se_pega():
    p = nueva()
    p.muro = []
    chk(not p.pedir_smash(), "sin carga, el botón no hace nada")
    _devolver(p, SMASH_CARGA)
    chk(p.carga == SMASH_CARGA, "cada devolución carga el smash")
    chk(p.pedir_smash(), "con la carga llena, el botón abre la ventana")
    chk(p.smash_t > 0, "(la ventana queda abierta)")
    p.balls = [[PX - 3, p.py, 2.0, 0.0, 0]]
    ev = p.step()
    b = p.balls[0]
    chk(any(e[0] == "smash" for e in ev), "pegar dentro de la ventana es smash")
    chk(b[2] == -SMASH_V, "la pelota sale rapidísima (%.1f)" % b[2])
    chk(b[6] == YO, "y en llamas")
    chk(p.carga == 0, "y la carga se gasta")


def test_el_smash_errado_no_se_pierde():
    p = nueva()
    p.muro = []
    p.carga = SMASH_CARGA
    p.balls = [[W / 2, 60, -2.0, 0.0, 0]]     # la pelota va para el otro lado
    chk(p.pedir_smash(), "se puede apretar en cualquier momento")
    for _ in range(SMASH_VENTANA + 2):
        p.step()
    chk(p.smash_t == 0, "la ventana se cierra sola")
    chk(p.carga == SMASH_CARGA, "pero la carga queda: se puede volver a probar")
    chk(not p.pedir_smash(), "tras un respiro corto")
    for _ in range(40):
        p.step()
    chk(p.pedir_smash(), "y después sí")


def test_la_pelota_en_llamas_atraviesa_el_muro():
    p = nueva()
    l = p.muro[4]
    b = [l[0] + 1, l[1] + 3, -SMASH_V, 0.0, YO, 0.0, YO, 0]
    s0 = p.score
    chk(p._pegar_muro(b, []), "la pelota en llamas pega en el ladrillo")
    chk(not l[2], "y lo rompe")
    chk(b[2] < 0, "pero no rebota: sigue hacia la máquina")
    chk(p.score - s0 == 2 * LADRILLO_VALE, "y el ladrillo paga doble")


def test_el_smash_ganador_paga_extra():
    p = nueva()
    p.cy = H - 6
    p.balls = [[1, COURT + 4, -SMASH_V, 0.0, YO, 0.0, YO, 0]]
    ev = p.step()
    chk(any(e[0] == "ganador" for e in ev), "ganar el punto en llamas se avisa")
    chk(p.score == PUNTO_VALE + GANADOR_VALE, "y paga %d + %d (%d)"
        % (PUNTO_VALE, GANADOR_VALE, p.score))


# --- los muros que cambian ----------------------------------------------------
def _derribar(p):
    ev = []
    n0 = p.muro_n
    for l in list(p.muro):
        while l[2] and p.muro_n == n0:
            p._pegar_muro([l[0] + 1, l[1] + 3, -2.0, 0.0, YO], ev)
        if p.muro_n != n0:
            break
    return ev


def test_cada_muro_trae_otro_patron():
    p = nueva()
    vistos = [p.nombre_muro()]
    for _ in range(4):
        ev = _derribar(p)
        chk(any(e[0] == "muro_nuevo" for e in ev), "derribar el muro trae otro")
        vistos.append(p.nombre_muro())
        chk(all(l[2] for l in p.muro), "que viene entero")
        chk(all(COURT <= l[1] and l[1] + 10 <= H for l in p.muro),
            "y dentro de la cancha")
        chk(all(l[0] > CX for l in p.muro), "del lado de la máquina")
    chk(len(set(vistos)) == 4, "los cuatro patrones aparecen (%s)" % vistos)


def test_el_bunker_tiene_blindados_y_nucleo():
    p = nueva()
    p.muro_n = 3
    p._armar_muro()
    tipos = [l[3] for l in p.muro]
    chk(NUCLEO in tipos and BLINDADO in tipos, "el búnker trae núcleo y blindados")
    n = next(l for l in p.muro if l[3] == NUCLEO)
    golpes = 0
    while n[2]:
        p._pegar_muro([n[0] + 1, n[1] + 3, -2.0, 0.0, YO], [])
        golpes += 1
    chk(golpes == 3, "el núcleo aguanta tres golpes (%d)" % golpes)


def test_el_muro_movil_no_se_sale():
    p = nueva()
    p.muro_n = 2
    p._armar_muro()
    chk(p.muro_vy != 0, "el muro móvil se mueve")
    y0 = p.muro[0][1]
    for _ in range(2000):
        p._mover_muro()
        chk(all(COURT <= l[1] and l[1] + 10 <= H for l in p.muro),
            "y nunca se sale de la cancha")
        if FALLAS:
            break
    chk(p.muro[0][1] != y0, "y de verdad se movió")


# --- rondas, oro, cámara lenta, escudo, saque ----------------------------------
def test_las_rondas_cambian_la_personalidad():
    p = nueva()
    vistas = []
    for _ in range(TIME):
        if p.balls:                              # perfecto, para llegar al final
            p.set_player(max(p.balls, key=lambda b: b[0])[1])
        for e in p.step():
            if e[0] == "ronda":
                vistas.append(e[1])
        if p.over:
            break
    chk(vistas[:2] == [1, 2], "a los 30 y 60 s cambia la máquina (%s)" % vistas)


def test_el_tiempo_de_oro_vale_doble():
    p = nueva()
    p.muro = []
    p.time = ORO_T + 1
    p.balls = [[W / 2, 60, -2.0, 0.0, 0]]
    ev = p.step()
    chk(p.oro and any(e[0] == "oro" for e in ev), "los últimos 15 s son de oro")
    s0 = p.score
    _devolver(p, 1)
    chk(p.score - s0 == 2, "y una devolución vale doble (%d)" % (p.score - s0))


def test_camara_lenta_en_el_punto_decisivo():
    p = nueva()
    p.muro = []
    p.cscore = TO_WIN - 1
    p.py = COURT + p.ph_p                      # tu paleta, lejos
    p.balls = [[W - 50, H - 20, 2.5, 0.0, MAQUINA]]
    t0 = p.time
    ev = []
    for _ in range(4):
        ev += p.step()
    chk(any(e[0] == "lento" for e in ev), "la pelota decisiva va en cámara lenta")
    chk(p.lento > 0, "(y dura un rato)")
    x0 = p.balls[0][0]
    p.step()
    chk(p.balls[0][0] - x0 < 1.5, "la pelota va lenta (%.2f px)" % (p.balls[0][0] - x0))
    chk(p.time == t0 - 5, "pero el reloj baja igual: uno por frame")
    p2 = nueva()
    p2.py = COURT + p2.ph_p
    p2.balls = [[W - 50, H - 20, 2.5, 0.0, MAQUINA]]
    ev = []
    for _ in range(4):
        ev += p2.step()
    chk(not any(e[0] == "lento" for e in ev), "en un punto cualquiera, no")


def test_la_muralla_salva_una_vez():
    p = nueva()
    p.muro = []
    p._tomar(ESCUDO, YO, [])
    p.py = COURT + p.ph_p
    p.balls = [[W - 2, H - 20, 3.0, 0.0, 0]]
    ev = p.step()
    chk(any(e[0] == "escudo" for e in ev), "la muralla salva la pelota")
    chk(p.cscore == 0 and p.balls[0][2] < 0, "y la devuelve")
    p.balls = [[W - 2, H - 20, 3.0, 0.0, 0]]
    p.step()
    chk(p.cscore == 1, "pero una sola vez")


def test_el_saque_espera_y_el_reloj_no():
    p = nueva()
    p.cy = H - 6
    p.py = H - 6
    p.balls = [[1, COURT + 4, -3.0, 0.0, 0]]
    p.step()
    chk(p.saque == SAQUE, "tras el punto, la pelota espera en el medio")
    x0, t0 = p.balls[0][0], p.time
    for _ in range(SAQUE - 1):
        p.step()
    chk(p.balls[0][0] == x0, "quieta durante el saque")
    chk(p.time == t0 - (SAQUE - 1), "con el reloj corriendo")
    p.step()
    p.step()
    chk(p.balls[0][0] != x0, "y después sale")


def test_ni_el_smash_estira_el_reloj():
    """un jugador perfecto que además smashea todo lo que puede: pausas de
    golpe, cámara lenta y saques no le agregan ni un frame a la partida."""
    for seed in (31, 32, 33):
        p = nueva(seed=seed)
        frames = 0
        while not p.over and frames < DOS_MIN + 600:
            if p.balls:
                objetivo = max(p.balls, key=lambda b: b[0])
                p.set_player(objetivo[1])
            p.pedir_smash()
            p.step()
            frames += 1
        chk(p.over and frames <= TIME + 2, "termina con el reloj o antes "
            "(%d de %d)" % (frames, TIME))
        chk(p.smashes >= 3, "(y smasheó de verdad: %d)" % p.smashes)


if __name__ == "__main__":
    for fn in (test_inicio, test_la_paleta_no_se_sale, test_rebote_en_tu_paleta,
               test_rebote_arriba_y_abajo, test_el_punto_se_anota,
               test_la_maquina_persigue_pero_se_le_puede_ganar,
               test_la_maquina_apunta_a_la_que_le_viene,
               test_la_larga_y_la_corta, test_el_efecto_caduca, test_multibola,
               test_turbo, test_la_pelota_activa_la_caja,
               test_la_caja_es_del_ultimo_que_toco,
               test_el_muro_arranca_entero,
               test_la_pelota_rompe_un_ladrillo,
               test_el_ladrillo_roto_no_vuelve_a_pegar,
               test_el_muro_se_rearma,
               test_la_paleta_en_movimiento_da_efecto,
               test_paleta_quieta_no_da_efecto, test_la_racha_paga_cada_diez,
               test_el_muro_suma_aparte_del_peloteo,
               test_la_partida_cabe_en_dos_minutos,
               test_tambien_termina_por_puntos, test_siempre_hay_pelota,
               test_el_smash_se_carga_y_se_pega,
               test_el_smash_errado_no_se_pierde,
               test_la_pelota_en_llamas_atraviesa_el_muro,
               test_el_smash_ganador_paga_extra,
               test_cada_muro_trae_otro_patron,
               test_el_bunker_tiene_blindados_y_nucleo,
               test_el_muro_movil_no_se_sale,
               test_las_rondas_cambian_la_personalidad,
               test_el_tiempo_de_oro_vale_doble,
               test_camara_lenta_en_el_punto_decisivo,
               test_la_muralla_salva_una_vez,
               test_el_saque_espera_y_el_reloj_no,
               test_ni_el_smash_estira_el_reloj):
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
