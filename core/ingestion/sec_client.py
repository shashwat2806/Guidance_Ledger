import hashlib
import json
import os
import time
from pathlib import Path

import httpx

CACHE_DIR = Path("cache/sec_raw")
MIN_INTERVAL = 0.11  # just over 1/10s, stays under the 10 req/s SEC fair-access limit


class SECClient:
    def __init__(self, user_agent=None, transport=None):
        self.user_agent = user_agent or os.environ["SEC_USER_AGENT"]
        self.last_request = 0.0
        self.http = httpx.Client(transport=transport, timeout=30)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _wait_for_slot(self):
        elapsed = time.monotonic() - self.last_request
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)

    def _cache_path(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        return CACHE_DIR / f"{key}.json"

    def get(self, url, use_cache=True):
        cache_path = self._cache_path(url)
        if use_cache and cache_path.exists():
            return json.loads(cache_path.read_text())

        headers = {"User-Agent": self.user_agent}
        backoff = 1.0
        for attempt in range(5):
            self._wait_for_slot()
            resp = self.http.get(url, headers=headers)
            self.last_request = time.monotonic()

            if resp.status_code == 200:
                data = resp.json()
                cache_path.write_text(json.dumps(data))
                return data

            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff *= 2
                continue

            resp.raise_for_status()

        raise RuntimeError(f"SEC request failed after retries: {url}")
