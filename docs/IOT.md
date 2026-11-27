# Báscula ESP32

Parte IoT (Octavio y Eduardo). El ESP32 pesa sobrante con una celda de carga y un HX711, y manda cada pesaje estable a `POST /api/lecturas` con el header `X-API-Key`. El panel usa `POST /basculas/lectura-esp32` (sin key) para enviar mediciones manuales.

Hardware de esta guía: **ESP32 DevKit + HX711 + celda de carga de 4 hilos**. El sketch único `firmware/bascula/bascula.ino` usa DT en GPIO 4 y SCK en GPIO 5. La variante con `config.h` trae DT 16 / SCK 4 como ejemplo: usa la que corresponda a tu cableado, pero **no flashear ambos sketches en la misma báscula**.

## Cableado

La celda trae cuatro cables. Los colores cambian según el fabricante: si la tuya no coincide, usa la hoja de esa celda. Lo que no cambia es el nombre del pin en el HX711.

| Celda de carga | HX711 |
|---|---|
| E+ (rojo, excitación +) | E+ |
| E- (negro, excitación -) | E- |
| A+ (verde, señal +) | A+ |
| A- (blanco, señal -) | A- |

| HX711 | ESP32 DevKit |
|---|---|
| VCC | 3.3 V |
| GND | GND |
| DT | GPIO 4 (sketch único) / GPIO 16 (variante `config.h`) |
| SCK | GPIO 5 (sketch único) / GPIO 4 (variante `config.h`) |

GND del HX711 y GND del ESP32 van juntos. No alimentes el módulo a 5 V y conectes DT directo al ESP32: ese pin es de 3.3 V.

## Qué hay en el firmware

| Archivo | Para qué |
|---|---|
| `firmware/esp32_bascula/config.example.h` | Plantilla. Se copia como `config.h` |
| `firmware/esp32_bascula/config.h` | Tus datos locales. Git lo ignora |
| `firmware/esp32_bascula/esp32_bascula.ino` | Sketch que pesa y envía |
| `firmware/esp32_bascula/calibracion/calibracion.ino` | Sketch aparte. Solo imprime la lectura cruda |
| `scripts/simular_bascula.py` | Plan B de la demo, sin hardware |

`config.h` lleva el WiFi, la IP de la PC, el código de la báscula, la API key, la categoría, los pines y el factor de calibración. No subas ese archivo.

Librerías en Arduino IDE: **HX711** (Bogdan Necula) y **ArduinoJson 7** (Benoit Blanchon). Placa: ESP32 Dev Module. Monitor serie: 115200.

## Preparar la API

La API tiene que estar arriba (`docker compose up` en la raíz) y hace falta, en este orden, un vendedor, una categoría y la báscula. Anota los `id` que devuelva cada `POST`: el firmware usa el id de la categoría, no el nombre.

Los JSON de abajo usan datos de ejemplo. La clave `clave-de-ejemplo` tiene que ser **la misma** en el `POST /basculas` y en `API_KEY` de `config.h`.

En PowerShell pega cada línea completa. `curl.exe` evita que `curl` se confunda con `Invoke-WebRequest`.

```text
curl.exe -s -X POST http://localhost:8000/usuarios/ -H "Content-Type: application/json" -d "{\"nombre\":\"Ana Perez\",\"email\":\"ana@demo.local\",\"password\":\"demo123\",\"rol\":\"VENDEDOR\",\"nombre_negocio\":\"Fruteria Ana\",\"tipo_negocio\":\"FRUTERIA\"}"
```

```text
curl.exe -s -X POST http://localhost:8000/categorias/ -H "Content-Type: application/json" -d "{\"nombre\":\"Frutas\",\"es_perecedero\":true,\"vida_util_dias\":5}"
```

```text
curl.exe -s -X POST http://localhost:8000/basculas/ -H "Content-Type: application/json" -d "{\"usuario_id\":1,\"codigo_dispositivo\":\"ESP32-BASCULA-01\",\"api_key\":\"clave-de-ejemplo\",\"alias\":\"Mostrador\"}"
```

Si el `id` de la categoría no es 1, cambia `CATEGORIA_ID` en `config.h` y `--categoria` en el simulador.

## Flashear y calibrar

1. Copia `firmware/esp32_bascula/config.example.h` como `config.h` en la misma carpeta.
2. Pon el SSID, la contraseña, la IP LAN de la PC (la que sale en `ipconfig`, por ejemplo `http://192.168.1.50:8000`), el código, la API key y el id de categoría.
3. Abre la carpeta `firmware/esp32_bascula/calibracion` como sketch **aparte**. No la metas dentro del sketch principal: Arduino juntaría los dos `.ino`.
4. Sube `calibracion.ino` con la báscula vacía. Cuando diga "Tara lista", pon un peso conocido (una bolsa de 500 g sirve).
5. El factor es `lectura cruda / gramos`. Anótalo en `FACTOR_CALIBRACION` de `config.h`.
6. Abre `firmware/esp32_bascula/esp32_bascula.ino`, compila y sube.
7. En el monitor serie debe salir la tara y, al conectar, la IP del ESP32.
8. Pon un sobrante de más de 30 g y espera a que deje de moverse. El LED parpadea lento sin WiFi, se queda encendido un momento si la API respondió bien y parpadea rápido si falló.

Con `SIMULAR` en `true` el sketch no usa el HX711: inventa pesos y manda `es_simulada: true`. Úsalo solo para probar la red.

El LED integrado de muchos DevKit está en el GPIO 2. Si enciende con nivel alto o bajo depende de la placa: si el LED se comporta al revés, cambia `LED_ACTIVO_EN_BAJO` en `config.h`.

## Probar sin flashear

Simulador (desde la raíz del repo):

```bash
python scripts/simular_bascula.py --url http://127.0.0.1:8000 --codigo ESP32-BASCULA-01 --api-key clave-de-ejemplo --categoria 1 --n 5 --intervalo 2
```

Una sola lectura con curl, el mismo JSON que arma el ESP32:

```text
curl.exe -s -X POST http://localhost:8000/basculas/lectura-esp32 -H "Content-Type: application/json" -H "X-API-Key: clave-de-ejemplo" -d "{\"codigo_dispositivo\":\"ESP32-BASCULA-01\",\"peso_g\":450.0,\"categoria_id\":1,\"tipo\":\"lectura\",\"es_simulada\":true}"
```

Respuestas que ya existen:

| Código | Qué pasó |
|---|---|
| 200 | Se guardó. En la base queda como tipo `SOBRANTE` |
| 404 | No existe esa báscula o esa categoría |
| 403 | La báscula está desactivada |

El header `X-API-Key` ya sale del firmware y del simulador. `POST /api/lecturas` **sí lo valida** contra `BASCULA_API_KEY` del `.env`: una clave incorrecta responde 401. `POST /basculas/lectura-esp32` (el que usa el panel) todavía no lo valida. La clave del firmware debe ser la misma que se registró al crear la báscula y la del `.env`.

## Qué es una lectura

**Pendiente de confirmar con el equipo.**

Suposición con la que está hecho el firmware: una lectura es un pesaje estable del sobrante que alguien dejó sobre la báscula. No se manda cada muestra cruda. Se promedian varias muestras, se espera a que el peso deje de moverse (ventana de unos pocos promedios, diferencia menor a `UMBRAL_ESTABLE_G`) y solo entonces se hace el POST, si el peso supera `PESO_MINIMO_G` y cambió más de `UMBRAL_CAMBIO_G` desde el último envío. Al quitar el alimento (peso otra vez bajo el mínimo), el siguiente pesaje se puede enviar aunque se parezca al anterior.

Con el código actual, cada POST manda el **peso total** que hay en la báscula en ese momento, no lo que se agregó desde el envío anterior. Si alguien agrega comida y el peso sube más de `UMBRAL_CAMBIO_G` frente al último total enviado, se envía otra lectura con el nuevo total; si quita comida y baja más de ese umbral, también se envía. Consecuencia: si el backend sumara todas las lecturas, contaría dos veces lo que ya estaba. Ejemplo: 450 g y después 700 g se guardan como 2 filas, y la suma daría 1150 g aunque en la báscula solo haya 700 g.

**Decisión pendiente entre Octavio y Eduardo** (no implementada, solo documentada):

- **(A)** El backend trata cada lectura como una foto del peso total y usa solo la última (o la mayor) por sesión.
- **(B)** El firmware manda un solo pesaje por vez: el primer peso estable después de que la báscula estuvo vacía, y no manda otro hasta que se vacíe de nuevo.

Hasta que se decida, evita sumar lecturas para calcular el sobrante.

El JSON siempre lleva `"tipo": "lectura"`. El backend ignora ese campo y guarda la fila como `SOBRANTE`.

## Problemas frecuentes

- **No conecta al WiFi.** El ESP32 solo usa 2.4 GHz. Una red de solo 5 GHz no va a aparecer.
- **El POST nunca llega y curl en la misma PC sí funciona.** En `SERVER_URL` va la IP LAN de la PC, no `localhost` ni `127.0.0.1`. El firewall de Windows suele bloquear el puerto 8000 para otras máquinas de la red: permite la entrada a ese puerto en la red privada, o abre el puerto para `docker` / Python.
- **HTTP -1 o timeout en el monitor serie.** La PC y el ESP32 no se ven, la API está caída, o la URL tiene una barra de más al final. El POST espera máximo 2 s y cada muestra del HX711 tiene timeout de 300 ms, así que un cable suelto no congela el servidor `/peso`.
- **404.** Falta registrar la báscula con ese `codigo_dispositivo`, o `CATEGORIA_ID` no existe. Créalos con los POST de arriba y revisa el id.
- **403.** Alguien llamó a `PATCH /basculas/{id}/desactivar`. Hay que volver a dejarla activa en la base; el firmware no tiene un endpoint para eso.
- **El peso sale al revés o enorme.** El factor es el de tu celda, no el de ejemplo. Repite la calibración. Si vacío no da cerca de 0, la tara no corrió: reinicia con la báscula vacía.
- **HX711 no responde.** DT y SCK intercambiados, o VCC/GND sueltos.

## Pendientes para el backend

No se tocó la API. Esto haría falta del otro lado:

1. **Verificar `X-API-Key` también en el panel.** `POST /api/lecturas` ya valida la clave global del `.env`. Falta hacerlo en `POST /basculas/lectura-esp32`: calcular SHA-256 y comparar con `api_key_hash` de la báscula. Si se agrega, el panel tendría que empezar a enviar el header.
2. **Categorías iniciales.** Sin un `POST /categorias` previo, toda lectura responde 404. Una semilla al arrancar (Frutas, Verduras, etc.) evitaría ese paso en la demo.
3. **Código de báscula repetido.** `POST /basculas` no atrapa un `codigo_dispositivo` duplicado. MySQL puede responder 500 en lugar de un error claro.
4. **Confirmar qué es una lectura.** El firmware asume un pesaje estable de sobrante y un `categoria_id` fijo en `config.h`. Si el equipo quiere inventario, varios alimentos por báscula o elegir la categoría desde la app, hay que cambiar el firmware.
5. **Reactivar una báscula.** Existe desactivar (`PATCH /basculas/{id}/desactivar`) y no hay un alta de vuelta. Un 403 deja la báscula muda hasta que alguien cambie `activa` en la base.
6. **Decidir qué significa una lectura.** Ver la decisión pendiente entre Octavio y Eduardo en "Qué es una lectura". El backend no debe sumar lecturas como si fueran peso agregado sin que el equipo elija la opción A o la B.
7. **Error 500 al guardar fechas.** En la prueba del simulador, `POST /basculas/lectura-esp32` respondió 500 al actualizar `BASCULAS.ultima_conexion`; `POST /usuarios/` falló igual con `creado_en`. SQLModel pide fechas con zona horaria (`datetime.now(timezone.utc)`) o campos anotados como `NaiveDatetime`. El simulador sí llegó a la API con el JSON y la clave correctos, pero la lectura no se guardó. No se tocó el backend.
