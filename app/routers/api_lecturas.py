"""
app/routers/api_lecturas.py

Endpoint de la báscula ESP32 -> API: POST /api/lecturas.

Solo valida y guarda la lectura en LECTURAS_PESO. No dispara el flujo de IA.
Los errores de validación responden 400 (no 422) porque quien consume el
endpoint es el firmware del ESP32.
"""

import math
import os
from decimal import Decimal

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.database import get_session
from app.schemas import LecturaPublic
from app.services.lecturas_service import guardar_lectura

load_dotenv()

# El firmware envía este header; se valida contra el .env.
API_KEY_ESPERADA = os.getenv("BASCULA_API_KEY", "clave-de-ejemplo")

router = APIRouter(prefix="/api", tags=["Hardware -> API"])


def _fallar(detalle: str) -> None:
    """Todo problema con el payload o el guardado responde 400."""
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detalle)


@router.post(
    "/lecturas",
    response_model=LecturaPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar lectura enviada por la báscula ESP32",
    description="""
Recibe exactamente el JSON del ESP32:

```json
{
  "codigo_dispositivo": "ESP32-BASCULA-01",
  "peso_g": 450.0,
  "categoria_id": 1,
  "tipo": "lectura",
  "es_simulada": false
}
```

Valida los campos, guarda la lectura como `SOBRANTE` y responde **201**.
Cualquier falla de validación o de guardado responde **400**.
El campo `tipo` se ignora (decisión del equipo, ver CLAUDE.md).
    """,
)
async def crear_lectura_hardware(
    request: Request,
    session: Session = Depends(get_session),
):
    # 0. Validar la API key del firmware (401 si falta o es incorrecta).
    if request.headers.get("X-API-Key") != API_KEY_ESPERADA:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key ausente o incorrecta.",
        )

    # 1. Leer el JSON del firmware (validación manual para responder 400 y no 422)
    try:
        data = await request.json()
    except Exception:
        _fallar("El cuerpo debe ser un JSON válido.")

    if not isinstance(data, dict):
        _fallar("El cuerpo debe ser un objeto JSON.")

    # 2. Validar campos
    codigo = data.get("codigo_dispositivo")
    if not isinstance(codigo, str) or not codigo.strip():
        _fallar("codigo_dispositivo es obligatorio y debe ser texto no vacío.")

    peso = data.get("peso_g")
    if isinstance(peso, bool) or not isinstance(peso, (int, float)) or not math.isfinite(peso):
        _fallar("peso_g debe ser un número.")
    if peso < 0:
        _fallar("peso_g debe ser mayor o igual a 0.")

    categoria_id = data.get("categoria_id")
    if isinstance(categoria_id, bool) or not isinstance(categoria_id, int):
        _fallar("categoria_id debe ser un entero.")

    es_simulada = data.get("es_simulada", False)
    if not isinstance(es_simulada, bool):
        _fallar("es_simulada debe ser verdadero o falso.")

    # 3. Guardar con la misma función que usa el panel.
    #    El tipo del JSON se ignora: se guarda como SOBRANTE (snapshot, no suma).
    try:
        return guardar_lectura(
            session=session,
            codigo_dispositivo=codigo,
            peso_g=Decimal(str(peso)),
            categoria_id=categoria_id,
            es_simulada=es_simulada,
        )
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        _fallar(f"No se pudo guardar la lectura: {exc}")
