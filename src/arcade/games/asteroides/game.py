"""asteroides — 90 segundos rompiendo piedra en órbita, para MHW RETRO FUTURE.

el clásico de vectores, con inercia de verdad: la nave gira sobre su eje y
empuja hacia donde mira, así que frenar es girar 180° y acelerar (o el freno).
la pantalla da la vuelta por los cuatro lados, para ti y para las piedras.

lo que le sumamos al original:

- **oleadas con anuncio**: "OLEADA 3". limpiar el campo entero paga un bono
  y trae la siguiente después de un respiro; si te demoras, la siguiente entra
  igual a los 20 s. cada oleada trae algo nuevo.
- **las piedras se parten**: una grande da dos medianas, una mediana dos chicas,
  y las chicas valen más. desarmar una grande entera paga más que reventarla.
- **minas** (desde la oleada 2): flotan quietas y si les pegas un tiro
  estallan y rompen todo lo que tengan cerca. una mina bien elegida es un
  combo de seis.
- **cometas** (desde la oleada 3): avisan por qué borde entran y cruzan la
  pantalla rápido, sin dar la vuelta. pegarles paga mucho.
- **el cazador**: un platillo que te apunta y dispara.
- **la dorada**: una piedra chica y rápida que vale mucho y se va sola.
- **cuatro poderes con duración visible**: triple (abanico de tres), ráfaga
  (doble cadencia), escudo (aguanta un golpe) y nova (revienta lo que tengas
  alrededor).
- **el combo**: roturas seguidas multiplican hasta x5, con su barrita.
- **la tormenta final**: los últimos 15 segundos llueven piedras y todo vale
  doble.
- **disparo continuo y predecible**: mantener FUEGO dispara siempre al mismo
  ritmo, sin tope de tiros ni munición. en el celular viene el auto-fuego
  prendido (botón AUTO para cambiarlo), así un pulgar gira y el otro empuja.

la lógica vive en la clase Espacio, sin pyxel: `step()` avanza un frame con el
input ya leído y devuelve qué pasó.
"""
import math
import random

import pyxel

from pixelkit import fx, scores, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import ctext, text

W, H = 256, 208
HUD = 18
FIELD_TOP = HUD

TIME = 90 * 60                   # el round entero: nada lo estira
VIDAS = 3
GRACIA = 110

SHIP_R = 6                       # radio de choque de la nave
TURN = 0.098
THRUST = 0.135
DRAG = 0.988                     # el espacio casi no frena: eso es la gracia
MAXV = 3.2
SHOT_V = 4.4
SHOT_TTL = 46
# la cadencia es lo único que limita el disparo: no hay munición ni tope de
# tiros en pantalla. mantener apretado dispara cada DISPARO_GAP frames, siempre
DISPARO_GAP = 8
RAFAGA_GAP = 4
FRENO = 0.72                     # un toque de freno
FRENO_SOSTENIDO = 0.9            # por frame, mientras se mantiene

GRANDE, MEDIANA, CHICA = 2, 1, 0
RADIO = {GRANDE: 15, MEDIANA: 9, CHICA: 5}
VALE = {GRANDE: 20, MEDIANA: 30, CHICA: 50}
VEL = {GRANDE: 0.42, MEDIANA: 0.72, CHICA: 1.15}

# las oleadas
OLEADA_GAP = 20 * 60             # si no la limpias, la siguiente entra igual
RESPIRO = 100                    # entre una limpia y la siguiente
LIMPIA_VALE = 100                # por número de oleada
TOPE_ROCAS = 34                  # para que dos oleadas encimadas no exploten

CAZADOR_GAP = 16 * 60
CAZADOR_VALE = 150
CAZADOR_V = 0.9
CAZADOR_TIRO = 90

MINA_R = 5
MINA_ONDA = 38                   # radio de la explosión
MINA_VALE = 40
MINA_V = 0.22

COMETA_GAP = 12 * 60
COMETA_AVISO = 60
COMETA_V = 3.0
COMETA_R = 5
COMETA_VALE = 120

TRIPLE, ESCUDO, RAFAGA, NOVA = range(4)
POWER_NOMBRE = {TRIPLE: "¡TRIPLE!", ESCUDO: "¡ESCUDO!", RAFAGA: "¡RÁFAGA!",
                NOVA: "¡NOVA!"}
TRIPLE_TTL = 9 * 60
RAFAGA_TTL = 7 * 60
POWER_TTL = 9 * 60
POWER_CHANCE = 0.16              # probabilidad de que una chica deje un poder
MINA_POWER = 0.35                # y una mina
NOVA_R = 64

# el combo: roturas seguidas. si pasa más de COMBO_TTL entre una y otra, se
# enfría. el techo evita que un campo lleno de chicas valga una fortuna.
# la mecha se acorta a medida que el combo crece: sostener un x5 pide no
# parar nunca, no alcanza con un campo lleno de chicas
COMBO_TTL = 70
COMBO_TTL_MIN = 24
COMBO_CADA = 4
COMBO_MAX = 5

# la dorada: rápida, no se parte, se va sola
DORADA_GAP = 17 * 60
DORADA_TTL = 7 * 60
DORADA_VALE = 250
DORADA_V = 1.7

TORMENTA = 15 * 60               # los últimos 15 s
TORMENTA_GAP = 100               # cada cuánto cae piedra extra

(BG, STAR1, STAR2, SHIP1, SHIP2, FLAME, ROCK1, ROCK2, ROCK3, SHOT, TXT, DIM,
 ACCENT, WARN, SHADOW, WHITE, NEON, NEON2, PINK, GOLD, HUNTER, HUNTER2,
 SHIELDC, GRID, PANEL, MINE, COMET) = range(27)
PAL = [
    0x0B0A16, 0x1E1B3A, 0x2E2A55, 0x38E8E0, 0xA8FFF8, 0xFF8A3A, 0x8E86B0,
    0xC0B8DC, 0x6A6294, 0xFFF3B0, 0xE8ECF5, 0x8A80B8, 0x38E8E0, 0xE04A2A,
    0x060512, 0xF2F5FB, 0xFF6EC7, 0xB03A8E, 0xE868C8, 0xFFD24A, 0x9AE84A,
    0x4E8E28, 0x7ADCFF, 0x171430, 0x110F24, 0xFF4040, 0xFFB050,
] + [0] * (256 - 27)

CHISPA_ROCA = (WHITE, ROCK2, ROCK1, ROCK3)
CHISPA_NAVE = (WHITE, SHIP2, SHIP1, NEON)
CHISPA_CAZA = (WHITE, GOLD, HUNTER, HUNTER2)
CHISPA_MINA = (WHITE, GOLD, MINE, FLAME, WARN)
CHISPA_COMETA = (WHITE, GOLD, COMET, FLAME)

# lo que trae cada oleada, además de las grandes: (grandes, minas, novedad)
OLEADAS = {1: (3, 0, "rompe las piedras"),
           2: (3, 2, "¡minas! dispárales de lejos"),
           3: (4, 2, "¡cometas! mira el aviso"),
           4: (4, 3, "¡viene el cazador!"),
           5: (5, 3, "todo junto")}


def envolver(x, y):
    """el campo da la vuelta: salir por un borde es entrar por el otro."""
    if x < 0:
        x += W
    elif x >= W:
        x -= W
    if y < FIELD_TOP:
        y += H - FIELD_TOP
    elif y >= H:
        y -= H - FIELD_TOP
    return x, y


def dist2(ax, ay, bx, by):
    """distancia al cuadrado, contando que el campo se envuelve."""
    dx = abs(ax - bx)
    dy = abs(ay - by)
    if dx > W / 2:
        dx = W - dx
    alto = H - FIELD_TOP
    if dy > alto / 2:
        dy = alto - dy
    return dx * dx + dy * dy


class Roca:
    def __init__(self, x, y, tam, a, rng, dorada=False):
        self.x, self.y, self.tam = x, y, tam
        self.dorada = dorada
        self.ttl = DORADA_TTL if dorada else -1
        v = DORADA_V if dorada else VEL[tam] * rng.uniform(0.75, 1.3)
        self.vx, self.vy = math.cos(a) * v, math.sin(a) * v
        self.giro = rng.uniform(-0.05, 0.05) * (3 if dorada else 1)
        self.rot = rng.uniform(0, math.tau)
        self.forma = [rng.uniform(0.68, 1.25) for _ in range(9)]

    @property
    def r(self):
        return RADIO[self.tam]

    def step(self):
        self.x, self.y = envolver(self.x + self.vx, self.y + self.vy)
        self.rot += self.giro


class Mina:
    """flota casi quieta. un tiro la hace estallar y se lleva lo de al lado."""

    def __init__(self, x, y, rng):
        self.x, self.y = x, y
        a = rng.uniform(0, math.tau)
        self.vx, self.vy = math.cos(a) * MINA_V, math.sin(a) * MINA_V
        self.fase = rng.randrange(60)

    def step(self):
        self.x, self.y = envolver(self.x + self.vx, self.y + self.vy)
        self.fase += 1


class Cometa:
    """avisa por dónde entra, después cruza derecho y se va."""

    def __init__(self, x, y, a):
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * COMETA_V, math.sin(a) * COMETA_V
        self.aviso = COMETA_AVISO

    def step(self):
        if self.aviso > 0:
            self.aviso -= 1
            return True
        self.x += self.vx
        self.y += self.vy
        return -20 < self.x < W + 20 and FIELD_TOP - 20 < self.y < H + 20


class Cazador:
    """el platillo: te sigue de lejos y te tira. lo único que te busca."""

    def __init__(self, x, y, rng):
        self.x, self.y = x, y
        self.rng = rng
        self.t = CAZADOR_TIRO
        self.vida = 2
        self.vy = rng.choice((-0.35, 0.35))

    def step(self, tx, ty):
        dx = tx - self.x
        if abs(dx) > W / 2:
            dx = -dx
        self.x += CAZADOR_V * (1 if dx > 0 else -1)
        self.y += self.vy
        if self.y < FIELD_TOP + 8 or self.y > H - 8:
            self.vy = -self.vy
        self.x, self.y = envolver(self.x, self.y)
        self.t -= 1
        if self.t <= 0:
            self.t = CAZADOR_TIRO
            return math.atan2(ty - self.y, tx - self.x)   # dispara hacia ti
        return None


class Espacio:
    """el campo entero, sin pyxel: nave, piedras, tiros, poderes y reloj."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.reset()

    def reset(self):
        self.x, self.y = W / 2, (FIELD_TOP + H) / 2
        self.a = -math.pi / 2
        self.vx = self.vy = 0.0
        self.score = 0
        self.lives = VIDAS
        self.over = False
        self.time = TIME
        self.gracia = GRACIA
        self.triple = 0
        self.rafaga = 0
        self.escudo = 0
        self.cool = 0
        self.rocas = []
        self.minas = []
        self.cometas = []
        self.tiros = []              # [x, y, vx, vy, ttl, mio]
        self.powers = []             # [x, y, tipo, ttl]
        self.cazador = None
        self.caza_t = CAZADOR_GAP
        self.cometa_t = COMETA_GAP
        self.oleada = 0
        self.oleada_t = OLEADA_GAP
        self.respiro = 0
        self.rotas = 0
        self.combo = 0
        self.combo_t = 0
        self.mejor_combo = 0
        self.dorada_t = DORADA_GAP
        self.doradas = 0
        self.tormenta_t = 0
        self.en_tormenta = False
        self.disparos = 0
        self._nueva_oleada([])

    # --- poblar ----------------------------------------------------------
    def _lejos(self, minimo=70):
        for _ in range(30):
            x = self.rng.uniform(0, W)
            y = self.rng.uniform(FIELD_TOP, H)
            if dist2(x, y, self.x, self.y) > minimo * minimo:
                return x, y
        return 4.0, float(FIELD_TOP + 4)

    def _soltar_roca(self, tam, dorada=False):
        x, y = self._lejos(72)
        self.rocas.append(Roca(x, y, tam, self.rng.uniform(0, math.tau), self.rng,
                               dorada=dorada))

    def _nueva_oleada(self, ev):
        self.oleada += 1
        self.oleada_t = OLEADA_GAP
        self.respiro = 0
        n = self.oleada
        grandes, minas, nota = OLEADAS[min(n, 5)]
        if n > 5:
            grandes += 1
        lugar = max(0, TOPE_ROCAS - len(self.rocas)) // 7   # una grande = 7
        for _ in range(min(grandes, max(1, lugar))):
            self._soltar_roca(GRANDE)
        for _ in range(max(0, minas - len(self.minas))):
            x, y = self._lejos(80)
            self.minas.append(Mina(x, y, self.rng))
        if n == 4 and self.cazador is None:
            self.caza_t = 90                  # el cazador llega con la 4
        ev.append(("oleada", n, nota))

    def mult(self):
        """el combo en multiplicador: cada tres roturas seguidas suma uno."""
        return min(COMBO_MAX, 1 + self.combo // COMBO_CADA)

    def tormenta(self):
        return 0 < self.time <= TORMENTA

    def _sumar(self, n):
        """todo lo que suma pasa por acá: en la tormenta, vale doble."""
        n *= 2 if self.tormenta() else 1
        self.score += n
        return n

    def piedras(self):
        """lo que hay que romper para limpiar la oleada."""
        return sum(1 for r in self.rocas if not r.dorada) + len(self.minas)

    # --- input ------------------------------------------------------------
    def disparar(self, ev):
        if self.cool > 0 or self.over:
            return False
        self.cool = RAFAGA_GAP if self.rafaga else DISPARO_GAP
        angulos = (self.a,) if not self.triple else (self.a - 0.26, self.a,
                                                     self.a + 0.26)
        for a in angulos:
            self.tiros.append([self.x + math.cos(a) * 8, self.y + math.sin(a) * 8,
                               math.cos(a) * SHOT_V + self.vx * 0.4,
                               math.sin(a) * SHOT_V + self.vy * 0.4,
                               SHOT_TTL, 1])
        self.disparos += 1
        ev.append(("tiro", self.x, self.y))
        return True

    def frenar(self, f=FRENO):
        self.vx *= f
        self.vy *= f

    # --- un frame ----------------------------------------------------------
    def step(self, rot, thrust, fire):
        ev = []
        if self.over:
            return ev
        # ojo: el escudo NO va acá. es un flag de "aguanta un golpe", no un
        # temporizador — metido en esta lista se gastaba solo en el mismo frame
        # en que lo agarrabas.
        for campo in ("gracia", "triple", "rafaga", "cool"):
            v = getattr(self, campo)
            if v > 0:
                setattr(self, campo, v - 1)
        if self.combo_t > 0:
            self.combo_t -= 1
            if self.combo_t == 0 and self.combo:
                if self.combo >= COMBO_CADA:
                    ev.append(("combo_frio", self.combo))
                self.combo = 0

        self.a += rot * TURN
        if thrust:
            self.vx += math.cos(self.a) * THRUST
            self.vy += math.sin(self.a) * THRUST
        self.vx *= DRAG
        self.vy *= DRAG
        v = math.hypot(self.vx, self.vy)
        if v > MAXV:
            self.vx, self.vy = self.vx / v * MAXV, self.vy / v * MAXV
        self.x, self.y = envolver(self.x + self.vx, self.y + self.vy)
        if fire:
            self.disparar(ev)

        self._mover_tiros(ev)
        for roca in self.rocas:
            roca.step()
        for m in self.minas:
            m.step()
        # la dorada se va sola
        for roca in list(self.rocas):
            if roca.ttl > 0:
                roca.ttl -= 1
                if roca.ttl == 0:
                    self.rocas.remove(roca)
                    ev.append(("dorada_ida", roca.x, roca.y))
        self.dorada_t -= 1
        if self.dorada_t <= 0:
            self.dorada_t = DORADA_GAP
            self._soltar_roca(CHICA, dorada=True)
            ev.append(("dorada_entra",))
        self._cazador(ev)
        self._cometas(ev)
        self._choques(ev)
        self._powers(ev)
        self._oleadas(ev)
        self._tormenta(ev)

        self.time -= 1
        if self.time <= 0:
            self.time = 0
            self.over = True
            ev.append(("aguantaste",))
        return ev

    def _oleadas(self, ev):
        if self.respiro > 0:
            self.respiro -= 1
            if self.respiro == 0:
                self._nueva_oleada(ev)
            return
        self.oleada_t -= 1
        if self.oleada_t <= 0:
            self._nueva_oleada(ev)
        elif not self.piedras():
            vale = self._sumar(LIMPIA_VALE * self.oleada)
            ev.append(("oleada_limpia", self.oleada, vale))
            self.respiro = RESPIRO

    def _tormenta(self, ev):
        if not self.tormenta():
            return
        if not self.en_tormenta:
            self.en_tormenta = True
            self.tormenta_t = 30
            self._soltar_roca(CHICA, dorada=True)
            ev.append(("tormenta",))
        self.tormenta_t -= 1
        if self.tormenta_t <= 0 and len(self.rocas) < TOPE_ROCAS + 8:
            self.tormenta_t = TORMENTA_GAP
            # entra por un borde, hacia el centro: se ve venir
            if self.rng.random() < 0.5:
                x, y = self.rng.choice((0.0, W - 1.0)), self.rng.uniform(FIELD_TOP, H)
            else:
                x, y = self.rng.uniform(0, W), float(FIELD_TOP)
            a = math.atan2((FIELD_TOP + H) / 2 - y, W / 2 - x) + \
                self.rng.uniform(-0.5, 0.5)
            tam = self.rng.choice((MEDIANA, MEDIANA, GRANDE))
            self.rocas.append(Roca(x, y, tam, a, self.rng))

    def _mover_tiros(self, ev):
        vivos = []
        for t in self.tiros:
            t[0], t[1] = envolver(t[0] + t[2], t[1] + t[3])
            t[4] -= 1
            if t[4] <= 0:
                continue
            if t[5]:                                   # tiro tuyo: pega piedra
                if self._pega(t, ev):
                    continue
            vivos.append(t)
        self.tiros = vivos

    def _pega(self, t, ev):
        for roca in self.rocas:
            if dist2(t[0], t[1], roca.x, roca.y) < roca.r * roca.r:
                self._romper(roca, ev)
                return True
        for m in self.minas:
            if dist2(t[0], t[1], m.x, m.y) < (MINA_R + 2) ** 2:
                self._estallar(m, ev)
                return True
        for c in self.cometas:
            if not c.aviso and dist2(t[0], t[1], c.x, c.y) < (COMETA_R + 3) ** 2:
                self.cometas.remove(c)
                self._contar_combo()
                vale = self._sumar(COMETA_VALE * self.mult())
                ev.append(("cometa", c.x, c.y, vale))
                return True
        if self.cazador and \
                dist2(t[0], t[1], self.cazador.x, self.cazador.y) < 64:
            self.cazador.vida -= 1
            if self.cazador.vida <= 0:
                self._bajar_cazador(ev)
            else:
                ev.append(("chispa", t[0], t[1]))
            return True
        return False

    def _bajar_cazador(self, ev):
        vale = self._sumar(CAZADOR_VALE)
        ev.append(("caza", self.cazador.x, self.cazador.y, vale))
        self.cazador = None
        self.caza_t = CAZADOR_GAP

    def mecha(self):
        """cuánto aguanta el combo sin romper nada, en frames."""
        return max(COMBO_TTL_MIN, COMBO_TTL - 3 * self.combo)

    def _contar_combo(self):
        self.combo += 1
        self.combo_t = self.mecha()
        self.rotas += 1
        self.mejor_combo = max(self.mejor_combo, self.combo)

    def _romper(self, roca, ev):
        if roca not in self.rocas:
            return
        self.rocas.remove(roca)
        self._contar_combo()
        m = self.mult()
        if roca.dorada:
            vale = self._sumar(DORADA_VALE * m)
            self.doradas += 1
            ev.append(("dorada", roca.x, roca.y, vale))
            return
        vale = self._sumar(VALE[roca.tam] * m)
        ev.append(("rompe", roca.x, roca.y, roca.tam, vale))
        if self.combo % COMBO_CADA == 0 and m > 1:
            ev.append(("combo", roca.x, roca.y, m))
        if roca.tam > CHICA:
            for _ in range(2):
                a = self.rng.uniform(0, math.tau)
                self.rocas.append(Roca(roca.x, roca.y, roca.tam - 1, a, self.rng))
        elif self.rng.random() < POWER_CHANCE:
            self._soltar_poder(roca.x, roca.y)

    def _soltar_poder(self, x, y):
        self.powers.append([x, y, self.rng.randrange(4), POWER_TTL])

    def _estallar(self, mina, ev):
        """la mina revienta: rompe lo que esté en la onda, y las minas de al
        lado revientan también (en cadena)."""
        if mina not in self.minas:
            return
        self.minas.remove(mina)
        self._contar_combo()
        vale = self._sumar(MINA_VALE * self.mult())
        ev.append(("mina", mina.x, mina.y, vale))
        if self.rng.random() < MINA_POWER:
            self._soltar_poder(mina.x, mina.y)
        self._onda(mina.x, mina.y, MINA_ONDA, ev)

    def _onda(self, x, y, r, ev):
        ev.append(("onda", x, y, r))
        r2 = r * r
        # sólo lo que ya estaba: los pedazos nuevos salen volando de la onda
        for roca in [q for q in self.rocas if dist2(x, y, q.x, q.y) < r2]:
            self._romper(roca, ev)
        for m in [q for q in self.minas if dist2(x, y, q.x, q.y) < r2]:
            self._estallar(m, ev)
        for c in [q for q in self.cometas
                  if not q.aviso and dist2(x, y, q.x, q.y) < r2]:
            self.cometas.remove(c)
            self._contar_combo()
            ev.append(("cometa", c.x, c.y, self._sumar(COMETA_VALE * self.mult())))
        if self.cazador and dist2(x, y, self.cazador.x, self.cazador.y) < r2:
            self._bajar_cazador(ev)

    def _cazador(self, ev):
        if self.cazador is None:
            if self.oleada < 4:
                return                        # llega con la oleada 4
            self.caza_t -= 1
            if self.caza_t <= 0:
                x, y = self._lejos(90)
                self.cazador = Cazador(x, y, self.rng)
                ev.append(("caza_entra", x, y))
            return
        a = self.cazador.step(self.x, self.y)
        if a is not None:
            self.tiros.append([self.cazador.x, self.cazador.y,
                               math.cos(a) * 2.4, math.sin(a) * 2.4,
                               SHOT_TTL * 2, 0])
            ev.append(("caza_tira", self.cazador.x, self.cazador.y))

    def _cometas(self, ev):
        if self.oleada >= 3:
            self.cometa_t -= 1
            if self.cometa_t <= 0:
                self.cometa_t = COMETA_GAP - (180 if self.tormenta() else 0)
                self._soltar_cometa(ev)
        self.cometas = [c for c in self.cometas if c.step()]

    def _soltar_cometa(self, ev):
        """entra por un borde y apunta cerca de donde estás: hay que moverse
        o pegarle."""
        lado = self.rng.randrange(4)
        if lado == 0:
            x, y = -8.0, self.rng.uniform(FIELD_TOP + 20, H - 20)
        elif lado == 1:
            x, y = W + 8.0, self.rng.uniform(FIELD_TOP + 20, H - 20)
        elif lado == 2:
            x, y = self.rng.uniform(20, W - 20), FIELD_TOP - 8.0
        else:
            x, y = self.rng.uniform(20, W - 20), H + 8.0
        a = math.atan2(self.y - y, self.x - x) + self.rng.uniform(-0.25, 0.25)
        c = Cometa(x, y, a)
        self.cometas.append(c)
        ev.append(("cometa_aviso", x, y, a))

    def _golpe(self, ev, x, y):
        if self.gracia or self.over:
            return
        if self.escudo:
            self.escudo = 0
            self.gracia = GRACIA
            ev.append(("escudo_roto", x, y))
            return
        self.lives -= 1
        self.gracia = GRACIA
        self.vx = self.vy = 0.0
        if self.combo >= COMBO_CADA:
            ev.append(("combo_frio", self.combo))
        self.combo = 0
        self.combo_t = 0
        ev.append(("golpe", x, y, self.lives))
        if self.lives <= 0:
            self.over = True
            ev.append(("fin", x, y))

    def _choques(self, ev):
        if self.gracia:
            return
        for roca in self.rocas:
            if dist2(self.x, self.y, roca.x, roca.y) < (roca.r + SHIP_R) ** 2:
                self._golpe(ev, self.x, self.y)
                return
        for m in self.minas:
            if dist2(self.x, self.y, m.x, m.y) < (MINA_R + SHIP_R) ** 2:
                self._golpe(ev, self.x, self.y)
                self._estallar(m, ev)          # te la llevas puesta
                return
        for c in self.cometas:
            if not c.aviso and dist2(self.x, self.y, c.x, c.y) < \
                    (COMETA_R + SHIP_R) ** 2:
                self._golpe(ev, self.x, self.y)
                return
        for t in list(self.tiros):
            if not t[5] and dist2(t[0], t[1], self.x, self.y) < SHIP_R * SHIP_R:
                self.tiros.remove(t)
                self._golpe(ev, self.x, self.y)
                return
        if self.cazador and dist2(self.x, self.y, self.cazador.x,
                                  self.cazador.y) < (SHIP_R + 7) ** 2:
            self._golpe(ev, self.x, self.y)

    def _powers(self, ev):
        quedan = []
        for p in self.powers:
            p[3] -= 1
            if p[3] <= 0:
                continue
            if dist2(self.x, self.y, p[0], p[1]) < (SHIP_R + 7) ** 2:
                self._tomar(p[2], ev)
            else:
                quedan.append(p)
        self.powers = quedan

    def _tomar(self, tipo, ev):
        ev.append(("power", self.x, self.y, tipo))
        if tipo == TRIPLE:
            self.triple = TRIPLE_TTL
        elif tipo == ESCUDO:
            self.escudo = 1
        elif tipo == RAFAGA:
            self.rafaga = RAFAGA_TTL
        else:
            self._onda(self.x, self.y, NOVA_R, ev)


# --- texto grande ------------------------------------------------------------
# la fuente de pyxel tiene 4x6. el puntaje y los carteles van al doble, para
# que se lean en el celular: cada glifo se lee una vez de una imagen chica.
_GLIFOS = {}
_TILDES = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "Á": "A",
           "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}


def _glifo(ch):
    g = _GLIFOS.get(ch)
    if g is None:
        if ch == "¡":                  # no está en la fuente: el ! dado vuelta
            g = [(x, 4 - y) for x, y in _glifo("!")]
        elif ch in _TILDES:
            g = _glifo(_TILDES[ch]) + [(2, -2), (1, -1)]
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


class World:
    def __init__(self):
        self.e = Espacio()
        self.fx = fx.Fx(gravity=0.0)
        self.thrust = False
        self.touch = web.is_touch()
        # en el celular el auto-fuego viene prendido: un pulgar gira, el otro
        # empuja, y no hace falta un tercero para disparar
        self.auto = self.touch
        self.auto_fx = 0
        self.ondas = []               # [x, y, r, rmax] anillos de explosión
        self.cartel = None
        self.hud_golpe = 0
        self.estrellas = [(i * 71 % W, FIELD_TOP + (i * 37) % (H - FIELD_TOP),
                           STAR1 if i % 3 else STAR2) for i in range(46)]
        try:
            lst = scores.top("asteroides", 1)
            self.record = lst[0]["score"] if lst else 0
        except Exception:
            self.record = 0
        self.record_visto = self.record <= 0
        self._efecto(("oleada", 1, OLEADAS[1][2]))

    @property
    def over(self):
        return self.e.over

    @property
    def score(self):
        return self.e.score

    def update(self):
        e = self.e
        rot = (1 if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D) else 0) \
            - (1 if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A) else 0)
        self.thrust = pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W)
        if pyxel.btnp(pyxel.KEY_C) or pyxel.btnp(pyxel.KEY_Z):
            self.auto = not self.auto
            self.auto_fx = 50
            self.fx.popup(W / 2, H - 24, "AUTO-FUEGO SÍ" if self.auto
                          else "AUTO-FUEGO NO", ACCENT if self.auto else TXT,
                          life=50)
        fire = self.auto or pyxel.btn(pyxel.KEY_SPACE) or pyxel.btn(pyxel.KEY_X)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            e.frenar()
            self.fx.burst(e.x, e.y, (WHITE, SHIELDC, DIM), n=8, speed=1.4,
                          life=12)
        elif pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S):
            e.frenar(FRENO_SOSTENIDO)
        for ev in e.step(rot, self.thrust, fire):
            self._efecto(ev)
        if self.thrust and pyxel.frame_count % 2 == 0:
            back = e.a + math.pi
            self.fx.burst(e.x + math.cos(back) * 7, e.y + math.sin(back) * 7,
                          (WHITE, FLAME, WARN), n=2, speed=0.8, life=12,
                          spread=0.8, angle=back)
        if e.mult() >= 3 and pyxel.frame_count % 3 == 0:   # la nave en racha
            self.fx.burst(e.x, e.y, (PINK, NEON2), n=1, speed=0.3, life=14)
        for c in e.cometas:
            if not c.aviso and pyxel.frame_count % 2 == 0:
                self.fx.burst(c.x, c.y, CHISPA_COMETA, n=2, speed=0.5, life=16,
                              spread=0.9, angle=math.atan2(-c.vy, -c.vx))
        self.ondas = [[x, y, r + 3, rm] for x, y, r, rm in self.ondas if r < rm]
        for campo in ("hud_golpe", "auto_fx"):
            v = getattr(self, campo)
            if v:
                setattr(self, campo, v - 1)
        if self.cartel:
            self.cartel[2] -= 1
            if self.cartel[2] <= 0:
                self.cartel = None
        if not self.record_visto and e.score > self.record:
            self.record_visto = True
            self.fx.popup(W / 2, FIELD_TOP + 50, "¡NUEVO RÉCORD!", GOLD, life=70)
            self.fx.burst(W / 2, FIELD_TOP + 50, (WHITE, GOLD, PINK), n=24,
                          speed=2.4, life=28)
            self.fx.destello(GOLD)
        self.fx.update()

    def _cartel(self, tit, sub, col, frames=100):
        self.cartel = [tit, sub, frames, col, frames]

    def _efecto(self, ev):
        k = ev[0]
        if k == "rompe":
            x, y, tam, vale = ev[1], ev[2], ev[3], ev[4]
            self.fx.burst(x, y, CHISPA_ROCA, n=8 + tam * 6, speed=1.5 + tam * 0.4,
                          life=20 + tam * 4)
            self.fx.popup(x, y - 8, "+%d" % vale, NEON if tam else GOLD)
            self.fx.shake(1 + tam)
        elif k == "combo":
            self.fx.popup(ev[1], ev[2] - 18, "¡COMBO x%d!" % ev[3], PINK)
            self.fx.destello(PINK)
        elif k == "combo_frio":
            self.fx.popup(W / 2, FIELD_TOP + 22, "combo frío", TXT)
        elif k == "oleada":
            n, nota = ev[1], ev[2]
            self._cartel("OLEADA %d" % n, nota, (ACCENT, MINE, COMET, HUNTER,
                                                  PINK)[min(n, 5) - 1])
            if n > 1:
                self.fx.destello(ACCENT)
        elif k == "oleada_limpia":
            self._cartel("¡LIMPIA!", "oleada %d despejada  +%d" % (ev[1], ev[2]),
                         GOLD, RESPIRO)
            self.fx.burst(W / 2, (FIELD_TOP + H) / 2, (WHITE, GOLD, ACCENT),
                          n=40, speed=3.0, life=34)
            self.fx.destello(GOLD)
        elif k == "tormenta":
            self._cartel("¡TORMENTA!", "15 segundos · todo vale doble", WARN, 110)
            self.fx.shake(6)
            self.fx.destello(WARN, 6)
        elif k == "dorada_entra":
            self.fx.popup(W / 2, FIELD_TOP + 34, "¡DORADA!", GOLD)
            self.fx.destello(GOLD)
        elif k == "dorada":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, PINK, SHOT), n=36,
                          speed=3.0, life=36)
            self.fx.popup(ev[1], ev[2] - 10, "+%d" % ev[3], GOLD)
            self.fx.shake(5)
            self.fx.destello(GOLD)
        elif k == "dorada_ida":
            self.fx.burst(ev[1], ev[2], (GOLD, DIM), n=8, speed=1.0, life=14)
        elif k == "mina":
            self.fx.burst(ev[1], ev[2], CHISPA_MINA, n=30, speed=2.8, life=28)
            self.fx.popup(ev[1], ev[2] - 10, "+%d" % ev[3], MINE)
            self.fx.shake(6)
            self.fx.destello(FLAME)
        elif k == "onda":
            self.ondas.append([ev[1], ev[2], 4, ev[3]])
        elif k == "cometa_aviso":
            pass                                  # el aviso se dibuja solo
        elif k == "cometa":
            self.fx.burst(ev[1], ev[2], CHISPA_COMETA, n=30, speed=2.6, life=30)
            self.fx.popup(ev[1], ev[2] - 10, "+%d" % ev[3], COMET)
            self.fx.shake(4)
            self.fx.destello(COMET)
        elif k == "caza":
            self.fx.burst(ev[1], ev[2], CHISPA_CAZA, n=34, speed=2.8, life=34)
            self.fx.popup(ev[1], ev[2] - 10, "+%d" % ev[3], GOLD)
            self.fx.shake(6)
            self.fx.destello(GOLD)
        elif k == "caza_entra":
            self._cartel("¡CAZADOR!", "te persigue y dispara", HUNTER, 80)
            self.fx.destello(HUNTER)
        elif k == "golpe":
            self.fx.burst(ev[1], ev[2], CHISPA_NAVE, n=32, speed=2.6, life=32)
            self.fx.popup(ev[1], ev[2] - 14, "-1 NAVE", WARN, life=40)
            self.fx.shake(7)
            self.fx.destello(WARN, 6)
            self.hud_golpe = 36
        elif k == "escudo_roto":
            self.fx.burst(ev[1], ev[2], (WHITE, SHIELDC, NEON), n=22, speed=2.2,
                          life=26)
            self.fx.popup(ev[1], ev[2] - 12, "¡te salvó el escudo!", SHIELDC)
            self.fx.shake(3)
        elif k == "power":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, PINK), n=18, speed=2.0,
                          life=24)
            self.fx.popup(ev[1], ev[2] - 12, POWER_NOMBRE[ev[3]], GOLD)
            self.fx.destello(GOLD)
        elif k == "chispa":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, HUNTER), n=5, speed=1.2,
                          life=12)
        elif k == "tiro":
            pass
        elif k == "aguantaste":
            self._cartel("¡SE ACABÓ EL AIRE!", "", ACCENT, 90)

    # --- dibujo ------------------------------------------------------------
    def draw(self):
        e = self.e
        fc = pyxel.frame_count
        sx, sy = self.fx.offset()
        pyxel.cls(BG)
        pyxel.camera(-sx, -sy)
        for x, y, c in self.estrellas:
            pyxel.pset(x, y, c)
        if e.tormenta() and (fc // 10) % 2:            # el borde late
            pyxel.rectb(0, FIELD_TOP, W, H - FIELD_TOP, WARN)
        for x, y, r, rm in self.ondas:
            pyxel.circb(int(x), int(y), int(r), GOLD if r < rm * 0.6 else FLAME)
        for p in e.powers:
            self._power(p)
        for m in e.minas:
            self._mina(m)
        for roca in e.rocas:
            self._roca(roca)
        for c in e.cometas:
            self._cometa(c)
        for t in e.tiros:
            pyxel.rect(int(t[0]) - 1, int(t[1]) - 1, 2, 2,
                       SHOT if t[5] else HUNTER)
        if e.cazador:
            self._cazador(e.cazador)
        if e.lives > 0 and (not e.gracia or (fc // 4) % 2):
            self._nave(e)
        self.fx.draw(0, 0)
        pyxel.camera()
        self.fx.draw_flash(0, FIELD_TOP, W, H - FIELD_TOP)
        self._dibujar_cartel()
        self._hud()

    def _roca(self, roca):
        """la piedra, como polígono irregular: vectorial, a tono con la casa."""
        pts = []
        n = len(roca.forma)
        for i, f in enumerate(roca.forma):
            a = roca.rot + i * math.tau / n
            pts.append((roca.x + math.cos(a) * roca.r * f,
                        roca.y + math.sin(a) * roca.r * f))
        col = (ROCK3, ROCK1, ROCK2)[roca.tam]
        if roca.dorada:
            if roca.ttl < 90 and (pyxel.frame_count // 4) % 2:
                return                                  # titila antes de irse
            col = GOLD if (pyxel.frame_count // 3) % 2 else SHOT
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if abs(x0 - x1) < W / 2 and abs(y0 - y1) < H / 2:
                pyxel.line(int(x0), int(y0), int(x1), int(y1), col)

    def _mina(self, m):
        x, y = int(m.x), int(m.y)
        cerca = dist2(m.x, m.y, self.e.x, self.e.y) < 50 * 50
        per = 4 if cerca else 12
        luz = (m.fase // per) % 2
        for a in range(4):                               # las púas
            ang = a * math.pi / 2 + m.fase * 0.02
            pyxel.line(x, y, int(x + math.cos(ang) * 7),
                       int(y + math.sin(ang) * 7), MINE)
        pyxel.circ(x, y, 3, MINE)
        pyxel.circb(x, y, 4, WARN)
        pyxel.pset(x, y, WHITE if luz else GOLD)
        if luz and cerca:
            pyxel.circb(x, y, MINA_ONDA // 3, WARN)

    def _cometa(self, c):
        fc = pyxel.frame_count
        if c.aviso:
            # el aviso: una flecha en el borde por donde va a entrar, que
            # apunta hacia donde va, titilando cada vez más rápido
            ang = math.atan2(c.vy, c.vx)
            ca, sa = math.cos(ang), math.sin(ang)
            # la ruta punteada, siempre: por dónde va a pasar
            for i in range(3, 60):
                if (i + fc // 2) % 3:
                    continue
                px_ = int(c.x + ca * i * 4)
                py_ = int(c.y + sa * i * 4)
                if FIELD_TOP < py_ < H - 1:
                    pyxel.rect(px_, py_, 2, 2, COMET)
            if (fc // (6 if c.aviso > 25 else 2)) % 2:
                return
            x = max(6, min(W - 7, c.x))
            y = max(FIELD_TOP + 6, min(H - 7, c.y))
            p0 = (x + ca * 6, y + sa * 6)
            p1 = (x - ca * 4 - sa * 5, y - sa * 4 + ca * 5)
            p2 = (x - ca * 4 + sa * 5, y - sa * 4 - ca * 5)
            pyxel.tri(p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], COMET)
            pyxel.text(int(x + ca * 10) - 1, int(y + sa * 10) - 2, "!", WHITE)
            return
        x, y = int(c.x), int(c.y)
        k = 5
        pyxel.line(x, y, int(c.x - c.vx * k), int(c.y - c.vy * k), FLAME)
        pyxel.line(x, y, int(c.x - c.vx * k * 0.6), int(c.y - c.vy * k * 0.6),
                   COMET)
        pyxel.circ(x, y, 3, COMET)
        pyxel.circ(x, y, 1, WHITE)

    def _nave(self, e):
        cosa, sina = math.cos(e.a), math.sin(e.a)

        def p(f, s):
            return (int(e.x + f * cosa - s * sina), int(e.y + f * sina + s * cosa))

        morro, izq, der, cola = p(9, 0), p(-6, -5), p(-6, 5), p(-3, 0)
        col = SHIP2 if e.escudo else SHIP1
        pyxel.tri(*morro, *izq, *cola, GRID)
        pyxel.tri(*morro, *der, *cola, GRID)
        pyxel.line(*morro, *izq, col)
        pyxel.line(*morro, *der, col)
        pyxel.line(*izq, *cola, col)
        pyxel.line(*der, *cola, col)
        if self.thrust and (pyxel.frame_count // 2) % 2:
            pyxel.line(*cola, *p(-11, 0), FLAME)
        if e.escudo:
            pyxel.circb(int(e.x), int(e.y), 11 + (pyxel.frame_count // 8) % 2,
                        SHIELDC)
        if e.triple:
            for s in (-4, 4):
                pyxel.pset(*p(7, s), NEON)
        if e.rafaga:
            pyxel.pset(*p(11, 0), SHOT)

    def _cazador(self, c):
        x, y = int(c.x), int(c.y)
        pyxel.line(x - 8, y, x + 8, y, HUNTER)
        pyxel.line(x - 8, y, x - 3, y - 4, HUNTER)
        pyxel.line(x + 8, y, x + 3, y - 4, HUNTER)
        pyxel.line(x - 3, y - 4, x + 3, y - 4, HUNTER)
        pyxel.line(x - 5, y + 1, x + 5, y + 1, HUNTER2)
        if (pyxel.frame_count // 6) % 2:
            pyxel.pset(x, y - 5, WHITE)

    def _icono(self, x, y, tipo):
        """el dibujito de cada poder, de 7x7 alrededor de (x, y)."""
        if tipo == TRIPLE:
            for d in (-2, 0, 2):
                pyxel.line(x + d, y + 2, x + d * 2, y - 2, NEON)
        elif tipo == ESCUDO:
            pyxel.circb(x, y, 3, SHIELDC)
            pyxel.pset(x - 1, y - 1, WHITE)
        elif tipo == RAFAGA:
            pyxel.rect(x - 2, y - 3, 1, 6, SHOT)
            pyxel.rect(x + 1, y - 3, 1, 6, SHOT)
        else:
            pyxel.circb(x, y, 3, GOLD)
            for a in range(4):
                ang = a * math.pi / 2 + 0.78
                pyxel.pset(int(x + math.cos(ang) * 4.5),
                           int(y + math.sin(ang) * 4.5), GOLD)
            pyxel.pset(x, y, WHITE)

    def _power(self, p):
        x, y, tipo, ttl = int(p[0]), int(p[1]), p[2], p[3]
        if ttl < 90 and (pyxel.frame_count // 4) % 2:
            return
        col = (NEON, SHIELDC, SHOT, GOLD)[tipo]
        r = 6 + (pyxel.frame_count // 6) % 2
        pyxel.circ(x, y, r - 1, SHADOW)
        pyxel.circb(x, y, r, col)
        self._icono(x, y, tipo)

    def _dibujar_cartel(self):
        c = self.cartel
        if not c:
            return
        tit, sub, f, col, f0 = c
        dx = max(0, (f - (f0 - 10)) * 18)
        if f < 20 and (f // 3) % 2:
            return
        y = FIELD_TOP + 58
        fx.flash(SHADOW, 0.7, 0, y - 5, W, 31 if sub else 21)
        pyxel.rect(0, y - 5, W, 1, col)
        pyxel.rect(0, y + (25 if sub else 15), W, 1, col)
        cbig(W / 2 + dx, y, tit, col, BG)
        if sub:
            ctext(W / 2 + dx, y + 16, sub, TXT)

    def _hud(self):
        e = self.e
        fc = pyxel.frame_count
        pyxel.rect(0, 0, W, HUD, PANEL)
        sc = "%d" % e.score
        big(3, 3, sc, GOLD if e.tormenta() else ACCENT, SHADOW)
        x = 3 + big_w(sc) + 5
        m = e.mult() * (2 if e.tormenta() else 1)
        if m > 1:                                   # el combo, con su mecha
            s = "x%d" % m
            col = PINK if (fc // 6) % 2 else GOLD
            big(x, 3, s, col, SHADOW)
            if e.combo_t:
                fx.bar(x, 15, big_w(s), 1, e.combo_t / e.mecha(), PINK, GRID)
        # la oleada
        text(86, 3, "OLEADA", TXT)
        big(112, 3, "%d" % e.oleada, TXT, SHADOW)
        if e.respiro and (fc // 6) % 2:
            text(86, 10, "LIMPIA", GOLD)
        elif e.oleada_t < 5 * 60 and not e.respiro:
            text(86, 10, "OTRA!", WARN if (fc // 8) % 2 else TXT)
        # las vidas, como navecitas
        jit = ((fc % 4) - 1.5) if self.hud_golpe else 0
        for i in range(VIDAS):
            col = SHIP1 if i < e.lives else GRID
            if i == e.lives and self.hud_golpe and (fc // 3) % 2:
                col = WARN
            bx = int(134 + i * 10 + jit)
            pyxel.tri(bx + 3, 4, bx, 12, bx + 6, 12, col)
            pyxel.pset(bx + 3, 9, BG if i < e.lives else GRID)
        # los poderes activos, con su barrita
        px = 166
        for tipo, t, t0 in ((ESCUDO, e.escudo, 0), (TRIPLE, e.triple, TRIPLE_TTL),
                            (RAFAGA, e.rafaga, RAFAGA_TTL)):
            if not t:
                continue
            if t0 and t < 60 and (fc // 4) % 2:
                px += 10
                continue
            self._icono(px + 3, 7, tipo)
            if t0:
                fx.bar(px, 12, 7, 2, t / t0, (NEON, SHIELDC, SHOT)[tipo], GRID)
            px += 10
        # el auto-fuego: prendido se ve, apagado queda tenue
        ax = 202
        if self.auto:
            on = not self.auto_fx or (fc // 4) % 2
            pyxel.rect(ax, 4, 19, 9, ACCENT if on else SHIP2)
            text(ax + 2, 6, "AUTO", BG)
        else:
            pyxel.rectb(ax, 4, 19, 9, GRID)
            text(ax + 2, 6, "AUTO", DIM)
        # el reloj, al doble, y la barra a todo lo ancho
        s = e.time // 60
        urge = s <= 10
        col = WARN if urge and fc % 30 < 15 else TXT
        r = "%d" % s
        big(W - big_w(r) - 3, 3, r, col, SHADOW)
        pyxel.rect(0, HUD - 2, W, 2, SHADOW)
        pyxel.rect(0, HUD - 2, int(W * e.time / TIME), 2,
                   WARN if e.tormenta() else ACCENT)


class Game:
    def __init__(self):
        Cabinet(
            game_id="asteroides", title="ASTEROIDES",
            subtitle="90 segundos de deriva",
            howto=["izq/der giran · arriba empuja · abajo frena",
                   "espacio dispara (mantén) · c auto-fuego",
                   "limpia cada oleada · ojo con minas y cometas",
                   "roturas seguidas hacen combo · caza la dorada"],
            width=W, height=H, palette=PAL, scale=3, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=GRID),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
