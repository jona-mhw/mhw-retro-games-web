"""pruebas de esquiva, sin ventana: PYTHONPATH=. python -m games.esquiva.test_esquiva

la lógica vive en la clase Esquiva, sin pyxel. lo que más importa acá: que la
partida termine sí o sí dentro de los dos minutos, con o sin jugador.
"""
import random

from games.esquiva.game import (BARRA, HUD, NUCLEO_H, PH, AMMO0, AMMO_MAX, BUSCA, BUSCA_VALE, DURA,
                                FASES, FINAL_EN, FIRE_GAP, FRENESI, IMAN,
                                JEFE_H, JEFE_HP, JEFE_VALE, JEFE_W,
                                ESCUDO, Esquiva, GEM_CADENA_CADA,
                                GEM_CADENA_MAX, GEM_VALE, H, NUCLEO_HP,
                                NUCLEO_VALE, Nucleo, NUCLEO_Y, OH, PLAYER_Y,
                                PW, RAFAGA, RALENTI, RAYO_AVISO, RAYO_W,
                                RECARGA, ROCA, ROCE_DIST, ROCE_VALE, SHOT_V,
                                ROMPER_VALE, SLOW_F, TIME, VIDA, VIDAS, W,
                                ZIGZAG)

FALLAS = []
DOS_MIN = 2 * 60 * 60


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def nueva(seed=99):
    return Esquiva(rng=random.Random(seed))


def _roca_encima(e, tipo=ROCA, w=16):
    """una roca justo sobre la nave, para provocar el choque."""
    return [e.px, PLAYER_Y - OH + 2, w, tipo, 0.0, 2 if tipo == DURA else 1]


# --- básicos -----------------------------------------------------------------
def test_inicio():
    e = nueva()
    chk(e.lives == VIDAS, "arranca con %d vidas" % VIDAS)
    chk(e.ammo == AMMO0, "y con %d balas" % AMMO0)
    chk(e.time == TIME and not e.over, "y con el reloj lleno")


def test_no_se_sale_de_la_pantalla():
    e = nueva()
    e.set_player(-100)
    chk(e.px == 0, "la nave no se va por la izquierda")
    e.set_player(9999)
    chk(e.px == W - PW, "ni por la derecha")


def test_esquivar_suma():
    e = nueva()
    vieja = [0, H - 1, 16, ROCA, 0.0, 1]
    e.rocks = [vieja]
    e.px = W - PW                       # la nave, lejos de esa roca
    e.step()
    chk(e.score >= 1, "dejar pasar un bloque suma")
    chk(vieja not in e.rocks, "y ese bloque se va de la lista")
    chk(e.esquivados == 1, "y cuenta como esquivado")


def test_la_arena_vertical_cabe():
    chk(H / W >= 1.45 and 216 <= W <= 256, "la arena es vertical (%dx%d)" % (W, H))
    chk(HUD < NUCLEO_Y and NUCLEO_Y + NUCLEO_H < PLAYER_Y - 100,
        "el núcleo flota arriba, lejos de la nave")
    chk(PLAYER_Y + PH + 8 <= BARRA, "la nave y su llama caben sobre el cargador")


# --- vidas y gracia ----------------------------------------------------------
def test_el_golpe_saca_una_vida_no_la_partida():
    e = nueva()
    e.rocks = [_roca_encima(e)]
    ev = e.step()
    chk(any(x[0] == "golpe" for x in ev), "el golpe se avisa")
    chk(e.lives == VIDAS - 1, "te saca una vida")
    chk(not e.over, "pero la partida sigue")
    chk(e.gracia > 0, "y quedas intocable un rato")


def test_la_gracia_te_protege():
    e = nueva()
    e.rocks = [_roca_encima(e)]
    e.step()
    vidas = e.lives
    for _ in range(10):
        e.rocks = [_roca_encima(e)]
        e.step()
    chk(e.lives == vidas, "durante la gracia no te pueden volver a pegar")


def test_sin_vidas_se_acaba():
    e = nueva()
    for _ in range(VIDAS):
        e.gracia = 0
        e.rocks = [_roca_encima(e)]
        e.step()
    chk(e.lives == 0 and e.over, "sin vidas, se termina")


# --- disparo -----------------------------------------------------------------
def test_disparar_gasta_y_se_acaba():
    e = nueva()
    for i in range(AMMO0):
        e.cool = 0
        chk(e.disparar(), "puedes disparar mientras tengas balas (%d)" % i)
    e.cool = 0
    chk(not e.disparar(), "sin munición, no dispara")
    chk(e.ammo == 0, "y el contador queda en cero")


def test_mantener_apretado_tiene_cadencia():
    e = nueva()
    chk(e.disparar(), "el primer tiro sale")
    chk(not e.disparar(), "el segundo no, en el mismo frame: hay cadencia")
    for _ in range(FIRE_GAP):
        e.step()
    chk(e.disparar(), "y pasada la cadencia, sale otro")


def test_la_municion_se_recarga_sola():
    """el bug del celular: al vaciarse el cargador, el botón quedaba muerto
    para siempre. ahora vuelve una bala por RECARGA frames, sin hacer nada."""
    e = nueva()
    e.rocks = []
    e.spawn_t = 10 ** 6
    e.ammo = 0
    e.carga = 0
    ev = []
    for _ in range(RECARGA):
        ev += e.step()
    chk(e.ammo == 1, "al rato vuelve una bala (hay %d)" % e.ammo)
    chk(any(x[0] == "recarga" for x in ev), "y se avisa, para el medidor")
    for _ in range(RECARGA * (AMMO_MAX + 2)):
        e.step()
        e.spawn_t = 10 ** 6
        e.rocks = []
        e.gracia = 10
    chk(e.ammo == AMMO_MAX, "y se llena hasta el tope (%d)" % e.ammo)
    chk(e.carga_frac() == 1.0, "con el medidor lleno")


def test_mantener_fuego_nunca_se_traba():
    """un jugador que mantiene el fuego toda la partida sigue disparando
    hasta el final: el ritmo baja al de la recarga, pero nunca a cero."""
    e = nueva(seed=5)
    tiros_por_tramo = []
    n0 = 0
    f = 0
    while not e.over:
        e.disparar()
        e.gracia = 10                     # que no se muera, para medir todo
        e.step()
        f += 1
        if f % (10 * 60) == 0:
            tiros_por_tramo.append(e.disparos - n0)
            n0 = e.disparos
    chk(all(t >= 8 for t in tiros_por_tramo),
        "cada 10 s salen tiros, siempre (%s)" % tiros_por_tramo)


def test_la_bala_rompe_el_bloque():
    e = nueva()
    e.rocks = [[e.px, PLAYER_Y - 40, 20, ROCA, 0.0, 1]]
    e.shots = [[e.px + 5, PLAYER_Y - 30]]
    ev = []
    for _ in range(12):
        ev += e.step()
        if not e.rocks:
            break
    chk(any(x[0] == "rompe" for x in ev), "la bala rompe el bloque")
    chk(e.score >= ROMPER_VALE, "y eso suma (%d)" % e.score)


def test_el_bloque_duro_aguanta_dos():
    e = nueva()
    e.rocks = [[50, 50, 20, DURA, 0.0, 2]]
    e.shots = [[55, 50 + SHOT_V + 1]]
    ev = e._mover_balas()
    chk(any(x[0] == "raspa" for x in ev), "el primer tiro sólo lo raspa")
    chk(e.rocks and e.rocks[0][5] == 1, "y le queda un golpe")
    e.shots = [[55, 50 + SHOT_V + 1]]
    ev = e._mover_balas()
    chk(any(x[0] == "rompe" for x in ev), "el segundo sí lo rompe")


# --- gemas y poderes ---------------------------------------------------------
def test_la_gema_vale():
    e = nueva()
    e.gems = [[e.px + PW / 2, PLAYER_Y + 2]]
    ev = e.step()
    chk(any(x[0] == "gema" for x in ev), "juntar una gema se avisa")
    chk(e.score >= GEM_VALE, "y vale %d (dio %d)" % (GEM_VALE, e.score))


def test_las_gemas_seguidas_valen_mas():
    e = nueva()
    for i in range(GEM_CADENA_CADA):
        e.gems = [[e.px + PW / 2, PLAYER_Y + 2]]
        ev = e.step()
    chk(e.gem_cadena == GEM_CADENA_CADA, "tres gemas seguidas hacen cadena")
    chk(any(x[0] == "cadena" for x in ev), "y se avisa")
    chk(e.gem_mult() == 2, "y la próxima vale por dos")
    s0 = e.score
    e.gems = [[e.px + PW / 2, PLAYER_Y + 2]]
    ev = e.step()
    g = [x for x in ev if x[0] == "gema"][0]
    chk(g[3] == GEM_VALE * 2, "de verdad (+%d)" % g[3])
    e.gem_cadena = 999
    chk(e.gem_mult() == GEM_CADENA_MAX, "con techo en x%d" % GEM_CADENA_MAX)
    e.gracia = 0
    e.rocks = [_roca_encima(e)]
    ev = e.step()
    chk(e.gem_cadena == 0, "un golpe corta la cadena")
    chk(any(x[0] == "cadena_rota" for x in ev), "y avisa")


def test_rozar_un_bloque_suma():
    e = nueva()
    e.gracia = 0
    e.px = 100
    cerca = [100 + PW + ROCE_DIST - 1, PLAYER_Y - 2, 16, ROCA, 0.0, 1]
    e.rocks = [cerca]
    s0 = e.score
    ev = e.step()
    chk(any(x[0] == "roce" for x in ev), "un bloque que pasa a un pelo se avisa")
    chk(e.score == s0 + ROCE_VALE, "y suma %d" % ROCE_VALE)
    chk(e.lives == VIDAS, "sin tocarte")
    e.step()
    chk(e.roces == 1, "y cada bloque roza una sola vez")
    lejos = [100 + PW + ROCE_DIST + 10, PLAYER_Y - 2, 16, ROCA, 0.0, 1]
    e.rocks = [lejos]
    ev = e.step()
    chk(not any(x[0] == "roce" for x in ev), "uno que pasa lejos, no")
    e.gracia = 50
    e.rocks = [[100 + PW + 1, PLAYER_Y - 2, 16, ROCA, 0.0, 1]]
    ev = e.step()
    chk(not any(x[0] == "roce" for x in ev), "y estando intocable tampoco cuenta")


def test_los_poderes_hacen_lo_suyo():
    e = nueva()
    e._tomar(ESCUDO, [])
    chk(e.escudo, "el escudo pone la burbuja")
    e.gracia = 0
    e.rocks = [_roca_encima(e)]
    ev = e.step()
    chk(e.lives == VIDAS, "la burbuja aguanta el golpe")
    chk(any(x[0] == "escudo_roto" for x in ev) and not e.escudo,
        "y se rompe avisando")
    e.lives = 1
    e._tomar(VIDA, [])
    chk(e.lives == 2, "la vida extra devuelve una vida")
    e.lives = VIDAS
    e.escudo = False
    e._tomar(VIDA, [])
    chk(e.lives == VIDAS and e.escudo, "con las vidas llenas, se vuelve escudo")
    e.ammo = 0
    e._tomar(RAFAGA, [])
    chk(e.ammo == AMMO_MAX and e.rafaga, "la ráfaga llena el cargador")
    n = e.ammo
    e.cool = 0
    e.shots = []
    e.disparar()
    chk(len(e.shots) == 2 and e.ammo == n, "y dispara doble sin gastar")
    e.slow = 0
    v0 = e.speed()
    e._tomar(RALENTI, [])
    chk(e.speed() < v0, "el ralentí frena todo (%.2f -> %.2f)" % (v0, e.speed()))
    chk(abs(e.speed() - v0 * SLOW_F) < 1e-6, "y frena en la proporción justa")


def test_el_iman_trae_las_gemas():
    e = nueva()
    e.spawn_t = 10 ** 6
    e._tomar(IMAN, [])
    e.gems = [[e.px + PW / 2 + 50, PLAYER_Y - 40]]
    s0 = e.score
    for _ in range(60):
        e.step()
        e.spawn_t = 10 ** 6
        e.rocks = []
    chk(not e.gems and e.score > s0, "con imán, una gema cercana viene sola")


def test_el_buscador_te_sigue_y_paga():
    e = nueva()
    e.spawn_t = 10 ** 6
    e.px = 150
    b = [20, 60, 9, BUSCA, 0.0, 1, 0]
    e.rocks = [b]
    for _ in range(40):
        e.step()
        e.spawn_t = 10 ** 6
    chk(b[0] > 20, "el buscador se corre hacia la nave (%.0f)" % b[0])
    e.rocks = [[50, 50, 9, BUSCA, 0.0, 1, 0]]
    e.shots = [[54, 50 + SHOT_V + 1]]
    s0 = e.score
    ev = e._mover_balas()
    chk(any(x[0] == "rompe" for x in ev), "un tiro lo rompe")
    chk(e.score - s0 == BUSCA_VALE, "y paga %d" % BUSCA_VALE)


def test_el_rayo_avisa_y_despues_quema():
    e = nueva()
    e.spawn_t = 10 ** 6
    e.gracia = 0
    ev = []
    e._rayo(e.px + PW / 2, ev)
    chk(any(x[0] == "rayo_aviso" for x in ev), "el rayo avisa primero")
    for _ in range(RAYO_AVISO - 2):
        e.step()
        e.spawn_t = 10 ** 6
    chk(e.lives == VIDAS, "durante el aviso no hace daño")
    for _ in range(4):
        e.step()
    chk(e.lives == VIDAS - 1, "si te quedas en la columna, te quema")
    e2 = nueva()
    e2.gracia = 0
    e2._rayo(e2.px + PW / 2, [])
    e2.set_player(e2.px + RAYO_W + PW)
    for _ in range(RAYO_AVISO + 10):
        e2.step()
        e2.spawn_t = 10 ** 6
    chk(e2.lives == VIDAS, "y si te mueves del aviso, te salvas")


def test_las_oleadas_se_anuncian():
    e = nueva()
    vistas = []
    while not e.over:
        e.gracia = 10
        for x in e.step():
            if x[0] == "fase":
                vistas.append(x[1])
    chk(vistas == list(range(2, len(FASES) + 1)),
        "cada oleada se anuncia una vez y en orden (%s)" % vistas)


def test_el_frenesi_vale_doble():
    e = nueva()
    e.time = FRENESI - 1
    e.gems = [[e.px + PW / 2, PLAYER_Y + 2]]
    s0 = e.score
    e.step()
    chk(e.score - s0 >= GEM_VALE * 2, "en el frenesí una gema vale doble (%d)"
        % (e.score - s0))


def test_el_zigzag_rebota_en_los_bordes():
    e = nueva()
    e.slow = 0
    r = [W - 20, 40, 16, ZIGZAG, 0.9, 1]
    e.rocks = [r]
    e.px = 0                                  # la nave, lejos
    for _ in range(30):
        e.step()
        if r[4] < 0:
            break
    chk(r[4] < 0, "el bloque que zigzaguea rebota contra el borde")
    chk(0 <= r[0] <= W - r[2], "y no se sale de la pantalla")


# --- el jefe -----------------------------------------------------------------
def test_el_jefe_entra_solo_y_baja():
    e = nueva()
    e.jefe_t = 1
    ev = e.step()
    chk(e.jefe is not None, "el muro entra cuando le toca")
    chk(any(x[0] == "jefe_entra" for x in ev), "y se avisa")
    y0 = e.jefe[1]
    e.step()
    chk(e.jefe[1] > y0, "y baja")


def test_el_jefe_aguanta_varios_tiros():
    e = nueva()
    e.jefe = [50.0, 60.0, JEFE_HP, 0.0]
    for i in range(JEFE_HP - 1):
        e.shots = [[60.0, 60.0 + SHOT_V + 1]]
        e._mover_balas()
        chk(e.jefe is not None, "aguanta el tiro %d" % (i + 1))
    e.shots = [[60.0, 60.0 + SHOT_V + 1]]
    ev = e._mover_balas()
    chk(e.jefe is None, "y cae al último")
    chk(any(x[0] == "jefe_cae" for x in ev), "avisando")
    chk(e.score >= JEFE_VALE, "y paga %d (dio %d)" % (JEFE_VALE, e.score))


def test_el_jefe_suelta_premio_al_caer():
    e = nueva()
    e.jefe = [50.0, 60.0, 1, 0.0]
    e.powers = []
    e.gems = []
    e.shots = [[60.0, 60.0 + SHOT_V + 1]]
    e._mover_balas()
    chk(any(p[2] == RAFAGA for p in e.powers), "el muro deja una ráfaga al caer")
    chk(len(e.gems) >= 3, "y gemas")


def test_solo_dos_muros():
    e = nueva()
    muros = 0
    while not e.over:
        e.gracia = 10
        muros += sum(1 for x in e.step() if x[0] == "jefe_entra")
    chk(muros == 2, "vienen dos muros, el tercero es el núcleo (%d)" % muros)


# --- el núcleo ----------------------------------------------------------------
def test_el_nucleo_entra_al_final():
    e = nueva()
    e.time = FINAL_EN + 1
    e.step()
    chk(e.nucleo is None, "antes de su hora no está")
    ev = e.step()
    chk(e.nucleo is not None, "y entra cuando le toca")
    chk(any(x[0] == "nucleo_entra" for x in ev), "avisando")


def test_el_nucleo_ataca_en_orden():
    e = nueva()
    e.nucleo = Nucleo()
    e.nucleo.y = NUCLEO_Y
    e.nucleo.t = 1
    e.time = FINAL_EN
    ataques = []
    for _ in range(800):
        e.gracia = 10
        for x in e._nucleo():
            if x[0] == "nucleo_ataca":
                ataques.append(x[3])
    chk(ataques[:6] == [0, 1, 2, 0, 1, 2],
        "abanico, rayo, lluvia y vuelta: legible (%s)" % ataques[:6])
    chk(e.balas, "el abanico tira balas")


def test_romper_el_nucleo_gana_la_partida():
    e = nueva()
    e.time = 20 * 60
    e.nucleo = Nucleo()
    e.nucleo.y = NUCLEO_Y
    e.nucleo.hp = 1
    e.rocks = [[10, 60, 16, ROCA, 0.0, 1, 0]]
    cx = e.nucleo.x + 10
    e.shots = [[cx, e.nucleo.y + SHOT_V + 2]]
    s0 = e.score
    ev = e._mover_balas()
    chk(any(x[0] == "nucleo_cae" for x in ev), "el último tiro lo rompe")
    chk(e.score - s0 >= NUCLEO_VALE + 20 * 5,
        "y paga el núcleo y los segundos que sobran (%d)" % (e.score - s0))
    chk(not e.rocks, "la pantalla se limpia")
    f = 0
    while not e.over and f < 1000:
        e.step()
        f += 1
    chk(e.over and f <= 160, "y la partida termina enseguida (%d frames)" % f)
    chk(e.lives == VIDAS, "sin daño en la vuelta olímpica")


def test_el_nucleo_aguanta_varios_tiros():
    e = nueva()
    e.nucleo = Nucleo()
    e.nucleo.y = NUCLEO_Y
    for _ in range(NUCLEO_HP - 1):
        e.shots = [[e.nucleo.x + 10, e.nucleo.y + SHOT_V + 2]]
        e._mover_balas()
    chk(e.nucleo is not None and e.nucleo.hp == 1,
        "aguanta %d tiros" % (NUCLEO_HP - 1))
    chk(e.nucleo.enojado, "y a la mitad se enoja")


def test_el_jefe_te_pega_si_te_alcanza():
    e = nueva()
    e.gracia = 0
    e.jefe = [e.px, PLAYER_Y - JEFE_H + 2, JEFE_HP, 0.0]
    ev = e.step()
    chk(any(x[0] == "golpe" for x in ev), "el muro te lleva puesto")
    chk(e.lives == VIDAS - 1, "y cuesta una vida")
    chk(e.jefe is None, "y se va tras el impacto")


def test_el_jefe_rebota_en_los_bordes():
    e = nueva()
    e.jefe = [float(W - JEFE_W - 2), 40.0, JEFE_HP, 0.9]
    e.px = 0
    for _ in range(20):
        e.step()
        if e.jefe is None or e.jefe[3] < 0:
            break
    chk(e.jefe is not None and e.jefe[3] < 0, "el muro rebota contra el borde")
    chk(0 <= e.jefe[0] <= W - JEFE_W, "y no se sale de la pantalla")


# --- dificultad y cota de duración -------------------------------------------
def test_la_presion_sube_con_el_reloj():
    e = nueva()
    e.slow = 0
    v0, gap0 = e.speed(), e._spawn_gap()
    e.time = TIME // 3
    chk(e.speed() > v0, "cuanto más aguantas, más rápido cae (%.2f -> %.2f)"
        % (v0, e.speed()))
    chk(e._spawn_gap() < gap0, "y más seguido (%d -> %d)"
        % (gap0, e._spawn_gap()))
    chk(e.level() > 1, "y el nivel sube solo con el reloj")


def test_la_partida_cabe_en_dos_minutos():
    """dos extremos: el que no toca nada y el que no se deja tocar nunca."""
    quieto = nueva(seed=1)
    frames = 0
    while not quieto.over and frames < DOS_MIN + 600:
        quieto.step()
        frames += 1
    chk(quieto.over, "sin tocar nada, la partida termina")
    chk(frames <= DOS_MIN, "y dura menos de dos minutos (%d frames)" % frames)

    # el jugador perfecto: cada frame se corre al primer hueco libre (y nada
    # le pega: es la cota del que más tiempo puede jugar)
    dios = nueva(seed=2)
    frames = 0
    while not dios.over and frames < DOS_MIN + 600:
        libre = 0
        for cand in range(0, W - PW, 4):
            if all(not (r[0] < cand + PW and r[0] + r[2] > cand and r[1] > 120)
                   for r in dios.rocks):
                libre = cand
                break
        dios.set_player(libre)
        dios.gracia = 10
        dios.disparar()
        dios.step()
        frames += 1
    chk(dios.over, "y el jugador perfecto tampoco juega para siempre")
    chk(frames <= TIME + 2, "termina justo cuando se acaba el reloj (%d de %d)"
        % (frames, TIME))
    chk(frames <= DOS_MIN, "y cabe en dos minutos (%d frames)" % frames)


def test_nada_queda_colgado():
    """lo que cae se limpia: nada se acumula hasta comerse la memoria."""
    e = nueva(seed=3)
    for _ in range(TIME):
        e.step()
        if e.over:
            break
    chk(len(e.rocks) < 40, "no quedan bloques colgados (%d)" % len(e.rocks))
    chk(len(e.gems) < 30, "ni gemas (%d)" % len(e.gems))
    chk(len(e.powers) < 20, "ni poderes (%d)" % len(e.powers))
    chk(len(e.balas) < 60, "ni balas del núcleo (%d)" % len(e.balas))
    chk(len(e.rayos) < 6, "ni rayos (%d)" % len(e.rayos))
    chk(all(r[1] <= H + OH for r in e.rocks), "y nada quedó abajo de la pantalla")


if __name__ == "__main__":
    for fn in (test_inicio, test_la_arena_vertical_cabe,
               test_no_se_sale_de_la_pantalla, test_esquivar_suma,
               test_el_golpe_saca_una_vida_no_la_partida,
               test_la_gracia_te_protege, test_sin_vidas_se_acaba,
               test_disparar_gasta_y_se_acaba,
               test_mantener_apretado_tiene_cadencia,
               test_la_municion_se_recarga_sola,
               test_mantener_fuego_nunca_se_traba,
               test_la_bala_rompe_el_bloque,
               test_el_bloque_duro_aguanta_dos, test_la_gema_vale,
               test_las_gemas_seguidas_valen_mas, test_rozar_un_bloque_suma,
               test_los_poderes_hacen_lo_suyo, test_el_iman_trae_las_gemas,
               test_el_buscador_te_sigue_y_paga,
               test_el_rayo_avisa_y_despues_quema,
               test_las_oleadas_se_anuncian, test_el_frenesi_vale_doble,
               test_el_zigzag_rebota_en_los_bordes,
               test_el_jefe_entra_solo_y_baja,
               test_el_jefe_aguanta_varios_tiros,
               test_el_jefe_suelta_premio_al_caer, test_solo_dos_muros,
               test_el_nucleo_entra_al_final, test_el_nucleo_ataca_en_orden,
               test_romper_el_nucleo_gana_la_partida,
               test_el_nucleo_aguanta_varios_tiros,
               test_el_jefe_te_pega_si_te_alcanza,
               test_el_jefe_rebota_en_los_bordes,
               test_la_presion_sube_con_el_reloj,
               test_la_partida_cabe_en_dos_minutos, test_nada_queda_colgado):
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
