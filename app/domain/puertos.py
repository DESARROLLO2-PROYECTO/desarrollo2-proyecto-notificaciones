"""Puertos del Repository (Protocols): el dominio no conoce SQLAlchemy.

Las implementaciones viven en app/infrastructure/repositories.py.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.catalogo import DatosStock, Tipo, construir_mensaje


@dataclass(frozen=True)
class ApiKey:
    id: UUID
    rol: str
    hash: str
    creada_en: datetime
    activa: bool = True


@dataclass(frozen=True)
class Notificacion:
    id: UUID
    tipo: str
    destino: str
    fecha_registro: datetime
    datos: DatosStock

    @property
    def mensaje(self) -> str:
        return construir_mensaje(self.tipo, self.datos)


@dataclass(frozen=True)
class Alerta:
    id: UUID
    tipo: str
    clave: str
    notificacion_id: UUID
    creada_en: datetime
    expira_en: datetime


class ApiKeyRepository(Protocol):
    def contar_activas(self, rol: str) -> int: ...
    def crear(self, llave: ApiKey) -> None: ...
    def buscar_activa(self, hash: str) -> ApiKey | None: ...


class TipoRepository(Protocol):
    def obtener(self, nombre: str) -> Tipo: ...


class NotificacionRepository(Protocol):
    def obtener(self, id: UUID) -> Notificacion | None: ...

    def registrar(self, notificacion: Notificacion, alerta: Alerta) -> bool:
        """Guarda ambas o ninguna. False si ya había una alerta activa (UNIQUE parcial)."""
        ...


class AlertaRepository(Protocol):
    def obtener_activa(self, tipo: str, clave: str) -> Alerta | None: ...
    def expirar_vencidas(self, tipo: str, clave: str, ahora: datetime) -> None: ...
    def resolver(self, tipo: str, clave: str, ahora: datetime, motivo: str) -> bool:
        """Cierra la alerta activa; False si no había ninguna."""
        ...
