/*
  Báscula ESP32 + HX711.
  Pesa el sobrante, espera a que el peso se quede quieto y lo manda a la API.

  Flujo completo, una y otra vez:
    1. Leer el peso del HX711 (o inventarlo si SIMULAR está en true).
    2. Promediar varias muestras para que un saltito no parezca comida nueva.
    3. Esperar a que el peso se quede quieto: eso es un "peso estable".
    4. Decidir si se envía: tiene que pasar el mínimo y haber cambiado
       lo suficiente desde el último envío.
    5. Hacer el POST con el peso total que hay ahora en la báscula.
    6. Si falló la red o el servidor, reintentar unas veces; si falló la
       clave, la báscula o la categoría, no reintentar porque mandar lo
       mismo otra vez no lo arregla.

  Umbrales y tiempos (están en config.h):
    - NUM_MUESTRAS: cuántas lecturas se promedian para obtener un peso.
    - VENTANA_ESTABLE + UMBRAL_ESTABLE_G: cuántos promedios seguidos y cuánta
      diferencia máxima se acepta para decir "ya no se mueve".
    - PESO_MINIMO_G: por debajo de eso se trata como báscula vacía o ruido.
    - UMBRAL_CAMBIO_G: cuánto debe cambiar el total frente al último envío.
    - MAX_INTENTOS y HTTP_TIMEOUT_MS: intentos por pesaje y espera máxima
      de cada POST antes de rendirse.
    - REINTENTO_WIFI_MS: cada cuánto se vuelve a intentar la conexión WiFi.

  Librerías (Administrador de librerías de Arduino IDE):
    - HX711 de Bogdan Necula (bogde)
    - ArduinoJson de Benoit Blanchon, versión 7
  WiFi y HTTPClient ya vienen con el core ESP32.

  Antes de compilar: copia config.example.h como config.h y llena tus datos.
  Placa: ESP32 Dev Module. Monitor serie: 115200.

  Variante con config.h del sketch firmware/bascula/bascula.ino. Tiene el
  mismo endpoint (/api/lecturas) y el mismo timeout (HTTP_TIMEOUT_MS).
  NO flashear ambos sketches a la vez en la misma báscula.
*/

#if __has_include("config.h")
#include "config.h"
#else
#error "Copia config.example.h como config.h y completa los datos locales"
#endif

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <HX711.h>
#include <WiFi.h>

HX711 bascula;

// historial guarda los últimos promedios. Sirve para compararlos y saber
// si el peso ya se quedó quieto. Los otros dos solo recorren ese arreglo.
float historial[VENTANA_ESTABLE];
int historialTotal = 0;
int historialIndice = 0;

// ultimoPesoEnviado es el último total que se mandó; -9999 significa "nunca".
// yaEnviado recuerda que hubo un pesaje, para poder empezar de cero al vaciar.
float ultimoPesoEnviado = -9999.0f;
bool yaEnviado = false;

// hayEnvio = true mientras hay un pesaje esperando turno para enviarse.
// pesoPorEnviar guarda ese total; intentosHechos y proximoIntentoMs
// controlan los reintentos sin detener el resto del programa.
bool hayEnvio = false;
float pesoPorEnviar = 0;
int intentosHechos = 0;
unsigned long proximoIntentoMs = 0;

// Para no saturar la red: solo se relanza WiFi.begin cada cierto tiempo.
// wifiAnunciado evita repetir la IP en el monitor serie a cada vuelta.
unsigned long ultimoIntentoWifi = 0;
bool wifiAnunciado = false;

// Hasta qué instante se muestra el aviso de éxito / error en el LED.
unsigned long ledOkHasta = 0;
unsigned long ledErrorHasta = 0;

// Pesos falsos que se usan solo cuando SIMULAR está en true.
const float PESOS_DE_PRUEBA[] = {180.0f, 420.0f, 95.0f, 760.0f, 310.0f};
const int CANTIDAD_PESOS_PRUEBA = 5;

// Prende o apaga el LED respetando si en esta placa funciona al revés.
// Así el mismo sketch sirve para DevKit distintos.
void escribirLed(bool encendido) {
  bool nivelAlto = encendido;
  if (LED_ACTIVO_EN_BAJO) {
    nivelAlto = !encendido;
  }
  digitalWrite(PIN_LED, nivelAlto ? HIGH : LOW);
}

// Traduce el estado del programa en avisos del LED: WiFi, error o éxito.
// Se llama en cada vuelta del loop para que el aviso se vea aunque se espere.
void actualizarLed() {
  unsigned long ahora = millis();
  if (WiFi.status() != WL_CONNECTED) {
    escribirLed((ahora / 400) % 2 == 0);
    return;
  }
  if (ahora < ledErrorHasta) {
    escribirLed((ahora / 100) % 2 == 0);
    return;
  }
  escribirLed(ahora < ledOkHasta);
}

// Mantiene el WiFi conectado sin quedarse en un while: si no hay red lo intenta
// más tarde y mientras tanto el loop sigue atendiendo el LED y los envíos.
void mantenerWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiAnunciado) {
      wifiAnunciado = true;
      Serial.print("WiFi listo. IP de la bascula: ");
      Serial.println(WiFi.localIP());
    }
    return;
  }

  wifiAnunciado = false;
  if (millis() - ultimoIntentoWifi < REINTENTO_WIFI_MS) {
    return;
  }

  ultimoIntentoWifi = millis();
  Serial.println("Sin WiFi. Reintentando conexion...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// Inicia el HX711 y hace la tara: le dice "esto es cero" con la báscula vacía.
// Sin tara, todos los pesos saldrían corridos.
void prepararBascula() {
  bascula.begin(PIN_HX711_DT, PIN_HX711_SCK);
  bascula.set_scale(FACTOR_CALIBRACION);
  Serial.println("Tara: no pongas nada en la bascula.");
  delay(1500);
  // No llamar a tare() directo: espera con timeout para no colgarse si
  // el cable DT/SCK está suelto.
  for (int i = 0; i < MUESTRAS_TARA; i++) {
    if (!bascula.wait_ready_timeout(300)) {
      Serial.println("HX711 no responde. Revisa DT, SCK, VCC y GND.");
      return;
    }
  }
  bascula.tare(MUESTRAS_TARA);
  Serial.println("Tara lista.");
}

// Devuelve un peso falso que cambia cada 12 segundos.
// Sirve para probar el envío sin depender de la celda calibrada.
float pesoDePrueba() {
  int indice = (millis() / 12000) % CANTIDAD_PESOS_PRUEBA;
  return PESOS_DE_PRUEBA[indice];
}

// Toma un peso real promediando NUM_MUESTRAS lecturas, o el falso si SIMULAR.
// Si el HX711 no responde devuelve 0, para no inventar un peso.
float leerPeso() {
  if (SIMULAR) {
    return pesoDePrueba();
  }
  // is_ready() solo cubre la primera muestra: get_units(N) puede esperar
  // sin límite si el cable se suelta entre muestras. Esperar antes de CADA
  // muestra y abortar si no responde.
  float suma = 0;
  for (int i = 0; i < NUM_MUESTRAS; i++) {
    if (!bascula.wait_ready_timeout(300)) {
      Serial.println("HX711 no responde. Revisa cables DT y SCK.");
      return 0;
    }
    suma += bascula.get_units(1);
  }
  float peso = suma / NUM_MUESTRAS;
  return peso < 0 ? 0 : peso;
}

// Llena el historial con promedios y dice si ya dejaron de moverse.
// Evita enviar mientras alguien todavía está acomodando la comida.
bool pesoEstable(float peso) {
  historial[historialIndice] = peso;
  historialIndice = (historialIndice + 1) % VENTANA_ESTABLE;
  if (historialTotal < VENTANA_ESTABLE) {
    historialTotal++;
    return false;
  }

  float minimo = historial[0];
  float maximo = historial[0];
  for (int i = 1; i < VENTANA_ESTABLE; i++) {
    if (historial[i] < minimo) minimo = historial[i];
    if (historial[i] > maximo) maximo = historial[i];
  }
  return (maximo - minimo) <= UMBRAL_ESTABLE_G;
}

// Guarda el peso que se quiere mandar y marca que hay un envío pendiente.
// Separa "ya decidí enviar" de "enviar ahora", para poder reintentar después.
void programarEnvio(float peso) {
  hayEnvio = true;
  pesoPorEnviar = peso;
  intentosHechos = 0;
  proximoIntentoMs = millis();
  Serial.print("Peso estable. Se va a enviar: ");
  Serial.print(peso, 1);
  Serial.println(" g");
}

// Arma el JSON fijo y hace el POST con la clave en el header X-API-Key.
// Está aparte para que procesarEnvio solo se ocupe de cuándo llamarlo.
int postLectura(float peso) {
  HTTPClient http;
  String url = String(SERVER_URL) + "/api/lecturas";

  if (!http.begin(url)) {
    Serial.println("No se pudo armar la URL.");
    return -1;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  http.setTimeout(HTTP_TIMEOUT_MS);

  JsonDocument doc;
  doc["codigo_dispositivo"] = CODIGO_DISPOSITIVO;
  doc["peso_g"] = peso;
  doc["categoria_id"] = CATEGORIA_ID;
  doc["tipo"] = "lectura";
  doc["es_simulada"] = (bool)SIMULAR;

  char cuerpo[256];
  serializeJson(doc, cuerpo, sizeof(cuerpo));

  int codigo = http.POST(cuerpo);
  Serial.print("HTTP ");
  Serial.print(codigo);
  Serial.print(" ");
  Serial.println(http.getString());
  http.end();
  return codigo;
}

// Dice si un error tiene sentido intentarlo otra vez.
// Los errores de clave, báscula o categoría no cambian con un reintento.
bool convieneReintentar(int codigo) {
  // 401, 403 y 404 no se arreglan reintentando: la clave, la báscula o la categoría están mal.
  if (codigo == 401 || codigo == 403 || codigo == 404) {
    return false;
  }
  return codigo < 200 || codigo >= 300;
}

// Manda el pesaje pendiente cuando hay WiFi y ya pasó la espera.
// Cuenta los intentos y espera cada vez más para no llenar la API de peticiones.
void procesarEnvio() {
  if (!hayEnvio || millis() < proximoIntentoMs) {
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("El envio espera a que vuelva el WiFi.");
    proximoIntentoMs = millis() + 1000;
    return;
  }

  intentosHechos++;
  Serial.print("Intento ");
  Serial.print(intentosHechos);
  Serial.print(" de ");
  Serial.println(MAX_INTENTOS);

  int codigo = postLectura(pesoPorEnviar);
  if (codigo >= 200 && codigo < 300) {
    ultimoPesoEnviado = pesoPorEnviar;
    yaEnviado = true;
    hayEnvio = false;
    ledOkHasta = millis() + 2000;
    Serial.println("Lectura guardada.");
    return;
  }

  if (!convieneReintentar(codigo) || intentosHechos >= MAX_INTENTOS) {
    ultimoPesoEnviado = pesoPorEnviar;
    yaEnviado = true;
    hayEnvio = false;
    ledErrorHasta = millis() + 2500;
    Serial.println("No se guardo la lectura.");
    return;
  }

  // 1 s, luego 2 s, luego 4 s. El loop sigue atendiendo el LED y el WiFi.
  unsigned long espera = 1000UL << (intentosHechos - 1);
  proximoIntentoMs = millis() + espera;
  Serial.print("Reintento en ");
  Serial.print(espera / 1000);
  Serial.println(" s");
}

// Decide si el peso actual merece un envío nuevo.
// Al vaciar la báscula borra la memoria del último peso para que el próximo
// pesaje cuente aunque se parezca al anterior.
void revisarPeso(float peso) {
  if (!pesoEstable(peso)) {
    return;
  }

  if (peso < PESO_MINIMO_G) {
    if (yaEnviado) {
      ultimoPesoEnviado = -9999.0f;
      yaEnviado = false;
      Serial.println("Peso por debajo del minimo. Lista para otro pesaje.");
    }
    return;
  }

  if (fabs(peso - ultimoPesoEnviado) < UMBRAL_CAMBIO_G) {
    return;
  }

  programarEnvio(peso);
}

// Al arrancar: prepara el puerto serie, el LED, la calibración y el WiFi.
void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_LED, OUTPUT);
  escribirLed(false);

  Serial.println("Bascula iniciando.");
  if (SIMULAR) {
    Serial.println("SIMULAR activo: pesos de prueba y es_simulada=true.");
  } else {
    prepararBascula();
  }

  WiFi.mode(WIFI_STA);
  ultimoIntentoWifi = millis();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.println("Buscando WiFi...");
}

// Repite sin bloquear: WiFi, LED, envío pendiente y peso nuevo.
void loop() {
  mantenerWifi();
  actualizarLed();

  if (hayEnvio) {
    procesarEnvio();
    delay(50);
    return;
  }

  revisarPeso(leerPeso());
  if (SIMULAR) {
    delay(300);
  }
}
