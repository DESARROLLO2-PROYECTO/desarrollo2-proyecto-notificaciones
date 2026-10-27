from app.domain.catalogo import DatosStock, construir_mensaje


def test_mensaje_de_stock_bajo():
    # Arrange
    datos = DatosStock("INS-1", "Hilo", 3, 10)

    # Act
    mensaje = construir_mensaje("STOCK_BAJO_PRODUCTO", datos)

    # Assert
    assert mensaje == "Stock bajo de Hilo (INS-1): 3 de mínimo 10"


def test_mensaje_se_trunca_a_200_caracteres():
    # Arrange
    datos = DatosStock("X", "n" * 300, 1_000_000, 1_000_000)

    # Act
    mensaje = construir_mensaje("STOCK_BAJO_INSUMO", datos)

    # Assert
    assert len(mensaje) == 200
