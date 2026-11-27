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
    RolUsuario,
    TipoNegocio,
    Usuario,
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

        print("[seed] Listo. IDs: vendedor=%s, receptor=%s" % (vendedor.id, receptor.id))


if __name__ == "__main__":
    main()
