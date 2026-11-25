from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from sqlalchemy import BigInteger, Column, ForeignKey, Text, DECIMAL
from sqlmodel import SQLModel, Field, Relationship


# ══════════════════════════════════════════════════════════════════════════════
#  ENUMS
#  Se usan como tipos en los modelos; SQLModel los mapea a VARCHAR en MySQL.
# ══════════════════════════════════════════════════════════════════════════════

class RolUsuario(str, Enum):
    VENDEDOR = "VENDEDOR"   # Dueño del negocio que publica ofertas
    RECEPTOR = "RECEPTOR"   # Organización/persona que hace reservas


class TipoNegocio(str, Enum):
    MISCELANEA = "MISCELANEA"
    FRUTERIA   = "FRUTERIA"
    CAFETERIA  = "CAFETERIA"
    OTRO       = "OTRO"


class TipoLectura(str, Enum):
    INVENTARIO = "INVENTARIO"  # Lectura de control de inventario
    SOBRANTE   = "SOBRANTE"    # Lectura de excedente/desperdicio


class EstadoOferta(str, Enum):
    ACTIVA    = "ACTIVA"
    AGOTADA   = "AGOTADA"
    EXPIRADA  = "EXPIRADA"
    CANCELADA = "CANCELADA"


class EstadoReserva(str, Enum):
    PENDIENTE  = "PENDIENTE"
    CONFIRMADA = "CONFIRMADA"
    RECOGIDA   = "RECOGIDA"
    CANCELADA  = "CANCELADA"


class TipoReclamo(str, Enum):
    NO_CONECTA      = "NO_CONECTA"
    PESO_INCORRECTO = "PESO_INCORRECTO"
    OTRO            = "OTRO"


class EstadoReclamo(str, Enum):
    ABIERTO    = "ABIERTO"
    EN_PROCESO = "EN_PROCESO"
    RESUELTO   = "RESUELTO"
    CERRADO    = "CERRADO"


# ══════════════════════════════════════════════════════════════════════════════
#  TABLA INTERMEDIA — PREDICCION_LECTURAS (N:M)
#  Se define primero para evitar problemas de forward-reference.
# ══════════════════════════════════════════════════════════════════════════════

class PrediccionLectura(SQLModel, table=True):
    __tablename__ = "PREDICCION_LECTURAS"

    prediccion_id: int = Field(
        foreign_key="PREDICCIONES.id",
        primary_key=True
    )
    # lectura_id es BigInt para coincidir con LECTURAS_PESO.id
    lectura_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("LECTURAS_PESO.id"),
            primary_key=True,
            nullable=False
        )
    )


# ══════════════════════════════════════════════════════════════════════════════
#  MODELOS PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════════

class Usuario(SQLModel, table=True):
    __tablename__ = "USUARIOS"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    email: str = Field(unique=True, index=True)
    # IMPORTANTE: nunca devolver password_hash en las respuestas de la API
    password_hash: str
    telefono: Optional[str] = None
    rol: RolUsuario
    nombre_negocio: Optional[str] = None
    tipo_negocio: Optional[TipoNegocio] = None
    direccion: Optional[str] = None
    ciudad_region: Optional[str] = None
    estado: Optional[str] = None
    pais: Optional[str] = None
    # Decimal(10,7) para precisión geográfica suficiente (~1 cm)
    latitud: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(10, 7)))
    longitud: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(10, 7)))
    creado_en: datetime = Field(default_factory=datetime.utcnow)

    # Relaciones (lazy por defecto en SQLModel)
    basculas: List["Bascula"] = Relationship(back_populates="usuario")
    predicciones: List["Prediccion"] = Relationship(back_populates="usuario")
    ofertas: List["Oferta"] = Relationship(back_populates="usuario")
    reservas: List["Reserva"] = Relationship(back_populates="usuario")
    reclamos: List["Reclamo"] = Relationship(back_populates="usuario")


class Bascula(SQLModel, table=True):
    __tablename__ = "BASCULAS"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="USUARIOS.id", index=True)
    # El ESP32 se identifica con este código al enviar lecturas
    codigo_dispositivo: str = Field(unique=True)
    # IMPORTANTE: nunca devolver api_key_hash en las respuestas de la API
    api_key_hash: str
    alias: Optional[str] = None
    activa: bool = True
    ultima_conexion: Optional[datetime] = None

    usuario: Optional[Usuario] = Relationship(back_populates="basculas")
    lecturas: List["LecturaPeso"] = Relationship(back_populates="bascula")
    reclamos: List["Reclamo"] = Relationship(back_populates="bascula")


class CategoriaAlimento(SQLModel, table=True):
    __tablename__ = "CATEGORIAS_ALIMENTO"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)
    es_perecedero: bool = True
    vida_util_dias: Optional[int] = None

    lecturas: List["LecturaPeso"] = Relationship(back_populates="categoria")
    predicciones: List["Prediccion"] = Relationship(back_populates="categoria")
    ofertas: List["Oferta"] = Relationship(back_populates="categoria")


class LecturaPeso(SQLModel, table=True):
    __tablename__ = "LECTURAS_PESO"

    # BigInt porque esta tabla crece rápido (una lectura por pesaje)
    id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    bascula_id: int = Field(foreign_key="BASCULAS.id", index=True)
    categoria_id: Optional[int] = Field(default=None, foreign_key="CATEGORIAS_ALIMENTO.id")
    peso_g: Decimal = Field(sa_column=Column(DECIMAL(10, 2)))
    # Equivalente a TINYTEXT: descripción corta opcional del operador
    descripcion: Optional[str] = Field(default=None, max_length=255)
    tipo: TipoLectura
    fecha_hora: datetime = Field(default_factory=datetime.utcnow, index=True)
    es_simulada: bool = False

    bascula: Optional[Bascula] = Relationship(back_populates="lecturas")
    categoria: Optional[CategoriaAlimento] = Relationship(back_populates="lecturas")


class Prediccion(SQLModel, table=True):
    __tablename__ = "PREDICCIONES"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="USUARIOS.id", index=True)
    categoria_id: int = Field(foreign_key="CATEGORIAS_ALIMENTO.id")
    fecha_objetivo: date
    kg_estimados: Decimal = Field(sa_column=Column(DECIMAL(10, 2)))
    # kg_reales se llena después para evaluar la precisión del modelo de IA
    kg_reales: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(10, 2)))
    # confianza entre 0.0000 y 1.0000
    confianza: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(5, 4)))
    modelo: Optional[str] = None
    creada_en: datetime = Field(default_factory=datetime.utcnow)

    usuario: Optional[Usuario] = Relationship(back_populates="predicciones")
    categoria: Optional[CategoriaAlimento] = Relationship(back_populates="predicciones")
    ofertas: List["Oferta"] = Relationship(back_populates="prediccion")


class Oferta(SQLModel, table=True):
    __tablename__ = "OFERTAS"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="USUARIOS.id", index=True)
    prediccion_id: Optional[int] = Field(default=None, foreign_key="PREDICCIONES.id")
    categoria_id: int = Field(foreign_key="CATEGORIAS_ALIMENTO.id")
    titulo: str
    descripcion: Optional[str] = Field(default=None, max_length=255)
    kg_disponibles: Decimal = Field(sa_column=Column(DECIMAL(10, 2)))
    ventana_inicio: datetime
    ventana_fin: datetime
    estado: EstadoOferta = EstadoOferta.ACTIVA

    usuario: Optional[Usuario] = Relationship(back_populates="ofertas")
    prediccion: Optional[Prediccion] = Relationship(back_populates="ofertas")
    categoria: Optional[CategoriaAlimento] = Relationship(back_populates="ofertas")
    reservas: List["Reserva"] = Relationship(back_populates="oferta")


class Reserva(SQLModel, table=True):
    __tablename__ = "RESERVAS"

    id: Optional[int] = Field(default=None, primary_key=True)
    oferta_id: int = Field(foreign_key="OFERTAS.id")
    usuario_id: int = Field(foreign_key="USUARIOS.id", index=True)
    kg_reservados: Decimal = Field(sa_column=Column(DECIMAL(10, 2)))
    estado: EstadoReserva = EstadoReserva.PENDIENTE
    creada_en: datetime = Field(default_factory=datetime.utcnow)

    oferta: Optional[Oferta] = Relationship(back_populates="reservas")
    usuario: Optional[Usuario] = Relationship(back_populates="reservas")


class Reclamo(SQLModel, table=True):
    __tablename__ = "RECLAMOS"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="USUARIOS.id", index=True)
    bascula_id: Optional[int] = Field(default=None, foreign_key="BASCULAS.id")
    tipo: TipoReclamo
    # Text (no TinyText) para permitir descripciones largas del problema
    descripcion: str = Field(sa_column=Column(Text))
    estado: EstadoReclamo = EstadoReclamo.ABIERTO
    creado_en: datetime = Field(default_factory=datetime.utcnow)
    resuelto_en: Optional[datetime] = None

    usuario: Optional[Usuario] = Relationship(back_populates="reclamos")
    bascula: Optional[Bascula] = Relationship(back_populates="reclamos")
