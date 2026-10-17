"""arranque del juego: `python -m games.<id>`.

genérico: usa el nombre del paquete, así no hay que editarlo al copiar la
cruzar. el emulador (arcade.py) levanta cada juego por acá.
"""
from importlib import import_module

import_module(__package__ + ".game").Game()
