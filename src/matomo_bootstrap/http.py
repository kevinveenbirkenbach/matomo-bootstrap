from __future__ import annotations

import http.cookiejar
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Tuple


class HttpClient:
    def __init__(self, base_url: str, timeout: int = 20, debug: bool = False):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.debug = debug

        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def _dbg(self, msg: str) -> None:
        if self.debug:
            print(msg, file=sys.stderr)

    def _open(self, req: urllib.request.Request) -> Tuple[int, str]:
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return resp.status, body
        except urllib.error.HTTPError as exc:
            # urllib raises HTTPError for 4xx/5xx but it still contains status + body
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(exc)
            return exc.code, body

    def get(self, path: str, params: Dict[str, str]) -> Tuple[int, str]:
        qs = urllib.parse.urlencode(params)
        if path == "/":
            url = f"{self.base_url}/"
        else:
            url = f"{self.base_url}{path}"
        if qs:
            url = f"{url}?{qs}"

        self._dbg(f"[HTTP] GET {url}")

        req = urllib.request.Request(url, method="GET")
        return self._open(req)

    def post(self, path: str, data: Dict[str, str]) -> Tuple[int, str]:
        url = self.base_url + path
        encoded = urllib.parse.urlencode(data).encode()

        self._dbg(f"[HTTP] POST {url} keys={list(data.keys())}")

        req = urllib.request.Request(url, data=encoded, method="POST")
        return self._open(req)
