"""
routers/categorias.py

Gestión de categorías de alimento (ej. Frutas, Verduras, Lácteos, Panadería).
Necesarias para clasificar lecturas de peso, predicciones y ofertas.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import CategoriaAlimento
from app.schemas import CategoriaCreate, CategoriaPublic

router = APIRouter(prefix="/categorias", tags=["Categorías de Alimento"])


@router.get("/", response_model=list[CategoriaPublic], summary="Listar categorías de alimento")
def listar_categorias(session: Session = Depends(get_session)):
    """Devuelve todas las categorías registradas."""
    return session.exec(select(CategoriaAlimento)).all()


@router.get("/{categoria_id}", response_model=CategoriaPublic, summary="Obtener una categoría por ID")
def obtener_categoria(categoria_id: int, session: Session = Depends(get_session)):
    categoria = session.get(CategoriaAlimento, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return categoria


@router.post("/", response_model=CategoriaPublic, summary="Crear una categoría de alimento")
def crear_categoria(data: CategoriaCreate, session: Session = Depends(get_session)):
    """Crea una nueva categoría verificando que el nombre no esté repetido."""
    existente = session.exec(
        select(CategoriaAlimento).where(CategoriaAlimento.nombre == data.nombre)
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail=f"La categoría '{data.nombre}' ya existe")

    nueva = CategoriaAlimento(**data.model_dump())
    session.add(nueva)
    session.commit()
    session.refresh(nueva)
    return nueva
