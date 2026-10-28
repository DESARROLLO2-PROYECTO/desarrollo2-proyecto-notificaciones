# Fase 2, paso 2.1: Project Structure Blueprint

Alcance: Sprint 0, la línea base que pide la guía DevOps. Flujo transaccional: HU-NOT-01, con la parte de
HU-NOT-11 y HU-NOT-12 que hace falta para autenticarlo. Las capas siguen el diagrama lógico definitivo
(`das/02_logica_paquetes.png`).

```
proyecto/
├── app/
│   ├── main.py                        Bootstrap: crea FastAPI, registra routers, Swagger en /docs           [FastAPI]
│   ├── config.py                      Configuración externa (12-factor), todo por variables de entorno      [pydantic-settings]
│   │
│   ├── api/                           ── VIEW LAYER (app/api) ──
│   │   ├── deps.py                    Inyección de dependencias: sesión → repos → servicios; lee X-API-Key  [FastAPI Depends]
│   │   │                              y delega en domain/autenticacion. Es la raíz de composición:
│   │   │                              único punto de api que instancia repos; los routers solo usan
│   │   │                              servicios de domain y los DTO de security/schemas
│   │   ├── notificaciones.py          Router/Controlador REST (MVC): POST /notificaciones,                  [FastAPI APIRouter]
│   │   │                              GET /notificaciones/estado/{id}
│   │   └── health.py                  Health check: GET /health (proceso vivo; la BD la cubre compose)      [FastAPI]
│   │
│   ├── security/                      ── SECURITY LAYER (validaciones) ──
│   │   ├── schemas.py                 Validator / DTO: cuerpo por tipo (STOCK_BAJO_*), respuestas,          [Pydantic v2]
│   │   │                              422 con la lista de campos
│   │   └── api_key.py                 Autenticador: hash SHA-256, generar llave, verificar rol emisor       [hashlib, secrets]
│   │
│   ├── domain/                        ── LOGIC LAYER (app/domain) ──
│   │   ├── catalogo.py                Catálogo de tipos (Strategy): emisor, destino, expiración, mensaje    [Python]
│   │   ├── puertos.py                 Puertos del Repository (Protocols): el dominio no conoce SQLAlchemy   [typing.Protocol]
│   │   ├── errores.py                 Excepciones de dominio → 401/403/404/500                              [Python]
│   │   ├── autenticacion.py           Autenticador: hash de la llave (security.api_key) → ApiKeyRepository  [Python]
│   │   │                              → rol; 401 y log del motivo (HU-NOT-12) — Domain «use» API Key
│   │   └── notificacion_service.py    Application Service: registrar() con anti-duplicado (alerta activa),  [Python]
│   │                                  resultado REGISTRADA / ALERTA_YA_ACTIVA; obtener(id) con RBAC
│   │                                  por destino; log de resultado
│   │                                  (Worker y Scheduler llegan en los sprints de HU-NOT-03, 17 y 02)
│   │
│   └── infrastructure/                ── INFRASTRUCTURE LAYER (app/infrastructure) ──
│       ├── db.py                      Engine y sesión; Unit of Work = una transacción por solicitud         [SQLAlchemy 2, psycopg 3]
│       ├── models.py                  Model (extiende DeclarativeBase): ApiKey, TipoNotificacion,           [SQLAlchemy 2]
│       │                              Equipo, Notificacion, Alerta (+ tablas de HU futuras)
│       └── repositories.py            Repository/DAO: implementa los puertos; IntegrityError del UNIQUE     [SQLAlchemy 2]
│                                      → duplicado (concurrencia, HU-NOT-01 c6)
│
├── migrations/                        ── UTILITY LAYER: migraciones ──                                      [Alembic]
│   └── versions/0001_inicial.py       Tablas, catálogo sembrado (4 tipos, 24 h / 60 min),
│                                      UNIQUE parcial (tipo, clave) WHERE resuelta_en IS NULL
├── scripts/crear_api_key.py           HU-NOT-11 (mínimo): alta de llave por rol, se muestra una vez         [Python]
│
├── tests/
│   ├── unit/                          AAA, con mocks de los puertos: domain + security al 100 %             [pytest, pytest-cov]
│   └── integration/test_flujo.py      POST → Postgres → GET de punta a punta, con BD real                   [pytest, httpx TestClient]
│
├── Dockerfile                         Multi-stage (builder con uv → runtime slim), usuario no root,         [Docker]
│                                      base fijada (sin latest)
├── .dockerignore                      Excluye .git, .env, tests, __pycache__, .venv                         [Archetype Convention Addition]
├── docker-compose.yml                 db (postgres:16.x-alpine, healthcheck, volumen) + api                 [Docker Compose v2]
│                                      (depends_on healthy, healthcheck); red notif_net; .env;
│                                      solo se expone el 8000.
│                                      Postgres local en lugar de Neon: [Archetype Convention Addition], paridad dev/prod
├── .env.example                       Todas las variables comentadas, valores de ejemplo                    [R6]
├── .gitignore                         Guía del profe + coverage/, build/, dist/                             [R6]
├── pyproject.toml / uv.lock           Dependencias fijadas; config de ruff, mypy, pytest y coverage         [uv]
├── alembic.ini
├── .github/workflows/ci.yml           En cada PR: ruff → mypy → pytest (global ≥ 80 %,                      [GitHub Actions]
│                                      domain+security = 100 %) → docker build
└── README.md                          Las 8 secciones de R7
```

Fuera de este sprint, documentado en el README como siguientes pasos con su HU:
- Worker de entrega (HU-NOT-17).
- Publisher AMQP (HU-NOT-03).
- Scheduler y `/notificaciones/ciclo` (HU-NOT-02).
- Mailer Brevo (HU-NOT-04).
- Resto de consultas (HU-NOT-07 a 10).
- Destinatarios y callbacks (HU-NOT-13 a 16).
- CD a EC2 (semana del 2 nov).
- Prometheus/Grafana.

## Verificación contra el diagrama lógico definitivo
| Dependencia del diagrama | Dónde queda |
|---|---|
| API «Inject» Domain | `api/deps.py` construye los servicios de `domain/` |
| API «use» Pydantic / Swagger | `security/schemas.py` en los routers; `/docs` de FastAPI |
| Domain «use» API Key/HMAC | `domain/autenticacion.py` → `security/api_key.py` |
| Domain «Inject» Repository | servicios reciben puertos (`domain/puertos.py`) implementados en `infrastructure/repositories.py` |
| Repository «use» Model; Model «Extend» SQLAlchemy, «use» Alembic | `infrastructure/models.py` (DeclarativeBase) + `migrations/` |
| Worker / Scheduler «Inject/use» Domain; Domain «use» aio-pika / httpx | ⚠️ diferido a HU-NOT-03/17/02 (sprints 2-3) |

Verificado por el orquestador el 2026-10-26: dos ajustes (autenticación vía Domain y /health sin acceso directo a la BD).
