"""
routers/reclamos.py

Gestión de reclamos por fallas de báscula.
Un VENDEDOR reporta que su báscula no conecta, da peso incorrecto, etc.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bascula, Reclamo, EstadoReclamo, RolUsuario, utcnow
from app.schemas import ReclamoCreate, ReclamoPublic
from app.services.usuarios_service import resolver_usuario

router = APIRouter(prefix="/reclamos", tags=["Reclamos"])


def _publicar_reclamo(reclamo: Reclamo, session: Session) -> ReclamoPublic:
    """Completa el alias que el panel lee de /reclamos."""
    bascula = session.get(Bascula, reclamo.bascula_id) if reclamo.bascula_id else None
    return ReclamoPublic.model_validate(
        {
            **reclamo.model_dump(),
            "bascula": (bascula.alias or bascula.codigo_dispositivo) if bascula else None,
        }
    )


@router.get("/", response_model=list[ReclamoPublic], summary="Listar reclamos")
def listar_reclamos(
    usuario_id: int | None = None,
    session: Session = Depends(get_session),
):
    query = select(Reclamo)
    if usuario_id:
        query = query.where(Reclamo.usuario_id == usuario_id)
    return [_publicar_reclamo(r, session) for r in session.exec(query).all()]


@router.get("/{reclamo_id}", response_model=ReclamoPublic, summary="Obtener un reclamo")
def obtener_reclamo(reclamo_id: int, session: Session = Depends(get_session)):
    reclamo = session.get(Reclamo, reclamo_id)
    if not reclamo:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return _publicar_reclamo(reclamo, session)


@router.post("/", response_model=ReclamoPublic, summary="Crear un reclamo de falla")
def crear_reclamo(data: ReclamoCreate, session: Session = Depends(get_session)):
    vendedor = resolver_usuario(session, RolUsuario.VENDEDOR, data.usuario_id)
    valores = data.model_dump()
    valores["usuario_id"] = vendedor.id
    nuevo = Reclamo(**valores)
    session.add(nuevo)
    session.commit()
    session.refresh(nuevo)
    return _publicar_reclamo(nuevo, session)


@router.patch("/{reclamo_id}/resolver", response_model=ReclamoPublic, summary="Marcar reclamo como resuelto")
def resolver_reclamo(reclamo_id: int, session: Session = Depends(get_session)):
    """Marca el reclamo como RESUELTO y registra la fecha/hora de resolución."""
    reclamo = session.get(Reclamo, reclamo_id)
    if not reclamo:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    reclamo.estado = EstadoReclamo.RESUELTO
    reclamo.resuelto_en = utcnow()
    session.add(reclamo)
    session.commit()
    session.refresh(reclamo)
    return _publicar_reclamo(reclamo, session)
