# MHW · RETRO · FUTURE — web

el cabinet de juegos pixel art de [rs-pixel-arcade](https://github.com/jona-mhw/rs-pixel-arcade),
jugable en el navegador.

**▶ jugar: https://jona-mhw.github.io/mhw-retro-games-web/**

los mismos 8 juegos en Python + [pyxel](https://github.com/kitao/pyxel), sin
reescribirlos: corren en el navegador con Pyxel Web (Python en WebAssembly vía
Pyodide). la primera carga baja el runtime (~10 MB) y después queda en caché.

## pensado para el celular

- **controles táctiles bajo la pantalla**, propios de cada juego y con nombre
  ("fuego", "empuje", "caer", "guardar"…). abajo de cada nombre va la tecla que
  aprieta, para que calce con lo que dice el juego ("enter para jugar").
- **cambian con la escena**: en título, game over e iniciales aparece la
  cruceta + OK; al jugar, los del juego.
- **la cruceta sigue al dedo**: se desliza de una dirección a otra sin levantarlo.
- **gestos**: en culebra y cruzar se puede deslizar sobre la pantalla; en pong y
  esquiva, arrastrar el dedo; en powder se pinta con el dedo.
- **en vertical** el juego va arriba y los controles abajo; **acostado**, el
  juego al centro y los controles a los costados.
- **menú**: un toque elige el juego (y muestra su ficha y récord), otro lo lanza.
- **pantalla completa**: el botón ⛶ (android). en iphone: compartir →
  *agregar a inicio*, y se abre como app, sin barras.
- cambiar de juego **no recarga la página**: pyxel se reinicia con el cartucho nuevo.

en el computador no aparecen los controles: teclado (flechas o wasd, enter,
espacio, esc) o un gamepad. **récords y config** se guardan en el navegador.

atajos directos a un juego: `?game=powder`, `?game=pong`, `?game=autos`, etc.

## cómo está armado

```
index.html          carga pyxel.js, arranca arcade.pyxapp y dibuja los controles táctiles
arcade.pyxapp       el cabinet empaquetado (lo genera build.sh)
src/arcade/
  main.py           el arranque web: sin parámetros abre el menú, ?game=<id> bootea ese juego
  pixelkit/web.py   lo que cambia en el navegador: navegar en vez de lanzar procesos,
                    localStorage en vez de json en disco, gamepad virtual como teclado
  pixelkit/, games/ copia del arcade de escritorio (sin tests). cada game.toml
                    declara sus controles táctiles en [game.touch]
build.sh            reempaqueta src/arcade -> arcade.pyxapp
```

en el escritorio cada juego es un proceso aparte; en la web **elegir un juego es
navegar** a `?game=<id>` y salir es volver a la página sin parámetros. el resto
de pixelkit no se enteró: `config` y `scores` leen y graban por localStorage
cuando corren en pyodide.

### actualizar los juegos

```
pip install pyxel
# copiar los cambios de rs-pixel-arcade a src/arcade (pixelkit/ y games/)
./build.sh
git commit -am "..." && git push
```

cada push a `main` se copia a la rama `gh-pages`, que es la que publica Pages.

créditos en [CREDITS.md](CREDITS.md). pyxel es de Takashi Kitao (MIT).
