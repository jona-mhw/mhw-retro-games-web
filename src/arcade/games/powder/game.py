# powder — física de partículas estilo falling sand, con pyxel
#
# la grilla guarda en cada celda un byte que YA es el índice de paleta:
# cada material ocupa un rango de tonos, así la textura viaja con la partícula
# y el frame se dibuja copiando el bytearray al framebuffer, sin conversión.
# la simulación solo recorre los chunks que tuvieron actividad.
import math
import os
import random
from collections import deque

import pyxel

from pixelkit import config, crt, fx, web
from pixelkit.blit import FpsMeter, blit_slow, fast_blit
from pixelkit.palette import shades as _shades
from pixelkit.pxtext import big_ctext, big_text, big_width, ctext, text as pxtext

W, H = 224, 336
# vertical, para el celular parado. la mesa simula ~62.000 celdas, las mismas
# que la versión apaisada (320x194): cada celda es un píxel, nada se escala, y
# en el teléfono (~1.74x) cada grano mide casi 2 px de pantalla: más fino que
# antes, no más tosco.
#
# la barra de abajo va **por categorías**: una fila de 5 pestañas (polvos,
# fluidos, sólidos, energía, borrar) y debajo los materiales de la pestaña
# abierta, a lo sumo 6, en casillas de 37×38 px. en el celular son 64×66 px de
# pantalla: más grandes que las de antes (64×37), y pegadas al pulgar.
TAB_H = 22
CELL_H = 38
CELL_W = 37
UI_H = TAB_H + CELL_H
SH = H - UI_H  # alto del área de simulación
CSS = 390 / W  # cuánto mide un píxel del juego en un celular de 390 px de ancho

CHB = 5  # chunk de 32x32
CHS = 1 << CHB
CW = (W + CHS - 1) >> CHB
CH_ROWS = (SH + CHS - 1) >> CHB
NCHUNK = CW * CH_ROWS

# tipos lógicos
(K_EMPTY, K_WALL, K_WOOD, K_METAL, K_TRUNK, K_LEAF, K_SAND, K_WATER, K_OIL,
 K_PLANT, K_ACID, K_FIRE, K_LAVA, K_STONE, K_STEAM, K_SMOKE, K_POWDER,
 K_ICE, K_SEED, K_GAS, K_SPARK, K_MCOOL,
 K_SNOW, K_FWORK, K_ROCKET, K_EMBER, K_VIRUS, K_BHOLE, K_CLONE,
 K_PLASMA, K_ROCK) = range(31)

NAMES = {
    K_WALL: "muro", K_WOOD: "madera", K_SAND: "arena", K_WATER: "agua",
    K_OIL: "aceite", K_PLANT: "planta", K_ACID: "ácido", K_FIRE: "fuego",
    K_LAVA: "lava", K_STONE: "piedra", K_STEAM: "vapor", K_SMOKE: "humo",
    K_POWDER: "pólvora", K_EMPTY: "borrar", K_ICE: "hielo", K_SEED: "semilla",
    K_GAS: "gas", K_SPARK: "chispa", K_METAL: "metal",
    K_TRUNK: "tronco", K_LEAF: "hoja",
    K_SNOW: "nieve", K_FWORK: "cohete", K_ROCKET: "cohete", K_EMBER: "chispas",
    K_VIRUS: "virus", K_BHOLE: "agujero negro", K_CLONE: "clonador",
    K_PLASMA: "rayo", K_ROCK: "roca",
}
# en la casilla de 53 px entran 12 letras justas
SHORT = {**NAMES, K_BHOLE: "agujero"}

FIRE_RAMP = (0xFFF6D8, 0xFFE89A, 0xFFD24A, 0xFFAE1E, 0xFF8A12, 0xF5670C,
             0xE04A08, 0xC23306, 0x9C2205, 0x7A1604, 0x551003, 0x3A0B02)
LAVA_RAMP = (0xFF9A2E, 0xFF7A1E, 0xF25C12, 0xDC4409, 0xC03206, 0xA02404)

# _shades (tonos de un color) vive ahora en pixelkit.palette, se importa arriba.

PAL = [0x0D0D14]  # índice 0 = vacío
_KIND = bytearray(256)
BASE = {}
NVAR = {}


def _reg(kind, colors):
    BASE[kind] = len(PAL)
    NVAR[kind] = len(colors)
    for c in colors:
        _KIND[len(PAL)] = kind
        PAL.append(c)


# el orden importa: lo inerte va primero para que el loop lo descarte
# con una sola comparación (e < FIRST_ACTIVE) sin mirar la tabla KIND
_reg(K_WALL, _shades(0x8A8FA3, 4))
_reg(K_WOOD, _shades(0x8A5A2E, 4))
_reg(K_METAL, _shades(0xB8C2D0, 4))
_reg(K_TRUNK, _shades(0x8A5C30, 4))
_reg(K_LEAF, _shades(0x4FC24F, 5))
_reg(K_ROCK, _shades(0x4E4650, 4, 0.8, 1.15))    # roca de escenografía (volcán)
FIRST_ACTIVE = len(PAL)
_reg(K_SAND, _shades(0xE8C96A, 5))
# el 5º tono del agua es "templada": la que acaba de salir del hielo.
# el hielo no la vuelve a congelar hasta que se enfría, así el calor gana terreno
_reg(K_WATER, _shades(0x3A72D8, 4, 0.85, 1.12) + [0x5AA0E0])
_reg(K_OIL, _shades(0x6B5836, 3))
_reg(K_PLANT, _shades(0x3FAE3F, 4))
_reg(K_ACID, _shades(0xA8E63C, 3))
_reg(K_FIRE, FIRE_RAMP)
_reg(K_LAVA, LAVA_RAMP)
_reg(K_STONE, _shades(0x6E7280, 4))
_reg(K_STEAM, _shades(0xC8DCF0, 3))
_reg(K_SMOKE, _shades(0x4A4A52, 4))
_reg(K_POWDER, _shades(0x9A9A6E, 4))
_reg(K_ICE, _shades(0xA8DCF0, 4, 0.88, 1.10))
_reg(K_SEED, _shades(0xC8A04A, 3))
_reg(K_GAS, _shades(0x8A6ECC, 3))
_reg(K_SPARK, [0xFFFFFF, 0xC8F0FF, 0x7ADCFF, 0x3AB4F0])
# cable recién descargado: mientras enfría no vuelve a conducir, así el pulso
# avanza en una sola dirección en vez de rebotar (como en wireworld)
_reg(K_MCOOL, _shades(0x7E8698, 3))
# lo nuevo. todo activo: va después de FIRST_ACTIVE
_reg(K_SNOW, _shades(0xEEF4FF, 3, 0.90, 1.0))
_reg(K_FWORK, [0xE03A44, 0xF2ECE0, 0xC02A34, 0x3A5AD0])     # cohete a rayas
# los fuegos artificiales vienen en 5 colores: el cohete lleva el suyo en el
# tono (ROCKET_BASE + color) y las chispas en un tramo de 4 que se apaga
FW_COLORS = ((0xFF5A6E, 0xE8304A, 0xA81A30, 0x5A0C18),       # rojo
             (0x8AFF7A, 0x3ED84A, 0x1E9A2E, 0x0C4A16),       # verde
             (0x9AD8FF, 0x4A9EFF, 0x2A5AE0, 0x142A80),       # azul
             (0xFFF08A, 0xFFC83A, 0xE08A1A, 0x7A400A),       # oro
             (0xFF9AF0, 0xF04ADC, 0xA82AA8, 0x501450))       # rosa
NFW = len(FW_COLORS)
_reg(K_ROCKET, [c[0] for c in FW_COLORS])
_reg(K_EMBER, [t for c in FW_COLORS for t in c])
_reg(K_VIRUS, _shades(0xC844E8, 4, 0.7, 1.15))
_reg(K_BHOLE, [0x000000, 0x7A3AE0, 0xB88AFF, 0xF0E0FF])   # núcleo y borde que brilla
_reg(K_CLONE, [0x8A7A4A, 0xE8C040, 0xFFE070])               # apagado, cargado x2
_reg(K_PLASMA, [0xFFFFFF, 0xEAF6FF, 0xB8E2FF, 0x88BCFF])

# --- la piel: bordes con luz, fondo, brillos ----------------------------------
# cada material sólido o líquido tiene un tono de luz (su borde de arriba, el
# que da al aire) y uno de sombra (el de abajo). se aplican al dibujar, no en la
# grilla: la simulación no se entera.
RIM = {K_WALL: (1.30, 0.62), K_WOOD: (1.35, 0.6), K_METAL: (1.18, 0.62),
       K_TRUNK: (1.35, 0.6), K_LEAF: (1.30, 0.62), K_ROCK: (1.9, 0.65),
       K_SAND: (1.16, 0.70), K_WATER: (1.55, None), K_OIL: (1.6, None),
       K_PLANT: (1.35, 0.62), K_ACID: (1.25, None), K_STONE: (1.32, 0.64),
       K_POWDER: (1.30, 0.66), K_ICE: (1.12, 0.78), K_SEED: (1.3, 0.65),
       K_SNOW: (1.0, 0.82), K_FWORK: (1.2, 0.6), K_MCOOL: (1.2, 0.62),
       K_VIRUS: (1.3, 0.6), K_CLONE: (1.35, 0.6)}


def _mul(c, k):
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    return (min(255, int(r * k)) << 16) | (min(255, int(g * k)) << 8) | min(255, int(b * k))


_TL = list(range(256))       # índice -> su tono de luz
_TD = list(range(256))       # índice -> su tono de sombra
for _k, (_lk, _dk) in RIM.items():
    _mid = PAL[BASE[_k] + NVAR[_k] // 2]
    _li = len(PAL)
    PAL.append(_mul(_mid, _lk) if _k != K_LAVA else 0xFFC850)
    _di = None
    if _dk is not None:
        _di = len(PAL)
        PAL.append(_mul(_mid, _dk))
    for _e in range(BASE[_k], BASE[_k] + NVAR[_k]):
        _TL[_e] = _li
        if _di is not None:
            _TD[_e] = _di
# la lava tiene su costra encendida arriba
_TL[BASE[K_LAVA]:BASE[K_LAVA] + NVAR[K_LAVA]] = [len(PAL)] * NVAR[K_LAVA]
PAL.append(0xFFC24A)
T_LIGHT = bytes(_TL)
T_DARK = bytes(_TD)
# el cielo: un degradé de noche con tramado, y estrellas
SKY = [0x07070F, 0x0A0A16, 0x0D0E1D, 0x111326, 0x15182F, 0x1A1E38, 0x20253F]
SKY_BASE = len(PAL)
PAL.extend(SKY)
STAR1, STAR2 = len(PAL), len(PAL) + 1
PAL.extend([0x8A90C0, 0xE8ECFF])
# el resplandor de lo que quema (tibio) y del rayo (frío), y el brillo del agua
GLOW1, GLOW2, COLD1, COLD2, SPARKLE = range(len(PAL), len(PAL) + 5)
PAL.extend([0x4A2210, 0x2A140E, 0x1E3462, 0x141F3C, 0xE8F6FF])
assert len(PAL) <= 247, len(PAL)

LAB_RED, UI_TAB, UI_SH, UI_BG, UI_LINE, UI_DIM, UI_TXT, UI_HI = (247, 248, 249, 250,
                                                               251, 252, 253, 254)
UI_TAB2 = 255
while len(PAL) < 256:
    PAL.append(0)
PAL[UI_TAB2] = 0x343A56
PAL[LAB_RED] = 0xE04A4A
PAL[UI_TAB] = 0x22263A
PAL[UI_SH] = 0x050508
PAL[UI_BG] = 0x101018
PAL[UI_LINE] = 0x2E3242
PAL[UI_DIM] = 0x8A90A8
PAL[UI_TXT] = 0xE8ECF5
PAL[UI_HI] = 0xFFD24A
PAL[UI_BG] = 0x0E0F18
PAL[UI_TAB] = 0x1E2236
KIND = bytes(_KIND)
# tablas de máscaras: 0xFF donde la celda es de esa clase, 0 si no
T_EMPTY = bytes([0xFF] + [0] * 255)
T_HOT = bytes(0xFF if _KIND[_i] in (K_FIRE, K_LAVA, K_ROCKET) and _i
              else 0 for _i in range(256))
T_COLD = bytes(0xFF if _KIND[_i] in (K_PLASMA, K_SPARK) and _i else 0
               for _i in range(256))
T_WATER = bytes(0xFF if _KIND[_i] == K_WATER and _i else 0 for _i in range(256))
# las cuatro de una: bit 0 vacío, 1 caliente, 2 frío, 3 agua
T_CLASS = bytes((T_EMPTY[_i] & 1) | (T_HOT[_i] & 2) | (T_COLD[_i] & 4) | (T_WATER[_i] & 8)
                for _i in range(256))
INERT = bytes(range(FIRST_ACTIVE))   # lo que el loop descarta sin mirar

F_BASE, F_N = BASE[K_FIRE], NVAR[K_FIRE]
L_BASE, L_N = BASE[K_LAVA], NVAR[K_LAVA]
SP_BASE, SP_N = BASE[K_SPARK], NVAR[K_SPARK]
RK_BASE = BASE[K_ROCKET]
EM_BASE = BASE[K_EMBER]
VI_BASE, VI_N = BASE[K_VIRUS], NVAR[K_VIRUS]
BH_BASE, BH_N = BASE[K_BHOLE], NVAR[K_BHOLE]
CL_BASE = BASE[K_CLONE]
PL_BASE, PL_N = BASE[K_PLASMA], NVAR[K_PLASMA]
SM_BASE, SM_N = BASE[K_SMOKE], NVAR[K_SMOKE]
WA_BASE, WA_N = BASE[K_WATER], NVAR[K_WATER] - 1  # tonos de agua fría
W_WARM = BASE[K_WATER] + WA_N                     # agua recién deshelada
# tabla (índice de paleta, fila) -> con qué índice se dibuja la celda al llegar a
# esa fila. para todo lo demás es la identidad; para el agua fría son **bandas
# horizontales**: con un tono al azar por celda el agua se lee granulada, como
# arena mojada, y en bandas se lee como agua. cuesta una lectura de tabla por
# movimiento, contra un random.
_TF = bytearray(256 * SH)
for _e in range(256):
    _b = _e * SH
    for _y in range(SH):
        _TF[_b + _y] = _e
for _n in range(NVAR[K_WATER] - 1):
    _b = (BASE[K_WATER] + _n) * SH
    for _y in range(SH):
        _TF[_b + _y] = (BASE[K_WATER] + NVAR[K_WATER] - 2
                        - ((_y >> 2) % (NVAR[K_WATER] - 1)))
TONO_FILA = bytes(_TF)

FIRE_MAX = 55     # vida a la que el fuego arde en su tono más claro
SPARK_LIFE = 5    # frames que brilla cada celda al pasar el pulso
MCOOL_TIME = 24   # frames que el cable queda descargado tras conducir

# líquidos: se escurren de lado (agua, aceite, ácido)
LIQUIDS = (K_WATER, K_OIL, K_ACID)
# ¿el índice de paleta es de un líquido? una tabla de 256 bytes en vez de
# `KIND[e] in LIQUIDS`: una lectura contra una tupla, y esto se consulta por
# celda de líquido en cada frame
IS_LIQ = bytes(1 if _KIND[_i] in LIQUIDS else 0 for _i in range(256))
# cuántas celdas puede correrse un líquido por frame, y de paso hasta dónde **ve**
# el desnivel: sólo se mueve si en ese alcance encuentra por dónde bajar (o si
# tiene peso encima). con 5 px el agua se amontonaba en un talud de pendiente
# 1:10 y se quedaba así, como la arena: la cima no alcanzaba a ver la bajada, que
# estaba a 10-15 px. el aceite va espeso a propósito. (16 y no 14 desde la mesa
# vertical: con 14 un montículo en el charco más angosto quedaba 4 px arriba)
SPREAD, SPREAD_OIL = 16, 3
# el agua guarda en `aux` cuántos frames viene cayendo: es su velocidad. al
# tocar fondo, si venía con impulso, salpica.
FALL_MAX = 12
SPLASH_MIN = 4                   # caída mínima para que valga la pena salpicar
# lo que el fuego puede prender, con su probabilidad de prender por contacto
FLAMMABLE = {K_PLANT: 0.30, K_OIL: 0.70, K_WOOD: 0.05, K_LEAF: 0.38,
             K_TRUNK: 0.06, K_SEED: 0.25, K_GAS: 0.90}
# lo que el ácido NO disuelve
ACID_PROOF = (K_EMPTY, K_WALL, K_ACID, K_WATER, K_FIRE, K_SMOKE, K_STEAM,
              K_SPARK, K_GAS, K_CLONE, K_BHOLE, K_PLASMA, K_EMBER, K_ROCKET)
# suelo firme donde una semilla puede echar raíz
SOIL = (K_SAND, K_STONE, K_WOOD, K_PLANT, K_TRUNK, K_WALL, K_METAL, K_ROCK)
# lo que enciende al gas, a la pólvora, al cohete y derrite la nieve
HOT = (K_FIRE, K_LAVA, K_SPARK, K_PLASMA)
# el virus se come todo menos esto (y el fuego lo quema)
VIRUS_PROOF = (K_EMPTY, K_WALL, K_ROCK, K_VIRUS, K_CLONE, K_BHOLE, K_FIRE, K_SMOKE,
               K_STEAM, K_EMBER, K_PLASMA, K_LAVA, K_SPARK, K_ROCKET)
# el agujero negro chupa todo menos esto
BH_PROOF = (K_EMPTY, K_WALL, K_BHOLE, K_CLONE, K_ROCK)
BH_RAY = 15                      # de cerca: hasta dónde mira cada celda del borde
BH_R = 34                        # alcance del tirón, en celdas
# lo que el clonador puede copiar: lo que se mueve o cambia, nada de muros
CLONABLE = bytes(1 if (_i >= FIRST_ACTIVE and _KIND[_i] not in
                       (K_CLONE, K_BHOLE, K_ROCKET, K_EMBER, K_PLASMA, K_SPARK,
                        K_MCOOL, K_TRUNK, K_LEAF)) else 0 for _i in range(256))
CLONE_P = 0.06                   # cuánto escupe por frame cada celda cargada
CLONE_FW = 0.012
# cada uno a su ritmo: los cohetes poco (cada uno es un show), la lava mucho
# (es viscosa y se amontona en la boca: si sale poco, el volcán no erupciona)
CLONE_RATE = {K_FWORK: CLONE_FW, K_LAVA: 0.5}
# lo que un cohete atraviesa al subir
ROCKET_PASS = bytes(1 if _KIND[_i] in (K_FWORK, K_SMOKE, K_STEAM, K_EMBER, K_FIRE,
                                       K_GAS) else 0 for _i in range(256))                 # los cohetes, mucho menos: cada uno es un show
LAVA_COOL = 0.0006               # la lava quieta se hace piedra (≈30 s): un
                                 # volcán que no se enfría llena la pantalla
VIRUS_LIFE = (50, 110)
# lo que necesita una vida en `aux` al nacer (si no, se muere en el acto)
VIDA = (K_FIRE, K_STEAM, K_SMOKE, K_VIRUS)
PLASMA_LIFE = 10
# lo que el pincel puede desplazar: se le echa lava al mar sin borrarlo antes,
# pero lo que construiste (muro, metal, hielo...) no se pisa por accidente
REPLACEABLE = (K_EMPTY, K_WATER, K_OIL, K_ACID, K_STEAM, K_SMOKE, K_GAS, K_FIRE)
REPL = bytes(1 if _KIND[_i] in REPLACEABLE else 0 for _i in range(256))
NB4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
NB8 = ((1, 0), (-1, 0), (0, 1), (0, -1),
       (1, 1), (1, -1), (-1, 1), (-1, -1))

CATS = (("polvos", (K_SAND, K_POWDER, K_STONE, K_SEED, K_SNOW, K_FWORK)),
        ("fluidos", (K_WATER, K_OIL, K_ACID, K_LAVA, K_GAS, K_VIRUS)),
        ("sólidos", (K_WALL, K_WOOD, K_METAL, K_ICE, K_PLANT, K_CLONE)),
        ("energía", (K_FIRE, K_SPARK, K_PLASMA, K_BHOLE)),
        ("borrar", (K_EMPTY,)))
TOOLS = tuple(k for _, ks in CATS for k in ks)
TAB_W = W // len(CATS)
TOOL_CAT = {k: c for c, (_, ks) in enumerate(CATS) for k in ks}


def cat_of(tool):
    """la pestaña donde vive la herramienta n."""
    return TOOL_CAT[TOOLS[tool]]


def cell_box(i):
    """(x, y, w, h) de la casilla i de la fila de materiales."""
    return 1 + i * CELL_W, SH + TAB_H, CELL_W - 1, CELL_H


def tool_at(mx, my, cat):
    """qué hay bajo el dedo en la barra: ("tab", c), ("tool", n) o None."""
    if my < SH:
        return None
    if my < SH + TAB_H:
        return ("tab", max(0, min(len(CATS) - 1, mx // TAB_W)))
    i = (mx - 1) // CELL_W
    ks = CATS[cat][1]
    if 0 <= i < len(ks):
        return ("tool", TOOLS.index(ks[i]))
    return None


def fire_tone(life):
    t = F_N - 1 - (life * F_N // FIRE_MAX)
    return F_BASE + (0 if t < 0 else (F_N - 1 if t >= F_N else t))


class Sim:
    def __init__(self):
        n = W * SH
        self.g = bytearray(n)          # byte = índice de paleta
        self.aux = bytearray(n)        # vida de fuego / vapor / humo
        self.upd = bytearray(n)        # ya se movió en este frame
        self._zero = bytes(n)
        self.active = bytearray(b"\x01" * NCHUNK)
        self.nxt = bytearray(NCHUNK)
        self._zc = bytes(NCHUNK)
        self.frame = 0
        self.awake = NCHUNK
        self.bursts = []               # fuegos artificiales abriéndose: [x, y, r, rmax, color]
        self.flash = 0                 # frames de fogonazo pendientes (los rayos)

    def clear(self):
        self.g[:] = self._zero
        self.aux[:] = self._zero
        self.active[:] = b"\x01" * NCHUNK
        self.bursts = []

    def wake(self, x, y):
        c = (y >> CHB) * CW + (x >> CHB)
        self.nxt[c] = 1
        self.active[c] = 1

    def step(self):
        self.frame += 1
        g, aux, upd, nxt = self.g, self.aux, self.upd, self.nxt
        active, KND = self.active, KIND
        upd[:] = self._zero
        nxt[:] = self._zc
        r = random.random
        ri = random.randint
        f = self.frame
        if self.bursts:
            self._abrir_fuegos()

        for y in range(SH - 1, -1, -1):
            crow = (y >> CHB) * CW
            row = y * W
            flip = (y ^ f) & 1
            down_row = ((y + 1) >> CHB) * CW
            up_row = ((y - 1) >> CHB) * CW
            for ci in range(CW):
                cx = (CW - 1 - ci) if flip else ci
                chunk = crow + cx
                if not active[chunk]:
                    continue
                x0 = cx << CHB
                x1 = x0 + CHS
                if x1 > W:
                    x1 = W
                # el tramo de fila sin nada que se mueva se salta de un saque:
                # un translate en C contra 32 vueltas de python. en un chunk
                # despierto la mayoría de las filas son aire o muro.
                if not g[row + x0:row + x1].translate(None, INERT):
                    continue
                xs = range(x1 - 1, x0 - 1, -1) if flip else range(x0, x1)
                for x in xs:
                    i = row + x
                    e = g[i]
                    if e < FIRST_ACTIVE or upd[i]:
                        continue
                    k = KND[e]

                    if k == K_SAND or k == K_POWDER or k == K_STONE or k == K_FWORK:
                        if k == K_FWORK:
                            # la mecha: algo caliente al lado y despega
                            dx, dy = NB4[int(r() * 4)]
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < W and 0 <= ny < SH and \
                                    KND[g[ny * W + nx]] in HOT:
                                g[i] = RK_BASE + int(r() * NFW)
                                aux[i] = ri(60, 130)
                                upd[i] = 1
                                nxt[chunk] = 1
                                continue
                        if y < SH - 1:
                            j = i + W
                            b = g[j]
                            if b == 0:
                                g[j] = e
                                g[i] = 0
                                upd[j] = 1
                                nxt[chunk] = 1
                                nxt[down_row + cx] = 1
                                continue
                            bk = KND[b]
                            if bk in LIQUIDS and r() < (0.55 if k == K_STONE else 0.4):
                                g[j] = e
                                g[i] = b
                                upd[j] = 1
                                upd[i] = 1
                                nxt[chunk] = 1
                                nxt[down_row + cx] = 1
                                continue
                            if bk in LIQUIDS:
                                # se hunde, sólo que no en este frame: que el
                                # chunk no se duerma con el grano a medio camino
                                nxt[chunk] = 1
                            if k != K_STONE:
                                d = 1 if r() < 0.5 else -1
                                for dx in (d, -d):
                                    nx = x + dx
                                    if 0 <= nx < W and g[i + dx] == 0 and g[j + dx] == 0:
                                        g[j + dx] = e
                                        g[i] = 0
                                        upd[j + dx] = 1
                                        nxt[chunk] = 1
                                        nxt[down_row + (nx >> CHB)] = 1
                                        break
                        continue

                    if k == K_WATER or k == K_OIL or k == K_ACID:
                        # el atajo del charco: una gota encerrada (abajo, los
                        # costados y las diagonales de abajo ocupados) no tiene
                        # a dónde ir, y el interior de un lago son miles de ésas
                        # en cada frame. se descarta sin sortear nada. el ácido y
                        # el agua templada no: tienen cosas que hacer quietos.
                        if k != K_ACID and e != W_WARM and 0 < x < W - 1 \
                                and y < SH - 1:
                            j = i + W
                            b = g[j]
                            if b and g[i - 1] and g[i + 1] and g[j - 1] \
                                    and g[j + 1] and (aux[i] & 15) < SPLASH_MIN \
                                    and not (k == K_WATER and KND[b] == K_OIL):
                                continue
                        if e == W_WARM:
                            nxt[chunk] = 1  # sigue viva mientras se enfría
                            if r() < 0.012:
                                e = WA_BASE + int(r() * WA_N)
                                g[i] = e
                        if k == K_ACID and r() < 0.25:
                            dx, dy = NB4[int(r() * 4)]
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < W and 0 <= ny < SH:
                                j2 = ny * W + nx
                                if KND[g[j2]] not in ACID_PROOF:
                                    if r() < 0.2:
                                        g[j2] = BASE[K_SMOKE] + int(r() * NVAR[K_SMOKE])
                                        aux[j2] = ri(20, 50)
                                        upd[j2] = 1
                                    else:
                                        g[j2] = 0
                                    nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                                    if r() < 0.4:
                                        g[i] = 0
                                        nxt[chunk] = 1
                                        continue
                        moved = False
                        caia = aux[i] & 15               # cuánto viene cayendo
                        # el tono con el que se dibuja al llegar a la fila de
                        # abajo: para el agua son bandas (ver TONO_FILA)
                        eb = e * SH
                        if y < SH - 1:
                            j = i + W
                            b = g[j]
                            if b == 0:
                                g[j] = TONO_FILA[eb + y + 1]
                                g[i] = 0
                                # lleva la cuenta de cuánto viene cayendo:
                                # es la "velocidad" que después salpica
                                aux[j] = caia + 1 if caia < FALL_MAX else FALL_MAX
                                aux[i] = 0
                                upd[j] = 1
                                nxt[down_row + cx] = 1
                                moved = True
                            elif k == K_WATER and KND[b] == K_OIL and r() < 0.25:
                                g[j] = TONO_FILA[eb + y + 1]
                                g[i] = b
                                aux[j], aux[i] = caia, 0
                                upd[j] = 1
                                upd[i] = 1
                                nxt[down_row + cx] = 1
                                moved = True
                            else:
                                if k == K_WATER and KND[b] == K_OIL:
                                    # el aceite de abajo todavía tiene que subir:
                                    # sin esto, un frame sin suerte dormía el chunk
                                    # con el aceite atrapado en el fondo
                                    nxt[chunk] = 1
                                d = 1 if r() < 0.5 else -1
                                for dx in (d, -d):
                                    nx = x + dx
                                    if 0 <= nx < W and g[i + dx] == 0 and g[j + dx] == 0:
                                        g[j + dx] = TONO_FILA[eb + y + 1]
                                        g[i] = 0
                                        aux[j + dx], aux[i] = caia, 0
                                        upd[j + dx] = 1
                                        nxt[down_row + (nx >> CHB)] = 1
                                        moved = True
                                        break
                            if moved:
                                nxt[chunk] = 1
                        if not moved:
                            # tocó fondo: si venía cayendo, salpica
                            if caia >= SPLASH_MIN:
                                self.splash(x, y, caia)
                                aux[i] = 0
                                nxt[chunk] = 1
                                continue
                            # **nivelarse sin quedar revolviéndose.** las dos cosas
                            # a la vez, y de ahí la regla.
                            #
                            # un charco nivelado NO está quieto por sí solo: en su
                            # superficie cada gota se corre de lado, deja un hueco
                            # y otra lo llena, para siempre. medido: 600 celdas
                            # cambiando por frame en un estanque en reposo, media
                            # pantalla de chunks despiertos y 21 ms/frame que no
                            # bajaban nunca.
                            #
                            # frenar eso con un contador de frames («si no bajaste
                            # en diez, quedate quieta») apaga el revoltijo, pero
                            # deja el agua AMONTONADA: congela también a la gota
                            # que todavía tenía camino, y el charco queda con un
                            # domo encima, apilado como si fuera arena. se ve de
                            # lejos. tres parches sobre el contador dieron 8, 6 y
                            # 5 px de domo residual, siempre estable.
                            #
                            # lo que distingue los dos casos no es el tiempo, es la
                            # **presión**: se corre de lado la gota que tiene
                            # líquido ENCIMA (el peso de arriba la empuja hasta
                            # nivelar) o la que al correrse encuentra un vacío por
                            # donde bajar. la de la superficie de un charco plano
                            # no tiene ni una ni otra, y ésa era justo la que se
                            # revolvía: ahora no se mueve, y sin contadores.
                            #
                            # la búsqueda para en cuanto la celda de al lado está
                            # ocupada, así que en el interior de un charco no
                            # cuesta nada; y cuando ya nadie tiene aire al lado, el
                            # chunk se duerme y deja de pagarse.
                            presion = y > 0 and IS_LIQ[g[i - W]]
                            if k != K_OIL or r() < 0.5:
                                paso = SPREAD if k != K_OIL else SPREAD_OIL
                                d = 1 if r() < 0.5 else -1
                                for dd in (d, -d):
                                    nx = x
                                    bajada = False
                                    for _ in range(paso):
                                        cand = nx + dd
                                        if not (0 <= cand < W) or g[row + cand] != 0:
                                            break
                                        nx = cand
                                        if y < SH - 1 and g[row + W + nx] == 0:
                                            bajada = True
                                            break
                                    if nx != x and (presion or bajada):
                                        g[row + nx] = TONO_FILA[eb + y]
                                        g[i] = 0
                                        aux[row + nx] = 0
                                        aux[i] = 0
                                        upd[row + nx] = 1
                                        nxt[chunk] = 1
                                        nxt[crow + (nx >> CHB)] = 1
                                        break
                        continue

                    if k == K_FIRE:
                        life = aux[i]
                        nxt[chunk] = 1
                        if life <= 1:
                            if r() < 0.4:
                                g[i] = BASE[K_SMOKE] + int(r() * NVAR[K_SMOKE])
                                aux[i] = ri(20, 60)
                            else:
                                g[i] = 0
                                aux[i] = 0
                            continue
                        life -= 1
                        aux[i] = life
                        g[i] = fire_tone(life)
                        doused = False
                        for dx, dy in NB4:
                            nx, ny = x + dx, y + dy
                            if not (0 <= nx < W and 0 <= ny < SH):
                                continue
                            j2 = ny * W + nx
                            tk = KND[g[j2]]
                            # el agua templada del deshielo aún no lo apaga:
                            # así una llama sostenida gana terreno sobre el hielo
                            if tk == K_WATER and g[j2] != W_WARM:
                                g[i] = BASE[K_STEAM] + int(r() * NVAR[K_STEAM])
                                aux[i] = ri(40, 90)
                                doused = True
                                break
                            if tk == K_POWDER:
                                self.explode(nx, ny)
                            elif tk in FLAMMABLE and r() < FLAMMABLE[tk]:
                                lf = ri(60, 120) if tk == K_WOOD else ri(15, 40)
                                g[j2] = fire_tone(lf)
                                aux[j2] = lf
                                upd[j2] = 1
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        if doused:
                            continue
                        if y > 0 and r() < 0.5:
                            nx = x + int(r() * 3) - 1
                            if 0 <= nx < W:
                                j2 = i - W + (nx - x)
                                if g[j2] == 0:
                                    g[j2] = g[i]
                                    aux[j2] = aux[i]
                                    g[i] = 0
                                    aux[i] = 0
                                    upd[j2] = 1
                                    nxt[up_row + (nx >> CHB)] = 1
                        continue

                    if k == K_LAVA:
                        nxt[chunk] = 1
                        turned = False
                        for dx, dy in NB4:
                            nx, ny = x + dx, y + dy
                            if not (0 <= nx < W and 0 <= ny < SH):
                                continue
                            j2 = ny * W + nx
                            tk = KND[g[j2]]
                            # el agua templada del deshielo no la solidifica:
                            # así una colada de lava se abre paso por el hielo
                            if tk == K_WATER and g[j2] != W_WARM:
                                g[i] = BASE[K_STONE] + int(r() * NVAR[K_STONE])
                                g[j2] = BASE[K_STEAM] + int(r() * NVAR[K_STEAM])
                                aux[j2] = ri(40, 90)
                                upd[j2] = 1
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                                turned = True
                                break
                            if tk == K_POWDER:
                                self.explode(nx, ny)
                            elif tk in FLAMMABLE and r() < FLAMMABLE[tk] * 0.6:
                                lf = ri(20, 60)
                                g[j2] = fire_tone(lf)
                                aux[j2] = lf
                                upd[j2] = 1
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        if turned:
                            continue
                        if r() < LAVA_COOL and not self._junto_a(x, y, K_CLONE):
                            # se enfría: costra de piedra. la de la boca de un
                            # clonador no, o el volcán se tapa solo
                            g[i] = BASE[K_STONE] + int(r() * NVAR[K_STONE])
                            continue
                        if r() < 0.06:  # brasas: la lava respira
                            g[i] = L_BASE + int(r() * L_N)
                        if y > 0 and g[i - W] == 0 and r() < 0.015:
                            lf = ri(5, 15)
                            g[i - W] = fire_tone(lf)
                            aux[i - W] = lf
                            nxt[up_row + cx] = 1
                        if r() < 0.5:
                            e = g[i]
                            moved = False
                            if y < SH - 1:
                                j = i + W
                                if g[j] == 0:
                                    g[j] = e
                                    g[i] = 0
                                    upd[j] = 1
                                    nxt[down_row + cx] = 1
                                    moved = True
                                elif g[j] == W_WARM:  # se hunde por el deshielo
                                    g[j] = e
                                    g[i] = W_WARM
                                    upd[j] = 1
                                    upd[i] = 1
                                    nxt[down_row + cx] = 1
                                    moved = True
                                else:
                                    d = 1 if r() < 0.5 else -1
                                    for dx in (d, -d):
                                        nx = x + dx
                                        if 0 <= nx < W and g[i + dx] == 0 and g[j + dx] == 0:
                                            g[j + dx] = e
                                            g[i] = 0
                                            upd[j + dx] = 1
                                            nxt[down_row + (nx >> CHB)] = 1
                                            moved = True
                                            break
                            if not moved:
                                d = 1 if r() < 0.5 else -1
                                nx = x + d
                                if 0 <= nx < W and g[i + d] == 0:
                                    g[i + d] = e
                                    g[i] = 0
                                    upd[i + d] = 1
                                    nxt[crow + (nx >> CHB)] = 1
                        continue

                    if k == K_STEAM or k == K_SMOKE:
                        life = aux[i]
                        nxt[chunk] = 1
                        if life <= 1:
                            if k == K_STEAM and r() < 0.3:
                                g[i] = WA_BASE + int(r() * WA_N)
                            else:
                                g[i] = 0
                            aux[i] = 0
                            continue
                        aux[i] = life - 1
                        if y > 0:
                            j = i - W
                            if g[j] == 0 and r() < 0.8:
                                g[j] = e
                                aux[j] = aux[i]
                                g[i] = 0
                                aux[i] = 0
                                upd[j] = 1
                                nxt[up_row + cx] = 1
                                continue
                            d = 1 if r() < 0.5 else -1
                            moved = False
                            for dx in (d, -d):
                                nx = x + dx
                                if 0 <= nx < W and g[i + dx] == 0 and g[j + dx] == 0:
                                    g[j + dx] = e
                                    aux[j + dx] = aux[i]
                                    g[i] = 0
                                    aux[i] = 0
                                    upd[j + dx] = 1
                                    nxt[up_row + (nx >> CHB)] = 1
                                    moved = True
                                    break
                            if moved:
                                continue
                        if k == K_STEAM and r() < 0.02:
                            g[i] = WA_BASE + int(r() * WA_N)
                            aux[i] = 0
                            continue
                        d = 1 if r() < 0.5 else -1
                        nx = x + d
                        if 0 <= nx < W and g[i + d] == 0 and r() < 0.5:
                            g[i + d] = e
                            aux[i + d] = aux[i]
                            g[i] = 0
                            aux[i] = 0
                            upd[i + d] = 1
                            nxt[crow + (nx >> CHB)] = 1
                        continue

                    if k == K_PLANT:
                        dx, dy = NB4[int(r() * 4)]
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < SH:
                            j2 = ny * W + nx
                            if KND[g[j2]] == K_WATER:
                                # mientras tenga de dónde beber sigue despierta
                                nxt[chunk] = 1
                                if r() < 0.06:
                                    g[j2] = BASE[K_PLANT] + int(r() * NVAR[K_PLANT])
                                    upd[j2] = 1
                                    nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        continue

                    if k == K_ICE:
                        melt = False
                        for dx, dy in NB4:
                            nx, ny = x + dx, y + dy
                            if not (0 <= nx < W and 0 <= ny < SH):
                                continue
                            j2 = ny * W + nx
                            b = g[j2]
                            tk = KND[b]
                            if tk == K_FIRE or tk == K_LAVA:
                                melt = True
                                break
                            if tk == K_WATER and b != W_WARM:
                                nxt[chunk] = 1  # queda algo por congelar
                                if r() < 0.03:
                                    g[j2] = BASE[K_ICE] + int(r() * NVAR[K_ICE])
                                    upd[j2] = 1
                                    nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        if melt:
                            g[i] = W_WARM  # deshielo: no se recongela al toque
                            nxt[chunk] = 1
                        continue

                    if k == K_SEED:
                        st = aux[i]
                        if st == 0:  # todavía es una semilla suelta que cae
                            if y < SH - 1:
                                j = i + W
                                b = g[j]
                                if b == 0:
                                    g[j] = e
                                    g[i] = 0
                                    upd[j] = 1
                                    nxt[chunk] = 1
                                    nxt[down_row + cx] = 1
                                    continue
                                bk = KND[b]
                                if bk in SOIL:
                                    aux[i] = ri(26, 48)  # germina: altura a crecer
                                    nxt[chunk] = 1
                                    continue
                                if bk in LIQUIDS and r() < 0.4:
                                    g[j] = e
                                    g[i] = b
                                    upd[j] = 1
                                    upd[i] = 1
                                    nxt[chunk] = 1
                                    nxt[down_row + cx] = 1
                                    continue
                                d = 1 if r() < 0.5 else -1
                                for dx in (d, -d):
                                    nx = x + dx
                                    if 0 <= nx < W and g[i + dx] == 0 and g[j + dx] == 0:
                                        g[j + dx] = e
                                        g[i] = 0
                                        upd[j + dx] = 1
                                        nxt[chunk] = 1
                                        nxt[down_row + (nx >> CHB)] = 1
                                        break
                            continue
                        # brote activo: sube dejando tronco y se ramifica
                        nxt[chunk] = 1
                        up = i - W
                        if st > 1 and y > 0 and (g[up] == 0 or KND[g[up]] == K_LEAF):
                            g[i] = BASE[K_TRUNK] + int(r() * NVAR[K_TRUNK])
                            aux[i] = 0
                            if st > 26:  # el tronco nace grueso y se afina
                                td = 1 if r() < 0.5 else -1
                                if 0 <= x + td < W and g[i + td] == 0:
                                    g[i + td] = BASE[K_TRUNK] + int(r() * NVAR[K_TRUNK])
                                    nxt[crow + ((x + td) >> CHB)] = 1
                            g[up] = e
                            aux[up] = st - 1
                            upd[up] = 1
                            nxt[up_row + cx] = 1
                            if st > 9 and r() < 0.11:  # rama lateral
                                bd = 1 if r() < 0.5 else -1
                                bx = x + bd
                                if 0 <= bx < W and g[up + bd] == 0:
                                    g[up + bd] = BASE[K_SEED] + int(r() * NVAR[K_SEED])
                                    aux[up + bd] = st // 2
                                    upd[up + bd] = 1
                                    nxt[up_row + (bx >> CHB)] = 1
                            if st < 18 and r() < 0.35:  # follaje al costado
                                ld = 1 if r() < 0.5 else -1
                                if 0 <= x + ld < W and g[i + ld] == 0:
                                    g[i + ld] = BASE[K_LEAF] + int(r() * NVAR[K_LEAF])
                                    nxt[crow + ((x + ld) >> CHB)] = 1
                        else:  # topó o se quedó sin savia: copa
                            g[i] = BASE[K_LEAF] + int(r() * NVAR[K_LEAF])
                            aux[i] = 0
                            for dy in range(-4, 5):
                                ny = y + dy
                                if not 0 <= ny < SH:
                                    continue
                                for dx in range(-4, 5):
                                    if dx * dx + dy * dy > 17:
                                        continue
                                    nx = x + dx
                                    if 0 <= nx < W and g[ny * W + nx] == 0 and r() < 0.6:
                                        g[ny * W + nx] = (BASE[K_LEAF] +
                                                          int(r() * NVAR[K_LEAF]))
                                        nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        continue

                    if k == K_GAS:
                        nxt[chunk] = 1
                        ign = False
                        for dx, dy in NB4:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < W and 0 <= ny < SH and KND[g[ny * W + nx]] in HOT:
                                ign = True
                                break
                        if ign:  # deflagra: cada celda prende a la siguiente
                            lf = ri(22, 46)
                            g[i] = fire_tone(lf)
                            aux[i] = lf
                            continue
                        if y > 0:
                            j = i - W
                            if g[j] == 0:
                                g[j] = e
                                g[i] = 0
                                upd[j] = 1
                                nxt[up_row + cx] = 1
                                continue
                        d = 1 if r() < 0.5 else -1
                        for dx in (d, -d):
                            nx = x + dx
                            if 0 <= nx < W and g[i + dx] == 0 and r() < 0.6:
                                g[i + dx] = e
                                g[i] = 0
                                upd[i + dx] = 1
                                nxt[crow + (nx >> CHB)] = 1
                                break
                        continue

                    if k == K_SPARK:
                        life = aux[i]
                        nxt[chunk] = 1
                        if life <= 1:  # se descarga: el cable queda enfriando
                            g[i] = BASE[K_MCOOL] + int(r() * NVAR[K_MCOOL])
                            aux[i] = MCOOL_TIME
                            continue
                        life -= 1
                        aux[i] = life
                        g[i] = SP_BASE + min(SP_N - 1, SPARK_LIFE - life)
                        for dx, dy in NB8:
                            nx, ny = x + dx, y + dy
                            if not (0 <= nx < W and 0 <= ny < SH):
                                continue
                            j2 = ny * W + nx
                            tk = KND[g[j2]]
                            if tk == K_METAL:  # el pulso no pierde fuerza
                                g[j2] = SP_BASE
                                aux[j2] = SPARK_LIFE
                                upd[j2] = 1
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                            elif tk == K_POWDER:
                                self.explode(nx, ny)
                            elif tk == K_GAS or (tk in FLAMMABLE and r() < 0.5):
                                lf = ri(20, 45)
                                g[j2] = fire_tone(lf)
                                aux[j2] = lf
                                upd[j2] = 1
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        continue

                    if k == K_MCOOL:
                        a = aux[i]
                        nxt[chunk] = 1
                        if a <= 1:
                            g[i] = BASE[K_METAL] + int(r() * NVAR[K_METAL])
                            aux[i] = 0
                        else:
                            aux[i] = a - 1
                        continue

                    if k == K_EMBER:
                        # chispa de fuego artificial: cae despacio, titila y se apaga
                        life = aux[i]
                        nxt[chunk] = 1
                        if life <= 1:
                            g[i] = 0
                            aux[i] = 0
                            continue
                        life -= 1
                        aux[i] = life
                        c4 = EM_BASE + ((e - EM_BASE) & ~3)
                        if r() < 0.12:
                            e = c4                       # destello
                        else:
                            e = c4 + (0 if life > 40 else 1 if life > 24
                                      else 2 if life > 10 else 3)
                        g[i] = e
                        if y < SH - 1 and r() < 0.3:
                            dx = int(r() * 3) - 1
                            nx = x + dx
                            j = i + W + dx
                            if 0 <= nx < W and g[j] == 0:
                                g[j] = e
                                aux[j] = life
                                g[i] = 0
                                aux[i] = 0
                                upd[j] = 1
                                nxt[down_row + (nx >> CHB)] = 1
                        continue

                    if k == K_ROCKET:
                        # sube dejando una estela de fuego; sin mecha o contra
                        # algo, revienta
                        life = aux[i]
                        nxt[chunk] = 1
                        if life <= 1 or y < 16:      # que el anillo entre en pantalla
                            self._reventar(x, y, e - RK_BASE)
                            continue
                        nx = x + (int(r() * 3) - 1 if r() < 0.2 else 0)
                        j2 = i - W + (nx - x)
                        if 0 <= nx < W and (g[j2] == 0 or ROCKET_PASS[g[j2]]):
                            # lo liviano (otros cohetes de la pila, humo, chispas)
                            # no lo frena: baja a ocupar su lugar. si no, un
                            # cohete del fondo de la pila reventaba en el suelo
                            b = g[j2]
                            g[j2] = e
                            aux[j2] = life - 1
                            upd[j2] = 1
                            if b and KND[b] == K_FWORK:
                                g[i] = b
                                aux[i] = 0
                            else:
                                g[i] = fire_tone(4)
                                aux[i] = ri(3, 7)
                            nxt[up_row + (nx >> CHB)] = 1
                        elif 0 <= nx < W and KND[g[j2]] == K_ROCKET:
                            aux[i] = life - 1          # otro cohete adelante: espera
                        else:
                            self._reventar(x, y, e - RK_BASE)
                        continue

                    if k == K_SNOW:
                        # se derrite con calor al lado; cae lenta, se apila
                        dx, dy = NB4[int(r() * 4)]
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < SH and KND[g[ny * W + nx]] in HOT:
                            g[i] = W_WARM
                            aux[i] = 0
                            nxt[chunk] = 1
                            continue
                        if y < SH - 1:
                            j = i + W
                            b = g[j]
                            if b == 0:
                                nxt[chunk] = 1           # aunque no caiga en este frame
                                if r() < 0.55:
                                    g[j] = e
                                    g[i] = 0
                                    upd[j] = 1
                                    nxt[down_row + cx] = 1
                                continue
                            if KND[b] == K_WATER:        # en el agua se deshace
                                nxt[chunk] = 1
                                if r() < 0.04:
                                    g[i] = WA_BASE + int(r() * WA_N)
                                continue
                            d = 1 if r() < 0.5 else -1
                            for dx in (d, -d):
                                nx = x + dx
                                if 0 <= nx < W and g[i + dx] == 0 and g[j + dx] == 0:
                                    nxt[chunk] = 1
                                    if r() < 0.5:
                                        g[j + dx] = e
                                        g[i] = 0
                                        upd[j + dx] = 1
                                        nxt[down_row + (nx >> CHB)] = 1
                                    break
                        continue

                    if k == K_VIRUS:
                        # moho que se come lo que toca y después se muere
                        life = aux[i]
                        nxt[chunk] = 1
                        if life <= 1:
                            if r() < 0.4:
                                g[i] = SM_BASE + int(r() * SM_N)
                                aux[i] = ri(10, 30)
                            else:
                                g[i] = 0
                                aux[i] = 0
                            continue
                        aux[i] = life - 1
                        if r() < 0.2:
                            g[i] = VI_BASE + int(r() * VI_N)
                        dx, dy = NB4[int(r() * 4)]
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < SH:
                            j2 = ny * W + nx
                            b = g[j2]
                            if b:
                                tk = KND[b]
                                if tk == K_FIRE or tk == K_LAVA or tk == K_PLASMA:
                                    lf = ri(10, 25)          # el fuego lo quema
                                    g[i] = fire_tone(lf)
                                    aux[i] = lf
                                elif tk not in VIRUS_PROOF and r() < 0.5:
                                    g[j2] = VI_BASE + int(r() * VI_N)
                                    aux[j2] = ri(VIRUS_LIFE[0], VIRUS_LIFE[1])
                                    upd[j2] = 1
                                    nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        continue

                    if k == K_BHOLE:
                        # el núcleo no hace nada: sólo el borde (la celda que
                        # tiene algo que no es agujero al lado) brilla y tira.
                        # de cerca tira por un rayo hacia afuera, de a dos pasos
                        # por frame (le gana a la gravedad: si no, la arena se
                        # suelta y pasa de largo); de lejos elige celdas al azar
                        # y las acerca torcidas, así lo que cae entra girando.
                        nxt[chunk] = 1
                        ux = uy = 0
                        for dx, dy in NB8:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < W and 0 <= ny < SH and \
                                    KND[g[ny * W + nx]] != K_BHOLE:
                                ux += dx
                                uy += dy
                        if ux == 0 and uy == 0:
                            g[i] = BH_BASE
                            continue
                        g[i] = BH_BASE + 1 + int(r() * (BH_N - 1))
                        ux = 1 if ux > 0 else -1 if ux < 0 else 0
                        uy = 1 if uy > 0 else -1 if uy < 0 else 0
                        for d in range(1, BH_RAY):
                            sx, sy = x + ux * d, y + uy * d
                            if not (0 <= sx < W and 0 <= sy < SH):
                                break
                            js = sy * W + sx
                            b = g[js]
                            if not b:
                                continue
                            if KND[b] in BH_PROOF:
                                break
                            if d <= 2:
                                g[js] = 0                # se lo tragó
                                aux[js] = 0
                                nxt[(sy >> CHB) * CW + (sx >> CHB)] = 1
                                continue
                            tx, ty = sx - ux * 2, sy - uy * 2
                            jt = ty * W + tx
                            if g[jt] == 0:
                                g[jt] = b
                                aux[jt] = aux[js]
                                g[js] = 0
                                aux[js] = 0
                                upd[jt] = 1
                                nxt[(ty >> CHB) * CW + (tx >> CHB)] = 1
                                nxt[(sy >> CHB) * CW + (sx >> CHB)] = 1
                        for _ in range(4):
                            q = r()
                            rad = 4 + q * BH_R
                            ang = r() * 6.2832
                            ox = int(math.cos(ang) * rad)
                            oy = int(math.sin(ang) * rad)
                            sx, sy = x + ox, y + oy
                            if not (0 <= sx < W and 0 <= sy < SH):
                                continue
                            js = sy * W + sx
                            b = g[js]
                            if not b or KND[b] in BH_PROOF:
                                continue
                            for _ in range(5):
                                # hacia el centro, con un cuarto de giro
                                stx = -ox - oy * 0.6
                                sty = -oy + ox * 0.6
                                tx = sx + (1 if stx > 0.5 else -1 if stx < -0.5 else 0)
                                ty = sy + (1 if sty > 0.5 else -1 if sty < -0.5 else 0)
                                if not (0 <= tx < W and 0 <= ty < SH):
                                    break
                                jt = ty * W + tx
                                bt = g[jt]
                                if bt == 0:
                                    g[jt] = b
                                    aux[jt] = aux[js]
                                    g[js] = 0
                                    aux[js] = 0
                                    upd[jt] = 1
                                    nxt[(ty >> CHB) * CW + (tx >> CHB)] = 1
                                    nxt[(sy >> CHB) * CW + (sx >> CHB)] = 1
                                    sx, sy, js = tx, ty, jt
                                    ox, oy = sx - x, sy - y
                                elif KND[bt] == K_BHOLE:
                                    g[js] = 0            # se lo tragó
                                    aux[js] = 0
                                    nxt[(sy >> CHB) * CW + (sx >> CHB)] = 1
                                    break
                                else:
                                    break
                        continue

                    if k == K_CLONE:
                        st = aux[i]
                        if st == 0:
                            # vacío: se carga con lo primero que lo toque
                            for dx, dy in NB4:
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < W and 0 <= ny < SH:
                                    b = g[ny * W + nx]
                                    if CLONABLE[b]:
                                        aux[i] = KND[b]
                                        g[i] = CL_BASE + 1
                                        nxt[chunk] = 1
                                        break
                            continue
                        nxt[chunk] = 1
                        if r() < 0.1:
                            g[i] = CL_BASE + 1 + int(r() * 2)
                        if r() < CLONE_RATE.get(st, CLONE_P):
                            # el primer vecino libre, empezando por uno al azar
                            o = int(r() * 4)
                            for n4 in range(4):
                                dx, dy = NB4[(o + n4) & 3]
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < W and 0 <= ny < SH:
                                    j2 = ny * W + nx
                                    if g[j2] == 0:
                                        self.put(j2, st, ri(20, 60) if st in VIDA else 0)
                                        upd[j2] = 1
                                        nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                                        break
                        continue

                    if k == K_PLASMA:
                        # el rayo: dura unos frames y le pega a todo lo que toca
                        life = aux[i]
                        nxt[chunk] = 1
                        if life <= 1:
                            g[i] = 0
                            aux[i] = 0
                            continue
                        life -= 1
                        aux[i] = life
                        g[i] = PL_BASE + min(PL_N - 1, (PLASMA_LIFE - life) >> 1)
                        for dx, dy in NB4:
                            nx, ny = x + dx, y + dy
                            if not (0 <= nx < W and 0 <= ny < SH):
                                continue
                            j2 = ny * W + nx
                            tk = KND[g[j2]]
                            if tk == K_METAL:
                                g[j2] = SP_BASE
                                aux[j2] = SPARK_LIFE
                                upd[j2] = 1
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                            elif tk == K_POWDER:
                                self.explode(nx, ny)
                            elif tk == K_GAS or (tk in FLAMMABLE and r() < 0.3):
                                lf = ri(20, 45)
                                g[j2] = fire_tone(lf)
                                aux[j2] = lf
                                upd[j2] = 1
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                            elif tk == K_WATER and r() < 0.03:
                                g[j2] = BASE[K_STEAM] + int(r() * NVAR[K_STEAM])
                                aux[j2] = ri(30, 60)
                                nxt[(ny >> CHB) * CW + (nx >> CHB)] = 1
                        continue

        # un chunk con actividad despierta también a sus vecinos: cubre a la
        # partícula que cruza una frontera y a la que espera que se libere la
        # celda de al lado, en un chunk que si no seguiría dormido
        active[:] = self._zc
        for c in range(NCHUNK):
            if nxt[c]:
                cy, cx = divmod(c, CW)
                for oy in (-1, 0, 1):
                    ny = cy + oy
                    if 0 <= ny < CH_ROWS:
                        nb = ny * CW
                        for ox in (-1, 0, 1):
                            nx = cx + ox
                            if 0 <= nx < CW:
                                active[nb + nx] = 1
        self.awake = sum(active)

    def _junto_a(self, x, y, kind):
        """¿hay `kind` en alguna de las 8 celdas vecinas?"""
        g = self.g
        for dx, dy in NB8:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < SH and KIND[g[ny * W + nx]] == kind:
                return True
        return False

    def splash(self, x, y, fuerza):
        """la gota que llega con impulso se abre: gotas al costado y para arriba.

        no crea agua nueva — mueve la que ya está. busca huecos en el arco de
        arriba y le pasa la celda, así una catarata levanta espuma en el borde
        en vez de apilarse en una columna muda.
        """
        g, aux = self.g, self.aux
        r = random.random
        n = 1 + (fuerza >= FALL_MAX // 2) + (fuerza >= FALL_MAX - 2)
        i = y * W + x
        for _ in range(n):
            if g[i] == 0:                     # ya se fue: no hay qué salpicar
                return
            dx = (1 if r() < 0.5 else -1) * (1 + int(r() * 2))
            dy = -1 if r() < 0.75 else 0
            nx, ny = x + dx, y + dy
            if not (0 <= nx < W and 0 <= ny < SH):
                continue
            j = ny * W + nx
            if g[j] == 0:
                g[j] = g[i]
                aux[j] = 0
                g[i] = 0
                aux[i] = 0
                self.upd[j] = 1
                self.wake(nx, ny)
                self.wake(x, y)
                return

    def explode(self, x, y):
        g, aux = self.g, self.aux
        r = random.random
        ri = random.randint
        rad = 9
        for dy in range(-rad, rad + 1):
            ny = y + dy
            if not 0 <= ny < SH:
                continue
            for dx in range(-rad, rad + 1):
                if dx * dx + dy * dy > rad * rad:
                    continue
                nx = x + dx
                if not 0 <= nx < W:
                    continue
                j = ny * W + nx
                kk = KIND[g[j]]
                if kk == K_WALL or kk == K_CLONE or kk == K_BHOLE or kk == K_ROCK:
                    continue
                if kk == K_FWORK:              # la onda lanza los cohetes vecinos
                    g[j] = RK_BASE + int(r() * NFW)
                    aux[j] = ri(30, 80)
                    self.wake(nx, ny)
                    continue
                if kk == K_ROCKET:
                    continue
                if r() < 0.82:
                    lf = ri(6, 30)
                    g[j] = fire_tone(lf)
                    aux[j] = lf
                else:
                    g[j] = BASE[K_SMOKE] + int(r() * NVAR[K_SMOKE])
                    aux[j] = ri(15, 50)
                self.upd[j] = 1
                self.wake(nx, ny)

    # --- fuegos artificiales y rayos ---

    def _reventar(self, x, y, color):
        """el cohete llegó arriba: se abre en un anillo que crece."""
        self.g[y * W + x] = 0
        self.aux[y * W + x] = 0
        self.bursts.append([x, y, 1.0, random.randint(9, 15), color % NFW])
        self.wake(x, y)

    def _abrir_fuegos(self):
        """cada frame, los fuegos en curso pintan un anillo un poco más grande:
        así se ve la explosión abrirse, y las chispas que quedan caen solas."""
        g, aux = self.g, self.aux
        r = random.random
        ri = random.randint
        vivos = []
        for b in self.bursts:
            x, y, rad, rmax, c = b
            base = EM_BASE + c * 4
            n = int(6 + rad * 2.4)
            a0 = r() * 6.2832
            for k in range(n):
                a = a0 + k * 6.2832 / n
                px = int(x + math.cos(a) * rad)
                py = int(y + math.sin(a) * rad * 0.9)
                if 0 <= px < W and 0 <= py < SH:
                    j = py * W + px
                    kk = KIND[g[j]]
                    if kk == K_EMPTY or kk == K_SMOKE or kk == K_EMBER:
                        g[j] = base
                        aux[j] = ri(28, 64)
                        self.wake(px, py)
            b[2] = rad + 1.4
            if b[2] <= rmax:
                vivos.append(b)
        self.bursts = vivos

    def bolt(self, tx, ty):
        """un rayo: cae del cielo en zigzag hasta (tx, ty), o hasta lo primero
        que encuentre en el camino, y ahí descarga. energiza el metal, prende
        lo que arde, revienta la pólvora y lanza los cohetes."""
        g = self.g
        r = random.random
        tx = max(0, min(W - 1, tx))
        ty = max(0, min(SH - 1, ty))
        x = max(0, min(W - 1, tx + random.randint(-28, 28)))
        camino = []
        golpe = (tx, ty)
        libre = (K_EMPTY, K_SMOKE, K_STEAM, K_GAS, K_PLASMA, K_EMBER, K_FIRE)
        for y in range(0, ty + 1):
            falta = ty - y + 1
            x0 = x
            if r() < 0.7:
                x += (1 if tx > x else -1 if tx < x else 0) * (1 + (abs(tx - x) > falta))
            else:
                x += int(r() * 3) - 1
            x = max(0, min(W - 1, x))
            k = KIND[g[y * W + x]]
            if k not in libre:
                golpe = (x, y)
                break
            if abs(x - x0) > 1:                # sin agujeros en el trazo
                camino.append(((x + x0) // 2, y))
            camino.append((x, y))
            if x + 1 < W and KIND[g[y * W + x + 1]] in libre:
                camino.append((x + 1, y))      # de dos de grueso: que se vea
        # ramitas que se abren hacia abajo
        ramas = []
        for (x, y) in camino[::9]:
            if r() < 0.5:
                d = 1 if r() < 0.5 else -1
                bx = x
                for by in range(y, min(SH, y + 4 + int(r() * 10))):
                    bx += d if r() < 0.6 else 0
                    if 0 <= bx < W:
                        ramas.append((bx, by))
        for (x, y) in camino + ramas:
            j = y * W + x
            k = KIND[g[j]]
            if k == K_EMPTY or k == K_SMOKE or k == K_STEAM:
                g[j] = PL_BASE
                self.aux[j] = PLASMA_LIFE + int(r() * 3)
                self.wake(x, y)
            elif k == K_GAS:
                self.put(j, K_FIRE, 30)
                self.wake(x, y)
        # la descarga: plasma alrededor del punto donde pegó
        gx, gy = golpe
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < W and 0 <= ny < SH and dx * dx + dy * dy <= 5:
                    j = ny * W + nx
                    k = KIND[g[j]]
                    if k == K_EMPTY or k == K_SMOKE or k == K_STEAM:
                        g[j] = PL_BASE
                        self.aux[j] = PLASMA_LIFE
                    elif k == K_METAL:
                        g[j] = SP_BASE
                        self.aux[j] = SPARK_LIFE
                    elif k == K_POWDER:
                        self.explode(nx, ny)
                    elif k in FLAMMABLE:
                        self.put(j, K_FIRE, random.randint(20, 50))
                    self.wake(nx, ny)
        self.flash = 3
        return golpe

    def put(self, j, kind, life=0):
        if kind == K_EMPTY:
            self.g[j] = 0
            self.aux[j] = 0
        elif kind == K_FIRE:
            self.g[j] = fire_tone(life)
            self.aux[j] = life
        elif kind == K_WATER:
            # el agua toma el tono de su fila (bandas horizontales), y nunca el
            # tono "templada": ése lo pone sólo el hielo al derretirse, y el
            # pincel lo pintaba por azar — un charco que el hielo no congelaba
            self.g[j] = TONO_FILA[WA_BASE * SH + j // W]
            self.aux[j] = life
        else:
            self.g[j] = BASE[kind] + int(random.random() * NVAR[kind])
            self.aux[j] = life

    def paint(self, cx, cy, kind, rad):
        """un sello redondo del pincel en (cx, cy).

        va por filas (el ancho de cada fila sale de la raíz, no se prueba el
        círculo celda por celda) y despierta los chunks del recuadro una sola
        vez al final: con el pincel de 16 eran 1.000 llamadas a wake por sello.
        """
        g, aux = self.g, self.aux
        r = random.random
        ri = random.randint
        r2 = rad * rad
        solid = kind in (K_WALL, K_WOOD, K_PLANT, K_METAL, K_ICE, K_CLONE, K_BHOLE)
        # lo común (arena, muro, lava...) va por el camino corto
        simple = kind not in (K_EMPTY, K_VIRUS, K_SPARK, K_FIRE, K_WATER)
        base = BASE.get(kind, 0)
        nv = NVAR.get(kind, 1)
        for dy in range(-rad, rad + 1):
            ny = cy + dy
            if not 0 <= ny < SH:
                continue
            hw = int((r2 - dy * dy) ** 0.5)
            x0 = cx - hw if cx - hw > 0 else 0
            x1 = cx + hw if cx + hw < W - 1 else W - 1
            if x1 < x0:
                continue
            row = ny * W
            if kind == K_EMPTY:
                n = x1 - x0 + 1
                g[row + x0:row + x1 + 1] = bytes(n)
                aux[row + x0:row + x1 + 1] = bytes(n)
                continue
            if simple:
                for j in range(row + x0, row + x1 + 1):
                    if REPL[g[j]] and (solid or r() < 0.55):
                        g[j] = base + int(r() * nv)
                        aux[j] = 0
                continue
            for nx in range(x0, x1 + 1):
                j = row + nx
                cur = KIND[g[j]]
                if kind == K_VIRUS:
                    # el pincel de virus contagia lo que hay debajo; en el aire
                    # deja apenas unas esporas
                    if cur != K_EMPTY and cur not in VIRUS_PROOF:
                        if r() < 0.35:
                            self.put(j, K_VIRUS, ri(*VIRUS_LIFE))
                    elif cur == K_EMPTY and r() < 0.12:
                        self.put(j, K_VIRUS, ri(*VIRUS_LIFE))
                elif kind == K_SPARK:
                    # la chispa no se pinta al aire: energiza el cable
                    if cur == K_METAL:
                        g[j] = SP_BASE
                        aux[j] = SPARK_LIFE
                elif kind == K_FIRE:
                    if cur == K_POWDER:
                        self.explode(nx, ny)
                    elif cur in FLAMMABLE:
                        self.put(j, K_FIRE, ri(20, 60))
                    elif cur == K_ICE or cur == K_SNOW:  # el pincel de fuego hace de soplete
                        g[j] = W_WARM
                        aux[j] = 0
                    elif cur == K_EMPTY and r() < 0.35:
                        self.put(j, K_FIRE, ri(15, 40))
                elif REPL[g[j]] and r() < 0.55:          # agua
                    self.put(j, kind)
        cy0 = max(0, cy - rad) >> CHB
        cy1 = min(SH - 1, cy + rad) >> CHB
        cx0 = max(0, cx - rad) >> CHB
        cx1 = min(W - 1, cx + rad) >> CHB
        for c_y in range(cy0, cy1 + 1):
            for c_x in range(cx0, cx1 + 1):
                c = c_y * CW + c_x
                self.active[c] = 1
                self.nxt[c] = 1

    # --- escena de arranque ---

    def _blob(self, cx, cy, rad, kind, force=False):
        for dy in range(-rad, rad + 1):
            ny = cy + dy
            if not 0 <= ny < SH:
                continue
            for dx in range(-rad, rad + 1):
                if dx * dx + dy * dy > rad * rad:
                    continue
                nx = cx + dx
                if not 0 <= nx < W:
                    continue
                j = ny * W + nx
                if force or self.g[j] == 0:
                    self.put(j, kind)

    def _bar(self, x0, y0, x1, y1, kind, th=3):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for s in range(steps + 1):
            x = x0 + (x1 - x0) * s // steps
            y = y0 + (y1 - y0) * s // steps
            for dy in range(th):
                for dx in range(th):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < W and 0 <= ny < SH:
                        self.put(ny * W + nx, kind)

    def _clone(self, x0, x1, y, kind):
        """una barra de clonador ya cargada con `kind`."""
        for x in range(x0, x1 + 1):
            j = y * W + x
            self.g[j] = CL_BASE + 1
            self.aux[j] = kind

    def _top(self, x, kind=K_STONE):
        """la primera fila (de arriba) con `kind` en la columna x, o SH."""
        for y in range(SH):
            if KIND[self.g[y * W + x]] == kind:
                return y
        return SH

    def demo(self, n=0):
        """arma la escena n (ver ESCENAS) y despierta todo."""
        self.clear()
        (self._isla, self._volcan, self._fuegos, self._agujero)[n % len(ESCENAS)]()
        self.active[:] = b"\x01" * NCHUNK

    def _isla(self):
        # océano
        for y in range(SH - 34, SH):
            for x in range(W):
                self.put(y * W + x, K_WATER)
        # isla con una semilla lista para hacerse árbol
        self._blob(112, SH - 1, 36, K_STONE, force=True)
        self.put((SH - 39) * W + 112, K_SEED)
        # témpano en un rincón: se va comiendo el mar de a poco
        self._blob(22, SH - 26, 7, K_ICE, force=True)
        # mancha de aceite
        self._blob(62, SH - 38, 7, K_OIL, force=True)
        # caldero de lava con gotera
        self._bar(12, 40, 12, 66, K_WALL)
        self._bar(52, 40, 52, 66, K_WALL)
        self._bar(12, 64, 52, 64, K_WALL)
        for y in range(48, 64):
            for x in range(16, 52):
                self.put(y * W + x, K_LAVA)
        for y in range(64, 68):
            for x in range(31, 34):
                self.put(y * W + x, K_EMPTY)
        # repisa diagonal que recibe la gotera
        self._bar(8, 116, 92, 146, K_WALL)
        # meteorito de arena cayendo al océano
        self._blob(150, 36, 12, K_SAND)
        # circuito: cable de metal desde un pulsador hasta la carga de pólvora.
        # dale chispa (o un rayo) al extremo izquierdo
        self._bar(140, 92, 206, 92, K_METAL, th=2)
        self._bar(206, 92, 206, 128, K_METAL, th=2)
        self._bar(134, 144, 214, 144, K_WOOD)
        self._blob(206, 136, 8, K_POWDER)
        # y una batería de cohetes en la punta de la repisa, para el rayo
        for x in range(146, 168, 7):
            self._blob(x, 140, 2, K_FWORK)

    def _volcan(self):
        """un volcán en una isla: la cumbre tiene un clonador cargado de lava,
        así que la erupción no para. la colada baja por las laderas, quema el
        bosque, derrite la nieve y al llegar al mar hace piedra y vapor. la
        lava quieta se enfría sola, así que el volcán va creciendo."""
        cx, pico = 112, SH - 138
        for y in range(SH - 24, SH):
            for x in range(W):
                self.put(y * W + x, K_WATER)
        for y in range(pico, SH):
            hw = int((y - pico) * 0.6) + 5
            for x in range(cx - hw, cx + hw + 1):
                if 0 <= x < W:
                    self.put(y * W + x, K_ROCK)
        # nieve en las laderas altas
        for x in range(cx - 26, cx + 27):
            y = self._top(x, K_ROCK)
            if abs(x - cx) > 7:
                for dy in (1, 2, 3):
                    if y - dy >= 0:
                        self.put((y - dy) * W + x, K_SNOW)
        # la boca: un clonador de lava en la cumbre, con aire alrededor
        self._clone(cx - 4, cx + 4, pico, K_LAVA)
        self._clone(cx - 2, cx + 2, pico - 1, K_LAVA)
        # bosque en la ladera baja
        for x in (44, 60, 76, 148, 164, 180):
            y = self._top(x, K_ROCK)
            if 0 < y < SH:
                self.put((y - 1) * W + x, K_SEED)

    def _fuegos(self):
        """noche de fuegos artificiales: una mecha de planta corre por un
        canal bajo el suelo y va lanzando las baterías una por una. a la
        izquierda, un clonador de cohetes los deja caer en un brasero: el show
        no se termina."""
        for y in range(SH - 5, SH):
            for x in range(W):
                self.put(y * W + x, K_WALL)
        # la mecha corre tapada (si no, la llama se escapa hacia arriba y se
        # apaga): planta en el canal, techo de muro con un hueco en cada batería
        self._bar(14, SH - 6, 214, SH - 6, K_PLANT, th=1)
        self._bar(14, SH - 7, 214, SH - 7, K_WALL, th=1)
        xs = list(range(46, 214, 32))
        for x in xs:
            for d in (-1, 0, 1):
                self.put((SH - 7) * W + x + d, K_EMPTY)
        for x in xs:
            self._blob(x, SH - 10, 3, K_FWORK)
        # la lava que la enciende, en una copa a la izquierda
        self._bar(2, SH - 15, 2, SH - 6, K_WALL, th=2)
        self._bar(14, SH - 15, 14, SH - 8, K_WALL, th=2)
        for y in range(SH - 11, SH - 5):
            for x in range(4, 14):
                self.put(y * W + x, K_LAVA)
        # el lanzador eterno: un brasero (clonador de fuego: la lava se enfría,
        # el fuego clonado no) con un clonador de cohetes metido en la pared,
        # que sólo puede escupir hacia adentro
        by = 150
        self._bar(28, by, 48, by, K_WALL, th=2)
        self._bar(28, by - 16, 28, by + 1, K_WALL, th=2)
        self._bar(47, by - 8, 47, by + 1, K_WALL, th=2)
        self._clone(30, 46, by - 1, K_FIRE)
        self._clone(29, 29, by - 12, K_FWORK)
        # unas estrellas fijas en el cielo (metal: brillan si les cae un rayo)
        for k in range(16):
            x, y = (k * 67 + 23) % W, (k * 41 + 9) % 110 + 4
            if x > 70:
                self.put(y * W + x, K_METAL)

    def _agujero(self):
        """un agujero negro y tres chorros que caen: arena, agua y lava. lo
        que pasa cerca entra girando y desaparece."""
        cx, cy = 112, SH - 120
        self._blob(cx, cy, 9, K_BHOLE, force=True)
        self._clone(94, 98, 2, K_SAND)
        self._clone(126, 130, 2, K_WATER)
        self._clone(111, 113, 2, K_LAVA)
        for x in range(W):
            self.put((SH - 1) * W + x, K_WALL)
        # unos planetas de muro, que no se los traga
        for (px, py, rr) in ((40, 70, 7), (180, 56, 9), (176, 200, 5), (52, 214, 4)):
            self._blob(px, py, rr, K_WALL, force=True)


ESCENAS = ("isla", "volcán", "fuegos", "agujero negro")


# --- la piel: de la grilla al cuadro ------------------------------------------
# la grilla se sigue copiando de un saque al framebuffer, pero antes pasa por un
# compositor que trabaja con la mesa entera como **un solo entero de Python**
# (un byte por celda). desplazar ese entero 8 bits es correr la mesa una celda;
# 8·W bits, una fila. con AND/OR/XOR de enteros gigantes —que Python hace en C,
# a ~10 µs por operación sobre 62.000 celdas— salen gratis cosas que celda por
# celda costarían un frame entero:
#
# - el borde de arriba de cada material (el que da al aire) un tono más claro:
#   los montones tienen volumen,
# - el cielo con degradé y estrellas detrás de lo vacío,
# - el resplandor del fuego, la lava y los cohetes sobre el aire, y uno frío
#   alrededor del rayo y del cable con corriente,
# - destellos que titilan en la superficie del agua.
N_CELLS = W * SH


def _rep(c, n=N_CELLS):
    return int.from_bytes(bytes([c]) * n, "little")


_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


class Piel:
    def __init__(self):
        n = N_CELLS
        self.n = n
        self.all = (1 << (8 * n)) - 1
        self.row = 8 * W
        self.g1, self.g2 = _rep(GLOW1), _rep(GLOW2)
        self.c1, self.c2 = _rep(COLD1), _rep(COLD2)
        self.spk = _rep(SPARKLE)
        fila_a = bytes([0xFF, 0]) * (W // 2)
        fila_b = bytes([0, 0xFF]) * (W // 2)
        self.chk = int.from_bytes((fila_a + fila_b) * (SH // 2) + fila_a * (SH % 2), "little")
        # destellos: una celda de cada 29, en un dibujo que cambia de fase
        base = bytes(0xFF if i == 0 else 0 for i in range(29)) * (W // 29 + 3)
        self.brillos = []
        for fase in range(4):
            rows = []
            for y in range(SH):
                o = (y * 13 + fase * 7) % 29
                rows.append(base[o:o + W])
            self.brillos.append(int.from_bytes(b"".join(rows), "little"))
        self.cielos = {}
        self.r01 = _rep(1)
        self.r08 = _rep(8)
        self._glow = None

    def cielo(self, escena):
        """el fondo de una escena: degradé tramado y estrellas fijas."""
        hit = self.cielos.get(escena)
        if hit is not None:
            return hit
        rnd = random.Random(77 + escena)
        nsky = len(SKY)
        buf = bytearray(N_CELLS)
        for y in range(SH):
            t = (y / max(1, SH - 1)) * (nsky - 1)
            lo = int(t)
            fr = int((t - lo) * 16)
            row = _BAYER[y & 3]
            quad = bytes(SKY_BASE + min(nsky - 1, lo + (1 if row[x] < fr else 0))
                         for x in range(4))
            buf[y * W:(y + 1) * W] = (quad * (W // 4 + 1))[:W]
        nst = (90, 70, 160, 120)[escena % 4]
        for _ in range(nst):
            x = rnd.randrange(W)
            y = int(rnd.random() ** 1.8 * SH * 0.8)
            buf[y * W + x] = STAR2 if rnd.random() < 0.25 else STAR1
        hit = self.cielos[escena] = int.from_bytes(bytes(buf), "little")
        return hit

    def componer(self, g, frame, escena):
        """el cuadro listo para copiar al framebuffer (bytes de W·SH)."""
        A, R8 = self.all, self.row
        r01 = self.r01
        G = int.from_bytes(g, "little")
        # una sola traducción da las cuatro máscaras, una por bit
        C = int.from_bytes(g.translate(T_CLASS), "little")
        E = (C & r01) * 255
        top = (A ^ E) & (E << R8) & A          # lleno, con aire arriba
        L = int.from_bytes(g.translate(T_LIGHT), "little")
        out = (G & (A ^ top)) | (L & top)
        # el agua: su superficie titila
        if C & self.r08:
            sp = ((C >> 3) & r01) * 255 & top & self.brillos[(frame // 9) & 3]
            if sp:
                out = (out & (A ^ sp)) | (self.spk & sp)
        # resplandores sobre el aire. se recalculan cada 2 cuadros: un cuadro de
        # atraso no se nota y el resplandor es la parte cara
        if frame & 1 or self._glow is None or self._glow[0] != escena:
            self._glow = (escena,) + self._resplandor(C, E)
        _, glow, color = self._glow
        out |= color & E
        out |= self.cielo(escena) & E & (A ^ glow)
        return out.to_bytes(self.n, "little")

    def _resplandor(self, C, E):
        """(máscara, colores) del resplandor tibio del fuego y frío del rayo."""
        A, R8, r01 = self.all, self.row, self.r01
        glow = color = 0
        for bit, k1, k2 in ((1, self.g1, self.g2), (2, self.c1, self.c2)):
            if not C & (r01 << bit):
                continue
            m = (C >> bit) & r01
            d1 = (m | (m << 8) | (m >> 8) | (m << R8) | (m >> R8)) & A
            d2 = (d1 | (d1 << 16) | (d1 >> 16) | (d1 << 2 * R8) | (d1 >> 2 * R8)) & A
            n1 = d1 * 255 & E & (A ^ glow)
            n2 = (d2 ^ d1) * 255 & E & self.chk & (A ^ glow) & (A ^ n1)
            glow |= n1 | n2
            color |= (k1 & n1) | (k2 & n2)
        return glow, color


# --- letra grande (para PAUSA y los avisos) ----------------------------------
def big(cx, y, s, col, k=2):
    """texto centrado a k veces, con sombra (el texto grande de pixelkit)."""
    big_ctext(cx, y, s, col, k, UI_SH)


# --- muestras de material para la barra ----------------------------------------
_SWATCH = {}
SW_W, SW_H = 29, 17


def swatch_img():
    """una imagen con una muestra de cada material: un montoncito con sus tonos,
    su borde de luz y su sombra, como se ve en la mesa."""
    if "img" in _SWATCH:
        return _SWATCH["img"]
    img = pyxel.Image(SW_W * 8, SW_H * 4)
    img.cls(UI_BG)
    rnd = random.Random(5)
    for n, kind in enumerate(TOOLS):
        u, v = (n % 8) * SW_W, (n // 8) * SW_H
        _muestra(img, u, v, kind, rnd)
        _SWATCH[kind] = (u, v)
    _SWATCH["img"] = img
    return img


def _muestra(img, u, v, kind, rnd):
    w, h = SW_W, SW_H
    img.rect(u, v, w, h, SKY_BASE + 2)
    for y in range(h):
        for x in range(w):
            if rnd.random() < 0.04 and y < h // 2:
                img.pset(u + x, v + y, STAR1)
    if kind == K_EMPTY:
        img.rect(u, v, w, h, SKY_BASE + 1)
        for d in (0, 1):
            img.line(u + 6 + d, v + 3, u + w - 7 + d, v + h - 4, LAB_RED)
            img.line(u + 6 + d, v + h - 4, u + w - 7 + d, v + 3, LAB_RED)
        return
    if kind == K_PLASMA:
        img.rect(u, v, w, h, COLD2)
        mx = u + w // 2
        pts = ((mx + 4, v), (mx - 2, v + 7), (mx + 2, v + 8), (mx - 4, v + h - 1))
        for a, b in zip(pts, pts[1:]):
            img.line(a[0], a[1], b[0], b[1], PL_BASE + 1)
            img.line(a[0] + 1, a[1], b[0] + 1, b[1], PL_BASE + 3)
        return
    if kind == K_BHOLE:
        cx, cy = u + w // 2, v + h // 2
        img.circ(cx, cy, 7, BH_BASE + 1)
        img.circ(cx, cy, 6, BH_BASE + 2)
        img.circb(cx, cy, 7, BH_BASE + 3)
        img.circ(cx, cy, 4, BH_BASE)
        return
    if kind == K_FWORK:
        for n_ in range(5):
            c = EM_BASE + (n_ % NFW) * 4
            cx, cy = u + 4 + n_ * 5, v + 3 + (n_ * 7) % 9
            img.pset(cx, cy, c)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                img.pset(cx + dx * 2, cy + dy * 2, c + 1)
        for x in range(u + 6, u + w - 6, 4):
            img.rect(x, v + h - 5, 2, 5, BASE[K_FWORK] + (x // 4) % 2)
            img.pset(x, v + h - 5, BASE[K_FWORK] + 3)
        return
    if kind == K_FIRE:
        for y in range(h):
            for x in range(w):
                d = abs(x - w / 2) / (w / 2)
                alto = h * (1 - d * d) * (0.75 + 0.25 * rnd.random())
                if h - y <= alto:
                    t = (h - y) / max(1, alto)
                    img.pset(u + x, v + y, fire_tone(int(FIRE_MAX * (1 - t))))
        return
    b, nv = BASE[kind], NVAR[kind]
    if kind == K_CLONE:
        b, nv = CL_BASE + 1, 2
    liquido = kind in (K_WATER, K_OIL, K_ACID, K_LAVA, K_GAS, K_VIRUS)
    for x in range(w):
        if liquido:
            top = 7 if kind != K_GAS else 2
        elif kind in (K_SAND, K_POWDER, K_STONE, K_SEED, K_SNOW):
            d = abs(x - w / 2) / (w / 2)
            top = int(2 + d * d * 10)
        else:
            top = 3
        for y in range(top, h):
            if kind == K_GAS and rnd.random() < 0.35:
                continue
            c = b + int(rnd.random() * nv)
            if y == top:
                c = T_LIGHT[c]
            elif y == h - 1:
                c = T_DARK[c]
            img.pset(u + x, v + y, c)
    if kind == K_WATER:
        for x in range(2, w, 7):
            img.pset(u + x, v + 7, SPARKLE)


BRUSHES = (1, 2, 4, 7, 11, 16)      # lo que recorre el botón "pincel"
UNDO_MAX = 12
SCENE_START = 2                     # arranca con los fuegos artificiales


class App:
    def __init__(self):
        pyxel.init(W, H, title="powder", fps=60, display_scale=2,
                   capture_scale=2, quit_key=pyxel.KEY_NONE)
        pyxel.colors[:] = PAL
        pyxel.mouse(True)
        cfg = config.apply()       # pantalla y demás, según el sistema del cabinet
        self.crt = config.crt_level(cfg)
        self.setup(os.environ.get("POWDER_TEST") == "1")
        pyxel.run(self.update, self.draw)

    def setup(self, test=False):
        """todo el estado, aparte de pyxel.init: así se arma en una prueba."""
        self.sim = Sim()
        self.piel = Piel()
        self.nframe = 0
        self.escena = SCENE_START
        self.sim.demo(self.escena)
        self.tool = 0
        self.cat = 0
        self.rad = 4
        self.paused = False
        self.menu = False
        self.prev = None
        self.fast = True
        self.fps = 0.0
        self.parts = 0
        self.meter = FpsMeter()
        self.touch = web.is_touch()
        self.hist = deque(maxlen=UNDO_MAX)
        self.toast = None              # [texto, frames]
        self.brush_t = 0               # frames que se ve la muestra del pincel
        self.bolt_t = 0
        self.last = (W // 2, SH // 2)  # dónde se pintó por última vez
        self.test = test
        # powder es "recreativo": sin puntaje. arranca en una pantalla de título
        # con el demo vivo detrás; enter (o tocar) entra a la mesa de arena.
        self.scene = "play" if self.test else "title"
        self.tanim = 0
        web.touch("play" if self.test else "nav")

    def _meter(self):
        self.fps = self.meter.tick()
        if self.meter.updated:
            self.parts = W * SH - self.sim.g.count(0)

    # --- acciones (teclado, botones táctiles y menú hacen lo mismo) ---------
    def snapshot(self):
        self.hist.append((bytes(self.sim.g), bytes(self.sim.aux)))

    def undo(self):
        if not self.hist:
            self._toast("nada que deshacer")
            return
        g, aux = self.hist.pop()
        self.sim.g[:] = g
        self.sim.aux[:] = aux
        self.sim.bursts = []
        self.sim.active[:] = b"\x01" * NCHUNK
        self._toast("deshecho  (quedan %d)" % len(self.hist))

    def vaciar(self):
        self.snapshot()
        self.sim.clear()
        self._toast("mesa vacía · deshacer la recupera")

    def escena_sig(self):
        self.snapshot()
        self.escena = (self.escena + 1) % len(ESCENAS)
        self.sim.demo(self.escena)
        self._toast("escena: " + ESCENAS[self.escena])

    def pincel_sig(self, d=None):
        if d is None:                   # el botón: recorre los tamaños
            mas = [b for b in BRUSHES if b > self.rad]
            self.rad = mas[0] if mas else BRUSHES[0]
        else:                           # la rueda: de a 2
            self.rad = max(1, min(20, self.rad + d))
        self.brush_t = 50

    def elegir(self, n):
        self.tool = n
        self.cat = cat_of(n)
        self._toast(NAMES[TOOLS[n]], 40)

    def _toast(self, s, t=70):
        self.toast = [s, t]

    def update(self):
        if self.test and pyxel.frame_count > 180:
            print("render:", "fast" if self.fast else "pset", flush=True)
            print("fps: %.0f | particulas: %d | chunks: %d/%d"
                  % (self.fps, self.parts, self.sim.awake, NCHUNK), flush=True)
            pyxel.quit()
        self._meter()
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            if self.menu:
                self.menu = False
            elif self.scene == "title":
                web.quit()            # desde el título, esc vuelve al emulador
            else:
                self.scene = "title"  # desde la mesa, esc vuelve al título
                web.touch("nav")
            return
        if self.scene == "title":
            self.tanim += 1
            if (pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE)
                    or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)):
                self.scene = "play"
                web.touch("play")
                self._toast("pinta arriba · elige material abajo", 150)
            self.sim.step()           # el demo sigue vivo detrás del título
            return
        if self.toast:
            self.toast[1] -= 1
            if self.toast[1] <= 0:
                self.toast = None
        if self.brush_t:
            self.brush_t -= 1
        self.play_input()
        if not self.paused:
            self.sim.step()

    def play_input(self):
        if pyxel.btnp(pyxel.KEY_H):
            self.menu = not self.menu
        if self.menu:
            self._menu_input()
            return
        keys = (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4, pyxel.KEY_5,
                pyxel.KEY_6, pyxel.KEY_7, pyxel.KEY_8, pyxel.KEY_9)
        for n, key in enumerate(keys):
            if pyxel.btnp(key):
                self.elegir(n)
        if pyxel.btnp(pyxel.KEY_0):
            self.elegir(len(TOOLS) - 1)
        if pyxel.btnp(pyxel.KEY_TAB):
            self.elegir((self.tool + 1) % len(TOOLS))
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.paused = not self.paused
        if pyxel.btnp(pyxel.KEY_R):
            self.escena_sig()
        if pyxel.btnp(pyxel.KEY_C):
            self.vaciar()
        if pyxel.btnp(pyxel.KEY_X) or pyxel.btnp(pyxel.KEY_U):
            self.undo()
        if pyxel.btnp(pyxel.KEY_Z):
            self.pincel_sig()
        if pyxel.mouse_wheel:
            self.pincel_sig(2 if pyxel.mouse_wheel > 0 else -2)

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        left = pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
        right = pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT)
        press = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and my >= SH:
            hit = tool_at(mx, my, self.cat)
            if hit and hit[0] == "tab":
                self.cat = hit[1]
                ks = CATS[self.cat][1]
                if len(ks) == 1 or TOOLS[self.tool] in ks:
                    self.elegir(TOOLS.index(ks[0]) if len(ks) == 1 else self.tool)
            elif hit:
                self.elegir(hit[1])
            self.prev = None
        elif (left or right) and my < SH and (self.prev is not None or press):
            kind = K_EMPTY if right else TOOLS[self.tool]
            x1 = max(0, min(W - 1, mx))
            y1 = max(0, min(SH - 1, my))
            if press:
                self.snapshot()           # cada trazo se puede deshacer
            if kind == K_PLASMA:
                # el rayo no se pinta: cae. uno al tocar y otro cada tanto si
                # se mantiene apretado
                if press or self.bolt_t <= 0:
                    self.sim.bolt(x1, y1)
                    self.bolt_t = 14
                self.bolt_t -= 1
                self.prev = (x1, y1)
            else:
                x0, y0 = self.prev if self.prev else (x1, y1)
                # un sello cada medio radio, no cada píxel: con el pincel de 16
                # un trazo rápido eran 11 sellos de 1.000 celdas en un frame
                steps = max(1, max(abs(x1 - x0), abs(y1 - y0)) // max(1, self.rad // 2))
                for st in range(steps + 1):
                    self.sim.paint(x0 + (x1 - x0) * st // steps,
                                   y0 + (y1 - y0) * st // steps, kind, self.rad)
                self.prev = (x1, y1)
            self.last = (x1, y1)
        else:
            self.prev = None

    # --- el menú (botón "menú" o tecla h) ----------------------------------
    MENU_W, MENU_BTN_H, MENU_Y = 200, 28, 40

    def _menu_btns(self):
        bx = W // 2 - self.MENU_W // 2
        y0 = self.MENU_Y + 34
        labels = (("seguir", "seguir"),
                  ("vaciar", "vaciar la mesa"),
                  ("escena", "escena: %s  >" % ESCENAS[(self.escena + 1) % len(ESCENAS)]),
                  ("pausa", "reanudar" if self.paused else "pausar"))
        return [(key, lab, bx + 12, y0 + n * (self.MENU_BTN_H + 6),
                 self.MENU_W - 24, self.MENU_BTN_H) for n, (key, lab) in enumerate(labels)]

    def _menu_input(self):
        if pyxel.btnp(pyxel.KEY_C):
            self.vaciar()
            self.menu = False
        if pyxel.btnp(pyxel.KEY_R):
            self.escena_sig()
            self.menu = False
        if pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_RETURN):
            self.menu = False
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            for key, _, x, y, w, h in self._menu_btns():
                if x <= mx < x + w and y <= my < y + h:
                    if key == "vaciar":
                        self.vaciar()
                    elif key == "escena":
                        self.escena_sig()
                    elif key == "pausa":
                        self.paused = not self.paused
                    self.menu = False
                    return
        self.prev = None

    # --- dibujo ------------------------------------------------------------
    def draw(self):
        self.nframe += 1
        frame = self.piel.componer(self.sim.g, self.nframe, self.escena)
        if self.fast:
            self.fast = fast_blit(frame, W * SH)
        if not self.fast:
            pyxel.cls(0)
            blit_slow(self.sim.g, W, SH)
        if self.sim.flash:                 # el fogonazo del rayo
            fx.flash(UI_TXT, 0.10 * self.sim.flash, 0, 0, W, SH)
            self.sim.flash -= 1

        self._barra()
        if self.scene == "title":
            self._title_card()
        else:
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            self._chip(mx, my)
            if 0 <= my < SH and not self.menu and (not self.touch or
                                                   pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)):
                if TOOLS[self.tool] == K_PLASMA:
                    for d, col in ((5, UI_SH), (4, UI_HI)):
                        pyxel.line(mx - d, my, mx + d, my, col)
                        pyxel.line(mx, my - d, mx, my + d, col)
                else:
                    pyxel.circb(mx, my, self.rad + 1, UI_SH)
                    pyxel.circb(mx, my, self.rad, UI_TXT)
            if self.brush_t:
                cx, cy = W // 2, SH // 2
                pyxel.circ(cx, cy, self.rad + 2, UI_SH)
                pyxel.circ(cx, cy, self.rad, UI_TAB)
                pyxel.circb(cx, cy, self.rad, UI_HI)
                big(cx, cy + self.rad + 8, "PINCEL %d" % self.rad, UI_HI)
            if self.paused and not self.menu:
                pyxel.rect(W // 2 - 66, 40, 132, 50, UI_SH)
                pyxel.rectb(W // 2 - 66, 40, 132, 50, UI_HI)
                big(W // 2, 50, "PAUSA", UI_HI, 3)
                ctext(W // 2, 76, "toca pausa para seguir" if self.touch
                      else "espacio para seguir", UI_TXT)
            if self.toast and not self.menu:
                s, t = self.toast
                if t > 8 or (pyxel.frame_count // 2) % 2:
                    w = len(s) * 4 + 16
                    y = SH - 20
                    pyxel.rect(W // 2 - w // 2, y, w, 14, UI_SH)
                    pyxel.rectb(W // 2 - w // 2, y, w, 14, UI_LINE)
                    ctext(W // 2, y + 4, s, UI_TXT)
            if self.menu:
                self._menu_draw()
        crt.apply(self.crt)        # el vidrio del cabinet, al final de todo

    def _swatch(self, x, y, kind):
        img = swatch_img()
        u, v = _SWATCH[kind]
        pyxel.blt(x, y, img, u, v, SW_W, SW_H)

    def _barra(self):
        y0 = SH
        pyxel.rect(0, y0, W, UI_H, UI_BG)
        pyxel.rect(0, y0, W, 1, UI_LINE)
        # pestañas: la abierta sube y se une a la fila de materiales
        for c, (nom, ks) in enumerate(CATS):
            x = c * TAB_W + 2
            w = TAB_W - 3
            abierta = c == self.cat
            col = (LAB_RED if ks[0] == K_EMPTY else T_LIGHT[BASE[ks[0]] + NVAR[ks[0]] // 2])
            tiene = TOOLS[self.tool] in ks
            if abierta:
                pyxel.rect(x, y0 + 2, w, TAB_H - 1, UI_TAB)
                pyxel.rect(x, y0 + 2, w, 2, col)
            else:
                pyxel.rect(x, y0 + 4, w, TAB_H - 6, UI_SH)
                pyxel.rectb(x, y0 + 4, w, TAB_H - 6, UI_LINE)
            pyxel.rect(x + 3, y0 + 9, 5, 5, UI_SH)
            pyxel.rect(x + 4, y0 + 10, 3, 3, col)
            pxtext(x + 11, y0 + 10, nom, UI_HI if tiene else
                   (UI_TXT if abierta else UI_DIM))
        cy = y0 + TAB_H
        pyxel.rect(0, cy, W, CELL_H + 1, UI_TAB)
        # las casillas de la pestaña abierta
        for n, kind in enumerate(CATS[self.cat][1]):
            x, y, w, h = cell_box(n)
            sel = TOOLS[self.tool] == kind
            pyxel.rect(x + 1, y + 2, w - 2, h - 4, UI_TAB2 if sel else UI_BG)
            self._swatch(x + (w - SW_W) // 2, y + 4, kind)
            pyxel.rectb(x + (w - SW_W) // 2 - 1, y + 3, SW_W + 2, SW_H + 2, UI_SH)
            nombre = SHORT[kind]
            pxtext(int(x + w / 2 - len(nombre) * 2), y + 26, nombre,
                   UI_HI if sel else UI_TXT)
            if sel:
                pyxel.rectb(x, y + 1, w, h - 2, UI_HI)
                pyxel.rectb(x + 1, y + 2, w - 2, h - 4, UI_HI)
        if CATS[self.cat][1] == (K_EMPTY,):
            pxtext(52, cy + 11, "arrastra para borrar", UI_TXT)
            pxtext(52, cy + 22, "(clic derecho también borra)" if not self.touch
                   else "deshacer recupera lo borrado", UI_DIM)

    def _chip(self, mx, my):
        """qué tienes en la mano: material y pincel, siempre a la vista."""
        kind = TOOLS[self.tool]
        nom = NAMES[kind]
        sub = "toca donde cae" if kind == K_PLASMA else "pincel %d" % self.rad
        w = max(big_width(nom, 1) * 2, len(sub) * 4) + SW_W + 14
        x = 3
        if mx < w + 10 and my < 30:
            x = W - w - 3                 # se corre si el dedo está encima
        pyxel.rect(x, 3, w, 25, UI_SH)
        pyxel.rectb(x, 3, w, 25, UI_LINE)
        self._swatch(x + 3, 7, kind)
        big_text(x + SW_W + 8, 7, nom, UI_TXT, 2, UI_SH)
        pxtext(x + SW_W + 8, 20, sub, UI_DIM)
        if kind != K_PLASMA:            # el grosor del pincel, en chico
            rr = min(5, max(1, self.rad // 3))
            pyxel.circb(x + w - 8, 21, rr, UI_HI)

    def _menu_draw(self):
        bw = self.MENU_W
        bx = W // 2 - bw // 2
        bh = 236
        by = self.MENU_Y
        pyxel.rect(bx + 4, by + 4, bw, bh, UI_SH)
        pyxel.rect(bx, by, bw, bh, UI_BG)
        pyxel.rectb(bx, by, bw, bh, UI_LINE)
        pyxel.rect(bx, by, bw, 2, UI_HI)
        big(W // 2, by + 11, "POWDER", UI_HI, 2)
        for key, lab, x, y, w, h in self._menu_btns():
            pyxel.rect(x, y, w, h, UI_TAB2 if key == "seguir" else UI_TAB)
            pyxel.rectb(x, y, w, h, UI_HI if key == "seguir" else UI_LINE)
            ctext(x + w // 2, y + h // 2 - 2, lab, UI_TXT)
        y = by + 176
        if self.touch:
            lines = ("pinta arriba · elige el material abajo",
                     "pincel cambia el grosor",
                     "deshacer vuelve atrás",
                     "%d partículas · %.0f fps" % (self.parts, self.fps))
        else:
            lines = ("izq pinta · der borra · rueda o z: pincel",
                     "x deshace · 1-0 o tab material",
                     "espacio pausa · c vacía · r escena",
                     "h menú · esc título",
                     "%d partículas · %.0f fps" % (self.parts, self.fps))
        for n, l in enumerate(lines):
            ctext(W // 2, y + n * 10, l, UI_DIM)

    def _title_card(self):
        cx = W // 2
        bw, bh = W - 24, 150
        bx, by = cx - bw // 2, 44
        pyxel.rect(bx + 4, by + 4, bw, bh, UI_SH)
        pyxel.rect(bx, by, bw, bh, UI_BG)
        pyxel.rectb(bx, by, bw, bh, UI_LINE)
        pyxel.rect(bx, by, bw, 2, UI_HI)
        # el título con un degradé de fuego que sube
        k = 5
        tw = big_width("POWDER", k)
        big_text(cx - tw // 2 + 1, by + 16 + 2, "POWDER", fire_tone(8), k)
        for i, ch in enumerate("POWDER"):
            vida = FIRE_MAX - (i * 5 + self.tanim // 3) % 26
            big_text(cx - tw // 2 + i * 4 * k, by + 16, ch, fire_tone(vida), k)
        ctext(cx, by + 52, "recreativo · mesa de arena", T_LIGHT[BASE[K_LEAF]])
        # una fila de muestras: lo que hay para pintar
        img = swatch_img()
        for n, kind in enumerate((K_SAND, K_WATER, K_LAVA, K_FIRE, K_PLANT, K_FWORK)):
            u, v = _SWATCH[kind]
            sx = bx + 9 + n * 30
            pyxel.blt(sx, by + 66, img, u, v, 26, SW_H)
            pyxel.rectb(sx - 1, by + 65, 28, SW_H + 2, UI_SH)
        for n, s in enumerate(("23 materiales: cohetes, virus,",
                               "rayos, clonador y un agujero negro",
                               "pinta con el dedo · elige abajo" if self.touch
                               else "click pinta · rueda pincel · x deshace")):
            ctext(cx, by + 94 + n * 10, s, UI_TXT)
        if (self.tanim // 20) % 2 == 0:
            msg = "toca para entrar" if self.touch else "enter para entrar"
            pw = len(msg) * 4 + 18
            pyxel.rect(cx - pw // 2, by + bh - 22, pw, 13, UI_HI)
            ctext(cx, by + bh - 18, msg, UI_SH)


if __name__ == "__main__":
    App()
