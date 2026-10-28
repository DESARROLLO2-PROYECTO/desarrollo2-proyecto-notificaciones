"""Fakes en memoria de los puertos (sin BD)."""

from datetime import datetime
from uuid import UUID

from app.domain.catalogo import Tipo
from app.domain.puertos import Alerta, ApiKey, Notificacion

TIPOS = {
    "STOCK_BAJO_INSUMO": Tipo("STOCK_BAJO_INSUMO", "inventario", "inventario", 1440),
    "STOCK_BAJO_PRODUCTO": Tipo("STOCK_BAJO_PRODUCTO", "inventario", "fabricacion", 1440),
}


class FakeApiKeys:
    def __init__(self) -> None:
        self.llaves: list[ApiKey] = []

    def contar_activas(self, rol: str) -> int:
        return sum(1 for k in self.llaves if k.rol == rol and k.activa)

    def crear(self, llave: ApiKey) -> int:
        self.llaves.append(llave)
        return len(self.llaves)

    def buscar_activa(self, hash: str) -> ApiKey | None:
        return next((k for k in self.llaves if k.hash == hash and k.activa), None)


class FakeTipos:
    def obtener(self, nombre: str) -> Tipo | None:
        return TIPOS.get(nombre)


class FakeNotificaciones:
    """registrar() reproduce el UNIQUE parcial: falla si hay alerta activa de la misma clave."""

    def __init__(self, alertas: "FakeAlertas") -> None:
        self.guardadas: dict[UUID, Notificacion] = {}
        self._alertas = alertas

    def obtener(self, id: UUID) -> Notificacion | None:
        return self.guardadas.get(id)

    def registrar(self, notificacion: Notificacion, alerta: Alerta) -> bool:
        if self._alertas.obtener_activa(alerta.tipo, alerta.clave):
            return False
        self.guardadas[notificacion.id] = notificacion
        self._alertas.activas.append(alerta)
        return True


class FakeAlertas:
    def __init__(self) -> None:
        self.activas: list[Alerta] = []
        self.resueltas: list[tuple[Alerta, str]] = []

    def obtener_activa(self, tipo: str, clave: str) -> Alerta | None:
        return next((a for a in self.activas if (a.tipo, a.clave) == (tipo, clave)), None)

    def expirar_vencidas(self, tipo: str, clave: str, ahora: datetime) -> None:
        a = self.obtener_activa(tipo, clave)
        if a and a.expira_en <= ahora:
            self.activas.remove(a)
            self.resueltas.append((a, "EXPIRACION"))

    def resolver(self, tipo: str, clave: str, ahora: datetime) -> bool:
        a = self.obtener_activa(tipo, clave)
        if a is None:
            return False
        self.activas.remove(a)
        self.resueltas.append((a, "EMISOR"))
        return True
