# powder — física de partículas estilo falling sand, con pyxel
#
# la grilla guarda en cada celda un byte que YA es el índice de paleta:
# cada material ocupa un rango de tonos, así la textura viaja con la partícula
# y el frame se dibuja copiando el bytearray al framebuffer, sin conversión.
# la simulación solo recorre los chunks que tuvieron actividad.
import os
import random

import pyxel

from pixelkit import config, crt, web
from pixelkit.blit import FpsMeter, blit_slow, fast_blit
from pixelkit.palette import shades as _shades
from pixelkit.pxtext import ctext, text as pxtext

W, H = 320, 240
# la barra va en dos filas con el NOMBRE debajo de cada material. en una sola
# fila entraban 18 swatches de 16 px y en 16 px no cabe ni una palabra de 4
# letras: había que pasar el mouse por encima para saber qué era cada color.
# con dos filas cada celda mide 35 px ≈ 8 caracteres, y ahí entra "pólvora".
TOOL_COLS = 9
TOOL_CW = W // TOOL_COLS         # ancho de celda: swatch + nombre debajo
TOOL_ROW_H = 21                  # 13 del swatch + el renglón del nombre
UI_H = 2 * TOOL_ROW_H + 14       # las dos filas más la línea de estado
SH = H - UI_H  # alto del área de simulación

CHB = 5  # chunk de 32x32
CHS = 1 << CHB
CW = (W + CHS - 1) >> CHB
CH_ROWS = (SH + CHS - 1) >> CHB
NCHUNK = CW * CH_ROWS

# tipos lógicos
(K_EMPTY, K_WALL, K_WOOD, K_METAL, K_TRUNK, K_LEAF, K_SAND, K_WATER, K_OIL,
 K_PLANT, K_ACID, K_FIRE, K_LAVA, K_STONE, K_STEAM, K_SMOKE, K_POWDER,
 K_ICE, K_SEED, K_GAS, K_SPARK, K_MCOOL) = range(22)

NAMES = {
    K_WALL: "muro", K_WOOD: "madera", K_SAND: "arena", K_WATER: "agua",
    K_OIL: "aceite", K_PLANT: "planta", K_ACID: "ácido", K_FIRE: "fuego",
    K_LAVA: "lava", K_STONE: "piedra", K_STEAM: "vapor", K_SMOKE: "humo",
    K_POWDER: "pólvora", K_EMPTY: "borrar", K_ICE: "hielo", K_SEED: "semilla",
    K_GAS: "gas", K_SPARK: "chispa", K_METAL: "metal",
    K_TRUNK: "tronco", K_LEAF: "hoja",
}

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

UI_BG, UI_LINE, UI_DIM, UI_TXT, UI_HI = 250, 251, 252, 253, 254
while len(PAL) < 256:
    PAL.append(0)
PAL[UI_BG] = 0x101018
PAL[UI_LINE] = 0x2E3242
PAL[UI_DIM] = 0x6A7085
PAL[UI_TXT] = 0xE8ECF5
PAL[UI_HI] = 0xFFD24A
KIND = bytes(_KIND)

F_BASE, F_N = BASE[K_FIRE], NVAR[K_FIRE]
L_BASE, L_N = BASE[K_LAVA], NVAR[K_LAVA]
SP_BASE, SP_N = BASE[K_SPARK], NVAR[K_SPARK]
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
# estaba a 10-15 px. el aceite va espeso a propósito.
SPREAD, SPREAD_OIL = 14, 3
# el agua guarda en `aux` cuántos frames viene cayendo: es su velocidad. al
# tocar fondo, si venía con impulso, salpica.
FALL_MAX = 12
SPLASH_MIN = 4                   # caída mínima para que valga la pena salpicar
# lo que el fuego puede prender, con su probabilidad de prender por contacto
FLAMMABLE = {K_PLANT: 0.30, K_OIL: 0.70, K_WOOD: 0.05, K_LEAF: 0.38,
             K_TRUNK: 0.06, K_SEED: 0.25, K_GAS: 0.90}
# lo que el ácido NO disuelve
ACID_PROOF = (K_EMPTY, K_WALL, K_ACID, K_WATER, K_FIRE, K_SMOKE, K_STEAM,
              K_SPARK, K_GAS)
# suelo firme donde una semilla puede echar raíz
SOIL = (K_SAND, K_STONE, K_WOOD, K_PLANT, K_TRUNK, K_WALL, K_METAL)
# lo que enciende al gas y a la pólvora
HOT = (K_FIRE, K_LAVA, K_SPARK)
# lo que el pincel puede desplazar: se le echa lava al mar sin borrarlo antes,
# pero lo que construiste (muro, metal, hielo...) no se pisa por accidente
REPLACEABLE = (K_EMPTY, K_WATER, K_OIL, K_ACID, K_STEAM, K_SMOKE, K_GAS, K_FIRE)
NB4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
NB8 = ((1, 0), (-1, 0), (0, 1), (0, -1),
       (1, 1), (1, -1), (-1, 1), (-1, -1))

TOOLS = (K_SAND, K_WATER, K_WALL, K_FIRE, K_PLANT, K_OIL, K_ACID, K_LAVA,
         K_POWDER, K_WOOD, K_STONE, K_ICE, K_SEED, K_GAS, K_METAL, K_SPARK,
         K_EMPTY)


def tool_box(n):
    """(x, y) del swatch n en la barra de dos filas."""
    fila, col = divmod(n, TOOL_COLS)
    return col * TOOL_CW + (TOOL_CW - 13) // 2, SH + 3 + fila * TOOL_ROW_H


def tool_at(mx, my):
    """qué material hay bajo el mouse en la barra, o -1 si no hay ninguno."""
    if my < SH:
        return -1
    fila = (my - SH) // TOOL_ROW_H
    if fila > (len(TOOLS) - 1) // TOOL_COLS:
        return -1
    n = fila * TOOL_COLS + min(TOOL_COLS - 1, mx // TOOL_CW)
    return n if 0 <= n < len(TOOLS) else -1


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

    def clear(self):
        self.g[:] = self._zero
        self.aux[:] = self._zero
        self.active[:] = b"\x01" * NCHUNK

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
                xs = range(x1 - 1, x0 - 1, -1) if flip else range(x0, x1)
                for x in xs:
                    i = row + x
                    e = g[i]
                    if e < FIRST_ACTIVE or upd[i]:
                        continue
                    k = KND[e]

                    if k == K_SAND or k == K_POWDER or k == K_STONE:
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
                if KIND[g[j]] == K_WALL:
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
        g = self.g
        r = random.random
        ri = random.randint
        r2 = rad * rad
        solid = kind in (K_WALL, K_WOOD, K_PLANT, K_METAL, K_ICE)
        for dy in range(-rad, rad + 1):
            ny = cy + dy
            if not 0 <= ny < SH:
                continue
            for dx in range(-rad, rad + 1):
                if dx * dx + dy * dy > r2:
                    continue
                nx = cx + dx
                if not 0 <= nx < W:
                    continue
                j = ny * W + nx
                cur = KIND[g[j]]
                if kind == K_EMPTY:
                    self.put(j, K_EMPTY)
                elif kind == K_SPARK:
                    # la chispa no se pinta al aire: energiza el cable
                    if cur == K_METAL:
                        self.g[j] = SP_BASE
                        self.aux[j] = SPARK_LIFE
                elif kind == K_FIRE:
                    if cur == K_POWDER:
                        self.explode(nx, ny)
                    elif cur in FLAMMABLE:
                        self.put(j, K_FIRE, ri(20, 60))
                    elif cur == K_ICE:  # el pincel de fuego hace de soplete
                        self.g[j] = W_WARM
                        self.aux[j] = 0
                    elif cur == K_EMPTY and r() < 0.35:
                        self.put(j, K_FIRE, ri(15, 40))
                elif cur in REPLACEABLE:
                    if solid or r() < 0.55:
                        self.put(j, kind)
                self.wake(nx, ny)

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

    def demo(self):
        self.clear()
        # océano
        for y in range(SH - 26, SH):
            for x in range(W):
                self.put(y * W + x, K_WATER)
        # isla con una semilla lista para hacerse árbol
        self._blob(150, SH - 1, 30, K_STONE, force=True)
        self.put((SH - 33) * W + 150, K_SEED)
        # témpano en un rincón: se va comiendo el mar de a poco
        self._blob(28, SH - 20, 7, K_ICE, force=True)
        # mancha de aceite
        self._blob(104, SH - 30, 7, K_OIL, force=True)
        # caldero de lava con gotera
        self._bar(16, 20, 16, 46, K_WALL)
        self._bar(56, 20, 56, 46, K_WALL)
        self._bar(16, 44, 56, 44, K_WALL)
        for y in range(28, 44):
            for x in range(20, 56):
                self.put(y * W + x, K_LAVA)
        for y in range(44, 48):
            for x in range(35, 38):
                self.put(y * W + x, K_EMPTY)
        # repisa diagonal que recibe la gotera
        self._bar(12, 92, 108, 122, K_WALL)
        # meteorito de arena cayendo al océano
        self._blob(210, 30, 13, K_SAND)
        # circuito: cable de metal desde un pulsador hasta la carga de pólvora.
        # dale chispa (tecla 16 / click en el swatch) al extremo izquierdo
        self._bar(232, 60, 300, 60, K_METAL, th=2)
        self._bar(300, 60, 300, 96, K_METAL, th=2)
        self._bar(228, 112, 306, 112, K_WOOD)
        self._blob(300, 104, 8, K_POWDER)


class App:
    def __init__(self):
        pyxel.init(W, H, title="powder", fps=60, display_scale=3,
                   capture_scale=2, quit_key=pyxel.KEY_NONE)
        pyxel.colors[:] = PAL
        pyxel.mouse(True)
        cfg = config.apply()       # pantalla y demás, según el sistema del cabinet
        self.crt = config.crt_level(cfg)
        self.sim = Sim()
        self.sim.demo()
        self.tool = 0
        self.rad = 4
        self.paused = False
        self.help = True
        self.prev = None
        self.fast = True
        self.fps = 0.0
        self.parts = 0
        self.meter = FpsMeter()
        self.test = os.environ.get("POWDER_TEST") == "1"
        # powder es "recreativo": sin puntaje. arranca en una pantalla de título
        # con el demo vivo detrás; enter entra a la mesa de arena.
        self.scene = "play" if self.test else "title"
        self.tanim = 0
        pyxel.run(self.update, self.draw)

    def _meter(self):
        self.fps = self.meter.tick()
        if self.meter.updated:
            self.parts = W * SH - self.sim.g.count(0)

    def update(self):
        if self.test and pyxel.frame_count > 180:
            print("render:", "fast" if self.fast else "pset", flush=True)
            print("fps: %.0f | particulas: %d | chunks: %d/%d"
                  % (self.fps, self.parts, self.sim.awake, NCHUNK), flush=True)
            pyxel.quit()
        self._meter()
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            if self.scene == "title":
                web.quit()            # desde el título, esc vuelve al emulador
            else:
                self.scene = "title"  # desde la mesa, esc vuelve al título
            return
        if self.scene == "title":
            self.tanim += 1
            if (pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE)
                    or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)):
                self.scene = "play"
            self.sim.step()           # el demo sigue vivo detrás del título
            return
        keys = (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4, pyxel.KEY_5,
                pyxel.KEY_6, pyxel.KEY_7, pyxel.KEY_8, pyxel.KEY_9)
        for n, key in enumerate(keys):
            if pyxel.btnp(key):
                self.tool = n
        if pyxel.btnp(pyxel.KEY_0):
            self.tool = len(TOOLS) - 1
        if pyxel.btnp(pyxel.KEY_TAB):
            self.tool = (self.tool + 1) % len(TOOLS)
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.paused = not self.paused
        if pyxel.btnp(pyxel.KEY_H):
            self.help = not self.help
        if pyxel.btnp(pyxel.KEY_R):
            self.sim.demo()
        if pyxel.btnp(pyxel.KEY_C):
            self.sim.clear()
        if pyxel.mouse_wheel:
            self.rad = max(1, min(20, self.rad + (2 if pyxel.mouse_wheel > 0 else -2)))

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        left = pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
        right = pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and my >= SH:
            idx = tool_at(mx, my)
            if idx >= 0:
                self.tool = idx
            self.prev = None
        elif (left or right) and my < SH:
            self.help = False
            kind = K_EMPTY if right else TOOLS[self.tool]
            x1 = max(0, min(W - 1, mx))
            y1 = max(0, min(SH - 1, my))
            x0, y0 = self.prev if self.prev else (x1, y1)
            steps = max(abs(x1 - x0), abs(y1 - y0), 1)
            for s in range(steps + 1):
                self.sim.paint(x0 + (x1 - x0) * s // steps,
                               y0 + (y1 - y0) * s // steps, kind, self.rad)
            self.prev = (x1, y1)
        else:
            self.prev = None

        if not self.paused:
            self.sim.step()

    def draw(self):
        if self.fast:
            self.fast = fast_blit(self.sim.g, W * SH)
        if not self.fast:
            pyxel.cls(0)
            blit_slow(self.sim.g, W, SH)

        pyxel.rect(0, SH, W, UI_H, UI_BG)
        pyxel.rect(0, SH, W, 1, UI_LINE)
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        hover = tool_at(mx, my)
        for n, kind in enumerate(TOOLS):
            sx, sy = tool_box(n)
            if kind == K_EMPTY:
                pyxel.rectb(sx, sy, 13, 13, UI_DIM)
                pyxel.text(sx + 5, sy + 4, "x", UI_DIM)
            else:
                b, nv = BASE[kind], NVAR[kind]
                for row in range(13):
                    pyxel.rect(sx, sy + row, 13, 1, b + (row * nv // 13))
            if n == self.tool:
                pyxel.rectb(sx - 2, sy - 2, 17, 17, UI_HI)
            elif n == hover:
                pyxel.rectb(sx - 1, sy - 1, 15, 15, UI_DIM)
            # el nombre, siempre: es lo que hace que la barra se lea de un vistazo
            nombre = NAMES[kind]
            col = UI_HI if n == self.tool else (UI_TXT if n == hover else UI_DIM)
            cx = n % TOOL_COLS * TOOL_CW + TOOL_CW // 2
            pxtext(int(cx - len(nombre) * 2), sy + 14, nombre, col)

        y = SH + 2 * TOOL_ROW_H + 6
        pyxel.rect(0, y - 2, W, 1, UI_LINE)
        pxtext(4, y + 1, "pincel %d" % self.rad, UI_DIM)
        pyxel.text(W - 60, y + 1, "%3.0f fps" % self.fps, UI_DIM)

        if self.paused:
            pyxel.text(W - 28, 4, "PAUSA", UI_HI)
        if 0 <= my < SH:
            pyxel.circb(mx, my, self.rad, UI_TXT)

        if self.help and self.scene == "play":
            bx, by, bw = 14, 46, 168
            lines = ("click izq pinta / der borra",
                     "rueda: grosor del pincel",
                     "1-0 o tab: material",
                     "espacio: pausa    r: escena",
                     "c: vaciar  h: ayuda  esc: título")
            bh = 20 + len(lines) * 8
            pyxel.rect(bx, by, bw, bh, UI_BG)
            pyxel.rectb(bx, by, bw, bh, UI_LINE)
            pyxel.text(bx + 8, by + 7, "P O W D E R", UI_HI)
            for n, s in enumerate(lines):
                pyxel.text(bx + 8, by + 19 + n * 8, s, UI_TXT)

        if self.scene == "title":
            self._title_card()

        crt.apply(self.crt)        # el vidrio del cabinet, al final de todo

    def _title_card(self):
        cx = W // 2
        bw, bh = 214, 92
        bx, by = cx - bw // 2, 42
        pyxel.rect(bx + 3, by + 3, bw, bh, 0)
        pyxel.rect(bx, by, bw, bh, UI_BG)
        pyxel.rectb(bx, by, bw, bh, UI_LINE)
        ctext(cx, by + 12, "P O W D E R", UI_HI)
        ctext(cx, by + 26, "recreativo · mesa de arena", BASE[K_LEAF] + 3)
        for n, s in enumerate(("17 materiales que caen, arden y salpican",
                               "click pinta · rueda pincel · tab material",
                               "espacio pausa · esc vuelve al título")):
            ctext(cx, by + 42 + n * 9, s, UI_TXT)
        if (self.tanim // 20) % 2 == 0:
            ctext(cx, by + bh - 14, "enter para entrar", UI_HI)


if __name__ == "__main__":
    App()
