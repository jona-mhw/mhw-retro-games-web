"""pruebas de autos, sin ventana: PYTHONPATH=. python -m games.autos.test_autos

la ciudad, el auto, los peatones, las patrullas y la partida entera son clases
sin pyxel, así que se prueban directo — incluido lo que no se puede comprobar
jugando a ojo: que la partida SIEMPRE termine dentro de los dos minutos.
"""
import math
from collections import deque

from games.autos.game import (B, BANCO_MIN, BANCO_PROPINA, BILLS, BLD,
                              BLOQUEO_TTL, CALOR, COPS_MAX, Car, City, Cop,
                              DRIFT_ANG, DRIFT_CAP, EVADE_T, EXTRA_MAX,
                              FOCO_MARCA, HELI_WANTED, Heli, IMAN, MH,
                              MISION_PAGO, MISION_PRIMERA, MISION_T, MW, NITRO,
                              Partida, Ped, RELOJ, ROAD, SIDEWALK, SOBORNO,
                              SOLID, TILE, TIME, WANTED_MAX, World, _wrap)

FALLAS = []
DOS_MIN = 2 * 60 * 60          # el tope que pidió el cabinet, en frames


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


# --- ciudad y auto (lo de siempre) -------------------------------------------
def test_ciudad():
    c = City()
    roads = c.road_tiles()
    chk(len(roads) > 100, "la ciudad tiene calles (%d tiles)" % len(roads))
    bld = next((tx, ty) for ty in range(MH) for tx in range(MW)
               if c.t[ty][tx] == BLD)
    chk(c.solid_px(bld[0] * TILE + 8, bld[1] * TILE + 8), "un edificio es sólido")
    rd = roads[0]
    chk(not c.solid_px(rd[0] * TILE + 8, rd[1] * TILE + 8), "la calle no es sólida")
    chk(len(c.walk_tiles()) > 50, "hay veredas por donde caminen los peatones")


def test_auto_acelera():
    c = City()
    car = Car(8 * TILE + 8, 8 * TILE + 8, a=0.0)
    x0, s0 = car.x, car.spd
    car.step(1, 0, c)
    chk(car.spd > s0, "acelerar sube la velocidad")
    chk(car.x > x0, "y el auto avanza")


def test_el_tope_de_velocidad_es_de_verdad():
    """acelerando a fondo, el auto tiene que LLEGAR a su tope.

    éste es el test que faltaba. con arrastre constante la velocidad se
    estabiliza sola en `accel·drag/(1−drag)`, y el `min(maxspd, ...)` no manda
    nada mientras ese equilibrio quede por debajo. con los números viejos
    (ACCEL 0.10, DRAG 0.94) el equilibrio caía en **1.57** contra un MAXSPD
    declarado de 3.4: el auto no pasaba de la mitad de su tope y ningún maxspd
    del juego servía para nada — ni el de las patrullas ni el del nitro. no
    fallaba ninguna prueba porque ninguna miraba la velocidad de crucero.
    """
    c = City()
    for tope in (Car.MAXSPD, 2.6, 5.4):
        car = Car(8 * TILE + 8, 8 * TILE + 8, a=0.0, maxspd=tope)
        for _ in range(400):
            car.spd += car.accel          # a fondo, sin ciudad de por medio
            car.spd *= Car.DRAG
            car.spd = min(car.maxspd, car.spd)
        chk(abs(car.spd - tope) < 0.02, "con tope %.1f la velocidad de crucero "
            "llega ahí (quedó en %.2f)" % (tope, car.spd))
    # y tiene que llegar en un tiempo de arcade, no de camión
    car = Car(8 * TILE + 8, 8 * TILE + 8, a=0.0)
    frames = 0
    while car.spd < Car.MAXSPD * 0.9 and frames < 600:
        car.step(1, 0, c)
        frames += 1
    chk(frames < 60, "y tarda menos de un segundo en ponerse a tiro "
        "(tardó %d frames)" % frames)


def test_la_patrulla_es_mas_lenta_que_vos():
    """el balance de la persecución depende de que los topes sean reales."""
    p = Partida(seed=99)
    p.bills = []
    for w in range(1, WANTED_MAX + 1):
        p.cops = []
        p.wanted = w - 1
        p.money = CALOR * w
        p.calor_base = 0
        p.step(0, 0)
        chk(p.cops[0].car.maxspd < Car.MAXSPD,
            "con %d estrellas la patrulla sigue siendo más lenta que vos "
            "(%.2f vs %.2f)" % (w, p.cops[0].car.maxspd, Car.MAXSPD))


def test_te_podes_escapar_de_la_policia():
    """en recta y a fondo, la patrulla tiene que quedarse atrás. siempre.

    que su `maxspd` sea menor no alcanza como prueba: hasta que la aceleración
    se derivó del tope, **ningún** maxspd se alcanzaba y todos los autos del
    juego iban a la misma velocidad real. esto mide lo único que importa —
    si la distancia crece.

    (ojo al medirlo a mano: el mapa se acaba. si dejás correr la simulación
    hasta que el auto pega contra el borde, la patrulla lo alcanza siempre y
    parece que no se puede escapar.)
    """
    c = City()
    ty = 8                                    # una avenida horizontal larga
    antes = None
    for w in (1, WANTED_MAX):
        car = Car(4 * TILE + 8, ty * TILE + 8, a=0.0)
        cop = Cop(car.x - 40, car.y, 0.0,
                  maxspd=min(Car.MAXSPD - 0.2, 2.6 + 0.15 * w))
        for _ in range(160):                  # se corta antes del borde del mapa
            car.step(1, 0, c)
            cop.step(c, car.x, car.y)
        gana = car.x - cop.x
        chk(gana > 40, "con %d estrellas te despegás manejando a fondo "
            "(quedaste a %.0f px)" % (w, gana))
        if antes is not None:
            chk(gana < antes, "y con más estrellas cuesta más escaparse "
                "(%.0f px contra %.0f)" % (gana, antes))
        antes = gana


def test_el_nitro_no_te_mete_dentro_de_un_edificio():
    """a la velocidad del nitro el auto avanza más por frame: que no se cuele."""
    c, loc = _muro()
    tx, ty = loc
    car = Car((tx - 3) * TILE + 8, ty * TILE + 8, a=0.0, maxspd=5.4)
    for _ in range(80):
        car.step(1, 0, c)
        chk(not c.solid_px(car.x, car.y),
            "el auto nunca termina dentro de un edificio (%.1f,%.1f)"
            % (car.x, car.y))
        if FALLAS:
            return


def test_auto_frena_solo():
    c = City()
    car = Car(8 * TILE + 8, 8 * TILE + 8, a=0.0)
    car.spd = 2.0
    car.step(0, 0, c)
    chk(car.spd < 2.0, "sin acelerar, la fricción frena")


def _muro():
    """un edificio con vereda a la izquierda, para estrellar el auto contra él."""
    c = City()
    loc = next(((tx, ty) for ty in range(1, MH) for tx in range(1, MW)
                if c.t[ty][tx] == BLD and c.t[ty][tx - 1] == SIDEWALK), None)
    return c, loc


def test_auto_choca():
    c, loc = _muro()
    chk(loc is not None, "hay un edificio con vereda al lado para la prueba")
    if loc:
        tx, ty = loc
        car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
        x0 = car.x
        for _ in range(6):
            car.step(1, 0, c)
        chk(abs(car.x - x0) < TILE, "el auto no atraviesa el edificio")


def test_encajado_te_despegas_doblando():
    """quedarse pegado a un edificio no puede costar más de un segundo.

    el auto se sentía trabado después de un rato de juego: cada roce le dejaba
    el 15% de la velocidad, y en calles de dos tiles se raspa todo el tiempo.
    lo que se fija acá es la salida — doblando se sale, y rápido. de frente
    contra la pared no, y así debe ser.
    """
    c, loc = _muro()
    tx, ty = loc
    car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
    for _ in range(40):
        car.step(1, 0, c)                      # encajarlo de frente
    x0, y0 = car.x, car.y

    def frames_para_salir(thr, st, tope=240):
        car.x, car.y, car.a, car.spd = x0, y0, 0.0, 0.0
        for i in range(tope):
            car.step(thr, st, c)
            if abs(car.x - x0) + abs(car.y - y0) > 24:
                return i
        return None

    doblando = frames_para_salir(1, 1)
    chk(doblando is not None and doblando < 60,
        "doblando y acelerando te despegás en menos de un segundo (%s)"
        % doblando)
    atras = frames_para_salir(-1, 1)
    chk(atras is not None and atras < 60,
        "y en reversa, más rápido todavía (%s)" % atras)
    chk(frames_para_salir(1, 0) is None,
        "pero empujando de frente sin doblar no salís, y está bien")


def test_raspar_no_te_deja_en_cero():
    """rozar un edificio frena, no clava: si no, cada esquina te para en seco."""
    c, loc = _muro()
    tx, ty = loc
    car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
    for _ in range(60):
        car.step(1, 0, c)
    chk(abs(car.spd) > 0.05, "contra la pared queda algo de velocidad para "
        "maniobrar (%.3f)" % car.spd)


def test_el_morro_no_queda_atrapado_dentro():
    """el atasco que se sentía 'pegado': morro adentro y centro en plena calle.

    el paragolpes vive a 8 px del centro, así que con el morro metido en un
    muro toda posición vecina también lo tiene adentro y el auto no se podía
    mover ni un píxel en ninguna dirección. `_desencajar` resuelve esa
    penetración empujándolo hacia atrás.
    """
    c, loc = _muro()
    tx, ty = loc
    car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
    # el centro en la vereda (libre) y el morro, 8 px más allá, dentro del muro
    car.x = tx * TILE - 6.0
    car.spd = 0.0
    chk(not c.solid_px(car.x, car.y), "(el centro arranca en la calle)")
    chk(c.solid_px(car.x + 8, car.y), "(y el morro, dentro del edificio)")
    for _ in range(30):
        car.step(0, 0, c)
    chk(not c.solid_px(car.x + 8, car.y),
        "el auto se desencaja solo en vez de quedar clavado (morro en %.1f)"
        % (car.x + 8))
    chk(not c.solid_px(car.x, car.y), "y sin meterse dentro del edificio")


def test_choque_se_avisa():
    """`crashed` es lo que corta la racha: tiene que prenderse sólo al golpe."""
    c, loc = _muro()
    tx, ty = loc
    car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
    car.step(0, 0, c)
    chk(not car.crashed, "quieto y sin acelerar, no hay choque")
    car.spd = 3.0
    car.step(1, 0, c)
    chk(car.crashed, "estrellarse a fondo sí cuenta como choque")


# --- lo nuevo: racha, calor, poderes -----------------------------------------
def test_racha_multiplica():
    p = Partida(seed=1)
    chk(p.mult() == 1, "sin racha, el fajo vale de a uno")
    p.racha = 3
    chk(p.mult() == 2, "cada 3 fajos limpios suben el multiplicador")
    p.racha = 99
    chk(p.mult() == 5, "el multiplicador tiene techo en 5")


def test_fajo_paga_por_el_multiplicador():
    p = Partida(seed=2)
    p.racha = 6                                  # x3
    p.bills = [[p.car.x + 2, p.car.y]]           # uno encima del auto
    ev = p.step(0, 0)
    fajo = [e for e in ev if e[0] == "fajo"]
    chk(len(fajo) == 1, "levantar el fajo avisa una sola vez")
    chk(p.money == 300, "cobra 100 por el multiplicador x3 (cobró %d)" % p.money)
    chk(len(p.bills) == 1, "y aparece otro fajo en la calle")


def test_chocar_corta_la_racha():
    c, loc = _muro()
    tx, ty = loc
    p = Partida(seed=3)
    p.city = c
    p.car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
    p.car.spd = 3.0
    p.racha = 9
    p.bills = []
    ev = p.step(1, 0)
    chk(any(e[0] == "choque" for e in ev), "el choque sale como evento")
    chk(p.racha == 0, "chocar te deja sin racha")


def test_la_racha_se_enfria_sola():
    p = Partida(seed=4)
    p.bills = []
    p.racha, p.racha_t = 5, 2
    p.step(0, 0)
    p.step(0, 0)
    chk(p.racha == 0, "si dejás de levantar fajos, la racha se enfría sola")


def test_la_plata_trae_patrullas():
    p = Partida(seed=5)
    p.bills = []
    p.money = CALOR * 2
    p.step(0, 0)
    chk(p.wanted == 2, "con %d de botín son 2 estrellas (dio %d)"
        % (CALOR * 2, p.wanted))
    chk(len(p.cops) == 2, "y salen dos patrullas a buscarte")
    p.money = CALOR * 99
    p.step(0, 0)
    chk(p.wanted == WANTED_MAX, "las estrellas tienen techo en %d" % WANTED_MAX)


def test_el_soborno_enfria_de_verdad():
    """la trampa: con el calor atado a la plata, la estrella volvía sola."""
    p = Partida(seed=6)
    p.bills = []
    p.money = CALOR * 3
    p.step(0, 0)
    chk(p.wanted == 3, "arranca con 3 estrellas")
    p._tomar_power(SOBORNO, [])
    for _ in range(5):
        p.step(0, 0)
    chk(p.wanted == 0, "tras el soborno seguís frío aunque conserves la plata")
    chk(not p.cops, "y las patrullas se fueron")
    p.money += CALOR
    p.step(0, 0)
    chk(p.wanted == 1, "pero si volvés a robar, te vuelven a calentar")


def test_atropellar_calienta():
    p = Partida(seed=7)
    p.bills = []
    p.car.spd = 2.0
    p.peds = [Ped(p.car.x + 2, p.car.y, 0.0, p.rng)]
    ev = p.step(0, 0)
    chk(any(e[0] == "atropello" for e in ev), "llevarse un peatón puesto se avisa")
    chk(p.atropellos == 1 and p.wanted >= 1,
        "y te sube una estrella de búsqueda")


def test_el_peaton_huye():
    p = Partida(seed=8)
    ped = Ped(p.car.x + 30, p.car.y, 0.0, p.rng)
    d0 = (ped.x - p.car.x) ** 2 + (ped.y - p.car.y) ** 2
    for _ in range(20):
        ped.step(p.city, p.car)
    chk(ped.scared, "con el auto encima, el peatón se asusta")
    chk((ped.x - p.car.x) ** 2 + (ped.y - p.car.y) ** 2 > d0,
        "y arranca para el otro lado")


def test_nitro_y_iman():
    p = Partida(seed=9)
    p.bills = []
    p._tomar_power(NITRO, [])
    p.step(1, 0)
    chk(p.car.maxspd > Car.MAXSPD, "el nitro sube el tope de velocidad")
    for _ in range(p.nitro + 1):
        p.step(0, 0)
    chk(p.car.maxspd == Car.MAXSPD, "y se le acaba la cuerda")
    p2 = Partida(seed=10)
    p2.bills = [[p2.car.x + 50, p2.car.y]]
    d0 = abs(p2.bills[0][0] - p2.car.x)
    p2._tomar_power(IMAN, [])
    p2.step(0, 0)
    chk(abs(p2.bills[0][0] - p2.car.x) < d0, "el imán arrastra el fajo hacia vos")


def test_la_patrulla_maneja():
    c = City()
    roads = c.road_tiles()
    tx, ty = roads[len(roads) // 2]
    cop = Cop(tx * TILE + 8, ty * TILE + 8, 0.0, maxspd=3.0)
    meta = (tx * TILE + 8 + 90, ty * TILE + 8)
    d0 = abs(cop.x - meta[0])
    for _ in range(60):
        cop.step(c, *meta)
    chk(abs(cop.x - meta[0]) < d0, "la patrulla se acerca a su objetivo")


def test_el_embiste_cuesta_plata():
    p = Partida(seed=11)
    p.bills = []
    p.money = 1000
    p.calor_base = 10 ** 9          # sin estrellas, para que no aparezcan solas
    p.cops = [Cop(p.car.x + 4, p.car.y, 0.0, maxspd=3.0)]
    ev = p.step(0, 0)
    chk(any(e[0] == "embiste" for e in ev), "la patrulla encima te embiste")
    chk(p.money < 1000, "y te saca un tajo del botín (quedaron %d)" % p.money)
    plata = p.money
    p.step(0, 0)
    chk(p.money == plata, "pero hay un respiro: no te cobra todos los frames")


# --- el banco ----------------------------------------------------------------
def test_el_banco_guarda_con_propina_y_se_muda():
    p = Partida(seed=21)
    p.bills = []
    p.calor_base = 10 ** 9
    bx, by = p.banco_xy
    d = ((bx - p.car.x) ** 2 + (by - p.car.y) ** 2) ** 0.5
    chk(d > 150, "el banco nace lejos (%.0f px)" % d)
    p.money = BANCO_MIN
    p.car.x, p.car.y = bx, by
    ev = p.step(0, 0)
    dep = [e for e in ev if e[0] == "deposito"]
    chk(len(dep) == 1, "pasar por el banco con el mínimo deposita")
    chk(p.money == 0, "y te vacía los bolsillos")
    chk(p.banco == BANCO_MIN + int(BANCO_MIN * BANCO_PROPINA),
        "con propina (%d)" % p.banco)
    chk(p.score == p.banco, "y el puntaje lo cuenta")
    chk(p.banco_xy != (bx, by), "y el banco se muda")
    nbx, nby = p.banco_xy
    chk(((nbx - bx) ** 2 + (nby - by) ** 2) ** 0.5 > 100, "lejos")


def test_sin_el_minimo_el_banco_no_hace_nada():
    p = Partida(seed=22)
    p.bills = []
    p.calor_base = 10 ** 9
    bx, by = p.banco_xy
    p.money = BANCO_MIN - 1
    p.car.x, p.car.y = bx, by
    ev = p.step(0, 0)
    chk(not any(e[0] == "deposito" for e in ev), "con menos del mínimo, nada")
    chk(p.money == BANCO_MIN - 1 and p.banco == 0, "y la plata sigue encima")


def test_lo_depositado_no_te_lo_sacan():
    p = Partida(seed=23)
    p.bills = []
    p.calor_base = 10 ** 9
    p.banco = 2000
    p.money = 500
    p.cops = [Cop(p.car.x + 4, p.car.y, 0.0, maxspd=3.0)]
    ev = p.step(0, 0)
    chk(any(e[0] == "embiste" for e in ev), "(la patrulla te embiste)")
    chk(p.money < 500, "te saca de lo que llevás encima")
    chk(p.banco == 2000, "pero el banco no lo toca")


def test_depositar_no_enfria_el_calor():
    p = Partida(seed=24)
    p.bills = []
    p.money = CALOR * 2
    p.step(0, 0)
    w0 = p.wanted
    chk(w0 >= 2, "(con esa plata ya hay estrellas: %d)" % w0)
    p.car.x, p.car.y = p.banco_xy
    p.step(0, 0)
    chk(p.banco > 0 and p.money == 0, "(depositó)")
    for _ in range(5):
        p.step(0, 0)
    chk(p.wanted == w0, "guardar la plata no te saca las estrellas (%d)"
        % p.wanted)


# --- la cota de los dos minutos ----------------------------------------------
def _corre(p, thr=0, steer=0, tope=DOS_MIN + 600):
    frames = 0
    while not p.over and frames < tope:
        p.step(thr, steer)
        frames += 1
    return frames


def test_la_partida_cabe_en_dos_minutos():
    """sin display no se puede comprobar jugando: se prueba a mano."""
    quieto = Partida(seed=12)
    f = _corre(quieto)
    chk(quieto.over, "parado sin tocar nada, la partida termina")
    chk(f <= DOS_MIN, "y dura menos de dos minutos (%d frames)" % f)

    corriendo = Partida(seed=13)
    f = _corre(corriendo, thr=1, steer=0)
    chk(corriendo.over and f <= DOS_MIN,
        "manejando a fondo también termina a tiempo (%d frames)" % f)


def test_el_reloj_no_estira_la_partida():
    """el caso que rompió el primer diseño: un jugador que agarra TODOS los relojes.

    con un tope por reloj (`min(TIME, time + bonus)`) la partida no terminaba
    nunca: cada reloj rellenaba el marcador a 90 s y bastaba con encadenarlos.
    lo que la acota es el presupuesto común: entre todos pueden dar EXTRA_MAX.
    """
    p = Partida(seed=14)
    p.bills = []
    frames = 0
    pasado = False
    while not p.over and frames < DOS_MIN + 600:
        p._tomar_power(RELOJ, [])          # agarra un reloj CADA frame
        pasado = pasado or p.time > TIME
        p.step(0, 0)
        frames += 1
    chk(not pasado, "el marcador nunca pasa del tiempo inicial")
    chk(p.over, "aun agarrando relojes sin parar, la partida se acaba")
    chk(frames <= TIME + EXTRA_MAX, "no dura más que el presupuesto: %d frames "
        "de %d" % (frames, TIME + EXTRA_MAX))
    chk(frames <= DOS_MIN, "y sigue cabiendo en dos minutos (%d frames)" % frames)


def test_la_ciudad_no_se_queda_vacia():
    """los fajos y los peatones se reponen: no se puede vaciar el mapa."""
    p = Partida(seed=15)
    for _ in range(900):
        p.step(1, 1)
    chk(len(p.bills) == BILLS, "siempre hay %d fajos en la calle (hay %d)"
        % (BILLS, len(p.bills)))
    chk(len(p.peds) == 14, "y 14 peatones caminando (hay %d)" % len(p.peds))
    chk(all(0 <= b[0] <= MW * TILE and 0 <= b[1] <= MH * TILE for b in p.bills),
        "y ninguno se fue del mapa")



# --- lo nuevo: derrapes, rampas, misiones, bloqueos, helicóptero -------------
def _llano():
    """una ciudad toda de asfalto y sin rampas, para medir el auto suelto."""
    c = City()
    c.t = [[ROAD] * MW for _ in range(MH)]
    c.ramps = {}
    return c


def _partida_llana(seed=31):
    p = Partida(seed=seed)
    p.city = _llano()
    p.bills = []
    p.peds = []
    p.calor_base = 10 ** 9
    p.mision_t = 10 ** 9
    p.power_t = 10 ** 9
    p.car.x, p.car.y, p.car.a, p.car.va = 120.0, 270.0, 0.0, 0.0
    return p


def test_el_freno_de_mano_abre_la_cola():
    """doblar a fondo apenas abre la cola; frenar doblando, sí derrapa."""
    c = _llano()
    car = Car(100, 270, a=0.0)
    for _ in range(60):
        car.step(1, 0, c)
    peor = 0.0
    for _ in range(40):
        car.step(1, 1, c)
        peor = max(peor, car.drift_ang())
    chk(peor < DRIFT_ANG, "una curva normal no cuenta como derrape (%.2f rad)" % peor)
    car = Car(100, 270, a=0.0)
    for _ in range(60):
        car.step(1, 0, c)
    peor = 0.0
    for _ in range(25):
        car.step(-1, 1, c)
        peor = max(peor, car.drift_ang())
    chk(peor > DRIFT_ANG, "freno + volante a velocidad suelta la cola (%.2f rad)" % peor)
    chk(car.spd > 1.5, "y derrapando no se clava: queda velocidad (%.2f)" % car.spd)


def test_el_derrape_paga_al_enderezar():
    p = _partida_llana()
    for _ in range(60):
        p.step(1, 0)
    ev = []
    for _ in range(34):
        ev += p.step(-1, 1)
    chk(p.drift > 0, "derrapando, el contador corre (%d)" % p.drift)
    for _ in range(40):
        ev += p.step(1, 0)
    pagos = [e[3] for e in ev if e[0] == "derrape"]
    chk(len(pagos) == 1, "un derrape largo paga una vez (%d)" % len(pagos))
    chk(pagos and 50 <= pagos[0] <= DRIFT_CAP, "y paga con tope (%s)" % pagos)
    chk(p.money == sum(pagos), "lo cobra en el bolsillo")


def test_chocar_derrapando_pierde_el_derrape():
    p = _partida_llana()
    p.drift = 40
    p.car.crashed = False
    c, loc = _muro()
    p.city = c
    tx, ty = loc
    p.car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
    p.car.spd = 3.0
    ev = p.step(1, 0)
    chk(any(e[0] == "choque" for e in ev), "(chocó)")
    chk(p.drift == 0 and not any(e[0] == "derrape" for e in ev),
        "el choque se come el derrape sin pagarlo")


def _rampa_horizontal(c):
    return next((t for t, eje in sorted(c.ramps.items()) if eje == 0), None)


def test_hay_rampas_en_la_calle():
    c = City()
    chk(len(c.ramps) >= 8, "la ciudad tiene rampas (%d tiles)" % len(c.ramps))
    chk(all(c.t[ty][tx] == ROAD for tx, ty in c.ramps), "y todas sobre asfalto")
    chk(all(not c.solid_px(tx * TILE + 8, ty * TILE + 8) for tx, ty in c.ramps),
        "y no son sólidas")


def test_la_rampa_hace_volar_y_paga_al_aterrizar():
    p = Partida(seed=32)
    p.bills, p.peds = [], []
    p.calor_base = 10 ** 9
    p.mision_t = p.power_t = 10 ** 9
    tx, ty = _rampa_horizontal(p.city)
    p.car = Car((tx - 4) * TILE + 8, ty * TILE + 8, a=0.0)
    ev = []
    volo = 0
    for _ in range(120):
        ev += p.step(1, 0)
        volo = max(volo, p.car.air)
    chk(any(e[0] == "salto" for e in ev), "a fondo por la rampa, el auto salta")
    chk(volo > 20, "y vuela un rato (%d frames)" % volo)
    at = [e for e in ev if e[0] == "aterrizaje"]
    chk(len(at) == 1 and at[0][3] >= 100, "al aterrizar cobra el salto (%s)" % at)
    chk(not p.city.solid_px(p.car.x, p.car.y), "y cae en la calle, no en un edificio")
    # despacio no salta
    p2 = Partida(seed=33)
    p2.bills, p2.peds = [], []
    p2.calor_base = 10 ** 9
    p2.car = Car((tx - 1) * TILE + 8, ty * TILE + 8, a=0.0)
    p2.car.spd = 1.0
    ev = []
    for _ in range(20):
        ev += p2.step(0.3, 0)
    chk(not any(e[0] == "salto" for e in ev), "despacio, la rampa no te tira")


def test_en_el_aire_no_te_tocan():
    p = Partida(seed=34)
    p.bills = []
    p.money = 1000
    p.calor_base = 10 ** 9
    p.mision_t = 10 ** 9
    p.car.air = 30
    p.car.spd = 3.0
    p.cops = [Cop(p.car.x + 4, p.car.y, 0.0, maxspd=3.0)]
    p.peds = [Ped(p.car.x + 2, p.car.y, 0.0, p.rng)]
    ev = p.step(0, 0)
    chk(not any(e[0] in ("embiste", "atropello") for e in ev),
        "volando no te embisten ni atropellas")
    chk(p.money == 1000, "y no pierdes plata")


def _con_mision(p, m):
    p.mision = dict(m)
    p.mision.setdefault("t", MISION_T[m["tipo"]])
    p.mision.setdefault("t0", MISION_T[m["tipo"]])
    p.mision.setdefault("fase", 0)


def test_las_misiones_aparecen_solas():
    p = Partida(seed=35)
    for _ in range(MISION_PRIMERA + 1):
        p.step(0, 0)
    chk(p.mision is not None, "a los pocos segundos aparece una misión")
    chk(p.objetivos(), "y la flecha tiene a dónde apuntar")


def test_mision_de_entrega():
    p = Partida(seed=36)
    p.bills = []
    p.calor_base = 10 ** 9
    x, y = p._lejos(p.roads, 100, 200)
    _con_mision(p, {"tipo": "entrega", "x": x, "y": y})
    p.car.x, p.car.y = x, y
    ev = p.step(0, 0)
    chk(any(e[0] == "mision_paso" for e in ev), "recoger el paquete se avisa")
    chk(p.mision["fase"] == 1, "y ahora hay que llevarlo")
    dx, dy = p.mision["x"], p.mision["y"]
    chk(math.hypot(dx - x, dy - y) > 200, "a un punto lejos")
    p.car.x, p.car.y = dx, dy
    ev = p.step(0, 0)
    ok = [e for e in ev if e[0] == "mision_ok"]
    chk(len(ok) == 1 and ok[0][3] >= MISION_PAGO["entrega"],
        "entregarlo paga la misión (%s)" % ok)
    chk(p.money == ok[0][3] if ok else False, "en el bolsillo")
    chk(p.mision is None and p.misiones_ok == 1, "y la misión se cierra")


def test_mision_de_carrera():
    p = Partida(seed=37)
    p.bills = []
    p.calor_base = 10 ** 9
    pts = [p._lejos(p.roads, 100, 200) for _ in range(3)]
    _con_mision(p, {"tipo": "ruta", "pts": pts, "n": 0})
    pasos = 0
    for x, y in pts:
        p.car.x, p.car.y = x, y
        ev = p.step(0, 0)
        pasos += sum(1 for e in ev if e[0] == "mision_paso")
        if any(e[0] == "mision_ok" for e in ev):
            break
    chk(pasos == 2, "las dos primeras metas se avisan (%d)" % pasos)
    chk(p.mision is None and p.money >= MISION_PAGO["ruta"],
        "y la tercera cierra la carrera y paga (%d)" % p.money)


def test_la_mision_se_vence():
    p = Partida(seed=38)
    p.bills = []
    x, y = p._lejos(p.roads, 150, 200)
    _con_mision(p, {"tipo": "entrega", "x": x, "y": y, "t": 2})
    ev = p.step(0, 0) + p.step(0, 0)
    chk(any(e[0] == "mision_fail" for e in ev), "si se acaba el tiempo, se pierde")
    chk(p.money == 0 and p.mision is None, "sin paga")


def test_salir_del_cerco_baja_una_estrella():
    p = Partida(seed=39)
    p.bills = []
    p.money = CALOR * 3
    p.step(0, 0)
    chk(p.wanted == 3, "(3 estrellas)")
    _con_mision(p, {"tipo": "escape", "cx": p.car.x, "cy": p.car.y, "r": 100})
    p.car.x += 150
    ev = p.step(0, 0)
    chk(any(e[0] == "mision_ok" for e in ev), "salir del círculo cumple el cerco")
    chk(p.wanted == 2, "y te saca una estrella (%d)" % p.wanted)
    for _ in range(3):
        p.step(0, 0)
    chk(p.wanted == 2, "que no vuelve sola al frame siguiente (%d)" % p.wanted)


def test_cinco_estrellas_cuatro_patrullas_y_helicoptero():
    p = Partida(seed=40)
    p.bills = []
    p.money = CALOR * 99
    ev = p.step(0, 0)
    chk(p.wanted == WANTED_MAX == 5, "la búsqueda llega a 5 estrellas")
    chk(len(p.cops) == COPS_MAX, "con %d patrullas (hay %d)" % (COPS_MAX, len(p.cops)))
    chk(p.heli is not None, "y el helicóptero en el aire")


def test_el_foco_del_helicoptero_cobra():
    p = Partida(seed=41)
    p.bills = []
    p.money = CALOR * HELI_WANTED
    p.step(0, 0)
    chk(p.heli is not None, "(con %d estrellas vuela)" % HELI_WANTED)
    for c in p.cops:
        c.stun = 10 ** 6                      # que no embistan: medimos el foco
        c.car.x, c.car.y = 30, 30
    plata = p.money
    marcado = None
    for i in range(FOCO_MARCA * 2):
        p.heli.x, p.heli.y = p.car.x, p.car.y
        ev = p.step(0, 0)
        if any(e[0] == "marcado" for e in ev):
            marcado = i
            break
    chk(marcado is not None and marcado >= FOCO_MARCA - 2,
        "quedarse bajo el foco te marca, pero no al toque (frame %s)" % marcado)
    chk(p.money < plata, "y te saca plata")


def test_el_helicoptero_no_te_alcanza_en_recta():
    h = Heli(0.0, 270.0)
    car = Car(60, 270, a=0.0)
    c = _llano()
    for _ in range(200):
        car.step(1, 0, c)
        h.step(car.x, car.y)
    chk(car.x - h.x > 30, "a fondo te despegas del helicóptero (%.0f px)" % (car.x - h.x))


def test_el_bloqueo_corta_la_calle_y_se_va():
    p = Partida(seed=42)
    p.bills = []
    p.money = CALOR * 3
    p.step(0, 0)
    for c in p.cops:
        c.stun = 10 ** 6
    for _ in range(20):
        p.step(1, 0)
    ok = False
    for _ in range(30):
        if p._spawn_bloqueo([]):
            ok = True
            break
        p.step(1, 0)
    chk(ok, "con 3 estrellas se puede armar un bloqueo delante")
    if not ok:
        return
    b = p.bloqueos[-1]
    chk(all(p.city.solid_px(tx * TILE + 8, ty * TILE + 8) for tx, ty in b["tiles"]),
        "la barricada es sólida")
    vert = b["eje"] == 1
    tx, ty = b["tiles"][0]
    chk((tx % B < 2) == vert and len(b["tiles"]) == 2,
        "y corta los dos carriles de un tramo recto")
    chk(math.hypot(b["x"] - p.car.x, b["y"] - p.car.y) > 48, "lejos del auto")
    p.bloqueo_t = 10 ** 9
    for _ in range(BLOQUEO_TTL + 2):
        p.step(0, 0)
    chk(not any(p.city.solid_px(tx * TILE + 8, ty * TILE + 8) for tx, ty in b["tiles"]),
        "y al rato se levanta")


def test_si_te_pierden_baja_una_estrella():
    p = Partida(seed=43)
    p.bills = []
    p.money = CALOR * 2
    p.mision_t = 10 ** 9
    p.step(0, 0)
    chk(p.wanted == 2, "(2 estrellas)")
    for c in p.cops:                     # lejos y quietas: no te ven
        c.stun = 10 ** 6
        c.car.x, c.car.y = 700 - p.car.x % 50, 530
    ev = []
    for _ in range(EVADE_T + 2):
        ev += p.step(0, 0)
    chk(any(e[0] == "estrella_menos" for e in ev), "sin patrullas cerca, te pierden")
    chk(p.wanted == 1 and len(p.cops) == 1, "una estrella y una patrulla menos "
        "(%d, %d)" % (p.wanted, len(p.cops)))
    p.money += 100
    for _ in range(3):
        p.step(0, 0)
    chk(p.wanted == 1, "y un fajo más no te la devuelve")


def test_el_soborno_levanta_bloqueos_y_helicoptero():
    p = Partida(seed=44)
    p.bills = []
    p.money = CALOR * 5
    p.step(0, 0)
    for _ in range(20):
        p.step(1, 0)
    p._spawn_bloqueo([])
    p._tomar_power(SOBORNO, [])
    chk(p.heli is None and not p.bloqueos and not p.city.extra,
        "el soborno se lleva el helicóptero y las barricadas")


# --- con jugador: un bot con gps -----------------------------------------------
class _Bot:
    """bfs por los tiles libres hasta el objetivo de turno: misión, banco o
    el fajo más cercano. maneja mal, pero llega."""

    def __init__(self, p):
        self.p, self.path, self.t, self.stuck, self.rev = p, [], 0, 0, 0

    def _bfs(self, s, g):
        c = self.p.city
        prev = {s: None}
        q = deque([s])
        while q:
            cur = q.popleft()
            if cur == g:
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cur[0] + dx, cur[1] + dy)
                if n in prev or not (0 <= n[0] < MW and 0 <= n[1] < MH) \
                        or c.t[n[1]][n[0]] in SOLID or n in c.extra:
                    continue
                prev[n] = cur
                q.append(n)
        out, n = [], (g if g in prev else None)
        while n is not None:
            out.append(n)
            n = prev[n]
        return out[::-1]

    def _meta(self):
        p, car = self.p, self.p.car
        m = p.mision
        if m is not None and m["tipo"] == "escape":
            a = math.atan2(car.y - m["cy"], car.x - m["cx"])
            return m["cx"] + math.cos(a) * (m["r"] + 60), m["cy"] + math.sin(a) * (m["r"] + 60)
        for x, y, k, _ in p.objetivos():
            if k != "banco":
                return x, y
        if p.money >= 900:
            return p.banco_xy
        b = min(p.bills, key=lambda b: (b[0] - car.x) ** 2 + (b[1] - car.y) ** 2)
        return b[0], b[1]

    def act(self):
        car = self.p.car
        self.t += 1
        if self.rev > 0:
            self.rev -= 1
            return -1, 1
        self.stuck = self.stuck + 1 if abs(car.spd) < 0.3 else 0
        if self.stuck > 40:
            self.stuck, self.rev = 0, 25
        if self.t % 12 == 1 or not self.path:
            gx, gy = self._meta()
            g = (max(0, min(MW - 1, int(gx // TILE))), max(0, min(MH - 1, int(gy // TILE))))
            self.path = self._bfs((int(car.x // TILE), int(car.y // TILE)), g)
        if not self.path:
            return 1, 0
        ct = (int(car.x // TILE), int(car.y // TILE))
        if ct in self.path:
            self.path = self.path[self.path.index(ct):]
        wx, wy = self.path[min(2, len(self.path) - 1)]
        diff = _wrap(math.atan2(wy * TILE + 8 - car.y, wx * TILE + 8 - car.x) - car.a)
        st = 1 if diff > 0.12 else (-1 if diff < -0.12 else 0)
        if abs(diff) > 1.0 and car.spd > 2.2:
            return -1, st                      # freno de mano en la esquina
        return (1 if abs(diff) < 1.3 else 0.3), st


def test_jugando_de_verdad_termina_a_tiempo_y_paga():
    """con un jugador que hace todo (misiones, banco, derrapes, saltos), la
    partida sigue terminando sola antes de los dos minutos."""
    for seed in (51, 52, 53):
        p = Partida(seed=seed)
        bot = _Bot(p)
        f = 0
        while not p.over and f < DOS_MIN + 600:
            p.step(*bot.act())
            f += 1
        chk(p.over and f <= DOS_MIN, "con jugador la partida termina a tiempo "
            "(%d frames)" % f)
        chk(p.score > 1500, "y un jugador con gps junta plata (%d)" % p.score)
        chk(p.misiones_ok >= 1, "y cumple alguna misión (%d)" % p.misiones_ok)
        chk(not p.city.solid_px(p.car.x, p.car.y), "sin terminar dentro de un muro")


def test_en_el_celular_acelera_solo():
    """con el dedo no hay botón de acelerar: el auto va solo y el botón frena."""
    import pyxel
    viejo = pyxel.btn
    apretadas = set()
    pyxel.btn = lambda k: k in apretadas
    try:
        w = World(seed=61, auto=True)
        w.p.mision_t = 10 ** 9
        for _ in range(40):
            w.update()
        chk(w.p.car.spd > 2.5, "sin tocar nada, el auto acelera solo (%.2f)" % w.p.car.spd)
        apretadas.add(pyxel.KEY_DOWN)
        for _ in range(20):
            w.update()
        chk(w.p.car.spd < 0.5, "y el freno lo para (%.2f)" % w.p.car.spd)
        apretadas.clear()
        t = World(seed=61, auto=False)
        for _ in range(40):
            t.update()
        chk(abs(t.p.car.spd) < 0.01, "con teclado, sin acelerar, el auto no arranca")
    finally:
        pyxel.btn = viejo

if __name__ == "__main__":
    for fn in (test_ciudad, test_auto_acelera,
               test_el_tope_de_velocidad_es_de_verdad,
               test_la_patrulla_es_mas_lenta_que_vos,
               test_te_podes_escapar_de_la_policia,
               test_el_nitro_no_te_mete_dentro_de_un_edificio,
               test_auto_frena_solo,
               test_auto_choca, test_encajado_te_despegas_doblando,
               test_raspar_no_te_deja_en_cero,
               test_el_morro_no_queda_atrapado_dentro,
               test_choque_se_avisa, test_racha_multiplica,
               test_fajo_paga_por_el_multiplicador, test_chocar_corta_la_racha,
               test_la_racha_se_enfria_sola, test_la_plata_trae_patrullas,
               test_el_soborno_enfria_de_verdad, test_atropellar_calienta,
               test_el_peaton_huye, test_nitro_y_iman, test_la_patrulla_maneja,
               test_el_embiste_cuesta_plata,
               test_el_banco_guarda_con_propina_y_se_muda,
               test_sin_el_minimo_el_banco_no_hace_nada,
               test_lo_depositado_no_te_lo_sacan,
               test_depositar_no_enfria_el_calor,
               test_la_partida_cabe_en_dos_minutos,
               test_el_reloj_no_estira_la_partida,
               test_la_ciudad_no_se_queda_vacia,
               test_el_freno_de_mano_abre_la_cola,
               test_el_derrape_paga_al_enderezar,
               test_chocar_derrapando_pierde_el_derrape,
               test_hay_rampas_en_la_calle,
               test_la_rampa_hace_volar_y_paga_al_aterrizar,
               test_en_el_aire_no_te_tocan,
               test_las_misiones_aparecen_solas, test_mision_de_entrega,
               test_mision_de_carrera, test_la_mision_se_vence,
               test_salir_del_cerco_baja_una_estrella,
               test_cinco_estrellas_cuatro_patrullas_y_helicoptero,
               test_el_foco_del_helicoptero_cobra,
               test_el_helicoptero_no_te_alcanza_en_recta,
               test_el_bloqueo_corta_la_calle_y_se_va,
               test_si_te_pierden_baja_una_estrella,
               test_el_soborno_levanta_bloqueos_y_helicoptero,
               test_jugando_de_verdad_termina_a_tiempo_y_paga,
               test_en_el_celular_acelera_solo):
        fn()
    print()
    print("=== TODO OK ===" if not FALLAS else "=== %d FALLAS ===" % len(FALLAS))
