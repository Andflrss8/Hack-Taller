"""
routers/bascula.py

Endpoints relacionados con las básculas ESP32.
El endpoint más importante es POST /basculas/lectura-esp32,
que recibe el JSON fijo del hardware y lo guarda en LECTURAS_PESO.
"""

import hashlib
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bascula, CategoriaAlimento, LecturaPeso, TipoLectura
from app.schemas import BasculaCreate, BasculaPublic, LecturaESP32, LecturaPublic

router = APIRouter(prefix="/basculas", tags=["Básculas"])


def _hash_key(key: str) -> str:
    """Hashea una clave con SHA-256. Nunca guardar claves en claro."""
    return hashlib.sha256(key.encode()).hexdigest()


# ─── ESP32 ────────────────────────────────────────────────────────────────────

@router.post(
    "/lectura-esp32",
    response_model=LecturaPublic,
    summary="Recibir lectura desde el ESP32",
    description="""
Endpoint que consume el JSON fijo del hardware:

```json
{
  "codigo_dispositivo": "ESP32-BASCULA-01",
  "peso_g": 450.0,
  "categoria_id": 1,
  "tipo": "lectura",
  "es_simulada": true
}
```

Busca la báscula por `codigo_dispositivo`, crea la lectura y actualiza
`ultima_conexion`. El campo `tipo` del JSON se ignora y se guarda como **SOBRANTE**.
    """,
)
def recibir_lectura_esp32(
    payload: LecturaESP32,
    session: Session = Depends(get_session),
):
    # 1. Buscar la báscula por su código de dispositivo único
    bascula = session.exec(
        select(Bascula).where(Bascula.codigo_dispositivo == payload.codigo_dispositivo)
    ).first()

    if not bascula:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Báscula con código '{payload.codigo_dispositivo}' no encontrada. "
                "Regístrela primero en POST /basculas."
            ),
        )

    if not bascula.activa:
        raise HTTPException(status_code=403, detail="La báscula está desactivada.")

    # Verificar que la categoría exista para evitar error 500 por llave foránea en MySQL
    categoria = session.get(CategoriaAlimento, payload.categoria_id)
    if not categoria:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Categoría con id={payload.categoria_id} no encontrada. "
                "Créela primero en POST /categorias."
            ),
        )

    # 2. Crear la lectura.
    #    El campo 'tipo' del ESP32 siempre es "lectura" (string genérico del hardware).
    #    Se guarda como SOBRANTE por decisión del equipo (ver CLAUDE.md sección 7).
    nueva_lectura = LecturaPeso(
        bascula_id=bascula.id,
        categoria_id=payload.categoria_id,
        peso_g=Decimal(str(payload.peso_g)),
        tipo=TipoLectura.SOBRANTE,
        fecha_hora=datetime.utcnow(),
        es_simulada=payload.es_simulada,
    )

    # 3. Actualizar la última vez que esta báscula envió datos
    bascula.ultima_conexion = datetime.utcnow()
    session.add(bascula)

    session.add(nueva_lectura)
    session.commit()
    session.refresh(nueva_lectura)

    return nueva_lectura


# ─── CRUD Báscula ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[BasculaPublic], summary="Listar básculas")
def listar_basculas(session: Session = Depends(get_session)):
    return session.exec(select(Bascula)).all()


@router.get("/{bascula_id}", response_model=BasculaPublic, summary="Obtener una báscula")
def obtener_bascula(bascula_id: int, session: Session = Depends(get_session)):
    bascula = session.get(Bascula, bascula_id)
    if not bascula:
        raise HTTPException(status_code=404, detail="Báscula no encontrada")
    return bascula


@router.post("/", response_model=BasculaPublic, summary="Registrar una nueva báscula")
def crear_bascula(data: BasculaCreate, session: Session = Depends(get_session)):
    """
    Registra una báscula y hashea su api_key antes de guardar.
    El api_key_hash nunca se devuelve en la respuesta.
    """
    nueva = Bascula(
        usuario_id=data.usuario_id,
        codigo_dispositivo=data.codigo_dispositivo,
        api_key_hash=_hash_key(data.api_key),  # Se guarda el hash, nunca la clave original
        alias=data.alias,
    )
    session.add(nueva)
    session.commit()
    session.refresh(nueva)
    return nueva


@router.patch("/{bascula_id}/desactivar", response_model=BasculaPublic, summary="Desactivar una báscula")
def desactivar_bascula(bascula_id: int, session: Session = Depends(get_session)):
    bascula = session.get(Bascula, bascula_id)
    if not bascula:
        raise HTTPException(status_code=404, detail="Báscula no encontrada")
    bascula.activa = False
    session.add(bascula)
    session.commit()
    session.refresh(bascula)
    return bascula
