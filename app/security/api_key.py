"""Autenticador (API Key): funciones puras, sin I/O."""

import hashlib
import secrets


def generar_llave() -> str:
    """Llave aleatoria de 32 bytes (HU-NOT-11)."""
    return secrets.token_urlsafe(32)


def hashear(llave: str) -> str:
    """SHA-256 en hexadecimal; es lo único que se guarda."""
    return hashlib.sha256(llave.encode()).hexdigest()
