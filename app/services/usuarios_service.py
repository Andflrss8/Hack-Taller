"""
services/usuarios_service.py

Resuelve el usuario demo según su rol. Evita ids fijos en los schemas:
el vendedor y el receptor pueden tener ids distintos según el orden en que
se crearon en cada base de datos.
"""

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import RolUsuario, Usuario


def resolver_usuario(
    session: Session,
    rol: RolUsuario,
    usuario_id: int | None = None,
) -> Usuario:
    """Usa el id indicado o, si no viene, el primer usuario con ese rol."""
    if usuario_id is not None:
        usuario = session.get(Usuario, usuario_id)
        if not usuario:
            raise HTTPException(status_code=404, detail=f"Usuario con id={usuario_id} no encontrado")
        return usuario

    usuario = session.exec(
        select(Usuario).where(Usuario.rol == rol).order_by(Usuario.id)
    ).first()
    if not usuario:
        raise HTTPException(
            status_code=404,
            detail=f"No hay ningún usuario con rol {rol.value} registrado.",
        )
    return usuario
