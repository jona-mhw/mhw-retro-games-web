"""pong — 90 segundos contra la máquina, para el cabinet MHW · RETRO · FUTURE.

el pong de siempre no termina: si sos bueno, el peloteo puede durar para siempre.
acá la partida es un round de 90 segundos y el puntaje es cuántas devolviste. lo
que le cambia la cara:

- **cajas de poder en el medio de la cancha**, que se activan cuando **la pelota
  las toca** — y valen para el último que la golpeó. o sea: no las agarrás, las
  apuntás. eso convierte cada devolución en una decisión de puntería.
- **paleta larga** para vos, **corta** para el rival, **turbo** a todas las
  pelotas, y **multibola**, que mete dos más en la cancha.
- **la máquina aprende**: su tope de velocidad sube con el peloteo, así que al
  principio le ganás y a los 60 segundos ya no.
- la pelota deja **estela** y el golpe **sacude** la pantalla.
- **efecto**: si la paleta viene moviéndose cuando pega, la pelota sale con
  comba y se curva en el aire. es lo que le da puntería al tiro: podés doblarla
  hacia una caja o lejos de la máquina.
- **racha**: cada 10 devoluciones seguidas sin perder un punto hay un bono. la
  máquina que te saca el punto te la corta.

la física vive en la clase Pong, sin pyxel. como el reloj sólo baja, no hay
peloteo que estire la partida, y eso se prueba sin jugar.
"""
import random

import pyxel

from pixelkit import fx
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import text

W, H = 220, 170
HUD = 14
COURT = HUD                      # arriba de la cancha
PH = 26                          # alto de la paleta
PHALF = PH // 2
PX = W - 9                       # cara de la paleta del jugador
CX = 9                           # cara de la paleta de la máquina
TO_WIN = 7
TIME = 90 * 60                   # el round entero: nada lo estira

LARGA, CORTA, MULTI, TURBO = range(4)
POWER_NOMBRE = {LARGA: "¡LARGA!", CORTA: "¡CORTA!", MULTI: "¡MULTIBOLA!",
                TURBO: "¡TURBO!"}
POWER_GAP = 7 * 60
POWER_TTL = 10 * 60
EFECTO_TTL = 8 * 60
PH_LARGA, PH_CORTA = 40, 14
MAX_BALLS = 5
YO, MAQUINA = 1, -1              # quién tocó la pelota por última vez

# el muro: una columna de ladrillos delante de la máquina. la pelota los rompe
# y suman aparte del peloteo, así que conviene apuntarle en vez de sólo
# devolver. cuando no queda ninguno se rearma, más arriba en la cancha.
LADRILLO_W, LADRILLO_H = 5, 10
LADRILLOS = 9
LADRILLO_X = CX + 12
LADRILLO_VALE = 15

# el efecto: la velocidad de la paleta al pegar se vuelve comba. la pelota va
# curvando su vy cada frame y la comba se disipa sola.
EFECTO_GANANCIA = 0.22
EFECTO_MAX = 1.4
EFECTO_CURVA = 0.045
EFECTO_DISIPA = 0.975

# la racha: devoluciones seguidas sin que la máquina te saque un punto.
RACHA_CADA = 10
RACHA_VALE = 10

(BG, COURTC, NET, TXT, DIM, ACCENT, PLAYER, CPU, BALLC, WARN, SHADOW, WHITE,
 TRAIL1, TRAIL2, TRAIL3, GOLD, MAGENTA, SLOWC, GLOW, HOT) = range(20)
PAL = [
    0x0C0E14, 0x111726, 0x232C44, 0xE8ECF5, 0x5A6480, 0x8AC52F, 0x8AC52F,
    0xE0842E, 0xF2F5FB, 0xE0402A, 0x070810, 0xFFFFFF,
    0xB8C4E0, 0x6E7A9C, 0x3A4463, 0xFFD24A, 0xD84AB8, 0x4DA6FF, 0x7ADCFF,
    0xFF8A3A,
] + [0] * (256 - 20)

CHISPA_GOLPE = (WHITE, GLOW, TRAIL1, TRAIL2)
CHISPA_PUNTO = (WHITE, WARN, HOT, TRAIL3)


class Pong:
    """la cancha: paletas, pelotas, poderes y tanteo. sin pyxel, testeable."""

    def __init__(self, rng=None):
        self.rng = rng or random
        self.reset()

    def reset(self):
        self.py = self.cy = (COURT + H) / 2      # centros de las paletas
        self.pscore = self.cscore = 0
        self.rallies = 0
        self.pscore_muro = 0
        self.over = False
        self.time = TIME
        self.balls = []                          # [x, y, vx, vy, dueño]
        self.powers = []                         # [x, y, tipo, ttl]
        self.power_t = POWER_GAP
        self.ph_p = self.ph_c = PHALF            # media altura de cada paleta
        self.ttl_p = self.ttl_c = 0
        self.muro = []
        self.pvy = 0.0                           # con qué velocidad viene tu paleta
        self.racha = 0                           # devoluciones seguidas sin perder
        self.racha_bonus = 0
        self._armar_muro()
        self._serve(self.rng.choice((-1, 1)))

    # --- la máquina --------------------------------------------------------
    def cpu_speed(self):
        """la máquina se pone brava con el peloteo, con techo: siempre se le
        puede ganar un punto, nunca es imposible."""
        return min(3.6, 2.1 + self.rallies * 0.035)

    def _serve(self, dirx):
        if self.pscore >= TO_WIN or self.cscore >= TO_WIN:
            self.over = True
            return
        vy = self.rng.uniform(-1.1, 1.1)
        self.balls = [[W / 2, (COURT + H) / 2, 1.9 * dirx, vy, 0, 0.0]]

    def _armar_muro(self):
        """la columna de ladrillos, centrada en la cancha."""
        alto = LADRILLOS * LADRILLO_H
        y0 = (COURT + H) / 2 - alto / 2
        self.muro = [[LADRILLO_X, y0 + i * LADRILLO_H, 1]
                     for i in range(LADRILLOS)]

    def _pegar_muro(self, b, ev):
        """¿la pelota tocó un ladrillo? lo rompe y rebota."""
        for l in self.muro:
            if not l[2]:
                continue
            if l[0] - 2 <= b[0] <= l[0] + LADRILLO_W + 2 and \
                    l[1] <= b[1] <= l[1] + LADRILLO_H:
                l[2] = 0
                b[2] = abs(b[2])                 # sale rebotado hacia vos
                self.pscore_muro += LADRILLO_VALE
                self.rallies += 1
                ev.append(("ladrillo", l[0], l[1] + LADRILLO_H / 2))
                if not any(x[2] for x in self.muro):
                    self._armar_muro()
                    ev.append(("muro_nuevo",))
                return True
        return False

    def set_player(self, y):
        antes = self.py
        self.py = min(H - self.ph_p, max(COURT + self.ph_p, y))
        self.pvy = self.py - antes

    def _bounce(self, b, paddle_y, dirx, half, efecto=0.0):
        off = (b[1] - paddle_y) / half           # -1..1 según dónde pegó
        b[2] = dirx * min(4.2, abs(b[2]) * 1.06 + 0.05)
        b[3] = max(-3.2, min(3.2, b[3] + off * 1.4))
        # la comba: se guarda en la pelota y curva la vy frame a frame
        while len(b) < 6:
            b.append(0.0)
        b[5] = max(-EFECTO_MAX, min(EFECTO_MAX, efecto * EFECTO_GANANCIA))

    # --- poderes -----------------------------------------------------------
    def _tomar(self, tipo, dueño, ev):
        if tipo == LARGA:
            if dueño == MAQUINA:
                self.ph_c, self.ttl_c = PH_LARGA // 2, EFECTO_TTL
            else:
                self.ph_p, self.ttl_p = PH_LARGA // 2, EFECTO_TTL
        elif tipo == CORTA:                      # le pega al OTRO
            if dueño == MAQUINA:
                self.ph_p, self.ttl_p = PH_CORTA // 2, EFECTO_TTL
            else:
                self.ph_c, self.ttl_c = PH_CORTA // 2, EFECTO_TTL
        elif tipo == MULTI:
            base = self.balls[0] if self.balls else [W / 2, (COURT + H) / 2,
                                                     1.9, 0.4, 0]
            for d in (-1.0, 1.0):
                if len(self.balls) < MAX_BALLS:
                    self.balls.append([base[0], base[1], base[2],
                                       base[3] + d * 0.9, base[4], 0.0])
        else:                                    # turbo a todo lo que se mueva
            for b in self.balls:
                b[2] *= 1.35
                b[3] *= 1.15
        ev.append(("power", tipo, dueño))

    def _efectos_ttl(self):
        if self.ttl_p:
            self.ttl_p -= 1
            if not self.ttl_p:
                self.ph_p = PHALF
        if self.ttl_c:
            self.ttl_c -= 1
            if not self.ttl_c:
                self.ph_c = PHALF

    # --- un frame ----------------------------------------------------------
    def step(self):
        ev = []
        if self.over:
            return ev
        self._efectos_ttl()
        self._mover_cpu()
        self._spawn_power()
        ev += self._mover_pelotas()
        self.pvy = 0.0            # la comba es de ESTE frame: si no te moviste, no hay
        if not self.balls:
            self._serve(self.rng.choice((-1, 1)))
        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("tiempo",))
        return ev

    def _mover_cpu(self):
        """persigue la pelota que le viene, no cualquiera: con multibola,
        elegir mal es lo que la hace fallar (y es justo)."""
        objetivo = None
        for b in self.balls:
            if b[2] < 0 and (objetivo is None or b[0] < objetivo[0]):
                objetivo = b
        if objetivo is None and self.balls:
            objetivo = self.balls[0]
        if objetivo is None:
            return
        v = self.cpu_speed()
        if self.cy < objetivo[1] - 2:
            self.cy += min(v, objetivo[1] - self.cy)
        elif self.cy > objetivo[1] + 2:
            self.cy -= min(v, self.cy - objetivo[1])
        self.cy = min(H - self.ph_c, max(COURT + self.ph_c, self.cy))

    def _spawn_power(self):
        if self.powers:
            for p in self.powers:
                p[3] -= 1
            self.powers = [p for p in self.powers if p[3] > 0]
            return
        self.power_t -= 1
        if self.power_t <= 0:
            x = self.rng.randint(W // 2 - 40, W // 2 + 40)
            y = self.rng.randint(COURT + 14, H - 14)
            self.powers.append([x, y, self.rng.randrange(4), POWER_TTL])
            self.power_t = POWER_GAP

    def _mover_pelotas(self):
        ev = []
        quedan = []
        for b in self.balls:
            while len(b) < 6:
                b.append(0.0)
            if b[5]:                                 # la comba curva el vuelo
                b[3] = max(-3.4, min(3.4, b[3] + b[5] * EFECTO_CURVA))
                b[5] *= EFECTO_DISIPA
                if abs(b[5]) < 0.02:
                    b[5] = 0.0
            b[0] += b[2]
            b[1] += b[3]
            if b[1] < COURT + 2:
                b[1] = COURT + 2
                b[3] = abs(b[3])
                ev.append(("pared", b[0], b[1]))
            if b[1] > H - 2:
                b[1] = H - 2
                b[3] = -abs(b[3])
                ev.append(("pared", b[0], b[1]))
            # paleta del jugador (derecha)
            if b[2] > 0 and b[0] >= PX - 2 and abs(b[1] - self.py) <= self.ph_p + 2:
                b[0] = PX - 2
                self._bounce(b, self.py, -1, self.ph_p, efecto=self.pvy)
                b[4] = YO
                self.rallies += 1
                self.racha += 1
                ev.append(("golpe", b[0], b[1], YO))
                if abs(b[5]) > 0.5:
                    ev.append(("efecto", b[0], b[1]))
                if self.racha % RACHA_CADA == 0:
                    self.racha_bonus += RACHA_VALE
                    ev.append(("racha", self.racha))
            # paleta de la máquina (izquierda)
            if b[2] < 0 and b[0] <= CX + 2 and abs(b[1] - self.cy) <= self.ph_c + 2:
                b[0] = CX + 2
                self._bounce(b, self.cy, 1, self.ph_c)
                b[4] = MAQUINA
                ev.append(("golpe", b[0], b[1], MAQUINA))
            if self._pegar_muro(b, ev):
                pass
            # cajas de poder: las activa la pelota, a favor de quien la tocó
            for p in list(self.powers):
                if abs(b[0] - p[0]) < 7 and abs(b[1] - p[1]) < 7:
                    self.powers.remove(p)
                    self._tomar(p[2], b[4] or YO, ev)
                    self.power_t = POWER_GAP
                    break
            if b[0] < 0:
                self.pscore += 1
                ev.append(("punto", YO))
            elif b[0] > W:
                self.cscore += 1
                if self.racha >= RACHA_CADA:
                    ev.append(("racha_rota", self.racha))
                self.racha = 0
                ev.append(("punto", MAQUINA))
            else:
                quedan.append(b)
        self.balls = quedan
        if self.pscore >= TO_WIN or self.cscore >= TO_WIN:
            self.over = True
            ev.append(("fin",))
        return ev

    @property
    def score(self):
        return self.rallies + self.pscore_muro + self.racha_bonus


class World:
    def __init__(self):
        self.p = Pong()
        self.fx = fx.Fx(gravity=0.0)
        self.hitflash = 0
        self.fx.destello(WHITE)
        self.trail = []               # las últimas posiciones, para la estela
        self.use_mouse = False        # gana el último input que hayas usado
        self._lm = None

    @property
    def over(self):
        return self.p.over

    @property
    def score(self):
        return self.p.score

    def update(self):
        p = self.p
        my = pyxel.mouse_y
        if self._lm is not None and my != self._lm:
            self.use_mouse = True
        self._lm = my
        up = pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W)
        down = pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S)
        if up or down:
            self.use_mouse = False
        if self.use_mouse:
            p.set_player(my)
        elif up:
            p.set_player(p.py - 3.4)
        elif down:
            p.set_player(p.py + 3.4)
        self.hitflash = max(0, self.hitflash - 1)
        for e in p.step():
            self._efecto(e)
        self.trail.append([(b[0], b[1]) for b in p.balls])
        del self.trail[:-6]
        self.fx.update()

    def _efecto(self, e):
        kind = e[0]
        if kind == "golpe":
            self.fx.burst(e[1], e[2], CHISPA_GOLPE, n=8, speed=1.5, life=14)
            self.fx.shake(2)
            self.hitflash = 4
        elif kind == "pared":
            self.fx.burst(e[1], e[2], (WHITE, TRAIL1, TRAIL2), n=4, speed=1.0,
                          life=10)
        elif kind == "efecto":
            self.fx.burst(e[1], e[2], (WHITE, MAGENTA, GLOW), n=10, speed=1.8,
                          life=18, spread=2.2, angle=3.1416)
            self.fx.popup(e[1] - 22, e[2] - 10, "efecto", MAGENTA, life=22)
        elif kind == "racha":
            self.fx.popup(W / 2, (COURT + H) / 2 - 30, "¡RACHA %d! +%d"
                          % (e[1], RACHA_VALE), GOLD)
            self.fx.destello(GOLD)
            self.fx.shake(3)
        elif kind == "racha_rota":
            self.fx.popup(W - 40, (COURT + H) / 2 + 10, "racha rota", DIM)
        elif kind == "punto":
            quien = e[1]
            x = W - 20 if quien == YO else 20
            self.fx.burst(x, (COURT + H) / 2, CHISPA_PUNTO, n=26, speed=2.6,
                          life=30)
            self.fx.popup(W / 2, (COURT + H) / 2 - 20,
                          "PUNTO TUYO" if quien == YO else "PUNTO SUYO",
                          ACCENT if quien == YO else WARN)
            self.fx.shake(5)
            self.fx.destello(ACCENT if quien == YO else WARN)
        elif kind == "ladrillo":
            self.fx.burst(e[1], e[2], (WHITE, GOLD, HOT, TRAIL2), n=12,
                          speed=1.8, life=20)
            self.fx.popup(e[1] + 14, e[2] - 6, "+%d" % LADRILLO_VALE, GOLD)
            self.fx.shake(2)
        elif kind == "muro_nuevo":
            self.fx.popup(W / 2, COURT + 20, "¡MURO NUEVO!", GOLD)
            self.fx.destello(GOLD)
        elif kind == "power":
            tipo, dueño = e[1], e[2]
            self.fx.popup(W / 2, COURT + 26, POWER_NOMBRE[tipo],
                          GOLD if dueño == YO else MAGENTA)
            self.fx.destello(GOLD if dueño == YO else MAGENTA)
            self.fx.shake(3)

    def draw(self):
        p = self.p
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        pyxel.rect(0, COURT, W, H - COURT, COURTC)
        for y in range(COURT, H, 8):             # red punteada
            pyxel.rect(W // 2 - 1, y, 2, 4, NET)
        for l in p.muro:
            if l[2]:
                pyxel.rect(int(l[0]), int(l[1]) + 1, LADRILLO_W,
                           LADRILLO_H - 2, GOLD)
                pyxel.rect(int(l[0]), int(l[1]) + 1, LADRILLO_W, 1, WHITE)
        for px_, py_, tipo, ttl in p.powers:
            self._power(px_, py_, tipo, ttl)
        self._estela()
        pyxel.rect(int(CX - 3), int(p.cy - p.ph_c), 4, p.ph_c * 2, CPU)
        pyxel.rect(int(PX - 1), int(p.py - p.ph_p), 4, p.ph_p * 2, PLAYER)
        if p.ttl_p:                              # halo del efecto activo
            pyxel.rectb(int(PX - 2), int(p.py - p.ph_p - 1), 6, p.ph_p * 2 + 2,
                        GOLD)
        if p.ttl_c:
            pyxel.rectb(int(CX - 4), int(p.cy - p.ph_c - 1), 6, p.ph_c * 2 + 2,
                        MAGENTA)
        col = BALLC if self.hitflash == 0 else WHITE
        for b in p.balls:
            pyxel.rect(int(b[0] - 2), int(b[1] - 2), 4, 4, col)
            if len(b) > 5 and abs(b[5]) > 0.3:      # con efecto: gira
                k = (pyxel.frame_count // 3) % 4
                dx, dy = ((-2, -2), (1, -2), (1, 1), (-2, 1))[k]
                pyxel.pset(int(b[0]) + dx, int(b[1]) + dy, MAGENTA)
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(0, COURT, W, H - COURT)
        self._hud()

    def _estela(self):
        """las posiciones viejas de cada pelota, cada vez más apagadas."""
        for i, snap in enumerate(self.trail):
            c = (TRAIL3, TRAIL3, TRAIL2, TRAIL2, TRAIL1, TRAIL1)[i]
            for bx, by in snap:
                pyxel.rect(int(bx - 1), int(by - 1), 2, 2, c)

    def _power(self, x, y, tipo, ttl):
        if ttl < 90 and (pyxel.frame_count // 4) % 2:      # titila antes de irse
            return
        col = (ACCENT, WARN, GOLD, HOT)[tipo]
        r = 5 + (pyxel.frame_count // 6) % 2
        pyxel.rectb(x - r, y - r, r * 2, r * 2, col)
        pyxel.rectb(x - r + 1, y - r + 1, r * 2 - 2, r * 2 - 2, SHADOW)
        if tipo == LARGA:
            pyxel.rect(x - 1, y - 4, 2, 8, col)
        elif tipo == CORTA:
            pyxel.rect(x - 1, y - 2, 2, 4, col)
        elif tipo == MULTI:
            pyxel.rect(x - 3, y - 2, 2, 2, col)
            pyxel.rect(x + 1, y, 2, 2, col)
            pyxel.rect(x - 1, y + 2, 2, 2, col)
        else:
            pyxel.line(x + 1, y - 4, x - 2, y, col)
            pyxel.line(x - 2, y, x + 1, y + 1, col)

    def _hud(self):
        p = self.p
        pyxel.rect(0, 0, W, HUD, SHADOW)
        text(4, 4, "rally %d" % p.rallies, ACCENT)
        m = "%d - %d" % (p.pscore, p.cscore)
        text(W // 2 - len(m) * 2, 4, m, TXT)
        quedan = sum(1 for l in p.muro if l[2])
        text(58, 4, "muro %d" % quedan, GOLD if quedan else DIM)
        if len(p.balls) > 1:
            text(W // 2 + 18, 4, "x%d" % len(p.balls), GOLD)
        if p.racha >= 3:                             # la racha, cuando ya vale
            col = GOLD if p.racha % RACHA_CADA >= RACHA_CADA - 2 else DIM
            text(W // 2 + 34, 4, "r%d" % p.racha, col)
        s = p.time // 60
        col = WHITE if s <= 10 and pyxel.frame_count % 30 < 15 else TXT
        r = "%ds" % s
        text(W - len(r) * 4 - 4, 4, r, col)
        fx.bar(W - 66, 5, 28, 4, p.time / TIME, ACCENT, COURTC)


class Game:
    def __init__(self):
        Cabinet(
            game_id="pong", title="PONG", subtitle="90 segundos contra la máquina",
            howto=["mouse o flechas mueven", "pegale a las cajas con la pelota",
                   "movete al pegar: la pelota sale con efecto",
                   "cada 10 devoluciones seguidas, bono"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=COURTC),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
