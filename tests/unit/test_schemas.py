import pytest
from pydantic import ValidationError

from app.security.schemas import NotificacionIn

VALIDO = {
    "tipo": "STOCK_BAJO_INSUMO",
    "productoId": "INS-1",
    "nombre": "Hilo",
    "stockActual": 3,
    "stockMinimo": 10,
}


def test_cuerpo_valido_usa_detectada_por_defecto():
    # Arrange / Act
    n = NotificacionIn.model_validate(VALIDO)

    # Assert
    assert n.evento == "DETECTADA"
    assert n.producto_id == "INS-1"


def test_producto_id_entero_se_convierte_a_texto():
    # Arrange / Act
    n = NotificacionIn.model_validate({**VALIDO, "productoId": 42})

    # Assert
    assert n.producto_id == "42"


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("productoId", "con espacio"),
        ("productoId", "x" * 51),
        ("productoId", True),
        ("nombre", ""),
        ("nombre", "n" * 101),
        ("stockActual", -1),
        ("stockActual", 1.5),
        ("stockMinimo", 1_000_001),
        ("tipo", "CONDICION_URGENTE"),
        ("evento", "OTRO"),
    ],
)
def test_cuerpo_invalido_se_rechaza(campo, valor):
    # Arrange
    cuerpo = {**VALIDO, campo: valor}

    # Act / Assert
    with pytest.raises(ValidationError):
        NotificacionIn.model_validate(cuerpo)
