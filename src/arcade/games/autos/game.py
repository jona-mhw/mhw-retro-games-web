"""autos — atraco a la ciudad, top-down estilo gta 2, para el cabinet.

vista aérea, auto con inercia y derrape, una ciudad con calles, veredas y plazas.
levantas fajos de billetes contra reloj, pero cada fajo te calienta: a partir de
cierta plata aparecen **patrullas** que te persiguen de verdad (manejan, no
flotan) y te sacan un tajo del botín si te embisten. hay **peatones** que cruzan
y se asustan, una **racha** que multiplica lo que levantas mientras manejes
limpio, y **poderes** tirados por la calle: nitro, imán, soborno y reloj.

y está **el banco**: la plata que llevas encima es la que te sacan las
patrullas. si pasas por el banco con un mínimo, la depositas con un 10% de
propina y queda a salvo — y el banco se muda lejos.

lo que suma emoción a la vuelta del banco:

- **misiones cortas** que aparecen solas: llevar un paquete a un punto, pasar
  por tres metas contra reloj, o salir de un cerco policial. una flecha en el
  borde de la pantalla te lleva.
- **búsqueda de 5 estrellas**: con 3 aparecen bloqueos en la calle, con 4 un
  helicóptero con foco. si te alejas de todos un rato, pierdes una estrella
  (las estrellas titilan mientras te pierden la pista).
- **derrapes**: frenar doblando a toda velocidad suelta la cola; un derrape
  largo paga y mantiene viva la racha.
- **rampas**: a fondo por una rampa, el auto vuela y aterriza cobrando.

la partida dura 90 segundos y ni el reloj ni los poderes pueden estirarla más
(el reloj suma con tope), así que se juega entera en menos de dos minutos.

la lógica vive en clases sin pyxel — City, Car, Ped, Cop, Heli y **Partida**,
que es el juego entero: recibe el input ya leído y devuelve una lista de
eventos. World sólo lee el teclado, traduce esos eventos a chispas y dibuja.
así toda la mecánica se testea sin abrir ventana.
"""
import math
import random
from collections import deque

import pyxel

from pixelkit import fx, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import _ACUTE, _TILDE, ctext, text

W, H = 384, 288
HUD = 26                         # la barra de arriba: números al doble de tamaño
VIEW_H = H - HUD
TILE = 16
MW, MH = 44, 34                  # ciudad en tiles → 704 x 544
MAP_PX, MAP_PY = MW * TILE, MH * TILE
B = 8                            # calle cada 8 tiles, de 2 de ancho
TIME = 90 * 60                   # 90 segundos, y el reloj no puede pasarse

BILLS = 10                       # fajos en la calle a la vez
VALOR = 100                      # lo que vale un fajo, antes del multiplicador
RECOGE = 17                      # radio para levantar un fajo, en píxeles
RACHA_TTL = 4 * 60               # sin levantar nada, la racha se enfría
MULT_MAX = 5
CALOR = 900                      # cada tanta plata, una estrella más
WANTED_MAX = 5
COPS_MAX = 4                     # la 5ª estrella no trae otra patrulla: trae todo lo demás
BLOQUEO_WANTED = 3               # desde acá cortan calles
HELI_WANTED = 4                  # y desde acá vuela el helicóptero
BUST_COST = 0.08                 # cuánto del botín te saca una patrulla
BUST_GRACE = 150                 # invulnerable un rato después del embiste
BUST_STUN = 75                   # y la patrulla se queda frenada otro tanto
POWER_GAP = 7 * 60               # cada cuánto aparece un poder nuevo
POWERS_MAX = 2

# perderlos: si ninguna patrulla te tiene a tiro (ni el foco del helicóptero)
# durante EVADE_T, se cae una estrella. es lo que vuelve una persecución algo
# que se gana manejando, no sólo con el soborno.
EVADE_R = 230
EVADE_T = 5 * 60

# el banco: depositar lo que llevas lo pone a salvo de las patrullas y paga
# una propina. hay un mínimo para que no sea un trámite de cada esquina.
BANCO_MIN = 300
BANCO_PROPINA = 0.10
BANCO_R = 18                     # radio para depositar, en píxeles

# derrape: freno + volante a toda velocidad. paga al terminar, con tope, y
# hace falta enderezar antes de empezar otro (así dar vueltas no es una mina)
DRIFT_ANG = 0.35                 # radianes entre el morro y la marcha
DRIFT_SPD = 1.7
DRIFT_MIN = 24                   # frames de derrape para cobrar
DRIFT_CAP = 300

# rampas: el auto vuela unos frames, no dobla en el aire y no lo tocan
RAMPA_SPD = 2.3
RAMPA_CD = 50                    # después de aterrizar, un respiro

# helicóptero: te sigue apenas más lento que tu tope. si el foco te tiene
# encima FOCO_MARCA frames (no necesariamente seguidos), te marca y cobra.
HELI_SPD = 2.75
FOCO_R = 26
FOCO_MARCA = 90

# bloqueos: dos tiles de barricada que cortan la calle por donde vas
BLOQUEO_GAP = 6 * 60
BLOQUEO_TTL = 9 * 60
BLOQUEOS_MAX = 2

# misiones: una a la vez, cortas, y ninguna toca el reloj de la partida
MISION_PRIMERA = 6 * 60
MISION_GAP = 5 * 60
MISION_R = 18
MISION_T = {"entrega": 28 * 60, "ruta": 22 * 60, "escape": 10 * 60}
MISION_PAGO = {"entrega": 350, "ruta": 300, "escape": 200}
MISION_SEG = 10                  # cada segundo que sobra paga esto
ESCAPE_R = 165

# tipos de tile
ROAD, SIDEWALK, GRASS, TREE, FOUNT, BLD = range(6)
SOLID = (TREE, FOUNT, BLD)
WALKABLE = (SIDEWALK, GRASS, ROAD)

# poderes
NITRO, IMAN, SOBORNO, RELOJ = range(4)
POWER_NAME = {NITRO: "NITRO!", IMAN: "IMÁN!", SOBORNO: "SOBORNO!",
              RELOJ: "+8 SEG"}
NITRO_TTL, IMAN_TTL = 5 * 60, 8 * 60
IMAN_R = 64                      # radio del imán, en píxeles
RELOJ_BONUS = 8 * 60             # lo que suma un reloj...
EXTRA_MAX = 20 * 60              # ...y el total que pueden sumar TODOS juntos
# el tope por reloj no alcanza para acotar la partida: como el reloj rellena
# hasta TIME, agarrar uno atrás de otro la deja clavada en 90 s para siempre.
# el presupuesto sí: la corrida más larga posible es TIME + EXTRA_MAX = 110 s.

# paleta
(BG, ASPHALT, LINE, SIDE, SIDE2, GRASS1, GRASS2, TREETOP, TREEDK, TRUNK,
 WATER, BLD1, BLD2, BLD3, ROOF, GLASS, CARBODY, CARROOF, HEAD, BILL, BILL2,
 TXT, DIM, ACCENT, SHADOW, WHITE,
 COP1, COP2, LIGHTR, LIGHTB, SKIN, PED1, PED2, PED3,
 SMOKE1, SMOKE2, SPARK1, SPARK2, SPARK3, NITRO1, NITRO2,
 GOLD, MAGENTA, MAPBG, MAPRD, MAPME, SKID, ORANGE, HELI1, PANEL) = range(50)
PAL = [
    0x0C0E14, 0x33383F, 0xC9A227, 0x6B7280, 0x828A9C, 0x3E7A32, 0x4E9440,
    0x57A544, 0x2E5E28, 0x6B4A2A, 0x3E86C4, 0x8A5A44, 0x6E6A82, 0xB0865A,
    0x242834, 0x7ADCFF, 0xE0402A, 0x9C2A1E, 0xFFF0A0, 0x3FA65C, 0x9BE88A,
    0xE8ECF5, 0x5A6480, 0x8AC52F, 0x070810, 0xF2F5FB,
    0x1E3A8A, 0xDCE3F0, 0xFF3B30, 0x4DA6FF, 0xE8B48A, 0xD8483A, 0x4A78D8,
    0xE7C13B, 0x6E7684, 0x39404E, 0xFFF3B0, 0xFFA23A, 0xE0402A, 0x7ADCFF,
    0x2E7FBF, 0xFFD24A, 0xD84AB8, 0x11131C, 0x3A4152, 0x8AC52F,
    0x22262C, 0xFF8C1A, 0x2A3550, 0x161A26,
] + [0] * (256 - 50)

SMOKE = (SMOKE1, SMOKE2, ASPHALT)
TIRE = (WHITE, SMOKE1, SMOKE2)
SPARKS = (WHITE, SPARK1, SPARK2, SPARK3)
NITROFX = (WHITE, NITRO1, NITRO2, WATER)
CASH = (WHITE, BILL2, BILL, GRASS1)
GOLDFX = (WHITE, GOLD, ORANGE, SPARK3)


def _wrap(a):
    return (a + math.pi) % math.tau - math.pi


class City:
    """la ciudad en tiles: calles, veredas, plazas con árboles y fuentes.

    `extra` son tiles que se vuelven sólidos un rato (las barricadas de los
    bloqueos) y `ramps` las rampas, fijas, en mitad de algunas cuadras.
    """

    def __init__(self, seed=20260726):
        self.mw, self.mh = MW, MH
        self.t = [[BLD] * MW for _ in range(MH)]
        self.extra = set()
        for ty in range(MH):
            for tx in range(MW):
                self.t[ty][tx] = self._base(tx, ty)
        # decorar plazas: árboles sobre el pasto y una fuente al centro
        for ty in range(MH):
            for tx in range(MW):
                if self.t[ty][tx] == GRASS and (tx * 13 + ty * 7) % 6 == 0:
                    self.t[ty][tx] = TREE
        for by in range(MH // B + 1):
            for bx in range(MW // B + 1):
                if self._plaza(bx, by):
                    cx = bx * B + B // 2
                    cy = by * B + B // 2
                    if 0 <= cx < MW and 0 <= cy < MH and self.t[cy][cx] in (GRASS, TREE):
                        self.t[cy][cx] = FOUNT
        # rampas: cruzan la calle entera (los dos carriles), a mitad de cuadra,
        # así el salto cae sobre la misma avenida y no contra un edificio
        self.ramps = {}
        for by in range(MH // B + 1):
            for bx in range(MW // B):
                h = (bx * 7 + by * 3) % 5
                if h == 0:                       # calle horizontal: se salta en x
                    tx, ty = bx * B + 5, by * B
                    cells, eje = ((tx, ty), (tx, ty + 1)), 0
                elif h == 2:                     # calle vertical: se salta en y
                    tx, ty = bx * B, by * B + 5
                    cells, eje = ((tx, ty), (tx + 1, ty)), 1
                else:
                    continue
                if all(self.tile(cx, cy) == ROAD for cx, cy in cells):
                    for c in cells:
                        self.ramps[c] = eje

    def _plaza(self, bx, by):
        return (bx * 5 + by * 3) % 4 == 1

    def _base(self, tx, ty):
        rc, rr = tx % B, ty % B
        if rc < 2 or rr < 2:
            return ROAD
        edge = rc == 2 or rr == 2 or rc == B - 1 or rr == B - 1
        if self._plaza(tx // B, ty // B):
            return SIDEWALK if edge else GRASS
        return SIDEWALK if edge else BLD

    def tile(self, tx, ty):
        if 0 <= tx < MW and 0 <= ty < MH:
            return self.t[ty][tx]
        return BLD

    def solid_px(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        if self.tile(tx, ty) in SOLID:
            return True
        return bool(self.extra) and (tx, ty) in self.extra

    def walkable_px(self, x, y):
        return self.tile(int(x // TILE), int(y // TILE)) in WALKABLE

    def road_tiles(self):
        return [(tx, ty) for ty in range(MH) for tx in range(MW)
                if self.t[ty][tx] == ROAD]

    def walk_tiles(self):
        return [(tx, ty) for ty in range(MH) for tx in range(MW)
                if self.t[ty][tx] == SIDEWALK]


class Car:
    """el auto: posición, rumbo y velocidad, con choque contra lo sólido.

    **la aceleración se deriva del tope, no se elige aparte.** con arrastre
    constante, la velocidad se estabiliza sola en `ACCEL·DRAG/(1−DRAG)` — el
    `min(maxspd, ...)` no manda nada mientras ese equilibrio quede por debajo.
    calculando `accel` a partir de `maxspd`, la velocidad terminal **es**
    `maxspd` por construcción.

    **derrape**: el auto tiene dos ángulos. `a` es hacia dónde mira el morro y
    `va` hacia dónde se mueve de verdad; `va` persigue a `a` con un agarre. con
    agarre normal la cola apenas se abre en las curvas; frenando mientras
    doblas a velocidad (el freno de mano) el agarre cae, el morro gira más
    rápido que la marcha y el auto cruza la calle de costado. sin esto los
    autos doblaban sobre rieles.

    `air` son los frames que le quedan volando tras una rampa: en el aire no
    dobla ni acelera, sólo sigue.
    """

    DRAG = 0.94                    # cuánto conserva por frame (la inercia)
    MAXSPD, MAXREV, TURN = 3.4, 1.5, 0.070
    CRASH_FRAC = 0.55              # a partir de qué fracción del tope es "golpe"
    GRIP_FRAC = 0.45               # y a qué fracción el volante ya agarra del todo
    GRIP, MANO_GRIP = 0.24, 0.07   # cuánto persigue la marcha al morro por frame
    MANO_SPD = 1.6                 # desde qué velocidad el freno + volante derrapa
    MANO_DRAG = 0.988              # derrapando se frena de a poco, no en seco
    MANO_TURN = 1.3

    def __init__(self, x, y, a=0.0, maxspd=None):
        self.x, self.y, self.a, self.spd = x, y, a, 0.0
        self.va = a
        self.maxspd = self.MAXSPD if maxspd is None else maxspd
        self.crashed = False           # chocó en el último step
        self.mano = False              # está tirando del freno de mano
        self.air = 0

    @property
    def accel(self):
        """la que hace que el equilibrio caiga justo en `maxspd`."""
        return self.maxspd * (1 - self.DRAG) / self.DRAG

    def drift_ang(self):
        """cuánto se abrió la cola: el ángulo entre el morro y la marcha."""
        return abs(_wrap(self.a - self.va))

    def _parag(self):
        """el paragolpes que va adelante en el sentido de la marcha."""
        sgn = 1 if self.spd >= 0 else -1
        return math.cos(self.a) * 8 * sgn, math.sin(self.a) * 8 * sgn

    def _libre(self, city, x, y):
        """¿cabe el auto ahí? el centro y el paragolpes de la marcha."""
        if city.solid_px(x, y):
            return False
        fx_, fy_ = self._parag()
        return not city.solid_px(x + fx_, y + fy_)

    def _desencajar(self, city):
        """si el morro quedó metido en un edificio, sácalo de a poco.

        el paragolpes vive a 8 px del centro, así que con el morro adentro de un
        muro **toda** posición vecina también lo tiene adentro: el auto quedaba
        clavado. resolver la penetración es lo que hace cualquier motor de
        colisión: empujamos el auto en sentido contrario al morro.
        """
        fx_, fy_ = self._parag()
        if not city.solid_px(self.x + fx_, self.y + fy_):
            return
        ex, ey = -math.cos(self.a) * 0.7, -math.sin(self.a) * 0.7
        for _ in range(12):                    # como mucho 8 px, el largo del morro
            if not city.solid_px(self.x + fx_, self.y + fy_):
                return
            if city.solid_px(self.x + ex, self.y + ey):
                return                         # atrás tampoco hay lugar: ríndete
            self.x += ex
            self.y += ey

    def step(self, throttle, steer, city):
        self.mano = False
        if self.air > 0:
            self.air -= 1
            self.spd *= 0.995                  # volando no hay roce ni volante
        else:
            self.mano = throttle < 0 and steer != 0 and self.spd > self.MANO_SPD
            if self.mano:
                self.spd *= self.MANO_DRAG
            else:
                self.spd += throttle * self.accel
                self.spd *= self.DRAG
            self.spd = max(-self.MAXREV, min(self.maxspd, self.spd))
            if abs(self.spd) > 0.15:
                grip = min(1.0, abs(self.spd) / (self.maxspd * self.GRIP_FRAC))
                k = self.MANO_TURN if self.mano else 1.0
                self.a += steer * self.TURN * (1 if self.spd > 0 else -1) * grip * k
            elif throttle:
                # clavado y acelerando: igual puedes maniobrar en el sitio. sin
                # esto hay un empate del que no se sale (sin velocidad no hay grip)
                self.a += steer * self.TURN * 0.6
            if abs(self.spd) < 1.0:
                self.va = self.a
            else:
                self.va += _wrap(self.a - self.va) * (
                    self.MANO_GRIP if self.mano else self.GRIP)
        dx, dy = math.cos(self.va) * self.spd, math.sin(self.va) * self.spd
        nx, ny = self.x + dx, self.y + dy
        self.crashed = False
        if self._libre(city, nx, ny):
            self.x, self.y = nx, ny
        else:
            if abs(self.spd) > self.maxspd * self.CRASH_FRAC:
                self.crashed = True         # golpe de verdad, no un roce
                self.air = 0
            # **deslizar en vez de clavarse**: si el paso completo no entra,
            # probamos cada eje por separado. rozar una pared en diagonal te
            # frena y te acompaña, que es como se maneja un top-down.
            if self._libre(city, nx, self.y):
                self.x = nx
                self.spd *= 0.72
            elif self._libre(city, self.x, ny):
                self.y = ny
                self.spd *= 0.72
            else:
                # de frente: frena, pero no te clava
                self.spd *= 0.30
                self.va = self.a
        self._desencajar(city)
        self.x = max(8, min(MAP_PX - 8, self.x))
        self.y = max(8, min(MAP_PY - 8, self.y))


class Ped:
    """un peatón: camina por la vereda y se asusta si le pasas cerca.

    no es un obstáculo sólido — es una multa con piernas: llevártelo puesto no
    te frena, te sube una estrella de búsqueda y te corta la racha.
    """

    SPD, RUN, SCARE = 0.32, 0.95, 46

    def __init__(self, x, y, a, rng):
        self.x, self.y, self.a = x, y, a
        self.rng = rng
        self.scared = 0
        self.gone = False              # ya lo atropellaron, sale de la lista
        self.step_t = rng.randrange(30)

    def step(self, city, car):
        dx, dy = car.x - self.x, car.y - self.y
        d2 = dx * dx + dy * dy
        if d2 < self.SCARE * self.SCARE:
            self.scared = 40
            self.a = math.atan2(-dy, -dx)          # huye en dirección contraria
        elif self.scared:
            self.scared -= 1
        v = self.RUN if self.scared else self.SPD
        nx, ny = self.x + math.cos(self.a) * v, self.y + math.sin(self.a) * v
        if city.walkable_px(nx, ny) and 4 < nx < MAP_PX - 4 and 4 < ny < MAP_PY - 4:
            self.x, self.y = nx, ny
        else:
            self.a += self.rng.uniform(1.2, 2.6)   # rebota contra lo que no se camina
        self.step_t += 1
        if not self.scared and self.step_t % 90 == 0:
            self.a += self.rng.uniform(-0.9, 0.9)
        return d2 < 7 * 7                          # ¿lo tocó el auto?


class Cop:
    """una patrulla: **maneja**, no flota. usa el mismo Car que tú.

    la IA es de tres líneas — apunta al jugador, acelera si está mirando para
    allá, y si se quedó pegada contra un muro mete marcha atrás. alcanza para
    que persiga por las calles y a veces se estrelle sola.
    """

    def __init__(self, x, y, a, maxspd):
        self.car = Car(x, y, a, maxspd=maxspd)
        self.stuck = 0
        self.stun = 0              # frenada tras embestir: tu ventana para huir

    @property
    def x(self):
        return self.car.x

    @property
    def y(self):
        return self.car.y

    def step(self, city, tx, ty):
        c = self.car
        if self.stun > 0:
            # acaba de embestirte: se frena y te deja irte. sin esto la patrulla
            # se queda pegada y te cobra otra vez apenas se acaba tu inmunidad
            self.stun -= 1
            c.step(0, 0, city)
            return False
        want = math.atan2(ty - c.y, tx - c.x)
        diff = _wrap(want - c.a)
        steer = 1 if diff > 0.10 else (-1 if diff < -0.10 else 0)
        thr = 1 if abs(diff) < 1.3 else 0.35
        if abs(c.spd) < 0.25:
            self.stuck += 1
        else:
            self.stuck = 0
        if self.stuck > 26:                     # encajado: sale marcha atrás
            thr, steer = -1, 1
            if self.stuck > 52:
                self.stuck = 0
        c.step(thr, steer, city)
        return (c.x - tx) ** 2 + (c.y - ty) ** 2 < 13 ** 2    # ¿te embistió?


class Heli:
    """el helicóptero: vuela derecho (los edificios no lo frenan), persigue con
    inercia y alumbra el piso. es apenas más lento que tu tope: en recta te
    lo sacas, en las esquinas te corta camino."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0

    def step(self, tx, ty):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy) or 1.0
        want = min(HELI_SPD, d * 0.08)
        self.vx += (dx / d * want - self.vx) * 0.05
        self.vy += (dy / d * want - self.vy) * 0.05
        self.x += self.vx
        self.y += self.vy
        return d < FOCO_R                       # ¿te tiene en el foco?


class Partida:
    """el juego entero, sin pyxel: recibe el input y devuelve qué pasó.

    `step(thr, steer)` avanza un frame y devuelve una lista de eventos
    (`("fajo", x, y, monto)`, `("choque", x, y)`, ...). el World los traduce a
    chispas y carteles; los tests los leen para saber qué ocurrió.
    """

    def __init__(self, seed=None):
        self.city = City()
        self.rng = random.Random(seed)
        self.roads = self.city.road_tiles()
        self.walks = self.city.walk_tiles()
        tx, ty = min(self.roads,
                     key=lambda p: abs(p[0] - MW // 2) + abs(p[1] - MH // 2))
        self.car = Car(tx * TILE + 8, ty * TILE + 8)
        self.money = 0
        self.racha = 0
        self.racha_t = 0
        self.wanted = 0
        self.atropellos = 0
        self.calor_base = 0        # plata "ya perdonada": lo que corre el soborno
        self.peds = []
        self.time = TIME
        self.extra = EXTRA_MAX     # segundos que los relojes todavía pueden dar
        self.over = False
        self.grace = 0
        self.nitro = 0
        self.iman = 0
        self.bills = []
        self.cops = []
        self.powers = []           # [x, y, tipo]
        self.power_t = POWER_GAP
        self.busts = 0
        self.banco = 0             # lo ya depositado: intocable
        self.depositos = 0
        self.banco_xy = self._lejos(self.roads, 220, 380)
        # lo nuevo
        self.drift = 0             # frames del derrape en curso
        self.derrapes = 0
        self.vuelo = 0             # frames del salto en curso
        self.saltos = 0
        self.ramp_cd = 0
        self.heli = None
        self.foco = 0
        self.bloqueos = []         # {"tiles", "x", "y", "eje", "t"}
        self.bloqueo_t = BLOQUEO_GAP // 2
        self.evade = 0
        self.mision = None
        self.mision_t = MISION_PRIMERA
        self.misiones_ok = 0
        for _ in range(BILLS):
            self._spawn_bill()
        for _ in range(14):
            self._spawn_ped()

    # --- multiplicador ---------------------------------------------------
    def mult(self):
        """la racha en multiplicador: cada 3 fajos limpios suma uno, hasta 5."""
        return min(MULT_MAX, 1 + self.racha // 3)

    @property
    def score(self):
        return self.money + self.banco

    def _depositar(self, ev):
        """pasas por el banco con el mínimo encima: se guarda con propina, y
        el banco se muda lejos para que la próxima vuelta sea otra."""
        monto = self.money
        propina = int(monto * BANCO_PROPINA)
        self.banco += monto + propina
        self.money = 0
        self.calor_base += propina         # el calor mira el total robado: ni
                                           # se enfría, ni la propina lo sube
        self.depositos += 1
        x, y = self.banco_xy
        ev.append(("deposito", x, y, monto, propina))
        self.banco_xy = self._lejos(self.roads, 240, 420)

    # --- poblar la ciudad ------------------------------------------------
    def _anillo(self, cx, cy, pool, minimo, maximo=None, ok=None):
        """un tile del pool a la distancia justa de (cx, cy)."""
        for _ in range(40):
            tx, ty = self.rng.choice(pool)
            if (tx, ty) in self.city.extra:
                continue
            x, y = tx * TILE + 8, ty * TILE + 8
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 > minimo * minimo and (maximo is None or d2 < maximo * maximo) \
                    and (ok is None or ok(tx, ty)):
                return x, y
        return tx * TILE + 8, ty * TILE + 8

    def _lejos(self, pool, minimo=140, maximo=None):
        """un tile del pool a la distancia justa del auto: ni encima, ni perdido.

        sin `maximo` los fajos se repartían por todo el mapa y en 90 segundos un
        jugador apenas alcanzaba dos o tres. en un anillo alrededor tuyo siempre
        hay algo a mano y la partida no se muere buscando.
        """
        return self._anillo(self.car.x, self.car.y, pool, minimo, maximo)

    def _spawn_bill(self):
        self.bills.append(list(self._lejos(self.roads, 60, 220)))

    def _spawn_ped(self):
        if not self.walks:
            return
        x, y = self._lejos(self.walks, 90)
        self.peds.append(Ped(x, y, self.rng.uniform(0, math.tau), self.rng))

    def _spawn_cop(self):
        x, y = self._lejos(self.roads, 190, 330)
        a = math.atan2(self.car.y - y, self.car.x - x)
        # cada estrella los hace un poco más rápidos, pero SIEMPRE por debajo
        # tuyo: que te pisen los talones es la gracia; que te alcancen sí o
        # sí, no (un bot comió 31 embistes en una partida con patrullas más
        # rápidas que él).
        tope = min(Car.MAXSPD - 0.2, 2.6 + 0.15 * self.wanted)
        self.cops.append(Cop(x, y, a, maxspd=tope))

    def _spawn_power(self):
        x, y = self._lejos(self.roads, 110, 380)
        self.powers.append([x, y, self.rng.randrange(4)])

    # --- calor -----------------------------------------------------------
    def _recalcular_wanted(self, ev):
        """el calor sube con lo que llevas robado y con los sustos que diste."""
        objetivo = min(WANTED_MAX,
                       (self.money + self.banco - self.calor_base) // CALOR
                       + self.atropellos)
        if objetivo > self.wanted:
            self.wanted = objetivo
            ev.append(("wanted", self.wanted))
        while len(self.cops) < min(self.wanted, COPS_MAX):
            self._spawn_cop()

    def _enfriar(self, ev):
        """el soborno: borra las estrellas y se lleva a las patrullas.

        además corre el piso del calor a la plata que llevas ahora. sin eso,
        el mismo dinero volvía a levantar la estrella al frame siguiente.
        """
        self.wanted = 0
        self.atropellos = 0
        self.calor_base = self.money + self.banco
        self.cops = []
        self.heli = None
        self.foco = 0
        self._quitar_bloqueos()
        ev.append(("enfriado", 0))

    def _bajar_estrella(self, ev, motivo):
        """una estrella menos (te perdieron, o saliste del cerco).

        el piso del calor se corre justo al borde de la estrella nueva: hace
        falta robar un CALOR entero para volver a subir, no un fajo.
        """
        if self.wanted <= 0:
            return
        w = self.wanted - 1
        self.atropellos = min(self.atropellos, w)
        self.calor_base = max(self.calor_base, self.money + self.banco
                              - (w - self.atropellos) * CALOR)
        self.wanted = w
        car = self.car
        self.cops.sort(key=lambda c: (c.x - car.x) ** 2 + (c.y - car.y) ** 2)
        del self.cops[min(w, COPS_MAX):]       # se van las más lejanas
        if w < HELI_WANTED:
            self.heli = None
            self.foco = 0
        ev.append(("estrella_menos", w, motivo))

    # --- bloqueos ----------------------------------------------------------
    def _quitar_bloqueos(self):
        for b in self.bloqueos:
            self.city.extra.difference_update(b["tiles"])
        self.bloqueos = []

    def _spawn_bloqueo(self, ev):
        """corta la calle por donde vas, un poco más adelante.

        busca un tramo recto (no un cruce) delante del auto, y la barricada
        ocupa los dos carriles: hay que doblar antes o saltarla por la vereda.
        nunca encima de un auto, del banco, de una rampa ni de la misión.
        """
        car = self.car
        rumbo = car.va if car.spd >= 0 else car.va + math.pi
        prohibidos = [(car.x, car.y)] + [(c.x, c.y) for c in self.cops]
        prohibidos.append(self.banco_xy)
        prohibidos += [(o[0], o[1]) for o in self.objetivos()]
        for _ in range(50):
            tx, ty = self.rng.choice(self.roads)
            vert, horiz = tx % B < 2, ty % B < 2
            if vert == horiz or not (3 <= (ty % B if vert else tx % B) <= 6):
                continue                       # un cruce, o pegado a la esquina
            x, y = tx * TILE + 8, ty * TILE + 8
            d = math.hypot(x - car.x, y - car.y)
            if not 120 < d < 250:
                continue
            if abs(_wrap(math.atan2(y - car.y, x - car.x) - rumbo)) > 0.7:
                continue
            if vert:
                x0 = tx - tx % B
                tiles = ((x0, ty), (x0 + 1, ty))
                eje = 1
            else:
                y0 = ty - ty % B
                tiles = ((tx, y0), (tx, y0 + 1))
                eje = 0
            if any(t in self.city.ramps or t in self.city.extra for t in tiles):
                continue
            cx = sum(t[0] for t in tiles) * TILE / 2 + 8
            cy = sum(t[1] for t in tiles) * TILE / 2 + 8
            if any((px - cx) ** 2 + (py - cy) ** 2 < 48 ** 2 for px, py in prohibidos):
                continue
            self.city.extra.update(tiles)
            self.bloqueos.append({"tiles": tiles, "x": cx, "y": cy, "eje": eje,
                                  "t": BLOQUEO_TTL})
            ev.append(("bloqueo", cx, cy))
            return True
        return False

    # --- misiones ----------------------------------------------------------
    def objetivos(self):
        """a dónde apuntan las flechas: (x, y, tipo, etiqueta)."""
        out = []
        m = self.mision
        if m is not None:
            if m["tipo"] == "entrega":
                out.append((m["x"], m["y"],
                            "paquete" if m["fase"] == 0 else "destino", ""))
            elif m["tipo"] == "ruta":
                x, y = m["pts"][m["n"]]
                out.append((x, y, "meta", str(m["n"] + 1)))
        if self.money >= BANCO_MIN:
            bx, by = self.banco_xy
            out.append((bx, by, "banco", "$"))
        return out

    def _nueva_mision(self, ev):
        tipos = ["entrega", "ruta"]
        if self.wanted >= 2:
            tipos += ["escape", "escape"]
        tipo = self.rng.choice(tipos)
        dur = MISION_T[tipo]
        if self.time < dur + 120:              # no cabe antes del final: no hay
            self.mision_t = 10 ** 9
            return
        car = self.car
        m = {"tipo": tipo, "t": dur, "t0": dur, "fase": 0}
        if tipo == "entrega":
            m["x"], m["y"] = self._lejos(self.roads, 100, 210)
        elif tipo == "ruta":
            pts = []
            cx, cy = car.x, car.y
            for _ in range(3):
                cx, cy = self._anillo(cx, cy, self.roads, 120, 210)
                pts.append((cx, cy))
            m["pts"], m["n"] = pts, 0
        else:
            m["cx"], m["cy"], m["r"] = car.x, car.y, ESCAPE_R
        self.mision = m
        ev.append(("mision", tipo))

    def _cerrar_mision(self, ev, ok):
        m = self.mision
        self.mision = None
        self.mision_t = MISION_GAP
        if not ok:
            ev.append(("mision_fail", m["tipo"]))
            return
        pago = MISION_PAGO[m["tipo"]] + (m["t"] // 60) * MISION_SEG
        self.money += pago
        self.misiones_ok += 1
        ev.append(("mision_ok", self.car.x, self.car.y, pago, m["tipo"]))
        if m["tipo"] == "escape":
            self._bajar_estrella(ev, "cerco")

    def _misiones(self, ev):
        m = self.mision
        if m is None:
            self.mision_t -= 1
            if self.mision_t <= 0:
                self._nueva_mision(ev)
            return
        car = self.car
        m["t"] -= 1
        tipo = m["tipo"]
        if tipo == "escape":
            if self.wanted == 0:               # el soborno te sacó del cerco
                self.mision = None
                self.mision_t = MISION_GAP
                return
            if (car.x - m["cx"]) ** 2 + (car.y - m["cy"]) ** 2 > m["r"] ** 2:
                self._cerrar_mision(ev, True)
                return
        else:
            if tipo == "entrega":
                tx, ty = m["x"], m["y"]
            else:
                tx, ty = m["pts"][m["n"]]
            if (car.x - tx) ** 2 + (car.y - ty) ** 2 < MISION_R ** 2:
                if tipo == "entrega" and m["fase"] == 0:
                    m["fase"] = 1
                    m["x"], m["y"] = self._lejos(self.roads, 230, 400)
                    ev.append(("mision_paso", tx, ty, "paquete"))
                elif tipo == "ruta" and m["n"] < len(m["pts"]) - 1:
                    m["n"] += 1
                    ev.append(("mision_paso", tx, ty, str(m["n"])))
                else:
                    self._cerrar_mision(ev, True)
                    return
        if m["t"] <= 0:
            self._cerrar_mision(ev, False)

    # --- un frame --------------------------------------------------------
    def step(self, thr, steer):
        ev = []
        if self.over:
            return ev
        car = self.car
        if self.nitro > 0:
            self.nitro -= 1
            car.maxspd = 5.4
            if self.nitro == 0:
                car.maxspd = Car.MAXSPD
        if self.iman > 0:
            self.iman -= 1
        if self.grace > 0:
            self.grace -= 1
        if self.ramp_cd > 0:
            self.ramp_cd -= 1

        volaba = car.air > 0
        car.step(thr, steer, self.city)
        if car.crashed:
            ev.append(("choque", car.x, car.y))
            self.drift = 0                          # el derrape se pierde
            if self.racha:
                self.racha = 0                      # chocar te corta la racha
                ev.append(("racha_rota", car.x, car.y))

        # rampas y aterrizaje
        if volaba:
            self.vuelo += 1
            if car.air == 0:
                if not car.crashed:
                    pago = int((100 + self.vuelo * 3) // 10) * 10
                    self.money += pago
                    self.saltos += 1
                    ev.append(("aterrizaje", car.x, car.y, pago))
                self.vuelo = 0
                self.ramp_cd = RAMPA_CD
        elif self.ramp_cd == 0 and car.spd > RAMPA_SPD:
            eje = self.city.ramps.get((int(car.x // TILE), int(car.y // TILE)))
            if eje is not None:
                al = abs(math.cos(car.va)) if eje == 0 else abs(math.sin(car.va))
                if al > 0.75:
                    car.air = int(8 + car.spd * 7)
                    self.vuelo = 0
                    self.drift = 0
                    ev.append(("salto", car.x, car.y))

        # derrape: cuenta mientras la cola va abierta a velocidad
        ang = car.drift_ang()
        if car.air == 0 and car.spd > DRIFT_SPD and ang > DRIFT_ANG:
            self.drift += 1
        elif self.drift and (ang < 0.18 or car.spd < 1.2 or car.air):
            if self.drift >= DRIFT_MIN:
                pago = min(DRIFT_CAP, 50 + (self.drift - DRIFT_MIN) // 10 * 25)
                self.money += pago
                self.derrapes += 1
                if self.racha:
                    self.racha_t = max(self.racha_t, RACHA_TTL // 2)
                ev.append(("derrape", car.x, car.y, pago))
            self.drift = 0

        # fajos: el imán los arrastra, el auto los levanta
        quedan = []
        for b in self.bills:
            dx, dy = car.x - b[0], car.y - b[1]
            d2 = dx * dx + dy * dy
            if self.iman and d2 < IMAN_R * IMAN_R and d2 > 1:
                d = math.sqrt(d2)
                b[0] += dx / d * 2.4
                b[1] += dy / d * 2.4
                d2 = (car.x - b[0]) ** 2 + (car.y - b[1]) ** 2
            if d2 < RECOGE * RECOGE:
                monto = VALOR * self.mult()
                self.money += monto
                self.racha += 1
                self.racha_t = RACHA_TTL
                ev.append(("fajo", b[0], b[1], monto))
                self._spawn_bill()
            else:
                quedan.append(b)
        self.bills = quedan

        # el banco
        bx, by = self.banco_xy
        if self.money >= BANCO_MIN and \
                (car.x - bx) ** 2 + (car.y - by) ** 2 < BANCO_R * BANCO_R:
            self._depositar(ev)

        # la racha se enfría sola si dejas de levantar
        if self.racha:
            self.racha_t -= 1
            if self.racha_t <= 0:
                self.racha = 0
                ev.append(("racha_fria", car.x, car.y))

        # poderes
        self.power_t -= 1
        if self.power_t <= 0 and len(self.powers) < POWERS_MAX:
            self._spawn_power()
            self.power_t = POWER_GAP
        quedan = []
        for p in self.powers:
            if (car.x - p[0]) ** 2 + (car.y - p[1]) ** 2 < 14 * 14:
                self._tomar_power(p[2], ev)
            else:
                quedan.append(p)
        self.powers = quedan

        # peatones (volando les pasas por encima)
        for ped in self.peds:
            if ped.step(self.city, car) and abs(car.spd) > 0.6 and not car.air:
                ped.gone = True
                self.atropellos += 1
                self.racha = 0
                ev.append(("atropello", ped.x, ped.y))
        vivos = [p for p in self.peds if not p.gone]
        faltan = 14 - len(vivos)
        self.peds = vivos
        for _ in range(faltan):
            self._spawn_ped()

        self._misiones(ev)
        self._recalcular_wanted(ev)

        # patrullas
        cerca = False
        for cop in self.cops:
            if cop.step(self.city, car.x, car.y) and self.grace <= 0 \
                    and not car.air:
                self._cobrar(ev, cop.x, cop.y, "embiste")
                cop.stun = BUST_STUN
                car.spd *= -0.35                    # el embiste te rebota
            if (cop.x - car.x) ** 2 + (cop.y - car.y) ** 2 < EVADE_R * EVADE_R:
                cerca = True

        # helicóptero
        if self.wanted >= HELI_WANTED:
            if self.heli is None:
                a = self.rng.uniform(0, math.tau)
                self.heli = Heli(max(0, min(MAP_PX, car.x + math.cos(a) * 300)),
                                 max(0, min(MAP_PY, car.y + math.sin(a) * 300)))
                ev.append(("heli", self.heli.x, self.heli.y))
            if self.heli.step(car.x, car.y) and not car.air:
                self.foco += 1
                cerca = True
            else:
                self.foco = max(0, self.foco - 1)
            if self.foco >= FOCO_MARCA and self.grace <= 0:
                self.foco = 0
                self._cobrar(ev, car.x, car.y, "marcado")
        elif self.heli is not None:
            self.heli = None
            self.foco = 0

        # bloqueos
        for b in self.bloqueos:
            b["t"] -= 1
        if any(b["t"] <= 0 for b in self.bloqueos):
            for b in self.bloqueos:
                if b["t"] <= 0:
                    self.city.extra.difference_update(b["tiles"])
            self.bloqueos = [b for b in self.bloqueos if b["t"] > 0]
        if self.wanted >= BLOQUEO_WANTED:
            self.bloqueo_t -= 1
            if self.bloqueo_t <= 0:
                self.bloqueo_t = BLOQUEO_GAP
                if len(self.bloqueos) < BLOQUEOS_MAX and car.spd > 1.0:
                    self._spawn_bloqueo(ev)
        else:
            self.bloqueo_t = BLOQUEO_GAP // 2

        # perderlos: nadie te tiene a tiro un rato y se cae una estrella
        if self.wanted and not cerca:
            self.evade += 1
            if self.evade >= EVADE_T:
                self.evade = 0
                self._bajar_estrella(ev, "perdidos")
        else:
            self.evade = 0

        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            self.mision = None
            ev.append(("fin", car.x, car.y))
        return ev

    def _cobrar(self, ev, x, y, tipo):
        """un embiste o la marca del helicóptero: te sacan un tajo del bolsillo."""
        perdido = int(self.money * BUST_COST)
        self.money = max(0, self.money - perdido)
        self.racha = 0
        self.drift = 0
        self.busts += 1
        self.grace = BUST_GRACE
        ev.append((tipo, x, y, perdido))

    def _tomar_power(self, tipo, ev):
        if tipo == NITRO:
            self.nitro = NITRO_TTL
        elif tipo == IMAN:
            self.iman = IMAN_TTL
        elif tipo == SOBORNO:
            self._enfriar(ev)
        elif tipo == RELOJ:
            # sale del presupuesto común, y lo que no cabe en el marcador no se
            # cobra: agarrar un reloj con el tiempo lleno no te lo quema
            dar = min(RELOJ_BONUS, self.extra, TIME - self.time)
            self.extra -= dar
            self.time += dar
        ev.append(("power", self.car.x, self.car.y, tipo))


# --- letra grande ----------------------------------------------------------
# la fuente de pyxel es de 4x6: a la escala del teléfono (~1x en este juego de
# 384 px) se lee como hormigas. los números que importan (plata, reloj,
# misión) van al doble: cada glifo se lee una vez de la fuente y se guarda como
# tiras horizontales, que después se pintan con rect. son ~10 rects por letra.
_GLY = {}


def _glyph(ch):
    g = _GLY.get(ch)
    if g is not None:
        return g
    if ch == "$":
        # el $ de la fuente, al doble, se lee como una f: va dibujado a mano
        runs = [(1, -1, 1), (0, 0, 3), (0, 1, 1), (0, 2, 3), (2, 3, 1),
                (0, 4, 3), (1, 5, 1)]
        _GLY[ch] = runs
        return runs
    base = _ACUTE.get(ch) or _TILDE.get(ch) or ch
    flip = base == "¡"
    img = pyxel.Image(8, 8)
    img.cls(0)
    img.text(0, 0, "!" if flip else base, 1)
    runs = []
    for gy in range(6):
        gx = 0
        while gx < 4:
            if img.pget(gx, gy):
                s0 = gx
                while gx < 4 and img.pget(gx, gy):
                    gx += 1
                runs.append((s0, (4 - gy) if flip else gy, gx - s0))
            else:
                gx += 1
    if ch in _ACUTE:
        runs += [(2, -2, 1), (1, -1, 1)]
    elif ch in _TILDE:
        runs += [(0, -1, 1), (1, -2, 1), (2, -1, 1)]
    _GLY[ch] = runs
    return runs


def big(x, y, s, col, k=2, sh=SHADOW):
    """texto a k veces, con sombra para leerse sobre la ciudad."""
    x, y = int(x), int(y)
    for i, ch in enumerate(s):
        if ch == " ":
            continue
        ox = x + i * 4 * k
        for gx, gy, w in _glyph(ch):
            if sh is not None:
                pyxel.rect(ox + gx * k + 1, y + gy * k + 1, w * k, k, sh)
            pyxel.rect(ox + gx * k, y + gy * k, w * k, k, col)


def big_w(s, k=2):
    return len(s) * 4 * k


def cbig(cx, y, s, col, k=2, sh=SHADOW):
    big(cx - big_w(s, k) / 2, y, s, col, k, sh)


def stext(x, y, s, col, sh=SHADOW):
    """texto chico con sombra: sobre el mapa, gris sobre gris no se lee."""
    text(int(x) + 1, int(y) + 1, s, sh)
    text(int(x), int(y), s, col)


def con_dedo():
    """¿se juega con los controles táctiles? la página los muestra con
    `pointer: coarse` **o** si hay `ontouchstart` (una notebook con pantalla
    táctil), y `web.is_touch()` sólo mira lo primero. si diera falso con los
    botones en pantalla, el auto quedaría sin acelerador: se mira también la
    clase que pone la página."""
    if not web.ACTIVE:
        return False
    if web.is_touch():
        return True
    try:
        import js
        return bool(js.document.body.classList.contains("touch"))
    except Exception:
        return False


MISION_COL = {"entrega": ORANGE, "ruta": NITRO1, "escape": LIGHTR}
MISION_TIT = {"entrega": "ENTREGA", "ruta": "CARRERA", "escape": "CERCO"}
OBJ_COL = {"paquete": ORANGE, "destino": ORANGE, "meta": NITRO1, "banco": BILL2}
RW, RH = 72, 52                  # el radar: una ventana del plano, a 2 px por tile


class World:
    """la partida jugándose: lee el teclado, dibuja y le pone chispas."""

    def __init__(self, seed=None, auto=None):
        self.p = Partida(seed)
        self.fx = fx.Fx(gravity=0.0, max_parts=260)
        self.fx.destello(WHITE)
        # en el celular el auto acelera solo: el pulgar derecho queda para el
        # freno (y freno + doblar = derrape). con teclado, como siempre.
        self.auto = con_dedo() if auto is None else auto
        self.combo_pop = 0
        self.city_img = None
        self.radar = None
        self.exhaust = 0
        self.marcas = deque(maxlen=420)     # huellas de goma en el asfalto
        self.banner = None                  # [texto, col, vida, sub]
        self.f = 0                          # reloj de animación propio
        cx, cy = self._cam_target()
        self.camx, self.camy = cx, cy

    @property
    def over(self):
        return self.p.over

    @property
    def score(self):
        return self.p.score

    # --- update ----------------------------------------------------------
    def leer(self):
        up = pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W)
        down = pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S)
        if self.auto:
            thr = -1 if down else 1
        else:
            thr = (1 if up else 0) - (1 if down else 0)
        st = (1 if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D) else 0) \
            - (1 if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A) else 0)
        return thr, st

    def update(self):
        self.tick(*self.leer())

    def tick(self, thr, st):
        p = self.p
        antes = p.mult()
        for e in p.step(thr, st):
            self._efecto(e, antes)
        if p.mult() > antes:
            self.combo_pop = 26
            if p.mult() >= 3:
                self._banner("RACHA x%d" % p.mult(), GOLD)
        if self.combo_pop:
            self.combo_pop -= 1
        if self.banner:
            self.banner[2] -= 1
            if self.banner[2] <= 0:
                self.banner = None
        car = p.car
        self.exhaust += 1
        self.f += 1
        # humo del escape cuando aceleras fuerte, y llamarada con nitro
        if abs(car.spd) > 1.8 and self.exhaust % 3 == 0 and not car.air:
            back = car.a + math.pi
            self.fx.burst(car.x + math.cos(back) * 10, car.y + math.sin(back) * 10,
                          NITROFX if p.nitro else SMOKE,
                          n=3 if p.nitro else 2, speed=0.9, life=16,
                          spread=0.7, angle=back)
        # goma: derrapando o frenando fuerte quedan huellas y sale humo blanco
        if not car.air and (car.drift_ang() > 0.25 and car.spd > 1.5
                            or (car.mano and car.spd > 1.2)
                            or (thr < 0 and car.spd > 1.8)):
            ca, sa = math.cos(car.a), math.sin(car.a)
            for s in (-5, 5):
                wx = car.x - 8 * ca - s * sa
                wy = car.y - 8 * sa + s * ca
                self.marcas.append((int(wx), int(wy)))
                if self.exhaust % 2 == 0:
                    self.fx.burst(wx, wy, TIRE, n=1, speed=0.5, life=24,
                                  spread=math.tau)
        # la cámara mira hacia donde vas: más rápido, más adelante
        tx, ty = self._cam_target()
        self.camx += (tx - self.camx) * 0.10
        self.camy += (ty - self.camy) * 0.10
        # pero el auto nunca se va al borde: con la cámara lenta y el nitro
        # quedaba pegado a la orilla, sin ver lo que venía
        self.camx = max(car.x - W + 90, min(car.x - 90, self.camx))
        self.camy = max(car.y - VIEW_H + 70, min(car.y - 70, self.camy))
        self.camx = max(0, min(MAP_PX - W, self.camx))
        self.camy = max(0, min(MAP_PY - VIEW_H, self.camy))
        self.fx.update()

    def _cam_target(self):
        car = self.p.car
        look = 30
        tx = car.x + math.cos(car.va) * car.spd * look - W / 2
        ty = car.y + math.sin(car.va) * car.spd * look * 0.8 - VIEW_H / 2
        return (max(0, min(MAP_PX - W, tx)), max(0, min(MAP_PY - VIEW_H, ty)))

    def _banner(self, s, col, sub="", life=60):
        self.banner = [s, col, life, sub, life]

    def _efecto(self, e, mult_antes):
        """cada evento de la lógica se vuelve chispas, cartel y temblor."""
        kind = e[0]
        p = self.p
        car = p.car
        if kind == "fajo":
            _, x, y, monto = e
            self.fx.burst(x, y, CASH, n=14, speed=1.9, life=26)
            self.fx.popup(x, y - 8, "$%d" % monto, BILL2)
        elif kind == "choque":
            _, x, y = e
            self.fx.burst(x, y, SPARKS, n=12, speed=2.1, life=18)
            self.fx.shake(3)
        elif kind in ("embiste", "marcado"):
            _, x, y, perdido = e
            self.fx.burst(x, y, SPARKS, n=26, speed=2.8, life=26)
            self.fx.popup(car.x, car.y - 12, "-$%d" % perdido, LIGHTR)
            self.fx.shake(6)
            self.fx.destello(LIGHTR)
            if kind == "marcado":
                self._banner("TE MARCARON", LIGHTR, "el foco te cobró -$%d" % perdido)
        elif kind == "atropello":
            _, x, y = e
            self.fx.burst(x, y, (WHITE, SKIN, PED1), n=10, speed=1.6, life=22)
            self.fx.popup(x, y - 10, "EH!", WHITE)
            self.fx.shake(2)
        elif kind == "power":
            _, x, y, tipo = e
            self.fx.burst(x, y, (WHITE, GOLD, MAGENTA), n=22, speed=2.4, life=30)
            self._banner(POWER_NAME[tipo], GOLD)
            self.fx.destello(GOLD)
        elif kind == "deposito":
            _, x, y, monto, propina = e
            self.fx.burst(x, y, CASH, n=30, speed=2.6, life=34)
            self._banner("A SALVO $%d" % monto, BILL2,
                         "+$%d de propina" % propina if propina else "")
            self.fx.shake(3)
            self.fx.destello(BILL2)
        elif kind == "wanted":
            sub = ""
            if e[1] == BLOQUEO_WANTED:
                sub = "cortan las calles: ojo con los bloqueos"
            elif e[1] == HELI_WANTED:
                sub = "llega el helicóptero: escapa de su foco"
            elif e[1] == WANTED_MAX:
                sub = "búsqueda máxima"
            self._banner("%d ESTRELLAS" % e[1] if e[1] > 1 else "1 ESTRELLA",
                         LIGHTR, sub)
            self.fx.destello(LIGHTR)
        elif kind == "estrella_menos":
            _, w, motivo = e
            self._banner("TE PERDIERON" if motivo == "perdidos" else "FUERA DEL CERCO",
                         ACCENT, "una estrella menos")
            self.fx.burst(car.x, car.y, (WHITE, ACCENT, GRASS1), n=18, speed=2.2)
        elif kind == "enfriado":
            self._banner("TE SOLTARON", ACCENT, "sin estrellas")
            self.fx.destello(ACCENT)
        elif kind == "racha_rota":
            _, x, y = e
            if mult_antes > 1:
                self.fx.popup(x, y - 14, "RACHA ROTA", WHITE)
        elif kind == "salto":
            self.fx.burst(e[1], e[2], GOLDFX, n=10, speed=1.6, life=18)
            self.fx.popup(e[1], e[2] - 16, "SALTO!", GOLD)
        elif kind == "aterrizaje":
            _, x, y, pago = e
            self.fx.burst(x, y, SMOKE, n=16, speed=1.8, life=22)
            self.fx.shake(4)
            self._banner("SALTO $%d" % pago, GOLD)
        elif kind == "derrape":
            _, x, y, pago = e
            self.fx.burst(x, y, GOLDFX, n=12, speed=1.8, life=22)
            self._banner("DERRAPE $%d" % pago, GOLD)
        elif kind == "mision":
            tipo = e[1]
            sub = {"entrega": "recoge el paquete y llévalo",
                   "ruta": "pasa por las 3 metas",
                   "escape": "sal del círculo rojo"}[tipo]
            self._banner(MISION_TIT[tipo], MISION_COL[tipo], sub, life=90)
            self.fx.destello(MISION_COL[tipo])
        elif kind == "mision_paso":
            _, x, y, cual = e
            self.fx.burst(x, y, (WHITE, ORANGE, NITRO1), n=18, speed=2.2, life=24)
            self.fx.popup(x, y - 12, "PAQUETE!" if cual == "paquete"
                          else "META %s" % cual, WHITE)
        elif kind == "mision_ok":
            _, x, y, pago, tipo = e
            self.fx.burst(x, y, GOLDFX, n=34, speed=3.0, life=34)
            self._banner("MISIÓN +$%d" % pago, GOLD, "%s cumplida" % MISION_TIT[tipo].lower())
            self.fx.shake(4)
            self.fx.destello(GOLD)
        elif kind == "mision_fail":
            self._banner("SE ACABÓ EL TIEMPO", DIM, "misión perdida", life=60)
        elif kind == "bloqueo":
            self.fx.burst(e[1], e[2], (WHITE, LIGHTR, LIGHTB), n=12, speed=1.6)
        elif kind == "heli":
            pass

    # --- dibujo ----------------------------------------------------------
    def _bake_city(self):
        """la ciudad entera pintada UNA vez en una imagen de 704×544.

        antes eran ~450 tiles con 4-6 rects cada uno, todos los frames: la mitad
        del costo del juego. ahora es un solo blt de la ventana visible.
        """
        img = pyxel.Image(MAP_PX, MAP_PY)
        for ty in range(MH):
            for tx in range(MW):
                self._tile(img, tx * TILE, ty * TILE, tx, ty)
        for (tx, ty), eje in self.p.city.ramps.items():
            self._rampa(img, tx * TILE, ty * TILE, eje, tx, ty)
        self.city_img = img

    def draw(self):
        if self.city_img is None:
            self._bake_city()
        p = self.p
        pyxel.cls(BG)
        sx, sy = self.fx.offset()
        camx = int(self.camx) - sx                   # el temblor mueve la cámara
        camy = int(self.camy) - sy
        oy = HUD - camy                              # mundo -> pantalla, en y
        pyxel.blt(0, HUD, self.city_img, camx, camy, W, VIEW_H)
        for x, y in self.marcas:
            pyxel.pset(x - camx, y + oy, SKID)
        for b in p.bloqueos:
            self._bloqueo(b, camx, oy)
        m = p.mision
        if m is not None:
            self._mision_mundo(m, camx, oy)
        bx, by = p.banco_xy
        self._banco(bx - camx, by + oy)
        for pw in p.powers:
            self._power(pw[0] - camx, pw[1] + oy, pw[2])
        for b in p.bills:
            self._bill(b[0] - camx, b[1] + oy)
        for ped in p.peds:
            self._ped(ped, camx, oy)
        if p.heli is not None:
            self._foco(p.heli.x - camx, p.heli.y + oy)
        self.fx.draw(camx, -oy)
        for cop in p.cops:
            self._car_sprite(cop.x - camx, cop.y + oy, cop.car.a, COP1, COP2, cop=True)
        car = p.car
        if p.grace <= 0 or (self.f // 4) % 2:
            alto = 0.0
            if car.air:
                total = car.air + p.vuelo
                alto = math.sin(math.pi * p.vuelo / max(1, total))
            self._car_sprite(car.x - camx, car.y + oy, car.a, CARBODY, CARROOF,
                             k=1 + 0.45 * alto, sombra=2 + int(9 * alto))
        if p.iman:
            self._halo(car.x - camx, car.y + oy)
        if p.heli is not None:
            self._heli(p.heli.x - camx, p.heli.y + oy)
        self.fx.draw_flash(0, HUD, W, VIEW_H)
        self._flechas(camx, oy)
        self._radar()
        self._hud()
        self._mision_hud()
        self._draw_banner()

    def _tile(self, img, px, py, tx, ty):
        t = self.p.city.tile(tx, ty)
        if t == ROAD:
            img.rect(px, py, TILE, TILE, ASPHALT)
            if tx % B == 0 and (ty % 3):
                img.rect(px + TILE - 1, py, 2, TILE, LINE)
            if ty % B == 0 and (tx % 3):
                img.rect(px, py + TILE - 1, TILE, 2, LINE)
        elif t == SIDEWALK:
            img.rect(px, py, TILE, TILE, SIDE)
            img.rectb(px, py, TILE, TILE, SIDE2)
        elif t == GRASS:
            img.rect(px, py, TILE, TILE, GRASS1)
            img.pset(px + 4, py + 5, GRASS2)
            img.pset(px + 11, py + 10, GRASS2)
        elif t == TREE:
            img.rect(px, py, TILE, TILE, GRASS1)
            img.rect(px + 7, py + 8, 2, 5, TRUNK)
            img.circ(px + 8, py + 6, 5, TREEDK)
            img.circ(px + 8, py + 6, 4, TREETOP)
        elif t == FOUNT:
            img.rect(px, py, TILE, TILE, SIDE)
            img.circ(px + 8, py + 8, 6, SIDE2)
            img.circ(px + 8, py + 8, 4, WATER)
            img.pset(px + 7, py + 6, WHITE)
        else:  # BLD
            bx, by = tx // B, ty // B
            base = (BLD1, BLD2, BLD3)[(bx * 7 + by * 11) % 3]
            img.rect(px, py, TILE, TILE, base)
            img.rectb(px, py, TILE, TILE, ROOF)
            for wy in (4, 10):
                for wx in (4, 10):
                    lit = (tx * 3 + ty * 5 + wx + wy) % 3 == 0
                    img.rect(px + wx, py + wy, 2, 2, GLASS if lit else ROOF)

    def _rampa(self, img, px, py, eje, tx, ty):
        """una rampa amarilla con franjas: la flecha dice hacia dónde se salta."""
        if eje == 0:                           # se salta en x: franjas verticales
            img.rect(px + 2, py, 12, TILE, GOLD)
            for i in range(0, TILE, 4):
                img.rect(px + 2, py + i, 12, 2, SHADOW)
            img.rect(px + 2, py, 2, TILE, ORANGE)
            img.rect(px + 12, py, 2, TILE, ORANGE)
        else:
            img.rect(px, py + 2, TILE, 12, GOLD)
            for i in range(0, TILE, 4):
                img.rect(px + i, py + 2, 2, 12, SHADOW)
            img.rect(px, py + 2, TILE, 2, ORANGE)
            img.rect(px, py + 12, TILE, 2, ORANGE)

    def _banco(self, cx, cy):
        """la boca del banco: un rombo verde en la calle con el $ adentro. late
        cuando llevas lo suficiente como para depositar."""
        cx, cy = int(cx), int(cy)
        if not (-20 < cx < W + 20 and HUD - 20 < cy < H + 20):
            return
        activo = self.p.money >= BANCO_MIN
        r = BANCO_R - 2 + ((self.f // 5) % 2 if activo else 0)
        col = BILL2 if activo else BILL
        for i in range(4):
            a0 = i * math.pi / 2 + self.f * 0.03
            a1 = a0 + math.pi / 2
            pyxel.line(int(cx + math.cos(a0) * r), int(cy + math.sin(a0) * r),
                       int(cx + math.cos(a1) * r), int(cy + math.sin(a1) * r), col)
        pyxel.rect(cx - 7, cy - 6, 14, 12, SHADOW)
        pyxel.rectb(cx - 7, cy - 6, 14, 12, col)
        if activo:
            big(cx - 3, cy - 5, "$", col, k=2, sh=None)
        else:
            text(cx - 1, cy - 2, "$", col)

    def _bill(self, cx, cy):
        """un fajo de billetes, flotando apenas para que se vea desde lejos."""
        cx, cy = int(cx), int(cy + (self.f // 8) % 2)
        if not (-8 < cx < W + 8 and HUD - 8 < cy < H + 8):
            return
        pyxel.rect(cx - 5, cy - 1, 10, 5, SHADOW)
        pyxel.rect(cx - 5, cy - 3, 10, 5, BILL)
        pyxel.rect(cx - 5, cy - 3, 10, 1, BILL2)
        pyxel.pset(cx, cy - 1, BILL2)
        pyxel.pset(cx - 3, cy - 1, BILL2)
        pyxel.pset(cx + 3, cy - 1, BILL2)

    def _power(self, cx, cy, tipo):
        """la caja de poder: late y trae su símbolo adentro."""
        cx, cy = int(cx), int(cy)
        if not (-10 < cx < W + 10 and HUD - 10 < cy < H + 10):
            return
        r = 7 + (self.f // 5) % 2
        pyxel.rect(cx - r, cy - r, r * 2, r * 2, SHADOW)
        col = (NITRO1, MAGENTA, ACCENT, GOLD)[tipo]
        pyxel.rectb(cx - r, cy - r, r * 2, r * 2, col)
        pyxel.rectb(cx - r + 1, cy - r + 1, r * 2 - 2, r * 2 - 2, WHITE)
        if tipo == NITRO:                                  # un rayo
            pyxel.line(cx + 1, cy - 4, cx - 2, cy, col)
            pyxel.line(cx - 2, cy, cx + 1, cy, col)
            pyxel.line(cx + 1, cy, cx - 1, cy + 4, col)
        elif tipo == IMAN:                                 # una herradura
            pyxel.rectb(cx - 3, cy - 4, 7, 6, col)
            pyxel.rect(cx - 2, cy - 1, 5, 4, SHADOW)
            pyxel.rect(cx - 3, cy + 1, 2, 3, col)
            pyxel.rect(cx + 2, cy + 1, 2, 3, col)
        elif tipo == SOBORNO:                              # un billete doblado
            pyxel.rect(cx - 4, cy - 2, 9, 5, col)
            pyxel.pset(cx, cy, SHADOW)
        else:                                              # un reloj
            pyxel.circb(cx, cy, 4, col)
            pyxel.line(cx, cy, cx, cy - 3, col)
            pyxel.line(cx, cy, cx + 2, cy, col)

    def _ped(self, ped, camx, oy):
        x, y = int(ped.x - camx), int(ped.y + oy)
        if not (-8 < x < W + 8 and HUD - 8 < y < H + 8):
            return
        ropa = (PED1, PED2, PED3)[int(ped.x + ped.y) % 3]
        paso = (self.f // (4 if ped.scared else 9)) % 2
        pyxel.rect(x - 1, y + 3, 3, 1, SHADOW)
        pyxel.rect(x - 1, y - 1, 3, 4, ropa)               # cuerpo
        pyxel.pset(x - 1 + paso, y + 3, ropa)              # la pierna que pisa
        pyxel.rect(x - 1, y - 3, 3, 2, SKIN)               # cabeza
        if ped.scared:
            pyxel.pset(x + (2 if paso else -2), y - 5, WHITE)   # gotita de susto

    def _car_sprite(self, sx, sy, a, body, roof, cop=False, k=1.0, sombra=2):
        if not (-24 < sx < W + 24 and HUD - 24 < sy < H + 24):
            return
        c1, s1 = math.cos(a), math.sin(a)
        cosa, sina = c1 * k, s1 * k

        def corner(f, s):
            return (int(sx + f * cosa - s * sina), int(sy + f * sina + s * cosa))

        fl, fr = corner(11, -6), corner(11, 6)
        bl, br = corner(-11, -6), corner(-11, 6)
        # la sombra queda del tamaño real, en el piso: es lo que hace leer el
        # salto (el auto crece y se separa de su sombra)
        sh = [(int(sx + f * c1 - s * s1) + sombra, int(sy + f * s1 + s * c1) + sombra)
              for f, s in ((11, -6), (11, 6), (-11, 6), (-11, -6))]
        pyxel.tri(*sh[0], *sh[1], *sh[2], SHADOW)
        pyxel.tri(*sh[0], *sh[2], *sh[3], SHADOW)
        pyxel.tri(*fl, *fr, *br, body)
        pyxel.tri(*fl, *br, *bl, body)
        rl, rr = corner(4, -4), corner(4, 4)
        rbl, rbr = corner(-6, -4), corner(-6, 4)
        pyxel.tri(*rl, *rr, *rbr, roof)
        pyxel.tri(*rl, *rbr, *rbl, roof)
        wl, wr = corner(9, -4), corner(9, 4)
        pyxel.tri(*rl, *rr, *wr, GLASS)
        pyxel.tri(*rl, *wr, *wl, GLASS)
        for s in (-4, 4):
            hx, hy = corner(11, s)
            pyxel.pset(hx, hy, HEAD)
        if cop:                                    # balizas rojo/azul alternando
            izq = (self.f // 4) % 2
            for s, on in ((-3, izq), (3, not izq)):
                bxp, byp = corner(0, s)
                pyxel.rect(bxp - 1, byp - 1, 2, 2, LIGHTR if on else LIGHTB)

    def _halo(self, cx, cy):
        """el anillo del imán, girando, para que se note que está activo."""
        for i in range(8):
            a = self.f * 0.09 + i * math.tau / 8
            pyxel.pset(int(cx + math.cos(a) * IMAN_R * 0.5),
                       int(cy + math.sin(a) * IMAN_R * 0.5), MAGENTA)

    def _bloqueo(self, b, camx, oy):
        """la barricada: vallas a franjas en los dos carriles y una patrulla
        cruzada con las balizas prendidas. titila cuando está por irse."""
        if b["t"] < 90 and (self.f // 4) % 2:
            return
        cx, cy = int(b["x"] - camx), int(b["y"] + oy)
        if not (-40 < cx < W + 40 and HUD - 40 < cy < H + 40):
            return
        for tx, ty in b["tiles"]:
            px, py = int(tx * TILE - camx), int(ty * TILE + oy)
            if b["eje"] == 1:                       # calle vertical: valla horizontal
                pyxel.rect(px, py + 5, TILE, 6, WHITE)
                for i in range(0, TILE, 6):
                    pyxel.rect(px + i, py + 5, 3, 6, LIGHTR)
                pyxel.rect(px, py + 11, TILE, 1, SHADOW)
            else:
                pyxel.rect(px + 5, py, 6, TILE, WHITE)
                for i in range(0, TILE, 6):
                    pyxel.rect(px + 5, py + i, 6, 3, LIGHTR)
                pyxel.rect(px + 11, py, 1, TILE, SHADOW)
        a = 0.0 if b["eje"] == 1 else math.pi / 2
        off = (0, -13) if b["eje"] == 1 else (-13, 0)
        self._car_sprite(cx + off[0], cy + off[1], a, COP1, COP2, cop=True)

    def _mision_mundo(self, m, camx, oy):
        f = self.f
        if m["tipo"] == "escape":
            # el cerco: un círculo rojo a trazos que gira
            cx, cy, r = m["cx"] - camx, m["cy"] + oy, m["r"]
            col = LIGHTR if (f // 6) % 2 else ORANGE
            n = 48
            for i in range(n):
                if i % 2:
                    continue
                a0 = i * math.tau / n + f * 0.01
                a1 = a0 + math.tau / n
                x0, y0 = cx + math.cos(a0) * r, cy + math.sin(a0) * r
                x1, y1 = cx + math.cos(a1) * r, cy + math.sin(a1) * r
                pyxel.line(int(x0), int(y0), int(x1), int(y1), col)
                pyxel.line(int(x0) + 1, int(y0), int(x1) + 1, int(y1), col)
            return
        if m["tipo"] == "entrega":
            x, y = int(m["x"] - camx), int(m["y"] + oy)
            if m["fase"] == 0:                      # el paquete, saltando
                yy = y - 2 - (f // 6) % 3
                pyxel.circb(x, y, 10 + (f // 5) % 3, ORANGE)
                pyxel.rect(x - 5, yy - 4, 10, 8, TRUNK)
                pyxel.rectb(x - 5, yy - 4, 10, 8, ORANGE)
                pyxel.line(x, yy - 4, x, yy + 3, GOLD)
                pyxel.line(x - 5, yy, x + 4, yy, GOLD)
            else:                                   # el punto de entrega
                for rr in (14, 9):
                    pyxel.circb(x, y, rr + (f // 4) % 3, ORANGE if rr == 14 else GOLD)
                pyxel.rect(x - 1, y - 14, 2, 14, WHITE)
                pyxel.tri(x + 1, y - 14, x + 9, y - 11, x + 1, y - 8, ORANGE)
            return
        # la carrera: la meta que toca, grande; las siguientes, chicas
        for i in range(m["n"], len(m["pts"])):
            x, y = int(m["pts"][i][0] - camx), int(m["pts"][i][1] + oy)
            if i == m["n"]:
                pyxel.circb(x, y, 12 + (f // 4) % 3, NITRO1)
                pyxel.circb(x, y, 9, WHITE)
                big(x - 3, y - 5, str(i + 1), WHITE, k=2)
            else:
                pyxel.circb(x, y, 6, NITRO2)
                text(x - 1, y - 2, str(i + 1), NITRO2)

    def _foco(self, x, y):
        """el foco del helicóptero en el piso: se pone rojo cuando te tiene."""
        x, y = int(x), int(y)
        caliente = self.p.foco > 0
        pyxel.dither(0.35)
        pyxel.circ(x, y, FOCO_R, LIGHTR if caliente else WHITE)
        pyxel.dither(1.0)
        pyxel.circb(x, y, FOCO_R, LIGHTR if caliente and (self.f // 4) % 2
                    else WHITE)
        if caliente:
            fx.bar(x - 14, y + FOCO_R + 3, 28, 3, self.p.foco / FOCO_MARCA,
                   LIGHTR, SHADOW)

    def _heli(self, x, y):
        x, y = int(x), int(y) - 18                  # vuela: se dibuja más arriba
        pyxel.circ(x + 6, y + 20, 5, SHADOW)
        pyxel.line(x, y, x - 13, y + 1, HELI1)       # cola
        pyxel.rect(x - 15, y - 2, 3, 5, HELI1)
        pyxel.circ(x, y, 5, HELI1)
        pyxel.circ(x + 2, y, 3, GLASS)
        a = self.f * 0.6
        for da in (0, math.pi / 2):
            c, s = math.cos(a + da) * 12, math.sin(a + da) * 12
            pyxel.line(int(x - c), int(y - s), int(x + c), int(y + s), TXT)
        pyxel.pset(x - 14, y, LIGHTR if (self.f // 6) % 2 else WHITE)

    # --- flechas, radar y hud ----------------------------------------------
    def _flechas(self, camx, oy):
        """a dónde ir: una flecha gorda en el borde de la pantalla por cada
        objetivo fuera de vista, con su ícono y la distancia. en el teléfono la
        pantalla es chica y el radar no alcanza para orientarse."""
        p = self.p
        car = p.car
        ccx, ccy = car.x - camx, car.y + oy
        f = self.f
        top = HUD + (30 if p.mision else 8)
        left, right, bot = 10, W - 10, H - 10
        for x, y, kind, lab in p.objetivos():
            col = OBJ_COL[kind]
            sx, sy = x - camx, y + oy
            if left <= sx <= right and HUD + 6 <= sy <= bot:
                # a la vista: una flecha que rebota encima del objetivo
                yy = int(sy) - 20 - (f // 5) % 3
                pyxel.tri(int(sx) - 5, yy, int(sx) + 5, yy, int(sx), yy + 6, col)
                pyxel.rect(int(sx) - 2, yy - 5, 5, 5, col)
                continue
            dx, dy = sx - ccx, sy - ccy
            a = math.atan2(dy, dx)
            # el punto del borde en esa dirección
            t = 1e9
            if dx > 0:
                t = min(t, (right - ccx) / dx)
            elif dx < 0:
                t = min(t, (left - ccx) / dx)
            if dy > 0:
                t = min(t, (bot - ccy) / dy)
            elif dy < 0:
                t = min(t, (top - ccy) / dy)
            ex, ey = ccx + dx * t, ccy + dy * t
            ca, sa = math.cos(a), math.sin(a)
            bx, by = ex - ca * 9, ey - sa * 9         # el centro del ícono
            tipx, tipy = ex + ca * 1, ey + sa * 1
            lx, ly = bx + math.cos(a + 1.9) * 8, by + math.sin(a + 1.9) * 8
            rx, ry = bx + math.cos(a - 1.9) * 8, by + math.sin(a - 1.9) * 8
            pyxel.tri(int(tipx), int(tipy), int(lx), int(ly), int(rx), int(ry), col)
            ix, iy = int(bx - ca * 5), int(by - sa * 5)
            pyxel.circ(ix, iy, 6, SHADOW)
            pyxel.circb(ix, iy, 6, col if (f // 8) % 2 else WHITE)
            if lab:
                text(ix - 1, iy - 2, lab, WHITE)
            elif kind == "paquete":
                pyxel.rect(ix - 3, iy - 2, 6, 5, ORANGE)
            else:
                pyxel.rect(ix - 1, iy - 3, 2, 6, WHITE)
            dist = "%dm" % (math.hypot(x - car.x, y - car.y) / 4)
            if abs(ey - top) < 2 or abs(ey - bot) < 2:     # borde de arriba/abajo
                tx_ = ix + 9 if ix < W - 40 else ix - 9 - len(dist) * 4
                ty_ = iy - 2
            else:                                          # costados
                tx_ = max(2, min(W - len(dist) * 4 - 2, ix - len(dist) * 2))
                ty_ = iy + 9
            stext(tx_, ty_, dist, col)
        # las patrullas que vienen y todavía no se ven: balizas en el borde
        if (f // 5) % 2:
            for cop in p.cops:
                sx, sy = cop.x - camx, cop.y + oy
                if 0 <= sx < W and HUD <= sy < H:
                    continue
                ex = max(3, min(W - 6, sx))
                ey = max(HUD + 3, min(H - 6, sy))
                pyxel.rect(int(ex), int(ey), 4, 4, LIGHTR if (f // 10) % 2 else LIGHTB)

    def _radar(self):
        """el plano, a 2 px por tile, en una ventana alrededor tuyo.

        se pinta UNA vez a una imagen y se estampa con blt; los puntos que se
        mueven van encima. lo que queda fuera de la ventana (el banco, la
        misión) se dibuja pegado al borde, para que siempre diga hacia dónde.
        """
        p = self.p
        if self.radar is None:
            img = pyxel.Image(MW * 2, MH * 2)
            for ty in range(MH):
                for tx in range(MW):
                    t = p.city.tile(tx, ty)
                    img.rect(tx * 2, ty * 2, 2, 2, MAPRD if t == ROAD else
                             (GRASS1 if t in (GRASS, TREE) else MAPBG))
            self.radar = img
        car = p.car
        u = int(max(0, min(MW * 2 - RW, car.x / TILE * 2 - RW / 2)))
        v = int(max(0, min(MH * 2 - RH, car.y / TILE * 2 - RH / 2)))
        mx, my = W - RW - 4, H - RH - 4
        pyxel.rect(mx - 2, my - 2, RW + 4, RH + 4, SHADOW)
        pyxel.blt(mx, my, self.radar, u, v, RW, RH)
        f = self.f

        def punto(x, y, n, col, borde=False):
            px = mx + x / TILE * 2 - u
            py = my + y / TILE * 2 - v
            if not borde and not (mx <= px < mx + RW and my <= py < my + RH):
                return
            px = max(mx, min(mx + RW - n, px - n // 2))
            py = max(my, min(my + RH - n, py - n // 2))
            pyxel.rect(int(px), int(py), n, n, col)

        for b in p.bills:
            punto(b[0], b[1], 2, BILL2)
        for pw in p.powers:
            punto(pw[0], pw[1], 3, GOLD)
        for b in p.bloqueos:
            punto(b["x"], b["y"], 3, WHITE)
        bx, by = p.banco_xy
        punto(bx, by, 4, BILL2 if (f // 8) % 2 else WHITE, borde=True)
        for x, y, kind, _ in p.objetivos():
            if kind != "banco":
                punto(x, y, 4, OBJ_COL[kind] if (f // 6) % 2 else WHITE, borde=True)
        if (f // 6) % 2:
            for cop in p.cops:
                punto(cop.x, cop.y, 3, LIGHTR)
            if p.heli is not None:
                punto(p.heli.x, p.heli.y, 3, MAGENTA)
        punto(car.x, car.y, 3, WHITE)
        pyxel.rectb(mx - 1, my - 1, RW + 2, RH + 2, DIM)

    def _hud(self):
        p = self.p
        f = self.f
        pyxel.rect(0, 0, W, HUD, PANEL)
        pyxel.rect(0, HUD - 1, W, 1, ASPHALT)
        # la plata que llevas encima: lo que te pueden sacar
        s = "$%d" % p.money
        big(4, 3, s, BILL2)
        x = 4 + big_w(s) + 6
        m = p.mult()
        if m > 1:
            col = GOLD if self.combo_pop and (f // 3) % 2 else ORANGE
            big(x, 3, "x%d" % m, col)
            fx.bar(x, 16, big_w("x%d" % m), 3, p.racha_t / RACHA_TTL, GOLD, ASPHALT)
        # lo guardado, chico, debajo
        if p.banco:
            text(4, 17, "banco $%d" % p.banco, BILL)
        # las estrellas, grandes y al centro. titilan mientras te pierden
        n = WANTED_MAX
        x0 = W // 2 - n * 13 // 2 + 6
        perdiendo = p.evade > 0 and (f // 6) % 2
        for i in range(n):
            lleno = i < p.wanted
            if lleno and not perdiendo:
                col = LIGHTR if (f // 8 + i) % 2 else GOLD
            elif lleno:
                col = DIM
            else:
                col = None
            self._estrella(x0 + i * 13, 10, col)
        if p.wanted:
            if p.evade > 0:
                fx.bar(x0 - 6, 20, n * 13 - 2, 3, p.evade / EVADE_T, ACCENT, ASPHALT)
            elif p.heli is not None:
                text(W // 2 - 22, 19, "helicóptero", MAGENTA)
            elif p.bloqueos:
                text(W // 2 - 16, 19, "bloqueos", LIGHTR)
        # el reloj: grande, y rojo en los últimos 10 segundos
        sec = (p.time + 59) // 60
        r = "%d" % sec
        col = (LIGHTR if f % 30 < 15 else WHITE) if sec <= 10 else TXT
        big(W - big_w(r) - 12, 3, r, col)
        text(W - 9, 9, "s", col)
        # los poderes activos, en chips debajo de la barra
        y = HUD + 3
        for activo, ttl, nom, col in ((p.nitro, NITRO_TTL, "NITRO", NITRO1),
                                      (p.iman, IMAN_TTL, "IMÁN", MAGENTA)):
            if activo:
                pyxel.rect(3, y, 62, 11, SHADOW)
                text(6, y + 3, nom, col)
                fx.bar(30, y + 4, 32, 3, activo / ttl, col, ASPHALT)
                y += 13
        if p.drift > 6:
            pyxel.rect(3, y, 62, 11, SHADOW)
            text(6, y + 3, "DERRAPE", GOLD)
            fx.bar(36, y + 4, 26, 3, min(1.0, p.drift / DRIFT_MIN), GOLD, ASPHALT)

    def _estrella(self, x, y, col):
        """una estrella de 9 px; vacía, sólo el contorno apagado."""
        if col is None:
            col = MAPRD                    # el hueco: la misma estrella, apagada
        pyxel.tri(x, y - 5, x - 2, y, x + 2, y, col)
        pyxel.rect(x - 5, y - 1, 11, 2, col)
        pyxel.tri(x - 1, y, x - 4, y + 5, x + 1, y + 1, col)
        pyxel.tri(x + 1, y, x + 4, y + 5, x - 1, y + 1, col)
        pyxel.rect(x - 2, y - 1, 5, 3, col)

    def _mision_hud(self):
        m = self.p.mision
        if m is None:
            return
        col = MISION_COL[m["tipo"]]
        tit = MISION_TIT[m["tipo"]]
        sec = (m["t"] + 59) // 60
        if m["tipo"] == "entrega":
            sub = "recoge el paquete" if m["fase"] == 0 else "llévalo a la bandera"
        elif m["tipo"] == "ruta":
            sub = "meta %d de %d" % (m["n"] + 1, len(m["pts"]))
        else:
            sub = "sal del círculo rojo"
        bw = 170
        bx, by = W // 2 - bw // 2, HUD + 2
        pyxel.rect(bx, by, bw, 24, SHADOW)
        pyxel.rect(bx, by, 3, 24, col)
        fx.bar(bx + 3, by + 22, bw - 3, 2, m["t"] / m["t0"], col, ASPHALT)
        big(bx + 8, by + 3, tit, col)
        r = "%d" % sec
        tc = (LIGHTR if (self.f // 8) % 2 else WHITE) if sec <= 5 else WHITE
        big(bx + bw - big_w(r) - 5, by + 3, r, tc)
        text(bx + 8, by + 15, sub, TXT)

    def _draw_banner(self):
        b = self.banner
        if b is None:
            return
        s, col, vida, sub, vida0 = b
        if vida < 12 and (self.f // 2) % 2:
            return
        y = HUD + 34 + max(0, (vida - vida0 + 8)) * 3   # entra bajando
        w = max(big_w(s, 3), len(sub) * 4) + 16
        pyxel.dither(0.75)
        pyxel.rect(W // 2 - w // 2, y - 4, w, 30 if sub else 24, SHADOW)
        pyxel.dither(1.0)
        cbig(W // 2, y, s, col, k=3)
        if sub:
            ctext(W // 2, y + 19, sub, WHITE)


class Game:
    def __init__(self):
        touch = con_dedo()
        Cabinet(
            game_id="autos", title="AUTOS", subtitle="90 segundos de atraco",
            howto=["acelera solo · freno + doblar = derrape" if touch
                   else "flechas manejan · freno + doblar = derrape",
                   "levanta fajos sin chocar: multiplican",
                   "misiones, saltos y derrapes pagan extra",
                   "la plata trae patrullas: piérdelas",
                   "el banco guarda lo que llevas encima"],
            width=W, height=H, palette=PAL, scale=2, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=CARBODY, shadow=SHADOW, panel=ASPHALT),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
