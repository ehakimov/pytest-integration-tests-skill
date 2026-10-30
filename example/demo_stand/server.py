"""
Demo stand for the example: a contracts service, an OAuth2 token server and a sign-in page.

It lets the example run without real services. Python standard library only.

    python demo_stand/server.py            # http://127.0.0.1:8099
    STAND_PORT=9000 TOKEN_TTL=60 python demo_stand/server.py

Routes:
- POST /oauth/token: a token (password / client_credentials);
- POST /api/v1/contracts: creates a contract, validates the body (400 with errors[].field);
- GET /api/v1/contracts/{id}: status PENDING, ACTIVE from the third request (asynchronous processing);
  signedAt comes back reformatted like real backends do: milliseconds and +00:00 instead of Z;
- POST /api/v1/contracts/{id}/documents: accepts a file (multipart);
- POST /api/v1/contracts/{id}/submit: 400 without a document, 200 after one is uploaded;
- DELETE /api/v1/contracts/{id};
- GET /api/v1/flaky?key=...: 503 twice, then 200 (retries); POST /api/v1/flaky?key=...: always 503 (no retries);
- any request to /down/...: 503 (the gateway is up, the service is not);
- GET /web/login: the sign-in page (password "secret");
- GET /debug/calls?key=...: calls of /api/v1/flaky with that key; GET /debug/token_calls: tokens issued.
Every response carries X-Request-Id, as a real gateway would.
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATE = {"token_calls": 0, "contracts": {}, "flaky": {}}
LOCK = threading.Lock()
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "300"))
USER_PASSWORD = "autotest-pass"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Sign in</title></head>
<body><form id="f">
<label for="u">Username</label><input id="u" data-testid="login-username">
<label for="p">Password</label><input id="p" type="password">
<button type="submit">Sign in</button></form>
<div data-testid="login-result" role="status"></div>
<script>
document.getElementById('f').addEventListener('submit', e => {
  e.preventDefault();
  const u = document.getElementById('u').value, p = document.getElementById('p').value;
  setTimeout(() => {
    document.querySelector('[data-testid=login-result]').textContent =
      p === 'secret' ? 'Welcome, ' + u : 'Invalid username or password';
  }, 300);
});
</script></body></html>"""


def reformat_instant(value):
    """2026-10-30T08:41:31.123Z -> 2026-10-30T08:41:31.123+00:00: the same moment, another form."""
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return value
    return moment.isoformat(timespec="milliseconds")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body=None, ctype="application/json"):
        data = b""
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode() if ctype == "application/json" else body.encode()
        self.send_response(code)
        self.send_header("X-Request-Id", uuid.uuid4().hex[:16])
        if body is not None:
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _authorized(self):
        return (self.headers.get("Authorization") or "").startswith("Bearer demo-token-")

    def _common(self, url):
        """Routes shared by all methods; True if the request was answered."""
        if url.path.startswith("/down/"):
            self._send(503, "Service Unavailable", ctype="text/plain")
            return True
        if url.path == "/api/v1/flaky":
            key = parse_qs(url.query).get("key", ["default"])[0]
            with LOCK:
                STATE["flaky"][key] = STATE["flaky"].get(key, 0) + 1
                calls = STATE["flaky"][key]
            if self.command != "GET" or calls <= 2:
                self._send(503, "Service Unavailable", ctype="text/plain")
            else:
                self._send(200, {"ok": True, "attempt": calls})
            return True
        return False

    def do_GET(self):
        url = urlparse(self.path)
        if self._common(url):
            return
        if url.path == "/debug/token_calls":
            return self._send(200, {"token_calls": STATE["token_calls"]})
        if url.path == "/debug/calls":
            key = parse_qs(url.query).get("key", ["default"])[0]
            return self._send(200, {"calls": STATE["flaky"].get(key, 0)})
        if url.path == "/web/login":
            return self._send(200, LOGIN_HTML, ctype="text/html")
        if not self._authorized():
            return self._send(401, {"message": "unauthorized"})
        match = re.match(r"^/api/v1/contracts/([0-9a-f-]+)$", url.path)
        if match:
            with LOCK:
                contract = STATE["contracts"].get(match.group(1))
                if not contract:
                    return self._send(404, {"message": "not found"})
                contract["polls"] += 1
                if contract["status"] == "PENDING" and contract["polls"] >= 3:
                    contract["status"] = "ACTIVE"
                body = {**contract["body"], "signedAt": reformat_instant(contract["body"].get("signedAt"))}
                return self._send(200, {"id": match.group(1), "status": contract["status"], **body})
        return self._send(404, {"message": "no route"})

    def do_POST(self):
        url = urlparse(self.path)
        raw = self._body()
        if self._common(url):
            return
        if url.path == "/oauth/token":
            form = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
            if form.get("grant_type") == "password" and form.get("password") != USER_PASSWORD:
                return self._send(401, {"error": "invalid_grant"})
            with LOCK:
                STATE["token_calls"] += 1
                calls = STATE["token_calls"]
            return self._send(200, {"access_token": f"demo-token-{calls}", "expires_in": TOKEN_TTL})
        if not self._authorized():
            return self._send(401, {"message": "unauthorized"})
        if url.path == "/api/v1/contracts":
            body = json.loads(raw or b"{}")
            errors = []
            if not body.get("number"):
                errors.append({"field": "number", "message": "is required"})
            if not UUID_RE.match(str(body.get("planId", ""))):
                errors.append({"field": "planId", "message": "must be a UUID"})
            if not body.get("customer", {}).get("lastName"):
                errors.append({"field": "lastName", "message": "is required"})
            if errors:
                return self._send(400, {"code": "VALIDATION_ERROR", "errors": errors})
            contract_id = str(uuid.uuid4())
            with LOCK:
                STATE["contracts"][contract_id] = {"body": body, "polls": 0, "documents": [], "status": "PENDING"}
            return self._send(201, {"id": contract_id, "status": "PENDING", "errors": []})
        match = re.match(r"^/api/v1/contracts/([0-9a-f-]+)/(documents|submit)$", url.path)
        if match:
            with LOCK:
                contract = STATE["contracts"].get(match.group(1))
                if not contract:
                    return self._send(404, {"message": "not found"})
                if match.group(2) == "documents":
                    name = re.search(rb'filename="([^"]+)"', raw)
                    contract["documents"].append(name.group(1).decode() if name else "file")
                    return self._send(201, {"documentId": str(uuid.uuid4())})
                if not contract["documents"]:
                    return self._send(400, {"code": "SUBMIT_REJECTED", "errors": [
                        {"field": "documents", "message": "At least one document is required", "critical": True}]})
                contract["status"] = "SUBMITTED"
                return self._send(200, {"status": "SUBMITTED"})
        return self._send(404, {"message": "no route"})

    def do_PUT(self):
        self._body()
        if not self._common(urlparse(self.path)):
            self._send(404, {"message": "no route"})

    def do_DELETE(self):
        url = urlparse(self.path)
        if self._common(url):
            return
        if not self._authorized():
            return self._send(401, {"message": "unauthorized"})
        match = re.match(r"^/api/v1/contracts/([0-9a-f-]+)$", url.path)
        with LOCK:
            if match and STATE["contracts"].pop(match.group(1), None) is not None:
                return self._send(204)
        return self._send(404, {"message": "not found"})


def main():
    port = int(os.environ.get("STAND_PORT", "8099"))
    print(f"Demo stand: http://127.0.0.1:{port}  (Ctrl+C to stop)", flush=True)  # noqa: T201
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
