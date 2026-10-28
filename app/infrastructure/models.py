"""Model: tablas de SQLAlchemy 2 (estilo Mapped). Espejo de migrations/versions/0001 y del ER."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

TZ = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class Equipo(Base):
    __tablename__ = "equipos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    es_admin: Mapped[bool]


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    prefijo: Mapped[str] = mapped_column(String(16))
    activa: Mapped[bool]
    creada_at: Mapped[datetime] = mapped_column(TZ)


class TipoNotificacion(Base):
    __tablename__ = "tipos_notificacion"

    codigo: Mapped[str] = mapped_column(String(60), primary_key=True)
    equipo_emisor_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    equipo_destino_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    schema: Mapped[dict[str, Any]] = mapped_column(JSONB)
    campo_clave: Mapped[str | None] = mapped_column(String(60))
    ttl_alerta_min: Mapped[int] = mapped_column(Integer)
    activo: Mapped[bool]


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tipo: Mapped[str] = mapped_column(
        String(60), ForeignKey("tipos_notificacion.codigo"), index=True
    )
    equipo_emisor_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    equipo_destino_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    creada_at: Mapped[datetime] = mapped_column(TZ, index=True)
    publicada_at: Mapped[datetime | None] = mapped_column(TZ)
    intentos_publicacion: Mapped[int] = mapped_column(Integer, server_default="0")
    ultimo_error_publicacion: Mapped[str | None] = mapped_column(Text)
    entregada_at: Mapped[datetime | None] = mapped_column(TZ)
    intentos_entrega: Mapped[int] = mapped_column(Integer, server_default="0")
    proximo_intento_entrega_at: Mapped[datetime | None] = mapped_column(TZ)
    ultimo_error_entrega: Mapped[str | None] = mapped_column(Text)
    leida_at: Mapped[datetime | None] = mapped_column(TZ)


class Alerta(Base):
    __tablename__ = "alertas"
    __table_args__ = (
        # Una sola alerta activa por (tipo, clave): resuelve la concurrencia de HU-NOT-01 c6.
        Index(
            "uq_alerta_activa",
            "tipo",
            "clave",
            unique=True,
            postgresql_where=text("cerrada_at IS NULL"),
        ),
        CheckConstraint("motivo_resolucion IN ('EMISOR', 'EXPIRACION')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(60), ForeignKey("tipos_notificacion.codigo"))
    clave: Mapped[str] = mapped_column(String(100))
    notificacion_id: Mapped[UUID] = mapped_column(ForeignKey("notificaciones.id"), unique=True)
    creada_at: Mapped[datetime] = mapped_column(TZ)
    expira_at: Mapped[datetime] = mapped_column(TZ)
    cerrada_at: Mapped[datetime | None] = mapped_column(TZ)
    motivo_resolucion: Mapped[str | None] = mapped_column(String(20))


# Tablas de HU futuras: solo esquema, sin repositorio todavía.
class Destinatario(Base):
    __tablename__ = "destinatarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    activo: Mapped[bool]
    creado_at: Mapped[datetime] = mapped_column(TZ)


class DestinatarioTipo(Base):
    __tablename__ = "destinatario_tipos"

    destinatario_id: Mapped[int] = mapped_column(ForeignKey("destinatarios.id"), primary_key=True)
    tipo_codigo: Mapped[str] = mapped_column(
        String(60), ForeignKey("tipos_notificacion.codigo"), primary_key=True
    )


class EnvioCorreo(Base):
    __tablename__ = "envios_correo"

    id: Mapped[int] = mapped_column(primary_key=True)
    notificacion_id: Mapped[UUID] = mapped_column(ForeignKey("notificaciones.id"))
    destinatario_id: Mapped[int] = mapped_column(ForeignKey("destinatarios.id"))
    email: Mapped[str] = mapped_column(String(254))
    enviado_at: Mapped[datetime | None] = mapped_column(TZ)
    intentos: Mapped[int] = mapped_column(Integer, server_default="0")
    proximo_intento_at: Mapped[datetime | None] = mapped_column(TZ)
    ultimo_error: Mapped[str | None] = mapped_column(Text)


class Callback(Base):
    __tablename__ = "callbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), unique=True)
    url: Mapped[str] = mapped_column(Text)
    secreto: Mapped[str] = mapped_column(String(128))
    activo: Mapped[bool]
    actualizado_at: Mapped[datetime] = mapped_column(TZ)
