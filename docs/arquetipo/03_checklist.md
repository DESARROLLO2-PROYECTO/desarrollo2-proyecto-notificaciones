# Fase 2, paso 2.3: Archetype Self-Validation Checklist

Verificado el 2026-10-26 en local con los mismos comandos que corre `ci.yml`:
- `ruff check` y `ruff format --check`: OK.
- `mypy app` (strict): 0 errores.
- `pytest --cov=app`: 46 tests, cobertura global de 98.38 %.
- `coverage report` sobre `app/domain` y `app/security`: 100 %.
- `docker compose up --build`: db y api en estado healthy; `POST` → 201.

También pasó una revisión independiente (reviewer), con sus hallazgos corregidos.

| Ítem | Estado | Evidencia |
|---|---|---|
| C01 Cada capa del DAS tiene su paquete | ✅ PASS | `app/api` (View), `app/domain` (Logic), `app/infrastructure` (Data Access), `app/security` (Security), `migrations/` (Utility: Alembic) |
| C02 Cada patrón de la Fase 1 está implementado y anotado | ⚠️ PARTIAL | Ver la explicación debajo de la tabla |
| C03 El flujo transaccional está conectado de punta a punta | ✅ PASS | `POST /notificaciones` → `NotificacionService.registrar` → repositorios → PostgreSQL → 201; `GET /notificaciones/estado/{id}` lo lee. Probado en `tests/integration/test_flujo.py` |
| C04 Cada método público de domain y application tiene test | ✅ PASS | `tests/unit/`, con 100 % de sentencias y ramas en domain y security |
| C05 Herramienta de cobertura configurada y comando en el README | ✅ PASS | `[tool.coverage]` con `fail_under = 80`; el 100 % de domain y security se exige en CI; README §5 |
| C06 `docker compose up --build` arranca limpio | ✅ PASS | db y api healthy, `/health` → `{"status":"UP"}` |
| C07 Sin secretos ni valores de entorno hardcodeados | ✅ PASS | Todo sale de `.env` o `pydantic-settings`; `grep` sin hallazgos; las llaves solo se guardan como hash SHA-256 |
| C08 `.env.example` documenta cada variable | ✅ PASS | Todas las variables llevan comentario y placeholder |
| C09 Dockerfile multi-stage y sin root | ✅ PASS | Etapa builder (uv) y etapa runtime `python:3.12.16-slim-bookworm`, con uid 10001; sin `latest` |
| C10 README con comandos exactos | ✅ PASS | §3 quick start, §4 tests, §5 cobertura |
| C11 Nada contradice al DAS | ✅ PASS | Las capas siguen el diagrama lógico definitivo; las adiciones están marcadas como `[Archetype Convention Addition]` |
| C12 Los ⚠️ de la Fase 1 están resueltos o documentados | ✅ PASS | C1 y C3-C5 están en README §8 y §9; C2 en compose; C6 en CI; C7 con protocolos en `domain/puertos.py`; C8 con alcance de Sprint 0 |

## Por qué C02 queda en PARTIAL

**Implementados en el flujo:**
- Multicapa
- MVC/Router
- Validator (Pydantic)
- Inyección de dependencias
- Repository/DAO
- Unit of Work
- Autenticador (API Key con SHA-256 y RBAC)
- Catálogo de tipos (Strategy)
- Receptor idempotente (alerta activa con UNIQUE parcial)
- Health check
- Contenerización

**Fuera del alcance de este sprint:**

| Patrón | HU | Sprint |
|---|---|---|
| Productor-consumidor (Worker) | HU-NOT-17 | 3 |
| Adapter Publisher | HU-NOT-03 | 2 |
| Adapter Mailer | HU-NOT-04 | 3 |
| Retry (Scheduler) | HU-NOT-02 | 1 |
| Webhook HMAC | HU-NOT-17 | 3 |

Esos patrones salen del backlog y entran en su sprint. Generarlos ahora sería código especulativo sin un criterio de aceptación que lo pruebe. El README §8 los deja como siguientes pasos.

## Known Limitations / Next Steps
Ver README §8:
- CD a EC2 (semana del 2 nov, con la guía del profe).
- SonarCloud: se activa con `SONAR_TOKEN` y la variable `SONAR_ENABLED`.
- TLS en el 443.
- Prometheus y Grafana.
- Migraciones en el CMD: válido mientras haya una sola réplica.
