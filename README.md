# Hack-Taller (Backend API)

Proyecto de hackathon desarrollado para combatir el desperdicio alimentario en comercios locales y comunidades de México.

El backend gestiona la base de datos (MySQL 8), el registro de pesajes provenientes de básculas basadas en **ESP32**, la predicción de excedentes y la publicación de ofertas para que organizaciones y receptores puedan reservarlas desde la **aplicación de escritorio**.

---

## 🛠️ Stack Tecnológico

- **Lenguaje:** Python 3.12
- **Framework:** FastAPI
- **ORM / Modelado:** SQLModel (SQLAlchemy + Pydantic)
- **Base de Datos:** MySQL 8.4
- **Contenedores:** Docker & Docker Compose

---

## 🚀 Guía de inicio rápido para el equipo

Sigue estos sencillos pasos para levantar el entorno de desarrollo con Docker:

### 1. Clonar el repositorio y entrar al proyecto
```bash
git clone <URL_DEL_REPOSITORIO>
cd Hack-Taller
```

### 2. Configurar las variables de entorno
Crea tu archivo local `.env` a partir de la plantilla:

- En **Windows (PowerShell)** o **Linux/macOS**:
  ```bash
  cp .env.example .env
  ```
- En **Windows (CMD)**:
  ```cmd
  copy .env.example .env
  ```

> ⚠️ **Nota:** No necesitas cambiar nada en `.env` para desarrollo local a menos que quieras personalizar tus contraseñas. Si las cambias, asegúrate de que la clave en `MYSQL_ROOT_PASSWORD` y en `DATABASE_URL` sean idénticas.

### 3. Levantar los contenedores con Docker
Ejecuta el siguiente comando en la raíz del proyecto:

```bash
docker compose up --build
```
*(Si prefieres que corra en segundo plano, añade la bandera `-d`: `docker compose up -d --build`).*

---

## 🌐 Enlaces y Servicios Disponibles

Una vez que los contenedores estén corriendo, puedes acceder a:

| Servicio | URL / Host | Descripción |
|---|---|---|
| **Documentación Interactiva (Swagger UI)** | [http://localhost:8000/docs](http://localhost:8000/docs) | **Recomendado para Frontend:** prueba y visualiza todos los endpoints |
| **Documentación Alternativa (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Documentación limpia y detallada de la API |
| **API Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Verificar si el servidor está respondiendo |
| **Base de Datos MySQL (Host Externo)** | `localhost:3307` | Para conectar clientes visuales (DBeaver, MySQL Workbench, etc.) |

---

## 📡 Endpoint clave para el ESP32

El hardware de la báscula enviará automáticamente los pesajes al endpoint:
- **Método:** `POST`
- **URL:** `http://localhost:8000/basculas/lectura-esp32`
- **Formato del JSON:**
  ```json
  {
    "codigo_dispositivo": "ESP32-BASCULA-01",
    "peso_g": 450.0,
    "categoria_id": 1,
    "tipo": "lectura",
    "es_simulada": true
  }
  ```
