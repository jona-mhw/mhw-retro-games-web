"""cruzar, el arte: paleta con rampas, sprites horneados y los fondos de cada tramo.

todo lo que no se mueve se dibuja una sola vez:

- **los sprites** (autos, camiones, buses, motos, trenes, troncos y cintas) se
  hornean mirando a la derecha en los bancos de imágenes 0 y 1; los que van
  para la izquierda se dibujan con `blt` de ancho negativo, que los espeja.
  así un vehículo con volumen, sombra y haz de luz es un solo `blt`.
- **las texturas** (asfalto, pasto, baldosas, ripio, agua) se hornean en
  mosaicos chicos con ruido determinista, y con ellos se arma
- **el fondo de cada tramo**: una imagen del tamaño de la pantalla, hecha una
  vez por tramo, que se estampa entera con un `blt` por frame.

lo único vivo encima es el agua (un `blt` por carril, con dos cuadros que se
alternan), lo que circula y los avisos.
"""
import pyxel

# --- la paleta -----------------------------------------------------------------
# rampas de 3-4 tonos (luz / medio / sombra) para que todo tenga volumen. el 0
# es el fondo y es también el color transparente de los sprites: ningún sprite
# lo usa (los contornos van con OUT).
_PAL = [
    ("BG", 0x0B0A16), ("SHADOW", 0x060512), ("OUT", 0x0D0A1A),
    ("WHITE", 0xF2F5FB), ("TXT", 0xE8ECF5), ("DIM", 0x9A90C8),
    ("ACCENT", 0x38E8E0), ("WARN", 0xFF5A3A), ("GOLD", 0xFFD24A),
    ("GOLDDK", 0xA8741E), ("GOLDHI", 0xFFF2B0), ("PINK", 0xE868C8),
    ("PINKDK", 0x8A2A7A), ("META", 0x9AE84A), ("ROJO", 0xFF3B30),
    ("ROJODK", 0x9A1A1E), ("HUDC", 0x0E0C1C), ("HUD2", 0x1C1834),
    ("EDGE", 0x3A2C63), ("LUZ", 0xFFF2A8), ("LUZ2", 0xE8B85A),
    ("SOMBRA", 0x07060E),
    # el asfalto de cada tramo: oscuro, medio, claro
    ("ASB0", 0x100E24), ("ASB1", 0x1A1736), ("ASB2", 0x2A2650),
    ("ASV0", 0x0C1230), ("ASV1", 0x141D40), ("ASV2", 0x223058),
    ("AST0", 0x15121C), ("AST1", 0x1F1B2A), ("AST2", 0x302A40),
    ("ASR0", 0x0C171E), ("ASR1", 0x13242C), ("ASR2", 0x1F3A44),
    ("ASA0", 0x180C1C), ("ASA1", 0x24142A), ("ASA2", 0x3A2244),
    ("LINEA", 0x8A84A8), ("LINEA2", 0x4A4468), ("AMARILLA", 0xC8A040),
    # veredas y soleras
    ("VER0", 0x26223A), ("VER1", 0x37324F), ("VER2", 0x4A4466),
    ("VER3", 0x625C80), ("CURB", 0x9A94B8),
    # el pasto
    ("PASTO0", 0x0A2016), ("PASTO1", 0x123620), ("PASTO2", 0x1E522E),
    ("PASTO3", 0x3A8040), ("PASTO4", 0x6AB04E),
    # el agua
    ("AGUA0", 0x0A1A42), ("AGUA1", 0x112E66), ("AGUA2", 0x1D4C94),
    ("AGUA3", 0x4A88D4), ("ESPUMA", 0xBFE8FF),
    ("BARRO", 0x3A2A1E), ("BARRO2", 0x5A442E),
    # los troncos
    ("TRONCO0", 0x2A170A), ("TRONCODK", 0x5A3618), ("TRONCO", 0x8A5628),
    ("TRONCOHI", 0xC08446), ("ANILLO", 0xE6C48A), ("MUSGO", 0x4E7A2A),
    # la vía
    ("BAL0", 0x18161E), ("BAL1", 0x28242F), ("BAL2", 0x3C3846),
    ("DURM", 0x4A3020), ("DURM2", 0x6A4830), ("RIEL", 0x8A8CA8),
    ("RIELHI", 0xD8DCF0),
    # el tren, los vidrios
    ("TREN0", 0x3A4058), ("TREN1", 0x6A7490), ("TREN2", 0xA8B0C8),
    ("TREN3", 0xE0E6F4), ("VIDRIO", 0x1C2A48), ("VIDRIO2", 0x3A6A9A),
    ("VIDRIOHI", 0x9AE0FF),
    # los autos: luz, medio, sombra
    ("CRP0", 0xFFA8E0), ("CRP1", 0xFF5EBE), ("CRP2", 0xA02E78),
    ("CRY0", 0xFFEC9A), ("CRY1", 0xFFC23A), ("CRY2", 0xA87414),
    ("CRG0", 0xC8FF8A), ("CRG1", 0x84D23A), ("CRG2", 0x3A841E),
    ("CRC0", 0xA8FFF8), ("CRC1", 0x2CCACA), ("CRC2", 0x147480),
    ("CRV0", 0xD4B4FF), ("CRV1", 0x9A6AF0), ("CRV2", 0x5636A0),
    ("CAB0", 0xFF8A6A), ("CAB1", 0xE04A2A), ("CAB2", 0x8A2416),
    ("BUS0", 0x9AD0FF), ("BUS1", 0x4D96F0), ("BUS2", 0x2850A0),
    ("MOT0", 0xFFC88A), ("MOT1", 0xFF8A2E), ("MOT2", 0xA04A14),
    # el que cruza
    ("PL3", 0xDCFFFC), ("PL2", 0x7AF4EC), ("PL1", 0x30D8D0), ("PL0", 0x157E7E),
    # ítems y climas
    ("SHIELD", 0x7ADCFF), ("HIELOC", 0xA8E8FF), ("POSTE", 0x3A3452),
    ("CINTA0", 0x0E1A30), ("CINTA1", 0x2A72B4), ("CINTA2", 0x7ADCFF),
    ("CINTA3", 0x16426E),
    ("HOJA0", 0x0C2A1C), ("HOJA1", 0x1A4E2E), ("HOJA2", 0x2E7A3E),
    ("HOJA3", 0x5AA84C),
]
globals().update({n: i for i, (n, _) in enumerate(_PAL)})
PAL = [c for _, c in _PAL] + [0] * (256 - len(_PAL))

# asfalto por tramo (oscuro, medio, claro)
ASFALTO = {"BARRIO": (ASB0, ASB1, ASB2), "AVENIDA": (ASV0, ASV1, ASV2),
           "VÍA DEL TREN": (AST0, AST1, AST2), "EL RÍO": (ASR0, ASR1, ASR2),
           "AUTOPISTA": (ASA0, ASA1, ASA2)}
# los colores de los autos, de a rampa
AUTOS = ((CRP0, CRP1, CRP2), (CRY0, CRY1, CRY2), (CRG0, CRG1, CRG2),
         (CRC0, CRC1, CRC2), (CRV0, CRV1, CRV2))

BEAM = 6          # el haz de los faros, delante del auto (va dentro del sprite)


class _Rng:
    """ruido determinista: el fondo sale igual en cada arranque."""

    def __init__(self, seed):
        self.s = seed & 0x7FFFFFFF

    def __call__(self, n):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s >> 8) % n


class _Pen:
    """dibuja en una imagen corrida a (u, v): los sprites se escriben en
    coordenadas propias."""

    def __init__(self, img, u, v):
        self.img, self.u, self.v = img, u, v

    def r(self, x, y, w, h, c):
        if w > 0 and h > 0:
            self.img.rect(self.u + x, self.v + y, w, h, c)

    def p(self, x, y, c):
        self.img.pset(self.u + x, self.v + y, c)


class _Atlas:
    """reparte los bancos 0 y 1 en estantes."""

    def __init__(self):
        self.bank = 0
        self.x = self.y = self.row = 0
        pyxel.images[0].cls(0)
        pyxel.images[1].cls(0)

    def alloc(self, w, h):
        if self.x + w > 256:
            self.x, self.y, self.row = 0, self.y + self.row + 1, 0
        if self.y + h > 256:
            self.bank += 1
            self.x = self.y = self.row = 0
        u, v = self.x, self.y
        self.x += w + 1
        self.row = max(self.row, h)
        return self.bank, u, v


SPR = {}


def _bake(atlas, key, w, h, fn, *args):
    bank, u, v = atlas.alloc(w, h)
    fn(_Pen(pyxel.images[bank], u, v), *args)
    SPR[key] = (bank, u, v, w, h)


def _beam(p, x0, y0, y1, largo):
    """el haz de los faros: un tramado que se abre y se apaga hacia adelante."""
    for j in range(largo):
        for y in range(y0 - j // 2, y1 + 1 + j // 2):
            if (j + y) % 2 == 0 and (j < largo - 2 or (y + j) % 4 == 0):
                p.p(x0 + j, y, LUZ if j < 2 else LUZ2)


def _ruedas(p, xs, top, bot):
    for x in xs:
        p.r(x, top, 4, 2, OUT)
        p.r(x, bot, 4, 2, OUT)
        p.p(x + 1, bot + 1, TREN0)


def _auto(p, w, ramp):
    hi, mid, dk = ramp
    p.r(2, 12, w - 1, 4, SOMBRA)                    # la sombra en el asfalto
    _ruedas(p, (3, w - 7), 1, 12)
    p.r(1, 2, w - 2, 11, OUT)                        # contorno redondeado
    p.r(0, 3, w, 9, OUT)
    p.r(2, 3, w - 4, 9, mid)
    p.r(1, 4, w - 2, 7, mid)
    p.r(2, 3, w - 4, 1, hi)                          # luz arriba
    p.r(1, 4, 1, 4, hi)
    p.r(1, 9, w - 2, 2, dk)                          # el costado, en sombra
    p.r(2, 11, w - 4, 1, dk)
    c0, c1 = int(w * 0.26), int(w * 0.8)            # la cabina
    p.r(c0, 4, c1 - c0, 5, OUT)
    p.r(c0 + 1, 4, 2, 5, VIDRIO)                     # luneta
    p.r(c0 + 3, 4, c1 - c0 - 6, 5, hi)               # techo
    p.r(c0 + 3, 8, c1 - c0 - 6, 1, mid)
    p.r(c1 - 3, 4, 3, 5, VIDRIO2)                    # parabrisas
    p.p(c1 - 2, 5, VIDRIOHI)
    p.p(c1 - 3, 4, VIDRIOHI)
    p.r(c1, 4, w - c1 - 2, 1, hi)                    # el capó, con brillo
    p.p(w - 1, 4, LUZ)                               # faros
    p.p(w - 1, 9, LUZ)
    p.p(w - 2, 4, WHITE)
    p.p(0, 4, ROJO)                                  # luces de atrás
    p.p(0, 9, ROJO)
    _beam(p, w, 4, 9, BEAM)


def _camion(p, w):
    cab = 10
    tw = w - cab - 1
    p.r(2, 12, w - 1, 4, SOMBRA)
    _ruedas(p, (2, 8, w - 7), 0, 13)
    # el contenedor
    p.r(0, 1, tw, 12, OUT)
    p.r(1, 2, tw - 2, 10, TREN2)
    p.r(1, 2, tw - 2, 1, TREN3)
    p.r(1, 10, tw - 2, 2, TREN1)
    for x in range(4, tw - 2, 3):
        p.r(x, 3, 1, 7, TREN1)
    p.r(3, 5, tw - 6, 3, CAB1)                       # la franja de la empresa
    p.r(3, 5, tw - 6, 1, CAB0)
    p.p(0, 3, ROJO)
    p.p(0, 10, ROJO)
    p.r(tw, 6, 2, 2, OUT)                            # el enganche
    # la cabina
    x = tw + 1
    p.r(x, 2, cab - 1, 10, OUT)
    p.r(x + 1, 1, cab - 3, 12, OUT)
    p.r(x + 1, 3, cab - 3, 8, CAB1)
    p.r(x + 1, 3, cab - 3, 1, CAB0)
    p.r(x + 1, 9, cab - 3, 2, CAB2)
    p.r(x + 2, 4, 3, 5, CAB0)                        # el techo
    p.r(w - 4, 3, 2, 7, VIDRIO2)
    p.p(w - 4, 4, VIDRIOHI)
    p.p(w - 2, 4, LUZ)
    p.p(w - 2, 9, LUZ)
    _beam(p, w - 1, 4, 9, BEAM)


def _bus(p, w):
    p.r(2, 12, w - 1, 4, SOMBRA)
    _ruedas(p, (4, 11, w - 9), 0, 13)
    p.r(1, 1, w - 2, 12, OUT)
    p.r(0, 2, w, 10, OUT)
    p.r(1, 2, w - 2, 10, BUS1)
    p.r(1, 2, w - 2, 1, BUS0)
    p.r(1, 10, w - 2, 2, BUS2)
    for x in range(3, w - 6, 5):                     # las ventanas del costado
        p.r(x, 8, 4, 2, VIDRIO2)
        p.p(x, 8, VIDRIOHI)
    for x in (7, 22):                                # el aire acondicionado
        p.r(x, 3, 8, 4, TREN1)
        p.r(x, 3, 8, 1, TREN3)
        p.r(x + 1, 4, 6, 2, TREN2)
    p.r(w - 4, 3, 2, 8, VIDRIO2)
    p.p(w - 4, 4, VIDRIOHI)
    p.r(w - 8, 3, 3, 1, LUZ2)                        # el letrero del recorrido
    p.p(w - 1, 4, LUZ)
    p.p(w - 1, 9, LUZ)
    p.p(0, 4, ROJO)
    p.p(0, 9, ROJO)
    _beam(p, w, 4, 9, BEAM)


MOTO = [
    "........kkk.....",
    ".......kWWWk....",
    ".......kWWvv....",
    "......kjkWkk....",
    ".....kjJJk......",
    "....kjJJJJk.....",
    "...kkkJJkmmmkk..",
    "..kkhmmmmmmmmLk.",
    ".kOOkMMMMMMkOOk.",
    "kOooOkkkkkkOooOk",
    "kOooOk....kOooOk",
    ".kOOk......kOOk.",
    "..ssssssssssss..",
]
_MOTO_CM = {"k": "OUT", "W": "WHITE", "v": "VIDRIO2", "j": "TREN1",
            "J": "TREN0", "m": "MOT1", "M": "MOT2", "h": "MOT0", "O": "OUT",
            "o": "TREN1", "L": "LUZ", "s": "SOMBRA"}


def _grid(p, rows, cm):
    """un sprite escrito como texto: una letra por píxel, '.' es transparente."""
    g = globals()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                p.p(x, y, g[cm[ch]])


def _moto(p, w):
    _grid(p, MOTO, _MOTO_CM)


def _tren(p, w):
    loco = 32
    p.r(2, 14, w - 1, 4, SOMBRA)
    x = 0
    while x < w - loco - 2:
        cw = min(38, w - loco - 2 - x)
        p.r(x, 1, cw, 14, OUT)
        p.r(x + 1, 2, cw - 2, 12, TREN2)
        p.r(x + 1, 2, cw - 2, 2, TREN3)
        p.r(x + 1, 12, cw - 2, 2, TREN1)
        p.r(x + 1, 7, cw - 2, 3, VIDRIO)
        for wx in range(x + 3, x + cw - 4, 6):
            p.r(wx, 7, 4, 3, VIDRIO2)
            p.p(wx, 7, VIDRIOHI)
        p.r(x + 1, 10, cw - 2, 1, PINK)              # la franja
        p.r(x + 6, 4, 8, 2, TREN1)                   # rejillas del techo
        p.r(x + cw - 14, 4, 8, 2, TREN1)
        p.r(x + cw, 6, 2, 3, OUT)                    # el enganche
        x += cw + 2
    # la locomotora, roja, con la trompa redondeada
    x = w - loco
    p.r(x, 1, loco - 2, 14, OUT)
    p.r(x, 2, loco, 12, OUT)
    p.r(x + 1, 2, loco - 3, 12, CAB1)
    p.r(x + 1, 2, loco - 3, 2, CAB0)
    p.r(x + 1, 12, loco - 3, 2, CAB2)
    p.r(x + 1, 6, loco - 3, 2, TREN3)                # la franja blanca
    p.r(x + 4, 3, 10, 2, CAB2)
    p.r(w - 6, 3, 3, 9, VIDRIO2)
    p.p(w - 5, 4, VIDRIOHI)
    p.p(w - 6, 3, VIDRIOHI)
    p.r(w - 2, 6, 2, 3, LUZ)
    p.r(w - 13, 9, 6, 2, VIDRIO)


def _tronco(p, w, bajo):
    dy = 2 if bajo else 0
    body, top, sh = (TRONCODK, TRONCO, TRONCO0) if bajo else (TRONCO, TRONCOHI,
                                                               TRONCODK)
    p.r(1, 13 + dy, w - 1, 3, AGUA0)                 # su sombra en el agua
    p.r(1, 2 + dy, w - 2, 12, TRONCO0)
    p.r(0, 3 + dy, w, 10, TRONCO0)
    p.r(2, 3 + dy, w - 4, 10, body)
    p.r(2, 3 + dy, w - 4, 2, top)
    p.r(2, 10 + dy, w - 4, 3, sh)
    rng = _Rng(w * 31 + dy)
    for x in range(6, w - 7, 5):                     # la corteza
        p.r(x, 6 + dy + rng(3), 3 + rng(3), 1, sh)
        if rng(2):
            p.r(x + 1, 4 + dy, 2, 1, ANILLO if not bajo else TRONCOHI)
    for cx in (1, w - 4):                            # las puntas, cortadas
        p.r(cx, 4 + dy, 3, 8, ANILLO if not bajo else TRONCOHI)
        p.r(cx + 1, 6 + dy, 1, 4, TRONCOHI if not bajo else TRONCO)
    p.r(w // 3, 3 + dy, 5, 1, MUSGO)                 # musgo y una rama
    p.p(w // 3 + 1, 4 + dy, MUSGO)
    p.r(w * 2 // 3, 1 + dy, 2, 2, TRONCO0)
    p.p(w * 2 // 3, 1 + dy, TRONCODK)
    if bajo:                                         # el agua ya lo tapa
        p.r(0, 12, w, 4, AGUA1)
        for x in range(0, w, 3):
            p.p(x, 12, ESPUMA if x % 2 else AGUA3)
    else:
        p.p(0, 12, ESPUMA)
        p.p(w - 1, 12, ESPUMA)
        p.r(w // 2 - 2, 15, 4, 1, AGUA2)


def _cinta(p, w, k):
    p.r(2, 12, w - 1, 3, SOMBRA)                     # sombra en el pasto
    p.r(0, 1, w, 12, CINTA0)
    p.r(2, 2, w - 4, 10, CINTA1)
    p.r(2, 2, w - 4, 1, CINTA2)
    p.r(2, 10, w - 4, 2, CINTA3)
    for x in range(2 + k, w - 3, 4):                 # las tablillas, que corren
        p.r(x, 3, 1, 7, CINTA3)
    for cx in (w // 3, 2 * w // 3):                  # flechas fijas: para dónde
        for j in range(3):
            p.r(cx - 1 + j, 4 + j, 1, 1, WHITE)
            p.r(cx - 1 + j, 8 - j, 1, 1, WHITE)
            p.r(cx - 2 + j, 4 + j, 1, 1, CINTA2)
            p.r(cx - 2 + j, 8 - j, 1, 1, CINTA2)
    p.r(0, 2, 2, 10, CINTA3)                         # los rodillos
    p.r(w - 2, 2, 2, 10, CINTA3)
    p.r(0, 2, 2, 1, CINTA2)
    p.r(w - 2, 2, 2, 1, CINTA2)


def bake_sprites():
    """los sprites, una vez por proceso, en los bancos 0 y 1."""
    if SPR:
        return SPR
    a = _Atlas()
    _bake(a, "tren", 150, 18, _tren, 150)
    for w in (48, 56, 64):
        _bake(a, ("tronco", w, 0), w, 18, _tronco, w, False)
        _bake(a, ("tronco", w, 1), w, 18, _tronco, w, True)
    for w in (34, 44, 54):
        for k in range(4):
            _bake(a, ("cinta", w, k), w, 16, _cinta, w, k)
    for w in (16, 20, 24):
        for i, ramp in enumerate(AUTOS):
            _bake(a, ("auto", w, i), w + BEAM, 16, _auto, w, ramp)
    for w in (30, 36):
        _bake(a, ("camion", w), w + BEAM, 16, _camion, w)
    _bake(a, ("bus", 42), 42 + BEAM, 16, _bus, 42)
    _bake(a, ("moto", 11), 16, 13, _moto, 11)
    return SPR


def spr(key, x, y, flip=False):
    """estampa un sprite horneado. con `flip`, espejado (mira a la izquierda)."""
    bank, u, v, w, h = SPR[key]
    pyxel.blt(x, y, bank, u, v, -w if flip else w, h, 0)


# --- texturas ------------------------------------------------------------------
TW = 80            # ancho de un mosaico de textura
LH = 20            # alto de un carril (igual a LANE_H del juego)
_TEX = {}


def _tex_asfalto(img, v, ramp):
    d, m, l = ramp
    img.rect(0, v, TW, LH, m)
    rng = _Rng(v * 7 + 3)
    for _ in range(170):
        img.pset(rng(TW), v + rng(LH), d)
    for _ in range(70):
        img.pset(rng(TW), v + rng(LH), l)
    # las huellas de las ruedas: dos franjas apenas más oscuras
    img.dither(0.5)
    img.rect(0, v + 5, TW, 2, d)
    img.rect(0, v + 13, TW, 2, d)
    img.dither(1.0)


def _tex_pasto(img, v):
    img.rect(0, v, TW, LH, PASTO1)
    rng = _Rng(911)
    for _ in range(28):                              # manchones oscuros
        x, y = rng(TW), rng(LH)
        img.rect(x, v + y, 2 + rng(4), 1 + rng(2), PASTO0)
    for _ in range(150):                             # hojitas de pasto
        x, y = rng(TW), rng(LH - 2)
        img.pset(x, v + y, PASTO2)
        img.pset(x, v + y + 1, PASTO2)
        if rng(3) == 0:
            img.pset(x, v + y, PASTO3)
    for _ in range(5):                               # florcitas
        x, y = rng(TW), rng(LH)
        img.pset(x, v + y, (GOLD, PINK, WHITE)[rng(3)])


def _tex_baldosa(img, v):
    img.rect(0, v, TW, LH, VER0)
    rng = _Rng(77)
    for fila in range(2):
        off = 5 if fila else 0
        y = v + fila * 10
        for x in range(-off, TW, 10):
            c = (VER1, VER1, VER1, VER2, VER0)[rng(5)]
            img.rect(x + 1, y + 1, 9, 9, c)
            img.rect(x + 1, y + 1, 9, 1, VER2 if c != VER2 else VER3)
            img.rect(x + 1, y + 1, 1, 9, VER2 if c != VER2 else VER3)
            if rng(6) == 0:                           # una trizadura
                img.line(x + 3, y + 3, x + 6, y + 7, VER0)


def _tex_ripio(img, v):
    img.rect(0, v, TW, LH, BAL1)
    rng = _Rng(4242)
    for _ in range(260):
        img.pset(rng(TW), v + rng(LH), (BAL0, BAL2, BAL0)[rng(3)])


AGUA_P = 96        # período del agua: el mosaico se repite cada tantos px
AGUA_IMG = []


def _bake_agua():
    """dos cuadros de agua, periódicos en x, de ancho W + período: se estampan
    corridos para que fluya."""
    img = pyxel.Image(256 + AGUA_P, LH * 2)
    for f in range(2):
        v = f * LH
        img.rect(0, v, img.width, LH, AGUA1)
        img.dither(0.5)
        img.rect(0, v, img.width, 2, AGUA0)
        img.rect(0, v + LH - 3, img.width, 3, AGUA0)
        img.dither(1.0)
        rng = _Rng(55)
        olas = [(rng(AGUA_P), 2 + rng(LH - 5), 3 + rng(6)) for _ in range(16)]
        for x0, y0, n in olas:
            if f:
                x0 += 2
                n += rng(3) - 1
            for rep in range(0, img.width + AGUA_P, AGUA_P):
                x = x0 + rep
                img.rect(x, v + y0 + 1, n, 1, AGUA0)  # el valle de la ola
                img.rect(x, v + y0, n, 1, AGUA2)
                img.rect(x + n // 2, v + y0, max(1, n // 3), 1, AGUA3)
        for _ in range(6):                            # destellos sueltos
            x, y = rng(AGUA_P), rng(LH)
            for rep in range(0, img.width + AGUA_P, AGUA_P):
                if (x + y + f) % 2:
                    img.pset(x + rep, v + y, ESPUMA)
    AGUA_IMG.append(img)
    return img


def agua(x, y, off, f):
    if not AGUA_IMG:
        _bake_agua()
    pyxel.blt(x, y, AGUA_IMG[0], int(off) % AGUA_P, f * LH, 256, LH)


def _bake_tex():
    if _TEX:
        return _TEX
    keys = ["pasto", "baldosa", "ripio"] + list(ASFALTO)
    img = pyxel.Image(TW, LH * len(keys))
    for i, k in enumerate(keys):
        v = i * LH
        if k == "pasto":
            _tex_pasto(img, v)
        elif k == "baldosa":
            _tex_baldosa(img, v)
        elif k == "ripio":
            _tex_ripio(img, v)
        else:
            _tex_asfalto(img, v, ASFALTO[k])
        _TEX[k] = v
    _TEX["_img"] = img
    return _TEX


def _tile(dst, key, y, w, h=LH, sy=0):
    t = _bake_tex()
    for x in range(0, w, TW):
        dst.blt(x, y, t["_img"], 0, t[key] + sy, min(TW, w - x), h)


# --- los fondos de cada tramo ---------------------------------------------------
_BG = {}


def _tipo(letra):
    if letra in "TKBM":
        return "T"
    return letra


def _arbusto(img, x, y, r):
    """un arbusto redondo con luz arriba a la izquierda."""
    img.circ(x + 1, y + 2, r, SOMBRA)
    img.circ(x, y, r, HOJA0)
    img.circ(x, y, r - 1, HOJA1)
    img.circ(x - 1, y - 1, max(1, r - 2), HOJA2)
    img.pset(x - 2, y - 2, HOJA3)
    img.pset(x - 1, y - 2, HOJA3)


def _farol(img, x, y):
    """un farol visto de arriba: el poste y la ampolleta."""
    img.rect(x - 1, y - 1, 3, 3, POSTE)
    img.pset(x, y, LUZ)


def _baldosas(img, y, w, faroles, seed):
    """la vereda, baldosa por baldosa: las que caen bajo un farol salen más
    claras, así el charco de luz se ve hecho de baldosas y no de puntitos."""
    img.rect(0, y, w, LH, VER0)
    rng = _Rng(seed)
    for fila in range(2):
        off = 5 if fila else 0
        yy = y + fila * 10
        for x in range(-off, w, 10):
            cx, cy = x + 5, yy + 5
            luz = 0.0
            for lx, ly in faroles:
                luz = max(luz, 1 - ((cx - lx) / 34.0) ** 2 - ((cy - ly) / 16.0) ** 2)
            r = rng(6)
            if luz > 0.55:
                c, hi = VER3, CURB
            elif luz > 0.1:
                c, hi = VER2, VER3
            else:
                c, hi = (VER1, VER1, VER1, VER1, VER2, VER0)[r], VER2
                if c == VER2:
                    hi = VER3
            img.rect(x + 1, yy + 1, 9, 9, c)
            img.rect(x + 1, yy + 1, 9, 1, hi)
            img.rect(x + 1, yy + 1, 1, 9, hi)
            if rng(7) == 0:                             # una trizadura
                img.line(x + 3, yy + 3, x + 6, yy + 7, VER0)


def _orilla_agua(img, y, arriba):
    """la ribera: barro y matas. `arriba`: el agua queda encima de esta franja."""
    rng = _Rng(y * 13)
    if arriba:
        img.rect(0, y, 256, 1, SOMBRA)
        img.rect(0, y + 1, 256, 1, BARRO)
        img.rect(0, y + 2, 256, 1, BARRO2)
        for x in range(0, 256, 3):
            if rng(3):
                img.pset(x, y + 3, PASTO2)
            if rng(4) == 0:
                img.pset(x + 1, y + 2, PASTO3)
    else:
        img.rect(0, y - 3, 256, 1, BARRO2)
        img.rect(0, y - 2, 256, 1, BARRO)
        img.rect(0, y - 1, 256, 1, SOMBRA)
        for x in range(0, 256, 3):
            if rng(3):
                img.pset(x, y - 4, PASTO2)
            if rng(4) == 0:
                img.pset(x + 1, y - 3, PASTO3)


def bake_fondo(nombre, plano, W, H, hud, top):
    """la pantalla entera del tramo, sin nada que se mueva."""
    key = (nombre, plano)
    if key in _BG:
        return _BG[key]
    img = pyxel.Image(W, H)
    img.cls(BG)
    asf = nombre if nombre in ASFALTO else "BARRIO"
    d0, d1, d2 = ASFALTO[asf]
    tipos = [_tipo(c) for c in plano]
    n = len(tipos)
    bottom = top + n * LH
    # la meta: pasto con arbustos y la bandera a cuadros (la bandera se
    # estampa viva encima, porque cambia de color en la hora punta)
    _tile(img, "pasto", hud, W)
    for x in range(8, W, 26):
        _arbusto(img, x + (x * 7) % 9, hud + 4, 4)
    # los carriles
    for i, t in enumerate(tipos):
        y = top + i * LH
        arriba = tipos[i - 1] if i > 0 else "META"
        abajo = tipos[i + 1] if i + 1 < n else "ORILLA"
        if t == "T":
            _tile(img, asf, y, W)
            if abajo == "T":                          # la línea entre carriles
                for x in range(4, W, 14):
                    img.rect(x, y + LH - 1, 8, 1, LINEA)
            else:
                img.rect(0, y + LH - 1, W, 1, d0)
            if arriba != "T":
                img.rect(0, y, W, 1, d0)
                img.dither(0.5)
                img.rect(0, y + 1, W, 1, d0)
                img.dither(1.0)
        elif t == "V":
            fs = [(x, y + 3) for x in range(40 + i * 17 % 30, W, 96)]
            _baldosas(img, y, W, fs, i * 101 + len(nombre))
            img.rect(0, y, W, 1, CURB)                # las soleras
            img.rect(0, y + 1, W, 1, VER0)
            img.rect(0, y + LH - 2, W, 1, CURB)
            img.rect(0, y + LH - 1, W, 1, SOMBRA)
            for fx_, fy in fs:
                _farol(img, fx_, fy)
        elif t == "C":
            _tile(img, "pasto", y, W)
            if arriba == "T" or arriba == "META":
                pass
        elif t == "F":
            _tile(img, "ripio", y, W)
            for x in range(0, W, 7):                  # los durmientes
                img.rect(x, y + 3, 4, LH - 6, DURM)
                img.rect(x, y + 3, 4, 1, DURM2)
                img.rect(x + 3, y + 4, 1, LH - 7, BAL0)
            for ry in (y + 6, y + LH - 8):            # los rieles
                img.rect(0, ry, W, 2, RIEL)
                img.rect(0, ry, W, 1, RIELHI)
                img.rect(0, ry + 2, W, 1, BAL0)
            img.rect(0, y, W, 1, BAL0)
            img.rect(0, y + LH - 1, W, 1, BAL0)
        elif t == "A":
            img.rect(0, y, W, LH, AGUA1)
        # la ribera, dentro del carril seco que toca el agua
        if t != "A":
            if arriba == "A":
                _orilla_agua(img, y, True)
            if abajo == "A":
                _orilla_agua(img, y + LH, False)
        # el borde con la calle: una solera
        if t in ("C",) and abajo == "T":
            img.rect(0, y + LH - 2, W, 1, CURB)
            img.rect(0, y + LH - 1, W, 1, SOMBRA)
        if t in ("C",) and arriba == "T":
            img.rect(0, y, W, 1, CURB)
            img.rect(0, y + 1, W, 1, VER0)
    # la meta, si el primer carril es agua, tiene su ribera
    if tipos[0] == "A":
        _orilla_agua(img, top, False)
    # la orilla de abajo: la vereda de donde se sale
    fs = [(x, bottom + 4) for x in (30, 130, 210)]
    _baldosas(img, bottom, W, fs, 999)
    img.rect(0, bottom, W, 1, CURB)
    img.rect(0, bottom + 1, W, 1, VER0)
    if tipos[-1] == "A":
        _orilla_agua(img, bottom, True)
    for fx_, fy in fs:
        _farol(img, fx_, fy)
    # viñeta: los costados apenas más oscuros, para centrar la mirada
    for k, a in ((0, 0.5), (1, 0.35), (2, 0.2)):
        img.dither(a)
        img.rect(k, hud, 1, bottom + LH - hud, SHADOW)
        img.rect(W - 1 - k, hud, 1, bottom + LH - hud, SHADOW)
    img.dither(1.0)
    _BG[key] = img
    return img


_META = []


def bandera(y, W, climax):
    """la franja a cuadros de la llegada (dos versiones horneadas)."""
    if not _META:
        img = pyxel.Image(W, 16)
        for v, (a, b) in ((0, (WHITE, OUT)), (8, (GOLD, PINK))):
            for x in range(0, W, 4):
                for j in range(2):
                    img.rect(x, v + j * 4, 4, 4, a if ((x // 4) + j) % 2 else b)
            img.rect(0, v + 7, W, 1, SOMBRA)
        _META.append(img)
    pyxel.blt(0, y, _META[0], 0, 8 if climax else 0, W, 8)
