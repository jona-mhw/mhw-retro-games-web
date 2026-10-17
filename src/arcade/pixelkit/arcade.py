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
from pixelkit.pxtext import ctext, text

TITLE, PLAY, OVER, INITIALS, ATTRACT = range(5)
IDLE_TO_ATTRACT = 240                       # 4 s a 60 fps
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
        self.world = self.make_world()
        self.scene = PLAY
        web.touch("play")

    def _to_title(self):
        self.scene = TITLE
        self.idle = 0
        web.touch("nav")

    def update(self):
        self.anim += 1
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            if self.scene == TITLE:
                web.quit()                       # en la web: vuelve al menú
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

    def _draw_title(self):
        u, cx = self.ui, self.w / 2
        pyxel.cls(u.bg)
        pyxel.rect(0, 0, self.w, 3, u.accent)
        pyxel.rect(0, self.h - 3, self.w, 3, u.accent)
        ctext(cx, self.h * 0.20, spaced(self.title), u.accent)
        ctext(cx, self.h * 0.20 + 14, self.subtitle, u.dim)
        y = self.h * 0.44
        for line in self.howto:
            ctext(cx, y, line, u.text)
            y += 10
        if self.scoring:
            lst = scores.top(self.id, 3)
            if lst:
                ctext(cx, self.h - 58, "mejores", u.dim)
                yy = self.h - 47
                for i, e in enumerate(lst):
                    ctext(cx, yy, "%d  %s  %d" % (i + 1, e["ini"], e["score"]),
                          u.accent if i == 0 else u.text)
                    yy += 9
        else:
            ctext(cx, self.h - 44, "recreativo", u.accent)
        if self._blink():
            ctext(cx, self.h * 0.36, "enter para jugar", u.warn)

    def _draw_over(self):
        u, cx = self.ui, self.w / 2
        bw, bh = min(self.w - 24, 176), 52
        bx, by = int(cx - bw / 2), int(self.h / 2 - bh / 2)
        pyxel.rect(bx + 3, by + 3, bw, bh, u.shadow)
        pyxel.rect(bx, by, bw, bh, u.bg)
        pyxel.rectb(bx, by, bw, bh, u.warn if self.record else u.dim)
        if self.record:
            col = u.accent if self._blink(16) else u.warn
            ctext(cx, by + 9, "¡NUEVO RÉCORD!", col)
        else:
            ctext(cx, by + 9, "fin de la partida", u.text)
        ctext(cx, by + 24, "puntaje  %d" % self.last_score, u.text)
        hint = "enter para tus iniciales" if self.record else "enter para seguir"
        ctext(cx, by + 39, hint, u.dim)

    def _draw_initials(self):
        u, cx = self.ui, self.w / 2
        pyxel.cls(u.bg)
        pyxel.rect(0, 0, self.w, 3, u.warn)
        pyxel.rect(0, self.h - 3, self.w, 3, u.warn)
        ctext(cx, self.h * 0.22, spaced("RÉCORD"), u.warn)
        ctext(cx, self.h * 0.22 + 14, "puntaje  %d" % self.last_score, u.text)
        # las tres letras, grandes (2x), con el cursor titilando
        s = self.initials.chars
        gap = 26
        x0 = cx - gap
        for i, ch in enumerate(s):
            col = u.accent if i == self.initials.cur else u.text
            if i == self.initials.cur and not self._blink(15):
                col = u.warn
            _big_char(int(x0 + i * gap), int(self.h * 0.48), ch, col)
            if i == self.initials.cur:
                pyxel.rect(int(x0 + i * gap - 4), int(self.h * 0.48 + 20), 16, 2, u.accent)
        ctext(cx, self.h - 34, "arriba/abajo letra · izq/der mueve", u.dim)
        ctext(cx, self.h - 24, "enter confirma", u.dim)

    def _draw_attract(self):
        u, cx = self.ui, self.w / 2
        pyxel.cls(u.bg)
        # fondo con líneas diagonales que se mueven
        for i in range(-self.h, self.w, 16):
            x = i + (self.anim % 16)
            pyxel.line(x, 0, x - self.h, self.h, u.panel)
        ctext(cx, self.h * 0.12, spaced(self.title), u.accent)
        ctext(cx, self.h * 0.12 + 13, "mejores puntajes", u.dim)
        lst = scores.top(self.id, 5)
        y0 = self.h * 0.34
        beam = (self.anim // 22) % max(1, len(lst))     # resaltador que baja
        for i, e in enumerate(lst):
            appear = self.anim - i * 10
            if appear < 0:
                continue
            dx = max(0, 40 - appear * 4)                 # entra deslizando
            col = u.warn if i == beam else (u.accent if i == 0 else u.text)
            row = "%d   %s   %d" % (i + 1, e["ini"], e["score"])
            ctext(cx + dx, y0 + i * 12, row, col)
        if self._blink(20):
            ctext(cx, self.h - 18, "una tecla para volver", u.dim)


# fuente 2x hecha a mano para las 3 iniciales grandes ------------------------
def spaced(s):
    return "  ".join(s)


def _big_char(x, y, ch, col):
    """dibuja un carácter de la fuente de pyxel al doble, para las iniciales."""
    # se dibuja chico en una zona fuera de pantalla y se relee no es viable;
    # en su lugar, se dibuja el glifo normal escalado con rectángulos leyendo
    # cada píxel via un pyxel.Image temporal.
    img = _glyph_image()
    img.cls(0)
    img.text(0, 0, ch, 7)
    for gy in range(6):
        for gx in range(4):
            if img.pget(gx, gy) == 7:
                pyxel.rect(x + gx * 2, y + gy * 2, 2, 2, col)


_GLYPH = None


def _glyph_image():
    global _GLYPH
    if _GLYPH is None:
        _GLYPH = pyxel.Image(8, 8)
    return _GLYPH
