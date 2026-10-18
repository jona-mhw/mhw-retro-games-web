"""esquiva, el arte: paleta con rampas, sprites horneados y el espacio de fondo.

la identidad de esquiva es otra que la de neón: acá no hay sol synthwave ni
grilla, hay **espacio profundo** (una nebulosa verde azulada, un planeta con
anillo que pasa lento durante la partida) y lo que cae son **bloques**:
cajones naranjos con bisel, muros morados blindados, flechas coral que
zigzaguean y buscadores menta. la nave es verde lima.

los sprites se escriben como texto (una letra por píxel) o se dibujan con
rects, y se hornean una vez en los bancos 0 y 1: dibujar un bloque con su
bisel y su sombra es un solo `blt`. el fondo lejano (degradé y nebulosa) se
hornea en una imagen del alto de la pantalla y se estampa corrido para que
avance; las estrellas de las capas cercanas se dibujan vivas, son pocas.
"""
import math

import pyxel

_PAL = [
    ("BG", 0x060910), ("SHADOW", 0x03050A), ("OUT", 0x080A14),
    ("WHITE", 0xF2F5FB), ("TXT", 0xE8ECF5), ("DIM", 0x7A86A8),
    # la nave
    ("SHIP3", 0xE4FF9A), ("SHIP2", 0xB6F03C), ("SHIP1", 0x7FBE2A),
    ("SHIP0", 0x3E6A16), ("GL0", 0x0E2A3A), ("GL1", 0x2A7A9A),
    ("GL2", 0xA8F0FA),
    # bloques: naranjo, coral, morado, menta
    ("RK3", 0xFFC27A), ("RK2", 0xF08A3A), ("RK1", 0xC4581F), ("RK0", 0x6E2810),
    ("ZG3", 0xFFB4A4), ("ZG2", 0xFF7464), ("ZG1", 0xD0443A), ("ZG0", 0x701A18),
    ("HD3", 0xE4CCFF), ("HD2", 0xBE96F0), ("HD1", 0x8456CC), ("HD0", 0x40246E),
    ("SK3", 0xCCFFE4), ("SK2", 0x5CF0A0), ("SK1", 0x24A464), ("SK0", 0x105434),
    # gemas, tiros, poderes
    ("GM3", 0xEAFDFF), ("GM2", 0xA8F0FA), ("GM1", 0x3AC6D8), ("GM0", 0x17607E),
    ("SHOT", 0xFFF3B0), ("GOLD", 0xFFD24A), ("GOLDDK", 0xA8741E),
    ("LASER", 0xFF5A3C), ("LASER2", 0xFFB07A), ("LASERDK", 0x8A1E1A),
    ("MAG3", 0xFFB0EE), ("MAG2", 0xF060D0), ("MAG1", 0xB02A98), ("MAG0", 0x58104C),
    ("HEART", 0xFF4D6A), ("HEARTDK", 0x8A1E36), ("SHIELD", 0x7ADCFF),
    ("SLOWC", 0x4DA6FF), ("WARN", 0xFF4A2E), ("ACCENT", 0xA6E83A),
    # el marcador
    ("PANEL", 0x0C1220), ("PANEL2", 0x162036), ("EDGE", 0x2A3A5A),
    # el espacio
    ("SP0", 0x060910), ("SP1", 0x0A1020), ("SP2", 0x0D172C), ("SP3", 0x122038),
    ("NB0", 0x0C2632), ("NB1", 0x14404C), ("NB2", 0x1E1A40), ("NB3", 0x34285A),
    ("STAR", 0x6A7AA0), ("STAR2", 0x2A3350), ("STAR3", 0xD0DCF8),
    ("PLA0", 0x0C1826), ("PLA1", 0x162C44), ("PLA2", 0x264A68),
    ("PLA3", 0x4A7E98), ("RG0", 0x4A3C30), ("RG1", 0x8A6C4E), ("RG2", 0xCCAA80),
    ("FL0", 0xFFF6C0), ("FL1", 0xFFB040), ("FL2", 0xE0402A),
]
globals().update({n: i for i, (n, _) in enumerate(_PAL)})
PAL = [c for _, c in _PAL] + [0] * (256 - len(_PAL))

CM = {".": None, "k": OUT, "3": SHIP3, "2": SHIP2, "1": SHIP1, "0": SHIP0,
      "b": GL0, "g": GL1, "G": GL2, "e": FL1, "r": FL2, "w": WHITE,
      "y": SHOT, "o": GOLD, "m": MAG2, "M": MAG1, "p": MAG3, "d": MAG0,
      "c": GM1, "C": GM0, "h": GM2, "H": GM3, "s": SHADOW}

# la nave: mitad izquierda, se espeja entera (24 de ancho)
NAVE = [
    "..........k3",
    ".........k32",
    ".........k22",
    "........k2bg",
    "........k2gG",
    ".k......k2gg",
    "k3k.....k21b",
    "k2k...kk2211",
    "k2k.kk222211",
    "k2kk22221111",
    "k21222111110",
    "k11111110000",
    ".k00kkk0k0er",
    "..kk...kkkkk",
]
GEMA = [
    "....k....",
    "...kHk...",
    "..kHhck..",
    ".kHhhcck.",
    "kHhhcccCk",
    ".kccccCk.",
    "..kccCk..",
    "...kCk...",
    "....k....",
]
# las balas del núcleo: un orbe con contorno, núcleo blanco (cuarto de arriba
# a la izquierda; se espeja a los cuatro lados)
BALA = [
    "...kk",
    "..kMM",
    ".kMmm",
    "kMmpp",
    "kMmpw",
]


def _mirror(rows):
    return [r + r[::-1] for r in rows]


def _mirror4(rows):
    full = [r + r[-2::-1] for r in rows]
    return full + full[-2::-1]


class _Pen:
    """dibuja dentro de la celda (u, v, bw, bh) de un banco: lo que se sale
    se recorta, así un sprite no pisa al vecino."""

    def __init__(self, img, u, v, bw=256, bh=256):
        self.img, self.u, self.v, self.bw, self.bh = img, u, v, bw, bh

    def r(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.bw, x + w), min(self.bh, y + h)
        if x1 > x0 and y1 > y0:
            self.img.rect(self.u + x0, self.v + y0, x1 - x0, y1 - y0, c)

    def p(self, x, y, c):
        if 0 <= x < self.bw and 0 <= y < self.bh:
            self.img.pset(self.u + x, self.v + y, c)

    def grid(self, rows, x=0, y=0, cm=CM):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                c = cm.get(ch)
                if c is not None:
                    self.p(x + i, y + j, c)


class _Atlas:
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
SOMBRA_D = (3, 4)          # la sombra de lo que cae, corrida abajo a la derecha


def _bake(a, key, w, h, fn, *args):
    bank, u, v = a.alloc(w, h)
    fn(_Pen(pyxel.images[bank], u, v, w, h), *args)
    SPR[key] = (bank, u, v, w, h)


def _bloque(p, w, h, ramp, deco):
    """un bloque con bisel: luz arriba a la izquierda, sombra abajo a la
    derecha, contorno oscuro y su sombra proyectada sobre el espacio."""
    l3, l2, l1, l0 = ramp
    sx, sy = SOMBRA_D
    p.r(sx, sy, w, h, SHADOW)
    p.r(0, 0, w, h, OUT)
    p.r(1, 1, w - 2, h - 2, l2)
    p.r(1, 1, w - 2, 1, l3)
    p.r(1, 1, 1, h - 2, l3)
    p.r(1, h - 3, w - 2, 2, l1)
    p.r(w - 2, 2, 1, h - 4, l1)
    p.p(1, h - 2, l1)
    p.p(2, 2, WHITE)
    if deco == "caja":                   # un panel hundido y remaches
        p.r(4, 4, w - 8, h - 8, l1)
        p.r(5, 5, w - 10, h - 10, l2)
        p.r(4, 4, w - 8, 1, l0)
        for x in (3, w - 4):
            p.p(x, 3, l3)
            p.p(x, h - 4, l0)
    elif deco == "duro":                 # placas cruzadas y remaches
        p.r(1, h // 2 - 1, w - 2, 2, l1)
        p.r(1, h // 2 - 1, w - 2, 1, l0)
        for x in range(3, w - 2, 5):
            p.p(x, 3, l3)
            p.p(x, h - 4, l3)
            p.p(x + 1, 4, l0)
    elif deco == "roto":                 # el mismo duro, trizado
        p.r(1, h // 2 - 1, w - 2, 1, l0)
        x = 2
        y = 2
        while x < w - 3:
            p.p(x, y, l0)
            p.p(x + 1, y, WHITE if x % 7 == 0 else l0)
            x += 2
            y = 2 + (x // 3) % (h - 4)
        for x in range(3, w - 2, 6):
            p.p(x, h - 4, l3)
    elif deco == "zig":                  # flechas: hacia dónde rebota
        cy = h // 2
        for j in range(3):
            p.r(3 + j, cy - 2 + j, 1, 1, WHITE)
            p.r(3 + j, cy + 2 - j, 1, 1, WHITE)
            p.r(w - 4 - j, cy - 2 + j, 1, 1, WHITE)
            p.r(w - 4 - j, cy + 2 - j, 1, 1, WHITE)
        p.r(w // 2 - 1, 2, 2, h - 4, l1)


def _buscador(p, w, h):
    """un rombo menta con contorno y sombra; el ojo se dibuja vivo."""
    sx, sy = SOMBRA_D
    cx = w // 2
    for capa, (dx, dy, col) in enumerate(((sx, sy, SHADOW), (0, 0, OUT))):
        for y in range(h):
            half = cx - abs(y - (h - 1) / 2) * cx / ((h - 1) / 2)
            hw = int(round(half))
            p.r(dx + cx - hw, dy + y, hw * 2 + 1, 1, col)
    for y in range(1, h - 1):
        half = cx - abs(y - (h - 1) / 2) * cx / ((h - 1) / 2) - 1
        hw = int(round(half))
        if hw < 0:
            continue
        p.r(cx - hw, y, hw * 2 + 1, 1, SK2)
        p.r(cx - hw, y, 1, 1, SK3)
        if y > h // 2:
            p.r(cx - hw, y, hw * 2 + 1, 1, SK1)
            p.r(cx + hw, y, 1, 1, SK0)
    p.r(cx - 2, h // 2 - 2, 5, 5, SK0)     # la cuenca del ojo


def _gema(p, frame):
    p.grid(GEMA, 0, 0)
    if frame:
        p.p(3, 3, WHITE)
        p.p(4, 2, WHITE)
        p.p(2, 4, WHITE)


def _nave(p):
    p.grid(_mirror(NAVE))


def _nave_blanca(p):
    rows = _mirror(NAVE)
    cm = {k: (WHITE if v is not None and k != "k" else v) for k, v in CM.items()}
    p.grid(rows, cm=cm)


def _bala(p, frame):
    rows = _mirror4(BALA)
    if frame:
        cm = dict(CM, m=LASER, M=LASERDK, p=LASER2)
    else:
        cm = CM
    p.grid(rows, cm=cm)


def _tiro(p):
    """el tiro de la nave: un trazo dorado con punta blanca."""
    p.r(0, 2, 3, 7, GOLDDK)
    p.r(1, 0, 1, 9, SHOT)
    p.p(1, 0, WHITE)
    p.p(1, 1, WHITE)
    p.r(0, 2, 1, 3, GOLD)
    p.r(2, 2, 1, 3, GOLD)


def _muro(p, w, h):
    """el muro: blindaje morado con franjas de peligro arriba y abajo."""
    sx, sy = SOMBRA_D
    p.r(sx, sy, w, h, SHADOW)
    p.r(0, 0, w, h, OUT)
    p.r(1, 1, w - 2, h - 2, HD1)
    for y0 in (1, h - 5):                 # franjas amarillas y negras
        p.r(1, y0, w - 2, 4, GOLD)
        for x in range(-4, w, 8):
            for j in range(4):
                p.r(x + j + 1, y0 + j, 4, 1, OUT)
    p.r(1, 1, w - 2, 1, GOLD)
    p.r(1, h - 2, w - 2, 1, GOLDDK)
    p.r(0, 0, 1, h, OUT)
    p.r(w - 1, 0, 1, h, OUT)
    # el blindaje, en placas con bisel
    for x in range(2, w - 2, 15):
        pw = min(14, w - 2 - x)
        p.r(x, 6, pw, h - 12, HD2)
        p.r(x, 6, pw, 1, HD3)
        p.r(x, h - 7, pw, 1, HD0)
        p.r(x + pw - 1, 6, 1, h - 12, HD0)
        p.p(x + 2, 8, HD3)
        p.p(x + pw - 3, h - 9, HD0)


def _planeta(img, r):
    """un planeta con anillo, de noche: casi todo en sombra y el borde
    iluminado arriba a la izquierda."""
    cx = cy = r + 12
    img.cls(0)
    # el anillo de atrás
    img.elli(cx - r - 12, cy - 6, 2 * r + 24, 12, RG0)
    img.elli(cx - r - 8, cy - 4, 2 * r + 16, 8, 0)
    img.circ(cx, cy, r, PLA0)
    img.circ(cx - 2, cy - 2, r - 2, PLA1)
    img.circ(cx - 5, cy - 5, r - 7, PLA1)
    # franjas de nubes
    for k, y in enumerate(range(cy - r + 6, cy + r - 4, 7)):
        half = int(math.sqrt(max(0, r * r - (y - cy) ** 2))) - 2
        img.dither(0.5)
        img.rect(cx - half, y, half * 2, 2, PLA2 if k % 2 else PLA0)
        img.dither(1.0)
    # el borde iluminado (una luna creciente)
    for a in range(200, 320, 3):
        t = math.radians(a)
        for d in (0, 1):
            x = int(cx + math.cos(t) * (r - d))
            y = int(cy + math.sin(t) * (r - d))
            img.pset(x, y, PLA3 if d == 0 else PLA2)
    # el anillo de adelante, sobre el planeta
    for a in range(0, 181, 2):
        t = math.radians(a)
        for rr, col in ((r + 12, RG1), (r + 9, RG2), (r + 6, RG0)):
            x = int(cx + math.cos(t) * rr)
            y = int(cy + math.sin(t) * rr * 0.22)
            img.pset(x, y, col)


def bake_sprites():
    if SPR:
        return SPR
    a = _Atlas()
    _bake(a, "nave", 24, 14, _nave)
    _bake(a, "nave_w", 24, 14, _nave_blanca)
    for w in (14, 18, 26):
        dx, dy = SOMBRA_D
        for key, ramp, deco in (("roca", (RK3, RK2, RK1, RK0), "caja"),
                                ("zig", (ZG3, ZG2, ZG1, ZG0), "zig"),
                                ("dura", (HD3, HD2, HD1, HD0), "duro"),
                                ("dura1", (HD2, HD1, HD0, OUT), "roto")):
            _bake(a, (key, w), w + dx, 12 + dy, _bloque, w, 12, ramp, deco)
    _bake(a, ("busca", 13), 13 + 3, 12 + 4, _buscador, 13, 12)
    for f in range(2):
        _bake(a, ("gema", f), 9, 9, _gema, f)
        _bake(a, ("bala", f), 9, 9, _bala, f)
    _bake(a, "tiro", 3, 9, _tiro)
    _bake(a, "muro", 90 + 3, 22 + 4, _muro, 90, 22)
    return SPR


def spr(key, x, y):
    bank, u, v, w, h = SPR[key]
    pyxel.blt(int(x), int(y), bank, u, v, w, h, 0)


# --- el fondo ---------------------------------------------------------------
_FONDO = []


class _Rng:
    def __init__(self, seed):
        self.s = seed

    def __call__(self, n):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s >> 8) % n


def bake_fondo(W, H):
    """el espacio lejano: degradé en franjas, nubes de nebulosa y estrellas
    fijas. es periódico en y (se estampa dos veces, corrido)."""
    if _FONDO:
        return _FONDO[0]
    img = pyxel.Image(W, H)
    bands = ((0, SP0), (0.30, SP1), (0.55, SP2), (0.80, SP3))
    for i, (f, col) in enumerate(bands):
        y0 = int(f * H)
        y1 = int(bands[i + 1][0] * H) if i + 1 < len(bands) else H
        img.rect(0, y0, W, y1 - y0, col)
        if i:
            prev = bands[i - 1][1]
            for a in (0.75, 0.5, 0.25):          # transición tramada
                img.dither(a)
                img.rect(0, y0 + int((0.75 - a) * 16), W, 4, prev)
            img.dither(1.0)
    # el borde de abajo vuelve a SP0 para que el corte del período no se vea
    for a, k in ((0.25, 40), (0.5, 24), (0.75, 10)):
        img.dither(a)
        img.rect(0, H - k, W, k, SP0)
    img.dither(1.0)
    # nebulosa: nubes de óvalos tramados, verde azulado y violeta
    rng = _Rng(31337)
    for col, n, alfa in ((NB0, 9, 0.4), (NB2, 6, 0.35), (NB1, 6, 0.25),
                         (NB3, 3, 0.22)):
        for _ in range(n):
            x, y = rng(W), 30 + rng(H - 60)
            rw, rh = 30 + rng(60), 14 + rng(30)
            img.dither(alfa)
            img.elli(x - rw // 2, y - rh // 2, rw, rh, col)
            img.dither(alfa * 0.6)
            img.elli(x - rw, y - rh, rw * 2, rh * 2, col)
    img.dither(1.0)
    for i in range(70):                          # estrellas lejanas
        x, y = rng(W), rng(H)
        img.pset(x, y, STAR2 if i % 4 else STAR)
    _FONDO.append(img)
    return img


_PLANETA = []


def planeta(x, y):
    if not _PLANETA:
        img = pyxel.Image(96, 96)
        _planeta(img, 34)
        _PLANETA.append(img)
    pyxel.blt(int(x), int(y), _PLANETA[0], 0, 0, 96, 96, 0)
