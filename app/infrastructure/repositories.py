"""Repository/DAO: implementa los puertos de app/domain/puertos.py con SQLAlchemy."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.domain import puertos
from app.domain.catalogo import DatosStock, Tipo
from app.infrastructure import models as m


class ApiKeyRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def contar_activas(self, rol: str) -> int:
        q = (
            select(func.count())
            .select_from(m.ApiKey)
            .join(m.Equipo, m.Equipo.id == m.ApiKey.equipo_id)
            .where(m.Equipo.nombre == rol, m.ApiKey.activa)
        )
        return self._s.scalar(q) or 0

    def crear(self, llave: puertos.ApiKey) -> int:
        registro = m.ApiKey(
            equipo_id=_equipo_id(self._s, llave.rol),
            hash=llave.hash,
            prefijo=llave.prefijo,
            creada_at=llave.creada_en,
            activa=llave.activa,
        )
        self._s.add(registro)
        self._s.flush()  # asigna el id autogenerado
        return registro.id

    def buscar_activa(self, hash: str) -> puertos.ApiKey | None:
        fila = self._s.execute(
            select(m.ApiKey, m.Equipo.nombre)
            .join(m.Equipo, m.Equipo.id == m.ApiKey.equipo_id)
            .where(m.ApiKey.hash == hash, m.ApiKey.activa)
        ).one_or_none()
        if fila is None:
            return None
        r, rol = fila
        return puertos.ApiKey(rol, r.hash, r.prefijo, r.creada_at, r.activa)


class TipoRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def obtener(self, nombre: str) -> Tipo | None:
        emisor, destino = aliased(m.Equipo), aliased(m.Equipo)
        t = m.TipoNotificacion
        fila = self._s.execute(
            select(t.codigo, emisor.nombre, destino.nombre, t.ttl_alerta_min)
            .join(emisor, emisor.id == t.equipo_emisor_id)
            .join(destino, destino.id == t.equipo_destino_id)
            .where(t.codigo == nombre, t.activo)
        ).one_or_none()
        return None if fila is None else Tipo(*fila)


def _equipo_id(session: Session, nombre: str) -> int:
    # scalar_one: un equipo inexistente es un error interno, no una "duplicada".
    return session.execute(select(m.Equipo.id).where(m.Equipo.nombre == nombre)).scalar_one()


class NotificacionRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def obtener(self, id: UUID) -> puertos.Notificacion | None:
        fila = self._s.execute(
            select(m.Notificacion, m.Equipo.nombre)
            .join(m.Equipo, m.Equipo.id == m.Notificacion.equipo_destino_id)
            .where(m.Notificacion.id == id)
        ).one_or_none()
        if fila is None:
            return None
        r, destino = fila
        p = r.payload
        datos = DatosStock(
            str(p["productoId"]), str(p["nombre"]), int(p["stockActual"]), int(p["stockMinimo"])
        )
        return puertos.Notificacion(r.id, r.tipo, destino, r.creada_at, datos)

    def registrar(self, notificacion: puertos.Notificacion, alerta: puertos.Alerta) -> bool:
        d = notificacion.datos
        emisor_id = self._s.get_one(m.TipoNotificacion, notificacion.tipo).equipo_emisor_id
        try:
            # SAVEPOINT: si el UNIQUE parcial falla, se descarta también la notificación.
            with self._s.begin_nested():
                self._s.add(
                    m.Notificacion(
                        id=notificacion.id,
                        tipo=notificacion.tipo,
                        equipo_emisor_id=emisor_id,
                        equipo_destino_id=_equipo_id(self._s, notificacion.destino),
                        payload={
                            "productoId": d.producto_id,
                            "nombre": d.nombre,
                            "stockActual": d.stock_actual,
                            "stockMinimo": d.stock_minimo,
                        },
                        creada_at=notificacion.fecha_registro,
                    )
                )
                self._s.flush()  # la alerta referencia a la notificación (FK)
                self._s.add(
                    m.Alerta(
                        tipo=alerta.tipo,
                        clave=alerta.clave,
                        notificacion_id=alerta.notificacion_id,
                        creada_at=alerta.creada_en,
                        expira_at=alerta.expira_en,
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
                m.Alerta.tipo == tipo, m.Alerta.clave == clave, m.Alerta.cerrada_at.is_(None)
            )
        )
        if r is None:
            return None
        return puertos.Alerta(r.tipo, r.clave, r.notificacion_id, r.creada_at, r.expira_at)

    def expirar_vencidas(self, tipo: str, clave: str, ahora: datetime) -> None:
        self._s.execute(
            update(m.Alerta)
            .where(
                m.Alerta.tipo == tipo,
                m.Alerta.clave == clave,
                m.Alerta.cerrada_at.is_(None),
                m.Alerta.expira_at <= ahora,
            )
            .values(cerrada_at=ahora, motivo_resolucion="EXPIRACION")
        )

    def resolver(self, tipo: str, clave: str, ahora: datetime) -> bool:
        r = self._s.execute(
            update(m.Alerta)
            .where(m.Alerta.tipo == tipo, m.Alerta.clave == clave, m.Alerta.cerrada_at.is_(None))
            .values(cerrada_at=ahora, motivo_resolucion="EMISOR")  # REPUESTO/RESUELTA
        )
        return bool(r.rowcount)  # type: ignore[attr-defined]  # CursorResult en tiempo de ejecución
