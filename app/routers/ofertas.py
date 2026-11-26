"""
routers/ofertas.py

Publicación y gestión de ofertas de excedente alimentario.
Un VENDEDOR crea una oferta; los RECEPTORES la ven y hacen reservas.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Bascula,
    CategoriaAlimento,
    EstadoOferta,
    LecturaPeso,
    Oferta,
    Prediccion,
    PrediccionLectura,
    Usuario,
)
from app.schemas import (
    AnalisisCompletoIAResponse,
    CentroDonacionPublic,
    CentrosCercanosResponse,
    GenerarOfertaIARequest,
    OfertaCreate,
    OfertaPublic,
)
from app.services.flujo_ia import (
    construir_info_negocio,
    ejecutar_analisis_y_guardar,
    obtener_receptores_cercanos,
)
from app.services.gemini_service import buscar_centros_donacion_gemini

router = APIRouter(prefix="/ofertas", tags=["Ofertas"])


@router.get("/", response_model=list[OfertaPublic], summary="Listar ofertas")
def listar_ofertas(
    estado: Optional[EstadoOferta] = None,
    usuario_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """
    Lista ofertas con filtros opcionales:
    - ?estado=ACTIVA   → solo las activas (útil para la vista de receptores)
    - ?usuario_id=X    → ofertas de un vendedor específico
    """
    query = select(Oferta)
    if estado:
        query = query.where(Oferta.estado == estado)
    if usuario_id:
        query = query.where(Oferta.usuario_id == usuario_id)
    return session.exec(query).all()


@router.get("/{oferta_id}", response_model=OfertaPublic, summary="Obtener una oferta")
def obtener_oferta(oferta_id: int, session: Session = Depends(get_session)):
    oferta = session.get(Oferta, oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    return oferta


@router.post("/", response_model=OfertaPublic, summary="Crear una oferta")
def crear_oferta(data: OfertaCreate, session: Session = Depends(get_session)):
    nueva = Oferta(**data.model_dump())
    session.add(nueva)
    session.commit()
    session.refresh(nueva)
    return nueva


@router.patch("/{oferta_id}/estado", response_model=OfertaPublic, summary="Cambiar estado de una oferta")
def actualizar_estado(
    oferta_id: int,
    estado: EstadoOferta,
    session: Session = Depends(get_session),
):
    """
    Cambia el estado de una oferta (ACTIVA → CANCELADA, AGOTADA, etc.).
    Útil para que el vendedor cierre o cancele una oferta desde la app.
    """
    oferta = session.get(Oferta, oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    oferta.estado = estado
    session.add(oferta)
    session.commit()
    session.refresh(oferta)
    return oferta


@router.post(
    "/generar-ia",
    response_model=AnalisisCompletoIAResponse,
    summary="Generar oferta con Gemini y obtener centros cercanos",
)
def generar_oferta_ia(
    data: GenerarOfertaIARequest,
    session: Session = Depends(get_session),
):
    """
    Genera una oferta y sugiere centros de donación cercanos (DIF, Cáritas, etc.)
    a partir de una `lectura_id` o una `prediccion_id`.
    """
    if not data.lectura_id and not data.prediccion_id:
        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar `lectura_id` o `prediccion_id`.",
        )

    if data.lectura_id:
        lectura = session.get(LecturaPeso, data.lectura_id)
        if not lectura:
            raise HTTPException(status_code=404, detail="Lectura no encontrada")
        bascula = session.get(Bascula, lectura.bascula_id)
        vendedor = session.get(Usuario, bascula.usuario_id)
        categoria = session.get(CategoriaAlimento, lectura.categoria_id)
        if not categoria:
            raise HTTPException(status_code=400, detail="La lectura no tiene categoría asignada")
        return ejecutar_analisis_y_guardar(
            session=session,
            vendedor=vendedor,
            categoria=categoria,
            lecturas=[lectura],
            crear_oferta=True,
        )

    # Si se pasó prediccion_id, recuperamos sus lecturas vinculadas
    prediccion = session.get(Prediccion, data.prediccion_id)
    if not prediccion:
        raise HTTPException(status_code=404, detail="Predicción no encontrada")
    vendedor = session.get(Usuario, prediccion.usuario_id)
    categoria = session.get(CategoriaAlimento, prediccion.categoria_id)

    vinculos = session.exec(
        select(PrediccionLectura).where(PrediccionLectura.prediccion_id == prediccion.id)
    ).all()
    lectura_ids = [v.lectura_id for v in vinculos]
    lecturas = (
        session.exec(select(LecturaPeso).where(LecturaPeso.id.in_(lectura_ids))).all()
        if lectura_ids
        else []
    )

    if not lecturas:
        raise HTTPException(
            status_code=400,
            detail="La predicción no tiene lecturas vinculadas para generar la oferta.",
        )

    return ejecutar_analisis_y_guardar(
        session=session,
        vendedor=vendedor,
        categoria=categoria,
        lecturas=list(lecturas),
        fecha_objetivo=prediccion.fecha_objetivo,
        crear_oferta=True,
    )


@router.get(
    "/{oferta_id}/centros-cercanos",
    response_model=CentrosCercanosResponse,
    summary="Listar centros de donación cercanos (DIF, Cáritas, etc.) para una oferta",
)
def obtener_centros_cercanos(oferta_id: int, session: Session = Depends(get_session)):
    """
    Devuelve para una oferta:
    1. `receptores_registrados`: usuarios con rol RECEPTOR en nuestra BD, ordenados por distancia.
    2. `centros_donacion_sugeridos`: centros locales (DIF, Cáritas, Bancos de Alimentos)
       sugeridos por Gemini según la ubicación del local vendedor.
    """
    oferta = session.get(Oferta, oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")

    vendedor = session.get(Usuario, oferta.usuario_id)
    if not vendedor:
        raise HTTPException(status_code=404, detail="Vendedor de la oferta no encontrado")

    receptores = obtener_receptores_cercanos(session, vendedor)
    negocio_info = construir_info_negocio(vendedor)

    try:
        sugeridos = buscar_centros_donacion_gemini(
            negocio_info=negocio_info,
            titulo_oferta=oferta.titulo,
            kg_disponibles=float(oferta.kg_disponibles),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al consultar Gemini: {e}")

    ubicacion_texto = ", ".join(
        p for p in [vendedor.ciudad_region, vendedor.estado, vendedor.pais] if p
    ) or None

    return CentrosCercanosResponse(
        oferta_id=oferta.id,
        ubicacion_local=ubicacion_texto,
        receptores_registrados=receptores,
        centros_donacion_sugeridos=[
            CentroDonacionPublic(**c.model_dump()) for c in sugeridos
        ],
    )
