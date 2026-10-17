"""pong — 90 segundos contra la máquina, para el cabinet MHW · RETRO · FUTURE.

el pong de siempre no termina: si eres bueno, el peloteo puede durar para
siempre. acá la partida es un round de 90 segundos y el puntaje es lo que
hagas en ese rato. lo que le cambia la cara:

- **cajas de poder en el medio de la cancha**, que se activan cuando **la
  pelota las toca** — y valen para el último que la golpeó. no se agarran, se
  apuntan: larga, corta (al rival), multibola, turbo y escudo (una muralla en
  tu arco que salva una pelota).
- **el smash**: cada 4 devoluciones se carga. con la carga llena, apretar el
  botón abre una ventana corta: si la pelota te pega dentro de ella sale
  **en llamas**, rapidísima, atraviesa ladrillos y a la máquina le cuesta.
  es el golpe para ganar el punto, y hay que medirle el tiempo.
- **jefes de muro**: delante de la máquina hay ladrillos que se rompen y
  pagan. cada muro derribado trae el siguiente patrón: columna, tablero,
  muro que se mueve, y el búnker (ladrillos blindados y un núcleo de oro).
- **tres rondas, tres personalidades**: cada 30 s la máquina cambia. TRANQUI
  se equivoca, COMBERO le pega con efecto, FURIA es rápida y te devuelve
  smashes. su tope sube con el peloteo, con techo: siempre se le puede ganar.
- **efecto**: si la paleta viene moviéndose cuando pega, la pelota sale con
  comba y se curva en el aire.
- **combo**: las devoluciones seguidas sin perder un punto se ven gigantes en
  la cancha y pagan cada 10, cada vez más.
- **tiempo de oro**: los últimos 15 s todo vale doble, y en los puntos
  decisivos la pelota entra en **cámara lenta** cuando va al arco.

la física vive en la clase Pong, sin pyxel. el reloj baja un frame por step
pase lo que pase (saques, pausas de golpe y cámara lenta incluidos), así que
no hay peloteo ni efecto que estire la partida, y eso se prueba sin jugar.
"""
import random

import pyxel

from pixelkit import fx, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import ctext, text

from .grande import Fx, ancho, big, cbig

W, H = 220, 170
HUD = 16
COURT = HUD                      # arriba de la cancha
PH = 26                          # alto de la paleta
PHALF = PH // 2
PX = W - 9                       # cara de la paleta del jugador
CX = 9                           # cara de la paleta de la máquina
TO_WIN = 11                      # a 11, como el ping-pong
TIME = 90 * 60                   # el round entero: nada lo estira
SAQUE = 40                       # la pelota espera en el medio tras un punto

LARGA, CORTA, MULTI, TURBO, ESCUDO = range(5)
POWER_NOMBRE = {LARGA: "¡LARGA!", CORTA: "¡CORTA!", MULTI: "¡MULTIBOLA!",
                TURBO: "¡TURBO!", ESCUDO: "¡MURALLA!"}
POWER_GAP = 6 * 60
POWER_TTL = 10 * 60
EFECTO_TTL = 8 * 60
ESCUDO_TTL = 9 * 60
PH_LARGA, PH_CORTA = 40, 14
MAX_BALLS = 5
YO, MAQUINA = 1, -1              # quién tocó la pelota por última vez

# una pelota es [x, y, vx, vy, dueño, comba, fuego, drama]. los tests y el
# código viejo arman pelotas de 5; `_pad` completa lo que falte.
BALL_LEN = 8

# --- el muro -----------------------------------------------------------------
# delante de la máquina. la pelota los rompe y suman aparte del peloteo, así
# que conviene apuntarle en vez de sólo devolver. cuando cae el último, viene
# el patrón siguiente. un ladrillo es [x, y, vida, tipo].
LADRILLO_W, LADRILLO_H = 5, 10
LADRILLOS = 9
LADRILLO_X = CX + 12
NORMAL, BLINDADO, NUCLEO = range(3)
LADRILLO_VALE = 15
VALE = {NORMAL: LADRILLO_VALE, BLINDADO: 25, NUCLEO: 60}
MURO_BONO = 30
MUROS = ("COLUMNA", "TABLERO", "MURO MÓVIL", "EL BÚNKER")

# el efecto: la velocidad de la paleta al pegar se vuelve comba. la pelota va
# curvando su vy cada frame y la comba se disipa sola.
EFECTO_GANANCIA = 0.22
EFECTO_MAX = 1.4
EFECTO_CURVA = 0.045
EFECTO_DISIPA = 0.975

# la racha (el combo): devoluciones seguidas sin que la máquina te saque un
# punto. paga cada 10, y cada vez más: 10, 20, 30...
RACHA_CADA = 10
RACHA_VALE = 10

# el smash
SMASH_CARGA = 4                  # devoluciones para cargarlo
SMASH_VENTANA = 22               # frames en que la paleta pega en llamas
SMASH_ESPERA = 24                # si erraste la ventana, cuánto para volver a probar
SMASH_V = 5.0
SMASH_VALE = 3                   # extra por pegarlo
GANADOR_VALE = 20                # extra si el punto lo gana una pelota en llamas
DEVUELTO_VALE = 8                # devolverle un smash a la máquina

PUNTO_VALE = 10
VICTORIA_VALE = 50               # ganarle los 11 puntos antes de que suene el reloj
SEGUNDO_VALE = 3                 # y cada segundo que sobre, para que ganar rápido
                                 # nunca convenga menos que estirar el peloteo

# las rondas: (nombre, factor de velocidad, error de puntería en px, desde
# qué fracción de la cancha empieza a seguir la pelota). la máquina que
# reacciona tarde es la que se come los tiros cruzados.
RONDA_T = 30 * 60
RONDAS = (("TRANQUI", 0.82, 17, 0.58), ("COMBERO", 1.0, 12, 0.7),
          ("FURIA", 1.12, 8, 0.85))
CPU_TOPE = 3.3
FURIA_SMASH = 0.22               # chance de que FURIA devuelva en llamas

ORO_T = 15 * 60                  # los últimos 15 s valen doble
LENTO = 30                       # frames de cámara lenta
LENTO_K = 0.32
LENTO_MAX = 6                    # cuántas veces por partida

(BG, COURTC, NET, TXT, DIM, ACCENT, PLAYER, CPU, BALLC, WARN, SHADOW, WHITE,
 TRAIL1, TRAIL2, TRAIL3, GOLD, MAGENTA, SLOWC, GLOW, HOT, BIGC, COURT2,
 GOLDDK, FIRE, ARMOR, ARMORDK, OROC, PLAYERDK, CPUDK, MAGDK, WARNDK,
 HUDC, BIGC2) = range(33)
PAL = [
    0x0C0E14, 0x111726, 0x2A3452, 0xE8ECF5, 0x8A94B0, 0x9AE03A, 0x9AE03A,
    0xFF9A3E, 0xF2F5FB, 0xFF4A34, 0x05060B, 0xFFFFFF,
    0xB8C4E0, 0x6E7A9C, 0x3A4463, 0xFFD24A, 0xF05AD0, 0x4DA6FF, 0x7ADCFF,
    0xFF8A3A, 0x1D2640, 0x141B2E, 0xA8741E, 0xFF5A1F, 0xB4C0E0, 0x5A668E,
    0x2A2414, 0x4E8A1A, 0x9A5418, 0x8A2A78, 0x9A2418, 0x080A12, 0x34406A,
] + [0] * (256 - 33)

CHISPA_GOLPE = (WHITE, GLOW, TRAIL1, TRAIL2)
CHISPA_PUNTO = (WHITE, WARN, HOT, TRAIL3)
CHISPA_FUEGO = (WHITE, GOLD, FIRE, WARNDK)
RONDA_COL = (CPU, MAGENTA, WARN)
RONDA_DK = (CPUDK, MAGDK, WARNDK)


def _pad(b):
    while len(b) < BALL_LEN:
        b.append(0.0 if len(b) == 5 else 0)
    return b


class Pong:
    """la cancha: paletas, pelotas, poderes y tanteo. sin pyxel, testeable."""

    def __init__(self, rng=None):
        self.rng = rng or random
        self.reset()

    def reset(self):
        self.py = self.cy = (COURT + H) / 2      # centros de las paletas
        self.pscore = self.cscore = 0
        self.rallies = 0                         # devoluciones (cuenta, no puntaje)
        self.pts = 0                             # el puntaje
        self.over = False
        self.time = TIME
        self.balls = []
        self.powers = []                         # [x, y, tipo, ttl]
        self.power_t = POWER_GAP
        self.ph_p = self.ph_c = PHALF            # media altura de cada paleta
        self.ttl_p = self.ttl_c = 0
        self.escudo_p = self.escudo_c = 0
        self.muro = []
        self.muro_n = 0                          # cuántos muros van
        self.muro_vy = 0.0
        self.pvy = 0.0                           # con qué velocidad viene tu paleta
        self.racha = 0                           # devoluciones seguidas sin perder
        self.carga = 0                           # el smash
        self.smash_t = 0
        self.smash_cd = 0
        self.smashes = 0
        self.saque = 0
        self.parada = 0                          # hit-stop: el reloj sigue
        self.lento = 0
        self.lentos = 0
        self.cpu_err = 0.0
        self.ronda = 0
        self.oro = False
        self._armar_muro()
        self._serve(self.rng.choice((-1, 1)))
        self.saque = 0                           # el primero sale ya

    # --- puntaje -------------------------------------------------------------
    def mult(self):
        return 2 if self.oro else 1

    def _sumar(self, n):
        n *= self.mult()
        self.pts += n
        return n

    @property
    def score(self):
        return self.pts

    # --- la máquina ----------------------------------------------------------
    def cpu_speed(self):
        """la máquina se pone brava con el peloteo y con la ronda, con techo:
        siempre se le puede ganar un punto, nunca es imposible."""
        base = 1.75 + self.rallies * 0.014
        return min(CPU_TOPE, base * RONDAS[self.ronda][1])

    def _serve(self, dirx):
        if self.pscore >= TO_WIN or self.cscore >= TO_WIN:
            self.over = True
            return
        vy = self.rng.uniform(-1.1, 1.1)
        self.balls = [_pad([W / 2, (COURT + H) / 2, 1.9 * dirx, vy, 0])]
        self.saque = SAQUE

    # --- el muro -------------------------------------------------------------
    def _armar_muro(self):
        """el patrón que toca. el primero es la columna de siempre; después
        rotan tablero, móvil y búnker."""
        n = self.muro_n
        pat = 0 if n == 0 else 1 + (n - 1) % 3
        mid = (COURT + H) / 2
        self.muro_vy = 0.0
        m = []
        if pat == 0:                             # columna
            y0 = mid - LADRILLOS * LADRILLO_H / 2
            m = [[LADRILLO_X, y0 + i * LADRILLO_H, 1, NORMAL]
                 for i in range(LADRILLOS)]
        elif pat == 1:                           # tablero: dos columnas en damero
            y0 = mid - 12 * LADRILLO_H / 2
            for i in range(12):
                x = LADRILLO_X + (LADRILLO_W + 2) * (i % 2)
                m.append([x, y0 + i * LADRILLO_H, 1, NORMAL])
        elif pat == 2:                           # muro móvil: sube y baja
            y0 = mid - 7 * LADRILLO_H / 2
            m = [[LADRILLO_X, y0 + i * LADRILLO_H, 1,
                  BLINDADO if i in (0, 6) else NORMAL] for i in range(7)]
            self.muro_vy = 0.55
        else:                                    # el búnker
            y0 = mid - 9 * LADRILLO_H / 2
            for i in range(9):
                tipo = NUCLEO if i == 4 else (BLINDADO if i in (3, 5) else NORMAL)
                m.append([LADRILLO_X, y0 + i * LADRILLO_H,
                          {NORMAL: 1, BLINDADO: 2, NUCLEO: 3}[tipo], tipo])
            for i in (2, 3, 5, 6):               # una segunda capa blindada
                m.append([LADRILLO_X + LADRILLO_W + 2, y0 + i * LADRILLO_H, 2,
                          BLINDADO])
            self.muro_vy = 0.3
        self.muro = m

    def nombre_muro(self):
        n = self.muro_n
        return MUROS[0 if n == 0 else 1 + (n - 1) % 3]

    def _mover_muro(self):
        if not self.muro_vy:
            return
        vivos = [l for l in self.muro if l[2]]
        if not vivos:
            return
        top = min(l[1] for l in vivos)
        bot = max(l[1] for l in vivos) + LADRILLO_H
        if top + self.muro_vy < COURT + 4 or bot + self.muro_vy > H - 4:
            self.muro_vy = -self.muro_vy
        for l in self.muro:
            l[1] += self.muro_vy

    def _pegar_muro(self, b, ev):
        """¿la pelota tocó un ladrillo? lo golpea y rebota (la pelota en
        llamas no rebota: lo atraviesa)."""
        _pad(b)
        for l in self.muro:
            if not l[2]:
                continue
            if l[0] - 2 <= b[0] <= l[0] + LADRILLO_W + 2 and \
                    l[1] <= b[1] <= l[1] + LADRILLO_H:
                tipo = l[3] if len(l) > 3 else NORMAL
                fuego = b[6]
                l[2] = 0 if fuego else l[2] - 1
                if not fuego:
                    b[2] = abs(b[2])             # sale rebotado hacia ti
                self.rallies += 1
                if l[2]:
                    self._sumar(2)
                    ev.append(("blindado", l[0], l[1] + LADRILLO_H / 2))
                    return True
                ganado = self._sumar(VALE[tipo] * (2 if fuego else 1))
                ev.append(("ladrillo", l[0], l[1] + LADRILLO_H / 2, ganado,
                           tipo))
                if not any(x[2] for x in self.muro):
                    bono = self._sumar(MURO_BONO)
                    self.muro_n += 1
                    self._armar_muro()
                    ev.append(("muro_nuevo", bono, self.nombre_muro()))
                return True
        return False

    # --- tu paleta -----------------------------------------------------------
    def set_player(self, y):
        antes = self.py
        self.py = min(H - self.ph_p, max(COURT + self.ph_p, y))
        self.pvy = self.py - antes

    def pedir_smash(self):
        """el botón. con la carga llena abre la ventana; si no, nada."""
        if self.carga >= SMASH_CARGA and not self.smash_t and \
                not self.smash_cd and not self.over:
            self.smash_t = SMASH_VENTANA
            return True
        return False

    def _bounce(self, b, paddle_y, dirx, half, efecto=0.0):
        off = (b[1] - paddle_y) / half           # -1..1 según dónde pegó
        b[2] = dirx * min(4.2, abs(b[2]) * 1.06 + 0.05)
        b[3] = max(-3.2, min(3.2, b[3] + off * 1.4))
        _pad(b)
        # la comba: se guarda en la pelota y curva la vy frame a frame
        b[5] = max(-EFECTO_MAX, min(EFECTO_MAX, efecto * EFECTO_GANANCIA))
        b[6] = 0
        b[7] = 0

    # --- poderes -------------------------------------------------------------
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
                    self.balls.append(_pad([base[0], base[1], base[2],
                                            base[3] + d * 0.9, base[4]]))
        elif tipo == ESCUDO:
            if dueño == MAQUINA:
                self.escudo_c = ESCUDO_TTL
            else:
                self.escudo_p = ESCUDO_TTL
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
        if self.escudo_p:
            self.escudo_p -= 1
        if self.escudo_c:
            self.escudo_c -= 1

    # --- un frame ------------------------------------------------------------
    def step(self):
        ev = []
        if self.over:
            return ev
        # el reloj primero, siempre: ni el saque, ni el hit-stop, ni la cámara
        # lenta lo frenan. así la cota de los 90 s no depende de nada más.
        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("tiempo",))
            return ev
        ronda = min(len(RONDAS) - 1, (TIME - self.time) // RONDA_T)
        if ronda != self.ronda:
            self.ronda = ronda
            ev.append(("ronda", ronda))
        if not self.oro and self.time <= ORO_T:
            self.oro = True
            ev.append(("oro",))
        if self.smash_t:
            self.smash_t -= 1
            if not self.smash_t:
                self.smash_cd = SMASH_ESPERA     # la erraste: un respiro
        elif self.smash_cd:
            self.smash_cd -= 1
        if self.parada:
            self.parada -= 1
            self.pvy = 0.0
            return ev
        if self.lento:
            self.lento -= 1
        self._efectos_ttl()
        self._mover_cpu()
        self._spawn_power()
        self._mover_muro()
        if self.saque:
            self.saque -= 1
        else:
            ev += self._mover_pelotas()
        self.pvy = 0.0            # la comba es de ESTE frame: si no te moviste, no hay
        if not self.balls and not self.over:
            self._serve(self.rng.choice((-1, 1)))
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
        if len(objetivo) > 6 and objetivo[6] == YO:
            v *= 0.72                            # el smash la descoloca
        if self.lento:
            v *= LENTO_K
        meta = objetivo[1] + (self.cpu_err if objetivo[2] < 0 else 0)
        if objetivo[2] >= 0 or objetivo[0] > W * RONDAS[self.ronda][3]:
            # todavía no reacciona: vuelve al medio, sin apuro
            meta = (COURT + H) / 2
            v *= 0.5
        if self.cy < meta - 2:
            self.cy += min(v, meta - self.cy)
        elif self.cy > meta + 2:
            self.cy -= min(v, self.cy - meta)
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
            self.powers.append([x, y, self.rng.randrange(5), POWER_TTL])
            self.power_t = POWER_GAP

    def decisivo(self):
        """¿el próximo punto pesa? en el tiempo de oro, o si alguien está a
        uno de ganar."""
        return self.oro or self.pscore == TO_WIN - 1 or self.cscore == TO_WIN - 1

    def _drama(self, b, ev):
        """cámara lenta cuando una pelota decisiva va al arco y la paleta que
        defiende no está ahí: el '¿llega?' se ve."""
        if self.lento or self.lentos >= LENTO_MAX or b[7] or not self.decisivo():
            return
        if b[2] > 0 and b[0] > W - 48 and abs(b[1] - self.py) > self.ph_p + 6:
            lado = YO
        elif b[2] < 0 and b[0] < 48 and abs(b[1] - self.cy) > self.ph_c + 6:
            lado = MAQUINA
        else:
            return
        b[7] = 1
        self.lento = LENTO
        self.lentos += 1
        ev.append(("lento", lado))

    def _mover_pelotas(self):
        ev = []
        quedan = []
        k = LENTO_K if self.lento else 1.0
        for b in self.balls:
            _pad(b)
            if b[5]:                                 # la comba curva el vuelo
                b[3] = max(-3.4, min(3.4, b[3] + b[5] * EFECTO_CURVA * k))
                b[5] *= EFECTO_DISIPA
                if abs(b[5]) < 0.02:
                    b[5] = 0.0
            self._drama(b, ev)
            b[0] += b[2] * k
            b[1] += b[3] * k
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
                self._golpe_tuyo(b, ev)
            # paleta de la máquina (izquierda)
            if b[2] < 0 and b[0] <= CX + 2 and abs(b[1] - self.cy) <= self.ph_c + 2:
                self._golpe_suyo(b, ev)
            self._pegar_muro(b, ev)
            # cajas de poder: las activa la pelota, a favor de quien la tocó
            for p in list(self.powers):
                if abs(b[0] - p[0]) < 7 and abs(b[1] - p[1]) < 7:
                    self.powers.remove(p)
                    self._tomar(p[2], b[4] or YO, ev)
                    self.power_t = POWER_GAP
                    break
            # las murallas: salvan una pelota y se gastan
            if b[0] > W - 3 and b[2] > 0 and self.escudo_p:
                self.escudo_p = 0
                b[0], b[2] = W - 3, -abs(b[2])
                ev.append(("escudo", b[0], b[1], YO))
            elif b[0] < 3 and b[2] < 0 and self.escudo_c:
                self.escudo_c = 0
                b[0], b[2] = 3, abs(b[2])
                ev.append(("escudo", b[0], b[1], MAQUINA))
            if b[0] < 0:
                self._punto(YO, b, ev)
            elif b[0] > W:
                self._punto(MAQUINA, b, ev)
            else:
                quedan.append(b)
        self.balls = quedan
        if not self.over and (self.pscore >= TO_WIN or self.cscore >= TO_WIN):
            self.over = True
            if self.pscore >= TO_WIN:
                ev.append(("victoria", self._sumar(
                    VICTORIA_VALE + SEGUNDO_VALE * (self.time // 60))))
            ev.append(("fin",))
        return ev

    def _golpe_tuyo(self, b, ev):
        b[0] = PX - 2
        venia = b[6]
        self._bounce(b, self.py, -1, self.ph_p, efecto=self.pvy)
        b[4] = YO
        self.rallies += 1
        self.racha += 1
        self._sumar(1)
        if venia == MAQUINA:
            ev.append(("devuelto", b[0], b[1], self._sumar(DEVUELTO_VALE)))
        if self.smash_t:
            # el smash: sale recta hacia donde apuntaste con el borde de la
            # paleta, rapidísima y en llamas
            # mitad la apuntas tú con el borde de la paleta, mitad busca sola
            # el hueco: la mitad de la cancha donde la máquina no está
            off = (b[1] - self.py) / self.ph_p
            hueco = COURT + 8 if self.cy > (COURT + H) / 2 else H - 8
            busca = (hueco - b[1]) / ((PX - CX) / SMASH_V)
            b[2] = -SMASH_V
            b[3] = max(-3.0, min(3.0, off * 1.6 + busca * 0.6))
            b[5] = 0.0
            b[6] = YO
            self.smash_t = 0
            self.carga = 0
            self.smashes += 1
            self.parada = 5
            ev.append(("smash", b[0], b[1], self._sumar(SMASH_VALE)))
        else:
            self.carga = min(SMASH_CARGA, self.carga + 1)
            if self.carga == SMASH_CARGA and not self.smash_t:
                ev.append(("carga",))
        ev.append(("golpe", b[0], b[1], YO))
        if abs(b[5]) > 0.5:
            ev.append(("efecto", b[0], b[1]))
        if self.racha % RACHA_CADA == 0:
            vale = self._sumar(RACHA_VALE * (self.racha // RACHA_CADA))
            ev.append(("racha", self.racha, vale))
        # la máquina elige dónde equivocarse para la próxima
        err = RONDAS[self.ronda][2]
        self.cpu_err = self.rng.uniform(-err, err)

    def _golpe_suyo(self, b, ev):
        b[0] = CX + 2
        self._bounce(b, self.cy, 1, self.ph_c)
        b[4] = MAQUINA
        nombre = RONDAS[self.ronda][0]
        if nombre == "COMBERO":
            # la curva hacia el lado contrario de tu paleta
            lado = 1.0 if self.py < (COURT + H) / 2 else -1.0
            b[5] = lado * self.rng.uniform(0.7, 1.3)
        elif nombre == "FURIA" and self.rng.random() < FURIA_SMASH:
            b[2] = SMASH_V * 0.86
            b[6] = MAQUINA
            ev.append(("smash_suyo", b[0], b[1]))
        ev.append(("golpe", b[0], b[1], MAQUINA))

    def _punto(self, quien, b, ev):
        if quien == YO:
            self.pscore += 1
            ganado = self._sumar(PUNTO_VALE)
            if b[6] == YO:
                ganado += self._sumar(GANADOR_VALE)
                ev.append(("ganador", ganado))
            ev.append(("punto", YO, ganado))
        else:
            self.cscore += 1
            if self.racha >= RACHA_CADA:
                ev.append(("racha_rota", self.racha))
            self.racha = 0
            ev.append(("punto", MAQUINA, 0))
        if self.pscore == TO_WIN - 1 and self.cscore == TO_WIN - 1:
            ev.append(("punto_oro",))


# --- la piel -----------------------------------------------------------------
class World:
    def __init__(self):
        self.p = Pong()
        self.fx = Fx(gravity=0.0, max_parts=200, sombra=SHADOW)
        self.hitflash = 0
        self.fx.destello(WHITE)
        self.trail = []               # las últimas posiciones, para la estela
        self.use_mouse = False        # gana el último input que hayas usado
        self._lm = None
        self.touch = web.is_touch()
        self.hold = 0                 # frames con la flecha apretada (aceleración)
        self.carteles = []            # [texto, y, col, vida, vida0, k]
        self.combo_pulso = 0
        self.lento_vis = 0
        self.flash_paleta = 0
        self._cartel("RONDA 1", "TRANQUI", RONDA_COL[0])

    @property
    def over(self):
        return self.p.over

    @property
    def score(self):
        return self.p.score

    def _cartel(self, s, sub=None, col=GOLD, vida=70, k=3):
        """un cartel grande en el medio de la cancha (uno a la vez)."""
        self.carteles = [[s, sub, col, vida, vida, k]]

    # --- input ---------------------------------------------------------------
    def update(self):
        p = self.p
        _, ddy = web.drag()
        my = pyxel.mouse_y
        if not self.touch and self._lm is not None and my != self._lm:
            self.use_mouse = True
        self._lm = my
        up = pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W)
        down = pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S)
        if up or down or ddy:
            self.use_mouse = False
        if up or down:
            self.hold += 1
        else:
            self.hold = 0
        # con flechas acelera: el primer toque es fino, sostenido cruza rápido
        vel = min(4.4, 2.2 + self.hold * 0.28)
        if ddy:
            p.set_player(p.py + ddy)
        elif up:
            p.set_player(p.py - vel)
        elif down:
            p.set_player(p.py + vel)
        elif self.use_mouse:
            p.set_player(my)
        if pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_X) or \
                pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if p.pedir_smash():
                self.flash_paleta = 6
                self.fx.burst(PX, p.py, CHISPA_FUEGO, n=10, speed=1.4, life=14)
        self.hitflash = max(0, self.hitflash - 1)
        self.combo_pulso = max(0, self.combo_pulso - 1)
        self.flash_paleta = max(0, self.flash_paleta - 1)
        for e in p.step():
            self._efecto(e)
        if p.lento:
            self.lento_vis = min(8, self.lento_vis + 1)
        else:
            self.lento_vis = max(0, self.lento_vis - 1)
        if not p.parada:
            self.trail.append([(b[0], b[1], b[6], abs(b[2])) for b in p.balls])
            del self.trail[:-8]
        for b in p.balls:                     # la pelota en llamas larga brasas
            if b[6] and pyxel.frame_count % 2 == 0:
                self.fx.burst(b[0], b[1], CHISPA_FUEGO, n=2, speed=0.6, life=12,
                              angle=0.0 if b[2] < 0 else 3.1416, spread=1.2)
        for c in self.carteles:
            c[3] -= 1
        self.carteles = [c for c in self.carteles if c[3] > 0]
        self.fx.update()

    # --- jugo ----------------------------------------------------------------
    def _efecto(self, e):
        p = self.p
        kind = e[0]
        mid = (COURT + H) / 2
        if kind == "golpe":
            self.fx.burst(e[1], e[2], CHISPA_GOLPE, n=8, speed=1.5, life=14)
            self.fx.shake(2)
            self.hitflash = 4
            if e[3] == YO:
                self.combo_pulso = 10
        elif kind == "pared":
            self.fx.burst(e[1], e[2], (WHITE, TRAIL1, TRAIL2), n=4, speed=1.0,
                          life=10)
        elif kind == "efecto":
            self.fx.burst(e[1], e[2], (WHITE, MAGENTA, GLOW), n=10, speed=1.8,
                          life=18, spread=2.2, angle=3.1416)
            self.fx.popup(e[1] - 22, e[2] - 10, "efecto", MAGENTA, life=22)
        elif kind == "smash":
            self.fx.burst(e[1], e[2], CHISPA_FUEGO, n=34, speed=3.0, life=26,
                          spread=2.4, angle=3.1416)
            self.fx.shake(6)
            self.fx.destello(FIRE, 6)
            self._cartel("¡SMASH!", "+%d" % e[3], FIRE, vida=45)
        elif kind == "smash_suyo":
            self.fx.burst(e[1], e[2], CHISPA_FUEGO, n=20, speed=2.4, life=20,
                          spread=2.4)
            self.fx.shake(4)
            self.fx.popup(60, e[2] - 8, "¡SMASH SUYO!", WARN)
        elif kind == "devuelto":
            self.fx.burst(e[1], e[2], (WHITE, GOLD, GLOW), n=20, speed=2.2,
                          life=22, spread=2.4, angle=3.1416)
            self.fx.popup(e[1] - 30, e[2] - 10, "¡DEVUELTO! +%d" % e[3], GOLD)
            self.fx.shake(4)
        elif kind == "carga":
            self.fx.popup(PX - 30, p.py - p.ph_p - 8, "¡SMASH LISTO!", FIRE,
                          life=40)
            self.fx.burst(PX, p.py, CHISPA_FUEGO, n=12, speed=1.6, life=16)
        elif kind == "racha":
            self._cartel("COMBO %d" % e[1], "+%d" % e[2], GOLD, vida=55)
            self.fx.destello(GOLD)
            self.fx.shake(3)
        elif kind == "racha_rota":
            self.fx.popup(W - 50, mid + 12, "combo roto", WARN)
        elif kind == "punto":
            quien = e[1]
            x = W - 20 if quien == YO else 20
            self.fx.burst(x, mid, CHISPA_PUNTO, n=26, speed=2.6, life=30)
            if quien == YO:
                self._cartel("¡PUNTO!", "+%d" % e[2], ACCENT, vida=50)
            else:
                self._cartel("PUNTO SUYO", None, WARN, vida=50, k=2)
            self.fx.shake(5)
            self.fx.destello(ACCENT if quien == YO else WARN)
            self.trail = []
        elif kind == "ganador":
            self.fx.burst(20, mid, CHISPA_FUEGO, n=30, speed=3.0, life=30)
            self._cartel("¡GANADOR!", "+%d" % e[1], FIRE, vida=60)
        elif kind == "ladrillo":
            tipo = e[4]
            col = (GOLD, ARMOR, GOLD)[tipo]
            self.fx.burst(e[1], e[2], (WHITE, col, HOT, TRAIL2),
                          n=12 if tipo != NUCLEO else 30, speed=1.8, life=20)
            self.fx.popup(e[1] + 18, e[2] - 6, "+%d" % e[3], GOLD)
            self.fx.shake(2 if tipo != NUCLEO else 5)
            if tipo == NUCLEO:
                self.p.parada = max(self.p.parada, 4)
                self.fx.destello(GOLD, 6)
        elif kind == "blindado":
            self.fx.burst(e[1], e[2], (WHITE, ARMOR, ARMORDK), n=8, speed=1.4,
                          life=14)
            self.fx.shake(1)
        elif kind == "muro_nuevo":
            self._cartel("¡DERRIBADO!", "+%d · viene %s" % (e[1], e[2]), GOLD,
                         vida=80)
            self.fx.destello(GOLD, 6)
            self.fx.shake(4)
        elif kind == "power":
            tipo, dueño = e[1], e[2]
            self.fx.popup(W / 2, COURT + 30, POWER_NOMBRE[tipo],
                          GOLD if dueño == YO else MAGENTA)
            self.fx.destello(GOLD if dueño == YO else MAGENTA)
            self.fx.shake(3)
        elif kind == "escudo":
            self.fx.burst(e[1], e[2], (WHITE, SLOWC, GLOW), n=18, speed=2.0,
                          life=18)
            self.fx.popup(W - 50 if e[3] == YO else 50, e[2] - 8, "¡SALVADA!",
                          SLOWC)
            self.fx.shake(3)
        elif kind == "ronda":
            r = e[1]
            self._cartel("RONDA %d" % (r + 1), RONDAS[r][0], RONDA_COL[r],
                         vida=80)
            self.fx.destello(RONDA_COL[r], 6)
        elif kind == "oro":
            self._cartel("¡TIEMPO DE ORO!", "todo vale doble", GOLD, vida=90,
                         k=2)
            self.fx.destello(GOLD, 8)
            self.fx.shake(4)
        elif kind == "punto_oro":
            self._cartel("PUNTO DE ORO", "el que lo gana, gana", GOLD, vida=80,
                         k=2)
        elif kind == "lento":
            self.fx.popup(W / 2, H - 20, "¿llega?", SLOWC, life=30)
        elif kind == "victoria":
            self._cartel("¡GANASTE!", "+%d" % e[1], ACCENT, vida=120)
            self.fx.destello(ACCENT, 8)
            self.fx.burst(W / 2, mid, (WHITE, GOLD, ACCENT, GLOW), n=60,
                          speed=3.0, life=40)

    # --- dibujo --------------------------------------------------------------
    def draw(self):
        p = self.p
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        self._cancha()
        for l in p.muro:
            if l[2]:
                self._ladrillo(l)
        for px_, py_, tipo, ttl in p.powers:
            self._power(px_, py_, tipo, ttl)
        self._estela()
        self._paletas()
        col = BALLC if self.hitflash == 0 else WHITE
        for b in p.balls:
            if p.saque and (pyxel.frame_count // 5) % 2:
                continue                       # el saque titila
            bc = col
            if b[6]:
                bc = GOLD if (pyxel.frame_count // 2) % 2 else FIRE
            elif p.oro:
                bc = GOLD
            x, y = int(b[0]), int(b[1])
            pyxel.rect(x - 2, y - 2, 4, 4, bc)
            pyxel.pset(x - 2, y - 2, SHADOW if not b[6] else WHITE)
            if abs(b[5]) > 0.3:                # con efecto: gira
                k = (pyxel.frame_count // 3) % 4
                dx, dy = ((-2, -2), (1, -2), (1, 1), (-2, 1))[k]
                pyxel.pset(x + dx, y + dy, MAGENTA)
        self.fx.draw(0, 0)
        pyxel.camera()
        self._carteles()
        if self.lento_vis:                     # cámara lenta: bandas de cine
            h = self.lento_vis
            pyxel.rect(0, COURT, W, h, SHADOW)
            pyxel.rect(0, H - h, W, h, SHADOW)
        self.fx.draw_flash(0, COURT, W, H - COURT)
        self._hud()

    def _cancha(self):
        p = self.p
        pyxel.rect(0, COURT, W, H - COURT, OROC if p.oro else COURTC)
        # el tanteo gigante de fondo, como en el pong de verdad
        cbig(W // 4 + 4, COURT + 10, "%d" % p.cscore, BIGC, k=4)
        cbig(3 * W // 4, COURT + 10, "%d" % p.pscore, BIGC, k=4)
        # el combo, gigante, detrás de todo
        if p.racha >= 3:
            k = 4 if self.combo_pulso > 6 else 3
            col = GOLDDK if p.racha % RACHA_CADA >= RACHA_CADA - 3 else BIGC2
            cbig(W // 2 + 1, (COURT + H) // 2 + 14, "%d" % p.racha, col, k=k)
            ctext(W // 2 + 1, (COURT + H) // 2 + 14 + 6 * k, "combo", col)
        r = p.ronda
        text(4, COURT + 4, RONDAS[r][0], RONDA_COL[r])
        if p.muro_n:
            text(4, H - 8, p.nombre_muro().lower(), GOLDDK)
        for y in range(COURT, H, 8):             # red punteada
            pyxel.rect(W // 2 - 1, y, 2, 4, NET)
        bord = GOLD if p.oro else NET
        pyxel.rect(0, COURT, W, 1, bord)
        pyxel.rect(0, H - 1, W, 1, bord)
        # las murallas: una línea que late en el arco
        if p.escudo_p:
            c = SLOWC if p.escudo_p > 90 or (pyxel.frame_count // 4) % 2 else GLOW
            pyxel.rect(W - 2, COURT, 2, H - COURT, c)
        if p.escudo_c:
            c = MAGENTA if p.escudo_c > 90 or (pyxel.frame_count // 4) % 2 else MAGDK
            pyxel.rect(0, COURT, 2, H - COURT, c)

    def _ladrillo(self, l):
        x, y = int(l[0]), int(l[1])
        tipo = l[3] if len(l) > 3 else NORMAL
        if tipo == NUCLEO:
            c = GOLD if (pyxel.frame_count // 8) % 2 else HOT
            pyxel.rect(x - 1, y, LADRILLO_W + 2, LADRILLO_H, c)
            pyxel.rectb(x - 1, y, LADRILLO_W + 2, LADRILLO_H, WHITE)
            for i in range(l[2]):              # cuántos golpes le quedan
                pyxel.pset(x + 1 + i, y + LADRILLO_H // 2, SHADOW)
            return
        if tipo == BLINDADO:
            c = ARMOR if l[2] > 1 else ARMORDK
            pyxel.rect(x, y + 1, LADRILLO_W, LADRILLO_H - 2, c)
            pyxel.rect(x, y + 1, LADRILLO_W, 1, WHITE)
            pyxel.pset(x + 2, y + 4, SHADOW)
            if l[2] == 1:                      # rajado
                pyxel.line(x + 1, y + 3, x + 3, y + 7, SHADOW)
            return
        pyxel.rect(x, y + 1, LADRILLO_W, LADRILLO_H - 2, GOLD)
        pyxel.rect(x, y + LADRILLO_H - 2, LADRILLO_W, 1, GOLDDK)
        pyxel.rect(x, y + 1, LADRILLO_W, 1, WHITE)

    def _paletas(self):
        p = self.p
        r = p.ronda
        # la máquina: el color de su personalidad
        cc, cd = RONDA_COL[r], RONDA_DK[r]
        x, y, h = int(CX - 3), int(p.cy - p.ph_c), p.ph_c * 2
        pyxel.rect(x, y, 4, h, cc)
        pyxel.rect(x + 3, y, 1, h, cd)
        pyxel.rect(x, y, 4, 1, WHITE)
        # tú. con la ventana de smash abierta, la paleta arde y se adelanta
        lista = p.carga >= SMASH_CARGA
        x, y, h = int(PX - 1), int(p.py - p.ph_p), p.ph_p * 2
        if p.smash_t:
            x -= 2
            c = WHITE if (pyxel.frame_count // 2) % 2 else FIRE
            pyxel.rect(x - 1, y - 1, 6, h + 2, FIRE)
            pyxel.rect(x, y, 4, h, c)
        else:
            c = PLAYER
            if lista and (pyxel.frame_count // 6) % 2:
                c = GOLD
            pyxel.rect(x, y, 4, h, c)
            pyxel.rect(x, y, 1, h, PLAYERDK if c == PLAYER else GOLDDK)
            pyxel.rect(x, y, 4, 1, WHITE)
        if p.ttl_p:                              # halo del efecto activo
            pyxel.rectb(int(PX - 2), int(p.py - p.ph_p - 1), 6, p.ph_p * 2 + 2,
                        GOLD)
        if p.ttl_c:
            pyxel.rectb(int(CX - 4), int(p.cy - p.ph_c - 1), 6, p.ph_c * 2 + 2,
                        MAGENTA)

    def _estela(self):
        """las posiciones viejas de cada pelota, más largas y calientes cuanto
        más rápido va; la que está en llamas deja fuego."""
        n = len(self.trail)
        for i, snap in enumerate(self.trail):
            f = i / max(1, n - 1)
            for bx, by, fuego, v in snap:
                if fuego:
                    c = (WARNDK, FIRE, HOT, GOLD)[min(3, int(f * 4))]
                    s = 2 + int(f * 2)
                elif v > 3.4 and i >= n - 5:
                    c = (HOT, HOT, GOLD, GOLD, WHITE)[min(4, i - (n - 5))]
                    s = 2
                elif i >= n - 5:
                    c = (TRAIL3, TRAIL3, TRAIL2, TRAIL2, TRAIL1)[min(4, i - (n - 5))]
                    s = 2
                else:
                    continue
                pyxel.rect(int(bx - s / 2), int(by - s / 2), s, s, c)

    def _power(self, x, y, tipo, ttl):
        if ttl < 90 and (pyxel.frame_count // 4) % 2:      # titila antes de irse
            return
        col = (ACCENT, WARN, GOLD, HOT, SLOWC)[tipo]
        r = 6 + (pyxel.frame_count // 6) % 2
        pyxel.rect(x - r, y - r, r * 2, r * 2, SHADOW)
        pyxel.rectb(x - r, y - r, r * 2, r * 2, col)
        if tipo == LARGA:
            pyxel.rect(x - 1, y - 4, 2, 8, col)
            pyxel.pset(x - 2, y - 3, col)
            pyxel.pset(x + 1, y - 3, col)
            pyxel.pset(x - 2, y + 2, col)
            pyxel.pset(x + 1, y + 2, col)
        elif tipo == CORTA:
            pyxel.rect(x - 1, y - 2, 2, 4, col)
        elif tipo == MULTI:
            pyxel.rect(x - 3, y - 3, 2, 2, col)
            pyxel.rect(x + 1, y - 1, 2, 2, col)
            pyxel.rect(x - 2, y + 2, 2, 2, col)
        elif tipo == ESCUDO:
            pyxel.rect(x - 3, y - 3, 6, 4, col)
            pyxel.rect(x - 2, y + 1, 4, 2, col)
            pyxel.pset(x - 1, y + 3, col)
            pyxel.pset(x, y + 3, col)
        else:
            pyxel.line(x + 1, y - 4, x - 2, y, col)
            pyxel.line(x - 2, y, x + 1, y + 1, col)
            pyxel.line(x + 1, y + 1, x - 1, y + 4, col)

    def _carteles(self):
        for s, sub, col, vida, vida0, k in self.carteles:
            if vida < vida0 * 0.3 and (vida // 3) % 2:
                continue
            # entra grande y se asienta
            kk = k + 1 if vida > vida0 - 5 else k
            y = (COURT + H) // 2 - 22
            cbig(W // 2, y, s, col, k=kk, sombra=SHADOW)
            if sub:
                ctext(W // 2 + 1, y + 6 * kk + 4, sub, SHADOW)
                ctext(W // 2, y + 6 * kk + 3, sub, WHITE)

    def _hud(self):
        p = self.p
        pyxel.rect(0, 0, W, HUD, HUDC)
        pyxel.rect(0, HUD - 1, W, 1, GOLD if p.oro else NET)
        # el puntaje, grande: es lo que va a los récords
        big(3, 3, "%d" % p.score, GOLD if p.oro else ACCENT, k=2)
        if p.oro:
            text(3 + len("%d" % p.score) * 8 + 2, 3, "x2", GOLD)
        # el smash: cuatro rayitas que se llenan; llena, titila
        sx = 54
        lista = p.carga >= SMASH_CARGA
        lab = "SMASH"
        lc = FIRE if lista and (pyxel.frame_count // 6) % 2 else (
            WHITE if lista else DIM)
        text(sx, 2, lab, lc)
        for i in range(SMASH_CARGA):
            c = FIRE if i < p.carga else NET
            if lista:
                c = GOLD if (pyxel.frame_count // 6) % 2 else FIRE
            pyxel.rect(sx + i * 5, 9, 4, 4, c)
        # el tanteo, con el color de cada uno
        cx = W // 2 + 4
        r = p.ronda
        cs = "%d" % p.cscore
        big(cx - 5 - ancho(cs), 3, cs, RONDA_COL[r], k=2)
        text(cx - 18 - ancho(cs), 5, "cpu", RONDA_COL[r])
        pyxel.rect(cx - 2, 7, 2, 2, TXT)
        ps = "%d" % p.pscore
        big(cx + 3, 3, ps, ACCENT, k=2)
        text(cx + 6 + ancho(ps), 5, "tú", ACCENT)
        # el reloj: número grande y barra
        s = p.time // 60
        col = WHITE
        if s <= 10:
            col = WARN if pyxel.frame_count % 30 < 15 else WHITE
        rs = "%d" % s
        big(W - len(rs) * 8 - 2, 3, rs, col, k=2)
        fx.bar(W - 60, 6, 32, 4, p.time / TIME, GOLD if p.oro else ACCENT, NET)
        pyxel.rect(W - 60 + int(32 * ORO_T / TIME), 5, 1, 6, GOLD)


class Game:
    def __init__(self):
        touch = web.is_touch()
        Cabinet(
            game_id="pong", title="PONG", subtitle="90 segundos contra la máquina",
            howto=["arrastra en el panel para mover" if touch else
                   "mouse o flechas mueven",
                   "cada 4 devoluciones: SMASH (botón al pegar)" if touch else
                   "cada 4 devoluciones: SMASH (espacio al pegar)",
                   "rompe el muro · muévete al pegar: efecto"],
            width=W, height=H, palette=PAL, scale=3,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=COURTC),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
