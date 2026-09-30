"""Orden médica: archivo como data URI, fecha de aprobación e historial.

- archivo_url pasa de varchar(300) a text: ahora guarda el archivo de la
  formula (imagen o PDF) codificado en base64 en vez de un link externo, y
  eso facilmente supera un varchar corto.
- aprobado_en: se llena solo al aprobar, para poder calcular hasta cuando es
  valida la autorizacion (aprobado_en + duracion_tratamiento_dias del
  medicamento).
- historial_estado_orden: trazabilidad append-only de cada cambio de estado
  de la orden, mismo patron que historial_estado_domicilio.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260930_04_ips"
down_revision = "20260816_03_ips"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("orden_medica", "archivo_url", type_=sa.Text(), existing_type=sa.String(length=300))
    op.add_column("orden_medica", sa.Column("aprobado_en", sa.DateTime(), nullable=True))

    estado_orden_enum = postgresql.ENUM(
        "PENDIENTE", "APROBADA", "RECHAZADA",
        name="estadoorden",
        create_type=False,
    )
    op.create_table(
        "historial_estado_orden",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("orden_id", sa.Integer(), sa.ForeignKey("orden_medica.id"), nullable=False),
        sa.Column("estado", estado_orden_enum, nullable=False),
        sa.Column("revisado_por", sa.String(length=120), nullable=True),
        sa.Column("registrado_en", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_historial_estado_orden_orden_id", "historial_estado_orden", ["orden_id"])


def downgrade() -> None:
    op.drop_index("ix_historial_estado_orden_orden_id", table_name="historial_estado_orden")
    op.drop_table("historial_estado_orden")
    op.drop_column("orden_medica", "aprobado_en")
    op.alter_column("orden_medica", "archivo_url", type_=sa.String(length=300), existing_type=sa.Text())
