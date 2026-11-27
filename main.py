"""
main.py — Punto de entrada de la API.

Al arrancar (lifespan), crea todas las tablas en MySQL si no existen.
Los routers están organizados por entidad del modelo de datos.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.routers import api_lecturas, bascula, categorias, usuarios, lecturas, ofertas, reservas, reclamos, predicciones

from pathlib import Path
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al iniciar el servidor: crear tablas automáticamente
    # Equivalente a correr las migraciones en modo hackathon
    create_db_and_tables()
    yield
    # (aquí iría código de cleanup al apagar, si fuera necesario)


app = FastAPI(
    title="Hack-Taller API",
    description="""
## API de reducción de desperdicio alimentario

### Flujo principal
1. Registrar **usuarios** (`POST /usuarios`) y **básculas** (`POST /basculas`)
2. La báscula ESP32 envía lecturas automáticas → `POST /basculas/lectura-esp32`
3. Las lecturas generan **predicciones** de excedente → `POST /predicciones`
4. Las predicciones originan **ofertas** → `POST /ofertas`
5. Los receptores hacen **reservas** → `POST /reservas`

### Documentación interactiva
Disponible en `/docs` (Swagger UI) y `/redoc`.
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Permite que cualquier frontend de escritorio (Electron, Tauri, webview, etc.)
# consuma la API en desarrollo sin bloqueos de origen cruzado.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Registro de routers ──────────────────────────────────────────────────────
# Cada router agrega su prefijo automáticamente (/usuarios, /basculas, etc.)

app.include_router(api_lecturas.router)
app.include_router(usuarios.router)
app.include_router(categorias.router)
app.include_router(bascula.router)
app.include_router(lecturas.router)
app.include_router(predicciones.router)
app.include_router(ofertas.router)
app.include_router(reservas.router)
app.include_router(reclamos.router)

STATIC_DIR = Path(__file__).resolve().parent / "app" / "static"
app.mount("/panel", StaticFiles(directory=STATIC_DIR, html=True), name="panel")


# ─── Rutas base ───────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
def root():
    return {
        "status": "ok",
        "mensaje": "Hack-Taller API corriendo",
        "docs": "/docs",
    }


@app.get("/health", tags=["Root"])
def health():
    """Endpoint de salud — útil para saber si el servidor está vivo."""
    return {"status": "healthy"}
