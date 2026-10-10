import pytest
import pandas as pd
import numpy as np
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import MarketPrice, WeatherRecord, FAOSTATIndicator, RouteRecord
from app.services.preprocessing_service import DataPreprocessingService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_market_price_cleaning_and_feature_engineering():
    service = DataPreprocessingService()

    raw_data = pd.DataFrame([
        {
            "id": 1,
            "state": "Kerala",
            "district": "Thrissur",
            "market": "Thrissur APMC",
            "commodity": "Tomato",
            "variety": "Hybrid",
            "arrival_date": "2026-08-20",
            "min_price": 2200.0,
            "max_price": 2600.0,
            "modal_price": 2400.0,
            "source": "Agmarknet",
            "created_at": "2026-08-20T10:00:00",
        },
        {
            "id": 2,
            "state": "Kerala",
            "district": "Thrissur",
            "market": "Thrissur APMC",
            "commodity": "Tomato",
            "variety": "Hybrid",
            "arrival_date": "2026-08-21",
            "min_price": 2300.0,
            "max_price": 2700.0,
            "modal_price": 2500.0,
            "source": "Agmarknet",
            "created_at": "2026-08-21T10:00:00",
        },
    ])

    df_clean, stats = service.preprocess_market_prices(raw_data)

    assert stats["input_rows"] == 2
    assert stats["output_rows"] == 2
    assert stats["invalid_rows_filtered"] == 0

    # Verify temporal features
    assert "arrival_day_of_week" in df_clean.columns
    assert "arrival_month" in df_clean.columns
    assert "is_weekend" in df_clean.columns

    # Verify price spreads
    assert df_clean.loc[0, "price_spread"] == 400.0
    assert df_clean.loc[0, "price_spread_pct"] == round((400.0 / 2400.0) * 100.0, 2)

    # Verify rolling and lag features
    assert "price_rolling_mean_3d" in df_clean.columns
    assert "price_lag_1d" in df_clean.columns
    assert "price_change_1d" in df_clean.columns


def test_missing_price_imputation():
    service = DataPreprocessingService()

    # 1. Missing modal_price -> impute as average of min and max
    raw_1 = pd.DataFrame([{
        "state": "Kerala", "district": "Thrissur", "market": "Thrissur", "commodity": "Tomato",
        "variety": "Local", "arrival_date": "2026-08-20",
        "min_price": 2000.0, "max_price": 3000.0, "modal_price": np.nan, "source": "Agmarknet"
    }])
    df1, stats1 = service.preprocess_market_prices(raw_1)
    assert df1.loc[0, "modal_price"] == 2500.0
    assert stats1["missing_values_handled"] == 1

    # 2. Missing min_price -> impute from modal_price
    raw_2 = pd.DataFrame([{
        "state": "Kerala", "district": "Thrissur", "market": "Thrissur", "commodity": "Tomato",
        "variety": "Local", "arrival_date": "2026-08-20",
        "min_price": np.nan, "max_price": 3000.0, "modal_price": 2500.0, "source": "Agmarknet"
    }])
    df2, stats2 = service.preprocess_market_prices(raw_2)
    assert df2.loc[0, "min_price"] == 2500.0


def test_inverted_price_anomaly_correction():
    service = DataPreprocessingService()

    # min_price > max_price (e.g. min=3000, max=2000)
    raw = pd.DataFrame([{
        "state": "Kerala", "district": "Thrissur", "market": "Thrissur", "commodity": "Tomato",
        "variety": "Local", "arrival_date": "2026-08-20",
        "min_price": 3000.0, "max_price": 2000.0, "modal_price": 2500.0, "source": "Agmarknet"
    }])
    df, stats = service.preprocess_market_prices(raw)
    assert df.loc[0, "min_price"] == 2000.0
    assert df.loc[0, "max_price"] == 3000.0
    assert df.loc[0, "price_spread"] == 1000.0


def test_invalid_and_duplicate_rows_handling():
    service = DataPreprocessingService()

    raw = pd.DataFrame([
        # Valid row
        {
            "state": "Kerala", "district": "Thrissur", "market": "Thrissur APMC", "commodity": "Tomato",
            "variety": "Local", "arrival_date": "2026-08-20",
            "min_price": 2000.0, "max_price": 2400.0, "modal_price": 2200.0, "source": "Agmarknet"
        },
        # Duplicate of row 1
        {
            "state": "Kerala", "district": "Thrissur", "market": "Thrissur APMC", "commodity": "Tomato",
            "variety": "Local", "arrival_date": "2026-08-20",
            "min_price": 2000.0, "max_price": 2400.0, "modal_price": 2200.0, "source": "Agmarknet"
        },
        # Corrupted row (negative price)
        {
            "state": "Kerala", "district": "Thrissur", "market": "Thrissur APMC", "commodity": "Tomato",
            "variety": "Local", "arrival_date": "2026-08-21",
            "min_price": -500.0, "max_price": 0.0, "modal_price": -100.0, "source": "Agmarknet"
        },
    ])

    df, stats = service.preprocess_market_prices(raw)
    assert stats["input_rows"] == 3
    assert stats["duplicates_removed"] == 1
    assert stats["invalid_rows_filtered"] == 1
    assert stats["output_rows"] == 1


def test_weather_preprocessing():
    service = DataPreprocessingService()

    raw_weather = pd.DataFrame([
        {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "location_name": "Thrissur",
            "record_date": "2026-08-24",
            "temp_mean_celsius": 28.0,
            "temp_min_celsius": 24.0,
            "temp_max_celsius": 32.0,
            "humidity_mean_pct": 75.0,
            "precipitation_mm": 5.4,
            "rain_mm": 5.4,
            "weather_code": 61,
            "weather_condition": "Rain: Slight",
            "source": "Open-Meteo",
        }
    ])

    df_w = service.preprocess_weather_records(raw_weather)
    assert len(df_w) == 1
    assert df_w.loc[0, "temp_diurnal_range"] == 8.0  # 32 - 24
    assert df_w.loc[0, "is_rainy"] == 1  # precip > 0.1
    assert "weather_month" in df_w.columns


def test_route_preprocessing():
    service = DataPreprocessingService()

    raw_routes = pd.DataFrame([
        {
            "origin_lat": 10.5276,
            "origin_lon": 76.2144,
            "origin_name": "Thrissur",
            "dest_lat": 9.9312,
            "dest_lon": 76.2673,
            "dest_name": "Kochi",
            "distance_km": 84.89,
            "duration_minutes": 82.95,
            "duration_hours": 1.38,
            "geometry_geojson": {},
            "routing_provider": "OSRM",
        }
    ])

    df_r = service.preprocess_route_records(raw_routes)
    assert len(df_r) == 1
    # Speed: 84.89 / 1.38 = ~61.51 km/h
    assert df_r.loc[0, "avg_speed_kmh"] == round(84.89 / 1.38, 2)


def test_full_pipeline_extraction_from_db(test_db):
    # Insert test row in in-memory DB
    item = MarketPrice(
        state="Kerala",
        district="Thrissur",
        market="Thrissur APMC",
        commodity="Tomato",
        variety="Local",
        arrival_date=date(2026, 8, 24),
        min_price=Decimal("2000.00"),
        max_price=Decimal("2400.00"),
        modal_price=Decimal("2200.00"),
        source="Agmarknet",
    )
    test_db.add(item)
    test_db.commit()

    service = DataPreprocessingService(db=test_db)
    res = service.run_pipeline(test_db)

    assert res["status"] == "success"
    assert res["market_prices"]["stats"]["output_rows"] == 1
    assert "price_spread" in res["market_prices"]["features"]
