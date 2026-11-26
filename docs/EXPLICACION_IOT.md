# Explicación de la parte IoT (para Octavio)

Resumen de lo que hicimos Eduardo y yo en la báscula. No incluye el backend.

## a) Qué hace cada archivo

- `firmware/esp32_bascula/esp32_bascula.ino`: programa principal. Lee la celda, promedia, espera peso estable, decide si envía, hace el POST y reintenta.
- `config.example.h`: plantilla con WiFi, IP de la PC, código de la báscula, clave, categoría, pines y umbrales.
- `config.h`: copia local de la plantilla con los datos reales. Git lo ignora; aquí no se sube.
- `calibracion/calibracion.ino`: programa aparte que imprime la lectura cruda para calcular el factor de la celda.
- `.gitignore`: evita que `config.h` (con datos privados) se suba al repo.
- `scripts/simular_bascula.py`: envía lecturas falsas desde la PC para la demo sin hardware.
- `docs/IOT.md`: cableado, pasos para registrar la báscula, pruebas y problemas comunes.
- `docs/EXPLICACION_IOT.md`: este resumen.

## b) Cómo viaja una lectura

1. Al encender con la báscula vacía, el ESP32 hace la **tara** (le dice "esto es cero").
2. Se pone comida. El HX711 entrega la señal; el sketch promedia 10 muestras y aplica el factor de calibración para obtener gramos.
3. Guarda 4 promedios seguidos. Si entre el mayor y el menor hay 5 g o menos, considera que el peso ya se quedó quieto. Así no envía mientras alguien acomoda la comida.
4. Envía solo si el total pasa 30 g y cambió al menos 20 g frente al último envío. Lo enviado es el **peso total que hay ahora**, no lo que se agregó.
5. Con WiFi, hace el POST a la IP de la PC con el JSON fijo y el header `X-API-Key`. Sin WiFi, espera y lo intenta cuando vuelva la red.
6. Si la API responde bien, recuerda el total enviado y el LED se queda encendido un momento. Si falla la red o el servidor, reintenta hasta 3 veces (1, 2 y 4 s). Si es 401, 403 o 404, no reintenta.
7. La API guarda una fila en `LECTURAS_PESO` con tipo `SOBRANTE`, fecha, categoría y `es_simulada`. Ahí termina el viaje.

## c) 5 preguntas que podría hacer un juez

1. **¿Qué pasa si falla el WiFi?** El pesaje se queda esperando en la memoria del ESP32 y se envía al volver la red; el programa no se congela. Si se corta la luz antes, ese pesaje se pierde: no guardamos en memoria permanente.
2. **¿Cómo se evitan lecturas falsas y qué falta?** El firmware y el simulador mandan `X-API-Key`, pero hoy la API no la revisa, así que cualquiera que conozca la URL podría mandar un peso inventado. Falta que el backend compare la clave con el hash de la báscula y responda 401 si no coincide. Las lecturas de prueba llevan `es_simulada: true`.
3. **¿Qué significa una lectura?** Hoy es una foto del peso total de la báscula en un momento estable, no el alimento agregado. Por eso 450 g y luego 700 g serían dos filas; sumarlas daría 1150 g aunque solo haya 700 g. Octavio y Eduardo deben decidir entre (A) usar solo la última/mayor foto por sesión en el backend, o (B) mandar un pesaje por vez, el primero tras vaciar la báscula. Nada de esto está implementado.
4. **¿Se puede probar sin ESP32?** Sí: `python scripts/simular_bascula.py --url http://127.0.0.1:8000 --codigo ESP32-BASCULA-01 --api-key clave-de-ejemplo --categoria 1`. También se puede poner `SIMULAR true` en `config.h`; en ambos casos se marca `es_simulada: true`.
5. **¿Cómo sabemos que el peso es correcto?** Con `calibracion/calibracion.ino`: se hace tara vacío, se pone un peso conocido y el factor es `lectura cruda / gramos`. Si el factor está mal, el peso sale mal; no inventamos ese número.

## d) Qué quedó fuera de mi parte

El backend (API, modelos, base de datos, Docker y la validación de la clave), la app de escritorio, las predicciones con IA, ofertas, reservas y reclamos. También quedó fuera flashear los ESP32 reales, decidir entre las opciones A y B, y registrar datos privados: SSID, contraseñas y API keys se llenan en `config.h` local y nunca se suben.
