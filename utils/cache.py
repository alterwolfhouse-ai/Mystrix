from __future__ import annotations

import time
from typing import Any, Dict, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: int = 900, max_items: int = 512):
        self.ttl = ttl_seconds
        self.max = max_items
        self._store: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}

    def get(self, key: Tuple[Any, ...]):
        now = time.time()
        v = self._store.get(key)
        if not v:
            return None
        ts, data = v
        if now - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return data

    def set(self, key: Tuple[Any, ...], value: Any):
        if len(self._store) > self.max:
            # drop oldest
            oldest = sorted(self._store.items(), key=lambda kv: kv[1][0])[: int(self.max * 0.1) or 1]
            for k, _ in oldest:
                self._store.pop(k, None)
        self._store[key] = (time.time(), value)


global_cache = TTLCache()
