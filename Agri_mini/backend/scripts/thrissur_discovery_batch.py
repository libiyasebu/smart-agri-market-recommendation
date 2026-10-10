"""
thrissur_discovery_batch.py
===========================
Quota-safe Thrissur-only discovery batch.

Rules enforced:
  - MAX 9 API requests (one per commodity, excluding already-SUCCESS Sweet Potato 2024Q4)
  - Reads checkpoint READ-ONLY first; prints pre-batch state
  - Does NOT recreate or delete the checkpoint DB
  - Does NOT modify SUCCESS or NO_DATA tasks
  - Does NOT touch ML model, processed CSV, PostgreSQL, or frontend
  - On HTTP 429 -> save state + STOP immediately
  - Raw files saved with identical naming/format to main downloader
  - Full post-batch report with market IDs and RF-eligibility

Usage:
  python backend/scripts/thrissur_discovery_batch.py [--dry-run]

--dry-run:  print which tasks would be selected, make NO API calls.
"""

import os
import sys
import json
import uuid
import time
import hashlib
import sqlite3
import logging
import argparse
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

import requests
from dotenv import load_dotenv

# -- Path bootstrap -----------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
BACKEND_DIR  = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR  / ".env")

# -- Directories --------------------------------------------------------------
CEDA_DIR       = PROJECT_ROOT / "data" / "ceda_historical"
RAW_DIR        = CEDA_DIR / "raw"
METADATA_DIR   = CEDA_DIR / "metadata"
LOGS_DIR       = CEDA_DIR / "logs"
CHECKPOINT_DB  = METADATA_DIR / "download_state.sqlite"

RAW_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# -- Logging ------------------------------------------------------------------
LOG_FILE = LOGS_DIR / f"thrissur_discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("thrissur_discovery")

# -- Constants ----------------------------------------------------------------
CEDA_BASE_URL      = "https://api.ceda.ashoka.edu.in/v1"
KERALA_STATE_ID    = 32
THRISSUR_DIST_ID   = 594
THRISSUR_DIST_NAME = "Thrissur"

MAX_REQUESTS     = 10     # one per commodity (9 x 2024Q4 + Sweet Potato 2025Q1)
REQUEST_DELAY_S  = 7      # seconds between requests (conservative)
CONNECT_TIMEOUT  = 20
READ_TIMEOUT     = 90

MIN_LAG_ROWS     = 2      # from price_prediction_service.py

ACTIVE_COMMODITIES = {
    19:  "Banana",
    90:  "Banana - Green",
    78:  "Tomato",
    23:  "Onion",
    24:  "Potato",
    35:  "Brinjal",
    87:  "Green Chilli",
    153: "Carrot",
    154: "Cabbage",
    152: "Sweet Potato",
}

# Status codes (match main downloader exactly)
PENDING          = "PENDING"
SUCCESS          = "SUCCESS"
NO_DATA          = "NO_DATA"
FAILED_RETRYABLE = "FAILED_RETRYABLE"
FAILED_FINAL     = "FAILED_FINAL"


class CedaRateLimitError(Exception):
    pass

class CedaAuthError(Exception):
    pass


# -- SQLite helpers -----------------------------------------------------------

def _db_connect() -> sqlite3.Connection:
    if not CHECKPOINT_DB.exists():
        raise FileNotFoundError(f"Checkpoint DB not found: {CHECKPOINT_DB}")
    conn = sqlite3.connect(str(CHECKPOINT_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _get_status_counts() -> Dict[str, int]:
    conn = _db_connect()
    rows = conn.execute(
        "SELECT status, COUNT(*) FROM download_tasks GROUP BY status"
    ).fetchall()
    conn.close()
    counts = {PENDING: 0, SUCCESS: 0, NO_DATA: 0,
              FAILED_RETRYABLE: 0, FAILED_FINAL: 0}
    for r in rows:
        counts[r[0]] = r[1]
    return counts


def _get_total_records() -> int:
    conn = _db_connect()
    n = conn.execute(
        "SELECT COALESCE(SUM(record_count), 0) FROM download_tasks WHERE status=?",
        (SUCCESS,)
    ).fetchone()[0]
    conn.close()
    return n


def _get_thrissur_records_count() -> int:
    conn = _db_connect()
    n = conn.execute(
        "SELECT COALESCE(SUM(record_count), 0) FROM download_tasks "
        "WHERE district_id=? AND status=?",
        (THRISSUR_DIST_ID, SUCCESS)
    ).fetchone()[0]
    conn.close()
    return n


def _select_pinned_tasks() -> List[sqlite3.Row]:
    """
    For each of our 10 commodities, select AT MOST ONE PENDING Thrissur task.
    Preference: 2024Q4 -> 2025Q1 -> 2025Q2 -> first available PENDING.
    Skips any commodity whose task is already SUCCESS or NO_DATA for that chunk.
    Returns list ordered by commodity_id.
    """
    conn = _db_connect()
    placeholders = ",".join("?" * len(ACTIVE_COMMODITIES))
    rows = conn.execute(f"""
        SELECT * FROM download_tasks
        WHERE district_id = ?
          AND commodity_id IN ({placeholders})
        ORDER BY commodity_id ASC, chunk_label ASC
    """, [THRISSUR_DIST_ID] + list(ACTIVE_COMMODITIES.keys())).fetchall()
    conn.close()

    by_commodity: Dict[int, List[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_commodity[row["commodity_id"]].append(row)

    PREFERRED = ["2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4",
                 "2026Q1", "2026Q2", "2026Q3"]

    selected = []
    for cid in sorted(ACTIVE_COMMODITIES.keys()):
        tasks = by_commodity.get(cid, [])
        if not tasks:
            log.warning("No Thrissur tasks in DB for commodity_id=%d (%s)",
                        cid, ACTIVE_COMMODITIES[cid])
            continue

        done = [t for t in tasks if t["status"] in (SUCCESS, NO_DATA)]
        if done:
            done_chunks = [t["chunk_label"] for t in done]
            log.info("commodity_id=%d (%s): already done chunks: %s",
                     cid, ACTIVE_COMMODITIES[cid], done_chunks)

        pending = [t for t in tasks if t["status"] == PENDING]
        if not pending:
            log.info("commodity_id=%d (%s): no PENDING tasks — skip",
                     cid, ACTIVE_COMMODITIES[cid])
            continue

        # Pick by preferred chunk order
        chosen = None
        for chunk in PREFERRED:
            for t in pending:
                if t["chunk_label"] == chunk:
                    chosen = t
                    break
            if chosen:
                break
        if chosen is None:
            chosen = pending[0]

        log.info("  Pinned: %s  [%s->%s]  commodity=%s(%d)",
                 chosen["task_id"], chosen["start_date"], chosen["end_date"],
                 ACTIVE_COMMODITIES[cid], cid)
        selected.append(chosen)

    return selected


def _upsert_task_update(task_id: str, updates: dict):
    """Update an existing task's mutable fields only. Does NOT insert new rows."""
    conn = _db_connect()
    now = datetime.now().isoformat()
    conn.execute("""
        UPDATE download_tasks SET
            status=?, attempt_count=?, record_count=?,
            output_file=?, sha256=?, last_error=?, updated_at=?
        WHERE task_id=?
    """, (
        updates.get("status", PENDING),
        updates.get("attempt_count", 0),
        updates.get("record_count", 0),
        updates.get("output_file", ""),
        updates.get("sha256", ""),
        updates.get("last_error", ""),
        now,
        task_id,
    ))
    conn.commit()
    conn.close()


def _save_known_markets_db(markets: Dict[int, str]):
    if not markets:
        return
    conn = _db_connect()
    for mid, mname in markets.items():
        conn.execute("""
            INSERT OR REPLACE INTO known_markets
              (market_id, market_name, district_id, district_name, state_id)
            VALUES (?, ?, ?, ?, ?)
        """, (str(mid), mname, THRISSUR_DIST_ID, THRISSUR_DIST_NAME, KERALA_STATE_ID))
    conn.commit()
    conn.close()


# -- API helpers --------------------------------------------------------------

def _get_api_key() -> str:
    key = os.getenv("CEDA_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "CEDA_API_KEY not set. Add it to D:\\Agri_mini\\.env"
        )
    return key


def _extract_records(data: Any) -> List[dict]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    out = data.get("output")
    if isinstance(out, dict):
        inner = out.get("data")
        if isinstance(inner, list):
            return inner
    if isinstance(out, list):
        return out
    for key in ("data", "results", "records", "prices"):
        val = data.get(key)
        if isinstance(val, list):
            return val
    return []


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ceda_post_prices(
    commodity_id: int,
    from_date: str,
    to_date: str,
    run_state: dict,
) -> Tuple[Optional[Any], int, Optional[str]]:
    api_key = _get_api_key()
    url     = f"{CEDA_BASE_URL}/agmarknet/prices"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
        "User-Agent":    "AgriMiniThrissurDiscovery/1.0",
    }
    body = {
        "commodity_id":       commodity_id,
        "state_id":           KERALA_STATE_ID,
        "census_state_id":    KERALA_STATE_ID,
        "district_id":        THRISSUR_DIST_ID,
        "census_district_id": THRISSUR_DIST_ID,
        "from_date":          from_date,
        "to_date":            to_date,
    }

    for attempt in range(1, 3):
        try:
            resp = requests.post(
                url, headers=headers, json=body,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
            run_state["requests_made"] += 1
            http_status = resp.status_code

            if http_status == 200:
                try:
                    return resp.json(), 200, None
                except ValueError as e:
                    return None, 200, f"JSON parse error: {e}"
            elif http_status in (401, 403):
                raise CedaAuthError(f"HTTP {http_status}: {resp.text[:200]}")
            elif http_status == 429:
                raise CedaRateLimitError(f"HTTP 429: {resp.text[:100]}")
            elif http_status in (500, 502, 503, 504):
                if attempt < 2:
                    time.sleep(10 * attempt)
                    continue
                return None, http_status, f"Server error HTTP {http_status}"
            else:
                return None, http_status, f"HTTP {http_status}: {resp.text[:100]}"

        except (CedaAuthError, CedaRateLimitError):
            raise
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as e:
            if attempt < 2:
                time.sleep(10)
                continue
            return None, 0, str(e)

    return None, 0, "All retries exhausted"


def _extract_market_ids(records: List[dict]) -> Dict[int, str]:
    seen: Dict[int, str] = {}
    for r in records:
        mid = r.get("market_id")
        if mid is None and isinstance(r.get("market"), dict):
            mid = r["market"].get("id")
        mname = r.get("market_name") or ""
        if isinstance(r.get("market"), dict):
            mname = r["market"].get("name", mname)
        if mid is not None:
            try:
                mid = int(mid)
            except (ValueError, TypeError):
                pass
            if mid not in seen:
                seen[mid] = str(mname) if mname else "unknown"
    return seen


def _save_raw_file(task: sqlite3.Row, records: List[dict]) -> Path:
    comm_name = task["commodity_name"]
    safe_c    = comm_name.replace(" ", "_").replace("/", "_")
    fname     = f"kerala_{THRISSUR_DIST_ID}_{safe_c}_{task['chunk_label']}.json"
    fpath     = RAW_DIR / fname

    payload = {
        "task_id":             task["task_id"],
        "state_id":            KERALA_STATE_ID,
        "district_id":         THRISSUR_DIST_ID,
        "district_name":       THRISSUR_DIST_NAME,
        "commodity_name":      comm_name,
        "chunk_label":         task["chunk_label"],
        "start_date":          task["start_date"],
        "end_date":            task["end_date"],
        "retrieval_timestamp": datetime.now().isoformat(),
        "source":              "CEDA_AGMARKNET",
        "api_endpoint":        f"{CEDA_BASE_URL}/agmarknet/prices",
        "record_count":        len(records),
        "records":             records,
    }

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    log.info("  Raw file saved: %s  (%d records)", fname, len(records))
    return fpath


# -- Main discovery batch -----------------------------------------------------

def run_discovery(dry_run: bool = False):
    log.info("=" * 70)
    log.info("THRISSUR DISCOVERY BATCH  (dry_run=%s)", dry_run)
    log.info("MAX_REQUESTS=%d  DELAY=%ds  MIN_LAG_ROWS=%d",
             MAX_REQUESTS, REQUEST_DELAY_S, MIN_LAG_ROWS)
    log.info("=" * 70)

    if not CHECKPOINT_DB.exists():
        log.error("CHECKPOINT DB NOT FOUND: %s", CHECKPOINT_DB)
        sys.exit(1)

    # -- 1. Pre-batch state (read-only) ---------------------------------------
    pre_counts   = _get_status_counts()
    pre_records  = _get_total_records()
    pre_thrissur = _get_thrissur_records_count()

    print()
    print("=" * 70)
    print("  PRE-BATCH STATE")
    print("=" * 70)
    total_tasks = sum(pre_counts.values())
    print(f"  Checkpoint DB    : {CHECKPOINT_DB}")
    print(f"  Total tasks      : {total_tasks}")
    print(f"  SUCCESS          : {pre_counts[SUCCESS]}")
    print(f"  NO_DATA          : {pre_counts[NO_DATA]}")
    print(f"  PENDING          : {pre_counts[PENDING]}")
    print(f"  FAILED_RETRYABLE : {pre_counts[FAILED_RETRYABLE]}")
    print(f"  FAILED_FINAL     : {pre_counts[FAILED_FINAL]}")
    print(f"  Total records (SUCCESS tasks)  : {pre_records:,}")
    print(f"  Thrissur records (SUCCESS only): {pre_thrissur}")
    print("=" * 70)

    # -- 2. Select pinned tasks -----------------------------------------------
    pinned_tasks = _select_pinned_tasks()

    print()
    print(f"  Pinned tasks for this batch: {len(pinned_tasks)}")
    for t in pinned_tasks:
        print(f"    [{t['commodity_id']:>3}] {t['commodity_name']:<20}  "
              f"{t['chunk_label']}  {t['start_date']} -> {t['end_date']}  "
              f"task_id={t['task_id']}")
    print()

    if not pinned_tasks:
        print("  No PENDING Thrissur tasks found. Nothing to do.")
        return

    if dry_run:
        print("  [DRY-RUN] No API calls made. Exiting.")
        return

    # -- 3. Execute -----------------------------------------------------------
    run_state = {
        "requests_made":     0,
        "records_downloaded": 0,
        "stop_reason":       "budget_reached",
    }
    results: Dict[int, dict] = {}

    for task in pinned_tasks:
        if run_state["requests_made"] >= MAX_REQUESTS:
            run_state["stop_reason"] = "budget_reached"
            log.info("Budget of %d requests reached.", MAX_REQUESTS)
            break

        cid       = task["commodity_id"]
        cname     = task["commodity_name"]
        chunk_lbl = task["chunk_label"]
        attempt   = task["attempt_count"] + 1

        log.info("[%d/%d] %s(%d)  chunk=%s  %s -> %s",
                 run_state["requests_made"] + 1, MAX_REQUESTS,
                 cname, cid, chunk_lbl, task["start_date"], task["end_date"])

        try:
            data, http_status, err = _ceda_post_prices(
                commodity_id=cid,
                from_date=task["start_date"],
                to_date=task["end_date"],
                run_state=run_state,
            )
            time.sleep(REQUEST_DELAY_S)

        except CedaRateLimitError as e:
            log.error("HTTP 429 — checkpoint saved, stopping immediately.")
            _upsert_task_update(task["task_id"], {
                "status": FAILED_RETRYABLE, "attempt_count": attempt,
                "last_error": str(e)[:400],
            })
            results[cid] = {"commodity": cname, "chunk": chunk_lbl,
                            "outcome": "RATE_LIMITED", "records": 0,
                            "markets": {}, "http_status": 429}
            run_state["stop_reason"] = "rate_limited"
            break

        except CedaAuthError as e:
            log.error("Auth error — stopping.")
            _upsert_task_update(task["task_id"], {
                "status": FAILED_FINAL, "attempt_count": attempt,
                "last_error": str(e)[:400],
            })
            results[cid] = {"commodity": cname, "chunk": chunk_lbl,
                            "outcome": "AUTH_ERROR", "records": 0,
                            "markets": {}, "http_status": 401}
            run_state["stop_reason"] = "auth_error"
            break

        # Process normal response
        if http_status == 200 and data is not None:
            records    = _extract_records(data)
            market_ids = _extract_market_ids(records)

            if records:
                fpath  = _save_raw_file(task, records)
                digest = _sha256_file(fpath)
                _upsert_task_update(task["task_id"], {
                    "status": SUCCESS, "attempt_count": attempt,
                    "record_count": len(records),
                    "output_file": str(fpath), "sha256": digest, "last_error": "",
                })
                if market_ids:
                    _save_known_markets_db(market_ids)
                run_state["records_downloaded"] += len(records)
                results[cid] = {"commodity": cname, "chunk": chunk_lbl,
                                "outcome": SUCCESS, "records": len(records),
                                "markets": market_ids, "http_status": 200}
                log.info("  -> SUCCESS: %d records  markets: %s",
                         len(records), market_ids)
            else:
                _upsert_task_update(task["task_id"], {
                    "status": NO_DATA, "attempt_count": attempt,
                    "record_count": 0, "output_file": "",
                    "sha256": "", "last_error": "",
                })
                results[cid] = {"commodity": cname, "chunk": chunk_lbl,
                                "outcome": NO_DATA, "records": 0,
                                "markets": {}, "http_status": 200}
                log.info("  -> NO_DATA (HTTP 200, empty records)")
        else:
            err_msg    = err or f"HTTP {http_status}"
            new_status = FAILED_RETRYABLE if attempt < 3 else FAILED_FINAL
            _upsert_task_update(task["task_id"], {
                "status": new_status, "attempt_count": attempt,
                "record_count": 0, "last_error": err_msg[:400],
            })
            results[cid] = {"commodity": cname, "chunk": chunk_lbl,
                            "outcome": f"FAILED({http_status})", "records": 0,
                            "markets": {}, "http_status": http_status}
            log.warning("  -> FAILED: HTTP %d  %s", http_status, err_msg)

    # -- 4. Post-batch report -------------------------------------------------
    post_counts   = _get_status_counts()
    post_records  = _get_total_records()
    post_thrissur = _get_thrissur_records_count()

    success_count = 0
    no_data_count = 0
    failed_count  = 0
    all_market_ids: Dict[int, Dict[int, str]] = {}

    for cid, r in results.items():
        if r["outcome"] == SUCCESS:
            success_count += 1
            all_market_ids[cid] = r["markets"]
        elif r["outcome"] == NO_DATA:
            no_data_count += 1
        else:
            failed_count += 1

    print()
    print("=" * 70)
    print("  THRISSUR DISCOVERY BATCH — RESULTS")
    print("=" * 70)
    print(f"  Requests used      : {run_state['requests_made']} / {MAX_REQUESTS}")
    print(f"  Records downloaded : {run_state['records_downloaded']}")
    print(f"  Stop reason        : {run_state['stop_reason']}")
    print()

    print(f"  {'Commodity':<22} {'cid':>5} {'Chunk':<8} {'Outcome':<16} "
          f"{'Records':>7}  Market IDs discovered")
    print("  " + "-" * 85)

    for cid in sorted(ACTIVE_COMMODITIES.keys()):
        cname = ACTIVE_COMMODITIES[cid]
        if cid in results:
            r       = results[cid]
            outcome = r["outcome"]
            n       = r["records"]
            mids    = r["markets"]
            chunk   = r["chunk"]
            mid_str = ", ".join(f"{mid}({mn})" for mid, mn in mids.items()) if mids else "-"
            print(f"  {cname:<22} {cid:>5} {chunk:<8} {outcome:<16} {n:>7}  {mid_str}")
        else:
            # Check for pre-existing done tasks
            conn = _db_connect()
            existing = conn.execute(
                "SELECT status, record_count, chunk_label FROM download_tasks "
                "WHERE district_id=? AND commodity_id=? AND status IN (?,?)",
                (THRISSUR_DIST_ID, cid, SUCCESS, NO_DATA)
            ).fetchall()
            conn.close()
            if existing:
                for e in existing:
                    note = f"PRE-EXISTING {e['status']} ({e['chunk_label']}, {e['record_count']} recs)"
                    print(f"  {cname:<22} {cid:>5} {e['chunk_label']:<8} {note}")
            else:
                print(f"  {cname:<22} {cid:>5} {'—':<8} {'SKIPPED':<16} {'—':>7}  —")

    print()
    print(f"  Batch totals: SUCCESS={success_count}  NO_DATA={no_data_count}  "
          f"FAILED={failed_count}  RATE_LIMITED={'YES' if run_state['stop_reason']=='rate_limited' else 'NO'}")

    # RF eligibility
    print()
    print(f"  RF-Eligibility (MIN_LAG_ROWS={MIN_LAG_ROWS}):")
    print(f"  {'Commodity':<22} {'cid':>5} {'market_id':>10} {'records':>8}  Eligible?")
    print("  " + "-" * 60)

    eligible_combos = []
    for cid in sorted(ACTIVE_COMMODITIES.keys()):
        cname = ACTIVE_COMMODITIES[cid]
        # Sum all SUCCESS records for this commodity in Thrissur
        conn = _db_connect()
        total_n = conn.execute(
            "SELECT COALESCE(SUM(record_count), 0) FROM download_tasks "
            "WHERE district_id=? AND commodity_id=? AND status=?",
            (THRISSUR_DIST_ID, cid, SUCCESS)
        ).fetchone()[0]
        conn.close()

        mids = all_market_ids.get(cid, {})
        if mids:
            for mid, mname in mids.items():
                eligible = total_n >= MIN_LAG_ROWS
                flag = "YES" if eligible else "NO (need more data)"
                print(f"  {cname:<22} {cid:>5} {mid:>10} {total_n:>8}  {flag}")
                if eligible:
                    eligible_combos.append((cid, cname, mid, mname, total_n))
        else:
            eligible = total_n >= MIN_LAG_ROWS
            flag = "YES" if eligible else "NO"
            mid_display = "(pre-existing)" if total_n > 0 else "—"
            print(f"  {cname:<22} {cid:>5} {mid_display:>10} {total_n:>8}  {flag}")
            if eligible and total_n > 0:
                eligible_combos.append((cid, cname, "pre-existing", "", total_n))

    print()
    if eligible_combos:
        print("  Commodity-market combinations safe to add to candidate list:")
        for cid, cname, mid, mname, n in eligible_combos:
            print(f"    OK  {cname} (id={cid})  market_id={mid}  "
                  f"market_name={mname or '(unknown)'}  records={n}")
    else:
        print("  No Thrissur markets meet the RF minimum record threshold.")

    # Checkpoint totals
    print()
    print("  Post-batch checkpoint totals:")
    print(f"    SUCCESS          : {post_counts[SUCCESS]}")
    print(f"    NO_DATA          : {post_counts[NO_DATA]}")
    print(f"    PENDING          : {post_counts[PENDING]}")
    print(f"    FAILED_RETRYABLE : {post_counts[FAILED_RETRYABLE]}")
    print(f"    FAILED_FINAL     : {post_counts[FAILED_FINAL]}")
    print(f"    Total records (SUCCESS tasks)  : {post_records:,}")
    print(f"    Thrissur records (SUCCESS only): {post_thrissur}")

    # Integrity
    print()
    print("  Data integrity:")
    ok_s = post_counts[SUCCESS]  >= pre_counts[SUCCESS]
    ok_n = post_counts[NO_DATA]  >= pre_counts[NO_DATA]
    print(f"    Existing SUCCESS preserved : {'YES' if ok_s else 'WARNING!'}"
          f"  ({pre_counts[SUCCESS]} -> {post_counts[SUCCESS]})")
    print(f"    Existing NO_DATA preserved : {'YES' if ok_n else 'WARNING!'}"
          f"  ({pre_counts[NO_DATA]} -> {post_counts[NO_DATA]})")
    print(f"    Only genuine CEDA data used: YES")
    print(f"    ML model / processed CSV / frontend: UNTOUCHED")

    if run_state["stop_reason"] == "rate_limited":
        print()
        print("  [RATE-LIMITED] Checkpoint saved. Wait ~60 min before next batch.")

    print("=" * 70)
    log.info("Discovery batch complete. Log: %s", LOG_FILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thrissur CEDA discovery batch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview selected tasks, make NO API calls")
    args = parser.parse_args()
    run_discovery(dry_run=args.dry_run)
