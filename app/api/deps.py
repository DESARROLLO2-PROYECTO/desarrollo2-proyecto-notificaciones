"""Inyección de dependencias: sesión → repos → servicios; lee X-API-Key."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.domain.autenticacion import ServicioAutenticacion
from app.domain.notificacion_service import NotificacionService
from app.infrastructure.db import transaccion
from app.infrastructure.repositories import AlertaRepo, ApiKeyRepo, NotificacionRepo, TipoRepo

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_session() -> Iterator[Session]:
    with transaccion() as session:
        yield session


# scope="function": el commit ocurre antes de enviar la respuesta, no después.
# NOSONAR: python:S930 no conoce el parámetro scope de Depends (FastAPI >= 0.120).
SessionDep = Annotated[Session, Depends(get_session, scope="function")]  # NOSONAR


def get_autenticacion(session: SessionDep) -> ServicioAutenticacion:
    return ServicioAutenticacion(ApiKeyRepo(session))


def get_notificaciones(session: SessionDep) -> NotificacionService:
    return NotificacionService(TipoRepo(session), NotificacionRepo(session), AlertaRepo(session))


def rol_actual(
    request: Request,
    llave: Annotated[str | None, Security(api_key_header)],
    auth: Annotated[ServicioAutenticacion, Depends(get_autenticacion)],
) -> str:
    return auth.autenticar(llave, f"{request.method} {request.scope['route'].path}")


RolDep = Annotated[str, Depends(rol_actual)]
ServicioDep = Annotated[NotificacionService, Depends(get_notificaciones)]
