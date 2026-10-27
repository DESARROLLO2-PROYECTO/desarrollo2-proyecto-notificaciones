"""Router/Controlador REST (MVC)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Response

from app.api.deps import RolDep, ServicioDep
from app.domain.catalogo import DatosStock
from app.domain.notificacion_service import (
    ALERTA_CERRADA,
    ALERTA_YA_ACTIVA,
    REGISTRADA,
    SIN_ALERTA,
)
from app.security.schemas import NotificacionIn, NotificacionOut, RegistroOut, ValidacionOut

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])

_MENSAJES = {
    REGISTRADA: "Notificación registrada correctamente",
    ALERTA_YA_ACTIVA: "Ya existe una alerta activa para este artículo",
    ALERTA_CERRADA: "Alerta cerrada correctamente",  # provisional hasta HU-NOT-02
    SIN_ALERTA: "No había una alerta activa",
}


@router.post(
    "",
    status_code=201,
    response_model=RegistroOut,
    response_model_exclude_none=True,
    responses={200: {"model": RegistroOut}, 422: {"model": ValidacionOut}},
)
def registrar(
    cuerpo: NotificacionIn, rol: RolDep, servicio: ServicioDep, response: Response
) -> RegistroOut:
    datos = DatosStock(cuerpo.producto_id, cuerpo.nombre, cuerpo.stock_actual, cuerpo.stock_minimo)
    r = servicio.registrar(rol, cuerpo.tipo, cuerpo.evento, datos)
    if r.resultado != REGISTRADA:
        response.status_code = 200
    return RegistroOut(
        id=r.id,
        mensaje=_MENSAJES[r.resultado],
        duplicada=True if r.resultado == ALERTA_YA_ACTIVA else None,
    )


@router.get(
    "/estado/{id}", response_model=NotificacionOut, responses={422: {"model": ValidacionOut}}
)
def estado(id: Annotated[UUID, Path()], rol: RolDep, servicio: ServicioDep) -> NotificacionOut:
    n = servicio.obtener(rol, id)
    d = n.datos
    return NotificacionOut(
        id=n.id,
        tipo=n.tipo,
        destino=n.destino,
        mensaje=n.mensaje,
        fecha_registro=n.fecha_registro,
        producto_id=d.producto_id,
        nombre=d.nombre,
        stock_actual=d.stock_actual,
        stock_minimo=d.stock_minimo,
    )
