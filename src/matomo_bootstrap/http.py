import http.cookiejar
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

    def get(self, path: str, params: Dict[str, str]) -> Tuple[int, str]:
        qs = urllib.parse.urlencode(params)
        url = f"{self.base_url}{path}?{qs}"

        if self.debug:
            print(f"[HTTP] GET {url}")

        req = urllib.request.Request(url, method="GET")
        with self.opener.open(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body

    def post(self, path: str, data: Dict[str, str]) -> Tuple[int, str]:
        url = self.base_url + path
        encoded = urllib.parse.urlencode(data).encode()

        if self.debug:
            print(f"[HTTP] POST {url} keys={list(data.keys())}")

        req = urllib.request.Request(url, data=encoded, method="POST")
        with self.opener.open(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
