// Heart&Eat - Báscula ESP32 + HX711
// Servidor /peso y /tara (IGUAL que el sketch original) + cliente HTTP:
// cada 5 segundos hace POST /api/lecturas con el peso leído del HX711.
//
// Librerías: "HX711 Arduino Library" de Bogdan Necula (Bogde)
//            "ArduinoJson" de Benoit Blanchon (versión 7)
// WiFi y HTTPClient ya vienen con el core ESP32.
// Placa: ESP32 Dev Module. Monitor serie: 115200.

#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "HX711.h"

const char* ssid     = "TU_WIFI";       // red de 2.4 GHz
const char* password = "TU_PASSWORD";

// ─── Configuración del envío a la API ─────────────────────────────────────────
// IP de la PC en la red local (la de ipconfig). No uses localhost.
#define SERVER_URL "http://192.168.1.50:8000"
#define CODIGO_DISPOSITIVO "ESP32-BASCULA-01"
#define CATEGORIA_ID 1
#define API_KEY "clave-de-ejemplo"   // debe coincidir con BASCULA_API_KEY del .env
#define INTERVALO_POST_MS 5000
#define API_TIMEOUT_MS 8000

// Modo de prueba aparte:false = peso real del HX711 y es_simulada=false.
//                       true  = peso fijo de 450 g y es_simulada=true.
// NO es el funcionamiento normal del hardware.
#define SIMULAR false
const float PESO_SIMULADO = 450.0;

#define DT  4
#define SCK 5

// 1.0 para calibrar (paso 4). Después pon aquí tu factor.
float FACTOR = 1.0;

HX711 balanza;
WebServer server(80);
float peso = 0;
unsigned long ultimaLectura = 0;
unsigned long ultimoPost = 0;
unsigned long ultimoIntentoWifi = 0;

// ─── Servidor /peso y /tara (sin cambios) ─────────────────────────────────────

void cors() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Private-Network", "true");
}

void handlePeso() {
  cors();
  String json = "{\"device_id\":\"ESP32-BASCULA-01\",\"peso_gramos\":" + String(peso, 1) + "}";
  server.send(200, "application/json", json);
}

void handleTara() {
  cors();
  balanza.tare(10);
  peso = 0;
  server.send(200, "application/json", "{\"ok\":true}");
}

void handleOptions() {
  cors();
  server.sendHeader("Access-Control-Allow-Methods", "GET,OPTIONS");
  server.send(204);
}

// ─── Cliente: POST /api/lecturas ──────────────────────────────────────────────

void enviarLectura() {
  if (WiFi.status() != WL_CONNECTED) {
    // Reconectar sin bloquear el loop; mientras tanto se sigue pesando.
    if (millis() - ultimoIntentoWifi > 10000) {
      ultimoIntentoWifi = millis();
      WiFi.begin(ssid, password);
    }
    Serial.println("Sin WiFi: lectura no enviada.");
    return;
  }

  float pesoEnviado = SIMULAR ? PESO_SIMULADO : peso;

  HTTPClient http;
  String url = String(SERVER_URL) + "/api/lecturas";
  if (!http.begin(url)) {
    Serial.println("No se pudo armar la URL del POST.");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  http.setTimeout(API_TIMEOUT_MS);

  JsonDocument doc;
  doc["codigo_dispositivo"] = CODIGO_DISPOSITIVO;
  doc["peso_g"] = pesoEnviado;
  doc["categoria_id"] = CATEGORIA_ID;
  doc["tipo"] = "lectura";
  doc["es_simulada"] = SIMULAR;

  char cuerpo[256];
  serializeJson(doc, cuerpo, sizeof(cuerpo));

  int codigo = http.POST(cuerpo);
  Serial.print("POST /api/lecturas -> HTTP ");
  Serial.print(codigo);
  Serial.print(" ");
  Serial.println(http.getString());
  http.end();
}

// ─── Setup (sin cambios) ──────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  balanza.begin(DT, SCK);
  balanza.set_scale(FACTOR);
  delay(2000);          // que se estabilice
  balanza.tare(20);     // en cero (la báscula debe estar vacía al encender)

  WiFi.begin(ssid, password);
  Serial.print("Conectando");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("IP de la bascula: ");
  Serial.println(WiFi.localIP());   // <- esta IP va en el HTML

  server.on("/peso", HTTP_GET, handlePeso);
  server.on("/tara", HTTP_GET, handleTara);
  server.on("/peso", HTTP_OPTIONS, handleOptions);
  server.on("/tara", HTTP_OPTIONS, handleOptions);
  server.begin();
}

// ─── Loop: pesa, atiende el servidor y envía cada 5 s ─────────────────────────

void loop() {
  server.handleClient();

  if (millis() - ultimaLectura > 300) {
    ultimaLectura = millis();
    peso = balanza.get_units(3);
    if (peso > -2 && peso < 2) peso = 0;   // ignora ruido chiquito
    Serial.println(peso, 1);               // útil para calibrar
  }

  if (millis() - ultimoPost >= INTERVALO_POST_MS) {
    ultimoPost = millis();
    enviarLectura();
  }
}
