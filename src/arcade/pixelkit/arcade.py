"""el Cabinet: la parafernalia de sala recreativa, una sola vez, para todos.

un juego se enchufa acá y hereda gratis: pantalla de título, attract mode a los
4 segundos de no tocar nada (con los mejores puntajes animados), fin de partida,
y la entrada de 3 iniciales cuando hacés un récord. el juego sólo aporta su
"mundo" (update/draw/over/score) y su ficha.

    class Game:
        def __init__(self):
            Cabinet(
                game_id="culebra", title="CULEBRA",
                subtitle="comé, crecé, no te muerdas",
                howto=["flechas mueven", "cada manzana acelera", "no te muerdas"],
                width=W, height=H, palette=PAL,
                ui=UIColors(bg=BG, text=TXT, dim=DIM, accent=GREEN,
                            warn=RED, shadow=SHADOW),
                make_world=lambda: World(),
            ).run()

el mundo es un objeto con update(), draw(), y los atributos over (bool) y
score (int). nada de manejar ESC ni título: de eso se encarga el Cabinet.
"""
import pyxel

from pixelkit import config, crt, scores, web
from pixelkit.pxtext import big_ctext, big_width, ctext, text

TITLE, PLAY, OVER, INITIALS, ATTRACT, READY, PAUSE = range(7)
IDLE_TO_ATTRACT = 240                       # 4 s a 60 fps
COUNT_STEP = 34      # frames de cada número de la cuenta regresiva (3, 2, 1)
GO_FRAMES = 36       # el "¡YA!" se queda encima mientras el juego ya corre
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
_WAKE = (pyxel.KEY_RETURN, pyxel.KEY_SPACE, pyxel.KEY_UP, pyxel.KEY_DOWN,
         pyxel.KEY_LEFT, pyxel.KEY_RIGHT, pyxel.KEY_W, pyxel.KEY_A,
         pyxel.KEY_S, pyxel.KEY_D, pyxel.KEY_X, pyxel.MOUSE_BUTTON_LEFT)


class UIColors:
    """los índices de paleta que el Cabinet usa para su parte de la interfaz."""

    def __init__(self, bg, text, dim, accent, warn, shadow, panel=None):
        self.bg = bg
        self.text = text
        self.dim = dim
        self.accent = accent
        self.warn = warn
        self.shadow = shadow
        self.panel = panel if panel is not None else shadow


class Initials:
    """entrada de 3 iniciales: arriba/abajo cambia letra, izq/der mueve, enter
    confirma (avanza y cierra en la última)."""

    def __init__(self, seed="AAA"):
        self.chars = list((seed + "AAA")[:3])
        self.cur = 0
        self.done = False

    def _cycle(self, d):
        i = ALPHABET.index(self.chars[self.cur])
        self.chars[self.cur] = ALPHABET[(i + d) % len(ALPHABET)]

    def update(self):
        if pyxel.btnp(pyxel.KEY_UP, 14, 3) or pyxel.btnp(pyxel.KEY_W, 14, 3):
            self._cycle(1)
        if pyxel.btnp(pyxel.KEY_DOWN, 14, 3) or pyxel.btnp(pyxel.KEY_S, 14, 3):
            self._cycle(-1)
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A):
            self.cur = (self.cur - 1) % 3
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D):
            self.cur = (self.cur + 1) % 3
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            if self.cur < 2:
                self.cur += 1
            else:
                self.done = True

    def value(self):
        return "".join(self.chars)


def _woke():
    return any(pyxel.btnp(k) for k in _WAKE)


class Cabinet:
    def __init__(self, *, game_id, title, subtitle, howto, width, height,
                 palette, ui, make_world, scale=3, scoring=True):
        self.id = game_id
        self.title = title
        self.subtitle = subtitle
        self.howto = howto
        self.w, self.h = width, height
        self.palette = palette
        self.ui = ui
        self.make_world = make_world
        self.scale = scale
        self.scoring = scoring
        self._shade = None        # tabla color -> su sombra, para el velo

    # --- ciclo -----------------------------------------------------------
    def run(self):
        pyxel.init(self.w, self.h, title=self.id, fps=60,
                   display_scale=self.scale, quit_key=pyxel.KEY_NONE)
        pyxel.colors[:] = self.palette
        pyxel.mouse(True)
        self.crt = config.crt_level(config.apply())
        self.scene = TITLE
        self.idle = 0
        self.anim = 0
        self.world = None
        self.last_score = 0
        self.record = False
        self.initials = None
        self.last_ini = "AAA"
        web.touch("nav")
        pyxel.run(self.update, self.draw)

    def _start(self):
        """partida nueva: el mundo se arma ya (se ve detrás de la cuenta) pero
        no corre hasta el ¡YA!. así nadie arranca perdiendo medio segundo."""
        self.world = self.make_world()
        self._ready(3)
        web.touch("play")

    def _ready(self, n):
        """cuenta regresiva desde n (3 al empezar, 1 al volver de la pausa)."""
        self.scene = READY
        self.anim = (3 - n) * COUNT_STEP
        self.go = 0

    def _pause(self):
        self.scene = PAUSE
        self.anim = 0
        web.touch("pause")

    def _to_title(self):
        self.scene = TITLE
        self.idle = 0
        web.touch("nav")

    def update(self):
        self.anim += 1
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            if self.scene == TITLE:
                web.quit()                       # en la web: vuelve al menú
            elif self.scene in (PLAY, READY):    # jugando, esc pausa: un toque
                self._pause()                    # sin querer no tira la partida
            else:
                self._to_title()
            return
        if self.scene == TITLE:
            self._upd_title()
        elif self.scene == PLAY:
            self._upd_play()
        elif self.scene == OVER:
            self._upd_over()
        elif self.scene == INITIALS:
            self._upd_initials()
        elif self.scene == ATTRACT:
            self._upd_attract()
        elif self.scene == READY:
            self._upd_ready()
        elif self.scene == PAUSE:
            self._upd_pause()

    def _upd_ready(self):
        if self.anim >= 3 * COUNT_STEP:
            self.scene = PLAY
            self.go = GO_FRAMES

    def _upd_pause(self):
        if self.anim < 10:                       # que el mismo toque no la saque
            return
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE) \
                or pyxel.btnp(pyxel.KEY_P) or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self._ready(1)
            web.touch("play")

    def _upd_title(self):
        if _woke():
            self.idle = 0
        else:
            self.idle += 1
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE) \
                or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self._start()
        elif self.idle >= IDLE_TO_ATTRACT:
            self.scene = ATTRACT
            self.anim = 0

    def _upd_play(self):
        # p pausa, y en el celular se pausa sola si te vas a otra app
        if pyxel.btnp(pyxel.KEY_P) or web.page_hidden():
            self._pause()
            return
        self.go = max(0, self.go - 1)
        self.world.update()
        if getattr(self.world, "over", False):
            self.last_score = int(getattr(self.world, "score", 0))
            self.record = self.scoring and scores.qualifies(self.id, self.last_score)
            self.scene = OVER
            self.anim = 0
            web.touch("nav")

    def _upd_over(self):
        if self.anim < 24:                       # un respiro antes de aceptar tecla
            return
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE) \
                or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):  # o tocar la pantalla
            if self.record:
                self.initials = Initials(self.last_ini)
                self.scene = INITIALS
            else:
                self._to_title()

    def _upd_initials(self):
        self.initials.update()
        if self.initials.done:
            self.last_ini = self.initials.value()
            scores.add(self.id, self.last_ini, self.last_score)   # graba ya
            self._to_title()

    def _upd_attract(self):
        if _woke():
            self._to_title()

    # --- dibujo ----------------------------------------------------------
    def draw(self):
        if self.scene == PLAY:
            self.world.draw()
            if self.go:
                self._draw_go()
        elif self.scene == READY:
            self.world.draw()
            self._draw_count()
        elif self.scene == PAUSE:
            self.world.draw()
            self._draw_pause()
        elif self.scene == OVER:
            self.world.draw()
            self._draw_over()
        elif self.scene == INITIALS:
            self._draw_initials()
        elif self.scene == ATTRACT:
            self._draw_attract()
        else:
            self._draw_title()
        crt.apply(getattr(self, "crt", crt.OFF))   # el vidrio, al final de todo

    def _blink(self, period=30):
        return (self.anim // period) % 2 == 0

    # las pantallas del cabinet se arman en proporción al alto, así sirven
    # igual en un juego apaisado (320x240) que en uno vertical (240x360). lo
    # importante (título, puntaje, iniciales) va con el texto grande: la
    # fuente de pyxel mide 4x6 y en el celular se lee chica.
    def _backdrop(self, col, step=16, speed=2):
        """diagonales que se corren lento: movimiento sin competir con el texto."""
        off = (self.anim // speed) % step
        for i in range(-self.h, self.w + step, step):
            x = i + off
            pyxel.line(x, 0, x + self.h, self.h, col)

    def _frame(self, col):
        pyxel.rect(0, 0, self.w, 3, col)
        pyxel.rect(0, self.h - 3, self.w, 3, col)

    def _panel(self, x, y, w, h, border):
        x, y, w, h = int(x), int(y), int(w), int(h)
        pyxel.rect(x + 3, y + 3, w, h, self.ui.shadow)
        pyxel.rect(x, y, w, h, self.ui.bg)
        pyxel.rectb(x, y, w, h, border)

    def _title_scale(self):
        """el título lo más grande que quepa, de 4x a 2x."""
        for s in (4, 3):
            if big_width(self.title, s) <= self.w - 20:
                return s
        return 2

    def _draw_title(self):
        u, cx, w, h = self.ui, self.w / 2, self.w, self.h
        pyxel.cls(u.bg)
        self._backdrop(u.panel, speed=3)
        self._frame(u.accent)
        # el título, grande y con sombra honda, y un brillo que lo recorre
        s = self._title_scale()
        ty = int(h * 0.09)
        big_ctext(cx + 2, ty + 2, self.title, u.shadow, s)
        big_ctext(cx, ty, self.title, u.accent, s)
        tw = big_width(self.title, s)
        ly = ty + 6 * s + 3
        pyxel.rect(cx - tw / 2, ly, tw, 1, u.dim)
        sx = (self.anim * 2) % (tw + 60) - 30
        pyxel.rect(cx - tw / 2 + max(0, sx), ly, max(0, min(18, tw - max(0, sx))), 1, u.text)
        ctext(cx, ly + 7, self.subtitle, u.text)
        # el llamado a jugar, en una píldora que titila
        py = int(h * (0.30 if h > w else 0.33))
        call = _t("toca para jugar", "enter para jugar")
        pw = big_width(call, 1) + 18
        lit = self._blink()
        pyxel.rect(cx - pw / 2, py - 4, pw, 13, u.warn if lit else u.bg)
        pyxel.rectb(cx - pw / 2, py - 4, pw, 13, u.warn)
        ctext(cx, py, call, u.bg if lit else u.warn)
        # cómo se juega, en su panel
        bw = min(w - 20, 220)
        lines = self.howto[:6]
        hy = int(h * (0.41 if h > w else 0.43))
        hh = 16 + 10 * len(lines)
        self._panel(cx - bw / 2, hy, bw, hh, u.dim)
        ctext(cx, hy + 5, "cómo se juega", u.accent)
        for i, line in enumerate(lines):
            ctext(cx, hy + 16 + i * 10, line, u.text)
        # los récords abajo. en vertical sobra alto: los tres con número
        # grande; apaisado, el primero grande y los otros dos en una línea
        if self.scoring:
            lst = scores.top(self.id, 3)
            if lst:
                tall = h > w
                rh = 16 + 20 * len(lst) if tall else 52
                ry = max(hy + hh + 10, h - rh - 12)
                self._panel(cx - bw / 2, ry, bw, rh, u.accent)
                ctext(cx, ry + 5, "mejores", u.dim)
                if tall:
                    for i, e in enumerate(lst):
                        big_ctext(cx, ry + 16 + 20 * i, "%d %s %6d" % (i + 1, e["ini"], e["score"]),
                                  u.accent if i == 0 else u.text, 2, u.shadow)
                else:
                    first = lst[0]
                    big_ctext(cx, ry + 15, "%s %d" % (first["ini"], first["score"]),
                              u.accent, 2, u.shadow)
                    rest = "   ".join("%d %s %d" % (i + 2, e["ini"], e["score"])
                                      for i, e in enumerate(lst[1:]))
                    ctext(cx, ry + 36, rest, u.text)
        else:
            ctext(cx, h - 30, "recreativo: sin reloj ni puntaje", u.accent)

    def _draw_over(self):
        u, cx = self.ui, self.w / 2
        self._veil()
        bw, bh = min(self.w - 20, 200), 92
        bx, by = int(cx - bw / 2), int(self.h / 2 - bh / 2)
        self._panel(bx, by, bw, bh, u.warn if self.record else u.accent)
        if self.record:
            col = u.accent if self._blink(16) else u.warn
            big_ctext(cx, by + 9, "¡RÉCORD!", col, 2, u.shadow)
        else:
            ctext(cx, by + 11, "fin de la partida", u.text)
        ctext(cx, by + 30, "puntaje", u.dim)
        score = str(self.last_score)
        s = 3 if big_width(score, 3) <= bw - 16 else 2
        big_ctext(cx, by + 41, score, u.text, s, u.shadow)
        if self.record:
            hint = _t("toca: tus iniciales", "enter para tus iniciales")
        else:
            hint = _t("toca para seguir", "enter para seguir")
        if self.anim >= 24:
            ctext(cx, by + bh - 13, hint, u.accent if self._blink(20) else u.dim)

    def _draw_initials(self):
        u, cx, h = self.ui, self.w / 2, self.h
        pyxel.cls(u.bg)
        self._backdrop(u.panel)
        self._frame(u.warn)
        big_ctext(cx, int(h * 0.16), "¡RÉCORD!", u.warn, 3, u.shadow)
        ctext(cx, int(h * 0.16) + 26, "puntaje", u.dim)
        big_ctext(cx, int(h * 0.16) + 36, str(self.last_score), u.text, 2, u.shadow)
        # las tres letras, a 4x, con el cursor titilando
        s = self.initials.chars
        gap = 30
        y = int(h * 0.50)
        for i, ch in enumerate(s):
            x = int(cx + (i - 1) * gap)
            cur = i == self.initials.cur
            pyxel.rect(x - 11, y - 6, 22, 36, u.panel)
            pyxel.rectb(x - 11, y - 6, 22, 36, u.accent if cur else u.dim)
            col = u.text
            if cur:
                col = u.accent if self._blink(15) else u.warn
            big_ctext(x, y, ch, col, 4)
            if cur:
                pyxel.tri(x - 4, y - 10, x + 4, y - 10, x, y - 14, u.accent)
                pyxel.tri(x - 4, y + 32, x + 4, y + 32, x, y + 36, u.accent)
        ctext(cx, h - 34, "arriba/abajo letra · izq/der mueve", u.dim)
        ctext(cx, h - 24, _t("OK confirma", "enter confirma"), u.text)

    def _draw_attract(self):
        u, cx, h = self.ui, self.w / 2, self.h
        pyxel.cls(u.bg)
        self._backdrop(u.panel, speed=1)
        self._frame(u.accent)
        s = self._title_scale()
        big_ctext(cx + 2, int(h * 0.09) + 2, self.title, u.shadow, s)
        big_ctext(cx, int(h * 0.09), self.title, u.accent, s)
        ctext(cx, int(h * 0.09) + 6 * s + 8, "mejores puntajes", u.text)
        lst = scores.top(self.id, 5)
        y0 = int(h * 0.30)
        step = min(26, int((h * 0.58) / 5))
        beam = (self.anim // 22) % max(1, len(lst))     # resaltador que baja
        bw = min(self.w - 20, 200)
        for i, e in enumerate(lst):
            appear = self.anim - i * 10
            if appear < 0:
                continue
            dx = max(0, 40 - appear * 4)                 # entra deslizando
            y = y0 + i * step
            if i == beam:
                pyxel.rect(cx - bw / 2 + dx, y - 4, bw, 20, u.panel)
            col = u.warn if i == beam else (u.accent if i == 0 else u.text)
            row = "%d %s %6d" % (i + 1, e["ini"], e["score"])
            big_ctext(cx + dx, y, row, col, 2, u.shadow)
        if self._blink(20):
            ctext(cx, h - 18, _t("toca para volver", "una tecla para volver"), u.dim)

    # --- cuenta regresiva y pausa ------------------------------------------
    def _veil(self):
        """oscurece el juego para que lo de encima se lea. de verdad: cada
        color del framebuffer pasa a su gemelo en sombra (el más parecido de
        la paleta a ese color apagado). si eso no se puede, un tramado."""
        try:
            if self._shade is None:
                self._shade = _shade_map(self.palette)
            mv = memoryview(pyxel.screen.data_ptr()).cast("B")
            mv[:] = bytes(mv).translate(self._shade)
        except Exception:
            self._shade = False
        if self._shade is False:
            pyxel.dither(0.55)
            pyxel.rect(0, 0, self.w, self.h, self.ui.shadow)
            pyxel.dither(1.0)

    def _draw_count(self):
        u = self.ui
        self._veil()
        n = 3 - self.anim // COUNT_STEP
        t = (self.anim % COUNT_STEP) / COUNT_STEP          # 0 -> 1 dentro del número
        scale = 6 if t < 0.15 else 5                       # golpe al aparecer
        col = (u.warn, u.accent, u.text)[max(0, min(2, 3 - n))]
        # va en el tercio de arriba: al medio suelen estar los carteles de
        # entrada de cada juego ("¡DESPEGUE!", "OLEADA 1") y se pisaban
        _big_text(self.w / 2, self.h * 0.3, str(n), col, scale, u.shadow)
        ctext(self.w / 2, self.h * 0.3 + 24, "¡prepárate!", u.text)

    def _draw_go(self):
        u = self.ui
        k = self.go / GO_FRAMES                            # 1 -> 0
        if self.go % 6 < 4 or k < 0.5:
            _big_text(self.w / 2, self.h * 0.3, "¡YA!", u.accent, 3 + int(3 * k), u.shadow)

    def _draw_pause(self):
        u, cx = self.ui, self.w / 2
        self._veil()
        bw, bh = min(self.w - 20, 170), 56
        bx, by = int(cx - bw / 2), int(self.h / 2 - bh / 2)
        pyxel.rect(bx + 3, by + 3, bw, bh, u.shadow)
        pyxel.rect(bx, by, bw, bh, u.bg)
        pyxel.rectb(bx, by, bw, bh, u.accent)
        _big_text(cx, by + 16, "PAUSA", u.accent, 2, u.shadow)
        ctext(cx, by + 32, _t("OK o toca para seguir", "enter para seguir"), u.text)
        ctext(cx, by + 43, _t("volver: sale al título", "esc: sale al título"), u.dim)


def _shade_map(palette, k=0.38):
    """tabla de 256 bytes: cada índice -> el color de la paleta más parecido a
    ese mismo color apagado (k de brillo, con un dejo azul de noche). sirve
    para bytes.translate sobre la pantalla."""
    rgb = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in palette]
    out = bytearray(range(256))
    for i, (r, g, b) in enumerate(rgb[:256]):
        tr, tg, tb = r * k, g * k, b * k + 6
        out[i] = min(range(len(rgb)), key=lambda j: (rgb[j][0] - tr) ** 2 * 3
                     + (rgb[j][1] - tg) ** 2 * 4 + (rgb[j][2] - tb) ** 2 * 2)
    return bytes(out)


# fuente 2x hecha a mano para las 3 iniciales grandes ------------------------
def spaced(s):
    return "  ".join(s)


def _t(touch, keys):
    """el texto que corresponde: el de tocar en el celular, el de teclas si no."""
    return touch if web.is_touch() else keys


def _big_text(cx, cy, s, col, scale=2, shadow=None):
    """texto grande centrado en (cx, cy), escalando la fuente de pyxel píxel a
    píxel. entiende "¡" (el "!" dado vuelta), que la fuente no trae."""
    img = _glyph_image()
    w = len(s) * 4 * scale
    x0 = int(cx - w / 2 + scale / 2)
    y0 = int(cy - 3 * scale)
    for i, ch in enumerate(s):
        flip = ch == "¡"
        img.cls(0)
        img.text(0, 0, "!" if flip else ch, 7)
        for gy in range(5):                  # los glifos usan 5 filas de 6
            for gx in range(4):
                if img.pget(gx, (4 - gy) if flip else gy) == 7:
                    px, py = x0 + (i * 4 + gx) * scale, y0 + gy * scale
                    if shadow is not None:
                        pyxel.rect(px + 1, py + 1, scale, scale, shadow)
                    pyxel.rect(px, py, scale, scale, col)


_GLYPH = None


def _glyph_image():
    global _GLYPH
    if _GLYPH is None:
        _GLYPH = pyxel.Image(8, 8)
    return _GLYPH
