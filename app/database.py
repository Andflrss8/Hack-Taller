import os
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@db:3306/desperdicio")

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables() -> None:
    """Crea todas las tablas definidas en los modelos si no existen."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependencia de FastAPI para inyectar una sesión de base de datos."""
    with Session(engine) as session:
        yield session
