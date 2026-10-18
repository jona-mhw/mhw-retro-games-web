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

la pantalla es vertical (240x360), como el teléfono parado: caben 14 carriles
a la vista, de 20 px, y cada tramo se arma con secciones que se reconocen de
un vistazo (la plaza de las cintas, el río con su ribera, la vía con
durmientes, la avenida con su vereda al medio). el arte (paleta, sprites,
fondos horneados) vive en art.py.
"""
import math
import random

import pyxel

from pixelkit import scores, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import big_ctext, big_text, big_width, ctext, text

from . import art
from .art import *  # noqa: F401,F403  (los colores de la paleta)
from .grande import Fx

W, H = 240, 360
HUD = 28                         # el marcador de arriba
LANE_H = 20                      # alto de cada carril
LANES = 14                       # carriles entre la orilla de abajo y la meta
TOP = HUD + LANE_H               # la meta: la franja de arriba
BOTTOM = TOP + LANES * LANE_H    # la orilla de abajo, desde donde sales
BARRA = BOTTOM + LANE_H          # la barrita de abajo: tramo y ritmo

TIME = 90 * 60
VIDAS = 3
GRACIA = 90
PW, PH = 10, 11                  # el que cruza
PASO_X = 8                       # un toque al costado (un swipe = un paso que se ve)
HOLGURA = 2                      # el auto tiene que morderte de verdad

MULT_MAX = 5
VUELTA_TTL = 12 * 60             # tardar más que esto enfría la racha
# con 14 carriles cada cruce es un viaje más largo que con los 11 de antes:
# vale un cuarto más, así el puntaje por minuto queda en la misma escala
CRUCE_VALE = 125

TRAFICO, CINTA, RIO, TREN, VEREDA = range(5)
AUTO, CAMION, MOTO, BUS = range(4)   # qué anda por un carril de tráfico
SEMAFORO_GAP = 7 * 60
SEMAFORO_TTL = 3 * 60

# el ritmo: cada cruce acelera el tráfico un poco, con techo, para que el
# cruce 20 siga siendo cruzable.
RITMO_PASO = 0.05
RITMO_MAX = 1.6
VIDA_CADA = 3                    # cada 3 cruces, una vida de vuelta (sin pasar de 3)

# las monedas: nacen en un carril de tráfico, entre dos autos, y viajan con él.
MONEDA_GAP = 3 * 60
MONEDA_TTL = 9 * 60
MONEDA_VALE = 40
MONEDAS_MAX = 3

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

# los tramos: nombre y carriles de arriba hacia abajo (14 cada uno).
# C cinta · A río · V vereda · T autos · K camiones · B buses · M motos · F tren
# con la pantalla vertical cada tramo tiene secciones: arriba lo que cambia la
# lectura (cintas, río), una vereda para respirar, y el tráfico abajo.
TRAMOS = (
    ("BARRIO", "CCCVTKTTVBTKTT"),
    ("AVENIDA", "CCCVTMBTVTKTMT"),
    ("VÍA DEL TREN", "CCVTKFTVMFTVFT"),
    ("EL RÍO", "AAAVTMKTFVBTKT"),
    ("AUTOPISTA", "CAAVMKTBFVTMKM"),
)

CHISPA_CRUCE = (WHITE, ACCENT, PL1, CINTA1)
CHISPA_GOLPE = (WHITE, WARN, CAB1, ROJODK)
CHISPA_AGUA = (WHITE, ESPUMA, AGUA3, AGUA2)
CONFETI = (WHITE, GOLD, PINK, ACCENT, META)


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
def _sombra_txt(cx, y, s, col, k, sombra=SHADOW, d=1):
    """texto grande centrado con contorno (sombra a los cuatro lados y una
    honda abajo): sobre la calle se despega de todo."""
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (d + 1, d + 1)):
        big_ctext(cx + ox, y + oy, s, sombra, k)
    big_ctext(cx, y, s, col, k)


def _corazon(x, y, col, dk):
    pyxel.rect(x + 1, y, 2, 1, col)
    pyxel.rect(x + 4, y, 2, 1, col)
    pyxel.rect(x, y + 1, 7, 3, col)
    pyxel.rect(x + 1, y + 4, 5, 1, col)
    pyxel.rect(x + 2, y + 5, 3, 1, col)
    pyxel.pset(x + 3, y + 6, col)
    pyxel.rect(x + 4, y + 3, 2, 2, dk)
    pyxel.pset(x + 1, y + 1, WHITE)


def bicho(x, y, aw, ah, ramp, mira=(0, -1), pies=True):
    """el que cruza: un bicho cuadrado con ojos, contorno oscuro y volumen
    (luz arriba a la izquierda, sombra abajo a la derecha)."""
    c3, c2, c1, c0 = ramp
    pyxel.rect(x, y + 1, aw, ah - 2, OUT)            # contorno redondeado
    pyxel.rect(x + 1, y, aw - 2, ah, OUT)
    pyxel.rect(x + 1, y + 1, aw - 2, ah - 2, c1)
    pyxel.rect(x + 1, y + ah - 3, aw - 2, 2, c0)     # panza en sombra
    pyxel.rect(x + aw - 2, y + 2, 1, ah - 4, c0)
    pyxel.rect(x + 2, y + 1, aw - 4, 1, c2)          # luz
    pyxel.rect(x + 1, y + 2, 1, ah - 5, c2)
    pyxel.pset(x + 2, y + 2, c3)
    # los ojos: blancos con la pupila hacia donde salta
    ex = x + aw // 2 - 4
    ey = y + 2 + (1 if mira[1] > 0 else 0)
    for ox in (0, 5):
        pyxel.rect(ex + ox, ey, 3, 3, WHITE)
        px = ex + ox + 1 + mira[0]
        py = ey + 1 + (1 if mira[1] > 0 else (-1 if mira[1] < 0 else 0))
        pyxel.rect(px, max(ey, py), 2, 2, OUT)
    if pies:
        pyxel.rect(x + 1, y + ah, 3, 1, c0)
        pyxel.rect(x + aw - 4, y + ah, 3, 1, c0)


class World:
    def __init__(self):
        art.bake_sprites()
        self.c = Cruce()
        self.fx = Fx(gravity=0.1, max_parts=260, sombra=SHADOW)
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
        self.hud_golpe = 0
        self.touch = web.is_touch()
        self._fondo(todos=True)
        self._cartel("BARRIO", "cruce 1", ACCENT, vida=80)

    @property
    def over(self):
        return self.c.over

    @property
    def score(self):
        return self.c.score

    def _fondo(self, todos=False):
        if todos:                    # todos de una, antes de la cuenta: así
            for nombre, plano in TRAMOS:   # cruzar no hornea en plena partida
                art.bake_fondo(nombre, plano, W, H, HUD, TOP)
        plano = dict(TRAMOS)[self.c.tramo]
        self.bg = art.bake_fondo(self.c.tramo, plano, W, H, HUD, TOP)

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
        self.hud_golpe = max(0, self.hud_golpe - 1)
        for k in self.carteles:
            k[3] -= 1
        self.carteles = [k for k in self.carteles if k[3] > 0]
        if c.climax and c.time % 60 == 0 and c.time <= 5 * 60:
            self.fx.destello(PINK, 3)
        self.fx.update()

    def _efecto(self, ev):
        k = ev[0]
        if k == "cruce":
            _, x, y, ganado, mult = ev
            self.fx.burst(x + PW / 2, TOP - 6, CONFETI, n=44, speed=2.8,
                          life=44, angle=-1.5708, spread=2.6, gravity=0.08)
            self.fx.burst(W / 2, TOP - 6, CONFETI, n=24, speed=2.2, life=40,
                          angle=-1.5708, spread=3.0, gravity=0.08)
            self.fx.shake(3)
            self.fx.destello(ACCENT, 5)
            self.fiesta = 34
            self.fiesta_x = x
            self.cartel_cruce = ("+%d" % ganado, mult)
        elif k == "tramo":
            nombre, n = ev[1], ev[2]
            ganado, mult = self.cartel_cruce
            sub = "x%d · cruce %d: %s" % (mult, n + 1, nombre.lower()) if mult > 1 \
                else "cruce %d: %s" % (n + 1, nombre.lower())
            self._cartel(ganado, sub, GOLD, vida=75)
            self.telon = 18
            self._fondo()
        elif k == "golpe":
            causa = ev[4] if len(ev) > 4 else "auto"
            x, y = ev[1] + PW / 2, ev[2] + LANE_H / 2
            if causa == "agua":
                self.fx.burst(x, y, CHISPA_AGUA, n=34, speed=2.4, life=32,
                              angle=-1.5708, spread=2.4, gravity=0.15)
                self.fx.popup(x, y - 14, "¡SPLASH!", ESPUMA, life=44, k=2)
            elif causa == "tren":
                self.fx.burst(x, y, CHISPA_GOLPE, n=44, speed=3.6, life=38)
                self.fx.popup(x, y - 14, "¡TREN!", WARN, life=44, k=2)
            elif causa == "borde":
                self.fx.burst(x, y, CHISPA_GOLPE, n=26, speed=2.4, life=30)
                self.fx.popup(x, y - 14, "¡AL BORDE!", WARN, life=44, k=2)
            else:
                self.fx.burst(x, y, CHISPA_GOLPE, n=34, speed=2.8, life=34)
                self.fx.popup(x, y - 14, "¡PLAF!", WARN, life=44, k=2)
            self.fx.shake(7)
            self.fx.destello(WARN, 5)
            self.hud_golpe = 40
            if ev[3] > 0:
                self._cartel("%d %s" % (ev[3], "VIDA" if ev[3] == 1 else "VIDAS"),
                             None, WARN, vida=48, k=2)
        elif k == "vida":
            self.fx.popup(W / 2, HUD + 10, "¡VIDA EXTRA!", ROJO, life=60,
                          vy=-0.1, k=2)
            self.fx.burst(96, 10, (WHITE, ROJO, PINK), n=18, speed=1.6, life=22,
                          gravity=0.0)
        elif k == "escudo_roto":
            x, y = ev[1] + PW / 2, ev[2] + LANE_H / 2
            self.fx.burst(x, y, (WHITE, SHIELD, CINTA1), n=30, speed=2.4, life=26)
            self.fx.popup(x, y - 14, "¡SALVADO!", SHIELD, life=40, k=2)
            self.fx.shake(4)
        elif k == "moneda":
            _, x, y, ganado = ev
            self.fx.burst(x, y + LANE_H / 2, (WHITE, GOLDHI, GOLD, GOLDDK), n=14,
                          speed=1.7, life=22)
            self.fx.popup(x, y - 4, "+%d" % ganado, GOLD, k=2)
        elif k == "item":
            _, x, y, tipo = ev
            col = SHIELD if tipo == ESCUDO else HIELOC
            self.fx.burst(x, y + LANE_H / 2, (WHITE, col, CINTA1), n=20,
                          speed=1.9, life=24)
            if tipo == ESCUDO:
                self.fx.popup(x, y - 6, "¡ESCUDO!", SHIELD, k=2)
            else:
                self._cartel("¡TIEMPO QUIETO!", "el tráfico se congela", HIELOC,
                             vida=56, k=2)
                self.fx.destello(HIELOC, 5)
        elif k == "aviso_tren":
            self.fx.shake(1)
        elif k == "racha_fria":
            self.fx.popup(ev[1] + PW / 2, ev[2] - 6, "racha fría", DIM)
        elif k == "climax":
            self._cartel("¡HORA PUNTA!", "cada cruce vale doble", PINK, vida=96,
                         k=3)
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
        pyxel.blt(0, 0, self.bg, 0, 0, W, H)
        art.bandera(TOP - 9, W, c.climax)
        fc = pyxel.frame_count
        for carril in c.carriles:
            self._carril(carril, fc)
        for ci, mx, ttl in c.monedas:
            self._moneda(int(mx), c.carriles[ci].y, ttl, fc)
        for ci, mx, ttl, tipo in c.items:
            self._item(int(mx), c.carriles[ci].y, ttl, tipo, fc)
        if self.fiesta:
            self._festejo()
        self._jugador(c, fc)
        self.fx.draw(0, 0)
        pyxel.camera()
        if self.telon:
            self._cortina()
        if c.hielo:
            self._escarcha(fc)
        self._carteles()
        self.fx.draw_flash(0, HUD, W, BOTTOM + LANE_H - HUD)
        if c.climax:
            col = PINK if (fc // 8) % 2 else GOLD
            pyxel.rectb(0, HUD, W, BARRA - HUD, col)
            pyxel.rectb(1, HUD + 1, W - 2, BARRA - HUD - 2, PINKDK)
        self._hud(fc)
        self._barra()

    # los carriles --------------------------------------------------------
    def _carril(self, carril, fc):
        y = carril.y
        t = carril.tipo
        if t == TRAFICO:
            if carril.rojo:
                self._semaforo(y, fc)
            else:
                self._flechas(carril, y)
            self._vehiculos(carril, y)
        elif t == CINTA:
            k = int(fc * min(1.0, abs(carril.v)) * 0.5) % 4
            izq = carril.v < 0
            for x in carril.cosas:
                art.spr(("cinta", carril.ancho, k), int(x), y + 2, izq)
        elif t == RIO:
            art.agua(0, y, -carril.t * carril.v * 0.6, (fc // 20 + carril.i) % 2)
            for k, x in enumerate(carril.cosas):
                self._tronco(int(x), y, carril, k, fc)
        elif t == TREN:
            self._via(carril, y, fc)

    def _vehiculos(self, carril, y):
        der = carril.v > 0
        veh = carril.vehiculo
        w = carril.ancho
        for k, x in enumerate(carril.cosas):
            x = int(x)
            if veh == MOTO:
                art.spr(("moto", 11), x - 2 if der else x - 3, y + 4, not der)
                if carril.factor() > 1.25:           # la estela del acelerón
                    sx = x - 7 if der else x + w + 2
                    pyxel.rect(sx, y + 10, 5, 1, GOLD)
                    pyxel.rect(sx + (2 if der else 0), y + 12, 3, 1, WARN)
                continue
            if veh == CAMION:
                key = ("camion", w)
            elif veh == BUS:
                key = ("bus", w)
            else:
                key = ("auto", w, (carril.i * 3 + k) % len(art.AUTOS))
            art.spr(key, x if der else x - art.BEAM, y + 2, not der)

    def _flechas(self, carril, y):
        """de qué lado entra y cuán rápido: chevrons en el borde de entrada."""
        v = carril.vel()
        col = WARN if abs(v) > 1.25 else LINEA2
        cy = y + LANE_H // 2
        if v > 0:
            for i in range(2):
                x = 3 + i * 4
                pyxel.line(x, cy - 3, x + 3, cy, col)
                pyxel.line(x + 3, cy, x, cy + 3, col)
        elif v < 0:
            for i in range(2):
                x = W - 4 - i * 4
                pyxel.line(x, cy - 3, x - 3, cy, col)
                pyxel.line(x - 3, cy, x, cy + 3, col)

    def _semaforo(self, y, fc):
        """el carril en rojo: semáforos a los dos lados, que brillan."""
        on = (fc // 6) % 2
        for x in (1, W - 8):
            if on:
                pyxel.dither(0.3)
                pyxel.circ(x + 3, y + 7, 6, ROJO)
                pyxel.dither(1.0)
            pyxel.rect(x, y + 2, 7, 15, OUT)
            pyxel.rect(x + 1, y + 3, 5, 13, POSTE)
            pyxel.circ(x + 3, y + 6, 2, ROJO if on else ROJODK)
            pyxel.pset(x + 2, y + 5, WHITE if on else ROJO)
            pyxel.circ(x + 3, y + 12, 2, OUT)
        pyxel.dither(0.25)
        pyxel.rect(9, y + LANE_H - 2, W - 18, 1, ROJO)
        pyxel.dither(1.0)

    def _via(self, carril, y, fc):
        if carril.aviso:
            on = (fc // 5) % 2
            # la vía entera se pone roja a golpes: no se te pasa ni en una
            # pantalla chica
            if on:
                pyxel.dither(0.4)
                pyxel.rect(0, y, W, LANE_H, ROJO)
                pyxel.dither(1.0)
            pyxel.rect(0, y, W, 1, ROJO if on else GOLD)
            pyxel.rect(0, y + LANE_H - 1, W, 1, ROJO if on else GOLD)
            # las barreras: luces rojas que se alternan en los dos extremos
            for bx in (1, W - 9):
                pyxel.rect(bx, y + 2, 8, 16, OUT)
                for j, prende in ((0, on), (1, not on)):
                    cy = y + 6 + j * 8
                    if prende:
                        pyxel.dither(0.35)
                        pyxel.circ(bx + 4, cy, 6, ROJO)
                        pyxel.dither(1.0)
                    pyxel.circ(bx + 4, cy, 2, ROJO if prende else ROJODK)
                    if prende:
                        pyxel.pset(bx + 3, cy - 1, WHITE)
            # de dónde viene: flecha y cartel del lado por el que entra
            d = 1 if carril.v > 0 else -1
            ax = 12 if d > 0 else W - 13
            pyxel.tri(ax, y + 3, ax, y + LANE_H - 4, ax + 6 * d, y + LANE_H // 2,
                      WHITE if on else ROJO)
            s = "¡TREN!"
            tw = big_width(s, 2)
            tx = 22 if d > 0 else W - 22 - tw
            pyxel.rect(tx - 3, y + 3, tw + 5, 14, OUT)
            pyxel.rectb(tx - 3, y + 3, tw + 5, 14, ROJO if on else GOLD)
            big_text(tx, y + 5, s, WHITE if on else GOLD, 2)
        for x in carril.cosas:
            art.spr("tren", int(x), y + 1, carril.v < 0)

    def _tronco(self, x, y, carril, k, fc):
        e = carril.estado_tronco(k)
        w = carril.ancho
        if e == 2:                                    # abajo: la silueta y burbujas
            pyxel.rect(x + 3, y + 7, w - 6, 7, AGUA0)
            if (fc // 6 + k) % 2:
                for bx in range(x + 5, x + w - 3, 9):
                    pyxel.pset(bx, y + 8 + (bx // 9) % 3, ESPUMA)
            return
        bajo = 1 if e == 1 and (fc // 5) % 2 else 0  # avisando: titila y baja
        art.spr(("tronco", w, bajo), x, y + 1)
        if e == 1 and not bajo:
            pyxel.rect(x, y + 14, w, 1, ESPUMA)

    # monedas e ítems -----------------------------------------------------
    def _moneda(self, x, y, ttl, fc):
        if ttl < 90 and (fc // 4) % 2:
            return
        cy = y + LANE_H // 2
        w = (4, 3, 1, 3)[(fc // 5) % 4]              # gira sobre su eje
        pyxel.rect(x - 3, cy + 5, 7, 2, SOMBRA)
        pyxel.rect(x - w - 1, cy - 4, w * 2 + 2, 9, OUT)
        pyxel.rect(x - w, cy - 5, w * 2, 11, OUT)
        pyxel.rect(x - w, cy - 4, w * 2, 9, GOLD)
        pyxel.rect(x - w, cy + 2, w * 2, 2, GOLDDK)
        pyxel.rect(x - w, cy - 4, max(1, w), 2, GOLDHI)
        if w > 2:
            pyxel.rect(x - 1, cy - 2, 2, 4, GOLDDK)

    def _item(self, x, y, ttl, tipo, fc):
        if ttl < 90 and (fc // 4) % 2:
            return
        cy = y + LANE_H // 2 + (1 if (fc // 10) % 2 else 0)
        col = SHIELD if tipo == ESCUDO else HIELOC
        if (fc // 8) % 2:
            pyxel.dither(0.3)
            pyxel.circ(x, cy, 10, col)
            pyxel.dither(1.0)
        pyxel.rect(x - 7, cy + 6, 15, 2, SOMBRA)
        pyxel.rect(x - 7, cy - 7, 14, 14, OUT)
        pyxel.rect(x - 6, cy - 6, 12, 12, HUD2)
        pyxel.rectb(x - 7, cy - 7, 14, 14, col)
        if tipo == ESCUDO:
            pyxel.rect(x - 4, cy - 4, 8, 5, SHIELD)
            pyxel.rect(x - 3, cy + 1, 6, 2, SHIELD)
            pyxel.rect(x - 1, cy + 3, 2, 1, SHIELD)
            pyxel.rect(x - 3, cy - 3, 1, 4, WHITE)
            pyxel.rect(x + 1, cy - 2, 2, 4, CINTA1)
        else:
            pyxel.circ(x, cy, 4, HIELOC)
            pyxel.circb(x, cy, 4, CINTA1)
            pyxel.line(x, cy, x, cy - 3, OUT)
            pyxel.line(x, cy, x + 2, cy, OUT)
            pyxel.pset(x - 2, cy - 2, WHITE)

    # el que cruza --------------------------------------------------------
    def _jugador(self, c, fc):
        if c.gracia and (fc // 4) % 2:
            return
        x, y = int(self.vx), int(self.vy)
        # squash & stretch: arranca estirado, vuela, aterriza aplastado
        s = self.salto
        if s <= 2:
            aw, ah, lift = PW, PH + 3, 4
        elif s <= 5:
            aw, ah, lift = PW + 1, PH + 1, 5 - (s - 3)
        elif s <= 8:
            aw, ah, lift = PW + 5, PH - 1, 0
        else:
            aw, ah, lift = PW + 2, PH + 1, 0
        cx = x + PW // 2
        base = y + LANE_H - 3
        # la sombra en el piso: dice dónde vas a caer (se achica en el aire)
        sw = 10 - lift
        pyxel.rect(cx - sw // 2, base - 1, sw, 3, SOMBRA)
        pyxel.rect(cx - sw // 2 - 1, base, sw + 2, 1, SOMBRA)
        sx, sy = cx - aw // 2, base - ah - lift
        ramp = (PL3, PL3, PL2, PL1) if s <= 5 else (PL3, PL2, PL1, PL0)
        bicho(sx, sy, aw, ah, ramp, self.mira, pies=lift == 0)
        if c.escudo:                                 # la burbuja del escudo
            r = 10 + (fc // 8) % 2
            pyxel.circb(cx, sy + ah // 2, r, SHIELD)
            pyxel.pset(cx - 5, sy - 1, WHITE)
            pyxel.pset(cx - 6, sy, WHITE)

    def _festejo(self):
        """el que llegó salta arriba, festejando, mientras el nuevo arranca abajo."""
        f = 34 - self.fiesta
        hop = abs(math.sin(f * 0.35)) * 7
        x = int(self.fiesta_x)
        y = int(TOP - LANE_H + 3 - hop)
        ramp = (GOLDHI, GOLDHI, GOLD, GOLDDK)
        if (f // 3) % 2 == 0:
            bicho(x, y, PW + 2, PH + 1, ramp, (0, -1))
        else:
            bicho(x - 1, y + 1, PW + 4, PH, ramp, (0, -1))

    # capas de arriba ------------------------------------------------------
    def _cortina(self):
        """el tramo nuevo entra de arriba hacia abajo: una franja que barre."""
        f = 18 - self.telon
        yl = HUD + int((BOTTOM + LANE_H - HUD) * f / 18)
        pyxel.dither(0.7)
        pyxel.rect(0, yl, W, BOTTOM + LANE_H - yl, SHADOW)
        pyxel.dither(1.0)
        pyxel.rect(0, yl, W, 2, ACCENT)
        pyxel.rect(0, yl + 2, W, 1, CINTA1)

    def _escarcha(self, fc):
        """el congelado: bordes de hielo y copos que caen despacio."""
        c = self.c
        if c.hielo < 60 and (fc // 4) % 2:
            return
        y0, y1 = TOP, BOTTOM
        pyxel.rect(0, y0, 3, y1 - y0, HIELOC)
        pyxel.rect(W - 3, y0, 3, y1 - y0, HIELOC)
        pyxel.rect(3, y0, 1, y1 - y0, CINTA1)
        pyxel.rect(W - 4, y0, 1, y1 - y0, CINTA1)
        for k in range(0, y1 - y0, 23):               # cristales en el borde
            yy = y0 + k + 6
            pyxel.tri(3, yy - 4, 3, yy + 4, 8, yy, HIELOC)
            pyxel.tri(W - 4, yy - 3, W - 4, yy + 5, W - 9, yy + 1, HIELOC)
        for i in range(18):
            x = (i * 53 + fc // 3) % W
            y = y0 + (i * 37 + fc // 2) % (y1 - y0)
            pyxel.pset(x, y, WHITE)
            pyxel.pset(x + 1, y, HIELOC)
            pyxel.pset(x - 1, y, HIELOC)
            pyxel.pset(x, y - 1, HIELOC)
            pyxel.pset(x, y + 1, HIELOC)

    def _carteles(self):
        for s, sub, col, vida, vida0, k in self.carteles:
            if vida < vida0 * 0.3 and (vida // 3) % 2:
                continue
            kk = k + 1 if vida > vida0 - 5 else k
            y = TOP + 34
            _sombra_txt(W // 2, y, s, col, kk, OUT, 1)
            if sub:
                yy = y + 6 * kk + 4
                sw = len(sub) * 4 + 8
                pyxel.rect(W // 2 - sw // 2, yy - 3, sw, 11, OUT)
                pyxel.rectb(W // 2 - sw // 2, yy - 3, sw, 11, col)
                ctext(W // 2, yy, sub, WHITE)

    # el marcador -----------------------------------------------------------
    def _hud(self, fc):
        c = self.c
        pyxel.rect(0, 0, W, HUD, HUDC)
        pyxel.rect(0, 0, W, 12, HUD2)
        pyxel.dither(0.5)
        pyxel.rect(0, 12, W, 4, HUD2)
        pyxel.dither(1.0)
        pyxel.rect(0, HUD - 3, W, 1, PINK if c.climax else EDGE)
        # el reloj, como barra a todo lo ancho bajo el marcador
        frac = c.time / TIME
        pyxel.rect(0, HUD - 2, W, 2, SHADOW)
        bc = PINK if c.climax else (WARN if c.time <= 10 * 60 else ACCENT)
        pyxel.rect(0, HUD - 2, int(W * frac), 2, bc)
        # el puntaje, grande
        text(5, 3, "PUNTOS", DIM)
        big_text(5, 11, "%d" % c.score, ACCENT, 2, SHADOW)
        # el multiplicador, con la barra de lo que le queda a la racha
        m = c.mult() * (CLIMAX_X if c.climax else 1)
        x = 52
        if m > 1:
            col = GOLD if (fc // 6) % 2 else PINK
            big_text(x, 6, "x%d" % m, col, 2, SHADOW)
            if c.racha:
                bw = big_width("x%d" % m, 2) - 2
                pyxel.rect(x, 19, bw, 3, OUT)
                pyxel.rect(x, 19, max(1, int(bw * c.vuelta_t / VUELTA_TTL)), 3,
                           PINK)
        # las vidas: corazones (se sacuden al perder una)
        hx = 89
        jit = ((fc % 4) - 1.5) if self.hud_golpe else 0
        for i in range(VIDAS):
            on = i < c.lives
            col = ROJO if on else EDGE
            if i == c.lives and self.hud_golpe and (fc // 3) % 2:
                col = WHITE
            _corazon(int(hx + i * 10 + jit), 5, col, ROJODK if on else HUD2)
        # lo que tienes encima: escudo y congelado
        ix = 91
        if c.escudo:
            pyxel.rect(ix, 15, 7, 5, SHIELD)
            pyxel.rect(ix + 1, 20, 5, 1, SHIELD)
            pyxel.rect(ix + 2, 21, 3, 1, SHIELD)
            pyxel.rect(ix + 1, 16, 1, 3, WHITE)
            ix += 11
        if c.hielo:
            pyxel.circ(ix + 3, 18, 3, HIELOC)
            pyxel.line(ix + 3, 18, ix + 3, 16, OUT)
            pyxel.line(ix + 3, 18, ix + 5, 18, OUT)
            text(ix + 9, 16, "%d" % (c.hielo // 60 + 1), HIELOC)
        # cruces: banderita y número grande
        cx = 128
        text(cx, 3, "CRUCES", DIM)
        pyxel.rect(cx, 11, 1, 11, TXT)
        for j in range(3):
            for i in range(3):
                pyxel.rect(cx + 1 + i * 2, 11 + j * 2, 2, 2,
                           WHITE if (i + j) % 2 else OUT)
        big_text(cx + 10, 11, "%d" % c.cruces, TXT, 2, SHADOW)
        # el reloj, grande
        s = c.time // 60
        col = WHITE
        if s <= 10:
            col = WARN if fc % 30 < 15 else WHITE
        rs = "%d" % s
        text(W - 29, 3, "TIEMPO", DIM)
        big_text(W - 5 - big_width(rs, 2), 11, rs, col, 2, SHADOW)

    def _barra(self):
        """la barrita de abajo: en qué cruce vas, el tramo y el ritmo."""
        c = self.c
        y = BARRA
        pyxel.rect(0, y, W, H - y, HUDC)
        pyxel.rect(0, y, W, 1, EDGE)
        t = "cruce %d · %s" % (c.cruces + 1, c.tramo.lower())
        text(5, y + 4, t, TXT)
        r = c.ritmo()
        s = "ritmo %.1fx" % r
        col = WARN if r >= RITMO_MAX else (GOLD if r > 1.2 else DIM)
        text(W - len(s) * 4 - 22, y + 4, s, col)
        # el velocímetro: cinco rayitas que se prenden con el ritmo
        n = 1 + int((r - 1.0) / (RITMO_MAX - 1.0) * 4 + 0.001)
        for i in range(5):
            pyxel.rect(W - 18 + i * 3, y + 9 - i, 2, 2 + i,
                       col if i < n else EDGE)


class CruzarCabinet(Cabinet):
    """el Cabinet de siempre; sólo cambia la portada, que es el barrio de
    noche con el tráfico andando. si algo falla, vuelve a la de fábrica."""

    def _draw_title(self):
        try:
            self._titulo()
        except Exception:
            super()._draw_title()

    def _titulo(self):
        if not hasattr(self, "_demo"):
            art.bake_sprites()
            self._demo = World()
            self._demo.c.time = 10 ** 9
        d = self._demo
        for carril in d.c.carriles:
            carril.step(1.0)
        d.fx.update()
        fc = pyxel.frame_count
        pyxel.cls(BG)
        pyxel.blt(0, 0, d.bg, 0, 0, W, H)
        for carril in d.c.carriles:
            d._carril(carril, fc)
        pyxel.rect(0, 0, W, HUD, HUDC)
        pyxel.rect(0, HUD - 1, W, 1, EDGE)
        ctext(W // 2, 11, "MHW · RETRO · FUTURE", DIM)
        a = self.anim
        cx = W // 2
        # el logo, grande, con contorno y sombra honda
        y = 30
        _sombra_txt(cx, y, "CRUZAR", ACCENT, 5, OUT, 2)
        pyxel.rect(cx - 70, y + 34, 140, 1, CINTA1)
        sx = (a * 2) % 200 - 30
        pyxel.rect(cx - 70 + max(0, sx), y + 34, max(0, min(16, 140 - max(0, sx))),
                   1, WHITE)
        sw = len(self.subtitle) * 4 + 10
        pyxel.rect(cx - sw // 2, y + 37, sw, 11, OUT)
        ctext(cx, y + 40, self.subtitle, TXT)
        # el bicho, saltando en su lugar
        hop = abs(math.sin(a * 0.08)) * 8
        pyxel.rect(cx - 6, 104, 12, 3, SOMBRA)
        bicho(cx - 7, int(90 - hop), 14, 14, (PL3, PL2, PL1, PL0), (0, -1),
              pies=hop < 1)
        # el llamado
        call = "toca para jugar" if web.is_touch() else "enter para jugar"
        lit = self._blink(24)
        pw = len(call) * 4 + 18
        pyxel.rect(cx - pw // 2, 120, pw, 15, GOLD if lit else OUT)
        pyxel.rectb(cx - pw // 2, 120, pw, 15, GOLD)
        ctext(cx, 125, call, OUT if lit else GOLD)
        # cómo se juega
        bw = W - 24
        hy = 148
        hh = 18 + 11 * len(self.howto)
        pyxel.rect(12 + 3, hy + 3, bw, hh, SHADOW)
        pyxel.rect(12, hy, bw, hh, HUDC)
        pyxel.rectb(12, hy, bw, hh, EDGE)
        ctext(cx, hy + 6, "cómo se juega", ACCENT)
        for i, line in enumerate(self.howto):
            ctext(cx, hy + 18 + i * 11, line, TXT)
        # los récords
        lst = scores.top(self.id, 3)
        if lst:
            ry = hy + hh + 12
            rh = 18 + 20 * len(lst)
            pyxel.rect(12 + 3, ry + 3, bw, rh, SHADOW)
            pyxel.rect(12, ry, bw, rh, HUDC)
            pyxel.rectb(12, ry, bw, rh, GOLDDK)
            ctext(cx, ry + 6, "mejores", DIM)
            for i, e in enumerate(lst):
                big_ctext(cx, ry + 17 + 20 * i,
                          "%d %s %6d" % (i + 1, e["ini"], e["score"]),
                          GOLD if i == 0 else TXT, 2, SHADOW)


class Game:
    def __init__(self):
        touch = web.is_touch()
        CruzarCabinet(
            game_id="cruzar", title="CRUZAR", subtitle="90 segundos de ida y vuelta",
            howto=["desliza o usa la cruceta para saltar" if touch else
                   "flechas o wasd saltan",
                   "abajo esquivas · arriba te arrastran",
                   "en el río, súbete a los troncos",
                   "cada cruce cambia el tramo y acelera"],
            width=W, height=H, palette=PAL, scale=2, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=HUD2),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
