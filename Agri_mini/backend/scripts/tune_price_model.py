import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load .env
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

from app.database import SessionLocal, check_db_connection
from app.services.dataset_builder import MLDatasetBuilder
from app.services.model_service import ModelTrainingService


def print_separator(char="=", length=105):
    print(char * length)


def main():
    parser = argparse.ArgumentParser(description="Model Validation, Hyperparameter Tuning & Selection (Phase 5B)")
    parser.add_argument("--test-size", type=float, default=0.2, help="Chronological test set proportion (default: 0.2)")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    print_separator()
    print("  AGRICULTURAL PRICE PREDICTION -- VALIDATION, TUNING & FINAL SELECTION (Phase 5B)")
    print_separator()

    db_info = check_db_connection()
    print(f"  Source Database   : {db_info['database_name']} (User: {db_info['current_user']}, Server: {db_info['server_version']})")
    print(f"  Target Variable   : modal_price (INR per quintal)")
    print(f"  Chronological Split: 80% Train / 20% Test (Untouched)")
    print_separator("-")

    db = SessionLocal()
    try:
        # 1. Load ML dataset using MLDatasetBuilder
        print("  [1/5] Loading prepared ML dataset from PostgreSQL...")
        builder = MLDatasetBuilder(db=db)
        ml_data = builder.prepare_ml_dataset(test_size=args.test_size, db=db)

        print(f"        -> X_train shape: {ml_data['X_train'].shape} (Dates: {ml_data['train_date_range']['start']} to {ml_data['train_date_range']['end']})")
        print(f"        -> X_test shape : {ml_data['X_test'].shape} (Dates: {ml_data['test_date_range']['start']} to {ml_data['test_date_range']['end']})")
        print(f"        -> Total model features: {len(ml_data['feature_names'])}")

        # 2. Run Master Tuning and Evaluation Pipeline
        print("\n  [2/5] Performing leakage audit, TimeSeriesSplit CV, and hyperparameter tuning...")
        trainer = ModelTrainingService(random_state=args.random_state)
        tuning_results = trainer.train_tune_and_evaluate_all(ml_data)

        # 3. Leakage Audit Report
        audit = tuning_results["audit"]
        print("\n  =======================================================================================")
        print("                                  TARGET LEAKAGE AUDIT REPORT                            ")
        print("  =======================================================================================")
        print(f"  - Direct Price Leaks Found In Features : {len(audit['direct_price_leaks_found'])} (modal/min/max/spreads excluded)")
        print(f"  - Historical Lag Shift Verified        : {audit['historical_lag_shift_verified']} (Strictly t-1)")
        print(f"  - Chronological Train/Test Non-Overlap : {not audit['train_test_date_overlap']} ({ml_data['train_date_range']['end']} <= {ml_data['test_date_range']['start']})")
        print(f"  - Overall Leakage Audit Status         : {'PASSED (Zero Leakage)' if audit['passed'] else 'FAILED'}")
        print("\n  [Statistical Context on R^2 (0.998)]:")
        print(f"  {audit['r2_investigation_note']}")
        print("  =======================================================================================")

        # 4. Hyperparameter Tuning Results
        print("\n  =======================================================================================")
        print("                        BEST HYPERPARAMETERS (TUNED ON TRAINING DATA ONLY)               ")
        print("  =======================================================================================")
        rf_tune = tuning_results["tuning"]["random_forest"]
        xgb_tune = tuning_results["tuning"]["xgboost"]

        print(f"  [Random Forest Best Params] (CV MAE: Rs. {rf_tune['tuning_info']['best_cv_mae']:.2f}):")
        for k, v in rf_tune["params"].items():
            print(f"    - {k:<20}: {v}")

        print(f"\n  [XGBoost Best Params]       (CV MAE: Rs. {xgb_tune['tuning_info']['best_cv_mae']:.2f}):")
        for k, v in xgb_tune["params"].items():
            print(f"    - {k:<20}: {v}")
        print("  =======================================================================================")

        # 5. Time-Series Cross Validation Comparison
        print("\n  =======================================================================================")
        print("                     TIME-SERIES CROSS-VALIDATION (4-FOLD CHRONOLOGICAL CV)              ")
        print("  =======================================================================================")
        print(f"  {'Model Name':<26} | {'CV Mean MAE (Rs.)':<18} | {'CV Mean RMSE (Rs.)':<19} | {'CV Mean R^2':<12}")
        print("  " + "-" * 87)

        for model_name, cv_info in tuning_results["cv_results"].items():
            if cv_info is not None:
                mae_str = f"Rs. {cv_info['mean_mae']:.2f} +/- {cv_info['std_mae']:.2f}"
                rmse_str = f"Rs. {cv_info['mean_rmse']:.2f} +/- {cv_info['std_rmse']:.2f}"
                r2_str = f"{cv_info['mean_r2']:.4f} +/- {cv_info['std_r2']:.4f}"
                print(f"  {model_name:<26} | {mae_str:<18} | {rmse_str:<19} | {r2_str:<12}")
        print("  =======================================================================================")

        # 6. Final Model Comparison on Untouched Test Set
        print("\n  =======================================================================================")
        print("                   FINAL MODEL COMPARISON (UNTOUCHED CHRONOLOGICAL TEST SET)             ")
        print("  =======================================================================================")
        print(f"  {'Model Name':<26} | {'Test MAE (Rs.)':<14} | {'Test RMSE (Rs.)':<15} | {'Test R^2':<10} | {'Test MAPE (%)':<12}")
        print("  " + "-" * 87)

        for model_name, metrics in tuning_results["results"].items():
            t = metrics["test"]
            print(f"  {model_name:<26} | Rs. {t['mae']:<10.2f} | Rs. {t['rmse']:<11.2f} | {t['r2']:<10.4f} | {t['mape']:<8.2f}%")
        print("  =======================================================================================")

        # 7. Final Selected Production Model
        best_name = tuning_results["best_model_name"]
        best_test = tuning_results["results"][best_name]["test"]
        print(f"\n  [3/5] Final Selected Production Model: >>> {best_name.upper()} <<<")
        print(f"        -> Test MAE  : Rs. {best_test['mae']:.2f} / quintal")
        print(f"        -> Test RMSE : Rs. {best_test['rmse']:.2f} / quintal")
        print(f"        -> Test R^2  : {best_test['r2']:.4f}")
        print(f"        -> Test MAPE : {best_test['mape']:.2f}%")
        print(f"        -> Selection Basis: Lowest generalization error on untouched chronological test set.")

        # 8. Top 15 Feature Importances
        print("\n  =======================================================================================")
        print(f"                       TOP 15 FEATURE IMPORTANCES ({best_name})                         ")
        print("  =======================================================================================")
        print(f"  {'Rank':<5} | {'Feature Name':<38} | {'Importance Score':<18} | {'Bar'}")
        print("  " + "-" * 87)

        top_15 = tuning_results["feature_importance"][:15]
        for item in top_15:
            bar = "#" * int(item["importance"] * 50)
            print(f"  {item['rank']:<5} | {item['feature']:<38} | {item['importance']:<18.6f} | {bar}")
        print("  =======================================================================================")

        # 9. Chronological Actual vs Predicted Samples
        best_preds = tuning_results["predictions"][best_name]["test"]
        samples = trainer.generate_actual_vs_predicted_table(
            y_true=ml_data["y_test"],
            y_pred=best_preds,
            df_test=ml_data["test_dataframe"],
            limit=12,
        )

        print("\n  =======================================================================================")
        print("               SAMPLE CHRONOLOGICAL ACTUAL VS PREDICTED (TOP 12 TEST OBSERVATIONS)       ")
        print("  =======================================================================================")
        print(f"  {'#':<3} | {'Market':<20} | {'Commodity':<12} | {'Date':<10} | {'Actual (Rs.)':<12} | {'Pred (Rs.)':<12} | {'Error (Rs.)':<12} | {'% Error'}")
        print("  " + "-" * 100)

        for s in samples:
            print(f"  {s['sample_index']:<3} | {s.get('market','N/A')[:20]:<20} | {s.get('commodity','N/A'):<12} | {s.get('arrival_date','N/A'):<10} | Rs.{s['actual_price']:<8.2f} | Rs.{s['predicted_price']:<8.2f} | Rs.{s['error']:<+8.2f} | {s['error_pct']:<+6.2f}%")
        print("  =======================================================================================")

        # 10. Save Final Production Artifacts
        print("\n  [4/5] Serializing and saving final production model, preprocessor, and metadata...")
        saved_paths = trainer.save_model_artifacts(tuning_results, builder_instance=builder)

        print(f"        -> Production Model Artifact : {saved_paths['model_path']}")
        print(f"        -> Preprocessor Artifact     : {saved_paths['preprocessor_path']}")
        print(f"        -> Metadata JSON Summary     : {saved_paths['metadata_path']}")

        print_separator("-")
        print(" [PHASE 5B SUCCESS] Model validation, hyperparameter tuning & production selection completed!")

    except Exception as e:
        print(f"\n [ERROR] Phase 5B tuning pipeline encountered an error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
