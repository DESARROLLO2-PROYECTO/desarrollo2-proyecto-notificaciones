"""Repository/DAO: implementa los puertos de app/domain/puertos.py con SQLAlchemy."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import puertos
from app.domain.catalogo import DatosStock, Tipo
from app.infrastructure import models as m


class ApiKeyRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def contar_activas(self, rol: str) -> int:
        q = select(func.count()).select_from(m.ApiKey).where(m.ApiKey.rol == rol, m.ApiKey.activa)
        return self._s.scalar(q) or 0

    def crear(self, llave: puertos.ApiKey) -> None:
        self._s.add(
            m.ApiKey(
                id=llave.id,
                rol=llave.rol,
                hash=llave.hash,
                creada_en=llave.creada_en,
                activa=llave.activa,
            )
        )
        self._s.flush()

    def buscar_activa(self, hash: str) -> puertos.ApiKey | None:
        r = self._s.scalar(select(m.ApiKey).where(m.ApiKey.hash == hash, m.ApiKey.activa))
        return None if r is None else puertos.ApiKey(r.id, r.rol, r.hash, r.creada_en, r.activa)


class TipoRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def obtener(self, nombre: str) -> Tipo:
        t = self._s.get_one(m.TipoNotificacion, nombre)
        return Tipo(t.nombre, t.emisor, t.destino, t.expiracion_min)


class NotificacionRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def obtener(self, id: UUID) -> puertos.Notificacion | None:
        r = self._s.get(m.Notificacion, id)
        if r is None:
            return None
        datos = DatosStock(r.producto_id, r.nombre, r.stock_actual, r.stock_minimo)
        return puertos.Notificacion(r.id, r.tipo, r.destino, r.fecha_registro, datos)

    def registrar(self, notificacion: puertos.Notificacion, alerta: puertos.Alerta) -> bool:
        d = notificacion.datos
        try:
            # SAVEPOINT: si el UNIQUE parcial falla, se descarta también la notificación.
            with self._s.begin_nested():
                self._s.add(
                    m.Notificacion(
                        id=notificacion.id,
                        tipo=notificacion.tipo,
                        destino=notificacion.destino,
                        producto_id=d.producto_id,
                        nombre=d.nombre,
                        stock_actual=d.stock_actual,
                        stock_minimo=d.stock_minimo,
                        fecha_registro=notificacion.fecha_registro,
                    )
                )
                self._s.flush()  # la alerta referencia a la notificación (FK)
                self._s.add(
                    m.Alerta(
                        id=alerta.id,
                        tipo=alerta.tipo,
                        clave=alerta.clave,
                        notificacion_id=alerta.notificacion_id,
                        creada_en=alerta.creada_en,
                        expira_en=alerta.expira_en,
                    )
                )
                self._s.flush()
        except IntegrityError:
            return False
        return True


class AlertaRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def obtener_activa(self, tipo: str, clave: str) -> puertos.Alerta | None:
        r = self._s.scalar(
            select(m.Alerta).where(
                m.Alerta.tipo == tipo, m.Alerta.clave == clave, m.Alerta.resuelta_en.is_(None)
            )
        )
        if r is None:
            return None
        return puertos.Alerta(r.id, r.tipo, r.clave, r.notificacion_id, r.creada_en, r.expira_en)

    def expirar_vencidas(self, tipo: str, clave: str, ahora: datetime) -> None:
        self._s.execute(
            update(m.Alerta)
            .where(
                m.Alerta.tipo == tipo,
                m.Alerta.clave == clave,
                m.Alerta.resuelta_en.is_(None),
                m.Alerta.expira_en <= ahora,
            )
            .values(resuelta_en=ahora, motivo_resolucion="EXPIRACION")
        )

    def resolver(self, tipo: str, clave: str, ahora: datetime, motivo: str) -> bool:
        r = self._s.execute(
            update(m.Alerta)
            .where(m.Alerta.tipo == tipo, m.Alerta.clave == clave, m.Alerta.resuelta_en.is_(None))
            .values(resuelta_en=ahora, motivo_resolucion=motivo)
        )
        return bool(r.rowcount)  # type: ignore[attr-defined]  # CursorResult en tiempo de ejecución
