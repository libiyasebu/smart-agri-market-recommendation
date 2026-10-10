from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, DateTime, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FAOSTATIndicator(Base):
    """SQLAlchemy ORM model for macro agricultural production and yield benchmarks (FAOSTAT UN)."""
    __tablename__ = "faostat_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    area_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    commodity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    indicator_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Large metrics (e.g. National Production in Tonnes) stored with high precision
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    flag: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    flag_description: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    source: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "area_code", "item_code", "indicator_code", "year",
            name="uq_faostat_indicators_metric"
        ),
        Index("ix_faostat_item_indicator_year", "item_code", "indicator_code", "year"),
    )

    def __repr__(self) -> str:
        return f"<FAOSTATIndicator(area='{self.area}', item='{self.commodity}', indicator='{self.indicator}', year={self.year}, value={self.value} {self.unit})>"
