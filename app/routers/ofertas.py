"""
routers/ofertas.py

Publicación y gestión de ofertas de excedente alimentario.
Un VENDEDOR crea una oferta; los RECEPTORES la ven y hacen reservas.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Oferta, EstadoOferta
from app.schemas import OfertaCreate, OfertaPublic

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
