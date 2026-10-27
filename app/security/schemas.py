"""Validator / DTO (Pydantic v2). JSON en camelCase como en las HU."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator
from pydantic.alias_generators import to_camel

Cantidad = Annotated[StrictInt, Field(ge=0, le=1_000_000)]


class _Base(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class NotificacionIn(_Base):
    # Sprint 0: solo STOCK_BAJO_*; los otros tipos del catálogo son de HU-NOT-05/06.
    tipo: Literal["STOCK_BAJO_INSUMO", "STOCK_BAJO_PRODUCTO"]
    evento: Literal["DETECTADA", "REPUESTO", "RESUELTA"] = "DETECTADA"
    producto_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{1,50}$")]
    nombre: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    stock_actual: Cantidad
    stock_minimo: Cantidad

    @field_validator("producto_id", mode="before")
    @classmethod
    def _entero_a_texto(cls, v: Any) -> Any:
        # El productoId puede llegar como entero (HU-NOT-01 c1); bool es int en Python.
        return str(v) if isinstance(v, int) and not isinstance(v, bool) else v


class RegistroOut(_Base):
    id: UUID | None = None
    mensaje: str
    duplicada: bool | None = None


class NotificacionOut(_Base):
    id: UUID
    tipo: str
    destino: str
    mensaje: str
    fecha_registro: datetime
    producto_id: str
    nombre: str
    stock_actual: int
    stock_minimo: int


class ErrorCampo(BaseModel):
    campo: str
    error: str


class ValidacionOut(BaseModel):
    mensaje: str
    errores: list[ErrorCampo]
