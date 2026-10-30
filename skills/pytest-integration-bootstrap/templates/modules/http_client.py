"""The single HTTP entry point: timeout, retries, Allure attachments, masked logging."""
import logging
from http.cookiejar import DefaultCookiePolicy

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from modules.allure_helper import attach_http, mask_url

log = logging.getLogger(__name__)

# A failed connection is retried for any method: the request never reached the server.
# 502/503/504 are retried only for safe methods: a repeated POST/PUT/DELETE may run a business action twice
# (PUT is often an action like /submit, a repeated DELETE answers 404). If a client's PUT is truly idempotent,
# give that client its own Retry with PUT in allowed_methods.
# read=0: no retry after the request was sent. Retry-After is ignored: a maintenance page with
# "Retry-After: 600" would otherwise hang every request for minutes.
RETRY = Retry(total=3, connect=3, read=0, status=3, backoff_factor=0.5, status_forcelist=(502, 503, 504),
              allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}), respect_retry_after_header=False,
              raise_on_status=False)  # after the retries return the last response: the assertion will show it

_sessions: dict[tuple, requests.Session] = {}


def _session(verify: bool, retry: Retry) -> requests.Session:
    """One session (connection pool) per process and settings: no TLS handshake per test entity.

    Cookies are not kept: a shared session would carry them from one test to another. A cookie-based login
    passes cookies= explicitly or uses its own requests.Session in that client.
    """
    key = (verify, id(retry))
    if key not in _sessions:
        session = requests.Session()
        session.verify = verify
        session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
        for prefix in ("http://", "https://"):
            session.mount(prefix, HTTPAdapter(max_retries=retry))
        _sessions[key] = session
    return _sessions[key]


class HttpClient:
    """Base for API clients: a service client passes base_url and auth (an object with headers())."""

    def __init__(self, base_url: str, auth=None, timeout: float = 30, verify: bool = True, retry: Retry = RETRY):
        self.base_url, self.auth, self.timeout = base_url.rstrip("/"), auth, timeout
        self.session = _session(verify, retry)
        if not verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def request(self, method: str, route: str = "", *, url: str | None = None, headers: dict | None = None,
                attach: bool = True, timeout: float | None = None, **kwargs) -> requests.Response:
        """route: path from base_url; url: a full address (another service, a link from a response).

        headers={"Authorization": None} sends the request without the header at all.
        """
        if url is None:
            url = f"{self.base_url}/{route.lstrip('/')}" if route else self.base_url
        all_headers = {**(self.auth.headers() if self.auth else {}), **(headers or {})}
        response = self.session.request(method, url, headers=all_headers, timeout=timeout or self.timeout, **kwargs)
        log.info("%s %s -> %s (%.2f s)", method, mask_url(url), response.status_code, response.elapsed.total_seconds())
        if attach:
            attach_http(response)
        return response

    def get(self, route: str = "", **kwargs):
        return self.request("GET", route, **kwargs)

    def post(self, route: str = "", **kwargs):
        return self.request("POST", route, **kwargs)

    def put(self, route: str = "", **kwargs):
        return self.request("PUT", route, **kwargs)

    def patch(self, route: str = "", **kwargs):
        return self.request("PATCH", route, **kwargs)

    def delete(self, route: str = "", **kwargs):
        return self.request("DELETE", route, **kwargs)
