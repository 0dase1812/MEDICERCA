"""Registro sanitario del medicamento: unico.

Se ha duplicado dos veces en produccion por correr el mismo script de seed
o de migracion manual mas de una vez (sin este candado, nada lo impedia).
Antes de crear la restriccion se borran duplicados que ya existan,
quedandose con la fila de menor id (la mas antigua) en cada caso.
"""
from alembic import op

revision = "20260930_05_central"
down_revision = "20260930_04_central"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM medicamento a USING medicamento b
        WHERE a.registro_sanitario = b.registro_sanitario AND a.id > b.id
        """
    )
    op.create_unique_constraint("uq_medicamento_registro_sanitario", "medicamento", ["registro_sanitario"])


def downgrade() -> None:
    op.drop_constraint("uq_medicamento_registro_sanitario", "medicamento", type_="unique")
