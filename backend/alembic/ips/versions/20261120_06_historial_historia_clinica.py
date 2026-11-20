"""Add historial_historia_clinica table.

Registro append-only de cada creacion, edicion o retiro de un diagnostico o
una prescripcion (Sprint 3, HU-S3-02). Antes de esta migracion no habia
forma de sustentar ante una auditoria o un regente que cambio, quien lo
hizo y cuando, a pesar de que la historia clinica es informacion sensible.

Es intencionalmente una tabla simple (sin updated_at, sin borrado logico):
nunca se edita ni se borra una fila existente, solo se agregan nuevas —
mismo patron ya usado en historial_estado_domicilio e
historial_estado_orden.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261120_06_ips"
down_revision = "20260930_05_ips"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historial_historia_clinica",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("historia_id", sa.Integer(), sa.ForeignKey("historia_clinica.id"), nullable=False),
        sa.Column("entidad", sa.String(length=20), nullable=False),
        sa.Column("entidad_id", sa.Integer(), nullable=True),
        sa.Column("accion", sa.String(length=20), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_nuevo", sa.Text(), nullable=True),
        sa.Column("autor", sa.String(length=120), nullable=False),
        sa.Column("registrado_en", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_historial_historia_clinica_historia_id",
        "historial_historia_clinica",
        ["historia_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_historial_historia_clinica_historia_id", table_name="historial_historia_clinica")
    op.drop_table("historial_historia_clinica")
