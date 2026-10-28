"""Flujo de punta a punta con Postgres real (testcontainers). Sin Docker, se omite."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from testcontainers.community.postgres import PostgresContainer

# Misma versión que docker-compose.yml y CI.
IMAGEN_PG = "postgres:16.15-alpine"


@pytest.fixture(scope="module", autouse=True)
def _postgres():
    try:
        contenedor = PostgresContainer(IMAGEN_PG, driver="psycopg")
        contenedor.start()
    except Exception as e:  # Docker no disponible
        pytest.skip(f"Docker no disponible: {e}")
    os.environ["DATABASE_URL"] = contenedor.get_connection_url()
    yield
    contenedor.stop()


@pytest.fixture(scope="module")
def client(_postgres):
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient

    from app.main import create_app

    command.upgrade(Config("alembic.ini"), "head")
    with TestClient(create_app()) as c:
        yield c


def _llave(rol: str) -> dict[str, str]:
    from app.domain.puertos import ApiKey
    from app.infrastructure.db import transaccion
    from app.infrastructure.repositories import ApiKeyRepo
    from app.security.api_key import generar_llave, hashear

    llave = generar_llave()
    with transaccion() as s:
        ApiKeyRepo(s).crear(ApiKey(rol, hashear(llave), llave[:8], datetime.now(UTC)))
    return {"X-API-Key": llave}


@pytest.fixture(scope="module")
def inventario(client):
    return _llave("inventario")


@pytest.fixture(scope="module")
def fabricacion(client):
    return _llave("fabricacion")


def _cuerpo(**cambios):
    return {
        "tipo": "STOCK_BAJO_INSUMO",
        "productoId": f"P-{uuid4().hex[:12]}",
        "nombre": "Hilo",
        "stockActual": 3,
        "stockMinimo": 10,
    } | cambios


def test_flujo_completo(client, inventario, fabricacion):
    # Arrange
    cuerpo = _cuerpo()

    # Act / Assert: registro
    r = client.post("/notificaciones", json=cuerpo, headers=inventario)
    assert r.status_code == 201
    assert r.json()["mensaje"] == "Notificación registrada correctamente"
    id_ = r.json()["id"]

    # repetir: 200 con el mismo id
    r = client.post("/notificaciones", json=cuerpo, headers=inventario)
    assert r.status_code == 200
    assert r.json() == {
        "id": id_,
        "mensaje": "Ya existe una alerta activa para este artículo",
        "duplicada": True,
    }

    # lectura con el rol destino
    r = client.get(f"/notificaciones/estado/{id_}", headers=inventario)
    assert r.status_code == 200
    assert r.json()["mensaje"] == f"Stock bajo de Hilo ({cuerpo['productoId']}): 3 de mínimo 10"
    assert r.json()["destino"] == "inventario"

    # otro rol: 404
    r = client.get(f"/notificaciones/estado/{id_}", headers=fabricacion)
    assert r.status_code == 404
    assert r.json() == {"mensaje": "Notificación no encontrada"}


def test_sin_llave_es_401(client):
    r = client.post("/notificaciones", json=_cuerpo())
    assert r.status_code == 401
    assert r.json() == {"mensaje": "Acceso denegado"}


def test_emisor_equivocado_es_403(client, fabricacion):
    r = client.post("/notificaciones", json=_cuerpo(), headers=fabricacion)
    assert r.status_code == 403
    assert r.json() == {"mensaje": "Acceso denegado"}


def test_cuerpo_invalido_es_422_con_lista_de_campos(client, inventario):
    r = client.post("/notificaciones", json=_cuerpo(stockActual=-1, nombre=""), headers=inventario)
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["mensaje"] == "Los datos enviados no cumplen las reglas establecidas"
    assert {e["campo"] for e in cuerpo["errores"]} == {"stockActual", "nombre"}


def test_tipo_inactivo_es_422_y_no_registra(client, inventario):
    # Arrange
    cuerpo = _cuerpo()
    _sql("UPDATE tipos_notificacion SET activo = false WHERE codigo = :c", c=cuerpo["tipo"])
    try:
        # Act
        r = client.post("/notificaciones", json=cuerpo, headers=inventario)
    finally:
        _sql("UPDATE tipos_notificacion SET activo = true WHERE codigo = :c", c=cuerpo["tipo"])

    # Assert
    assert r.status_code == 422
    assert r.json()["mensaje"] == "Los datos enviados no cumplen las reglas establecidas"
    assert r.json()["errores"][0]["campo"] == "tipo"
    assert _sql("SELECT 1 FROM alertas WHERE clave = :k", k=cuerpo["productoId"]) == []


def test_tipo_inactivo_no_cierra_la_alerta_activa(client, inventario):
    # Arrange
    cuerpo = _cuerpo()
    assert client.post("/notificaciones", json=cuerpo, headers=inventario).status_code == 201
    _sql("UPDATE tipos_notificacion SET activo = false WHERE codigo = :c", c=cuerpo["tipo"])
    try:
        # Act
        r = client.post("/notificaciones", json=cuerpo | {"evento": "RESUELTA"}, headers=inventario)
    finally:
        _sql("UPDATE tipos_notificacion SET activo = true WHERE codigo = :c", c=cuerpo["tipo"])

    # Assert
    assert r.status_code == 422
    abiertas = "SELECT 1 FROM alertas WHERE clave = :k AND cerrada_at IS NULL"
    assert len(_sql(abiertas, k=cuerpo["productoId"])) == 1


def test_id_que_no_es_uuid_es_422(client, inventario):
    r = client.get("/notificaciones/estado/abc", headers=inventario)
    assert r.status_code == 422
    assert r.json()["mensaje"] == "Solicitud inválida: verifique los parámetros enviados"


def test_health_y_docs_no_piden_llave(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "UP"}
    assert client.get("/openapi.json").status_code == 200


def _sql(sentencia: str, **params):
    from sqlalchemy import text

    from app.infrastructure.db import get_engine

    with get_engine().begin() as c:
        r = c.execute(text(sentencia), params)
        return r.all() if r.returns_rows else []


def test_dos_detectada_en_paralelo_registran_una_sola(client, inventario):
    # Arrange
    cuerpo = _cuerpo()

    # Act
    with ThreadPoolExecutor(8) as ex:
        rs = list(
            ex.map(
                lambda _: client.post("/notificaciones", json=cuerpo, headers=inventario), range(8)
            )
        )

    # Assert
    assert sorted(r.status_code for r in rs) == [200] * 7 + [201]
    assert len({r.json()["id"] for r in rs}) == 1
    n = _sql(
        "SELECT count(*) FROM notificaciones WHERE payload->>'productoId' = :p",
        p=cuerpo["productoId"],
    )
    assert n[0][0] == 1


def test_alerta_vencida_permite_una_nueva_notificacion(client, inventario):
    # Arrange
    cuerpo = _cuerpo()
    primera = client.post("/notificaciones", json=cuerpo, headers=inventario).json()["id"]
    _sql(
        "UPDATE alertas SET expira_at = now() - interval '1 hour' WHERE clave = :c",
        c=cuerpo["productoId"],
    )

    # Act
    r = client.post("/notificaciones", json=cuerpo, headers=inventario)

    # Assert
    assert r.status_code == 201
    assert r.json()["id"] != primera
    motivos = _sql(
        "SELECT motivo_resolucion FROM alertas WHERE clave = :c AND cerrada_at IS NOT NULL",
        c=cuerpo["productoId"],
    )
    assert [m[0] for m in motivos] == ["EXPIRACION"]


def test_repuesto_cierra_la_alerta_y_luego_se_puede_registrar(client, inventario):
    # Arrange
    cuerpo = _cuerpo()
    client.post("/notificaciones", json=cuerpo, headers=inventario)

    # Act
    cierre = client.post(
        "/notificaciones", json=cuerpo | {"evento": "REPUESTO"}, headers=inventario
    )
    nueva = client.post("/notificaciones", json=cuerpo, headers=inventario)

    # Assert
    assert cierre.status_code == 200
    assert nueva.status_code == 201


def test_falla_al_crear_la_alerta_no_deja_nada_parcial(client, inventario, monkeypatch):
    # Arrange
    cuerpo = _cuerpo()

    def falla(**_):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr("app.infrastructure.models.Alerta", falla)

    # Act
    r = client.post("/notificaciones", json=cuerpo, headers=inventario)

    # Assert
    assert r.status_code == 500
    assert r.json() == {"mensaje": "No fue posible registrar la notificación, intente de nuevo"}
    p = cuerpo["productoId"]
    assert (
        _sql("SELECT count(*) FROM notificaciones WHERE payload->>'productoId' = :p", p=p)[0][0]
        == 0
    )
    assert _sql("SELECT count(*) FROM alertas WHERE clave = :p", p=p)[0][0] == 0


def test_crear_llave_valida_rol_y_limite(client):
    # Arrange
    from app.domain.autenticacion import ServicioAutenticacion
    from app.domain.errores import LimiteDeLlaves, RolInvalido
    from app.infrastructure.db import transaccion
    from app.infrastructure.repositories import ApiKeyRepo

    with transaccion() as s:
        servicio = ServicioAutenticacion(ApiKeyRepo(s))

        # Act / Assert
        with pytest.raises(RolInvalido, match="Rol no válido"):
            servicio.crear_llave("admin")
        primera, _ = servicio.crear_llave("notificaciones")
        segunda, _ = servicio.crear_llave("notificaciones")
        assert isinstance(primera, int)
        assert segunda > primera
        with pytest.raises(LimiteDeLlaves, match="Ya existen dos llaves activas para este rol"):
            servicio.crear_llave("notificaciones")


def test_equipo_inexistente_falla_y_no_se_toma_por_duplicada(client):
    # Arrange
    from sqlalchemy.exc import NoResultFound

    from app.infrastructure.db import transaccion
    from app.infrastructure.repositories import _equipo_id

    # Act / Assert
    with transaccion() as s, pytest.raises(NoResultFound):
        _equipo_id(s, "no_existe")


def test_estado_de_id_inexistente_es_404(client, inventario):
    r = client.get(f"/notificaciones/estado/{uuid4()}", headers=inventario)
    assert r.status_code == 404
