"""
routers/reservas.py

Gestión de reservas de excedente alimentario.

Regla de negocio clave: la suma de kg_reservados (excluyendo canceladas)
no puede superar kg_disponibles de la oferta. Esta validación se hace aquí,
en la capa de servicio, no en el modelo.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Reserva, Oferta, EstadoReserva
from app.schemas import ReservaCreate, ReservaPublic

router = APIRouter(prefix="/reservas", tags=["Reservas"])


@router.get("/", response_model=list[ReservaPublic], summary="Listar reservas")
def listar_reservas(
    oferta_id: int | None = None,
    usuario_id: int | None = None,
    session: Session = Depends(get_session),
):
    """
    Lista reservas con filtros opcionales:
    - ?oferta_id=X   → reservas de una oferta (útil para el vendedor)
    - ?usuario_id=X  → reservas de un receptor (útil para ver mis reservas)
    """
    query = select(Reserva)
    if oferta_id:
        query = query.where(Reserva.oferta_id == oferta_id)
    if usuario_id:
        query = query.where(Reserva.usuario_id == usuario_id)
    return session.exec(query).all()


@router.post("/", response_model=ReservaPublic, summary="Crear una reserva")
def crear_reserva(data: ReservaCreate, session: Session = Depends(get_session)):
    """
    Crea una reserva validando que no se supere la capacidad de la oferta.

    Suma los kg ya reservados (en estados PENDIENTE, CONFIRMADA o RECOGIDA)
    y verifica que quepan los nuevos kg_reservados.
    """
    # Verificar que la oferta existe y está activa
    oferta = session.get(Oferta, data.oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")

    # Calcular kg ya comprometidos (excluye las canceladas)
    reservas_vigentes = session.exec(
        select(Reserva).where(
            Reserva.oferta_id == data.oferta_id,
            Reserva.estado != EstadoReserva.CANCELADA,
        )
    ).all()

    kg_comprometidos = sum(r.kg_reservados for r in reservas_vigentes)
    kg_disponibles_reales = oferta.kg_disponibles - kg_comprometidos

    if data.kg_reservados > kg_disponibles_reales:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No hay suficiente excedente disponible. "
                f"Disponibles: {kg_disponibles_reales} kg, solicitados: {data.kg_reservados} kg."
            ),
        )

    nueva = Reserva(**data.model_dump())
    session.add(nueva)
    session.commit()
    session.refresh(nueva)
    return nueva


@router.patch("/{reserva_id}/estado", response_model=ReservaPublic, summary="Actualizar estado de una reserva")
def actualizar_estado(
    reserva_id: int,
    estado: EstadoReserva,
    session: Session = Depends(get_session),
):
    reserva = session.get(Reserva, reserva_id)
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    reserva.estado = estado
    session.add(reserva)
    session.commit()
    session.refresh(reserva)
    return reserva
