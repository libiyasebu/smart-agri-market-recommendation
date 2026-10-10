import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from app.services.model_service import ModelTrainingService


@pytest.fixture
def synthetic_training_data():
    """Generates synthetic dataset for tuning and validation tests."""
    np.random.seed(42)
    n_train = 80
    n_test = 20
    n_features = 8

    feature_names = [f"feature_{i}" for i in range(n_features - 1)] + ["hist_lag_1d_price"]

    y_train = np.random.uniform(1500, 3500, size=n_train)
    y_test = np.random.uniform(1500, 3500, size=n_test)

    # Shifted lag price (row 0 uses y_train[0], row 1 uses y_train[0], row 2 uses y_train[1], etc.)
    lag_train = np.roll(y_train, 1)
    lag_train[0] = y_train[0]
    lag_test = np.roll(y_test, 1)
    lag_test[0] = y_train[-1]

    X_train = np.random.randn(n_train, n_features)
    X_test = np.random.randn(n_test, n_features)
    X_train[:, -1] = lag_train
    X_test[:, -1] = lag_test

    train_dates = pd.date_range("2026-08-01", periods=n_train, freq="D")
    test_dates = pd.date_range(train_dates[-1] + pd.Timedelta(days=1), periods=n_test, freq="D")

    df_train = pd.DataFrame({
        "market": ["Thrissur APMC"] * n_train,
        "commodity": ["Tomato"] * n_train,
        "arrival_date": train_dates,
        "modal_price": y_train,
        "hist_lag_1d_price": lag_train,
    })
    df_test = pd.DataFrame({
        "market": ["Thrissur APMC"] * n_test,
        "commodity": ["Tomato"] * n_test,
        "arrival_date": test_dates,
        "modal_price": y_test,
        "hist_lag_1d_price": lag_test,
    })

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "feature_names": feature_names,
        "train_dataframe": df_train,
        "test_dataframe": df_test,
        "numerical_features": feature_names,
        "categorical_encoded_features": [],
        "train_date_range": {"start": str(train_dates[0].date()), "end": str(train_dates[-1].date())},
        "test_date_range": {"start": str(test_dates[0].date()), "end": str(test_dates[-1].date())},
    }


def test_time_series_cross_validation(synthetic_training_data):
    trainer = ModelTrainingService(random_state=42)
    rf = RandomForestRegressor(n_estimators=10, max_depth=4, random_state=42)

    cv_results = trainer.cross_validate_model(
        rf,
        synthetic_training_data["X_train"],
        synthetic_training_data["y_train"],
        n_splits=3,
    )

    assert "folds" in cv_results
    assert len(cv_results["folds"]) == 3
    assert "mean_mae" in cv_results
    assert "std_mae" in cv_results
    assert cv_results["mean_mae"] > 0.0

    # Verify expanding window sizes
    folds = cv_results["folds"]
    assert folds[0]["train_size"] < folds[1]["train_size"] < folds[2]["train_size"]


def test_hyperparameter_tuning_uses_train_only(synthetic_training_data):
    trainer = ModelTrainingService(random_state=42)
    X_train = synthetic_training_data["X_train"]
    y_train = synthetic_training_data["y_train"]

    best_rf, rf_params, rf_info = trainer.tune_random_forest(X_train, y_train, n_splits=3)

    assert isinstance(best_rf, RandomForestRegressor)
    assert "n_estimators" in rf_params
    assert "max_depth" in rf_params
    assert "best_cv_mae" in rf_info

    best_xgb, xgb_params, xgb_info = trainer.tune_xgboost(X_train, y_train, n_splits=3)
    assert isinstance(best_xgb, XGBRegressor)
    assert "learning_rate" in xgb_params
    assert "best_cv_mae" in xgb_info


def test_leakage_audit(synthetic_training_data):
    trainer = ModelTrainingService(random_state=42)
    audit = trainer.perform_leakage_audit(synthetic_training_data)

    assert audit["passed"] is True
    assert len(audit["direct_price_leaks_found"]) == 0
    assert audit["train_test_date_overlap"] is False
    assert "R²" in audit["r2_investigation_note"] or "R^2" in audit["r2_investigation_note"]


def test_train_tune_and_evaluate_all_workflow(synthetic_training_data):
    trainer = ModelTrainingService(random_state=42)
    res = trainer.train_tune_and_evaluate_all(synthetic_training_data)

    results = res["results"]
    assert "Persistence Baseline" in results
    assert "Linear Regression" in results
    assert "Random Forest (Default)" in results
    assert "Random Forest (Tuned)" in results
    assert "XGBoost (Default)" in results
    assert "XGBoost (Tuned)" in results

    assert res["best_model_name"] in results
    assert len(res["feature_importance"]) == len(synthetic_training_data["feature_names"])

    best_pred = res["predictions"][res["best_model_name"]]["test"]
    assert len(best_pred) == len(synthetic_training_data["y_test"])
    assert not np.isnan(best_pred).any()
    assert not np.isinf(best_pred).any()


def test_save_and_load_tuned_artifacts(tmp_path, synthetic_training_data):
    trainer = ModelTrainingService(random_state=42, artifacts_dir=tmp_path)
    res = trainer.train_tune_and_evaluate_all(synthetic_training_data)

    paths = trainer.save_model_artifacts(res)

    assert paths["model_path"].exists()
    assert paths["metadata_path"].exists()
    assert paths["preprocessor_path"].exists()

    meta = trainer.load_metadata(paths["metadata_path"])
    assert meta["selected_production_model"] == res["best_model_name"]
    assert "final_test_metrics" in meta
    assert "hyperparameter_tuning_results" in meta
    assert "leakage_audit" in meta
