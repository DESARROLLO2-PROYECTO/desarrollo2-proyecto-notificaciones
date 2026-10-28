"""Excepciones de dominio; la capa API las traduce a HTTP (401/403/404/500)."""


class ErrorDominio(Exception):
    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoAutenticado(ErrorDominio):
    """401"""


class NoAutorizado(ErrorDominio):
    """403"""


class NoEncontrado(ErrorDominio):
    """404"""


class ErrorInterno(ErrorDominio):
    """500"""


class RolInvalido(ErrorDominio):
    """Alta de llave con un rol fuera de los permitidos (HU-NOT-11)."""


class LimiteDeLlaves(ErrorDominio):
    """El rol ya tiene dos llaves activas (HU-NOT-11)."""


class TipoNoDisponible(ErrorDominio):
    """422: tipo fuera del catálogo o inactivo (HU-NOT-01 c4)."""
