import enum

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CondicionVenta(str, enum.Enum):
    """Decreto 677 de 1995: mecanismos de comercialización autorizados."""
    RX = "RX"     # requiere fórmula médica
    OTC = "OTC"   # venta libre


class Medicamento(Base):
    """
    Catálogo NACIONAL de medicamentos (vive en la base central).
    No tiene relación directa a inventario: cada IPS referencia este id
    "sueltamente" desde su propia base de datos (ver app/models_ips.py),
    simulando que el registro INVIMA es único pero el stock es de cada IPS.
    """
    __tablename__ = "medicamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_generico: Mapped[str] = mapped_column(String(150), index=True)
    nombre_comercial: Mapped[str] = mapped_column(String(150))
    dosis: Mapped[str] = mapped_column(String(50))
    presentacion: Mapped[str] = mapped_column(String(80))
    condicion_venta: Mapped[CondicionVenta] = mapped_column(Enum(CondicionVenta))
    control_especial: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ley 9 de 1979. Unico: ya se duplico dos veces en produccion por correr
    # el mismo script de seed/migracion mas de una vez, asi que la base de
    # datos misma debe impedirlo en vez de confiar en que nadie se equivoque.
    registro_sanitario: Mapped[str] = mapped_column(String(50), unique=True)
    # Información de posología para que el paciente sepa cómo tomarlo y cuánto
    # le corresponde por entrega, sin tener que interpretar la orden médica.
    indicaciones_uso: Mapped[str] = mapped_column(String(300))
    cantidad_por_entrega: Mapped[str] = mapped_column(String(100))
    duracion_tratamiento_dias: Mapped[int] = mapped_column(Integer)
