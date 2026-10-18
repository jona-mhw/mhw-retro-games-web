"""esquiva — aguanta 100 segundos, para el cabinet MHW · RETRO · FUTURE.

la partida tiene una meta y un final: duras 100 segundos y el puntaje es lo que
juntas mientras tanto. tiene forma de función con actos:

- **oleadas con nombre**: bloques y gemas, después zigzag, después rayos que
  avisan la columna antes de quemarla, después buscadores que te persiguen.
- **dos muros** (a los 30 y a los 60) que hay que romper a tiros o esquivar.
- **el jefe final, el NÚCLEO**, a los 72: se mueve arriba y alterna tres
  ataques que se leen de lejos (abanico de balas, rayo a tu columna, lluvia de
  bloques). con la mitad de vida se enoja y ataca más seguido. si lo rompes,
  los segundos que sobran se pagan y la partida termina en victoria.
- **frenesí final**: los últimos 15 segundos todo vale doble.
- **la munición se recarga sola**: un cargador de 6 balas que se rellena de a
  una por segundo, con el medidor grande abajo, junto a la nave. disparar sin balas avisa
  ("SIN BALAS", el medidor se sacude) en vez de no hacer nada: el jugador del
  celular reportaba que "dejaba de disparar" y era esto.
- **poderes con duración visible**: escudo (una burbuja que aguanta un golpe),
  ralentí, ráfaga (tiro doble sin gastar balas), imán de gemas y vida extra.
- **rozar paga** y **cadena de gemas** (x2..x4), como antes.

el movimiento en el celular va por el trackpad (pad = "drag"): el dedo se
arrastra abajo de la pantalla y no tapa la nave. con teclado, ◀ ▶; con mouse,
la nave sigue al puntero.

la lógica vive en la clase Esquiva, sin pyxel: `step()` avanza un frame y
devuelve qué pasó. como el reloj sólo baja, la partida termina siempre en 100
segundos o antes, y eso se prueba sin jugar.

la arena es vertical (240x360), como un shooter de celular: hay más alto
para leer lo que viene, y por eso todo cae algo más rápido que en la arena
apaisada de antes. el arte (paleta, sprites, el espacio) vive en art.py.
"""
import math
import random

import pyxel

from pixelkit import fx, scores, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import big_ctext, big_text, big_width, ctext, text

from . import art
from .art import *  # noqa: F401,F403  (los colores de la paleta)

W, H = 240, 360
HUD = 30                         # el marcador de arriba
BARRA = H - 16                   # la barra de abajo: el cargador
PLAYER_Y = H - 42
PW, PH = 24, 14                  # nave
OH = 12                          # alto de un bloque
ANCHOS = (14, 18, 26)            # anchos de los bloques

TIME = 100 * 60                  # la partida entera: no hay forma de estirarla
VIDAS = 3
GRACIA = 100                     # invulnerable después de un golpe

# el cargador: se rellena solo. antes eran 5 balas y sólo volvían con cajas, y
# al vaciarse el botón quedaba muerto: parecía un bug. ahora nunca te quedas
# más de un segundo sin bala, y si aprietas vacío el juego te lo dice.
AMMO_MAX = 6
AMMO0 = AMMO_MAX
RECARGA = 40                     # frames por bala que vuelve
FIRE_GAP = 8                     # mantener apretado dispara a este ritmo
RAFAGA_GAP = 5
SHOT_V = 6.0
NAVE_V = 4.2                     # con teclado

GEM_VALE, ROMPER_VALE = 5, 2
SLOW_TTL, SLOW_F = 5 * 60, 0.45
RAFAGA_TTL = 6 * 60
IMAN_TTL = 8 * 60
GEM_GAP, POWER_GAP = 3 * 60, 8 * 60

# el muro: baja lento y hay que romperlo a tiros o esquivarlo. viene dos veces
JEFE_CADA = 30 * 60
JEFE_W, JEFE_H = 90, 22
JEFE_HP = 7
JEFE_V = 0.7
JEFE_VALE = 60

# el núcleo: el jefe final
FINAL_EN = 28 * 60               # entra cuando quedan 28 s
NUCLEO_W, NUCLEO_H = 72, 36
NUCLEO_HP = 24
NUCLEO_Y = HUD + 26              # dónde se queda flotando
NUCLEO_VALE = 250
NUCLEO_PEGA = 3                  # cada tiro que le entra
NUCLEO_GAP, NUCLEO_GAP_ENOJO = 120, 80
BONO_SEG = 5                     # lo que paga cada segundo que sobra
VICTORIA = 150                   # la vuelta olímpica antes de terminar
BALA_V = 2.0                     # balas del núcleo
ABANICO, RAYO_ATQ, LLUVIA = range(3)
ATAQUE_NOMBRE = {ABANICO: "¡ABANICO!", RAYO_ATQ: "¡RAYO!", LLUVIA: "¡LLUVIA!"}

# los rayos: avisan la columna y después la queman. apuntan a donde estabas
RAYO_W = 16
RAYO_AVISO = 60
RAYO_FUEGO = 18
RAYO_GAP = 5 * 60

# los buscadores: chicos, te siguen de costado mientras caen
BUSCA_VALE = 8
BUSCA_W = 13
BUSCA_GIRO = 0.06
BUSCA_VMAX = 1.3

FRENESI = 15 * 60                # los últimos 15 s valen doble

# rozar: el bloque que pasa a esta distancia (o menos) de la nave, sin tocarla
ROCE_DIST = 7
ROCE_VALE = 3
# la cadena de gemas: cada tres seguidas, la próxima vale una vez más
GEM_CADENA_CADA = 3
GEM_CADENA_MAX = 4
IMAN_R = 110

ROCA, ZIGZAG, DURA, BUSCA = range(4)
ESCUDO, RALENTI, RAFAGA, IMAN, VIDA = range(5)
POWER_NOMBRE = {ESCUDO: "¡ESCUDO!", RALENTI: "¡RALENTÍ!", RAFAGA: "¡RÁFAGA!",
                IMAN: "¡IMÁN!", VIDA: "¡+1 VIDA!"}
POWER_PESO = ((ESCUDO, 3), (RALENTI, 2), (RAFAGA, 3), (IMAN, 2), (VIDA, 1))

# los actos: (segundos jugados, título, bajada). el nivel es el índice + 1
FASES = ((0, "OLEADA 1", "esquiva y junta gemas"),
         (15, "OLEADA 2", "¡bloques en zigzag!"),
         (38, "OLEADA 3", "¡rayos! muévete del aviso"),
         (52, "OLEADA 4", "¡buscadores! dispárales"),
         ((TIME - FINAL_EN) // 60, "JEFE FINAL", "rompe el núcleo"),
         ((TIME - FRENESI) // 60, "¡FRENESÍ!", "todo vale doble"))

class Nucleo:
    """el jefe final: flota arriba, va y viene, y ataca en un orden fijo.

    el orden fijo es a propósito: abanico, rayo, lluvia, y vuelta. el segundo
    ciclo ya lo conoces y lo puedes jugar, que es lo que hace a un jefe legible.
    antes de cada ataque el núcleo "carga" (se pone blanco) un momento.
    """

    def __init__(self):
        self.x = (W - NUCLEO_W) / 2
        self.y = float(HUD - NUCLEO_H)
        self.vx = 0.7
        self.hp = NUCLEO_HP
        self.t = 90                    # primer ataque, después de bajar
        self.cual = 0
        self.golpe = 0                 # frames de "me pegaron" (dibujo)

    @property
    def enojado(self):
        return self.hp <= NUCLEO_HP // 2

    @property
    def cargando(self):
        return self.t <= 24

    def cx(self):
        return self.x + NUCLEO_W / 2


class Esquiva:
    """la nave, lo que cae y el tanteo. sin pyxel, testeable de a de veras."""

    def __init__(self, rng=None):
        self.rng = rng or random
        self.reset()

    def reset(self):
        self.px = (W - PW) / 2
        self.rocks = []              # [x, y, w, tipo, vx, hp, rozado]
        self.gems = []               # [x, y]
        self.powers = []             # [x, y, tipo]
        self.shots = []              # [x, y]
        self.balas = []              # balas del núcleo [x, y, vx, vy]
        self.rayos = []              # [x, aviso, fuego]
        self.score = 0
        self.lives = VIDAS
        self.ammo = AMMO0
        self.carga = 0               # cuánto va la próxima bala (0..RECARGA)
        self.cool = 0
        self.over = False
        self.spawn_t = 0
        self.gem_t = GEM_GAP
        self.power_t = POWER_GAP
        self.rayo_t = RAYO_GAP
        self.gracia = 0
        self.slow = 0
        self.rafaga = 0
        self.iman = 0
        self.escudo = False
        self.jefe = None             # el muro [x, y, hp, vx]
        self.jefe_t = JEFE_CADA
        self.muros = 0
        self.nucleo = None
        self.nucleo_roto = False
        self.victoria = 0
        self.time = TIME
        self.fase = 0
        self.esquivados = 0
        self.roces = 0
        self.gem_cadena = 0
        self.disparos = 0

    # --- dificultad ------------------------------------------------------
    def jugado(self):
        return TIME - self.time

    def level(self):
        """el nivel lo marca el reloj, no el puntaje: la presión sube igual
        aunque juegues a lo seguro y no sumes nada."""
        s = self.jugado() // 60
        n = 0
        for i, (t, _, _) in enumerate(FASES):
            if s >= t:
                n = i
        return n + 1

    def frenesi(self):
        return 0 < self.time <= FRENESI

    def speed(self):
        # la arena es más alta que la de antes: cae un 30 % más rápido, así el
        # tiempo para reaccionar queda parecido y la pantalla se llena igual
        v = min(6.2, 2.1 + self.jugado() * 0.0009)
        return v * (SLOW_F if self.slow else 1.0)

    def _spawn_gap(self):
        g = max(10, 31 - self.jugado() // 110)
        if self.nucleo is not None:
            g = int(g * 1.7)         # con el jefe arriba, menos relleno
        return g

    def set_player(self, x):
        self.px = min(W - PW, max(0, x))

    def gem_mult(self):
        return min(GEM_CADENA_MAX, 1 + self.gem_cadena // GEM_CADENA_CADA)

    def _sumar(self, n):
        """todo lo que suma pasa por acá: así el frenesí vale doble parejo."""
        n *= 2 if self.frenesi() else 1
        self.score += n
        return n

    def _roza(self, x, y, w, h):
        """¿pasa a un pelo de la nave, sin tocarla? a la altura de la nave y
        con el hueco horizontal menor que ROCE_DIST."""
        if not (y + h > PLAYER_Y and y < PLAYER_Y + PH):
            return False
        if x < self.px + PW and x + w > self.px:
            return False                         # eso es tocar, no rozar
        hueco = (self.px - (x + w)) if x + w <= self.px else (x - (self.px + PW))
        return hueco <= ROCE_DIST

    def _toca(self, x, y, w, h):
        return (x < self.px + PW and x + w > self.px
                and y + h > PLAYER_Y and y < PLAYER_Y + PH)

    def puede_disparar(self):
        return not self.over and self.cool == 0 and (self.rafaga or self.ammo > 0)

    def disparar(self):
        """un tiro, si hay bala y pasó la cadencia. devuelve si salió."""
        if not self.puede_disparar():
            return False
        cx = self.px + PW / 2
        if self.rafaga:                          # doble y gratis
            self.shots.append([cx - 7, PLAYER_Y + 2])
            self.shots.append([cx + 7, PLAYER_Y + 2])
            self.cool = RAFAGA_GAP
        else:
            self.ammo -= 1
            self.shots.append([cx, PLAYER_Y - 4])
            self.cool = FIRE_GAP
        self.disparos += 1
        return True

    def carga_frac(self):
        """cuánto falta para la próxima bala, de 0 a 1 (1 = lleno)."""
        if self.ammo >= AMMO_MAX:
            return 1.0
        return self.carga / RECARGA

    # --- un frame --------------------------------------------------------
    def step(self):
        ev = []
        if self.over:
            return ev
        for campo in ("gracia", "slow", "cool", "rafaga", "iman"):
            v = getattr(self, campo)
            if v > 0:
                setattr(self, campo, v - 1)
        ev += self._recargar()
        ev += self._fases()

        if self.victoria:
            self.victoria -= 1
            v = self.speed()
            ev += self._mover_balas()
            ev += self._mover_gemas(v)
            if self.victoria == 0:
                self.over = True
                ev.append(("victoria_fin", 0, 0))
        else:
            self._spawnear(ev)
            ev += self._jefe()
            ev += self._nucleo()
            v = self.speed()
            ev += self._mover_balas()
            ev += self._mover_rocas(v)
            ev += self._mover_gemas(v)
            ev += self._mover_poderes(v)
            ev += self._mover_enemigas()
            ev += self._rayos()

        self.time -= 1
        if self.time <= 0 and not self.over:
            self.time = 0
            self.over = True
            ev.append(("aguantaste", 0, 0))
        return ev

    def _recargar(self):
        if self.ammo >= AMMO_MAX:
            self.carga = 0
            return []
        self.carga += 1
        if self.carga >= RECARGA:
            self.carga = 0
            self.ammo += 1
            return [("recarga", self.ammo)]
        return []

    def _fases(self):
        n = self.level() - 1
        if n != self.fase:
            self.fase = n
            _, tit, sub = FASES[n]
            return [("fase", n + 1, tit, sub)]
        return []

    def _tipo_al_azar(self):
        f = self.fase
        r = self.rng.random()
        zig = (0.06, 0.24, 0.28, 0.28, 0.22, 0.30)[f]
        busca = (0.0, 0.0, 0.0, 0.14, 0.08, 0.14)[f]
        dura = 0.10
        if r < zig:
            return ZIGZAG
        if r < zig + busca:
            return BUSCA
        if r > 1 - dura:
            return DURA
        return ROCA

    def _spawnear(self, ev):
        self.spawn_t -= 1
        if self.spawn_t <= 0:
            tipo = self._tipo_al_azar()
            w = BUSCA_W if tipo == BUSCA else self.rng.choice(ANCHOS)
            x = self.rng.randint(0, W - w)
            vx = self.rng.choice((-0.9, 0.9)) if tipo == ZIGZAG else 0.0
            # [x, y, w, tipo, vx, hp, rozado]
            self.rocks.append([x, HUD - OH, w, tipo, vx, 2 if tipo == DURA else 1,
                               0])
            self.spawn_t = self._spawn_gap()
        self.gem_t -= 1
        if self.gem_t <= 0:
            self.gems.append([self.rng.randint(4, W - 8), HUD - 6])
            self.gem_t = GEM_GAP + self.rng.randrange(60)
        self.power_t -= 1
        if self.power_t <= 0:
            self.powers.append([self.rng.randint(6, W - 12), HUD - 8,
                                self._poder_al_azar()])
            self.power_t = POWER_GAP + self.rng.randrange(120)
        # los rayos, desde la oleada 3 (el núcleo tira los suyos)
        if self.fase >= 2 and self.nucleo is None:
            self.rayo_t -= 1
            if self.rayo_t <= 0:
                self.rayo_t = RAYO_GAP - 60 * min(2, self.fase - 2) \
                    + self.rng.randrange(60)
                self._rayo(self.px + PW / 2, ev)

    def _poder_al_azar(self):
        total = sum(p for _, p in POWER_PESO)
        r = self.rng.randrange(total)
        for tipo, p in POWER_PESO:
            if r < p:
                return tipo
            r -= p
        return ESCUDO

    def _rayo(self, cx, ev):
        x = max(0, min(W - RAYO_W, cx - RAYO_W / 2))
        self.rayos.append([x, RAYO_AVISO, RAYO_FUEGO])
        ev.append(("rayo_aviso", x + RAYO_W / 2, HUD))

    def _rayos(self):
        ev = []
        quedan = []
        for r in self.rayos:
            if r[1] > 0:
                r[1] -= 1
                if r[1] == 0:
                    ev.append(("rayo_fuego", r[0] + RAYO_W / 2, PLAYER_Y))
                quedan.append(r)
                continue
            r[2] -= 1
            if not self.gracia and r[0] < self.px + PW - 3 and \
                    r[0] + RAYO_W > self.px + 3:
                self._golpe(self.px + PW / 2, PLAYER_Y, ev)
            if r[2] > 0:
                quedan.append(r)
        self.rayos = quedan
        return ev

    def _jefe(self):
        """el muro: baja despacio, se corre de lado y aguanta varios tiros."""
        ev = []
        if self.jefe is None:
            if self.muros >= 2:
                return ev              # el tercero es el núcleo
            self.jefe_t -= 1
            if self.jefe_t <= 0:
                self.jefe_t = JEFE_CADA
                self.muros += 1
                self.jefe = [(W - JEFE_W) / 2, HUD - JEFE_H, JEFE_HP,
                             self.rng.choice((-0.8, 0.8))]
                ev.append(("jefe_entra", 0, 0))
            return ev
        j = self.jefe
        f = SLOW_F if self.slow else 1.0
        j[1] += JEFE_V * f
        j[0] += j[3] * f
        if j[0] <= 0 or j[0] + JEFE_W >= W:
            j[3] = -j[3]
            j[0] = max(0, min(W - JEFE_W, j[0]))
        if self._toca(j[0], j[1], JEFE_W, JEFE_H):
            if not self.gracia:
                self._golpe(j[0] + JEFE_W / 2, j[1], ev)
                self.jefe = None
            return ev
        if j[1] > H:                       # se te escapó: no suma, pero no duele
            self.jefe = None
            ev.append(("jefe_pasa", 0, 0))
        return ev

    def _nucleo(self):
        ev = []
        n = self.nucleo
        if n is None:
            if not self.nucleo_roto and self.time <= FINAL_EN:
                self.nucleo = Nucleo()
                ev.append(("nucleo_entra", W / 2, HUD))
            return ev
        if n.golpe:
            n.golpe -= 1
        f = SLOW_F if self.slow else 1.0
        if n.y < NUCLEO_Y:
            n.y += 0.5
            return ev
        n.x += n.vx * f * (1.5 if n.enojado else 1.0)
        if n.x <= 2 or n.x + NUCLEO_W >= W - 2:
            n.vx = -n.vx
            n.x = max(2, min(W - 2 - NUCLEO_W, n.x))
        n.t -= 1
        if n.t <= 0:
            n.t = NUCLEO_GAP_ENOJO if n.enojado else NUCLEO_GAP
            cual = n.cual % 3
            n.cual += 1
            cx, by = n.cx(), n.y + NUCLEO_H
            if cual == ABANICO:
                k = 7 if n.enojado else 5
                for i in range(k):
                    a = math.pi / 2 + (i - (k - 1) / 2) * 0.32
                    self.balas.append([cx, by, math.cos(a) * BALA_V,
                                       math.sin(a) * BALA_V])
            elif cual == RAYO_ATQ:
                self._rayo(self.px + PW / 2, ev)
                if n.enojado:                    # y otro donde vas a escapar
                    lado = 44 if self.px < W / 2 else -44
                    self._rayo(self.px + PW / 2 + lado, ev)
            else:
                for i in range(4 if n.enojado else 3):
                    w = self.rng.choice(ANCHOS[:2])
                    x = self.rng.randint(0, W - w)
                    self.rocks.append([x, by - OH, w, ROCA, 0.0, 1, 0])
            ev.append(("nucleo_ataca", cx, by, cual))
        return ev

    def _mover_enemigas(self):
        ev = []
        quedan = []
        f = SLOW_F if self.slow else 1.0
        for b in self.balas:
            b[0] += b[2] * f
            b[1] += b[3] * f
            if self._toca(b[0] - 2, b[1] - 2, 4, 4):
                if not self.gracia:
                    self._golpe(b[0], b[1], ev)
                continue
            if -4 < b[0] < W + 4 and b[1] < H + 4:
                quedan.append(b)
        self.balas = quedan
        return ev

    def _mover_balas(self):
        ev = []
        quedan = []
        for s in self.shots:
            s[1] -= SHOT_V
            if s[1] < HUD - 6:
                continue
            pegó = False
            n = self.nucleo
            if n is not None and n.x <= s[0] <= n.x + NUCLEO_W \
                    and n.y <= s[1] <= n.y + NUCLEO_H:
                n.hp -= 1
                n.golpe = 6
                self._sumar(NUCLEO_PEGA)
                if n.hp <= 0:
                    self._romper_nucleo(ev)
                else:
                    ev.append(("nucleo_pega", s[0], s[1]))
                    if n.hp == NUCLEO_HP // 2:
                        ev.append(("nucleo_enojo", n.cx(), n.y))
                continue
            j = self.jefe
            if j is not None and j[0] <= s[0] <= j[0] + JEFE_W \
                    and j[1] <= s[1] <= j[1] + JEFE_H:
                j[2] -= 1
                if j[2] <= 0:
                    vale = self._sumar(JEFE_VALE)
                    ev.append(("jefe_cae", j[0] + JEFE_W / 2, j[1] + JEFE_H / 2,
                               vale))
                    self.jefe = None
                    # el muro suelta una ráfaga y gemas: es el premio
                    self.powers.append([j[0] + JEFE_W / 2, j[1], RAFAGA])
                    for k in (-30, 0, 30):
                        self.gems.append([j[0] + JEFE_W / 2 + k, j[1] + 4])
                else:
                    ev.append(("raspa", s[0], s[1], ROCA))
                continue
            for r in self.rocks:
                if r[0] <= s[0] <= r[0] + r[2] and r[1] <= s[1] <= r[1] + OH:
                    r[5] -= 1
                    pegó = True
                    if r[5] <= 0:
                        vale = self._sumar(BUSCA_VALE if r[3] == BUSCA
                                           else ROMPER_VALE)
                        ev.append(("rompe", r[0] + r[2] / 2, r[1] + OH / 2, r[3],
                                   vale))
                        self.rocks.remove(r)
                    else:
                        ev.append(("raspa", s[0], s[1], r[3]))
                    break
            if not pegó:
                quedan.append(s)
        self.shots = quedan
        return ev

    def _romper_nucleo(self, ev):
        n = self.nucleo
        vale = self._sumar(NUCLEO_VALE)
        seg = self.time // 60
        bono = self._sumar(seg * BONO_SEG)
        ev.append(("nucleo_cae", n.cx(), n.y + NUCLEO_H / 2, vale, bono, seg))
        self.nucleo = None
        self.nucleo_roto = True
        # se limpia la pantalla: cada cosa que cae estalla y paga
        for r in self.rocks:
            ev.append(("rompe", r[0] + r[2] / 2, r[1] + OH / 2, r[3],
                       self._sumar(ROMPER_VALE)))
        self.rocks = []
        self.balas = []
        self.rayos = []
        self.jefe = None
        # y llueven gemas para la vuelta olímpica
        for i in range(10):
            self.gems.append([12 + i * 24, HUD + 6 + (i % 3) * 14])
        self.victoria = min(VICTORIA, max(1, self.time - 1))

    def _golpe(self, x, y, ev):
        """te tocaron: pierdes una vida y quedas invulnerable un rato. si
        tienes escudo, se rompe la burbuja y nada más."""
        if self.over or self.victoria:
            return
        if self.escudo:
            self.escudo = False
            self.gracia = GRACIA // 2
            ev.append(("escudo_roto", self.px + PW / 2, PLAYER_Y))
            return
        self.lives -= 1
        self.gracia = GRACIA
        if self.gem_cadena >= GEM_CADENA_CADA:
            ev.append(("cadena_rota", self.gem_cadena))
        self.gem_cadena = 0
        ev.append(("golpe", x, y, self.lives))
        if self.lives <= 0:
            self.over = True
            ev.append(("fin", x, y))

    def _mover_rocas(self, v):
        ev = []
        quedan = []
        f = SLOW_F if self.slow else 1.0
        cxn = self.px + PW / 2
        for r in self.rocks:
            if r[3] == BUSCA:
                r[1] += v * 0.8
                # te sigue de costado, con inercia: se lo puede engañar
                d = cxn - (r[0] + r[2] / 2)
                r[4] += BUSCA_GIRO if d > 0 else -BUSCA_GIRO
                r[4] = max(-BUSCA_VMAX, min(BUSCA_VMAX, r[4]))
                r[0] = max(0, min(W - r[2], r[0] + r[4] * f))
            else:
                r[1] += v
            if r[3] == ZIGZAG:
                r[0] += r[4] * f
                if r[0] <= 0 or r[0] + r[2] >= W:
                    r[4] = -r[4]
                    r[0] = max(0, min(W - r[2], r[0]))
            if self._toca(r[0], r[1], r[2], OH):
                if not self.gracia:
                    self._golpe(r[0] + r[2] / 2, r[1], ev)
                    continue                        # el bloque que te pegó se va
                quedan.append(r)
                continue
            # el roce: una vez por bloque, y sólo si no estás intocable
            while len(r) < 7:
                r.append(0)
            if not r[6] and not self.gracia and self._roza(r[0], r[1], r[2], OH):
                r[6] = 1
                vale = self._sumar(ROCE_VALE)
                self.roces += 1
                lado = r[0] + r[2] if r[0] + r[2] <= self.px else r[0]
                ev.append(("roce", lado, PLAYER_Y + PH / 2, vale))
            if r[1] > H:
                self._sumar(1)
                self.esquivados += 1
            else:
                quedan.append(r)
        self.rocks = quedan
        return ev

    def _mover_gemas(self, v):
        ev = []
        quedan = []
        cx, cy = self.px + PW / 2, PLAYER_Y + PH / 2
        for g in self.gems:
            g[1] += v * 0.82                        # caen algo más lento
            if self.iman or self.victoria:
                dx, dy = cx - g[0], cy - g[1]
                if self.victoria or dx * dx + dy * dy < IMAN_R * IMAN_R:
                    g[0] += max(-2.6, min(2.6, dx * 0.09))
                    g[1] += max(-2.6, min(2.6, dy * 0.09))
            if self._toca(g[0] - 4, g[1] - 4, 8, 8):
                vale = self._sumar(GEM_VALE * self.gem_mult())
                self.gem_cadena += 1
                ev.append(("gema", g[0], g[1], vale))
                if self.gem_cadena % GEM_CADENA_CADA == 0 and self.gem_mult() > 1:
                    ev.append(("cadena", g[0], g[1], self.gem_mult()))
            elif g[1] <= H:
                quedan.append(g)
        self.gems = quedan
        return ev

    def _mover_poderes(self, v):
        ev = []
        quedan = []
        for p in self.powers:
            p[1] += v * 0.7
            if self._toca(p[0] - 6, p[1] - 6, 12, 12):
                self._tomar(p[2], ev)
            elif p[1] <= H:
                quedan.append(p)
        self.powers = quedan
        return ev

    def _tomar(self, tipo, ev):
        if tipo == VIDA and self.lives >= VIDAS:
            tipo = ESCUDO                        # con todo lleno, burbuja
        if tipo == ESCUDO:
            self.escudo = True
        elif tipo == VIDA:
            self.lives += 1
        elif tipo == RALENTI:
            self.slow = SLOW_TTL
        elif tipo == RAFAGA:
            self.rafaga = RAFAGA_TTL
            self.ammo = AMMO_MAX
        else:
            self.iman = IMAN_TTL
        ev.append(("power", self.px + PW / 2, PLAYER_Y, tipo))


# --- la piel -----------------------------------------------------------------
CHISPA_ROCA = (WHITE, RK3, RK2, RK1, RK0)
CHISPA_GEM = (WHITE, GM3, GM2, GM1)
CHISPA_GOLPE = (WHITE, LASER2, WARN, LASERDK)
CHISPA_NUCLEO = (WHITE, MAG3, MAG2, MAG1, MAG0)
CHISPA_DURA = (WHITE, HD3, HD2, HD1)
FASE_COL = (ACCENT, ZG2, LASER, SK2, MAG2, GOLD)
POWER_COL = (SHIELD, SLOWC, GOLD, WARN, HEART)

_CORAZON = (".XX.XX.", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX..", "...X...")


def corazon(x, y, col, dk=None):
    for j, fila in enumerate(_CORAZON):
        i = fila.index("X")
        k = fila.rindex("X") + 1
        pyxel.rect(x + i, y + j, k - i, 1, col)
    if dk is not None:
        pyxel.rect(x + 4, y + 2, 2, 2, dk)
        pyxel.rect(x + 3, y + 4, 2, 1, dk)
        pyxel.pset(x + 1, y + 1, WHITE)


def _txt(cx, y, s, col, k, sombra=OUT):
    """texto grande centrado con contorno: se lee sobre cualquier fondo."""
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (2, 2)):
        big_ctext(cx + ox, y + oy, s, sombra, k)
    big_ctext(cx, y, s, col, k)


class Fx(fx.Fx):
    """el Fx de pixelkit con carteles que suben a dos tamaños y con sombra:
    `popup(..., k=2)` para lo que importa."""

    def popup(self, x, y, s, col, life=38, vy=-0.55, k=1):
        self.pops.append([float(x), float(y), vy, s, col, life, life, k])

    def draw(self, camx=0, camy=0):
        pops, self.pops = self.pops, []
        try:
            super().draw(camx, camy)
        finally:
            self.pops = pops
        for q in pops:
            x, y, s, col, vida, vida0 = q[0], q[1], q[3], q[4], q[5], q[6]
            k = q[7] if len(q) > 7 else 1
            if vida < vida0 * 0.35 and (self.t // 3) % 2:
                continue
            half = len(s) * 2 * k + 2
            x = max(camx + half, min(camx + pyxel.width - half, x))
            if k == 1:
                ctext(x - camx + 1, int(y - camy) + 1, s, OUT)
                ctext(x - camx, int(y - camy), s, col)
            else:
                big_ctext(x - camx + 1, int(y - camy) + 1, s, OUT, k)
                big_ctext(x - camx, int(y - camy), s, col, k)


class World:
    def __init__(self):
        art.bake_sprites()
        self.fondo = art.bake_fondo(W, H)
        self.e = Esquiva()
        self.fx = Fx(gravity=0.06, max_parts=260)
        self.fx.destello(WHITE)
        self.use_mouse = False        # gana el último input que hayas usado
        self._lm = None
        self._toque = None            # arrastre sobre la pantalla (celular)
        self.touch = web.is_touch()
        self.vacio = 0                # el medidor se sacude: "no hay balas"
        self.vacio_pop = 0
        self.hud_golpe = 0
        self.recarga_fx = 0
        self.muro_golpe = 0
        self.scroll = 0.0             # cuánto avanzó el fondo lejano
        self.inclina = 0.0            # la nave se ladea al moverse
        self.cartel = None            # [titulo, bajada, frames, color]
        self.anillos = []             # ondas de las explosiones grandes
        try:
            lst = scores.top("esquiva", 1)
            self.record = lst[0]["score"] if lst else 0
        except Exception:
            self.record = 0
        self.record_visto = self.record <= 0
        self._efecto(("fase", 1, FASES[0][1], FASES[0][2]))

    @property
    def over(self):
        return self.e.over

    @property
    def score(self):
        return self.e.score

    # --- input -----------------------------------------------------------
    def _mover(self):
        e = self.e
        x0 = e.px
        dx, _ = web.drag()                         # el trackpad del celular
        left = pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A)
        right = pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D)
        mx = pyxel.mouse_x
        if self.touch:
            # con el dedo sobre la pantalla: movimiento relativo, sin saltos
            # (si el trackpad ya movió este frame, no se suma: así un toque
            # que pyxel también lea como mouse no mueve la nave dos veces)
            if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
                if self._toque is not None and not dx:
                    dx = (mx - self._toque) * 1.4
                self._toque = mx
            else:
                self._toque = None
        else:
            if self._lm is not None and mx != self._lm:
                self.use_mouse = True
            self._lm = mx
        if left or right or dx:
            self.use_mouse = False
        if dx:
            e.set_player(e.px + dx)
        elif self.use_mouse:
            e.set_player(mx - PW / 2)
        elif left:
            e.set_player(e.px - NAVE_V)
        elif right:
            e.set_player(e.px + NAVE_V)
        d = e.px - x0
        self.inclina += (max(-1.0, min(1.0, d / 3.0)) - self.inclina) * 0.3

    def _fuego(self):
        e = self.e
        teclas = (pyxel.KEY_SPACE, pyxel.KEY_UP, pyxel.KEY_W, pyxel.KEY_X)
        if not self.touch:
            teclas += (pyxel.MOUSE_BUTTON_LEFT,)
        aprieta = any(pyxel.btn(k) for k in teclas)
        nuevo = any(pyxel.btnp(k) for k in teclas)
        if not aprieta:
            return
        if e.disparar():
            cx = e.px + PW / 2
            self.fx.burst(cx, PLAYER_Y - 2, (WHITE, SHOT, GOLD),
                          n=5, speed=1.1, life=10, spread=1.2, angle=-1.5708)
        elif e.ammo == 0 and not e.rafaga and nuevo:
            # sin balas: que se note. chispa apagada en el cañón, el medidor
            # se sacude y un cartel dice qué pasa y que ya vuelve
            self.vacio = 24
            self.fx.burst(e.px + PW / 2, PLAYER_Y - 2, (DIM, STAR2), n=5,
                          speed=0.8, life=10, spread=1.6, angle=-1.5708)
            if not self.vacio_pop:
                self.fx.popup(e.px + PW / 2, PLAYER_Y - 22, "SIN BALAS", WARN,
                              life=34, k=2)
                self.vacio_pop = 40

    def update(self):
        e = self.e
        self._mover()
        self._fuego()
        for campo in ("vacio", "vacio_pop", "hud_golpe", "recarga_fx",
                      "muro_golpe"):
            v = getattr(self, campo)
            if v:
                setattr(self, campo, v - 1)
        if self.cartel:
            self.cartel[2] -= 1
            if self.cartel[2] <= 0:
                self.cartel = None
        for ev in e.step():
            self._efecto(ev)
        if not self.record_visto and e.score > self.record:
            self.record_visto = True
            self.fx.popup(W / 2, HUD + 60, "¡NUEVO RÉCORD!", GOLD, life=80, k=2)
            self.fx.burst(W / 2, HUD + 60, (WHITE, GOLD, MAG2), n=28,
                          speed=2.6, life=30)
            self.fx.destello(GOLD)
        # el fondo avanza más rápido cuanto más aprieta la partida
        self.scroll += 0.12 + e.speed() * 0.06
        # la estela de los motores
        if not e.over and pyxel.frame_count % 2 == 0:
            self.fx.burst(e.px + PW / 2 + (pyxel.frame_count // 2 % 3 - 1) * 2,
                          PLAYER_Y + PH + 2, (FL0, FL1, FL2, STAR2), n=1,
                          speed=1.2, life=12, spread=0.4, angle=1.5708,
                          gravity=0.0)
        n = e.nucleo
        if n is not None and n.enojado and pyxel.frame_count % 9 == 0:
            self.fx.burst(n.x + 8 + (pyxel.frame_count * 7) % (NUCLEO_W - 16),
                          n.y + NUCLEO_H - 6, (WHITE, LASER2, LASER, STAR2),
                          n=3, speed=1.0, life=16)
        for a in self.anillos:
            a[2] += a[3]
            a[3] *= 0.92
            a[4] -= 1
        self.anillos = [a for a in self.anillos if a[4] > 0]
        self.fx.update()

    def anillo(self, x, y, col, dr=3.0, vida=18):
        self.anillos.append([x, y, 2.0, dr, vida, vida, col])

    def _efecto(self, ev):
        kind = ev[0]
        if kind == "gema":
            self.fx.burst(ev[1], ev[2], CHISPA_GEM, n=16, speed=1.8, life=24)
            self.fx.popup(ev[1], ev[2] - 10, "+%d" % ev[3], GM2, k=2)
        elif kind == "cadena":
            self.fx.popup(ev[1], ev[2] - 28, "¡CADENA x%d!" % ev[3], GOLD, k=2)
            self.fx.destello(GM1)
        elif kind == "cadena_rota":
            self.fx.popup(W / 2, PLAYER_Y - 40, "cadena rota", TXT)
        elif kind == "roce":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, SHIP2), n=8, speed=1.3,
                          life=14, spread=1.0, angle=-1.5708)
            self.fx.popup(ev[1], ev[2] - 16, "¡cerca! +%d" % ev[3], GOLD,
                          life=28)
        elif kind == "rompe":
            if ev[3] == BUSCA:
                ramp, col = (WHITE, SK3, SK2, SK1), SK2
            elif ev[3] == DURA:
                ramp, col = CHISPA_DURA, HD3
            elif ev[3] == ZIGZAG:
                ramp, col = (WHITE, ZG3, ZG2, ZG1), ZG3
            else:
                ramp, col = CHISPA_ROCA, WHITE
            self.fx.burst(ev[1], ev[2], ramp, n=18, speed=2.1, life=24)
            self.fx.popup(ev[1], ev[2] - 8, "+%d" % ev[4], col)
            self.fx.shake(2)
        elif kind == "raspa":
            self.fx.burst(ev[1], ev[2], CHISPA_DURA, n=7, speed=1.5, life=12)
            if self.e.jefe is not None:
                self.muro_golpe = 2
        elif kind == "recarga":
            self.recarga_fx = 10
        elif kind == "golpe":
            self.fx.burst(ev[1], ev[2], CHISPA_GOLPE, n=34, speed=2.8, life=32)
            self.fx.burst(self.e.px + PW / 2, PLAYER_Y + 6, (WHITE, HEART, WARN),
                          n=18, speed=2.2, life=24)
            self.fx.popup(self.e.px + PW / 2, PLAYER_Y - 26, "-1 VIDA", HEART,
                          life=44, k=2)
            self.fx.shake(7)
            self.fx.destello(WARN, 6)
            self.anillo(self.e.px + PW / 2, PLAYER_Y + PH / 2, HEART, 3.0, 14)
            self.hud_golpe = 36
        elif kind == "escudo_roto":
            self.fx.burst(ev[1], ev[2], (WHITE, SHIELD, SLOWC), n=28, speed=2.4,
                          life=26)
            self.fx.popup(ev[1], ev[2] - 24, "¡te salvó el escudo!", SHIELD)
            self.fx.shake(3)
        elif kind == "power":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, POWER_COL[ev[3]]), n=22,
                          speed=2.2, life=26)
            self.fx.popup(ev[1], ev[2] - 22, POWER_NOMBRE[ev[3]],
                          POWER_COL[ev[3]], life=44, k=2)
            self.fx.destello(GOLD)
        elif kind == "jefe_entra":
            self._cartel("¡MURO!", "rómpelo a tiros o pasa por el lado", HD2)
            self.fx.destello(HD2)
            self.fx.shake(4)
        elif kind == "jefe_cae":
            self.fx.burst(ev[1], ev[2], (WHITE, HD3, HD2, GOLD, GM2), n=48,
                          speed=3.2, life=38)
            for k in (-30, 30):
                self.fx.burst(ev[1] + k, ev[2], CHISPA_DURA, n=16, speed=2.2,
                              life=28)
            self.fx.popup(ev[1], ev[2], "+%d" % ev[3], GOLD, life=50, k=2)
            self.anillo(ev[1], ev[2], HD3, 4.0, 20)
            self.anillo(ev[1], ev[2], GOLD, 2.4, 24)
            self.fx.shake(8)
            self.fx.destello(GOLD)
        elif kind == "fase":
            n, tit, sub = ev[1], ev[2], ev[3]
            col = FASE_COL[n - 1]
            self._cartel(tit, sub, col)
            if n > 1:
                self.fx.destello(col)
        elif kind == "rayo_fuego":
            self.fx.shake(3)
            self.fx.burst(ev[1], ev[2] + 10, (WHITE, LASER2, LASER, GOLD), n=14,
                          speed=1.8, life=18, angle=-1.5708, spread=2.4)
        elif kind == "nucleo_entra":
            # el cartel lo pone la fase ("JEFE FINAL"), que llega en el mismo frame
            self.fx.shake(6)
            self.fx.destello(MAG2, 6)
        elif kind == "nucleo_ataca":
            self.fx.popup(ev[1], ev[2] + 12, ATAQUE_NOMBRE[ev[3]], LASER2,
                          life=34, k=2)
            self.fx.burst(ev[1], ev[2], (WHITE, MAG3, MAG2), n=10, speed=1.6,
                          life=14, angle=1.5708, spread=2.0)
        elif kind == "nucleo_pega":
            self.fx.burst(ev[1], ev[2], CHISPA_NUCLEO, n=7, speed=1.5, life=12)
        elif kind == "nucleo_enojo":
            self._cartel("¡SE ENOJÓ!", "ataca más rápido", WARN, 70)
            self.fx.shake(5)
            self.fx.destello(WARN)
        elif kind == "nucleo_cae":
            x, y, vale, bono, seg = ev[1], ev[2], ev[3], ev[4], ev[5]
            for k in range(5):
                self.fx.burst(x + (k - 2) * 14, y + (k % 2) * 8,
                              CHISPA_NUCLEO + (GOLD,), n=30, speed=3.4, life=44)
            self.fx.popup(x, y, "+%d" % vale, GOLD, life=70, k=3)
            self.anillo(x, y, WHITE, 6.0, 26)
            self.anillo(x, y, MAG2, 4.0, 30)
            self.anillo(x, y, GOLD, 2.5, 34)
            self._cartel("¡NÚCLEO ROTO!",
                         "%d s sobrantes +%d" % (seg, bono), GOLD, VICTORIA)
            self.fx.shake(10)
            self.fx.destello(GOLD, 8)
        elif kind == "aguantaste":
            self._cartel("¡AGUANTASTE!", "", ACCENT, 90)

    def _cartel(self, tit, sub, col, frames=100):
        self.cartel = [tit, sub, frames, col, frames]

    # --- dibujo ----------------------------------------------------------
    def draw(self):
        e = self.e
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        fc = pyxel.frame_count
        self._espacio(e, fc)
        if e.frenesi() and (fc // 8) % 2:          # el borde late en el final
            pyxel.rectb(0, HUD, W, BARRA - HUD, GOLD)
            pyxel.rectb(1, HUD + 1, W - 2, BARRA - HUD - 2, GOLDDK)
        for r in e.rayos:
            self._rayo(r, fc)
        for r in e.rocks:
            self._roca(r, fc)
        if e.jefe:
            self._muro(e.jefe, fc)
        if e.nucleo:
            self._nucleo(e.nucleo, fc)
        f = (fc // 6) % 2
        for gx, gy in e.gems:
            art.spr(("gema", f), gx - 4, gy - 4)
        for px_, py_, tipo in e.powers:
            self._power(int(px_), int(py_), tipo, fc)
        for sx_, sy_ in e.shots:
            art.spr("tiro", sx_ - 1, sy_ - 1)
        fb = (fc // 4) % 2
        for b in e.balas:
            art.spr(("bala", fb), b[0] - 4, b[1] - 4)
        self._nave(e, fc)
        for x, y, r, _, vida, vida0, col in self.anillos:
            pyxel.circb(int(x), int(y), int(r), col if vida > vida0 // 3 else STAR)
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(0, HUD, W, BARRA - HUD)
        if e.nucleo:
            self._barra_nucleo(e.nucleo)
        self._dibujar_cartel()
        self._hud(fc)
        self._barra(fc)

    def _espacio(self, e, fc):
        """tres capas: la nebulosa lejana (horneada, lenta), el planeta que
        pasa durante la partida, y estrellas cerca que corren rápido."""
        off = int(self.scroll) % H
        pyxel.blt(0, off - H, self.fondo, 0, 0, W, H)
        pyxel.blt(0, off, self.fondo, 0, 0, W, H)
        py = -96 + (TIME - e.time) * 0.07
        if py < H:
            art.planeta(W - 84, py)
        vel = 1 if e.slow else 2 + (1 if e.frenesi() else 0)
        s = self.scroll
        for i in range(22):                       # estrellas del medio
            x = (i * 53 + 7) % W
            y = int(i * 71 + s * 3) % H
            pyxel.pset(x, y, STAR)
        for i in range(10):                       # polvo cercano: rayas
            x = (i * 97 + 13) % W
            y = int(i * 41 + s * 7) % H
            pyxel.line(x, y, x, y + vel, STAR3 if i % 3 == 0 else STAR)

    def _rayo(self, r, fc):
        x, aviso, fuego = int(r[0]), r[1], r[2]
        y0, y1 = HUD, BARRA
        ya = y0 + (14 if self.e.nucleo is not None else 0)   # bajo la barra del jefe
        if aviso > 0:
            # el aviso: dos líneas punteadas y una flecha, titilando cada vez
            # más rápido a medida que se acerca el disparo
            per = 8 if aviso > 25 else 3
            on = (fc // per) % 2
            if on:
                fx.flash(LASER, 0.22, x, y0, RAYO_W, y1 - y0)
            col = LASER if on else WARN
            off = (fc // 2) % 6
            for y in range(y0 + 2 + off, y1, 6):
                pyxel.rect(x, y, 1, 3, col)
                pyxel.rect(x + RAYO_W - 1, y, 1, 3, col)
            cx = x + RAYO_W // 2
            pyxel.tri(cx - 6, ya + 3, cx + 6, ya + 3, cx, ya + 11, OUT)
            pyxel.tri(cx - 4, ya + 4, cx + 4, ya + 4, cx, ya + 9, col)
            _txt(cx, ya + 14, "!", WHITE if on else LASER2, 2)
            # y abajo, a la altura de la nave, otra marca: ahí quema
            pyxel.rect(x - 2, PLAYER_Y + PH + 4, RAYO_W + 4, 2, col)
            return
        k = 2 if fuego > 6 else 1
        fx.flash(LASER2, 0.4, x - 3, y0, RAYO_W + 6, y1 - y0)
        pyxel.rect(x, y0, RAYO_W, y1 - y0, LASER)
        pyxel.rect(x + 3 - k + 1, y0, RAYO_W - 6 + 2 * (k - 1), y1 - y0, GOLD)
        pyxel.rect(x + RAYO_W // 2 - 1, y0, 2, y1 - y0, WHITE)
        for i in range(4):                        # chispas que suben por el rayo
            yy = y1 - ((fc * 6 + i * 70) % (y1 - y0))
            pyxel.rect(x + 2 + (i * 5) % (RAYO_W - 4), yy, 2, 3, WHITE)

    def _roca(self, r, fc):
        x, y, w, tipo, hp = int(r[0]), int(r[1]), r[2], r[3], r[5]
        if tipo == BUSCA:
            key = ("busca", BUSCA_W)
        else:
            nombre = {ZIGZAG: "zig", DURA: "dura" if hp > 1 else "dura1"}.get(
                tipo, "roca")
            wk = min(ANCHOS, key=lambda a: abs(a - w))
            key = (nombre, wk)
            x += (w - wk) // 2
        art.spr(key, x, y)
        if tipo == BUSCA:                         # el ojo mira a la nave
            cx = x + BUSCA_W // 2
            ojo = 1 if self.e.px + PW / 2 > cx else -1
            pyxel.rect(cx - 1, y + OH // 2 - 1, 3, 3, WHITE)
            pyxel.rect(cx - 1 + ojo + (1 if ojo < 0 else 0), y + OH // 2 - 1, 2, 2,
                       OUT)
            if (fc // 5) % 2:
                pyxel.pset(cx, y - 2, SK2)

    def _muro(self, j, fc):
        x, y, hp = int(j[0]), int(j[1]), j[2]
        art.spr("muro", x, y)
        if self.muro_golpe:
            fx.flash(WHITE, 0.3, x, y, JEFE_W, JEFE_H)
        # las grietas: más cuanto menos vida le queda
        dano = JEFE_HP - hp
        for i in range(dano):
            gx = x + 8 + (i * 37) % (JEFE_W - 16)
            gy = y + 7
            pyxel.line(gx, gy, gx + 3, gy + 4, OUT)
            pyxel.line(gx + 3, gy + 4, gx + 1, gy + 8, OUT)
        # la barra de vida va encima: hay que saber cuánto falta
        bw = JEFE_W - 24
        bx = x + 12
        by = y + JEFE_H // 2 - 2
        pyxel.rect(bx - 1, by - 1, bw + 2, 6, OUT)
        fx.bar(bx, by, bw, 4, hp / JEFE_HP, WARN if hp <= 2 else GM1, SHADOW)
        for i in range(1, JEFE_HP):
            pyxel.pset(bx + bw * i // JEFE_HP, by, OUT)

    def _nucleo(self, n, fc):
        x, y = int(n.x), int(n.y)
        golpe = n.golpe and (fc // 2) % 2
        if n.enojado:
            ramp = (ZG3, ZG2, ZG1, ZG0)
        else:
            ramp = (HD3, HD2, HD1, HD0)
        l3, l2, l1, l0 = (WHITE, ramp[0], ramp[1], ramp[2]) if golpe else ramp
        w, h = NUCLEO_W, NUCLEO_H
        # su sombra, sobre el espacio
        pyxel.rect(x + 10, y + 6, w - 12, h, SHADOW)
        # los cañones de los costados
        for cx in (x - 4, x + w - 6):
            pyxel.rect(cx, y + 10, 10, 18, OUT)
            pyxel.rect(cx + 1, y + 11, 8, 16, l1)
            pyxel.rect(cx + 1, y + 11, 8, 2, l2)
            pyxel.rect(cx + 3, y + 27, 4, 5, OUT)
            pyxel.rect(cx + 4, y + 27, 2, 4, MAG2 if not n.cargando else WHITE)
        # el cuerpo: un octógono blindado con bisel
        pyxel.rect(x + 8, y, w - 16, h, OUT)
        pyxel.rect(x + 2, y + 6, w - 4, h - 12, OUT)
        pyxel.rect(x + 4, y + 3, w - 8, h - 6, OUT)
        pyxel.rect(x + 9, y + 1, w - 18, h - 2, l1)
        pyxel.rect(x + 3, y + 7, w - 6, h - 14, l1)
        pyxel.rect(x + 5, y + 4, w - 10, h - 8, l1)
        pyxel.rect(x + 9, y + 1, w - 18, 2, l3)
        pyxel.rect(x + 5, y + 4, 4, 2, l2)
        pyxel.rect(x + 3, y + 7, 2, h - 16, l2)
        pyxel.rect(x + 9, y + h - 4, w - 18, 3, l0)
        pyxel.rect(x + w - 5, y + 7, 2, h - 14, l0)
        # placas, con costuras que brillan al ritmo del ataque
        brillo = MAG3 if n.cargando and (fc // 3) % 2 else (
            LASER2 if n.enojado else MAG2)
        for px_ in (x + 8, x + w - 16):
            pyxel.rect(px_, y + 8, 8, h - 16, l2)
            pyxel.rect(px_, y + 8, 8, 1, l3)
            pyxel.rect(px_, y + h - 9, 8, 1, l0)
            pyxel.rect(px_ + 3, y + 11, 2, h - 22, brillo)
        pyxel.rect(x + 18, y + 4, w - 36, 1, brillo)
        pyxel.rect(x + 18, y + h - 5, w - 36, 1, brillo)
        # las antenas de arriba
        for ax in (x + 14, x + w - 16):
            pyxel.rect(ax, y - 5, 3, 6, OUT)
            pyxel.rect(ax + 1, y - 4, 1, 5, l2)
            pyxel.pset(ax + 1, y - 5, brillo if (fc // 8) % 2 else l3)
        # el ojo: blanco cuando carga un ataque, rojo si está enojado
        cx, cy = x + w // 2, y + h // 2
        pyxel.circ(cx, cy, 13, OUT)
        pyxel.circ(cx, cy, 12, l0)
        if n.cargando and (fc // 3) % 2:
            core, core2 = WHITE, GM3
        elif n.enojado:
            core, core2 = LASER, LASER2
        else:
            core, core2 = MAG2, MAG3
        pyxel.circ(cx, cy, 9 + (fc // 10) % 2, core)
        pyxel.circ(cx - 2, cy - 2, 5, core2)
        mira = max(-4, min(4, (self.e.px + PW / 2 - cx) / 16))
        pyxel.circ(int(cx + mira), cy + 2, 4, OUT)
        pyxel.pset(int(cx + mira) - 1, cy, WHITE)
        pyxel.pset(cx - 5, cy - 5, WHITE)
        # luces que orbitan el ojo
        for i in range(8):
            a = i * 0.785 + fc * (0.09 if n.enojado else 0.05)
            ox = int(cx + math.cos(a) * 16)
            oy = int(cy + math.sin(a) * 15)
            if y + 1 < oy < y + h - 1:
                pyxel.pset(ox, oy, GOLD if i % 2 else MAG3)
        # cargando: la energía se junta en el ojo
        if n.cargando:
            k = n.t / 24
            for i in range(6):
                a = i * 1.047 + fc * 0.2
                rr = 8 + 26 * k
                pyxel.rect(int(cx + math.cos(a) * rr), int(cy + math.sin(a) * rr),
                           2, 2, WHITE if i % 2 else MAG3)

    def _barra_nucleo(self, n):
        y = HUD + 3
        pyxel.rect(0, y - 2, W, 12, OUT)
        text(5, y + 1, "NÚCLEO", MAG3 if not n.enojado else LASER2)
        bx, bw = 36, W - 42
        pyxel.rect(bx - 1, y, bw + 2, 7, MAG0)
        fx.bar(bx, y + 1, bw, 5, n.hp / NUCLEO_HP,
               LASER if n.enojado else MAG2, SHADOW)
        pyxel.rect(bx, y + 1, int(bw * n.hp / NUCLEO_HP), 1,
                   LASER2 if n.enojado else MAG3)
        for i in range(1, 4):
            pyxel.rect(bx + bw * i // 4, y + 1, 1, 5, OUT)

    def _icono(self, x, y, tipo):
        """el dibujito de cada poder, de 7x7 alrededor de (x, y)."""
        if tipo == ESCUDO:
            pyxel.rect(x - 3, y - 3, 7, 4, SHIELD)
            pyxel.rect(x - 2, y + 1, 5, 2, SHIELD)
            pyxel.pset(x, y + 3, SHIELD)
            pyxel.rect(x - 2, y - 2, 1, 3, WHITE)
        elif tipo == RALENTI:
            pyxel.circ(x, y, 3, SLOWC)
            pyxel.line(x, y, x, y - 2, WHITE)
            pyxel.line(x, y, x + 2, y, WHITE)
        elif tipo == RAFAGA:
            for bx in (x - 2, x + 1):
                pyxel.rect(bx, y - 2, 2, 6, SHOT)
                pyxel.rect(bx, y - 3, 2, 1, WHITE)
                pyxel.rect(bx, y + 3, 2, 1, GOLDDK)
        elif tipo == IMAN:
            pyxel.rect(x - 3, y - 3, 2, 5, WARN)
            pyxel.rect(x + 2, y - 3, 2, 5, WARN)
            pyxel.rect(x - 3, y + 1, 7, 2, WARN)
            pyxel.rect(x - 3, y - 3, 2, 1, WHITE)
            pyxel.rect(x + 2, y - 3, 2, 1, WHITE)
        else:
            corazon(x - 3, y - 3, HEART)

    def _power(self, x, y, tipo, fc):
        col = POWER_COL[tipo]
        if (fc // 6) % 2:
            pyxel.dither(0.3)
            pyxel.circ(x, y, 11, col)
            pyxel.dither(1.0)
        pyxel.rect(x - 5 + 3, y - 5 + 4, 12, 12, SHADOW)
        pyxel.rect(x - 7, y - 6, 15, 13, OUT)
        pyxel.rect(x - 6, y - 7, 13, 15, OUT)
        pyxel.rect(x - 5, y - 5, 11, 11, PANEL2)
        pyxel.rectb(x - 6, y - 6, 13, 13, col)
        pyxel.rect(x - 5, y - 6, 11, 1, WHITE if (fc // 6) % 2 else col)
        self._icono(x, y, tipo)

    def _nave(self, e, fc):
        x = int(e.px)
        cx = x + PW // 2
        y = PLAYER_Y
        if not (e.gracia and (fc // 4) % 2):       # titila mientras es intocable
            # la llama de los motores, que late
            f = 4 + (fc // 2) % 3
            pyxel.tri(cx - 3, y + PH - 1, cx + 2, y + PH - 1, cx - 1 + (fc % 2),
                      y + PH + f + 2, FL2)
            pyxel.tri(cx - 2, y + PH - 1, cx + 1, y + PH - 1, cx, y + PH + f,
                      FL1)
            pyxel.rect(cx - 1, y + PH - 1, 2, 2 + f // 2, FL0)
            # los cañones de las alas, encendidos si hay balas
            lit = e.ammo > 0 or e.rafaga
            art.spr("nave_w" if self.hud_golpe > 30 else "nave", x, y)
            if lit:
                pyxel.pset(x + 1, y + 6, SHOT)
                pyxel.pset(x + PW - 2, y + 6, SHOT)
            # se ladea: un ala se ilumina hacia donde va
            if self.inclina > 0.4:
                pyxel.rect(x + PW - 7, y + 9, 4, 1, SHIP3)
            elif self.inclina < -0.4:
                pyxel.rect(x + 3, y + 9, 4, 1, SHIP3)
        if e.slow:
            pyxel.circb(cx, y + PH // 2, 17, SLOWC)
            pyxel.circb(cx, y + PH // 2, 19 + (fc // 6) % 2, STAR2)
        if e.escudo:
            r = 17 + (fc // 8) % 2
            pyxel.circb(cx, y + PH // 2, r, SHIELD)
            pyxel.circb(cx, y + PH // 2, r - 1, SLOWC)
            pyxel.pset(cx - 9, y - 6, WHITE)
            pyxel.pset(cx - 10, y - 5, WHITE)
        if e.iman:                                 # chispas que se juntan
            rr = 28 - (fc % 18)
            for i in range(8):
                a = i * 0.785 + fc * 0.05
                pyxel.pset(int(cx + math.cos(a) * rr),
                           int(y + PH // 2 + math.sin(a) * rr), GM2)
        if e.rafaga:
            pyxel.pset(cx - 7, y - 1, SHOT)
            pyxel.pset(cx + 7, y - 1, SHOT)
        # sin balas: la barrita de recarga sobre la nave, para que se vea que
        # vuelve sola y cuánto falta
        if e.ammo == 0 and not e.rafaga:
            by = y - 8
            col = WARN if self.vacio and (fc // 3) % 2 else SHOT
            pyxel.rect(cx - 13, by - 1, 26, 4, OUT)
            fx.bar(cx - 12, by, 24, 2, e.carga_frac(), col, STAR2)

    def _dibujar_cartel(self):
        c = self.cartel
        if not c:
            return
        tit, sub, f, col, f0 = c
        # entra desde la izquierda y se va titilando
        dx = max(0, (f - (f0 - 10)) * 16)
        if f < 20 and (f // 3) % 2:
            return
        y = HUD + 84
        hh = 42 if sub else 28
        # la franja es de trama, no sólida: no te tapa lo que viene cayendo
        fx.flash(SHADOW, 0.45, 0, y - 7, W, hh)
        pyxel.rect(0, y - 8, W, 1, col)
        pyxel.rect(0, y - 7 + hh, W, 1, col)
        _txt(W / 2 + dx, y, tit, col, 3)
        if sub:
            ctext(W / 2 + dx + 1, y + 24, sub, OUT)
            ctext(W / 2 + dx, y + 23, sub, TXT)

    def _hud(self, fc):
        e = self.e
        pyxel.rect(0, 0, W, HUD, PANEL)
        pyxel.rect(0, 0, W, 12, PANEL2)
        fx.flash(PANEL2, 0.5, 0, 12, W, 5)
        pyxel.rect(0, HUD - 3, W, 1, GOLD if e.frenesi() else EDGE)
        # el puntaje
        text(5, 3, "PUNTOS", DIM)
        sc = "%d" % e.score
        big_text(5, 12, sc, GOLD if e.frenesi() else ACCENT, 2, OUT)
        x = 5 + big_width(sc, 2) + 4
        m = e.gem_mult()
        if m > 1 or e.frenesi():                   # multiplicadores
            s = "x%d" % (m * (2 if e.frenesi() else 1))
            col = GOLD if (fc // 6) % 2 else GM2
            big_text(x, 12, s, col, 2, OUT)
        # las vidas, como corazones (se sacuden al perder una)
        hx = 96
        jit = ((fc % 4) - 1.5) if self.hud_golpe else 0
        for i in range(VIDAS):
            on = i < e.lives
            col = HEART if on else EDGE
            if i == e.lives and self.hud_golpe and (fc // 3) % 2:
                col = WHITE
            corazon(int(hx + i * 10 + jit), 4, col, HEARTDK if on else None)
        self._poderes_hud(hx - 2, 15)
        # el reloj, al doble, y la barra de tiempo a todo lo ancho
        s = e.time // 60
        urge = s <= 10
        col = WARN if urge and fc % 30 < 15 else (SLOWC if e.slow else TXT)
        r = "%d" % s
        text(W - 29, 3, "TIEMPO", DIM)
        big_text(W - 5 - big_width(r, 2), 12, r, col, 2, OUT)
        frac = e.time / TIME
        pyxel.rect(0, HUD - 2, W, 2, SHADOW)
        pyxel.rect(0, HUD - 2, int(W * frac), 2,
                   WARN if urge else (GOLD if e.frenesi() else ACCENT))

    def _poderes_hud(self, x, y):
        """los poderes activos, como íconos con su barrita de tiempo abajo.
        titilan el último segundo."""
        e = self.e
        fc = pyxel.frame_count
        for tipo, t, t0 in ((ESCUDO, 1 if e.escudo else 0, 0),
                            (RAFAGA, e.rafaga, RAFAGA_TTL),
                            (RALENTI, e.slow, SLOW_TTL),
                            (IMAN, e.iman, IMAN_TTL)):
            if not t:
                continue
            if t0 and t < 60 and (fc // 4) % 2:
                x += 11
                continue
            self._icono(x + 4, y + 3, tipo)
            if t0:
                fx.bar(x, y + 8, 9, 2, t / t0, POWER_COL[tipo], STAR2)
            x += 11

    def _barra(self, fc):
        """el cargador, abajo, cerca de la nave: seis balas grandes. la que se
        está recargando se llena desde abajo; si aprietas vacío, se sacude."""
        e = self.e
        y = BARRA
        pyxel.rect(0, y, W, H - y, PANEL)
        pyxel.rect(0, y, W, 1, EDGE)
        text(5, y + 6, "BALAS", DIM)
        ax = 30 + ((fc % 3) - 1 if self.vacio else 0)
        for i in range(AMMO_MAX):
            bx = ax + i * 9
            by = y + 3
            pyxel.rect(bx - 1, by - 1, 7, 12, OUT)
            if e.rafaga:
                col = SHOT if (fc // 4 + i) % 2 else GOLD
                pyxel.rect(bx, by + 2, 5, 8, col)
                pyxel.rect(bx + 1, by, 3, 2, WHITE)
            elif i < e.ammo:
                fresca = self.recarga_fx and i == e.ammo - 1
                pyxel.rect(bx, by + 3, 5, 7, WHITE if fresca else SHOT)
                pyxel.rect(bx, by + 8, 5, 2, GOLDDK)
                pyxel.rect(bx + 1, by, 3, 3, GOLD)
                pyxel.pset(bx + 1, by + 4, WHITE)
            else:
                pyxel.rectb(bx, by, 5, 10, WARN if self.vacio else EDGE)
                if i == e.ammo:
                    h = int(8 * e.carga_frac())
                    if h:
                        pyxel.rect(bx + 1, by + 9 - h, 3, h, GOLDDK)
        tx = ax + AMMO_MAX * 9 + 4
        if e.rafaga:
            text(tx, y + 6, "¡RÁFAGA!", GOLD if (fc // 6) % 2 else SHOT)
        elif e.ammo == 0 and (fc // 10) % 2:
            text(tx, y + 6, "RECARGA", WARN)
        fase = FASES[e.fase][1].lower()
        text(W - 5 - len(fase) * 4, y + 6, fase, FASE_COL[e.fase])


class EsquivaCabinet(Cabinet):
    """el Cabinet de siempre; sólo cambia la portada: el espacio de esquiva,
    la nave flotando y bloques que caen. si algo falla, la de fábrica."""

    def _draw_title(self):
        try:
            self._titulo()
        except Exception:
            super()._draw_title()

    def _titulo(self):
        art.bake_sprites()
        fondo = art.bake_fondo(W, H)
        a = self.anim
        cx = W // 2
        pyxel.cls(BG)
        off = int(a * 0.3) % H
        pyxel.blt(0, off - H, fondo, 0, 0, W, H)
        pyxel.blt(0, off, fondo, 0, 0, W, H)
        art.planeta(W - 70, 58)
        for i in range(22):
            pyxel.pset((i * 53 + 7) % W, int(i * 71 + a * 0.9) % H, STAR)
        # bloques que caen de adorno, a los costados
        for i, (key, x) in enumerate(((("roca", 18), 14), (("zig", 14), 200),
                                      (("dura", 26), 30), (("busca", 13), 190),
                                      (("roca", 26), 206))):
            y = int(i * 83 + a * (0.6 + i * 0.1)) % (H + 40) - 20
            art.spr(key, x, y)
        # el logo, grande, con contorno
        y = 34
        _txt(cx, y, "ESQUIVA", ACCENT, 5)
        pyxel.rect(cx - 70, y + 34, 140, 1, SHIP0)
        sx = (a * 2) % 200 - 30
        pyxel.rect(cx - 70 + max(0, sx), y + 34, max(0, min(16, 140 - max(0, sx))),
                   1, WHITE)
        sw = len(self.subtitle) * 4 + 10
        pyxel.rect(cx - sw // 2, y + 38, sw, 11, OUT)
        ctext(cx, y + 41, self.subtitle, TXT)
        # la nave, flotando, con su llama
        bob = int(math.sin(a / 16) * 2)
        ny = 96 + bob
        f = 6 + (a // 2) % 4
        pyxel.tri(cx - 5, ny + 26, cx + 4, ny + 26, cx, ny + 30 + f, FL2)
        pyxel.tri(cx - 3, ny + 26, cx + 2, ny + 26, cx, ny + 27 + f, FL1)
        pyxel.rect(cx - 1, ny + 26, 2, 3 + f // 3, FL0)
        bank, u, v, sw, sh = art.SPR["nave"]
        pyxel.blt(cx - sw // 2, ny + 7, bank, u, v, sw, sh, 0, scale=2)
        # el llamado
        call = "toca para jugar" if web.is_touch() else "enter para jugar"
        lit = self._blink(24)
        pw = len(call) * 4 + 18
        pyxel.rect(cx - pw // 2, 132, pw, 15, ACCENT if lit else OUT)
        pyxel.rectb(cx - pw // 2, 132, pw, 15, ACCENT)
        ctext(cx, 137, call, OUT if lit else ACCENT)
        # cómo se juega
        bw = W - 24
        hy = 158
        hh = 18 + 11 * len(self.howto)
        pyxel.rect(15, hy + 3, bw, hh, SHADOW)
        pyxel.rect(12, hy, bw, hh, PANEL)
        pyxel.rectb(12, hy, bw, hh, EDGE)
        ctext(cx, hy + 6, "cómo se juega", ACCENT)
        for i, line in enumerate(self.howto):
            ctext(cx, hy + 18 + i * 11, line, TXT)
        lst = scores.top(self.id, 3)
        if lst:
            ry = hy + hh + 12
            rh = 18 + 20 * len(lst)
            pyxel.rect(15, ry + 3, bw, rh, SHADOW)
            pyxel.rect(12, ry, bw, rh, PANEL)
            pyxel.rectb(12, ry, bw, rh, GOLDDK)
            ctext(cx, ry + 6, "mejores", DIM)
            for i, e in enumerate(lst):
                big_ctext(cx, ry + 17 + 20 * i,
                          "%d %s %6d" % (i + 1, e["ini"], e["score"]),
                          GOLD if i == 0 else TXT, 2, OUT)


class Game:
    def __init__(self):
        EsquivaCabinet(
            game_id="esquiva", title="ESQUIVA", subtitle="aguanta 100 segundos",
            howto=["arrastra o flechas mueven · fuego dispara",
                   "las balas se recargan solas",
                   "gemas seguidas valen más · rozar suma",
                   "muros, rayos y un jefe final"],
            width=W, height=H, palette=PAL, scale=2,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=PANEL2),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
