"""Agrega el estado CANCELADO al enum de domicilio.

Sin esto no existia forma de deshacer un domicilio pedido por error: una
vez creado, quedaba ahi para siempre (y desde que se agrego la regla de
"una orden = un domicilio", ni siquiera se podia volver a pedir).
"""
from alembic import op

revision = "20260930_05_ips"
down_revision = "20260930_04_ips"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE estadodomicilio ADD VALUE IF NOT EXISTS 'CANCELADO'")


def downgrade() -> None:
    # Postgres no soporta quitarle un valor a un enum directamente; revertir
    # esto a mano requeriria recrear el tipo. No es necesario para este
    # proyecto, asi que se deja como no-op documentado.
    pass
