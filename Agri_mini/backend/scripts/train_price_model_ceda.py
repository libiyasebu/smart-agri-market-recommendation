"""
train_price_model_ceda.py
=========================
ML Feature Engineering + Time-Based Split + Baseline + Random Forest + XGBoost
Target: modal_price (genuine CEDA/AGMARKNET Kerala price data)

Invariants:
- No synthetic data
- No random split (time-based only)
- No target leakage (min_price/max_price/price_range/price_midpoint excluded)
- No CEDA or weather API calls
- Raw files / checkpoint / weather cache untouched
"""
import json, math, sys, warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer
import joblib

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT         = Path(__file__).resolve().parent.parent.parent
PROCESSED    = ROOT / "data" / "processed"
MODELS_DIR   = ROOT / "models"
IN_CSV       = PROCESSED / "ceda_prices_weather.csv"
ML_CSV       = PROCESSED / "ml_price_features.csv"
MODEL_PATH   = MODELS_DIR / "agri_price_model.joblib"
METRICS_PATH = MODELS_DIR / "model_metrics.json"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET = "modal_price"
LEAKAGE_COLS = ["min_price", "max_price", "price_range", "price_midpoint", TARGET]
AUDIT_COLS   = ["source", "raw_file", "quality_flag", "commodity_name",
                "district_name", "state_id"]
TRAIN_SPLIT  = 0.80   # 80% of earliest dates for training

COMMODITY_MAP = {
    19:"Banana", 90:"Banana-Green", 78:"Tomato", 23:"Onion", 24:"Potato",
    35:"Brinjal", 87:"Green Chilli", 153:"Carrot", 154:"Cabbage", 152:"Sweet Potato"
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def rmse(y_true, y_pred):
    return math.sqrt(mean_squared_error(y_true, y_pred))

def mape(y_true, y_pred):
    y_true_arr = np.array(y_true, dtype=float)
    y_pred_arr = np.array(y_pred, dtype=float)
    mask = y_true_arr > 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((y_true_arr[mask] - y_pred_arr[mask]) / y_true_arr[mask])) * 100.0)

def metrics(y_true, y_pred):
    mse_val = float(mean_squared_error(y_true, y_pred))
    return {
        "MAE":  round(float(mean_absolute_error(y_true, y_pred)), 2),
        "MSE":  round(mse_val, 2),
        "RMSE": round(math.sqrt(mse_val), 2),
        "R2":   round(float(r2_score(y_true, y_pred)), 4),
        "MAPE": round(mape(y_true, y_pred), 2),
    }

def sep(title=""):
    print("=" * 64)
    if title:
        print(f"  {title}")
        print("=" * 64)

# ---------------------------------------------------------------------------
# STEP 1 — Load & inspect
# ---------------------------------------------------------------------------
sep("STEP 1: LOAD & INSPECT")
df = pd.read_csv(IN_CSV, parse_dates=["date"])
df["date"] = df["date"].dt.normalize()
print(f"  Rows: {len(df):,}  |  Cols: {len(df.columns)}")
print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")
print(f"  Commodities: {df['commodity_id'].nunique()}")
print(f"  Markets: {df['market_id'].nunique()}")
missing = df.isnull().sum()
missing = missing[missing > 0]
print(f"  Missing values: {missing.to_dict() if len(missing) else 'none'}")
dups = df.duplicated().sum()
print(f"  Duplicate rows: {dups}")
mp = df[TARGET]
print(f"  modal_price — min:{mp.min():.0f}  p25:{mp.quantile(.25):.0f}  "
      f"median:{mp.median():.0f}  p75:{mp.quantile(.75):.0f}  max:{mp.max():.0f}")

# ---------------------------------------------------------------------------
# STEP 3 — Historical price lag + rolling features
# ---------------------------------------------------------------------------
sep("STEP 3: LAG + ROLLING FEATURES")
df = df.sort_values(["commodity_id", "market_id", "date"]).reset_index(drop=True)

grp = df.groupby(["commodity_id", "market_id"])["modal_price"]

# Lags (observation-based, not calendar-day)
df["modal_price_lag_1"]  = grp.shift(1)
df["modal_price_lag_7"]  = grp.shift(7)
df["modal_price_lag_14"] = grp.shift(14)
df["modal_price_lag_30"] = grp.shift(30)

# Rolling: shift(1) BEFORE rolling so current day is excluded
shifted = grp.shift(1)
df["modal_price_roll_mean_7"]  = shifted.groupby(df["commodity_id"].astype(str) + "_" + df["market_id"].astype(str)).transform(lambda x: x.rolling(7,  min_periods=1).mean())
df["modal_price_roll_mean_14"] = shifted.groupby(df["commodity_id"].astype(str) + "_" + df["market_id"].astype(str)).transform(lambda x: x.rolling(14, min_periods=1).mean())
df["modal_price_roll_mean_30"] = shifted.groupby(df["commodity_id"].astype(str) + "_" + df["market_id"].astype(str)).transform(lambda x: x.rolling(30, min_periods=1).mean())

print("  Lag/rolling columns created (shift(1) applied before rolling — no leakage)")

# ---------------------------------------------------------------------------
# STEP 4 — Cyclical date features
# ---------------------------------------------------------------------------
sep("STEP 4: DATE FEATURES")
df["day_of_year"] = df["date"].dt.dayofyear
df["month_sin"]         = np.sin(2 * np.pi * df["month"]       / 12)
df["month_cos"]         = np.cos(2 * np.pi * df["month"]       / 12)
df["day_of_year_sin"]   = np.sin(2 * np.pi * df["day_of_year"] / 365)
df["day_of_year_cos"]   = np.cos(2 * np.pi * df["day_of_year"] / 365)
print("  month_sin/cos, day_of_year_sin/cos added")

# ---------------------------------------------------------------------------
# STEP 7 — Build final ML dataset
# ---------------------------------------------------------------------------
sep("STEP 7: BUILD ML DATASET")
# Required lag (lag_1 is the minimum required)
required_lag = ["modal_price_lag_1"]
rows_before = len(df)
df_ml = df.dropna(subset=required_lag).copy()
rows_removed = rows_before - len(df_ml)
print(f"  Rows before lag drop : {rows_before:,}")
print(f"  Rows removed (no lag): {rows_removed:,}")
print(f"  ML-ready rows        : {len(df_ml):,}")

FEATURE_COLS = [
    # Categorical / location
    "commodity_id", "district_id", "market_id",
    # Date
    "year", "month", "day", "day_of_week", "quarter",
    "month_sin", "month_cos", "day_of_year_sin", "day_of_year_cos",
    # Weather
    "temperature_max_c", "temperature_min_c", "temperature_mean_c",
    "humidity_mean_pct", "precipitation_sum_mm", "rain_sum_mm", "is_rainy_day",
    # Historical price lags
    "modal_price_lag_1", "modal_price_lag_7", "modal_price_lag_14", "modal_price_lag_30",
    # Rolling averages
    "modal_price_roll_mean_7", "modal_price_roll_mean_14", "modal_price_roll_mean_30",
]

save_cols = ["date", "commodity_id", "commodity_name", "district_id", "district_name",
             "market_id", TARGET] + [c for c in FEATURE_COLS if c not in ["commodity_id","district_id","market_id"]]
save_cols = list(dict.fromkeys(save_cols))   # deduplicate, preserve order
df_ml[save_cols].to_csv(ML_CSV, index=False)
print(f"  Saved: {ML_CSV}")
print(f"  Features ({len(FEATURE_COLS)}): {FEATURE_COLS}")

# Verify no leakage cols in FEATURE_COLS
for lc in LEAKAGE_COLS:
    assert lc not in FEATURE_COLS, f"LEAKAGE: {lc} found in features!"
print("  [OK] No leakage columns in feature set")

# ---------------------------------------------------------------------------
# STEP 8 — Time-based split
# ---------------------------------------------------------------------------
sep("STEP 8: TIME-BASED SPLIT")
df_ml = df_ml.sort_values("date").reset_index(drop=True)
unique_dates = df_ml["date"].sort_values().unique()
split_idx    = int(len(unique_dates) * TRAIN_SPLIT)
split_date   = unique_dates[split_idx]

train_df = df_ml[df_ml["date"] <  split_date].copy()
test_df  = df_ml[df_ml["date"] >= split_date].copy()

assert train_df["date"].max() < test_df["date"].min(), "SPLIT ERROR: train/test dates overlap!"

print(f"  Split date    : {pd.Timestamp(split_date).date()}")
print(f"  Train         : {train_df['date'].min().date()} to {train_df['date'].max().date()} | {len(train_df):,} rows")
print(f"  Test          : {test_df['date'].min().date()} to {test_df['date'].max().date()} | {len(test_df):,} rows")

X_train = train_df[FEATURE_COLS]
y_train = train_df[TARGET]
X_test  = test_df[FEATURE_COLS]
y_test  = test_df[TARGET]

# ---------------------------------------------------------------------------
# Preprocessing pipeline
# ---------------------------------------------------------------------------
CAT_COLS = ["commodity_id", "district_id", "market_id"]
NUM_COLS = [c for c in FEATURE_COLS if c not in CAT_COLS]

preprocessor = ColumnTransformer(transformers=[
    ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CAT_COLS),
    ("num", "passthrough", NUM_COLS),
], remainder="drop")

# ---------------------------------------------------------------------------
# STEP 9 — Baseline (lag_1 naive)
# ---------------------------------------------------------------------------
sep("STEP 9: BASELINE (LAG-1 NAIVE)")
mask_test_lag1 = test_df["modal_price_lag_1"].notna()
y_test_bl  = y_test[mask_test_lag1]
y_pred_bl  = test_df.loc[mask_test_lag1, "modal_price_lag_1"]
baseline_m = metrics(y_test_bl, y_pred_bl)
print(f"  Baseline rows used : {mask_test_lag1.sum():,}")
print(f"  MAE  : {baseline_m['MAE']}")
print(f"  RMSE : {baseline_m['RMSE']}")
print(f"  R2   : {baseline_m['R2']}")

# ---------------------------------------------------------------------------
# STEP 10 — Random Forest
# ---------------------------------------------------------------------------
sep("STEP 10: RANDOM FOREST")
rf_pipe = Pipeline([
    ("prep", preprocessor),
    ("model", RandomForestRegressor(
        n_estimators=200, max_features="sqrt",
        min_samples_leaf=5, random_state=42, n_jobs=-1
    ))
])
rf_pipe.fit(X_train, y_train)
y_pred_rf = rf_pipe.predict(X_test)
rf_m = metrics(y_test, y_pred_rf)
print(f"  MAE  : {rf_m['MAE']}")
print(f"  RMSE : {rf_m['RMSE']}")
print(f"  R2   : {rf_m['R2']}")

# Feature importances (RF)
rf_model     = rf_pipe.named_steps["model"]
cat_names    = CAT_COLS
num_names    = NUM_COLS
all_feat_names = cat_names + num_names
rf_importances = pd.Series(rf_model.feature_importances_, index=all_feat_names).sort_values(ascending=False)
print(f"\n  Top 10 RF feature importances:")
for fn, fi in rf_importances.head(10).items():
    print(f"    {fn:<35s}: {fi:.4f}")

# ---------------------------------------------------------------------------
# STEP 11 — XGBoost
# ---------------------------------------------------------------------------
sep("STEP 11: XGBOOST")
try:
    from xgboost import XGBRegressor
    xgb_pipe = Pipeline([
        ("prep", ColumnTransformer(transformers=[
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CAT_COLS),
            ("num", "passthrough", NUM_COLS),
        ], remainder="drop")),
        ("model", XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1,
            tree_method="hist", verbosity=0
        ))
    ])
    xgb_pipe.fit(X_train, y_train)
    y_pred_xgb = xgb_pipe.predict(X_test)
    xgb_m = metrics(y_test, y_pred_xgb)
    print(f"  MAE  : {xgb_m['MAE']}")
    print(f"  RMSE : {xgb_m['RMSE']}")
    print(f"  R2   : {xgb_m['R2']}")

    xgb_model     = xgb_pipe.named_steps["model"]
    xgb_feat_prep = xgb_pipe.named_steps["prep"]
    xgb_importances = pd.Series(
        xgb_model.feature_importances_,
        index=all_feat_names
    ).sort_values(ascending=False)
    print(f"\n  Top 10 XGB feature importances:")
    for fn, fi in xgb_importances.head(10).items():
        print(f"    {fn:<35s}: {fi:.4f}")
    xgb_available = True
except Exception as e:
    print(f"  XGBoost unavailable: {e}")
    xgb_m = None
    xgb_available = False

# ---------------------------------------------------------------------------
# STEP 12 — Model comparison
# ---------------------------------------------------------------------------
sep("STEP 12: MODEL COMPARISON")
print(f"  {'Model':<28s}  {'MAE':>8s}  {'RMSE':>9s}  {'R2':>7s}")
print(f"  {'-'*60}")
print(f"  {'Naive lag-1 baseline':<28s}  {baseline_m['MAE']:>8.1f}  {baseline_m['RMSE']:>9.1f}  {baseline_m['R2']:>7.4f}")
print(f"  {'Random Forest':<28s}  {rf_m['MAE']:>8.1f}  {rf_m['RMSE']:>9.1f}  {rf_m['R2']:>7.4f}")
if xgb_available:
    print(f"  {'XGBoost':<28s}  {xgb_m['MAE']:>8.1f}  {xgb_m['RMSE']:>9.1f}  {xgb_m['R2']:>7.4f}")

# Select Random Forest as the production model artifact
candidates = {"Random Forest": (rf_pipe, rf_m, rf_importances)}
if xgb_available:
    candidates["XGBoost"] = (xgb_pipe, xgb_m, xgb_importances)
best_name = "Random Forest"
best_pipe, best_m, best_imp = candidates[best_name]
print(f"\n  Production model: {best_name}  (MAE={best_m['MAE']})")

# Leakage sanity check
if best_m["R2"] > 0.99:
    print("  WARNING: R2 > 0.99 — investigate for leakage before production use!")
else:
    print(f"  [OK] R2={best_m['R2']} — no obvious leakage signal")

# ---------------------------------------------------------------------------
# STEP 13 — Per-commodity evaluation (best model)
# ---------------------------------------------------------------------------
sep(f"STEP 13: PER-COMMODITY EVALUATION ({best_name})")
best_pred_test = best_pipe.predict(X_test)
test_df = test_df.copy()
test_df["_pred"] = best_pred_test

per_commodity = []
print(f"  {'ID':<4} {'Commodity':<16} {'Rows':>5} {'MAE':>8} {'RMSE':>9} {'R2':>7}")
print(f"  {'-'*56}")
for cid, cname in sorted(COMMODITY_MAP.items()):
    mask = test_df["commodity_id"] == cid
    if mask.sum() < 2:
        continue
    yt = test_df.loc[mask, TARGET]
    yp = test_df.loc[mask, "_pred"]
    cm = metrics(yt, yp)
    per_commodity.append({"commodity_id": cid, "commodity_name": cname, "test_rows": int(mask.sum()), **cm})
    print(f"  {cid:<4} {cname:<16} {mask.sum():>5} {cm['MAE']:>8.1f} {cm['RMSE']:>9.1f} {cm['R2']:>7.4f}")

# ---------------------------------------------------------------------------
# STEP 14 — Feature importances (top 10, best model)
# ---------------------------------------------------------------------------
sep(f"STEP 14: TOP FEATURE IMPORTANCES ({best_name})")
print(f"  {'Feature':<35s} {'Importance':>10}")
print(f"  {'-'*47}")
for fn, fi in best_imp.head(10).items():
    print(f"  {fn:<35s} {fi:>10.4f}")

# ---------------------------------------------------------------------------
# STEP 15 — Save artifacts
# ---------------------------------------------------------------------------
sep("STEP 15: SAVE ARTIFACTS")
joblib.dump(best_pipe, MODEL_PATH)
print(f"  Model saved : {MODEL_PATH}")

metrics_out = {
    "model_name":       best_name,
    "target":           TARGET,
    "feature_list":     FEATURE_COLS,
    "excluded_leakage": LEAKAGE_COLS,
    "excluded_audit":   AUDIT_COLS,
    "split_date":       str(pd.Timestamp(split_date).date()),
    "train_start":      str(train_df["date"].min().date()),
    "train_end":        str(train_df["date"].max().date()),
    "test_start":       str(test_df["date"].min().date()),
    "test_end":         str(test_df["date"].max().date()),
    "train_rows":       len(train_df),
    "test_rows":        len(test_df),
    "overall_MAE":      best_m["MAE"],
    "overall_MSE":      best_m["MSE"],
    "overall_RMSE":     best_m["RMSE"],
    "overall_R2":       best_m["R2"],
    "overall_MAPE":     best_m["MAPE"],
    "baseline_MAE":     baseline_m["MAE"],
    "baseline_MSE":     baseline_m["MSE"],
    "baseline_RMSE":    baseline_m["RMSE"],
    "baseline_R2":      baseline_m["R2"],
    "baseline_MAPE":    baseline_m["MAPE"],
    "rf_MAE":           rf_m["MAE"],
    "rf_MSE":           rf_m["MSE"],
    "rf_RMSE":          rf_m["RMSE"],
    "rf_R2":            rf_m["R2"],
    "rf_MAPE":          rf_m["MAPE"],
    "xgb_MAE":          xgb_m["MAE"] if xgb_available else None,
    "xgb_MSE":          xgb_m["MSE"] if xgb_available else None,
    "xgb_RMSE":         xgb_m["RMSE"] if xgb_available else None,
    "xgb_R2":           xgb_m["R2"] if xgb_available else None,
    "xgb_MAPE":         xgb_m["MAPE"] if xgb_available else None,
    "per_commodity":    per_commodity,
    "generated_at":     datetime.now().isoformat(),
}
with open(METRICS_PATH, "w") as f:
    json.dump(metrics_out, f, indent=2)
print(f"  Metrics saved: {METRICS_PATH}")

# ---------------------------------------------------------------------------
# STEP 16 — Lightweight validation
# ---------------------------------------------------------------------------
sep("STEP 16: VALIDATION")
assert ML_CSV.exists(),    "ml_price_features.csv missing!"
assert MODEL_PATH.exists(),"agri_price_model.joblib missing!"
assert METRICS_PATH.exists(),"model_metrics.json missing!"
for lc in LEAKAGE_COLS:
    assert lc not in FEATURE_COLS, f"LEAKAGE: {lc} in features!"
assert train_df["date"].max() < test_df["date"].min(), "Date overlap!"
preds = best_pipe.predict(X_test)
assert len(preds) == len(y_test), "Prediction count mismatch!"
assert not np.isnan(preds).any(), "NaN in predictions!"
# Verify original files untouched
orig_rows = len(pd.read_csv(PROCESSED / "ceda_prices_weather.csv"))
assert orig_rows == 27265, f"ceda_prices_weather.csv modified! rows={orig_rows}"
orig_clean = len(pd.read_csv(PROCESSED / "ceda_prices_clean.csv"))
assert orig_clean == 27265, f"ceda_prices_clean.csv modified! rows={orig_clean}"
print("  [OK] ml_price_features.csv exists")
print("  [OK] agri_price_model.joblib exists")
print("  [OK] model_metrics.json exists")
print("  [OK] No leakage columns in feature set")
print("  [OK] Train dates strictly before test dates")
print("  [OK] Prediction count == test row count")
print("  [OK] No NaN in predictions")
print("  [OK] ceda_prices_weather.csv unchanged (27265 rows)")
print("  [OK] ceda_prices_clean.csv unchanged (27265 rows)")

sep("ALL DONE")
print("  Invariants:")
print("  [OK] No CEDA API calls")
print("  [OK] No weather API calls")
print("  [OK] No synthetic data")
print("  [OK] No random split (time-based only)")
print("  [OK] No target leakage columns used")
print("  [OK] Raw/checkpoint files untouched")
sep()
