"""dibujar y medir, las dos cosas que pyxel no te da servidas.

fast_blit copia un bytearray de índices de paleta directo al framebuffer en un
solo memcpy — el truco que sostiene el framerate cuando pintas la pantalla
entera cada frame. FpsMeter mide fps a mano porque `pyxel.avg_fps` no existe en
pyxel 2.9.8.
"""
import time

import pyxel


def fast_blit(buf, n=None):
    """copia buf (bytes de índices de paleta) al framebuffer de pyxel.

    devuelve True si logró el camino rápido (un memcpy), False si falló y hay
    que caer a blit_slow. `n` = cuántos bytes copiar, por defecto todos.
    el `.cast("B")` es obligatorio: sin él el slice revienta con
    `NotImplementedError: unsupported format <B`.
    """
    if n is None:
        n = len(buf)
    try:
        memoryview(pyxel.screen.data_ptr()).cast("B")[0:n] = buf
        return True
    except Exception:
        return False


def blit_slow(buf, w, h):
    """respaldo pset a pset, por si data_ptr no estuviera disponible."""
    pset = pyxel.pset
    i = 0
    for y in range(h):
        for x in range(w):
            if buf[i]:
                pset(x, y, buf[i])
            i += 1


class FpsMeter:
    """fps promediado cada `every` frames. `pyxel.avg_fps` no existe en 2.9.8.

    `tick()` devuelve el fps y deja `updated=True` sólo en el frame en que
    recalcula, por si querés colgar de ahí otras cuentas caras (contar
    partículas, por ejemplo) sin hacerlas los 60 frames.
    """

    def __init__(self, every=20):
        self.every = every
        self.fps = 0.0
        self.updated = False
        self._t = time.perf_counter()
        self._n = 0

    def tick(self):
        self._n += 1
        self.updated = False
        if self._n >= self.every:
            now = time.perf_counter()
            self.fps = self._n / (now - self._t)
            self._t, self._n = now, 0
            self.updated = True
        return self.fps
