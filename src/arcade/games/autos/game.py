"""autos — atraco a la ciudad, top-down estilo gta 2, para el cabinet.

vista aérea, auto con inercia y derrape, una ciudad con calles, veredas y plazas.
levantás fajos de billetes contra reloj, pero cada fajo te calienta: a partir de
cierta plata aparecen **patrullas** que te persiguen de verdad (manejan, no
flotan) y te sacan un tajo del botín si te embisten. hay **peatones** que cruzan
y se asustan, una **racha** que multiplica lo que levantás mientras manejes
limpio, y **poderes** tirados por la calle: nitro, imán, soborno y reloj.

y está **el banco**: la plata que llevás encima es la que te sacan las
patrullas. si pasás por el banco con un mínimo, la depositás con un 10% de
propina y queda a salvo — y el banco se muda lejos. es la decisión de cada
vuelta: ¿sigo juntando con la patrulla atrás, o voy a guardar?

la partida dura 90 segundos y ni el reloj ni los poderes pueden estirarla más
(el reloj suma con tope), así que se juega entera en menos de dos minutos.

la lógica vive en clases sin pyxel — City, Car, Ped, Cop y **Partida**, que es
el juego entero: recibe el input ya leído y devuelve una lista de eventos. World
sólo lee el teclado, traduce esos eventos a chispas y dibuja. así toda la
mecánica se testea sin abrir ventana, incluido "¿termina siempre a los 90s?".
"""
import math
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

W, H = 384, 288
HUD = 16
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
WANTED_MAX = 4
BUST_COST = 0.08                 # cuánto del botín te saca una patrulla
BUST_GRACE = 150                 # invulnerable un rato después del embiste
BUST_STUN = 75                   # y la patrulla se queda frenada otro tanto
POWER_GAP = 7 * 60               # cada cuánto aparece un poder nuevo
POWERS_MAX = 2

# el banco: depositar lo que llevás lo pone a salvo de las patrullas y paga
# una propina. hay un mínimo para que no sea un trámite de cada esquina.
BANCO_MIN = 300
BANCO_PROPINA = 0.10
BANCO_R = 18                     # radio para depositar, en píxeles

# tipos de tile
ROAD, SIDEWALK, GRASS, TREE, FOUNT, BLD = range(6)
SOLID = (TREE, FOUNT, BLD)
WALKABLE = (SIDEWALK, GRASS, ROAD)

# poderes
NITRO, IMAN, SOBORNO, RELOJ = range(4)
POWER_NAME = {NITRO: "¡NITRO!", IMAN: "¡IMÁN!", SOBORNO: "¡SOBORNO!",
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
 GOLD, MAGENTA, MAPBG, MAPRD, MAPME) = range(46)
PAL = [
    0x0C0E14, 0x33383F, 0xC9A227, 0x6B7280, 0x828A9C, 0x3E7A32, 0x4E9440,
    0x57A544, 0x2E5E28, 0x6B4A2A, 0x3E86C4, 0x8A5A44, 0x6E6A82, 0xB0865A,
    0x242834, 0x7ADCFF, 0xE0402A, 0x9C2A1E, 0xFFF0A0, 0x3FA65C, 0x9BE88A,
    0xE8ECF5, 0x5A6480, 0x8AC52F, 0x070810, 0xF2F5FB,
    0x1E3A8A, 0xDCE3F0, 0xFF3B30, 0x4DA6FF, 0xE8B48A, 0xD8483A, 0x4A78D8,
    0xE7C13B, 0x6E7684, 0x39404E, 0xFFF3B0, 0xFFA23A, 0xE0402A, 0x7ADCFF,
    0x2E7FBF, 0xFFD24A, 0xD84AB8, 0x11131C, 0x3A4152, 0x8AC52F,
] + [0] * (256 - 46)

SMOKE = (SMOKE1, SMOKE2, ASPHALT)
SPARKS = (WHITE, SPARK1, SPARK2, SPARK3)
NITROFX = (WHITE, NITRO1, NITRO2, WATER)
CASH = (WHITE, BILL2, BILL, GRASS1)


class City:
    """la ciudad en tiles: calles, veredas, plazas con árboles y fuentes."""

    def __init__(self, seed=20260726):
        self.mw, self.mh = MW, MH
        self.t = [[BLD] * MW for _ in range(MH)]
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
        return self.tile(int(x // TILE), int(y // TILE)) in SOLID

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
    con los números viejos (ACCEL 0.10, DRAG 0.94) el equilibrio estaba en
    **1.57** contra un MAXSPD declarado de 3.4: el auto no llegaba ni a la mitad
    de su tope, tardaba una eternidad en arrancar, y ningún `maxspd` del juego
    hacía nada — ni el de las patrullas ni el 5.4 del nitro.

    calculando `accel` a partir de `maxspd` en cada frame, la velocidad terminal
    **es** `maxspd` por construcción y no se pueden desincronizar. subir el tope
    de una patrulla ahora la hace más rápida de verdad.
    """

    DRAG = 0.94                    # cuánto conserva por frame (la inercia)
    MAXSPD, MAXREV, TURN = 3.4, 1.5, 0.070
    CRASH_FRAC = 0.55              # a partir de qué fracción del tope es "golpe"
    GRIP_FRAC = 0.45               # y a qué fracción el volante ya agarra del todo

    def __init__(self, x, y, a=0.0, maxspd=None):
        self.x, self.y, self.a, self.spd = x, y, a, 0.0
        self.maxspd = self.MAXSPD if maxspd is None else maxspd
        self.crashed = False           # chocó en el último step

    @property
    def accel(self):
        """la que hace que el equilibrio caiga justo en `maxspd`."""
        return self.maxspd * (1 - self.DRAG) / self.DRAG

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
        """si el morro quedó metido en un edificio, sacalo de a poco.

        éste es el atasco que se sentía "pegado" después de un rato: el
        paragolpes vive a 8 px del centro, así que con el morro adentro de un
        muro **toda** posición vecina también lo tiene adentro. el auto quedaba
        clavado con el centro en plena calle, sin poder avanzar ni deslizar en
        ninguna dirección, y encima cada frame el choque le comía la velocidad,
        así que tampoco lograba maniobrar para salir. medido: 0 px recorridos en
        4.500 frames seguidos.

        resolver la penetración es lo que hace cualquier motor de colisión:
        empujamos el auto en sentido contrario al morro hasta que se libere.
        no depende de que el jugador adivine que tiene que meter reversa.
        """
        fx_, fy_ = self._parag()
        if not city.solid_px(self.x + fx_, self.y + fy_):
            return
        ex, ey = -math.cos(self.a) * 0.7, -math.sin(self.a) * 0.7
        for _ in range(12):                    # como mucho 8 px, el largo del morro
            if not city.solid_px(self.x + fx_, self.y + fy_):
                return
            if city.solid_px(self.x + ex, self.y + ey):
                return                         # atrás tampoco hay lugar: rendite
            self.x += ex
            self.y += ey

    def step(self, throttle, steer, city):
        self.spd += throttle * self.accel
        self.spd *= self.DRAG
        self.spd = max(-self.MAXREV, min(self.maxspd, self.spd))
        if abs(self.spd) > 0.15:
            grip = min(1.0, abs(self.spd) / (self.maxspd * self.GRIP_FRAC))
            self.a += steer * self.TURN * (1 if self.spd > 0 else -1) * grip
        elif throttle:
            # clavado y acelerando: igual podés maniobrar en el sitio. sin esto
            # hay un empate del que no se sale — chocar te quita la velocidad,
            # y sin velocidad no hay grip para girar, así que volvés a chocar.
            # un bot terminó una partida entera parado en la misma esquina.
            self.a += steer * self.TURN * 0.6
        dx, dy = math.cos(self.a) * self.spd, math.sin(self.a) * self.spd
        nx, ny = self.x + dx, self.y + dy
        self.crashed = False
        if self._libre(city, nx, ny):
            self.x, self.y = nx, ny
        else:
            if abs(self.spd) > self.maxspd * self.CRASH_FRAC:
                self.crashed = True         # golpe de verdad, no un roce
            # **deslizar en vez de clavarse**: si el paso completo no entra,
            # probamos cada eje por separado. rozar una pared en diagonal te
            # frena y te acompaña, que es como se maneja un top-down; frenar en
            # seco contra cualquier esquina era lo que hacía sentir el auto
            # trabado aun cuando aceleraba bien.
            if self._libre(city, nx, self.y):
                self.x = nx
                self.spd *= 0.72
            elif self._libre(city, self.x, ny):
                self.y = ny
                self.spd *= 0.72
            else:
                # de frente: frena, pero no te clava. con el 0.15 de antes cada
                # roce te dejaba en cero y en calles de dos tiles se raspa todo
                # el tiempo — se sentía como manejar con el freno de mano puesto
                self.spd *= 0.30
        self._desencajar(city)
        self.x = max(8, min(MAP_PX - 8, self.x))
        self.y = max(8, min(MAP_PY - 8, self.y))


class Ped:
    """un peatón: camina por la vereda y se asusta si le pasás cerca.

    no es un obstáculo sólido — es una multa con piernas: llevártelo puesto no
    te frena, te sube una estrella de búsqueda y te corta la racha. huye del
    auto cuando lo tiene encima, así casi siempre se salva solo.
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
    """una patrulla: **maneja**, no flota. usa el mismo Car que vos.

    la IA es de tres líneas — apuntá al jugador, acelerá si estás mirando para
    allá, y si te quedaste pegado contra un muro meté marcha atrás. eso alcanza
    para que persiga por las calles y a veces se estrelle sola, que es la mitad
    de la gracia.
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
            # se queda pegada y te cobra otra vez apenas se acaba tu inmunidad —
            # un bot comió 33 embistes en una partida y terminó sin nada.
            self.stun -= 1
            c.step(0, 0, city)
            return False
        want = math.atan2(ty - c.y, tx - c.x)
        diff = (want - c.a + math.pi) % math.tau - math.pi   # -pi..pi
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


class Partida:
    """el juego entero, sin pyxel: recibe el input y devuelve qué pasó.

    `step(thr, steer)` avanza un frame y devuelve una lista de eventos
    (`("fajo", x, y, monto)`, `("choque", x, y)`, ...). el World los traduce a
    chispas y carteles; los tests los leen para saber qué ocurrió. la lógica no
    sabe que existe una pantalla.
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
        """pasás por el banco con el mínimo encima: se guarda con propina, y
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
    def _lejos(self, pool, minimo=140, maximo=None):
        """un tile del pool a la distancia justa del auto: ni encima, ni perdido.

        el `maximo` no estaba y era el problema más grande del juego: los fajos
        se repartían por todo el mapa (704×544) y en 90 segundos un jugador
        apenas alcanzaba dos o tres — un bot que perseguía el más cercano
        terminó varias corridas en $0. spawneándolos en un anillo alrededor
        tuyo siempre hay algo a mano y la partida no se muere buscando.
        """
        for _ in range(40):
            tx, ty = self.rng.choice(pool)
            x, y = tx * TILE + 8, ty * TILE + 8
            d2 = (x - self.car.x) ** 2 + (y - self.car.y) ** 2
            if d2 > minimo * minimo and (maximo is None or d2 < maximo * maximo):
                return x, y
        return tx * TILE + 8, ty * TILE + 8

    def _spawn_bill(self):
        self.bills.append(list(self._lejos(self.roads, 60, 220)))

    def _spawn_ped(self):
        if not self.walks:
            return
        x, y = self._lejos(self.walks, 90)
        self.peds.append(Ped(x, y, self.rng.uniform(0, math.tau), self.rng))

    def _spawn_cop(self):
        x, y = self._lejos(self.roads, 190)
        a = math.atan2(self.car.y - y, self.car.x - x)
        # cada estrella los hace un poco más rápidos, pero SIEMPRE por debajo
        # tuyo: con 2.9 + 0.22·estrellas, a las 4 estrellas la patrulla corría
        # a 3.78 contra tus 3.4 y era imposible sacártela de encima — un bot
        # comió 31 embistes en una sola partida. que te pisen los talones es
        # la gracia; que te alcancen sí o sí, no.
        tope = min(Car.MAXSPD - 0.2, 2.6 + 0.15 * self.wanted)
        self.cops.append(Cop(x, y, a, maxspd=tope))

    def _spawn_power(self):
        x, y = self._lejos(self.roads, 110, 380)
        self.powers.append([x, y, self.rng.randrange(4)])

    # --- calor -----------------------------------------------------------
    def _recalcular_wanted(self, ev):
        """el calor sube con lo que llevás robado y con los sustos que diste."""
        objetivo = min(WANTED_MAX,
                       (self.money + self.banco - self.calor_base) // CALOR
                       + self.atropellos)
        if objetivo > self.wanted:
            self.wanted = objetivo
            ev.append(("wanted", self.wanted))
        while len(self.cops) < self.wanted:
            self._spawn_cop()

    def _enfriar(self, ev):
        """el soborno: borra las estrellas y se lleva a las patrullas.

        además corre el piso del calor a la plata que llevás ahora. sin eso,
        el mismo dinero volvía a levantar la estrella al frame siguiente y el
        soborno no servía para nada: hay que volver a robar para calentarte.
        """
        self.wanted = 0
        self.atropellos = 0
        self.calor_base = self.money + self.banco
        self.cops = []
        ev.append(("enfriado", 0))

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

        car.step(thr, steer, self.city)
        if car.crashed:
            ev.append(("choque", car.x, car.y))
            if self.racha:
                self.racha = 0                      # chocar te corta la racha
                ev.append(("racha_rota", car.x, car.y))

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

        # la racha se enfría sola si dejás de levantar
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

        # peatones
        for ped in self.peds:
            if ped.step(self.city, car) and abs(car.spd) > 0.6:
                ped.gone = True
                self.atropellos += 1
                self.racha = 0
                ev.append(("atropello", ped.x, ped.y))
        vivos = [p for p in self.peds if not p.gone]
        faltan = 14 - len(vivos)
        self.peds = vivos
        for _ in range(faltan):
            self._spawn_ped()

        self._recalcular_wanted(ev)

        # patrullas
        for cop in self.cops:
            if cop.step(self.city, car.x, car.y) and self.grace <= 0:
                perdido = int(self.money * BUST_COST)
                self.money = max(0, self.money - perdido)
                self.racha = 0
                self.busts += 1
                self.grace = BUST_GRACE
                cop.stun = BUST_STUN
                car.spd *= -0.35                    # el embiste te rebota
                ev.append(("embiste", cop.x, cop.y, perdido))

        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("fin", car.x, car.y))
        return ev

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


class World:
    """la partida jugándose: lee el teclado, dibuja y le pone chispas."""

    def __init__(self):
        self.p = Partida()
        self.fx = fx.Fx(gravity=0.0)
        self.fx.destello(WHITE)
        self.combo_pop = 0
        self.minimap = None
        self.exhaust = 0

    @property
    def over(self):
        return self.p.over

    @property
    def score(self):
        return self.p.score

    # --- update ----------------------------------------------------------
    def update(self):
        thr = (1 if pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W) else 0) \
            - (1 if pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S) else 0)
        st = (1 if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D) else 0) \
            - (1 if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A) else 0)
        antes = self.p.mult()
        for e in self.p.step(thr, st):
            self._efecto(e, antes)
        if self.p.mult() > antes:
            self.combo_pop = 26
        if self.combo_pop:
            self.combo_pop -= 1
        # humo del escape cuando acelerás fuerte, y llamarada con nitro
        car = self.p.car
        self.exhaust += 1
        if abs(car.spd) > 1.8 and self.exhaust % 3 == 0:
            back = car.a + math.pi
            self.fx.burst(car.x + math.cos(back) * 10, car.y + math.sin(back) * 10,
                          NITROFX if self.p.nitro else SMOKE,
                          n=3 if self.p.nitro else 2, speed=0.9, life=16,
                          spread=0.7, angle=back)
        self.fx.update()

    def _efecto(self, e, mult_antes):
        """cada evento de la lógica se vuelve chispas, cartel y temblor."""
        kind = e[0]
        if kind == "fajo":
            _, x, y, monto = e
            self.fx.burst(x, y, CASH, n=14, speed=1.9, life=26)
            self.fx.popup(x, y - 8, "$%d" % monto, BILL2)
        elif kind == "choque":
            _, x, y = e
            self.fx.burst(x, y, SPARKS, n=12, speed=2.1, life=18)
            self.fx.shake(3)
        elif kind == "embiste":
            _, x, y, perdido = e
            self.fx.burst(x, y, SPARKS, n=26, speed=2.8, life=26)
            self.fx.popup(self.p.car.x, self.p.car.y - 12, "-$%d" % perdido, LIGHTR)
            self.fx.shake(6)
            self.fx.destello(LIGHTR)
        elif kind == "atropello":
            _, x, y = e
            self.fx.burst(x, y, (WHITE, SKIN, PED1), n=10, speed=1.6, life=22)
            self.fx.popup(x, y - 10, "¡EH!", WHITE)
            self.fx.shake(2)
        elif kind == "power":
            _, x, y, tipo = e
            self.fx.burst(x, y, (WHITE, GOLD, MAGENTA), n=22, speed=2.4, life=30)
            self.fx.popup(x, y - 12, POWER_NAME[tipo], GOLD)
            self.fx.destello(GOLD)
        elif kind == "deposito":
            _, x, y, monto, propina = e
            self.fx.burst(x, y, CASH, n=30, speed=2.6, life=34)
            self.fx.popup(x, y - 14, "A SALVO $%d" % monto, BILL2)
            if propina:
                self.fx.popup(x, y - 26, "+$%d propina" % propina, GOLD)
            self.fx.shake(3)
            self.fx.destello(BILL2)
        elif kind == "wanted":
            self.fx.popup(self.p.car.x, self.p.car.y - 16,
                          "BUSCADO %d" % e[1], LIGHTR)
            self.fx.destello(LIGHTR)
        elif kind == "enfriado":
            self.fx.popup(self.p.car.x, self.p.car.y - 16, "TE SOLTARON", ACCENT)
            self.fx.destello(ACCENT)
        elif kind == "racha_rota":
            _, x, y = e
            if mult_antes > 1:
                self.fx.popup(x, y - 14, "RACHA ROTA", DIM)

    # --- dibujo ----------------------------------------------------------
    def _cam(self):
        cx = max(0, min(MAP_PX - W, self.p.car.x - W / 2))
        cy = max(0, min(MAP_PY - VIEW_H, self.p.car.y - VIEW_H / 2))
        return cx, cy

    def draw(self):
        pyxel.cls(BG)
        camx, camy = self._cam()
        sx, sy = self.fx.offset()
        camx -= sx                                   # el temblor mueve la cámara
        camy -= sy
        t0x, t0y = int(camx // TILE), int(camy // TILE)
        for ty_ in range(VIEW_H // TILE + 2):
            for tx_ in range(W // TILE + 2):
                tx, ty = t0x + tx_, t0y + ty_
                self._tile(tx * TILE - camx, ty * TILE - camy + HUD, tx, ty)
        bx, by = self.p.banco_xy
        self._banco(bx - camx, by - camy + HUD)
        for p in self.p.powers:
            self._power(p[0] - camx, p[1] - camy + HUD, p[2])
        for b in self.p.bills:
            self._bill(b[0] - camx, b[1] - camy + HUD)
        for ped in self.p.peds:
            self._ped(ped, camx, camy)
        self.fx.draw(camx, camy - HUD)
        for cop in self.p.cops:
            self._car_sprite(cop.x - camx, cop.y - camy + HUD, cop.car.a,
                             COP1, COP2, cop=True)
        car = self.p.car
        if self.p.grace <= 0 or (pyxel.frame_count // 4) % 2:
            self._car_sprite(car.x - camx, car.y - camy + HUD, car.a,
                             CARBODY, CARROOF)
        if self.p.iman:
            self._halo(car.x - camx, car.y - camy + HUD)
        self.fx.draw_flash(0, HUD, W, VIEW_H)
        self._hud()
        self._minimap()

    def _tile(self, px, py, tx, ty):
        px, py = int(px), int(py)
        t = self.p.city.tile(tx, ty)
        if t == ROAD:
            pyxel.rect(px, py, TILE, TILE, ASPHALT)
            if tx % B == 0 and (ty % 3):
                pyxel.rect(px + TILE - 1, py, 2, TILE, LINE)
            if ty % B == 0 and (tx % 3):
                pyxel.rect(px, py + TILE - 1, TILE, 2, LINE)
        elif t == SIDEWALK:
            pyxel.rect(px, py, TILE, TILE, SIDE)
            pyxel.rectb(px, py, TILE, TILE, SIDE2)
        elif t == GRASS:
            pyxel.rect(px, py, TILE, TILE, GRASS1)
            pyxel.pset(px + 4, py + 5, GRASS2)
            pyxel.pset(px + 11, py + 10, GRASS2)
        elif t == TREE:
            pyxel.rect(px, py, TILE, TILE, GRASS1)
            pyxel.rect(px + 7, py + 8, 2, 5, TRUNK)
            pyxel.circ(px + 8, py + 6, 5, TREEDK)
            pyxel.circ(px + 8, py + 6, 4, TREETOP)
        elif t == FOUNT:
            pyxel.rect(px, py, TILE, TILE, SIDE)
            pyxel.circ(px + 8, py + 8, 6, SIDE2)
            pyxel.circ(px + 8, py + 8, 4, WATER)
            pyxel.pset(px + 7, py + 6, WHITE)
        else:  # BLD
            bx, by = tx // B, ty // B
            base = (BLD1, BLD2, BLD3)[(bx * 7 + by * 11) % 3]
            pyxel.rect(px, py, TILE, TILE, base)
            pyxel.rectb(px, py, TILE, TILE, ROOF)
            for wy in (4, 10):
                for wx in (4, 10):
                    lit = (tx * 3 + ty * 5 + wx + wy) % 3 == 0
                    pyxel.rect(px + wx, py + wy, 2, 2, GLASS if lit else ROOF)

    def _banco(self, cx, cy):
        """la boca del banco: un rombo verde en la calle con el $ adentro. late
        cuando llevás lo suficiente como para depositar."""
        cx, cy = int(cx), int(cy)
        if not (-20 < cx < W + 20 and HUD - 20 < cy < H + 20):
            return
        activo = self.p.money >= BANCO_MIN
        r = BANCO_R - 4 + ((pyxel.frame_count // 5) % 2 if activo else 0)
        col = BILL2 if activo else BILL
        for i in range(4):
            a0 = i * math.pi / 2 + pyxel.frame_count * 0.03
            a1 = a0 + math.pi / 2
            pyxel.line(int(cx + math.cos(a0) * r), int(cy + math.sin(a0) * r),
                       int(cx + math.cos(a1) * r), int(cy + math.sin(a1) * r), col)
        pyxel.rect(cx - 5, cy - 4, 10, 8, SHADOW)
        pyxel.rectb(cx - 5, cy - 4, 10, 8, col)
        text(cx - 2, cy - 3, "$", col)

    def _flecha_banco(self):
        """cuando llevás plata para depositar, una flecha en el hud apunta al
        banco. sin esto, el banco mudado es un punto en el minimapa y nada más."""
        p = self.p
        if p.money < BANCO_MIN:
            return
        bx, by = p.banco_xy
        a = math.atan2(by - p.car.y, bx - p.car.x)
        cx, cy = W - MW - 40, H - 10          # al lado del minimapa: es un plano
        col = BILL2 if (pyxel.frame_count // 8) % 2 else GOLD
        px, py = cx + math.cos(a) * 6, cy + math.sin(a) * 6
        lx, ly = cx + math.cos(a + 2.6) * 5, cy + math.sin(a + 2.6) * 5
        rx, ry = cx + math.cos(a - 2.6) * 5, cy + math.sin(a - 2.6) * 5
        pyxel.tri(int(px), int(py), int(lx), int(ly), int(rx), int(ry), col)
        text(cx - 30, cy - 3, "banco", col)

    def _bill(self, cx, cy):
        """un fajo de billetes, flotando apenas para que se vea desde lejos."""
        cx, cy = int(cx), int(cy + (pyxel.frame_count // 8) % 2)
        pyxel.rect(cx - 5, cy - 1, 10, 5, SHADOW)
        pyxel.rect(cx - 5, cy - 3, 10, 5, BILL)
        pyxel.rect(cx - 5, cy - 3, 10, 1, BILL2)
        pyxel.pset(cx, cy - 1, BILL2)
        pyxel.pset(cx - 3, cy - 1, BILL2)
        pyxel.pset(cx + 3, cy - 1, BILL2)

    def _power(self, cx, cy, tipo):
        """la caja de poder: late y trae su símbolo adentro."""
        cx, cy = int(cx), int(cy)
        r = 7 + (pyxel.frame_count // 5) % 2
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

    def _ped(self, ped, camx, camy):
        x, y = int(ped.x - camx), int(ped.y - camy + HUD)
        if not (-8 < x < W + 8 and HUD - 8 < y < H + 8):
            return
        ropa = (PED1, PED2, PED3)[int(ped.x + ped.y) % 3]
        paso = (pyxel.frame_count // (4 if ped.scared else 9)) % 2
        pyxel.rect(x - 1, y + 3, 3, 1, SHADOW)
        pyxel.rect(x - 1, y - 1, 3, 4, ropa)               # cuerpo
        pyxel.pset(x - 1 + paso, y + 3, ropa)              # la pierna que pisa
        pyxel.rect(x - 1, y - 3, 3, 2, SKIN)               # cabeza
        if ped.scared:
            pyxel.pset(x + (2 if paso else -2), y - 5, WHITE)   # gotita de susto

    def _car_sprite(self, sx, sy, a, body, roof, cop=False):
        cosa, sina = math.cos(a), math.sin(a)

        def corner(f, s):
            return (int(sx + f * cosa - s * sina), int(sy + f * sina + s * cosa))

        fl, fr = corner(11, -6), corner(11, 6)
        bl, br = corner(-11, -6), corner(-11, 6)
        sh = [(x + 2, y + 2) for x, y in (fl, fr, br, bl)]
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
            izq = (pyxel.frame_count // 4) % 2
            for s, on in ((-3, izq), (3, not izq)):
                bxp, byp = corner(0, s)
                pyxel.rect(bxp - 1, byp - 1, 2, 2, LIGHTR if on else LIGHTB)

    def _halo(self, cx, cy):
        """el anillo del imán, girando, para que se note que está activo."""
        for i in range(8):
            a = pyxel.frame_count * 0.09 + i * math.tau / 8
            pyxel.pset(int(cx + math.cos(a) * IMAN_R * 0.5),
                       int(cy + math.sin(a) * IMAN_R * 0.5), MAGENTA)

    # --- hud -------------------------------------------------------------
    def _hud(self):
        p = self.p
        pyxel.rect(0, 0, W, HUD, SHADOW)
        text(4, 5, "$%d" % p.money, BILL2)
        m = p.mult()
        if m > 1:
            col = GOLD if self.combo_pop and (pyxel.frame_count // 3) % 2 else BILL2
            text(70, 5, "x%d" % m, col)
            fx.bar(88, 6, 30, 4, p.racha_t / RACHA_TTL, ACCENT, ASPHALT)
        if p.wanted:
            for i in range(p.wanted):
                self._estrella(140 + i * 11, 8,
                               LIGHTR if (pyxel.frame_count // 8) % 2 else GOLD)
        if p.nitro:
            fx.bar(W - 170, 6, 34, 4, p.nitro / NITRO_TTL, NITRO1, ASPHALT)
            text(W - 200, 5, "nitro", NITRO1)
        if p.iman:
            fx.bar(W - 120, 6, 34, 4, p.iman / IMAN_TTL, MAGENTA, ASPHALT)
            text(W - 148, 5, "imán", MAGENTA)
        s = p.time // 60
        col = WHITE if s <= 10 and pyxel.frame_count % 30 < 15 else TXT
        r = "%ds" % s
        text(W - len(r) * 4 - 4, 5, r, col)

    def _estrella(self, x, y, col):
        pyxel.rect(x - 3, y, 7, 1, col)
        pyxel.rect(x, y - 3, 1, 7, col)
        pyxel.pset(x - 2, y - 2, col)
        pyxel.pset(x + 2, y - 2, col)
        pyxel.pset(x - 2, y + 2, col)
        pyxel.pset(x + 2, y + 2, col)

    def _minimap(self):
        """el plano de la ciudad, pintado UNA vez a un Image y después blt.

        eran 1.496 tiles: dibujarlos con pset cada frame costaba más que la
        ciudad entera. acá el plano es una imagen de 44×34 que se estampa de un
        golpe, y sólo los puntos que se mueven se dibujan encima.
        """
        if self.minimap is None:
            img = pyxel.Image(MW, MH)
            for ty in range(MH):
                for tx in range(MW):
                    t = self.p.city.tile(tx, ty)
                    img.pset(tx, ty, MAPRD if t == ROAD else
                             (GRASS1 if t in (GRASS, TREE) else MAPBG))
            self.minimap = img
        mx, my = W - MW - 4, H - MH - 4
        pyxel.rect(mx - 1, my - 1, MW + 2, MH + 2, SHADOW)
        if self.p.banco:                       # lo guardado, arriba del plano
            r = "$%d a salvo" % self.p.banco
            pyxel.rect(W - len(r) * 4 - 6, my - 11, len(r) * 4 + 4, 9, SHADOW)
            text(W - len(r) * 4 - 4, my - 9, r, BILL)
        self._flecha_banco()
        pyxel.blt(mx, my, self.minimap, 0, 0, MW, MH)
        for b in self.p.bills:
            pyxel.pset(mx + int(b[0] // TILE), my + int(b[1] // TILE), BILL2)
        for p in self.p.powers:
            pyxel.pset(mx + int(p[0] // TILE), my + int(p[1] // TILE), GOLD)
        bx, by = self.p.banco_xy
        pyxel.rectb(mx + int(bx // TILE) - 1, my + int(by // TILE) - 1, 3, 3,
                    BILL2 if (pyxel.frame_count // 8) % 2 else BILL)
        if (pyxel.frame_count // 6) % 2:
            for cop in self.p.cops:
                pyxel.pset(mx + int(cop.x // TILE), my + int(cop.y // TILE), LIGHTR)
        car = self.p.car
        pyxel.rect(mx + int(car.x // TILE), my + int(car.y // TILE), 2, 2, MAPME)


class Game:
    def __init__(self):
        Cabinet(
            game_id="autos", title="AUTOS", subtitle="90 segundos de atraco",
            howto=["flechas o wasd manejan", "levantá fajos sin chocar: multiplican",
                   "la plata trae patrullas · agarrá los poderes",
                   "pasá por el banco: lo depositado no te lo sacan"],
            width=W, height=H, palette=PAL, scale=2, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=CARBODY, shadow=SHADOW, panel=ASPHALT),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
