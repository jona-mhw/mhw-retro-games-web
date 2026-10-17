"""neón, la lógica: sin pyxel, para poder probarla y medirla sin ventana.

`Neon.step(mx, my, focus, bomb)` avanza un frame con el input ya leído (cuánto
se quiere mover la nave en px, si el foco está apretado y si se pidió bomba) y
devuelve la lista de eventos del frame, que la piel (game.py) convierte en
chispas, carteles y temblores.

la partida es un guion con reloj duro:

    oleadas A (~37 s) -> mini-jefe (máx 16 s) -> oleadas B (18 s)
    -> ¡PELIGRO! (3 s) -> jefe final, hasta el segundo 104 como mucho

matar al mini-jefe rápido adelanta el resto; matar al jefe final antes del 104
paga bono por cada segundo que sobra. pase lo que pase, `t` sólo sube y a los
104 s el jefe se va: la partida no se puede estirar.

las balas enemigas son listas planas [x, y, vx, vy, tipo, rozada, acel] en una
sola lista: en el peor momento hay ~300 y un objeto por bala costaría el doble.
"""
import math
import random

W, H = 180, 320
HUD_H = 20
FPS = 60

T_END = 104 * FPS            # a esta hora el jefe se va, lo hayas matado o no
END_DELAY = 100              # frames entre el final y los resultados

# --- la nave -------------------------------------------------------------------
P_SPEED = 2.4                # px/frame con teclado
P_FOCUS = 1.2                # con foco: lento y preciso
HIT_R = 1.5                  # el hitbox es un puntito: lo que choca es el centro
GRAZE_R = 10                 # una bala a menos de esto, sin tocarte, es un roce
LIVES = 3
INVULN = 150                 # después de reaparecer
DEAD_T = 55                  # frames sin nave después de un golpe
BOMBS0, BOMBS_MAX = 2, 4
BOMB_T = 100                 # cuánto dura la bomba (invulnerable y borrando)
BOMB_CLEAR = 55              # los primeros frames de la bomba siguen borrando
BOMB_DMG, BOMB_BOSS_DMG = 30, 45
GRAZE_PER_BOMB = 45          # roces para ganar una bomba
FIRE_EVERY = 5
SHOT_V = 8.0
MAX_SHOTS = 90
P_MAX = 4                    # nivel de arma

# --- puntaje ------------------------------------------------------------------
CRYSTAL_V = 10               # cada cristal, por el multiplicador
GRAZE_V = 20                 # cada roce, por el multiplicador
SQUAD_V = 300                # escuadrón entero derribado, por el multiplicador
PMAX_V = 3000                # un P con el arma al máximo
MINI_V = 15000
PHASE_V = 5000
BOSS_V = 40000
TIME_BONUS = 1500            # por segundo que sobra al matar al jefe
LIFE_BONUS = 10000           # por vida que queda al final (si ganas)
BOMB_BONUS = 3000            # por bomba sin usar al final
CHAIN_STEP = 12              # puntos de cadena por nivel de multiplicador
MULT_MAX = 8
CHAIN_T = 200                # sin matar ni rozar, la cadena empieza a caer
CRYS_MAX = 160

# --- balas enemigas -------------------------------------------------------------
PELLET, FAST, ORB = range(3)
BR = (2.0, 2.0, 3.5)                              # radio de cada tipo
HIT2 = tuple((r + HIT_R) ** 2 for r in BR)
GRAZE2 = tuple((r + GRAZE_R) ** 2 for r in BR)
MAX_EB = 340                                      # tope duro de balas en pantalla

# --- enemigos -------------------------------------------------------------------
DART, WEAVER, KAMI, TURRET, CARRIER = range(5)
#            hp   hw  hh   vale  cristales
FOE = {DART:    (3, 5, 4, 100, 1),
       WEAVER:  (6, 6, 5, 150, 2),
       KAMI:    (2, 4, 4, 120, 1),
       TURRET:  (34, 8, 8, 600, 5),
       CARRIER: (80, 13, 9, 1500, 10)}
FIRE_MAX_Y = H * 0.6         # nadie dispara desde muy abajo: sería injusto

# --- items ----------------------------------------------------------------------
ITEM_P, ITEM_B = range(2)
ITEM_MAGNET2 = 28 ** 2

# --- jefes ----------------------------------------------------------------------
MINI, FINAL = range(2)
MINI_HP = 560
MINI_TIME = 16 * FPS         # si no lo matas en esto, se va
FINAL_HP = (560, 660, 760)   # tres fases, una barra cada una
BOSS_ENTER = 110

# --- secciones del guion ----------------------------------------------------------
SEC_A, SEC_MINI, SEC_B, SEC_WARN, SEC_BOSS, SEC_END = range(6)
WARN_T = 180
LEN_A = 2250
LEN_B = 1080

# el guion: (frame dentro de la sección, qué, argumentos). las formaciones
# varían a propósito: enjambres en V que se abren, trenes que serpentean,
# murciélagos que cruzan, kamikazes que avisan antes de tirarse, torretas que
# se plantan a dibujar anillos y naves nodriza que sueltan el arma.
SCRIPT_A = [
    (70, "swarm", (90, 0, 5, 1)),
    (220, "swarm", (50, 1, 5, 0)),
    (330, "swarm", (130, -1, 5, 0)),
    (450, "weavers", (1, 4, 74)),
    (560, "kamis", (3,)),
    (680, "carrier", (90, 1)),
    (900, "swarm", (45, 1, 5, 0)),
    (900, "swarm", (135, -1, 5, 1)),
    (1060, "turret", (40, 92, 0)),
    (1060, "turret", (140, 92, 0)),
    (1250, "weavers", (-1, 5, 112)),
    (1330, "kamis", (4,)),
    (1420, "train", (34, 1, 7)),
    (1530, "carrier", (60, 1)),
    (1530, "train", (146, -1, 6)),
    (1720, "turret", (90, 78, 1)),
    (1780, "swarm", (40, 1, 5, 0)),
    (1850, "swarm", (140, -1, 5, 0)),
    (1920, "weavers", (1, 4, 62)),
    (1980, "weavers", (-1, 4, 140)),
    (2050, "kamis", (5,)),
]
SCRIPT_B = [
    (60, "turret", (46, 74, 1)),
    (60, "turret", (134, 74, 1)),
    (210, "swarm", (90, 0, 7, 0)),
    (340, "kamis", (5,)),
    (430, "carrier", (50, 1)),
    (430, "carrier", (130, 0)),
    (620, "train", (28, 1, 8)),
    (680, "train", (152, -1, 8)),
    (790, "weavers", (1, 5, 84)),
    (790, "weavers", (-1, 5, 132)),
    (900, "turret", (90, 100, 0)),
    (900, "kamis", (4,)),
    (1000, "swarm", (50, 1, 5, 0)),
    (1030, "swarm", (130, -1, 5, 1)),
]

TAU = math.tau


class Foe:
    """un enemigo. son pocos (menos de 30), así que acá sí vale un objeto."""

    __slots__ = ("kind", "x", "y", "vx", "vy", "hp", "hp0", "hw", "hh", "value",
                 "crys", "t", "wait", "squad", "flash", "mode", "a", "b", "c",
                 "ty", "fire", "burst", "drop", "dead")

    def __init__(self, kind, x, y, squad=-1, wait=0, mode=0):
        hp, hw, hh, value, crys = FOE[kind]
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.hp = self.hp0 = hp
        self.hw, self.hh = hw, hh
        self.value, self.crys = value, crys
        self.t = 0
        self.wait = wait             # frames antes de entrar (trenes)
        self.squad = squad
        self.flash = 0
        self.mode = mode
        self.a = self.b = self.c = 0.0
        self.ty = 0.0
        self.fire = 0
        self.burst = 0
        self.drop = -1
        self.dead = False


class Boss:
    __slots__ = ("kind", "x", "y", "hp", "hp0", "phase", "phases", "t", "state",
                 "st", "flash", "a", "hw", "hh", "x0", "fire", "leaving")

    def __init__(self, kind):
        self.kind = kind
        self.x, self.y = W / 2, -40.0
        self.phases = (MINI_HP,) if kind == MINI else FINAL_HP
        self.phase = 0
        self.hp = self.hp0 = self.phases[0]
        self.t = 0                   # frames en la fase actual
        self.state = "enter"         # enter, fight, break, die, leave
        self.st = 0                  # frames en el estado actual
        self.flash = 0
        self.a = 0.0
        self.hw, self.hh = (20, 10) if kind == MINI else (32, 16)
        self.x0 = W / 2
        self.fire = 0
        self.leaving = False

    def vulnerable(self):
        return self.state == "fight"


class Neon:
    """la partida entera. `step()` avanza un frame y devuelve los eventos."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.reset()

    def reset(self):
        self.t = 0
        self.px, self.py = W / 2, H - 40.0
        self.lives = LIVES
        self.bombs = BOMBS0
        self.power = 1
        self.inv = 90                 # un respiro al empezar
        self.dead_t = 0
        self.bomb_t = 0
        self.focus = False
        self.fire_t = 0
        self.shots = []               # [x, y, vx]
        self.eb = []                  # balas enemigas, ver arriba
        self.foes = []
        self.items = []               # [x, y, vy, tipo, t]
        self.crys = []                # [x, y, vx, vy, t]
        self.boss = None
        self.score = 0
        self.chain = 0.0
        self.chain_t = 0
        self.graze_meter = 0
        self.sec = SEC_A
        self.sec_t = 0
        self.script_i = 0
        self.squads = {}              # id -> [vivos, total, suelta P, x, y]
        self.squad_n = 0
        self.done = False             # terminó: la piel muestra los resultados
        self.ending = None            # "victoria", "escapo", "derribado"
        self.end_t = 0
        self.results = None
        self.boss_killed_at = None
        # estadísticas para la pantalla de resultados
        self.kills = 0
        self.grazes = 0
        self.max_mult = 1
        self.bombs_used = 0
        self.hits = 0
        self.crys_got = 0

    # --- consultas ----------------------------------------------------------------
    def mult(self):
        return min(MULT_MAX, 1 + int(self.chain // CHAIN_STEP))

    def chain_frac(self):
        """lo que falta para que la cadena empiece a caer, de 0 a 1."""
        return self.chain_t / CHAIN_T

    def alive(self):
        return self.dead_t == 0 and self.lives > 0

    def time_left(self):
        """segundos de reloj que quedan (el reloj de la partida entera)."""
        return max(0, (T_END - self.t) // FPS)

    def vulnerable(self):
        return self.alive() and self.inv == 0 and self.bomb_t == 0

    # --- un frame -----------------------------------------------------------------
    def step(self, mx=0.0, my=0.0, focus=False, bomb=False):
        ev = []
        if self.done:
            return ev
        self.t += 1
        self.focus = bool(focus)
        self._player(mx, my, bomb, ev)
        self._section(ev)
        self._step_foes(ev)
        self._step_boss(ev)
        self._step_shots(ev)
        self._step_bullets(ev)
        self._step_items(ev)
        self._step_crystals(ev)
        self._step_chain()
        if self.sec != SEC_END and self.t >= T_END:
            self._finish("escapo", ev)
        if self.sec == SEC_END:
            self.end_t += 1
            if self.end_t >= END_DELAY and not self.done:
                self._results(ev)
        return ev

    # --- la nave --------------------------------------------------------------------
    def _player(self, mx, my, bomb, ev):
        if self.inv:
            self.inv -= 1
        if self.bomb_t:
            self.bomb_t -= 1
            if self.bomb_t > BOMB_T - BOMB_CLEAR and self.eb:
                self._cancel(ev, crystals=True)
        if self.dead_t:
            self.dead_t -= 1
            if self.dead_t == 0 and self.lives > 0:
                self.px, self.py = W / 2, H - 30.0
                self.inv = INVULN
                self.bombs = max(self.bombs, BOMBS0)
                ev.append(("respawn", self.px, self.py))
            return
        if self.lives <= 0 or self.sec == SEC_END and self.ending == "derribado":
            return
        self.px = min(W - 6.0, max(6.0, self.px + mx))
        self.py = min(H - 8.0, max(HUD_H + 12.0, self.py + my))
        if bomb and self.bombs > 0 and self.bomb_t == 0 and self.sec != SEC_END:
            self.bombs -= 1
            self.bombs_used += 1
            self.bomb_t = BOMB_T
            self._cancel(ev, crystals=True)
            ev.append(("bomb", self.px, self.py))
            for f in self.foes:
                if not f.wait and f.y > -4:
                    self._hurt_foe(f, BOMB_DMG, ev)
            b = self.boss
            if b and b.vulnerable():
                self._hurt_boss(BOMB_BOSS_DMG, ev)
        # el disparo es automático: siempre, mientras haya nave
        if self.sec == SEC_END:
            return
        self.fire_t -= 1
        if self.fire_t <= 0:
            self.fire_t = FIRE_EVERY
            self._volley()

    def _volley(self):
        x, y = self.px, self.py - 7
        s = self.shots
        if len(s) > MAX_SHOTS:
            return
        p = self.power
        f = self.focus
        s.append([x - 2, y, 0.0])
        s.append([x + 2, y, 0.0])
        if p >= 2:
            if f:
                s.append([x - 5, y + 2, 0.0])
                s.append([x + 5, y + 2, 0.0])
            else:
                s.append([x - 4, y + 2, -0.9])
                s.append([x + 4, y + 2, 0.9])
        if p >= 3:
            s.append([x, y - 2, 0.0])
            for ox, oy in self.options():
                s.append([ox, oy - 4, 0.0])
        if p >= 4:
            if f:
                s.append([x - 8, y + 3, 0.0])
                s.append([x + 8, y + 3, 0.0])
            else:
                s.append([x - 6, y + 3, -2.0])
                s.append([x + 6, y + 3, 2.0])

    def options(self):
        """los drones de los costados (arma 3 en adelante). con foco se juntan
        adelante de la nave para concentrar el fuego."""
        if self.power < 3:
            return ()
        if self.focus:
            return ((self.px - 7, self.py - 6), (self.px + 7, self.py - 6))
        return ((self.px - 13, self.py + 3), (self.px + 13, self.py + 3))

    def _hit_player(self, ev):
        """te dieron: una vida menos, el arma baja y la cadena se corta."""
        self.hits += 1
        self.lives -= 1
        lost_mult = self.mult()
        self.chain = 0.0
        self.chain_t = 0
        if self.power > 1:
            # el arma baja, pero el nivel perdido queda flotando: se recupera
            self.power -= 1
            self.items.append([self.px, max(HUD_H + 30.0, self.py - 50), -1.6,
                               ITEM_P, 0])
        self.dead_t = DEAD_T
        self.graze_meter = 0
        ev.append(("hit", self.px, self.py, self.lives, lost_mult))
        self._cancel(ev, crystals=False)
        if self.lives <= 0:
            self._finish("derribado", ev)

    # --- el guion -------------------------------------------------------------------
    def _section(self, ev):
        self.sec_t += 1
        s = self.sec
        if s == SEC_A or s == SEC_B:
            script = SCRIPT_A if s == SEC_A else SCRIPT_B
            while self.script_i < len(script) and script[self.script_i][0] <= self.sec_t:
                _, what, args = script[self.script_i]
                getattr(self, "_spawn_" + what)(*args)
                self.script_i += 1
            if s == SEC_A and self.sec_t >= LEN_A:
                self._enter(SEC_MINI)
                self.boss = Boss(MINI)
                ev.append(("boss_in", MINI))
            elif s == SEC_B and self.sec_t >= LEN_B:
                self._enter(SEC_WARN)
                ev.append(("peligro",))
        elif s == SEC_MINI:
            if self.boss is None:
                self._enter(SEC_B)
        elif s == SEC_WARN:
            if self.sec_t >= WARN_T:
                self._enter(SEC_BOSS)
                self.boss = Boss(FINAL)
                ev.append(("boss_in", FINAL))

    def _enter(self, sec):
        self.sec = sec
        self.sec_t = 0
        self.script_i = 0

    def _finish(self, how, ev):
        if self.sec == SEC_END:
            return
        self.sec = SEC_END
        self.sec_t = 0
        self.ending = how
        self.end_t = 0
        if how == "escapo" and self.boss is not None:
            self.boss.state = "leave"
            self.boss.st = 0
        ev.append(("fin", how))

    def _results(self, ev):
        """el cierre: los bonos entran al puntaje acá, antes de terminar."""
        win = self.ending == "victoria"
        secs = 0
        if win and self.boss_killed_at is not None:
            secs = max(0, (T_END - self.boss_killed_at) // FPS)
        tb = secs * TIME_BONUS
        lb = self.lives * LIFE_BONUS if win else 0
        bb = self.bombs * BOMB_BONUS if self.lives > 0 else 0
        base = self.score
        self.score += tb + lb + bb
        self.results = {"ending": self.ending, "base": base, "time_s": secs,
                        "time_bonus": tb, "life_bonus": lb, "bomb_bonus": bb,
                        "kills": self.kills, "grazes": self.grazes,
                        "max_mult": self.max_mult, "total": self.score}
        self.done = True
        ev.append(("results",))

    # --- formaciones -----------------------------------------------------------------
    def _squad(self, n, drop):
        self.squad_n += 1
        self.squads[self.squad_n] = [n, n, drop, 0.0, 0.0]
        return self.squad_n

    def _spawn_swarm(self, cx, side, n, drop):
        """enjambre en V: baja junto y se abre. side 0 = se parte en dos."""
        sq = self._squad(n, drop)
        mid = n // 2
        for i in range(n):
            k = i - mid
            f = Foe(DART, cx + k * 13, -10 - abs(k) * 11, squad=sq)
            f.vy = 1.7
            f.a = side if side else (-1 if k < 0 else 1 if k > 0 else
                                     self.rng.choice((-1, 1)))
            f.ty = 96 + self.rng.randrange(30)       # dónde dobla
            f.fire = 50 + self.rng.randrange(70)
            self.foes.append(f)

    def _spawn_train(self, x0, side, n):
        """un tren que serpentea bajando desde una esquina."""
        sq = self._squad(n, 0)
        for i in range(n):
            f = Foe(DART, x0, -10, squad=sq, wait=i * 12, mode=1)
            f.a = float(x0)
            f.b = side
            f.fire = 70 + self.rng.randrange(90)
            self.foes.append(f)

    def _spawn_weavers(self, side, n, y0):
        """murciélagos que cruzan de lado haciendo olas, y disparan abanicos."""
        sq = self._squad(n, 0)
        for i in range(n):
            x = -10 if side > 0 else W + 10
            f = Foe(WEAVER, x, y0, squad=sq, wait=i * 20)
            f.vx = 1.05 * side
            f.a = float(y0)
            f.fire = 40 + i * 13
            self.foes.append(f)

    def _spawn_kamis(self, n):
        """kamikazes: bajan, avisan con una línea y se tiran contra ti."""
        sq = self._squad(n, 0)
        xs = [20 + (W - 40) * (i + 0.5) / n for i in range(n)]
        self.rng.shuffle(xs)
        for i, x in enumerate(xs):
            f = Foe(KAMI, x, -8, squad=sq, wait=i * 16)
            f.ty = 40 + self.rng.randrange(40)
            self.foes.append(f)

    def _spawn_turret(self, x, ty, mode):
        f = Foe(TURRET, x, -12, mode=mode)
        f.ty = float(ty)
        f.fire = 50
        self.foes.append(f)

    def _spawn_carrier(self, x, drop):
        f = Foe(CARRIER, x, -16)
        f.ty = 66.0
        f.a = float(x)
        f.drop = ITEM_P if drop else -1
        f.fire = 80
        self.foes.append(f)

    # --- disparos enemigos ----------------------------------------------------------
    def _aim(self, x, y):
        return math.atan2(self.py - y, self.px - x)

    def _shoot(self, x, y, ang, v, kind=PELLET, acc=1.0):
        if len(self.eb) >= MAX_EB:
            return
        # nunca una bala nacida encima de la nave: no hay cómo esquivarla
        dx, dy = x - self.px, y - self.py
        if dx * dx + dy * dy < 900:
            return
        self.eb.append([x, y, math.cos(ang) * v, math.sin(ang) * v, kind, 0, acc])

    def _ring(self, x, y, n, v, off=0.0, kind=PELLET, acc=1.0):
        for i in range(n):
            self._shoot(x, y, off + TAU * i / n, v, kind, acc)

    def _fan(self, x, y, n, spread, v, ang, kind=PELLET):
        for i in range(n):
            a = ang + (i - (n - 1) / 2) * spread
            self._shoot(x, y, a, v, kind)

    def _late(self):
        """las oleadas B disparan un poco más rápido."""
        return self.sec >= SEC_B

    # --- enemigos ---------------------------------------------------------------------
    def _step_foes(self, ev):
        keep = []
        late = self._late()
        for f in self.foes:
            if f.dead:
                continue
            if f.wait:
                f.wait -= 1
                keep.append(f)
                continue
            f.t += 1
            if f.flash:
                f.flash -= 1
            k = f.kind
            if k == DART:
                self._move_dart(f, late)
            elif k == WEAVER:
                f.x += f.vx
                f.y = f.a + 16 * math.sin(f.t / 22)
                f.fire -= 1
                if f.fire <= 0:
                    f.fire = 84 if not late else 66
                    if 8 < f.x < W - 8 and f.y < FIRE_MAX_Y:
                        self._fan(f.x, f.y + 4, 3, 0.26, 1.35 if not late else 1.6,
                                  self._aim(f.x, f.y))
            elif k == KAMI:
                self._move_kami(f, ev)
            elif k == TURRET:
                self._move_turret(f, late)
            elif k == CARRIER:
                self._move_carrier(f, late)
            # tocar un enemigo duele (los kamikazes viven de esto)
            if self.vulnerable() and abs(f.x - self.px) < f.hw - 1 \
                    and abs(f.y - self.py) < f.hh - 1:
                self._hit_player(ev)
                if f.kind == KAMI:
                    f.hp = 0
                    f.dead = True
                    self._squad_lost(f)
                    ev.append(("pop", f.x, f.y, f.kind))
                    continue
            if f.y > H + 20 or f.y < -40 or f.x < -30 or f.x > W + 30:
                self._squad_lost(f)
                continue
            keep.append(f)
        self.foes = keep

    def _move_dart(self, f, late):
        if f.mode == 1:              # tren: serpentea en diagonal
            f.y += 1.35
            f.a += 0.35 * f.b
            f.x = f.a + 26 * math.sin(f.t / 18)
        else:                        # V: baja y, pasada la línea, dobla
            if f.y >= f.ty:          # se abre de costado, no se te tira encima
                f.vx += 0.08 * f.a
                f.vx = max(-2.8, min(2.8, f.vx))
                f.vy = max(0.2, f.vy - 0.045)
            f.x += f.vx
            f.y += f.vy
        f.fire -= 1
        if f.fire == 0 and HUD_H < f.y < FIRE_MAX_Y:
            self._shoot(f.x, f.y + 3, self._aim(f.x, f.y), 1.9 if late else 1.55)

    def _move_kami(self, f, ev):
        if f.t < 50:                 # baja a su puesto
            f.y += (f.ty - f.y) * 0.07
        elif f.t < 90:               # avisa: apunta (se ve la línea) y titila
            if f.t < 80:
                f.a = self._aim(f.x, f.y)
            if f.t == 50:
                ev.append(("aim", f.x, f.y))
        else:                        # se tira, cada vez más rápido
            v = min(4.6, 1.0 + (f.t - 90) * 0.12)
            f.x += math.cos(f.a) * v
            f.y += math.sin(f.a) * v

    def _move_turret(self, f, late):
        if f.t < 300:
            f.y += (f.ty - f.y) * 0.05
        else:
            f.y -= min(2.0, (f.t - 300) * 0.04)
            return
        if f.t < 50:
            return
        f.fire -= 1
        if f.mode == 0:              # anillos que giran de a poco
            if f.fire <= 0:
                f.fire = 46 if not late else 38
                f.b += 0.13
                self._ring(f.x, f.y, 14 if not late else 16, 1.15, f.b)
        else:                        # espiral de tres brazos
            if f.fire <= 0:
                f.fire = 6 if not late else 5
                f.b += 0.19
                for i in range(3):
                    self._shoot(f.x, f.y, f.b + TAU * i / 3, 1.25, PELLET)

    def _move_carrier(self, f, late):
        if f.t < 520:
            f.y += (f.ty - f.y) * 0.03
            f.x = f.a + 22 * math.sin(f.t / 70)
        else:
            f.y -= min(1.4, (f.t - 520) * 0.02)
            return
        if f.t < 60:
            return
        f.fire -= 1
        if f.fire <= 0:              # ráfaga apuntada de cuatro, rápida
            f.fire = 90 if not late else 72
            f.burst = 4
            f.c = self._aim(f.x, f.y)
        if f.burst and f.t % 5 == 0:
            f.burst -= 1
            for s in (-8, 8):
                self._shoot(f.x + s, f.y + 6, f.c, 2.3, FAST)
        if f.t % (150 if not late else 120) == 0:
            self._ring(f.x, f.y, 16, 0.85, f.t * 0.01, ORB)

    def _hurt_foe(self, f, dmg, ev):
        f.hp -= dmg
        f.flash = 3
        if f.hp <= 0 and not f.dead:
            self._kill(f, ev)

    def _kill(self, f, ev):
        f.dead = True
        self.kills += 1
        self.chain += 3 if f.kind in (TURRET, CARRIER) else 1
        self.chain_t = CHAIN_T
        pts = f.value * self.mult()
        self.score += pts
        self.max_mult = max(self.max_mult, self.mult())
        ev.append(("kill", f.x, f.y, f.kind, pts))
        for i in range(f.crys):
            a = TAU * i / max(1, f.crys) + self.rng.random()
            self._crystal(f.x, f.y, math.cos(a) * 1.4, math.sin(a) * 1.4 - 0.6)
        if f.drop >= 0:
            self.items.append([f.x, f.y, -1.2, f.drop, 0])
        sq = self.squads.get(f.squad)
        if sq is not None:
            sq[0] -= 1
            sq[3], sq[4] = f.x, f.y
            if sq[0] <= 0 and sq[1] >= 3:
                pts = SQUAD_V * self.mult() * sq[1] // 5
                self.score += pts
                ev.append(("squad", f.x, f.y, pts))
                if sq[2]:
                    self.items.append([f.x, f.y, -1.2, ITEM_P, 0])
                del self.squads[f.squad]

    def _squad_lost(self, f):
        """se escapó uno: ese escuadrón ya no paga el bono completo."""
        if f.squad in self.squads:
            del self.squads[f.squad]

    # --- jefes -----------------------------------------------------------------------
    def _step_boss(self, ev):
        b = self.boss
        if b is None:
            return
        b.st += 1
        if b.flash:
            b.flash -= 1
        if b.state == "enter":
            ty = 66.0 if b.kind == MINI else 78.0
            b.y += (ty - b.y) * 0.045
            if b.st >= BOSS_ENTER:
                b.state, b.st, b.t = "fight", 0, 0
        elif b.state == "fight":
            b.t += 1
            if b.kind == MINI:
                self._mini(b, ev)
            else:
                self._final(b, ev)
        elif b.state == "break":         # entre fases: respira y se enoja
            b.x += (b.x0 - b.x) * 0.05
            if b.st >= 70:
                b.state, b.st, b.t = "fight", 0, 0
        elif b.state == "die":
            b.y += 0.15
            b.x += math.sin(b.st * 1.7) * 0.8
            if b.st % 9 == 0:
                ev.append(("boss_boom", b.x + self.rng.uniform(-b.hw, b.hw),
                           b.y + self.rng.uniform(-b.hh, b.hh), b.kind))
            if b.st >= (60 if b.kind == MINI else 100):
                ev.append(("boss_dead", b.x, b.y, b.kind))
                self._cancel(ev, crystals=True)
                for i in range(30 if b.kind == MINI else 60):
                    a = TAU * i / 30
                    self._crystal(b.x + math.cos(a) * 10, b.y + math.sin(a) * 6,
                                  math.cos(a) * 2.2, math.sin(a) * 2.2)
                if b.kind == MINI:
                    self.items.append([b.x - 10, b.y, -1.4, ITEM_P, 0])
                    self.items.append([b.x + 10, b.y, -1.4, ITEM_B, 0])
                self.boss = None
                if b.kind == FINAL:
                    self._finish("victoria", ev)
        elif b.state == "leave":
            b.y -= min(3.0, b.st * 0.05)
            if b.y < -60:
                self.boss = None
                ev.append(("boss_gone", b.kind))
        # chocar con el jefe también duele
        if b.state in ("fight", "break", "enter") and self.vulnerable() \
                and abs(b.x - self.px) < b.hw and abs(b.y - self.py) < b.hh:
            self._hit_player(ev)

    def _mini(self, b, ev):
        """el centinela: espiral doble, después abanicos desde las alas."""
        t = b.t
        b.x = W / 2 + 46 * math.sin(t / 95)
        if t >= MINI_TIME:
            b.state, b.st = "leave", 0
            ev.append(("flee", MINI))
            return
        c = t % 400
        if 20 <= c < 170:                       # espiral doble que gira
            if c % 5 == 0:
                b.a += 0.23
                for k in (0, math.pi):
                    self._shoot(b.x, b.y + 4, b.a + k, 1.35)
                    self._shoot(b.x, b.y + 4, -b.a + k + 0.6, 1.0, PELLET)
        elif 210 <= c < 360:                    # abanicos apuntados + orbes
            if c % 34 == 0:
                for s in (-17, 17):
                    self._fan(b.x + s, b.y + 6, 5, 0.2, 2.0,
                              self._aim(b.x + s, b.y), FAST)
            if c % 68 == 30:
                self._ring(b.x, b.y, 10, 0.9, c * 0.05, ORB)

    def _final(self, b, ev):
        """OCASO-85: tres fases, cada una con su dibujo de balas."""
        t = b.t
        ph = b.phase
        if ph == 0:      # flores: anillos alternados + ráfagas de las alas
            b.x = b.x0 + 30 * math.sin(t / 110)
            if t % 42 == 0:
                fast = (t // 42) % 2
                self._ring(b.x, b.y + 8, 20, 1.55 if fast else 1.15,
                           (t // 42) * 0.17 + (TAU / 40 if fast else 0))
            if t % 100 == 60:
                for s in (-28, 28):
                    self._fan(b.x + s, b.y + 10, 3, 0.16, 2.2,
                              self._aim(b.x + s, b.y + 10), FAST)
        elif ph == 1:    # lluvia: ondas desde las alas + orbes apuntados
            b.x = b.x0 + 44 * math.sin(t / 80)
            if t % 4 == 0:
                w = 0.75 * math.sin(t / 26)
                self._shoot(b.x - 28, b.y + 10, math.pi / 2 + w, 1.7)
                self._shoot(b.x + 28, b.y + 10, math.pi / 2 - w, 1.7)
            if t % 64 == 20:
                self._fan(b.x, b.y + 12, 3, 0.35, 1.0, self._aim(b.x, b.y), ORB)
            if t % 128 == 90:
                self._ring(b.x, b.y + 8, 20, 1.0, t * 0.03)
        else:            # furia: espirales que se cruzan + anillos apuntados
            tx = min(W - 40.0, max(40.0, self.px))
            b.x += (tx - b.x) * 0.012
            if t % 5 == 0:
                b.a += 0.12
                for i in range(2):
                    o = math.pi * i
                    self._shoot(b.x, b.y + 6, b.a + o, 1.3)
                    self._shoot(b.x, b.y + 6, -b.a + o + 0.4, 1.3, PELLET)
            if t % 100 == 50:
                a = self._aim(b.x, b.y)
                self._ring(b.x, b.y + 6, 22, 0.55, a + TAU / 44, FAST, acc=1.025)
            if t % 100 == 0 and t:
                for s in (-28, 28):
                    self._ring(b.x + s, b.y + 10, 8, 0.8, t * 0.02, ORB)

    def _hurt_boss(self, dmg, ev):
        b = self.boss
        b.hp -= dmg
        b.flash = 2
        self.chain_t = max(self.chain_t, CHAIN_T // 2)
        if b.hp > 0:
            return
        if b.phase + 1 < len(b.phases):         # se rompe una fase
            b.phase += 1
            b.hp = b.hp0 = b.phases[b.phase]
            b.state, b.st = "break", 0
            b.x0 = W / 2
            pts = PHASE_V
            self.score += pts
            self._cancel(ev, crystals=True)
            ev.append(("phase", b.phase, b.x, b.y, pts))
        else:
            b.hp = 0
            b.state, b.st = "die", 0
            pts = MINI_V if b.kind == MINI else BOSS_V
            self.score += pts
            self.kills += 1
            if b.kind == FINAL:
                self.boss_killed_at = self.t
            self._cancel(ev, crystals=True)
            ev.append(("boss_kill", b.x, b.y, b.kind, pts))

    # --- disparos de la nave -----------------------------------------------------------
    def _step_shots(self, ev):
        keep = []
        b = self.boss
        bhit = b is not None and b.vulnerable()
        if bhit:
            bx0, bx1 = b.x - b.hw, b.x + b.hw
            by0, by1 = b.y - b.hh, b.y + b.hh
        foes = [f for f in self.foes if not f.wait and f.y > HUD_H - 6]
        sparks = 0
        for s in self.shots:
            s[0] += s[2]
            s[1] -= SHOT_V
            x, y = s[0], s[1]
            if y < HUD_H - 4 or x < -4 or x > W + 4:
                continue
            if bhit and bx0 < x < bx1 and by0 < y < by1:
                self._hurt_boss(1, ev)
                if sparks < 2:
                    sparks += 1
                    ev.append(("spark", x, y))
                bhit = self.boss is not None and self.boss.vulnerable()
                continue
            hit = False
            for f in foes:
                if not f.dead and abs(x - f.x) < f.hw + 1 and -f.hh - 4 < y - f.y < f.hh:
                    self._hurt_foe(f, 1, ev)
                    if sparks < 3:
                        sparks += 1
                        ev.append(("spark", x, y))
                    hit = True
                    break
            if not hit:
                keep.append(s)
        self.shots = keep

    # --- balas enemigas ----------------------------------------------------------------
    def _step_bullets(self, ev):
        px, py = self.px, self.py
        alive = self.alive()
        vuln = self.vulnerable()
        can_graze = alive and self.inv == 0 and self.bomb_t == 0
        keep = []
        hit = False
        gz = 0
        gx = gy = 0.0
        for b in self.eb:
            acc = b[6]
            if acc != 1.0:
                b[2] *= acc
                b[3] *= acc
                if b[2] * b[2] + b[3] * b[3] > 6.0:
                    b[6] = 1.0
            x = b[0] + b[2]
            y = b[1] + b[3]
            if x < -6 or x > W + 6 or y < -6 or y > H + 6:
                continue
            b[0] = x
            b[1] = y
            if alive:
                dx = x - px
                dy = y - py
                if -14 < dx < 14 and -14 < dy < 14:
                    d2 = dx * dx + dy * dy
                    k = b[4]
                    if vuln and not hit and d2 < HIT2[k]:
                        hit = True
                        continue
                    if can_graze and not b[5] and d2 < GRAZE2[k]:
                        b[5] = 1
                        gz += 1
                        gx, gy = x, y
            keep.append(b)
        self.eb = keep
        if gz:
            self._graze(gz, gx, gy, ev)
        if hit:
            self._hit_player(ev)

    def _graze(self, n, x, y, ev):
        m = self.mult()
        self.grazes += n
        self.score += GRAZE_V * m * n
        self.chain += 0.34 * n
        self.chain_t = CHAIN_T
        self.max_mult = max(self.max_mult, self.mult())
        ev.append(("graze", x, y, n))
        self.graze_meter += n
        while self.graze_meter >= GRAZE_PER_BOMB:
            self.graze_meter -= GRAZE_PER_BOMB
            if self.bombs < BOMBS_MAX:
                self.bombs += 1
                ev.append(("bomb_gain", self.px, self.py))
            else:
                self.score += 2000 * m
                ev.append(("bomb_full", self.px, self.py, 2000 * m))

    def _cancel(self, ev, crystals):
        """borra todas las balas enemigas; si `crystals`, cada una deja un
        cristal que vuela hacia ti (la lluvia de premios al romper una fase)."""
        if not self.eb:
            return
        n = len(self.eb)
        if crystals:
            for b in self.eb[::2]:               # una de cada dos: que no sature
                self._crystal(b[0], b[1], 0.0, -0.4)
        ev.append(("cancel", n))
        self.eb = []

    # --- cristales e items -----------------------------------------------------------
    def _crystal(self, x, y, vx, vy):
        if len(self.crys) < CRYS_MAX:
            self.crys.append([x, y, vx, vy, 0])
        else:
            self.score += CRYSTAL_V * self.mult()

    def _step_crystals(self, ev):
        keep = []
        alive = self.alive()
        px, py = self.px, self.py
        got = 0
        val = CRYSTAL_V * self.mult()
        for c in self.crys:
            c[4] += 1
            if alive and c[4] > 16:
                # imán: todos vuelan a la nave, cada vez más rápido
                dx = px - c[0]
                dy = py - c[1]
                d = math.sqrt(dx * dx + dy * dy) + 0.01
                if d < 8:
                    got += 1
                    continue
                v = min(9.0, 1.0 + (c[4] - 16) * 0.22)
                c[0] += dx / d * v
                c[1] += dy / d * v
            else:
                c[2] *= 0.92
                c[3] = c[3] * 0.92 + 0.03
                c[0] += c[2]
                c[1] += c[3]
                if c[1] > H + 4:
                    continue
            keep.append(c)
        self.crys = keep
        if got:
            self.crys_got += got
            self.score += val * got
            ev.append(("crys", got, val * got))

    def _step_items(self, ev):
        keep = []
        alive = self.alive()
        for it in self.items:
            it[4] += 1
            it[2] = min(1.0, it[2] + 0.04)
            it[1] += it[2]
            it[0] += math.sin(it[4] / 14) * 0.4
            it[0] = min(W - 6.0, max(6.0, it[0]))
            if alive:                            # un imán corto: rozarlo basta
                dx, dy = self.px - it[0], self.py - it[1]
                if dx * dx + dy * dy < ITEM_MAGNET2:
                    it[0] += dx * 0.12
                    it[1] += dy * 0.12
            if alive and abs(it[0] - self.px) < 10 and abs(it[1] - self.py) < 10:
                self._take(it[3], ev)
                continue
            if it[1] < H + 10:
                keep.append(it)
        self.items = keep

    def _take(self, kind, ev):
        if kind == ITEM_P:
            if self.power < P_MAX:
                self.power += 1
                ev.append(("power", self.px, self.py, self.power))
            else:
                pts = PMAX_V * self.mult()
                self.score += pts
                ev.append(("pmax", self.px, self.py, pts))
        else:
            if self.bombs < BOMBS_MAX:
                self.bombs += 1
            ev.append(("bomb_gain", self.px, self.py))

    def _step_chain(self):
        if self.chain_t > 0:
            self.chain_t -= 1
        elif self.chain > 0:
            # sin matar ni rozar, el multiplicador cae de a un escalón
            self.chain = max(0.0, (self.mult() - 2) * CHAIN_STEP)
            self.chain_t = 60 if self.chain > 0 else 0
