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
  una por segundo, con el medidor grande en el hud. disparar sin balas avisa
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
"""
import math
import random

import pyxel

from pixelkit import fx, scores, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import ctext, text

W, H = 200, 220
HUD = 18
PLAYER_Y = H - 16
PW, PH = 22, 9                   # nave
OH = 10                          # alto de un bloque

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
SHOT_V = 4.6
NAVE_V = 3.6                     # con teclado

GEM_VALE, ROMPER_VALE = 5, 2
SLOW_TTL, SLOW_F = 5 * 60, 0.45
RAFAGA_TTL = 6 * 60
IMAN_TTL = 8 * 60
GEM_GAP, POWER_GAP = 3 * 60, 8 * 60

# el muro: baja lento y hay que romperlo a tiros o esquivarlo. viene dos veces
JEFE_CADA = 30 * 60
JEFE_W, JEFE_H = 74, 16
JEFE_HP = 7
JEFE_V = 0.55
JEFE_VALE = 60

# el núcleo: el jefe final
FINAL_EN = 28 * 60               # entra cuando quedan 28 s
NUCLEO_W, NUCLEO_H = 48, 20
NUCLEO_HP = 24
NUCLEO_Y = HUD + 16              # dónde se queda flotando
NUCLEO_VALE = 250
NUCLEO_PEGA = 3                  # cada tiro que le entra
NUCLEO_GAP, NUCLEO_GAP_ENOJO = 120, 80
BONO_SEG = 5                     # lo que paga cada segundo que sobra
VICTORIA = 150                   # la vuelta olímpica antes de terminar
BALA_V = 1.5                     # balas del núcleo
ABANICO, RAYO_ATQ, LLUVIA = range(3)
ATAQUE_NOMBRE = {ABANICO: "¡ABANICO!", RAYO_ATQ: "¡RAYO!", LLUVIA: "¡LLUVIA!"}

# los rayos: avisan la columna y después la queman. apuntan a donde estabas
RAYO_W = 14
RAYO_AVISO = 60
RAYO_FUEGO = 18
RAYO_GAP = 5 * 60

# los buscadores: chicos, te siguen de costado mientras caen
BUSCA_VALE = 8
BUSCA_W = 9
BUSCA_GIRO = 0.06
BUSCA_VMAX = 1.1

FRENESI = 15 * 60                # los últimos 15 s valen doble

# rozar: el bloque que pasa a esta distancia (o menos) de la nave, sin tocarla
ROCE_DIST = 6
ROCE_VALE = 3
# la cadena de gemas: cada tres seguidas, la próxima vale una vez más
GEM_CADENA_CADA = 3
GEM_CADENA_MAX = 4
IMAN_R = 90

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

(BG, STAR, SHIP, SHIP2, ROCK, ROCK2, TXT, DIM, ACCENT, WARN, SHADOW, WHITE,
 GEM, GEM2, SHOT, SHIELD, HARD, HARD2, ZIG, ZIG2, SLOWC, GOLD, MAGENTA,
 STAR2, PANEL, HEART, LASER, SEEK) = range(28)
PAL = [
    0x0C0E14, 0x1A2236, 0x8AC52F, 0xB6F03C, 0xE0842E, 0xE0402A, 0xE8ECF5,
    0x7A86A8, 0x8AC52F, 0xE0402A, 0x070810, 0xF2F5FB,
    0x3AC6D8, 0xA8F0FA, 0xFFF3B0, 0x7ADCFF, 0x8A5AD0, 0xC79BF0, 0xD8483A,
    0xFF8A7A, 0x4DA6FF, 0xFFD24A, 0xD84AB8, 0x2A3350, 0x141826, 0xFF4D6A,
    0xFF5A3C, 0x5CF0A0,
] + [0] * (256 - 28)

CHISPA_ROCA = (WHITE, ROCK2, ROCK, DIM)
CHISPA_GEM = (WHITE, GEM2, GEM, ACCENT)
CHISPA_GOLPE = (WHITE, WARN, ROCK2, SHADOW)
CHISPA_NUCLEO = (WHITE, MAGENTA, HARD2, HARD)


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
        v = min(4.8, 1.6 + self.jugado() * 0.0007)
        return v * (SLOW_F if self.slow else 1.0)

    def _spawn_gap(self):
        g = max(13, 40 - self.jugado() // 90)
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
            self.shots.append([cx - 5, PLAYER_Y - 2])
            self.shots.append([cx + 5, PLAYER_Y - 2])
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
            w = BUSCA_W if tipo == BUSCA else self.rng.choice((12, 16, 22))
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
                    lado = 34 if self.px < W / 2 else -34
                    self._rayo(self.px + PW / 2 + lado, ev)
            else:
                for i in range(4 if n.enojado else 3):
                    w = self.rng.choice((12, 16))
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
                    for k in (-24, 0, 24):
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
            self.gems.append([12 + i * 19, HUD + 4 + (i % 3) * 10])
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
            if self._toca(g[0] - 3, g[1] - 3, 6, 6):
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
            if self._toca(p[0] - 5, p[1] - 5, 10, 10):
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


# --- texto grande ------------------------------------------------------------
# la fuente de pyxel tiene 4x6. para el puntaje y los carteles se dibuja al
# doble, leyendo una vez cada glifo de una imagen chica y guardando sus píxeles.
_GLIFOS = {}


_TILDES = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "Á": "A",
           "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}


def _glifo(ch):
    g = _GLIFOS.get(ch)
    if g is None:
        if ch == "¡":                  # no está en la fuente: el ! dado vuelta
            g = [(x, 4 - y) for x, y in _glifo("!")]
        elif ch in _TILDES:            # la letra y la tilde encima
            g = _glifo(_TILDES[ch]) + [(2, -2), (1, -1)]
        elif ch == "Ñ" or ch == "ñ":
            g = _glifo("N" if ch == "Ñ" else "n") + [(0, -1), (1, -2), (2, -1)]
        else:
            img = pyxel.Image(8, 8)
            img.cls(0)
            img.text(0, 0, ch, 1)
            g = [(x, y) for y in range(6) for x in range(4)
                 if img.pget(x, y) == 1]
        _GLIFOS[ch] = g
    return g


def big(x, y, s, col, sombra=None, k=2):
    x, y = int(x), int(y)
    rect = pyxel.rect
    if sombra is not None:
        for i, ch in enumerate(s):
            gx = x + i * 4 * k
            for px, py in _glifo(ch):
                rect(gx + px * k + 1, y + py * k + 1, k, k, sombra)
    for i, ch in enumerate(s):
        gx = x + i * 4 * k
        for px, py in _glifo(ch):
            rect(gx + px * k, y + py * k, k, k, col)


def big_w(s, k=2):
    return len(s) * 4 * k - k


def cbig(cx, y, s, col, sombra=None, k=2):
    big(cx - big_w(s, k) / 2, y, s, col, sombra, k)


_CORAZON = (".XX.XX.", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX..", "...X...")


def corazon(x, y, col):
    for j, fila in enumerate(_CORAZON):
        i = 0
        while i < len(fila):
            if fila[i] == "X":
                k = i
                while k < len(fila) and fila[k] == "X":
                    k += 1
                pyxel.rect(x + i, y + j, k - i, 1, col)
                i = k
            else:
                i += 1


class World:
    def __init__(self):
        self.e = Esquiva()
        self.fx = fx.Fx(gravity=0.06)
        self.fx.destello(WHITE)
        self.use_mouse = False        # gana el último input que hayas usado
        self._lm = None
        self._toque = None            # arrastre sobre la pantalla (celular)
        self.touch = web.is_touch()
        self.vacio = 0                # el medidor se sacude: "no hay balas"
        self.vacio_pop = 0
        self.hud_golpe = 0
        self.recarga_fx = 0
        self.cartel = None            # [titulo, bajada, frames, color]
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
            self.fx.burst(cx, PLAYER_Y - 4, (WHITE, SHOT, ACCENT),
                          n=4, speed=1.0, life=10, spread=1.2, angle=-1.5708)
        elif e.ammo == 0 and not e.rafaga and nuevo:
            # sin balas: que se note. chispa apagada en el cañón, el medidor
            # se sacude y un cartel dice qué pasa y que ya vuelve
            self.vacio = 24
            self.fx.burst(e.px + PW / 2, PLAYER_Y - 4, (DIM, STAR2), n=5,
                          speed=0.8, life=10, spread=1.6, angle=-1.5708)
            if not self.vacio_pop:
                self.fx.popup(e.px + PW / 2, PLAYER_Y - 18, "SIN BALAS", WARN,
                              life=30)
                self.vacio_pop = 40

    def update(self):
        e = self.e
        self._mover()
        self._fuego()
        for campo in ("vacio", "vacio_pop", "hud_golpe", "recarga_fx"):
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
            self.fx.popup(W / 2, HUD + 40, "¡NUEVO RÉCORD!", GOLD, life=70)
            self.fx.burst(W / 2, HUD + 40, (WHITE, GOLD, MAGENTA), n=24,
                          speed=2.4, life=28)
            self.fx.destello(GOLD)
        self.fx.update()

    def _efecto(self, ev):
        kind = ev[0]
        if kind == "gema":
            self.fx.burst(ev[1], ev[2], CHISPA_GEM, n=14, speed=1.7, life=24)
            self.fx.popup(ev[1], ev[2] - 8, "+%d" % ev[3], GEM2)
        elif kind == "cadena":
            self.fx.popup(ev[1], ev[2] - 18, "¡CADENA x%d!" % ev[3], GOLD)
            self.fx.destello(GEM)
        elif kind == "cadena_rota":
            self.fx.popup(W / 2, PLAYER_Y - 30, "cadena rota", TXT)
        elif kind == "roce":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, SHIP2), n=6, speed=1.2,
                          life=14, spread=1.0, angle=-1.5708)
            self.fx.popup(ev[1], ev[2] - 12, "¡cerca! +%d" % ev[3], GOLD,
                          life=26)
        elif kind == "rompe":
            col = SEEK if ev[3] == BUSCA else WHITE
            self.fx.burst(ev[1], ev[2], CHISPA_ROCA, n=16, speed=2.0, life=22)
            self.fx.popup(ev[1], ev[2] - 6, "+%d" % ev[4], col)
            self.fx.shake(2)
        elif kind == "raspa":
            self.fx.burst(ev[1], ev[2], (WHITE, HARD2, HARD), n=6, speed=1.4,
                          life=12)
        elif kind == "recarga":
            self.recarga_fx = 8
        elif kind == "golpe":
            self.fx.burst(ev[1], ev[2], CHISPA_GOLPE, n=30, speed=2.6, life=30)
            self.fx.burst(self.e.px + PW / 2, PLAYER_Y, (WHITE, HEART, WARN),
                          n=16, speed=2.0, life=22)
            self.fx.popup(self.e.px + PW / 2, PLAYER_Y - 20, "-1 VIDA", HEART,
                          life=40)
            self.fx.shake(7)
            self.fx.destello(WARN, 6)
            self.hud_golpe = 36
        elif kind == "escudo_roto":
            self.fx.burst(ev[1], ev[2], (WHITE, SHIELD, SLOWC), n=26, speed=2.4,
                          life=26)
            self.fx.popup(ev[1], ev[2] - 18, "¡te salvó el escudo!", SHIELD)
            self.fx.shake(3)
        elif kind == "power":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, MAGENTA), n=20, speed=2.2,
                          life=26)
            self.fx.popup(ev[1], ev[2] - 16, POWER_NOMBRE[ev[3]], GOLD)
            self.fx.destello(GOLD)
        elif kind == "jefe_entra":
            self._cartel("¡MURO!", "rómpelo a tiros o pasa por el lado",
                         HARD2)
            self.fx.destello(HARD2)
            self.fx.shake(4)
        elif kind == "jefe_cae":
            self.fx.burst(ev[1], ev[2], (WHITE, HARD2, HARD, GEM), n=40,
                          speed=3.0, life=36)
            self.fx.popup(ev[1], ev[2], "+%d" % ev[3], GOLD)
            self.fx.shake(8)
            self.fx.destello(GOLD)
        elif kind == "fase":
            n, tit, sub = ev[1], ev[2], ev[3]
            col = (ACCENT, ZIG2, LASER, SEEK, MAGENTA, GOLD)[n - 1]
            self._cartel(tit, sub, col)
            if n > 1:
                self.fx.destello(col)
        elif kind == "rayo_fuego":
            self.fx.shake(3)
            self.fx.burst(ev[1], ev[2], (WHITE, LASER, GOLD), n=10, speed=1.6,
                          life=16)
        elif kind == "nucleo_entra":
            self.fx.shake(6)
        elif kind == "nucleo_ataca":
            self.fx.popup(ev[1], ev[2] + 10, ATAQUE_NOMBRE[ev[3]], LASER, life=30)
        elif kind == "nucleo_pega":
            self.fx.burst(ev[1], ev[2], CHISPA_NUCLEO, n=6, speed=1.4, life=12)
        elif kind == "nucleo_enojo":
            self._cartel("¡SE ENOJÓ!", "ataca más rápido", WARN, 70)
            self.fx.shake(5)
            self.fx.destello(WARN)
        elif kind == "nucleo_cae":
            x, y, vale, bono, seg = ev[1], ev[2], ev[3], ev[4], ev[5]
            for k in range(3):
                self.fx.burst(x + (k - 1) * 16, y, CHISPA_NUCLEO + (GOLD,), n=30,
                              speed=3.2, life=40)
            self.fx.popup(x, y, "+%d" % vale, GOLD, life=60)
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
        # dos capas de estrellas: más rápidas cuanto más avanza la partida
        vel = 1 if e.slow else 2 + (1 if e.frenesi() else 0)
        fc = pyxel.frame_count
        for i in range(20):
            pyxel.pset((i * 53) % W, (i * 71 + fc * vel) % (H - HUD) + HUD, STAR2)
        for i in range(14):
            pyxel.pset((i * 97 + 13) % W,
                       (i * 41 + fc * vel * 2) % (H - HUD) + HUD, STAR)
        if e.frenesi() and (fc // 8) % 2:          # el borde late en el final
            pyxel.rectb(0, HUD, W, H - HUD, GOLD)
        for r in e.rayos:
            self._rayo(r)
        for r in e.rocks:
            self._roca(int(r[0]), int(r[1]), r[2], r[3], r[5])
        if e.jefe:
            self._jefe_dibujo(e.jefe)
        if e.nucleo:
            self._nucleo(e.nucleo)
        for gx, gy in e.gems:
            self._gema(int(gx), int(gy))
        for px_, py_, tipo in e.powers:
            self._power(int(px_), int(py_), tipo)
        for sx_, sy_ in e.shots:
            pyxel.rect(int(sx_), int(sy_), 1, 5, SHOT)
            pyxel.pset(int(sx_), int(sy_), WHITE)
        for b in e.balas:
            c = WHITE if (fc // 3) % 2 else LASER
            pyxel.circ(int(b[0]), int(b[1]), 2, LASER)
            pyxel.pset(int(b[0]), int(b[1]), c)
        self._nave(e)
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(0, HUD, W, H - HUD)
        self._dibujar_cartel()
        self._hud()

    def _rayo(self, r):
        x, aviso, fuego = int(r[0]), r[1], r[2]
        fc = pyxel.frame_count
        if aviso > 0:
            # el aviso: dos líneas punteadas y una flecha, titilando cada vez
            # más rápido a medida que se acerca el disparo
            per = 8 if aviso > 25 else 3
            on = (fc // per) % 2
            if on:
                fx.flash(LASER, 0.25, x, HUD, RAYO_W, H - HUD)
            col = LASER if on else WARN
            off = (fc // 2) % 6
            for y in range(HUD + 2 + off, H, 6):
                pyxel.rect(x, y, 1, 3, col)
                pyxel.rect(x + RAYO_W - 1, y, 1, 3, col)
            pyxel.tri(x + RAYO_W // 2 - 4, HUD + 3, x + RAYO_W // 2 + 4,
                      HUD + 3, x + RAYO_W // 2, HUD + 9, col)
            pyxel.text(x + RAYO_W // 2 - 1, HUD + 11, "!", WHITE)
            return
        k = 2 if fuego > 6 else 1
        pyxel.rect(x, HUD, RAYO_W, H - HUD, LASER)
        pyxel.rect(x + 3 - k + 1, HUD, RAYO_W - 6 + 2 * (k - 1), H - HUD, GOLD)
        pyxel.rect(x + RAYO_W // 2 - 1, HUD, 2, H - HUD, WHITE)

    def _roca(self, x, y, w, tipo, hp):
        if tipo == BUSCA:
            # un rombo con un ojo que mira hacia la nave
            cx = x + w // 2
            pyxel.tri(cx, y, x, y + OH // 2, cx, y + OH, SEEK)
            pyxel.tri(cx, y, x + w, y + OH // 2, cx, y + OH, SEEK)
            ojo = 1 if self.e.px + PW / 2 > cx else -1
            pyxel.rect(cx - 1 + ojo, y + OH // 2 - 1, 2, 2, BG)
            if (pyxel.frame_count // 5) % 2:
                pyxel.pset(cx, y - 2, SEEK)
            return
        if tipo == ZIGZAG:
            base, borde = ZIG, ZIG2
        elif tipo == DURA:
            base, borde = (HARD, HARD2) if hp > 1 else (ROCK, ROCK2)
        else:
            base, borde = ROCK, ROCK2
        pyxel.rect(x, y, w, OH, base)
        pyxel.rect(x, y, w, 1, borde)
        pyxel.rect(x, y + OH - 1, w, 1, SHADOW)
        if tipo == DURA:                       # remaches, para leerlo de un ojo
            for i in range(2, w - 2, 6):
                pyxel.pset(x + i, y + OH // 2, borde)
        elif tipo == ZIGZAG:                   # flechitas: hacia dónde va
            pyxel.line(x + 2, y + 3, x + 4, y + 5, WHITE)
            pyxel.line(x + 4, y + 5, x + 2, y + 7, WHITE)
            pyxel.line(x + w - 3, y + 3, x + w - 5, y + 5, WHITE)
            pyxel.line(x + w - 5, y + 5, x + w - 3, y + 7, WHITE)

    def _jefe_dibujo(self, j):
        x, y, hp = int(j[0]), int(j[1]), j[2]
        pyxel.rect(x, y, JEFE_W, JEFE_H, HARD)
        pyxel.rect(x, y, JEFE_W, 2, HARD2)
        pyxel.rect(x, y + JEFE_H - 2, JEFE_W, 2, SHADOW)
        for i in range(6, JEFE_W - 4, 12):      # remaches
            pyxel.rect(x + i, y + 5, 2, 2, HARD2)
            pyxel.rect(x + i, y + JEFE_H - 7, 2, 2, HARD2)
        # la barra de vida va encima: hay que saber cuánto falta
        fx.bar(x + 4, y + JEFE_H // 2 - 1, JEFE_W - 8, 3, hp / JEFE_HP,
               WARN if hp <= 2 else GEM, SHADOW)

    def _nucleo(self, n):
        x, y = int(n.x), int(n.y)
        fc = pyxel.frame_count
        body = WHITE if n.golpe else HARD
        pyxel.rect(x + 4, y, NUCLEO_W - 8, NUCLEO_H, body)
        pyxel.rect(x, y + 4, NUCLEO_W, NUCLEO_H - 8, body)
        pyxel.rect(x + 4, y, NUCLEO_W - 8, 2, HARD2)
        pyxel.rect(x + 4, y + NUCLEO_H - 2, NUCLEO_W - 8, 2, SHADOW)
        # cañones a los lados
        pyxel.rect(x + 6, y + NUCLEO_H, 4, 3, HARD2)
        pyxel.rect(x + NUCLEO_W - 10, y + NUCLEO_H, 4, 3, HARD2)
        # el ojo: blanco cuando carga un ataque, rojo si está enojado
        cx, cy = x + NUCLEO_W // 2, y + NUCLEO_H // 2
        if n.cargando and (fc // 3) % 2:
            core = WHITE
        else:
            core = WARN if n.enojado else MAGENTA
        pyxel.circ(cx, cy, 6 + (fc // 10) % 2, core)
        mira = max(-3, min(3, (self.e.px + PW / 2 - cx) / 20))
        pyxel.circ(int(cx + mira), cy + 1, 2, BG)
        # la barra de vida grande, bajo el hud
        bw = W - 40
        text(4, HUD + 3, "NÚCLEO", MAGENTA)
        fx.bar(32, HUD + 3, bw, 5, n.hp / NUCLEO_HP,
               WARN if n.enojado else MAGENTA, SHADOW, STAR2)

    def _gema(self, x, y):
        r = 2 + (pyxel.frame_count // 7) % 2
        pyxel.circ(x, y, r, GEM)
        pyxel.pset(x - 1, y - 1, GEM2)

    def _icono(self, x, y, tipo):
        """el dibujito de cada poder, de 7x7 alrededor de (x, y)."""
        if tipo == ESCUDO:
            pyxel.circb(x, y, 3, SHIELD)
            pyxel.pset(x - 1, y - 1, WHITE)
        elif tipo == RALENTI:
            pyxel.circb(x, y, 3, SLOWC)
            pyxel.line(x, y, x, y - 2, WHITE)
            pyxel.line(x, y, x + 1, y, WHITE)
        elif tipo == RAFAGA:
            pyxel.rect(x - 2, y - 3, 1, 6, SHOT)
            pyxel.rect(x + 1, y - 3, 1, 6, SHOT)
            pyxel.pset(x - 2, y - 3, WHITE)
            pyxel.pset(x + 1, y - 3, WHITE)
        elif tipo == IMAN:
            pyxel.rect(x - 3, y - 3, 2, 5, WARN)
            pyxel.rect(x + 2, y - 3, 2, 5, WARN)
            pyxel.rect(x - 3, y + 1, 7, 2, WARN)
            pyxel.rect(x - 3, y - 3, 2, 1, WHITE)
            pyxel.rect(x + 2, y - 3, 2, 1, WHITE)
        else:
            corazon(x - 3, y - 3, HEART)

    def _power(self, x, y, tipo):
        col = (SHIELD, SLOWC, SHOT, WARN, HEART)[tipo]
        pyxel.rect(x - 5, y - 5, 11, 11, SHADOW)
        pyxel.rectb(x - 6, y - 6, 13, 13, col)
        if (pyxel.frame_count // 6) % 2:
            pyxel.rectb(x - 5, y - 5, 11, 11, WHITE)
        self._icono(x, y, tipo)

    def _nave(self, e):
        fc = pyxel.frame_count
        x = int(e.px)
        cx = x + PW // 2
        if not (e.gracia and (fc // 4) % 2):       # titila mientras es intocable
            pyxel.rect(x, PLAYER_Y, PW, PH, SHIP)
            pyxel.rect(x, PLAYER_Y, PW, 1, SHIP2)
            pyxel.tri(cx - 3, PLAYER_Y, cx + 3, PLAYER_Y, cx, PLAYER_Y - 4, SHIP2)
            pyxel.rect(cx - 2, PLAYER_Y + 3, 4, 3, BG)          # cabina
            pyxel.pset(cx - 1, PLAYER_Y + 3, GEM2)
            f = 2 + (fc // 3) % 2
            pyxel.rect(x + 4, PLAYER_Y + PH, 3, f, WARN)
            pyxel.rect(x + PW - 7, PLAYER_Y + PH, 3, f, WARN)
        if e.slow:
            pyxel.circb(cx, PLAYER_Y + PH // 2, 14, SLOWC)
        if e.escudo:
            r = 15 + (fc // 8) % 2
            pyxel.circb(cx, PLAYER_Y + PH // 2, r, SHIELD)
            pyxel.pset(cx - 8, PLAYER_Y - 6, WHITE)
        if e.iman:                                 # chispas que se juntan
            rr = 24 - (fc % 16)
            for i in range(8):
                a = i * 0.785 + fc * 0.05
                pyxel.pset(int(cx + math.cos(a) * rr),
                           int(PLAYER_Y + PH // 2 + math.sin(a) * rr), GEM2)
        if e.rafaga:
            pyxel.pset(cx - 5, PLAYER_Y - 2, SHOT)
            pyxel.pset(cx + 5, PLAYER_Y - 2, SHOT)
        # sin balas: la barrita de recarga sobre la nave, para que se vea que
        # vuelve sola y cuánto falta
        if e.ammo == 0 and not e.rafaga:
            by = PLAYER_Y - 9
            col = WARN if self.vacio and (fc // 3) % 2 else SHOT
            fx.bar(cx - 11, by, 22, 2, e.carga_frac(), col, STAR2)

    def _dibujar_cartel(self):
        c = self.cartel
        if not c:
            return
        tit, sub, f, col, f0 = c
        # entra desde la izquierda y se va titilando
        dx = max(0, (f - (f0 - 10)) * 14)
        if f < 20 and (f // 3) % 2:
            return
        y = HUD + 46
        # la franja es de trama, no sólida: no te tapa lo que viene cayendo
        fx.flash(SHADOW, 0.7, 0, y - 4, W, 30 if sub else 20)
        pyxel.rect(0, y - 4, W, 1, col)
        pyxel.rect(0, y + (25 if sub else 15), W, 1, col)
        cbig(W / 2 + dx, y, tit, col, BG)
        if sub:
            ctext(W / 2 + dx, y + 16, sub, TXT)

    def _hud(self):
        e = self.e
        fc = pyxel.frame_count
        pyxel.rect(0, 0, W, HUD, PANEL)
        # el puntaje, al doble
        big(3, 3, "%d" % e.score, GOLD if e.frenesi() else ACCENT, SHADOW)
        x = 5 + big_w("%d" % e.score) + 4
        m = e.gem_mult()
        if m > 1 or e.frenesi():                   # multiplicadores
            s = "x%d" % (m * (2 if e.frenesi() else 1))
            col = GOLD if (fc // 6) % 2 else GEM2
            big(x, 3, s, col, SHADOW)
        self._poderes_hud(66)
        # las vidas, como corazones (se sacuden al perder una)
        hx = 102
        jit = ((fc % 4) - 1.5) if self.hud_golpe else 0
        for i in range(VIDAS):
            col = HEART if i < e.lives else STAR2
            if i == e.lives and self.hud_golpe and (fc // 3) % 2:
                col = WHITE
            corazon(int(hx + i * 9 + jit), 6, col)
        # el cargador: balas grandes. la que se está recargando se llena
        # desde abajo. si aprietas vacío, se sacude en rojo
        ax = 132 + ((fc % 3) - 1 if self.vacio else 0)
        for i in range(AMMO_MAX):
            bx = ax + i * 5
            if e.rafaga:
                col = SHOT if (fc // 4 + i) % 2 else GOLD
                pyxel.rect(bx, 4, 3, 10, col)
            elif i < e.ammo:
                pyxel.rect(bx, 4, 3, 10, SHOT)
                pyxel.rect(bx, 4, 3, 2, WHITE if self.recarga_fx and
                           i == e.ammo - 1 else GOLD)
            else:
                pyxel.rectb(bx, 4, 3, 10, WARN if self.vacio else DIM)
                if i == e.ammo:
                    h = int(8 * e.carga_frac())
                    if h:
                        pyxel.rect(bx + 1, 13 - h, 1, h, SHOT)
        if e.ammo == 0 and not e.rafaga and (fc // 10) % 2:
            text(ax - 1, HUD + 3 if not e.nucleo else HUD + 11, "RECARGA",
                 WARN)
        # el reloj, al doble, y la barra de tiempo a todo lo ancho
        s = e.time // 60
        urge = s <= 10
        col = WARN if urge and fc % 30 < 15 else (SLOWC if e.slow else TXT)
        r = "%d" % s
        big(W - big_w(r) - 3, 3, r, col, SHADOW)
        frac = e.time / TIME
        pyxel.rect(0, HUD - 2, W, 2, SHADOW)
        pyxel.rect(0, HUD - 2, int(W * frac), 2,
                   WARN if urge else (GOLD if e.frenesi() else ACCENT))


    def _poderes_hud(self, x):
        """los poderes activos, como íconos en el hud con su barrita de tiempo
        abajo. titilan el último segundo."""
        e = self.e
        fc = pyxel.frame_count
        for tipo, t, t0 in ((ESCUDO, 1 if e.escudo else 0, 0),
                            (RAFAGA, e.rafaga, RAFAGA_TTL),
                            (RALENTI, e.slow, SLOW_TTL),
                            (IMAN, e.iman, IMAN_TTL)):
            if not t:
                continue
            if t0 and t < 60 and (fc // 4) % 2:
                x += 9
                continue
            self._icono(x + 3, 7, tipo)
            if t0:
                fx.bar(x, 12, 7, 2, t / t0, (SHIELD, SLOWC, SHOT, WARN)[tipo],
                       STAR2)
            x += 9


class Game:
    def __init__(self):
        Cabinet(
            game_id="esquiva", title="ESQUIVA", subtitle="aguanta 100 segundos",
            howto=["arrastra o flechas mueven · fuego dispara",
                   "las balas se recargan solas",
                   "gemas seguidas valen más · rozar suma",
                   "muros, rayos y un jefe final"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=STAR),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
