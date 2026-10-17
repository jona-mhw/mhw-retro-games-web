"""paletas indexadas para pyxel.

la idea que hace volar a estos juegos: el byte de cada celda de la grilla ES el
índice de paleta, no el tipo de material. cada material ocupa un rango contiguo
de tonos, así la textura viaja con la partícula al moverse y el frame entero se
dibuja copiando el arreglo al framebuffer de una sola vez (ver pixelkit.blit).
una tabla `kind` de 256 bytes traduce un índice de vuelta a su material cuando
la lógica necesita saber qué es. pyxel acepta 256 colores, no sólo los 16 del
preset.
"""


def shades(rgb, n, lo=0.78, hi=1.16):
    """n tonos de un color, multiplicando de lo*rgb a hi*rgb.

    n=1 devuelve el color tal cual. sirve para que un material no sea un bloque
    plano: cada partícula toma un tono del rango y el material respira.
    """
    r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
    out = []
    for i in range(n):
        t = 1.0 if n == 1 else lo + (hi - lo) * i / (n - 1)
        out.append((min(255, int(r * t)) << 16) |
                   (min(255, int(g * t)) << 8) | min(255, int(b * t)))
    return out


class Palette:
    """arma una paleta de 256 colores registrando materiales por tramos.

    cada material queda en un rango contiguo de índices: `base[k]` es el primer
    índice, `nvar[k]` cuántos tonos, y `kind[i]` traduce un índice de vuelta a
    su material. el índice 0 es el vacío. ejemplo (así arranca la plantilla):

        pal = Palette()
        pal.add(SAND, shades(0xE8C96A, 5))
        pal.mark_active()                 # lo inerte va antes de esta marca
        pal.add(WATER, shades(0x3A72D8, 4))
        pal.set(UI_TXT, 0xE8ECF5)         # colores sueltos de la interfaz
        pal.finalize()
        pyxel.colors[:] = pal.colors

    el orden importa: registra primero lo que no se mueve y llama a
    `mark_active()`. así el bucle de simulación descarta lo inerte con una sola
    comparación (`indice < first_active`) sin mirar la tabla kind.
    """

    def __init__(self, empty=0x0D0D14):
        self.colors = [empty]
        self.kind = bytearray(256)
        self.base = {}
        self.nvar = {}
        self.first_active = 1

    def add(self, kind, tones):
        """registra un material con su lista de tonos. devuelve self (encadena)."""
        self.base[kind] = len(self.colors)
        self.nvar[kind] = len(tones)
        for c in tones:
            self.kind[len(self.colors)] = kind
            self.colors.append(c)
        return self

    def mark_active(self):
        """marca el corte: todo lo agregado a partir de aquí cuenta como activo."""
        self.first_active = len(self.colors)
        return self

    def set(self, index, rgb):
        """fija un índice suelto, para los colores de la interfaz."""
        while len(self.colors) <= index:
            self.colors.append(0)
        self.colors[index] = rgb
        return self

    def finalize(self):
        """rellena hasta 256 y congela la tabla kind. llamar al final."""
        while len(self.colors) < 256:
            self.colors.append(0)
        self.kind = bytes(self.kind)
        return self
