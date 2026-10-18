# pruebas de la simulación, sin abrir ventana: `python test_powder.py`
#
# varias de estas nacieron de bugs reales. las que miden geometría verifican
# primero que las piezas se toquen: montar mal la escena da un falso fallo.
import random
import time

from games.powder.game import (CATS, CELL_H, CELL_W, CHB, CSS, CW, ESCENAS, H, KIND,
                    NB8, NCHUNK, SH, TAB_H, TAB_W, TOOLS, W, App, Sim, cell_box,
                    tool_at, K_ACID, K_BHOLE, K_CLONE, K_EMBER, K_EMPTY, K_FIRE,
                    K_FWORK, K_GAS, K_ICE, K_LAVA, K_LEAF, K_MCOOL, K_METAL,
                    K_OIL, K_PLANT, K_PLASMA, K_POWDER, K_ROCKET, K_SAND,
                    K_SEED, K_SNOW, K_SPARK, K_STONE, K_TRUNK,
                    K_VIRUS, K_WALL, K_WATER)

FALLAS = []


def chk(cond, msg):
    if not cond:
        FALLAS.append(msg)
        print("   !! FALLA:", msg)


def cuenta(s, k):
    return sum(1 for c in s.g if KIND[c] == k)


def tocan(s, k1, k2):
    """(x, y) de una celda k1 con una k2 al lado, o None si no se tocan"""
    for y in range(1, SH - 1):
        for x in range(1, W - 1):
            if KIND[s.g[y * W + x]] == k1:
                for dx, dy in NB8:
                    if KIND[s.g[(y + dy) * W + x + dx]] == k2:
                        return (x, y)
    return None


def flotantes(s):
    """sólidos con vacío debajo EN UN CHUNK DORMIDO. si el despertar de chunks
       falla aparecen justo en las fronteras (y = 31/32, 63/64, ...)

    que el chunk esté dormido es la mitad que importa: un grano en pleno vuelo
    también tiene vacío debajo y no tiene nada de malo — su chunk está despierto
    y el frame que viene sigue cayendo. sin esa condición la prueba falla por una
    celda de piedra que la gotera de lava del demo acaba de fabricar sobre el
    océano, y que 400 frames después ya cayó.
    """
    return [(x, y) for y in range(SH - 1) for x in range(W)
            if KIND[s.g[y * W + x]] in (K_SAND, K_POWDER, K_STONE)
            and s.g[(y + 1) * W + x] == 0
            and not s.active[(y >> CHB) * CW + (x >> CHB)]]


def correr(s, n):
    for _ in range(n):
        s.step()


def rellena(s, x0, x1, y0, y1, kind, life=0):
    for y in range(y0, y1):
        for x in range(x0, x1):
            s.put(y * W + x, kind, life)
            s.wake(x, y)


def estanque(alto=45):
    """agua contenida entre muros y ya asentada"""
    s = Sim()
    rellena(s, 60, 200, SH - alto, SH, K_WATER)
    for y in range(SH - alto - 5, SH):
        s.put(y * W + 59, K_WALL)
        s.put(y * W + 200, K_WALL)
    correr(s, 100)
    return s


# --- chunks: lo que se rompe primero si el despertar está mal ---

def test_chunks():
    s = Sim()
    puestos = 0
    for cx in (20, 64, 96, 128, 190):      # tres caen justo en una frontera
        for y in range(2, 30):
            for x in range(cx - 3, cx + 4):
                s.put(y * W + x, K_SAND)
                s.wake(x, y)
                puestos += 1
    correr(s, 900)
    quedan = cuenta(s, K_SAND)
    fl = flotantes(s)
    print(f"chunks: {puestos} granos -> {quedan}, flotando {len(fl)}, "
          f"chunks despiertos al reposar {s.awake}/{NCHUNK}")
    chk(quedan == puestos, "se perdió masa al cruzar chunks")
    chk(not fl, f"granos flotando (mira las fronteras): {fl[:5]}")
    chk(s.awake == 0, "los chunks no se duermen con la escena en reposo")


def test_chunk_vecino():
    """el caso clásico: algo se libera en el chunk de abajo y el de arriba
       tiene que despertar solo"""
    s = Sim()
    rellena(s, 48, 53, 20, 32, K_SAND)
    for x in range(48, 53):
        s.put(32 * W + x, K_PLANT)
        s.wake(x, 32)
    for y in range(20, 60):
        s.put(y * W + 47, K_WALL)
        s.put(y * W + 53, K_WALL)
        s.wake(47, y)
        s.wake(53, y)
    correr(s, 30)
    s.paint(50, 34, K_FIRE, 2)
    correr(s, 600)
    bajo = sum(1 for y in range(40, SH) for x in range(46, 55)
               if KIND[s.g[y * W + x]] == K_SAND)
    print(f"chunk vecino: {bajo} granos bajaron al quemarse el soporte")
    chk(bajo > 20, "el chunk de arriba no despertó al liberarse el de abajo")


# --- materiales ---

def _piso(s, y=None):
    y = SH - 1 if y is None else y
    for x in range(W):
        s.put(y * W + x, K_WALL)
        s.wake(x, y)


def _ancho(s, k=K_WATER):
    xs = [x for y in range(SH) for x in range(W) if KIND[s.g[y * W + x]] == k]
    return (max(xs) - min(xs) + 1) if xs else 0


def test_el_agua_se_desparrama():
    """una columna de agua tiene que EXTENDERSE, no quedarse apilada.

    con dispersión de una celda por frame el agua se comporta como arena
    mojada: se amontona en una torre y tarda cientos de frames en nivelarse.
    """
    s = Sim()
    _piso(s)
    rellena(s, 155, 165, SH - 40, SH - 1, K_WATER)   # columna angosta y alta
    a0 = _ancho(s)
    correr(s, 60)
    a1 = _ancho(s)
    chk(a1 > a0 * 4, "en un segundo el agua se desparrama de %d a %d celdas "
        "de ancho" % (a0, a1))
    alto = max((y for y in range(SH) for x in range(W)
                if KIND[s.g[y * W + x]] == K_WATER), default=SH)
    chk(SH - 1 - alto < 12, "y queda como un charco bajo, no como una torre "
        "(%d celdas de alto)" % (SH - 1 - alto))


def test_el_agua_no_se_desparrama_a_traves_del_muro():
    """la dispersión de varias celdas no puede atravesar paredes."""
    s = Sim()
    _piso(s)
    for y in range(SH - 20, SH - 1):                 # dos muros, un pozo angosto
        for x in (150, 158):
            s.put(y * W + x, K_WALL)
            s.wake(x, y)
    rellena(s, 151, 158, SH - 20, SH - 2, K_WATER)
    correr(s, 90)
    fuera = [(x, y) for y in range(SH) for x in range(W)
             if KIND[s.g[y * W + x]] == K_WATER and not (150 < x < 158)]
    chk(not fuera, "el agua se queda en su pozo (%d celdas se escaparon)"
        % len(fuera))


def test_el_agua_salpica_al_caer():
    """la gota que llega con impulso se abre; la que ya está quieta, no."""
    s = Sim()
    _piso(s)
    rellena(s, 158, 162, 20, 26, K_WATER)            # un chorro, bien alto
    correr(s, SH + 40)          # el agua cae 1 celda por frame: hay que esperarla
    a = _ancho(s)
    chk(a > 8, "el chorro que cae desde arriba se abre al tocar fondo "
        "(quedó de %d celdas)" % a)

    quieta = Sim()
    _piso(quieta)
    rellena(quieta, 158, 162, SH - 7, SH - 1, K_WATER)   # ya apoyada, sin caída
    antes = cuenta(quieta, K_WATER)
    correr(quieta, 30)
    chk(cuenta(quieta, K_WATER) == antes,
        "salpicar mueve agua, no la crea ni la destruye")


def _tope(s, x, kind=K_WATER):
    """la y más alta con ese material en la columna, o None."""
    for y in range(SH):
        if KIND[s.g[y * W + x]] == kind:
            return y
    return None


def test_el_agua_no_queda_amontonada():
    """el agua se nivela: un montículo tiene que desarmarse solo.

    esto es lo que se ve de lejos y no lo miraba ninguna prueba. la `calma` que
    apagaba el revoltijo de la superficie contaba el correrse de lado como "no
    avanzar" —y para la gota que oscila en una superficie plana está bien—, pero
    con eso congelaba también a la que estaba bajando por el flanco de un
    montículo: quedaba un domo de agua apilado como si fuera arena.
    """
    s = Sim()
    _piso(s)
    rellena(s, 12, 212, SH - 14, SH - 1, K_WATER)        # el charco
    s._blob(112, SH - 22, 13, K_WATER, force=True)       # el montículo encima
    s.active[:] = b"\x01" * NCHUNK
    alto0 = SH - 1 - min(y for y in range(SH) for x in range(12, 213)
                         if KIND[s.g[y * W + x]] == K_WATER)
    correr(s, 500)
    topes = [t for t in (_tope(s, x) for x in range(14, 211)) if t is not None]
    topes.sort()
    mediana = topes[len(topes) // 2]
    pico = topes[0]                                      # la columna más alta
    print(f"agua amontonada: partió con {alto0} px de alto; tras 500 frames el "
          f"pico está {mediana - pico} px sobre la mediana")
    chk(mediana - pico <= 3, "el montículo se nivela (quedaron %d px de pico "
        "sobre el nivel)" % (mediana - pico))
    chk(len(topes) > 180, "y el agua sigue cubriendo el charco (%d columnas)"
        % len(topes))


def test_el_agua_quieta_deja_dormir_los_chunks():
    """un charco en reposo tiene que costar CERO, y ésta era la fuga grande.

    un charco nivelado no está quieto por sí solo: en la superficie cada gota
    se corre de lado, deja un hueco y otra lo llena, indefinidamente. medido en
    un estanque "asentado": 600 celdas cambiando por frame, media pantalla de
    chunks despiertos y 21 ms/frame que no bajaban nunca — powder se arrastraba
    después de un rato de juego sin que pasara nada en pantalla.
    """
    s = Sim()
    _piso(s)
    for y in range(SH - 60, SH - 1):
        for x in range(16, 208):
            s.put(y * W + x, K_WATER)
            s.wake(x, y)
    correr(s, 1200)
    chk(s.awake == 0, "el agua asentada duerme todos los chunks (quedan %d de "
        "%d despiertos)" % (s.awake, NCHUNK))
    antes = bytes(s.g)
    correr(s, 5)
    chk(bytes(s.g) == antes, "y deja de moverse del todo")


def test_el_agua_asentada_se_despierta():
    """asentarse no puede volverla piedra: si se abre un hueco, tiene que fluir."""
    s = Sim()
    _piso(s)
    for y in range(SH - 40, SH - 1):
        for x in range(12, 212):
            s.put(y * W + x, K_WATER)
            s.wake(x, y)
    correr(s, 900)
    chk(s.awake == 0, "arranca asentada")
    for y in range(SH - 20, SH - 1):          # le abrimos un pozo a un costado
        for x in range(100, 112):
            s.put(y * W + x, K_EMPTY)
            s.wake(x, y)
    correr(s, 120)
    lleno = sum(1 for y in range(SH - 20, SH - 1) for x in range(100, 112)
                if KIND[s.g[y * W + x]] == K_WATER)
    chk(lleno > 100, "el agua vuelve a correr y llena el pozo (%d celdas)"
        % lleno)
    correr(s, 900)
    chk(s.awake == 0, "y se vuelve a dormir cuando termina (%d despiertos)"
        % s.awake)


def test_agua_apaga():
    s = estanque(40)
    s.paint(130, SH - 45, K_FIRE, 5)
    correr(s, 60)
    print(f"agua fría + fuego: quedan {cuenta(s, K_FIRE)} llamas")
    chk(cuenta(s, K_FIRE) < 5, "el agua fría dejó de apagar el fuego")


def test_lava_agua():
    s = estanque()
    s.paint(130, SH - 30, K_LAVA, 6)
    chk(cuenta(s, K_LAVA) > 20, "el pincel no puede pintar lava sobre agua")
    correr(s, 200)
    print(f"lava al mar: {cuenta(s, K_STONE)} piedra nueva")
    chk(cuenta(s, K_STONE) > 10, "lava + agua no dio piedra")


def test_hielo_congela():
    s = estanque()
    s._blob(130, SH - 20, 4, K_ICE, force=True)
    s.wake(130, SH - 20)
    serie = [cuenta(s, K_ICE)]
    for _ in range(4):
        correr(s, 100)
        serie.append(cuenta(s, K_ICE))
    print(f"hielo congelando el estanque: {serie}")
    chk(serie[-1] > serie[0] * 4, "el hielo no se propaga por el agua")


def test_hielo_calor():
    s = Sim()
    for x in range(80, 180):
        s.put((SH - 1) * W + x, K_WALL)
        s.wake(x, SH - 1)
    rellena(s, 100, 160, SH - 30, SH - 1, K_ICE)
    h0 = cuenta(s, K_ICE)
    s.paint(130, SH - 40, K_LAVA, 7)
    correr(s, 400)
    print(f"hielo + lava: {h0} -> {cuenta(s, K_ICE)} "
          f"(derritió {h0 - cuenta(s, K_ICE)}, piedra {cuenta(s, K_STONE)})")
    chk(cuenta(s, K_ICE) < h0 - 20, "la lava no derrite el hielo")

    s = Sim()
    for x in range(80, 180):
        s.put((SH - 1) * W + x, K_WALL)
        s.wake(x, SH - 1)
    rellena(s, 110, 150, SH - 20, SH - 1, K_ICE)
    h0 = cuenta(s, K_ICE)
    s.paint(130, SH - 10, K_FIRE, 6)  # el pincel de fuego es soplete
    print(f"soplete sobre hielo: {h0} -> {cuenta(s, K_ICE)} al instante")
    chk(cuenta(s, K_ICE) < h0 - 50, "el soplete no derrite")


def test_arbol():
    s = Sim()
    for x in range(60, 90):
        s.put((SH - 1) * W + x, K_STONE)
        s.wake(x, SH - 1)
    s.put((SH - 2) * W + 75, K_SEED)
    s.wake(75, SH - 2)
    correr(s, 400)
    tr, ho = cuenta(s, K_TRUNK), cuenta(s, K_LEAF)
    print(f"árbol: {tr} de tronco + {ho} hojas")
    chk(tr > 10 and ho >= 3, "la semilla no dio árbol")
    chk(cuenta(s, K_SEED) == 0, "quedaron brotes sin resolver")
    s.paint(75, SH - 25, K_FIRE, 3)
    correr(s, 500)
    print(f"  incendiado -> {cuenta(s, K_TRUNK)} tronco, {cuenta(s, K_LEAF)} hojas")
    chk(cuenta(s, K_LEAF) < ho, "el árbol no arde")


def test_gas():
    s = Sim()
    rellena(s, 100, 160, 60, 100, K_GAS)
    g0 = cuenta(s, K_GAS)
    s.paint(130, 99, K_FIRE, 2)
    correr(s, 90)
    print(f"gas + fuego: {g0} -> {cuenta(s, K_GAS)}")
    chk(cuenta(s, K_GAS) < g0 // 3, "el gas no deflagra en cadena")


def test_circuito():
    """el pulso debe recorrer un cable largo entero, no agotarse a medias"""
    s = Sim()
    for x in range(20, 206):
        s.put(60 * W + x, K_METAL)
        s.wake(x, 60)
    for x in range(200, 224):
        s.put(64 * W + x, K_WALL)
        s.wake(x, 64)
    rellena(s, 204, 222, 61, 64, K_POWDER)
    chk(tocan(s, K_METAL, K_POWDER) is not None,
        "escena mal montada: el cable no toca la carga")
    a = cuenta(s, K_POWDER)
    s.paint(22, 60, K_SPARK, 1)
    detono = None
    for n in range(400):
        s.step()
        if detono is None and cuenta(s, K_POWDER) < a - 5:
            detono = n
    print(f"circuito de 186 celdas: pólvora {a} -> {cuenta(s, K_POWDER)}, "
          f"detonó en el frame {detono}")
    chk(cuenta(s, K_POWDER) < a // 2, "el pulso no llegó al final del cable")
    correr(s, 600)
    print(f"  chispas {cuenta(s, K_SPARK)}, enfriando {cuenta(s, K_MCOOL)}, "
          f"cable {cuenta(s, K_METAL)}")
    chk(cuenta(s, K_SPARK) == 0, "el pulso nunca se apaga (rebota infinito)")
    chk(cuenta(s, K_MCOOL) == 0, "el cable no se recupera tras conducir")


def test_chispa_gas():
    s = Sim()
    for y in range(74, 101):
        s.put(y * W + 130, K_WALL)
        s.put(y * W + 165, K_WALL)
    for x in range(130, 166):
        s.put(74 * W + x, K_WALL)
    for x in range(131, 165):
        s.put(101 * W + x, K_WALL)
    rellena(s, 131, 165, 75, 101, K_GAS)
    # el cable va al final: entra a la cámara sin que el muro lo tape
    for x in range(40, 133):
        s.put(100 * W + x, K_METAL)
        s.wake(x, 100)
    chk(tocan(s, K_METAL, K_GAS) is not None,
        "escena mal montada: el cable no toca el gas")
    g0 = cuenta(s, K_GAS)
    s.paint(42, 100, K_SPARK, 1)
    correr(s, 300)
    print(f"chispa -> cámara de gas: {g0} -> {cuenta(s, K_GAS)}")
    chk(cuenta(s, K_GAS) < g0 // 2, "la chispa no enciende el gas por el cable")


def test_acido():
    s = Sim()
    rellena(s, 100, 160, 120, 160, K_SAND)
    a0 = cuenta(s, K_SAND)
    correr(s, 60)
    s.paint(130, 110, K_ACID, 6)
    correr(s, 300)
    print(f"ácido: {a0} de arena -> {cuenta(s, K_SAND)}")
    chk(cuenta(s, K_SAND) < a0, "el ácido no disuelve")
    s2 = Sim()
    rellena(s2, 100, 160, 120, 160, K_WALL)
    w0 = cuenta(s2, K_WALL)
    s2.paint(130, 110, K_ACID, 6)
    correr(s2, 300)
    chk(cuenta(s2, K_WALL) == w0, "el ácido comió el muro (debe resistir)")


def test_flotabilidad():
    """el aceite sube por el agua"""
    s = estanque()
    for _ in range(40):
        s.paint(130, SH - 10, K_OIL, 3)
    correr(s, 400)
    ys = [y for y in range(SH) for x in range(60, 200)
          if KIND[s.g[y * W + x]] == K_OIL]
    ya = [y for y in range(SH) for x in range(60, 200)
          if KIND[s.g[y * W + x]] == K_WATER]
    if ys and ya:
        print(f"aceite: y medio {sum(ys)/len(ys):.0f} vs agua {sum(ya)/len(ya):.0f} "
              f"(menor = más arriba)")
        chk(sum(ys) / len(ys) < sum(ya) / len(ya), "el aceite no flota sobre el agua")


def test_rendimiento():
    s = Sim()
    s.demo()
    t0 = time.perf_counter()
    correr(s, 300)
    demo = 300 / (time.perf_counter() - t0)
    print(f"demo: {demo:.0f} fps de simulación ({s.awake}/{NCHUNK} chunks)")
    chk(demo > 70, f"la escena de arranque va lenta ({demo:.0f} fps)")

    s = Sim()
    for y in range(0, SH, 2):
        for x in range(0, W, 2):
            s.put(y * W + x, (K_SAND, K_WATER, K_OIL, K_GAS)[(x + y) // 2 % 4])
    s.active[:] = b"\x01" * NCHUNK
    t0 = time.perf_counter()
    correr(s, 150)
    peor = 150 / (time.perf_counter() - t0)
    print(f"peor caso (pantalla llena y activa): {peor:.0f} fps de simulación")
    # son ~31.000 partículas despiertas a la vez, el triple de lo que pide el
    # cabinet. en una máquina compartida esta medida baila entre 54 y 64 (la
    # versión anterior daba 57-63 con la misma carga): el piso es 50 para que
    # la prueba avise de una regresión y no del ruido
    chk(peor > 50, f"el peor caso se arrastra ({peor:.0f} fps)")

    # lo que pide el cabinet: +10.000 partículas moviéndose a 60 fps
    s = Sim()
    _piso(s)
    random.seed(3)
    for y in range(10, 172):                  # la mesa es más angosta y más alta
        for x in range(20, 210, 3):
            s.put(y * W + x, (K_SAND, K_WATER, K_SAND, K_OIL)[(x // 3 + y) % 4])
    s.active[:] = b"\x01" * NCHUNK
    n = W * SH - s.g.count(0)
    t0 = time.perf_counter()
    correr(s, 150)
    diez = 150 / (time.perf_counter() - t0)
    print(f"{n} partículas cayendo a la vez: {diez:.0f} fps de simulación")
    chk(n > 10000 and diez > 60, f"con {n} partículas cayendo no llega a 60 fps ({diez:.0f})")

    s = Sim()
    s.demo()
    correr(s, 600)
    fl = flotantes(s)
    print(f"demo tras 600 frames: {len(fl)} granos flotando")
    chk(not fl, "la escena de arranque deja granos flotando")



# --- la barra por categorías ---

def test_barra_por_categorias():
    """cada material en una sola pestaña, que entren en una fila, y casillas
    grandes: en el celular se eligen con el dedo."""
    vistos = [k for _, ks in CATS for k in ks]
    chk(len(vistos) == len(set(vistos)) == len(TOOLS), "cada material está en una sola pestaña")
    chk(all(len(ks) * CELL_W <= W for _, ks in CATS), "y los de cada pestaña caben en una fila")
    # en un celular de 390 px de ancho, medidas en px de pantalla: un dedo
    # acierta sin pensar a partir de ~44
    chk(CELL_W * CSS >= 60 and CELL_H * CSS >= 60, "las casillas son grandes "
        "(%dx%d px de pantalla)" % (CELL_W * CSS, CELL_H * CSS))
    chk(TAB_W * CSS >= 60 and TAB_H * CSS >= 36, "y las pestañas también (%dx%d)"
        % (TAB_W * CSS, TAB_H * CSS))
    chk(SH + TAB_H + CELL_H <= H, "la barra entra en la pantalla")
    chk(W * SH <= 320 * 194 * 1.01, "la mesa no simula más celdas que la apaisada "
        "(%d)" % (W * SH))
    chk(1.45 <= H / W <= 1.6 and 216 <= W <= 256, "pantalla vertical (%dx%d)" % (W, H))
    chk(len(TOOLS) - 1 == 22, "22 materiales + borrar (hay %d)" % (len(TOOLS) - 1))
    chk(tool_at(5, SH - 1, 0) is None, "tocar arriba de la barra no elige nada")
    chk(tool_at(TAB_W * 2 + 3, SH + 2, 0) == ("tab", 2), "tocar una pestaña la abre")
    for c, (_, ks) in enumerate(CATS):
        for i, k in enumerate(ks):
            x, y, w, h = cell_box(i)
            hit = tool_at(x + w // 2, y + h // 2, c)
            chk(hit == ("tool", TOOLS.index(k)), "la casilla %d de %s elige su material"
                % (i, CATS[c][0]))


def test_deshacer_y_vaciar():
    a = App.__new__(App)
    a.setup(test=True)
    a.sim.clear()
    a.snapshot()
    rellena(a.sim, 100, 120, 100, 120, K_SAND)
    a.snapshot()
    a.vaciar()
    chk(not any(a.sim.g), "vaciar deja la mesa limpia")
    a.undo()
    chk(cuenta(a.sim, K_SAND) == 400, "deshacer devuelve lo vaciado (%d)" % cuenta(a.sim, K_SAND))
    a.undo()
    chk(cuenta(a.sim, K_SAND) == 400, "y otra vez, el estado anterior")
    a.undo()
    chk(cuenta(a.sim, K_SAND) == 0, "hasta el principio")
    a.undo()                                # sin historia: no revienta
    a.rad = 4
    a.pincel_sig()
    chk(a.rad == 7, "el botón pincel pasa al tamaño siguiente (%d)" % a.rad)
    a.rad = 16
    a.pincel_sig()
    chk(a.rad == 1, "y del más grande vuelve al más chico")


# --- materiales nuevos ---

def test_virus_contagia_y_se_apaga():
    s = Sim()
    _piso(s)
    rellena(s, 60, 200, SH - 40, SH - 1, K_SAND)
    rellena(s, 100, 160, SH - 60, SH - 41, K_WATER)
    m0 = cuenta(s, K_WALL)
    a0 = cuenta(s, K_SAND)
    s.paint(130, SH - 30, K_VIRUS, 2)
    pico = 0
    for _ in range(12):
        correr(s, 100)
        pico = max(pico, cuenta(s, K_VIRUS))
    print(f"virus: pico de {pico} celdas, arena {a0} -> {cuenta(s, K_SAND)}")
    chk(pico > 200, "el virus se contagia (%d celdas en el pico)" % pico)
    chk(cuenta(s, K_SAND) < a0 // 3, "y se come la arena")
    correr(s, 800)
    chk(cuenta(s, K_VIRUS) == 0, "y al final se apaga solo (%d)" % cuenta(s, K_VIRUS))
    chk(cuenta(s, K_WALL) == m0, "el muro no se contagia")


def test_el_fuego_quema_el_virus():
    quedan = []
    for fuego in (False, True):
        s = Sim()
        rellena(s, 100, 120, 100, 120, K_VIRUS, life=200)
        if fuego:
            rellena(s, 120, 124, 100, 120, K_FIRE, life=60)
        correr(s, 25)
        quedan.append(cuenta(s, K_VIRUS))
    chk(quedan[1] < quedan[0], "el fuego quema al virus (%d contra %d sin fuego)"
        % (quedan[1], quedan[0]))


def test_agujero_negro_traga():
    """en promedio de tres corridas: con 90 granos el resultado de una sola
    baila ±4 y caía justo en el borde según la semilla."""
    quedan = []
    for semilla in (1, 2, 3):
        random.seed(semilla)
        s = Sim()
        s._blob(160, 100, 4, K_BHOLE, force=True)
        b0 = cuenta(s, K_BHOLE)
        for x in range(140, 158):                # una repisa al lado del agujero
            s.put(113 * W + x, K_WALL)
        rellena(s, 144, 154, 104, 113, K_SAND)
        rellena(s, 120, 126, 60, 140, K_WALL)
        m0 = cuenta(s, K_WALL)
        a0 = cuenta(s, K_SAND)
        correr(s, 300)
        quedan.append(cuenta(s, K_SAND))
        chk(cuenta(s, K_BHOLE) == b0, "y no crece ni se achica")
        chk(cuenta(s, K_WALL) == m0, "el muro resiste")
    print(f"agujero negro: arena {a0} -> {quedan}")
    chk(sum(quedan) / 3 < a0 / 2, "el agujero negro se traga la arena de al lado")


def test_clonador():
    s = Sim()
    for x in range(140, 160):
        s.put(50 * W + x, K_CLONE)
        s.put(49 * W + x, K_WATER)
        s.wake(x, 50)
    _piso(s)
    correr(s, 300)
    agua = cuenta(s, K_WATER)
    chk(agua > 150, "el clonador copia lo que lo toca: agua (%d)" % agua)
    chk(cuenta(s, K_CLONE) == 20, "y él queda igual")
    s2 = Sim()
    rellena(s2, 140, 160, 120, 124, K_CLONE)
    s2.paint(150, 115, K_ACID, 4)
    correr(s2, 200)
    chk(cuenta(s2, K_CLONE) == 80, "el ácido no se lo come (%d)" % cuenta(s2, K_CLONE))


def test_cohetes():
    s = Sim()
    _piso(s)
    s._blob(160, SH - 6, 4, K_FWORK)
    f0 = cuenta(s, K_FWORK)
    s.paint(155, SH - 3, K_LAVA, 2)
    abiertos, chispas, alto = 0, 0, SH
    for _ in range(260):
        s.step()
        abiertos = max(abiertos, len(s.bursts))
        chispas = max(chispas, cuenta(s, K_EMBER)) if s.frame % 10 == 0 else chispas
        for y in range(SH):
            if any(KIND[c] == K_ROCKET for c in s.g[y * W:(y + 1) * W]):
                alto = min(alto, y)
                break
    print(f"cohetes: {f0} -> {cuenta(s, K_FWORK)}, subieron hasta y={alto}, "
          f"{chispas} chispas en el aire")
    chk(cuenta(s, K_FWORK) < f0 // 2, "el fuego lanza los cohetes")
    chk(alto < SH - 50, "suben de verdad (llegaron a y=%d)" % alto)
    chk(abiertos >= 1 and chispas > 100, "y revientan en chispas de colores (%d)" % chispas)
    correr(s, 400)
    chk(cuenta(s, K_EMBER) == 0 and cuenta(s, K_ROCKET) == 0 and not s.bursts,
        "y las chispas se apagan solas")


def test_la_explosion_lanza_cohetes():
    s = Sim()
    _piso(s)
    s._blob(150, SH - 5, 3, K_POWDER)
    s._blob(158, SH - 5, 2, K_FWORK)
    s.explode(150, SH - 5)
    chk(cuenta(s, K_ROCKET) > 0, "la onda de la pólvora enciende los cohetes vecinos")


def test_nieve():
    s = Sim()
    _piso(s)
    rellena(s, 150, 160, 20, 30, K_SNOW)
    n0 = cuenta(s, K_SNOW)
    correr(s, 600)
    chk(cuenta(s, K_SNOW) == n0, "la nieve cae y se apila sin perderse")
    chk(all(KIND[s.g[(SH - 2) * W + x]] in (K_SNOW, K_EMPTY) for x in range(W)),
        "(está en el piso)")
    chk(cuenta(s, K_SNOW) and min(y for y in range(SH) for x in range(W)
                                 if KIND[s.g[y * W + x]] == K_SNOW) > SH - 30,
        "y llegó abajo")
    s.paint(155, SH - 4, K_FIRE, 5)
    correr(s, 30)
    chk(cuenta(s, K_SNOW) < n0 // 2, "el fuego la derrite (%d de %d)"
        % (cuenta(s, K_SNOW), n0))
    chk(cuenta(s, K_WATER) > 20, "y se vuelve agua")


def test_rayo():
    s = Sim()
    for x in range(40, 200):
        s.put(150 * W + x, K_METAL)
    for x in range(200, 214):
        s.put(150 * W + x, K_WALL)
    rellena(s, 196, 212, 140, 150, K_POWDER)
    p0 = cuenta(s, K_POWDER)
    gx, gy = s.bolt(60, 170)
    chk(gy <= 150, "el rayo pega en lo primero que encuentra (y=%d)" % gy)
    chk(cuenta(s, K_PLASMA) > 50, "y se ve: deja un camino de plasma")
    chk(s.flash > 0, "con fogonazo")
    correr(s, 300)
    chk(cuenta(s, K_POWDER) < p0 // 2, "y su descarga corre por el cable y revienta la pólvora")
    chk(cuenta(s, K_PLASMA) == 0, "el plasma se apaga solo")
    s2 = Sim()
    rellena(s2, 120, 200, 120, 160, K_GAS)
    g0 = cuenta(s2, K_GAS)
    s2.bolt(160, 140)
    correr(s2, 90)
    chk(cuenta(s2, K_GAS) < g0 // 3, "un rayo en el gas lo hace estallar")


def test_la_lava_quieta_se_enfria():
    s = Sim()
    _piso(s)
    rellena(s, 100, 140, SH - 10, SH - 1, K_LAVA)
    l0 = cuenta(s, K_LAVA)
    correr(s, 2400)
    chk(cuenta(s, K_LAVA) < l0 // 3, "la lava se hace piedra con el tiempo (%d de %d)"
        % (cuenta(s, K_LAVA), l0))


def test_escenas():
    """todas las escenas arrancan, no dejan granos flotando y van rápido."""
    for n, nombre in enumerate(ESCENAS):
        random.seed(99)
        s = Sim()
        s.demo(n)
        t0 = time.perf_counter()
        correr(s, 600)
        fps = 600 / (time.perf_counter() - t0)
        fl = flotantes(s)
        parts = W * SH - s.g.count(0)
        print(f"escena {nombre}: {fps:.0f} fps de simulación, {parts} partículas, "
              f"{len(fl)} flotando")
        chk(fps > 90, f"la escena {nombre} va lenta ({fps:.0f} fps)")
        chk(not fl, f"la escena {nombre} deja granos flotando: {fl[:3]}")
        chk(parts > 500, f"la escena {nombre} tiene qué mirar ({parts})")

def test_la_piel():
    """el compositor: borde de luz arriba, cielo en lo vacío, resplandor junto
    al fuego, y la grilla de la simulación intacta."""
    from games.powder.game import (GLOW1, Piel, SKY_BASE, SKY, STAR1,
                                   STAR2, T_LIGHT)
    s = Sim()
    rellena(s, 50, 70, SH - 10, SH, K_SAND)
    rellena(s, 150, 153, SH - 10, SH - 7, K_FIRE, life=40)
    antes = bytes(s.g)
    p = Piel()
    out = p.componer(s.g, 1, 0)
    chk(len(out) == W * SH and bytes(s.g) == antes, "dibuja sin tocar la grilla")
    arriba = out[(SH - 10) * W + 60]
    chk(arriba == T_LIGHT[s.g[(SH - 10) * W + 60]] and arriba != s.g[(SH - 10) * W + 60],
        "la cara de arriba de la arena va con su tono de luz")
    chk(out[(SH - 5) * W + 60] == s.g[(SH - 5) * W + 60], "el interior, con su tono")
    cielo = set(range(SKY_BASE, SKY_BASE + len(SKY))) | {STAR1, STAR2}
    chk(out[20 * W + 100] in cielo, "lo vacío es cielo")
    chk(out[(SH - 9) * W + 153] == GLOW1, "al lado del fuego, resplandor")
    chk(out[(SH - 9) * W + 180] in cielo, "y lejos, no")
    t0 = time.perf_counter()
    for f in range(40):
        p.componer(s.g, f, 0)
    ms = (time.perf_counter() - t0) / 40 * 1000
    print(f"piel: {ms:.2f} ms por cuadro")
    chk(ms < 2.5, "la piel es barata (%.2f ms)" % ms)


if __name__ == "__main__":
    for fn in (test_chunks, test_chunk_vecino, test_agua_apaga, test_lava_agua,
               test_hielo_congela, test_hielo_calor, test_arbol, test_gas,
               test_el_agua_no_queda_amontonada,
               test_el_agua_quieta_deja_dormir_los_chunks,
               test_el_agua_asentada_se_despierta,
               test_el_agua_se_desparrama,
               test_el_agua_no_se_desparrama_a_traves_del_muro,
               test_el_agua_salpica_al_caer,
               test_circuito, test_chispa_gas, test_acido,
               test_flotabilidad, test_rendimiento,
               test_barra_por_categorias, test_deshacer_y_vaciar,
               test_virus_contagia_y_se_apaga, test_el_fuego_quema_el_virus,
               test_agujero_negro_traga, test_clonador, test_cohetes,
               test_la_explosion_lanza_cohetes, test_nieve, test_rayo,
               test_la_lava_quieta_se_enfria, test_escenas, test_la_piel):
        random.seed(1234)  # misma escena en cada corrida
        fn()
    print("\n=== TODO OK ===" if not FALLAS
          else f"\n=== {len(FALLAS)} FALLAS ===\n- " + "\n- ".join(FALLAS))
