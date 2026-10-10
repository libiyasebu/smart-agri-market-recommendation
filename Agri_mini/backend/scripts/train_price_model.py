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
    parser = argparse.ArgumentParser(description="Train and Evaluate Agricultural Price Prediction Models (Phase 5A)")
    parser.add_argument("--test-size", type=float, default=0.2, help="Chronological test set proportion (default: 0.2)")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    print_separator()
    print("  AGRICULTURAL PRICE PREDICTION -- BASELINE MODELS & XGBOOST REGRESSION (Phase 5A)")
    print_separator()

    db_info = check_db_connection()
    print(f"  Source Database   : {db_info['database_name']} (User: {db_info['current_user']}, Server: {db_info['server_version']})")
    print(f"  Target Variable   : modal_price (INR per quintal)")
    print(f"  Chronological Split: 80% Train / 20% Test")
    print_separator("-")

    db = SessionLocal()
    try:
        # 1. Load ML dataset using MLDatasetBuilder
        print("  [1/4] Loading and preparing leakage-free ML dataset from PostgreSQL...")
        builder = MLDatasetBuilder(db=db)
        ml_data = builder.prepare_ml_dataset(test_size=args.test_size, db=db)

        print(f"        -> X_train shape: {ml_data['X_train'].shape} (Dates: {ml_data['train_date_range']['start']} to {ml_data['train_date_range']['end']})")
        print(f"        -> X_test shape : {ml_data['X_test'].shape} (Dates: {ml_data['test_date_range']['start']} to {ml_data['test_date_range']['end']})")
        print(f"        -> Total model features: {len(ml_data['feature_names'])}")

        # 2. Train and evaluate all candidate models
        print("\n  [2/4] Training and evaluating candidate regression models...")
        trainer = ModelTrainingService(random_state=args.random_state)
        eval_results = trainer.train_and_evaluate(ml_data)

        # 3. Model Comparison Table (Test Set)
        print("\n  =======================================================================================")
        print("                         MODEL PERFORMANCE COMPARISON (CHRONOLOGICAL TEST SET)           ")
        print("  =======================================================================================")
        print(f"  {'Model Name':<24} | {'Test MAE (Rs.)':<14} | {'Test RMSE (Rs.)':<15} | {'Test R^2':<10} | {'Test MAPE (%)':<12}")
        print("  " + "-" * 87)

        for model_name, metrics in eval_results["results"].items():
            t = metrics["test"]
            print(f"  {model_name:<24} | Rs. {t['mae']:<10.2f} | Rs. {t['rmse']:<11.2f} | {t['r2']:<10.4f} | {t['mape']:<8.2f}%")
        print("  =======================================================================================")

        # 4. Overfitting Analysis Table
        print("\n  =======================================================================================")
        print("                                  TRAIN VS TEST OVERFITTING ANALYSIS                     ")
        print("  =======================================================================================")
        print(f"  {'Model Name':<24} | {'Train MAE':<11} | {'Test MAE':<11} | {'Train R^2':<10} | {'Test R^2':<10} | {'Status':<12}")
        print("  " + "-" * 87)

        for model_name, metrics in eval_results["results"].items():
            tr = metrics["train"]
            te = metrics["test"]
            mae_gap = te["mae"] - tr["mae"]
            status = "Optimal" if abs(mae_gap) < 30.0 else ("Moderate Gap" if mae_gap < 80.0 else "High Overfit")
            print(f"  {model_name:<24} | Rs.{tr['mae']:<7.2f} | Rs.{te['mae']:<7.2f} | {tr['r2']:<10.4f} | {te['r2']:<10.4f} | {status:<12}")
        print("  =======================================================================================")

        # 5. Best Model Declaration
        best_name = eval_results["best_model_name"]
        best_test = eval_results["results"][best_name]["test"]
        print(f"\n  [3/4] Best Model Selected: >>> {best_name.upper()} <<<")
        print(f"        -> Test MAE  : Rs. {best_test['mae']:.2f} / quintal")
        print(f"        -> Test RMSE : Rs. {best_test['rmse']:.2f} / quintal")
        print(f"        -> Test R^2  : {best_test['r2']:.4f}")
        print(f"        -> Test MAPE : {best_test['mape']:.2f}%")
        print(f"        -> Selection Basis: Lowest measured Test MAE and RMSE on untouched chronological test set.")

        # 6. Top 15 XGBoost Feature Importances
        print("\n  =======================================================================================")
        print("                             TOP 15 XGBOOST FEATURE IMPORTANCES                          ")
        print("  =======================================================================================")
        print(f"  {'Rank':<5} | {'Feature Name':<38} | {'Importance Score':<18} | {'Bar'}")
        print("  " + "-" * 87)

        top_15 = eval_results["xgb_feature_importance"][:15]
        for item in top_15:
            bar = "#" * int(item["importance"] * 50)
            print(f"  {item['rank']:<5} | {item['feature']:<38} | {item['importance']:<18.6f} | {bar}")
        print("  =======================================================================================")

        # 7. Actual vs Predicted Samples
        best_preds = eval_results["predictions"][best_name]["test"]
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
            print(f"  {s['sample_index']:<3} | {s.get('market','N/A')[:20]:<20} | {s.get('commodity','N/A')[:12]:<12} | {s.get('arrival_date','N/A'):<10} | Rs.{s['actual_price']:<8.2f} | Rs.{s['predicted_price']:<8.2f} | Rs.{s['error']:<+8.2f} | {s['error_pct']:<+6.2f}%")
        print("  =======================================================================================")

        # 8. Save Artifacts
        print("\n  [4/4] Serializing and saving trained model, preprocessor, and metadata...")
        saved_paths = trainer.save_model_artifacts(eval_results, builder_instance=builder)

        print(f"        -> Trained Model Artifact : {saved_paths['model_path']}")
        print(f"        -> Preprocessor Artifact  : {saved_paths['preprocessor_path']}")
        print(f"        -> Metadata JSON Summary  : {saved_paths['metadata_path']}")

        print_separator("-")
        print(" [MODEL SUCCESS] Phase 5A baseline and XGBoost price prediction models completed successfully!")

    except Exception as e:
        print(f"\n [MODEL FAILURE] Training pipeline encountered an error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
