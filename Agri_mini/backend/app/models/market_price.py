from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Date, DateTime, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MarketPrice(Base):
    """SQLAlchemy ORM model for agricultural mandi prices and arrivals (Agmarknet / data.gov.in)."""
    __tablename__ = "market_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    commodity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    variety: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    arrival_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Prices stored as precise Numeric(10, 2) INR per quintal
    min_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    modal_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="data.gov.in (Agmarknet)")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "state", "district", "market", "commodity", "variety", "arrival_date",
            name="uq_market_prices_record"
        ),
        Index("ix_market_prices_commodity_date", "commodity", "arrival_date"),
        Index("ix_market_prices_market_commodity", "market", "commodity"),
    )

    def __repr__(self) -> str:
        return f"<MarketPrice(market='{self.market}', commodity='{self.commodity}', modal={self.modal_price}, date='{self.arrival_date}')>"
