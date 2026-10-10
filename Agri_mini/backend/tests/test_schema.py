import pytest
from sqlalchemy import create_engine, Numeric, Integer, String, Date, DateTime, JSON
from app.database import Base
from app.models import MarketPrice, WeatherRecord, FAOSTATIndicator, RouteRecord


def test_models_metadata_registered():
    tables = Base.metadata.tables
    assert "market_prices" in tables
    assert "weather_records" in tables
    assert "faostat_indicators" in tables
    assert "route_records" in tables


def test_market_price_model_schema():
    table = MarketPrice.__table__
    assert table.name == "market_prices"
    
    # Check PK
    pk_cols = [c.name for c in table.primary_key.columns]
    assert pk_cols == ["id"]

    # Check precision types
    assert isinstance(table.c.min_price.type, Numeric)
    assert isinstance(table.c.max_price.type, Numeric)
    assert isinstance(table.c.modal_price.type, Numeric)
    assert isinstance(table.c.arrival_date.type, Date)

    # Check unique constraint
    uq_names = [uq.name for uq in table.constraints if hasattr(uq, "name") and uq.name]
    assert "uq_market_prices_record" in uq_names


def test_weather_record_model_schema():
    table = WeatherRecord.__table__
    assert table.name == "weather_records"

    # Check PK
    assert [c.name for c in table.primary_key.columns] == ["id"]

    # Check precision types
    assert isinstance(table.c.latitude.type, Numeric)
    assert isinstance(table.c.longitude.type, Numeric)
    assert isinstance(table.c.temp_mean_celsius.type, Numeric)
    assert isinstance(table.c.humidity_mean_pct.type, Numeric)
    assert isinstance(table.c.precipitation_mm.type, Numeric)
    assert isinstance(table.c.record_date.type, Date)

    # Check unique constraint
    uq_names = [uq.name for uq in table.constraints if hasattr(uq, "name") and uq.name]
    assert "uq_weather_records_loc_date" in uq_names


def test_faostat_indicator_model_schema():
    table = FAOSTATIndicator.__table__
    assert table.name == "faostat_indicators"

    assert [c.name for c in table.primary_key.columns] == ["id"]
    assert isinstance(table.c.value.type, Numeric)
    assert isinstance(table.c.year.type, Integer)

    uq_names = [uq.name for uq in table.constraints if hasattr(uq, "name") and uq.name]
    assert "uq_faostat_indicators_metric" in uq_names


def test_route_record_model_schema():
    table = RouteRecord.__table__
    assert table.name == "route_records"

    assert [c.name for c in table.primary_key.columns] == ["id"]
    assert isinstance(table.c.distance_km.type, Numeric)
    assert isinstance(table.c.duration_minutes.type, Numeric)
    assert isinstance(table.c.duration_hours.type, Numeric)
    assert isinstance(table.c.geometry_geojson.type, JSON)


def test_in_memory_ddl_creation():
    # Verify DDL compiles cleanly across all models in SQLite in-memory engine
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    assert "market_prices" in table_names
    assert "weather_records" in table_names
    assert "faostat_indicators" in table_names
    assert "route_records" in table_names
    engine.dispose()
