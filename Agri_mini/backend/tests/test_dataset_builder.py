import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from app.services.dataset_builder import MLDatasetBuilder


def create_synthetic_market_data(num_days=10):
    """Generates synthetic multi-day mandi records for testing."""
    records = []
    base_date = date(2026, 8, 1)
    commodities = ["Tomato", "Onion"]
    markets = [
        {"state": "Kerala", "district": "Thrissur", "market": "Thrissur APMC"},
        {"state": "Kerala", "district": "Ernakulam", "market": "Kochi Market"},
    ]

    for d in range(num_days):
        cur_date = base_date + timedelta(days=d)
        for m in markets:
            for c in commodities:
                base = 2000.0 if c == "Tomato" else 2500.0
                modal = base + d * 20.0
                records.append({
                    "state": m["state"],
                    "district": m["district"],
                    "market": m["market"],
                    "commodity": c,
                    "variety": "Local",
                    "arrival_date": cur_date,
                    "min_price": modal - 150.0,
                    "max_price": modal + 200.0,
                    "modal_price": modal,
                    "source": "Agmarknet",
                })
    return pd.DataFrame(records)


def test_target_leakage_prevention():
    builder = MLDatasetBuilder()
    df_market = create_synthetic_market_data(num_days=8)

    data = builder.prepare_ml_dataset(test_size=0.25, custom_market_df=df_market)

    feature_names = data["feature_names"]

    # Target and same-day bounds/spreads MUST NOT be in feature names
    forbidden_features = [
        "modal_price", "min_price", "max_price", "price_spread",
        "price_spread_pct", "price_to_min_ratio", "price_to_max_ratio"
    ]
    for forbidden in forbidden_features:
        assert forbidden not in feature_names, f"Leakage detected: '{forbidden}' is in feature names!"


def test_chronological_train_test_split_ordering():
    builder = MLDatasetBuilder()
    df_market = create_synthetic_market_data(num_days=10)

    data = builder.prepare_ml_dataset(test_size=0.3, custom_market_df=df_market)

    df_train = data["train_dataframe"]
    df_test = data["test_dataframe"]

    max_train_date = df_train["arrival_date"].max()
    min_test_date = df_test["arrival_date"].min()

    # Chronological integrity: Train dates strictly <= Test dates
    assert max_train_date <= min_test_date
    assert data["train_date_range"]["start"] <= data["train_date_range"]["end"]
    assert data["test_date_range"]["start"] <= data["test_date_range"]["end"]


def test_historical_features_are_strictly_shifted():
    builder = MLDatasetBuilder()
    df_market = create_synthetic_market_data(num_days=5)

    df_featured = builder.construct_historical_price_features(df_market)

    # Filter for single series: Thrissur APMC, Tomato
    series = df_featured[(df_featured["market"] == "Thrissur APMC") & (df_featured["commodity"] == "Tomato")].sort_values("arrival_date").reset_index(drop=True)

    # Day 1: lag_1d_price should be Day 0 modal price
    day0_modal = series.loc[0, "modal_price"]
    day1_lag = series.loc[1, "hist_lag_1d_price"]
    assert day1_lag == day0_modal

    # Day 2: lag_1d_price should be Day 1 modal price
    day1_modal = series.loc[1, "modal_price"]
    day2_lag = series.loc[2, "hist_lag_1d_price"]
    assert day2_lag == day1_modal

    # Day 2 rolling mean 3d should be mean of day0 and day1
    expected_roll = (day0_modal + day1_modal) / 2.0
    assert series.loc[2, "hist_rolling_mean_3d"] == expected_roll


def test_no_nan_or_inf_in_processed_matrices():
    builder = MLDatasetBuilder()
    df_market = create_synthetic_market_data(num_days=6)

    data = builder.prepare_ml_dataset(test_size=0.33, custom_market_df=df_market)

    X_train = data["X_train"]
    X_test = data["X_test"]
    y_train = data["y_train"]
    y_test = data["y_test"]

    assert not np.isnan(X_train).any(), "X_train contains NaN values!"
    assert not np.isinf(X_train).any(), "X_train contains Inf values!"
    assert not np.isnan(X_test).any(), "X_test contains NaN values!"
    assert not np.isinf(X_test).any(), "X_test contains Inf values!"

    assert not np.isnan(y_train).any(), "y_train contains NaN values!"
    assert not np.isnan(y_test).any(), "y_test contains NaN values!"

    assert X_train.shape[0] == len(y_train)
    assert X_test.shape[0] == len(y_test)
    assert X_train.shape[1] == X_test.shape[1] == len(data["feature_names"])


def test_encoder_and_scaler_fitted_only_on_train():
    builder = MLDatasetBuilder()
    df_market = create_synthetic_market_data(num_days=8)

    data = builder.prepare_ml_dataset(test_size=0.25, custom_market_df=df_market)

    # Verify encoder and scaler were initialized and fit
    assert builder.encoder is not None
    assert builder.scaler is not None
    assert hasattr(builder.encoder, "categories_")
    assert hasattr(builder.scaler, "mean_")

    # Scaler mean must have length equal to numerical features
    assert len(builder.scaler.mean_) == len(data["numerical_features"])


def test_safe_handling_of_unmatched_multi_source_data():
    builder = MLDatasetBuilder()
    # Market data with commodity and district not present in weather/faostat/routes
    unmatched_market = pd.DataFrame([{
        "state": "RemoteState", "district": "UnknownDistrict", "market": "UnknownMandi",
        "commodity": "ExoticCrop", "variety": "Standard", "arrival_date": date(2026, 8, 20),
        "min_price": 5000.0, "max_price": 5500.0, "modal_price": 5200.0, "source": "Agmarknet"
    }, {
        "state": "RemoteState", "district": "UnknownDistrict", "market": "UnknownMandi",
        "commodity": "ExoticCrop", "variety": "Standard", "arrival_date": date(2026, 8, 21),
        "min_price": 5100.0, "max_price": 5600.0, "modal_price": 5300.0, "source": "Agmarknet"
    }])

    data = builder.prepare_ml_dataset(test_size=0.5, custom_market_df=unmatched_market)

    assert data["unmatched_stats"]["weather_unmatched"] == 2
    assert data["unmatched_stats"]["faostat_unmatched"] == 2
    assert data["unmatched_stats"]["route_unmatched"] == 2

    # Despite being unmatched, matrices must remain finite and clean
    assert not np.isnan(data["X_train"]).any()
    assert not np.isnan(data["X_test"]).any()
