"""el vidrio del cabinet: el tubo crt, estampado sobre el framebuffer.

pyxel trae un modo "retro" propio (`screen_mode(2)`), pero es uno solo y no se
regula. acá el efecto lo ponemos nosotros, encima de lo que el juego ya dibujó,
en dos intensidades:

    suave   una scanline cada 2 filas, apenas apagada — se nota y no molesta
    fuerte  scanlines marcadas + rejilla de apertura vertical — sala recreativa

**apagamos, no borramos.** el primer intento pintaba las scanlines con líneas
del color de fondo y el texto de 5 px de alto quedaba ilegible: una franja
maciza se come un tercio de cada letra. acá cada píxel de la scanline se cambia
por una versión **más oscura de su propio color**, así la letra sigue entera,
sólo que tenue. es lo que hace un tubo de verdad.

el framebuffer es indexado, así que el truco es tener el tono oscuro de cada
color en la propia paleta:

- si sobran índices (el menú usa 16, los juegos chicos 32), se escribe la capa
  oscura al final de los 256 y la traducción es exacta.
- si no sobra ninguno — powder gasta 255 — se busca para cada color el índice
  **ya existente** más parecido a su versión oscurecida. powder tiene varios
  tonos por material, así que casi siempre cae en el tono oscuro del mismo
  material y el efecto sale igual de bien.

la traducción se arma una vez por proceso (cada juego es un proceso) y después
cada frame son dos `translate` por fila, en C. `apply()` va al FINAL del draw:
el Cabinet y el menú ya lo llaman.
"""
import sys

import pyxel

OFF, SOFT, HARD = 0, 1, 2

# por nivel: (factor de brillo de la scanline, cada cuántas columnas la rejilla)
LEVELS = {
    SOFT: (0.72, 0),
    HARD: (0.50, 3),
}

_cache = {}          # nivel -> tabla de 256 bytes (o None si no se pudo armar)
_base = None         # la paleta del juego, tal como estaba antes de tocarla
_extras = {}         # los tonos apagados que ya escribimos, por índice


def _rgb(c):
    return (c >> 16) & 255, (c >> 8) & 255, c & 255


def _used(colors):
    """cuántos índices usa de verdad la paleta: hasta el último no-negro."""
    for i in range(len(colors) - 1, -1, -1):
        if colors[i]:
            return i + 1
    return 0


def _luma(r, g, b):
    return 3 * r + 6 * g + b            # brillo percibido, en enteros


def _nearest(colors, used, target):
    """el índice existente más parecido a `target`, **sin pasarse de brillo**.

    el filtro por luma es lo que hace que la scanline se vea en una paleta
    llena: sin él, el color más "cercano" a un naranja oscurecido es el mismo
    naranja apenas más apagado (en powder cada material trae tonos de 0.78 a
    1.16, así que la distancia mínima siempre cae en el propio material) y el
    efecto no se nota. exigiendo que el candidato sea más oscuro que el target
    se acepta un pelín de corrimiento de matiz a cambio de que la línea exista.
    """
    tr, tg, tb = target
    tl = _luma(tr, tg, tb)
    best, bd = None, 1 << 30
    fallback, fd = 0, 1 << 30
    for i in range(used):
        r, g, b = _rgb(colors[i])
        d = 3 * (r - tr) ** 2 + 4 * (g - tg) ** 2 + 2 * (b - tb) ** 2
        if d < fd:
            fallback, fd = i, d
        if _luma(r, g, b) <= tl and d < bd:
            best, bd = i, d
    return fallback if best is None else best


def build_table(colors, factor, slot=0, levels=1):
    """tabla de 256 bytes: índice -> índice de su versión al `factor` de brillo.

    si hay lugar en la paleta escribe los tonos oscuros al final (exacto) y los
    devuelve para que el llamador los cargue; si no, mapea a lo más parecido de
    lo que ya hay. devuelve (tabla, {índice: color} a escribir en la paleta).

    `slot`/`levels`: cada intensidad se guarda en su propio bloque al final de
    la paleta. si compartieran bloque, la segunda pisaría los tonos de la
    primera y las dos terminarían viéndose igual — que es justo lo que hay que
    poder comparar. por eso el lugar tiene que alcanzar para TODOS los niveles.
    """
    colors = list(colors)
    used = _used(colors)
    table = bytearray(range(256))
    extra = {}
    if used and used * (1 + levels) <= 256:      # cabe una capa por intensidad
        start = 256 - (slot + 1) * used
        for i in range(used):
            r, g, b = _rgb(colors[i])
            dark = (int(r * factor) << 16) | (int(g * factor) << 8) | int(b * factor)
            extra[start + i] = dark
            table[i] = start + i
    else:                                        # paleta llena: al más parecido
        for i in range(used):
            r, g, b = _rgb(colors[i])
            table[i] = _nearest(colors, used,
                                (int(r * factor), int(g * factor), int(b * factor)))
    return bytes(table), extra


def _table(level):
    """arma (y cachea) la traducción del nivel, cargando los tonos que falten.

    dos cuidados, los dos aprendidos a golpes:

    - `pyxel.colors[:] = PAL` deja la paleta **del largo de PAL** (16 en el
      menú, no 256): la capa oscura no se puede escribir por índice suelto, hay
      que asignar la lista entera ya estirada a 256.
    - la tabla se arma contra la paleta **original** (`_base`), no contra la que
      hay en pyxel: al armar la segunda intensidad, la primera ya le agregó sus
      tonos oscuros, y tomarlos como paleta del juego hacía que la segunda se
      viera igual que la primera (probar crt suave y después crt fuerte en el
      menú daba el mismo dibujo).
    """
    global _base
    if level in _cache:
        return _cache[level]
    factor = LEVELS[level][0]
    slot = sorted(LEVELS).index(level)
    try:
        if _base is None:
            _base = list(pyxel.colors)
        table, extra = build_table(_base, factor, slot, len(LEVELS))
        if extra:
            _extras.update(extra)
            full = list(_base) + [0] * (256 - len(_base))
            for idx, col in _extras.items():
                full[idx] = col
            pyxel.colors[:] = full
    except Exception as e:                       # backend raro: seguimos sin crt
        print("crt: sin efecto (%s: %s)" % (type(e).__name__, e), file=sys.stderr)
        table = None
    _cache[level] = table
    return table


def reset():
    """olvida las tablas y la paleta base. hay que llamarlo si el juego cambia
    su paleta en caliente (ninguno lo hace hoy: la cargan una vez al bootear)."""
    global _base
    _cache.clear()
    _extras.clear()
    _base = None


def apply(level):
    """estampa el crt sobre el frame actual. `level` es OFF, SOFT o HARD."""
    if level not in LEVELS:
        return
    table = _table(level)
    if table is None:
        return
    _, col_step = LEVELS[level]
    w, h = pyxel.width, pyxel.height
    buf = memoryview(pyxel.screen.data_ptr()).cast("B")
    for y in range(1, h, 2):                     # scanlines: las filas impares
        off = y * w
        row = buf[off:off + w]
        row[:] = bytes(row).translate(table)
    if col_step:                                 # rejilla: columnas en las pares
        for y in range(0, h, 2):
            off = y * w
            row = buf[off:off + w]
            dark = bytes(row).translate(table)
            row[col_step - 1::col_step] = dark[col_step - 1::col_step]
