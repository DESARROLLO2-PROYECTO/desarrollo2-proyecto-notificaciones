import hashlib

from app.security.api_key import generar_llave, hashear


def test_generar_llave_es_aleatoria_y_de_al_menos_32_bytes():
    # Arrange / Act
    a, b = generar_llave(), generar_llave()

    # Assert
    assert a != b
    assert len(a) >= 43  # 32 bytes en base64 url-safe


def test_hashear_es_sha256_hexadecimal():
    # Arrange
    llave = "abc"

    # Act
    resultado = hashear(llave)

    # Assert
    assert resultado == hashlib.sha256(b"abc").hexdigest()
    assert len(resultado) == 64
