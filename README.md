# Notificaciones

## 1. Notificaciones: overview arquitectónico

Microservicio de Notificaciones (Desarrollo II). API REST en FastAPI con capas estrictas
`app/api` → `app/domain` ← `app/infrastructure`, más la capa de seguridad (`app/security`:
validación Pydantic y funciones puras de API Key). El dominio define puertos (Protocols) y la
infraestructura los implementa con SQLAlchemy 2 sobre PostgreSQL 16; una transacción por
solicitud (commit al final, rollback ante error). Este arquetipo (Sprint 0) cubre el flujo
HU-NOT-01 (reportar stock bajo) con lo mínimo de HU-NOT-11 y HU-NOT-12 (API Key).

## 2. Prerrequisitos

- Docker 29
- Docker Compose v2 o superior (probado con v5.6)
- uv 0.13
- Python 3.12 (uv lo descarga si falta)

## 3. Quick start

```bash
git clone <URL_DEL_REPO> proyecto && cd proyecto
cp .env.example .env          # cambia las claves de ejemplo
docker compose up --build
```

En otra terminal, crea una llave (se muestra una sola vez) y úsala:

```bash
docker compose exec api python scripts/crear_api_key.py inventario

curl -i -X POST http://localhost:8000/notificaciones \
  -H "X-API-Key: <LLAVE>" -H "Content-Type: application/json" \
  -d '{"tipo":"STOCK_BAJO_INSUMO","productoId":"INS-1","nombre":"Hilo","stockActual":3,"stockMinimo":10}'
```

Swagger en http://localhost:8000/docs (botón Authorize con `X-API-Key`). `/docs`, `/openapi.json`
y `/health` no piden llave.

Nota: en este sprint `POST /notificaciones` solo acepta `STOCK_BAJO_INSUMO` y
`STOCK_BAJO_PRODUCTO`. `CONDICION_URGENTE` y `ACUMULACION_PEDIDOS` ya están sembrados en el
catálogo, pero son de HU-NOT-05/06 y responden 422 ("tipo fuera del catálogo").

El esquema completo (9 tablas) sigue el ER del DAS (`das/02_modelo_er.puml`).

## 4. Tests locales (sin Docker para la app)

```bash
uv sync
uv run pytest                    # unitarios + integración
uv run pytest tests/unit         # solo unitarios (sin BD ni Docker)
```

La integración usa testcontainers: levanta `postgres:16.15-alpine`, corre Alembic y prueba el
flujo. Requiere Docker en marcha; si no está disponible, esos tests se omiten.

## 5. Cobertura

```bash
uv run pytest --cov --cov-report=term-missing --cov-report=html   # global >= 80 %
uv run coverage report --include='app/domain/*,app/security/*' --fail-under=100
```

El reporte HTML queda en `htmlcov/index.html`.

## 6. Estructura

Anotada en [`docs/arquetipo/02_blueprint.md`](docs/arquetipo/02_blueprint.md).

```
app/main.py            bootstrap, routers y manejadores de error (422 con lista de campos)
app/config.py          DATABASE_URL y LOG_LEVEL (pydantic-settings)
app/api/               View: routers, health, deps.py (sesión → repos → servicios)
app/security/          schemas.py (Pydantic) y api_key.py (generar y hashear)
app/domain/            Logic: catálogo, puertos, errores, autenticación, servicio
app/infrastructure/    db.py, models.py, repositories.py
migrations/            Alembic; 0001 crea tablas, siembra el catálogo y el UNIQUE parcial
scripts/               crear_api_key.py
tests/unit | integration
```

## 7. Decisiones clave

Ver DAS y [`docs/arquetipo/01_validacion.md`](docs/arquetipo/01_validacion.md).

- Capas estrictas e inyección por `Depends`; el dominio no importa FastAPI ni SQLAlchemy (C7).
- Anti-duplicado con índice UNIQUE parcial `(tipo, clave) WHERE resuelta_en IS NULL`; las
  alertas vencidas se marcan `EXPIRACION` en la misma transacción antes de insertar.
- El mensaje de la notificación se calcula, no se guarda.
- API Key por rol con hash SHA-256, máximo 2 activas; la llave nunca se loguea.
- Cobertura: 100 % en `app/domain` + `app/security`, 80 % global (C6).
- `docker-compose.yml` usa PostgreSQL local en lugar de Neon: [Archetype Convention Addition],
  paridad dev/prod (12-factor X).
- `API_PORT` en `.env` es solo para compose (puerto publicado en el host).

## 8. Limitaciones y siguientes pasos

- Worker de entrega (HU-NOT-17) y Publisher AMQP (HU-NOT-03).
- Scheduler cada 5 min y `POST /notificaciones/ciclo` (HU-NOT-02); la resolución de alertas con
  REPUESTO/RESUELTA se acepta ya en forma mínima.
- Mailer Brevo (HU-NOT-04).
- Consultas HU-NOT-07 a 10.
- Destinatarios y callbacks (HU-NOT-13 a 16).
- CD a EC2 (semana del 2 nov).
- Prometheus/Grafana.
- TLS en el 443 (Caddy/Nginx o ALB).
- Las migraciones corren en el `CMD` del contenedor: válido con una sola réplica; con varias, mover
  `alembic upgrade head` a un paso de despliegue aparte.

## 9. Flujo de trabajo Git

- Ramas: `main` (estable), `develop` (integración) y una rama personal por HU/tarea.
- `main` y `develop` están protegidas con rulesets (`protect-main`, `protect-develop`): sin push
  directo, solo PR.
- Todo PR a `develop`/`main` requiere CI en verde (`.github/workflows/ci.yml`) y revisión de Qodo.
- Commits convencionales: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`.

### Secrets y variables de CI

| Nombre | Tipo | Uso |
|---|---|---|
| `SONAR_TOKEN` | Secret del repo | Token de SonarCloud |
| `SONAR_ENABLED` | Variable del repo (`true`) | Activa el job `sonar`; si falta, se omite |

Antes de activar Sonar, descomenta `sonar.projectKey` y `sonar.organization` en
`sonar-project.properties`. Los secrets del CD a EC2 se agregan la semana del 2 nov.
