from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import String, Integer, Numeric, DateTime, JSON, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RouteRecord(Base):
    """SQLAlchemy ORM model for road network distances, durations, and GeoJSON geometries (OSRM)."""
    __tablename__ = "route_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_lat: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False, index=True)
    origin_lon: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False, index=True)
    origin_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    
    dest_lat: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False, index=True)
    dest_lon: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False, index=True)
    dest_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # Road logistics metrics
    distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duration_minutes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duration_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Route geometry stored as structured JSON
    geometry_geojson: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    routing_provider: Mapped[str] = mapped_column(String(100), nullable=False, default="OSRM (OpenStreetMap)")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_route_records_origin_dest", "origin_lat", "origin_lon", "dest_lat", "dest_lon"),
    )

    def __repr__(self) -> str:
        return f"<RouteRecord(from='({self.origin_lat}, {self.origin_lon})', to='({self.dest_lat}, {self.dest_lon})', dist={self.distance_km}km, dur={self.duration_minutes}m)>"
