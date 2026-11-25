"""
routers/usuarios.py

Registro y consulta de usuarios.
Los passwords se hashean con SHA-256 antes de guardarse.
NOTA para producción: reemplazar SHA-256 con bcrypt o argon2.
"""

import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Usuario
from app.schemas import UsuarioCreate, UsuarioPublic

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


def _hash_password(password: str) -> str:
    """
    Hashea el password con SHA-256.
    Suficiente para hackathon; en producción usar bcrypt/argon2.
    """
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/", response_model=UsuarioPublic, summary="Registrar un nuevo usuario")
def crear_usuario(data: UsuarioCreate, session: Session = Depends(get_session)):
    # Verificar email único antes de insertar
    if session.exec(select(Usuario).where(Usuario.email == data.email)).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    nuevo = Usuario(
        nombre=data.nombre,
        email=data.email,
        password_hash=_hash_password(data.password),  # Nunca se guarda en claro
        telefono=data.telefono,
        rol=data.rol,
        nombre_negocio=data.nombre_negocio,
        tipo_negocio=data.tipo_negocio,
        direccion=data.direccion,
        ciudad_region=data.ciudad_region,
        estado=data.estado,
        pais=data.pais,
        latitud=data.latitud,
        longitud=data.longitud,
    )
    session.add(nuevo)
    session.commit()
    session.refresh(nuevo)
    return nuevo


@router.get("/", response_model=list[UsuarioPublic], summary="Listar todos los usuarios")
def listar_usuarios(session: Session = Depends(get_session)):
    return session.exec(select(Usuario)).all()


@router.get("/{usuario_id}", response_model=UsuarioPublic, summary="Obtener un usuario por ID")
def obtener_usuario(usuario_id: int, session: Session = Depends(get_session)):
    usuario = session.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario
