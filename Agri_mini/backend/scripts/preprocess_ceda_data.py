r"""
preprocess_ceda_data.py
=======================
Converts genuine CEDA/AGMARKNET raw JSON files into one clean,
ML-ready historical price dataset.

Source  : data/ceda_historical/raw/  (READ-ONLY -- never modified)
Output  : data/processed/ceda_prices_clean.csv
          data/processed/ceda_data_quality.json

Guaranteed invariants
---------------------
* Raw JSON files are opened read-only and never written/deleted.
* Checkpoint DB is never touched.
* No API calls are made.
* No synthetic / imputed prices are generated.
* No ML model is trained.

Usage
-----
    python backend/scripts/preprocess_ceda_data.py

Run from project root:
    D:\Agri_mini>  python backend/scripts/preprocess_ceda_data.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
BACKEND_DIR   = SCRIPT_DIR.parent
PROJECT_ROOT  = BACKEND_DIR.parent

RAW_DIR       = PROJECT_ROOT / "data" / "ceda_historical" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUT_CSV       = PROCESSED_DIR / "ceda_prices_clean.csv"
OUT_QUALITY   = PROCESSED_DIR / "ceda_data_quality.json"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Active commodity registry  (commodity_id -> canonical_name)
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

# ---------------------------------------------------------------------------
# STEP 1 -- LOAD all raw JSON files
# ---------------------------------------------------------------------------
def load_raw_files(raw_dir):
    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        print(f"ERROR: no JSON files found in {raw_dir}", file=sys.stderr)
        sys.exit(1)

    rows = []
    files_loaded = 0
    files_skipped = 0
    total_raw_records = 0

    for jf in json_files:
        try:
            with jf.open("r", encoding="utf-8") as fh:
                wrapper = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  WARN: cannot read {jf.name}: {exc}", file=sys.stderr)
            files_skipped += 1
            continue

        records = wrapper.get("records")
        if not isinstance(records, list):
            files_skipped += 1
            continue

        prov_district_name  = wrapper.get("district_name", "")
        prov_commodity_name = wrapper.get("commodity_name", "")
        prov_source         = wrapper.get("source", "CEDA_AGMARKNET")
        prov_raw_file       = jf.name

        for rec in records:
            row = dict(rec)
            row["_prov_district_name"]  = prov_district_name
            row["_prov_commodity_name"] = prov_commodity_name
            row["_prov_source"]         = prov_source
            row["_prov_raw_file"]       = prov_raw_file
            rows.append(row)

        total_raw_records += len(records)
        files_loaded += 1

    print(f"LOAD  : {files_loaded} files loaded, {files_skipped} skipped")
    print(f"LOAD  : {total_raw_records} raw records extracted")
    return pd.DataFrame(rows), total_raw_records


# ---------------------------------------------------------------------------
# STEP 2 -- NORMALIZE
# ---------------------------------------------------------------------------
def normalize(df):
    rename = {
        "date":                 "date_raw",
        "commodity_id":         "commodity_id",
        "census_state_id":      "state_id",
        "census_district_id":   "district_id",
        "market_id":            "market_id",
        "min_price":            "min_price",
        "max_price":            "max_price",
        "modal_price":          "modal_price",
        "_prov_district_name":  "district_name",
        "_prov_commodity_name": "commodity_name_raw",
        "_prov_source":         "source",
        "_prov_raw_file":       "raw_file",
    }
    existing_rename = {k: v for k, v in rename.items() if k in df.columns}
    df = df.rename(columns=existing_rename)

    df["commodity_name"] = (
        df["commodity_id"]
        .map(ACTIVE_COMMODITIES)
        .fillna(df.get("commodity_name_raw", "Unknown"))
    )

    # Parse ISO 8601 date strings (e.g. "2024-11-29T00:00:00.000Z")
    df["date"] = pd.to_datetime(df["date_raw"], utc=True, errors="coerce").dt.normalize()
    df["date"] = df["date"].dt.tz_localize(None)

    df["year"]        = df["date"].dt.year
    df["month"]       = df["date"].dt.month
    df["day"]         = df["date"].dt.day
    df["day_of_week"] = df["date"].dt.dayofweek
    df["quarter"]     = df["date"].dt.quarter

    for col in ("commodity_id", "state_id", "district_id", "market_id"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in ("min_price", "max_price", "modal_price"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = [
        "date", "year", "month", "day", "day_of_week", "quarter",
        "commodity_id", "commodity_name",
        "state_id", "district_id", "district_name", "market_id",
        "min_price", "max_price", "modal_price",
        "source", "raw_file",
    ]
    available = [c for c in keep if c in df.columns]
    df = df[available].copy()

    print(f"NORM  : {len(df)} rows after normalisation, {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# STEP 3 -- CLEAN
# ---------------------------------------------------------------------------
def clean(df):
    issues = {}

    issues["missing_date"]         = int(df["date"].isna().sum())
    issues["missing_commodity_id"] = int(df["commodity_id"].isna().sum())
    issues["missing_district_id"]  = int(df["district_id"].isna().sum())
    issues["missing_market_id"]    = int(df["market_id"].isna().sum())
    issues["missing_min_price"]    = int(df["min_price"].isna().sum())
    issues["missing_max_price"]    = int(df["max_price"].isna().sum())
    issues["missing_modal_price"]  = int(df["modal_price"].isna().sum())

    zero_min   = int((df["min_price"] == 0).sum())
    zero_max   = int((df["max_price"] == 0).sum())
    zero_modal = int((df["modal_price"] == 0).sum())
    neg_mask   = (df["min_price"] < 0) | (df["max_price"] < 0) | (df["modal_price"] < 0)
    neg_prices = int(neg_mask.sum())

    issues["zero_min_price"]   = zero_min
    issues["zero_max_price"]   = zero_max
    issues["zero_modal_price"] = zero_modal
    issues["negative_prices"]  = neg_prices

    min_gt_max     = int((df["min_price"] > df["max_price"]).sum())
    modal_low      = int((df["modal_price"] < df["min_price"]).sum())
    modal_high     = int((df["modal_price"] > df["max_price"]).sum())
    modal_outside  = int(
        ((df["modal_price"] < df["min_price"]) | (df["modal_price"] > df["max_price"])).sum()
    )
    issues["min_price_gt_max_price"]      = min_gt_max
    issues["modal_below_min"]             = modal_low
    issues["modal_above_max"]             = modal_high
    issues["modal_outside_min_max_range"] = modal_outside

    # Quality flag (bitfield)
    #   bit 0 (1)  = zero price in any field
    #   bit 1 (2)  = negative price (will be removed but flagged first)
    #   bit 2 (4)  = min_price > max_price
    #   bit 3 (8)  = modal_price outside [min, max]
    df = df.copy()
    df["quality_flag"] = 0

    zero_mask     = (df["min_price"] == 0) | (df["max_price"] == 0) | (df["modal_price"] == 0)
    min_gt_mask   = df["min_price"] > df["max_price"]
    modal_out_mask = (df["modal_price"] < df["min_price"]) | (df["modal_price"] > df["max_price"])

    df.loc[zero_mask,       "quality_flag"] |= 1
    df.loc[neg_mask,        "quality_flag"] |= 2
    df.loc[min_gt_mask,     "quality_flag"] |= 4
    df.loc[modal_out_mask,  "quality_flag"] |= 8

    # Remove negative-price rows (physically impossible)
    n_before_neg = len(df)
    df = df[~neg_mask].copy()
    n_removed_neg = n_before_neg - len(df)
    issues["removed_negative_price_rows"] = n_removed_neg

    # Remove exact duplicates
    dup_cols = ["date", "commodity_id", "district_id", "market_id",
                "min_price", "max_price", "modal_price"]
    n_before_dup = len(df)
    df = df.drop_duplicates(subset=dup_cols, keep="first")
    n_dupes = n_before_dup - len(df)
    issues["exact_duplicates_removed"] = n_dupes

    print(f"CLEAN : {n_dupes} exact duplicates removed")
    print(f"CLEAN : {n_removed_neg} negative-price rows removed")
    print(f"CLEAN : {len(df)} rows remaining after cleaning")
    return df, issues


# ---------------------------------------------------------------------------
# STEP 4 -- COMMODITY VALIDATION
# ---------------------------------------------------------------------------
def validate_commodities(df):
    before = len(df)
    df = df[df["commodity_id"].isin(ACTIVE_COMMODITIES.keys())].copy()
    removed = before - len(df)
    if removed:
        print(f"VALID : {removed} rows with non-active commodity IDs removed")
    else:
        print("VALID : all records belong to the 10 active commodities")
    return df


# ---------------------------------------------------------------------------
# STEP 5 -- DATA QUALITY FEATURES
# ---------------------------------------------------------------------------
def add_features(df):
    df = df.copy()
    df["price_range"]    = df["max_price"] - df["min_price"]
    df["price_midpoint"] = (df["min_price"] + df["max_price"]) / 2.0
    print("FEAT  : added price_range, price_midpoint")
    return df


# ---------------------------------------------------------------------------
# STEP 7 -- SAVE OUTPUT
# ---------------------------------------------------------------------------
def save_output(df, quality):
    df = df.sort_values(["commodity_id", "district_id", "market_id", "date"]).reset_index(drop=True)
    df.to_csv(OUT_CSV, index=False)
    csv_size_kb = OUT_CSV.stat().st_size / 1024

    quality_out = {
        "generated_at": datetime.now().isoformat(),
        "output_csv": str(OUT_CSV),
        "output_csv_size_kb": round(csv_size_kb, 1),
        **quality,
    }
    with OUT_QUALITY.open("w", encoding="utf-8") as fh:
        json.dump(quality_out, fh, indent=2)

    print(f"SAVE  : {OUT_CSV.name} -- {len(df)} rows -- {csv_size_kb:.1f} KB")
    print(f"SAVE  : {OUT_QUALITY.name}")


# ---------------------------------------------------------------------------
# STEP 8 -- VERIFY
# ---------------------------------------------------------------------------
def verify(df, raw_count, quality):
    sep = "=" * 60
    print()
    print(sep)
    print("  PREPROCESSING VERIFICATION REPORT")
    print(sep)

    print(f"\n  1. Raw records loaded           : {raw_count:,}")
    print(f"  2. Exact duplicates removed     : {quality.get('exact_duplicates_removed', 0):,}")
    print(f"  3. Final cleaned records        : {len(df):,}")
    print(f"  4. Number of commodities        : {df['commodity_id'].nunique()}")

    print("\n  5. Records per commodity:")
    comm_counts = (
        df.groupby(["commodity_id", "commodity_name"])
          .size().reset_index(name="records")
          .sort_values("commodity_id")
    )
    for _, row in comm_counts.iterrows():
        print(f"       {int(row['commodity_id']):>4d}  {str(row['commodity_name']):<15s}: {int(row['records']):>6,}")

    print("\n  6. Districts per commodity:")
    dist_counts = (
        df.groupby(["commodity_id", "commodity_name"])["district_id"]
          .nunique().reset_index(name="districts")
          .sort_values("commodity_id")
    )
    for _, row in dist_counts.iterrows():
        print(f"       {int(row['commodity_id']):>4d}  {str(row['commodity_name']):<15s}: {int(row['districts']):>3} districts")

    print(f"\n  7. Unique markets               : {df['market_id'].nunique():,}")
    print(f"  8. Earliest date                : {df['date'].min().date()}")
    print(f"  9. Latest date                  : {df['date'].max().date()}")

    print("\n  10. Missing values (key columns):")
    for col in ["date", "commodity_id", "district_id", "market_id",
                "min_price", "max_price", "modal_price"]:
        n = int(df[col].isna().sum())
        print(f"        {col:<20s}: {n}")

    zero_count = int(
        ((df["min_price"] == 0) | (df["max_price"] == 0) | (df["modal_price"] == 0)).sum()
    )
    print(f"\n  11. Zero/negative price rows    : {zero_count} zero  /  "
          f"{quality.get('removed_negative_price_rows', 0)} negative (removed before this step)")

    invalid_price_rel = int(
        ((df["min_price"] > df["max_price"]) |
         (df["modal_price"] < df["min_price"]) |
         (df["modal_price"] > df["max_price"])).sum()
    )
    print(f"  12. Invalid price relationships : {invalid_price_rel} (retained with quality_flag)")

    csv_kb = OUT_CSV.stat().st_size / 1024
    print(f"\n  13. Output CSV                  : {OUT_CSV}")
    print(f"      Size                        : {csv_kb:.1f} KB")

    print()
    print(sep)
    print("  INVARIANTS CONFIRMED")
    print(sep)
    print("   [OK] Raw CEDA JSON files:   READ-ONLY (never written/deleted)")
    print("   [OK] Checkpoint DB:         NOT TOUCHED")
    print("   [OK] API calls:             NONE")
    print("   [OK] Synthetic data:        NONE")
    print("   [OK] ML model training:     NONE")
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print()
    print("=" * 60)
    print("  CEDA HISTORICAL DATA PREPROCESSING")
    print("=" * 60)
    print(f"  Source : {RAW_DIR}")
    print(f"  Output : {PROCESSED_DIR}")
    print()

    df, raw_count = load_raw_files(RAW_DIR)
    df = normalize(df)
    df, quality = clean(df)
    df = validate_commodities(df)
    df = add_features(df)

    banana_count = int((df["commodity_id"] == 19).sum())
    print(f"BANANA: {banana_count:,} Banana records preserved intact (imbalance handled at training time)")

    save_output(df, quality)
    verify(df, raw_count, quality)


if __name__ == "__main__":
    main()
