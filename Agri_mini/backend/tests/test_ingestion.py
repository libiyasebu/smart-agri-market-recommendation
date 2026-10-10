import pytest
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import MarketPrice, WeatherRecord, FAOSTATIndicator, RouteRecord
from app.services.ingestion_service import (
    DataIngestionService,
    parse_date_safe,
    to_decimal_safe,
)


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_date_parser_helper():
    assert parse_date_safe("24/08/2026") == date(2026, 8, 24)
    assert parse_date_safe("2026-08-24") == date(2026, 8, 24)
    assert parse_date_safe("24-08-2026") == date(2026, 8, 24)
    assert parse_date_safe(date(2026, 8, 24)) == date(2026, 8, 24)
    assert parse_date_safe(datetime(2026, 8, 24, 10, 30)) == date(2026, 8, 24)


def test_decimal_parser_helper():
    assert to_decimal_safe("2,400.50") == Decimal("2400.50")
    assert to_decimal_safe(1500) == Decimal("1500")
    assert to_decimal_safe(None) is None
    assert to_decimal_safe("") is None


def test_ingest_market_prices(in_memory_db):
    records = [
        {
            "state": "Kerala",
            "district": "Thrissur",
            "market": "Thrissur APMC",
            "commodity": "Tomato",
            "variety": "Hybrid",
            "arrival_date": "2026-08-24",
            "min_price": "2200.00",
            "max_price": "2600.00",
            "modal_price": "2400.00",
            "source": "Agmarknet",
        },
        {
            "state": "Kerala",
            "district": "Ernakulam",
            "market": "Kochi Market",
            "commodity": "Onion",
            "variety": "Red",
            "arrival_date": "2026-08-24",
            "min_price": "2500.00",
            "max_price": "3000.00",
            "modal_price": "2800.00",
            "source": "Agmarknet",
        },
    ]

    res = DataIngestionService.ingest_market_prices(records, in_memory_db)
    assert res["total"] == 2
    assert in_memory_db.query(MarketPrice).count() == 2

    # Test idempotency / update
    updated_records = [
        {
            "state": "Kerala",
            "district": "Thrissur",
            "market": "Thrissur APMC",
            "commodity": "Tomato",
            "variety": "Hybrid",
            "arrival_date": "2026-08-24",
            "min_price": "2300.00",
            "max_price": "2700.00",
            "modal_price": "2500.00",
            "source": "Agmarknet",
        }
    ]

    res_up = DataIngestionService.ingest_market_prices(updated_records, in_memory_db)
    assert res_up["updated"] == 1
    assert in_memory_db.query(MarketPrice).count() == 2
    row = in_memory_db.query(MarketPrice).filter_by(market="Thrissur APMC", commodity="Tomato").first()
    assert row.modal_price == Decimal("2500.00")


def test_ingest_weather_data(in_memory_db):
    payload = {
        "source": "Open-Meteo",
        "location": {"latitude": 10.5276, "longitude": 76.2144},
        "daily_forecasts": [
            {
                "date": "2026-08-24",
                "temp_mean_celsius": 28.5,
                "temp_min_celsius": 24.0,
                "temp_max_celsius": 32.0,
                "humidity_mean_pct": 78.0,
                "precipitation_mm": 5.2,
                "rain_mm": 5.2,
                "weather_code": 61,
                "weather_condition": "Rain: Slight",
            }
        ],
    }

    res = DataIngestionService.ingest_weather_data(payload, in_memory_db, location_name="Thrissur Hub")
    assert res["total"] == 1
    assert in_memory_db.query(WeatherRecord).count() == 1

    row = in_memory_db.query(WeatherRecord).first()
    assert row.location_name == "Thrissur Hub"
    assert row.temp_mean_celsius == Decimal("28.50")
    assert row.weather_code == 61


def test_ingest_faostat_indicators(in_memory_db):
    payload = {
        "status": "success",
        "source": "FAOSTAT (QCL)",
        "records": [
            {
                "area": "India",
                "area_code": 100,
                "item": "Tomatoes",
                "item_code": 388,
                "indicator": "Production",
                "indicator_code": 5510,
                "year": 2022,
                "value": 20694000.0,
                "unit": "t",
                "flag": "A",
                "flag_description": "Official figure",
            }
        ],
    }

    res = DataIngestionService.ingest_faostat_indicators(payload, in_memory_db)
    assert res["total"] == 1
    assert in_memory_db.query(FAOSTATIndicator).count() == 1

    row = in_memory_db.query(FAOSTATIndicator).first()
    assert row.area == "India"
    assert row.value == Decimal("20694000.00")
    assert row.unit == "t"


def test_ingest_route_data(in_memory_db):
    payload = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "origin": {"latitude": 10.5276, "longitude": 76.2144},
        "destination": {"latitude": 9.9312, "longitude": 76.2673},
        "distance_km": 84.89,
        "duration_minutes": 82.95,
        "duration_hours": 1.38,
        "geometry": {
            "type": "LineString",
            "coordinates": [[76.214365, 10.527607], [76.267344, 9.93123]],
            "total_points": 2,
        },
    }

    route_obj = DataIngestionService.ingest_route_data(
        payload, in_memory_db, origin_name="Thrissur", dest_name="Kochi"
    )
    assert route_obj.id is not None
    assert route_obj.distance_km == Decimal("84.89")
    assert route_obj.duration_minutes == Decimal("82.95")
    assert in_memory_db.query(RouteRecord).count() == 1
