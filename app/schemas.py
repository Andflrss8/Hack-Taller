"""
schemas.py — Schemas de entrada (Create) y salida (Public) para la API.

REGLA CLAVE: Los schemas *Public nunca exponen campos sensibles
(password_hash, api_key_hash). Los modelos SQLModel son para la BD;
estos schemas son lo que ve el cliente de escritorio.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models import (
    RolUsuario, TipoNegocio, TipoLectura,
    EstadoOferta, EstadoReserva, TipoReclamo, EstadoReclamo
)


# ══════════════════════════════════════════════════════════════════════════════
#  USUARIOS
# ══════════════════════════════════════════════════════════════════════════════

class UsuarioCreate(BaseModel):
    """Datos necesarios para registrar un nuevo usuario."""
    nombre: str
    email: str
    # 'password' en claro: el router lo hashea antes de guardarlo
    password: str
    telefono: Optional[str] = None
    rol: RolUsuario
    nombre_negocio: Optional[str] = None
    tipo_negocio: Optional[TipoNegocio] = None
    direccion: Optional[str] = None
    ciudad_region: Optional[str] = None
    estado: Optional[str] = None
    pais: Optional[str] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None


class UsuarioPublic(BaseModel):
    """Respuesta pública — SIN password_hash."""
    id: int
    nombre: str
    email: str
    telefono: Optional[str]
    rol: RolUsuario
    nombre_negocio: Optional[str]
    tipo_negocio: Optional[TipoNegocio]
    direccion: Optional[str]
    ciudad_region: Optional[str]
    estado: Optional[str]
    pais: Optional[str]
    latitud: Optional[Decimal]
    longitud: Optional[Decimal]
    creado_en: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  BASCULAS
# ══════════════════════════════════════════════════════════════════════════════

class BasculaCreate(BaseModel):
    """Datos para registrar una nueva báscula."""
    usuario_id: int
    codigo_dispositivo: str
    # 'api_key' en claro: el router la hashea antes de guardar como api_key_hash
    api_key: str
    alias: Optional[str] = None


class BasculaPublic(BaseModel):
    """Respuesta pública — SIN api_key_hash."""
    id: int
    usuario_id: int
    codigo_dispositivo: str
    alias: Optional[str]
    activa: bool
    ultima_conexion: Optional[datetime]

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  ESP32 — JSON fijo que envía la báscula física
# ══════════════════════════════════════════════════════════════════════════════

class LecturaESP32(BaseModel):
    """
    Estructura exacta del JSON que manda el ESP32. NO modificar.

    El campo 'tipo' siempre llega como "lectura" desde el hardware;
    el endpoint lo ignora y guarda la lectura como SOBRANTE por defecto.
    """
    codigo_dispositivo: str
    peso_g: float
    categoria_id: int
    tipo: str         # Siempre "lectura" — se ignora en la lógica de negocio
    es_simulada: bool = False


# ══════════════════════════════════════════════════════════════════════════════
#  LECTURAS DE PESO
# ══════════════════════════════════════════════════════════════════════════════

class LecturaCreate(BaseModel):
    """Para crear una lectura manualmente desde la app de escritorio."""
    bascula_id: int
    categoria_id: Optional[int] = None
    peso_g: Decimal
    descripcion: Optional[str] = None
    tipo: TipoLectura
    es_simulada: bool = False


class LecturaPublic(BaseModel):
    id: int
    bascula_id: int
    categoria_id: Optional[int]
    peso_g: Decimal
    descripcion: Optional[str]
    tipo: TipoLectura
    fecha_hora: datetime
    es_simulada: bool

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  CATEGORIAS DE ALIMENTO
# ══════════════════════════════════════════════════════════════════════════════

class CategoriaCreate(BaseModel):
    nombre: str
    es_perecedero: bool = True
    vida_util_dias: Optional[int] = None


class CategoriaPublic(BaseModel):
    id: int
    nombre: str
    es_perecedero: bool
    vida_util_dias: Optional[int]

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICCIONES
# ══════════════════════════════════════════════════════════════════════════════

class PrediccionCreate(BaseModel):
    usuario_id: int
    categoria_id: int
    fecha_objetivo: date
    kg_estimados: Decimal
    confianza: Optional[Decimal] = None
    modelo: Optional[str] = None


class PrediccionPublic(BaseModel):
    id: int
    usuario_id: int
    categoria_id: int
    fecha_objetivo: date
    kg_estimados: Decimal
    # kg_reales se llena después, cuando se sabe cuánto se desperdició de verdad
    kg_reales: Optional[Decimal]
    confianza: Optional[Decimal]
    modelo: Optional[str]
    creada_en: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  OFERTAS
# ══════════════════════════════════════════════════════════════════════════════

class OfertaCreate(BaseModel):
    usuario_id: int
    prediccion_id: Optional[int] = None
    categoria_id: int
    titulo: str
    descripcion: Optional[str] = None
    kg_disponibles: Decimal
    ventana_inicio: datetime
    ventana_fin: datetime


class OfertaPublic(BaseModel):
    id: int
    usuario_id: int
    prediccion_id: Optional[int]
    categoria_id: int
    titulo: str
    descripcion: Optional[str]
    kg_disponibles: Decimal
    ventana_inicio: datetime
    ventana_fin: datetime
    estado: EstadoOferta

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  RESERVAS
# ══════════════════════════════════════════════════════════════════════════════

class ReservaCreate(BaseModel):
    oferta_id: int
    usuario_id: int
    kg_reservados: Decimal

    @field_validator("kg_reservados")
    @classmethod
    def kg_positivo(cls, v: Decimal) -> Decimal:
        # Validación básica: no se pueden reservar 0 o negativos
        if v <= 0:
            raise ValueError("kg_reservados debe ser mayor que 0")
        return v


class ReservaPublic(BaseModel):
    id: int
    oferta_id: int
    usuario_id: int
    kg_reservados: Decimal
    estado: EstadoReserva
    creada_en: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  RECLAMOS
# ══════════════════════════════════════════════════════════════════════════════

class ReclamoCreate(BaseModel):
    usuario_id: int
    bascula_id: Optional[int] = None
    tipo: TipoReclamo
    descripcion: str


class ReclamoPublic(BaseModel):
    id: int
    usuario_id: int
    bascula_id: Optional[int]
    tipo: TipoReclamo
    descripcion: str
    estado: EstadoReclamo
    creado_en: datetime
    resuelto_en: Optional[datetime]

    model_config = {"from_attributes": True}
