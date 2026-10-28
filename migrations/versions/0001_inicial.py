"""Esquema completo del ER (das/02_modelo_er.puml), equipos y catálogo sembrados.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None

TZ = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB

_STOCK = {
    "type": "object",
    "required": ["productoId", "nombre", "stockActual", "stockMinimo"],
    "properties": {
        "productoId": {"type": "string", "pattern": "^[A-Za-z0-9-]{1,50}$"},
        "nombre": {"type": "string", "minLength": 1, "maxLength": 100},
        "stockActual": {"type": "integer", "minimum": 0, "maximum": 1000000},
        "stockMinimo": {"type": "integer", "minimum": 0, "maximum": 1000000},
    },
}


def _fk(tabla: str) -> sa.ForeignKey:
    return sa.ForeignKey(f"{tabla}.id")


def upgrade() -> None:
    equipos = op.create_table(
        "equipos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nombre", sa.String(50), nullable=False, unique=True),
        sa.Column("es_admin", sa.Boolean, nullable=False),
    )
    op.bulk_insert(
        equipos,
        [
            {"id": 1, "nombre": "inventario", "es_admin": False},
            {"id": 2, "nombre": "fabricacion", "es_admin": False},
            {"id": 3, "nombre": "notificaciones", "es_admin": True},
        ],
    )
    op.execute("SELECT setval(pg_get_serial_sequence('equipos', 'id'), 3)")
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("equipo_id", sa.Integer, _fk("equipos"), nullable=False),
        sa.Column("hash", sa.CHAR(64), nullable=False, unique=True),
        sa.Column("prefijo", sa.String(16), nullable=False),
        sa.Column("activa", sa.Boolean, nullable=False),
        sa.Column("creada_at", TZ, nullable=False),
    )
    tipos = op.create_table(
        "tipos_notificacion",
        sa.Column("codigo", sa.String(60), primary_key=True),
        sa.Column("equipo_emisor_id", sa.Integer, _fk("equipos"), nullable=False),
        sa.Column("equipo_destino_id", sa.Integer, _fk("equipos"), nullable=False),
        sa.Column("schema", JSONB, nullable=False),
        sa.Column("campo_clave", sa.String(60)),
        sa.Column("ttl_alerta_min", sa.Integer, nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False),
    )
    columnas = (
        "codigo",
        "equipo_emisor_id",
        "equipo_destino_id",
        "schema",
        "campo_clave",
        "ttl_alerta_min",
    )
    op.bulk_insert(
        tipos,
        [
            dict(zip(columnas, fila, strict=True)) | {"activo": True}
            for fila in [
                ("STOCK_BAJO_INSUMO", 1, 1, _STOCK, "productoId", 1440),
                ("STOCK_BAJO_PRODUCTO", 1, 2, _STOCK, "productoId", 1440),
                ("CONDICION_URGENTE", 2, 2, {}, None, 60),
                ("ACUMULACION_PEDIDOS", 1, 1, {}, None, 60),
            ]
        ],
    )
    op.create_table(
        "notificaciones",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tipo", sa.String(60), sa.ForeignKey("tipos_notificacion.codigo"), nullable=False
        ),
        sa.Column("equipo_emisor_id", sa.Integer, _fk("equipos"), nullable=False),
        sa.Column("equipo_destino_id", sa.Integer, _fk("equipos"), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("creada_at", TZ, nullable=False),
        sa.Column("publicada_at", TZ),
        sa.Column("intentos_publicacion", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ultimo_error_publicacion", sa.Text),
        sa.Column("entregada_at", TZ),
        sa.Column("intentos_entrega", sa.Integer, nullable=False, server_default="0"),
        sa.Column("proximo_intento_entrega_at", TZ),
        sa.Column("ultimo_error_entrega", sa.Text),
        sa.Column("leida_at", TZ),
    )
    op.create_index("ix_notificaciones_creada_at", "notificaciones", ["creada_at"])
    op.create_index("ix_notificaciones_tipo", "notificaciones", ["tipo"])
    op.create_index("ix_notificaciones_equipo_destino_id", "notificaciones", ["equipo_destino_id"])
    op.create_table(
        "alertas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "tipo", sa.String(60), sa.ForeignKey("tipos_notificacion.codigo"), nullable=False
        ),
        sa.Column("clave", sa.String(100), nullable=False),
        sa.Column(
            "notificacion_id",
            sa.Uuid,
            sa.ForeignKey("notificaciones.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("creada_at", TZ, nullable=False),
        sa.Column("expira_at", TZ, nullable=False),
        sa.Column("cerrada_at", TZ),
        sa.Column("motivo_resolucion", sa.String(20)),
        sa.CheckConstraint("motivo_resolucion IN ('EMISOR', 'EXPIRACION')"),
    )
    op.create_index(
        "uq_alerta_activa",
        "alertas",
        ["tipo", "clave"],
        unique=True,
        postgresql_where=sa.text("cerrada_at IS NULL"),
    )
    op.create_table(
        "destinatarios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("equipo_id", sa.Integer, _fk("equipos"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False),
        sa.Column("creado_at", TZ, nullable=False),
    )
    op.create_table(
        "destinatario_tipos",
        sa.Column("destinatario_id", sa.Integer, _fk("destinatarios"), primary_key=True),
        sa.Column(
            "tipo_codigo",
            sa.String(60),
            sa.ForeignKey("tipos_notificacion.codigo"),
            primary_key=True,
        ),
    )
    op.create_table(
        "envios_correo",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("notificacion_id", sa.Uuid, sa.ForeignKey("notificaciones.id"), nullable=False),
        sa.Column("destinatario_id", sa.Integer, _fk("destinatarios"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("enviado_at", TZ),
        sa.Column("intentos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("proximo_intento_at", TZ),
        sa.Column("ultimo_error", sa.Text),
    )
    op.create_table(
        "callbacks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("equipo_id", sa.Integer, _fk("equipos"), nullable=False, unique=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("secreto", sa.String(128), nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False),
        sa.Column("actualizado_at", TZ, nullable=False),
    )


def downgrade() -> None:
    for tabla in (
        "callbacks",
        "envios_correo",
        "destinatario_tipos",
        "destinatarios",
        "alertas",
        "notificaciones",
        "tipos_notificacion",
        "api_keys",
        "equipos",
    ):
        op.drop_table(tabla)
