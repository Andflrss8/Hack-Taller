# CLAUDE.md — Contexto del proyecto

> Archivo de contexto para Claude. Léelo completo antes de proponer código, esquemas o cambios.
> Idioma de trabajo: **español** (nombres de tablas y campos en español, `snake_case`).

## 1. ¿Qué es este proyecto?

Proyecto de **hackathon** desarrollado en equipo. Somos una "startup" que ofrece a locales de comida y mercados pequeños (misceláneas, fruterías, cafeterías, etc.) una o varias **básculas conectadas a una aplicación**.

Con las básculas se pesan los alimentos; con esas lecturas se genera una **predicción (apoyada con IA) de cuánto alimento se va a desperdiciar**. A partir de la predicción, el vendedor crea **ofertas** de ese excedente para que otras personas u organizaciones puedan **reservarlo**, de modo que el alimento se aproveche en lugar de tirarse.

**Propósito social:** combatir la pobreza alimentaria y el desperdicio de alimentos, sobre todo en México.

## 2. Flujo principal del negocio

1. El usuario (dueño del negocio) tiene una o varias **básculas** vinculadas a su cuenta.
2. Hace una o varias **lecturas de peso** (`LECTURAS_PESO`), opcionalmente con una descripción corta (`tinytext`) de lo que pesó y una categoría de alimento.
3. A partir de una o varias lecturas se elabora una **predicción** (`PREDICCIONES`) de excedente/desperdicio. Una predicción usa varias lecturas (tabla intermedia `PREDICCION_LECTURAS`).
4. A partir de una predicción se pueden crear **una o varias ofertas** (`OFERTAS`).
5. Otros usuarios hacen **reservas** (`RESERVAS`) sobre una oferta indicando cuántos kg quieren.
6. Si una báscula falla, el usuario levanta un **reclamo** (`RECLAMOS`).

Más adelante, `PREDICCIONES.kg_reales` permitirá comparar lo estimado contra lo que realmente se desperdició, para evaluar y mejorar el modelo.

## 3. Stack

| Capa | Tecnología |
|---|---|
| Base de datos | **MySQL 8** (decisión del equipo) |
| ORM | **Prisma** |
| Runtime | Node.js 22 (`node:22-slim` en Docker) |
| Contenedores | Docker + Docker Compose (servicios `db` y `app`) |
| App | Puerto 3000, arranca con `npm run dev` |

### Docker (estado actual y pendiente)

- `docker-compose.yml`, `Dockerfile` y `README.md` están en la raíz del repo.
- El `Dockerfile` instala `openssl` (necesario para Prisma en `slim`), copia `package*.json` y `prisma/` antes del resto para aprovechar caché, corre `npx prisma generate` y expone el 3000.
- ⚠️ **El `docker-compose.yml` actual levanta PostgreSQL (`postgres:16-alpine`)**, pero el proyecto está definido en **MySQL**. Hay que alinearlo: imagen `mysql:8.4`, puerto 3306, `DATABASE_URL="mysql://root:<pass>@db:3306/<db>"` y `provider = "mysql"` en `schema.prisma`.
- En desarrollo conviene usar `root` en MySQL porque `prisma migrate dev` necesita crear una base de datos sombra.
- Las credenciales no deben quedar fijas en el compose si el repo es público: usar `.env` y `${VARIABLE}`.
- Falta un `.dockerignore` (`node_modules`, `.git`, `.env`).
- Si se agregan dependencias: `docker compose up --build -V` (por el volumen anónimo de `node_modules`).

## 4. Modelo de datos (versión vigente)

Decisión de diseño clave: **un usuario = un negocio (relación 1:1)**. No existe tabla `NEGOCIOS`; los datos del negocio viven dentro de `USUARIOS`. Tampoco existe tabla `ORGANIZACIONES`; quien recibe el alimento es un usuario con otro `rol` que hace `RESERVAS`.

### USUARIOS
| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nombre | string | |
| email | string | UK |
| password_hash | string | nunca guardar contraseña en claro |
| telefono | string | |
| rol | enum | distingue vendedor / quien reserva (valores por definir; propuesta: `VENDEDOR`, `RECEPTOR`) |
| nombre_negocio | string | |
| tipo_negocio | enum | miscelánea, frutería, cafetería, etc. (valores por definir) |
| direccion | string | |
| ciudad_region | string | |
| estado | string | |
| pais | string | |
| latitud | decimal | para emparejar ofertas cercanas |
| longitud | decimal | |
| creado_en | datetime | |

### BASCULAS
`id` PK · `usuario_id` FK · `codigo_dispositivo` UK · `api_key_hash` (autenticación del dispositivo, guardar solo el hash) · `alias` · `activa` boolean · `ultima_conexion` datetime

### CATEGORIAS_ALIMENTO
`id` PK · `nombre` UK · `es_perecedero` boolean · `vida_util_dias` int

### LECTURAS_PESO
`id` **bigint** PK (tabla de mayor crecimiento) · `bascula_id` FK · `categoria_id` FK (opcional) · `peso_g` decimal · `descripcion` **tinytext** (opcional, lo escribe el usuario) · `tipo` enum (propuesta: `INVENTARIO`, `SOBRANTE`) · `fecha_hora` datetime · `es_simulada` boolean

### PREDICCIONES
`id` PK · `usuario_id` FK · `categoria_id` FK · `fecha_objetivo` date · `kg_estimados` decimal · `kg_reales` decimal (opcional, se llena después para evaluar el modelo) · `confianza` decimal · `modelo` string · `creada_en` datetime

### PREDICCION_LECTURAS (tabla intermedia N:M)
`prediccion_id` PK/FK · `lectura_id` (bigint) PK/FK — llave compuesta.

### OFERTAS
`id` PK · `usuario_id` FK · `prediccion_id` FK (opcional: se puede ofertar sin predicción) · `categoria_id` FK · `titulo` · `descripcion` tinytext · `kg_disponibles` decimal · `ventana_inicio` datetime · `ventana_fin` datetime · `estado` enum (propuesta: `ACTIVA`, `AGOTADA`, `EXPIRADA`, `CANCELADA`)

### RESERVAS
`id` PK · `oferta_id` FK · `usuario_id` FK · `kg_reservados` decimal · `estado` enum (propuesta: `PENDIENTE`, `CONFIRMADA`, `RECOGIDA`, `CANCELADA`) · `creada_en` datetime

### RECLAMOS
Reportes de **falla de báscula** (no son reclamos sobre ofertas).
`id` PK · `usuario_id` FK · `bascula_id` FK (opcional) · `tipo` enum (propuesta: `NO_CONECTA`, `PESO_INCORRECTO`, `OTRO`) · `descripcion` text · `estado` enum · `creado_en` · `resuelto_en`

## 5. Relaciones

- USUARIOS 1—N BASCULAS (`tiene`), PREDICCIONES (`genera`), OFERTAS (`publica`), RECLAMOS (`levanta`), RESERVAS (`reserva`)
- BASCULAS 1—N LECTURAS_PESO (`registra`) y 0..N RECLAMOS (`sobre`)
- CATEGORIAS_ALIMENTO 0..1—N LECTURAS_PESO, PREDICCIONES y OFERTAS (`clasifica` / `categoriza`)
- PREDICCIONES N—M LECTURAS_PESO vía PREDICCION_LECTURAS (`usa` / `alimenta`)
- PREDICCIONES 1—0..N OFERTAS (`origina`): una predicción puede generar varias ofertas
- OFERTAS 1—N RESERVAS (`recibe`)

## 6. Convenciones para Prisma + MySQL

- `provider = "mysql"` en `datasource db`.
- Campos de peso y kg → **`Decimal`** (no `Float`), para evitar errores de redondeo. Ej.: `@db.Decimal(10, 2)`.
- `LECTURAS_PESO.id` → `BigInt @id @default(autoincrement())`. Su FK en `PREDICCION_LECTURAS` también es `BigInt`.
- `descripcion` de lecturas y ofertas → `String? @db.TinyText`; `RECLAMOS.descripcion` → `@db.Text`.
- `estado`, `tipo`, `rol`, `tipo_negocio` → `enum` de Prisma (MySQL los soporta).
- `PREDICCION_LECTURAS` → `@@id([prediccion_id, lectura_id])`.
- Nombres de modelos y campos en español `snake_case`; si se prefiere PascalCase en el cliente, usar `@@map` / `@map` para mantener los nombres de tabla.
- Agregar `@@index` en FKs de alto uso (`bascula_id`, `usuario_id`, `fecha_hora`).
- Decidir y documentar `onDelete` en cada relación (por defecto `Restrict`; en `PREDICCION_LECTURAS` tiene sentido `Cascade`).
- Hashes (`password_hash`, `api_key_hash`): nunca devolverlos en respuestas de la API.

## 7. Decisiones abiertas

- Valores exactos de los enums (`rol`, `tipo_negocio`, estados, tipos).
- Si `OFERTAS.categoria_id` se mantiene o se deduce de la predicción.
- Cómo se valida que la suma de `RESERVAS.kg_reservados` no exceda `OFERTAS.kg_disponibles` (lógica de aplicación o transacción).
- Permisos por `rol` (qué puede hacer cada tipo de usuario).
- Alinear Docker Compose con MySQL (ver sección 3).

## 8. Cómo debe trabajar Claude en este repo

- Responder en español y de forma concisa.
- Respetar el modelo de la sección 4; si algo del código contradice el diagrama, **avisar** en lugar de asumir.
- Antes de agregar tablas o campos, proponerlo y esperar confirmación del equipo.
- No inventar valores de enums ya definidos: usar los de este archivo y marcar como "propuesta" los nuevos.
- Es un hackathon: priorizar soluciones simples y funcionales sobre sobreingeniería, sin sacrificar la integridad de datos.
- Mantener este archivo actualizado cuando cambie el esquema.
