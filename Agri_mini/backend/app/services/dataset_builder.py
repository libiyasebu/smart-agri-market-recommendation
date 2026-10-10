from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.services.preprocessing_service import DataPreprocessingService


class MLDatasetBuilder:
    """
    Builds clean, leakage-free, multi-source integrated ML datasets
    for agricultural price forecasting (predicting modal_price).
    """

    CATEGORICAL_COLUMNS = ["commodity", "market", "district", "state", "variety"]
    
    # Mapping commodity names to FAOSTAT benchmark item names
    COMMODITY_TO_FAO_MAP = {
        "tomato": "Tomatoes",
        "tomatoes": "Tomatoes",
        "onion": "Onions, dry",
        "onions": "Onions, dry",
        "potato": "Potatoes",
        "potatoes": "Potatoes",
        "wheat": "Wheat",
        "rice": "Rice, paddy",
        "paddy": "Rice, paddy",
    }

    # District to Weather Hub name mapping
    DISTRICT_TO_WEATHER_MAP = {
        "thrissur": "Thrissur Agricultural Hub, Kerala",
        "ernakulam": "Kochi Market Hub, Kerala",
        "kochi": "Kochi Market Hub, Kerala",
        "palakkad": "Palakkad Farming Valley, Kerala",
        "wayanad": "Wayanad Highland Belt, Kerala",
    }

    # Market to primary logistics corridor mapping
    MARKET_TO_ROUTE_MAP = {
        "kochi (ernakulam) market": ("Thrissur, Kerala", "Kochi, Kerala"),
        "thrissur apmc": ("Palakkad, Kerala", "Thrissur, Kerala"),
        "kozhikode central mandi": ("Wayanad, Kerala", "Kozhikode, Kerala"),
        "kalpetta (wayanad) market": ("Wayanad, Kerala", "Kozhikode, Kerala"),
        "palakkad wholesale mandi": ("Palakkad, Kerala", "Thrissur, Kerala"),
    }

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.preprocessing_service = DataPreprocessingService(db=db)
        self.encoder: Optional[OneHotEncoder] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []
        self.numerical_feature_names: List[str] = []
        self.categorical_feature_names: List[str] = []

    # -------------------------------------------------------------------------
    # 1. Historical Lag & Rolling Feature Construction (Leakage Free)
    # -------------------------------------------------------------------------

    def construct_historical_price_features(self, df_clean: pd.DataFrame) -> pd.DataFrame:
        """
        Derives historical lag and rolling price features strictly using past observations.
        Current modal_price, min_price, max_price, and current-row spreads are NOT used.
        """
        df = df_clean.copy()
        df = df.sort_values(by=["market", "commodity", "variety", "arrival_date"]).reset_index(drop=True)

        grouped = df.groupby(["market", "commodity"], group_keys=False)

        # 1-day historical lag (price at t-1)
        df["hist_lag_1d_price"] = grouped["modal_price"].shift(1)

        # 3-day historical rolling average (mean of t-1, t-2, t-3)
        df["hist_rolling_mean_3d"] = grouped["hist_lag_1d_price"].transform(
            lambda s: s.rolling(window=3, min_periods=1).mean()
        )

        # 7-day historical rolling average (mean of t-1 .. t-7)
        df["hist_rolling_mean_7d"] = grouped["hist_lag_1d_price"].transform(
            lambda s: s.rolling(window=7, min_periods=1).mean()
        )

        # 7-day historical price volatility (std of t-1 .. t-7)
        df["hist_rolling_std_7d"] = grouped["hist_lag_1d_price"].transform(
            lambda s: s.rolling(window=7, min_periods=1).std().fillna(0.0)
        )

        # 1-day historical price momentum (change from t-2 to t-1)
        df["hist_price_momentum_1d"] = (df["hist_lag_1d_price"] - grouped["modal_price"].shift(2)).fillna(0.0)

        # Impute the very first observation of each group (where lag is NaN) using group mean or commodity mean
        commodity_means = df.groupby("commodity")["modal_price"].transform("mean")
        df["hist_lag_1d_price"] = df["hist_lag_1d_price"].fillna(commodity_means).round(2)
        df["hist_rolling_mean_3d"] = df["hist_rolling_mean_3d"].fillna(df["hist_lag_1d_price"]).round(2)
        df["hist_rolling_mean_7d"] = df["hist_rolling_mean_7d"].fillna(df["hist_lag_1d_price"]).round(2)
        df["hist_rolling_std_7d"] = df["hist_rolling_std_7d"].fillna(0.0).round(2)
        df["hist_price_momentum_1d"] = df["hist_price_momentum_1d"].fillna(0.0).round(2)

        return df

    # -------------------------------------------------------------------------
    # 2. Multi-Source Integration (Weather, FAOSTAT, Route)
    # -------------------------------------------------------------------------

    def integrate_multi_source_data(
        self,
        df_market: pd.DataFrame,
        df_weather: pd.DataFrame,
        df_faostat: pd.DataFrame,
        df_routes: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Integrates weather, FAOSTAT, and logistics features into the market dataset.
        Tracks matched and unmatched counts cleanly without fabricating artificial rows.
        """
        df = df_market.copy()
        unmatched_stats = {
            "total_market_records": len(df),
            "weather_matched": 0,
            "weather_unmatched": 0,
            "faostat_matched": 0,
            "faostat_unmatched": 0,
            "route_matched": 0,
            "route_unmatched": 0,
        }

        # --- A. Weather Integration ---
        # Map district to weather location_name
        df["_weather_loc"] = df["district"].str.lower().map(self.DISTRICT_TO_WEATHER_MAP)
        
        if not df_weather.empty and "record_date" in df_weather.columns:
            w_df = df_weather.copy()
            w_df["record_date"] = pd.to_datetime(w_df["record_date"])
            w_subset = w_df[[
                "location_name", "record_date", "temp_mean_celsius", "temp_min_celsius",
                "temp_max_celsius", "humidity_mean_pct", "precipitation_mm", "rain_mm",
                "temp_diurnal_range", "is_rainy"
            ]].drop_duplicates(subset=["location_name", "record_date"])

            df = df.merge(
                w_subset,
                left_on=["_weather_loc", "arrival_date"],
                right_on=["location_name", "record_date"],
                how="left"
            )
            df.drop(columns=["_weather_loc", "location_name", "record_date"], errors="ignore", inplace=True)
            df["weather_matched"] = df["temp_mean_celsius"].notna().astype(int)
        else:
            for col in ["temp_mean_celsius", "temp_min_celsius", "temp_max_celsius", "humidity_mean_pct", "precipitation_mm", "rain_mm", "temp_diurnal_range", "is_rainy"]:
                df[col] = np.nan
            df["weather_matched"] = 0

        unmatched_stats["weather_matched"] = int(df["weather_matched"].sum())
        unmatched_stats["weather_unmatched"] = len(df) - unmatched_stats["weather_matched"]

        # --- B. FAOSTAT Macro Indicators Integration ---
        df["_fao_commodity"] = df["commodity"].str.lower().map(self.COMMODITY_TO_FAO_MAP)

        if not df_faostat.empty:
            f_df = df_faostat.copy()
            # Pivot indicators: Production, Yield, Area harvested
            pivoted = f_df.pivot_table(
                index=["commodity", "year"],
                columns="indicator",
                values="value",
                aggfunc="first"
            ).reset_index()

            # Rename columns cleanly
            col_rename = {
                "Production": "faostat_production_tonnes",
                "Yield": "faostat_yield_hg_per_ha",
                "Area harvested": "faostat_area_harvested_ha",
            }
            pivoted.rename(columns=col_rename, inplace=True)

            # Ensure expected columns exist
            for expected_col in ["faostat_production_tonnes", "faostat_yield_hg_per_ha", "faostat_area_harvested_ha"]:
                if expected_col not in pivoted.columns:
                    pivoted[expected_col] = np.nan

            # For recent years (e.g. 2026) where latest benchmark year in FAOSTAT is 2022/2023,
            # map to the latest available benchmark year per crop
            latest_fao = pivoted.sort_values("year").groupby("commodity").last().reset_index()
            latest_fao.drop(columns=["year"], errors="ignore", inplace=True)

            df = df.merge(
                latest_fao,
                left_on="_fao_commodity",
                right_on="commodity",
                how="left",
                suffixes=("", "_fao")
            )
            df.drop(columns=["_fao_commodity", "commodity_fao"], errors="ignore", inplace=True)
            df["faostat_matched"] = df["faostat_production_tonnes"].notna().astype(int)
        else:
            for col in ["faostat_production_tonnes", "faostat_yield_hg_per_ha", "faostat_area_harvested_ha"]:
                df[col] = np.nan
            df["faostat_matched"] = 0

        unmatched_stats["faostat_matched"] = int(df["faostat_matched"].sum())
        unmatched_stats["faostat_unmatched"] = len(df) - unmatched_stats["faostat_matched"]

        # --- C. Route Logistics Integration ---
        # Map market to primary transport corridor
        if not df_routes.empty:
            r_df = df_routes.copy()
            route_lookup = {}
            for _, r in r_df.iterrows():
                key = (r["origin_name"], r["dest_name"])
                route_lookup[key] = {
                    "route_distance_km": r["distance_km"],
                    "route_duration_minutes": r["duration_minutes"],
                    "route_avg_speed_kmh": r.get("avg_speed_kmh", 0.0),
                }

            r_dist, r_dur, r_spd, r_match = [], [], [], []
            for _, row in df.iterrows():
                m_key = row["market"].lower().strip()
                corridor = self.MARKET_TO_ROUTE_MAP.get(m_key)
                if corridor and corridor in route_lookup:
                    r_dist.append(route_lookup[corridor]["route_distance_km"])
                    r_dur.append(route_lookup[corridor]["route_duration_minutes"])
                    r_spd.append(route_lookup[corridor]["route_avg_speed_kmh"])
                    r_match.append(1)
                else:
                    r_dist.append(np.nan)
                    r_dur.append(np.nan)
                    r_spd.append(np.nan)
                    r_match.append(0)

            df["route_distance_km"] = r_dist
            df["route_duration_minutes"] = r_dur
            df["route_avg_speed_kmh"] = r_spd
            df["route_matched"] = r_match
        else:
            for col in ["route_distance_km", "route_duration_minutes", "route_avg_speed_kmh"]:
                df[col] = np.nan
            df["route_matched"] = 0

        unmatched_stats["route_matched"] = int(df["route_matched"].sum())
        unmatched_stats["route_unmatched"] = len(df) - unmatched_stats["route_matched"]

        return df, unmatched_stats

    # -------------------------------------------------------------------------
    # 3. Train / Test Split & Leakage-Free Preprocessing / Encoding
    # -------------------------------------------------------------------------

    def prepare_ml_dataset(
        self,
        test_size: float = 0.2,
        db: Optional[Session] = None,
        custom_market_df: Optional[pd.DataFrame] = None,
        custom_weather_df: Optional[pd.DataFrame] = None,
        custom_faostat_df: Optional[pd.DataFrame] = None,
        custom_route_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end dataset preparation:
        1. Pipeline extraction and data cleaning.
        2. Leakage-free historical price feature construction.
        3. Multi-source integration (weather, FAOSTAT, routes).
        4. Chronological train/test split.
        5. Encoder & Scaler fitting exclusively on training data.
        6. Returns X_train, X_test, y_train, y_test, metadata, and statistics.
        """
        session = db or self.db

        if custom_market_df is not None:
            raw_market = custom_market_df
            raw_weather = custom_weather_df if custom_weather_df is not None else pd.DataFrame()
            raw_faostat = custom_faostat_df if custom_faostat_df is not None else pd.DataFrame()
            raw_routes = custom_route_df if custom_route_df is not None else pd.DataFrame()
            clean_market, _ = self.preprocessing_service.preprocess_market_prices(raw_market)
            clean_weather = self.preprocessing_service.preprocess_weather_records(raw_weather)
            clean_faostat = self.preprocessing_service.preprocess_faostat_indicators(raw_faostat)
            clean_routes = self.preprocessing_service.preprocess_route_records(raw_routes)
        else:
            if not session:
                raise ValueError("Database session required when custom DataFrames are not supplied.")
            pipe_results = self.preprocessing_service.run_pipeline(session)
            clean_market = pipe_results["market_prices"]["dataframe"]
            clean_weather = pipe_results["weather_records"]["dataframe"]
            clean_faostat = pipe_results["faostat_indicators"]["dataframe"]
            clean_routes = pipe_results["route_records"]["dataframe"]

        if clean_market.empty:
            raise ValueError("No market price records available to build ML dataset.")

        # 1. Construct historical price features (leakage free)
        df_featured = self.construct_historical_price_features(clean_market)

        # 2. Multi-source integration
        df_merged, unmatched_stats = self.integrate_multi_source_data(
            df_featured, clean_weather, clean_faostat, clean_routes
        )

        # 3. Sort strictly by arrival_date for chronological split
        df_merged = df_merged.sort_values(by=["arrival_date", "market", "commodity"]).reset_index(drop=True)

        # 4. Target variable separation (modal_price)
        y = df_merged["modal_price"].values.astype(np.float64)

        # 5. Feature selection: strictly exclude current-row price leaks
        # Excluded: modal_price, min_price, max_price, price_spread, price_spread_pct, price_to_min_ratio, price_to_max_ratio
        # Excluded non-predictive metadata: id, source, created_at, arrival_date
        
        numerical_features = [
            # Temporal features
            "arrival_year", "arrival_month", "arrival_day", "arrival_day_of_week",
            "arrival_quarter", "arrival_day_of_year", "is_weekend",
            # Historical lag & rolling price dynamics
            "hist_lag_1d_price", "hist_rolling_mean_3d", "hist_rolling_mean_7d",
            "hist_rolling_std_7d", "hist_price_momentum_1d",
            # Weather features
            "temp_mean_celsius", "temp_min_celsius", "temp_max_celsius",
            "temp_diurnal_range", "humidity_mean_pct", "precipitation_mm",
            "rain_mm", "is_rainy", "weather_matched",
            # FAOSTAT features
            "faostat_production_tonnes", "faostat_yield_hg_per_ha",
            "faostat_area_harvested_ha", "faostat_matched",
            # Route logistics features
            "route_distance_km", "route_duration_minutes",
            "route_avg_speed_kmh", "route_matched",
        ]

        categorical_features = self.CATEGORICAL_COLUMNS

        # 6. Chronological Train / Test Split
        n_total = len(df_merged)
        split_idx = int(n_total * (1.0 - test_size))
        # Ensure at least 1 test sample
        split_idx = max(1, min(split_idx, n_total - 1))

        df_train = df_merged.iloc[:split_idx].copy()
        df_test = df_merged.iloc[split_idx:].copy()

        y_train = y[:split_idx]
        y_test = y[split_idx:]

        train_dates = (
            df_train["arrival_date"].min().strftime("%Y-%m-%d"),
            df_train["arrival_date"].max().strftime("%Y-%m-%d"),
        )
        test_dates = (
            df_test["arrival_date"].min().strftime("%Y-%m-%d"),
            df_test["arrival_date"].max().strftime("%Y-%m-%d"),
        )

        # 7. Impute missing numerical values using Training set statistics ONLY
        train_num = df_train[numerical_features].copy()
        test_num = df_test[numerical_features].copy()

        train_medians = train_num.median()
        # Fallback to 0.0 if all values in column are NaN in train
        train_medians = train_medians.fillna(0.0)

        train_num = train_num.fillna(train_medians)
        test_num = test_num.fillna(train_medians)

        # 8. Fit Scaler ONLY on Training data
        self.scaler = StandardScaler()
        X_train_num_scaled = self.scaler.fit_transform(train_num)
        X_test_num_scaled = self.scaler.transform(test_num)

        # 9. Fit OneHotEncoder ONLY on Training data
        self.encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        X_train_cat = self.encoder.fit_transform(df_train[categorical_features])
        X_test_cat = self.encoder.transform(df_test[categorical_features])

        cat_feature_names = list(self.encoder.get_feature_names_out(categorical_features))
        self.feature_names = numerical_features + cat_feature_names
        self.numerical_feature_names = numerical_features
        self.categorical_feature_names = cat_feature_names

        # 10. Combine Numerical and Categorical Arrays
        X_train = np.hstack([X_train_num_scaled, X_train_cat])
        X_test = np.hstack([X_test_num_scaled, X_test_cat])

        # 11. Target & Dataset Statistics
        target_stats = {
            "train": {
                "count": int(len(y_train)),
                "mean": round(float(np.mean(y_train)), 2),
                "std": round(float(np.std(y_train)), 2),
                "min": round(float(np.min(y_train)), 2),
                "max": round(float(np.max(y_train)), 2),
                "p25": round(float(np.percentile(y_train, 25)), 2),
                "p50": round(float(np.percentile(y_train, 50)), 2),
                "p75": round(float(np.percentile(y_train, 75)), 2),
            },
            "test": {
                "count": int(len(y_test)),
                "mean": round(float(np.mean(y_test)), 2),
                "std": round(float(np.std(y_test)), 2),
                "min": round(float(np.min(y_test)), 2),
                "max": round(float(np.max(y_test)), 2),
                "p25": round(float(np.percentile(y_test, 25)), 2),
                "p50": round(float(np.percentile(y_test, 50)), 2),
                "p75": round(float(np.percentile(y_test, 75)), 2),
            },
        }

        dataset_stats = {
            "total_samples": n_total,
            "train_samples": len(y_train),
            "test_samples": len(y_test),
            "numerical_features_count": len(numerical_features),
            "categorical_encoded_features_count": len(cat_feature_names),
            "total_model_features": len(self.feature_names),
            "split_ratio": f"{round((1 - test_size)*100)}:{round(test_size*100)}",
        }

        return {
            "status": "success",
            "X_train": X_train,
            "X_test": X_test,
            "y_train": y_train,
            "y_test": y_test,
            "feature_names": self.feature_names,
            "numerical_features": numerical_features,
            "categorical_encoded_features": cat_feature_names,
            "train_date_range": {"start": train_dates[0], "end": train_dates[1]},
            "test_date_range": {"start": test_dates[0], "end": test_dates[1]},
            "dataset_stats": dataset_stats,
            "unmatched_stats": unmatched_stats,
            "target_stats": target_stats,
            "train_dataframe": df_train,
            "test_dataframe": df_test,
        }
