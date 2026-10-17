# MHW · RETRO · FUTURE — web

el cabinet de juegos pixel art de [rs-pixel-arcade](https://github.com/jona-mhw/rs-pixel-arcade),
jugable en el navegador.

**▶ jugar: https://jona-mhw.github.io/mhw-retro-games-web/**

los mismos 8 juegos en Python + [pyxel](https://github.com/kitao/pyxel), sin
reescribir: corren en el navegador con Pyxel Web (Python en WebAssembly vía
Pyodide). la primera carga baja el runtime (~10 MB) y después queda en caché.

- **teclado**: flechas o wasd, enter elige, espacio dispara, esc vuelve.
- **celular**: aparece una cruceta virtual; A = espacio/enter, B = x, X = c,
  Y = z, BACK = esc. powder se juega con el dedo como pincel.
- **récords y config** (pantalla, crt) se guardan en el navegador (localStorage).

atajos directos a un juego: `?game=powder`, `?game=pong`, `?game=autos`, etc.

## cómo está armado

```
index.html          carga pyxel.js y arranca arcade.pyxapp
arcade.pyxapp       el cabinet empaquetado (lo genera build.sh)
src/arcade/
  main.py           el arranque web: sin parámetros abre el menú, ?game=<id> bootea ese juego
  pixelkit/web.py   lo que cambia en el navegador: navegar en vez de lanzar procesos,
                    localStorage en vez de json en disco, gamepad virtual como teclado
  pixelkit/, games/ copia del arcade de escritorio (sin tests)
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
