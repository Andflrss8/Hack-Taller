// Heart&Eat - Báscula ESP32 + HX711 (versión corregida)
// - Servidor /peso y /tara para el panel.
// - Cliente: POST /api/lecturas SOLO cuando el peso se estabiliza y hay algo encima.
//
// Librerías:
//   - "HX711 Arduino Library" de Bogdan Necula (Bogde)
//   - "ArduinoJson" de Benoit Blanchon (versión 7)
// WiFi, WebServer y HTTPClient ya vienen con el core ESP32.
// Placa: ESP32 Dev Module. Monitor serie: 115200.
//
// IMPORTANTE: este es el sketch único de la báscula. La carpeta
// firmware/esp32_bascula/ es una variante con config.h; no flashear ambos
// al mismo tiempo. Si el cableado real es DT 16 / SCK 4, cambiar DT y SCK.

#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "HX711.h"

// ─── CAMBIAR AQUÍ ──────────────────────────────────────────────────────────────
const char* ssid     = "NOMBRE_DE_TU_WIFI";     // Wi-Fi de 2.4 GHz
const char* password = "PASSWORD_DE_TU_WIFI";

// IP LAN de la PC que corre Docker. NO uses localhost.
#define SERVER_URL "http://192.168.1.50:8000"

#define CODIGO_DISPOSITIVO "ESP32-BASCULA-01"
#define CATEGORIA_ID 1
#define API_KEY "clave-de-ejemplo"   // debe coincidir con BASCULA_API_KEY del .env

#define API_TIMEOUT_MS 2000          // si el backend no responde, no congela la báscula
#define REINTENTO_MS 5000            // espera entre intentos si el POST falla

#define UMBRAL_MINIMO_G 10.0         // por debajo de esto se considera "báscula vacía"
#define VARIACION_G 5.0              // cambio mayor a esto = el peso se movió
#define ESTABLE_MS 2000              // tiempo quieto antes de enviar

// false = peso real del HX711 | true = manda 450 g cada 5 s, sin celda
#define SIMULAR false
const float PESO_SIMULADO = 450.0;
#define INTERVALO_SIMULADO_MS 5000

#define DT  4
#define SCK 5

// Para no colgar el servidor si se suelta un cable del HX711.
#define MUESTRAS_LECTURA 3
#define TIMEOUT_MUESTRA_MS 300
#define TIMEOUT_TARA_MS 300

// Calibración: pon aquí tu factor después de calibrar.
float FACTOR = 1.0;
// ───────────────────────────────────────────────────────────────────────────────

HX711 balanza;
WebServer server(80);

float pesoCrudo = 0;     // sin filtrar (se imprime en el serial, sirve para calibrar)
float peso = 0;          // filtrado (el que se muestra y se envía)
float pesoPrevio = 0;
float ultimoEnviado = 0;
unsigned long ultimaLectura = 0;
unsigned long estableDesde = 0;
unsigned long ultimoIntento = 0;
unsigned long ultimoIntentoWifi = 0;
unsigned long ultimoSimulado = 0;

// ─── Lectura del HX711 con timeout por muestra ────────────────────────────────

bool leerConTimeout(float &resultado) {
  float suma = 0;
  for (int i = 0; i < MUESTRAS_LECTURA; i++) {
    // is_ready() solo cubre la primera muestra: get_units() puede esperar
    // sin límite si el cable se suelta entre muestras. Por eso se espera
    // antes de CADA muestra y se aborta si el HX711 no responde.
    if (!balanza.wait_ready_timeout(TIMEOUT_MUESTRA_MS)) {
      return false;
    }
    suma += balanza.get_units(1);
  }
  resultado = suma / MUESTRAS_LECTURA;
  return true;
}

bool tareaConTimeout(int muestras) {
  for (int i = 0; i < muestras; i++) {
    if (!balanza.wait_ready_timeout(TIMEOUT_TARA_MS)) {
      return false;
    }
  }
  balanza.tare(muestras);
  return true;
}

// ─── Servidor /peso y /tara ────────────────────────────────────────────────────

void cors() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Private-Network", "true");
}

void handlePeso() {
  cors();
  String json = "{\"device_id\":\"" CODIGO_DISPOSITIVO "\",\"peso_gramos\":"
              + String(peso, 1) + "}";
  server.send(200, "application/json", json);
}

void handleTara() {
  cors();
  if (tareaConTimeout(10)) {
    peso = 0;
    pesoCrudo = 0;
    ultimoEnviado = 0;
    server.send(200, "application/json", "{\"ok\":true}");
  } else {
    server.send(503, "application/json", "{\"ok\":false,\"error\":\"hx711\"}");
  }
}

void handleOptions() {
  cors();
  server.sendHeader("Access-Control-Allow-Methods", "GET,OPTIONS");
  server.send(204);
}

// ─── Cliente: POST /api/lecturas ───────────────────────────────────────────────

bool enviarLectura(float pesoEnviado) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Sin WiFi: lectura no enviada.");
    return false;
  }

  HTTPClient http;
  String url = String(SERVER_URL) + "/api/lecturas";

  if (!http.begin(url)) {
    Serial.println("No se pudo armar la URL del POST.");
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  http.setTimeout(API_TIMEOUT_MS);

  JsonDocument doc;
  doc["codigo_dispositivo"] = CODIGO_DISPOSITIVO;
  doc["peso_g"] = round(pesoEnviado * 10.0) / 10.0;
  doc["categoria_id"] = CATEGORIA_ID;
  doc["tipo"] = "lectura";
  doc["es_simulada"] = SIMULAR;

  char cuerpo[256];
  serializeJson(doc, cuerpo, sizeof(cuerpo));

  int codigo = http.POST(cuerpo);

  Serial.print("POST /api/lecturas -> ");
  if (codigo > 0) {
    Serial.print("HTTP ");
    Serial.print(codigo);
    Serial.print(" ");
    Serial.println(http.getString());
  } else {
    Serial.println(http.errorToString(codigo));
  }

  http.end();
  return codigo >= 200 && codigo < 300;
}

// ─── Setup ─────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);

  balanza.begin(DT, SCK);
  balanza.set_scale(FACTOR);
  delay(2000);   // que se estabilice

  if (tareaConTimeout(20)) {
    Serial.println("Tara lista.");
  } else {
    Serial.println("HX711 no responde. Revisa DT, SCK, VCC y GND.");
  }

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid, password);
  Serial.print("Conectando");

  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("IP de la báscula: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("No conectó al WiFi. Seguirá intentando.");
  }

  server.on("/peso", HTTP_GET, handlePeso);
  server.on("/tara", HTTP_GET, handleTara);
  server.on("/peso", HTTP_OPTIONS, handleOptions);
  server.on("/tara", HTTP_OPTIONS, handleOptions);
  server.begin();
}

// ─── Loop ──────────────────────────────────────────────────────────────────────

void loop() {
  server.handleClient();

  // Reconectar WiFi sin bloquear.
  if (WiFi.status() != WL_CONNECTED && millis() - ultimoIntentoWifi > 10000) {
    ultimoIntentoWifi = millis();
    WiFi.begin(ssid, password);
  }

  if (SIMULAR) {
    // Modo prueba: 450 g cada 5 s.
    if (millis() - ultimoSimulado >= INTERVALO_SIMULADO_MS) {
      ultimoSimulado = millis();
      enviarLectura(PESO_SIMULADO);
    }
    return;
  }

  // Leer peso cada 300 ms, con timeout por muestra para no congelar /peso.
  if (millis() - ultimaLectura > 300) {
    ultimaLectura = millis();

    float leido = 0;
    if (leerConTimeout(leido)) {
      pesoCrudo = leido;
      peso = leido;
      if (peso < 2) peso = 0;   // ruido pequeño y valores negativos
      Serial.println(pesoCrudo, 1);
    } else {
      Serial.println("HX711 no responde. Revisa cables DT y SCK.");
    }
  }

  // Detectar si el peso está quieto.
  if (fabs(peso - pesoPrevio) > VARIACION_G) estableDesde = millis();
  pesoPrevio = peso;

  // Báscula vacía: ya se puede registrar otra pesada.
  if (peso <= UMBRAL_MINIMO_G) ultimoEnviado = 0;

  // Enviar una sola vez cuando el peso queda estable y hay algo encima.
  if (peso > UMBRAL_MINIMO_G &&
      millis() - estableDesde > ESTABLE_MS &&
      fabs(peso - ultimoEnviado) > VARIACION_G &&
      millis() - ultimoIntento > REINTENTO_MS) {
    ultimoIntento = millis();
    if (enviarLectura(peso)) {
      ultimoEnviado = peso;
    }
  }
}
