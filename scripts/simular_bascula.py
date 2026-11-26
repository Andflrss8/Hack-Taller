#!/usr/bin/env python3
"""Manda lecturas de prueba a la API, como si fueran de una báscula ESP32.

Sirve para la demo si el hardware no está listo. Solo usa la librería estándar.
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request


def peso_realista() -> float:
    """Gramos típicos de un sobrante en frutería o miscelánea."""
    base = random.choice([120, 180, 250, 340, 480, 620, 850, 1100])
    peso = base + random.uniform(-25, 25)
    return round(max(peso, 50.0), 1)


def enviar(url_base: str, codigo: str, api_key: str, categoria: int, peso: float) -> bool:
    cuerpo = {
        "codigo_dispositivo": codigo,
        "peso_g": peso,
        "categoria_id": categoria,
        "tipo": "lectura",
        "es_simulada": True,
    }
    destino = url_base.rstrip("/") + "/basculas/lectura-esp32"
    peticion = urllib.request.Request(
        destino,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            texto = respuesta.read().decode("utf-8")
            print(f"HTTP {respuesta.status}  {peso} g")
            print(texto)
            return 200 <= respuesta.status < 300
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}  {peso} g")
        print(detalle)
        return False
    except urllib.error.URLError as error:
        print(f"Error de red  {peso} g")
        print(error.reason)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Simula lecturas de una báscula ESP32")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base de la API, sin barra final")
    parser.add_argument("--codigo", default="ESP32-BASCULA-01")
    parser.add_argument("--api-key", default="clave-de-ejemplo")
    parser.add_argument("--categoria", type=int, default=1)
    parser.add_argument("--n", type=int, default=5, help="Cuántas lecturas enviar")
    parser.add_argument("--intervalo", type=float, default=2.0, help="Segundos entre lecturas")
    args = parser.parse_args()

    if args.n < 1:
        print("Nada que enviar: --n debe ser al menos 1")
        return 1

    fallos = 0
    for indice in range(args.n):
        peso = peso_realista()
        if not enviar(args.url, args.codigo, args.api_key, args.categoria, peso):
            fallos += 1
        if indice + 1 < args.n:
            time.sleep(args.intervalo)

    if fallos:
        print(f"Terminó con {fallos} envío(s) fallido(s).")
        return 1
    print("Todas las lecturas se enviaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
