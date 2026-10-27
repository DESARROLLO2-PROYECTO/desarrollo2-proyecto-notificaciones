"""Catálogo de tipos (Strategy): cada tipo sabe armar su mensaje.

Emisor, destino y expiración viven en la tabla tipos_notificacion (sembrada en 0001).
"""

from collections.abc import Callable
from dataclasses import dataclass

MAX_MENSAJE = 200


@dataclass(frozen=True)
class Tipo:
    nombre: str
    emisor: str
    destino: str
    expiracion_min: int


@dataclass(frozen=True)
class DatosStock:
    producto_id: str
    nombre: str
    stock_actual: int
    stock_minimo: int


def _stock_bajo(d: DatosStock) -> str:
    return (
        f"Stock bajo de {d.nombre} ({d.producto_id}): {d.stock_actual} de mínimo {d.stock_minimo}"
    )


_MENSAJES: dict[str, Callable[[DatosStock], str]] = {
    "STOCK_BAJO_INSUMO": _stock_bajo,
    "STOCK_BAJO_PRODUCTO": _stock_bajo,
}


def construir_mensaje(tipo: str, datos: DatosStock) -> str:
    """El mensaje se calcula en cada lectura; no se guarda."""
    return _MENSAJES[tipo](datos)[:MAX_MENSAJE]
