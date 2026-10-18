# MHW · RETRO · FUTURE — web

el cabinet de juegos pixel art de [rs-pixel-arcade](https://github.com/jona-mhw/rs-pixel-arcade),
jugable en el navegador.

**▶ jugar: https://jona-mhw.github.io/mhw-retro-games-web/**

9 juegos en Python + [pyxel](https://github.com/kitao/pyxel), sin
reescribirlos: corren en el navegador con Pyxel Web (Python en WebAssembly vía
Pyodide). la primera carga baja el runtime (~10 MB) y después queda en caché.

## los juegos

todos van en formato parado (~240x360) para llenar el celular vertical, y el
canvas se dibuja a la resolución real de la pantalla, con píxeles parejos.

- **neón** *(nuevo)* — shoot'em up vertical synthwave. se mueve con el trackpad y dispara solo; roces que
  pagan, cadena hasta x8, el mini-jefe CENTINELA y el jefe final OCASO-85.
- **asteroides** — oleadas anunciadas, minas en cadena, cometas, auto-fuego,
  poderes y una tormenta final.
- **autos** — atraco top-down: misiones, búsqueda de 5 estrellas con bloqueos y
  helicóptero, derrapes, rampas y el banco.
- **bloques** — tetris blitz que se juega con el dedo sobre el tablero: pieza
  dorada, fiebre final y carteles grandes.
- **cruzar** — cada cruce es un tramo nuevo: barrio, avenida, vía del tren, río
  y autopista.
- **culebra** — snake con hambre: ratón que huye, arañas, frenesí final y
  escenarios por nivel.
- **esquiva** — munición que se recarga sola, rayos, buscadores, muros y el
  jefe NÚCLEO.
- **pong** — SMASH, jefes de muro y tres personalidades de la máquina.
- **powder** — la mesa de arena, recreativa, con materiales por pestañas.

todas las partidas (menos powder) duran menos de dos minutos, arrancan con
una cuenta **3-2-1-¡YA!** y se pueden **pausar** (⏸ en la barra, esc o p; se
pausa sola si cambias de app).

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
- **trackpad**: en neón, esquiva y pong el dedo se arrastra en la zona de
  controles y la nave se mueve arriba, sin taparla.
- **menú**: en el celular parado es vertical, con filas grandes. un toque elige el juego (y muestra su ficha y récord), otro lo lanza.
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
