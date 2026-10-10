import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
import joblib
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import MarketPrice, WeatherRecord, FAOSTATIndicator, RouteRecord
from app.schemas.prediction import PricePredictionRequest, PricePredictionResponse


class PredictionService:
    """
    Inference service for Agricultural Modal Price Prediction.
    Loads and caches trained model artifacts, performs leakage-free
    feature preparation from PostgreSQL history, and executes inference.
    """

    _instance: Optional["PredictionService"] = None

    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = artifacts_dir or (Path(__file__).resolve().parent.parent.parent / "artifacts")
        self.model = None
        self.encoder = None
        self.scaler = None
        self.metadata = {}
        self.feature_names: List[str] = []
        self.numerical_features: List[str] = []
        self.categorical_features: List[str] = []
        self._load_artifacts()

    @classmethod
    def get_instance(cls, artifacts_dir: Optional[Path] = None) -> "PredictionService":
        """Singleton accessor to prevent reloading artifacts on every HTTP request."""
        if cls._instance is None:
            cls._instance = cls(artifacts_dir=artifacts_dir)
        return cls._instance

    # -------------------------------------------------------------------------
    # 1. Artifact Loading & Validation
    # -------------------------------------------------------------------------

    def _load_artifacts(self):
        """Loads and strictly validates model, preprocessor, and metadata artifacts."""
        model_path = self.artifacts_dir / "best_price_model.joblib"
        preprocessor_path = self.artifacts_dir / "preprocessor.joblib"
        metadata_path = self.artifacts_dir / "model_metadata.json"

        if not model_path.exists():
            raise FileNotFoundError(f"Model artifact not found at: {model_path}")
        if not preprocessor_path.exists():
            raise FileNotFoundError(f"Preprocessor artifact not found at: {preprocessor_path}")
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata artifact not found at: {metadata_path}")

        # Load metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        # Validate metadata schema
        target = self.metadata.get("target_variable")
        if target != "modal_price":
            raise ValueError(f"Incompatible model target '{target}'. Expected 'modal_price'.")

        # Load preprocessor
        prep_data = joblib.load(preprocessor_path)
        self.encoder = prep_data["encoder"]
        self.scaler = prep_data["scaler"]
        self.feature_names = prep_data["feature_names"]
        self.numerical_features = prep_data["numerical_features"]
        self.categorical_features = ["commodity", "market", "district", "state", "variety"]

        if len(self.feature_names) != 54:
            raise ValueError(f"Expected 54 model features, found {len(self.feature_names)}.")

        # Load trained production model
        self.model = joblib.load(model_path)

    # -------------------------------------------------------------------------
    # 2. Historical Feature Derivation (Zero Leakage)
    # -------------------------------------------------------------------------

    def derive_historical_features(
        self,
        request: PricePredictionRequest,
        db: Session,
    ) -> Tuple[Dict[str, float], int, Optional[float]]:
        """
        Queries historical market records strictly prior to prediction_date
        to calculate shifted lag-1d price, rolling means, and volatility.
        """
        # 1. Query records matching commodity and market before prediction_date
        query = (
            db.query(MarketPrice)
            .filter(
                func.lower(MarketPrice.commodity) == func.lower(request.commodity),
                func.lower(MarketPrice.market) == func.lower(request.market),
                MarketPrice.arrival_date < request.prediction_date,
            )
            .order_by(MarketPrice.arrival_date.asc())
        )
        records = query.all()

        # Fallback 1: match by commodity and district if specific market has no prior data
        if not records:
            query_district = (
                db.query(MarketPrice)
                .filter(
                    func.lower(MarketPrice.commodity) == func.lower(request.commodity),
                    func.lower(MarketPrice.district) == func.lower(request.district),
                    MarketPrice.arrival_date < request.prediction_date,
                )
                .order_by(MarketPrice.arrival_date.asc())
            )
            records = query_district.all()

        # Fallback 2: match by commodity anywhere in state
        if not records:
            query_state = (
                db.query(MarketPrice)
                .filter(
                    func.lower(MarketPrice.commodity) == func.lower(request.commodity),
                    MarketPrice.arrival_date < request.prediction_date,
                )
                .order_by(MarketPrice.arrival_date.asc())
            )
            records = query_state.all()

        if not records:
            raise ValueError(
                f"Insufficient historical price records for commodity '{request.commodity}' "
                f"in market '{request.market}' prior to {request.prediction_date}."
            )

        prices = [float(r.modal_price) for r in records if r.modal_price is not None and float(r.modal_price) > 0]
        if not prices:
            raise ValueError(f"No valid numerical historical prices recorded for '{request.commodity}'.")

        n_pts = len(prices)
        latest_price = prices[-1]
        lag_1d = prices[-1]
        roll_3d = float(np.mean(prices[-3:]))
        roll_7d = float(np.mean(prices[-7:]))
        roll_std_7d = float(np.std(prices[-7:])) if len(prices[-7:]) >= 2 else 0.0
        momentum_1d = float(prices[-1] - prices[-2]) if n_pts >= 2 else 0.0

        hist_features = {
            "hist_lag_1d_price": lag_1d,
            "hist_rolling_mean_3d": roll_3d,
            "hist_rolling_mean_7d": roll_7d,
            "hist_rolling_std_7d": roll_std_7d,
            "hist_price_momentum_1d": momentum_1d,
        }

        return hist_features, n_pts, latest_price

    # -------------------------------------------------------------------------
    # 3. Contextual Features Integration (Weather, FAOSTAT, Route)
    # -------------------------------------------------------------------------

    def get_contextual_features(
        self,
        request: PricePredictionRequest,
        db: Session,
    ) -> Tuple[Dict[str, float], bool, bool, bool]:
        """
        Retrieves matching weather, FAOSTAT, and route features or applies default medians.
        """
        # A. Weather lookup
        weather_matched = False
        weather_dict = {
            "temp_mean_celsius": 28.5,
            "temp_min_celsius": 24.0,
            "temp_max_celsius": 32.5,
            "temp_diurnal_range": 8.5,
            "humidity_mean_pct": 82.0,
            "precipitation_mm": 5.0,
            "rain_mm": 5.0,
            "is_rainy": 1.0,
            "weather_matched": 0.0,
        }

        w_rec = (
            db.query(WeatherRecord)
            .filter(
                func.lower(WeatherRecord.location_name).like(f"%{request.district.lower()}%"),
                WeatherRecord.record_date <= request.prediction_date,
            )
            .order_by(WeatherRecord.record_date.desc())
            .first()
        )
        if w_rec:
            weather_matched = True
            t_mean = float(w_rec.temp_mean_celsius or 28.5)
            t_min = float(w_rec.temp_min_celsius or (t_mean - 4.0))
            t_max = float(w_rec.temp_max_celsius or (t_mean + 4.0))
            rain = float(w_rec.rain_mm or w_rec.precipitation_mm or 0.0)
            weather_dict = {
                "temp_mean_celsius": t_mean,
                "temp_min_celsius": t_min,
                "temp_max_celsius": t_max,
                "temp_diurnal_range": t_max - t_min,
                "humidity_mean_pct": float(w_rec.humidity_mean_pct or 82.0),
                "precipitation_mm": rain,
                "rain_mm": rain,
                "is_rainy": 1.0 if rain > 1.0 else 0.0,
                "weather_matched": 1.0,
            }

        # B. FAOSTAT lookup
        faostat_matched = False
        faostat_dict = {
            "faostat_production_tonnes": 2000000.0,
            "faostat_yield_hg_per_ha": 220000.0,
            "faostat_area_harvested_ha": 95000.0,
            "faostat_matched": 0.0,
        }

        f_recs = (
            db.query(FAOSTATIndicator)
            .filter(func.lower(FAOSTATIndicator.commodity).like(f"%{request.commodity.lower()}%"))
            .order_by(FAOSTATIndicator.year.desc())
            .all()
        )
        if f_recs:
            faostat_matched = True
            prod_val = 2000000.0
            yield_val = 220000.0
            area_val = 95000.0

            for r in f_recs:
                ind_lower = r.indicator.lower() if r.indicator else ""
                if "production" in ind_lower:
                    prod_val = float(r.value)
                elif "yield" in ind_lower:
                    yield_val = float(r.value)
                elif "area" in ind_lower or "harvested" in ind_lower:
                    area_val = float(r.value)

            faostat_dict = {
                "faostat_production_tonnes": prod_val,
                "faostat_yield_hg_per_ha": yield_val,
                "faostat_area_harvested_ha": area_val,
                "faostat_matched": 1.0,
            }

        # C. Route logistics lookup
        route_matched = False
        route_dict = {
            "route_distance_km": 85.0,
            "route_duration_minutes": 83.0,
            "route_avg_speed_kmh": 61.4,
            "route_matched": 0.0,
        }

        r_rec = (
            db.query(RouteRecord)
            .filter(
                (func.lower(RouteRecord.origin_name).like(f"%{request.market.lower()}%")) |
                (func.lower(RouteRecord.dest_name).like(f"%{request.market.lower()}%")) |
                (func.lower(RouteRecord.origin_name).like(f"%{request.district.lower()}%")) |
                (func.lower(RouteRecord.dest_name).like(f"%{request.district.lower()}%"))
            )
            .first()
        )
        if r_rec:
            route_matched = True
            dist = float(r_rec.distance_km or 85.0)
            dur = float(r_rec.duration_minutes or 83.0)
            speed = (dist / (dur / 60.0)) if dur > 0 else 60.0
            route_dict = {
                "route_distance_km": dist,
                "route_duration_minutes": dur,
                "route_avg_speed_kmh": round(speed, 2),
                "route_matched": 1.0,
            }

        context = {**weather_dict, **faostat_dict, **route_dict}
        return context, weather_matched, faostat_matched, route_matched

    # -------------------------------------------------------------------------
    # 4. Feature Assembly, Scaling, Encoding & Prediction
    # -------------------------------------------------------------------------

    def predict_price(
        self,
        request: PricePredictionRequest,
        db: Session,
    ) -> PricePredictionResponse:
        """
        Executes end-to-end inference for agricultural modal price.
        """
        # 1. Temporal calendar features
        p_date = request.prediction_date
        temporal_dict = {
            "arrival_year": float(p_date.year),
            "arrival_month": float(p_date.month),
            "arrival_day": float(p_date.day),
            "arrival_day_of_week": float(p_date.weekday()),
            "arrival_quarter": float((p_date.month - 1) // 3 + 1),
            "arrival_day_of_year": float(p_date.timetuple().tm_yday),
            "is_weekend": 1.0 if p_date.weekday() >= 5 else 0.0,
        }

        # 2. Historical price features
        hist_dict, n_pts, latest_price = self.derive_historical_features(request, db)

        # 3. Contextual features
        context_dict, w_match, f_match, r_match = self.get_contextual_features(request, db)

        # 4. Combine numerical features dictionary
        num_row_dict = {**temporal_dict, **hist_dict, **context_dict}

        # Build numerical feature DataFrame with column names to align with StandardScaler
        num_df = pd.DataFrame([[num_row_dict[f] for f in self.numerical_features]], columns=self.numerical_features)

        # Scale numerical features with fitted scaler
        num_scaled = self.scaler.transform(num_df)

        # 5. Build categorical dataframe and encode
        cat_df = pd.DataFrame([{
            "commodity": request.commodity,
            "market": request.market,
            "district": request.district,
            "state": request.state,
            "variety": request.variety,
        }])
        cat_encoded = self.encoder.transform(cat_df)
        if hasattr(cat_encoded, "toarray"):
            cat_encoded = cat_encoded.toarray()

        # 6. Concatenate numerical and categorical arrays
        X_infer = np.hstack([num_scaled, cat_encoded])

        if X_infer.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Feature dimension mismatch: prepared {X_infer.shape[1]} features, "
                f"expected {len(self.feature_names)}."
            )

        if np.isnan(X_infer).any() or np.isinf(X_infer).any():
            raise ValueError("Inference vector contains NaN or Inf values.")

        # 7. Execute Model Prediction
        pred_val = float(self.model.predict(X_infer)[0])
        pred_rounded = round(max(0.0, pred_val), 2)

        model_name = self.metadata.get("selected_production_model", self.metadata.get("best_model_name", "Random Forest (Tuned)"))

        return PricePredictionResponse(
            status="success",
            commodity=request.commodity,
            market=request.market,
            district=request.district,
            state=request.state,
            variety=request.variety,
            prediction_date=request.prediction_date,
            predicted_modal_price=pred_rounded,
            unit="INR/quintal",
            model_used=model_name,
            historical_data_points_used=n_pts,
            latest_known_price=latest_price,
            weather_matched=w_match,
            faostat_matched=f_match,
            route_matched=r_match,
            features_used_count=len(self.feature_names),
            prediction_timestamp=datetime.now().isoformat(),
        )
