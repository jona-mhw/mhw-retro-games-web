"""bots para probar y calibrar neón, sin ventana (los usa test_neon.py).

`dodger` esquiva mirando unos frames adelante: prueba nueve direcciones y se
queda con la que más lejos lo deja de las balas, con preferencia por ponerse
debajo de lo que hay que matar. no es un jugador humano, pero aguanta lo
suficiente para medir puntajes y ver que el jefe se puede pasar.
"""
import math

from games.neon.logic import (BR, H, HUD_H, P_FOCUS, P_SPEED, SEC_END, W)

DIRS = [(0, 0)] + [(math.cos(a * math.pi / 4), math.sin(a * math.pi / 4))
                   for a in range(8)]
LOOK = (3, 6, 10, 15)


def _target_x(g):
    b = g.boss
    if b is not None and b.state in ("fight", "enter", "break"):
        return b.x
    best, by = None, -1
    for f in g.foes:
        if not f.wait and 0 < f.y < H * 0.7:
            w = f.y + (200 if f.kind >= 3 else 0)   # lo grande primero
            if w > by:
                best, by = f.x, w
    return best


def dodger(g, skill=1.0, bombs=True):
    """devuelve (mx, my, focus, bomb) para este frame."""
    if g.sec == SEC_END or not g.alive():
        return 0.0, 0.0, False, False
    px, py = g.px, g.py
    near = []
    for b in g.eb:
        dx, dy = b[0] - px, b[1] - py
        if -50 < dx < 50 and -60 < dy < 40:
            near.append((b[0], b[1], b[2], b[3], BR[b[4]]))
    for f in g.foes:
        if not f.wait and abs(f.x - px) < 50 and -60 < f.y - py < 30:
            vx = vy = 0.0
            if f.kind == 2 and f.t >= 90:           # kamikaze tirándose
                vx, vy = math.cos(f.a) * 4, math.sin(f.a) * 4
            elif f.kind == 0:
                vx, vy = (0.0, 1.35) if f.mode else (f.vx, f.vy)
            near.append((f.x, f.y, vx, vy, max(f.hw, f.hh)))
    b = g.boss
    if b is not None:
        near.append((b.x, b.y, 0.0, 0.0, b.hh + 4))
    focus = len(near) > 10 and g.power >= 2
    sp = P_FOCUS if focus else P_SPEED
    tx = _target_x(g)
    ty = H - 50
    for it in g.items:                          # los ítems valen el desvío
        if it[1] > HUD_H + 20:
            tx, ty = it[0], max(H * 0.45, it[1])
            break
    best, bscore, bmin = (0, 0), -1e9, 99.0
    for ux, uy in DIRS:
        mn = 40.0
        for k in LOOK:
            qx = min(W - 6, max(6, px + ux * sp * k))
            qy = min(H - 8, max(HUD_H + 12, py + uy * sp * k))
            for bx, by, bvx, bvy, r in near:
                ex = bx + bvx * k - qx
                ey = by + bvy * k - qy
                d = math.sqrt(ex * ex + ey * ey) - r
                if d < mn:
                    mn = d
        qx = px + ux * sp * 6
        qy = py + uy * sp * 6
        s = min(mn, 14.0 * skill) * 3
        if tx is not None:
            s -= abs(qx - tx) * 0.08
        s -= abs(qy - ty) * (0.08 if ty != H - 50 else 0.03)
        s -= abs(qx - W / 2) * 0.01
        if s > bscore:
            bscore, best, bmin = s, (ux, uy), mn
    bomb = bombs and bmin < 1.5 and g.bombs > 0 and g.vulnerable()
    return best[0] * sp, best[1] * sp, focus, bomb


def idle(g):
    return 0.0, 0.0, False, False


def play(g, policy=dodger, max_frames=20000):
    """juega una partida entera; devuelve cuántos frames duró."""
    n = 0
    while not g.done and n < max_frames:
        g.step(*policy(g))
        n += 1
    return n


class Human:
    """un jugador más de carne y hueso: decide cada `react` frames (y mientras
    tanto sigue con lo último), ve las balas con un margen chico y a veces se
    distrae. `bombs` dice si sabe usar la bomba cuando se ve encerrado."""

    def __init__(self, rng, react=6, skill=0.55, slip=0.04, bombs=True):
        self.rng = rng
        self.react = react
        self.skill = skill
        self.slip = slip
        self.bombs = bombs
        self.k = 0
        self.last = (0.0, 0.0, False, False)
        self.__name__ = "human"

    def __call__(self, g):
        self.k += 1
        if self.k % self.react:
            mx, my, focus, _ = self.last
            return mx, my, focus, False
        if self.rng.random() < self.slip:
            a = self.rng.random() * math.tau
            self.last = (math.cos(a) * P_SPEED, math.sin(a) * P_SPEED, False, False)
            return self.last
        mx, my, focus, bomb = dodger(g, skill=self.skill, bombs=self.bombs)
        if bomb and self.rng.random() < 0.4:
            bomb = False                        # se le olvidó
        self.last = (mx, my, focus, False)
        return mx, my, focus, bomb
