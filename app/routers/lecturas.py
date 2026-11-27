"""
routers/lecturas.py

Gestión de lecturas de peso registradas manualmente desde la app de escritorio.
Las lecturas automáticas del ESP32 llegan por POST /basculas/lectura-esp32.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import CategoriaAlimento, LecturaPeso, utcnow
from app.schemas import LecturaCreate, LecturaPanel, LecturaPublic

router = APIRouter(prefix="/lecturas", tags=["Lecturas de Peso"])


def _para_panel(lectura: LecturaPeso, session: Session) -> LecturaPanel:
    """Alias que el panel lee en 'Lecturas recientes'."""
    categoria = session.get(CategoriaAlimento, lectura.categoria_id)
    return LecturaPanel.model_validate(
        {
            **lectura.model_dump(),
            "c": categoria.nombre if categoria else "—",
            "g": float(lectura.peso_g),
            "h": lectura.fecha_hora.strftime("%H:%M"),
            "s": lectura.es_simulada,
        }
    )


@router.get("/", response_model=list[LecturaPanel], summary="Listar lecturas de peso")
def listar_lecturas(
    bascula_id: int | None = None,
    session: Session = Depends(get_session),
):
    """
    Lista lecturas de peso. Filtra por báscula si se pasa ?bascula_id=X.
    Útil para que la app de escritorio muestre el historial de una báscula.
    """
    query = select(LecturaPeso).order_by(LecturaPeso.fecha_hora.desc())
    if bascula_id is not None:
        query = query.where(LecturaPeso.bascula_id == bascula_id)
    return [_para_panel(lectura, session) for lectura in session.exec(query).all()]


@router.get("/{lectura_id}", response_model=LecturaPublic, summary="Obtener una lectura por ID")
def obtener_lectura(lectura_id: int, session: Session = Depends(get_session)):
    lectura = session.get(LecturaPeso, lectura_id)
    if not lectura:
        raise HTTPException(status_code=404, detail="Lectura no encontrada")
    return lectura


@router.post("/", response_model=LecturaPublic, summary="Registrar una lectura manualmente")
def crear_lectura(data: LecturaCreate, session: Session = Depends(get_session)):
    """Permite al operador registrar una lectura desde la app de escritorio (sin ESP32)."""
    nueva = LecturaPeso(
        bascula_id=data.bascula_id,
        categoria_id=data.categoria_id,
        peso_g=data.peso_g,
        descripcion=data.descripcion,
        tipo=data.tipo,
        fecha_hora=utcnow(),
        es_simulada=data.es_simulada,
    )
    session.add(nueva)
    session.commit()
    session.refresh(nueva)
    return nueva
