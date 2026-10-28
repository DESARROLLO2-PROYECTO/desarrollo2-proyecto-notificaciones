"""Bootstrap: crea FastAPI, registra routers y manejadores de error. Swagger en /docs."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import health, notificaciones
from app.config import get_settings
from app.domain.errores import (
    ErrorDominio,
    ErrorInterno,
    NoAutenticado,
    NoAutorizado,
    NoEncontrado,
    TipoNoDisponible,
)

log = logging.getLogger(__name__)

_ESTADOS: dict[type[ErrorDominio], int] = {
    NoAutenticado: 401,
    NoAutorizado: 403,
    NoEncontrado: 404,
    ErrorInterno: 500,
}


def _error_dominio(_: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, ErrorDominio)
    return JSONResponse({"mensaje": e.mensaje}, status_code=_ESTADOS.get(type(e), 500))


def _tipo_no_disponible(_: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, TipoNoDisponible)
    return JSONResponse(
        {
            "mensaje": "Los datos enviados no cumplen las reglas establecidas",
            "errores": [{"campo": "tipo", "error": e.mensaje}],
        },
        status_code=422,
    )


def _error_validacion(request: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, RequestValidationError)
    errores = e.errors()
    en_cuerpo = any(x["loc"][0] == "body" for x in errores)
    mensaje = (
        "Los datos enviados no cumplen las reglas establecidas"
        if en_cuerpo
        else "Solicitud inválida: verifique los parámetros enviados"
    )
    campos = [{"campo": str(x["loc"][-1]), "error": x["msg"]} for x in errores]
    log.warning(
        "RECHAZADA 422 endpoint=%s %s campos=%s",
        request.method,
        request.scope["route"].path,  # plantilla de la ruta: evita inyectar saltos de línea
        [c["campo"] for c in campos],
    )
    return JSONResponse({"mensaje": mensaje, "errores": campos}, status_code=422)


def _error_inesperado(request: Request, e: Exception) -> JSONResponse:
    log.error("Error no controlado en %r", request.url.path, exc_info=e)
    # Ej. falla el commit fuera de registrar(): mismos mensajes que HU-NOT-01 c7 y HU-NOT-07/09.
    mensaje = (
        "No fue posible registrar la notificación, intente de nuevo"
        if request.method == "POST"
        else "No fue posible consultar las notificaciones, intente de nuevo"
    )
    return JSONResponse({"mensaje": mensaje}, status_code=500)


def create_app() -> FastAPI:
    logging.basicConfig(
        level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    app = FastAPI(title="Notificaciones", version="0.1.0")
    app.add_exception_handler(ErrorDominio, _error_dominio)
    app.add_exception_handler(TipoNoDisponible, _tipo_no_disponible)
    app.add_exception_handler(RequestValidationError, _error_validacion)
    app.add_exception_handler(Exception, _error_inesperado)
    app.include_router(health.router)
    app.include_router(notificaciones.router)
    return app


app = create_app()
