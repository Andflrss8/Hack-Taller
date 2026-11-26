# CLAUDE.md — Contexto del proyecto

> Archivo de contexto para Claude. Léelo completo antes de proponer código, esquemas o cambios.
> Idioma de trabajo: **español** (nombres de tablas y campos en español, `snake_case`).

## 1. ¿Qué es este proyecto?

Proyecto de **hackathon** desarrollado en equipo. Somos una "startup" que ofrece a locales de comida y mercados pequeños (misceláneas, fruterías, cafeterías, etc.) una o varias **básculas conectadas a una aplicación de escritorio**.

Con las básculas se pesan los alimentos; con esas lecturas se genera una **predicción (apoyada con IA) de cuánto alimento se va a desperdiciar**. A partir de la predicción, el vendedor crea **ofertas** de ese excedente para que otras personas u organizaciones puedan **reservarlo**, de modo que el alimento se aproveche en lugar de tirarse.

**Propósito social:** combatir la pobreza alimentaria y el desperdicio de alimentos, sobre todo en México.

### Plataforma objetivo

La interfaz de usuario es una **aplicación de escritorio**. La tecnología específica aún no está definida por el equipo. El backend expone una **API REST** (FastAPI) que la app de escritorio consume.

## 2. Flujo principal del negocio

1. El usuario (dueño del negocio) tiene una o varias **básculas** vinculadas a su cuenta.
2. La báscula (ESP32) envía automáticamente **lecturas de peso** vía `POST /basculas/lectura-esp32` con un JSON fijo.
3. A partir de una o varias lecturas se elabora una **predicción** (`PREDICCIONES`) de excedente/desperdicio. Una predicción usa varias lecturas (tabla intermedia `PREDICCION_LECTURAS`).
4. A partir de una predicción se pueden crear **una o varias ofertas** (`OFERTAS`).
5. Otros usuarios hacen **reservas** (`RESERVAS`) sobre una oferta indicando cuántos kg quieren.
6. Si una báscula falla, el usuario levanta un **reclamo** (`RECLAMOS`).

Más adelante, `PREDICCIONES.kg_reales` permitirá comparar lo estimado contra lo que realmente se desperdició, para evaluar y mejorar el modelo.

## 3. Stack

| Capa | Tecnología |
|---|---|
| Base de datos | **MySQL 8** (`mysql:8.4` en Docker) |
| ORM | **SQLModel** (sobre SQLAlchemy + Pydantic) |
| Driver MySQL | **PyMySQL** + `cryptography` (auth MySQL 8) |
| IA / Predicciones | **Google Gemini API** (`google-genai`, salida JSON estructurada) |
| Framework API | **FastAPI** |
| Runtime | **Python 3.12** (`python:3.12-slim` en Docker) |
| Servidor ASGI | **Uvicorn** (con `--reload` en desarrollo) |
| Contenedores | Docker + Docker Compose (servicios `db` y `app`) |
| App | Puerto **8000**, arranca con `uvicorn main:app --reload` |
| Frontend | App de **escritorio** — tecnología por definir |

### Estructura del proyecto

```
Hack-Taller/
├── app/
│   ├── __init__.py
│   ├── app.py               # script de prueba standalone de la API de Gemini
│   ├── database.py          # engine, create_db_and_tables(), get_session()
│   ├── models.py            # modelos SQLModel (tablas) + enums
│   ├── schemas.py           # schemas Pydantic para request/response (sin campos sensibles)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_service.py # cliente Gemini + prompt de seguridad + schemas IA
│   │   └── flujo_ia.py       # orquestación ESP32 -> Predicción -> Oferta + centros
│   └── routers/
│       ├── __init__.py
│       ├── bascula.py       # ESP32 endpoints (/lectura-esp32 y /lectura-esp32/procesar-ia) + CRUD
│       ├── categorias.py    # CRUD de categorías de alimento
│       ├── usuarios.py      # registro y consulta de usuarios
│       ├── lecturas.py      # lecturas manuales
│       ├── ofertas.py       # publicar, generar con IA y buscar centros cercanos
│       ├── reservas.py      # reservar excedente (con validación de kg)
│       ├── reclamos.py      # reportar fallas de báscula
│       └── predicciones.py  # predicciones (manual y con IA) + vincular lecturas
├── main.py                  # instancia FastAPI, lifespan, CORS, registro de routers
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .dockerignore
└── CLAUDE.md
```

### Docker

- Las credenciales se leen del archivo `.env` (no versionado). Usar `.env.example` como plantilla.
- El `DATABASE_URL` usa el formato SQLAlchemy: `mysql+pymysql://root:<pass>@db:3306/<db>`.
- Las tablas se crean automáticamente al arrancar vía `SQLModel.metadata.create_all()`.
- Hot-reload activo: los cambios en el código se reflejan sin reconstruir la imagen (volumen `.:/app`).
- Si se agregan dependencias al `requirements.txt`: `docker compose up --build`.

### Conexión local (sin Docker)

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
# Crear .env con DATABASE_URL apuntando a localhost
uvicorn main:app --reload --port 8000
```

### JSON fijo del ESP32

La báscula envía este JSON a `POST /basculas/lectura-esp32` — **no modificar su estructura**:

```json
{
  "codigo_dispositivo": "ESP32-BASCULA-01",
  "peso_g": 450.0,
  "categoria_id": 1,
  "tipo": "lectura",
  "es_simulada": true
}
```

El campo `tipo` siempre llega como `"lectura"` desde el hardware. El endpoint lo ignora y guarda la lectura con `tipo = SOBRANTE` por defecto (decisión del equipo).

## 4. Modelo de datos (versión vigente)

Decisión de diseño clave: **un usuario = un negocio (relación 1:1)**. No existe tabla `NEGOCIOS`; los datos del negocio viven dentro de `USUARIOS`. Tampoco existe tabla `ORGANIZACIONES`; quien recibe el alimento es un usuario con otro `rol` que hace `RESERVAS`.

Los modelos están definidos en [`app/models.py`](app/models.py).  
Los schemas de entrada/salida en [`app/schemas.py`](app/schemas.py).

### USUARIOS
| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nombre | str | |
| email | str | UK + índice |
| password_hash | str | **nunca devolver en la API** |
| telefono | str? | |
| rol | enum | `VENDEDOR`, `RECEPTOR` |
| nombre_negocio | str? | |
| tipo_negocio | enum? | `MISCELANEA`, `FRUTERIA`, `CAFETERIA`, `OTRO` |
| direccion | str? | |
| ciudad_region | str? | |
| estado | str? | |
| pais | str? | |
| latitud | Decimal(10,7)? | para emparejar ofertas cercanas |
| longitud | Decimal(10,7)? | |
| creado_en | datetime | default `utcnow` |

### BASCULAS
`id` PK · `usuario_id` FK+idx · `codigo_dispositivo` UK · `api_key_hash` (**nunca devolver**) · `alias` · `activa` bool · `ultima_conexion` datetime?

### CATEGORIAS_ALIMENTO
`id` PK · `nombre` UK · `es_perecedero` bool · `vida_util_dias` int?

### LECTURAS_PESO
`id` **BigInt** PK · `bascula_id` FK+idx · `categoria_id` FK? · `peso_g` Decimal(10,2) · `descripcion` str?(max 255) · `tipo` enum(`INVENTARIO`,`SOBRANTE`) · `fecha_hora` datetime+idx · `es_simulada` bool

### PREDICCIONES
`id` PK · `usuario_id` FK+idx · `categoria_id` FK · `fecha_objetivo` date · `kg_estimados` Decimal(10,2) · `kg_reales` Decimal(10,2)? · `confianza` Decimal(5,4)? · `modelo` str? · `creada_en` datetime

### PREDICCION_LECTURAS (tabla intermedia N:M)
`prediccion_id` PK/FK (int) · `lectura_id` PK/FK (**bigint**) — llave compuesta.

### OFERTAS
`id` PK · `usuario_id` FK+idx · `prediccion_id` FK? · `categoria_id` FK · `titulo` str · `descripcion` str?(max 255) · `kg_disponibles` Decimal(10,2) · `ventana_inicio` datetime · `ventana_fin` datetime · `estado` enum(`ACTIVA`,`AGOTADA`,`EXPIRADA`,`CANCELADA`)

### RESERVAS
`id` PK · `oferta_id` FK · `usuario_id` FK+idx · `kg_reservados` Decimal(10,2) · `estado` enum(`PENDIENTE`,`CONFIRMADA`,`RECOGIDA`,`CANCELADA`) · `creada_en` datetime

### RECLAMOS
`id` PK · `usuario_id` FK+idx · `bascula_id` FK? · `tipo` enum(`NO_CONECTA`,`PESO_INCORRECTO`,`OTRO`) · `descripcion` Text · `estado` enum(`ABIERTO`,`EN_PROCESO`,`RESUELTO`,`CERRADO`) · `creado_en` datetime · `resuelto_en` datetime?

## 5. Relaciones

- USUARIOS 1—N BASCULAS, PREDICCIONES, OFERTAS, RECLAMOS, RESERVAS
- BASCULAS 1—N LECTURAS_PESO y 0..N RECLAMOS
- CATEGORIAS_ALIMENTO 0..1—N LECTURAS_PESO, PREDICCIONES y OFERTAS
- PREDICCIONES N—M LECTURAS_PESO vía PREDICCION_LECTURAS
- PREDICCIONES 1—0..N OFERTAS
- OFERTAS 1—N RESERVAS

## 6. Convenciones para SQLModel + MySQL

- Campos de peso y kg → `DECIMAL(10, 2)` vía `sa_column=Column(DECIMAL(10, 2))`.
- `LECTURAS_PESO.id` y `PREDICCION_LECTURAS.lectura_id` → `BigInteger` vía `sa_column`.
- Enums → clases `str, Enum` de Python; SQLModel los mapea a `VARCHAR` en MySQL.
- `password_hash` y `api_key_hash`: **nunca incluirlos en schemas de respuesta de la API**.
- Usar schemas separados (`UsuarioPublic`, etc.) para controlar qué campos se exponen.
- Validaciones de negocio (ej: suma de `kg_reservados` ≤ `kg_disponibles`) van en el router, no en el modelo.

## 7. Decisiones tomadas

- `tipo` del JSON ESP32 (`"lectura"`) se ignora; las lecturas se guardan como `SOBRANTE` por defecto.
- Hash de passwords: SHA-256 (suficiente para hackathon; en producción usar bcrypt).

## 8. Decisiones abiertas

- Valores finales de `tipo_negocio` enum.
- Si `OFERTAS.categoria_id` se mantiene o se deduce de la predicción.
- Autenticación (JWT, sesiones, etc.).
- Permisos por `rol` (qué endpoints puede usar cada tipo de usuario).
- Tecnología del frontend de escritorio.

## 9. Cómo debe trabajar Claude en este repo

- Responder en español y de forma concisa.
- Respetar el modelo de la sección 4; si algo del código contradice el esquema, **avisar** en lugar de asumir.
- Antes de agregar tablas o campos, proponerlo y esperar confirmación del equipo.
- No inventar valores de enums ya definidos: usar los de este archivo y marcar como "propuesta" los nuevos.
- Es un hackathon: priorizar soluciones simples y funcionales sobre sobreingeniería, sin sacrificar la integridad de datos.
- Mantener este archivo actualizado cuando cambie el esquema.
- El consumidor de la API es una **app de escritorio**: diseñar respuestas JSON limpias, sin campos sensibles.
