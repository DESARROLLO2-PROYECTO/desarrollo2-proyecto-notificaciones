"""Model: tablas de SQLAlchemy 2 (estilo Mapped). Espejo de migrations/versions/0001."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    rol: Mapped[str] = mapped_column(String(20))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activa: Mapped[bool]


class TipoNotificacion(Base):
    __tablename__ = "tipos_notificacion"

    nombre: Mapped[str] = mapped_column(String(50), primary_key=True)
    emisor: Mapped[str] = mapped_column(String(20))
    destino: Mapped[str] = mapped_column(String(20))
    expiracion_min: Mapped[int] = mapped_column(Integer)


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tipo: Mapped[str] = mapped_column(ForeignKey("tipos_notificacion.nombre"))
    destino: Mapped[str] = mapped_column(String(20), index=True)
    producto_id: Mapped[str] = mapped_column(String(50))
    nombre: Mapped[str] = mapped_column(String(100))
    stock_actual: Mapped[int] = mapped_column(Integer)
    stock_minimo: Mapped[int] = mapped_column(Integer)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Alerta(Base):
    __tablename__ = "alertas"
    __table_args__ = (
        # Una sola alerta activa por (tipo, clave): resuelve la concurrencia de HU-NOT-01 c6.
        Index(
            "uq_alerta_activa",
            "tipo",
            "clave",
            unique=True,
            postgresql_where=text("resuelta_en IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tipo: Mapped[str] = mapped_column(ForeignKey("tipos_notificacion.nombre"))
    clave: Mapped[str] = mapped_column(String(50))
    notificacion_id: Mapped[UUID] = mapped_column(ForeignKey("notificaciones.id"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_resolucion: Mapped[str | None] = mapped_column(String(20))
