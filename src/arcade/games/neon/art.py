"""neón, el arte: paleta, sprites a mano y el fondo synthwave pre-dibujado.

los sprites chicos están escritos como texto (una letra por píxel, sólo la
mitad izquierda: se espejan solos) y se hornean una vez en el banco de
imágenes 0, cada uno con una copia blanca al lado para el destello del golpe.
así dibujar un enemigo o una bala es un solo `blt`, que es lo que deja tener
300 balas en pantalla a 60 fps en el teléfono.
"""
import pyxel

(BG, SKY1, SKY2, SKY3, SKY4, GRID, GRID2, SUN1, SUN2, SUN3, MOUNT, MOUNT_E,
 CYAN, CYAN_D, MAGENTA, MAG_D, WHITE, TXT, DIM, SHADOW, YELLOW, ORANGE, RED,
 GREEN, VIOLET, BLUE, PINK, HULL, HULL2, DEEP, STAR, GOLD) = range(32)

PAL = [
    0x0B0722, 0x160C3A, 0x24104F, 0x3A1462, 0x5E1A6E, 0x5A1F86, 0xB02FC0,
    0xFFD35C, 0xFF8B4A, 0xF23E86, 0x140A33, 0x2B7FC4,
    0x3BF4FF, 0x168FC0, 0xFF36D2, 0x9C1C9C, 0xFFFFFF, 0xE8E6FF, 0x9A90D0,
    0x04020C, 0xFFF27A, 0xFF9838, 0xFF3550, 0x5DFF8F, 0xA875FF, 0x2A47B8,
    0xFFB0F0, 0x2A2A5C, 0x4F5BA6, 0x080418, 0x7F8AD8, 0xFFC53A,
] + [0] * (256 - 32)

CM = {".": None, "k": SHADOW, "h": HULL, "H": HULL2, "c": CYAN, "C": CYAN_D,
      "m": MAGENTA, "M": MAG_D, "w": WHITE, "t": TXT, "y": YELLOW, "o": ORANGE,
      "r": RED, "g": GREEN, "v": VIOLET, "b": BLUE, "p": PINK, "d": DEEP,
      "G": GOLD, "s": STAR}

# --- sprites (mitad izquierda con la columna del centro; se espejan) ----------
SHIP = [
    "......w",
    ".....kc",
    ".....cw",
    "....kcw",
    "....kcb",
    "....cbd",
    "...kcbc",
    "..kmcCc",
    ".kmpcCw",
    "kmmMcCc",
    "mmMkkcC",
    "mMk..kc",
    "Mk...km",
    "k.....M",
]
DART = [
    "kk....",
    "kmk...",
    "kpmk..",
    ".kmmk.",
    ".kmMmk",
    "..kMmy",
    "..kmMw",
    "...kmk",
    "....kk",
]
WEAVER = [
    "k......",
    "vk...kk",
    "vvk.kvH",
    "kvvkvvh",
    ".kvvvpw",
    ".kvvvvc",
    "..kvkkv",
    "...k..k",
]
KAMI = [
    "....k",
    "...kr",
    "..kro",
    ".kroy",
    "kroyw",
    ".kroy",
    "..kro",
    "...kr",
    "...ko",
    "....y",
]
OPTION = [
    ".kk",
    "kmm",
    "mpw",
    "kmc",
    ".kk",
]
PELLET = [
    "..kk",
    ".kmm",
    "kmpw",
    "kmww",
]
FASTB = [
    "..kk",
    ".koo",
    "koyw",
    "koww",
]
ORB = [
    "...kkk",
    "..kvvv",
    ".kvmmm",
    "kvmmpp",
    "kvmpww",
    "kvmpww",
]
SHOT = [
    ".w",
    "cw",
    "cw",
    "cw",
    "Cc",
    ".C",
    ".C",
]
CRYS = [
    "..w",
    ".wy",
    "wyG",
    ".Go",
    "..o",
]
ITEM = [
    "..kkk",
    ".kgggg",
    "kggggg",
    "kggggg",
    "kggggg",
    "kggggg",
    "kggggg",
    "kggggg",
    ".kgggg",
    "..kkk",
]
LIFE = [
    "..c",
    ".kc",
    "kcw",
    "cCc",
    "c.c",
]


def _expand(rows, mirror=True, vflip_half=False):
    """las filas completas: la mitad izquierda + su espejo (sin repetir el
    centro). si `vflip_half`, las filas también se espejan hacia abajo (para
    las balas redondas, que se escriben sólo el cuarto de arriba)."""
    out = []
    for r in rows:
        out.append(r + r[-2::-1] if mirror else r)
    if vflip_half:
        out = out + out[-2::-1]
    return out


class Atlas:
    """reparte el banco 0 en estantes y hornea cada sprite (más su versión
    blanca) una sola vez por proceso."""

    def __init__(self, img):
        self.img = img
        self.x = self.y = 0
        self.row_h = 0
        img.cls(0)

    def _alloc(self, w, h):
        if self.x + w > 256:
            self.x, self.y = 0, self.y + self.row_h + 1
            self.row_h = 0
        u, v = self.x, self.y
        self.x += w + 1
        self.row_h = max(self.row_h, h)
        return u, v

    def bake(self, rows, flash=WHITE, **kw):
        full = _expand(rows, **kw)
        w, h = len(full[0]), len(full)
        u, v = self._alloc(w * 2 + 1, h)
        for y, row in enumerate(full):
            for x, ch in enumerate(row):
                c = CM[ch]
                if c is None:
                    continue
                self.img.pset(u + x, v + y, c)
                self.img.pset(u + w + 1 + x, v + y, flash)
        return (u, v, w, h)

    def recolor(self, spr, mapping):
        """otra copia de un sprite con colores cambiados (balas de otro color,
        el ítem de bomba en magenta)."""
        u0, v0, w, h = spr
        u, v = self._alloc(w * 2 + 1, h)
        for y in range(h):
            for x in range(w * 2 + 1):
                c = self.img.pget(u0 + x, v0 + y)
                self.img.pset(u + x, v + y, mapping.get(c, c))
        return (u, v, w, h)


SPR = {}


def bake_all():
    """hornea los sprites en el banco 0. idempotente por proceso."""
    if SPR:
        return SPR
    a = Atlas(pyxel.images[0])
    SPR["ship"] = a.bake(SHIP)
    SPR["dart"] = a.bake(DART)
    SPR["weaver"] = a.bake(WEAVER)
    SPR["kami"] = a.bake(KAMI)
    SPR["option"] = a.bake(OPTION)
    SPR["pellet"] = a.bake(PELLET, vflip_half=True)
    SPR["pellet2"] = a.recolor(SPR["pellet"], {PINK: WHITE, MAGENTA: PINK})
    SPR["fast"] = a.bake(FASTB, vflip_half=True)
    SPR["fast2"] = a.recolor(SPR["fast"], {YELLOW: WHITE})
    SPR["orb"] = a.bake(ORB, vflip_half=True)
    SPR["orb2"] = a.recolor(SPR["orb"], {MAGENTA: VIOLET, VIOLET: MAGENTA})
    SPR["shot"] = a.bake(SHOT)
    SPR["crys"] = a.bake(CRYS, vflip_half=False)
    SPR["item_p"] = a.bake(ITEM)
    SPR["item_b"] = a.recolor(SPR["item_p"], {GREEN: MAGENTA})
    SPR["life"] = a.bake(LIFE)
    return SPR


# --- el fondo ---------------------------------------------------------------
HY = 136                      # el horizonte
MOUNT_V = 140                 # dónde vive la cordillera en el banco 1
MOUNT_W = 230


_BG_DONE = []


def bake_background():
    """cielo y cordillera, una vez, en el banco 1. lo que se mueve (sol,
    grilla, estrellas que titilan) se dibuja en vivo."""
    if _BG_DONE:
        return
    _BG_DONE.append(1)
    img = pyxel.images[1]
    img.cls(0)
    # el cielo en franjas, con transiciones a rayas como en un monitor viejo
    bands = [(0, BG), (40, SKY1), (70, SKY2), (98, SKY3), (120, SKY4)]
    for i, (y0, col) in enumerate(bands):
        y1 = bands[i + 1][0] if i + 1 < len(bands) else HY
        img.rect(0, y0, 180, y1 - y0, col)
        if i:
            prev = bands[i - 1][1]
            for k in range(0, 6, 2):            # rayado de transición
                img.line(0, y0 + k, 179, y0 + k, prev)
    # estrellas fijas
    seed = 7
    for i in range(46):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        x = seed % 180
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        y = seed % 100
        img.pset(x, y, STAR if i % 3 else TXT)
    # la cordillera: dos capas de picos de alambre
    img.rect(0, MOUNT_V, MOUNT_W, 40, 0)
    peaks_back = [(0, 26), (18, 14), (34, 22), (52, 8), (70, 20), (88, 30),
                  (106, 30), (126, 18), (142, 6), (160, 20), (178, 12),
                  (196, 24), (214, 10), (230, 22)]
    peaks_front = [(0, 30), (14, 22), (30, 30), (44, 18), (60, 30),
                   (150, 30), (166, 16), (182, 28), (198, 20), (214, 30),
                   (230, 26)]
    base = MOUNT_V + 32
    for peaks, fill, edge in ((peaks_back, SKY1, MOUNT_E),
                              (peaks_front, MOUNT, CYAN_D)):
        for (x0, y0), (x1, y1) in zip(peaks, peaks[1:]):
            img.tri(x0, MOUNT_V + y0, x1, MOUNT_V + y1, x0, base, fill)
            img.tri(x1, MOUNT_V + y1, x1, base, x0, base, fill)
        for (x0, y0), (x1, y1) in zip(peaks, peaks[1:]):
            img.line(x0, MOUNT_V + y0, x1, MOUNT_V + y1, edge)


def img_text(img, x, y, s, col):
    """pxtext.text pero sobre una imagen (para los carteles grandes)."""
    acute = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
             "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}
    tilde = {"ñ": "n", "Ñ": "N"}
    base, marks = [], []
    for i, ch in enumerate(s):
        if ch in acute:
            base.append(acute[ch]); marks.append((i, 0))
        elif ch in tilde:
            base.append(tilde[ch]); marks.append((i, 1))
        elif ch == "¡":
            base.append("!"); marks.append((i, 2))
        elif ch == "¿":
            base.append("?"); marks.append((i, 3))
        else:
            base.append(ch)
    img.text(x, y, "".join(base), col)
    for i, kind in marks:
        gx = x + i * 4
        if kind == 0:
            img.pset(gx + 2, y - 3, col)
            img.pset(gx + 1, y - 2, col)
        elif kind == 1:
            img.pset(gx, y - 2, col)
            img.pset(gx + 1, y - 3, col)
            img.pset(gx + 2, y - 2, col)
        else:
            # ¡ y ¿: el signo normal dado vuelta (borramos y redibujamos)
            img.rect(gx, y, 4, 6, 0)
            if kind == 2:
                img.pset(gx + 1, y, col)
                img.rect(gx + 1, y + 2, 1, 3, col)
            else:
                img.pset(gx + 1, y, col)
                img.pset(gx + 1, y + 2, col)
                img.pset(gx, y + 3, col)
                img.pset(gx, y + 4, col)
                img.rect(gx + 1, y + 4, 2, 1, col)
