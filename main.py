from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al arrancar: crear tablas si no existen
    create_db_and_tables()
    yield


app = FastAPI(
    title="Hack-Taller API",
    description="API para la plataforma de reducción de desperdicio alimentario.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"status": "ok", "mensaje": "Hack-Taller API corriendo"}


@app.get("/health")
def health():
    return {"status": "healthy"}
