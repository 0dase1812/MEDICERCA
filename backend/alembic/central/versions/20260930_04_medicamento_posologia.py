"""Add posologia fields to medicamento.

Antes, el catalogo solo tenia dosis/presentacion pero no decia con que
frecuencia se toma ni cuanto se entrega por autorizacion (ej. "2 cajas para
1 mes"). Se agregan tres columnas para que el paciente sepa como tomarlo y
para poder calcular hasta cuando es valida una orden ya aprobada.

Las tres quedan NOT NULL: se rellenan con un valor generico para las filas
existentes y luego se editan con datos reales via el seed o el catalogo.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260930_04_central"
down_revision = "20260813_03_central"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "medicamento",
        sa.Column("indicaciones_uso", sa.String(length=300), nullable=False, server_default="Según indicación médica."),
    )
    op.add_column(
        "medicamento",
        sa.Column("cantidad_por_entrega", sa.String(length=100), nullable=False, server_default="1 unidad"),
    )
    op.add_column(
        "medicamento",
        sa.Column("duracion_tratamiento_dias", sa.Integer(), nullable=False, server_default="30"),
    )
    # Los server_default eran solo para poder agregar la columna NOT NULL
    # sobre filas existentes; no queremos que apliquen a inserts futuros
    # desde la aplicación (que siempre manda un valor real explicito).
    op.alter_column("medicamento", "indicaciones_uso", server_default=None)
    op.alter_column("medicamento", "cantidad_por_entrega", server_default=None)
    op.alter_column("medicamento", "duracion_tratamiento_dias", server_default=None)


def downgrade() -> None:
    op.drop_column("medicamento", "duracion_tratamiento_dias")
    op.drop_column("medicamento", "cantidad_por_entrega")
    op.drop_column("medicamento", "indicaciones_uso")
