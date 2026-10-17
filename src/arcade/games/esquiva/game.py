"""esquiva — aguantá 100 segundos, para el cabinet MHW · RETRO · FUTURE.

era "movete y no te toquen". ahora la partida tiene una meta y un final: durás
100 segundos y el puntaje es lo que juntás mientras tanto. lo que cambia el
juego:

- **tres vidas** en vez de morir al primer roce: se puede recuperar.
- **gemas** que caen entre los bloques. valen, pero están donde no querés estar:
  te obligan a meterte en el tráfico en vez de vivir escondido en un costado.
- **disparo con munición contada**: podés romper un bloque, pero no todos. la
  gracia es elegir cuál.
- **bloques que zigzaguean** y **bloques duros** que aguantan dos tiros.
- **poderes**: escudo (una vida), ralentí (todo se frena unos segundos) y balas.
- **rozar paga**: un bloque que pasa a un pelo de la nave sin tocarla suma. es
  el premio por no esconderse en el costado, y se siente.
- **cadena de gemas**: gemas seguidas sin que te toquen valen cada vez más
  (hasta x4). un golpe la corta.

la lógica vive en la clase Esquiva, sin pyxel: `step()` avanza un frame y
devuelve qué pasó. como el reloj sólo baja, la partida termina siempre en 100
segundos o antes, y eso se prueba sin jugar.
"""
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

W, H = 200, 220
HUD = 14
PLAYER_Y = H - 16
PW, PH = 22, 9                   # nave
OH = 10                          # alto de un bloque

TIME = 100 * 60                  # la partida entera: no hay forma de estirarla
VIDAS = 3
GRACIA = 100                     # invulnerable después de un golpe
AMMO0, AMMO_PACK, AMMO_MAX = 5, 3, 9
SHOT_V = 4.2
GEM_VALE, ROMPER_VALE = 5, 2
SLOW_TTL, SLOW_F = 5 * 60, 0.45
GEM_GAP, POWER_GAP = 3 * 60, 9 * 60
# el jefe: un muro que baja lento y hay que romperlo a tiros o esquivarlo por
# el hueco. es lo que le da forma a los 100 segundos — sabés que cada 30 viene
# uno, y guardás munición para eso.
JEFE_CADA = 30 * 60
JEFE_W, JEFE_H = 74, 16
JEFE_HP = 7
JEFE_V = 0.55
JEFE_VALE = 60
# rozar: el bloque que pasa a esta distancia (o menos) de la nave, sin tocarla
ROCE_DIST = 6
ROCE_VALE = 3
# la cadena de gemas: cada tres seguidas, la próxima vale una vez más
GEM_CADENA_CADA = 3
GEM_CADENA_MAX = 4

ROCA, ZIGZAG, DURA = range(3)
ESCUDO, RALENTI, BALAS = range(3)
POWER_NOMBRE = {ESCUDO: "¡ESCUDO!", RALENTI: "¡RALENTÍ!", BALAS: "+BALAS"}

(BG, STAR, SHIP, SHIP2, ROCK, ROCK2, TXT, DIM, ACCENT, WARN, SHADOW, WHITE,
 GEM, GEM2, SHOT, SHIELD, HARD, HARD2, ZIG, ZIG2, SLOWC, GOLD, MAGENTA,
 STAR2) = range(24)
PAL = [
    0x0C0E14, 0x1A2236, 0x8AC52F, 0xB6F03C, 0xE0842E, 0xE0402A, 0xE8ECF5,
    0x5A6480, 0x8AC52F, 0xE0402A, 0x070810, 0xF2F5FB,
    0x3AC6D8, 0xA8F0FA, 0xFFF3B0, 0x7ADCFF, 0x8A5AD0, 0xC79BF0, 0xD8483A,
    0xFF8A7A, 0x4DA6FF, 0xFFD24A, 0xD84AB8, 0x2A3350,
] + [0] * (256 - 24)

CHISPA_ROCA = (WHITE, ROCK2, ROCK, DIM)
CHISPA_GEM = (WHITE, GEM2, GEM, ACCENT)
CHISPA_GOLPE = (WHITE, WARN, ROCK2, SHADOW)


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
        self.score = 0
        self.lives = VIDAS
        self.ammo = AMMO0
        self.over = False
        self.spawn_t = 0
        self.gem_t = GEM_GAP
        self.power_t = POWER_GAP
        self.gracia = 0
        self.slow = 0
        self.jefe = None             # [x, y, hp, vx]
        self.jefe_t = JEFE_CADA
        self.time = TIME
        self.esquivados = 0
        self.roces = 0
        self.gem_cadena = 0

    # --- dificultad ------------------------------------------------------
    def level(self):
        """el nivel lo marca el reloj, no el puntaje: la presión sube igual
        aunque juegues a lo seguro y no sumes nada."""
        return (TIME - self.time) // (20 * 60) + 1

    def speed(self):
        v = min(5.2, 1.6 + (TIME - self.time) * 0.0007)
        return v * (SLOW_F if self.slow else 1.0)

    def _spawn_gap(self):
        return max(13, 40 - (TIME - self.time) // 90)

    def set_player(self, x):
        self.px = min(W - PW, max(0, x))

    def gem_mult(self):
        return min(GEM_CADENA_MAX, 1 + self.gem_cadena // GEM_CADENA_CADA)

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

    def disparar(self):
        if self.ammo > 0 and not self.over:
            self.ammo -= 1
            self.shots.append([self.px + PW / 2, PLAYER_Y - 4])
            return True
        return False

    # --- un frame --------------------------------------------------------
    def step(self):
        ev = []
        if self.over:
            return ev
        if self.gracia:
            self.gracia -= 1
        if self.slow:
            self.slow -= 1

        self._spawnear()
        ev += self._jefe()
        v = self.speed()
        ev += self._mover_balas()
        ev += self._mover_rocas(v)
        ev += self._mover_gemas(v)
        ev += self._mover_poderes(v)

        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("aguantaste", 0, 0))
        return ev

    def _spawnear(self):
        self.spawn_t -= 1
        if self.spawn_t <= 0:
            w = self.rng.choice((12, 16, 22))
            tipo = ROCA
            r = self.rng.random()
            if r < 0.18 + 0.04 * self.level():
                tipo = ZIGZAG
            elif r > 0.90:
                tipo = DURA
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
                                self.rng.randrange(3)])
            self.power_t = POWER_GAP + self.rng.randrange(120)

    def _jefe(self):
        """el muro: baja despacio, se corre de lado y aguanta varios tiros."""
        ev = []
        if self.jefe is None:
            self.jefe_t -= 1
            if self.jefe_t <= 0:
                self.jefe_t = JEFE_CADA
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

    def _mover_balas(self):
        ev = []
        quedan = []
        for s in self.shots:
            s[1] -= SHOT_V
            if s[1] < HUD - 6:
                continue
            pegó = False
            j = self.jefe
            if j is not None and j[0] <= s[0] <= j[0] + JEFE_W \
                    and j[1] <= s[1] <= j[1] + JEFE_H:
                j[2] -= 1
                if j[2] <= 0:
                    self.score += JEFE_VALE
                    ev.append(("jefe_cae", j[0] + JEFE_W / 2, j[1] + JEFE_H / 2))
                    self.jefe = None
                    # el jefe suelta lo que te hace falta para el próximo
                    self.powers.append([j[0] + JEFE_W / 2, j[1], BALAS])
                else:
                    ev.append(("raspa", s[0], s[1], ROCA))
                continue
            for r in self.rocks:
                if r[0] <= s[0] <= r[0] + r[2] and r[1] <= s[1] <= r[1] + OH:
                    r[5] -= 1
                    pegó = True
                    if r[5] <= 0:
                        self.score += ROMPER_VALE
                        ev.append(("rompe", r[0] + r[2] / 2, r[1] + OH / 2, r[3]))
                        self.rocks.remove(r)
                    else:
                        ev.append(("raspa", s[0], s[1], r[3]))
                    break
            if not pegó:
                quedan.append(s)
        self.shots = quedan
        return ev

    def _golpe(self, x, y, ev):
        """te tocaron: perdés una vida y quedás invulnerable un rato."""
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
        for r in self.rocks:
            r[1] += v
            if r[3] == ZIGZAG:
                r[0] += r[4] * (SLOW_F if self.slow else 1.0)
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
                self.score += ROCE_VALE
                self.roces += 1
                lado = r[0] + r[2] if r[0] + r[2] <= self.px else r[0]
                ev.append(("roce", lado, PLAYER_Y + PH / 2))
            if r[1] > H:
                self.score += 1
                self.esquivados += 1
            else:
                quedan.append(r)
        self.rocks = quedan
        return ev

    def _mover_gemas(self, v):
        ev = []
        quedan = []
        for g in self.gems:
            g[1] += v * 0.82                        # caen algo más lento
            if self._toca(g[0] - 3, g[1] - 3, 6, 6):
                vale = GEM_VALE * self.gem_mult()
                self.score += vale
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
        if tipo == ESCUDO:
            self.lives = min(VIDAS, self.lives + 1)
        elif tipo == RALENTI:
            self.slow = SLOW_TTL
        else:
            self.ammo = min(AMMO_MAX, self.ammo + AMMO_PACK)
        ev.append(("power", self.px + PW / 2, PLAYER_Y, tipo))


class World:
    def __init__(self):
        self.e = Esquiva()
        self.fx = fx.Fx(gravity=0.06)
        self.lvl = 1
        self.levelflash = 0
        self.fx.destello(WHITE)
        self.use_mouse = False        # gana el último input que hayas usado
        self._lm = None

    @property
    def over(self):
        return self.e.over

    @property
    def score(self):
        return self.e.score

    def update(self):
        e = self.e
        mx = pyxel.mouse_x
        if self._lm is not None and mx != self._lm:
            self.use_mouse = True
        self._lm = mx
        left = pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A)
        right = pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D)
        if left or right:
            self.use_mouse = False
        if self.use_mouse:
            e.set_player(mx - PW / 2)
        elif left:
            e.set_player(e.px - 3.4)
        elif right:
            e.set_player(e.px + 3.4)
        if pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_UP) \
                or pyxel.btnp(pyxel.KEY_W) or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if e.disparar():
                self.fx.burst(e.px + PW / 2, PLAYER_Y - 4, (WHITE, SHOT, ACCENT),
                              n=4, speed=1.0, life=10, spread=1.2, angle=-1.5708)
        self.levelflash = max(0, self.levelflash - 1)
        for ev in e.step():
            self._efecto(ev)
        if e.level() != self.lvl:
            self.lvl = e.level()
            self.levelflash = 30
            self.fx.popup(W / 2, H / 2, "NIVEL %d" % self.lvl, GOLD)
        self.fx.update()

    def _efecto(self, ev):
        kind = ev[0]
        if kind == "gema":
            vale = ev[3] if len(ev) > 3 else GEM_VALE
            self.fx.burst(ev[1], ev[2], CHISPA_GEM, n=14, speed=1.7, life=24)
            self.fx.popup(ev[1], ev[2] - 8, "+%d" % vale, GEM2)
        elif kind == "cadena":
            self.fx.popup(ev[1], ev[2] - 18, "¡CADENA x%d!" % ev[3], GOLD)
            self.fx.destello(GEM)
        elif kind == "cadena_rota":
            self.fx.popup(W / 2, PLAYER_Y - 24, "cadena rota", DIM)
        elif kind == "roce":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, SHIP2), n=6, speed=1.2,
                          life=14, spread=1.0,
                          angle=-1.5708)
            self.fx.popup(ev[1], ev[2] - 12, "¡cerca! +%d" % ROCE_VALE, GOLD,
                          life=26)
        elif kind == "rompe":
            self.fx.burst(ev[1], ev[2], CHISPA_ROCA, n=18, speed=2.0, life=22)
            self.fx.popup(ev[1], ev[2] - 6, "+%d" % ROMPER_VALE, WHITE)
            self.fx.shake(2)
        elif kind == "raspa":
            self.fx.burst(ev[1], ev[2], (WHITE, HARD2, HARD), n=6, speed=1.4,
                          life=12)
        elif kind == "golpe":
            self.fx.burst(ev[1], ev[2], CHISPA_GOLPE, n=30, speed=2.6, life=30)
            self.fx.shake(6)
            self.fx.destello(WARN)
        elif kind == "power":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, MAGENTA), n=20, speed=2.2,
                          life=26)
            self.fx.popup(ev[1], ev[2] - 14, POWER_NOMBRE[ev[3]], GOLD)
            self.fx.destello(GOLD)
        elif kind == "jefe_entra":
            self.fx.popup(W / 2, H / 2 - 20, "¡MURO!", HARD2)
            self.fx.destello(HARD2)
            self.fx.shake(4)
        elif kind == "jefe_cae":
            self.fx.burst(ev[1], ev[2], (WHITE, HARD2, HARD, GEM), n=40,
                          speed=3.0, life=36)
            self.fx.popup(ev[1], ev[2], "+%d" % JEFE_VALE, GOLD)
            self.fx.shake(8)
            self.fx.destello(GOLD)
        elif kind == "aguantaste":
            self.fx.popup(W / 2, H / 2, "¡AGUANTASTE!", ACCENT)

    def draw(self):
        e = self.e
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        # dos capas de estrellas: la de atrás lenta, la de adelante rápida
        vel = 1 if e.slow else 2
        for i in range(20):
            pyxel.pset((i * 53) % W,
                       (i * 71 + pyxel.frame_count * vel) % (H - HUD) + HUD, STAR2)
        for i in range(14):
            pyxel.pset((i * 97 + 13) % W,
                       (i * 41 + pyxel.frame_count * vel * 2) % (H - HUD) + HUD,
                       STAR)
        for r in e.rocks:
            self._roca(int(r[0]), int(r[1]), r[2], r[3], r[5])
        if e.jefe:
            self._jefe_dibujo(e.jefe)
        for gx, gy in e.gems:
            self._gema(int(gx), int(gy))
        for px_, py_, tipo in e.powers:
            self._power(int(px_), int(py_), tipo)
        for sx_, sy_ in e.shots:
            pyxel.rect(int(sx_), int(sy_), 1, 4, SHOT)
        self._nave(e)
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(0, HUD, W, H - HUD)
        self._hud()

    def _roca(self, x, y, w, tipo, hp):
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
        elif tipo == ZIGZAG:
            pyxel.pset(x + w // 2, y + OH // 2, WHITE)

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

    def _gema(self, x, y):
        r = 2 + (pyxel.frame_count // 7) % 2
        pyxel.circ(x, y, r, GEM)
        pyxel.pset(x - 1, y - 1, GEM2)

    def _power(self, x, y, tipo):
        col = (SHIELD, SLOWC, SHOT)[tipo]
        pyxel.rectb(x - 5, y - 5, 11, 11, col)
        pyxel.rectb(x - 4, y - 4, 9, 9, WHITE if (pyxel.frame_count // 6) % 2
                    else SHADOW)
        if tipo == ESCUDO:
            pyxel.rect(x - 2, y - 3, 5, 4, col)
            pyxel.pset(x, y + 2, col)
        elif tipo == RALENTI:
            pyxel.circb(x, y, 3, col)
            pyxel.line(x, y, x, y - 2, col)
        else:
            pyxel.rect(x - 1, y - 3, 2, 6, col)

    def _nave(self, e):
        if e.gracia and (pyxel.frame_count // 4) % 2:
            return                                 # titila mientras es intocable
        x = int(e.px)
        pyxel.rect(x, PLAYER_Y, PW, PH, SHIP)
        pyxel.rect(x, PLAYER_Y, PW, 1, SHIP2)
        pyxel.tri(x + PW // 2 - 3, PLAYER_Y, x + PW // 2 + 3, PLAYER_Y,
                  x + PW // 2, PLAYER_Y - 4, SHIP2)
        # llama del motor, latiendo
        f = 2 + (pyxel.frame_count // 3) % 2
        pyxel.rect(x + 4, PLAYER_Y + PH, 3, f, WARN)
        pyxel.rect(x + PW - 7, PLAYER_Y + PH, 3, f, WARN)
        if e.slow:
            pyxel.circb(x + PW // 2, PLAYER_Y + PH // 2, 14, SLOWC)

    def _hud(self):
        e = self.e
        pyxel.rect(0, 0, W, HUD, SHADOW)
        text(4, 4, "%d" % e.score, ACCENT)
        for i in range(VIDAS):                     # las vidas, como navecitas
            col = SHIP if i < e.lives else DIM
            pyxel.tri(38 + i * 9, 9, 44 + i * 9, 9, 41 + i * 9, 3, col)
        m = e.gem_mult()
        if m > 1:                                  # la cadena de gemas
            col = GOLD if (pyxel.frame_count // 6) % 2 else GEM
            text(104, 4, "x%d" % m, col)
        for i in range(AMMO_MAX):                  # y la munición, como balas
            if i < e.ammo:
                pyxel.rect(74 + i * 3, 4, 1, 5, SHOT)
            else:
                pyxel.pset(74 + i * 3, 8, DIM)
        s = e.time // 60
        col = WHITE if s <= 10 and pyxel.frame_count % 30 < 15 else \
            (SLOWC if e.slow else TXT)
        r = "%ds" % s
        text(W - len(r) * 4 - 4, 4, r, col)
        fx.bar(W - 62, 4, 26, 5, e.time / TIME, ACCENT if not e.slow else SLOWC,
               STAR2)


class Game:
    def __init__(self):
        Cabinet(
            game_id="esquiva", title="ESQUIVA", subtitle="aguantá 100 segundos",
            howto=["mouse o flechas mueven · espacio dispara",
                   "las gemas valen, y seguidas valen más",
                   "rozar un bloque sin que te toque suma",
                   "tres vidas · la munición se cuenta"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=STAR),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
