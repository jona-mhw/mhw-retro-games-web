"""asteroides — 90 segundos rompiendo piedra en órbita, para MHW RETRO FUTURE.

el clásico de vectores, con inercia de verdad: la nave gira sobre su eje y
empuja hacia donde mira, así que frenar es girar 180° y acelerar (o el freno).
la pantalla da la vuelta por los cuatro lados, para ti y para las piedras.
la arena va parada, como el teléfono: en el celular vertical llena la pantalla.

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
import weakref

import pyxel

from pixelkit import fx, scores, web
from pixelkit.arcade import Cabinet, UIColors
from pixelkit.pxtext import big_ctext, big_text, big_width, text

W, H = 240, 360
HUD = 30
FIELD_TOP = HUD

TIME = 90 * 60                   # el round entero: nada lo estira
VIDAS = 3
GRACIA = 110

SHIP_R = 7                       # radio de choque de la nave
TURN = 0.098
THRUST = 0.15
DRAG = 0.988                     # el espacio casi no frena: eso es la gracia
MAXV = 3.6
SHOT_V = 5.0
SHOT_TTL = 52
# la cadencia es lo único que limita el disparo: no hay munición ni tope de
# tiros en pantalla. mantener apretado dispara cada DISPARO_GAP frames, siempre
DISPARO_GAP = 8
RAFAGA_GAP = 4
FRENO = 0.72                     # un toque de freno
FRENO_SOSTENIDO = 0.9            # por frame, mientras se mantiene

GRANDE, MEDIANA, CHICA = 2, 1, 0
RADIO = {GRANDE: 18, MEDIANA: 11, CHICA: 6}
VALE = {GRANDE: 20, MEDIANA: 30, CHICA: 50}
VEL = {GRANDE: 0.47, MEDIANA: 0.8, CHICA: 1.28}

# las oleadas
OLEADA_GAP = 20 * 60             # si no la limpias, la siguiente entra igual
RESPIRO = 100                    # entre una limpia y la siguiente
LIMPIA_VALE = 100                # por número de oleada
TOPE_ROCAS = 34                  # para que dos oleadas encimadas no exploten

CAZADOR_GAP = 16 * 60
CAZADOR_VALE = 150
CAZADOR_V = 1.0
CAZADOR_TIRO = 90
CAZADOR_R = 9                    # radio del platillo

MINA_R = 6
MINA_ONDA = 46                   # radio de la explosión
MINA_VALE = 40
MINA_V = 0.25

COMETA_GAP = 12 * 60
COMETA_AVISO = 60
COMETA_V = 3.4
COMETA_R = 6
COMETA_VALE = 120

TRIPLE, ESCUDO, RAFAGA, NOVA = range(4)
POWER_NOMBRE = {TRIPLE: "¡TRIPLE!", ESCUDO: "¡ESCUDO!", RAFAGA: "¡RÁFAGA!",
                NOVA: "¡NOVA!"}
TRIPLE_TTL = 9 * 60
RAFAGA_TTL = 7 * 60
POWER_TTL = 9 * 60
POWER_CHANCE = 0.16              # probabilidad de que una chica deje un poder
MINA_POWER = 0.35                # y una mina
NOVA_R = 76
POWER_R = 8                      # radio de la cápsula

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
DORADA_V = 1.9

TORMENTA = 15 * 60               # los últimos 15 s
TORMENTA_GAP = 100               # cada cuánto cae piedra extra

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
        self.vy = rng.choice((-0.4, 0.4))

    def step(self, tx, ty):
        dx = tx - self.x
        if abs(dx) > W / 2:
            dx = -dx
        self.x += CAZADOR_V * (1 if dx > 0 else -1)
        self.y += self.vy
        if self.y < FIELD_TOP + 10 or self.y > H - 10:
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
    def _lejos(self, minimo=80):
        for _ in range(30):
            x = self.rng.uniform(0, W)
            y = self.rng.uniform(FIELD_TOP, H)
            if dist2(x, y, self.x, self.y) > minimo * minimo:
                return x, y
        return 4.0, float(FIELD_TOP + 4)

    def _soltar_roca(self, tam, dorada=False):
        x, y = self._lejos(84)
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
            x, y = self._lejos(92)
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
                dist2(t[0], t[1], self.cazador.x, self.cazador.y) < CAZADOR_R ** 2:
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
                x, y = self._lejos(104)
                self.cazador = Cazador(x, y, self.rng)
                ev.append(("caza_entra", x, y))
            return
        a = self.cazador.step(self.x, self.y)
        if a is not None:
            self.tiros.append([self.cazador.x, self.cazador.y,
                               math.cos(a) * 2.7, math.sin(a) * 2.7,
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
                                  self.cazador.y) < (SHIP_R + CAZADOR_R - 1) ** 2:
            self._golpe(ev, self.x, self.y)

    def _powers(self, ev):
        quedan = []
        for p in self.powers:
            p[3] -= 1
            if p[3] <= 0:
                continue
            if dist2(self.x, self.y, p[0], p[1]) < (SHIP_R + POWER_R) ** 2:
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


# --- la piel -----------------------------------------------------------------
# la paleta: rampas de 4-5 tonos (brillo, luz, medio, sombra, contorno).
(BG, SHADOW, WHITE, TXT, DIM, PANEL, PANEL2, GRID,
 # el cielo: degradé de arriba (azul noche) a abajo (violeta), y la nebulosa
 SKY0, SKY1, SKY2, SKY3, NEB0, NEB1, NEB2, NEB3, NEBB0, NEBB1, NEBB2,
 # estrellas
 STAR0, STAR1, STAR2, STAR3,
 # el planeta del fondo
 PLA0, PLA1, PLA2,
 # la nave: casco, cabina y su acento
 SHIP0, SHIP1, SHIP2, SHIP3, GLASS, GLASS2, ACCENT, NEON2,
 # la piedra (contorno, sombra, medio, luz, brillo)
 ROCK0, ROCK1, ROCK2, ROCK3, ROCK4,
 # oro y fuego
 GOLD0, GOLD1, GOLD, GOLD3, FLAME, EMBER, SMOKE,
 # el resto
 SHOT, PINK, PINK2, WARN, WARN2, HUNTER0, HUNTER, HUNTER2, SHIELDC, MINE0,
 MINE, COMET) = range(58)
PAL = [
    0x07060F, 0x030208, 0xFFFFFF, 0xE8ECF5, 0x8A80B8, 0x0C0A1C, 0x18143A,
    0x262050,
    0x060716, 0x0A0B22, 0x110D2C, 0x180F34, 0x1A0B2A, 0x2A0F3C, 0x3E1650,
    0x5A2068, 0x0C1838, 0x132654, 0x1C3A72,
    0x2A2850, 0x5A5890, 0x9A98D0, 0xE8E8FF,
    0x120E26, 0x241A44, 0x3E2C66,
    0x0E2E3A, 0x1A7A86, 0x38E8E0, 0xB8FFF8, 0x2A6AD8, 0x9AD8FF, 0x38E8E0,
    0xB03A8E,
    0x0E0A1A, 0x2E2846, 0x524A78, 0x7E76AA, 0xB4ACD8,
    0x5A3A0E, 0xA8741E, 0xFFD24A, 0xFFF4B0, 0xFF8A3A, 0xC0401E, 0x2A2238,
    0xFFF3B0, 0xFF6EC7, 0xE868C8, 0xE04A2A, 0x7A1A14, 0x24481A, 0x9AE84A,
    0xD4FFA0, 0x7ADCFF, 0x5A0A10, 0xFF4040, 0xFFB050,
]
assert len(PAL) == COMET + 1
PAL += [0] * (256 - len(PAL))

ROCA_R = (ROCK0, ROCK1, ROCK2, ROCK3, ROCK4)    # contorno -> brillo
ORO_R = (GOLD0, GOLD0, GOLD1, GOLD, GOLD3)
CHISPA_ROCA = (WHITE, ROCK4, ROCK3, ROCK2, ROCK1)
CHISPA_NAVE = (WHITE, SHIP3, SHIP2, SHIP1)
CHISPA_CAZA = (WHITE, GOLD, HUNTER, HUNTER0)
CHISPA_MINA = (WHITE, GOLD3, GOLD, FLAME, EMBER)
CHISPA_COMETA = (WHITE, GOLD3, COMET, FLAME)
CHISPA_ORO = (WHITE, GOLD3, GOLD, PINK)
LUZ = -2.356                      # la luz viene de arriba a la izquierda
OLA_COL = (ACCENT, MINE, COMET, HUNTER, PINK)
FIELD_H = H - FIELD_TOP


class Fx(fx.Fx):
    """el Fx de pixelkit con los carteles en letra grande: cada popup puede
    traer su escala (el "+50" de cada piedra va chico, los avisos al doble)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

    def pop(self, x, y, s, col, life=38, k=2):
        self.popup(x, y, s, col, life=life)
        self.pops[-1].append(k)

    def draw(self, camx=0, camy=0):
        pops, self.pops = self.pops, []
        try:
            super().draw(camx, camy)
        finally:
            self.pops = pops
        for q in pops:
            x, y, s, col, vida, vida0 = q[0], q[1], q[3], q[4], q[5], q[6]
            if vida < vida0 * 0.35 and (self.t // 3) % 2:
                continue
            k = q[7] if len(q) > 7 else 2
            half = big_width(s, k) // 2 + 2
            x = max(half, min(W - half, x))
            y = max(FIELD_TOP + 2, min(H - 6 * k - 2, y))
            big_ctext(x, int(y), s, col, scale=k, shadow=SHADOW)


_FONDO = []
# la matriz de Bayer 4x4, para tramar a mano donde dither() no alcanza
_BAYER = [v / 16 for v in (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)]


def _fondo():
    """el espacio, horneado una vez: degradé, nebulosa, estrellas lejanas, un
    planeta y el panel del HUD. por frame es un solo blt."""
    if _FONDO:
        return _FONDO[0]
    rng = random.Random(7)
    img = pyxel.Image(W, H)
    img.cls(SKY0)
    tonos = (SKY0, SKY1, SKY2, SKY3)
    for y in range(FIELD_TOP, H):
        t = (y - FIELD_TOP) / FIELD_H
        nivel = min(2.999, t * 3.0)
        i = int(nivel)
        img.line(0, y, W, y, tonos[i])
        img.dither(nivel - i)
        img.line(0, y, W, y, tonos[i + 1])
        img.dither(1.0)
    # la nebulosa: nubes de círculos tramados, más densas en el centro de
    # cada brazo. una violeta que cruza en diagonal y una azul arriba
    for cx0, cy0, dx, dy, n, rmax, ramp in (
            (-10, 250, 2.1, -1.1, 70, 34, (NEB0, NEB1, NEB2, NEB3)),
            (250, 90, -1.7, 0.5, 46, 26, (NEBB0, NEBB0, NEBB1, NEBB2))):
        for i in range(n):
            f = i / n
            x = cx0 + dx * i * 2.0 + rng.uniform(-14, 14)
            y = cy0 + dy * i * 2.0 + rng.uniform(-14, 14)
            r = rmax * (0.4 + 0.6 * (1 - abs(f - 0.5) * 2)) * rng.uniform(0.6, 1.1)
            for capa, (alfa, kr) in enumerate(((0.25, 1.0), (0.3, 0.7),
                                               (0.35, 0.45), (0.4, 0.22))):
                img.dither(alfa)
                img.circ(x, y, r * kr, ramp[capa])
    img.dither(1.0)
    # un planeta lejano, abajo a la derecha: una esfera sombreada píxel por
    # píxel (luz de arriba a la izquierda) con tramado ordenado entre tonos,
    # y su anillo, que pasa por delante abajo y por detrás arriba
    px, py, pr = W - 22, H - 62, 40
    lx, ly, lz = -0.55, -0.55, 0.63
    tonos_p = (SKY3, PLA0, PLA1, PLA2, NEB2)
    for dy in range(-pr, pr + 1):
        for dx in range(-pr, pr + 1):
            d2 = dx * dx + dy * dy
            if d2 > pr * pr or not (0 <= px + dx < W and FIELD_TOP <= py + dy < H):
                continue
            nz = math.sqrt(pr * pr - d2) / pr
            luz = max(0.0, (dx / pr) * lx + (dy / pr) * ly + nz * lz)
            nivel = 0.6 + luz * 3.2
            k = int(nivel)
            if nivel - k > _BAYER[(dy & 3) * 4 + (dx & 3)]:
                k += 1
            img.pset(px + dx, py + dy, tonos_p[min(4, k)])
    for i in range(-pr - 22, pr + 23):
        x = px + i
        y = py + int(i * 0.3) + 4
        detras = (x - px) ** 2 + (y - py) ** 2 <= pr * pr and i > 0
        if not detras and 0 <= x < W and y < H:
            img.pset(x, y, PLA2 if i < 0 else PLA1)
            if i % 2 == 0:
                img.pset(x, y + 1, PLA0)
    # estrellas lejanas: casi todas apenas, unas pocas con brillo en cruz
    for i in range(170):
        x, y = rng.randrange(W), rng.randrange(FIELD_TOP, H)
        c = STAR0 if i % 4 else STAR1
        img.pset(x, y, c)
    for i in range(9):
        x, y = rng.randrange(8, W - 8), rng.randrange(FIELD_TOP + 8, H - 8)
        img.pset(x, y, STAR3)
        for d in (1, 2):
            c = STAR2 if d == 1 else STAR1
            img.pset(x - d, y, c)
            img.pset(x + d, y, c)
            img.pset(x, y - d, c)
            img.pset(x, y + d, c)
    # el HUD: un panel con su filo
    img.rect(0, 0, W, HUD, PANEL)
    img.dither(0.5)
    img.rect(0, 0, W, 15, PANEL2)
    img.dither(1.0)
    img.rect(0, HUD - 1, W, 1, SHADOW)
    _FONDO.append(img)
    return img


def _envolturas(x, y, r):
    """dónde dibujar algo de radio r: si asoma por un borde, también del otro
    lado (el campo da la vuelta y así no aparece de golpe)."""
    xs = [0]
    if x - r < 0:
        xs.append(W)
    elif x + r > W:
        xs.append(-W)
    ys = [0]
    if y - r < FIELD_TOP:
        ys.append(FIELD_H)
    elif y + r > H:
        ys.append(-FIELD_H)
    return [(dx, dy) for dx in xs for dy in ys]


def _tono(ang, ramp):
    """el tono de una cara según hacia dónde mira: de cara a la luz, brillo;
    de espaldas, sombra."""
    b = math.cos(ang - LUZ)
    if b > 0.72:
        return ramp[4]
    if b > 0.2:
        return ramp[3]
    if b > -0.35:
        return ramp[2]
    return ramp[1]


ROCA_PASOS = 64                   # pasos de giro que se pintan
ROCA_PASO = math.tau / ROCA_PASOS
ROCA_IMG = 2 * int(RADIO[GRANDE] * 1.3 + 2) + 2


def _pintar_roca(img, roca, rot):
    """la piedra, facetada, en su imagen: cada cara se pinta según cuánto
    mira a la luz (arriba a la izquierda), con contorno oscuro y un filo de
    luz del lado iluminado. los cráteres giran con ella."""
    ramp = ORO_R if roca.dorada else ROCA_R
    img.cls(BG)
    r = roca.r
    n = len(roca.forma)
    paso = math.tau / n
    c = ROCA_IMG // 2
    angs = [rot + i * paso for i in range(n)]
    pts = [(c + math.cos(a) * r * f, c + math.sin(a) * r * f)
           for a, f in zip(angs, roca.forma)]
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        img.tri(c, c, x0, y0, x1, y1, _tono(angs[i] + paso / 2, ramp))
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        filo = math.cos(angs[i] + paso / 2 - LUZ) > 0.55
        img.line(x0, y0, x1, y1, ramp[4] if filo else ramp[0])
    for j in range(roca.tam):                     # cráteres
        a = rot + 1.3 + j * 2.4
        d = r * (0.35 + 0.15 * j)
        kx, ky = int(c + math.cos(a) * d), int(c + math.sin(a) * d)
        kr = 1 + (roca.tam - j) // 2 + (r > 15)
        # hundido: el borde de abajo a la derecha agarra luz y la pared de
        # arriba a la izquierda queda en sombra
        img.circ(kx, ky, kr, ramp[3])
        img.circ(kx - 1, ky - 1, kr, ramp[1])


class World:
    def __init__(self):
        self.e = Espacio()
        _fondo()                      # se hornea una vez, durante la cuenta 3-2-1
        self.fx = Fx(gravity=0.0, max_parts=240)
        self.thrust = False
        self.touch = web.is_touch()
        # en el celular el auto-fuego viene prendido: un pulgar gira, el otro
        # empuja, y no hace falta un tercero para disparar
        self.auto = self.touch
        self.auto_fx = 0
        self.ondas = []               # [x, y, r, rmax] anillos de explosión
        self.bolas = []               # [x, y, r, vida, vida0] fogonazos
        self.humo = []                # [x, y, r, vida, vida0]
        self.cascos = []              # [x, y, vx, vy, ang, giro, tam, vida, vida0, ramp]
        self.sprites = weakref.WeakKeyDictionary()   # roca -> (imagen, paso)
        self.cartel = None
        self.hud_golpe = 0
        self.camx = self.camy = 0.0   # para el paralaje de las estrellas
        rng = random.Random(3)
        self.capas = [
            [(rng.uniform(0, W), rng.uniform(0, FIELD_H), STAR1) for _ in range(34)],
            [(rng.uniform(0, W), rng.uniform(0, FIELD_H),
              STAR3 if i % 3 == 0 else STAR2) for i in range(18)]]
        try:
            lst = scores.top("asteroides", 1)
            self.record = lst[0]["score"] if lst else 0
        except Exception:
            self.record = 0
        self.record_visto = self.record <= 0
        self._efecto(("oleada", 1, OLEADAS[1][2]))
        self.cartel[2] -= 10          # el primero ya entra quieto: se ve en la cuenta

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
            self.fx.pop(W / 2, H - 40, "AUTO-FUEGO SÍ" if self.auto
                        else "AUTO-FUEGO NO", ACCENT if self.auto else TXT,
                        life=50)
        fire = self.auto or pyxel.btn(pyxel.KEY_SPACE) or pyxel.btn(pyxel.KEY_X)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            e.frenar()
            self.fx.burst(e.x, e.y, (WHITE, GLASS2, DIM), n=10, speed=1.6,
                          life=12)
        elif pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S):
            e.frenar(FRENO_SOSTENIDO)
        for ev in e.step(rot, self.thrust, fire):
            self._efecto(ev)
        self.camx += e.vx
        self.camy += e.vy
        if self.thrust and e.lives > 0:
            back = e.a + math.pi
            self.fx.burst(e.x + math.cos(back) * 8, e.y + math.sin(back) * 8,
                          (WHITE, GOLD3, FLAME, EMBER), n=2, speed=1.0, life=12,
                          spread=0.7, angle=back)
        if e.mult() >= 3 and pyxel.frame_count % 3 == 0:   # la nave en racha
            self.fx.burst(e.x, e.y, (PINK, NEON2), n=1, speed=0.3, life=14)
        for c in e.cometas:
            if not c.aviso and pyxel.frame_count % 2 == 0:
                self.fx.burst(c.x, c.y, CHISPA_COMETA, n=2, speed=0.5, life=16,
                              spread=0.9, angle=math.atan2(-c.vy, -c.vx))
        self.ondas = [[x, y, r + 3.2, rm] for x, y, r, rm in self.ondas if r < rm]
        self.bolas = [[x, y, r, v - 1, v0] for x, y, r, v, v0 in self.bolas if v > 1]
        self.humo = [[x, y - 0.12, r + 0.25, v - 1, v0]
                     for x, y, r, v, v0 in self.humo if v > 1]
        vivos = []
        for c in self.cascos:
            c[0] += c[2]
            c[1] += c[3]
            c[2] *= 0.97
            c[3] *= 0.97
            c[4] += c[5]
            c[7] -= 1
            if c[7] > 0:
                vivos.append(c)
        self.cascos = vivos
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
            self.fx.pop(W / 2, FIELD_TOP + 60, "¡NUEVO RÉCORD!", GOLD, life=70)
            self.fx.burst(W / 2, FIELD_TOP + 60, (WHITE, GOLD, PINK), n=28,
                          speed=2.6, life=28)
            self.fx.destello(GOLD)
        self.fx.update()

    def _cartel(self, tit, sub, col, frames=100):
        self.cartel = [tit, sub, frames, col, frames]

    def _estallido(self, x, y, r, n_cascos, ramp, humo=True):
        """la explosión: fogonazo, anillo, pedazos que giran y humo."""
        self.bolas.append([x, y, r, 8, 8])
        self.ondas.append([x, y, 3, r * 1.6 + 8])
        for i in range(n_cascos):
            if len(self.cascos) >= 90:
                break
            a = random.uniform(0, math.tau)
            v = random.uniform(0.5, 1.6) * (1.2 if r < 8 else 1.0)
            self.cascos.append([x + math.cos(a) * r * 0.4, y + math.sin(a) * r * 0.4,
                                math.cos(a) * v, math.sin(a) * v,
                                random.uniform(0, math.tau),
                                random.uniform(-0.25, 0.25),
                                random.choice((2, 2, 3, 4)) if r > 8 else 2,
                                random.randint(26, 46), 46, ramp])
        if humo:
            for i in range(2 + int(r // 6)):
                if len(self.humo) >= 30:
                    break
                self.humo.append([x + random.uniform(-r, r) * 0.5,
                                  y + random.uniform(-r, r) * 0.5,
                                  r * 0.4 + 2, 34, 34])

    def _efecto(self, ev):
        k = ev[0]
        if k == "rompe":
            x, y, tam, vale = ev[1], ev[2], ev[3], ev[4]
            r = RADIO[tam]
            self.fx.burst(x, y, CHISPA_ROCA, n=8 + tam * 7, speed=1.6 + tam * 0.5,
                          life=20 + tam * 4)
            self._estallido(x, y, r, 3 + tam * 3, ROCA_R)
            self.fx.pop(x, y - r - 8, "+%d" % vale, ACCENT if tam else GOLD,
                        k=1)
            self.fx.shake(1 + tam)
        elif k == "combo":
            self.fx.pop(ev[1], ev[2] - 26, "¡COMBO x%d!" % ev[3], PINK)
            self.fx.destello(PINK)
        elif k == "combo_frio":
            self.fx.pop(W / 2, FIELD_TOP + 26, "combo frío", TXT, k=1)
        elif k == "oleada":
            n, nota = ev[1], ev[2]
            self._cartel("OLEADA %d" % n, nota, OLA_COL[min(n, 5) - 1])
            if n > 1:
                self.fx.destello(ACCENT)
        elif k == "oleada_limpia":
            self._cartel("¡LIMPIA!", "oleada %d despejada  +%d" % (ev[1], ev[2]),
                         GOLD, RESPIRO)
            self.fx.burst(W / 2, (FIELD_TOP + H) / 2, (WHITE, GOLD, ACCENT),
                          n=46, speed=3.2, life=34)
            self.fx.destello(GOLD)
        elif k == "tormenta":
            self._cartel("¡TORMENTA!", "15 segundos · todo vale doble", WARN, 110)
            self.fx.shake(6)
            self.fx.destello(WARN, 6)
        elif k == "dorada_entra":
            self.fx.pop(W / 2, FIELD_TOP + 40, "¡DORADA!", GOLD)
            self.fx.destello(GOLD)
        elif k == "dorada":
            self.fx.burst(ev[1], ev[2], CHISPA_ORO, n=40, speed=3.2, life=36)
            self._estallido(ev[1], ev[2], 10, 6, ORO_R, humo=False)
            self.fx.pop(ev[1], ev[2] - 18, "+%d" % ev[3], GOLD)
            self.fx.shake(5)
            self.fx.destello(GOLD)
        elif k == "dorada_ida":
            self.fx.burst(ev[1], ev[2], (GOLD, DIM), n=8, speed=1.0, life=14)
        elif k == "mina":
            self.fx.burst(ev[1], ev[2], CHISPA_MINA, n=34, speed=3.0, life=28)
            self._estallido(ev[1], ev[2], 14, 4, (MINE0, MINE0, WARN2, MINE, GOLD))
            self.fx.pop(ev[1], ev[2] - 18, "+%d" % ev[3], MINE)
            self.fx.shake(6)
            self.fx.destello(FLAME)
        elif k == "onda":
            self.ondas.append([ev[1], ev[2], 4, ev[3]])
        elif k == "cometa_aviso":
            pass                                  # el aviso se dibuja solo
        elif k == "cometa":
            self.fx.burst(ev[1], ev[2], CHISPA_COMETA, n=34, speed=2.8, life=30)
            self._estallido(ev[1], ev[2], 10, 0, ORO_R, humo=False)
            self.fx.pop(ev[1], ev[2] - 18, "+%d" % ev[3], COMET)
            self.fx.shake(4)
            self.fx.destello(COMET)
        elif k == "caza":
            self.fx.burst(ev[1], ev[2], CHISPA_CAZA, n=38, speed=3.0, life=34)
            self._estallido(ev[1], ev[2], 14, 8,
                            (HUNTER0, HUNTER0, HUNTER, HUNTER2, WHITE))
            self.fx.pop(ev[1], ev[2] - 18, "+%d" % ev[3], GOLD)
            self.fx.shake(6)
            self.fx.destello(GOLD)
        elif k == "caza_entra":
            self._cartel("¡CAZADOR!", "te persigue y dispara", HUNTER, 80)
            self.fx.destello(HUNTER)
        elif k == "golpe":
            self.fx.burst(ev[1], ev[2], CHISPA_NAVE, n=36, speed=2.8, life=32)
            self._estallido(ev[1], ev[2], 12, 7,
                            (SHIP0, SHIP0, SHIP1, SHIP2, SHIP3))
            self.fx.pop(ev[1], ev[2] - 22, "-1 NAVE", WARN, life=40)
            self.fx.shake(7)
            self.fx.destello(WARN, 6)
            self.hud_golpe = 36
        elif k == "escudo_roto":
            self.fx.burst(ev[1], ev[2], (WHITE, SHIELDC, GLASS2), n=24, speed=2.4,
                          life=26)
            self.ondas.append([ev[1], ev[2], 6, 30])
            self.fx.pop(ev[1], ev[2] - 22, "¡te salvó el escudo!", SHIELDC, k=1)
            self.fx.shake(3)
        elif k == "power":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, PINK), n=20, speed=2.2,
                          life=24)
            self.fx.pop(ev[1], ev[2] - 22, POWER_NOMBRE[ev[3]], GOLD)
            self.fx.destello(GOLD)
        elif k == "chispa":
            self.fx.burst(ev[1], ev[2], (WHITE, GOLD, HUNTER), n=6, speed=1.3,
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
        # el fondo no tiembla: tiembla lo que está encima, y se lee igual
        pyxel.blt(0, FIELD_TOP, _fondo(), 0, FIELD_TOP, W, FIELD_H)
        pyxel.clip(0, FIELD_TOP, W, FIELD_H)
        self._estrellas()
        pyxel.camera(-sx, -sy)
        if e.tormenta() and (fc // 10) % 2:            # el borde late
            pyxel.rectb(0, FIELD_TOP, W, FIELD_H, WARN)
            pyxel.rectb(1, FIELD_TOP + 1, W - 2, FIELD_H - 2, WARN2)
        self._humo()
        for p in e.powers:
            self._power(p)
        for m in e.minas:
            self._mina(m)
        for roca in e.rocas:
            self._roca(roca)
        self._cascos()
        for c in e.cometas:
            self._cometa(c)
        self._tiros()
        if e.cazador:
            self._cazador(e.cazador)
        if e.lives > 0 and (not e.gracia or (fc // 4) % 2):
            self._nave(e)
        self._explosiones()
        self.fx.draw(0, 0)
        pyxel.camera()
        pyxel.clip()
        self.fx.draw_flash(0, FIELD_TOP, W, FIELD_H)
        self._dibujar_cartel()
        pyxel.blt(0, 0, _fondo(), 0, 0, W, HUD)
        self._hud()

    def _estrellas(self):
        """dos capas de estrellas que se corren al revés de la nave, a
        distinto ritmo: lo de cerca pasa más rápido (paralaje)."""
        fc = pyxel.frame_count
        for capa, k in ((self.capas[0], 0.12), (self.capas[1], 0.3)):
            ox = -self.camx * k
            oy = -self.camy * k + fc * k * 0.25        # una deriva suave
            for i, (x, y, c) in enumerate(capa):
                xx = int((x + ox) % W)
                yy = FIELD_TOP + int((y + oy) % FIELD_H)
                if k > 0.2 and (fc // 12 + i) % 9 == 0:
                    c = STAR1                            # titila
                pyxel.pset(xx, yy, c)
                if k > 0.2 and i % 3 == 0:
                    pyxel.pset(xx + 1, yy, STAR1)

    def _humo(self):
        for x, y, r, v, v0 in self.humo:
            pyxel.dither(0.45 * v / v0)
            pyxel.circ(int(x), int(y), int(r), SMOKE)
        pyxel.dither(1.0)

    def _explosiones(self):
        for x, y, r, rm in self.ondas:
            f = r / rm
            c = WHITE if f < 0.25 else GOLD3 if f < 0.5 else GOLD if f < 0.75 \
                else FLAME
            pyxel.circb(int(x), int(y), int(r), c)
            if f < 0.7:
                pyxel.dither(0.5)
                pyxel.circb(int(x), int(y), int(r) - 2, FLAME)
                pyxel.dither(1.0)
        for x, y, r, v, v0 in self.bolas:
            f = v / v0                                   # 1 -> 0
            rr = r * (0.5 + 0.7 * (1 - f))
            if f > 0.6:
                pyxel.circ(int(x), int(y), int(rr), GOLD3)
                pyxel.circ(int(x), int(y), int(rr * 0.6), WHITE)
            else:
                pyxel.dither(0.3 + f)
                pyxel.circ(int(x), int(y), int(rr), FLAME if f > 0.3 else EMBER)
                pyxel.circ(int(x), int(y), int(rr * 0.5), GOLD)
                pyxel.dither(1.0)

    def _cascos(self):
        tri = pyxel.tri
        for x, y, vx, vy, a, giro, t, v, v0, ramp in self.cascos:
            if v < 10 and v % 2:
                continue
            ca, sa = math.cos(a) * t, math.sin(a) * t
            p0 = (x + ca, y + sa)
            p1 = (x - ca * 0.6 - sa, y - sa * 0.6 + ca)
            p2 = (x - ca * 0.6 + sa, y - sa * 0.6 - ca)
            tri(*p0, *p1, *p2, _tono(a, ramp))
            pyxel.pset(int(p0[0]), int(p0[1]), ramp[4] if v > 20 else ramp[2])

    def _roca(self, roca):
        """la piedra ya pintada (ver `_pintar_roca`), con un solo blt. se
        vuelve a pintar sólo cuando giró un paso: casi nunca por frame."""
        if roca.dorada and roca.ttl < 90 and (pyxel.frame_count // 4) % 2:
            return                                      # titila antes de irse
        paso = int(roca.rot / ROCA_PASO) % ROCA_PASOS
        hit = self.sprites.get(roca)
        if hit is None or hit[1] != paso:
            img = hit[0] if hit else pyxel.Image(ROCA_IMG, ROCA_IMG)
            _pintar_roca(img, roca, paso * ROCA_PASO)
            self.sprites[roca] = hit = (img, paso)
        h = ROCA_IMG // 2
        for dx, dy in _envolturas(roca.x, roca.y, roca.r * 1.3):
            x, y = int(roca.x + dx) - h, int(roca.y + dy) - h
            pyxel.blt(x, y, hit[0], 0, 0, ROCA_IMG, ROCA_IMG, BG)
            if roca.dorada and (pyxel.frame_count // 5) % 3 == 0:
                pyxel.pset(x + h - 3, y + h - 3, WHITE)

    def _mina(self, m):
        x, y = int(m.x), int(m.y)
        cerca = dist2(m.x, m.y, self.e.x, self.e.y) < 56 * 56
        per = 4 if cerca else 12
        luz = (m.fase // per) % 2
        for a in range(6):                               # las púas
            ang = a * math.pi / 3 + m.fase * 0.02
            ex, ey = x + math.cos(ang) * 9, y + math.sin(ang) * 9
            pyxel.line(x, y, ex, ey, MINE0)
            pyxel.pset(int(ex), int(ey), MINE if luz else WARN)
        pyxel.circ(x, y, MINA_R, MINE0)
        pyxel.circ(x, y, MINA_R - 1, WARN2)
        pyxel.circ(x - 1, y - 1, MINA_R - 2, MINE)
        pyxel.circ(x - 2, y - 2, 1, COMET)
        pyxel.rect(x - 1, y - 1, 2, 2, WHITE if luz else GOLD)
        if luz and cerca:
            pyxel.dither(0.5)
            pyxel.circb(x, y, MINA_ONDA // 3, WARN)
            pyxel.dither(1.0)

    def _cometa(self, c):
        fc = pyxel.frame_count
        if c.aviso:
            # el aviso: una flecha en el borde por donde va a entrar, que
            # apunta hacia donde va, titilando cada vez más rápido
            ang = math.atan2(c.vy, c.vx)
            ca, sa = math.cos(ang), math.sin(ang)
            # la ruta punteada, siempre: por dónde va a pasar
            for i in range(3, 90):
                if (i + fc // 2) % 3:
                    continue
                px_ = int(c.x + ca * i * 4)
                py_ = int(c.y + sa * i * 4)
                if FIELD_TOP < py_ < H - 1:
                    pyxel.rect(px_, py_, 2, 2, COMET)
            if (fc // (6 if c.aviso > 25 else 2)) % 2:
                return
            x = max(8, min(W - 9, c.x))
            y = max(FIELD_TOP + 8, min(H - 9, c.y))
            p0 = (x + ca * 8, y + sa * 8)
            p1 = (x - ca * 5 - sa * 7, y - sa * 5 + ca * 7)
            p2 = (x - ca * 5 + sa * 7, y - sa * 5 - ca * 7)
            pyxel.tri(*p0, *p1, *p2, COMET)
            pyxel.trib(*p0, *p1, *p2, WHITE)
            big_ctext(int(x + ca * 16), int(y + sa * 16) - 6, "!", WHITE,
                      scale=2, shadow=SHADOW)
            return
        x, y = c.x, c.y
        for i in range(9, 0, -1):                        # la cola, de lejos a cerca
            f = i / 9
            tx, ty = x - c.vx * i * 1.6, y - c.vy * i * 1.6
            col = (GOLD3, COMET, FLAME, EMBER)[min(3, int(f * 4))]
            pyxel.circ(int(tx), int(ty), max(1, int((1 - f) * 5)), col)
        pyxel.circ(int(x), int(y), 5, COMET)
        pyxel.circ(int(x), int(y), 3, GOLD3)
        pyxel.circ(int(x) - 1, int(y) - 1, 1, WHITE)

    def _tiros(self):
        line = pyxel.line
        for t in self.e.tiros:
            x, y = t[0], t[1]
            if t[5]:
                line(x - t[2] * 0.9, y - t[3] * 0.9, x, y, GOLD)
                pyxel.rect(int(x) - 1, int(y) - 1, 2, 2, SHOT)
            else:
                pyxel.circ(int(x), int(y), 2, HUNTER0)
                pyxel.circ(int(x), int(y), 1, HUNTER)
                pyxel.pset(int(x), int(y), WHITE)

    def _nave(self, e):
        cosa, sina = math.cos(e.a), math.sin(e.a)
        fc = pyxel.frame_count

        def p(f, s):
            return (e.x + f * cosa - s * sina, e.y + f * sina + s * cosa)

        tri = pyxel.tri
        morro, izq, der, cola = p(11, 0), p(-7, -7), p(-7, 7), p(-4, 0)
        # el contorno: la misma silueta un poco más grande, oscura
        tri(*p(13, 0), *p(-8.5, -8.5), *p(-5, 0), SHIP0)
        tri(*p(13, 0), *p(-8.5, 8.5), *p(-5, 0), SHIP0)
        # las dos mitades del casco, cada una con el tono que le da la luz
        rampa = (SHIP0, SHIP1, SHIP1, SHIP2, SHIP3)
        tri(*morro, *izq, *cola, _tono(e.a - math.pi / 2, rampa))
        tri(*morro, *der, *cola, _tono(e.a + math.pi / 2, rampa))
        # la quilla y las alas con su franja
        pyxel.line(*morro, *cola, SHIP3)
        pyxel.line(*p(-1, -3), *p(-6, -6), NEON2)
        pyxel.line(*p(-1, 3), *p(-6, 6), NEON2)
        # la cabina
        cx, cy = p(3, 0)
        pyxel.circ(cx, cy, 2, GLASS)
        gx, gy = p(4, -1)
        pyxel.pset(gx, gy, GLASS2)
        # las toberas, y la llama cuando empuja
        for s in (-2.5, 2.5):
            tx, ty = p(-5, s)
            pyxel.pset(tx, ty, SHADOW)
        if self.thrust:
            largo = 16 + (fc % 3) * 2
            tri(*p(-5, -3), *p(-5, 3), *p(-largo, 0), EMBER)
            tri(*p(-5, -2.2), *p(-5, 2.2), *p(-largo + 3, 0), FLAME)
            tri(*p(-5, -1.2), *p(-5, 1.2), *p(-largo + 8, 0), GOLD3)
            pyxel.pset(*p(-5, 0), WHITE)
        if e.escudo:
            r = 14 + (fc // 8) % 2
            pyxel.dither(0.5)
            pyxel.circb(int(e.x), int(e.y), r - 2, SHIELDC)
            pyxel.dither(1.0)
            pyxel.circb(int(e.x), int(e.y), r, GLASS2)
            a = fc * 0.1
            pyxel.pset(int(e.x + math.cos(a) * r), int(e.y + math.sin(a) * r), WHITE)
        if e.triple:
            for s in (-5, 5):
                pyxel.pset(*p(8, s), ACCENT)
        if e.rafaga:
            pyxel.pset(*p(13, 0), SHOT)

    def _cazador(self, c):
        x, y = int(c.x), int(c.y)
        fc = pyxel.frame_count
        pyxel.elli(x - 11, y - 3, 23, 8, HUNTER0)            # el plato, con contorno
        pyxel.elli(x - 10, y - 2, 21, 6, HUNTER)
        pyxel.line(x - 8, y - 1, x + 6, y - 1, HUNTER2)       # luz arriba
        pyxel.line(x - 8, y + 2, x + 8, y + 2, HUNTER0)       # sombra abajo
        pyxel.elli(x - 5, y - 7, 11, 7, GLASS)                # la cúpula
        pyxel.elli(x - 4, y - 6, 6, 3, GLASS2)
        for i in range(4):                                    # las luces que giran
            lx = x - 7 + ((i * 5 + fc // 4) % 15)
            pyxel.pset(lx, y + 1, WHITE if i % 2 else GOLD)

    def _icono(self, x, y, tipo):
        """el dibujito de cada poder, de 7x7 alrededor de (x, y)."""
        if tipo == TRIPLE:
            for d in (-2, 0, 2):
                pyxel.line(x + d, y + 3, x + d * 2, y - 3, ACCENT)
        elif tipo == ESCUDO:
            pyxel.circb(x, y, 3, SHIELDC)
            pyxel.pset(x - 1, y - 1, WHITE)
        elif tipo == RAFAGA:
            pyxel.rect(x - 2, y - 3, 1, 7, SHOT)
            pyxel.rect(x + 1, y - 3, 1, 7, SHOT)
        else:
            pyxel.circb(x, y, 3, GOLD)
            for a in range(4):
                ang = a * math.pi / 2 + 0.78
                pyxel.pset(int(x + math.cos(ang) * 4.5),
                           int(y + math.sin(ang) * 4.5), GOLD)
            pyxel.pset(x, y, WHITE)

    def _power(self, p):
        x, y, tipo, ttl = int(p[0]), int(p[1]), p[2], p[3]
        fc = pyxel.frame_count
        if ttl < 90 and (fc // 4) % 2:
            return
        col = (ACCENT, SHIELDC, SHOT, GOLD)[tipo]
        r = POWER_R
        pyxel.circ(x, y, r, SHADOW)
        pyxel.circb(x, y, r, col)
        pyxel.circb(x, y, r - 1, PANEL2)
        pyxel.pset(x - r + 2, y - r + 3, WHITE)
        a = fc * 0.08
        for i in range(3):                                # el anillo que gira
            aa = a + i * math.tau / 3
            pyxel.pset(int(x + math.cos(aa) * (r + 2)),
                       int(y + math.sin(aa) * (r + 2)), WHITE)
        self._icono(x, y, tipo)

    def _dibujar_cartel(self):
        c = self.cartel
        if not c:
            return
        tit, sub, f, col, f0 = c
        dx = max(0, (f - (f0 - 10)) * 22)
        if f < 20 and (f // 3) % 2:
            return
        k = 3
        while k > 1 and big_width(tit, k) > W - 10:
            k -= 1
        y = 168                        # bajo la cuenta 3-2-1 del Cabinet
        alto = 6 * k + (18 if sub else 8)
        fx.flash(SHADOW, 0.7, 0, y - 7, W, alto + 4)
        pyxel.rect(0, y - 8, W, 1, col)
        pyxel.rect(0, y + alto - 3, W, 1, col)
        big_ctext(W / 2 + dx + 2, y + 2, tit, BG, scale=k)
        big_ctext(W / 2 + dx, y, tit, col, scale=k)
        if sub:
            ks = 2 if big_width(sub, 2) <= W - 10 else 1
            big_ctext(W / 2 + dx, y + 6 * k + 4, sub, TXT, scale=ks,
                      shadow=SHADOW)

    def _hud(self):
        e = self.e
        fc = pyxel.frame_count
        # fila 1: puntaje, oleada y reloj, en grande
        sc = "%d" % e.score
        big_text(5, 5, sc, GOLD if e.tormenta() else ACCENT, scale=2,
                 shadow=SHADOW)
        x = 5 + big_width(sc, 2) + 4
        m = e.mult() * (2 if e.tormenta() else 1)
        if m > 1:                                   # el combo, con su mecha
            s = "x%d" % m
            col = PINK if (fc // 6) % 2 else GOLD
            pyxel.rect(x - 1, 3, big_width(s, 2) + 2, 13, SHADOW)
            big_text(x, 5, s, col, scale=2)
            if e.combo_t:
                fx.bar(x - 1, 17, big_width(s, 2) + 2, 2, e.combo_t / e.mecha(),
                       PINK, GRID)
        ox = 134
        text(ox - 26, 8, "OLEADA", DIM)
        big_text(ox, 5, "%d" % e.oleada, TXT, scale=2, shadow=SHADOW)
        if e.respiro and (fc // 6) % 2:
            text(ox + 14, 8, "LIMPIA", GOLD)
        elif e.oleada_t < 5 * 60 and not e.respiro:
            text(ox + 14, 8, "OTRA!", WARN if (fc // 8) % 2 else TXT)
        s = e.time // 60
        urge = s <= 10
        col = WARN if urge and fc % 30 < 15 else TXT
        r = "%d" % s
        big_text(W - big_width(r, 2) - 5, 5, r, col, scale=2, shadow=SHADOW)
        # fila 2: vidas, poderes y auto-fuego
        jit = ((fc % 4) - 1.5) if self.hud_golpe else 0
        for i in range(VIDAS):
            col, luz = (SHIP2, SHIP3) if i < e.lives else (GRID, GRID)
            if i == e.lives and self.hud_golpe and (fc // 3) % 2:
                col = luz = WARN
            bx = int(6 + i * 12 + jit)
            pyxel.tri(bx + 4, 18, bx, 26, bx + 8, 26, SHIP0)
            pyxel.tri(bx + 4, 19, bx + 1, 25, bx + 7, 25, col)
            pyxel.line(bx + 4, 19, bx + 1, 25, luz)
            pyxel.pset(bx + 4, 23, GLASS if i < e.lives else GRID)
        px = 50
        for tipo, t, t0 in ((ESCUDO, e.escudo, 0), (TRIPLE, e.triple, TRIPLE_TTL),
                            (RAFAGA, e.rafaga, RAFAGA_TTL)):
            if not t:
                continue
            if t0 and t < 60 and (fc // 4) % 2:
                px += 14
                continue
            self._icono(px + 4, 22, tipo)
            if t0:
                fx.bar(px, 27, 9, 1, t / t0, (ACCENT, SHIELDC, SHOT)[tipo], GRID)
            px += 14
        ax = W - 30
        if self.auto:
            on = not self.auto_fx or (fc // 4) % 2
            pyxel.rect(ax, 19, 25, 8, ACCENT if on else SHIP3)
            text(ax + 5, 20, "AUTO", BG)
        else:
            pyxel.rectb(ax, 19, 25, 8, GRID)
            text(ax + 5, 20, "AUTO", DIM)
        # el reloj también como barra, a todo lo ancho bajo el panel
        pyxel.rect(0, HUD - 2, W, 2, SHADOW)
        pyxel.rect(0, HUD - 2, int(W * e.time / TIME), 2,
                   WARN if e.tormenta() else ACCENT)
        pyxel.rect(int(W * TORMENTA / TIME), HUD - 3, 1, 3, WARN)


class Game:
    def __init__(self):
        touch = web.is_touch()
        Cabinet(
            game_id="asteroides", title="ASTEROIDES",
            subtitle="90 segundos de deriva",
            howto=(["las flechas giran · empuje y freno",
                    "auto-fuego prendido: dispara solo"]
                   if touch else
                   ["izq/der giran · arriba empuja · abajo frena",
                    "espacio dispara (mantén) · c auto-fuego"]) +
                  ["limpia cada oleada · ojo con minas y cometas",
                   "roturas seguidas hacen combo · caza la dorada"],
            width=W, height=H, palette=PAL, scale=2, scoring=True,
            ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=ACCENT,
                        warn=WARN, shadow=SHADOW, panel=GRID),
            make_world=lambda: World(),
        ).run()


if __name__ == "__main__":
    Game()
