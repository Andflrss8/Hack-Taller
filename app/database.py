import os
import time
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@db:3306/desperdicio")

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables(retries: int = 10, delay: int = 2) -> None:
    """Crea todas las tablas definidas en los modelos si no existen (con reintentos si MySQL aún está iniciando)."""
    for attempt in range(1, retries + 1):
        try:
            SQLModel.metadata.create_all(engine)
            return
        except Exception as e:
            if attempt == retries:
                raise
            print(f"[DB] Esperando a MySQL ({attempt}/{retries})... {e}")
            time.sleep(delay)


def get_session():
    """Dependencia de FastAPI para inyectar una sesión de base de datos."""
    with Session(engine) as session:
        yield session
