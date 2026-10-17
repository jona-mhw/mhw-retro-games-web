"""récords del cabinet, persistentes y compartidos entre juegos.

cada juego guarda su top-5 (iniciales + puntaje). el emulador arma con esto un
salón de la fama en el menú principal, y cada juego muestra los suyos en su
pantalla de título y en el attract mode.

viene semillado: aunque no exista el archivo, hay récords de fábrica para que el
podio y el attract nunca se vean vacíos en el primer arranque. los puntajes
reales van desplazando a los de fábrica a medida que se juega.
"""
import json
import os

from pixelkit import web
from pixelkit.registry import ROOT

PATH = os.path.join(ROOT, "arcade.scores.json")
N = 5   # cuántos récords guarda cada juego

# récords de fábrica (modestos, para que se puedan superar enseguida).
#
# están calibrados contra bots que juegan cada juego hasta el final, no a ojo:
# un jugador perfecto de pong llega a ~54 peloteos, uno de culebra que persigue
# la fruta hace 39-71, y un bot de bloques que coloca óptimo a ritmo humano
# pasa los 100.000. si cambia una escala de puntaje hay que volver a medir —
# un récord de fábrica inalcanzable arruina el podio igual que uno regalado.
DEFAULTS = {
    # culebra y bloques se recalibraron con el rediseño (frenesí, ratón y
    # arañas; oro y fiebre): bots viejos vs nuevos con la misma lógica dieron
    # 1,3-2,2x en culebra y 2,0-2,4x en bloques.
    "culebra": [("ACE", 65), ("BOA", 38), ("SSS", 17)],
    "bloques": [("TNT", 32000), ("BLK", 15000), ("ROW", 5000)],
    # pong sube un escalón por la racha (+10 cada 10 devoluciones seguidas):
    # el jugador perfecto simulado la cobra entera (+50) y hace 230-500 con el
    # muro. estos siguen siendo un piso para un humano, no una medición.
    # pong y cruzar se recalibraron con el rediseño (smash, jefes de muro,
    # tramos con tren y río) contra bots flojos, medios y buenos.
    "pong":    [("CPU", 600), ("ACE", 350), ("NET", 150)],
    # esquiva y asteroides cambiaron de escala con oleadas, jefe y frenesí:
    # calibrados con bots de lógica pura, por debajo de su mediana.
    "esquiva": [("DGE", 900), ("RUN", 450), ("HOP", 180)],
    "asteroides": [("VEC", 25000), ("ORB", 12000), ("AST", 5000)],
    # cruzar quedó de piso: el bot espera de más para elegir hueco y sólo logró
    # 3-6 cruces en 90 s. un humano lee el tráfico mucho mejor que esa heurística
    "cruzar":  [("HOP", 3500), ("RAN", 1800), ("PIE", 700)],
    # autos es el único que no se pudo medir bien: los bots manejan mal por una
    # ciudad con manzanas y ninguno sabe escaparse de la policía. la mediana de
    # un bot con gps quedó en $300 y su mejor corrida en $1.144, así que estos
    # números son un piso pensado para un humano, no una medición.
    # neón: 20 partidas por bot; el experto saca ~280k, el torpe 98-270k.
    "neon":    [("NEO", 180000), ("SOL", 90000), ("VHS", 35000)],
    "autos":   [("GTA", 1800), ("VIP", 900), ("DRV", 400)],
}


def _seed():
    return {gid: [{"ini": i, "score": s} for i, s in lst]
            for gid, lst in DEFAULTS.items()}


def _read():
    """el json guardado: del disco, o de localStorage en el navegador."""
    if web.ACTIVE:
        raw = web.load_text(os.path.basename(PATH))
        if raw is None:
            raise FileNotFoundError(PATH)
        return json.loads(raw)
    with open(PATH) as f:
        return json.load(f)


def load():
    """lee el tablero del disco sobre la semilla de fábrica."""
    board = _seed()
    try:
        saved = _read()
        for gid, lst in saved.items():
            board[gid] = [{"ini": str(e["ini"])[:3].upper(), "score": int(e["score"])}
                          for e in lst]
    except (FileNotFoundError, ValueError, OSError, KeyError, TypeError):
        pass
    return board


def save(board):
    if web.ACTIVE:
        web.save_text(os.path.basename(PATH), json.dumps(board))
        return
    try:
        with open(PATH, "w") as f:
            json.dump(board, f, indent=2)
    except OSError:
        pass


def top(gid, n=N, board=None):
    """el top-n de un juego, de mayor a menor."""
    board = board if board is not None else load()
    return sorted(board.get(gid, []), key=lambda e: -e["score"])[:n]


def qualifies(gid, score, board=None):
    """¿este puntaje entra al top-n? (o sea, ¿es un récord que pide iniciales?)"""
    if score is None or score <= 0:
        return False
    lst = top(gid, N, board)
    return len(lst) < N or score > lst[-1]["score"]


def add(gid, ini, score):
    """graba un puntaje con sus iniciales y devuelve el tablero. graba en disco
    en el acto: pyxel cierra el proceso en el quit, no hay 'después'."""
    board = load()
    board.setdefault(gid, [])
    board[gid].append({"ini": str(ini)[:3].upper(), "score": int(score)})
    board[gid] = sorted(board[gid], key=lambda e: -e["score"])[:N]
    save(board)
    return board


def hall(game_ids, per=3, board=None):
    """para el salón de la fama del menú: {game_id: top-per} en el orden dado."""
    board = board if board is not None else load()
    return [(gid, top(gid, per, board)) for gid in game_ids]
