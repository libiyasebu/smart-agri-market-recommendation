from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from app.models import MarketPrice, WeatherRecord, FAOSTATIndicator, RouteRecord


class DataPreprocessingService:
    """Service to extract, clean, validate, and engineer features from PostgreSQL tables."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    # -------------------------------------------------------------------------
    # 1. Extraction from Database
    # -------------------------------------------------------------------------

    def extract_market_prices_df(self, db: Optional[Session] = None) -> pd.DataFrame:
        """Extracts all market price records from PostgreSQL into a pandas DataFrame."""
        session = db or self.db
        if not session:
            raise ValueError("A valid SQLAlchemy database session is required for extraction.")

        records = session.query(MarketPrice).all()
        if not records:
            return pd.DataFrame()

        data = [
            {
                "id": r.id,
                "state": r.state,
                "district": r.district,
                "market": r.market,
                "commodity": r.commodity,
                "variety": r.variety,
                "arrival_date": r.arrival_date,
                "min_price": float(r.min_price) if r.min_price is not None else np.nan,
                "max_price": float(r.max_price) if r.max_price is not None else np.nan,
                "modal_price": float(r.modal_price) if r.modal_price is not None else np.nan,
                "source": r.source,
                "created_at": r.created_at,
            }
            for r in records
        ]
        return pd.DataFrame(data)

    def extract_weather_records_df(self, db: Optional[Session] = None) -> pd.DataFrame:
        """Extracts all weather records from PostgreSQL into a pandas DataFrame."""
        session = db or self.db
        if not session:
            raise ValueError("A valid SQLAlchemy database session is required for extraction.")

        records = session.query(WeatherRecord).all()
        if not records:
            return pd.DataFrame()

        data = [
            {
                "id": r.id,
                "latitude": float(r.latitude) if r.latitude is not None else np.nan,
                "longitude": float(r.longitude) if r.longitude is not None else np.nan,
                "location_name": r.location_name,
                "record_date": r.record_date,
                "temp_mean_celsius": float(r.temp_mean_celsius) if r.temp_mean_celsius is not None else np.nan,
                "temp_min_celsius": float(r.temp_min_celsius) if r.temp_min_celsius is not None else np.nan,
                "temp_max_celsius": float(r.temp_max_celsius) if r.temp_max_celsius is not None else np.nan,
                "humidity_mean_pct": float(r.humidity_mean_pct) if r.humidity_mean_pct is not None else np.nan,
                "precipitation_mm": float(r.precipitation_mm) if r.precipitation_mm is not None else np.nan,
                "rain_mm": float(r.rain_mm) if r.rain_mm is not None else np.nan,
                "weather_code": r.weather_code,
                "weather_condition": r.weather_condition,
                "source": r.source,
            }
            for r in records
        ]
        return pd.DataFrame(data)

    def extract_faostat_indicators_df(self, db: Optional[Session] = None) -> pd.DataFrame:
        """Extracts all FAOSTAT macro agricultural indicators from PostgreSQL into a pandas DataFrame."""
        session = db or self.db
        if not session:
            raise ValueError("A valid SQLAlchemy database session is required for extraction.")

        records = session.query(FAOSTATIndicator).all()
        if not records:
            return pd.DataFrame()

        data = [
            {
                "id": r.id,
                "area": r.area,
                "area_code": r.area_code,
                "commodity": r.commodity,
                "item_code": r.item_code,
                "indicator": r.indicator,
                "indicator_code": r.indicator_code,
                "year": r.year,
                "value": float(r.value) if r.value is not None else np.nan,
                "unit": r.unit,
                "flag": r.flag,
                "flag_description": r.flag_description,
                "source": r.source,
            }
            for r in records
        ]
        return pd.DataFrame(data)

    def extract_route_records_df(self, db: Optional[Session] = None) -> pd.DataFrame:
        """Extracts all route logistics records from PostgreSQL into a pandas DataFrame."""
        session = db or self.db
        if not session:
            raise ValueError("A valid SQLAlchemy database session is required for extraction.")

        records = session.query(RouteRecord).all()
        if not records:
            return pd.DataFrame()

        data = [
            {
                "id": r.id,
                "origin_lat": float(r.origin_lat) if r.origin_lat is not None else np.nan,
                "origin_lon": float(r.origin_lon) if r.origin_lon is not None else np.nan,
                "origin_name": r.origin_name,
                "dest_lat": float(r.dest_lat) if r.dest_lat is not None else np.nan,
                "dest_lon": float(r.dest_lon) if r.dest_lon is not None else np.nan,
                "dest_name": r.dest_name,
                "distance_km": float(r.distance_km) if r.distance_km is not None else np.nan,
                "duration_minutes": float(r.duration_minutes) if r.duration_minutes is not None else np.nan,
                "duration_hours": float(r.duration_hours) if r.duration_hours is not None else np.nan,
                "geometry_geojson": r.geometry_geojson,
                "routing_provider": r.routing_provider,
            }
            for r in records
        ]
        return pd.DataFrame(data)

    # -------------------------------------------------------------------------
    # 2. Market Price Cleaning & Feature Engineering
    # -------------------------------------------------------------------------

    def preprocess_market_prices(
        self, df_raw: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Cleans, validates, and engineers feature columns for market prices.

        Returns:
            Tuple of (cleaned_and_featured_dataframe, stats_dictionary)
        """
        if df_raw.empty:
            return pd.DataFrame(), {
                "input_rows": 0,
                "output_rows": 0,
                "invalid_rows_filtered": 0,
                "missing_values_handled": 0,
                "duplicates_removed": 0,
            }

        df = df_raw.copy()
        input_rows = len(df)
        missing_handled = 0
        invalid_filtered = 0

        # 1. Parse and standardize arrival_date
        df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
        null_date_mask = df["arrival_date"].isna()
        if null_date_mask.any():
            invalid_filtered += int(null_date_mask.sum())
            df = df[~null_date_mask].copy()

        # 2. Safe string stripping
        for col in ["state", "district", "market", "commodity", "variety"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # 3. Deduplication on composite keys
        dup_subset = ["state", "district", "market", "commodity", "variety", "arrival_date"]
        initial_count = len(df)
        df = df.drop_duplicates(subset=dup_subset, keep="last").copy()
        duplicates_removed = initial_count - len(df)

        # 4. Handle missing prices
        # Modal price imputation if min and max exist
        modal_na = df["modal_price"].isna() | (df["modal_price"] <= 0)
        min_valid = df["min_price"].notna() & (df["min_price"] > 0)
        max_valid = df["max_price"].notna() & (df["max_price"] > 0)

        impute_modal_mask = modal_na & min_valid & max_valid
        if impute_modal_mask.any():
            df.loc[impute_modal_mask, "modal_price"] = (
                df.loc[impute_modal_mask, "min_price"] + df.loc[impute_modal_mask, "max_price"]
            ) / 2.0
            missing_handled += int(impute_modal_mask.sum())

        # Impute missing min_price with modal_price
        min_na = df["min_price"].isna() | (df["min_price"] <= 0)
        impute_min_mask = min_na & df["modal_price"].notna() & (df["modal_price"] > 0)
        if impute_min_mask.any():
            df.loc[impute_min_mask, "min_price"] = df.loc[impute_min_mask, "modal_price"]
            missing_handled += int(impute_min_mask.sum())

        # Impute missing max_price with modal_price
        max_na = df["max_price"].isna() | (df["max_price"] <= 0)
        impute_max_mask = max_na & df["modal_price"].notna() & (df["modal_price"] > 0)
        if impute_max_mask.any():
            df.loc[impute_max_mask, "max_price"] = df.loc[impute_max_mask, "modal_price"]
            missing_handled += int(impute_max_mask.sum())

        # 5. Filter out corrupted/non-positive prices
        valid_prices = (
            df["modal_price"].notna() & (df["modal_price"] > 0) &
            df["min_price"].notna() & (df["min_price"] > 0) &
            df["max_price"].notna() & (df["max_price"] > 0)
        )
        invalid_prices_count = int((~valid_prices).sum())
        invalid_filtered += invalid_prices_count
        df = df[valid_prices].copy()

        # 6. Correct min_price > max_price anomalies (swap if inverted)
        inverted_mask = df["min_price"] > df["max_price"]
        if inverted_mask.any():
            temp_min = df.loc[inverted_mask, "min_price"]
            df.loc[inverted_mask, "min_price"] = df.loc[inverted_mask, "max_price"]
            df.loc[inverted_mask, "max_price"] = temp_min
            missing_handled += int(inverted_mask.sum())

        # 7. Engineer Temporal Features
        df["arrival_year"] = df["arrival_date"].dt.year
        df["arrival_month"] = df["arrival_date"].dt.month
        df["arrival_day"] = df["arrival_date"].dt.day
        df["arrival_day_of_week"] = df["arrival_date"].dt.dayofweek  # 0=Mon, 6=Sun
        df["arrival_quarter"] = df["arrival_date"].dt.quarter
        df["arrival_day_of_year"] = df["arrival_date"].dt.dayofyear
        df["is_weekend"] = df["arrival_day_of_week"].isin([5, 6]).astype(int)

        # 8. Engineer Price Spread and Ratio Features
        df["price_spread"] = (df["max_price"] - df["min_price"]).round(2)
        df["price_spread_pct"] = (
            (df["price_spread"] / df["modal_price"]) * 100.0
        ).round(2).clip(lower=0.0)
        df["price_to_min_ratio"] = (df["modal_price"] / df["min_price"]).round(4)
        df["price_to_max_ratio"] = (df["modal_price"] / df["max_price"]).round(4)

        # 9. Sort by commodity, market, and date for lag/rolling features
        df = df.sort_values(by=["market", "commodity", "variety", "arrival_date"]).reset_index(drop=True)

        # 10. Rolling and Lag Features per (market, commodity)
        grouped = df.groupby(["market", "commodity"], group_keys=False)
        
        # 3-day rolling mean modal price
        df["price_rolling_mean_3d"] = grouped["modal_price"].transform(
            lambda s: s.rolling(window=3, min_periods=1).mean().round(2)
        )
        # 7-day rolling mean modal price
        df["price_rolling_mean_7d"] = grouped["modal_price"].transform(
            lambda s: s.rolling(window=7, min_periods=1).mean().round(2)
        )
        # 7-day rolling standard deviation (volatility)
        df["price_rolling_std_7d"] = grouped["modal_price"].transform(
            lambda s: s.rolling(window=7, min_periods=1).std().fillna(0.0).round(2)
        )
        # 1-day price lag
        df["price_lag_1d"] = grouped["modal_price"].shift(1)
        # Fill first observation lag with current modal price to avoid nulls
        df["price_lag_1d"] = df["price_lag_1d"].fillna(df["modal_price"]).round(2)
        # Daily price momentum / change
        df["price_change_1d"] = (df["modal_price"] - df["price_lag_1d"]).round(2)

        stats = {
            "input_rows": input_rows,
            "output_rows": len(df),
            "invalid_rows_filtered": invalid_filtered,
            "missing_values_handled": missing_handled,
            "duplicates_removed": duplicates_removed,
        }

        return df, stats

    # -------------------------------------------------------------------------
    # 3. Weather Cleaning & Feature Engineering
    # -------------------------------------------------------------------------

    def preprocess_weather_records(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Cleans and prepares weather records with agro-meteorological features."""
        if df_raw.empty:
            return pd.DataFrame()

        df = df_raw.copy()
        df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce")
        df = df.dropna(subset=["record_date"]).copy()

        # Deduplicate on coordinates and date
        df = df.drop_duplicates(subset=["latitude", "longitude", "record_date"], keep="last").copy()

        # Diurnal temperature range (°C)
        df["temp_diurnal_range"] = (df["temp_max_celsius"] - df["temp_min_celsius"]).round(2)
        
        # Binary indicator for wet/rainy condition
        df["is_rainy"] = (df["precipitation_mm"] > 0.1).astype(int)

        # Date features
        df["weather_month"] = df["record_date"].dt.month
        df["weather_day_of_week"] = df["record_date"].dt.dayofweek

        return df.sort_values(by=["latitude", "longitude", "record_date"]).reset_index(drop=True)

    # -------------------------------------------------------------------------
    # 4. FAOSTAT Indicators Preparation
    # -------------------------------------------------------------------------

    def preprocess_faostat_indicators(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Cleans and formats national agricultural macro statistics."""
        if df_raw.empty:
            return pd.DataFrame()

        df = df_raw.copy()
        df = df.dropna(subset=["commodity", "indicator", "year", "value"]).copy()
        df = df.drop_duplicates(subset=["area_code", "item_code", "indicator_code", "year"], keep="last").copy()
        return df.sort_values(by=["commodity", "indicator", "year"]).reset_index(drop=True)

    # -------------------------------------------------------------------------
    # 5. Route Logistics Preparation
    # -------------------------------------------------------------------------

    def preprocess_route_records(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Cleans and formats road logistics and transportation metrics."""
        if df_raw.empty:
            return pd.DataFrame()

        df = df_raw.copy()
        df = df.dropna(subset=["distance_km", "duration_hours"]).copy()

        # Calculate average transit speed (km/h)
        df["avg_speed_kmh"] = np.where(
            df["duration_hours"] > 0,
            (df["distance_km"] / df["duration_hours"]).round(2),
            0.0
        )

        return df.reset_index(drop=True)

    # -------------------------------------------------------------------------
    # 6. Master Preprocessing Pipeline
    # -------------------------------------------------------------------------

    def run_pipeline(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Executes end-to-end data extraction, cleaning, validation, and feature
        engineering across all 4 database tables.
        """
        session = db or self.db
        if not session:
            raise ValueError("A database session must be provided to run the pipeline.")

        # Extract
        raw_market = self.extract_market_prices_df(session)
        raw_weather = self.extract_weather_records_df(session)
        raw_faostat = self.extract_faostat_indicators_df(session)
        raw_routes = self.extract_route_records_df(session)

        # Preprocess
        clean_market, market_stats = self.preprocess_market_prices(raw_market)
        clean_weather = self.preprocess_weather_records(raw_weather)
        clean_faostat = self.preprocess_faostat_indicators(raw_faostat)
        clean_routes = self.preprocess_route_records(raw_routes)

        return {
            "status": "success",
            "market_prices": {
                "stats": market_stats,
                "features": list(clean_market.columns) if not clean_market.empty else [],
                "sample_rows": clean_market.head(5).to_dict(orient="records") if not clean_market.empty else [],
                "dataframe": clean_market,
            },
            "weather_records": {
                "total_rows": len(clean_weather),
                "features": list(clean_weather.columns) if not clean_weather.empty else [],
                "dataframe": clean_weather,
            },
            "faostat_indicators": {
                "total_rows": len(clean_faostat),
                "commodities": clean_faostat["commodity"].unique().tolist() if not clean_faostat.empty else [],
                "dataframe": clean_faostat,
            },
            "route_records": {
                "total_routes": len(clean_routes),
                "corridors": [
                    f"{r['origin_name']} -> {r['dest_name']}" for _, r in clean_routes.iterrows()
                ] if not clean_routes.empty else [],
                "dataframe": clean_routes,
            },
        }
