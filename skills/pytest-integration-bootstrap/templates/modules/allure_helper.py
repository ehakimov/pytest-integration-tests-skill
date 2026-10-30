"""All Allure attachments go through here: secrets are masked, large bodies are truncated."""
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import unquote_plus, urlsplit, urlunsplit

import allure

# A key is secret if, without "_", "-" and case, it contains one of these: accessToken, X-API-Key, client_secret...
SECRET_FRAGMENTS = ("password", "passwd", "secret", "token", "apikey", "authorization", "cookie",
                    "credential", "privatekey", "signature")
TRACE_HEADERS = ("x-request-id", "x-correlation-id", "x-trace-id", "traceparent")  # shown in the response name
MASK = "***"
MAX_TEXT = 50_000
_http_attach = ContextVar("http_attach", default=True)


def is_secret(key) -> bool:
    normalized = re.sub(r"[\W_]", "", str(key)).lower()
    return any(fragment in normalized for fragment in SECRET_FRAGMENTS)


def mask_secrets(data):
    """dict/list with secret values replaced; other values are returned as is."""
    if isinstance(data, dict):
        return {k: MASK if is_secret(k) else mask_secrets(v) for k, v in data.items()}
    if isinstance(data, list):
        return [mask_secrets(v) for v in data]
    return data


def _mask_pairs(query: str) -> str:
    """a=1&password=x -> a=1&password=***, the original encoding of other pairs is kept."""
    parts = []
    for part in query.split("&"):
        key, sep, _ = part.partition("=")
        parts.append(f"{key}={MASK}" if sep and is_secret(unquote_plus(key)) else part)
    return "&".join(parts)


def mask_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(query=_mask_pairs(parts.query))) if parts.query else url


def mask_text(text: str) -> str:
    """JSON -> masked JSON, form body (a=1&b=2) -> masked pairs, anything else -> as is."""
    try:
        return json.dumps(mask_secrets(json.loads(text)), ensure_ascii=False)
    except ValueError:
        pass
    if re.fullmatch(r"[^\s=&]+=[^\s&]*(&[^\s=&]+=[^\s&]*)*", text):
        return _mask_pairs(text)
    return text


def body_preview(response, limit: int = 1000) -> str:
    """The start of a response body for assertion messages: masked like the attachments."""
    if not response.content:
        return "(empty body)"
    try:
        return mask_text(response.text)[:limit]
    except UnicodeDecodeError:
        return f"binary body, {len(response.content)} bytes"


def attach_json(data, name: str):
    """dict/list or a JSON string; invalid JSON is attached as (masked) text."""
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except ValueError:
            return attach_text(mask_text(data.decode("utf-8", "replace") if isinstance(data, bytes) else data), name)
    text = json.dumps(mask_secrets(data), ensure_ascii=False, indent=2, default=str)
    if len(text) > MAX_TEXT:
        return attach_text(text[:MAX_TEXT] + f"\n... truncated, {len(text)} characters in total", name)
    allure.attach(text, name=name, attachment_type=allure.attachment_type.JSON)


def attach_text(text, name: str):
    allure.attach(str(text)[:MAX_TEXT], name=name, attachment_type=allure.attachment_type.TEXT)


def attach_lines(lines, name: str):
    attach_text("\n".join(map(str, lines)), name)


def attach_png(png: bytes, name: str):
    allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)


def attach_file(path, name: str, attachment_type=None, extension: str | None = None):
    """attachment_type: allure.attachment_type.* or a MIME string ("application/zip")."""
    allure.attach.file(str(path), name=name, attachment_type=attachment_type, extension=extension)


@contextmanager
def http_attachments_off():
    """No HTTP attachments inside the block (polling in wait_until)."""
    token = _http_attach.set(False)
    try:
        yield
    finally:
        _http_attach.reset(token)


def attach_http(response, force: bool = False):
    """Two attachments in the current step: "POST to <url>" and "Response with status code N (t s)"."""
    if not (force or _http_attach.get()):
        return
    request = response.request
    name = f"{request.method} to {mask_url(request.url)}"
    body = request.body
    if body is None:
        attach_text("(no body)", name)
    elif isinstance(body, (str, bytes)):
        try:
            attach_json(body.decode("utf-8") if isinstance(body, bytes) else body, name)
        except UnicodeDecodeError:
            attach_text(f"binary body (multipart/file), {len(body)} bytes", name)
    else:
        attach_text(f"streamed body: {type(body).__name__}", name)
    trace = " ".join(f"{h}={response.headers[h]}" for h in TRACE_HEADERS if h in response.headers)
    name = f"Response with status code {response.status_code} ({response.elapsed.total_seconds():.2f} s)"
    name += f" {trace}" if trace else ""
    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type or response.content.lstrip()[:1] in (b"{", b"["):
        attach_json(response.text, name)
    elif not response.content or content_type.startswith("text/") or "xml" in content_type:
        attach_text(mask_text(response.text) if response.content else "(empty body)", name)
    else:
        attach_text(f"{content_type or 'binary response'}: {len(response.content)} bytes", name)
