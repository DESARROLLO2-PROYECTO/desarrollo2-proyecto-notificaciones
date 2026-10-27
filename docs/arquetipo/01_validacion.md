# Fase 1: Análisis y validación previa a la generación

Prompt: `Generador_Arquetipo_DAS_Promt.txt` (Desarrollo II, guía DevOps inicial).
Entradas:
- DAS: `Informe DAS.docx` v1.0, aprobado el 20/10/2026.
- Diagramas definitivos: `das/01_fisica.png`, `das/02_logica_paquetes.png` y `das/03_despliegue.png`.
- Backlog: `20261021_PB_Notificaciones`, con 17 HU.

Cuando la estructura de paquetes difiere, mandan los diagramas.

## A. Atributos de calidad (ISO/IEC 25010)

| Atributo | Prioridad | Cómo se verifica en el arquetipo |
|---|---|---|
| Fiabilidad: tolerancia a fallos y recuperabilidad | CRÍTICA | Estados `pendiente_publicacion` y `publicacion_fallida`; 3 intentos; ciclo cada 5 min con `FOR UPDATE SKIP LOCKED`; transacción por registro |
| Seguridad: confidencialidad, integridad, autenticidad, responsabilidad y resistencia | CRÍTICA | API Key con hash SHA-256 y 2 activas por rol; RBAC por emisor y destino; HMAC-SHA256 en el webhook; logs de rechazo sin la llave |
| Compatibilidad: interoperabilidad | ALTA | JSON, UTC ISO 8601, `X-API-Key`, códigos HTTP y catálogo de tipos; webhook con `X-Notification-Id`, `X-Timestamp` y `X-Signature` |
| Capacidad de interacción: protección contra errores | ALTA | Pydantic → 422 con la lista de campos; duplicado → 200 con el id existente |
| Eficiencia: comportamiento temporal y capacidad | ALTA | Paginación (máx. 100), índices, UNIQUE de alerta activa, límite de body |
| Mantenibilidad: modularidad, modificabilidad y capacidad de prueba | ALTA | Capas por inyección (`Depends`), catálogo de tipos en BD, pytest + SonarCloud |
| Flexibilidad: reemplazabilidad e instalabilidad | MEDIA | Adapter para Publisher y Mailer; imagen Docker |
| Flexibilidad: escalabilidad | BAJA | API, Worker y Scheduler separados lógicamente, pero en el mismo contenedor |
| Analizabilidad (Prometheus/Grafana) | BAJA | Ver ⚠️ C4 |

Conflictos entre atributos:
- **Escalabilidad vs. despliegue.** El DAS dice "API, worker y planificador separados", pero el despliegue los pone en un solo contenedor sobre una t2.micro. Se resuelve con un mismo código y entradas separables: se pueden partir después sin rediseñar.
- **Disponibilidad vs. entrega "al menos una vez".** La entrega se puede repetir. El PB lo asume: el destino deduplica con `X-Notification-Id`.

## B. Decisiones arquitectónicas

El DAS no trae ADRs formales. Estas son las decisiones implícitas:

| # | Contexto | Decisión | Justificación | Consecuencia |
|---|---|---|---|---|
| D1 | Separar responsabilidades y probar por partes | Capas View → Logic → Infrastructure, más Security y Utility | Modularidad y capacidad de prueba (ISO 25010) | Las dependencias solo bajan; el dominio no conoce FastAPI |
| D2 | El equipo trabaja en Python | Python 3.12 + FastAPI + Pydantic | Restricción del DAS; OpenAPI/Swagger gratis | Todo el stack es Python |
| D3 | Hace falta persistencia transaccional y concurrencia | PostgreSQL 16 (Neon) + SQLAlchemy 2 + Alembic | ACID, `SKIP LOCKED` e índices parciales; plan gratis | Migraciones versionadas; NullPool o pooler de Neon |
| D4 | Desacoplar el registro de la entrega | RabbitMQ (CloudAMQP), exchange direct `notificaciones` con cola `notif.<equipo>` | Productor-consumidor; el broker es interno | El webhook se entrega de forma asíncrona; el mensaje lleva solo id y tipo |
| D5 | Los equipos reciben sin hacer polling | Webhook HTTPS firmado con HMAC, timeout de 10 s y 3 intentos | Interoperabilidad e integridad | Validar la URL contra SSRF (https y IP pública) |
| D6 | Correo como canal alterno | Brevo por API HTTPS, detrás de un Adapter | Reemplazabilidad | En local, Mailpit por SMTP (C2) |
| D7 | Autenticar servicios, no personas | API Key por rol con hash SHA-256, rotación de 2 llaves y script de alta | Sin usuarios ni pantallas | La llave en claro se muestra una sola vez |
| D8 | Reintentos y expiración periódicos | Scheduler cada 5 min que llama a `ejecutar_ciclo` | Táctica Retry | Ver ⚠️ C1 |
| D9 | Calidad continua | GitHub Actions (ruff, pytest, cobertura, imagen) + SonarCloud con quality gate; CD por SSH a EC2 | Exigencia del curso (DevOps) | Hacen falta secretos del repo (C5) |

No hay decisiones contradictorias. D8 y D9 tienen huecos de detalle; van abajo.

## C. Patrones

- **Explícitos en el DAS y los diagramas:**
  - Multicapa
  - API REST / MVC (controlador)
  - Validator (Pydantic)
  - Inyección de dependencias
  - Repository / DAO
  - Adapter (Publisher, Mailer)
  - Productor-consumidor (Worker)
  - Retry (Scheduler)
  - Autenticador (API Key)
  - Webhook / callback
  - Contenerización
  - Health check
- **Implícitos:**
  - Unit of Work: la sesión de SQLAlchemy, una transacción por caso de uso.
  - Strategy: el catálogo de tipos decide emisor, destino, expiración, asunto y mensaje.
  - Idempotent Receiver: deduplicación por alerta activa y por `X-Notification-Id`.
  - Transactional Outbox simplificado: se guarda la notificación y luego se publica; si falla, la recoge el ciclo.
- **¿Se aplican bien?** Sí, salvo un ajuste. En el diagrama, Domain usa pika y httpx directamente. Para respetar el Adapter, el dominio define protocolos (`Publisher`, `Mailer` y `WebhookSender`) y sus implementaciones van en `app/infrastructure`. Así el dominio se prueba al 100 % con mocks.

## D. Diagramas (definitivos)

- **Física:**
  - EC2 t2.micro con Ubuntu 24.04 y Docker. Puertos: 443 (API), 22 (SSH) y 3000 (Grafana).
  - Neon en el 5432/TLS, CloudAMQP en el 5671/AMQPS y Brevo en el 443.
  - Los servidores de los equipos usan el 443 en los dos sentidos.
- **Lógica:**
  - Paquetes:
    - View Layer (`app/api`): API.
    - Logic Layer (`app/domain`): Domain, Worker y Scheduler.
    - Infrastructure Layer (`app/infrastructure`): Repository y Model.
    - Security Layer: Pydantic, API Key/HMAC.
    - Utility Layer: Swagger, aio-pika, httpx, SQLAlchemy y Alembic.
  - Dependencias:
    - API →«Inject» Domain.
    - Worker →«Inject» Domain.
    - Scheduler →«use» Domain.
    - Domain →«Inject» Repository.
    - Repository →«use» Model.
    - Model «Extend» SQLAlchemy.
  - El puerto es el 8000.
- **Despliegue:**
  - Un contenedor `notificaciones` con la API (Uvicorn), el worker, el cronjob y `crear_api_key.py`.
  - Un contenedor de monitoreo con Prometheus y Grafana.
  - GitHub Actions construye, prueba y hace la imagen. SonarCloud aplica el quality gate. El despliegue llega por SSH.
- **Ambigüedad:** la física expone el 443, pero la API escucha en el 8000. Nadie termina TLS (ver ⚠️ C3).

## E. Stack

| Tecnología | Versión a fijar | Notas |
|---|---|---|
| Python | 3.12 (imagen `python:3.12.x-slim-bookworm`, con el parche exacto al generar) | La exige el DAS |
| FastAPI / Uvicorn / Pydantic v2 | La estable al generar, fijada en `uv.lock` | Con pydantic-settings para la configuración |
| SQLAlchemy 2 + psycopg 3 + Alembic | 2.0.x / 3.2.x / 1.x | Estilo 2.0 (`Mapped`); `SKIP LOCKED` nativo en PG |
| PostgreSQL | 16 (Neon); en local `postgres:16.x-alpine` | |
| RabbitMQ | En local `rabbitmq:3.13.x-management-alpine`; aio-pika 9.x | CloudAMQP habla AMQP 0-9-1 |
| httpx | 0.28.x | Webhook y API de Brevo |
| pytest + pytest-cov + respx | Las estables | 100 % en las capas indicadas |
| ruff | La estable | Análisis estático local |
| uv | 0.x, fijado en el Dockerfile | Build reproducible con `uv.lock` |

Las versiones exactas se resuelven y se fijan al generar, porque la fecha de corte de mi conocimiento puede ir atrás de la última estable. No hay conflictos de compatibilidad conocidos.

## F. Validación cruzada

El estilo en capas es adecuado para un microservicio pequeño, con 5 personas y 4 sprints. No se ven antipatrones graves: hay una sola base de datos propia del servicio y la integración es solo por API y webhooks.

```
PRE-GENERATION VALIDATION REPORT
==================================
✅ Confirmed Decisions:
- Capas View (app/api) → Logic (app/domain) → Infrastructure (app/infrastructure) + Security + Utility, por inyección
- Python 3.12 + FastAPI + Pydantic; PostgreSQL 16 + SQLAlchemy 2 + Alembic
- RabbitMQ: exchange direct "notificaciones", cola notif.<destino>, mensaje = {id, tipo}
- Webhook firmado HMAC-SHA256 (X-Notification-Id, X-Timestamp, X-Signature), timeout 10 s, 3 intentos
- API Key por rol (inventario, fabricacion, notificaciones), hash SHA-256, máx. 2 activas, script de alta/baja
- Catálogo de tipos en BD (emisor, destino, expiración); estado calculado a partir de fechas e intentos
- Ciclo cada 5 min con FOR UPDATE SKIP LOCKED; tareas independientes (expirar, publicar, entregar, correo)
- Contenedor Docker; CI en GitHub Actions + SonarCloud

⚠️ Flagged Concerns:
- C1 Scheduler: el DAS dice "cronjob dentro del contenedor"; el PB (HU-NOT-02 c6) dice "un proceso programado
  externo llama POST /notificaciones/ciclo". Propuesta: tarea asyncio periódica dentro del contenedor que llama a
  ejecutar_ciclo(), y se conserva POST /notificaciones/ciclo (solo admin) para disparo manual y pruebas.
- C2 docker-compose local: el DAS usa servicios gestionados (Neon, CloudAMQP, Brevo). El compose levanta
  postgres, rabbitmq y mailpit como [Archetype Convention Addition] (paridad dev/prod, 12-factor X).
  El Mailer tiene dos adapters: Brevo (prod) y SMTP (local).
- C3 TLS: la vista física expone el 443 pero la API escucha en el 8000; el DAS no dice quién termina TLS.
  Propuesta: dejarlo fuera del arquetipo y documentarlo como siguiente paso (Caddy/Nginx o ALB).
- C4 Prometheus/Grafana: están en el DAS, pero R1-R7 no los piden y una t2.micro (1 GB) queda justa.
  Propuesta: exponer /metrics en la API (prometheus-fastapi-instrumentator) y dejar el contenedor de monitoreo
  en un compose aparte (docker-compose.monitoring.yml).
- C5 CD a EC2 y SonarCloud necesitan cuentas y secretos (SONAR_TOKEN, EC2_HOST, EC2_SSH_KEY). El workflow se genera
  y queda listo, pero no se puede probar sin ellos.
- C6 Cobertura 100 %: el prompt la pide en "dominio y aplicación". Aquí equivale a app/domain + app/security.
  app/api y app/infrastructure se prueban con integración, no se exigen al 100 %.
- C7 Adapter vs. diagrama: Domain «use» pika/httpx. Se implementa con protocolos en el dominio e
  implementaciones en infrastructure (misma intención, testeable).
- C8 Alcance: el prompt exige un flujo transaccional e2e; el plan es cubrir las 17 HU del PB, lo que adelanta
  los sprints 2-4. La evidencia de Scrum tendría que verse en commits por HU.

❌ Blocking Issues:
- Ninguno.

📋 Assumptions Made:
- Capas estrictas: api → domain → infrastructure; api nunca toca repositorios.
- Un solo proceso: API + worker + scheduler en el lifespan de FastAPI, con flags WORKER_ENABLED y SCHEDULER_ENABLED
  para poder separarlos.
- Tipos sembrados por migración: STOCK_BAJO_INSUMO (24 h), STOCK_BAJO_PRODUCTO (24 h), CONDICION_URGENTE (60 min)
  y ACUMULACION_PEDIDOS (60 min).
- Hora legible de los correos: America/Bogota (UTC-5).
- Flujo transaccional R2: HU-NOT-01, POST /notificaciones → domain → repository → PG → 201;
  GET /notificaciones/estado/{id} lo lee.
```
