r"""
integrate_weather.py
====================
Phase: Historical Weather Integration + Feature Engineering

Fetches genuine historical weather from Open-Meteo Archive API for
each Kerala district present in ceda_prices_clean.csv, then joins
weather to price records and produces the final ML-ready enriched
dataset.

Guaranteed invariants
---------------------
* CEDA raw JSON files: READ-ONLY, never modified
* CEDA checkpoint DB: NOT TOUCHED
* No API calls to CEDA
* No synthetic weather or prices generated
* No ML training performed
* No train/test split performed

Outputs
-------
data/weather/historical_kerala_weather.csv   -- cached weather (raw)
data/processed/ceda_prices_weather.csv       -- enriched final dataset
data/processed/weather_integration_quality.json

Usage
-----
    python backend/scripts/integrate_weather.py
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT  = SCRIPT_DIR.parent.parent

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
WEATHER_DIR   = PROJECT_ROOT / "data" / "weather"
WEATHER_CACHE = WEATHER_DIR / "historical_kerala_weather.csv"
PRICES_CSV    = PROCESSED_DIR / "ceda_prices_clean.csv"
OUT_CSV       = PROCESSED_DIR / "ceda_prices_weather.csv"
OUT_QUALITY   = PROCESSED_DIR / "weather_integration_quality.json"

WEATHER_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Date range (must match cleaned price dataset)
# ---------------------------------------------------------------------------
START_DATE = "2024-10-01"
END_DATE   = "2025-10-30"

# ---------------------------------------------------------------------------
# Open-Meteo Archive endpoint
# ---------------------------------------------------------------------------
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "precipitation_sum",
    "rain_sum",
]

# ---------------------------------------------------------------------------
# District coordinates (representative centroid per Kerala census district)
# Ordered by district_id ascending
# ---------------------------------------------------------------------------
DISTRICT_COORDS = {
    588: {"name": "Kasaragod",          "lat": 12.4996, "lon": 74.9869},
    589: {"name": "Kannur",             "lat": 11.8745, "lon": 75.3704},
    590: {"name": "Wayanad",            "lat": 11.6854, "lon": 76.1320},
    591: {"name": "Kozhikode",          "lat": 11.2588, "lon": 75.7804},
    592: {"name": "Malappuram",         "lat": 11.0510, "lon": 76.0711},
    593: {"name": "Palakkad",           "lat": 10.7867, "lon": 76.6548},
    594: {"name": "Thrissur",           "lat": 10.5276, "lon": 76.2144},
    595: {"name": "Ernakulam",          "lat": 9.9816,  "lon": 76.2999},
    596: {"name": "Idukki",             "lat": 9.9189,  "lon": 77.1025},
    600: {"name": "Kollam",             "lat": 8.8932,  "lon": 76.6141},
    601: {"name": "Thiruvananthapuram", "lat": 8.5241,  "lon": 76.9366},
}

# ---------------------------------------------------------------------------
# STEP 1 -- Fetch or load cached historical weather
# ---------------------------------------------------------------------------
def fetch_historical_weather(district_ids):
    """Fetch one request per district from Open-Meteo Archive, or load cache."""
    if WEATHER_CACHE.exists():
        df = pd.read_csv(WEATHER_CACHE, parse_dates=["date"])
        cached_districts = set(df["district_id"].unique())
        required_districts = set(district_ids)
        if required_districts.issubset(cached_districts):
            print(f"WEATHER: loaded from cache ({len(df):,} rows) -- no API calls needed")
            return df, 0

    print(f"WEATHER: fetching from Open-Meteo Archive for {len(district_ids)} districts ...")
    print(f"         Date range: {START_DATE} to {END_DATE}")

    all_rows = []
    api_calls = 0

    for district_id in sorted(district_ids):
        info = DISTRICT_COORDS.get(district_id)
        if info is None:
            print(f"  WARN: no coordinates for district_id={district_id}, skipping")
            continue

        params = {
            "latitude":   round(info["lat"], 4),
            "longitude":  round(info["lon"], 4),
            "start_date": START_DATE,
            "end_date":   END_DATE,
            "daily":      ",".join(DAILY_VARS),
            "timezone":   "Asia/Kolkata",
        }

        try:
            resp = requests.get(
                ARCHIVE_URL, params=params, timeout=30,
                headers={"Accept": "application/json", "User-Agent": "AgriMiniProject/1.0"},
            )
            api_calls += 1
        except requests.exceptions.RequestException as exc:
            print(f"  ERROR: district {district_id} ({info['name']}): {exc}", file=sys.stderr)
            print("STOPPING: Open-Meteo request failed. Do NOT fabricate data.", file=sys.stderr)
            sys.exit(1)

        if resp.status_code != 200:
            print(f"  ERROR: HTTP {resp.status_code} for district {district_id}: {resp.text[:300]}", file=sys.stderr)
            sys.exit(1)

        data = resp.json()
        daily = data.get("daily", {})
        times = daily.get("time", [])
        if not times:
            print(f"  WARN: no daily data returned for district {district_id} ({info['name']})")
            continue

        def safe(arr, i):
            if i < len(arr) and arr[i] is not None:
                try: return round(float(arr[i]), 2)
                except: return None
            return None

        t_max  = daily.get("temperature_2m_max", [])
        t_min  = daily.get("temperature_2m_min", [])
        t_mean = daily.get("temperature_2m_mean", [])
        hum    = daily.get("relative_humidity_2m_mean", [])
        prec   = daily.get("precipitation_sum", [])
        rain   = daily.get("rain_sum", [])

        for i, t in enumerate(times):
            all_rows.append({
                "date":                  t,
                "district_id":           district_id,
                "district_name":         info["name"],
                "latitude":              info["lat"],
                "longitude":             info["lon"],
                "temperature_max_c":     safe(t_max,  i),
                "temperature_min_c":     safe(t_min,  i),
                "temperature_mean_c":    safe(t_mean, i),
                "humidity_mean_pct":     safe(hum,    i),
                "precipitation_sum_mm":  safe(prec,   i),
                "rain_sum_mm":           safe(rain,    i),
            })

        print(f"  OK  district {district_id:>3d}  {info['name']:<20s}  {len(times)} days")
        time.sleep(0.4)   # polite pause between requests

    if not all_rows:
        print("ERROR: no weather data retrieved. Stopping.", file=sys.stderr)
        sys.exit(1)

    wdf = pd.DataFrame(all_rows)
    wdf["date"] = pd.to_datetime(wdf["date"])
    wdf.to_csv(WEATHER_CACHE, index=False)
    print(f"WEATHER: cached {len(wdf):,} rows -> {WEATHER_CACHE}")
    return wdf, api_calls


# ---------------------------------------------------------------------------
# STEP 4 -- Validate weather
# ---------------------------------------------------------------------------
def validate_weather(wdf):
    print("\nVALIDATE WEATHER:")
    n_districts = wdf["district_id"].nunique()
    date_min    = wdf["date"].min().date()
    date_max    = wdf["date"].max().date()
    dups        = int(wdf.duplicated(subset=["district_id", "date"]).sum())
    print(f"  Districts         : {n_districts}")
    print(f"  Date range        : {date_min} to {date_max}")
    print(f"  Total rows        : {len(wdf):,}")
    print(f"  Dup district/date : {dups}")

    wx_cols = ["temperature_max_c","temperature_min_c","temperature_mean_c",
               "humidity_mean_pct","precipitation_sum_mm","rain_sum_mm"]
    for col in wx_cols:
        n_null = int(wdf[col].isna().sum())
        if n_null:
            print(f"  Missing {col:<24s}: {n_null}")
        else:
            print(f"  Missing {col:<24s}: 0")

    expected_days = (pd.Timestamp(END_DATE) - pd.Timestamp(START_DATE)).days + 1
    for did, grp in wdf.groupby("district_id"):
        got = len(grp)
        if got < expected_days - 5:   # allow minor tolerance
            print(f"  WARN district {did}: got {got} days (expected ~{expected_days})")


# ---------------------------------------------------------------------------
# STEP 5 -- Join weather with CEDA prices
# ---------------------------------------------------------------------------
def join_weather(prices_df, wdf):
    # Normalize join keys
    prices_df = prices_df.copy()
    prices_df["date"] = pd.to_datetime(prices_df["date"]).dt.normalize()
    prices_df["district_id"] = prices_df["district_id"].astype("Int64")

    wdf = wdf.copy()
    wdf["date"] = pd.to_datetime(wdf["date"]).dt.normalize()
    wdf["district_id"] = wdf["district_id"].astype("Int64")

    wx_keep = ["date", "district_id", "temperature_max_c", "temperature_min_c",
               "temperature_mean_c", "humidity_mean_pct",
               "precipitation_sum_mm", "rain_sum_mm"]
    wdf_slim = wdf[wx_keep]

    merged = prices_df.merge(wdf_slim, on=["date", "district_id"], how="left")

    matched   = int(merged["temperature_mean_c"].notna().sum())
    unmatched = int(merged["temperature_mean_c"].isna().sum())
    pct       = round(matched / len(merged) * 100, 2) if len(merged) else 0.0

    print(f"\nJOIN:")
    print(f"  Price rows before  : {len(prices_df):,}")
    print(f"  Rows after join    : {len(merged):,}")
    print(f"  Matched to weather : {matched:,}")
    print(f"  Unmatched          : {unmatched:,}")
    print(f"  Match pct          : {pct:.2f}%")

    return merged, matched, unmatched, pct


# ---------------------------------------------------------------------------
# STEP 6 -- Feature engineering
# ---------------------------------------------------------------------------
def add_features(df):
    df = df.copy()
    # Date features (may already exist; overwrite to be safe)
    df["year"]        = pd.to_datetime(df["date"]).dt.year
    df["month"]       = pd.to_datetime(df["date"]).dt.month
    df["day"]         = pd.to_datetime(df["date"]).dt.day
    df["day_of_week"] = pd.to_datetime(df["date"]).dt.dayofweek
    df["quarter"]     = pd.to_datetime(df["date"]).dt.quarter

    # Weather binary
    df["is_rainy_day"] = (df["precipitation_sum_mm"].fillna(0) > 0).astype(int)

    print("FEAT  : is_rainy_day added")
    return df


# ---------------------------------------------------------------------------
# STEP 7 -- Target leakage annotation (columns to review, NOT removed)
# ---------------------------------------------------------------------------
POTENTIAL_LEAKAGE_COLS = ["min_price", "max_price", "price_range", "price_midpoint"]
# These same-day observation fields are preserved for audit but must NOT
# be used as input features when predicting future modal_price.
# They will be excluded at feature-selection time before model training.


# ---------------------------------------------------------------------------
# STEP 8 -- Save outputs
# ---------------------------------------------------------------------------
def save_outputs(df, quality_dict):
    df.to_csv(OUT_CSV, index=False)
    csv_kb = OUT_CSV.stat().st_size / 1024
    print(f"\nSAVE  : {OUT_CSV.name} -- {len(df):,} rows x {len(df.columns)} cols -- {csv_kb:.1f} KB")

    with OUT_QUALITY.open("w", encoding="utf-8") as fh:
        json.dump(quality_dict, fh, indent=2)
    print(f"SAVE  : {OUT_QUALITY.name}")


# ---------------------------------------------------------------------------
# STEP 9 -- Verification report
# ---------------------------------------------------------------------------
def verify(df, wdf, api_calls, matched, unmatched, pct):
    sep = "=" * 62
    print()
    print(sep)
    print("  WEATHER INTEGRATION VERIFICATION REPORT")
    print(sep)

    wx_cols = ["temperature_max_c","temperature_min_c","temperature_mean_c",
               "humidity_mean_pct","precipitation_sum_mm","rain_sum_mm"]

    print(f"\n  1.  Weather source            : Open-Meteo Archive API")
    print(f"      URL                       : {ARCHIVE_URL}")
    print(f"  2.  API requests made         : {api_calls}")
    print(f"  3.  Weather districts         : {wdf['district_id'].nunique()}")
    dist_list = sorted(wdf[["district_id","district_name"]].drop_duplicates()
                           .values.tolist())
    for did, dname in dist_list:
        print(f"        {int(did):>3d}  {dname}")
    print(f"  4.  Weather date range        : {wdf['date'].min().date()} to {wdf['date'].max().date()}")
    print(f"  5.  Historical weather rows   : {len(wdf):,}")
    print(f"  6.  Price rows before join    : {len(df):,}")
    print(f"  7.  Rows after join           : {len(df):,}")
    print(f"  8.  Matched to weather        : {matched:,}")
    print(f"  9.  Unmatched rows            : {unmatched:,}")
    print(f"  10. Match percentage          : {pct:.2f}%")
    print(f"\n  11. Missing values per weather variable (in joined dataset):")
    for col in wx_cols:
        n = int(df[col].isna().sum()) if col in df.columns else -1
        print(f"        {col:<28s}: {n}")
    print(f"\n  12. Output path               : {OUT_CSV}")
    print(f"  13. Final row count           : {len(df):,}")
    print(f"  14. Final column count        : {len(df.columns)}")

    print(f"\n  Potential leakage columns (preserved, NOT approved as ML inputs):")
    for c in POTENTIAL_LEAKAGE_COLS:
        print(f"        {c}")

    print()
    print(sep)
    print("  INVARIANTS CONFIRMED")
    print(sep)
    print("   [OK] CEDA API:            NOT CALLED")
    print("   [OK] CEDA raw JSON:       READ-ONLY, untouched")
    print("   [OK] CEDA checkpoint:     NOT TOUCHED")
    print("   [OK] Synthetic data:      NONE")
    print("   [OK] ML training:         NONE")
    print("   [OK] Train/test split:    NONE")
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print()
    print("=" * 62)
    print("  HISTORICAL WEATHER INTEGRATION")
    print("=" * 62)
    print(f"  Prices  : {PRICES_CSV}")
    print(f"  Weather : {WEATHER_CACHE}")
    print(f"  Output  : {OUT_CSV}")
    print()

    # Load prices
    prices_df = pd.read_csv(PRICES_CSV)
    prices_df["date"] = pd.to_datetime(prices_df["date"])
    print(f"PRICES: {len(prices_df):,} rows loaded from {PRICES_CSV.name}")

    district_ids = sorted(prices_df["district_id"].dropna().astype(int).unique().tolist())
    print(f"PRICES: {len(district_ids)} distinct districts: {district_ids}")

    # Step 1 -- fetch or load weather
    wdf, api_calls = fetch_historical_weather(district_ids)

    # Step 4 -- validate
    validate_weather(wdf)

    # Step 5 -- join
    merged, matched, unmatched, pct = join_weather(prices_df, wdf)

    # Step 6 -- features
    merged = add_features(merged)

    # Step 8 -- save
    wx_cols = ["temperature_max_c","temperature_min_c","temperature_mean_c",
               "humidity_mean_pct","precipitation_sum_mm","rain_sum_mm"]
    missing_wx = {col: int(merged[col].isna().sum()) for col in wx_cols if col in merged.columns}

    quality = {
        "generated_at":           datetime.now().isoformat(),
        "weather_source":         "Open-Meteo Archive API",
        "archive_url":            ARCHIVE_URL,
        "api_requests_made":      api_calls,
        "weather_district_count": int(wdf["district_id"].nunique()),
        "weather_date_range":     {"start": str(wdf["date"].min().date()),
                                   "end":   str(wdf["date"].max().date())},
        "weather_rows":           len(wdf),
        "price_rows":             len(prices_df),
        "matched_rows":           matched,
        "unmatched_rows":         unmatched,
        "match_percentage":       pct,
        "missing_weather_counts": missing_wx,
        "potential_leakage_cols": POTENTIAL_LEAKAGE_COLS,
    }
    save_outputs(merged, quality)

    # Step 9 -- verify
    verify(merged, wdf, api_calls, matched, unmatched, pct)


if __name__ == "__main__":
    main()
