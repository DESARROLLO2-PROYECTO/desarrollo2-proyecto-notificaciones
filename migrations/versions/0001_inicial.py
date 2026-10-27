"""Tablas, catálogo de tipos sembrado y UNIQUE parcial de alerta activa.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("rol", sa.String(20), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activa", sa.Boolean, nullable=False),
    )
    tipos = op.create_table(
        "tipos_notificacion",
        sa.Column("nombre", sa.String(50), primary_key=True),
        sa.Column("emisor", sa.String(20), nullable=False),
        sa.Column("destino", sa.String(20), nullable=False),
        sa.Column("expiracion_min", sa.Integer, nullable=False),
    )
    columnas = ("nombre", "emisor", "destino", "expiracion_min")
    op.bulk_insert(
        tipos,
        [
            dict(zip(columnas, fila, strict=True))
            for fila in [
                ("STOCK_BAJO_INSUMO", "inventario", "inventario", 1440),
                ("STOCK_BAJO_PRODUCTO", "inventario", "fabricacion", 1440),
                ("CONDICION_URGENTE", "fabricacion", "fabricacion", 60),
                ("ACUMULACION_PEDIDOS", "inventario", "inventario", 60),
            ]
        ],
    )
    op.create_table(
        "notificaciones",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tipo", sa.String(50), sa.ForeignKey("tipos_notificacion.nombre"), nullable=False
        ),
        sa.Column("destino", sa.String(20), nullable=False),
        sa.Column("producto_id", sa.String(50), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("stock_actual", sa.Integer, nullable=False),
        sa.Column("stock_minimo", sa.Integer, nullable=False),
        sa.Column("fecha_registro", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notificaciones_destino", "notificaciones", ["destino"])
    op.create_table(
        "alertas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tipo", sa.String(50), sa.ForeignKey("tipos_notificacion.nombre"), nullable=False
        ),
        sa.Column("clave", sa.String(50), nullable=False),
        sa.Column("notificacion_id", sa.Uuid, sa.ForeignKey("notificaciones.id"), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resuelta_en", sa.DateTime(timezone=True)),
        sa.Column("motivo_resolucion", sa.String(20)),
    )
    op.create_index(
        "uq_alerta_activa",
        "alertas",
        ["tipo", "clave"],
        unique=True,
        postgresql_where=sa.text("resuelta_en IS NULL"),
    )


def downgrade() -> None:
    for tabla in ("alertas", "notificaciones", "tipos_notificacion", "api_keys"):
        op.drop_table(tabla)
