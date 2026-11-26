"""
routers/predicciones.py

Gestión de predicciones de excedente/desperdicio.

Flujo:
1. Se crea una predicción (POST /predicciones)
2. Se vinculan las lecturas que la alimentaron (POST /predicciones/{id}/lecturas/{lectura_id})
3. La predicción origina una o varias ofertas (POST /ofertas)
4. Después, se puede registrar kg_reales para evaluar el modelo (PATCH /predicciones/{id}/kg-reales)
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Bascula,
    CategoriaAlimento,
    LecturaPeso,
    Prediccion,
    PrediccionLectura,
    Usuario,
)
from app.schemas import (
    AnalisisCompletoIAResponse,
    GenerarPrediccionIARequest,
    PrediccionCreate,
    PrediccionPublic,
)
from app.services.flujo_ia import ejecutar_analisis_y_guardar

router = APIRouter(prefix="/predicciones", tags=["Predicciones"])


@router.get("/", response_model=list[PrediccionPublic], summary="Listar predicciones")
def listar_predicciones(
    usuario_id: int | None = None,
    session: Session = Depends(get_session),
):
    query = select(Prediccion)
    if usuario_id:
        query = query.where(Prediccion.usuario_id == usuario_id)
    return session.exec(query).all()


@router.get("/{prediccion_id}", response_model=PrediccionPublic, summary="Obtener una predicción")
def obtener_prediccion(prediccion_id: int, session: Session = Depends(get_session)):
    pred = session.get(Prediccion, prediccion_id)
    if not pred:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")
    return pred


@router.post("/", response_model=PrediccionPublic, summary="Crear una predicción")
def crear_prediccion(data: PrediccionCreate, session: Session = Depends(get_session)):
    nueva = Prediccion(**data.model_dump())
    session.add(nueva)
    session.commit()
    session.refresh(nueva)
    return nueva


@router.post(
    "/{prediccion_id}/lecturas/{lectura_id}",
    summary="Vincular una lectura a una predicción",
)
def vincular_lectura(
    prediccion_id: int,
    lectura_id: int,
    session: Session = Depends(get_session),
):
    """
    Registra en PREDICCION_LECTURAS (tabla intermedia N:M) que
    esta lectura de peso alimenta esta predicción.
    """
    # Evitar duplicados en la tabla intermedia
    existente = session.exec(
        select(PrediccionLectura).where(
            PrediccionLectura.prediccion_id == prediccion_id,
            PrediccionLectura.lectura_id == lectura_id,
        )
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="La lectura ya está vinculada a esta predicción")

    vinculo = PrediccionLectura(prediccion_id=prediccion_id, lectura_id=lectura_id)
    session.add(vinculo)
    session.commit()
    return {"mensaje": "Lectura vinculada correctamente a la predicción"}


@router.patch(
    "/{prediccion_id}/kg-reales",
    response_model=PrediccionPublic,
    summary="Registrar kg reales desperdiciados",
)
def registrar_kg_reales(
    prediccion_id: int,
    kg_reales: Decimal,
    session: Session = Depends(get_session),
):
    """
    Permite al sistema de IA o al operador registrar cuántos kg se
    desperdiciaron realmente, para comparar contra la predicción y
    mejorar el modelo.
    """
    pred = session.get(Prediccion, prediccion_id)
    if not pred:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")
    pred.kg_reales = kg_reales
    session.add(pred)
    session.commit()
    session.refresh(pred)
    return pred


@router.post(
    "/generar-ia",
    response_model=AnalisisCompletoIAResponse,
    summary="Generar predicción con Gemini a partir de lecturas de báscula",
)
def generar_prediccion_ia(
    data: GenerarPrediccionIARequest,
    session: Session = Depends(get_session),
):
    """
    Usa Gemini (con validación de seguridad y reglas anti-alucinación) para
    estimar el desperdicio a partir de lecturas reales de la báscula ESP32.
    Si no se envían `lectura_ids`, toma las últimas 5 lecturas del usuario/categoría.
    """
    vendedor = session.get(Usuario, data.usuario_id)
    if not vendedor:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    categoria = session.get(CategoriaAlimento, data.categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría de alimento no encontrada")

    if data.lectura_ids:
        lecturas = session.exec(
            select(LecturaPeso).where(LecturaPeso.id.in_(data.lectura_ids))
        ).all()
    else:
        # Buscar las últimas 5 lecturas de las básculas del vendedor para esa categoría
        basculas_ids = session.exec(
            select(Bascula.id).where(Bascula.usuario_id == data.usuario_id)
        ).all()
        if not basculas_ids:
            raise HTTPException(status_code=404, detail="El usuario no tiene básculas registradas")

        lecturas = session.exec(
            select(LecturaPeso)
            .where(
                LecturaPeso.bascula_id.in_(basculas_ids),
                LecturaPeso.categoria_id == data.categoria_id,
            )
            .order_by(LecturaPeso.fecha_hora.desc())
            .limit(5)
        ).all()

    return ejecutar_analisis_y_guardar(
        session=session,
        vendedor=vendedor,
        categoria=categoria,
        lecturas=list(lecturas),
        fecha_objetivo=data.fecha_objetivo,
        crear_oferta=False,
    )
