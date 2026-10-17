"""arranque: python -m games.pong. lo levanta el emulador."""
from importlib import import_module

import_module(__package__ + ".game").Game()
