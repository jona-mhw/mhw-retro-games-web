"""pong — 90 segundos contra la máquina, para el cabinet MHW · RETRO · FUTURE.

la cancha va parada, como los pong y air hockey de celular: tú abajo, la
máquina arriba, y la paleta se mueve de lado a lado (con el trackpad, el dedo
sobre la cancha, el mouse o las flechas).

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
  pagan. cada muro derribado trae el siguiente patrón: hilera, tablero,
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

la física vive en la clase Pong, sin pyxel. coordenadas de pantalla: x va de
lado a lado (las bandas), y de arco a arco (la máquina arriba, en y chica). el
reloj baja un frame por step pase lo que pase (saques, pausas de golpe y
cámara lenta incluidos), así que no hay peloteo ni efecto que estire la
partida, y eso se prueba sin jugar.
"""
import random

import pyxel

from pixelkit import fx, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import big_ctext, big_text, big_width, text

from .grande import Fx

W, H = 240, 360
HUD = 24
COURT = HUD                      # la línea del arco de la máquina
MID = (COURT + H) // 2           # la red
LARGO = H - COURT
RIEL = 4                         # las bandas de los costados, donde rebota
BR = 3                           # radio de la pelota
PH = 40                          # largo de la paleta
PHALF = PH // 2
GROSOR = 7                       # y su grosor
FACE_P = H - 16                  # la cara de tu paleta (abajo)
FACE_C = COURT + 16              # la de la máquina (arriba)
TO_WIN = 11                      # a 11, como el ping-pong
TIME = 90 * 60                   # el round entero: nada lo estira
SAQUE = 40                       # la pelota espera en el medio tras un punto

# velocidades (px por frame). la cancha mide ~1,5 veces la de antes, y todo
# va 1,5 veces más rápido: un cruce tarda lo mismo que en la cancha acostada
SAQUE_V, SAQUE_LAT = 2.8, 1.6
VMAX = 6.3                       # hacia el arco
LAT_MAX = 4.8                    # de costado
LAT_PEGADA = 2.1                 # cuánto ángulo da pegarle con la punta

LARGA, CORTA, MULTI, TURBO, ESCUDO = range(5)
POWER_NOMBRE = {LARGA: "¡LARGA!", CORTA: "¡CORTA!", MULTI: "¡MULTIBOLA!",
                TURBO: "¡TURBO!", ESCUDO: "¡MURALLA!"}
POWER_GAP = 6 * 60
POWER_TTL = 10 * 60
POWER_R = 9                      # media caja
EFECTO_TTL = 8 * 60
ESCUDO_TTL = 9 * 60
PH_LARGA, PH_CORTA = 62, 22
MAX_BALLS = 5
YO, MAQUINA = 1, -1              # quién tocó la pelota por última vez

# una pelota es [x, y, vx, vy, dueño, comba, fuego, drama]. los tests arman
# pelotas de 5; `_pad` completa lo que falte.
BALL_LEN = 8

# --- el muro -----------------------------------------------------------------
# delante de la máquina, de banda a banda. la pelota los rompe y suman aparte
# del peloteo, así que conviene apuntarle en vez de sólo devolver. cuando cae
# el último, viene el patrón siguiente. un ladrillo es [x, y, vida, tipo], con
# (x, y) su esquina de arriba a la izquierda.
LAD_W, LAD_H = 15, 8
LADRILLOS = 9
LAD_Y = FACE_C + 18
NORMAL, BLINDADO, NUCLEO = range(3)
LADRILLO_VALE = 15
VALE = {NORMAL: LADRILLO_VALE, BLINDADO: 25, NUCLEO: 60}
MURO_BONO = 30
MUROS = ("HILERA", "TABLERO", "MURO MÓVIL", "EL BÚNKER")

# el efecto: la velocidad de la paleta al pegar se vuelve comba. la pelota va
# curvando su vx cada frame y la comba se disipa sola.
EFECTO_GANANCIA = 0.22
EFECTO_MAX = 2.1
EFECTO_CURVA = 0.045
EFECTO_DISIPA = 0.975
COMBA_VMAX = 5.1

# la racha (el combo): devoluciones seguidas sin que la máquina te saque un
# punto. paga cada 10, y cada vez más: 10, 20, 30...
RACHA_CADA = 10
RACHA_VALE = 10

# el smash
SMASH_CARGA = 4                  # devoluciones para cargarlo
SMASH_VENTANA = 22               # frames en que la paleta pega en llamas
SMASH_ESPERA = 24                # si erraste la ventana, cuánto para volver a probar
SMASH_V = 7.5
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
RONDAS = (("TRANQUI", 0.82, 25, 0.58), ("COMBERO", 1.0, 18, 0.7),
          ("FURIA", 1.12, 12, 0.85))
CPU_BASE, CPU_SUBE = 2.6, 0.021
CPU_TOPE = 4.95
FURIA_SMASH = 0.22               # chance de que FURIA devuelva en llamas

ORO_T = 15 * 60                  # los últimos 15 s valen doble
LENTO = 30                       # frames de cámara lenta
LENTO_K = 0.32
LENTO_MAX = 6                    # cuántas veces por partida


def _pad(b):
    while len(b) < BALL_LEN:
        b.append(0.0 if len(b) == 5 else 0)
    return b


def _clamp(v, m):
    return max(-m, min(m, v))


class Pong:
    """la cancha: paletas, pelotas, poderes y tanteo. sin pyxel, testeable."""

    def __init__(self, rng=None):
        self.rng = rng or random
        self.reset()

    def reset(self):
        self.px = self.cx = W / 2                # centros de las paletas (en x)
        self.pscore = self.cscore = 0
        self.rallies = 0                         # devoluciones (cuenta, no puntaje)
        self.pts = 0                             # el puntaje
        self.over = False
        self.time = TIME
        self.balls = []
        self.powers = []                         # [x, y, tipo, ttl]
        self.power_t = POWER_GAP
        self.ph_p = self.ph_c = PHALF            # medio largo de cada paleta
        self.ttl_p = self.ttl_c = 0
        self.escudo_p = self.escudo_c = 0
        self.muro = []
        self.muro_n = 0                          # cuántos muros van
        self.muro_vx = 0.0
        self.pvx = 0.0                           # con qué velocidad viene tu paleta
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
        base = CPU_BASE + self.rallies * CPU_SUBE
        return min(CPU_TOPE, base * RONDAS[self.ronda][1])

    def _serve(self, diry):
        if self.pscore >= TO_WIN or self.cscore >= TO_WIN:
            self.over = True
            return
        vx = self.rng.uniform(-SAQUE_LAT, SAQUE_LAT)
        self.balls = [_pad([W / 2, MID, vx, SAQUE_V * diry, 0])]
        self.saque = SAQUE

    # --- el muro -------------------------------------------------------------
    def _armar_muro(self):
        """el patrón que toca. el primero es la hilera de siempre; después
        rotan tablero, móvil y búnker."""
        n = self.muro_n
        pat = 0 if n == 0 else 1 + (n - 1) % 3
        self.muro_vx = 0.0
        m = []
        if pat == 0:                             # hilera
            x0 = W / 2 - LADRILLOS * LAD_W / 2
            m = [[x0 + i * LAD_W, LAD_Y, 1, NORMAL] for i in range(LADRILLOS)]
        elif pat == 1:                           # tablero: dos hileras en damero
            x0 = W / 2 - 12 * LAD_W / 2
            for i in range(12):
                y = LAD_Y + (LAD_H + 2) * (i % 2)
                m.append([x0 + i * LAD_W, y, 1, NORMAL])
        elif pat == 2:                           # muro móvil: va de banda a banda
            x0 = W / 2 - 7 * LAD_W / 2
            m = [[x0 + i * LAD_W, LAD_Y, 1,
                  BLINDADO if i in (0, 6) else NORMAL] for i in range(7)]
            self.muro_vx = 0.8
        else:                                    # el búnker
            x0 = W / 2 - 9 * LAD_W / 2
            for i in range(9):
                tipo = NUCLEO if i == 4 else (BLINDADO if i in (3, 5) else NORMAL)
                m.append([x0 + i * LAD_W, LAD_Y,
                          {NORMAL: 1, BLINDADO: 2, NUCLEO: 3}[tipo], tipo])
            for i in (2, 3, 5, 6):               # una segunda capa blindada
                m.append([x0 + i * LAD_W, LAD_Y + LAD_H + 2, 2, BLINDADO])
            self.muro_vx = 0.45
        self.muro = m

    def nombre_muro(self):
        n = self.muro_n
        return MUROS[0 if n == 0 else 1 + (n - 1) % 3]

    def _mover_muro(self):
        if not self.muro_vx:
            return
        vivos = [l for l in self.muro if l[2]]
        if not vivos:
            return
        izq = min(l[0] for l in vivos)
        der = max(l[0] for l in vivos) + LAD_W
        if izq + self.muro_vx < RIEL + 2 or der + self.muro_vx > W - RIEL - 2:
            self.muro_vx = -self.muro_vx
        for l in self.muro:
            l[0] += self.muro_vx

    def _pegar_muro(self, b, ev):
        """¿la pelota tocó un ladrillo? lo golpea y rebota (la pelota en
        llamas no rebota: lo atraviesa)."""
        _pad(b)
        for l in self.muro:
            if not l[2]:
                continue
            if l[0] <= b[0] <= l[0] + LAD_W and \
                    l[1] - BR <= b[1] <= l[1] + LAD_H + BR:
                tipo = l[3] if len(l) > 3 else NORMAL
                fuego = b[6]
                l[2] = 0 if fuego else l[2] - 1
                if not fuego:
                    b[3] = abs(b[3])             # sale rebotado hacia ti
                self.rallies += 1
                cx, cy = l[0] + LAD_W / 2, l[1] + LAD_H / 2
                if l[2]:
                    self._sumar(2)
                    ev.append(("blindado", cx, cy))
                    return True
                ganado = self._sumar(VALE[tipo] * (2 if fuego else 1))
                ev.append(("ladrillo", cx, cy, ganado, tipo))
                if not any(x[2] for x in self.muro):
                    bono = self._sumar(MURO_BONO)
                    self.muro_n += 1
                    self._armar_muro()
                    ev.append(("muro_nuevo", bono, self.nombre_muro()))
                return True
        return False

    # --- tu paleta -----------------------------------------------------------
    def set_player(self, x):
        antes = self.px
        self.px = min(W - RIEL - self.ph_p, max(RIEL + self.ph_p, x))
        self.pvx = self.px - antes

    def pedir_smash(self):
        """el botón. con la carga llena abre la ventana; si no, nada."""
        if self.carga >= SMASH_CARGA and not self.smash_t and \
                not self.smash_cd and not self.over:
            self.smash_t = SMASH_VENTANA
            return True
        return False

    def _bounce(self, b, paddle_x, diry, half, efecto=0.0):
        off = (b[0] - paddle_x) / half           # -1..1 según dónde pegó
        b[3] = diry * min(VMAX, abs(b[3]) * 1.06 + 0.08)
        b[2] = _clamp(b[2] + off * LAT_PEGADA, LAT_MAX)
        _pad(b)
        # la comba: se guarda en la pelota y curva la vx frame a frame
        b[5] = _clamp(efecto * EFECTO_GANANCIA, EFECTO_MAX)
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
            base = self.balls[0] if self.balls else [W / 2, MID, 0.6, SAQUE_V, 0]
            for d in (-1.0, 1.0):
                if len(self.balls) < MAX_BALLS:
                    self.balls.append(_pad([base[0], base[1],
                                            base[2] + d * 1.35, base[3], base[4]]))
        elif tipo == ESCUDO:
            if dueño == MAQUINA:
                self.escudo_c = ESCUDO_TTL
            else:
                self.escudo_p = ESCUDO_TTL
        else:                                    # turbo a todo lo que se mueva
            for b in self.balls:
                b[3] *= 1.35
                b[2] *= 1.15
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
            self.pvx = 0.0
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
        self.pvx = 0.0            # la comba es de ESTE frame: si no te moviste, no hay
        if not self.balls and not self.over:
            self._serve(self.rng.choice((-1, 1)))
        return ev

    def _mover_cpu(self):
        """persigue la pelota que le viene, no cualquiera: con multibola,
        elegir mal es lo que la hace fallar (y es justo)."""
        objetivo = None
        for b in self.balls:
            if b[3] < 0 and (objetivo is None or b[1] < objetivo[1]):
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
        meta = objetivo[0] + (self.cpu_err if objetivo[3] < 0 else 0)
        if objetivo[3] >= 0 or objetivo[1] - COURT > LARGO * RONDAS[self.ronda][3]:
            # todavía no reacciona: vuelve al medio, sin apuro
            meta = W / 2
            v *= 0.5
        if self.cx < meta - 2:
            self.cx += min(v, meta - self.cx)
        elif self.cx > meta + 2:
            self.cx -= min(v, self.cx - meta)
        self.cx = min(W - RIEL - self.ph_c, max(RIEL + self.ph_c, self.cx))

    def _spawn_power(self):
        if self.powers:
            for p in self.powers:
                p[3] -= 1
            self.powers = [p for p in self.powers if p[3] > 0]
            return
        self.power_t -= 1
        if self.power_t <= 0:
            x = self.rng.randint(RIEL + 20, W - RIEL - 20)
            y = self.rng.randint(MID - 60, MID + 60)
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
        if b[3] > 0 and b[1] > H - 72 and abs(b[0] - self.px) > self.ph_p + 9:
            lado = YO
        elif b[3] < 0 and b[1] < COURT + 72 and abs(b[0] - self.cx) > self.ph_c + 9:
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
                b[2] = _clamp(b[2] + b[5] * EFECTO_CURVA * k, COMBA_VMAX)
                b[5] *= EFECTO_DISIPA
                if abs(b[5]) < 0.02:
                    b[5] = 0.0
            self._drama(b, ev)
            b[0] += b[2] * k
            b[1] += b[3] * k
            if b[0] < RIEL + BR:
                b[0] = RIEL + BR
                b[2] = abs(b[2])
                ev.append(("pared", b[0], b[1]))
            if b[0] > W - RIEL - BR:
                b[0] = W - RIEL - BR
                b[2] = -abs(b[2])
                ev.append(("pared", b[0], b[1]))
            # tu paleta (abajo)
            if b[3] > 0 and b[1] >= FACE_P - BR and \
                    abs(b[0] - self.px) <= self.ph_p + BR:
                self._golpe_tuyo(b, ev)
            # la de la máquina (arriba)
            if b[3] < 0 and b[1] <= FACE_C + BR and \
                    abs(b[0] - self.cx) <= self.ph_c + BR:
                self._golpe_suyo(b, ev)
            self._pegar_muro(b, ev)
            # cajas de poder: las activa la pelota, a favor de quien la tocó
            for p in list(self.powers):
                if abs(b[0] - p[0]) < POWER_R and abs(b[1] - p[1]) < POWER_R:
                    self.powers.remove(p)
                    self._tomar(p[2], b[4] or YO, ev)
                    self.power_t = POWER_GAP
                    break
            # las murallas: salvan una pelota y se gastan
            if b[1] > H - 4 and b[3] > 0 and self.escudo_p:
                self.escudo_p = 0
                b[1], b[3] = H - 4, -abs(b[3])
                ev.append(("escudo", b[0], b[1], YO))
            elif b[1] < COURT + 4 and b[3] < 0 and self.escudo_c:
                self.escudo_c = 0
                b[1], b[3] = COURT + 4, abs(b[3])
                ev.append(("escudo", b[0], b[1], MAQUINA))
            if b[1] < COURT:
                self._punto(YO, b, ev)
            elif b[1] > H:
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
        b[1] = FACE_P - BR
        venia = b[6]
        self._bounce(b, self.px, -1, self.ph_p, efecto=self.pvx)
        b[4] = YO
        self.rallies += 1
        self.racha += 1
        self._sumar(1)
        if venia == MAQUINA:
            ev.append(("devuelto", b[0], b[1], self._sumar(DEVUELTO_VALE)))
        if self.smash_t:
            # el smash: sale rapidísima y en llamas. mitad la apuntas tú con
            # la punta de la paleta, mitad busca sola el hueco: la mitad de la
            # cancha donde la máquina no está
            off = (b[0] - self.px) / self.ph_p
            hueco = RIEL + 12 if self.cx > W / 2 else W - RIEL - 12
            busca = (hueco - b[0]) / ((FACE_P - FACE_C) / SMASH_V)
            b[3] = -SMASH_V
            b[2] = _clamp(off * 2.4 + busca * 0.6, 4.5)
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
        if abs(b[5]) > 0.75:
            ev.append(("efecto", b[0], b[1]))
        if self.racha % RACHA_CADA == 0:
            vale = self._sumar(RACHA_VALE * (self.racha // RACHA_CADA))
            ev.append(("racha", self.racha, vale))
        # la máquina elige dónde equivocarse para la próxima
        err = RONDAS[self.ronda][2]
        self.cpu_err = self.rng.uniform(-err, err)

    def _golpe_suyo(self, b, ev):
        b[1] = FACE_C + BR
        self._bounce(b, self.cx, 1, self.ph_c)
        b[4] = MAQUINA
        nombre = RONDAS[self.ronda][0]
        if nombre == "COMBERO":
            # la curva hacia el lado contrario de tu paleta
            lado = 1.0 if self.px < W / 2 else -1.0
            b[5] = lado * self.rng.uniform(1.05, 1.95)
        elif nombre == "FURIA" and self.rng.random() < FURIA_SMASH:
            b[3] = SMASH_V * 0.86
            b[6] = MAQUINA
            ev.append(("smash_suyo", b[0], b[1]))
        ev.append(("golpe", b[0], b[1], MAQUINA))

    def _punto(self, quien, b, ev):
        if quien == YO:
            self.pscore += 1
            ganado = self._sumar(PUNTO_VALE)
            if b[6] == YO:
                ganado += self._sumar(GANADOR_VALE)
                ev.append(("ganador", ganado, b[0]))
            ev.append(("punto", YO, ganado, b[0]))
        else:
            self.cscore += 1
            if self.racha >= RACHA_CADA:
                ev.append(("racha_rota", self.racha))
            self.racha = 0
            ev.append(("punto", MAQUINA, 0, b[0]))
        if self.pscore == TO_WIN - 1 and self.cscore == TO_WIN - 1:
            ev.append(("punto_oro",))


# --- la piel -----------------------------------------------------------------
# la paleta: rampas de 3-4 tonos (luz, medio, sombra, contorno) por color.
(BG, SHADOW, WHITE, TXT, DIM, HUDC, HUD2, HUD3,
 # el piso de la cancha, de lo más oscuro al brillo, y sus líneas
 F0, F1, F2, F3, F4, FDOT, FLIN, FLIN2,
 # el piso en el tiempo de oro
 O0, O1, O2, O3, O4, ODOT, OLIN, OLIN2,
 # las bandas
 RAIL0, RAIL1, RAIL2, RAIL3,
 # tú (verde)
 P0, P1, P2, P3,
 # la máquina: una rampa por personalidad
 C0, C1, C2, C3, M0, M1, M2, M3, R0, R1, R2, R3,
 # la pelota
 B0, B1, B2,
 # oro, fuego, blindado, frío
 G0, G1, G2, G3, FIRE, HOT, EMBER, A0, A1, A2, A3, SLOW, GLOW, SLOWDK,
 # los números grandes del fondo
 BIG1, BIG2, OBIG) = range(64)
PAL = [
    0x0A0C14, 0x04050A, 0xFFFFFF, 0xE8ECF5, 0x8A94B0, 0x080A12, 0x141A2C,
    0x232C48,
    0x0B1428, 0x101C36, 0x152446, 0x1B2E56, 0x27406E, 0x0D1730, 0x2E4A82,
    0x4A6CB0,
    0x1A1208, 0x24190B, 0x30220F, 0x3E2C14, 0x5A421C, 0x1E150A, 0x7A5A22,
    0xB48A34,
    0x05070E, 0x26304E, 0x46567E, 0x8A9ACA,
    0x1C3A0A, 0x3E7A16, 0x8CD836, 0xD8FF96,
    0x3A1A06, 0x8A4A14, 0xFF9A3E, 0xFFD6A8, 0x3A0A34, 0x84267A, 0xF05AD0,
    0xFFB8F2, 0x3E0A06, 0x962014, 0xFF4A34, 0xFFA898,
    0x5A6680, 0xC4CCE0, 0xFFFFFF,
    0x5A3A0E, 0xA8741E, 0xFFD24A, 0xFFF2A8, 0xFF5A1F, 0xFF8A3A, 0x9A2418,
    0x24283E, 0x5A668E, 0xB4C0E0, 0xE8EEFF, 0x4DA6FF, 0x9AE6FF, 0x1E4A8A,
    0x1E3260, 0x2A4478, 0x4A3616,
]
assert len(PAL) == OBIG + 1
PAL += [0] * (256 - len(PAL))

PLAYER_R = (P0, P1, P2, P3)                     # contorno, sombra, medio, luz
RONDA_R = ((C0, C1, C2, C3), (M0, M1, M2, M3), (R0, R1, R2, R3))
RONDA_COL = tuple(r[2] for r in RONDA_R)
GOLD = G2
ACCENT = P2
WARN = R2
MAGENTA = M2

CHISPA_GOLPE = (WHITE, GLOW, B1, B0)
CHISPA_PUNTO = (WHITE, R3, HOT, R1)
CHISPA_FUEGO = (WHITE, G3, FIRE, EMBER)
CHISPA_ORO = (WHITE, G3, G2, G1)

_FONDOS = {}


def _fondo(oro):
    """la cancha entera, horneada una vez en una imagen: piso con foco de luz
    y brillo, la grilla de agujeritos del air hockey, líneas, bandas y el
    panel del HUD. por frame es un solo blt."""
    if oro in _FONDOS:
        return _FONDOS[oro]
    f0, f1, f2, f3, f4, dot, lin, lin2 = (
        (O0, O1, O2, O3, O4, ODOT, OLIN, OLIN2) if oro else
        (F0, F1, F2, F3, F4, FDOT, FLIN, FLIN2))
    img = pyxel.Image(W, H)
    img.cls(BG)
    # el HUD: un panel con degradé y un filo abajo
    img.rect(0, 0, W, HUD, HUDC)
    img.dither(0.5)
    img.rect(0, 0, W, 9, HUD2)
    img.dither(1.0)
    img.rect(0, HUD - 3, W, 1, HUD3)
    img.rect(0, HUD - 2, W, 2, SHADOW)
    # el piso: foco de luz en el medio que se apaga hacia los arcos, con
    # tramado entre tono y tono para que el degradé no haga escalones
    img.clip(0, COURT, W, LARGO)
    cx = W // 2
    tonos = (f0, f1, f2, f3)
    for y in range(COURT, H):
        # fila por fila: el tono de abajo entero y el de arriba tramado, con
        # la proporción justa (el tramado ordenado hace el degradé suave)
        t = 1.0 - abs(y - MID) / (LARGO / 2)
        nivel = max(0.0, min(2.999, t * t * 0.6 * 3 + t * 0.4 * 3))
        i = int(nivel)
        img.line(0, y, W, y, tonos[i])
        img.dither(nivel - i)
        img.line(0, y, W, y, tonos[i + 1])
        img.dither(1.0)
    # y de costado: más oscuro contra las bandas
    for d in range(40):
        img.dither(0.4 * (1 - d / 40) ** 1.5)
        img.line(RIEL + d, COURT, RIEL + d, H, SHADOW)
        img.line(W - RIEL - 1 - d, COURT, W - RIEL - 1 - d, H, SHADOW)
    img.dither(1.0)
    # el brillo: una franja en diagonal, como el reflejo de un piso encerado
    for x0, ancho, alfa in ((156, 30, 0.16), (168, 3, 0.35), (196, 6, 0.2)):
        img.dither(alfa)
        for i in range(ancho):
            img.line(x0 + i, COURT, x0 + i - 150, H, f4)
    img.dither(1.0)
    # la grilla del air hockey: agujeritos en tresbolillo
    for j, y in enumerate(range(COURT + 7, H - 3, 9)):
        for x in range(RIEL + 6 + (j % 2) * 5, W - RIEL - 3, 10):
            img.pset(x, y, dot)
    # las líneas: red, círculo central y las áreas de cada arco
    img.rect(RIEL, MID - 1, W - 2 * RIEL, 2, lin)
    img.dither(0.5)
    img.rect(RIEL, MID - 2, W - 2 * RIEL, 1, lin2)
    img.dither(1.0)
    img.circb(cx, MID, 30, lin)
    img.circb(cx, MID, 29, lin)
    img.circ(cx, MID, 3, lin2)
    for y in (COURT, H):
        img.circb(cx, y, 46, lin)
    img.rect(cx - 60, COURT + 1, 120, 1, lin)
    img.rect(cx - 60, H - 2, 120, 1, lin)
    # viñeta: las puntas de la cancha, detrás de las paletas, más oscuras
    for d in range(14):
        img.dither(0.45 * (1 - d / 14))
        img.line(0, COURT + d, W, COURT + d, SHADOW)
        img.line(0, H - 1 - d, W, H - 1 - d, SHADOW)
    img.dither(1.0)
    img.clip()
    # las bocas de los arcos: una ranura oscura con su luz
    img.rect(cx - 64, COURT, 128, 2, SHADOW)
    img.rect(cx - 64, H - 2, 128, 2, SHADOW)
    # las bandas, con volumen: la luz viene de arriba a la izquierda
    for x, cara in ((0, RAIL3), (W - RIEL, RAIL2)):
        img.rect(x, COURT, RIEL, LARGO, RAIL1)
        img.rect(x, COURT, RIEL, 1, RAIL2)
        img.rect(x + (RIEL - 1 if x == 0 else 0), COURT, 1, LARGO, cara)
        img.rect(x + (0 if x == 0 else RIEL - 1), COURT, 1, LARGO, RAIL0)
        for y in range(COURT + 14, H, 42):          # los remaches
            img.pset(x + 1 + (x != 0), y, RAIL3)
            img.pset(x + 1 + (x != 0), y + 1, RAIL0)
    _FONDOS[oro] = img
    return img


def gran(cx, y, s, col, k=3, sombra=SHADOW):
    """texto grande centrado con una sombra que se ve a cualquier escala."""
    if sombra is not None:
        d = 1 if k <= 2 else 2
        big_ctext(cx + d, y + d, s, sombra, scale=k)
    big_ctext(cx, y, s, col, scale=k)


class World:
    def __init__(self):
        self.p = Pong()
        _fondo(False)                 # las dos canchas se hornean de entrada:
        _fondo(True)                  # así el tiempo de oro no da un tirón
        self.fx = Fx(gravity=0.0, max_parts=220, sombra=SHADOW)
        self.hitflash = 0
        self.fx.destello(WHITE)
        self.trail = []               # las últimas posiciones, para la estela
        self.use_mouse = False        # gana el último input que hayas usado
        self._lm = None
        self.touch = web.is_touch()
        self.hold = 0                 # frames con la flecha apretada (aceleración)
        self.carteles = []            # [texto, sub, col, vida, vida0, k]
        self.combo_pulso = 0
        self.lento_vis = 0
        self.flash_paleta = 0
        self.golpe_c = 0              # la paleta de la máquina se hunde al pegar
        self.golpe_p = 0
        self.marcador_p = 0           # el número del tanteo late al cambiar
        self.marcador_c = 0
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
        ddx, _ = web.drag()
        mx = pyxel.mouse_x
        if not self.touch and self._lm is not None and mx != self._lm:
            self.use_mouse = True
        self._lm = mx
        left = pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A)
        right = pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D)
        dedo = self.touch and pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
        if left or right or ddx:
            self.use_mouse = False
        if left or right:
            self.hold += 1
        else:
            self.hold = 0
        # con flechas acelera: el primer toque es fino, sostenido cruza rápido
        vel = min(6.6, 3.3 + self.hold * 0.42)
        if ddx:
            p.set_player(p.px + ddx)
        elif left:
            p.set_player(p.px - vel)
        elif right:
            p.set_player(p.px + vel)
        elif dedo:                    # el dedo sobre la cancha: la paleta lo sigue
            p.set_player(p.px + max(-14, min(14, mx - p.px)))
        elif self.use_mouse:
            p.set_player(mx)
        smash = pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_X) or \
            pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_UP) or \
            (not self.touch and pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT))
        if smash and p.pedir_smash():
            self.flash_paleta = 6
            self.fx.burst(p.px, FACE_P, CHISPA_FUEGO, n=12, speed=1.6, life=14,
                          angle=-1.5708, spread=2.6)
        for campo in ("hitflash", "combo_pulso", "flash_paleta", "golpe_c",
                      "golpe_p", "marcador_p", "marcador_c"):
            v = getattr(self, campo)
            if v:
                setattr(self, campo, v - 1)
        for e in p.step():
            self._efecto(e)
        if p.lento:
            self.lento_vis = min(10, self.lento_vis + 1)
        else:
            self.lento_vis = max(0, self.lento_vis - 1)
        if not p.parada:
            self.trail.append([(b[0], b[1], b[6], abs(b[3])) for b in p.balls])
            del self.trail[:-9]
        for b in p.balls:                     # la pelota en llamas larga brasas
            if b[6] and pyxel.frame_count % 2 == 0:
                self.fx.burst(b[0], b[1], CHISPA_FUEGO, n=3, speed=0.7, life=14,
                              angle=1.5708 if b[3] < 0 else -1.5708, spread=1.3)
        for c in self.carteles:
            c[3] -= 1
        self.carteles = [c for c in self.carteles if c[3] > 0]
        self.fx.update()

    # --- jugo ----------------------------------------------------------------
    def _efecto(self, e):
        p = self.p
        kind = e[0]
        if kind == "golpe":
            arriba = e[3] == MAQUINA
            self.fx.burst(e[1], e[2], CHISPA_GOLPE, n=10, speed=1.8, life=16,
                          angle=1.5708 if arriba else -1.5708, spread=2.8)
            self.fx.shake(2)
            self.hitflash = 4
            if arriba:
                self.golpe_c = 6
            else:
                self.golpe_p = 6
                self.combo_pulso = 10
        elif kind == "pared":
            ang = 0.0 if e[1] < W / 2 else 3.1416
            self.fx.burst(e[1], e[2], (WHITE, B1, B0), n=5, speed=1.2, life=10,
                          angle=ang, spread=2.4)
        elif kind == "efecto":
            self.fx.burst(e[1], e[2], (WHITE, M3, M2, GLOW), n=12, speed=2.0,
                          life=18, spread=2.2, angle=-1.5708)
            self.fx.popup(e[1], e[2] - 18, "efecto", M2, life=24)
        elif kind == "smash":
            self.fx.burst(e[1], e[2], CHISPA_FUEGO, n=40, speed=3.4, life=28,
                          spread=2.4, angle=-1.5708)
            self.fx.shake(6)
            self.fx.destello(FIRE, 6)
            self._cartel("¡SMASH!", "+%d" % e[3], FIRE, vida=45, k=4)
        elif kind == "smash_suyo":
            self.fx.burst(e[1], e[2], CHISPA_FUEGO, n=24, speed=2.6, life=20,
                          spread=2.4, angle=1.5708)
            self.fx.shake(4)
            self.fx.popup(W / 2, FACE_C + 40, "¡SMASH SUYO!", WARN)
        elif kind == "devuelto":
            self.fx.burst(e[1], e[2], CHISPA_ORO, n=22, speed=2.4,
                          life=22, spread=2.4, angle=-1.5708)
            self.fx.popup(e[1], e[2] - 20, "¡DEVUELTO! +%d" % e[3], GOLD)
            self.fx.shake(4)
        elif kind == "carga":
            self.fx.popup(p.px, FACE_P - 26, "¡SMASH LISTO!", FIRE, life=40)
            self.fx.burst(p.px, FACE_P, CHISPA_FUEGO, n=14, speed=1.8, life=16,
                          angle=-1.5708, spread=2.6)
        elif kind == "racha":
            self._cartel("COMBO %d" % e[1], "+%d" % e[2], GOLD, vida=55)
            self.fx.destello(GOLD)
            self.fx.shake(3)
        elif kind == "racha_rota":
            self.fx.popup(W / 2, MID + 40, "combo roto", WARN)
        elif kind == "punto":
            quien, x = e[1], e[3]
            y = COURT + 4 if quien == YO else H - 4
            self.fx.burst(x, y, CHISPA_PUNTO if quien != YO else
                          (WHITE, P3, P2, P1), n=34, speed=3.0, life=32,
                          angle=1.5708 if quien == YO else -1.5708, spread=3.0)
            if quien == YO:
                self._cartel("¡PUNTO!", "+%d" % e[2], ACCENT, vida=50)
                self.marcador_p = 24
            else:
                self._cartel("PUNTO SUYO", None, WARN, vida=50, k=3)
                self.marcador_c = 24
            self.fx.shake(5)
            self.fx.destello(ACCENT if quien == YO else WARN)
            self.trail = []
        elif kind == "ganador":
            self.fx.burst(e[2], COURT + 4, CHISPA_FUEGO, n=36, speed=3.2,
                          life=30, angle=1.5708, spread=3.0)
            self._cartel("¡GANADOR!", "+%d" % e[1], FIRE, vida=60)
        elif kind == "ladrillo":
            tipo = e[4]
            col = (G2, A2, G2)[tipo]
            self.fx.burst(e[1], e[2], (WHITE, col, HOT, G1),
                          n=14 if tipo != NUCLEO else 36, speed=2.0, life=20)
            self.fx.popup(e[1], e[2] + 14, "+%d" % e[3], GOLD)
            self.fx.shake(2 if tipo != NUCLEO else 5)
            if tipo == NUCLEO:
                self.p.parada = max(self.p.parada, 4)
                self.fx.destello(GOLD, 6)
        elif kind == "blindado":
            self.fx.burst(e[1], e[2], (WHITE, A2, A1), n=9, speed=1.5,
                          life=14)
            self.fx.shake(1)
        elif kind == "muro_nuevo":
            self._cartel("¡DERRIBADO!", "+%d · viene %s" % (e[1], e[2].lower()),
                         GOLD, vida=80)
            self.fx.destello(GOLD, 6)
            self.fx.shake(4)
        elif kind == "power":
            tipo, dueño = e[1], e[2]
            self.fx.popup(W / 2, MID - 30, POWER_NOMBRE[tipo],
                          GOLD if dueño == YO else MAGENTA)
            self.fx.destello(GOLD if dueño == YO else MAGENTA)
            self.fx.shake(3)
        elif kind == "escudo":
            self.fx.burst(e[1], e[2], (WHITE, GLOW, SLOW), n=20, speed=2.2,
                          life=18)
            self.fx.popup(e[1], H - 40 if e[3] == YO else COURT + 34,
                          "¡SALVADA!", SLOW)
            self.fx.shake(3)
        elif kind == "ronda":
            r = e[1]
            self._cartel("RONDA %d" % (r + 1), RONDAS[r][0], RONDA_COL[r],
                         vida=80)
            self.fx.destello(RONDA_COL[r], 6)
        elif kind == "oro":
            self._cartel("¡TIEMPO DE ORO!", "todo vale doble", GOLD, vida=90)
            self.fx.destello(GOLD, 8)
            self.fx.shake(4)
        elif kind == "punto_oro":
            self._cartel("PUNTO DE ORO", "el que lo gana, gana", GOLD, vida=80)
        elif kind == "lento":
            self.fx.popup(W / 2, MID + 30, "¿llega?", SLOW, life=30)
        elif kind == "victoria":
            self._cartel("¡GANASTE!", "+%d" % e[1], ACCENT, vida=120, k=4)
            self.fx.destello(ACCENT, 8)
            self.fx.burst(W / 2, MID, (WHITE, G3, P2, GLOW), n=70,
                          speed=3.4, life=40)

    # --- dibujo --------------------------------------------------------------
    def draw(self):
        p = self.p
        fc = pyxel.frame_count
        sx, sy = self.fx.offset()
        if sx or sy:
            pyxel.cls(BG)              # el temblor deja ver el borde
        pyxel.camera(-sx, -sy)
        pyxel.blt(0, 0, _fondo(p.oro), 0, 0, W, H)
        self._numeros()
        self._murallas()
        for l in p.muro:
            if l[2]:
                self._ladrillo(l)
        for px_, py_, tipo, ttl in p.powers:
            self._power(px_, py_, tipo, ttl)
        self._estela()
        # las sombras en el piso primero, así nada queda debajo de una sombra
        pyxel.dither(0.5)
        for b in p.balls:
            pyxel.circ(int(b[0]) + 2, int(b[1]) + 3, BR, SHADOW)
        pyxel.dither(1.0)
        self._paletas()
        for b in p.balls:
            if p.saque and (fc // 5) % 2:
                continue                       # el saque titila
            self._pelota(b)
        self.fx.draw(0, 0)
        pyxel.camera()
        if self.lento_vis:                     # cámara lenta: bandas de cine
            h = self.lento_vis
            pyxel.rect(0, COURT, W, h, SHADOW)
            pyxel.rect(0, H - h, W, h, SHADOW)
        self.fx.draw_flash(0, COURT, W, LARGO)
        self._carteles()
        self._hud()

    def _numeros(self):
        """el tanteo gigante en el piso, a cada lado de la red, y el combo en
        el círculo del medio: se leen de reojo sin tapar la pelota."""
        p = self.p
        big1 = OBIG if p.oro else BIG1
        x = W - 34
        for s, y, pulso, col in (("%d" % p.cscore, MID - 40, self.marcador_c,
                                  RONDA_R[p.ronda][1]),
                                 ("%d" % p.pscore, MID + 10, self.marcador_p, P1)):
            c = col if pulso else big1
            big_ctext(x, y, s, c, scale=5)
        if p.racha >= 3:
            k = 4 if self.combo_pulso > 6 else 3
            col = G1 if p.racha % RACHA_CADA >= RACHA_CADA - 3 else BIG2
            big_ctext(W // 2, MID - 3 * k + 1, "%d" % p.racha, col, scale=k)
        r = p.ronda
        # la personalidad de la máquina, en su lado de la cancha
        nom = RONDAS[r][0]
        ancho = len(nom) * 4 + 6
        pyxel.rect(RIEL + 3, COURT + 4, ancho, 9, SHADOW)
        pyxel.rect(RIEL + 3, COURT + 4, 2, 9, RONDA_COL[r])
        text(RIEL + 7, COURT + 6, nom, RONDA_R[r][3])
        if p.muro_n:
            s = p.nombre_muro().lower()
            text(W - RIEL - 4 - len(s) * 4, COURT + 6, s, G1)

    def _murallas(self):
        p = self.p
        fc = pyxel.frame_count
        for ttl, y, c1, c2 in ((p.escudo_p, H - 3, SLOW, GLOW),
                               (p.escudo_c, COURT, M2, M1)):
            if not ttl:
                continue
            c = c1 if ttl > 90 or (fc // 4) % 2 else c2
            pyxel.rect(RIEL, y, W - 2 * RIEL, 3, c)
            pyxel.dither(0.4)
            pyxel.rect(RIEL, y - 3 if y > MID else y + 3, W - 2 * RIEL, 3, c)
            pyxel.dither(1.0)
            for x in range(RIEL + (fc // 2) % 12, W - RIEL, 12):
                pyxel.rect(x, y + 1, 4, 1, WHITE)

    def _ladrillo(self, l):
        x, y = int(l[0]), int(l[1])
        tipo = l[3] if len(l) > 3 else NORMAL
        w, h = LAD_W - 1, LAD_H
        pyxel.dither(0.5)
        pyxel.rect(x + 2, y + 3, w, h, SHADOW)
        pyxel.dither(1.0)
        if tipo == NUCLEO:
            on = (pyxel.frame_count // 8) % 2
            pyxel.rect(x - 1, y - 1, w + 2, h + 2, G0)
            pyxel.rect(x, y, w, h, G3 if on else G2)
            pyxel.rect(x, y + h - 2, w, 2, G1)
            pyxel.rect(x, y, w, 1, WHITE)
            for i in range(l[2]):              # cuántos golpes le quedan
                pyxel.rect(x + 3 + i * 3, y + 3, 2, 2, G0)
            return
        if tipo == BLINDADO:
            lo, mid, hi = (A1, A2, A3) if l[2] > 1 else (A0, A1, A2)
            pyxel.rect(x, y, w, h, A0)
            pyxel.rect(x + 1, y + 1, w - 2, h - 2, mid)
            pyxel.rect(x + 1, y + 1, w - 2, 1, hi)
            pyxel.rect(x + 1, y + h - 2, w - 2, 1, lo)
            pyxel.pset(x + 2, y + 3, A0)
            pyxel.pset(x + w - 3, y + 3, A0)
            if l[2] == 1:                      # rajado
                pyxel.line(x + 4, y + 1, x + 8, y + h - 2, A0)
            return
        pyxel.rect(x, y, w, h, G0)
        pyxel.rect(x + 1, y + 1, w - 2, h - 2, G2)
        pyxel.rect(x + 1, y + 1, w - 2, 1, G3)
        pyxel.rect(x + 1, y + h - 2, w - 2, 1, G1)
        pyxel.pset(x + 1, y + 1, WHITE)

    def _paleta(self, cx, cara, half, ramp, abajo, hund, brillo=None):
        """una paleta con volumen: contorno, cuerpo con luz arriba y sombra
        abajo, puntas redondeadas y su sombra en el piso."""
        k0, k1, k2, k3 = ramp
        x = int(cx - half)
        w = half * 2
        y = int(cara if abajo else cara - GROSOR) + (hund if abajo else -hund)
        pyxel.dither(0.5)
        pyxel.rect(x + 3, y + 4, w, GROSOR, SHADOW)
        pyxel.dither(1.0)
        pyxel.rect(x, y + 1, w, GROSOR - 2, k0)
        pyxel.rect(x + 1, y, w - 2, GROSOR, k0)
        cuerpo = brillo if brillo is not None else k2
        pyxel.rect(x + 1, y + 1, w - 2, GROSOR - 2, cuerpo)
        pyxel.rect(x + 2, y + 1, w - 4, 1, k3)
        pyxel.rect(x + 2, y + GROSOR - 2, w - 4, 1, k1)
        pyxel.rect(x + w - 3, y + 2, 1, GROSOR - 4, k1)
        pyxel.rect(x + 2, y + 2, 1, GROSOR - 4, k3)
        pyxel.pset(x + 3, y + 2, WHITE)
        return x, y, w

    def _paletas(self):
        p = self.p
        fc = pyxel.frame_count
        r = p.ronda
        x, y, w = self._paleta(p.cx, FACE_C, p.ph_c, RONDA_R[r], False,
                               min(2, self.golpe_c))
        if p.ttl_c:                              # halo del poder activo
            pyxel.rectb(x - 2, y - 2, w + 4, GROSOR + 4, M2)
        # tú. con la ventana de smash abierta, la paleta arde y se adelanta
        lista = p.carga >= SMASH_CARGA
        if p.smash_t:
            c = WHITE if (fc // 2) % 2 else G3
            x, y, w = self._paleta(p.px, FACE_P - 2, p.ph_p,
                                   (EMBER, FIRE, G2, WHITE), True, 0, brillo=c)
            pyxel.dither(0.5)
            pyxel.rectb(x - 2, y - 2, w + 4, GROSOR + 4, FIRE)
            pyxel.dither(1.0)
        else:
            ramp = PLAYER_R
            if lista and (fc // 6) % 2:
                ramp = (G0, G1, G2, G3)
            x, y, w = self._paleta(p.px, FACE_P, p.ph_p, ramp, True,
                                   min(2, self.golpe_p))
        # la carga del smash, en la paleta misma: cuatro luces en el lomo
        cx = int(p.px)
        for i in range(SMASH_CARGA):
            lx = cx - 9 + i * 5
            c = (FIRE if (fc // 4) % 2 else G3) if lista else (
                HOT if i < p.carga else PLAYER_R[1])
            pyxel.rect(lx, y + 3, 3, 1, c)
        if p.ttl_p:
            pyxel.rectb(x - 2, y - 2, w + 4, GROSOR + 4, GOLD)

    def _pelota(self, b):
        p = self.p
        x, y = int(b[0]), int(b[1])
        if b[6]:
            on = (pyxel.frame_count // 2) % 2
            pyxel.circ(x, y, BR + 1, EMBER)
            pyxel.circ(x, y, BR, FIRE if on else HOT)
            pyxel.circ(x - 1, y - 1, 1, G3)
            pyxel.pset(x - 1, y - 1, WHITE)
            return
        if self.hitflash:
            c0, c1, c2 = B1, WHITE, WHITE
        elif p.oro:
            c0, c1, c2 = G1, G2, G3
        else:
            c0, c1, c2 = B0, B1, B2
        pyxel.circ(x, y, BR + 1, SHADOW)      # contorno: se despega del piso
        pyxel.circ(x, y, BR, c0)
        pyxel.circ(x - 1, y - 1, BR - 1, c1)
        pyxel.rect(x - 2, y - 2, 2, 2, c2)
        if abs(b[5]) > 0.45:                   # con efecto: gira
            k = (pyxel.frame_count // 3) % 4
            dx, dy = ((-2, -2), (1, -2), (1, 1), (-2, 1))[k]
            pyxel.pset(x + dx, y + dy, M2)
            pyxel.pset(x - dx - 1, y - dy - 1, M2)

    def _estela(self):
        """las posiciones viejas de cada pelota, más largas y calientes cuanto
        más rápido va; la que está en llamas deja fuego."""
        n = len(self.trail)
        for i, snap in enumerate(self.trail):
            f = (i + 1) / max(1, n)
            for bx, by, fuego, v in snap:
                if fuego:
                    c = (EMBER, FIRE, HOT, G2)[min(3, int(f * 4))]
                    r = 1 + int(f * 2.5)
                elif v > 4.6:
                    c = (EMBER, HOT, G2, G3)[min(3, int(f * 4))]
                    r = int(f * 2.6)
                elif i >= n - 6:
                    c = (FLIN, B0, B0, B1)[min(3, int(f * 4))]
                    r = int(0.5 + f * 2.4)
                else:
                    continue
                pyxel.circ(int(bx), int(by), r, c)

    def _power(self, x, y, tipo, ttl):
        fc = pyxel.frame_count
        if ttl < 90 and (fc // 4) % 2:           # titila antes de irse
            return
        col = (P2, R2, G2, HOT, SLOW)[tipo]
        dk = (P0, R0, G0, EMBER, SLOWDK)[tipo]
        r = POWER_R - 1
        bob = (fc // 10) % 2
        y -= bob
        pyxel.dither(0.5)
        pyxel.rect(x - r + 2, y - r + 3 + bob, r * 2, r * 2, SHADOW)
        pyxel.dither(1.0)
        pyxel.rect(x - r, y - r, r * 2, r * 2, dk)
        pyxel.rect(x - r + 1, y - r + 1, r * 2 - 2, r * 2 - 2, SHADOW)
        pyxel.rectb(x - r, y - r, r * 2, r * 2, col)
        pyxel.rect(x - r + 1, y - r, r * 2 - 2, 1, WHITE if fc % 40 < 20 else col)
        if tipo == LARGA:                        # flecha de dos puntas
            pyxel.rect(x - 5, y - 1, 10, 2, col)
            pyxel.tri(x - 6, y, x - 3, y - 3, x - 3, y + 3, col)
            pyxel.tri(x + 5, y, x + 2, y - 3, x + 2, y + 3, col)
        elif tipo == CORTA:
            pyxel.rect(x - 2, y - 1, 4, 2, col)
            pyxel.tri(x - 6, y - 3, x - 6, y + 3, x - 3, y, col)
            pyxel.tri(x + 5, y - 3, x + 5, y + 3, x + 2, y, col)
        elif tipo == MULTI:
            for dx, dy in ((-3, -2), (2, -3), (0, 2)):
                pyxel.circ(x + dx, y + dy, 1, col)
                pyxel.pset(x + dx - 1, y + dy - 1, WHITE)
        elif tipo == ESCUDO:
            pyxel.rect(x - 4, y - 4, 8, 5, col)
            pyxel.tri(x - 4, y + 1, x + 3, y + 1, x - 1, y + 5, col)
            pyxel.rect(x - 3, y - 3, 2, 3, WHITE)
        else:                                    # el rayo del turbo
            pyxel.tri(x + 2, y - 5, x - 3, y + 1, x + 1, y, col)
            pyxel.tri(x - 1, y + 5, x + 3, y - 1, x - 1, y, col)

    def _carteles(self):
        for s, sub, col, vida, vida0, k in self.carteles:
            if vida < vida0 * 0.3 and (vida // 3) % 2:
                continue
            kk = k + 1 if vida > vida0 - 5 else k   # entra grande y se asienta
            while kk > 1 and big_width(s, kk) > W - 10:
                kk -= 1
            y = MID - 44                  # bajo la cuenta 3-2-1 del Cabinet
            alto = 6 * kk + (18 if sub else 6)
            fx.flash(SHADOW, 0.55, 0, y - 6, W, alto + 4)
            pyxel.rect(0, y - 7, W, 1, col)
            pyxel.rect(0, y + alto - 2, W, 1, col)
            gran(W // 2, y, s, col, kk)
            if sub:
                ks = 2 if big_width(sub, 2) <= W - 10 else 1
                gran(W // 2, y + 6 * kk + 3, sub, WHITE, ks, SHADOW)

    def _hud(self):
        p = self.p
        fc = pyxel.frame_count
        # el puntaje, grande: es lo que va a los récords
        sc = "%d" % p.score
        big_text(5, 6, sc, G2 if p.oro else ACCENT, scale=2, shadow=SHADOW)
        x = 5 + big_width(sc, 2) + 2
        if p.oro:
            pyxel.rect(x, 6, 13, 9, G2)
            text(x + 2, 8, "x2", SHADOW)
        # el smash: cuatro llamitas que se llenan; llena, titila
        sx = 76
        lista = p.carga >= SMASH_CARGA
        lc = FIRE if lista and (fc // 6) % 2 else (WHITE if lista else DIM)
        text(sx, 3, "SMASH", lc)
        for i in range(SMASH_CARGA):
            c = FIRE if i < p.carga else HUD3
            if lista:
                c = G2 if (fc // 6) % 2 else FIRE
            pyxel.rect(sx + i * 6, 11, 5, 6, c)
            pyxel.rect(sx + i * 6, 11, 5, 1, G3 if i < p.carga else HUD2)
        # el tanteo: máquina - tú, con el color de cada uno
        cx = 144
        r = p.ronda
        cs, ps = "%d" % p.cscore, "%d" % p.pscore
        big_text(cx - 4 - big_width(cs, 2), 6, cs, RONDA_COL[r], scale=2,
                 shadow=SHADOW)
        pyxel.rect(cx - 2, 10, 3, 2, TXT)
        big_text(cx + 4, 6, ps, ACCENT, scale=2, shadow=SHADOW)
        # el reloj: número grande y barra
        s = p.time // 60
        col = WHITE
        if s <= 10:
            col = WARN if fc % 30 < 15 else WHITE
        rs = "%d" % s
        big_text(W - big_width(rs, 2) - 5, 6, rs, col, scale=2, shadow=SHADOW)
        bx, bw = 176, 30
        fx.bar(bx, 9, bw, 5, p.time / TIME, G2 if p.oro else ACCENT, HUD3)
        pyxel.rect(bx + int(bw * ORO_T / TIME), 8, 1, 7, G3)


class Game:
    def __init__(self):
        touch = web.is_touch()
        Cabinet(
            game_id="pong", title="PONG", subtitle="90 segundos contra la máquina",
            howto=["arrastra en el panel o en la cancha" if touch else
                   "mouse o flechas mueven",
                   "cada 4 devoluciones: SMASH (botón al pegar)" if touch else
                   "cada 4 devoluciones: SMASH (espacio al pegar)",
                   "rompe el muro · muévete al pegar: efecto"],
            width=W, height=H, palette=PAL, scale=2,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=F1),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
