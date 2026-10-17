"""arranque del cabinet en el navegador (pyxel web).

es el arcade.py de la web: en vez de lanzar procesos, mira la url. sin
parámetros abre el menú; con `?game=<id>` bootea ese juego. elegir en el menú
cambia la url y reinicia pyxel, y esc desde el título de un juego vuelve acá.
"""
import runpy

from pixelkit import web
from pixelkit.registry import discover_games

web.install_gamepad()

by_id = {g.id: g for g in discover_games()}
game = by_id.get(web.current_game() or "")

if game:
    web.configure(game.width, game.height, game.touch)
    runpy.run_module(game.module, run_name="__main__", alter_sys=True)
else:
    from pixelkit import menu
    web.configure(menu.W, menu.H)
    menu.run_menu()
