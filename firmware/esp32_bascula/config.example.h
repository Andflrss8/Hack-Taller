#pragma once

// Copia este archivo como config.h (en esta misma carpeta) y cambia los valores.
// config.h no se sube a git. No pongas aquí la clave real del negocio si vas a compartir la carpeta.

// WiFi de 2.4 GHz. El ESP32 no se conecta a redes de solo 5 GHz.
#define WIFI_SSID "cambia-por-tu-red"
#define WIFI_PASS "cambia-por-tu-clave"

// IP de la PC en la red local, no uses localhost: el ESP32 es otra máquina.
// Sin barra al final.
#define SERVER_URL "http://192.168.1.50:8000"

// Debe coincidir con el codigo_dispositivo registrado en POST /basculas.
#define CODIGO_DISPOSITIVO "ESP32-BASCULA-01"

// La misma cadena que se registró en la báscula. El firmware la manda en X-API-Key.
#define API_KEY "cambia-esta-clave"

// Id que devolvió POST /categorias. Si no existe, la API responde 404.
#define CATEGORIA_ID 1

// HX711. Cambialos si cableaste otros pines.
#define PIN_HX711_DT 16
#define PIN_HX711_SCK 4

// LED integrado del DevKit (suele ser el GPIO 2, activo en bajo).
#define PIN_LED 2
#define LED_ACTIVO_EN_BAJO true

// get_units() = lectura_cruda / FACTOR_CALIBRACION.
// Calculalo con el sketch calibracion/ y un peso conocido. Este número es solo un ejemplo.
#define FACTOR_CALIBRACION -7050.0f

#define NUM_MUESTRAS 10           // muestras que se promedian en cada lectura
#define VENTANA_ESTABLE 4         // promedios seguidos para decir que ya no se mueve
#define UMBRAL_ESTABLE_G 5.0f     // diferencia máxima (gramos) dentro de esa ventana
#define UMBRAL_CAMBIO_G 20.0f     // solo se envía si cambió al menos esto desde el último envío
#define PESO_MINIMO_G 30.0f       // por debajo de esto se ignora (báscula vacía o ruido)
#define MUESTRAS_TARA 20

#define HTTP_TIMEOUT_MS 2000          // corto: si el backend no responde, no congela la báscula
#define MAX_INTENTOS 3            // intentos de POST por pesaje
#define REINTENTO_WIFI_MS 10000   // cada cuánto se relanza WiFi.begin, sin esperar a que conecte

// true: no usa el HX711, inventa pesos y manda es_simulada = true.
#define SIMULAR false
