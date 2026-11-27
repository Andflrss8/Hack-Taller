"""
schemas.py — Schemas de entrada (Create) y salida (Public) para la API.

REGLA CLAVE: Los schemas *Public nunca exponen campos sensibles
(password_hash, api_key_hash). Los modelos SQLModel son para la BD;
estos schemas son lo que ve el cliente de escritorio.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.models import (
    RolUsuario, TipoNegocio, TipoLectura,
    EstadoOferta, EstadoReserva, TipoReclamo, EstadoReclamo,
    utcnow,
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


class LecturaPanel(LecturaPublic):
    """Lectura con los alias que el panel usa en 'Lecturas recientes'."""
    c: str          # nombre de la categoría
    g: float        # gramos como número (el JS llama g.toFixed)
    h: str          # hora legible
    s: bool         # es_simulada


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
    # Si el panel no manda usuario_id, el router resuelve al vendedor por rol.
    usuario_id: Optional[int] = None
    prediccion_id: Optional[int] = None
    categoria_id: int
    titulo: str
    descripcion: Optional[str] = None
    # El panel manda cantidad_kg; se acepta también el nombre canónico.
    kg_disponibles: Decimal = Field(
        validation_alias=AliasChoices("kg_disponibles", "cantidad_kg")
    )
    # El panel manda horario_recogida (texto) y ciudad, no fechas.
    ventana_inicio: datetime = Field(default_factory=utcnow)
    ventana_fin: datetime = Field(
        default_factory=lambda: utcnow() + timedelta(hours=24)
    )
    horario_recogida: Optional[str] = None
    ciudad: Optional[str] = None


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
    # Alias que el panel necesita para pintar la tarjeta.
    categoria: Optional[str] = None
    ciudad: Optional[str] = None
    horario_recogida: Optional[str] = None
    cantidad_kg: Optional[Decimal] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  RESERVAS
# ══════════════════════════════════════════════════════════════════════════════

class ReservaCreate(BaseModel):
    oferta_id: int
    # Si el panel no manda usuario_id, el router resuelve al receptor por rol.
    usuario_id: Optional[int] = None
    kg_reservados: Decimal = Field(
        validation_alias=AliasChoices("kg_reservados", "cantidad_kg")
    )

    @field_validator("kg_reservados")
    @classmethod
    def kg_positivo(cls, v: Decimal) -> Decimal:
        # Validación básica: no se pueden reservar 0 o negativos
        if v <= 0:
            raise ValueError("kg_reservados debe ser mayor que 0")
        return v


class ReservaEstadoUpdate(BaseModel):
    """El panel envía PATCH /reservas/{id} con {"estado": "..."}."""
    estado: EstadoReserva


class ReservaPublic(BaseModel):
    id: int
    oferta_id: int
    usuario_id: int
    kg_reservados: Decimal
    estado: EstadoReserva
    creada_en: datetime
    # Alias que el panel necesita para pintar la reserva.
    oferta: Optional[str] = None
    quien: Optional[str] = None
    cantidad_kg: Optional[Decimal] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  RECLAMOS
# ══════════════════════════════════════════════════════════════════════════════

class ReclamoCreate(BaseModel):
    # Si el panel no manda usuario_id, el router resuelve al vendedor por rol.
    usuario_id: Optional[int] = None
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
    # Alias que el panel necesita para pintar el reclamo.
    bascula: Optional[str] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  INTELIGENCIA ARTIFICIAL (GEMINI) Y CENTROS DE DONACIÓN CERCANOS
# ══════════════════════════════════════════════════════════════════════════════

class ReceptorCercano(BaseModel):
    """Organización o usuario con rol RECEPTOR registrado en nuestra BD."""
    id: int
    nombre: str
    nombre_negocio: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    ciudad_region: Optional[str] = None
    distancia_km: Optional[float] = None


class CentroDonacionPublic(BaseModel):
    """Centro de donación externo sugerido por Gemini (DIF, Cáritas, etc.)."""
    nombre: str
    tipo_institucion: str
    ubicacion_referencia: str
    motivo_cercania: str
    requiere_verificacion: bool


class CentrosCercanosResponse(BaseModel):
    """Respuesta combinada: receptores de la BD + centros sugeridos por IA."""
    oferta_id: int
    ubicacion_local: Optional[str] = None
    receptores_registrados: List[ReceptorCercano] = []
    centros_donacion_sugeridos: List[CentroDonacionPublic] = []


class GenerarPrediccionIARequest(BaseModel):
    """Petición para generar una predicción con Gemini a partir de lecturas reales."""
    usuario_id: int
    categoria_id: int
    # Si no se envían IDs, el endpoint toma las últimas 5 lecturas de esa báscula/categoría
    lectura_ids: Optional[List[int]] = None
    fecha_objetivo: Optional[date] = None


class GenerarOfertaIARequest(BaseModel):
    """Petición para generar una oferta y buscar centros de donación cercanos."""
    prediccion_id: Optional[int] = None
    lectura_id: Optional[int] = None


class AnalisisCompletoIAResponse(BaseModel):
    """Respuesta completa del flujo ESP32 -> Predicción IA -> Oferta + Centros cercanos."""
    lectura: Optional[LecturaPublic] = None
    prediccion: PrediccionPublic
    oferta: Optional[OfertaPublic] = None
    justificacion_ia: str
    receptores_registrados: List[ReceptorCercano] = []
    centros_donacion_sugeridos: List[CentroDonacionPublic] = []
