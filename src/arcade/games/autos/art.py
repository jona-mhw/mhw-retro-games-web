"""autos, el arte: paleta, ciudad horneada y autos pre-rotados.

nada de esto toca la lógica: la ciudad (City) dice qué tile es qué, y acá se
decide cómo se ve. todo lo estático se pinta UNA vez en imágenes de pyxel y
después se estampa con blt, que es lo que deja dibujar una ciudad con
veredas, techos con volumen y sombras a 60 fps en el teléfono.

- **la paleta** tiene rampas de 3-4 tonos por material y, para cada color, su
  "gemelo en sombra" (más oscuro y un poco azulado). las sombras de los
  edificios se hornean traduciendo los bytes de la imagen con esa tabla: una
  sombra que cae sobre vereda queda vereda en sombra, la que cae sobre pasto,
  pasto en sombra, sin dither.
- **los autos** se dibujan a mano mirando a la derecha y se pre-rotan a 64
  ángulos la primera vez que se usan. después de rotar se les pone luz de
  pantalla (borde de arriba-izquierda más claro, de abajo-derecha más oscuro)
  y un contorno oscuro: así el brillo no gira con el auto.
"""
import math
import random

import pyxel

# --- paleta -----------------------------------------------------------------
_BASE = [
    ("BG", 0x0B0D13), ("SHADOW", 0x07080D), ("OUTLINE", 0x0F1119),
    ("WHITE", 0xF4F6FB), ("TXT", 0xE6EAF2), ("DIM", 0x7A84A0),
    ("PANEL", 0x121624), ("PANEL2", 0x1C2234), ("PANEL3", 0x2A3248),
    ("ACCENT", 0x9BE03A),
    # asfalto y marcas
    ("AS0", 0x23262D), ("ASPHALT", 0x2E3239), ("AS2", 0x393D46), ("AS3", 0x454A54),
    ("LINEW", 0xD3D7DE), ("LINE", 0xD8A92A), ("LINED", 0x6E727A),
    # vereda
    ("SW0", 0x596070), ("SWJ", 0x6E7584), ("SIDE", 0x7E8592), ("SIDE2", 0x959CA8),
    ("CURB", 0xBAC0C9),
    # plaza
    ("GRASS0", 0x2B5426), ("GRASS1", 0x3A6E31), ("GRASS2", 0x4B883D),
    ("GRASS3", 0x66A44F), ("TREEDK", 0x1B3F20), ("TREE1", 0x2A612F),
    ("TREETOP", 0x3E8437), ("TREELT", 0x69B04F), ("TRUNK", 0x6B4A2A),
    ("PATH0", 0x9A8762), ("PATH1", 0xB9A57C), ("FLOW1", 0xE24A6C), ("FLOW2", 0xF2C84A),
    ("WATER0", 0x225089), ("WATER", 0x3A80C0), ("WATER2", 0x76C0EC),
    # techos: 5 materiales x (pared oscura, pared, techo, borde con luz)
    ("C0", 0x434756), ("C1", 0x626878), ("C2", 0x858B9A), ("C3", 0xACB2BF),
    ("K0", 0x582B24), ("K1", 0x844533), ("K2", 0xA6634B), ("K3", 0xC98A67),
    ("T0", 0x1E414F), ("T1", 0x2B6375), ("T2", 0x458797), ("T3", 0x75B1BD),
    ("S0", 0x68553B), ("S1", 0x937A5B), ("S2", 0xB69C75), ("S3", 0xD7C096),
    ("P0", 0x36304B), ("P1", 0x50486B), ("P2", 0x6A628B), ("P3", 0x8D85AD),
    # ventanas, vidrio y fierros
    ("WIN", 0x182030), ("WINLIT", 0xFFE39A), ("GLASS", 0x9EE2FA), ("GLASS0", 0x2A5878),
    ("GLASS1", 0x3F86B0),
    ("MET0", 0x525864), ("MET1", 0x848B97), ("MET2", 0xC3C9D2),
    # autos
    ("CAR0", 0x761812), ("CARBODY", 0xD6372A), ("CARROOF", 0xF2684A), ("CAR3", 0xFFB39A),
    ("COPD", 0x0E1838), ("COP1", 0x213D8C), ("COPL", 0x4A6CC8),
    ("COP2", 0xDCE3F0), ("COPWD", 0x9AA6BE),
    ("HEAD", 0xFFF2A8), ("TAIL", 0x9A1620), ("LIGHTR", 0xFF3B30), ("LIGHTB", 0x4DA6FF),
    # peatones
    ("SKIN", 0xE8B48A), ("SKIN0", 0xB27C59), ("HAIR", 0x3A2618),
    ("PED1", 0xD8483A), ("PED2", 0x4A78D8), ("PED3", 0xE7C13B), ("PED4", 0x6CC04A),
    # jugo
    ("SMOKE1", 0x7A8290), ("SMOKE2", 0x454C5A), ("SPARK1", 0xFFF3B0),
    ("SPARK2", 0xFFA23A), ("SPARK3", 0xE0402A), ("NITRO1", 0x7ADCFF), ("NITRO2", 0x2E7FBF),
    ("GOLD", 0xFFD24A), ("GOLD0", 0xB5841C), ("ORANGE", 0xFF8C1A), ("MAGENTA", 0xD84AB8),
    ("BILL0", 0x1E6636), ("BILL", 0x3FA65C), ("BILL2", 0x9BE88A),
    # radar, huellas, helicóptero
    ("MAPBG", 0x151925), ("MAPRD", 0x3A4152), ("MAPGR", 0x2B5730), ("SKID", 0x1B1E24),
    ("HELI0", 0x161D2E), ("HELI1", 0x2C3A5A), ("HELI2", 0x4E628C),
]
# cada nombre de la lista queda como constante del módulo con su índice
# (BG = 0, SHADOW = 1, ...): game.py los importa por nombre
for _i, (_n, _c) in enumerate(_BASE):
    globals()[_n] = _i
NBASE = len(_BASE)


def _sombra(c):
    """el gemelo en sombra: más oscuro y apenas azul (la luz del cielo)."""
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    r, g, b = int(r * 0.55), int(g * 0.58), int(b * 0.68 + 6)
    return (min(255, r) << 16) | (min(255, g) << 8) | min(255, b)


PAL = [c for _, c in _BASE] + [_sombra(c) for _, c in _BASE]
assert len(PAL) <= 256, len(PAL)
PAL += [0] * (256 - len(PAL))
# tabla para bytes.translate: cada color -> su gemelo en sombra
SHMAP = bytes([(i + NBASE) if i < NBASE else i for i in range(256)])


def sh(col):
    """el índice del gemelo en sombra de un color."""
    return col + NBASE if col < NBASE else col


ROOFS = ((C0, C1, C2, C3), (K0, K1, K2, K3), (T0, T1, T2, T3),
         (S0, S1, S2, S3), (P0, P1, P2, P3))

TILE = 16


# --- la ciudad, horneada ---------------------------------------------------
def _shade_rect(mv, iw, ih, x, y, w, h):
    """oscurece un rectángulo de la imagen traduciendo sus bytes (en C)."""
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(iw, int(x + w)), min(ih, int(y + h))
    if x1 <= x0:
        return
    for yy in range(y0, y1):
        a = yy * iw
        mv[a + x0:a + x1] = bytes(mv[a + x0:a + x1]).translate(SHMAP)


def _shade_circ(mv, iw, ih, cx, cy, rx, ry):
    """una sombra elíptica (la de un árbol o un tanque)."""
    for dy in range(-ry, ry + 1):
        hw = int(rx * math.sqrt(max(0.0, 1 - (dy / (ry + 0.5)) ** 2)))
        _shade_rect(mv, iw, ih, cx - hw, cy + dy, hw * 2 + 1, 1)


_CITY = {}


def city_image(city, B, kinds):
    """la ciudad entera en una imagen. se hornea una sola vez por sesión (la
    ciudad sale siempre igual), así una partida nueva no la vuelve a pintar."""
    hit = _CITY.get("img")
    if hit is not None:
        return hit
    ROAD, SIDEWALK, GRASS, TREE, FOUNT, BLD = kinds
    mw, mh = city.mw, city.mh
    iw, ih = mw * TILE, mh * TILE
    img = pyxel.Image(iw, ih)
    mv = memoryview(img.data_ptr()).cast("B")
    rng = random.Random(4471)
    t = city.tile

    # 1) el piso: asfalto, vereda, pasto
    for ty in range(mh):
        for tx in range(mw):
            px, py = tx * TILE, ty * TILE
            k = t(tx, ty)
            if k == ROAD:
                img.rect(px, py, TILE, TILE, ASPHALT)
                for _ in range(9):
                    img.pset(px + rng.randrange(TILE), py + rng.randrange(TILE),
                             AS0 if rng.random() < 0.6 else AS2)
            elif k in (SIDEWALK, FOUNT):
                img.rect(px, py, TILE, TILE, SIDE)
                # baldosas: juntas cada 8 px y alguna más clara
                img.rect(px, py + 7, TILE, 1, SWJ)
                img.rect(px + 7, py, 1, TILE, SWJ)
                if rng.random() < 0.35:
                    img.rect(px + rng.choice((0, 8)), py + rng.choice((0, 8)), 7, 7, SIDE2)
            elif k in (GRASS, TREE):
                img.rect(px, py, TILE, TILE, GRASS1)
                for _ in range(10):
                    img.pset(px + rng.randrange(TILE), py + rng.randrange(TILE),
                             rng.choice((GRASS0, GRASS2, GRASS2, GRASS3)))
            else:
                img.rect(px, py, TILE, TILE, SW0)       # el suelo bajo los edificios

    # 2) las calles: líneas, cebras, tapas y manchas
    for ty in range(mh):
        for tx in range(mw):
            if t(tx, ty) != ROAD:
                continue
            px, py = tx * TILE, ty * TILE
            rc, rr = tx % B, ty % B
            vert, horiz = rc < 2, rr < 2
            if vert and not horiz:
                lx = px + (TILE - 1 if rc == 0 else -1)
                if rr in (2, B - 1):
                    zy = py + (1 if rr == 2 else TILE - 11)
                    if rc == 0:
                        for i in range(2, 2 * TILE - 2, 5):
                            img.rect(px + i, zy, 3, 10, LINEW)
                else:
                    if rc == 0:
                        for yy in range(py, py + TILE):
                            if (yy // 6) % 2 == 0:
                                img.rect(lx, yy, 2, 1, LINE)
            elif horiz and not vert:
                ly = py + (TILE - 1 if rr == 0 else -1)
                if rc in (2, B - 1):
                    zx = px + (1 if rc == 2 else TILE - 11)
                    if rr == 0:
                        for i in range(2, 2 * TILE - 2, 5):
                            img.rect(zx, py + i, 10, 3, LINEW)
                else:
                    if rr == 0:
                        for xx in range(px, px + TILE):
                            if (xx // 6) % 2 == 0:
                                img.rect(xx, ly, 1, 2, LINE)
            elif vert and horiz and rc == 1 and rr == 1 and rng.random() < 0.5:
                img.circ(px, py, 3, AS0)                  # tapa en el cruce
                img.circb(px, py, 3, AS3)
                img.pset(px - 1, py - 1, AS2)
            if rng.random() < 0.10:                       # una mancha de aceite
                ox, oy = px + rng.randrange(3, 12), py + rng.randrange(3, 12)
                img.circ(ox, oy, rng.choice((1, 2)), AS0)

    # 2b) las rampas, con su sombra hacia abajo-derecha
    for (tx, ty), eje in city.ramps.items():
        rampa(img, tx * TILE, ty * TILE, eje)

    # 3) cordón: donde la vereda toca la calle, borde claro y sombra en el asfalto
    for ty in range(mh):
        for tx in range(mw):
            if t(tx, ty) not in (SIDEWALK, GRASS, TREE, FOUNT):
                continue
            px, py = tx * TILE, ty * TILE
            if t(tx, ty - 1) == ROAD:
                img.rect(px, py, TILE, 2, CURB)
                img.rect(px, py - 1, TILE, 1, AS0)
            if t(tx, ty + 1) == ROAD:
                img.rect(px, py + TILE - 2, TILE, 2, SIDE2)
                img.rect(px, py + TILE - 1, TILE, 1, SWJ)
            if t(tx - 1, ty) == ROAD:
                img.rect(px, py, 2, TILE, CURB)
                img.rect(px - 1, py, 1, TILE, AS0)
            if t(tx + 1, ty) == ROAD:
                img.rect(px + TILE - 2, py, 2, TILE, SIDE2)
                img.rect(px + TILE - 1, py, 1, TILE, SWJ)

    # 4) plazas: senderos en cruz hasta la fuente
    nbx, nby = mw // B + 1, mh // B + 1
    for by in range(nby):
        for bx in range(nbx):
            if not city._plaza(bx, by):
                continue
            cx, cy = bx * B + B // 2, by * B + B // 2
            if not (0 <= cx < mw and 0 <= cy < mh):
                continue
            x0, x1 = (bx * B + 3) * TILE, min(mw, bx * B + 7) * TILE
            y0, y1 = (by * B + 3) * TILE, min(mh, by * B + 7) * TILE
            ccx, ccy = cx * TILE + 8, cy * TILE + 8
            img.rect(ccx - 3, y0, 6, y1 - y0, PATH0)
            img.rect(x0, ccy - 3, x1 - x0, 6, PATH0)
            img.rect(ccx - 2, y0, 2, y1 - y0, PATH1)
            img.rect(x0, ccy - 2, x1 - x0, 2, PATH1)
            img.circ(ccx, ccy, 11, PATH0)
            img.circb(ccx, ccy, 11, SWJ)
            # canteros con flores
            for _ in range(10):
                fx = rng.randrange(x0 + 2, max(x0 + 3, x1 - 2))
                fy = rng.randrange(y0 + 2, max(y0 + 3, y1 - 2))
                if abs(fx - ccx) > 6 and abs(fy - ccy) > 6:
                    img.pset(fx, fy, rng.choice((FLOW1, FLOW2, WHITE)))

    # 5) las sombras de los edificios sobre el piso, y los edificios
    builds = []
    for by in range(nby):
        for bx in range(nbx):
            if city._plaza(bx, by):
                continue
            tx0, ty0 = bx * B + 3, by * B + 3
            tx1, ty1 = min(mw, bx * B + 7), min(mh, by * B + 7)
            if tx1 <= tx0 or ty1 <= ty0 or t(tx0, ty0) != BLD:
                continue
            builds += _lotes(bx, by, tx0 * TILE, ty0 * TILE, tx1 * TILE, ty1 * TILE)
    for b in builds:
        x0, y0, x1, y1, hh = b["x0"], b["y0"], b["x1"], b["y1"], b["h"]
        d = int(hh * 0.8) + 2
        _shade_rect(mv, iw, ih, x1, y0 + d, d, y1 - y0)
        _shade_rect(mv, iw, ih, x0 + d, y1, x1 - x0, d)
    for b in builds:
        _edificio(img, rng, b)
    # el más alto le hace sombra al techo del vecino de la manzana
    for a in builds:
        for b in builds:
            if b is a or b["blk"] != a["blk"] or b["h"] >= a["h"]:
                continue
            d = int((a["h"] - b["h"]) * 0.8) + 1
            if abs(b["x0"] - a["x1"] - 2) <= 1 and b["y0"] < a["y1"] and b["y1"] > a["y0"]:
                yy0 = max(b["y0"], a["y0"] + d)
                _shade_rect(mv, iw, ih, b["x0"], yy0, d, min(b["y1"] - b["h"], a["y1"] + d) - yy0)
            if abs(b["y0"] - a["y1"] - 2) <= 1 and b["x0"] < a["x1"] and b["x1"] > a["x0"]:
                xx0 = max(b["x0"], a["x0"] + d)
                _shade_rect(mv, iw, ih, xx0, b["y0"], min(b["x1"], a["x1"] + d) - xx0, d)

    # 6) árboles y fuentes, con su sombra
    for ty in range(mh):
        for tx in range(mw):
            k = t(tx, ty)
            cx, cy = tx * TILE + 8, ty * TILE + 7
            if k == TREE:
                _shade_circ(mv, iw, ih, cx + 4, cy + 5, 7, 5)
                r = 7 if (tx + ty) % 3 else 6
                img.circ(cx, cy, r, TREEDK)
                img.circ(cx, cy, r - 1, TREE1)
                img.circ(cx - 1, cy - 1, r - 2, TREETOP)
                for _ in range(5):
                    a = rng.uniform(math.pi, math.tau)
                    rr = rng.uniform(1, r - 2)
                    img.pset(int(cx - 1 + math.cos(a) * rr), int(cy - 1 + math.sin(a) * rr),
                             TREELT)
                img.circ(cx - 2, cy - 3, 1, TREELT)
                for _ in range(3):
                    img.pset(cx + rng.randrange(-r + 2, r - 1), cy + rng.randrange(1, r - 1),
                             TREE1)
            elif k == FOUNT:
                cy += 1
                _shade_circ(mv, iw, ih, cx + 2, cy + 3, 7, 6)
                img.circ(cx, cy, 7, MET1)
                img.circb(cx, cy, 7, SWJ)
                img.circ(cx, cy, 5, WATER0)
                img.circ(cx - 1, cy - 1, 4, WATER)
                img.circ(cx, cy, 1, WATER2)
                img.pset(cx - 3, cy - 2, WATER2)
                img.pset(cx + 2, cy + 2, WATER2)
                img.pset(cx - 1, cy - 4, WHITE)
                img.line(cx - 6, cy - 3, cx - 4, cy - 5, MET2)

    _CITY["img"] = img
    return img


def _lotes(bx, by, x0, y0, x1, y1):
    """cómo se reparte una manzana: un edificio, dos o cuatro, con un pasaje
    de 2 px entre ellos. alturas y materiales salen de un hash fijo."""
    h = (bx * 7 + by * 13) % 5
    w, hgt = x1 - x0, y1 - y0
    out = []
    if w < 48 or h == 0:
        cells = [(x0, y0, x1, y1)]
    elif h in (1, 3):
        m = x0 + w // 2
        cells = [(x0, y0, m - 1, y1), (m + 1, y0, x1, y1)]
    elif h == 2:
        m = y0 + hgt // 2
        cells = [(x0, y0, x1, m - 1), (x0, m + 1, x1, y1)]
    else:
        mx, my = x0 + w // 2, y0 + hgt // 2
        cells = [(x0, y0, mx - 1, my - 1), (mx + 1, y0, x1, my - 1),
                 (x0, my + 1, mx - 1, y1), (mx + 1, my + 1, x1, y1)]
    for i, (a, b_, c, d) in enumerate(cells):
        k = bx * 31 + by * 17 + i * 7
        alto = (6, 8, 10, 12, 14, 9)[k % 6]
        if len(cells) == 1:
            alto += 3
        out.append({"x0": a, "y0": b_, "x1": c, "y1": d, "h": alto,
                    "mat": (k // 3) % len(ROOFS), "seed": k, "blk": (bx, by),
                    "solo": len(cells) == 1})
    return out


def _edificio(img, rng, b):
    """un edificio visto desde arriba con la cámara apenas inclinada: el techo
    arriba y la fachada sur abajo, con ventanas. luz desde arriba-izquierda."""
    x0, y0, x1, y1, hh = b["x0"], b["y0"], b["x1"], b["y1"], b["h"]
    d0, d1, d2, d3 = ROOFS[b["mat"]]
    w = x1 - x0
    wall = max(4, hh // 2 + 2)
    ry1 = y1 - wall                       # dónde termina el techo
    r = random.Random(b["seed"])
    # fachada sur
    img.rect(x0, ry1, w, wall, d1)
    img.rect(x0, y1 - 1, w, 1, d0)
    img.rect(x1 - 2, ry1, 2, wall, d0)
    for wy in range(ry1 + 2, y1 - 2, 3):
        for wx in range(x0 + 3, x1 - 4, 4):
            lit = r.random() < 0.28
            img.rect(wx, wy, 2, 2, WINLIT if lit else WIN)
            if not lit and r.random() < 0.3:
                img.pset(wx, wy, GLASS0)
    # techo: parapeto con luz arriba-izquierda y sombra abajo-derecha
    img.rect(x0, y0, w, ry1 - y0, d2)
    img.rect(x0, y0, w, 2, d3)
    img.rect(x0, y0, 2, ry1 - y0, d3)
    img.rect(x0, ry1 - 2, w, 2, d1)
    img.rect(x1 - 2, y0 + 2, 2, ry1 - y0 - 2, d1)
    img.rect(x0 + 2, y0 + 2, w - 4, 1, d1)        # el borde interior del parapeto
    img.rect(x0 + 2, y0 + 2, 1, ry1 - y0 - 4, d1)
    img.rectb(x0 - 1, y0 - 1, w + 2, y1 - y0 + 2, OUTLINE)
    ix0, iy0, ix1, iy1 = x0 + 4, y0 + 4, x1 - 4, ry1 - 4
    if ix1 - ix0 < 16 or iy1 - iy0 < 14:
        return
    # grava
    for _ in range((ix1 - ix0) * (iy1 - iy0) // 14):
        img.pset(r.randrange(ix0, ix1), r.randrange(iy0, iy1), d1 if r.random() < 0.6 else d3)
    if r.random() < 0.15 and not b["solo"]:           # terraza con jardín
        img.rect(ix0, iy0, ix1 - ix0, iy1 - iy0, GRASS1)
        img.rectb(ix0, iy0, ix1 - ix0, iy1 - iy0, d1)
        for _ in range(6):
            cx, cy = r.randrange(ix0 + 3, ix1 - 3), r.randrange(iy0 + 3, iy1 - 3)
            img.circ(cx, cy, 2, TREE1)
            img.pset(cx - 1, cy - 1, TREELT)
        return
    if b["solo"] and r.random() < 0.5:                # helipuerto
        cx, cy = (ix0 + ix1) // 2, (iy0 + iy1) // 2
        rad = min(ix1 - ix0, iy1 - iy0) // 2 - 3
        img.circ(cx + 1, cy + 1, rad, d1)
        img.circ(cx, cy, rad, MET0)
        img.circb(cx, cy, rad, GOLD)
        img.rect(cx - 4, cy - 5, 2, 11, WHITE)
        img.rect(cx + 3, cy - 5, 2, 11, WHITE)
        img.rect(cx - 2, cy - 1, 5, 2, WHITE)
        return
    # aparatos en el techo: aire acondicionado, ventilas, tanque, claraboya
    n = 2 + r.randrange(3)
    for _ in range(n):
        kind = r.random()
        cx, cy = r.randrange(ix0 + 4, ix1 - 6), r.randrange(iy0 + 4, iy1 - 5)
        if kind < 0.45:
            img.rect(cx + 2, cy + 2, 7, 5, d1)           # su sombra
            img.rect(cx, cy, 7, 5, MET1)
            img.rect(cx, cy, 7, 1, MET2)
            img.rect(cx + 6, cy, 1, 5, MET0)
            img.rect(cx, cy + 4, 7, 1, MET0)
            img.circb(cx + 3, cy + 2, 1, MET0)
        elif kind < 0.65:
            img.circ(cx + 1, cy + 1, 2, d1)
            img.circ(cx, cy, 2, MET0)
            img.pset(cx - 1, cy - 1, MET2)
        elif kind < 0.82 and hh >= 10:
            img.circ(cx + 3, cy + 3, 5, d1)
            img.circ(cx, cy, 5, MET0)
            img.circ(cx - 1, cy - 1, 4, MET1)
            img.circb(cx, cy, 5, OUTLINE)
            img.pset(cx - 2, cy - 3, MET2)
            img.pset(cx - 3, cy - 2, MET2)
        else:
            ww = min(14, ix1 - cx - 1)
            if ww >= 6:
                img.rect(cx + 1, cy + 1, ww, 5, d1)
                img.rect(cx, cy, ww, 5, GLASS0)
                img.rect(cx, cy, ww, 1, GLASS)
                img.line(cx + 2, cy + 4, cx + 4, cy + 1, GLASS)
                img.rectb(cx - 1, cy - 1, ww + 2, 7, d0)


def rampa(img, px, py, eje):
    """la rampa: chapa amarilla con chevrones que dicen hacia dónde se salta,
    el borde alto con luz y el bajo con sombra."""
    if eje == 0:                       # se salta en x
        img.rect(px + 2, py, 12, TILE, GOLD)
        img.rect(px + 2, py, 2, TILE, GOLD0)
        img.rect(px + 12, py, 2, TILE, WHITE)
        for yy in range(py + 2, py + TILE - 2, 6):
            img.line(px + 5, yy, px + 9, yy + 2, OUTLINE)
            img.line(px + 9, yy + 2, px + 5, yy + 4, OUTLINE)
        img.rect(px + 14, py, 2, TILE, AS0)
    else:
        img.rect(px, py + 2, TILE, 12, GOLD)
        img.rect(px, py + 2, TILE, 2, GOLD0)
        img.rect(px, py + 12, TILE, 2, WHITE)
        for xx in range(px + 2, px + TILE - 2, 6):
            img.line(xx, py + 5, xx + 2, py + 9, OUTLINE)
            img.line(xx + 2, py + 9, xx + 4, py + 5, OUTLINE)
        img.rect(px, py + 14, TILE, 2, AS0)


def radar_image(city, kinds):
    ROAD, SIDEWALK, GRASS, TREE, FOUNT, BLD = kinds
    hit = _CITY.get("radar")
    if hit is not None:
        return hit
    img = pyxel.Image(city.mw * 2, city.mh * 2)
    for ty in range(city.mh):
        for tx in range(city.mw):
            k = city.tile(tx, ty)
            img.rect(tx * 2, ty * 2, 2, 2, MAPRD if k == ROAD else
                     (MAPGR if k in (GRASS, TREE, FOUNT) else MAPBG))
    _CITY["radar"] = img
    return img


# --- autos pre-rotados -------------------------------------------------------
# mirando a la derecha (el morro es la última columna). 22 x 12, el mismo
# largo y ancho que la caja de choque del auto.
#   b carrocería  d carrocería oscura  l techo  g vidrio  w brillo del vidrio
#   h faro  t luz de freno  s franja  r/u balizas (rojo/azul)  k parachoques
CAR = [
    "...kkk.......kkk......",
    ".tbbbbbbbbbbbbbbbbbbb.",
    "tbbbbbblllllbbbbbbbbbh",
    "kbbbggglllllggggbbbbbk",
    "kbbbwgglllllgwggbbbbbk",
    "ksssggglllllwgggsssssk",
    "ksssggglllllggggsssssk",
    "kbbbggglllllggggbbbbbk",
    "kbbbggglllllggggbbbbbk",
    "tbbbbbblllllbbbbbbbbbh",
    ".tbbbbbbbbbbbbbbbbbbb.",
    "...kkk.......kkk......",
]
COP = [
    "...kkk.......kkk......",
    ".tdddbbbbbbbbbbbbdddd.",
    "tdddbbblllllbbbbdddddh",
    "kdddgggllrrlggggdddddk",
    "kdddwggllrrlgwggdddddk",
    "kdddgggllrrlwgggdddddk",
    "kdddggglluulggggdddddk",
    "kdddggglluulggggdddddk",
    "kdddggglluulggggdddddk",
    "tdddbbblllllbbbbdddddh",
    ".tdddbbbbbbbbbbbbdddd.",
    "...kkk.......kkk......",
]
HELI = [
    "..............bbbbbb......",
    "............bbbbbbbbbb....",
    ".kk........bbbbbbbbbbbbg..",
    ".kk.......bbbbbllbbbbbggg.",
    ".kkddddddddbbbblllbbbbgwgg",
    ".ku.......dbbbblllbbbbgggw",
    ".kkddddddddbbbblllbbbbgggg",
    ".kk.......bbbbbllbbbbbggg.",
    ".kk........bbbbbbbbbbbbg..",
    "............bbbbbbbbbb....",
    "..............bbbbbb......",
]
_SKINS = {
    "auto": ({"b": CARBODY, "d": CAR0, "l": CARROOF, "g": GLASS1, "w": GLASS,
              "h": HEAD, "t": TAIL, "s": COP2, "k": OUTLINE}, 28),
    "cop": ({"b": COP2, "d": COP1, "l": COP2, "g": GLASS1, "w": GLASS, "h": HEAD,
             "t": TAIL, "r": TAIL, "u": NITRO2, "k": OUTLINE}, 28),
    "heli": ({"b": COP1, "d": COPD, "l": COPL, "g": GLASS1, "w": GLASS,
              "u": LIGHTR, "k": OUTLINE}, 32),
}
_ART = {"auto": CAR, "cop": COP, "heli": HELI}
# luz de pantalla: el borde que mira arriba-izquierda sube un tono, el de
# abajo-derecha baja uno
LIGHT = {CARBODY: CARROOF, CARROOF: CAR3, CAR0: CARBODY, COP1: COPL, COP2: WHITE,
         COPWD: COP2, GLASS0: GLASS1, GLASS1: GLASS, HELI1: HELI2, HELI0: HELI1, HELI2: MET2,
         TAIL: LIGHTR}
DARK = {CARBODY: CAR0, CARROOF: CARBODY, COP1: COPD, COP2: COPWD, COPL: COP1,
        GLASS0: OUTLINE, GLASS1: GLASS0, HELI1: HELI0, HELI2: HELI1,
        GLASS: GLASS1}
NANG = 64
TRANSP = BG                      # el color llave de las imágenes de sprites


class Rotados:
    """un sprite dibujado mirando a la derecha, pre-rotado a 64 ángulos la
    primera vez que se pide cada uno. abajo de cada cuadro va su silueta para
    la sombra."""

    def __init__(self, nombre):
        cmap, cell = _SKINS[nombre]
        rows = _ART[nombre]
        self.cell = cell
        self.src = [[cmap.get(ch) for ch in row] for row in rows]
        self.sw, self.sh = len(rows[0]), len(rows)
        self.img = pyxel.Image(cell * 8, cell * 16)
        self.img.cls(TRANSP)
        self.ok = bytearray(NANG)

    def _bake(self, n):
        c = self.cell
        a = n * math.tau / NANG
        ca, sa = math.cos(a), math.sin(a)
        half = c / 2
        src, sw, shh = self.src, self.sw, self.sh
        grid = [[None] * c for _ in range(c)]
        for y in range(c):
            Y = y + 0.5 - half
            row = grid[y]
            for x in range(c):
                X = x + 0.5 - half
                fx = ca * X + sa * Y + sw / 2
                fy = -sa * X + ca * Y + shh / 2
                if 0 <= fx < sw and 0 <= fy < shh:
                    row[x] = src[int(fy)][int(fx)]
        u, v = (n % 8) * c, (n // 8) * c
        img = self.img

        def op(xx, yy):
            return 0 <= xx < c and 0 <= yy < c and grid[yy][xx] is not None

        for y in range(c):
            for x in range(c):
                col = grid[y][x]
                if col is None:
                    if op(x - 1, y) or op(x + 1, y) or op(x, y - 1) or op(x, y + 1):
                        img.pset(u + x, v + y, OUTLINE)
                    continue
                if not op(x - 1, y - 1) or not op(x, y - 1):
                    col = LIGHT.get(col, col)
                elif not op(x + 1, y + 1) or not op(x, y + 1):
                    col = DARK.get(col, col)
                img.pset(u + x, v + y, col)
                img.pset(u + x, v + 8 * c + y, sh(ASPHALT))
        self.ok[n] = 1

    def idx(self, a):
        return int(round(a / math.tau * NANG)) % NANG

    def draw(self, x, y, a, k=1.0, sombra=2, sombra_col=None):
        n = self.idx(a)
        if not self.ok[n]:
            self._bake(n)
        c = self.cell
        u, v = (n % 8) * c, (n // 8) * c
        h = c // 2
        if sombra is not None:
            pyxel.blt(int(x) - h + sombra, int(y) - h + sombra, self.img, u, v + 8 * c,
                      c, c, TRANSP)
        if k != 1.0:
            pyxel.blt(int(x) - h, int(y) - h, self.img, u, v, c, c, TRANSP, scale=k)
        else:
            pyxel.blt(int(x) - h, int(y) - h, self.img, u, v, c, c, TRANSP)


_ROT = {}


def rotados(nombre):
    r = _ROT.get(nombre)
    if r is None:
        r = _ROT[nombre] = Rotados(nombre)
    return r


def oscurecer(y0=0, y1=None):
    """oscurece la pantalla de verdad (cada color pasa a su gemelo en sombra),
    sin tramado: para poner texto encima de la ciudad."""
    w = pyxel.width
    y1 = pyxel.height if y1 is None else y1
    mv = memoryview(pyxel.screen.data_ptr()).cast("B")
    a, b = y0 * w, y1 * w
    mv[a:b] = bytes(mv[a:b]).translate(SHMAP)


def warm(nombres=("auto", "cop"), n=None):
    """hornea ángulos por adelantado (lo usa el título, de a poco)."""
    for nom in nombres:
        r = rotados(nom)
        for i in range(NANG) if n is None else n:
            if not r.ok[i % NANG]:
                r._bake(i % NANG)
                return True
    return False
