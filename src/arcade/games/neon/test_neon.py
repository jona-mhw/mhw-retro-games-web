"""pruebas de neón, sin ventana: PYTHONPATH=. python -m games.neon.test_neon

la lógica vive en logic.Neon, sin pyxel. lo que más importa acá: que la partida
termine sí o sí dentro de los dos minutos (con jugador, sin jugador y con un
jugador intocable que no mata a nadie), que el jefe aparezca, y que roces,
bomba, arma y cadena hagan lo que dicen.
"""
import random
import time

from games.neon import bot
from games.neon.logic import (BOMB_T, BOMBS0, BOMBS_MAX, CHAIN_STEP, CRYSTAL_V,
                              DART, END_DELAY, FINAL, GRAZE_PER_BOMB,
                              GRAZE_R, GRAZE_V, ITEM_B, ITEM_P, LEN_A,
                              LIVES, MAX_EB, MINI, MULT_MAX, P_MAX, PELLET,
                              PMAX_V, SEC_BOSS, SEC_END, T_END, TIME_BONUS,
                              Boss, Foe, H, Neon, W)

FALLAS = []
DOS_MIN = 2 * 60 * 60
# lo que la piel le suma al reloj de la lógica, en el peor caso: resultados,
# cámara lenta del jefe y los congelados de impacto
PIEL_MAX = 300 + 100 + 3 * 8 + 2 * 10 + 2 * 12


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def nueva(seed=7):
    g = Neon(rng=random.Random(seed))
    g.inv = 0
    return g


def bala(g, dx, dy, vx=0.0, vy=0.0, kind=PELLET):
    g.eb.append([g.px + dx, g.py + dy, vx, vy, kind, 0, 1.0])


def jugar(g, policy, max_frames=20000):
    n = 0
    while not g.done and n < max_frames:
        g.step(*policy(g))
        n += 1
    return n


# --- básicos -----------------------------------------------------------------
def test_inicio():
    g = nueva()
    chk(g.lives == LIVES and g.bombs == BOMBS0 and g.power == 1,
        "arranca con %d vidas, %d bombas y el arma en 1" % (LIVES, BOMBS0))
    chk(not g.done and g.score == 0, "y sin puntaje")


def test_la_nave_no_se_sale():
    g = nueva()
    for _ in range(200):
        g.step(-50, -50)
    chk(g.px >= 0 and g.py >= 0, "no se va por arriba ni por la izquierda")
    for _ in range(200):
        g.step(50, 50)
    chk(g.px <= W and g.py <= H, "ni por abajo ni por la derecha")


def test_dispara_solo():
    g = nueva()
    for _ in range(12):
        g.step()
    chk(len(g.shots) >= 4, "sin tocar nada, la nave ya disparó (%d)" % len(g.shots))


def test_el_arma_sube_el_fuego():
    tiros = []
    for p in range(1, P_MAX + 1):
        g = nueva()
        g.power = p
        g._volley()
        tiros.append(len(g.shots))
    chk(tiros == sorted(tiros) and tiros[0] < tiros[-1],
        "cada nivel de arma dispara más (%s)" % tiros)


# --- roces ---------------------------------------------------------------------
def test_rozar_paga_una_vez():
    g = nueva()
    g.fire_t = 999                       # que no dispare: sólo medimos el roce
    bala(g, GRAZE_R - 2, -20, 0.0, 2.0)  # pasa al lado, sin tocar
    sc = 0
    for _ in range(25):
        g.step()
    chk(g.grazes == 1, "la bala que pasa cerca es un roce (y uno solo: %d)" % g.grazes)
    chk(g.score >= GRAZE_V, "y paga")
    chk(g.graze_meter == 1, "y carga la bomba")
    chk(g.lives == LIVES, "sin quitarte una vida")
    sc = g.score
    chk(sc > 0, "el roce dejó puntaje")


def test_los_roces_dan_bombas():
    g = nueva()
    g.bombs = 0
    g.graze_meter = GRAZE_PER_BOMB - 1
    g._graze(1, g.px, g.py, [])
    chk(g.bombs == 1, "al llenar la carga de roces se gana una bomba")
    g.bombs = BOMBS_MAX
    g.graze_meter = GRAZE_PER_BOMB - 1
    sc = g.score
    g._graze(1, g.px, g.py, [])
    chk(g.bombs == BOMBS_MAX and g.score > sc + 1000,
        "con las bombas llenas, la carga se paga en puntos")


def test_invulnerable_no_roza():
    g = nueva()
    g.inv = 100
    g.fire_t = 999
    bala(g, GRAZE_R - 2, -20, 0.0, 2.0)
    for _ in range(25):
        g.step()
    chk(g.grazes == 0, "parpadeando después de un golpe no se puede farmear roces")


# --- golpes --------------------------------------------------------------------
def test_el_golpe_saca_una_vida():
    g = nueva()
    g.power = 3
    g.chain = CHAIN_STEP * 4
    bala(g, 0, -1)
    ev = g.step()
    chk(any(e[0] == "hit" for e in ev), "el golpe se avisa")
    chk(g.lives == LIVES - 1 and not g.done, "te saca una vida, no la partida")
    chk(g.power == 2, "el arma baja un nivel")
    chk(any(it[3] == ITEM_P for it in g.items), "y el nivel perdido queda flotando")
    chk(g.mult() == 1, "la cadena se corta")
    chk(not g.eb, "y las balas se borran para que no te maten de nuevo")


def test_reaparece_intocable():
    g = nueva()
    bala(g, 0, -1)
    g.step()
    chk(not g.alive(), "después del golpe no hay nave un rato")
    for _ in range(80):
        g.step()
    chk(g.alive() and g.inv > 0, "y vuelve parpadeando, intocable")
    bala(g, 0, -1)
    g.step()
    chk(g.lives == LIVES - 1, "mientras parpadea no te pueden volver a pegar")


def test_el_hitbox_es_chico():
    g = nueva()
    g.fire_t = 999
    bala(g, 5, 0)            # tocaría el dibujo de la nave, no el puntito
    g.step()
    chk(g.lives == LIVES, "una bala sobre el ala no mata: choca el centro")
    g2 = nueva()
    bala(g2, 0, 1)
    g2.step()
    chk(g2.lives == LIVES - 1, "una bala en el centro sí")


def test_sin_vidas_se_acaba():
    g = nueva()
    g.lives = 1
    bala(g, 0, -1)
    g.step()
    chk(g.sec == SEC_END and g.ending == "derribado", "la última vida termina la partida")
    for _ in range(END_DELAY + 5):
        g.step()
    chk(g.done and g.results["ending"] == "derribado", "y muestra los resultados")


# --- bomba ---------------------------------------------------------------------
def test_la_bomba_limpia():
    g = nueva()
    for i in range(40):
        bala(g, (i % 10) * 15 - 70, -60 - (i // 10) * 12)
    f = Foe(DART, g.px, g.py - 80)
    g.foes.append(f)
    ev = g.step(bomb=True)
    chk(any(e[0] == "bomb" for e in ev), "la bomba se avisa")
    chk(g.bombs == BOMBS0 - 1, "gasta una bomba")
    chk(not g.eb, "borra todas las balas enemigas")
    chk(len(g.crys) >= 15, "y las balas dejan cristales (%d)" % len(g.crys))
    chk(f.dead, "y lastima a los enemigos")
    chk(g.bomb_t > 0 and not g.vulnerable(), "y te deja intocable")
    bala(g, 0, -1)
    g.step()
    chk(g.lives == LIVES and not g.eb, "lo que dispararon recién también se borra")
    for _ in range(60):
        g.step()
    chk(g.crys_got > 0, "los cristales vuelan solos a la nave")


def test_sin_bombas_no_hay_bomba():
    g = nueva()
    g.bombs = 0
    bala(g, 0, -60)
    g.step(bomb=True)
    chk(g.eb and g.bomb_t == 0, "sin bombas, apretar no hace nada")


def test_una_bomba_a_la_vez():
    g = nueva()
    g.step(bomb=True)
    g.step(bomb=True)
    chk(g.bombs == BOMBS0 - 1, "mientras dura una bomba no se gasta otra")
    for _ in range(BOMB_T):
        g.step()
    g.step(bomb=True)
    chk(g.bombs == BOMBS0 - 2, "cuando termina, sí")


# --- ítems y cadena ------------------------------------------------------------
def test_el_power_up():
    g = nueva()
    g.items.append([g.px, g.py, 0.0, ITEM_P, 0])
    ev = g.step()
    chk(g.power == 2 and any(e[0] == "power" for e in ev), "la P sube el arma")
    g.power = P_MAX
    sc = g.score
    g.items.append([g.px, g.py, 0.0, ITEM_P, 0])
    g.step()
    chk(g.power == P_MAX and g.score >= sc + PMAX_V, "con el arma al máximo, la P paga")
    g.bombs = 0
    g.items.append([g.px, g.py, 0.0, ITEM_B, 0])
    g.step()
    chk(g.bombs == 1, "la B da una bomba")


def test_el_iman_de_items():
    g = nueva()
    g.items.append([g.px + 20, g.py - 15, 0.0, ITEM_P, 0])
    for _ in range(30):
        g.step()
    chk(g.power == 2, "un ítem que pasa cerca se deja agarrar")


def test_la_cadena_sube_y_cae():
    g = nueva()
    for i in range(CHAIN_STEP * 3):
        f = Foe(DART, 30, 60)
        g._kill(f, [])
    chk(g.mult() == 4, "matar seguido sube el multiplicador (x%d)" % g.mult())
    sc = g.score
    g._kill(Foe(DART, 30, 60), [])
    chk(g.score - sc == 100 * 4, "y multiplica lo que vale cada enemigo")
    for _ in range(400):
        g._step_chain()                  # sólo el reloj de la cadena
        if g.mult() < 4:
            break
    chk(g.mult() < 4, "sin matar ni rozar, el multiplicador cae")
    chk(g.mult() >= 2, "de a un escalón, no de golpe")
    for i in range(CHAIN_STEP * 20):
        g._kill(Foe(DART, 30, 60), [])
    chk(g.mult() == MULT_MAX, "tope x%d" % MULT_MAX)


def test_los_cristales_pagan_por_la_cadena():
    g = nueva()
    g.chain = CHAIN_STEP * 2              # x3
    g.chain_t = 9999
    g.crys.append([g.px, g.py - 3, 0, 0, 20])
    sc = g.score
    g.fire_t = 999
    g.step()
    chk(g.score - sc == CRYSTAL_V * 3, "un cristal vale %d por el multiplicador"
        % CRYSTAL_V)


def test_escuadron_completo():
    g = nueva()
    g._spawn_swarm(90, 0, 5, 1)
    ev = []
    for f in list(g.foes):
        g._kill(f, ev)
    chk(any(e[0] == "squad" for e in ev), "derribar el escuadrón entero paga bono")
    chk(any(it[3] == ITEM_P for it in g.items), "y este escuadrón suelta una P")


# --- balas ---------------------------------------------------------------------
def test_tope_de_balas():
    g = nueva()
    for i in range(MAX_EB + 100):
        g._shoot(10, 40, 1.0, 0.5)
    chk(len(g.eb) <= MAX_EB, "nunca más de %d balas en pantalla" % MAX_EB)


def test_nadie_dispara_encima():
    g = nueva()
    g._shoot(g.px + 3, g.py - 5, 1.0, 1.0)
    chk(not g.eb, "una bala no puede nacer encima de la nave")


# --- jefes y reloj -------------------------------------------------------------
def test_el_mini_jefe_llega_a_tiempo():
    g = nueva()
    g.inv = 10 ** 9
    llegó = None
    for _ in range(LEN_A + 5):
        for e in g.step():
            if e[0] == "boss_in" and e[1] == MINI:
                llegó = g.t
    chk(llegó is not None and abs(llegó - LEN_A) < 3,
        "el mini-jefe entra a los %.1f s" % (LEN_A / 60))


def test_el_jefe_aparece_con_un_jugador():
    g = nueva(seed=3)
    vistos = set()
    while not g.done and g.t < DOS_MIN:
        for e in g.step(*bot.dodger(g)):
            if e[0] == "boss_in":
                vistos.add(e[1])
    chk(MINI in vistos and FINAL in vistos, "con un buen jugador aparecen los dos jefes")


def test_matar_al_jefe_paga_tiempo():
    g = nueva()
    g.sec = SEC_BOSS
    g.t = T_END - 20 * 60
    g.boss = Boss(FINAL)
    b = g.boss
    b.state, b.phase, b.hp = "fight", 2, 1
    g._hurt_boss(5, [])
    chk(b.state == "die", "el último golpe lo hace explotar")
    for _ in range(400):
        g.step()
        if g.done:
            break
    r = g.results
    chk(g.done and r["ending"] == "victoria", "y es victoria")
    chk(r["time_s"] >= 18 and r["time_bonus"] == r["time_s"] * TIME_BONUS,
        "cada segundo que sobra paga (%d s)" % r["time_s"])
    chk(r["total"] == g.score, "y el bono entra al puntaje")


def test_la_fase_rompe_y_premia():
    g = nueva()
    g.boss = Boss(FINAL)
    b = g.boss
    b.state, b.hp = "fight", 1
    for i in range(30):
        bala(g, i * 3 - 45, -100)
    ev = []
    g._hurt_boss(1, ev)
    chk(b.phase == 1 and b.state == "break", "la barra vacía pasa a la fase 2")
    chk(not g.eb and g.crys, "y sus balas se vuelven cristales")


def _cabe(frames, quien):
    chk(frames + PIEL_MAX <= DOS_MIN,
        "%s: la partida cabe en 2 min (%.1f s + %.1f s de piel)"
        % (quien, frames / 60, PIEL_MAX / 60))


def test_termina_sin_jugador():
    g = nueva()
    n = jugar(g, bot.idle)
    chk(g.done, "sin jugador la partida termina")
    _cabe(n, "sin jugador")


def test_termina_con_jugador():
    for seed in (1, 2):
        g = nueva(seed)
        n = jugar(g, bot.dodger)
        chk(g.done, "con un jugador bueno termina")
        _cabe(n, "jugador bueno %d" % seed)
        g = nueva(seed)
        n = jugar(g, bot.Human(random.Random(seed), react=8, skill=0.5))
        chk(g.done, "con uno más torpe también")
        _cabe(n, "jugador torpe %d" % seed)


def test_termina_con_un_fantasma():
    """el peor caso del reloj: un jugador intocable que nunca mata a nadie.
    los jefes se tienen que ir solos y la partida cerrar en T_END."""
    g = nueva()
    n = 0
    while not g.done and n < 20000:
        g.inv = 10 ** 6
        g.shots = []
        g.step()
        n += 1
    chk(g.done and g.ending == "escapo", "el jefe se escapa y se termina")
    chk(n <= T_END + END_DELAY + 1, "justo al cerrar el reloj (%d frames)" % n)
    _cabe(n, "fantasma")


def test_puntaje_razonable():
    g = nueva(5)
    jugar(g, bot.dodger)
    chk(150000 <= g.score <= 450000,
        "un bot bueno hace un puntaje de shmup (%d)" % g.score)
    g = nueva(5)
    jugar(g, bot.idle)
    chk(g.score < 5000, "quedarse quieto no paga (%d)" % g.score)


def test_la_logica_es_liviana():
    """la lógica sola, en la peor parte (el jefe), muy por debajo de 4 ms."""
    g = nueva(2)
    peor = 0.0
    while not g.done:
        a = bot.dodger(g)
        t0 = time.perf_counter()
        g.step(*a)
        dt = time.perf_counter() - t0
        if g.sec == SEC_BOSS:
            peor = max(peor, dt)
    chk(peor < 0.003, "step() en el jefe: %.2f ms" % (peor * 1000))


def test_nada_queda_colgado():
    g = nueva(4)
    jugar(g, bot.dodger)
    chk(len(g.foes) < 30 and len(g.crys) < 200 and len(g.items) < 10,
        "no se acumulan enemigos, cristales ni ítems")


if __name__ == "__main__":
    for fn in (test_inicio, test_la_nave_no_se_sale, test_dispara_solo,
               test_el_arma_sube_el_fuego, test_rozar_paga_una_vez,
               test_los_roces_dan_bombas, test_invulnerable_no_roza,
               test_el_golpe_saca_una_vida, test_reaparece_intocable,
               test_el_hitbox_es_chico, test_sin_vidas_se_acaba,
               test_la_bomba_limpia, test_sin_bombas_no_hay_bomba,
               test_una_bomba_a_la_vez, test_el_power_up, test_el_iman_de_items,
               test_la_cadena_sube_y_cae, test_los_cristales_pagan_por_la_cadena,
               test_escuadron_completo, test_tope_de_balas,
               test_nadie_dispara_encima, test_el_mini_jefe_llega_a_tiempo,
               test_el_jefe_aparece_con_un_jugador, test_matar_al_jefe_paga_tiempo,
               test_la_fase_rompe_y_premia, test_termina_sin_jugador,
               test_termina_con_jugador, test_termina_con_un_fantasma,
               test_puntaje_razonable, test_la_logica_es_liviana,
               test_nada_queda_colgado):
        print(fn.__name__)
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
