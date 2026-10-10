from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Date, DateTime, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class WeatherRecord(Base):
    """SQLAlchemy ORM model for daily agro-meteorological records (Open-Meteo)."""
    __tablename__ = "weather_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False, index=True)
    longitude: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False, index=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Weather metrics stored with decimal precision
    temp_mean_celsius: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)  # °C
    temp_min_celsius: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)   # °C
    temp_max_celsius: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)   # °C
    humidity_mean_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)  # %
    precipitation_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)   # mm
    rain_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)            # mm
    weather_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)                # WMO Code
    weather_condition: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)       # Descriptive text

    source: Mapped[str] = mapped_column(String(100), nullable=False, default="Open-Meteo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "latitude", "longitude", "record_date",
            name="uq_weather_records_loc_date"
        ),
        Index("ix_weather_records_coords_date", "latitude", "longitude", "record_date"),
    )

    def __repr__(self) -> str:
        return f"<WeatherRecord(lat={self.latitude}, lon={self.longitude}, date='{self.record_date}', temp={self.temp_mean_celsius}°C)>"
