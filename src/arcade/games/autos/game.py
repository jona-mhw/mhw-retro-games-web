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
  por tres metas contra reloj, o salir de un cerco policial. un chevrón que
  gira alrededor del auto apunta al objetivo, y un ícono en el borde de la
  pantalla dice a cuántos metros está.
- **búsqueda de 5 estrellas**: con 3 aparecen bloqueos en la calle, con 4 un
  helicóptero con foco. si te alejas de todos un rato, pierdes una estrella
  (las estrellas titilan mientras te pierden la pista).
- **derrapes**: frenar doblando a toda velocidad suelta la cola; un derrape
  largo paga y mantiene viva la racha.
- **rampas**: a fondo por una rampa, el auto vuela y aterriza cobrando.

la partida dura 90 segundos y ni el reloj ni los poderes pueden estirarla más
(el reloj suma con tope), así que se juega entera en menos de dos minutos.

la pantalla es vertical (256x384) y la ciudad también (544x704): la cámara
se adelanta hacia donde vas, así yendo para arriba o para abajo se ve mucho
camino. el arte (paleta, ciudad horneada con sombras, autos pre-rotados) vive
en art.py.

la lógica vive en clases sin pyxel — City, Car, Ped, Cop, Heli y **Partida**,
que es el juego entero: recibe el input ya leído y devuelve una lista de
eventos. World sólo lee el teclado, traduce esos eventos a chispas y dibuja.
así toda la mecánica se testea sin abrir ventana.
"""
import math
import random
from collections import deque

import pyxel

from games.autos import art
from games.autos.art import (ACCENT, ASPHALT, BG, BILL, BILL0, BILL2, CAR0,
                             CARBODY, COP2, DIM, GOLD, GRASS1, GRASS2, HAIR,
                             LIGHTB, LIGHTR, MAGENTA, MET2, NITRO1,
                             NITRO2, ORANGE, OUTLINE, PAL, PANEL, PANEL2,
                             PANEL3, PED1, PED2, PED3, PED4, SHADOW, SIDE,
                             SKID, SKIN, SMOKE1, SMOKE2, SPARK1, SPARK2,
                             SPARK3, TRUNK, TXT, WATER, WHITE, WINLIT)
from pixelkit import fx, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import big_ctext, big_text, big_width, ctext, text

W, H = 256, 384                  # vertical: llena el celular parado
HUD = 30                         # la barra de arriba: números al doble de tamaño
VIEW_H = H - HUD
TILE = 16
MW, MH = 34, 44                  # ciudad en tiles → 544 x 704: parada, como la pantalla
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

# paleta y arte: viven en art.py (rampas de tonos, sombras, autos rotados)
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
        # arranca en una calle horizontal (mirando a la derecha, a = 0), en el
        # tramo más cercano al centro: así acelerar sin doblar no te estrella
        tramo = [r for r in self.roads if r[1] % B < 2 and r[0] % B >= 2]
        tx, ty = min(tramo, key=lambda p: abs(p[0] - MW // 2) + abs(p[1] - MH // 2))
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


# --- la piel ---------------------------------------------------------------
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
RW, RH = 64, 64                  # el radar: una ventana del plano, a 2 px por tile
KINDS = (ROAD, SIDEWALK, GRASS, TREE, FOUNT, BLD)
ROPA = (PED1, PED2, PED3, PED4)

# el $ de la fuente, agrandado, se lee como una f: va dibujado a mano, en
# tiras (x, y, ancho) sobre la grilla de 4x6 de la letra
_DOLLAR = ((1, -1, 1), (0, 0, 3), (0, 1, 1), (0, 2, 3), (2, 3, 1), (0, 4, 3), (1, 5, 1))


def btext(x, y, s, col, k=2, shadow=None):
    """big_text de pixelkit, pero con un $ que se lee."""
    x, y = int(x), int(y)
    if "$" not in s:
        big_text(x, y, s, col, k, shadow)
        return
    big_text(x, y, s.replace("$", " "), col, k, shadow)
    for i, ch in enumerate(s):
        if ch != "$":
            continue
        ox = x + i * 4 * k
        for gx, gy, w in _DOLLAR:
            if shadow is not None:
                pyxel.rect(ox + gx * k + 1, y + gy * k + 1, w * k, k, shadow)
            pyxel.rect(ox + gx * k, y + gy * k, w * k, k, col)


def bctext(cx, y, s, col, k=2, shadow=None):
    btext(cx - big_width(s, k) / 2, y, s, col, k, shadow)


# íconos chicos, horneados una vez: estrellas, billete, reloj, banco
_ICONS = []


def _star(img, x, y, col, borde):
    """una estrella de 5 puntas de 11 px con contorno, en una imagen."""
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 5.6 if i % 2 == 0 else 2.4
        pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
    for oxy in ((-1, 0), (1, 0), (0, -1), (0, 1)) if borde is not None else ():
        for i in range(0, 10, 2):
            a, b, c = pts[i], pts[(i + 1) % 10], pts[(i - 1) % 10]
            img.tri(a[0] + oxy[0], a[1] + oxy[1], b[0] + oxy[0], b[1] + oxy[1],
                    c[0] + oxy[0], c[1] + oxy[1], borde)
        img.circ(x + oxy[0], y + oxy[1], 3, borde)
    for i in range(0, 10, 2):
        a, b, c = pts[i], pts[(i + 1) % 10], pts[(i - 1) % 10]
        img.tri(a[0], a[1], b[0], b[1], c[0], c[1], col)
    img.circ(x, y, 2, col)


def icons():
    """(imagen, {nombre: (u, v, w, h)})."""
    if _ICONS:
        return _ICONS[0]
    img = pyxel.Image(128, 32)
    img.cls(art.TRANSP)
    box = {}
    for i, (col, hi) in enumerate(((GOLD, WHITE), (LIGHTR, SPARK1), (PANEL3, None),
                                   (DIM, None))):
        x = 8 + i * 16
        _star(img, x, 8, col, OUTLINE)
        if hi is not None:
            img.pset(x - 1, 5, hi)
            img.pset(x - 2, 7, hi)
        box[("star", i)] = (x - 7, 1, 15, 15)
    # el billete
    x, y = 70, 2
    img.rect(x - 1, y - 1, 16, 11, OUTLINE)
    img.rect(x, y, 14, 9, BILL)
    img.rect(x, y, 14, 1, BILL2)
    img.rect(x, y + 8, 14, 1, BILL0)
    img.rect(x + 5, y + 2, 4, 5, BILL0)
    img.rect(x + 6, y + 3, 2, 3, BILL2)
    img.pset(x + 2, y + 4, BILL2)
    img.pset(x + 11, y + 4, BILL2)
    box["bill"] = (x - 1, y - 1, 16, 11)
    # el reloj
    x, y = 96, 8
    img.circ(x, y, 6, OUTLINE)
    img.circ(x, y, 5, TXT)
    img.circ(x, y, 4, WHITE)
    img.line(x, y, x, y - 3, OUTLINE)
    img.line(x, y, x + 2, y, OUTLINE)
    img.rect(x - 1, y - 8, 3, 2, OUTLINE)
    box["clock"] = (x - 7, 0, 15, 15)
    # el banco: un frontón con columnas
    x, y = 110, 2
    img.tri(x, y + 4, x + 6, y, x + 12, y + 4, OUTLINE)
    img.tri(x + 2, y + 3, x + 6, y + 1, x + 10, y + 3, BILL2)
    img.rect(x, y + 4, 13, 7, OUTLINE)
    for c in range(3):
        img.rect(x + 2 + c * 4, y + 5, 2, 4, BILL2)
    img.rect(x + 1, y + 9, 11, 1, BILL)
    box["bank"] = (x, y, 13, 12)
    # el paquete
    x, y = 2, 18
    img.rect(x, y, 12, 10, OUTLINE)
    img.rect(x + 1, y + 1, 10, 8, TRUNK)
    img.rect(x + 1, y + 1, 10, 2, ORANGE)
    img.rect(x + 5, y + 1, 2, 8, GOLD)
    box["paquete"] = (x, y, 12, 10)
    _ICONS.append((img, box))
    return _ICONS[0]


def icon(name, x, y, center=True):
    img, box = icons()
    u, v, w, h = box[name]
    if center:
        x, y = x - w // 2, y - h // 2
    pyxel.blt(int(x), int(y), img, u, v, w, h, art.TRANSP)


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
        self.banner = None                  # [texto, col, vida, sub, vida0]
        self.f = 0                          # reloj de animación propio
        self.thr = 0
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
        self.thr = thr
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
            self.fx.burst(car.x + math.cos(back) * 11, car.y + math.sin(back) * 11,
                          NITROFX if p.nitro else SMOKE,
                          n=3 if p.nitro else 2, speed=0.9, life=16,
                          spread=0.7, angle=back)
        # goma: derrapando o frenando fuerte quedan huellas y sale humo blanco
        if not car.air and (car.drift_ang() > 0.25 and car.spd > 1.5
                            or (car.mano and car.spd > 1.2)
                            or (thr < 0 and car.spd > 1.8)):
            ca, sa = math.cos(car.a), math.sin(car.a)
            for s in (-4, 4):
                wx = car.x - 7 * ca - s * sa
                wy = car.y - 7 * sa + s * ca
                self.marcas.append((int(wx), int(wy)))
                if self.exhaust % 2 == 0:
                    self.fx.burst(wx, wy, TIRE, n=1, speed=0.5, life=24,
                                  spread=math.tau)
        # la cámara mira hacia donde vas: en vertical se ve mucho más camino
        # adelante cuando vas para arriba o para abajo
        tx, ty = self._cam_target()
        self.camx += (tx - self.camx) * 0.08
        self.camy += (ty - self.camy) * 0.08
        # pero el auto nunca se va al borde
        self.camx = max(car.x - W + 64, min(car.x - 64, self.camx))
        self.camy = max(car.y - VIEW_H + 78, min(car.y - 96, self.camy))
        self.camx = max(0, min(MAP_PX - W, self.camx))
        self.camy = max(0, min(MAP_PY - VIEW_H, self.camy))
        self.fx.update()

    def _cam_target(self):
        car = self.p.car
        sp = max(0.0, car.spd)
        lx = max(-58.0, min(58.0, math.cos(car.va) * sp * 17))
        ly = max(-120.0, min(120.0, math.sin(car.va) * sp * 36))
        tx = car.x + lx - W / 2
        ty = car.y + ly - VIEW_H / 2 - 12
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
            self.fx.popup(x, y - 10, "+$%d" % monto, BILL2)
        elif kind == "choque":
            _, x, y = e
            self.fx.burst(x, y, SPARKS, n=12, speed=2.1, life=18)
            self.fx.shake(3)
        elif kind in ("embiste", "marcado"):
            _, x, y, perdido = e
            self.fx.burst(x, y, SPARKS, n=26, speed=2.8, life=26)
            self.fx.popup(car.x, car.y - 14, "-$%d" % perdido, LIGHTR)
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
            self.fx.burst(car.x, car.y, (WHITE, ACCENT, GRASS2), n=18, speed=2.2)
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

    # --- dibujo ----------------------------------------------------------
    def draw(self):
        if self.city_img is None:
            self.city_img = art.city_image(self.p.city, B, KINDS)
        p = self.p
        pyxel.cls(BG)
        sx, sy = self.fx.offset()
        camx = int(self.camx) - sx                   # el temblor mueve la cámara
        camy = int(self.camy) - sy
        oy = HUD - camy                              # mundo -> pantalla, en y
        pyxel.blt(0, HUD, self.city_img, camx, camy, W, VIEW_H)
        for x, y in self.marcas:
            pyxel.pset(x - camx, y + oy, SKID)
        pyxel.clip(0, HUD, W, VIEW_H)
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
        cop_spr = art.rotados("cop")
        for cop in p.cops:
            self._cop(cop_spr, cop.x - camx, cop.y + oy, cop.car.a)
        car = p.car
        if p.grace <= 0 or (self.f // 4) % 2:
            self._jugador(car, camx, oy)
        if p.iman:
            self._halo(car.x - camx, car.y + oy)
        if p.heli is not None:
            self._heli(p.heli, camx, oy)
        pyxel.clip()
        self.fx.draw_flash(0, HUD, W, VIEW_H)
        self._guia(camx, oy)
        self._flechas(camx, oy)
        self._radar()
        self._hud()
        self._mision_hud()
        self._chips()
        self._draw_banner()

    def _visible(self, x, y, m=24):
        return -m < x < W + m and HUD - m < y < H + m

    def _jugador(self, car, camx, oy):
        p = self.p
        x, y = car.x - camx, car.y + oy
        if not self._visible(x, y):
            return
        alto = 0.0
        if car.air:
            total = car.air + p.vuelo
            alto = math.sin(math.pi * p.vuelo / max(1, total))
        ca, sa = math.cos(car.a), math.sin(car.a)
        if p.nitro and not car.air:                  # la llamarada del nitro
            fl = 6 + (self.f // 2) % 3 * 2
            bx, by = x - ca * 11, y - sa * 11
            for s, col in ((3, NITRO2), (2, NITRO1), (1, WHITE)):
                pyxel.tri(bx - sa * s, by + ca * s, bx + sa * s, by - ca * s,
                          bx - ca * fl * s / 3, by - sa * fl * s / 3, col)
        art.rotados("auto").draw(x, y, car.a, k=1 + 0.45 * alto,
                                 sombra=2 + int(9 * alto))
        if self.thr < 0 and car.spd > 0.3 and not car.air:   # luces de freno
            for s in (-4, 4):
                hx = int(x - ca * 11 - sa * s)
                hy = int(y - sa * 11 + ca * s)
                pyxel.rect(hx - 1, hy - 1, 2, 2, LIGHTR)

    def _cop(self, spr, x, y, a):
        if not self._visible(x, y):
            return
        spr.draw(x, y, a)
        izq = (self.f // 5) % 2
        ca, sa = math.cos(a), math.sin(a)
        for s, on in ((-1.5, izq), (1.5, not izq)):
            if not on:
                continue
            bxp, byp = x - sa * s, y + ca * s
            col = LIGHTR if s < 0 else LIGHTB
            pyxel.dither(0.3)
            pyxel.circ(int(bxp), int(byp), 6, col)
            pyxel.dither(1.0)
            pyxel.rect(int(bxp) - 1, int(byp) - 1, 3, 3, col)
            pyxel.pset(int(bxp), int(byp), WHITE)

    def _banco(self, cx, cy):
        """la boca del banco: un círculo verde en la calle con el banco
        adentro. late y echa anillos cuando llevas lo suficiente."""
        cx, cy = int(cx), int(cy)
        if not self._visible(cx, cy, 30):
            return
        activo = self.p.money >= BANCO_MIN
        f = self.f
        if activo:
            rr = (f % 40) // 2
            pyxel.circb(cx, cy, BANCO_R - 6 + rr, BILL if rr < 14 else BILL0)
        col = BILL2 if activo else BILL
        r = BANCO_R - 2
        pyxel.dither(0.5)
        pyxel.circ(cx, cy, r, BILL0)
        pyxel.dither(1.0)
        for i in range(8):
            if i % 2:
                continue
            a0 = i * math.pi / 4 + f * 0.03
            a1 = a0 + math.pi / 4
            for d in (0, 1):
                pyxel.line(int(cx + math.cos(a0) * (r - d)), int(cy + math.sin(a0) * (r - d)),
                           int(cx + math.cos(a1) * (r - d)), int(cy + math.sin(a1) * (r - d)), col)
        pyxel.circ(cx, cy, 9, OUTLINE)
        pyxel.circ(cx, cy, 8, BILL0 if not activo else PANEL2)
        icon("bank", cx, cy - 1)

    def _bill(self, cx, cy):
        """un fajo de billetes con su faja, flotando sobre su sombra."""
        cx, cy = int(cx), int(cy)
        if not self._visible(cx, cy, 10):
            return
        bob = (self.f // 8 + cx) % 4
        bob = 1 if bob in (1, 3) else (2 if bob == 2 else 0)
        pyxel.rect(cx - 5, cy + 3, 11, 2, art.sh(ASPHALT))
        y = cy - 3 - bob
        pyxel.rect(cx - 7, y - 1, 15, 9, OUTLINE)
        pyxel.rect(cx - 6, y, 13, 7, BILL)
        pyxel.rect(cx - 6, y, 13, 1, BILL2)
        pyxel.rect(cx - 6, y + 4, 13, 1, BILL0)
        pyxel.rect(cx - 6, y + 6, 13, 1, BILL0)
        pyxel.rect(cx - 1, y, 3, 7, COP2)            # la faja
        pyxel.pset(cx, y + 2, GOLD)
        if (self.f + cx * 3) % 50 < 5:                # un destello
            pyxel.pset(cx - 5, y - 2, WHITE)
            pyxel.pset(cx - 6, y - 1, WHITE)
            pyxel.pset(cx - 4, y - 1, WHITE)

    def _power(self, cx, cy, tipo):
        """la caja de poder: late, brilla y trae su símbolo adentro."""
        cx, cy = int(cx), int(cy)
        if not self._visible(cx, cy, 14):
            return
        col = (NITRO1, MAGENTA, ACCENT, GOLD)[tipo]
        bob = (self.f // 6) % 4
        bob = 1 if bob in (1, 3) else (2 if bob == 2 else 0)
        pyxel.dither(0.25 + 0.1 * ((self.f // 5) % 2))
        pyxel.circ(cx, cy, 13, col)
        pyxel.dither(1.0)
        pyxel.rect(cx - 6, cy + 5, 13, 3, art.sh(ASPHALT))
        y = cy - bob
        pyxel.rect(cx - 8, y - 8, 17, 16, OUTLINE)
        pyxel.rect(cx - 7, y - 7, 15, 14, PANEL2)
        pyxel.rect(cx - 7, y - 7, 15, 1, col)
        pyxel.rect(cx - 7, y - 7, 1, 14, col)
        pyxel.rect(cx - 7, y + 6, 15, 1, PANEL)
        if tipo == NITRO:                                  # un rayo
            pyxel.tri(cx + 2, y - 5, cx - 3, y + 1, cx + 1, y, col)
            pyxel.tri(cx - 1, y, cx + 3, y - 1, cx - 2, y + 5, col)
        elif tipo == IMAN:                                 # una herradura
            pyxel.circ(cx, y, 4, col)
            pyxel.circ(cx, y, 2, PANEL2)
            pyxel.rect(cx - 2, y - 4, 5, 4, PANEL2)
            pyxel.rect(cx - 4, y - 4, 2, 2, WHITE)
            pyxel.rect(cx + 3, y - 4, 2, 2, WHITE)
        elif tipo == SOBORNO:                              # un billete
            pyxel.rect(cx - 5, y - 3, 11, 6, col)
            pyxel.rect(cx - 1, y - 2, 3, 4, BILL0)
        else:                                              # un reloj
            pyxel.circ(cx, y, 4, col)
            pyxel.line(cx, y, cx, y - 3, OUTLINE)
            pyxel.line(cx, y, cx + 2, y, OUTLINE)

    def _ped(self, ped, camx, oy):
        x, y = int(ped.x - camx), int(ped.y + oy)
        if not self._visible(x, y, 8):
            return
        k = int(ped.x * 0.1 + ped.y * 0.07) % 4
        ropa = ROPA[(id(ped) // 16) % 4]
        paso = (self.f // (4 if ped.scared else 9)) % 2
        pyxel.rect(x - 1, y + 4, 5, 1, art.sh(SIDE))       # sombra
        pyxel.rect(x - 2, y - 1, 5, 6, OUTLINE)
        pyxel.rect(x - 1, y, 3, 3, ropa)                   # cuerpo
        pyxel.pset(x - 1 + paso * 2, y + 3, HAIR)          # la pierna que pisa
        pyxel.rect(x - 2, y - 5, 5, 5, OUTLINE)
        pyxel.rect(x - 1, y - 4, 3, 3, SKIN)               # cabeza
        pyxel.rect(x - 1, y - 4, 3, 1, HAIR if k else PED3)
        if ped.scared:
            pyxel.pset(x + (3 if paso else -3), y - 6, WHITE)   # gotita de susto
            pyxel.pset(x + (3 if paso else -3), y - 5, NITRO1)

    def _halo(self, cx, cy):
        """el anillo del imán, girando, para que se note que está activo."""
        for i in range(10):
            a = self.f * 0.09 + i * math.tau / 10
            px = int(cx + math.cos(a) * IMAN_R * 0.5)
            py = int(cy + math.sin(a) * IMAN_R * 0.5)
            pyxel.rect(px - 1, py - 1, 2, 2, MAGENTA if i % 2 else WHITE)

    def _bloqueo(self, b, camx, oy):
        """la barricada: vallas a franjas en los dos carriles y una patrulla
        cruzada con las balizas prendidas. titila cuando está por irse."""
        if b["t"] < 90 and (self.f // 4) % 2:
            return
        cx, cy = int(b["x"] - camx), int(b["y"] + oy)
        if not self._visible(cx, cy, 40):
            return
        for tx, ty in b["tiles"]:
            px, py = int(tx * TILE - camx), int(ty * TILE + oy)
            if b["eje"] == 1:                       # calle vertical: valla horizontal
                pyxel.rect(px, py + 11, TILE, 2, art.sh(ASPHALT))
                pyxel.rect(px, py + 4, TILE, 8, OUTLINE)
                pyxel.rect(px, py + 5, TILE, 6, WHITE)
                for i in range(0, TILE, 6):
                    pyxel.rect(px + i, py + 5, 3, 6, LIGHTR)
                pyxel.rect(px, py + 5, TILE, 1, COP2)
            else:
                pyxel.rect(px + 11, py, 2, TILE, art.sh(ASPHALT))
                pyxel.rect(px + 4, py, 8, TILE, OUTLINE)
                pyxel.rect(px + 5, py, 6, TILE, WHITE)
                for i in range(0, TILE, 6):
                    pyxel.rect(px + 5, py + i, 6, 3, LIGHTR)
                pyxel.rect(px + 5, py, 1, TILE, COP2)
        a = 0.0 if b["eje"] == 1 else math.pi / 2
        off = (0, -14) if b["eje"] == 1 else (-14, 0)
        self._cop(art.rotados("cop"), cx + off[0], cy + off[1], a)

    def _mision_mundo(self, m, camx, oy):
        f = self.f
        if m["tipo"] == "escape":
            # el cerco: un círculo rojo a trazos que gira
            cx, cy, r = m["cx"] - camx, m["cy"] + oy, m["r"]
            col = LIGHTR if (f // 6) % 2 else ORANGE
            n = 48
            for i in range(0, n, 2):
                a0 = i * math.tau / n + f * 0.01
                a1 = a0 + math.tau / n
                x0, y0 = cx + math.cos(a0) * r, cy + math.sin(a0) * r
                x1, y1 = cx + math.cos(a1) * r, cy + math.sin(a1) * r
                if not (self._visible(x0, y0, 4) or self._visible(x1, y1, 4)):
                    continue
                for d in (0, 1, 2):
                    pyxel.line(int(x0) + d, int(y0), int(x1) + d, int(y1),
                               OUTLINE if d == 2 else col)
            return
        if m["tipo"] == "entrega":
            x, y = int(m["x"] - camx), int(m["y"] + oy)
            if not self._visible(x, y, 30):
                return
            if m["fase"] == 0:                      # el paquete, saltando
                yy = y - 3 - (f // 6) % 3
                pyxel.circb(x, y, 12 + (f // 5) % 3, ORANGE)
                pyxel.circb(x, y, 13 + (f // 5) % 3, OUTLINE)
                pyxel.rect(x - 5, y + 3, 11, 2, art.sh(ASPHALT))
                icon("paquete", x, yy)
            else:                                   # el punto de entrega
                for rr, col in ((16, ORANGE), (10, GOLD)):
                    pyxel.circb(x, y, rr + (f // 4) % 3, col)
                pyxel.rect(x + 1, y - 1, 6, 2, art.sh(ASPHALT))
                pyxel.rect(x - 1, y - 17, 3, 17, OUTLINE)
                pyxel.rect(x, y - 16, 1, 16, WHITE)
                ond = (f // 6) % 2
                pyxel.tri(x + 1, y - 16, x + 11, y - 13 + ond, x + 1, y - 9, ORANGE)
                pyxel.line(x + 1, y - 16, x + 10, y - 13 + ond, GOLD)
            return
        # la carrera: la meta que toca, grande; las siguientes, chicas
        for i in range(m["n"], len(m["pts"])):
            x, y = int(m["pts"][i][0] - camx), int(m["pts"][i][1] + oy)
            if not self._visible(x, y, 20):
                continue
            if i == m["n"]:
                pyxel.circ(x, y, 11, OUTLINE)
                pyxel.circb(x, y, 13 + (f // 4) % 3, NITRO1)
                pyxel.circb(x, y, 10, WHITE)
                pyxel.circb(x, y, 9, NITRO2)
                big_ctext(x, y - 5, str(i + 1), WHITE, 2, OUTLINE)
            else:
                pyxel.circ(x, y, 6, OUTLINE)
                pyxel.circb(x, y, 6, NITRO2)
                text(x - 1, y - 2, str(i + 1), NITRO1)

    def _foco(self, x, y):
        """el foco del helicóptero en el piso: se pone rojo cuando te tiene."""
        x, y = int(x), int(y)
        caliente = self.p.foco > 0
        pyxel.dither(0.30)
        pyxel.circ(x, y, FOCO_R, LIGHTR if caliente else WINLIT)
        pyxel.dither(0.5)
        pyxel.circ(x, y, FOCO_R - 8, LIGHTR if caliente else WHITE)
        pyxel.dither(1.0)
        pyxel.circb(x, y, FOCO_R, LIGHTR if caliente and (self.f // 4) % 2
                    else WINLIT)
        if caliente:
            fx.bar(x - 15, y + FOCO_R + 4, 30, 4, self.p.foco / FOCO_MARCA,
                   LIGHTR, SHADOW, OUTLINE)

    def _heli(self, h, camx, oy):
        x, y = h.x - camx, h.y + oy - 30              # vuela: se dibuja más arriba
        if not self._visible(x, y, 40):
            return
        a = math.atan2(h.vy, h.vx) if (h.vx or h.vy) else 0.0
        spr = art.rotados("heli")
        if not spr.ok[spr.idx(a)]:
            spr._bake(spr.idx(a))
        # la sombra va en el piso, corrida: así se lee que está alto
        n = spr.idx(a)
        c = spr.cell
        pyxel.dither(0.6)
        pyxel.blt(int(x) - c // 2 + 10, int(y) - c // 2 + 36, spr.img, (n % 8) * c,
                  (n // 8) * c + 8 * c, c, c, art.TRANSP)
        pyxel.dither(1.0)
        spr.draw(x, y, a, sombra=None)
        r = self.f * 0.7
        pyxel.dither(0.15)
        pyxel.circ(int(x), int(y), 16, MET2)
        pyxel.dither(1.0)
        for da in (0, math.pi / 2):
            c_, s_ = math.cos(r + da) * 16, math.sin(r + da) * 16
            pyxel.line(int(x - c_), int(y - s_), int(x + c_), int(y + s_), OUTLINE)
            pyxel.line(int(x - c_) + 1, int(y - s_), int(x + c_) + 1, int(y + s_), MET2)
        pyxel.circ(int(x), int(y), 2, OUTLINE)
        pyxel.pset(int(x), int(y), MET2)
        tx, ty = x - math.cos(a) * 12, y - math.sin(a) * 12
        pyxel.rect(int(tx) - 1, int(ty) - 1, 2, 2, LIGHTR if (self.f // 6) % 2 else WHITE)

    # --- guía, flechas, radar y hud ----------------------------------------
    def _meta(self):
        """el objetivo principal (x, y, color), o None: la misión, si no el banco."""
        p, car = self.p, self.p.car
        m = p.mision
        if m is not None and m["tipo"] == "escape":
            a = math.atan2(car.y - m["cy"], car.x - m["cx"])
            return (car.x + math.cos(a) * 200, car.y + math.sin(a) * 200, LIGHTR)
        for x, y, kind, _ in p.objetivos():
            return (x, y, OBJ_COL[kind])
        return None

    def _guia(self, camx, oy):
        """la flecha de misión: un chevrón grande que gira alrededor del auto
        y apunta a donde hay que ir, como en el gta. no se pierde nunca."""
        meta = self._meta()
        if meta is None:
            return
        car = self.p.car
        x, y, col = meta
        dx, dy = x - car.x, y - car.y
        d = math.hypot(dx, dy)
        if d < 44:
            return
        a = math.atan2(dy, dx)
        ca, sa = math.cos(a), math.sin(a)
        cx, cy = car.x - camx, car.y + oy
        r = 24 + (self.f // 6) % 3
        px_, py_ = -sa, ca                           # la perpendicular

        def punta(e):
            """las cuatro puntas del chevrón, engordado e px (el contorno)."""
            t = (cx + ca * (r + 12 + e * 1.6), cy + sa * (r + 12 + e * 1.6))
            l = (cx + ca * (r - e) + px_ * (10 + e), cy + sa * (r - e) + py_ * (10 + e))
            rr = (cx + ca * (r - e) - px_ * (10 + e), cy + sa * (r - e) - py_ * (10 + e))
            n = (cx + ca * (r + 2 - e), cy + sa * (r + 2 - e))
            return t, l, rr, n

        t, l, rr, n = punta(2)
        pyxel.tri(*t, *l, *n, OUTLINE)
        pyxel.tri(*t, *rr, *n, OUTLINE)
        t, l, rr, n = punta(0)
        luz = WHITE if (self.f // 8) % 4 == 0 else col
        pyxel.tri(*t, *l, *n, luz)
        pyxel.tri(*t, *rr, *n, luz)
        pyxel.line(*t, *l, WHITE)

    def _flechas(self, camx, oy):
        """a dónde ir: un ícono en el borde de la pantalla por cada objetivo
        fuera de vista, con la distancia; si se ve, una flecha que rebota encima."""
        p = self.p
        car = p.car
        ccx, ccy = car.x - camx, car.y + oy
        f = self.f
        top = HUD + (40 if p.mision else 12)
        left, right, bot = 12, W - 12, H - 12
        for x, y, kind, lab in p.objetivos():
            col = OBJ_COL[kind]
            sx, sy = x - camx, y + oy
            if left <= sx <= right and HUD + 6 <= sy <= bot:
                yy = int(sy) - 24 - (f // 5) % 3
                ix = int(sx)
                pyxel.tri(ix - 7, yy - 1, ix + 7, yy - 1, ix, yy + 8, OUTLINE)
                pyxel.rect(ix - 4, yy - 9, 9, 9, OUTLINE)
                pyxel.tri(ix - 5, yy, ix + 5, yy, ix, yy + 6, col)
                pyxel.rect(ix - 2, yy - 7, 5, 7, col)
                pyxel.rect(ix - 2, yy - 7, 1, 7, WHITE)
                continue
            dx, dy = sx - ccx, sy - ccy
            a = math.atan2(dy, dx)
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
            ix, iy = int(ex - ca * 10), int(ey - sa * 10)
            tipx, tipy = ex + ca * 2, ey + sa * 2
            lx, ly = ix + math.cos(a + 1.2) * 9, iy + math.sin(a + 1.2) * 9
            rx, ry = ix + math.cos(a - 1.2) * 9, iy + math.sin(a - 1.2) * 9
            pyxel.tri(tipx, tipy, lx, ly, rx, ry, col)
            pyxel.circ(ix, iy, 8, OUTLINE)
            pyxel.circ(ix, iy, 7, PANEL)
            pyxel.circb(ix, iy, 7, col if (f // 8) % 2 else WHITE)
            if lab and kind != "banco":
                text(ix - 1, iy - 2, lab, WHITE)
            elif kind == "banco":
                pyxel.rect(ix - 1, iy - 4, 2, 8, BILL2)
                pyxel.rect(ix - 3, iy - 2, 6, 1, BILL2)
                pyxel.rect(ix - 3, iy + 1, 6, 1, BILL2)
            elif kind == "paquete":
                pyxel.rect(ix - 3, iy - 3, 7, 6, ORANGE)
                pyxel.rect(ix, iy - 3, 1, 6, GOLD)
            else:
                pyxel.rect(ix - 1, iy - 4, 1, 8, WHITE)
                pyxel.tri(ix, iy - 4, ix + 4, iy - 2, ix, iy, ORANGE)
            dist = "%dm" % (math.hypot(x - car.x, y - car.y) / 4)
            if abs(ey - top) < 2 or abs(ey - bot) < 2:     # borde de arriba/abajo
                tx_ = ix + 11 if ix < W - 44 else ix - 11 - len(dist) * 4
                ty_ = iy - 2
            else:                                          # costados
                tx_ = max(2, min(W - len(dist) * 4 - 2, ix - len(dist) * 2))
                ty_ = iy + 11 if sy > ccy else iy - 16
            stext(tx_, ty_, dist, col, OUTLINE)
        # las patrullas que vienen y todavía no se ven: balizas en el borde
        if (f // 5) % 2:
            for cop in p.cops:
                sx, sy = cop.x - camx, cop.y + oy
                if 0 <= sx < W and HUD <= sy < H:
                    continue
                ex = int(max(4, min(W - 8, sx)))
                ey = int(max(HUD + 4, min(H - 8, sy)))
                col = LIGHTR if (f // 10) % 2 else LIGHTB
                pyxel.rect(ex - 1, ey - 1, 6, 6, OUTLINE)
                pyxel.rect(ex, ey, 4, 4, col)
                pyxel.pset(ex + 1, ey + 1, WHITE)

    def _radar(self):
        """el plano, a 2 px por tile, en una ventana alrededor tuyo. lo que
        queda fuera (el banco, la misión) se dibuja pegado al borde."""
        p = self.p
        if self.radar is None:
            self.radar = art.radar_image(p.city, KINDS)
        car = p.car
        u = int(max(0, min(MW * 2 - RW, car.x / TILE * 2 - RW / 2)))
        v = int(max(0, min(MH * 2 - RH, car.y / TILE * 2 - RH / 2)))
        mx, my = W - RW - 5, H - RH - 5
        pyxel.rect(mx - 3, my - 3, RW + 6, RH + 6, OUTLINE)
        pyxel.blt(mx, my, self.radar, u, v, RW, RH)
        pyxel.rectb(mx - 2, my - 2, RW + 4, RH + 4, PANEL3)
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
        # tú: un punto con la nariz hacia donde miras
        px = mx + car.x / TILE * 2 - u
        py = my + car.y / TILE * 2 - v
        pyxel.rect(int(px) - 1, int(py) - 1, 3, 3, WHITE)
        pyxel.pset(int(px + math.cos(car.a) * 3), int(py + math.sin(car.a) * 3), GOLD)

    def _hud(self):
        p = self.p
        f = self.f
        pyxel.rect(0, 0, W, HUD, PANEL)
        pyxel.rect(0, 0, W, 1, PANEL3)
        pyxel.rect(0, HUD - 2, W, 1, PANEL3)
        pyxel.rect(0, HUD - 1, W, 1, OUTLINE)
        # la plata que llevas encima: lo que te pueden sacar
        icon("bill", 3, 4, center=False)
        s = "%d" % p.money
        big_text(22, 5, s, BILL2, 2, OUTLINE)
        x = 22 + big_width(s, 2) + 5
        m = p.mult()
        if m > 1:
            col = GOLD if self.combo_pop and (f // 3) % 2 else ORANGE
            big_text(x, 5, "x%d" % m, col, 2, OUTLINE)
            fx.bar(x, 18, big_width("x%d" % m, 2), 2, p.racha_t / RACHA_TTL, GOLD, PANEL3)
        # lo guardado, chico, debajo
        if p.banco:
            stext(22, 20, "banco $%d" % p.banco, BILL, OUTLINE)
        # las estrellas, grandes y al centro. titilan mientras te pierden
        n = WANTED_MAX
        x0 = W // 2 - 2 * 14 - 2
        perdiendo = p.evade > 0 and (f // 6) % 2
        for i in range(n):
            lleno = i < p.wanted
            if lleno and not perdiendo:
                k = 1 if (f // 8 + i) % 2 else 0
            elif lleno:
                k = 3
            else:
                k = 2
            icon(("star", k), x0 + i * 14 + 2, 11)
        if p.wanted:
            if p.evade > 0:
                fx.bar(x0 - 5, 21, n * 14 - 1, 3, p.evade / EVADE_T, ACCENT, PANEL3)
            elif p.heli is not None:
                ctext(W // 2 + 2, 21, "helicóptero", MAGENTA)
            elif p.bloqueos:
                ctext(W // 2 + 2, 21, "bloqueos", LIGHTR)
        # el reloj: grande, y rojo en los últimos 10 segundos
        sec = (p.time + 59) // 60
        r = "%d" % sec
        col = (LIGHTR if f % 30 < 15 else WHITE) if sec <= 10 else TXT
        tw = big_width(r, 2)
        big_text(W - 5 - tw, 5, r, col, 2, OUTLINE)
        icon("clock", W - 5 - tw - 10, 11)
        fx.bar(W - 5 - tw - 17, 22, tw + 17, 2, p.time / TIME, col, PANEL3)

    def _chips(self):
        """los poderes activos y el derrape en curso, en chips a la izquierda."""
        p = self.p
        y = H - 18
        if p.drift > 6:
            self._chip(y, "DERRAPE", GOLD, min(1.0, p.drift / DRIFT_MIN))
            y -= 15
        for activo, ttl, nom, col in ((p.iman, IMAN_TTL, "IMÁN", MAGENTA),
                                      (p.nitro, NITRO_TTL, "NITRO", NITRO1)):
            if activo:
                self._chip(y, nom, col, activo / ttl)
                y -= 15

    def _chip(self, y, nom, col, frac):
        pyxel.rect(3, y, 74, 13, OUTLINE)
        pyxel.rect(4, y + 1, 72, 11, PANEL)
        pyxel.rect(4, y + 1, 2, 11, col)
        text(9, y + 4, nom, col)
        fx.bar(41, y + 5, 32, 3, frac, col, PANEL3)

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
        bw = W - 12
        bx, by = 6, HUD + 3
        pyxel.rect(bx - 1, by - 1, bw + 2, 32, OUTLINE)
        pyxel.rect(bx, by, bw, 30, PANEL)
        pyxel.rect(bx, by, 4, 30, col)
        fx.bar(bx + 4, by + 27, bw - 4, 3, m["t"] / m["t0"], col, PANEL3)
        big_text(bx + 10, by + 5, tit, col, 2, OUTLINE)
        text(bx + 10, by + 18, sub, TXT)
        r = "%d" % sec
        tc = (LIGHTR if (self.f // 8) % 2 else WHITE) if sec <= 5 else WHITE
        big_text(bx + bw - big_width(r, 2) - 6, by + 5, r, tc, 2, OUTLINE)

    def _draw_banner(self):
        b = self.banner
        if b is None:
            return
        s, col, vida, sub, vida0 = b
        if vida < 12 and (self.f // 2) % 2:
            return
        # arriba, debajo de la misión: el auto anda siempre más abajo, así el
        # cartel nunca lo tapa
        base = HUD + (40 if self.p.mision else 10)
        y = base + 6 - max(0, (vida - vida0 + 8)) * 3      # entra bajando
        k = 3 if big_width(s, 3) <= W - 16 else 2
        w = max(big_width(s, k), len(sub) * 4) + 20
        hgt = (6 * k + 12) + (10 if sub else 0)
        pyxel.dither(0.8)
        pyxel.rect(W // 2 - w // 2, y - 6, w, hgt, SHADOW)
        pyxel.dither(1.0)
        pyxel.rect(W // 2 - w // 2, y - 6, w, 1, col)
        pyxel.rect(W // 2 - w // 2, y - 7 + hgt, w, 1, col)
        bctext(W // 2, y, s, col, k, OUTLINE)
        if sub:
            ctext(W // 2, y + 6 * k + 3, sub, WHITE)


class AutosCabinet(Cabinet):
    """el Cabinet de siempre; sólo cambia la portada: la ciudad de fondo,
    paseándose, con un auto que la cruza y las patrullas atrás. si algo de
    esto fallara, vuelve al título de fábrica."""

    _city = None

    def _draw_title(self):
        try:
            self._autos_title()
        except Exception:
            super()._draw_title()

    def _autos_title(self):
        from pixelkit import scores
        a = self.anim
        if AutosCabinet._city is None:
            AutosCabinet._city = City()
        city = AutosCabinet._city
        img = art.city_image(city, B, KINDS)
        # mientras se mira la portada se hornean los autos rotados, de a poco
        for _ in range(3):
            art.warm()
        # la cámara baja por una avenida, lento, y da la vuelta
        span = MAP_PY - H
        t = (a * 0.35) % (2 * span)
        camy = t if t < span else 2 * span - t
        camx = 2 * B * TILE - 40
        pyxel.blt(0, 0, img, camx, int(camy), W, H)
        # un auto que baja por la calle, perseguido
        av = 2 * B * TILE + 8 - camx
        cy = (a * 2.2) % (H + 140) - 60
        art.rotados("auto").draw(av, cy, math.pi / 2)
        cop = art.rotados("cop")
        for i, d in enumerate((52, 84)):
            yy = cy - d
            cop.draw(av + (8 if i else -6), yy, math.pi / 2)
            izq = (a // 5 + i) % 2
            pyxel.rect(int(av + (8 if i else -6)) - 1 + (2 if izq else -2), int(yy) - 1, 3, 3,
                       LIGHTR if izq else LIGHTB)
        art.oscurecer()
        cx = W / 2
        # el logo
        y = 30
        s = 6
        tw = big_width(self.title, s)
        pyxel.rect(cx - tw / 2 - 10, y - 10, tw + 20, 6 * s + 64, OUTLINE)
        pyxel.rect(cx - tw / 2 - 8, y - 8, tw + 16, 6 * s + 60, PANEL)
        pyxel.rect(cx - tw / 2 - 8, y - 8, tw + 16, 2, CARBODY)
        pyxel.rect(cx - tw / 2 - 8, y + 6 * s + 50, tw + 16, 2, CARBODY)
        big_ctext(cx + 3, y + 3, self.title, CAR0, s)
        big_ctext(cx, y, self.title, GOLD, s)
        sx = (a * 3) % (tw + 80) - 40
        if 0 <= sx < tw:
            pyxel.dither(0.5)
            pyxel.rect(cx - tw / 2 + sx, y, 6, 5 * s, WHITE)
            pyxel.dither(1.0)
        ctext(cx, y + 6 * s + 10, self.subtitle, TXT)
        # las estrellas de búsqueda, de adorno
        ic, box = icons()
        for i in range(5):
            k = 1 if (a // 8 + i) % 2 else 0
            icon(("star", k), cx - 28 + i * 14, y + 6 * s + 32)
        # el llamado a jugar
        py = 142
        call = "toca para jugar" if web.is_touch() else "enter para jugar"
        lit = self._blink(24)
        pw = big_width(call, 1) + 22
        pyxel.rect(cx - pw / 2 - 1, py - 6, pw + 2, 17, OUTLINE)
        pyxel.rect(cx - pw / 2, py - 5, pw, 15, ACCENT if lit else PANEL)
        ctext(cx, py, call, OUTLINE if lit else ACCENT)
        # cómo se juega
        lines = self.howto[:6]
        hy = 170
        bw = W - 24
        hh = 16 + 11 * len(lines)
        pyxel.rect(cx - bw / 2 - 1, hy - 1, bw + 2, hh + 2, OUTLINE)
        pyxel.rect(cx - bw / 2, hy, bw, hh, PANEL)
        pyxel.rect(cx - bw / 2, hy, bw, 1, PANEL3)
        ctext(cx, hy + 5, "cómo se juega", GOLD)
        for i, line in enumerate(lines):
            ctext(cx, hy + 17 + i * 11, line, TXT)
        # los mejores
        lst = scores.top(self.id, 3)
        if lst:
            ry = hy + hh + 10
            rh = 18 + 20 * len(lst)
            pyxel.rect(cx - bw / 2 - 1, ry - 1, bw + 2, rh + 2, OUTLINE)
            pyxel.rect(cx - bw / 2, ry, bw, rh, PANEL)
            pyxel.rect(cx - bw / 2, ry, bw, 1, BILL)
            ctext(cx, ry + 5, "mejores atracos", DIM)
            for i, e in enumerate(lst):
                bctext(cx, ry + 17 + 20 * i, "%s $%d" % (e["ini"], e["score"]),
                          GOLD if i == 0 else TXT, 2, OUTLINE)


class Game:
    def __init__(self):
        touch = con_dedo()
        AutosCabinet(
            game_id="autos", title="AUTOS", subtitle="90 segundos de atraco",
            howto=["acelera solo · freno + doblar = derrape" if touch
                   else "flechas manejan · freno + doblar = derrape",
                   "levanta fajos sin chocar: multiplican",
                   "misiones, saltos y derrapes pagan extra",
                   "la plata trae patrullas: piérdelas",
                   "el banco guarda lo que llevas encima",
                   "sigue la flecha que gira junto a tu auto"],
            width=W, height=H, palette=PAL, scale=2, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=GOLD,
                        warn=CARBODY, shadow=SHADOW, panel=PANEL2),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
