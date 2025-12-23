import urllib.request
import urllib.parse
import http.cookiejar
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

    def post(self, path: str, data: Dict[str, str]) -> Tuple[int, str]:
        url = self.base_url + path
        encoded = urllib.parse.urlencode(data).encode()

        if self.debug:
            print(f"[HTTP] POST {url} keys={list(data.keys())}")

        req = urllib.request.Request(url, data=encoded, method="POST")
        with self.opener.open(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
