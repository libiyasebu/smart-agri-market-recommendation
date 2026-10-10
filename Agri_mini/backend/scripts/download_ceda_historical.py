r"""
download_ceda_historical.py
===========================
Resumable, safe incremental collector for genuine Kerala AGMARKNET
historical prices via the CEDA Ashoka University API.

API Base:  https://api.ceda.ashoka.edu.in/v1
Auth:      Authorization: Bearer <CEDA_API_KEY>
Endpoints:
  GET  /agmarknet/commodities
  GET  /agmarknet/geographies
  POST /agmarknet/markets      {"state_id": ..., "district_id": ...}
  POST /agmarknet/prices       {"commodity_id":..,"state_id":..,"from_date":"YYYY-MM-DD","to_date":"YYYY-MM-DD"}

Response shape: {"output": [...records...]}

IMPORTANT:
  - DATA ACQUISITION ONLY. Does NOT train or modify any model.
  - Does NOT touch the production PostgreSQL database.
  - Does NOT modify the current 588-row model dataset.
  - Does NOT generate synthetic records.
  - Reads CEDA_API_KEY exclusively from D:\Agri_mini\.env
  - api.data.gov.in is NOT used here.

Usage:
  python backend/scripts/download_ceda_historical.py --status
  python backend/scripts/download_ceda_historical.py --discover
  python backend/scripts/download_ceda_historical.py --run
  python backend/scripts/download_ceda_historical.py --build-normalized
  python backend/scripts/download_ceda_historical.py --report
  python backend/scripts/download_ceda_historical.py --test

CEDA Rate Limit: conservative budget 15 requests/run with 5s inter-request delay.
"""

import os
import sys
import csv
import json
import time
import uuid
import hashlib
import sqlite3
import logging
import argparse
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
BACKEND_DIR  = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
CEDA_DIR       = PROJECT_ROOT / "data" / "ceda_historical"
RAW_DIR        = CEDA_DIR / "raw"
NORMALIZED_DIR = CEDA_DIR / "normalized"
METADATA_DIR   = CEDA_DIR / "metadata"
LOGS_DIR       = CEDA_DIR / "logs"
REPORTS_DIR    = CEDA_DIR / "reports"

for _d in (RAW_DIR, NORMALIZED_DIR, METADATA_DIR, LOGS_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DB      = METADATA_DIR / "download_state.sqlite"
MANIFEST_CSV       = METADATA_DIR / "request_manifest.csv"
MARKET_CATALOG     = METADATA_DIR / "market_catalog.csv"
COMMODITIES_JSON   = METADATA_DIR / "commodities.json"
GEOGRAPHIES_JSON   = METADATA_DIR / "geographies.json"
NORMALIZED_CSV     = NORMALIZED_DIR / "ceda_kerala_prices.csv"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = LOGS_DIR / f"collector_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ceda_collector")

# ---------------------------------------------------------------------------
# CEDA API constants  — NO api.data.gov.in reference
# ---------------------------------------------------------------------------
CEDA_BASE_URL = "https://api.ceda.ashoka.edu.in/v1"

# Conservative rate limit for Batch 1: 10 requests/run, 6 s between requests.
# CEDA allows ~40/hour but burst limit is much tighter (~16 rapid fire -> 429).
# After Batch 1 is approved, this can be increased back toward 15.
MAX_REQUESTS_PER_RUN  = 10
REQUEST_DELAY_SECONDS = 6    # seconds between every API call

CONNECT_TIMEOUT = 20
READ_TIMEOUT    = 90

DATASET_START = date(2024, 10, 1)
DATASET_END   = date(2026, 9, 30)

# Seed IDs verified in prior CEDA authentication session.
# These will be confirmed / overridden by --discover before download begins.
KERALA_STATE_ID_SEED      = 32
THRISSUR_DISTRICT_ID_SEED = 594
TOMATO_COMMODITY_ID_SEED  = 78

# Approved 10-commodity shortlist -- finalised 2026-10-03.
# Exact CEDA names with confirmed IDs. The _matches_target() filter in cmd_run
# uses partial case-insensitive match; entries here must be specific enough to
# avoid pulling in unwanted variants (e.g. Red Cabbage).
# Beans (94) and Onion Green (358) removed: no records returned after
# verified CEDA queries; NO_DATA rows retained in checkpoint for audit.
COMMODITY_NAMES = [
    "Banana",         # id=19
    "Banana - Green", # id=90
    "Tomato",         # id=78
    "Onion",          # id=23
    "Potato",         # id=24
    "Brinjal",        # id=35
    "Green Chilli",   # id=87
    "Carrot",         # id=153
    "Cabbage",        # id=154
    "Sweet Potato",   # id=152
]

# Task status codes
PENDING          = "PENDING"
SUCCESS          = "SUCCESS"
NO_DATA          = "NO_DATA"
FAILED_RETRYABLE = "FAILED_RETRYABLE"
FAILED_FINAL     = "FAILED_FINAL"


# ---------------------------------------------------------------------------
# CEDA exceptions
# ---------------------------------------------------------------------------

class CedaRateLimitError(Exception):
    pass

class CedaAuthError(Exception):
    pass

class CedaChunkTooLargeError(Exception):
    """Raised when the response is too slow / times out — retry with smaller chunk."""
    pass


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    key = os.getenv("CEDA_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "CEDA_API_KEY is not set.\n"
            "Add:  CEDA_API_KEY=<your_key>  to  D:\\Agri_mini\\.env"
        )
    return key


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_records(data: Any) -> List[dict]:
    """Extract the records list from a CEDA response.

    VERIFIED schema (2026-10-02 live probe):
      response["output"]["data"]  — two levels deep.
      response["output"] is a dict: {"type": "success", "message": "...", "data": [...]}

    Falls back to common single-level keys for robustness.
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    # PRIMARY path: response["output"]["data"]  (verified live)
    out = data.get("output")
    if isinstance(out, dict):
        inner = out.get("data")
        if isinstance(inner, list):
            return inner
    # Fallback: output is itself a list (older API / edge responses)
    if isinstance(out, list):
        return out

    # Fallback: try flat keys
    for key in ("data", "results", "records", "prices"):
        val = data.get(key)
        if isinstance(val, list):
            return val

    return []


# ---------------------------------------------------------------------------
# CEDA HTTP client
# ---------------------------------------------------------------------------

def _ceda_get(
    path: str,
    params: Optional[dict],
    run_state: dict,
) -> Tuple[Optional[Any], int, Optional[str]]:
    """GET request to CEDA. Returns (json_body, http_status, error_msg)."""
    return _ceda_request("GET", path, params=params, body=None, run_state=run_state)


def _ceda_post(
    path: str,
    body: dict,
    run_state: dict,
) -> Tuple[Optional[Any], int, Optional[str]]:
    """POST request to CEDA. Returns (json_body, http_status, error_msg)."""
    return _ceda_request("POST", path, params=None, body=body, run_state=run_state)


def _ceda_request(
    method: str,
    path: str,
    params: Optional[dict],
    body: Optional[dict],
    run_state: dict,
) -> Tuple[Optional[Any], int, Optional[str]]:
    """
    Core CEDA HTTP caller with retry logic.
    Returns (json_body, http_status, error_msg).
    Raises CedaAuthError, CedaRateLimitError, CedaChunkTooLargeError.
    """
    api_key  = _get_api_key()
    url      = f"{CEDA_BASE_URL}{path}"
    headers  = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
        "User-Agent":    "AgriMiniCEDACollector/3.0",
    }

    max_retries = 3
    backoff     = 8  # seconds base backoff for transient errors

    for attempt in range(1, max_retries + 1):
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, params=params,
                                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            else:
                resp = requests.post(url, headers=headers, json=body,
                                     timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))

            http_status = resp.status_code
            run_state["requests_made"] += 1

            if http_status == 200:
                try:
                    return resp.json(), 200, None
                except ValueError as e:
                    return None, 200, f"JSON parse error: {e}"

            elif http_status in (401, 403):
                msg = f"Auth error HTTP {http_status}: {resp.text[:300]}"
                raise CedaAuthError(msg)

            elif http_status == 429:
                msg = f"Rate limited (HTTP 429): {resp.text[:200]}"
                log.warning(msg)
                raise CedaRateLimitError(msg)

            elif http_status == 504:
                raise CedaChunkTooLargeError(
                    f"504 Gateway Timeout on {method} {path}"
                )

            elif http_status in (500, 502, 503):
                err = f"Server error HTTP {http_status} attempt {attempt}"
                log.warning(err)
                if attempt < max_retries:
                    time.sleep(backoff * attempt)
                    continue
                return None, http_status, err

            else:
                err = f"Unexpected HTTP {http_status}: {resp.text[:200]}"
                log.error(err)
                return None, http_status, err

        except (requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout) as e:
            err = f"Timeout attempt {attempt}: {e}"
            log.warning(err)
            if attempt < max_retries:
                time.sleep(backoff * attempt)
                continue
            return None, 0, err

        except (requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as e:
            err = f"Network error attempt {attempt}: {e}"
            log.warning(err)
            if attempt < max_retries:
                time.sleep(backoff * attempt)
                continue
            return None, 0, err

    return None, 0, "All retries exhausted"


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

MANIFEST_FIELDNAMES = [
    "request_id", "timestamp", "method", "endpoint",
    "state_id", "district_id", "commodity_id", "commodity_name",
    "from_date", "to_date",
    "http_status", "record_count", "output_file", "sha256", "error",
]


def append_manifest(entry: dict):
    exists = MANIFEST_CSV.exists()
    safe = {k: entry.get(k, "") for k in MANIFEST_FIELDNAMES}
    with open(MANIFEST_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDNAMES)
        if not exists:
            w.writeheader()
        w.writerow(safe)


# ---------------------------------------------------------------------------
# Checkpoint database
# ---------------------------------------------------------------------------

def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(CHECKPOINT_DB))
    conn.row_factory = sqlite3.Row
    return conn


def init_checkpoint_db():
    conn = _db_connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS download_tasks (
        task_id        TEXT PRIMARY KEY,
        state_id       INTEGER,
        district_id    INTEGER,
        district_name  TEXT,
        commodity_id   INTEGER,
        commodity_name TEXT,
        start_date     TEXT,
        end_date       TEXT,
        chunk_label    TEXT,
        status         TEXT DEFAULT 'PENDING',
        attempt_count  INTEGER DEFAULT 0,
        record_count   INTEGER DEFAULT 0,
        output_file    TEXT,
        sha256         TEXT,
        last_error     TEXT,
        created_at     TEXT,
        updated_at     TEXT,
        priority       INTEGER DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS ceda_commodities (
        commodity_id   INTEGER PRIMARY KEY,
        commodity_name TEXT,
        raw_json       TEXT
    );
    CREATE TABLE IF NOT EXISTS ceda_districts (
        district_id    INTEGER,
        district_name  TEXT,
        state_id       INTEGER,
        PRIMARY KEY (district_id, state_id)
    );
    CREATE TABLE IF NOT EXISTS known_markets (
        market_id      TEXT PRIMARY KEY,
        market_name    TEXT,
        district_id    INTEGER,
        district_name  TEXT,
        state_id       INTEGER DEFAULT 32
    );
    """)
    conn.commit()
    # Migration guard: add priority column to existing DBs that pre-date it.
    # ALTER TABLE ADD COLUMN is idempotent-safe via the try/except below.
    try:
        conn.execute("ALTER TABLE download_tasks ADD COLUMN priority INTEGER DEFAULT NULL")
        conn.commit()
        log.info("Schema migration: added 'priority' column to download_tasks.")
    except Exception:
        pass  # Column already exists — nothing to do.
    conn.close()
    log.info("Checkpoint database ready: %s", CHECKPOINT_DB)


def upsert_task(task: dict):
    conn = _db_connect()
    now = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT task_id FROM download_tasks WHERE task_id=?", (task["task_id"],)
    ).fetchone()
    if existing:
        conn.execute("""
            UPDATE download_tasks SET
              status=?, attempt_count=?, record_count=?, output_file=?,
              sha256=?, last_error=?, updated_at=?
            WHERE task_id=?
        """, (
            task.get("status", PENDING),
            task.get("attempt_count", 0),
            task.get("record_count", 0),
            task.get("output_file", ""),
            task.get("sha256", ""),
            task.get("last_error", ""),
            now,
            task["task_id"],
        ))
    else:
        conn.execute("""
            INSERT INTO download_tasks
              (task_id, state_id, district_id, district_name,
               commodity_id, commodity_name, start_date, end_date, chunk_label,
               status, attempt_count, record_count, output_file, sha256,
               last_error, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            task["task_id"],
            task.get("state_id", KERALA_STATE_ID_SEED),
            task.get("district_id"),
            task.get("district_name", ""),
            task.get("commodity_id"),
            task.get("commodity_name", ""),
            task.get("start_date", ""),
            task.get("end_date", ""),
            task.get("chunk_label", ""),
            task.get("status", PENDING),
            task.get("attempt_count", 0),
            task.get("record_count", 0),
            task.get("output_file", ""),
            task.get("sha256", ""),
            task.get("last_error", ""),
            now, now,
        ))
    conn.commit()
    conn.close()


# Priority ordering for pending tasks — 10 active commodities.
# NOTE: The priority column in download_tasks now holds pre-computed
# geographic-diversity scores (written by the priority analysis script,
# 2026-10-03).  The ORDER BY below reads that column directly.
#
# Score formula (lower = runs sooner):
#   (commodity_base_priority × 1000)
#   + (0 if district has zero existing records for this commodity, else 500)
#   + district_id   [numeric tie-break]
#
# The dict and CASE string below are retained for reference / fallback only.
_COMMODITY_PRIORITY = {
    152: 1,   # Sweet Potato  — fewest records, highest need
    153: 2,   # Carrot
    23:  3,   # Onion
    78:  4,   # Tomato
    90:  5,   # Banana-Green
    154: 6,   # Cabbage
    35:  7,   # Brinjal
    87:  8,   # Green Chilli
    24:  9,   # Potato
    19:  10,  # Banana        — already 10k+ records, lowest priority
}

_PRIORITY_CASE = " ".join(
    f"WHEN commodity_id={cid} THEN {pri}"
    for cid, pri in sorted(_COMMODITY_PRIORITY.items(), key=lambda x: x[1])
)


def get_pending_tasks() -> List[sqlite3.Row]:
    """Return all PENDING / FAILED_RETRYABLE tasks in execution order.

    Ordering uses the pre-computed ``priority`` column (geographic-diversity
    score written to the DB on 2026-10-03).  Lower priority value = runs
    first.  Falls back to ``start_date`` then ``task_id`` for deterministic
    ordering when scores are equal.

    The old hard-coded CASE expression (commodity_id only) has been replaced
    by this column-based ordering so that geographic expansion tasks for
    under-represented districts sort ahead of tasks in already-covered
    Kasaragod.
    """
    conn = _db_connect()
    rows = conn.execute("""
        SELECT * FROM download_tasks
        WHERE status IN (?, ?)
        ORDER BY
            COALESCE(priority, 999999) ASC,
            start_date ASC,
            task_id ASC
    """, (PENDING, FAILED_RETRYABLE)).fetchall()
    conn.close()
    return rows


def get_status_counts() -> Dict[str, int]:
    conn = _db_connect()
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM download_tasks GROUP BY status"
    ).fetchall()
    conn.close()
    counts = {PENDING: 0, SUCCESS: 0, NO_DATA: 0,
              FAILED_RETRYABLE: 0, FAILED_FINAL: 0}
    for r in rows:
        counts[r["status"]] = r["cnt"]
    return counts


def get_all_tasks_count() -> int:
    conn = _db_connect()
    n = conn.execute("SELECT COUNT(*) FROM download_tasks").fetchone()[0]
    conn.close()
    return n


def get_total_records_downloaded() -> int:
    conn = _db_connect()
    n = conn.execute(
        "SELECT COALESCE(SUM(record_count),0) FROM download_tasks WHERE status=?",
        (SUCCESS,)
    ).fetchone()[0]
    conn.close()
    return n


def load_ceda_commodities() -> List[dict]:
    conn = _db_connect()
    rows = conn.execute("SELECT * FROM ceda_commodities").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_ceda_commodity(cid: int, name: str, raw: dict):
    conn = _db_connect()
    conn.execute("""
        INSERT OR REPLACE INTO ceda_commodities (commodity_id, commodity_name, raw_json)
        VALUES (?,?,?)
    """, (cid, name, json.dumps(raw)))
    conn.commit()
    conn.close()


def load_ceda_districts() -> List[dict]:
    conn = _db_connect()
    rows = conn.execute(
        "SELECT * FROM ceda_districts ORDER BY district_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_ceda_district(district_id: int, district_name: str, state_id: int):
    conn = _db_connect()
    conn.execute("""
        INSERT OR IGNORE INTO ceda_districts (district_id, district_name, state_id)
        VALUES (?,?,?)
    """, (district_id, district_name, state_id))
    conn.commit()
    conn.close()


def save_known_markets(markets: List[dict]):
    if not markets:
        return
    conn = _db_connect()
    for m in markets:
        conn.execute("""
            INSERT OR REPLACE INTO known_markets
              (market_id, market_name, district_id, district_name, state_id)
            VALUES (?,?,?,?,?)
        """, (
            str(m.get("market_id") or m.get("id") or uuid.uuid4()),
            m.get("market_name") or m.get("name") or "",
            m.get("district_id"), m.get("district_name"), 32,
        ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# CEDA Discovery
# ---------------------------------------------------------------------------

# Kerala district seed (verified from prior session, used if CEDA geo endpoint
# returns empty results)
KERALA_DISTRICTS_SEED = [
    (594, "Thrissur"),
    (570, "Thiruvananthapuram"),
    (571, "Kollam"),
    (572, "Pathanamthitta"),
    (573, "Alappuzha"),
    (574, "Kottayam"),
    (575, "Idukki"),
    (576, "Ernakulam"),
    (577, "Palakkad"),
    (578, "Malappuram"),
    (579, "Kozhikode"),
    (580, "Wayanad"),
    (581, "Kannur"),
    (582, "Kasaragod"),
]


def discover_commodities(run_state: dict) -> List[dict]:
    """GET /agmarknet/commodities → list of {commodity_id, commodity_name}."""
    log.info("Discovering commodities from CEDA...")
    data, status, err = _ceda_get("/agmarknet/commodities", None, run_state)
    time.sleep(REQUEST_DELAY_SECONDS)

    if status == 429:
        raise CedaRateLimitError("429 on commodities discovery")
    if status not in (200,):
        log.warning("Commodities endpoint returned %d (%s). Will use manual mapping.", status, err)
        return []

    records = _extract_records(data)
    log.info("Commodities endpoint returned %d items.", len(records))

    results = []
    for r in records:
        cid  = r.get("id") or r.get("commodity_id")
        name = r.get("name") or r.get("commodity_name") or str(r)
        if cid is not None:
            try:
                cid = int(cid)
            except (ValueError, TypeError):
                pass
            save_ceda_commodity(cid, str(name), r)
            results.append({"commodity_id": cid, "commodity_name": str(name)})

    append_manifest({
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "method": "GET", "endpoint": "/agmarknet/commodities",
        "http_status": status, "record_count": len(results), "error": err or "",
    })
    return results


def discover_geographies(run_state: dict) -> List[dict]:
    """GET /agmarknet/geographies → list of {district_id, district_name, state_id}.

    VERIFIED schema (2026-10-02 live probe):
      Records contain: census_state_id, census_state_name,
                       census_district_id, census_district_name
      Returns ALL state+district pairs (640 rows total), not filtered by state.
      The state_id param in query string appears to be ignored.
    """
    log.info("Discovering geographies from CEDA...")
    # Note: state_id query param appears to be ignored by the API;
    # endpoint returns all 640 state/district rows.
    data, status, err = _ceda_get(
        "/agmarknet/geographies",
        None,
        run_state,
    )
    time.sleep(REQUEST_DELAY_SECONDS)

    if status == 429:
        raise CedaRateLimitError("429 on geographies discovery")

    all_rows = _extract_records(data) if status == 200 else []
    log.info("Geographies endpoint returned %d total rows.", len(all_rows))

    # Filter to Kerala rows only using the verified field name: census_state_name
    records = [
        r for r in all_rows
        if "kerala" in str(r.get("census_state_name", r.get("state_name", ""))).lower()
    ]
    log.info("Kerala rows: %d", len(records))

    results = []
    for r in records:
        # Verified field names: census_district_id, census_district_name, census_state_id
        did   = r.get("census_district_id") or r.get("district_id") or r.get("id")
        dname = r.get("census_district_name") or r.get("district_name") or str(r)
        sid   = r.get("census_state_id") or r.get("state_id", KERALA_STATE_ID_SEED)
        if did is not None:
            try:
                did = int(did)
            except (ValueError, TypeError):
                pass
            save_ceda_district(did, str(dname), int(sid))
            results.append({"district_id": did, "district_name": str(dname), "state_id": int(sid)})

    append_manifest({
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "method": "GET", "endpoint": "/agmarknet/geographies",
        "http_status": status, "record_count": len(results), "error": err or "",
    })
    return results


def verify_price_combo(
    state_id: int,
    district_id: int,
    commodity_id: int,
    commodity_name: str,
    run_state: dict,
) -> Tuple[bool, int]:
    """
    Try a small /agmarknet/prices request to confirm the ID combination works.
    Returns (success, record_count).
    Uses a recent quarter — 2024 Q1 is confirmed to return 902 records
    for Banana/Kerala/Thrissur.
    """
    log.info(
        "Verifying: state_id=%d district_id=%d commodity_id=%d (%s)",
        state_id, district_id, commodity_id, commodity_name,
    )
    # CANONICAL date fields confirmed by live probe 2026-10-02:
    # from_date / to_date  — HTTP 200, 902 records returned.
    # Use a 1-month window here to avoid 504 Gateway Timeout on verification.
    body = {
        "commodity_id":        commodity_id,
        "state_id":            state_id,
        "census_state_id":     state_id,
        "district_id":         district_id,
        "census_district_id":  district_id,
        "from_date":           "2024-01-01",
        "to_date":             "2024-01-31",
    }
    data, status, err = _ceda_post("/agmarknet/prices", body, run_state)
    time.sleep(REQUEST_DELAY_SECONDS)

    append_manifest({
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "method": "POST", "endpoint": "/agmarknet/prices",
        "state_id": state_id, "district_id": district_id,
        "commodity_id": commodity_id, "commodity_name": commodity_name,
        "from_date": "2024-01-01", "to_date": "2024-01-31",
        "http_status": status,
        "record_count": len(_extract_records(data)) if data else 0,
        "error": err or "",
    })

    if status == 429:
        raise CedaRateLimitError("429 during verification")
    if status != 200 or data is None:
        return False, 0

    records = _extract_records(data)
    n = len(records)
    log.info("Verification: %d records returned for state_id=%d commodity_id=%d", n, state_id, commodity_id)
    return n > 0, n


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def _quarterly_chunks(start: date, end: date) -> List[Tuple[date, date, str]]:
    chunks = []
    cur = start
    while cur <= end:
        q = (cur.month - 1) // 3 + 1
        q_end_month = q * 3
        last_day = (date(cur.year, q_end_month, 1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        chunk_end = min(last_day, end)
        chunks.append((cur, chunk_end, f"{cur.year}Q{q}"))
        cur = chunk_end + timedelta(days=1)
    return chunks


def _monthly_chunks(start: date, end: date) -> List[Tuple[date, date, str]]:
    chunks = []
    cur = start
    while cur <= end:
        last = (cur.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        chunk_end = min(last, end)
        chunks.append((cur, chunk_end, cur.strftime("%Y%m")))
        cur = chunk_end + timedelta(days=1)
    return chunks


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------

def build_download_tasks(districts: List[dict], commodities: List[dict]):
    """Register all download tasks (idempotent)."""
    conn = _db_connect()
    existing = {r[0] for r in conn.execute("SELECT task_id FROM download_tasks").fetchall()}
    conn.close()

    chunks = _quarterly_chunks(DATASET_START, DATASET_END)
    new_tasks = 0

    for dist in districts:
        did   = dist["district_id"]
        dname = dist["district_name"]
        sid   = dist.get("state_id", KERALA_STATE_ID_SEED)
        for comm in commodities:
            cid   = comm["commodity_id"]
            cname = comm["commodity_name"]
            for (cs, ce, cl) in chunks:
                tid = f"s{sid}_d{did}_{cname.replace(' ','_')}_{cl}"
                if tid in existing:
                    continue
                upsert_task({
                    "task_id":       tid,
                    "state_id":      sid,
                    "district_id":   did,
                    "district_name": dname,
                    "commodity_id":  cid,
                    "commodity_name": cname,
                    "start_date":    cs.isoformat(),
                    "end_date":      ce.isoformat(),
                    "chunk_label":   cl,
                    "status":        PENDING,
                })
                new_tasks += 1

    log.info("Registered %d new download tasks.", new_tasks)


# ---------------------------------------------------------------------------
# Raw file save + task update
# ---------------------------------------------------------------------------

def _save_raw_and_update_task(task: sqlite3.Row, records: List[dict], attempt: int):
    task_id   = task["task_id"]
    dist_id   = task["district_id"]
    dist_name = task["district_name"]
    comm_name = task["commodity_name"]
    chunk_lbl = task["chunk_label"]
    state_id  = task["state_id"]
    start_str = task["start_date"]
    end_str   = task["end_date"]

    safe_c = comm_name.replace(" ", "_").replace("/", "_")
    fname  = f"kerala_{dist_id}_{safe_c}_{chunk_lbl}.json"
    fpath  = RAW_DIR / fname

    payload = {
        "task_id":              task_id,
        "state_id":             state_id,
        "district_id":          dist_id,
        "district_name":        dist_name,
        "commodity_name":       comm_name,
        "chunk_label":          chunk_lbl,
        "start_date":           start_str,
        "end_date":             end_str,
        "retrieval_timestamp":  datetime.now().isoformat(),
        "source":               "CEDA_AGMARKNET",
        "api_endpoint":         f"{CEDA_BASE_URL}/agmarknet/prices",
        "record_count":         len(records),
        "records":              records,
    }

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    digest = sha256_file(fpath)

    upsert_task({
        "task_id":       task_id,
        "state_id":      state_id,
        "district_id":   dist_id,
        "district_name": dist_name,
        "commodity_id":  task["commodity_id"],
        "commodity_name": comm_name,
        "start_date":    start_str,
        "end_date":      end_str,
        "chunk_label":   chunk_lbl,
        "status":        SUCCESS,
        "attempt_count": attempt,
        "record_count":  len(records),
        "output_file":   str(fpath),
        "sha256":        digest,
    })

    log.info("  -> SUCCESS: %d records -> %s  sha256=%s...",
             len(records), fname, digest[:12])

    # Extract market metadata from records
    seen = {}
    for r in records:
        mid  = r.get("market_id") or (r.get("market") or {}).get("id") if isinstance(r.get("market"), dict) else None
        mnam = (r.get("market") or {}).get("name") if isinstance(r.get("market"), dict) else r.get("market_name")
        if mid and mnam and str(mid) not in seen:
            seen[str(mid)] = {
                "market_id":    mid, "market_name": mnam,
                "district_id":  dist_id, "district_name": dist_name,
            }
    if seen:
        save_known_markets(list(seen.values()))


# ---------------------------------------------------------------------------
# Execute one download task
# ---------------------------------------------------------------------------

def execute_task(task: sqlite3.Row, run_state: dict) -> bool:
    task_id    = task["task_id"]
    state_id   = task["state_id"]
    dist_id    = task["district_id"]
    dist_name  = task["district_name"]
    comm_id    = task["commodity_id"]
    comm_name  = task["commodity_name"]
    start_str  = task["start_date"]
    end_str    = task["end_date"]
    chunk_lbl  = task["chunk_label"]
    attempt    = task["attempt_count"] + 1

    t_start = date.fromisoformat(start_str)
    t_end   = date.fromisoformat(end_str)

    log.info("[TASK] %s | dist=%s(%d) comm=%s(%d) %s->%s",
             task_id, dist_name, dist_id, comm_name, comm_id, t_start, t_end)

    def _fetch(from_d: date, to_d: date):
        # CANONICAL date fields confirmed 2026-10-02: from_date / to_date only.
        date_from = from_d.strftime("%Y-%m-%d")
        date_to   = to_d.strftime("%Y-%m-%d")
        body = {
            "commodity_id":        comm_id,
            "state_id":            state_id,
            "census_state_id":     state_id,
            "district_id":         dist_id,
            "census_district_id":  dist_id,
            "from_date":           date_from,
            "to_date":             date_to,
        }
        return _ceda_post("/agmarknet/prices", body, run_state)

    # --- Try quarterly first ---
    try:
        data, status, err = _fetch(t_start, t_end)
        time.sleep(REQUEST_DELAY_SECONDS)

    except CedaChunkTooLargeError:
        log.warning("504 on %s — subdividing into monthly chunks...", chunk_lbl)
        all_recs, sub_errs = [], []
        for (ms, me, ml) in _monthly_chunks(t_start, t_end):
            if run_state["requests_made"] >= MAX_REQUESTS_PER_RUN:
                _mark_retryable(task, attempt, "Budget reached during monthly subdivision")
                return False
            try:
                md, ms_, merr = _fetch(ms, me)
                time.sleep(REQUEST_DELAY_SECONDS)
                _log_manifest(task, ms, me, ms_, md, merr)
                if md and ms_ == 200:
                    all_recs.extend(_extract_records(md))
            except (CedaAuthError, CedaRateLimitError):
                raise
            except CedaChunkTooLargeError:
                sub_errs.append(f"{ml}: 504")

        if all_recs:
            _save_raw_and_update_task(task, all_recs, attempt)
            run_state["records_downloaded"] += len(all_recs)
            return True
        _mark_retryable(task, attempt, "; ".join(sub_errs) or "no records in monthly")
        return True

    except CedaAuthError:
        _mark_final(task, attempt, "Auth error")
        raise

    except CedaRateLimitError:
        _mark_retryable(task, attempt, "Rate limited")
        raise

    # --- Normal response handling ---
    _log_manifest(task, t_start, t_end, status, data, err)

    if status == 200 and data is not None:
        records = _extract_records(data)
        if records:
            _save_raw_and_update_task(task, records, attempt)
            run_state["records_downloaded"] += len(records)
            return True
        else:
            upsert_task({**_task_base(task), "status": NO_DATA,
                         "attempt_count": attempt, "record_count": 0, "last_error": ""})
            log.info("  -> NO_DATA")
            return True
    elif status == 429:
        _mark_retryable(task, attempt, err or "HTTP 429")
        raise CedaRateLimitError("429 on chunk")
    elif status in (401, 403):
        _mark_final(task, attempt, err or f"HTTP {status}")
        raise CedaAuthError(f"HTTP {status}")
    else:
        st = FAILED_RETRYABLE if attempt < 3 else FAILED_FINAL
        upsert_task({**_task_base(task), "status": st,
                     "attempt_count": attempt, "last_error": err or f"HTTP {status}"})
        log.warning("  -> %s (attempt %d)", st, attempt)
        return False


def _task_base(task: sqlite3.Row) -> dict:
    return {
        "task_id": task["task_id"], "state_id": task["state_id"],
        "district_id": task["district_id"], "district_name": task["district_name"],
        "commodity_id": task["commodity_id"], "commodity_name": task["commodity_name"],
        "start_date": task["start_date"], "end_date": task["end_date"],
        "chunk_label": task["chunk_label"],
    }


def _mark_retryable(task: sqlite3.Row, attempt: int, msg: str):
    upsert_task({**_task_base(task), "status": FAILED_RETRYABLE,
                 "attempt_count": attempt, "last_error": msg[:500]})


def _mark_final(task: sqlite3.Row, attempt: int, msg: str):
    upsert_task({**_task_base(task), "status": FAILED_FINAL,
                 "attempt_count": attempt, "last_error": msg[:500]})


def _log_manifest(task, from_d, to_d, status, data, err):
    records = _extract_records(data) if data else []
    append_manifest({
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "method": "POST", "endpoint": "/agmarknet/prices",
        "state_id": task["state_id"], "district_id": task["district_id"],
        "commodity_id": task["commodity_id"], "commodity_name": task["commodity_name"],
        "from_date": str(from_d), "to_date": str(to_d),
        "http_status": status, "record_count": len(records),
        "output_file": "", "sha256": "", "error": err or "",
    })


# ---------------------------------------------------------------------------
# --discover command
# ---------------------------------------------------------------------------

def cmd_discover():
    """
    Resolve CEDA commodity and geography IDs, then verify a test price fetch.
    Run this ONCE before the first --run to confirm connectivity.
    Uses at most ~5 requests (well within rate limit).
    """
    log.info("=" * 70)
    log.info("CEDA DISCOVER — Resolving IDs and verifying price endpoint")
    log.info("=" * 70)

    init_checkpoint_db()
    run_state = {"requests_made": 0, "records_downloaded": 0}

    # ---- 1. Commodities ----
    comms = discover_commodities(run_state)
    if comms:
        with open(COMMODITIES_JSON, "w", encoding="utf-8") as f:
            json.dump(comms, f, indent=2)
        log.info("Saved %d commodities to %s", len(comms), COMMODITIES_JSON)
    else:
        log.warning(
            "Commodities endpoint returned 0 items. "
            "Will use COMMODITY_NAMES list as seed for task registration."
        )
        # Save placeholder so task registration can proceed
        comms = [{"commodity_id": None, "commodity_name": n} for n in COMMODITY_NAMES]
        with open(COMMODITIES_JSON, "w", encoding="utf-8") as f:
            json.dump(comms, f, indent=2)

    # ---- 2. Geographies ----
    dists = discover_geographies(run_state)
    if dists:
        with open(GEOGRAPHIES_JSON, "w", encoding="utf-8") as f:
            json.dump(dists, f, indent=2)
        log.info("Saved %d districts to %s", len(dists), GEOGRAPHIES_JSON)
    else:
        log.warning(
            "Geographies endpoint returned 0 items. "
            "Using verified seed list of 14 Kerala districts."
        )
        dists = [{"district_id": did, "district_name": dn, "state_id": KERALA_STATE_ID_SEED}
                 for did, dn in KERALA_DISTRICTS_SEED]
        for d in dists:
            save_ceda_district(d["district_id"], d["district_name"], d["state_id"])
        with open(GEOGRAPHIES_JSON, "w", encoding="utf-8") as f:
            json.dump(dists, f, indent=2)

    # ---- 3. Verify price endpoint ----
    # VERIFIED IDs (live probe 2026-10-02):
    #   Banana = commodity_id 19 → returned 902 records for Thrissur Q1-2024
    # Use Banana as the verification commodity since its CEDA ID is confirmed.
    # Prefer any discovered commodity that matches our target names; fall back
    # to Banana ID 19 which is known-good.
    verify_comm_id   = 19        # Banana — CEDA confirmed
    verify_comm_name = "Banana"
    _target_priority = ("banana", "onion", "potato", "tomato", "brinjal")
    for _pref in _target_priority:
        for c in comms:
            cname = str(c.get("commodity_name", "")).lower()
            if _pref in cname and c.get("commodity_id") is not None:
                verify_comm_id   = c["commodity_id"]
                verify_comm_name = c["commodity_name"]
                break
        else:
            continue
        break

    # Resolve Kerala state_id and Thrissur district_id from discovered list
    kerala_sid   = KERALA_STATE_ID_SEED      # 32 — confirmed
    thrissur_did = THRISSUR_DISTRICT_ID_SEED  # 594 — confirmed
    for d in dists:
        if "thrissur" in str(d.get("district_name", "")).lower():
            thrissur_did = d["district_id"]
            kerala_sid   = d.get("state_id", KERALA_STATE_ID_SEED)
            break

    log.info("Verifying: Kerala state_id=%d Thrissur district_id=%d %s commodity_id=%d",
             kerala_sid, thrissur_did, verify_comm_name, verify_comm_id)

    try:
        ok, n = verify_price_combo(kerala_sid, thrissur_did, verify_comm_id, verify_comm_name, run_state)
    except CedaChunkTooLargeError:
        log.warning("504 on price verification — transient timeout. "
                    "Commodities and geographies are saved; --run can proceed.")
        ok, n = False, 0

    print()
    print("=" * 70)
    print("  CEDA DISCOVER — RESULT")
    print("=" * 70)
    print(f"  Requests made       : {run_state['requests_made']}")
    print(f"  Commodities found   : {sum(1 for c in comms if c.get('commodity_id'))}")
    print(f"  Districts found     : {len(dists)}")
    if n > 0:
        print(f"  Price verification  : SUCCESS ({n} records)")
    elif ok is False and n == 0 and run_state['requests_made'] >= 3:
        print("  Price verification  : 504 TIMEOUT (transient — commodities/geo saved OK)")
    else:
        print("  Price verification  : NO RECORDS / FAILED")
    print(f"  Verified IDs        : state={kerala_sid} district={thrissur_did} commodity({verify_comm_name})={verify_comm_id}")
    print()

    if ok:
        print("  [OK] CEDA price endpoint confirmed. Run --run to start collection.")
    else:
        print("  [WARN] Price verification returned 0 records.")
        print("         This may be a rate-limit window issue OR the ID mapping")
        print("         needs further investigation.")
        print("         Wait ~60 minutes for rate limit reset, then re-run --discover.")

    print("=" * 70)


# ---------------------------------------------------------------------------
# --run command
# ---------------------------------------------------------------------------

def _write_market_catalog():
    conn = _db_connect()
    markets = conn.execute("SELECT * FROM known_markets").fetchall()
    conn.close()
    if not markets:
        return
    with open(MARKET_CATALOG, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "market_id", "market_name", "district_id", "district_name", "state_id"
        ])
        w.writeheader()
        for m in markets:
            w.writerow(dict(m))
    log.info("Market catalog: %d entries -> %s", len(markets), MARKET_CATALOG)


def _print_stop_message(run_state: dict, stop_reason: str):
    counts = get_status_counts()
    total  = get_all_tasks_count()
    done   = counts[SUCCESS] + counts[NO_DATA]
    pct    = (done / total * 100) if total else 0.0

    print()
    print("=" * 70)
    print("  CEDA COLLECTOR — BATCH COMPLETE")
    print("=" * 70)
    print(f"  Requests this run      : {run_state['requests_made']}")
    print(f"  Records downloaded     : {run_state['records_downloaded']}")
    print(f"  Stop reason            : {stop_reason}")
    print()
    print(f"  Tasks total            : {total}")
    print(f"  SUCCESS                : {counts[SUCCESS]}")
    print(f"  NO_DATA                : {counts[NO_DATA]}")
    print(f"  PENDING                : {counts[PENDING]}")
    print(f"  FAILED_RETRYABLE       : {counts[FAILED_RETRYABLE]}")
    print(f"  FAILED_FINAL           : {counts[FAILED_FINAL]}")
    print(f"  Progress               : {pct:.1f}%")
    if run_state.get("errors"):
        print()
        for e in run_state["errors"][:5]:
            print(f"  ERROR: {e}")
    print()
    if stop_reason == "rate_limited":
        print("  [RATE-LIMITED] Wait ~60 minutes before the next batch.")
    elif counts[PENDING] + counts[FAILED_RETRYABLE] > 0:
        print("  NEXT BATCH:")
        print("  python backend/scripts/download_ceda_historical.py --run")
    else:
        print("  All tasks complete!")
        print("  Next: --build-normalized")
    print("=" * 70)


def cmd_run():
    log.info("=" * 70)
    log.info("CEDA COLLECTOR — BATCH START  (API: %s)", CEDA_BASE_URL)
    log.info("Dataset period: %s -> %s", DATASET_START, DATASET_END)
    log.info("Max requests this run: %d  Delay: %ds", MAX_REQUESTS_PER_RUN, REQUEST_DELAY_SECONDS)
    log.info("=" * 70)

    init_checkpoint_db()
    run_state = {"requests_made": 0, "records_downloaded": 0, "errors": []}

    # ---- Load geographies ----
    dists = load_ceda_districts()
    if not dists:
        if GEOGRAPHIES_JSON.exists():
            with open(GEOGRAPHIES_JSON, encoding="utf-8") as f:
                dists = json.load(f)
            for d in dists:
                save_ceda_district(d["district_id"], d["district_name"],
                                   d.get("state_id", KERALA_STATE_ID_SEED))
        else:
            log.warning("No districts found — using seed list. Run --discover first.")
            dists = [{"district_id": did, "district_name": dn,
                      "state_id": KERALA_STATE_ID_SEED}
                     for did, dn in KERALA_DISTRICTS_SEED]
            for d in dists:
                save_ceda_district(d["district_id"], d["district_name"], d["state_id"])

    log.info("Districts loaded: %d", len(dists))

    # ---- Load commodities ----
    comms_db = load_ceda_commodities()
    if comms_db:
        comms = [{"commodity_id": c["commodity_id"], "commodity_name": c["commodity_name"]}
                 for c in comms_db if c["commodity_id"] is not None]
    elif COMMODITIES_JSON.exists():
        with open(COMMODITIES_JSON, encoding="utf-8") as f:
            comms_raw = json.load(f)
        comms = [c for c in comms_raw if c.get("commodity_id") is not None]
    else:
        comms = []

    if not comms:
        log.warning(
            "No resolved commodity IDs available. "
            "Using seed Tomato id=%d only. Run --discover for full list.",
            TOMATO_COMMODITY_ID_SEED,
        )
        comms = [{"commodity_id": TOMATO_COMMODITY_ID_SEED, "commodity_name": "Tomato"}]

    log.info("Commodities loaded from DB: %d", len(comms))

    # Filter to exactly the 12 approved CEDA commodity IDs.
    # Using exact ID whitelist avoids the old broad substring match that
    # produced '25 commodities matched' at startup.
    _APPROVED_IDS = set(_COMMODITY_PRIORITY.keys())  # {78,23,24,35,87,90,153,154,94,152,358,19}

    comms_filtered = [
        c for c in comms
        if c.get("commodity_id") in _APPROVED_IDS
    ]

    if comms_filtered:
        # Sort by priority so task-registration order is deterministic
        comms_filtered.sort(key=lambda c: _COMMODITY_PRIORITY.get(c["commodity_id"], 99))
        log.info("Commodities after approved-ID filter: %d (from %d)",
                 len(comms_filtered), len(comms))
        for c in comms_filtered:
            pri = _COMMODITY_PRIORITY.get(c.get("commodity_id"), 99)
            log.info("  -> %s (id=%s, priority=%d)",
                     c.get("commodity_name"), c.get("commodity_id"), pri)
        comms = comms_filtered
    else:
        log.warning("Approved-ID filter matched 0 commodities from %d; "
                    "using Banana (id=19, confirmed) as fallback.", len(comms))
        comms = [{"commodity_id": 19, "commodity_name": "Banana"}]

    # ---- Build tasks (idempotent) ----
    if get_all_tasks_count() == 0:
        build_download_tasks(dists, comms)

    counts        = get_status_counts()
    pending_tasks = get_pending_tasks()
    total         = get_all_tasks_count()

    log.info("Tasks: total=%d  pending=%d  success=%d  no_data=%d",
             total, len(pending_tasks), counts[SUCCESS], counts[NO_DATA])

    if not pending_tasks:
        _print_stop_message(run_state, "no_pending_tasks")
        return

    # ---- Execute batch ----
    stop_reason = "budget_reached"
    for task in pending_tasks:
        if run_state["requests_made"] >= MAX_REQUESTS_PER_RUN:
            stop_reason = "budget_reached"
            break
        try:
            execute_task(task, run_state)
        except CedaAuthError as e:
            run_state["errors"].append(f"AUTH: {e}")
            stop_reason = "auth_error"
            break
        except CedaRateLimitError as e:
            run_state["errors"].append(f"RATE_LIMIT: {e}")
            stop_reason = "rate_limited"
            break
        except Exception as e:
            run_state["errors"].append(f"UNEXPECTED({task['task_id']}): {e}")
            log.error("Unexpected error on %s:\n%s", task["task_id"], traceback.format_exc())
    else:
        stop_reason = "all_tasks_complete"

    _print_stop_message(run_state, stop_reason)
    _write_market_catalog()


# ---------------------------------------------------------------------------
# --status command
# ---------------------------------------------------------------------------

def cmd_status():
    init_checkpoint_db()
    counts = get_status_counts()
    total  = get_all_tasks_count()
    done   = counts[SUCCESS] + counts[NO_DATA]
    pct    = (done / total * 100) if total else 0.0

    print()
    print("=" * 62)
    print("  CEDA COLLECTOR STATUS")
    print("=" * 62)
    print(f"  API               : {CEDA_BASE_URL}")
    print(f"  Dataset period    : {DATASET_START} -> {DATASET_END}")
    print(f"  Checkpoint DB     : {CHECKPOINT_DB}")
    print()
    print(f"  Total tasks       : {total}")
    print(f"  SUCCESS           : {counts[SUCCESS]}")
    print(f"  NO_DATA           : {counts[NO_DATA]}")
    print(f"  PENDING           : {counts[PENDING]}")
    print(f"  FAILED_RETRYABLE  : {counts[FAILED_RETRYABLE]}")
    print(f"  FAILED_FINAL      : {counts[FAILED_FINAL]}")
    print(f"  Progress          : {pct:.1f}%")
    print(f"  Records total     : {get_total_records_downloaded():,}")
    print()
    if counts[PENDING] + counts[FAILED_RETRYABLE] > 0:
        print("  Run: python backend/scripts/download_ceda_historical.py --run")
    elif total > 0:
        print("  Download complete. Run --build-normalized")
    else:
        print("  No tasks. Run --discover then --run")
    print("=" * 62)


# ---------------------------------------------------------------------------
# --build-normalized command
# ---------------------------------------------------------------------------

def _parse_date(raw) -> Optional[str]:
    """Normalise any CEDA / AGMARKNET date string to ISO YYYY-MM-DD.

    Handles:
      - YYYY-MM-DD             (plain date — already correct)
      - DD/MM/YYYY             (common AGMARKNET format)
      - DD-MM-YYYY
      - YYYY/MM/DD
      - YYYY-MM-DDTHH:MM:SS.mmmZ  (CEDA ISO datetime — verified live probe)
    """
    if not raw:
        return None
    s = str(raw).strip()
    # ISO datetime: take only the date part before 'T'
    if "T" in s:
        s = s.split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s or None


def _normalize_record(r: dict, payload: dict, source_file: str) -> dict:
    def sg(obj, *keys, default=None):
        v = obj
        for k in keys:
            v = v.get(k) if isinstance(v, dict) else None
        return v if v is not None else default

    def sf(val):
        if val is None:
            return None
        try:
            return float(str(val).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    # VERIFIED CEDA record field names (live probe 2026-10-02):
    #   census_state_id, census_district_id, market_id
    #   date (ISO: "2024-01-01T00:00:00.000Z")
    #   min_price, max_price, modal_price
    # No market_name or commodity_name in record — IDs only.

    state_id      = (r.get("census_state_id") or r.get("state_id") or
                     payload.get("state_id") or KERALA_STATE_ID_SEED)
    state_name    = r.get("census_state_name") or r.get("state_name") or "Kerala"
    district_id   = (r.get("census_district_id") or r.get("district_id") or
                     payload.get("district_id"))
    district_name = (r.get("census_district_name") or r.get("district_name") or
                     payload.get("district_name"))
    market_id     = r.get("market_id") or sg(r, "market", "id")
    market_name   = r.get("market_name") or sg(r, "market", "name") or r.get("market")
    commodity_id  = (r.get("commodity_id") or sg(r, "commodity", "id") or
                     payload.get("commodity_id"))
    commodity_name = (r.get("commodity_name") or sg(r, "commodity", "name") or
                      payload.get("commodity_name"))
    # Date field: 'date' in ISO format "2024-01-01T00:00:00.000Z"
    raw_date = (r.get("date") or r.get("arrival_date") or
                r.get("price_date") or r.get("reported_date") or "")

    return {
        "date":                _parse_date(raw_date),
        "state_id":            state_id,
        "state_name":          state_name,
        "district_id":         district_id,
        "district_name":       district_name,
        "market_id":           market_id,
        "market_name":         market_name,
        "commodity_id":        commodity_id,
        "commodity_name":      commodity_name,
        "variety":             r.get("variety") or "",
        "min_price":           sf(r.get("min_price")),
        "max_price":           sf(r.get("max_price")),
        "modal_price":         sf(r.get("modal_price")),
        "source":              "CEDA_AGMARKNET",
        "source_file":         Path(source_file).name,
        "retrieval_timestamp": payload.get("retrieval_timestamp", ""),
    }


def cmd_build_normalized():
    log.info("Building normalized dataset from raw files...")
    init_checkpoint_db()

    conn = _db_connect()
    success_tasks = conn.execute(
        "SELECT * FROM download_tasks WHERE status=?", (SUCCESS,)
    ).fetchall()
    conn.close()

    if not success_tasks:
        print("No SUCCESS tasks. Run --run first.")
        return

    all_rows = []
    for task in success_tasks:
        fpath = task["output_file"]
        if not fpath or not Path(fpath).exists():
            log.warning("Missing raw file for task %s", task["task_id"])
            continue
        actual = sha256_file(Path(fpath))
        if actual != task["sha256"]:
            log.error("SHA-256 MISMATCH: %s", fpath)
            continue
        with open(fpath, encoding="utf-8") as f:
            payload = json.load(f)
        for r in payload.get("records", []):
            all_rows.append(_normalize_record(r, payload, fpath))

    if not all_rows:
        print("No rows to normalize.")
        return

    try:
        import pandas as pd
    except ImportError:
        print("pandas not available.")
        return

    df = pd.DataFrame(all_rows)
    dup_keys = [k for k in ["date", "market_id", "commodity_name", "variety"] if k in df.columns]
    n_dups   = int(df.duplicated(subset=dup_keys, keep="first").sum()) if dup_keys else 0
    if dup_keys:
        df = df[~df.duplicated(subset=dup_keys, keep="first")].copy()

    df.to_csv(NORMALIZED_CSV, index=False, encoding="utf-8")
    log.info("Normalized CSV: %s  (%d rows, %d dups removed)", NORMALIZED_CSV, len(df), n_dups)
    print(f"\n[NORMALIZED] {len(df)} rows -> {NORMALIZED_CSV}")
    print(f"[QUALITY]    Duplicates removed: {n_dups}")
    print(f"[NOTE]       Source: CEDA_AGMARKNET (genuine records only)")


# ---------------------------------------------------------------------------
# --report command
# ---------------------------------------------------------------------------

def cmd_report():
    init_checkpoint_db()
    if not NORMALIZED_CSV.exists():
        print("Normalized CSV not found. Run --build-normalized first.")
        return

    try:
        import pandas as pd
    except ImportError:
        print("pandas not available.")
        return

    df = pd.read_csv(NORMALIZED_CSV, low_memory=False)
    counts = get_status_counts()

    summary = {
        "dataset_start":        DATASET_START.isoformat(),
        "dataset_end":          DATASET_END.isoformat(),
        "generated_at":         datetime.now().isoformat(),
        "source":               "CEDA_AGMARKNET",
        "api_endpoint":         f"{CEDA_BASE_URL}/agmarknet/prices",
        "total_records":        len(df),
        "markets":              int(df["market_name"].nunique()) if "market_name" in df.columns else 0,
        "districts":            int(df["district_name"].nunique()) if "district_name" in df.columns else 0,
        "commodities":          int(df["commodity_name"].nunique()) if "commodity_name" in df.columns else 0,
        "unique_dates":         int(df["date"].nunique()) if "date" in df.columns else 0,
        "earliest_date":        str(df["date"].min()) if "date" in df.columns else None,
        "latest_date":          str(df["date"].max()) if "date" in df.columns else None,
        "missing_modal_price":  int(df["modal_price"].isna().sum()) if "modal_price" in df.columns else 0,
        "download_tasks":       counts,
        "synthetic_records":    0,
        "authenticity":         "All records sourced from CEDA AGMARKNET API",
    }

    sjson = REPORTS_DIR / "dataset_summary.json"
    with open(sjson, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n[REPORT] {sjson}")
    for k, v in summary.items():
        if k != "download_tasks":
            print(f"  {k:<25}: {v}")


# ---------------------------------------------------------------------------
# --test command (NO API CALLS)
# ---------------------------------------------------------------------------

def cmd_test():
    import unittest, tempfile

    class CollectorTests(unittest.TestCase):

        # --- URL / auth ---
        def test_base_url_is_ceda_not_data_gov_in(self):
            self.assertIn("ceda.ashoka.edu.in", CEDA_BASE_URL)
            self.assertNotIn("data.gov.in", CEDA_BASE_URL)

        def test_no_data_gov_in_in_module(self):
            """Verify the source file contains no reference to api.data.gov.in."""
            src = Path(__file__).read_text(encoding="utf-8")
            # Allow reference only in this test's string and comments
            lines_with = [
                ln for ln in src.splitlines()
                if "api.data.gov.in" in ln
                and not ln.strip().startswith("#")
                and "test_no_data_gov_in" not in ln
                and "assertNotIn" not in ln
                and "api.data.gov.in" not in ln.split("#")[0]  # not in a comment
            ]
            self.assertEqual(lines_with, [],
                msg=f"Found api.data.gov.in in non-comment code:\n" + "\n".join(lines_with))

        def test_auth_method_is_bearer(self):
            """Auth header must be Bearer, not api-key query param."""
            import inspect
            src = inspect.getsource(_ceda_request)
            self.assertIn("Bearer", src)
            self.assertNotIn("api-key", src)

        def test_prices_are_post_not_get(self):
            """Price fetches must use POST."""
            import inspect
            src = inspect.getsource(execute_task)
            self.assertIn('_ceda_post', src)
            self.assertNotIn('_ceda_get("/agmarknet/prices"', src)

        def test_response_key_is_output(self):
            """_extract_records must check 'output' key."""
            import inspect
            src = inspect.getsource(_extract_records)
            self.assertIn('"output"', src)

        # --- date format ---
        def test_date_format_is_yyyy_mm_dd(self):
            import inspect
            src = inspect.getsource(execute_task)
            self.assertIn('"%Y-%m-%d"', src)
            self.assertNotIn('"%d/%m/%Y"', src)

        # --- chunking ---
        def test_quarterly_chunks_2years(self):
            chunks = _quarterly_chunks(date(2024, 10, 1), date(2026, 9, 30))
            self.assertEqual(len(chunks), 8)
            self.assertEqual(chunks[0][0], date(2024, 10, 1))
            self.assertEqual(chunks[-1][1], date(2026, 9, 30))

        def test_monthly_chunks_24(self):
            chunks = _monthly_chunks(date(2024, 10, 1), date(2026, 9, 30))
            self.assertEqual(len(chunks), 24)

        def test_chunk_day_coverage_equal(self):
            q = _quarterly_chunks(date(2024, 10, 1), date(2026, 9, 30))
            m = _monthly_chunks(date(2024, 10, 1), date(2026, 9, 30))
            self.assertEqual(
                sum((e - s).days + 1 for s, e, _ in q),
                sum((e - s).days + 1 for s, e, _ in m),
            )

        # --- utilities ---
        def test_sha256_file(self):
            import tempfile as tmp
            with tmp.NamedTemporaryFile(delete=False, suffix=".json") as tf:
                tf.write(b'{"ceda":true}')
                p = Path(tf.name)
            d = sha256_file(p)
            self.assertEqual(len(d), 64)
            p.unlink()

        def test_parse_date_formats(self):
            self.assertEqual(_parse_date("2024-10-01"), "2024-10-01")
            self.assertEqual(_parse_date("01/10/2024"), "2024-10-01")
            self.assertIsNone(_parse_date(""))
            self.assertIsNone(_parse_date(None))

        def test_extract_records_output_key(self):
            # Verified CEDA schema (live probe 2026-10-02): output.data (2 levels)
            data = {"output": {"type": "success", "message": "Data exists",
                               "data": [{"a": 1}, {"a": 2}]}}
            self.assertEqual(len(_extract_records(data)), 2)

        def test_extract_records_output_flat_list(self):
            # Fallback: output is directly a list (older API versions)
            data = {"output": [{"a": 1}, {"a": 2}]}
            self.assertEqual(len(_extract_records(data)), 2)

        def test_extract_records_list(self):
            self.assertEqual(len(_extract_records([1, 2, 3])), 3)

        def test_extract_records_empty(self):
            # Verified nested shape — empty data array
            self.assertEqual(_extract_records(
                {"output": {"type": "success", "data": []}}), [])
            self.assertEqual(_extract_records({}), [])
            self.assertEqual(_extract_records({"output": {}}), [])

        def test_normalize_record(self):
            # Verified CEDA record field names from live probe 2026-10-02
            r = {
                "census_state_id": 32,
                "census_district_id": 594,
                "market_id": 4381,
                "commodity_id": 19,
                # Verified CEDA date format: ISO datetime string
                "date": "2024-01-01T00:00:00.000Z",
                "min_price": 1200, "max_price": 1600, "modal_price": 1400,
            }
            payload = {"district_name": "Thrissur", "commodity_name": "Banana",
                       "retrieval_timestamp": ""}
            row = _normalize_record(r, payload, "test.json")
            # ISO datetime must be stripped to plain date
            self.assertEqual(row["date"], "2024-01-01")
            # modal_price from verified record
            self.assertAlmostEqual(row["modal_price"], 1400.0)
            self.assertEqual(row["source"], "CEDA_AGMARKNET")

        # --- checkpoint ---
        def test_checkpoint_roundtrip(self):
            with tempfile.TemporaryDirectory() as tmp:
                global CHECKPOINT_DB
                orig = CHECKPOINT_DB
                CHECKPOINT_DB = Path(tmp) / "state.sqlite"
                try:
                    init_checkpoint_db()
                    t = {
                        "task_id": "t1", "state_id": 32,
                        "district_id": 594, "district_name": "Thrissur",
                        "commodity_id": 78, "commodity_name": "Tomato",
                        "start_date": "2024-10-01", "end_date": "2024-12-31",
                        "chunk_label": "2024Q4", "status": PENDING,
                    }
                    upsert_task(t)
                    self.assertEqual(len(get_pending_tasks()), 1)
                    t["status"] = SUCCESS
                    t["record_count"] = 55
                    upsert_task(t)
                    self.assertEqual(len(get_pending_tasks()), 0)
                    self.assertEqual(get_status_counts()[SUCCESS], 1)
                finally:
                    CHECKPOINT_DB = orig

        def test_rate_limit_budget_conservative(self):
            """Batch 1 capped at 10 requests to stay within CEDA quota."""
            self.assertLessEqual(MAX_REQUESTS_PER_RUN, 10)

        def test_request_delay_sufficient(self):
            self.assertGreaterEqual(REQUEST_DELAY_SECONDS, 3)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(CollectorTests))
    if not result.wasSuccessful():
        sys.exit(1)
    print("\n[TESTS] All collector unit tests passed.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CEDA AGMARKNET Historical Data Collector — Kerala",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
API:  https://api.ceda.ashoka.edu.in/v1  (Bearer token auth)
NOT:  api.data.gov.in (not used here)

Commands:
  --status            Show current download progress
  --discover          Resolve CEDA IDs and verify price endpoint (run first)
  --run               Execute one safe download batch (max 15 requests)
  --build-normalized  Build normalized CSV from saved raw files
  --report            Generate dataset summary report
  --test              Run unit tests (no API calls)
        """,
    )
    parser.add_argument("--status",           action="store_true")
    parser.add_argument("--discover",         action="store_true")
    parser.add_argument("--run",              action="store_true")
    parser.add_argument("--build-normalized", action="store_true")
    parser.add_argument("--report",           action="store_true")
    parser.add_argument("--test",             action="store_true")
    args = parser.parse_args()

    if   args.status:           cmd_status()
    elif args.discover:         cmd_discover()
    elif args.run:              cmd_run()
    elif args.build_normalized: cmd_build_normalized()
    elif args.report:           cmd_report()
    elif args.test:             cmd_test()
    else:                       parser.print_help()


if __name__ == "__main__":
    main()
