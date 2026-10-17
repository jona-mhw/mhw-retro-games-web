"""el menú del arcade: la pantalla de selección del cabinet.

lo maneja el emulador (arcade.py). muestra los juegos que haya en games/, deja
elegir uno con teclado o mouse, tiene pantalla de CRÉDITOS y una de SISTEMA con
la config (interpolación, escala entera, pantalla completa). cuando elegís un
juego escribe su id en el archivo que le pasa arcade.py y sale; el emulador lo
lee y levanta ese juego como proceso aparte.

la navegación vive en MenuModel, sin pyxel, para poder probarla sin abrir
ventana. MenuApp es sólo la piel: input, dibujo y los efectos (aplicar y grabar
la config). los ajustes se ven en vivo: al cambiar la pantalla, el propio menú
se redibuja con el modo nuevo.

el layout: cada juego es una **fila de una línea** (título + resolución) y lo
que lo describe vive abajo, en un panel fijo que sigue al cursor. antes cada
tarjeta traía título y descripción adentro con offsets fijos (y+3, y+11) sobre
una fila de alto variable: al llegar al sexto juego las filas se achicaron y el
texto se salió de su caja. ahora todo se deriva de la altura de fila, así que
sumar juegos aprieta la lista pero no pisa nada.
"""
import math
import sys

import pyxel

from pixelkit import config, crt, scores, web
from pixelkit.pxtext import CW, ctext, text
from pixelkit.registry import discover_games

# en el celular parado el menú es vertical: filas más altas, que se tocan con
# el dedo sin errarle, y un horizonte synthwave en la cabecera. en el
# escritorio (o el celular acostado) sigue siendo el 320x240 de siempre.
PORTRAIT = web.is_touch() and web.portrait()
W, H = (240, 400) if PORTRAIT else (320, 240)
HEAD_H = 84 if PORTRAIT else 44

# paleta del menú (16 colores). el acento pasó del verde de marca a un cian
# eléctrico y el header a magenta: es lo que hace que el cabinet se lea como
# "retro future" y no como una herramienta de trabajo. el verde queda de
# secundario, para lo que confirma (récords, "listo").
BG, PANEL, SEL, LINE, DIM, TXT, TXT2, HEAD, ACC, ACC_DK, \
    SHADOW, AMBER, PINK, SKY, RED, TEAL_DK = range(16)
MENU_PAL = [
    0x0B0A16, 0x161228, 0x241B44, 0x3A2C63, 0x6E6499, 0xD8DEEC, 0xF2F5FB,
    0xE868C8, 0x38E8E0, 0x1E8E90, 0x060512, 0xFFC24A, 0xFF6EC7, 0x7ADCFF,
    0xE04A2A, 0x8AC52F,
]

ROW_Y0 = HEAD_H + 6                 # y de la primera fila de juego
ROW_H = 22 if PORTRAIT else 18      # alto máximo de cada fila (se achica si hay muchos juegos)
ROW_MIN = 9      # abajo de esto no entra ni una línea de texto
DETAIL_H = 66 if PORTRAIT else 42   # el panel de abajo, que describe lo que apunta el cursor
FOOT_H = 14
MARGIN = 16      # margen lateral de filas y panel

# ajustes que muestra la pantalla de sistema, en orden. en la web la pantalla
# completa es un botón de la página (pyxel la pediría sólo para el canvas y
# taparía los controles táctiles)
CONFIG_ITEMS = ("screen_mode", "integer_scale") + (() if web.ACTIVE else ("fullscreen",))
CONFIG_LABEL = {
    "screen_mode": "pantalla",
    "integer_scale": "escala entera",
    "fullscreen": "pantalla completa",
}
# qué hace cada modo de pantalla, en una línea (se muestra el del cursor)
MODE_HINT = {
    0: "pixel perfecto, sin filtro",
    1: "bilineal: los píxeles se difuminan",
    2: "tubo crt discreto: scanlines finas",
    3: "tubo crt de sala: scanlines + rejilla",
}


class MenuModel:
    """navegación pura del menú, sin pyxel. testeable de a de veras.

    el cursor de la lista recorre los juegos y dos filas extra: CRÉDITOS y
    SISTEMA. la vista de sistema tiene su propio cursor sobre los ajustes.
    """

    def __init__(self, games, cfg):
        self.games = games
        self.cfg = cfg
        self.rows = len(games) + 3        # + récords + créditos + sistema
        self.cursor = 0
        self.view = "list"                # "list" | "records" | "credits" | "config"
        self.cfg_cursor = 0

    @property
    def records_row(self):
        return len(self.games)

    @property
    def credits_row(self):
        return len(self.games) + 1

    @property
    def config_row(self):
        return len(self.games) + 2

    def move(self, d):
        if self.view == "list" and self.rows:
            self.cursor = (self.cursor + d) % self.rows
        elif self.view == "config":
            self.cfg_cursor = (self.cfg_cursor + d) % len(CONFIG_ITEMS)

    def point_at(self, row):
        """el mouse apunta a una fila de la lista; None la ignora."""
        if self.view == "list" and row is not None and 0 <= row < self.rows:
            self.cursor = row

    def select(self):
        """confirma. devuelve ('launch', id), ('config-changed', key) o None."""
        if self.view in ("credits", "records"):
            self.view = "list"
            return None
        if self.view == "config":
            return self.adjust(1)          # enter cicla el ajuste
        if self.cursor == self.records_row:
            self.view = "records"
            return None
        if self.cursor == self.credits_row:
            self.view = "credits"
            return None
        if self.cursor == self.config_row:
            self.view = "config"
            return None
        return ("launch", self.games[self.cursor].id)

    def adjust(self, d):
        """cambia el ajuste bajo el cursor de sistema. devuelve ('config-changed', key)."""
        if self.view != "config":
            return None
        key = CONFIG_ITEMS[self.cfg_cursor]
        if key == "screen_mode":
            self.cfg["screen_mode"] = (self.cfg["screen_mode"] + d) % len(config.MODES)
        else:
            self.cfg[key] = not self.cfg[key]
        return ("config-changed", key)

    def back(self):
        """esc / clic derecho. devuelve 'quit' si toca salir del arcade."""
        if self.view in ("credits", "config", "records"):
            self.view = "list"
            return None
        return "quit"


def wrap(s, cols):
    """parte un texto en líneas de a lo más `cols` caracteres, sin cortar
    palabras. `cols` sale del ancho en px dividido CW, no de un número mágico."""
    out, line = [], ""
    for word in s.split():
        cand = word if not line else line + " " + word
        if len(cand) <= cols:
            line = cand
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    return out


def credits_lines(games):
    """las líneas de la pantalla de créditos: bloque fijo + autores reales."""
    lines = [
        ("MHW · RETRO · FUTURE", ACC),
        ("el futuro, como se veía en 1985", DIM),
        ("", TXT),
        ("motor: pyxel — Takashi Kitao", TXT),
        ("arcade + pixelkit: Jona · jona-mhw", TXT),
        ("hecho con Claude Code, multiagente", DIM),
        ("", TXT),
        ("JUEGOS EN EL CABINET", HEAD),
    ]
    for g in games:
        firma = g.author or "—"
        if g.year:
            firma += " · %s" % g.year
        lines.append(("%s   %s" % (g.title, firma), TXT))
    lines += [
        ("", TXT),
        ("inspiración: Powder Game — Dan-Ball", DIM),
    ]
    return lines


def value_label(cfg, key):
    """el texto del valor de un ajuste, tal como se muestra."""
    if key == "screen_mode":
        return config.MODE_LABEL[cfg["screen_mode"]]
    return "sí" if cfg[key] else "no"


class MenuApp:
    def __init__(self, out_path=None):
        self.out = out_path
        self.cfg = config.load()
        self.model = MenuModel(discover_games(), self.cfg)
        self.result = "__quit__"
        # el tablero se lee UNA vez: el panel de detalle lo consulta en cada
        # frame y scores.top() abre el json cada vez que se lo llama. no se
        # desactualiza: al volver de un juego, el menú es un proceso nuevo.
        self.board = scores.load()
        self._mouse_at = None

    def loop(self):
        pyxel.init(W, H, title="MHW RETRO FUTURE", fps=60,
                   display_scale=3, quit_key=pyxel.KEY_NONE)
        pyxel.colors[:] = MENU_PAL
        pyxel.mouse(True)
        config.apply(self.cfg)             # arranca con lo guardado
        web.touch("menu")
        pyxel.run(self.update, self.draw)
        return self.result

    def _finish(self, result):
        """graba la elección y cierra. pyxel.run no retorna (el proceso sale
        en el quit), así que hay que escribir el archivo ANTES de quit()."""
        self.result = result
        if web.ACTIVE:                     # en la web lanzar es navegar, y del
            if result != "__quit__":       # cabinet no se sale: es la página
                web.launch(result)
            return
        if self.out:
            try:
                with open(self.out, "w") as f:
                    f.write(result)
            except OSError:
                pass
        pyxel.quit()

    def _commit_config(self):
        config.apply(self.cfg)             # se ve en vivo
        config.save(self.cfg)

    # --- layout (altura de fila dinámica, para que entren todas) ----------
    def _detail_h(self):
        """el panel cede espacio si hay tantos juegos que las filas no entran.
        con más de ~14 filas se queda en cero: ahí ya haría falta paginar."""
        libre = H - FOOT_H - 1 - ROW_Y0 - self.model.rows * ROW_MIN
        return max(0, min(DETAIL_H, libre))

    def _list_bottom(self):
        """dónde termina la lista: arriba del panel de detalle y del pie."""
        dh = self._detail_h()
        return H - FOOT_H - 1 - dh - (2 if dh else 0)

    def _rh(self):
        avail = self._list_bottom() - ROW_Y0
        return max(ROW_MIN, min(ROW_H, avail // max(1, self.model.rows)))

    def _row_y(self, i):
        return ROW_Y0 + i * self._rh()

    def _text_y(self, y, bh):
        """la y del texto dentro de una fila de alto bh: centrado, con los 3 px
        que el acento de pxtext dibuja por encima del glifo."""
        return y + max(3, (bh - 5) // 2 + 1)

    # --- input -----------------------------------------------------------
    def _mouse_row(self):
        my = pyxel.mouse_y
        if my < ROW_Y0:
            return None
        row = (my - ROW_Y0) // self._rh()
        return row if 0 <= row < self.model.rows else None

    def update(self):
        m = self.model
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            m.move(-1)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            m.move(1)
        if pyxel.mouse_wheel:
            m.move(-1 if pyxel.mouse_wheel > 0 else 1)
        moved = (pyxel.mouse_x, pyxel.mouse_y) != self._mouse_at
        self._mouse_at = (pyxel.mouse_x, pyxel.mouse_y)
        before = m.cursor
        if m.view == "list":
            if moved:
                m.point_at(self._mouse_row())
            if pyxel.btnp(pyxel.KEY_C):
                m.view = "credits"
        elif m.view == "config":
            d = 0
            if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D):
                d = 1
            if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A):
                d = -1
            if d and m.adjust(d):
                self._commit_config()

        confirm = pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE)
        if m.view != "config":            # en config el clic no cicla ajustes sin querer
            # con el dedo, el primer toque elige la fila (y muestra su ficha)
            # y el segundo la lanza. con mouse el hover ya la eligió: un clic
            tap = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
            if tap and m.view == "list" and (m.cursor != before
                                              or self._mouse_row() is None):
                tap = False
            confirm = confirm or tap
        if confirm:
            r = m.select()
            if r and r[0] == "launch":
                self._finish(r[1])
            elif r and r[0] == "config-changed":
                self._commit_config()
        if pyxel.btnp(pyxel.KEY_ESCAPE) or pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT):
            if m.back() == "quit":
                self._finish("__quit__")

    # --- dibujo ----------------------------------------------------------
    def draw(self):
        if self.model.view == "credits":
            self._draw_credits()
        elif self.model.view == "config":
            self._draw_config()
        elif self.model.view == "records":
            self._draw_records()
        else:
            self._draw_list()
        crt.apply(config.crt_level(self.cfg))    # el vidrio va al final de todo

    def _draw_header(self):
        pyxel.cls(BG)
        pyxel.rect(0, 0, W, HEAD_H, PANEL)
        pyxel.rect(0, HEAD_H, W, 1, LINE)
        blink = (pyxel.frame_count // 16) % 2 == 0
        if PORTRAIT:
            self._draw_horizon(34, HEAD_H)
        ctext(W / 2, 11, "M H W   R E T R O   F U T U R E", ACC if blink else HEAD)
        ctext(W / 2, 25, "el futuro, como se veía en 1985", DIM)
        if PORTRAIT:
            return
        # una línea de neón que se abre desde el centro, en cian y magenta: es
        # todo el guiño retrofuturista que se permite el header. probé un
        # abanico de rieles en perspectiva y en 7 px de alto no se lee como
        # horizonte, se lee como una estrella mal dibujada.
        for i in range(0, W // 2 - 6, 6):
            col = ACC if (i // 6) % 2 else PINK
            largo = 1 + i * 3 // W
            pyxel.rect(W // 2 + 4 + i, 35, largo + 2, 1, col)
            pyxel.rect(W // 2 - 6 - i, 35, largo + 2, 1, col)

    def _draw_horizon(self, top, bottom):
        """el atardecer synthwave de la cabecera vertical: estrellas, un sol
        rayado que se apoya en el horizonte y una grilla que avanza. en 50 px
        de alto sí se lee como paisaje (en los 7 px del menú apaisado no)."""
        f = pyxel.frame_count
        hor = top + (bottom - top) * 11 // 20
        for i in range(14):                         # estrellas que titilan
            sx = (i * 67 + 13) % W
            sy = top + (i * 29) % max(1, hor - top - 2)
            if (f // 20 + i) % 5:
                pyxel.pset(sx, sy, DIM if i % 3 else TXT)
        r = 17                                      # el sol, sólo la mitad de arriba
        cx = W // 2
        for dy in range(-r, 0):
            if dy > -r * 0.6 and (dy + f // 6) % 3 == 0:
                continue                            # las franjas, que bajan
            half = int(math.sqrt(r * r - dy * dy))
            pyxel.rect(cx - half, hor + dy, 2 * half + 1, 1, AMBER if dy < -r // 2 else PINK)
        pyxel.rect(0, hor, W, 1, ACC)               # el horizonte
        depth = bottom - hor
        for k in range(6):                          # líneas que se acercan
            t = ((k + (f % 30) / 30) / 6) ** 2
            y = hor + int(depth * t)
            if hor < y < bottom:
                pyxel.rect(0, y, W, 1, PINK if t > 0.45 else LINE)
        for i in range(-9, 10):                     # rieles hacia el sol
            pyxel.line(cx + i * 6, hor, cx + i * 34, bottom, LINE)

    def _draw_footer(self, hint):
        pyxel.rect(0, H - 14, W, 14, PANEL)
        pyxel.rect(0, H - 15, W, 1, LINE)
        ctext(W / 2, H - 10, hint, DIM)

    def _draw_list(self):
        self._draw_header()
        m = self.model
        for i, g in enumerate(m.games):
            self._draw_card(i, g)
        self._draw_special_row(m.records_row, "R É C O R D S", PINK)
        self._draw_special_row(m.credits_row, "C R É D I T O S", AMBER)
        self._draw_special_row(m.config_row, "S I S T E M A", SKY)
        self._draw_detail()
        self._draw_footer(_t("%d juegos en el cabinet" % len(m.games),
                             "flechas mover · enter elige"
                             + ("" if web.ACTIVE else " · esc salir")))

    def _row_box(self, i):
        """la caja de una fila: (x, y, ancho, alto, seleccionada)."""
        y, rh = self._row_y(i), self._rh()
        bh = rh - 3
        sel = self.model.cursor == i and self.model.view == "list"
        return MARGIN, y, W - 2 * MARGIN, bh, sel

    def _cursor_tri(self, x, y, bh, color):
        cy = y + bh // 2
        pyxel.tri(x + 5, cy - 3, x + 5, cy + 3, x + 10, cy, color)

    def _draw_card(self, i, g):
        x, y, w, bh, sel = self._row_box(i)
        ty = self._text_y(y, bh)
        pyxel.rect(x, y, w, bh, SEL if sel else PANEL)
        pyxel.rectb(x, y, w, bh, ACC if sel else LINE)
        if sel:
            self._cursor_tri(x, y, bh, ACC)
        text(x + 15, ty, g.title.upper(), ACC if sel else TXT2)
        tag = "%dx%d" % (g.width, g.height)
        text(x + w - len(tag) * CW - 5, ty, tag, TXT2 if sel else DIM)
        if g.badge:                         # "NUEVO": titila al lado del título
            bx = x + 15 + len(g.title) * CW + 6
            bw = len(g.badge) * CW + 4
            on = (pyxel.frame_count // 20) % 2 == 0
            pyxel.rect(bx, ty - 2, bw, 9, PINK if on else HEAD)
            text(bx + 2, ty, g.badge.upper(), BG)

    def _draw_special_row(self, i, label, color):
        x, y, w, bh, sel = self._row_box(i)
        pyxel.rectb(x, y, w, bh, color if sel else LINE)
        if sel:
            self._cursor_tri(x, y, bh, color)
        ctext(W / 2, self._text_y(y, bh), label, color if sel else DIM)

    # --- el panel de abajo: describe lo que apunta el cursor --------------
    def _detail_lines(self):
        """(líneas, color del título) de lo que está bajo el cursor."""
        m = self.model
        if m.cursor == m.records_row:
            return ("SALÓN DE LA FAMA", PINK,
                    ["los mejores de cada juego, todos juntos"], "")
        if m.cursor == m.credits_row:
            return ("CRÉDITOS", AMBER,
                    ["quién hizo qué en este cabinet"], "")
        if m.cursor == m.config_row:
            return ("SISTEMA", SKY,
                    ["pantalla, escala y modo crt — vale para todos"], "")
        g = m.games[m.cursor]
        cols = (W - 2 * MARGIN) // CW
        body = wrap(g.blurb, cols)[:4 if PORTRAIT else 2]
        if web.is_touch():
            if g.touch.get("hint"):
                body += wrap(g.touch["hint"], cols)[:1]
        elif g.controls:
            body.append(g.controls)
        best = scores.top(g.id, 1, self.board)
        record = "récord %s %d" % (best[0]["ini"], best[0]["score"]) if best else ""
        return (g.title.upper(), ACC, body, record)

    def _draw_detail(self):
        dh = self._detail_h()
        if dh < 20:                              # sin lugar: mejor nada que un
            return                               # panel cortado a la mitad
        y0 = H - FOOT_H - 1 - dh
        pyxel.rect(0, y0, W, dh, PANEL)
        pyxel.rect(0, y0, W, 1, LINE)
        title, col, body, right = self._detail_lines()
        text(MARGIN, y0 + 6, title, col)
        if right:
            text(W - MARGIN - len(right) * CW, y0 + 6, right, AMBER)
        y = y0 + 17
        for i, line in enumerate(body[:(dh - 12) // 9]):
            text(MARGIN, y, line, TXT if i == 0 else DIM)
            y += 9

    def _draw_credits(self):
        self._draw_header()
        y = HEAD_H + 12
        for s, col in credits_lines(self.model.games):
            if s:
                ctext(W / 2, y, s, col)
            y += 11
        self._draw_footer(_t("toca o volver para salir", "esc / clic para volver"))

    def _draw_config(self):
        self._draw_header()
        ctext(W / 2, HEAD_H + 10, "S I S T E M A", SKY)
        ctext(W / 2, HEAD_H + 22, "vale para todos los juegos", DIM)
        y0, rh = HEAD_H + 44, 20
        for i, key in enumerate(CONFIG_ITEMS):
            y = y0 + i * rh
            sel = i == self.model.cfg_cursor
            x, w = (16, W - 32) if PORTRAIT else (40, W - 80)
            pyxel.rect(x, y, w, rh - 4, SEL if sel else PANEL)
            pyxel.rectb(x, y, w, rh - 4, SKY if sel else LINE)
            text(x + 8, y + 5, CONFIG_LABEL[key], TXT2 if sel else TXT)
            val = "< %s >" % value_label(self.cfg, key)
            vx = x + w - 8 - len(val) * CW
            col = ACC if sel else DIM
            text(vx, y + 5, val, col)
        hint = MODE_HINT.get(self.cfg["screen_mode"], "") \
            if CONFIG_ITEMS[self.model.cfg_cursor] == "screen_mode" else ""
        if hint:
            ctext(W / 2, y0 + len(CONFIG_ITEMS) * rh + 8, hint, DIM)
        self._draw_footer(_t("cruceta: elegir y ajustar · volver",
                             "flechas: elegir y ajustar   esc volver"))

    def _draw_records(self):
        """el podio del emulador: los mejores de cada juego, en un solo lugar."""
        self._draw_header()
        ctext(W / 2, HEAD_H + 10, "S A L Ó N   D E   L A   F A M A", PINK)
        titles = {g.id: g.title for g in self.model.games}
        rows = [(gid, lst) for gid, lst in
                scores.hall([g.id for g in self.model.games], per=3,
                            board=self.board) if lst]
        if not rows:
            ctext(W / 2, HEAD_H + 60, "todavía no hay récords", DIM)
        else:
            # vertical: el juego en una línea y sus récords abajo, que a 240 de
            # ancho no entran al lado
            y = HEAD_H + 28
            for gid, lst in rows:
                text(22, y, titles.get(gid, gid).upper(), ACC)
                ex, ey = (22, y + 10) if PORTRAIT else (118, y)
                for j, e in enumerate(lst):
                    s = "%s %d" % (e["ini"], e["score"])
                    text(ex, ey, s, AMBER if j == 0 else TXT)
                    ex += len(s) * 4 + 8
                y += 24 if PORTRAIT else 16
        self._draw_footer(_t("toca o volver para salir", "esc / clic para volver"))


def _t(touch, keys):
    """el texto de tocar en el celular, el de teclas si no."""
    return touch if web.is_touch() else keys


def run_menu(out_path=None):
    return MenuApp(out_path).loop()


if __name__ == "__main__":
    run_menu(sys.argv[1] if len(sys.argv) > 1 else None)
