import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.catalogo import DatosStock
from app.domain.errores import ErrorInterno, NoAutorizado, NoEncontrado, TipoNoDisponible
from app.domain.notificacion_service import NotificacionService
from tests.unit.fakes import FakeAlertas, FakeNotificaciones, FakeTipos

T0 = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
DATOS = DatosStock("INS-1", "Hilo", 3, 10)


class Reloj:
    def __init__(self) -> None:
        self.ahora = T0

    def __call__(self) -> datetime:
        return self.ahora


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def alertas():
    return FakeAlertas()


@pytest.fixture
def notificaciones(alertas):
    return FakeNotificaciones(alertas)


@pytest.fixture
def servicio(notificaciones, alertas, reloj):
    return NotificacionService(FakeTipos(), notificaciones, alertas, reloj)


def test_registrar_crea_notificacion_y_alerta(servicio, notificaciones, alertas, caplog):
    # Arrange
    caplog.set_level(logging.INFO)

    # Act
    r = servicio.registrar("inventario", "STOCK_BAJO_PRODUCTO", "DETECTADA", DATOS)

    # Assert
    assert r.resultado == "REGISTRADA"
    n = notificaciones.guardadas[r.id]
    assert n.destino == "fabricacion"
    assert alertas.activas[0].expira_en == T0 + timedelta(minutes=1440)
    assert "REGISTRADA tipo=STOCK_BAJO_PRODUCTO destino=fabricacion clave=INS-1" in caplog.text


def test_registrar_repetido_devuelve_el_id_existente(servicio, notificaciones):
    # Arrange
    primera = servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)

    # Act
    segunda = servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)

    # Assert
    assert segunda.resultado == "ALERTA_YA_ACTIVA"
    assert segunda.id == primera.id
    assert len(notificaciones.guardadas) == 1


def test_alerta_vencida_se_expira_y_se_registra_otra(servicio, notificaciones, alertas, reloj):
    # Arrange
    primera = servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)
    reloj.ahora = T0 + timedelta(minutes=1440)

    # Act
    segunda = servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)

    # Assert
    assert segunda.resultado == "REGISTRADA"
    assert segunda.id != primera.id
    assert alertas.resueltas[0][1] == "EXPIRACION"


def test_registrar_con_emisor_equivocado_lanza_403_y_no_guarda(servicio, notificaciones, caplog):
    # Arrange / Act
    with caplog.at_level(logging.WARNING), pytest.raises(NoAutorizado, match="Acceso denegado"):
        servicio.registrar("fabricacion", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)

    # Assert
    assert not notificaciones.guardadas
    assert "emisor no permitido" in caplog.text
    assert "rol=fabricacion" in caplog.text


def test_tipo_no_disponible_lanza_422_y_no_guarda(servicio, notificaciones, caplog):
    # Arrange / Act
    with caplog.at_level(logging.WARNING), pytest.raises(TipoNoDisponible):
        servicio.registrar("inventario", "TIPO_INACTIVO", "DETECTADA", DATOS)

    # Assert
    assert not notificaciones.guardadas
    assert "RECHAZADA 422" in caplog.text


def test_evento_resuelta_cierra_la_alerta_activa(servicio, alertas):
    # Arrange
    servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)

    # Act
    r = servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "RESUELTA", DATOS)

    # Assert
    assert r.resultado == "ALERTA_CERRADA"
    assert not alertas.activas
    assert alertas.resueltas[0][1] == "EMISOR"


def test_evento_repuesto_sin_alerta_activa(servicio):
    # Arrange / Act
    r = servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "REPUESTO", DATOS)

    # Assert
    assert r.resultado == "SIN_ALERTA"
    assert r.id is None


def test_falla_interna_se_traduce_a_error_interno(servicio, notificaciones):
    # Arrange
    def falla(*_):
        raise RuntimeError("BD caída")

    notificaciones.registrar = falla

    # Act / Assert
    with pytest.raises(ErrorInterno, match="No fue posible registrar la notificación"):
        servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)


def test_duplicado_sin_alerta_activa_es_error_interno(servicio, notificaciones):
    # Arrange
    notificaciones.registrar = lambda *_: False

    # Act / Assert
    with pytest.raises(ErrorInterno):
        servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)


def test_obtener_respeta_el_destino_del_rol(servicio):
    # Arrange
    r = servicio.registrar("inventario", "STOCK_BAJO_PRODUCTO", "DETECTADA", DATOS)

    # Act
    n = servicio.obtener("fabricacion", r.id)

    # Assert
    assert n.mensaje == "Stock bajo de Hilo (INS-1): 3 de mínimo 10"
    assert servicio.obtener("notificaciones", r.id) == n


@pytest.mark.parametrize("rol", ["inventario", "fabricacion"])
def test_obtener_ajeno_o_inexistente_es_404(servicio, rol):
    # Arrange
    r = servicio.registrar("inventario", "STOCK_BAJO_PRODUCTO", "DETECTADA", DATOS)
    id_ = r.id if rol == "inventario" else uuid4()

    # Act / Assert
    with pytest.raises(NoEncontrado, match="Notificación no encontrada"):
        servicio.obtener(rol, id_)


def test_reloj_por_defecto_es_utc(notificaciones, alertas):
    # Arrange
    servicio = NotificacionService(FakeTipos(), notificaciones, alertas)

    # Act
    r = servicio.registrar("inventario", "STOCK_BAJO_INSUMO", "DETECTADA", DATOS)

    # Assert
    assert notificaciones.guardadas[r.id].fecha_registro.tzinfo is UTC
