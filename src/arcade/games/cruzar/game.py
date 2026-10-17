"""cruzar — 90 segundos para pasar de un lado al otro, para MHW RETRO FUTURE.

vas de abajo hacia arriba esquivando lo que cruza cada carril. llegas arriba,
sumas, y vuelves a empezar desde abajo — en un **tramo nuevo**: cada cruce
cambia el escenario, así nunca se cruza de memoria.

- **barrio**: autos y camiones abajo, cintas arriba.
- **avenida**: motos que pegan acelerones, y una vereda en el medio para
  respirar.
- **vía del tren**: un carril de rieles vacío... hasta que suenan las luces.
  el aviso dura un segundo; el tren, casi nada, pero no perdona.
- **el río**: agua de verdad. hay que ir **sobre** los troncos, y algunos se
  hunden (titilan antes de bajar).
- **autopista**: todo junto, más rápido.

las cintas no matan: arrastran hacia el costado, y el borde de la pantalla sí.
el río es al revés: lo que flota te salva. son lecturas distintas del mismo
salto.

y además:

- **la racha**: cada dos cruces limpios multiplica, hasta x5. te tocan y
  vuelve a uno; si tardas mucho en cruzar, se enfría sola.
- **el semáforo**: cada tanto un carril de tráfico se pone en rojo y frena.
- **el ritmo sube con cada cruce**, con techo.
- **monedas** que viajan con el tráfico, e **ítems** en la vereda: el
  **escudo** aguanta un golpe y el **reloj** congela el tráfico unos segundos
  (el reloj de la partida no: ése no se detiene nunca).
- **hora punta**: los últimos 15 s cada cruce vale doble.

la lógica vive en la clase Cruce, sin pyxel: `step()` avanza un frame con el
movimiento ya leído y devuelve qué pasó.
"""
import math
import random

import pyxel

from pixelkit import web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import ctext, text

from .grande import Fx, big, cbig

W, H = 240, 208
HUD = 16
LANE_H = 14                      # alto de cada carril
LANES = 11                       # carriles entre la orilla de abajo y la meta
TOP = HUD + LANE_H               # la meta: la franja de arriba
BOTTOM = TOP + LANES * LANE_H    # la orilla de abajo, desde donde sales

TIME = 90 * 60
VIDAS = 3
GRACIA = 90
PW, PH = 10, 11                  # el que cruza
PASO_X = 8                       # un toque al costado (un swipe = un paso que se ve)
HOLGURA = 2                      # el auto tiene que morderte de verdad

MULT_MAX = 5
VUELTA_TTL = 10 * 60             # tardar más que esto enfría la racha
CRUCE_VALE = 100

TRAFICO, CINTA, RIO, TREN, VEREDA = range(5)
AUTO, CAMION, MOTO, BUS = range(4)   # qué anda por un carril de tráfico
SEMAFORO_GAP = 7 * 60
SEMAFORO_TTL = 3 * 60

# el ritmo: cada cruce acelera el tráfico un poco, con techo, para que el
# cruce 20 siga siendo cruzable.
RITMO_PASO = 0.05
RITMO_MAX = 1.6
VIDA_CADA = 4                    # cada 4 cruces, una vida de vuelta (sin pasar de 3)

# las monedas: nacen en un carril de tráfico, entre dos autos, y viajan con él.
MONEDA_GAP = 3 * 60
MONEDA_TTL = 9 * 60
MONEDA_VALE = 40
MONEDAS_MAX = 2

# los ítems: en la vereda si hay, si no en el tráfico. uno a la vez.
ESCUDO, HIELO = range(2)
ITEM_GAP = 7 * 60
ITEM_TTL = 8 * 60
ITEM_VALE = 20
HIELO_TTL = 3 * 60
HIELO_K = 0.3                    # a qué fracción anda el tráfico congelado
ESCUDO_GRACIA = 50

# el tren: espera, avisa, pasa. el aviso es fijo (no se acorta con el ritmo):
# es la parte que tiene que ser justa.
TREN_ESPERA = (2 * 60, 5 * 60)
TREN_AVISO = 66
TREN_V = 6.5
TREN_LARGO = 150

# los troncos que se hunden: un ciclo por tronco, desfasados entre sí
HUNDE_CICLO = 300
HUNDE_AVISO = 60
HUNDE_ABAJO = 80

CLIMAX_T = 15 * 60               # la hora punta
CLIMAX_X = 2

# los tramos: nombre y carriles de arriba hacia abajo.
# C cinta · A río · V vereda · T autos · K camiones · B buses · M motos · F tren
TRAMOS = (
    ("BARRIO", "CCCTKTTKTBT"),
    ("AVENIDA", "CCCTMBVTMKT"),
    ("VÍA DEL TREN", "CCCVTKFMTFT"),
    ("EL RÍO", "ACAVTMKTFBT"),
    ("AUTOPISTA", "CAAVMKFMTBM"),
)

(BG, ROAD1, ROAD2, EDGE, LINEA, PLAYER, PLAYER2, CAR1, CAR2, CAR3, TRUCK,
 CINTA1, CINTA2, TXT, DIM, ACCENT, WARN, SHADOW, WHITE, NEON, PINK, GOLD,
 META, ROJO, AGUA1, AGUA2, ESPUMA, TRONCO, TRONCODK, TRONCOHI, TRENC,
 TRENDK, VEREDAC, VEREDA2, ROAD_AV, ROAD_VIA, ROAD_RIO, ROAD_AUTO, MOTOC,
 BUSC, SHIELD, HIELOC, GOLDDK, HUDC, RIEL, DURMIENTE, LUZ, VIDRIO) = range(48)
PAL = [
    0x0B0A16, 0x1E1B3A, 0x171430, 0x3A2C63, 0x6E6499, 0x38E8E0, 0xA8FFF8,
    0xFF6EC7, 0xFFD24A, 0x9AE84A, 0xE04A2A, 0x2E7FBF, 0x7ADCFF, 0xE8ECF5,
    0x9A90C8, 0x38E8E0, 0xFF5A3A, 0x060512, 0xF2F5FB, 0x38E8E0, 0xE868C8,
    0xFFD24A, 0x9AE84A, 0xFF3B30,
    0x173E7A, 0x2660B0, 0xBFE8FF, 0x9A6430, 0x5E3A1A, 0xD49A58, 0xC8D0E0,
    0x6A7490, 0x2E2A44, 0x423C5E, 0x131E3A, 0x1A2430, 0x132A26, 0x2A1626,
    0xFF9A3E, 0x4DA6FF, 0x7ADCFF, 0xA8E8FF, 0xA8741E, 0x07060F, 0x8A84A8,
    0x3A2C2A, 0xFFF2A8, 0x2A3A5A,
] + [0] * (256 - 48)

FONDO = {"BARRIO": ROAD2, "AVENIDA": ROAD_AV, "VÍA DEL TREN": ROAD_VIA,
         "EL RÍO": ROAD_RIO, "AUTOPISTA": ROAD_AUTO}

CHISPA_CRUCE = (WHITE, NEON, ACCENT, CINTA1)
CHISPA_GOLPE = (WHITE, WARN, TRUCK, ROAD2)
CHISPA_AGUA = (WHITE, ESPUMA, AGUA2, AGUA1)
CONFETI = (WHITE, GOLD, PINK, NEON, META)


class Carril:
    """una fila con cosas que se mueven. o te atropellan, o te arrastran, o
    te sostienen."""

    def __init__(self, i, tipo, v, ancho, hueco, rng, vehiculo=AUTO,
                 hunde=False):
        self.i = i
        self.tipo = tipo
        self.v = v                       # px por frame, con signo
        self.ancho = ancho
        self.vehiculo = vehiculo
        self.rojo = 0                    # frames de semáforo en rojo
        self.cosas = []                  # x de cada vehículo/plataforma
        self.hueco = hueco
        self.rng = rng
        self.t = 0
        self.fase = rng.uniform(0, math.tau)
        if tipo in (TRAFICO, CINTA, RIO):
            x = rng.uniform(0, hueco)
            while x < W + ancho:
                self.cosas.append(x)
                x += hueco
        # los troncos que se hunden: cada uno con su desfase
        self.hunde = [rng.randrange(HUNDE_CICLO) for _ in self.cosas] \
            if hunde else None
        # el tren
        self.tren_t = rng.randint(*TREN_ESPERA) if tipo == TREN else 0
        self.aviso = 0

    @property
    def y(self):
        return TOP + self.i * LANE_H

    def factor(self):
        """las motos pegan acelerones: la velocidad late."""
        if self.vehiculo == MOTO and self.tipo == TRAFICO:
            return 1.0 + 0.55 * math.sin(self.t * 0.045 + self.fase)
        return 1.0

    def vel(self):
        if self.rojo or self.tipo in (VEREDA, TREN):
            return 0.0
        return self.v * self.factor()

    def step(self, ritmo=1.0):
        self.t += 1
        if self.tipo == TREN:
            self._tren(ritmo)
            return
        if self.tipo == VEREDA:
            return
        if self.rojo:
            self.rojo -= 1
            return
        # el período del wrap tiene que ser el ancho recorrido, no el hueco: con
        # `W + ancho + hueco` el auto que salía se iba mucho más allá del borde
        # opuesto y tardaba de más en volver a entrar.
        p = W + 2 * self.ancho
        v = self.v * ritmo * self.factor()
        for k in range(len(self.cosas)):
            self.cosas[k] += v
            if v > 0 and self.cosas[k] > W + self.ancho:
                self.cosas[k] -= p
            elif v < 0 and self.cosas[k] < -self.ancho:
                self.cosas[k] += p
        if self.hunde is not None:
            for k in range(len(self.hunde)):
                self.hunde[k] = (self.hunde[k] + 1) % HUNDE_CICLO

    def _tren(self, ritmo):
        """espera → aviso → pasa. el congelado lo frena; el ritmo no lo apura."""
        if self.cosas:
            self.cosas[0] += self.v * TREN_V * min(1.0, ritmo)
            x = self.cosas[0]
            if x > W + 4 or x + self.ancho < -4:
                self.cosas = []
                self.tren_t = self.rng.randint(*TREN_ESPERA)
        elif self.aviso:
            self.aviso -= 1
            if not self.aviso:
                self.cosas = [-self.ancho if self.v > 0 else float(W)]
        else:
            self.tren_t -= 1
            if self.tren_t <= 0:
                self.aviso = TREN_AVISO

    def estado_tronco(self, k):
        """0 a flote, 1 avisando que se hunde, 2 abajo."""
        if self.hunde is None:
            return 0
        f = self.hunde[k]
        if f >= HUNDE_CICLO - HUNDE_ABAJO:
            return 2
        if f >= HUNDE_CICLO - HUNDE_ABAJO - HUNDE_AVISO:
            return 1
        return 0

    def hueco_libre(self, rng):
        """una x entre dos cosas del carril, para dejar una moneda."""
        if not self.cosas:
            return rng.uniform(8, W - 8)
        xs = sorted(self.cosas)
        i = rng.randrange(len(xs))
        sig = xs[(i + 1) % len(xs)]
        if sig <= xs[i]:
            sig += W + 2 * self.ancho
        return (xs[i] + self.ancho + sig) / 2

    def toca(self, px, pw):
        for x in self.cosas:
            if x < px + pw and x + self.ancho > px:
                return x
        return None

    def sostiene(self, px, pw):
        """¿hay algo a flote bajo el centro del que cruza? (el río)"""
        c = px + pw / 2
        for k, x in enumerate(self.cosas):
            if x - 2 <= c <= x + self.ancho + 2 and self.estado_tronco(k) != 2:
                return x
        return None


def armar_tramo(n, rng):
    """los carriles del tramo n. el primero es siempre el barrio; después
    rotan los otros cuatro, cada vez con velocidades nuevas."""
    idx = n if n < len(TRAMOS) else 1 + (n - 1) % (len(TRAMOS) - 1)
    nombre, plano = TRAMOS[idx]
    sentido = rng.choice((-1, 1))
    cs = []
    rio_n = 0
    for i, letra in enumerate(plano):
        d = sentido if i % 2 else -sentido           # alternados: se leen mejor
        if letra == "C":
            cs.append(Carril(i, CINTA, d * rng.uniform(0.4, 1.05),
                             rng.choice((34, 44, 54)),
                             rng.choice((72, 86, 100)), rng))
        elif letra == "A":
            rio_n += 1
            cs.append(Carril(i, RIO, d * rng.uniform(0.4, 0.75),
                             rng.choice((48, 56, 64)), rng.choice((78, 86, 94)),
                             rng, hunde=(rio_n % 2 == 1)))
        elif letra == "V":
            cs.append(Carril(i, VEREDA, 0.0, 0, W, rng))
        elif letra == "F":
            cs.append(Carril(i, TREN, float(d), TREN_LARGO, W, rng))
        elif letra == "K":
            cs.append(Carril(i, TRAFICO, d * rng.uniform(0.45, 0.75),
                             rng.choice((30, 36)), rng.choice((84, 100, 116)),
                             rng, CAMION))
        elif letra == "B":
            cs.append(Carril(i, TRAFICO, d * rng.uniform(0.5, 0.8), 42,
                             rng.choice((110, 126)), rng, BUS))
        elif letra == "M":
            cs.append(Carril(i, TRAFICO, d * rng.uniform(0.95, 1.25), 11,
                             rng.choice((56, 70, 84)), rng, MOTO))
        else:
            cs.append(Carril(i, TRAFICO, d * rng.uniform(0.55, 1.25),
                             rng.choice((16, 20, 24)), rng.choice((62, 74, 88)),
                             rng, AUTO))
    return nombre, cs


class Cruce:
    """el cruce entero, sin pyxel: carriles, el que cruza, racha y reloj."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.reset()

    def reset(self):
        self.px = (W - PW) / 2
        self.py = BOTTOM
        self.score = 0
        self.lives = VIDAS
        self.over = False
        self.time = TIME
        self.gracia = 0
        self.racha = 0
        self.vuelta_t = VUELTA_TTL
        self.cruces = 0
        self.sem_t = SEMAFORO_GAP
        self.monedas = []               # [carril_i, x, ttl]
        self.moneda_t = MONEDA_GAP
        self.monedas_tomadas = 0
        self.items = []                 # [carril_i, x, ttl, tipo]
        self.item_t = ITEM_GAP
        self.escudo = False
        self.hielo = 0
        self.climax = False
        self.tramo, self.carriles = armar_tramo(0, self.rng)

    def mult(self):
        return min(MULT_MAX, 1 + self.racha // 2)

    def ritmo(self):
        """cuánto más rápido va el tráfico que al empezar. sube por cruce."""
        return min(RITMO_MAX, 1 + self.cruces * RITMO_PASO)

    def ritmo_actual(self):
        """el ritmo con el congelado encima."""
        return self.ritmo() * (HIELO_K if self.hielo else 1.0)

    def carril_en(self, y):
        """el carril que pisa esa y, o None si está en una orilla."""
        if not TOP <= y < BOTTOM:
            return None
        return self.carriles[int((y - TOP) // LANE_H)]

    # --- movimiento --------------------------------------------------------
    def mover(self, dx, dy, ev):
        if self.over:
            return
        if dy:
            self.py = max(TOP - LANE_H, min(BOTTOM, self.py + dy * LANE_H))
        if dx:
            self.px = max(0, min(W - PW, self.px + dx * PASO_X))
        if self.py < TOP:                       # llegaste arriba
            self._cruzaste(ev)

    def _cruzaste(self, ev):
        x2 = CLIMAX_X if self.climax else 1
        ganado = CRUCE_VALE * self.mult() * x2
        self.score += ganado
        self.cruces += 1
        self.racha += 1
        self.vuelta_t = VUELTA_TTL
        ev.append(("cruce", self.px, TOP, ganado, self.mult() * x2))
        if self.cruces % VIDA_CADA == 0 and self.lives < VIDAS:
            self.lives += 1
            ev.append(("vida", self.lives))
        self.px = (W - PW) / 2
        self.py = BOTTOM                        # de vuelta abajo
        # tramo nuevo: lo que estaba en la calle se va con el viejo
        self.tramo, self.carriles = armar_tramo(self.cruces, self.rng)
        self.monedas = []
        self.items = []
        ev.append(("tramo", self.tramo, self.cruces))

    def _golpe(self, ev, x, y, causa="auto"):
        if self.gracia or self.over:
            return
        if self.escudo:
            # el escudo se lo come: te quedas donde estás, con un respiro
            self.escudo = False
            self.gracia = ESCUDO_GRACIA
            self.px = max(0, min(W - PW, self.px))
            ev.append(("escudo_roto", x, y, causa))
            return
        self.lives -= 1
        self.gracia = GRACIA
        self.racha = 0
        self.px = (W - PW) / 2
        self.py = BOTTOM
        ev.append(("golpe", x, y, self.lives, causa))
        if self.lives <= 0:
            self.over = True
            ev.append(("fin", x, y))

    # --- un frame ----------------------------------------------------------
    def step(self, dx, dy):
        ev = []
        if self.over:
            return ev
        # el reloj se descuenta ACÁ, antes que nada: ningún camino de salida
        # temprana puede regalar frames (una partida llegó a durar 7.341 de los
        # 5.400 que debía cuando estaba al final).
        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("aguantaste",))
            return ev
        if not self.climax and self.time <= CLIMAX_T:
            self.climax = True
            ev.append(("climax",))
        if self.gracia:
            self.gracia -= 1
        if self.hielo:
            self.hielo -= 1
            if not self.hielo:
                ev.append(("deshielo",))
        self.mover(dx, dy, ev)
        ritmo = self.ritmo_actual()
        for c in self.carriles:
            antes = c.aviso
            c.step(ritmo)
            if c.tipo == TREN and c.aviso and not antes:
                ev.append(("aviso_tren", c.i, c.v))
        self._semaforo()
        self._monedas(ev, ritmo)
        self._items(ev, ritmo)

        carril = self.carril_en(self.py)
        if carril is not None:
            if carril.tipo in (TRAFICO, TREN):
                if carril.toca(self.px + HOLGURA, PW - 2 * HOLGURA) is not None:
                    self._golpe(ev, self.px, self.py,
                                "tren" if carril.tipo == TREN else "auto")
                    return ev
            elif carril.tipo == CINTA:
                # la cinta te arrastra: si no estás sobre una, no pasa nada
                # malo (es piso firme), pero si estás, te lleva — y te puedes
                # caer del borde de la pantalla
                if carril.toca(self.px, PW) is not None:
                    self.px += carril.vel() * ritmo
                    if self.px < 0 or self.px > W - PW:
                        self._golpe(ev, max(0, min(W - PW, self.px)), self.py,
                                    "borde")
                        return ev
            elif carril.tipo == RIO:
                # el río al revés: lo que flota te salva, el agua no
                if carril.sostiene(self.px, PW) is None:
                    self._golpe(ev, self.px, self.py, "agua")
                    return ev
                self.px += carril.vel() * ritmo
                if self.px < 0 or self.px > W - PW:
                    self._golpe(ev, max(0, min(W - PW, self.px)), self.py,
                                "borde")
                    return ev

        if self.racha:
            self.vuelta_t -= 1
            if self.vuelta_t <= 0:
                self.racha = 0
                ev.append(("racha_fria", self.px, self.py))
        return ev

    def _viajar(self, c, x, ritmo):
        x += c.vel() * ritmo
        p = W + 2 * c.ancho
        if x > W + c.ancho:
            x -= p
        elif x < -c.ancho:
            x += p
        return x

    def _pisa(self, c, x):
        return self.carril_en(self.py) is c and not self.over and \
            x - 4 < self.px + PW and x + 4 > self.px

    def _monedas(self, ev, ritmo):
        """nacen entre dos autos, viajan con el carril, y se levantan pisándolas."""
        self.moneda_t -= 1
        if self.moneda_t <= 0 and len(self.monedas) < MONEDAS_MAX:
            self.moneda_t = MONEDA_GAP
            cands = [c for c in self.carriles if c.tipo == TRAFICO]
            if cands:
                c = self.rng.choice(cands)
                self.monedas.append([c.i, c.hueco_libre(self.rng), MONEDA_TTL])
        quedan = []
        for m in self.monedas:
            c = self.carriles[m[0]]
            m[1] = self._viajar(c, m[1], ritmo)
            m[2] -= 1
            if m[2] <= 0:
                continue
            if self._pisa(c, m[1]):
                ganado = MONEDA_VALE * self.mult()
                self.score += ganado
                self.monedas_tomadas += 1
                ev.append(("moneda", m[1], c.y, ganado))
                continue
            quedan.append(m)
        self.monedas = quedan

    def _items(self, ev, ritmo):
        """escudo y reloj: en la vereda si el tramo tiene, si no en el tráfico."""
        if not self.items:
            self.item_t -= 1
            if self.item_t <= 0:
                self.item_t = ITEM_GAP
                cands = [c for c in self.carriles if c.tipo == VEREDA] or \
                    [c for c in self.carriles if c.tipo == TRAFICO]
                if cands:
                    c = self.rng.choice(cands)
                    tipo = HIELO if self.escudo else self.rng.choice((ESCUDO, HIELO))
                    self.items.append([c.i, c.hueco_libre(self.rng), ITEM_TTL,
                                       tipo])
        quedan = []
        for it in self.items:
            c = self.carriles[it[0]]
            it[1] = self._viajar(c, it[1], ritmo)
            it[2] -= 1
            if it[2] <= 0:
                continue
            if self._pisa(c, it[1]):
                self.score += ITEM_VALE
                if it[3] == ESCUDO:
                    self.escudo = True
                else:
                    self.hielo = HIELO_TTL
                ev.append(("item", it[1], c.y, it[3]))
                continue
            quedan.append(it)
        self.items = quedan

    def _semaforo(self):
        self.sem_t -= 1
        if self.sem_t <= 0:
            self.sem_t = SEMAFORO_GAP
            candidatos = [c for c in self.carriles
                          if c.tipo == TRAFICO and not c.rojo]
            if candidatos:
                self.rng.choice(candidatos).rojo = SEMAFORO_TTL


# --- la piel -----------------------------------------------------------------
class World:
    def __init__(self):
        self.c = Cruce()
        self.fx = Fx(gravity=0.1, max_parts=220, sombra=SHADOW)
        # la posición dibujada persigue a la lógica: el salto se ve, no se
        # teletransporta. la lógica sigue siendo de a carriles enteros.
        self.vx, self.vy = self.c.px, self.c.py
        self.salto = 0               # frames desde el último salto
        self.mira = (0, -1)          # para dónde miran los ojos
        self.fiesta = 0              # el festejo arriba, tras cruzar
        self.fiesta_x = 0
        self.telon = 0               # la cortina del tramo nuevo
        self.carteles = []           # [texto, sub, col, vida, vida0, k]
        self.cartel_cruce = ("", 1)
        self.touch = web.is_touch()
        self._cartel("BARRIO", "cruce 1", ACCENT, vida=70)

    @property
    def over(self):
        return self.c.over

    @property
    def score(self):
        return self.c.score

    def _cartel(self, s, sub=None, col=GOLD, vida=60, k=3):
        self.carteles = [[s, sub, col, vida, vida, k]]

    def update(self):
        c = self.c
        dx = (1 if pyxel.btnp(pyxel.KEY_RIGHT, 10, 4) or
              pyxel.btnp(pyxel.KEY_D, 10, 4) else 0) \
            - (1 if pyxel.btnp(pyxel.KEY_LEFT, 10, 4) or
               pyxel.btnp(pyxel.KEY_A, 10, 4) else 0)
        dy = (1 if pyxel.btnp(pyxel.KEY_DOWN, 12, 6) or
              pyxel.btnp(pyxel.KEY_S, 12, 6) else 0) \
            - (1 if pyxel.btnp(pyxel.KEY_UP, 12, 6) or
               pyxel.btnp(pyxel.KEY_W, 12, 6) else 0)
        if dy:
            dx = 0               # un salto por vez: el swipe en diagonal no se duplica
        if dy or dx:
            self.salto = 0
            self.mira = (dx, dy)
        self.salto += 1
        for ev in c.step(dx, dy):
            self._efecto(ev)
        # el tween: si la lógica saltó lejos (cruce, golpe), la vista también.
        # rápido: la colisión es la de la lógica, y lo que se ve no puede
        # quedarse atrás de ella.
        if abs(c.py - self.vy) > LANE_H * 2 or abs(c.px - self.vx) > 40:
            self.vx, self.vy = c.px, c.py
        else:
            self.vx += (c.px - self.vx) * 0.6
            self.vy += (c.py - self.vy) * 0.6
        self.fiesta = max(0, self.fiesta - 1)
        self.telon = max(0, self.telon - 1)
        for k in self.carteles:
            k[3] -= 1
        self.carteles = [k for k in self.carteles if k[3] > 0]
        if c.climax and c.time % 60 == 0 and c.time <= 5 * 60:
            self.fx.destello(PINK, 3)
        self.fx.update()

    def _efecto(self, ev):
        k = ev[0]
        c = self.c
        if k == "cruce":
            _, x, y, ganado, mult = ev
            self.fx.burst(x + PW / 2, TOP - 4, CONFETI, n=40, speed=2.6,
                          life=40, angle=-1.5708, spread=2.6, gravity=0.08)
            self.fx.burst(W / 2, TOP - 4, CONFETI, n=20, speed=2.0, life=36,
                          angle=-1.5708, spread=3.0, gravity=0.08)
            self.fx.shake(3)
            self.fx.destello(NEON, 5)
            self.fiesta = 34
            self.fiesta_x = x
            self.cartel_cruce = ("+%d" % ganado, mult)
        elif k == "tramo":
            nombre, n = ev[1], ev[2]
            ganado, mult = self.cartel_cruce
            sub = "x%d · cruce %d: %s" % (mult, n + 1, nombre.lower()) if mult > 1 \
                else "cruce %d: %s" % (n + 1, nombre.lower())
            self._cartel(ganado, sub, GOLD, vida=70)
            self.telon = 16
        elif k == "golpe":
            causa = ev[4] if len(ev) > 4 else "auto"
            if causa == "agua":
                self.fx.burst(ev[1] + PW / 2, ev[2] + 6, CHISPA_AGUA, n=30,
                              speed=2.2, life=30, angle=-1.5708, spread=2.4,
                              gravity=0.15)
                self.fx.popup(ev[1] + PW / 2, ev[2] - 8, "¡SPLASH!", ESPUMA)
            elif causa == "tren":
                self.fx.burst(ev[1] + PW / 2, ev[2] + 6, CHISPA_GOLPE, n=40,
                              speed=3.4, life=36)
                self.fx.popup(ev[1] + PW / 2, ev[2] - 8, "¡TREN!", WARN)
            elif causa == "borde":
                self.fx.burst(ev[1] + PW / 2, ev[2] + 6, CHISPA_GOLPE, n=24,
                              speed=2.4, life=30)
                self.fx.popup(ev[1] + PW / 2, ev[2] - 8, "¡AL BORDE!", WARN)
            else:
                self.fx.burst(ev[1] + PW / 2, ev[2] + 6, CHISPA_GOLPE, n=30,
                              speed=2.6, life=32)
                self.fx.popup(ev[1] + PW / 2, ev[2] - 8, "¡PLAF!", WARN)
            self.fx.shake(7)
            self.fx.destello(WARN, 5)
            if ev[3] > 0:
                self._cartel("%d %s" % (ev[3], "VIDA" if ev[3] == 1 else "VIDAS"),
                             None, WARN, vida=45, k=2)
        elif k == "vida":
            self.fx.popup(124, HUD + 6, "¡VIDA EXTRA!", ROJO, life=60, vy=-0.1)
            self.fx.burst(124, 8, (WHITE, ROJO, PINK), n=16, speed=1.6, life=20,
                          gravity=0.0)
        elif k == "escudo_roto":
            self.fx.burst(ev[1] + PW / 2, ev[2] + 6, (WHITE, SHIELD, CINTA1),
                          n=28, speed=2.4, life=26)
            self.fx.popup(ev[1] + PW / 2, ev[2] - 8, "¡SALVADO!", SHIELD)
            self.fx.shake(4)
        elif k == "moneda":
            _, x, y, ganado = ev
            self.fx.burst(x, y + LANE_H / 2, (WHITE, GOLD, PINK, ROAD2), n=12,
                          speed=1.6, life=20)
            self.fx.popup(x, y - 4, "+%d" % ganado, GOLD)
        elif k == "item":
            _, x, y, tipo = ev
            col = SHIELD if tipo == ESCUDO else HIELOC
            self.fx.burst(x, y + LANE_H / 2, (WHITE, col, CINTA1), n=18,
                          speed=1.8, life=22)
            if tipo == ESCUDO:
                self.fx.popup(x, y - 6, "¡ESCUDO!", SHIELD)
            else:
                self._cartel("¡TIEMPO QUIETO!", "el tráfico se congela", HIELOC,
                             vida=50, k=2)
                self.fx.destello(HIELOC, 5)
        elif k == "aviso_tren":
            self.fx.shake(1)
        elif k == "racha_fria":
            self.fx.popup(ev[1], ev[2] - 10, "racha fría", DIM)
        elif k == "climax":
            self._cartel("¡HORA PUNTA!", "cada cruce vale doble", PINK, vida=90,
                         k=2)
            self.fx.destello(PINK, 6)
            self.fx.shake(3)
        elif k == "aguantaste":
            self._cartel("¡SE ACABÓ!", None, ACCENT, vida=120)

    # --- dibujo ------------------------------------------------------------
    def draw(self):
        c = self.c
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        self._meta()
        fondo = FONDO.get(c.tramo, ROAD2)
        for carril in c.carriles:
            self._carril(carril, fondo)
        self._orilla()
        for ci, mx, ttl in c.monedas:
            self._moneda(int(mx), c.carriles[ci].y, ttl)
        for ci, mx, ttl, tipo in c.items:
            self._item(int(mx), c.carriles[ci].y, ttl, tipo)
        if self.fiesta:
            self._festejo()
        self._jugador(c)
        self.fx.draw(0, 0)
        pyxel.camera()
        if self.telon:
            self._cortina()
        if c.hielo:
            self._escarcha()
        self._carteles()
        self.fx.draw_flash(0, HUD, W, H - HUD)
        if c.climax:
            col = PINK if (pyxel.frame_count // 8) % 2 else GOLD
            pyxel.rectb(0, HUD, W, H - HUD, col)
        self._hud()

    def _meta(self):
        c = self.c
        y = TOP - LANE_H
        pyxel.rect(0, y, W, LANE_H, ROAD1)
        # la llegada: una bandera a cuadros, que se lee como llegada
        a, b = (GOLD, PINK) if c.climax else (WHITE, SHADOW)
        for x in range(0, W, 4):
            for j in range(3):
                col = a if ((x // 4) + j) % 2 else b
                pyxel.rect(x, y + 3 + j * 3, 4, 3, col)
        pyxel.rect(0, TOP - 2, W, 2, META)

    def _orilla(self):
        c = self.c
        pyxel.rect(0, BOTTOM, W, H - BOTTOM, VEREDAC)
        for x in range(0, W, 16):
            pyxel.rect(x, BOTTOM + 2, 1, H - BOTTOM - 2, VEREDA2)
        pyxel.rect(0, BOTTOM, W, 2, EDGE)
        t = "cruce %d · %s" % (c.cruces + 1, c.tramo.lower())
        text(4, H - 8, t, TXT)
        r = c.ritmo()
        if r > 1.0:
            s = "ritmo %.1fx" % r
            text(W - len(s) * 4 - 4, H - 8, s, WARN if r >= RITMO_MAX else DIM)

    def _carril(self, carril, fondo):
        y = carril.y
        t = carril.tipo
        if t == TRAFICO:
            pyxel.rect(0, y, W, LANE_H, fondo)
            for x in range(0, W, 12):           # la línea del asfalto
                pyxel.rect(x, y + LANE_H - 1, 6, 1, ROAD1)
            if carril.rojo:                      # semáforo: se ve que está quieto
                col = ROJO if (pyxel.frame_count // 6) % 2 else GOLD
                pyxel.rect(0, y, 3, LANE_H, col)
                pyxel.rect(W - 3, y, 3, LANE_H, col)
            else:
                self._flechas(carril, y)
            for x in carril.cosas:
                self._vehiculo(int(x), y, carril)
        elif t == CINTA:
            pyxel.rect(0, y, W, LANE_H, BG)
            for x in carril.cosas:
                self._cinta(int(x), y, carril)
        elif t == RIO:
            pyxel.rect(0, y, W, LANE_H, AGUA1)
            off = (pyxel.frame_count // 4 + carril.i * 5) % 16
            for x in range(-16, W, 16):
                pyxel.rect(x + off, y + 4 + (x // 16) % 2 * 5, 5, 1, AGUA2)
            for k, x in enumerate(carril.cosas):
                self._tronco(int(x), y, carril, k)
        elif t == VEREDA:
            pyxel.rect(0, y, W, LANE_H, VEREDAC)
            pyxel.rect(0, y, W, 1, VEREDA2)
            pyxel.rect(0, y + LANE_H - 1, W, 1, VEREDA2)
            for x in range(0, W, 16):
                pyxel.rect(x, y + 1, 1, LANE_H - 2, VEREDA2)
        elif t == TREN:
            self._via(carril, y)

    def _flechas(self, carril, y):
        """de qué lado entra y cuán rápido: chevrons en el borde de entrada."""
        v = carril.vel()
        col = WARN if abs(v) > 1.25 else DIM
        cy = y + LANE_H // 2
        if v > 0:
            for i in range(2):
                x = 2 + i * 4
                pyxel.line(x, cy - 2, x + 2, cy, col)
                pyxel.line(x + 2, cy, x, cy + 2, col)
        elif v < 0:
            for i in range(2):
                x = W - 4 - i * 4
                pyxel.line(x, cy - 2, x - 2, cy, col)
                pyxel.line(x - 2, cy, x, cy + 2, col)

    def _via(self, carril, y):
        pyxel.rect(0, y, W, LANE_H, ROAD_VIA)
        for x in range(0, W, 6):
            pyxel.rect(x, y + 2, 3, LANE_H - 4, DURMIENTE)
        pyxel.rect(0, y + 4, W, 1, RIEL)
        pyxel.rect(0, y + LANE_H - 5, W, 1, RIEL)
        if carril.aviso:
            on = (pyxel.frame_count // 5) % 2
            # la vía entera se pone roja a golpes: no se te pasa ni en una
            # pantalla chica
            if on:
                pyxel.dither(0.45)
                pyxel.rect(0, y, W, LANE_H, ROJO)
                pyxel.dither(1.0)
            pyxel.rect(0, y, W, 1, ROJO if on else GOLD)
            pyxel.rect(0, y + LANE_H - 1, W, 1, ROJO if on else GOLD)
            # las barreras: luces rojas que se alternan en los dos extremos
            for bx in (1, W - 7):
                pyxel.rect(bx, y + 2, 6, 10, SHADOW)
                pyxel.rect(bx + 1, y + 3, 4, 3, ROJO if on else TRENDK)
                pyxel.rect(bx + 1, y + 8, 4, 3, TRENDK if on else ROJO)
            # de dónde viene: flecha y cartel del lado por el que entra
            d = 1 if carril.v > 0 else -1
            ax = 10 if d > 0 else W - 11
            pyxel.tri(ax, y + 2, ax, y + LANE_H - 3, ax + 5 * d,
                      y + LANE_H // 2, WHITE if on else ROJO)
            tx = 18 if d > 0 else W - 18 - 6 * 4
            pyxel.rect(tx - 2, y + 3, 6 * 4 + 3, 8, SHADOW)
            big(tx, y + 4, "¡TREN!", WHITE if on else GOLD, k=1)
        for x in carril.cosas:
            self._tren(int(x), y, carril)

    def _tren(self, x, y, carril):
        w = carril.ancho
        pyxel.rect(x, y + 1, w, LANE_H - 2, TRENC)
        pyxel.rect(x, y + 1, w, 1, WHITE)
        pyxel.rect(x, y + LANE_H - 3, w, 2, TRENDK)
        for wx in range(x + 6, x + w - 6, 10):        # las ventanas
            pyxel.rect(wx, y + 4, 6, 3, VIDRIO)
        for sx in range(x + 30, x + w, 30):           # los vagones
            pyxel.rect(sx, y + 1, 1, LANE_H - 2, TRENDK)
        # la trompa, en rojo, con el faro
        if carril.v > 0:
            pyxel.rect(x + w - 6, y + 1, 6, LANE_H - 2, ROJO)
            pyxel.rect(x + w - 2, y + 5, 2, 3, LUZ)
        else:
            pyxel.rect(x, y + 1, 6, LANE_H - 2, ROJO)
            pyxel.rect(x, y + 5, 2, 3, LUZ)

    def _vehiculo(self, x, y, carril):
        w = carril.ancho
        der = carril.v > 0
        veh = carril.vehiculo
        if veh == MOTO:
            col = MOTOC
            pyxel.rect(x, y + 6, w, 4, col)
            pyxel.rect(x + 3, y + 3, 4, 4, WHITE if der else WHITE)   # el piloto
            pyxel.pset(x + (5 if der else 4), y + 3, SHADOW)
            pyxel.rect(x, y + 10, 2, 2, SHADOW)
            pyxel.rect(x + w - 2, y + 10, 2, 2, SHADOW)
            # la estela del acelerón
            if carril.factor() > 1.25:
                sx = x - 6 if der else x + w + 1
                pyxel.rect(sx, y + 7, 5, 1, GOLD)
                pyxel.rect(sx + (2 if der else 0), y + 9, 3, 1, WARN)
            fx_ = x + w if der else x - 1
            pyxel.pset(fx_, y + 7, LUZ)
            return
        if veh == CAMION:
            cab = 9
            cx = x + w - cab if der else x
            tx = x if der else x + cab + 1
            pyxel.rect(tx, y + 1, w - cab - 1, LANE_H - 3, TRENC)
            pyxel.rect(tx, y + 1, w - cab - 1, 1, WHITE)
            pyxel.rect(tx + 2, y + 5, w - cab - 5, 1, TRENDK)
            pyxel.rect(cx, y + 3, cab, LANE_H - 5, TRUCK)
            pyxel.rect(cx + (5 if der else 1), y + 4, 3, 3, VIDRIO)
            col_luz = cx + cab - 1 if der else cx
            pyxel.rect(col_luz, y + 8, 1, 2, LUZ)
        elif veh == BUS:
            pyxel.rect(x, y + 1, w, LANE_H - 3, BUSC)
            pyxel.rect(x, y + 1, w, 1, WHITE)
            for wx in range(x + 3, x + w - 4, 6):
                pyxel.rect(wx, y + 3, 4, 3, VIDRIO)
            fr = x + w - 2 if der else x
            pyxel.rect(fr, y + 7, 2, 2, LUZ)
        else:
            col = (CAR1, CAR2, CAR3, PINK)[(carril.i + int(w)) % 4]
            pyxel.rect(x, y + 3, w, LANE_H - 6, col)
            pyxel.rect(x + 3, y + 2, w - 6, 2, col)
            pyxel.rect(x + 3, y + 2, w - 6, 1, WHITE)
            # el parabrisas mira hacia adelante
            pyxel.rect(x + w - 7 if der else x + 4, y + 4, 3, 3, VIDRIO)
            fr = x + w - 1 if der else x
            pyxel.rect(fr, y + 4, 1, 2, LUZ)
            tr = x if der else x + w - 1
            pyxel.rect(tr, y + 7, 1, 2, ROJO)
        # las ruedas
        pyxel.rect(x + 2, y + LANE_H - 3, 3, 2, SHADOW)
        pyxel.rect(x + w - 5, y + LANE_H - 3, 3, 2, SHADOW)
        # el haz de los faros, delante: dice para dónde va sin mirar el resto
        if der:
            pyxel.rect(x + w, y + 4, 3, 1, LINEA)
        else:
            pyxel.rect(x - 3, y + 4, 3, 1, LINEA)

    def _cinta(self, x, y, carril):
        w = carril.ancho
        pyxel.rect(x, y + 1, w, LANE_H - 2, CINTA1)
        pyxel.rect(x, y + 1, w, 1, CINTA2)
        pyxel.rect(x, y + LANE_H - 2, w, 1, SHADOW)
        # flechas que muestran para dónde te lleva
        d = 1 if carril.v > 0 else -1
        off = (pyxel.frame_count // 2) % 8
        cy = y + LANE_H // 2
        for i in range(4, w - 4, 8):
            fx_ = x + 4 + (i + off * d) % max(1, w - 8)
            pyxel.pset(fx_, cy, CINTA2)
            pyxel.pset(fx_ - d, cy - 1, CINTA2)
            pyxel.pset(fx_ - d, cy + 1, CINTA2)

    def _tronco(self, x, y, carril, k):
        e = carril.estado_tronco(k)
        w = carril.ancho
        if e == 2:                                    # abajo: sólo burbujas
            if (pyxel.frame_count // 6 + k) % 2:
                for bx in range(x + 4, x + w - 2, 9):
                    pyxel.pset(bx, y + 6, ESPUMA)
            return
        if e == 1 and (pyxel.frame_count // 4) % 2:
            c1, c2 = TRONCODK, TRONCO                # avisando: titila y baja
            dy = 1
        else:
            c1, c2 = TRONCO, TRONCOHI
            dy = 0
        pyxel.rect(x, y + 2 + dy, w, LANE_H - 4 - dy, c1)
        pyxel.rect(x, y + 2 + dy, w, 1, c2)
        for gx in range(x + 6, x + w - 4, 10):
            pyxel.rect(gx, y + 6 + dy, 4, 1, TRONCODK)
        pyxel.rect(x, y + 3 + dy, 2, LANE_H - 6 - dy, TRONCOHI)
        pyxel.rect(x + w - 2, y + 3 + dy, 2, LANE_H - 6 - dy, TRONCOHI)
        pyxel.rect(x - 1, y + LANE_H - 3, w + 2, 1, ESPUMA if dy else AGUA2)

    def _moneda(self, x, y, ttl):
        if ttl < 90 and (pyxel.frame_count // 4) % 2:
            return
        cy = y + LANE_H // 2
        w = (3, 2, 1, 2)[(pyxel.frame_count // 5) % 4]      # gira sobre su eje
        pyxel.rect(x - w, cy - 3, w * 2, 6, GOLD)
        pyxel.rect(x - w, cy - 3, w * 2, 1, WHITE)
        if w > 1:
            pyxel.pset(x, cy, PINK)

    def _item(self, x, y, ttl, tipo):
        if ttl < 90 and (pyxel.frame_count // 4) % 2:
            return
        cy = y + LANE_H // 2 + (1 if (pyxel.frame_count // 10) % 2 else 0)
        pyxel.rect(x - 6, cy - 6, 12, 12, SHADOW)
        if tipo == ESCUDO:
            pyxel.rectb(x - 6, cy - 6, 12, 12, SHIELD)
            pyxel.rect(x - 3, cy - 4, 6, 5, SHIELD)
            pyxel.rect(x - 2, cy + 1, 4, 2, SHIELD)
            pyxel.pset(x - 1, cy + 3, SHIELD)
            pyxel.pset(x, cy + 3, SHIELD)
            pyxel.rect(x - 2, cy - 3, 1, 3, WHITE)
        else:
            pyxel.rectb(x - 6, cy - 6, 12, 12, HIELOC)
            pyxel.circb(x, cy, 4, HIELOC)
            pyxel.line(x, cy, x, cy - 3, WHITE)
            pyxel.line(x, cy, x + 2, cy, WHITE)

    def _sprite(self, x, y, col, ancho, alto, mira=(0, -1)):
        """el que cruza: un bicho cuadrado con ojos, de ancho×alto."""
        pyxel.rect(x, y, ancho, alto, col)
        pyxel.rectb(x, y, ancho, alto, WHITE)      # contorno: hay que verlo
        pyxel.rect(x + 1, y + 1, ancho - 2, 1, PLAYER2)
        ex = x + ancho // 2 - 3 + mira[0]
        ey = y + 3 + (1 if mira[1] > 0 else 0)
        pyxel.rect(ex, ey, 2, 2, BG)               # los ojos
        pyxel.rect(ex + 4, ey, 2, 2, BG)
        pyxel.pset(ex, ey, WHITE)
        pyxel.pset(ex + 4, ey, WHITE)

    def _jugador(self, c):
        if c.gracia and (pyxel.frame_count // 4) % 2:
            return
        x, y = int(self.vx), int(self.vy)
        # squash & stretch: arranca estirado, vuela, aterriza aplastado
        s = self.salto
        if s <= 2:
            aw, ah, lift = PW - 2, PH + 1, 3
        elif s <= 5:
            aw, ah, lift = PW - 1, PH - 1, 4 - (s - 3)
        elif s <= 8:
            aw, ah, lift = PW + 2, PH - 3, 0
        else:
            aw, ah, lift = PW, PH - 1, 0
        cx = x + PW // 2
        base = y + LANE_H - 2
        # la sombra en el piso: dice dónde vas a caer
        pyxel.rect(cx - 4, base - 1, 8, 2, SHADOW)
        sx, sy = cx - aw // 2, base - ah - lift
        col = PLAYER2 if s <= 5 else PLAYER
        self._sprite(sx, sy, col, aw, ah, self.mira)
        if c.escudo:                               # la burbuja del escudo
            r = 9 + (pyxel.frame_count // 8) % 2
            pyxel.circb(cx, sy + ah // 2, r, SHIELD)

    def _festejo(self):
        """el que llegó salta arriba, festejando, mientras el nuevo arranca abajo."""
        f = 34 - self.fiesta
        hop = abs(math.sin(f * 0.35)) * 6
        x = int(self.fiesta_x)
        y = int(TOP - LANE_H + 1 - hop)
        if (f // 3) % 2 == 0:
            self._sprite(x, y, GOLD, PW, PH - 1, (0, -1))
        else:
            self._sprite(x - 1, y + 1, GOLD, PW + 2, PH - 2, (0, -1))

    def _cortina(self):
        """el tramo nuevo entra de arriba hacia abajo: una franja que barre."""
        f = 16 - self.telon
        yl = TOP - LANE_H + int((BOTTOM - TOP + LANE_H) * f / 16)
        pyxel.dither(0.7)
        pyxel.rect(0, yl, W, BOTTOM - yl, SHADOW)
        pyxel.dither(1.0)
        pyxel.rect(0, yl, W, 2, NEON)

    def _escarcha(self):
        """el congelado: bordes de hielo y copos que caen despacio. nada de
        teñir la pantalla entera: con dither se ve sucio y no se lee."""
        c = self.c
        if c.hielo < 60 and (pyxel.frame_count // 4) % 2:
            return
        pyxel.rect(0, TOP, 2, BOTTOM - TOP, HIELOC)
        pyxel.rect(W - 2, TOP, 2, BOTTOM - TOP, HIELOC)
        pyxel.rect(0, TOP, W, 1, HIELOC)
        pyxel.rect(0, BOTTOM - 1, W, 1, HIELOC)
        t = pyxel.frame_count
        for i in range(14):
            x = (i * 53 + t // 3) % W
            y = TOP + (i * 37 + t // 2) % (BOTTOM - TOP)
            pyxel.pset(x, y, WHITE)
            pyxel.pset(x + 1, y, HIELOC)
            pyxel.pset(x - 1, y, HIELOC)

    def _carteles(self):
        for s, sub, col, vida, vida0, k in self.carteles:
            if vida < vida0 * 0.3 and (vida // 3) % 2:
                continue
            kk = k + 1 if vida > vida0 - 5 else k
            y = TOP + 8
            cbig(W // 2, y, s, col, k=kk, sombra=SHADOW)
            if sub:
                yy = y + 6 * kk + 3
                w = len(sub) * 4 + 6
                pyxel.rect(W // 2 - w // 2, yy - 2, w, 9, SHADOW)
                ctext(W // 2, yy, sub, WHITE)

    def _hud(self):
        c = self.c
        pyxel.rect(0, 0, W, HUD, HUDC)
        pyxel.rect(0, HUD - 1, W, 1, PINK if c.climax else EDGE)
        # el puntaje, grande
        big(3, 3, "%d" % c.score, ACCENT, k=2)
        # el multiplicador, grande, con la barra de lo que le queda a la racha
        m = c.mult() * (CLIMAX_X if c.climax else 1)
        x = 62
        if m > 1:
            col = GOLD if (pyxel.frame_count // 6) % 2 else PINK
            big(x, 3, "x%d" % m, col, k=2)
            if c.racha:
                bw = 20
                pyxel.rect(x + 22, 7, bw, 4, ROAD1)
                pyxel.rect(x + 22, 7, max(1, int(bw * c.vuelta_t / VUELTA_TTL)),
                           4, PINK)
        # las vidas: corazones
        hx = 112
        for i in range(VIDAS):
            self._corazon(hx + i * 10, 4, ROJO if i < c.lives else ROAD1)
        # lo que tienes encima: escudo y congelado
        ix = 146
        if c.escudo:
            pyxel.rect(ix, 3, 7, 6, SHIELD)
            pyxel.rect(ix + 1, 9, 5, 2, SHIELD)
            pyxel.rect(ix + 3, 11, 1, 1, SHIELD)
            ix += 11
        if c.hielo:
            pyxel.circb(ix + 4, 7, 4, HIELOC)
            pyxel.line(ix + 4, 7, ix + 4, 4, WHITE)
            text(ix + 10, 5, "%d" % (c.hielo // 60 + 1), HIELOC)
        # cruces
        cr = "%d" % c.cruces
        text(176, 2, "cruces", DIM)
        text(176 + 12 - len(cr) * 2, 9, cr, TXT)
        # el reloj
        s = c.time // 60
        col = WHITE
        if s <= 10:
            col = WARN if pyxel.frame_count % 30 < 15 else WHITE
        rs = "%d" % s
        big(W - len(rs) * 8 - 2, 3, rs, col, k=2)

    @staticmethod
    def _corazon(x, y, col):
        pyxel.rect(x, y + 1, 7, 3, col)
        pyxel.rect(x + 1, y, 2, 1, col)
        pyxel.rect(x + 4, y, 2, 1, col)
        pyxel.rect(x + 1, y + 4, 5, 1, col)
        pyxel.rect(x + 2, y + 5, 3, 1, col)
        pyxel.pset(x + 3, y + 6, col)


class Game:
    def __init__(self):
        touch = web.is_touch()
        Cabinet(
            game_id="cruzar", title="CRUZAR", subtitle="90 segundos de ida y vuelta",
            howto=["desliza o usa la cruceta para saltar" if touch else
                   "flechas o wasd saltan",
                   "abajo esquivas · arriba te arrastran",
                   "en el río, súbete a los troncos",
                   "cada cruce cambia el tramo y acelera"],
            width=W, height=H, palette=PAL, scale=3, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=ROAD2),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
