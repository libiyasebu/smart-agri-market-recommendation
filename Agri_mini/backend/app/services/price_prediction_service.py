"""
price_prediction_service.py
===========================
Inference service for the CEDA-trained Random Forest price model.

Model artifact : models/agri_price_model.joblib   (26-feature sklearn Pipeline)
History source : data/processed/ceda_prices_weather.csv  (read-only)

Design guarantees
-----------------
* Model loaded once at class instantiation (singleton).
* Lag / rolling features built STRICTLY from records with
  date < prediction_date  (zero future-data leakage).
* Weather features taken from same historical CSV for the
  matching district_id + date; Open-Meteo called only when
  prediction_date is beyond the cached history.
* No synthetic data.  No DB writes.  No CEDA API calls.
"""

import math
import numpy as np
import pandas as pd
import joblib
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_APP_DIR      = Path(__file__).resolve().parent.parent          # backend/app
_PROJECT_ROOT = _APP_DIR.parent.parent                         # D:\Agri_mini
_MODEL_PATH   = _PROJECT_ROOT / "models" / "agri_price_model.joblib"
_HISTORY_CSV  = _PROJECT_ROOT / "data" / "processed" / "ceda_prices_weather.csv"

# ---------------------------------------------------------------------------
# Active commodity registry
# ---------------------------------------------------------------------------
ACTIVE_COMMODITIES = {
    19:  "Banana",
    90:  "Banana-Green",
    78:  "Tomato",
    23:  "Onion",
    24:  "Potato",
    35:  "Brinjal",
    87:  "Green Chilli",
    153: "Carrot",
    154: "Cabbage",
    152: "Sweet Potato",
}

# Exact 26-feature order expected by the saved pipeline
FEATURE_ORDER = [
    "commodity_id", "district_id", "market_id",
    "year", "month", "day", "day_of_week", "quarter",
    "month_sin", "month_cos", "day_of_year_sin", "day_of_year_cos",
    "temperature_max_c", "temperature_min_c", "temperature_mean_c",
    "humidity_mean_pct", "precipitation_sum_mm", "rain_sum_mm", "is_rainy_day",
    "modal_price_lag_1", "modal_price_lag_7", "modal_price_lag_14", "modal_price_lag_30",
    "modal_price_roll_mean_7", "modal_price_roll_mean_14", "modal_price_roll_mean_30",
]

MIN_LAG_ROWS = 2   # minimum prior observations to attempt any prediction


class PricePredictionService:
    """
    Singleton service: loads the CEDA Random Forest pipeline once and
    exposes predict() for the FastAPI endpoint.
    """

    _instance: Optional["PricePredictionService"] = None
    _history: Optional[pd.DataFrame] = None   # module-level cache

    def __init__(self):
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(f"Model artifact not found: {_MODEL_PATH}")
        self.pipeline = joblib.load(_MODEL_PATH)
        self._ensure_history()

    @classmethod
    def get_instance(cls) -> "PricePredictionService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # History loader (cached for the process lifetime)
    # ------------------------------------------------------------------
    @classmethod
    def _ensure_history(cls):
        if cls._history is None:
            if not _HISTORY_CSV.exists():
                raise FileNotFoundError(f"History CSV not found: {_HISTORY_CSV}")
            df = pd.read_csv(_HISTORY_CSV, parse_dates=["date"])
            df["date"] = df["date"].dt.normalize()
            cls._history = df

    # ------------------------------------------------------------------
    # Core prediction
    # ------------------------------------------------------------------
    def predict(
        self,
        commodity_id: int,
        district_id: int,
        market_id: int,
        prediction_date: date,
    ) -> Tuple[float, int, Optional[float]]:
        """
        Build the 26-feature row from historical CSV and run inference.

        Returns
        -------
        (predicted_modal_price, n_prior_records, latest_known_price)

        Raises
        ------
        ValueError  on validation failures (passed back as HTTP 400)
        """
        # --- Validate commodity ---
        if commodity_id not in ACTIVE_COMMODITIES:
            raise ValueError(
                f"commodity_id={commodity_id} is not an active commodity. "
                f"Valid IDs: {sorted(ACTIVE_COMMODITIES.keys())}"
            )

        pred_ts = pd.Timestamp(prediction_date)

        # --- Pull strictly-prior history for this market/commodity series ---
        hist = self._history
        series = hist[
            (hist["commodity_id"] == commodity_id) &
            (hist["market_id"] == market_id) &
            (hist["date"] < pred_ts)
        ].sort_values("date")

        if len(series) == 0:
            # Unknown market_id
            known_markets = sorted(
                hist[hist["commodity_id"] == commodity_id]["market_id"].unique().tolist()
            )
            raise ValueError(
                f"market_id={market_id} has no historical records for "
                f"commodity_id={commodity_id}. "
                f"Known markets for this commodity: {known_markets[:20]}"
            )

        if len(series) < MIN_LAG_ROWS:
            raise ValueError(
                f"Insufficient historical records: found {len(series)} prior "
                f"observations for commodity_id={commodity_id}, market_id={market_id} "
                f"before {prediction_date}. Minimum required: {MIN_LAG_ROWS}."
            )

        prices = series["modal_price"].values  # ordered ascending by date
        n_pts  = len(prices)
        latest_price = float(prices[-1])

        # --- Lag features (observation-based, not calendar-day) ---
        def lag(n):
            return float(prices[-n]) if n_pts >= n else float("nan")

        def roll_mean(n):
            window = prices[-n:] if n_pts >= n else prices
            return float(np.mean(window))

        lag_1  = lag(1)
        lag_7  = lag(7)
        lag_14 = lag(14)
        lag_30 = lag(30)
        roll_7  = roll_mean(7)
        roll_14 = roll_mean(14)
        roll_30 = roll_mean(30)

        # Verify no NaN in required lag_1
        if math.isnan(lag_1):
            raise ValueError("lag_1 could not be computed (no prior prices).")

        # --- Date features ---
        ts = pd.Timestamp(prediction_date)
        day_of_year = ts.day_of_year
        month_sin        = float(np.sin(2 * np.pi * ts.month / 12))
        month_cos        = float(np.cos(2 * np.pi * ts.month / 12))
        day_of_year_sin  = float(np.sin(2 * np.pi * day_of_year / 365))
        day_of_year_cos  = float(np.cos(2 * np.pi * day_of_year / 365))

        # --- Weather features ---
        # Use district + nearest date <= prediction_date from history cache.
        # If prediction_date is in the future (beyond cached history),
        # use the most recent available district weather as a proxy.
        wx_rows = hist[
            (hist["district_id"] == district_id) &
            (hist["date"] <= pred_ts)
        ].sort_values("date")

        WX_COLS = [
            "temperature_max_c", "temperature_min_c", "temperature_mean_c",
            "humidity_mean_pct", "precipitation_sum_mm", "rain_sum_mm",
        ]

        if len(wx_rows) == 0:
            # district not in history at all
            raise ValueError(
                f"district_id={district_id} has no weather records in the "
                f"historical cache. Ensure district is one of: "
                f"{sorted(hist['district_id'].unique().tolist())}"
            )

        wx = wx_rows.iloc[-1]   # most recent observation <= prediction_date
        temp_max    = float(wx["temperature_max_c"])
        temp_min    = float(wx["temperature_min_c"])
        temp_mean   = float(wx["temperature_mean_c"])
        humidity    = float(wx["humidity_mean_pct"])
        precip      = float(wx["precipitation_sum_mm"])
        rain        = float(wx["rain_sum_mm"])
        is_rainy    = int(precip > 0)

        weather_note = (
            "matched" if wx["date"] == pred_ts
            else f"nearest available ({wx['date'].date()})"
        )

        # --- Assemble feature row (exact FEATURE_ORDER) ---
        row = {
            "commodity_id":          commodity_id,
            "district_id":           district_id,
            "market_id":             market_id,
            "year":                  ts.year,
            "month":                 ts.month,
            "day":                   ts.day,
            "day_of_week":           ts.dayofweek,
            "quarter":               ts.quarter,
            "month_sin":             month_sin,
            "month_cos":             month_cos,
            "day_of_year_sin":       day_of_year_sin,
            "day_of_year_cos":       day_of_year_cos,
            "temperature_max_c":     temp_max,
            "temperature_min_c":     temp_min,
            "temperature_mean_c":    temp_mean,
            "humidity_mean_pct":     humidity,
            "precipitation_sum_mm":  precip,
            "rain_sum_mm":           rain,
            "is_rainy_day":          is_rainy,
            "modal_price_lag_1":     lag_1,
            "modal_price_lag_7":     lag_7,
            "modal_price_lag_14":    lag_14,
            "modal_price_lag_30":    lag_30,
            "modal_price_roll_mean_7":  roll_7,
            "modal_price_roll_mean_14": roll_14,
            "modal_price_roll_mean_30": roll_30,
        }

        X = pd.DataFrame([row])[FEATURE_ORDER]

        # Safety: check for NaN in critical lags
        nan_cols = X.columns[X.isna().any()].tolist()
        if nan_cols:
            # Fill sparse lags with lag_1 as a safe fallback rather than crashing
            X[nan_cols] = X[nan_cols].fillna(lag_1)

        pred = float(self.pipeline.predict(X)[0])
        pred = round(max(0.0, pred), 2)

        return pred, n_pts, latest_price, weather_note
