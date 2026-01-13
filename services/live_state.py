from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import HTTPException

from ml_pipeline.ml_filter import MLFilter

_LIVE_DATASET_CACHE: Dict[str, Dict[str, Any]] = {}
_LIVE_FILTER_CACHE: Dict[str, MLFilter] = {}
_LIVE_LAST_HEARTBEAT: Optional[datetime] = None
_DEMO_EVENT_QUEUE: List[Dict[str, Any]] = []
_DEMO_LOCK = threading.Lock()


def load_live_dataset(path: str) -> pd.DataFrame:
    path = str(path)
    cache = _LIVE_DATASET_CACHE.get(path)
    mtime = os.path.getmtime(path) if os.path.exists(path) else None
    if cache is not None and cache.get("mtime") == mtime:
        return cache["data"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"dataset not found: {path}")
    df = pd.read_csv(path, parse_dates=["entry_time", "exit_time"])
    _LIVE_DATASET_CACHE[path] = {"mtime": mtime, "data": df}
    return df


def load_live_filter(path: str) -> MLFilter:
    path = str(Path(path))
    filt = _LIVE_FILTER_CACHE.get(path)
    if filt is not None:
        return filt
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"model not found: {path}")
    filter_obj = MLFilter(Path(path))
    _LIVE_FILTER_CACHE[path] = filter_obj
    return filter_obj


def queue_demo_event(event: Dict[str, Any]) -> None:
    with _DEMO_LOCK:
        _DEMO_EVENT_QUEUE.append(event)


def drain_demo_events() -> List[Dict[str, Any]]:
    with _DEMO_LOCK:
        if not _DEMO_EVENT_QUEUE:
            return []
        events = list(_DEMO_EVENT_QUEUE)
        _DEMO_EVENT_QUEUE.clear()
        return events


def set_live_heartbeat(ts: datetime) -> None:
    global _LIVE_LAST_HEARTBEAT
    _LIVE_LAST_HEARTBEAT = ts


def get_live_heartbeat() -> Optional[datetime]:
    return _LIVE_LAST_HEARTBEAT
