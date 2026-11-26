/*
  Calibracion del HX711. Sketch aparte: abre ESTA carpeta en Arduino IDE.
  No la juntes con esp32_bascula.ino. No usa WiFi ni manda nada a la API.

  Pasos:
    1. Sube este sketch con la bascula vacia.
    2. Espera "Tara lista" en el Monitor Serie (115200).
    3. Pon un peso conocido, por ejemplo 500 g.
    4. Anota la lectura cruda cuando deje de saltar.
    5. FACTOR_CALIBRACION = lectura cruda / gramos conocidos.
       Ejemplo: cruda -352500 y peso 500 g -> factor -705.
    6. Escribe ese factor en config.h del sketch principal.

  Pines por defecto: DT = 16, SCK = 4. Cambialos aqui si usaste otros.
*/

#include <HX711.h>

const int PIN_DT = 16;
const int PIN_SCK = 4;

HX711 celda;

void setup() {
  Serial.begin(115200);
  delay(300);
  celda.begin(PIN_DT, PIN_SCK);
  celda.set_scale();

  Serial.println("Calibracion HX711.");
  Serial.println("Deja la bascula vacia. Tara en 2 segundos...");
  delay(2000);

  if (!celda.is_ready()) {
    Serial.println("HX711 no responde. Revisa DT, SCK, VCC y GND.");
    return;
  }

  celda.tare(20);
  Serial.println("Tara lista. Pon un peso conocido.");
  Serial.println("Factor = lectura cruda / gramos de ese peso.");
}

void loop() {
  if (!celda.is_ready()) {
    Serial.println("HX711 no responde.");
    delay(1000);
    return;
  }

  // get_value ya resta la tara. Con la bascula vacia debe verse cerca de 0.
  float cruda = celda.get_value(10);
  Serial.print("Lectura cruda: ");
  Serial.println(cruda, 1);
  delay(800);
}
