import logging

import pytest

from app.domain.autenticacion import ServicioAutenticacion
from app.domain.errores import LimiteDeLlaves, NoAutenticado, RolInvalido
from app.security.api_key import hashear
from tests.unit.fakes import FakeApiKeys


def test_crear_llave_guarda_solo_el_hash():
    # Arrange
    repo = FakeApiKeys()
    servicio = ServicioAutenticacion(repo)

    # Act
    llave = servicio.crear_llave("inventario")

    # Assert
    guardada = repo.llaves[0]
    assert guardada.prefijo == llave[:8]
    assert guardada.hash == hashear(llave)
    assert llave not in (guardada.hash, guardada.rol)


def test_crear_llave_rechaza_rol_invalido():
    # Arrange
    servicio = ServicioAutenticacion(FakeApiKeys())

    # Act / Assert
    with pytest.raises(RolInvalido, match="Rol no válido"):
        servicio.crear_llave("admin")


def test_crear_llave_rechaza_tercera_llave_activa():
    # Arrange
    servicio = ServicioAutenticacion(FakeApiKeys())
    servicio.crear_llave("fabricacion")
    servicio.crear_llave("fabricacion")

    # Act / Assert
    with pytest.raises(LimiteDeLlaves, match="Ya existen dos llaves activas para este rol"):
        servicio.crear_llave("fabricacion")


def test_autenticar_devuelve_el_rol():
    # Arrange
    servicio = ServicioAutenticacion(FakeApiKeys())
    llave = servicio.crear_llave("fabricacion")

    # Act
    rol = servicio.autenticar(llave, "GET /x")

    # Assert
    assert rol == "fabricacion"


@pytest.mark.parametrize(
    ("llave", "motivo"), [(None, "sin llave"), ("", "sin llave"), ("mala", "llave inválida")]
)
def test_autenticar_rechaza_y_loguea_el_motivo_sin_la_llave(llave, motivo, caplog):
    # Arrange
    servicio = ServicioAutenticacion(FakeApiKeys())

    # Act
    with caplog.at_level(logging.WARNING), pytest.raises(NoAutenticado, match="Acceso denegado"):
        servicio.autenticar(llave, "GET /x")

    # Assert
    assert motivo in caplog.text
    assert "GET /x" in caplog.text
    assert "mala" not in caplog.text
