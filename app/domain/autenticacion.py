"""Autenticador: llave → hash (security.api_key) → ApiKeyRepository → rol."""

import logging
from datetime import UTC, datetime

from app.domain.errores import LimiteDeLlaves, NoAutenticado, RolInvalido
from app.domain.puertos import ApiKey, ApiKeyRepository
from app.security.api_key import generar_llave, hashear

log = logging.getLogger(__name__)

ROLES = ("inventario", "fabricacion", "notificaciones")
MAX_LLAVES_ACTIVAS = 2
PREFIJO = 8  # solo para reconocer la llave; no la expone


class ServicioAutenticacion:
    def __init__(self, llaves: ApiKeyRepository) -> None:
        self._llaves = llaves

    def autenticar(self, llave: str | None, endpoint: str) -> str:
        """Devuelve el rol o lanza 401. El log nunca incluye la llave (HU-NOT-12)."""
        registro = self._llaves.buscar_activa(hashear(llave)) if llave else None
        if registro is None:
            motivo = "llave inválida" if llave else "sin llave"
            log.warning("RECHAZADA 401 motivo=%s endpoint=%s", motivo, endpoint)
            raise NoAutenticado("Acceso denegado")
        return registro.rol

    def crear_llave(self, rol: str) -> str:
        """Alta de llave. Devuelve la llave en claro; solo se guarda el hash."""
        if rol not in ROLES:
            raise RolInvalido("Rol no válido")
        if self._llaves.contar_activas(rol) >= MAX_LLAVES_ACTIVAS:
            raise LimiteDeLlaves("Ya existen dos llaves activas para este rol")
        llave = generar_llave()
        self._llaves.crear(ApiKey(rol, hashear(llave), llave[:PREFIJO], datetime.now(UTC)))
        return llave
