"""cruzar — 90 segundos para pasar de un lado al otro, para MHW RETRO FUTURE.

vas de abajo hacia arriba esquivando el tráfico de cada carril. llegás arriba,
sumás, y volvés a empezar desde abajo — cada vuelta paga más que la anterior si
no te tocaron en el medio.

la vuelta de tuerca es que **no todos los carriles son para esquivar**: los de
arriba son cinta transportadora, y ahí no te podés quedar quieto — te arrastran
hacia el costado y hay que cruzarlos moviéndote *con* la corriente. son dos
lecturas distintas del mismo movimiento.

y hay tres cosas más:

- **la racha**: cada cruce limpio multiplica, hasta x5. te tocan y vuelve a uno.
- **el semáforo**: cada tanto un carril se pone en rojo y su tráfico frena unos
  segundos. es la ventana para cruzar los que están imposibles.
- **el reloj de la vuelta**: si tardás mucho en cruzar, la racha se enfría sola.
- **el ritmo sube con cada cruce**: el tráfico acelera un poco por vuelta, con
  techo. la vuelta 1 y la 12 no son el mismo cruce.
- **monedas en la calle**: aparecen entre los autos y viajan con el carril.
  valen por el multiplicador, así que el camino recto deja de ser el óptimo.

la lógica vive en la clase Cruce, sin pyxel: `step()` avanza un frame con el
movimiento ya leído y devuelve qué pasó.
"""
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

W, H = 240, 208
HUD = 14
LANE_H = 14                      # alto de cada carril
LANES = 11                       # carriles entre la orilla de abajo y la meta
TOP = HUD + LANE_H               # la meta: la franja de arriba
BOTTOM = TOP + LANES * LANE_H    # la orilla de abajo, desde donde salís

TIME = 90 * 60
VIDAS = 3
GRACIA = 90
PW, PH = 10, 11                  # el que cruza

MULT_MAX = 5
VUELTA_TTL = 9 * 60              # tardar más que esto enfría la racha
CRUCE_VALE = 100

TRAFICO, CINTA = range(2)        # qué hace cada carril
SEMAFORO_GAP = 7 * 60
SEMAFORO_TTL = 3 * 60

# el ritmo: cada cruce acelera el tráfico un poco. sin esto los 11 carriles
# eran los mismos en la vuelta 1 y en la 12, y la racha x5 se sostenía de
# memoria. con techo, para que el cruce 20 siga siendo cruzable.
RITMO_PASO = 0.06
RITMO_MAX = 1.7

# las monedas: nacen en un carril de tráfico, entre dos autos, y viajan con él.
MONEDA_GAP = 3 * 60
MONEDA_TTL = 9 * 60
MONEDA_VALE = 40
MONEDAS_MAX = 2

(BG, ROAD1, ROAD2, EDGE, LINEA, PLAYER, PLAYER2, CAR1, CAR2, CAR3, TRUCK,
 CINTA1, CINTA2, TXT, DIM, ACCENT, WARN, SHADOW, WHITE, NEON, PINK, GOLD,
 META, ROJO) = range(24)
PAL = [
    0x0B0A16, 0x1E1B3A, 0x171430, 0x3A2C63, 0x6E6499, 0x38E8E0, 0xA8FFF8,
    0xFF6EC7, 0xFFD24A, 0x9AE84A, 0xE04A2A, 0x2E7FBF, 0x7ADCFF, 0xE8ECF5,
    0x6E6499, 0x38E8E0, 0xE04A2A, 0x060512, 0xF2F5FB, 0x38E8E0, 0xE868C8,
    0xFFD24A, 0x9AE84A, 0xFF3B30,
] + [0] * (256 - 24)

CHISPA_CRUCE = (WHITE, NEON, ACCENT, CINTA1)
CHISPA_GOLPE = (WHITE, WARN, TRUCK, ROAD2)


class Carril:
    """una fila con cosas que se mueven. o te atropellan, o te arrastran."""

    def __init__(self, i, tipo, v, ancho, hueco, rng):
        self.i = i
        self.tipo = tipo
        self.v = v                       # px por frame, con signo
        self.ancho = ancho
        self.rojo = 0                    # frames de semáforo en rojo
        self.cosas = []                  # x de cada vehículo/plataforma
        x = rng.uniform(0, hueco)
        while x < W + ancho:
            self.cosas.append(x)
            x += hueco
        self.hueco = hueco

    @property
    def y(self):
        return TOP + self.i * LANE_H

    def vel(self):
        return 0.0 if self.rojo else self.v

    def step(self, ritmo=1.0):
        if self.rojo:
            self.rojo -= 1
            return
        # el período del wrap tiene que ser el ancho recorrido, no el hueco: con
        # `W + ancho + hueco` el auto que salía se iba mucho más allá del borde
        # opuesto y tardaba de más en volver a entrar.
        p = W + 2 * self.ancho
        v = self.v * ritmo
        for k in range(len(self.cosas)):
            self.cosas[k] += v
            if v > 0 and self.cosas[k] > W + self.ancho:
                self.cosas[k] -= p
            elif v < 0 and self.cosas[k] < -self.ancho:
                self.cosas[k] += p

    def hueco_libre(self, rng):
        """una x entre dos cosas del carril, para dejar una moneda."""
        if not self.cosas:
            return rng.uniform(0, W)
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
        self.carriles = self._armar()

    def _armar(self):
        """los de abajo son tráfico; los tres de arriba, cinta. el salto de
        lectura a mitad de camino es lo que hace la partida."""
        cs = []
        for i in range(LANES):
            cinta = i < 3
            v = self.rng.choice((-1, 1)) * self.rng.uniform(0.55, 1.5)
            if cinta:
                cs.append(Carril(i, CINTA, v * 0.8, self.rng.choice((34, 44, 54)),
                                 self.rng.choice((72, 86, 100)), self.rng))
            else:
                cs.append(Carril(i, TRAFICO, v, self.rng.choice((16, 22, 30)),
                                 self.rng.choice((58, 70, 84)), self.rng))
        return cs

    def mult(self):
        return min(MULT_MAX, 1 + self.racha // 2)

    def ritmo(self):
        """cuánto más rápido va el tráfico que al empezar. sube por cruce."""
        return min(RITMO_MAX, 1 + self.cruces * RITMO_PASO)

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
            self.px = max(0, min(W - PW, self.px + dx * 6))
        if self.py < TOP:                       # llegaste arriba
            self._cruzaste(ev)

    def _cruzaste(self, ev):
        ganado = CRUCE_VALE * self.mult()
        self.score += ganado
        self.cruces += 1
        self.racha += 1
        self.vuelta_t = VUELTA_TTL
        ev.append(("cruce", self.px, TOP, ganado, self.mult()))
        self.px = (W - PW) / 2
        self.py = BOTTOM                        # de vuelta abajo

    def _golpe(self, ev, x, y):
        if self.gracia or self.over:
            return
        self.lives -= 1
        self.gracia = GRACIA
        self.racha = 0
        self.px = (W - PW) / 2
        self.py = BOTTOM
        ev.append(("golpe", x, y, self.lives))
        if self.lives <= 0:
            self.over = True
            ev.append(("fin", x, y))

    # --- un frame ----------------------------------------------------------
    def step(self, dx, dy):
        ev = []
        if self.over:
            return ev
        # el reloj se descuenta ACÁ, antes que nada. estaba al final y varios
        # caminos salían con `return` antes de llegar: cada golpe regalaba un
        # frame, y quedarse apretado contra el borde de una cinta lo congelaba
        # del todo. una partida llegó a durar 7.341 frames de los 5.400 que
        # debía — justo el agujero que la cota de dos minutos tiene que tapar.
        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("aguantaste",))
            return ev
        if self.gracia:
            self.gracia -= 1
        self.mover(dx, dy, ev)
        ritmo = self.ritmo()
        for c in self.carriles:
            c.step(ritmo)
        self._semaforo()
        self._monedas(ev, ritmo)

        carril = self.carril_en(self.py)
        if carril is not None:
            golpe = carril.toca(self.px, PW)
            if carril.tipo == TRAFICO:
                if golpe is not None:
                    self._golpe(ev, self.px, self.py)
                    return ev
            else:
                # la cinta te arrastra: si no estás sobre una, no pasa nada malo
                # (es piso firme), pero si estás, te lleva — y podés caerte del
                # borde de la pantalla
                if golpe is not None:
                    self.px += carril.vel() * ritmo
                    if self.px < 0 or self.px > W - PW:
                        # te llevó hasta el borde y te caés. la cinta no
                        # atropella: lo único que te puede pasar es esto.
                        self._golpe(ev, max(0, min(W - PW, self.px)), self.py)
                        return ev

        if self.racha:
            self.vuelta_t -= 1
            if self.vuelta_t <= 0:
                self.racha = 0
                ev.append(("racha_fria", self.px, self.py))
        return ev

    def _monedas(self, ev, ritmo):
        """nacen entre dos autos, viajan con el carril, y las levantás pisándolas."""
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
            m[1] += c.vel() * ritmo
            p = W + 2 * c.ancho
            if m[1] > W + c.ancho:
                m[1] -= p
            elif m[1] < -c.ancho:
                m[1] += p
            m[2] -= 1
            if m[2] <= 0:
                continue
            if self.carril_en(self.py) is c and not self.over and \
                    m[1] - 4 < self.px + PW and m[1] + 4 > self.px:
                ganado = MONEDA_VALE * self.mult()
                self.score += ganado
                self.monedas_tomadas += 1
                ev.append(("moneda", m[1], c.y, ganado))
                continue
            quedan.append(m)
        self.monedas = quedan

    def _semaforo(self):
        self.sem_t -= 1
        if self.sem_t <= 0:
            self.sem_t = SEMAFORO_GAP
            candidatos = [c for c in self.carriles
                          if c.tipo == TRAFICO and not c.rojo]
            if candidatos:
                self.rng.choice(candidatos).rojo = SEMAFORO_TTL


class World:
    def __init__(self):
        self.c = Cruce()
        self.fx = fx.Fx(gravity=0.1)
        self.paso = 0
        # la posición dibujada persigue a la lógica: el salto se ve, no se
        # teletransporta. la lógica sigue siendo de a carriles enteros.
        self.vx, self.vy = self.c.px, self.c.py

    @property
    def over(self):
        return self.c.over

    @property
    def score(self):
        return self.c.score

    def update(self):
        c = self.c
        dx = (1 if pyxel.btnp(pyxel.KEY_RIGHT, 10, 3) or
              pyxel.btnp(pyxel.KEY_D, 10, 3) else 0) \
            - (1 if pyxel.btnp(pyxel.KEY_LEFT, 10, 3) or
               pyxel.btnp(pyxel.KEY_A, 10, 3) else 0)
        dy = (1 if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S) else 0) \
            - (1 if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W) else 0)
        if dy or dx:
            self.paso = 6
        self.paso = max(0, self.paso - 1)
        for ev in c.step(dx, dy):
            self._efecto(ev)
        # el tween: si la lógica saltó lejos (cruce, golpe), la vista también
        if abs(c.py - self.vy) > LANE_H * 2 or abs(c.px - self.vx) > 40:
            self.vx, self.vy = c.px, c.py
        else:
            self.vx += (c.px - self.vx) * 0.5
            self.vy += (c.py - self.vy) * 0.45
        self.fx.update()

    def _efecto(self, ev):
        k = ev[0]
        if k == "cruce":
            _, x, y, ganado, mult = ev
            self.fx.burst(x + PW / 2, TOP, CHISPA_CRUCE, n=22, speed=2.0, life=28)
            self.fx.popup(W / 2, TOP + 14, "+%d" % ganado, GOLD)
            if mult > 1:
                self.fx.popup(W / 2, TOP + 26, "x%d" % mult, PINK)
            self.fx.shake(3)
            self.fx.destello(NEON)
        elif k == "golpe":
            self.fx.burst(ev[1] + PW / 2, ev[2], CHISPA_GOLPE, n=30, speed=2.6,
                          life=32)
            self.fx.shake(7)
            self.fx.destello(WARN)
        elif k == "moneda":
            _, x, y, ganado = ev
            self.fx.burst(x, y + LANE_H / 2, (WHITE, GOLD, PINK, ROAD2), n=12,
                          speed=1.6, life=20)
            self.fx.popup(x, y - 4, "+%d" % ganado, GOLD)
        elif k == "racha_fria":
            self.fx.popup(ev[1], ev[2] - 10, "racha fría", DIM)
        elif k == "aguantaste":
            self.fx.popup(W / 2, H / 2, "¡SE ACABÓ!", ACCENT)

    # --- dibujo ------------------------------------------------------------
    def draw(self):
        c = self.c
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        # las dos orillas. la meta no va de verde macizo: una franja plana de
        # color se come la pantalla y no se lee como "llegada"
        pyxel.rect(0, TOP - LANE_H, W, LANE_H, ROAD1)
        pyxel.rect(0, TOP - 2, W, 2, META)
        for x in range(0, W, 10):
            pyxel.rect(x + (pyxel.frame_count // 6) % 10, TOP - LANE_H + 4, 5, 2,
                       META if (x // 10) % 2 else NEON)
        pyxel.rect(0, BOTTOM, W, H - BOTTOM, ROAD1)
        pyxel.rect(0, BOTTOM, W, 2, EDGE)
        for carril in c.carriles:
            self._carril(carril)
        for ci, mx, ttl in c.monedas:
            self._moneda(int(mx), c.carriles[ci].y, ttl)
        self._jugador(c)
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(0, HUD, W, H - HUD)
        self._hud()

    def _carril(self, carril):
        y = carril.y
        fondo = ROAD2 if carril.tipo == TRAFICO else BG
        pyxel.rect(0, y, W, LANE_H, fondo)
        if carril.tipo == TRAFICO:
            for x in range(0, W, 12):           # la línea del asfalto
                pyxel.rect(x, y + LANE_H - 1, 6, 1, ROAD1)
            if carril.rojo:                      # semáforo: se ve que está quieto
                col = ROJO if (pyxel.frame_count // 6) % 2 else GOLD
                pyxel.rect(0, y, 2, LANE_H, col)
                pyxel.rect(W - 2, y, 2, LANE_H, col)
        for x in carril.cosas:
            if carril.tipo == TRAFICO:
                self._auto(int(x), y, carril)
            else:
                self._cinta(int(x), y, carril)

    def _auto(self, x, y, carril):
        col = (CAR1, CAR2, CAR3, TRUCK)[(carril.i + int(carril.ancho)) % 4]
        w = carril.ancho
        pyxel.rect(x, y + 2, w, LANE_H - 4, col)
        pyxel.rect(x, y + 2, w, 1, WHITE)
        faro = x + w - 2 if carril.v > 0 else x
        pyxel.rect(faro, y + 4, 2, 2, GOLD)
        pyxel.rect(x + 3, y + 4, w - 6, 3, ROAD2)      # el parabrisas

    def _cinta(self, x, y, carril):
        w = carril.ancho
        pyxel.rect(x, y + 1, w, LANE_H - 2, CINTA1)
        pyxel.rect(x, y + 1, w, 1, CINTA2)
        # flechas que muestran para dónde te lleva
        d = 1 if carril.v > 0 else -1
        off = (pyxel.frame_count * 2) % 10
        for i in range(4, w - 4, 10):
            fx_ = x + (i + off) % max(1, w - 8) + 4
            pyxel.pset(fx_, y + LANE_H // 2, CINTA2)
            pyxel.pset(fx_ + d, y + LANE_H // 2 - 1, CINTA2)
            pyxel.pset(fx_ + d, y + LANE_H // 2 + 1, CINTA2)

    def _moneda(self, x, y, ttl):
        if ttl < 90 and (pyxel.frame_count // 4) % 2:
            return
        cy = y + LANE_H // 2
        w = (3, 2, 1, 2)[(pyxel.frame_count // 5) % 4]      # gira sobre su eje
        pyxel.rect(x - w, cy - 3, w * 2, 6, GOLD)
        pyxel.rect(x - w, cy - 3, w * 2, 1, WHITE)
        if w > 1:
            pyxel.pset(x, cy, PINK)

    def _jugador(self, c):
        if c.gracia and (pyxel.frame_count // 4) % 2:
            return
        x, y = int(self.vx), int(self.vy)
        if self.paso:                                  # en el aire: se estira
            y -= 2
        col = PLAYER2 if self.paso else PLAYER
        pyxel.rect(x + 1, y + 1, PW - 2, PH - 2, SHADOW)
        pyxel.rect(x, y, PW - 2, PH - 2, col)
        pyxel.rectb(x, y, PW - 2, PH - 2, WHITE)      # contorno: hay que verlo
        pyxel.rect(x, y, PW - 2, 1, WHITE)
        pyxel.pset(x + 2, y + 3, BG)                  # los ojos, mirando arriba
        pyxel.pset(x + 5, y + 3, BG)
        if self.paso:                                  # las piernas al saltar
            pyxel.pset(x, y + PH - 2, col)
            pyxel.pset(x + PW - 3, y + PH - 2, col)

    def _hud(self):
        c = self.c
        pyxel.rect(0, 0, W, HUD, SHADOW)
        text(4, 4, "%d" % c.score, ACCENT)
        m = c.mult()
        if m > 1:
            col = GOLD if (pyxel.frame_count // 6) % 2 else PINK
            text(58, 4, "x%d" % m, col)
            fx.bar(74, 5, 24, 4, c.vuelta_t / VUELTA_TTL, PINK, ROAD1)
        for i in range(VIDAS):
            col = PLAYER if i < c.lives else DIM
            pyxel.rect(112 + i * 8, 4, 5, 6, col)
        cr = "%d cruces" % c.cruces
        text(150, 4, cr, DIM)
        r = c.ritmo()
        if r > 1.0:                                    # el ritmo, junto a los cruces
            text(150 + len(cr) * 4 + 6, 4, "%.1fx" % r,
                 WARN if r >= RITMO_MAX else DIM)
        s = c.time // 60
        col = WHITE if s <= 10 and pyxel.frame_count % 30 < 15 else TXT
        r = "%ds" % s
        text(W - len(r) * 4 - 4, 4, r, col)


class Game:
    def __init__(self):
        Cabinet(
            game_id="cruzar", title="CRUZAR", subtitle="90 segundos de ida y vuelta",
            howto=["flechas o wasd mueven",
                   "abajo esquivás · arriba te arrastran",
                   "cada cruce limpio multiplica · el tráfico acelera",
                   "las monedas viajan con el carril"],
            width=W, height=H, palette=PAL, scale=3, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=ROAD2),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
