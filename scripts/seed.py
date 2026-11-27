"""
Seed idempotente para la demo del hackathon.

Correr dentro del contenedor de la app:
    docker compose exec app python scripts/seed.py

Crea (si no existen):
- Usuario vendedor demo y receptor demo
- 5 categorías de alimento
- La báscula ESP32-BASCULA-01

Se puede ejecutar las veces que quiera: no duplica registros.
"""

import hashlib
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, select

# Permite correrlo desde la raíz o desde scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from app.database import create_db_and_tables, engine  # noqa: E402
from app.models import (  # noqa: E402
    Bascula,
    CategoriaAlimento,
    LecturaPeso,
    Prediccion,
    PrediccionLectura,
    RolUsuario,
    TipoLectura,
    TipoNegocio,
    Usuario,
    utcnow,
)


def _hash(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


CATEGORIAS = [
    ("Frutas", True, 5),
    ("Panaderia", True, 2),
    ("Platillos preparados", True, 1),
    ("Lacteos", True, 7),
    ("Abarrotes", False, None),
]


def main() -> None:
    create_db_and_tables()
    api_key = os.getenv("BASCULA_API_KEY", "clave-de-ejemplo")

    with Session(engine) as session:
        vendedor = session.exec(
            select(Usuario).where(Usuario.email == "ana@demo.local")
        ).first()
        if not vendedor:
            vendedor = Usuario(
                nombre="Ana Perez",
                email="ana@demo.local",
                password_hash=_hash("demo123"),
                rol=RolUsuario.VENDEDOR,
                nombre_negocio="Fruteria Ana",
                tipo_negocio=TipoNegocio.FRUTERIA,
            )
            session.add(vendedor)
            session.commit()
            session.refresh(vendedor)
            print("[seed] Vendedor demo creado.")

        receptor = session.exec(
            select(Usuario).where(Usuario.email == "dif@demo.local")
        ).first()
        if not receptor:
            receptor = Usuario(
                nombre="DIF Torreon",
                email="dif@demo.local",
                password_hash=_hash("demo123"),
                rol=RolUsuario.RECEPTOR,
            )
            session.add(receptor)
            session.commit()
            session.refresh(receptor)
            print("[seed] Receptor demo creado.")

        for nombre, perecedero, dias in CATEGORIAS:
            if session.exec(
                select(CategoriaAlimento).where(CategoriaAlimento.nombre == nombre)
            ).first():
                continue
            session.add(
                CategoriaAlimento(
                    nombre=nombre, es_perecedero=perecedero, vida_util_dias=dias
                )
            )
            print(f"[seed] Categoría '{nombre}' creada.")
        session.commit()

        if not session.exec(
            select(Bascula).where(Bascula.codigo_dispositivo == "ESP32-BASCULA-01")
        ).first():
            session.add(
                Bascula(
                    usuario_id=vendedor.id,
                    codigo_dispositivo="ESP32-BASCULA-01",
                    api_key_hash=_hash(api_key),
                    alias="Mostrador",
                    activa=True,
                )
            )
            session.commit()
            print("[seed] Báscula ESP32-BASCULA-01 creada.")

        # Datos de ejemplo: un clon fresco ya muestra una lectura y una
        # predicción en el panel, sin tener que flashear el ESP32.
        bascula = session.exec(
            select(Bascula).where(Bascula.codigo_dispositivo == "ESP32-BASCULA-01")
        ).first()
        categoria = session.exec(
            select(CategoriaAlimento).where(CategoriaAlimento.nombre == "Frutas")
        ).first()
        if bascula and categoria:
            lectura = session.exec(
                select(LecturaPeso).where(
                    LecturaPeso.bascula_id == bascula.id,
                    LecturaPeso.es_simulada.is_(True),
                )
            ).first()
            if not lectura:
                lectura = LecturaPeso(
                    bascula_id=bascula.id,
                    categoria_id=categoria.id,
                    peso_g=Decimal("450.00"),
                    descripcion="Lectura de ejemplo del seed",
                    tipo=TipoLectura.SOBRANTE,
                    fecha_hora=utcnow(),
                    es_simulada=True,
                )
                session.add(lectura)
                session.commit()
                session.refresh(lectura)
                print("[seed] Lectura de ejemplo creada.")

            prediccion = session.exec(
                select(Prediccion).where(Prediccion.usuario_id == vendedor.id)
            ).first()
            if not prediccion:
                prediccion = Prediccion(
                    usuario_id=vendedor.id,
                    categoria_id=categoria.id,
                    fecha_objetivo=date.today() + timedelta(days=1),
                    kg_estimados=Decimal("0.45"),
                    confianza=Decimal("0.7000"),
                    modelo="seed-demo",
                    creada_en=utcnow(),
                )
                session.add(prediccion)
                session.commit()
                session.refresh(prediccion)
                session.add(
                    PrediccionLectura(
                        prediccion_id=prediccion.id, lectura_id=lectura.id
                    )
                )
                session.commit()
                print("[seed] Predicción de ejemplo creada y vinculada.")

        print("[seed] Listo. IDs: vendedor=%s, receptor=%s" % (vendedor.id, receptor.id))


if __name__ == "__main__":
    main()
