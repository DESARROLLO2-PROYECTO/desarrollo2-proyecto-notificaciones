"""Application Service: registrar() con anti-duplicado y obtener() con RBAC por destino."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.domain.catalogo import DatosStock
from app.domain.errores import ErrorDominio, ErrorInterno, NoAutorizado, NoEncontrado
from app.domain.puertos import (
    Alerta,
    AlertaRepository,
    Notificacion,
    NotificacionRepository,
    TipoRepository,
)

log = logging.getLogger(__name__)

REGISTRADA = "REGISTRADA"
ALERTA_YA_ACTIVA = "ALERTA_YA_ACTIVA"
ALERTA_CERRADA = "ALERTA_CERRADA"
SIN_ALERTA = "SIN_ALERTA"  # provisional hasta HU-NOT-02 (resultado fuera de la lista de HU-01 c8)

ROL_ADMIN = "notificaciones"


@dataclass(frozen=True)
class Resultado:
    resultado: str
    id: UUID | None = None


def _ahora() -> datetime:
    return datetime.now(UTC)


class NotificacionService:
    def __init__(
        self,
        tipos: TipoRepository,
        notificaciones: NotificacionRepository,
        alertas: AlertaRepository,
        ahora: Callable[[], datetime] = _ahora,
    ) -> None:
        self._tipos = tipos
        self._notificaciones = notificaciones
        self._alertas = alertas
        self._ahora = ahora

    def registrar(self, rol: str, tipo: str, evento: str, datos: DatosStock) -> Resultado:
        try:
            return self._registrar(rol, tipo, evento, datos)
        except ErrorDominio:
            raise
        except Exception as e:
            log.exception(
                "RECHAZADA tipo=%s clave=%s motivo=error interno", tipo, datos.producto_id
            )
            raise ErrorInterno("No fue posible registrar la notificación, intente de nuevo") from e

    def _registrar(self, rol: str, tipo: str, evento: str, datos: DatosStock) -> Resultado:
        t = self._tipos.obtener(tipo)
        clave = datos.producto_id
        if t.emisor != rol:
            log.warning(
                "RECHAZADA 403 motivo=emisor no permitido endpoint=POST /notificaciones"
                " rol=%s tipo=%s destino=%s clave=%s",
                rol,
                tipo,
                t.destino,
                clave,
            )
            raise NoAutorizado("Acceso denegado")
        ahora = self._ahora()
        self._alertas.expirar_vencidas(tipo, clave, ahora)

        if evento != "DETECTADA":
            # Sprint 0: REPUESTO/RESUELTA solo cierran la alerta; el resto es HU-NOT-02.
            cerrada = self._alertas.resolver(tipo, clave, ahora)
            resultado = ALERTA_CERRADA if cerrada else SIN_ALERTA
            log.info("%s tipo=%s destino=%s clave=%s id=-", resultado, tipo, t.destino, clave)
            return Resultado(resultado)

        notificacion = Notificacion(uuid4(), tipo, t.destino, ahora, datos)
        alerta = Alerta(
            tipo,
            clave,
            notificacion.id,
            ahora,
            ahora + timedelta(minutes=t.expiracion_min),
        )
        if self._notificaciones.registrar(notificacion, alerta):
            resultado, id_ = REGISTRADA, notificacion.id
        else:
            # Otra solicitud ganó la carrera: se relee la alerta activa y se responde con su id.
            activa = self._alertas.obtener_activa(tipo, clave)
            if activa is None:
                raise ErrorInterno("Alerta activa no encontrada tras el duplicado")
            resultado, id_ = ALERTA_YA_ACTIVA, activa.notificacion_id
        log.info("%s tipo=%s destino=%s clave=%s id=%s", resultado, tipo, t.destino, clave, id_)
        return Resultado(resultado, id_)

    def obtener(self, rol: str, id: UUID) -> Notificacion:
        n = self._notificaciones.obtener(id)
        if n is None or (rol != ROL_ADMIN and n.destino != rol):
            raise NoEncontrado("Notificación no encontrada")
        return n
