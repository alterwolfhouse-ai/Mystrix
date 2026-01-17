import os
from pathlib import Path
import time
import sqlite3
import threading
from contextlib import contextmanager
from typing import Optional

import pandas as pd

from .data import fetch_ccxt_hist_range, resample_ohlcv, synthetic_hourly
from .bybit_data import fetch_klines, BYBIT_MAINNET

"""Stable SQLite path.

Previously this used the current working directory, which could differ
depending on how the server was launched (CLI, service, IDE). That led to
multiple data_cache.db files and confusing auth/login behavior.

Anchor the DB to the repository root (two levels up from this file), unless
overridden by the MYSTRIX_DB_PATH environment variable.
"""
_DEFAULT_DB_PATH = str(Path(__file__).resolve().parents[1] / "data_cache.db")
DB_PATH = os.environ.get("MYSTRIX_DB_PATH", _DEFAULT_DB_PATH)
def resolve_db_path(custom: Optional[Path] = None) -> str:
    if custom:
        return str(Path(custom).expanduser().resolve() / "data_cache.db")
    return os.environ.get("MYSTRIX_DB_PATH", _DEFAULT_DB_PATH)

# Serialize writers to avoid "database is locked" under concurrent upserts.
_WRITE_LOCK = threading.Lock()


@contextmanager
def _conn(custom_db: Optional[Path] = None):
    db_path = resolve_db_path(custom_db)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    try:
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute("PRAGMA busy_timeout=8000")
            con.execute("PRAGMA temp_store=MEMORY")
        except Exception:
            pass
        init_schema(con)
        yield con
        con.commit()
    finally:
        con.close()


def _df_to_rows(df: pd.DataFrame):
    for ts, row in df.iterrows():
        yield int(pd.Timestamp(ts).timestamp() * 1000), float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), float(row.get("volume", 0.0))


def cached_bounds(symbol: str, timeframe: str, cache_root: Optional[Path] = None) -> tuple[Optional[int], Optional[int]]:
    """Return (min_ts_ms, max_ts_ms) in cache for symbol/tf."""
    with _conn(cache_root) as con:
        cur = con.execute("SELECT MIN(ts), MAX(ts) FROM ohlcv WHERE symbol=? AND timeframe=?", (symbol, timeframe))
        row = cur.fetchone()
        if not row or (row[0] is None and row[1] is None):
            return None, None
        return (int(row[0]) if row[0] is not None else None, int(row[1]) if row[1] is not None else None)


def _bar_ms(tf: str) -> int:
    minutes = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240, "12h": 720, "1d": 1440,
    }.get(tf, 60)
    return minutes * 60_000


def ensure_range_in_db(symbol: str, timeframe: str, start: str, end: str, cache_root: Optional[Path] = None):
    """Ensure requested range is cached; fetch only missing head/tail."""
    start_ms = int(pd.to_datetime(start).timestamp() * 1000)
    end_ms = int(pd.to_datetime(end).timestamp() * 1000)
    bar_ms = _bar_ms(timeframe)
    min_cached, max_cached = cached_bounds(symbol, timeframe, cache_root=cache_root)

    # Fully covered, skip network
    if min_cached is not None and max_cached is not None and start_ms >= min_cached and end_ms <= max_cached:
        return

    ranges = []
    if min_cached is None or start_ms < (min_cached - bar_ms):
        fetch_start = start_ms
        fetch_end = min(min_cached - bar_ms if min_cached else end_ms, end_ms)
        ranges.append((fetch_start, fetch_end))
    if max_cached is None or end_ms > (max_cached + bar_ms):
        fetch_start = max(start_ms, (max_cached + bar_ms) if max_cached else start_ms)
        if fetch_start <= end_ms:
            ranges.append((fetch_start, end_ms))

    for (fs, fe) in ranges:
        df = None
        try:
            df = fetch_ccxt_hist_range(
                symbol,
                timeframe=timeframe,
                start=pd.to_datetime(fs, unit="ms").isoformat(),
                end=pd.to_datetime(fe, unit="ms").isoformat(),
            )
        except Exception:
            df = None
        if df is None or df.empty:
            try:
                tf_minutes = {"1m":1, "3m":3, "5m":5, "15m":15, "30m":30, "1h":60, "2h":120, "4h":240, "12h":720, "1d":1440}.get(timeframe, 60)
                step_ms = tf_minutes * 60_000 * 1000  # 1000 bars window
                end_cur = fe
                chunks = []
                attempts = 0
                while end_cur > fs and attempts < 5000:
                    attempts += 1
                    start_cur = max(fs, end_cur - step_ms)
                    by = fetch_klines(symbol.replace("/",""), timeframe, start_ms=start_cur, end_ms=end_cur, base_url=BYBIT_MAINNET)
                    if by is None or by.empty:
                        break
                    chunks.append(by)
                    first_ts = int(by.index[0].value // 10**6)
                    if first_ts <= fs:
                        break
                    end_cur = first_ts - 1
                    time.sleep(0.05)
                if chunks:
                    by_all = pd.concat(list(reversed(chunks))).sort_index().astype(float)
                    tmp = by_all.rename(columns={"volume_base":"volume"})
                    df = tmp[["open","high","low","close","volume"]]
            except Exception:
                df = None
        if df is None or df.empty:
            continue

        with _conn(cache_root) as con:
            con.executemany(
                "INSERT OR REPLACE INTO ohlcv(symbol, timeframe, ts, open, high, low, close, volume) VALUES(?,?,?,?,?,?,?,?)",
                ((symbol, timeframe, *row) for row in _df_to_rows(df))
            )


def get_ohlcv(symbol: str, timeframe: str, start: str, end: str, cache_root: Optional[Path] = None) -> pd.DataFrame:
    """Return OHLCV dataframe for the requested range, ensuring cache is populated."""
    ensure_range_in_db(symbol, timeframe, start, end, cache_root=cache_root)
    start_ms = int(pd.to_datetime(start).timestamp() * 1000)
    end_ms = int(pd.to_datetime(end).timestamp() * 1000)
    with _conn(cache_root) as con:
        cur = con.execute(
            "SELECT ts, open, high, low, close, volume FROM ohlcv WHERE symbol=? AND timeframe=? AND ts BETWEEN ? AND ? ORDER BY ts ASC",
            (symbol, timeframe, start_ms, end_ms),
        )
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=["open","high","low","close","volume"], index=pd.to_datetime([]))
    df = pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume"]) 
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df.astype(float)


def get_recent(symbol: str, timeframe: str, bars: int = 500) -> pd.DataFrame:
    """Convenience: return recent bars by looking back a safe window and reusing the cache."""
    end = pd.Timestamp.utcnow().floor("min")
    # rough window: assume 3m bars => 3*bars minutes; make it generous
    minutes = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 60*24
    }.get(timeframe, 60)
    start = end - pd.Timedelta(minutes=minutes * (bars + 50))
    return get_ohlcv(symbol, timeframe, start.isoformat(), end.isoformat())


def init_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlcv (
          symbol TEXT NOT NULL,
          timeframe TEXT NOT NULL,
          ts INTEGER NOT NULL,
          open REAL NOT NULL,
          high REAL NOT NULL,
          low REAL NOT NULL,
          close REAL NOT NULL,
          volume REAL NOT NULL,
          PRIMARY KEY(symbol, timeframe, ts)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_ohlcv(
          symbol TEXT NOT NULL,
          tf TEXT NOT NULL,
          ts INTEGER NOT NULL,
          open REAL, high REAL, low REAL, close REAL,
          volume_base REAL,
          volume_quote REAL,
          is_closed INTEGER,
          source TEXT DEFAULT 'bybit_v5',
          ingested_at INTEGER,
          PRIMARY KEY(symbol, tf, ts)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS derived_info(
          key TEXT PRIMARY KEY,
          value TEXT,
          updated_at INTEGER
        )
        """
    )
    # Basic auth + user data tables
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          name TEXT,
          pass_hash TEXT NOT NULL,
          pass_salt TEXT NOT NULL,
          is_admin INTEGER DEFAULT 0,
          created_at INTEGER
        )
        """
    )
    _ensure_user_columns(con)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions(
          sid TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          created_at INTEGER,
          expires_at INTEGER,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS favorites(
          user_id INTEGER NOT NULL,
          symbol TEXT NOT NULL,
          created_at INTEGER,
          PRIMARY KEY(user_id, symbol),
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS suggestions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          text TEXT NOT NULL,
          created_at INTEGER,
          resolved INTEGER DEFAULT 0,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS settings(
          key TEXT PRIMARY KEY,
          value TEXT,
          updated_at INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger_entries(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          principal_delta REAL NOT NULL DEFAULT 0,
          profit_delta REAL NOT NULL DEFAULT 0,
          kind TEXT NOT NULL,
          note TEXT,
          created_at INTEGER,
          batch_id INTEGER,
          created_by INTEGER,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS pool_yield_batches(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          amount REAL NOT NULL,
          total_principal REAL NOT NULL,
          allocated_to INTEGER NOT NULL,
          note TEXT,
          created_at INTEGER,
          created_by INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          admin_id INTEGER,
          action TEXT NOT NULL,
          target_user_id INTEGER,
          payload TEXT,
          created_at INTEGER,
          FOREIGN KEY(admin_id) REFERENCES users(id) ON DELETE SET NULL,
          FOREIGN KEY(target_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )


def _ensure_user_columns(con: sqlite3.Connection) -> None:
    cols = {row[1] for row in con.execute("PRAGMA table_info(users)").fetchall()}
    additions = {
        "has_mystrix_plus": "INTEGER DEFAULT 0",
        "has_backtest": "INTEGER DEFAULT 0",
        "has_autotrader": "INTEGER DEFAULT 0",
        "has_chat": "INTEGER DEFAULT 0",
        "is_active": "INTEGER DEFAULT 1",
        "plan_expires_at": "INTEGER DEFAULT NULL",
        "last_login": "INTEGER DEFAULT NULL",
        "plan_name": "TEXT DEFAULT ''",
        "plan_note": "TEXT DEFAULT ''",
    }
    for col, decl in additions.items():
        if col not in cols:
            con.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")

def upsert_ohlcv(df: pd.DataFrame, symbol: str, tf: str) -> int:
    if df is None or df.empty:
        return 0
    df = df.copy()
    cols = ["open","high","low","close","volume_base","volume_quote","is_closed"]
    for c in cols:
        if c not in df.columns:
            df[c] = 0.0
    with _WRITE_LOCK:
        with _conn() as con:
            rows = [
            (
                symbol,
                tf,
                int(pd.Timestamp(ts).timestamp() * 1000),
                float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                float(r["volume_base"]), float(r.get("volume_quote", 0.0)),
                int(r.get("is_closed", 1)),
                int(pd.Timestamp.utcnow().timestamp()),
            )
            for ts, r in df.iterrows()
        ]
        con.executemany(
            """
            INSERT OR REPLACE INTO raw_ohlcv(symbol, tf, ts, open, high, low, close, volume_base, volume_quote, is_closed, ingested_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        return len(rows)


def latest_ts(symbol: str, tf: str) -> Optional[int]:
    with _conn() as con:
        cur = con.execute("SELECT MAX(ts) FROM raw_ohlcv WHERE symbol=? AND tf=?", (symbol, tf))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None


def raw_ohlcv(symbol: str, tf: str, start_ms: Optional[int] = None, end_ms: Optional[int] = None) -> pd.DataFrame:
    q = "SELECT ts, open, high, low, close, volume_base, volume_quote, is_closed FROM raw_ohlcv WHERE symbol=? AND tf=?"
    args = [symbol, tf]
    if start_ms is not None:
        q += " AND ts >= ?"; args.append(int(start_ms))
    if end_ms is not None:
        q += " AND ts <= ?"; args.append(int(end_ms))
    q += " ORDER BY ts ASC"
    with _conn() as con:
        rows = con.execute(q, tuple(args)).fetchall()
    if not rows:
        return pd.DataFrame(columns=["open","high","low","close","volume_base","volume_quote","is_closed"], index=pd.to_datetime([]))
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume_base","volume_quote","is_closed"]) 
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df.set_index("ts", inplace=True)
    return df.astype(float)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["open","high","low","close","volume_base","volume_quote","is_closed"], index=pd.to_datetime([]))
    agg = {"open":"first","high":"max","low":"min","close":"last","volume_base":"sum","volume_quote":"sum","is_closed":"last"}
    return df.resample(rule).agg(agg).dropna()


def save_derived(key: str, value_json: str) -> None:
    with _conn() as con:
        con.execute("INSERT OR REPLACE INTO derived_info(key,value,updated_at) VALUES (?,?,?)", (key, value_json, int(pd.Timestamp.utcnow().timestamp())))


def load_derived(key: str) -> Optional[str]:
    with _conn() as con:
        row = con.execute("SELECT value FROM derived_info WHERE key=?", (key,)).fetchone()
    return row[0] if row else None



