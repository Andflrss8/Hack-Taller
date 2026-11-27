"""
services/lecturas_service.py

Único punto de guardado de lecturas de peso. Lo usan:
- POST /basculas/lectura-esp32 (panel)
- POST /api/lecturas (firmware ESP32)

Una lectura es un SNAPSHOT del peso actual en la báscula; NO se suman lecturas.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Bascula, CategoriaAlimento, LecturaPeso, TipoLectura, utcnow


def guardar_lectura(
    session: Session,
    codigo_dispositivo: str,
    peso_g: Decimal,
    categoria_id: int,
    es_simulada: bool,
) -> LecturaPeso:
    """Valida dispositivo/categoría, guarda la lectura y actualiza la báscula."""
    bascula = session.exec(
        select(Bascula).where(Bascula.codigo_dispositivo == codigo_dispositivo)
    ).first()
    if not bascula:
        raise HTTPException(
            status_code=404, detail=f"Báscula '{codigo_dispositivo}' no registrada."
        )
    if not bascula.activa:
        raise HTTPException(status_code=403, detail="La báscula está desactivada.")

    if not session.get(CategoriaAlimento, categoria_id):
        raise HTTPException(
            status_code=404,
            detail=f"Categoría con id={categoria_id} no encontrada. Créela primero en POST /categorias.",
        )

    lectura = LecturaPeso(
        bascula_id=bascula.id,
        categoria_id=categoria_id,
        peso_g=Decimal(str(peso_g)),
        tipo=TipoLectura.SOBRANTE,
        fecha_hora=utcnow(),
        es_simulada=es_simulada,
    )
    bascula.ultima_conexion = utcnow()
    session.add(bascula)
    session.add(lectura)
    session.commit()
    session.refresh(lectura)
    return lectura
