import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from app.services.model_service import (
    ModelTrainingService,
    calculate_mape,
    evaluate_predictions,
)


@pytest.fixture
def sample_ml_dataset():
    """Generates a synthetic ML dataset dictionary matching Phase 4B output structure."""
    np.random.seed(42)
    n_train = 100
    n_test = 25
    n_features = 10

    feature_names = [f"feature_{i}" for i in range(n_features - 1)] + ["hist_lag_1d_price"]

    # True price baseline
    y_train = np.random.uniform(1500, 3500, size=n_train)
    y_test = np.random.uniform(1500, 3500, size=n_test)

    # Features: correlated with price
    X_train = np.random.randn(n_train, n_features)
    X_test = np.random.randn(n_test, n_features)

    # Last column is historical lag price
    X_train[:, -1] = y_train + np.random.normal(0, 50, size=n_train)
    X_test[:, -1] = y_test + np.random.normal(0, 50, size=n_test)

    df_train = pd.DataFrame({"hist_lag_1d_price": X_train[:, -1]})
    df_test = pd.DataFrame({"hist_lag_1d_price": X_test[:, -1]})

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
        "train_date_range": {"start": "2026-08-01", "end": "2026-08-20"},
        "test_date_range": {"start": "2026-08-21", "end": "2026-08-27"},
    }


def test_metric_calculations():
    y_true = np.array([2000.0, 3000.0, 4000.0])
    y_pred = np.array([2100.0, 2900.0, 4000.0])

    metrics = evaluate_predictions(y_true, y_pred)

    # MAE = (100 + 100 + 0) / 3 = 66.67
    assert metrics["mae"] == round(200.0 / 3.0, 2)
    # RMSE = sqrt((10000 + 10000 + 0) / 3) = sqrt(6666.67) = 81.65
    assert metrics["rmse"] == round(np.sqrt(20000.0 / 3.0), 2)
    assert metrics["r2"] > 0.9
    assert metrics["mape"] > 0.0


def test_mape_safe_zero_handling():
    y_true_with_zero = np.array([0.0, 100.0, 200.0])
    y_pred = np.array([10.0, 105.0, 195.0])

    # Must not raise ZeroDivisionError or return NaN/Inf
    mape = calculate_mape(y_true_with_zero, y_pred)
    assert not np.isnan(mape)
    assert not np.isinf(mape)
    assert mape > 0.0


def test_model_training_and_predictions(sample_ml_dataset):
    trainer = ModelTrainingService(random_state=42)
    eval_results = trainer.train_and_evaluate(sample_ml_dataset)

    results = eval_results["results"]
    assert "Persistence Baseline" in results
    assert "Linear Regression" in results
    assert "Random Forest" in results
    assert "XGBoost" in results

    # Verify all predictions have valid shape and no NaN/Inf
    for name, preds in eval_results["predictions"].items():
        y_test_pred = preds["test"]
        assert len(y_test_pred) == len(sample_ml_dataset["y_test"])
        assert not np.isnan(y_test_pred).any(), f"NaN found in {name} predictions!"
        assert not np.isinf(y_test_pred).any(), f"Inf found in {name} predictions!"


def test_best_model_selection(sample_ml_dataset):
    trainer = ModelTrainingService(random_state=42)
    eval_results = trainer.train_and_evaluate(sample_ml_dataset)

    best_name = eval_results["best_model_name"]
    assert best_name in eval_results["results"]

    best_mae = eval_results["results"][best_name]["test"]["mae"]
    for name, metrics in eval_results["results"].items():
        assert best_mae <= metrics["test"]["mae"] + 1e-5


def test_xgboost_feature_importance(sample_ml_dataset):
    trainer = ModelTrainingService(random_state=42)
    eval_results = trainer.train_and_evaluate(sample_ml_dataset)

    importances = eval_results["xgb_feature_importance"]
    assert len(importances) == len(sample_ml_dataset["feature_names"])
    assert importances[0]["rank"] == 1
    assert importances[0]["importance"] >= importances[-1]["importance"]


def test_artifact_saving_and_loading(tmp_path, sample_ml_dataset):
    trainer = ModelTrainingService(random_state=42, artifacts_dir=tmp_path)
    eval_results = trainer.train_and_evaluate(sample_ml_dataset)

    paths = trainer.save_model_artifacts(eval_results)

    assert paths["model_path"].exists()
    assert paths["preprocessor_path"].exists()
    assert paths["metadata_path"].exists()

    # Load back
    loaded_model = trainer.load_best_model(paths["model_path"])
    loaded_meta = trainer.load_metadata(paths["metadata_path"])

    assert loaded_meta["best_model_name"] == eval_results["best_model_name"]

    # Test loaded model prediction if ML model
    if hasattr(loaded_model, "predict"):
        preds = loaded_model.predict(sample_ml_dataset["X_test"])
        assert len(preds) == len(sample_ml_dataset["y_test"])
        assert not np.isnan(preds).any()
