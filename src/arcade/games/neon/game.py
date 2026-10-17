"""neón — shoot'em up vertical para el cabinet MHW · RETRO · FUTURE.

el futuro, como se veía en 1985: vuelas sobre una grilla de neón hacia un sol
a rayas, y todo lo que aparece en el horizonte te dispara. es el único juego
del cabinet en formato vertical (180x320): en el celular parado llena la
pantalla, y se juega con un dedo:

- **trackpad**: el dedo se arrastra en la zona de controles y la nave se mueve
  lo mismo arriba, sin taparla. el disparo es **automático**, siempre.
- **bomba**: borra todas las balas (y cada una deja un cristal), lastima a
  todos y te deja intocable un segundo y medio. se cuentan.
- **foco** (opcional): la nave va lenta, el fuego se junta adelante y se ve el
  hitbox con un anillo. el hitbox es un puntito siempre visible: lo que choca
  es eso, no el dibujo entero.

lo que hace emocionante una partida de 100 segundos:

- **roces**: pasar a un pelo de una bala paga, alarga la cadena y carga la
  bomba. el juego premia meterse en el baile, no esconderse.
- **cadena x1..x8**: matar y rozar la sube; si pasan unos segundos sin nada,
  cae de a un escalón; un golpe la corta entera.
- **arma 1..4**: las naves nodriza y algunos escuadrones sueltan una P. el
  golpe la baja un nivel.
- **cristales**: todo lo que muere los suelta y vuelan solos a la nave. romper
  una fase del jefe convierte su lluvia de balas en una lluvia de cristales.
- **el guion**: oleadas -> mini-jefe CENTINELA -> oleadas -> ¡PELIGRO! ->
  OCASO-85, el jefe final de tres fases. si lo matas antes del segundo 104,
  cada segundo que sobra paga.

la lógica pura vive en `logic.py` (testeable sin ventana); acá sólo está la
piel: input, dibujo y jugo.
"""
import math

import pyxel

from pixelkit import fx, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

from games.neon import art
from games.neon.art import (BG, BLUE, CYAN, CYAN_D, DEEP, DIM, GOLD, GREEN,
                            GRID, GRID2, HULL, HULL2, HY, MAG_D, MAGENTA,
                            MOUNT_V, MOUNT_W, ORANGE, PAL, PINK, RED, SHADOW,
                            SKY2, SKY3, SKY4, STAR, SUN1, SUN2, SUN3, TXT,
                            VIOLET, WHITE, YELLOW)
from games.neon.logic import (BOMBS_MAX, CARRIER, DART, FINAL,
                              GRAZE_PER_BOMB, H, HUD_H, ITEM_P, KAMI, MINI,
                              MINI_TIME, MULT_MAX, P_FOCUS, P_MAX, P_SPEED,
                              SEC_BOSS, SEC_END, SEC_WARN, TURRET, WEAVER, W,
                              Neon)

RESULTS_T = 300               # cuánto se ven los resultados antes de terminar
RESULTS_SKIP = 100            # desde acá un toque los salta
DRAG_MAX = 9.0                # px por frame que la nave sigue al dedo

ALL_COLS = tuple(range(1, 32))
RAMP_FIRE = (WHITE, YELLOW, ORANGE, RED, MAG_D)
RAMP_PINK = (WHITE, PINK, MAGENTA, MAG_D)
RAMP_CYAN = (WHITE, CYAN, CYAN_D, BLUE)
RAMP_VIO = (WHITE, PINK, VIOLET, MAG_D)
RAMP_GOLD = (WHITE, YELLOW, GOLD, ORANGE)
FOE_RAMP = {DART: RAMP_PINK, WEAVER: RAMP_VIO, KAMI: RAMP_FIRE,
            TURRET: RAMP_CYAN, CARRIER: RAMP_FIRE}
LIGHTEN = ((HULL, HULL2), (HULL2, STAR), (DEEP, HULL), (MAG_D, MAGENTA),
           (CYAN_D, CYAN))
MULT_COL = {1: DIM, 2: CYAN, 3: CYAN, 4: MAGENTA, 5: MAGENTA, 6: ORANGE,
            7: ORANGE, 8: YELLOW}


def say(x, y, s, col):
    """pxtext.text que además entiende el ¡ (la fuente de pyxel no lo trae)."""
    if "¡" not in s:
        text(x, y, s, col)
        return
    text(x, y, s.replace("¡", " "), col)
    i = s.find("¡")
    while i >= 0:
        gx = x + i * 4
        pyxel.pset(gx + 1, y, col)
        pyxel.rect(gx + 1, y + 2, 1, 3, col)
        i = s.find("¡", i + 1)


def csay(cx, y, s, col):
    say(int(cx - len(s) * 2), y, s, col)


def backdrop(a, scroll, par=0.0, danger=False):
    """el fondo: cielo, sol a rayas, cordillera de alambre y la grilla que
    avanza. `par` corre el punto de fuga con la nave (paralaje), `danger`
    pone el sol rojo."""
    art.bake_background()
    pyxel.blt(0, 0, 1, 0, 0, W, HY, None)
    # estrellas que titilan
    for i in range(10):
        if (a // 9 + i * 5) % 7 == 0:
            pyxel.pset((i * 67 + 11) % W, 24 + (i * 37) % 70, WHITE)
    # el sol
    cx = W / 2 - par * 0.06
    cy = HY - 26
    R = 38
    c1, c2, c3 = (SUN1, SUN2, SUN3) if not danger else (SUN3, RED, MAG_D)
    off = (a // 4) % 8
    y0 = int(cy - R)
    for y in range(y0, HY):
        dy = y - cy
        if dy * dy >= R * R:
            continue
        if dy > -10:
            # las franjas: más gruesas cuanto más abajo, y bajando
            gap = 1 + int((dy + 10) / 12)
            if (y + off) % 8 < gap:
                continue
        hw = math.sqrt(R * R - dy * dy)
        t = (y - y0) / (2 * R)
        col = c1 if t < 0.36 else c2 if t < 0.62 else c3
        pyxel.line(cx - hw, y, cx + hw, y, col)
    # la cordillera
    pyxel.blt(int(-25 - par * 0.12), HY - 32, 1, 0, MOUNT_V, MOUNT_W, 32, 0)
    # el piso
    pyxel.rect(0, HY, W, H - HY, DEEP)
    vx = W / 2 - par * 0.3
    K = H - HY
    d = 1.0 - scroll % 1.0
    while True:
        y = HY + K / (d if d > 0.05 else 0.05)
        if y - HY < 5:
            break
        if y < H:
            pyxel.line(0, y, W, y, GRID2 if y > HY + 60 else
                       GRID if y > HY + 12 else SKY3)
        d += 1.0
    for k in range(-9, 10):
        pyxel.line(vx + k * 3, HY, vx + k * 34, H, GRID)
    pyxel.line(0, HY, W, HY, MAGENTA if not danger else RED)
    pyxel.line(0, HY + 1, W, HY + 1, MAG_D)


class BigText:
    """carteles grandes: el texto se escribe una vez en el banco 2 y se
    estampa agrandado con `blt(..., scale=)`, que es un solo llamado."""

    def __init__(self):
        self.img = pyxel.images[2]
        self.cache = {}
        self.row = 0

    def _get(self, s, col):
        key = (s, col)
        r = self.cache.get(key)
        if r is None:
            if self.row >= 24:          # 240+ es del logo del título
                self.cache.clear()
                self.row = 0
            v = self.row * 10
            self.img.rect(0, v, 256, 10, 0)
            art.img_text(self.img, 0, v + 3, s, col)
            r = (v, len(s) * 4)
            self.cache[key] = r
            self.row += 1
        return r

    def draw(self, cx, cy, s, col, scale=2, shadow=SHADOW):
        v, w = self._get(s, col)
        x = cx - w / 2
        y = cy - 5
        if shadow is not None:
            sv, _ = self._get(s, shadow)
            pyxel.blt(x + scale, y + scale, 2, 0, sv, w, 10, 0, scale=scale)
            pyxel.blt(x, y + scale, 2, 0, sv, w, 10, 0, scale=scale)
        pyxel.blt(x, y, 2, 0, v, w, 10, 0, scale=scale)


class World:
    def __init__(self):
        self.spr = art.bake_all()
        self.big = BigText()
        self.g = Neon()
        self.fx = fx.Fx(gravity=0.02, max_parts=360)
        self.blasts = []          # [x, y, rmax, vida, vida0, rampa]
        self.rings = []           # [x, y, r, dr, vida, col]
        self.msgs = []            # [texto, col, vida, vida0, y, escala, sub]
        self.anim = 0             # reloj de dibujo (sigue aunque la lógica pare)
        self.scroll = 0.0
        self.stop = 0             # congelado de impacto
        self.slow = 0             # cámara lenta
        self.res_t = 0
        self._over = False
        self.pend = [0.0, 0.0]
        self.mlast = None
        self.graze_ring = 0
        self.mult_bump = 0
        self.last_mult = 1
        self.crys_acc = 0
        self.crys_t = 0
        self.warn = 0
        self.bomb_q = 0           # una bomba pedida en un frame congelado
        self.say_msg("¡DESPEGUE!", CYAN, 90, sub="esquiva · roza · sobrevive")

    @property
    def over(self):
        return self._over

    @property
    def score(self):
        return self.g.score

    # --- input -----------------------------------------------------------------
    def _input(self):
        g = self.g
        focus = (pyxel.btn(pyxel.KEY_LSHIFT) or pyxel.btn(pyxel.KEY_RSHIFT)
                 or pyxel.btn(pyxel.KEY_Z))
        kx = (pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D)) \
            - (pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A))
        ky = (pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S)) \
            - (pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W))
        sp = P_FOCUS if focus else P_SPEED
        if kx and ky:
            sp *= 0.7071
        mx, my = kx * sp, ky * sp
        # el trackpad de la página y, en la pantalla, arrastrar el mouse o el
        # dedo: las dos cosas son movimiento relativo
        dx, dy = web.drag()
        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            m = (pyxel.mouse_x, pyxel.mouse_y)
            if self.mlast is not None:
                dx += m[0] - self.mlast[0]
                dy += m[1] - self.mlast[1]
            self.mlast = m
        else:
            self.mlast = None
        p = self.pend
        p[0] += dx
        p[1] += dy
        for i in (0, 1):
            step = max(-DRAG_MAX, min(DRAG_MAX, p[i]))
            p[i] -= step                # lo que sobra llega en los próximos
            if i == 0:
                mx += step
            else:
                my += step
        bomb = (pyxel.btnp(pyxel.KEY_X) or pyxel.btnp(pyxel.KEY_SPACE)
                or pyxel.btnp(pyxel.KEY_C))
        if g.done:
            return 0.0, 0.0, False, False
        return mx, my, focus, bomb

    def _skip_pressed(self):
        return (pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE)
                or pyxel.btnp(pyxel.KEY_X) or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT))

    # --- un frame --------------------------------------------------------------
    def update(self):
        g = self.g
        inp = self._input()
        if inp[3]:
            self.bomb_q = 10
        elif self.bomb_q:
            self.bomb_q -= 1
        if g.done:
            self.res_t += 1
            self._tick_fx()
            if self.res_t >= RESULTS_T or (self.res_t >= RESULTS_SKIP
                                           and self._skip_pressed()):
                self._over = True
            return
        # el congelado de impacto y la cámara lenta frenan la partida, no el
        # jugo: las chispas y el destello siguen a velocidad normal
        if self.stop:
            self.stop -= 1
            self._tick_fx()
            return
        if self.slow:
            self.slow -= 1
            if self.slow % 3:
                self._tick_fx()
                return
        for ev in g.step(inp[0], inp[1], inp[2], self.bomb_q > 0):
            self._event(ev)
        self.bomb_q = 0
        m = g.mult()
        if m > self.last_mult:
            self.mult_bump = 16
            if m >= 4:
                self.fx.popup(g.px, g.py - 22, "x%d" % m, MULT_COL[m], life=30)
        self.last_mult = m
        if self.crys_t:
            self.crys_t -= 1
            if self.crys_t == 0 and self.crys_acc:
                self.fx.popup(g.px + 12, g.py - 12, "+%d" % self.crys_acc, GOLD,
                              life=26)
                self.crys_acc = 0
        b = g.boss
        if b is not None and b.state in ("fight", "break"):
            self._boss_damage(b)
        if g.sec == SEC_WARN:
            self.warn += 1
            if self.warn % 40 == 1:
                self.fx.shake(2)
        self._tick_fx()

    def _boss_damage(self, b):
        """el jefe se va rompiendo a la vista: chispas de las alas en la fase
        2, y en la furia humo y chispas por todos lados."""
        t = self.g.t
        if b.kind == MINI:
            if b.hp < b.hp0 * 0.4 and t % 7 == 0:
                s = -17 if (t // 7) % 2 else 17
                self.fx.burst(b.x + s, b.y + 2, (YELLOW, ORANGE, RED), n=2,
                              speed=1.2, life=12)
            return
        if b.phase >= 1 and t % 6 == 0:
            s = -1 if (t // 6) % 2 else 1
            self.fx.burst(b.x + s * 30, b.y + 4, (WHITE, YELLOW, ORANGE, RED),
                          n=2, speed=1.4, life=14)
        if b.phase >= 2 and t % 4 == 0:
            self.fx.burst(b.x + ((t * 7) % 30) - 15, b.y + ((t * 3) % 20) - 10,
                          (HULL2, HULL, SHADOW), n=1, speed=0.5, life=24,
                          angle=-math.pi / 2, spread=1.0, gravity=-0.03)

    def _tick_fx(self):
        self.fx.update()
        keep = []
        for b in self.blasts:
            b[3] -= 1
            if b[3] > 0:
                keep.append(b)
        self.blasts = keep
        keep = []
        for r in self.rings:
            r[2] += r[3]
            r[4] -= 1
            if r[4] > 0:
                keep.append(r)
        self.rings = keep
        if self.graze_ring:
            self.graze_ring -= 1
        if self.mult_bump:
            self.mult_bump -= 1
        self._tick_msgs()

    def _tick_msgs(self):
        keep = []
        for m in self.msgs:
            m[2] -= 1
            if m[2] > 0:
                keep.append(m)
        self.msgs = keep

    # --- efectos ---------------------------------------------------------------
    def say_msg(self, s, col, life=80, y=150, scale=2, sub=None):
        self.msgs = [m for m in self.msgs if m[4] != y]
        self.msgs.append([s, col, life, life, y, scale, sub])

    def blast(self, x, y, r, life=18, ramp=RAMP_FIRE):
        if len(self.blasts) < 40:
            self.blasts.append([x, y, r, life, life, ramp])

    def ring(self, x, y, r, dr, life, col):
        if len(self.rings) < 24:
            self.rings.append([x, y, r, dr, life, col])

    def _event(self, ev):
        k = ev[0]
        g = self.g
        f = self.fx
        if k == "spark":
            f.burst(ev[1], ev[2], (WHITE, CYAN, CYAN_D), n=2, speed=1.2, life=7,
                    spread=1.6, angle=-math.pi / 2)
        elif k == "kill":
            x, y, kind, pts = ev[1], ev[2], ev[3], ev[4]
            big = kind in (TURRET, CARRIER)
            f.burst(x, y, FOE_RAMP[kind], n=26 if big else 12,
                    speed=2.6 if big else 1.8, life=26 if big else 18)
            self.blast(x, y, 16 if kind == CARRIER else 11 if big else 6,
                       life=22 if big else 14)
            if big:
                self.ring(x, y, 4, 2.2, 14, ORANGE)
                f.shake(4 if kind == CARRIER else 3)
                f.popup(x, y - 6, "%d" % pts, YELLOW, life=40)
            elif pts >= 400:
                f.popup(x, y - 4, "%d" % pts, MULT_COL[min(8, g.mult())], life=24)
        elif k == "pop":
            self.blast(ev[1], ev[2], 8, 16)
            f.burst(ev[1], ev[2], RAMP_FIRE, n=12, speed=2.0, life=16)
        elif k == "graze":
            f.burst(ev[1], ev[2], (WHITE, YELLOW, GOLD), n=2 + ev[3], speed=1.3,
                    life=10)
            self.graze_ring = 8
        elif k == "crys":
            self.crys_acc += ev[2]
            if not self.crys_t:
                self.crys_t = 24
            f.burst(g.px, g.py, (WHITE, YELLOW, GOLD), n=min(3, ev[1]),
                    speed=1.0, life=8)
        elif k == "hit":
            x, y = ev[1], ev[2]
            self.blast(x, y, 20, 30)
            self.ring(x, y, 2, 3.5, 20, WHITE)
            f.burst(x, y, (WHITE, CYAN, MAGENTA, MAG_D), n=50, speed=3.0, life=36)
            f.shake(8)
            f.destello(RED, 6)
            self.stop = 8
            if ev[3] > 0:
                self.say_msg("¡IMPACTO!", RED, 60, y=150,
                             sub="quedan %d" % ev[3] if ev[3] > 1 else "¡última vida!")
            if ev[4] >= 3:
                f.popup(W / 2, 180, "cadena rota (x%d)" % ev[4], DIM, life=50)
        elif k == "respawn":
            self.ring(ev[1], ev[2], 30, -1.5, 18, CYAN)
        elif k == "bomb":
            self.ring(ev[1], ev[2], 4, 6.0, 40, WHITE)
            self.ring(ev[1], ev[2], 2, 4.5, 46, MAGENTA)
            self.ring(ev[1], ev[2], 0, 3.0, 50, CYAN)
            f.destello(WHITE, 6)
            f.shake(5)
            f.burst(ev[1], ev[2], RAMP_PINK, n=40, speed=3.4, life=30)
        elif k == "cancel":
            pass
        elif k == "power":
            f.burst(ev[1], ev[2], (WHITE, GREEN, CYAN), n=24, speed=2.4, life=24)
            self.ring(ev[1], ev[2], 4, 2.0, 16, GREEN)
            s = "ARMA MAX" if ev[3] >= P_MAX else "ARMA %d" % ev[3]
            f.popup(ev[1], ev[2] - 18, s, GREEN, life=50)
        elif k == "pmax":
            f.burst(ev[1], ev[2], (WHITE, GREEN, YELLOW), n=18, speed=2.0, life=20)
            f.popup(ev[1], ev[2] - 18, "+%d" % ev[3], GREEN, life=46)
        elif k == "bomb_gain":
            f.popup(ev[1], ev[2] - 24, "+BOMBA", MAGENTA, life=50)
            self.ring(ev[1], ev[2], 4, 2.0, 16, MAGENTA)
        elif k == "bomb_full":
            f.popup(ev[1], ev[2] - 24, "+%d" % ev[3], MAGENTA, life=40)
        elif k == "squad":
            f.popup(ev[1], ev[2] + 8, "ESCUADRÓN %d" % ev[3], GOLD, life=50)
        elif k == "boss_in":
            if ev[1] == MINI:
                self.say_msg("¡ALERTA!", ORANGE, 110, y=150, sub="se acerca CENTINELA")
                f.shake(3)
            else:
                self.say_msg("OCASO-85", RED, 100, y=150, scale=3,
                             sub="el sol se pone en tu contra")
                f.shake(6)
                f.destello(RED, 6)
        elif k == "peligro":
            self.warn = 0
        elif k == "phase":
            x, y = ev[2], ev[3]
            self.stop = 10
            f.shake(9)
            f.destello(WHITE, 6)
            for i in range(5):
                self.blast(x + (i - 2) * 12, y + (i % 2) * 6, 12, 24 + i * 3)
            self.ring(x, y, 6, 3.0, 24, YELLOW)
            f.burst(x, y, RAMP_FIRE, n=60, speed=3.2, life=34)
            name = "FASE 2" if ev[1] == 1 else "¡FURIA!"
            self.say_msg(name, YELLOW if ev[1] == 1 else RED, 90, y=150,
                         scale=3 if ev[1] == 2 else 2, sub="+%d" % ev[4])
        elif k == "boss_kill":
            x, y = ev[1], ev[2]
            self.stop = 12
            self.slow = 100 if ev[3] == FINAL else 45
            f.shake(10)
            f.destello(WHITE, 6)
            self.ring(x, y, 6, 2.5, 30, WHITE)
            f.popup(x, y + 22, "+%d" % ev[4], YELLOW, life=70)
        elif k == "boss_boom":
            self.blast(ev[1], ev[2], 10 if ev[3] == MINI else 14, 20)
            f.burst(ev[1], ev[2], RAMP_FIRE, n=14, speed=2.4, life=22)
            f.shake(3)
        elif k == "boss_dead":
            x, y = ev[1], ev[2]
            big = ev[3] == FINAL
            for i in range(9 if big else 5):
                a = i * 0.7
                self.blast(x + math.cos(a) * i * 4, y + math.sin(a) * i * 3,
                           26 if big else 16, 30 + i * 4)
            self.ring(x, y, 8, 4.0, 40, WHITE)
            self.ring(x, y, 4, 3.0, 46, YELLOW)
            self.ring(x, y, 2, 2.0, 50, MAGENTA)
            f.burst(x, y, RAMP_FIRE, n=90 if big else 50, speed=4.0, life=44)
            f.burst(x, y, RAMP_PINK, n=50 if big else 20, speed=2.6, life=40)
            f.shake(14 if big else 9)
            f.destello(WHITE, 8)
            if big:
                self.say_msg("¡VICTORIA!", YELLOW, 160, y=150, scale=3,
                             sub="OCASO-85 derribado")
            else:
                self.say_msg("¡ABATIDO!", CYAN, 90, y=150, sub="CENTINELA cae")
        elif k == "flee":
            self.say_msg("SE ESCAPÓ", DIM, 70, y=150, sub="CENTINELA se retira")
        elif k == "fin":
            if ev[1] == "derribado":
                self.say_msg("DERRIBADO", RED, 200, y=150, scale=3)
            elif ev[1] == "escapo":
                self.say_msg("¡TIEMPO!", ORANGE, 200, y=150, scale=3,
                             sub="OCASO-85 se escapa")
        elif k == "results":
            self.res_t = 0

    # --- dibujo -----------------------------------------------------------------
    def draw(self):
        g = self.g
        self.anim += 1
        if not (self.stop or (self.slow and self.slow % 3)):
            boost = 1.9 if g.sec in (SEC_WARN, SEC_BOSS) else 1.0
            self.scroll += 0.028 * boost
        sx, sy = self.fx.offset()
        pyxel.camera(-sx, -sy)
        self._background()
        self._draw_items()
        self._draw_foes()
        self._draw_boss()
        self._draw_shots()
        self._draw_player()
        self._draw_crystals()
        self.fx.draw(0, 0)
        self._draw_blasts()
        self._draw_bullets()
        self._draw_hitbox()
        pyxel.camera()
        self._draw_warn()
        self.fx.draw_flash(0, 0, W, H)
        self._draw_msgs()
        self._hud()
        if g.done:
            self._draw_results()

    # el fondo: cielo, sol a rayas, cordillera de alambre y la grilla que avanza
    def _background(self):
        g = self.g
        danger = g.sec in (SEC_WARN, SEC_BOSS) or (g.sec == SEC_END and
                                                    g.ending != "victoria")
        backdrop(self.anim, self.scroll, g.px - W / 2, danger)

    def _blt(self, name, x, y, white=False):
        u, v, w, h = self.spr[name]
        pyxel.blt(int(x - w // 2), int(y - h // 2), 0, u + (w + 1 if white else 0),
                  v, w, h, 0)

    def _draw_items(self):
        for x, y, vy, kind, t in self.g.items:
            name = "item_p" if kind == ITEM_P else "item_b"
            self._blt(name, x, y, white=(t // 6) % 4 == 0)
            say(int(x) - 1, int(y) - 2, "P" if kind == ITEM_P else "B", SHADOW)

    def _draw_foes(self):
        a = self.anim
        for f in self.g.foes:
            if f.wait:
                continue
            k = f.kind
            fl = f.flash > 0
            if k == DART:
                self._blt("dart", f.x, f.y, fl)
            elif k == WEAVER:
                self._blt("weaver", f.x, f.y, fl)
            elif k == KAMI:
                if 50 <= f.t < 90:              # el aviso: línea y titileo
                    ca, sa = math.cos(f.a), math.sin(f.a)
                    col = RED if (a // 3) % 2 else ORANGE
                    run = (a % 8)                # las rayas avanzan hacia ti
                    for i in range(8, 220, 10):
                        d0 = i + run
                        pyxel.line(f.x + ca * d0, f.y + sa * d0,
                                   f.x + ca * (d0 + 5), f.y + sa * (d0 + 5), col)
                    say(int(f.x) - 1, int(f.y) - 13, "!", YELLOW if (a // 4) % 2
                        else RED)
                    fl = fl or (a // 4) % 2 == 0
                elif f.t >= 90:
                    pyxel.line(f.x, f.y, f.x - math.cos(f.a) * 8,
                               f.y - math.sin(f.a) * 8, ORANGE)
                self._blt("kami", f.x, f.y, fl)
            elif k == TURRET:
                self._turret(f, fl)
            elif k == CARRIER:
                self._carrier(f, fl)

    def _turret(self, f, fl):
        x, y = int(f.x), int(f.y)
        if fl:
            pyxel.circ(x, y, 8, WHITE)
            return
        pyxel.circ(x, y, 8, SHADOW)
        pyxel.circ(x, y, 7, HULL)
        pyxel.circb(x, y, 7, HULL2)
        for i in range(4):
            a = f.b + i * math.pi / 2
            pyxel.line(x + math.cos(a) * 3, y + math.sin(a) * 3,
                       x + math.cos(a) * 9, y + math.sin(a) * 9, CYAN)
        pyxel.circ(x, y, 3, MAG_D)
        pyxel.circ(x, y, 2, MAGENTA if (self.anim // 5) % 2 else PINK)
        pyxel.pset(x, y, WHITE)
        pyxel.circb(x, y, 8, CYAN_D)

    def _carrier(self, f, fl):
        x, y = int(f.x), int(f.y)
        if fl:
            pyxel.pal()
            for c in ALL_COLS:
                pyxel.pal(c, WHITE)
        # cuerpo
        pyxel.tri(x - 13, y - 6, x + 13, y - 6, x, y + 10, SHADOW)
        pyxel.rect(x - 13, y - 9, 27, 7, SHADOW)
        pyxel.rect(x - 12, y - 8, 25, 5, HULL)
        pyxel.tri(x - 11, y - 4, x + 11, y - 4, x, y + 8, HULL)
        pyxel.line(x - 12, y - 8, x + 12, y - 8, HULL2)
        pyxel.line(x - 11, y - 4, x, y + 8, ORANGE)
        pyxel.line(x + 11, y - 4, x, y + 8, ORANGE)
        # góndolas
        for s in (-1, 1):
            gx = x + s * 11
            pyxel.rect(gx - 3, y - 11, 7, 10, SHADOW)
            pyxel.rect(gx - 2, y - 10, 5, 8, HULL2)
            pyxel.rect(gx - 1, y - 3, 3, 3, RED if (self.anim // 4) % 2 else ORANGE)
        # puente
        pyxel.rect(x - 4, y - 7, 9, 4, BLUE)
        pyxel.rect(x - 3, y - 6, 7, 1, CYAN)
        pyxel.pset(x, y + 2, YELLOW)
        if fl:
            pyxel.pal()
        if f.hp < f.hp0 // 3 and (self.anim // 3) % 2:
            pyxel.pset(x - 6 + (self.anim % 12), y - 2, ORANGE)

    def _draw_boss(self):
        b = self.g.boss
        if b is None:
            return
        # al jefe le pegan casi todos los frames: un destello blanco entero lo
        # dejaría blanco siempre. se aclara de a ratos, y blanco sólo al morir
        fl = False
        if b.state == "die" and (self.anim // 2) % 2:
            fl = True
            for c in ALL_COLS:
                pyxel.pal(c, WHITE)
        elif b.flash and (self.anim // 2) % 2:
            fl = True
            for c, d in LIGHTEN:
                pyxel.pal(c, d)
        if b.kind == MINI:
            self._mini(b)
        else:
            self._final(b)
        if fl:
            pyxel.pal()

    def _mini(self, b):
        """CENTINELA: un rombo con dos cañones y un ojo que te sigue."""
        x, y = int(b.x), int(b.y)
        a = self.anim
        g = self.g
        pyxel.tri(x - 22, y - 2, x, y - 13, x + 22, y - 2, SHADOW)
        pyxel.tri(x - 22, y - 2, x, y + 12, x + 22, y - 2, SHADOW)
        pyxel.tri(x - 20, y - 2, x, y - 11, x + 20, y - 2, HULL2)
        pyxel.tri(x - 20, y - 2, x, y + 10, x + 20, y - 2, HULL)
        pyxel.line(x - 20, y - 2, x, y - 11, CYAN)
        pyxel.line(x + 20, y - 2, x, y - 11, CYAN)
        pyxel.line(x - 20, y - 2, x, y + 10, MAGENTA)
        pyxel.line(x + 20, y - 2, x, y + 10, MAGENTA)
        for s in (-17, 17):
            pyxel.rect(x + s - 3, y - 3, 7, 9, SHADOW)
            pyxel.rect(x + s - 2, y - 2, 5, 7, MAG_D)
            pyxel.rect(x + s - 1, y + 3, 3, 3, ORANGE if (a // 4) % 2 else YELLOW)
        # el ojo
        pyxel.circ(x, y - 1, 6, SHADOW)
        pyxel.circ(x, y - 1, 5, DEEP)
        ang = math.atan2(g.py - y, g.px - x)
        ex, ey = x + math.cos(ang) * 2.5, y - 1 + math.sin(ang) * 2.5
        pyxel.circ(ex, ey, 3, CYAN)
        pyxel.circ(ex, ey, 1, WHITE)

    def _final(self, b):
        """OCASO-85: una nave que carga su propio sol a rayas."""
        x, y = int(b.x), int(b.y)
        a = self.anim
        ph = b.phase
        wing = 0 if ph < 2 else 6                # en furia las alas quedan rotas
        # alas
        for s in (-1, 1):
            pyxel.tri(x + s * 8, y - 12, x + s * (40 - wing), y + 4,
                      x + s * 10, y + 14, SHADOW)
            pyxel.tri(x + s * 9, y - 10, x + s * (37 - wing), y + 3,
                      x + s * 10, y + 12, HULL)
            pyxel.line(x + s * 9, y - 10, x + s * (37 - wing), y + 3, MAGENTA)
            pyxel.line(x + s * (37 - wing), y + 3, x + s * 10, y + 12, MAG_D)
            gx = x + s * 28
            pyxel.rect(gx - 4, y + 2, 9, 11, SHADOW)
            pyxel.rect(gx - 3, y + 3, 7, 9, HULL2)
            hot = ORANGE if (a // 3) % 2 else YELLOW
            pyxel.rect(gx - 2, y + 9, 5, 3, hot if ph != 2 else RED)
            pyxel.line(gx - 3, y + 3, gx + 3, y + 3, CYAN)
        # cuerpo
        pyxel.rect(x - 16, y - 18, 33, 30, SHADOW)
        pyxel.rect(x - 15, y - 17, 31, 28, HULL)
        pyxel.rect(x - 15, y - 17, 31, 3, HULL2)
        pyxel.tri(x - 15, y + 11, x + 15, y + 11, x, y + 20, SHADOW)
        pyxel.tri(x - 13, y + 11, x + 13, y + 11, x, y + 18, HULL)
        pyxel.line(x - 15, y - 14, x - 15, y + 10, CYAN_D)
        pyxel.line(x + 15, y - 14, x + 15, y + 10, CYAN_D)
        pyxel.line(x - 12, y + 12, x, y + 18, CYAN)
        pyxel.line(x + 12, y + 12, x, y + 18, CYAN)
        # el sol del núcleo, con sus franjas bajando
        r = 11
        cols = (SUN1, SUN2, SUN3) if ph == 0 else (SUN2, SUN3, MAGENTA) \
            if ph == 1 else (RED, SUN3, MAG_D)
        pyxel.circ(x, y - 2, r + 1, SHADOW)
        off = (a // 3) % 5
        for yy in range(-r, r + 1):
            if yy > -3 and (yy + off) % 5 == 0:
                continue
            hw = math.sqrt(max(0, r * r - yy * yy))
            t = (yy + r) / (2 * r)
            col = cols[0] if t < 0.4 else cols[1] if t < 0.7 else cols[2]
            pyxel.line(x - hw, y - 2 + yy, x + hw, y - 2 + yy, col)
        if ph == 2:                               # grietas de la furia
            pyxel.line(x - 6, y - 10, x - 1, y - 2, SHADOW)
            pyxel.line(x + 4, y + 6, x + 1, y - 1, SHADOW)
        # luces
        for i in range(5):
            on = (a // 6 + i) % 5 == 0
            pyxel.pset(x - 12 + i * 6, y - 15, CYAN if on else CYAN_D)

    def _draw_shots(self):
        u, v, w, h = self.spr["shot"]
        blt = pyxel.blt
        for x, y, vx in self.g.shots:
            blt(int(x) - 1, int(y) - 3, 0, u, v, w, h, 0)

    def _draw_player(self):
        g = self.g
        if g.done and g.ending == "victoria":
            fly = self.res_t * self.res_t * 0.02
            if g.py - fly < -20:
                return
            py = g.py - fly
        else:
            py = g.py
        if not g.alive():
            return
        if g.inv and (self.anim // 3) % 2:
            return
        x = g.px
        a = self.anim
        # llama del motor
        fl = 3 + (a // 2) % 3
        pyxel.tri(x - 2, py + 7, x + 2, py + 7, x, py + 7 + fl + 2, CYAN_D)
        pyxel.tri(x - 1, py + 7, x + 1, py + 7, x, py + 7 + fl, WHITE)
        if a % 3 == 0 and not g.done:
            self.fx.burst(x, py + 9, (CYAN, CYAN_D, BLUE), n=1, speed=1.2,
                          life=10, spread=0.5, angle=math.pi / 2)
        self._blt("ship", x, py + 1)
        for ox, oy in g.options():
            oy = oy + (py - g.py)
            self._blt("option", ox, oy + math.sin(a / 8 + ox) * 1.2)
        if self.graze_ring:
            pyxel.circb(x, py, 10 - self.graze_ring // 3, YELLOW)

    def _draw_hitbox(self):
        g = self.g
        if not g.alive() or g.done:
            return
        x, y = int(g.px), int(g.py)
        if g.focus:
            pyxel.circb(x, y, 4, WHITE if (self.anim // 4) % 2 else MAGENTA)
            pyxel.rect(x - 1, y - 1, 3, 3, MAGENTA)
            pyxel.pset(x, y, WHITE)
        else:
            pyxel.rect(x - 1, y - 1, 3, 3, SHADOW)
            pyxel.pset(x, y, WHITE)
        if g.bomb_t:
            r = 14 + (self.anim % 6)
            pyxel.circb(x, y, r, MAGENTA if (self.anim // 2) % 2 else CYAN)

    def _draw_crystals(self):
        u, v, w, h = self.spr["crys"]
        blt = pyxel.blt
        a = self.anim // 4
        for c in self.g.crys:
            blt(int(c[0]) - 2, int(c[1]) - 2, 0, u + (w + 1 if (a + int(c[0])) % 5 == 0
                                                       else 0), v, w, h, 0)

    def _draw_blasts(self):
        for x, y, r, life, life0, ramp in self.blasts:
            t = 1.0 - life / life0
            rr = r * (0.35 + 0.65 * math.sqrt(t))
            i = min(len(ramp) - 1, int(t * len(ramp)))
            if t < 0.55:
                pyxel.circ(x, y, rr, ramp[i])
                if t < 0.3:
                    pyxel.circ(x, y, rr * 0.5, WHITE)
            else:
                pyxel.circb(x, y, rr, ramp[i])
        for x, y, r, dr, life, col in self.rings:
            if r > 0:
                pyxel.circb(x, y, r, col)

    def _draw_bullets(self):
        spr = self.spr
        flip = (self.anim // 6) % 2
        tbl = (spr["pellet2" if flip else "pellet"], spr["fast2" if flip else "fast"],
               spr["orb2" if flip else "orb"])
        blt = pyxel.blt
        for b in self.g.eb:
            u, v, w, h = tbl[b[4]]
            blt(int(b[0]) - (w >> 1), int(b[1]) - (h >> 1), 0, u, v, w, h, 0)

    def _draw_warn(self):
        g = self.g
        if g.sec != SEC_WARN:
            return
        a = self.warn
        on = (a // 10) % 2 == 0
        # cintas de peligro arriba y abajo del cartel
        for yb in (124, 172):
            pyxel.rect(0, yb, W, 9, SHADOW)
            off = (a // 2) % 12
            for i in range(-1, W // 12 + 2):
                x0 = i * 12 - off
                col = YELLOW if on else ORANGE
                pyxel.tri(x0, yb + 8, x0 + 6, yb + 8, x0 + 10, yb + 1, col)
                pyxel.tri(x0, yb + 8, x0 + 10, yb + 1, x0 + 4, yb + 1, col)
            pyxel.line(0, yb, W, yb, RED)
            pyxel.line(0, yb + 9, W, yb + 9, RED)
        if on or a > 150:
            self.big.draw(W / 2, 150, "¡PELIGRO!", RED if on else WHITE, scale=3)
        csay(W / 2, 162, "se acerca un jefe", WHITE if on else PINK)
        if a % 30 < 4:
            fx.flash(RED, 0.12, 0, HUD_H, W, H - HUD_H)

    def _draw_msgs(self):
        for s, col, life, life0, y, scale, sub in self.msgs:
            el = life0 - life
            if life < 14 and (life // 2) % 2:
                continue
            sc = scale + 1 if el < 5 else scale     # entra grande y se asienta
            self.big.draw(W / 2, y, s, col, scale=sc)
            if sub and el > 6:
                yy = y + 6 * scale + 2
                pyxel.rect(W / 2 - len(sub) * 2 - 3, yy - 2, len(sub) * 4 + 5, 9,
                           SHADOW)
                csay(W / 2, yy, sub, TXT)

    # --- hud -----------------------------------------------------------------
    def _hud(self):
        g = self.g
        a = self.anim
        pyxel.rect(0, 0, W, HUD_H, DEEP)
        pyxel.line(0, HUD_H - 1, W, HUD_H - 1, MAGENTA)
        pyxel.line(0, HUD_H, W, HUD_H, MAG_D)
        # puntaje: los ceros de adelante apagados
        sc = g.score if not g.done else self._rolling_score()
        s = "%07d" % min(9999999, sc)
        nz = len(s) - len(str(sc)) if sc else 6
        text(3, 3, s[:nz], SKY4)
        text(3 + nz * 4, 3, s[nz:], WHITE)
        # vidas
        for i in range(max(0, g.lives)):
            self._blt("life", 6 + i * 8, 13)
        # arma: P y cuatro rayitas
        text(30, 11, "P", GREEN)
        for i in range(P_MAX):
            col = GREEN if i < g.power else HULL
            pyxel.rect(35 + i * 4, 11, 3, 5, col)
        # multiplicador, grande, al centro
        m = g.mult()
        col = MULT_COL[m]
        if m == MULT_MAX and (a // 4) % 2:
            col = WHITE
        sc = 3 if self.mult_bump > 10 else 2
        self.big.draw(W / 2, 9, "x%d" % m, col, scale=sc)
        fx.bar(W / 2 - 13, 16, 26, 2, g.chain_frac() if m > 1 or g.chain else 0,
               col, HULL)
        # reloj
        secs = g.time_left()
        tcol = TXT
        if secs <= 10 and (a // 15) % 2:
            tcol = RED
        elif g.sec in (SEC_WARN, SEC_BOSS) and secs <= 20:
            tcol = ORANGE
        ts = "%d" % secs
        tx = W - 3 - len(ts) * 4
        text(tx, 3, ts, tcol)
        pyxel.circb(tx - 6, 5, 3, CYAN)
        pyxel.line(tx - 6, 5, tx - 6, 3, CYAN)
        pyxel.line(tx - 6, 5, tx - 5, 5, CYAN)
        # bombas y la carga por roces
        for i in range(BOMBS_MAX):
            bx = W - 6 - i * 8
            if i < g.bombs:
                pyxel.circ(bx, 12, 3, MAGENTA)
                pyxel.pset(bx - 1, 11, PINK)
            else:
                pyxel.circb(bx, 12, 3, HULL)
        fx.bar(W - 33, 17, 30, 1, g.graze_meter / GRAZE_PER_BOMB, YELLOW, HULL)
        text(W - 33 - 22, 11, "BOMBA", MAGENTA if g.bombs else DIM)
        self._boss_bar()

    def _boss_bar(self):
        g = self.g
        b = g.boss
        if b is None or b.state in ("leave",):
            return
        y = HUD_H + 3
        name = "CENTINELA" if b.kind == MINI else "OCASO-85"
        pyxel.rect(0, y - 2, W, 9, SHADOW)
        say(3, y, name, ORANGE if b.kind == MINI else RED)
        left = len(b.phases) - b.phase - 1
        x0 = 3 + len(name) * 4 + 3
        for i in range(left):                    # las fases que faltan
            pyxel.rect(x0 + i * 5, y + 1, 3, 3, YELLOW)
        x0 += left * 5 + 2
        frac = b.hp / b.hp0 if b.state != "die" else 0
        if b.state == "enter":
            frac = min(1.0, b.st / 100)
        col = RED if (b.kind == FINAL and b.phase == 2) else MAGENTA
        if b.flash:
            col = WHITE
        fx.bar(x0, y, W - 3 - x0, 5, frac, col, HULL, border=None)
        if b.kind == MINI and b.state == "fight":
            rest = max(0, (MINI_TIME - b.t) / MINI_TIME)
            pyxel.rect(x0, y + 5, int((W - 3 - x0) * rest), 1, DIM)

    # --- resultados ------------------------------------------------------------
    def _rolling_score(self):
        r = self.g.results
        t = max(0, self.res_t - 40)
        k = min(1.0, t / 120)
        return int(r["base"] + (r["total"] - r["base"]) * k)

    def _draw_results(self):
        g = self.g
        r = g.results
        t = self.res_t
        y0, h = 27, 98
        grow = min(1.0, t / 12)
        hh = int(h * grow)
        top = y0 + (h - hh) // 2
        pyxel.rect(10, top + 3, W - 20, hh, SHADOW)
        pyxel.rect(8, top, W - 16, hh, DEEP)
        pyxel.rectb(8, top, W - 16, hh, CYAN)
        pyxel.rectb(9, top + 1, W - 18, max(0, hh - 2), MAG_D)
        if grow < 1.0:
            return
        end = r["ending"]
        title = {"victoria": "MISIÓN CUMPLIDA", "escapo": "EL JEFE ESCAPÓ",
                 "derribado": "DERRIBADO"}[end]
        tcol = {"victoria": YELLOW, "escapo": ORANGE, "derribado": RED}[end]
        csay(W / 2, y0 + 7, title, tcol)
        pyxel.line(20, y0 + 15, W - 20, y0 + 15, MAG_D)
        rows = [("enemigos", "%d" % r["kills"], TXT),
                ("roces", "%d" % r["grazes"], TXT),
                ("cadena máxima", "x%d" % r["max_mult"], MULT_COL[r["max_mult"]])]
        if end == "victoria":
            rows.append(("tiempo %ds" % r["time_s"], "+%d" % r["time_bonus"], YELLOW))
            rows.append(("vidas", "+%d" % r["life_bonus"], GREEN))
        if r["bomb_bonus"]:
            rows.append(("bombas", "+%d" % r["bomb_bonus"], MAGENTA))
        y = y0 + 21
        for i, (label, val, col) in enumerate(rows):
            if t < 18 + i * 10:
                break
            text(18, y, label, DIM)
            text(W - 18 - len(val) * 4, y, val, col)
            y += 9
        if t >= 18 + len(rows) * 10:
            pyxel.line(20, y0 + h - 18, W - 20, y0 + h - 18, MAG_D)
            text(18, y0 + h - 12, "TOTAL", WHITE)
            s = "%d" % self._rolling_score()
            text(W - 18 - len(s) * 4, y0 + h - 12, s,
                 YELLOW if (t // 6) % 2 else WHITE)
        if t >= RESULTS_SKIP and not self._over and (t // 20) % 2:
            hint = "toca para seguir" if web.is_touch() else "enter para seguir"
            csay(W / 2, y0 + h + 6, hint, DIM)


LOGO = [
    "...................XX",
    "..................XX.",
    "XX...XX.XXXXXX..XXXXX..XX...XX",
    "XXX..XX.XX.....XX...XX.XXX..XX",
    "XXXX.XX.XX.....XX...XX.XXXX.XX",
    "XX.XXXX.XXXXX..XX...XX.XX.XXXX",
    "XX..XXX.XX.....XX...XX.XX..XXX",
    "XX...XX.XX.....XX...XX.XX...XX",
    "XX...XX.XXXXXX..XXXXX..XX...XX",
]
# el degradé cromado de los ochenta: cielo arriba, horizonte blanco, ocaso abajo
LOGO_RAMP = (WHITE, WHITE, CYAN, CYAN, WHITE, PINK, MAGENTA, MAG_D, MAG_D)


def _logo():
    """el logo NEÓN, dibujado a mano (la N de la fuente de pyxel parece una
    n chica al agrandarla) y horneado al pie del banco 2, debajo de los
    carteles: la versión con degradé y una sombra plana."""
    if _LOGO:
        return _LOGO[0]
    img = pyxel.images[2]
    img.rect(0, 240, 256, 16, 0)
    w = max(len(r) for r in LOGO)
    for y, row in enumerate(LOGO):
        for x, ch in enumerate(row):
            if ch == "X":
                img.pset(x, 240 + y, LOGO_RAMP[y])
                img.pset(40 + x, 240 + y, MAG_D)
                img.pset(80 + x, 240 + y, SHADOW)
    _LOGO.append(w)
    return w


_LOGO = []


class NeonCabinet(Cabinet):
    """el Cabinet de siempre; sólo cambia el dibujo del título, para que la
    portada sea la misma escena synthwave del juego y no una lista sobre
    negro. si algo de esto fallara (el Cabinet cambia por dentro), vuelve al
    título de fábrica."""

    def _draw_title(self):
        try:
            self._neon_title()
        except Exception:
            super()._draw_title()

    def _neon_title(self):
        from pixelkit import scores
        a = self.anim
        backdrop(a, a * 0.03)
        w = _logo()
        cx = W / 2
        csay(cx, 26, self.subtitle, PINK)
        # el logo, con extrusión, sombra y un brillo que cruza de vez en cuando
        sc = 4
        lx = cx - w / 2 + 0.5
        y = 52
        pyxel.blt(lx + 3, y + 6, 2, 80, 240, w, 9, 0, scale=sc)
        pyxel.blt(lx, y + 3, 2, 40, 240, w, 9, 0, scale=sc)
        # de vez en cuando el tubo de neón parpadea, como un letrero de verdad
        k = a % 210
        if not (k in (0, 1, 2, 7, 8) or 12 <= k < 14):
            pyxel.blt(lx, y, 2, 0, 240, w, 9, 0, scale=sc)
        if self._blink(24):
            go = "toca para jugar" if web.is_touch() else "enter para jugar"
            pyxel.rect(cx - len(go) * 2 - 6, 116, len(go) * 4 + 11, 11, SHADOW)
            pyxel.rectb(cx - len(go) * 2 - 6, 116, len(go) * 4 + 11, 11, MAGENTA)
            csay(cx, 119, go, WHITE)
        # cómo se juega, sobre un vidrio oscuro para que se lea encima de la grilla
        n = len(self.howto)
        top = 150
        fx.flash(SHADOW, 0.75, 8, top - 6, W - 16, n * 10 + 10)
        pyxel.rectb(8, top - 6, W - 16, n * 10 + 10, MAG_D)
        for i, line in enumerate(self.howto):
            csay(cx, top + i * 10, line, TXT)
        # la nave, flotando
        bob = math.sin(a / 18) * 2
        u, v, sw, sh = art.bake_all()["ship"]
        py = 236 + bob
        fl = 3 + (a // 2) % 3
        pyxel.tri(cx - 2, py + 7, cx + 2, py + 7, cx, py + 9 + fl, CYAN_D)
        pyxel.tri(cx - 1, py + 7, cx + 1, py + 7, cx, py + 7 + fl, WHITE)
        pyxel.blt(cx - sw // 2, py - sh // 2 + 1, 0, u, v, sw, sh, 0)
        # los mejores
        lst = scores.top(self.id, 3)
        if lst:
            yy = 262
            fx.flash(SHADOW, 0.75, 30, yy - 4, W - 60, 40)
            csay(cx, yy, "mejores", DIM)
            for i, e in enumerate(lst):
                csay(cx, yy + 10 + i * 9, "%d  %s  %7d" % (i + 1, e["ini"], e["score"]),
                     YELLOW if i == 0 else TXT)


class Game:
    def __init__(self):
        NeonCabinet(
            game_id="neon", title="NEÓN",
            subtitle="el futuro, como se veía en 1985",
            howto=["dispara solo · arrastra o usa flechas",
                   "rozar balas paga y carga la bomba",
                   "la bomba (x) borra todas las balas",
                   "mata seguido: la cadena sube a x8",
                   "100 segundos · un jefe al final"],
            width=W, height=H, palette=PAL, scale=2,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=CYAN, warn=MAGENTA,
                        shadow=SHADOW, panel=SKY2),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
