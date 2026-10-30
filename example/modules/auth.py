"""Authorization by profiles from config.yml. OAuth2 tokens are cached per process and refreshed before expiry."""
import base64
import time

import requests

from modules.config import get_env
from modules.errors import AuthError, EnvironmentUnavailable

_tokens: dict[tuple, tuple[str, float]] = {}  # (token_url, form) -> (token, valid until)


class TokenAuth:
    """OAuth2 / OIDC (Keycloak, Auth0, Okta, Azure AD...): grant_type password or client_credentials."""

    def __init__(self, token_url: str, profile: dict, verify: bool = True):
        self.token_url, self.verify = token_url, verify
        self.form = {"grant_type": profile["grant_type"], "client_id": profile["client_id"]}
        if profile.get("client_secret_env"):
            self.form["client_secret"] = get_env(profile["client_secret_env"])
        if profile["grant_type"] == "password":
            self.form |= {"username": get_env(profile["username_env"]), "password": get_env(profile["password_env"])}
        for key in ("scope", "audience", "resource"):
            if profile.get(key):
                self.form[key] = profile[key]
        self._key = (token_url, tuple(sorted(self.form.items())))  # different scope/user -> different token

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}"}

    def token(self) -> str:
        token, valid_until = _tokens.get(self._key, (None, 0.0))
        if time.monotonic() < valid_until:
            return token
        try:
            r = requests.post(self.token_url, data=self.form, timeout=30, verify=self.verify)
        except (requests.ConnectionError, requests.Timeout) as error:
            raise EnvironmentUnavailable(f"Token server {self.token_url} is unreachable: {error}") from error
        if r.status_code in (502, 503, 504):
            raise EnvironmentUnavailable(f"Token server {self.token_url} answered {r.status_code}")
        if r.status_code != 200:  # the response may echo the request: do not put the body into the message
            raise AuthError(f"No token for client {self.form['client_id']}: {r.status_code} from {self.token_url}")
        body = r.json()
        ttl = body.get("expires_in", 300)
        _tokens[self._key] = (body["access_token"], time.monotonic() + max(ttl - 30, ttl / 2))
        return body["access_token"]

    def invalidate(self):
        """Drop the cached token, e.g. after the server revoked it."""
        _tokens.pop(self._key, None)


class BasicAuth:
    def __init__(self, profile: dict):
        raw = f"{get_env(profile['username_env'])}:{get_env(profile['password_env'])}"
        self._header = "Basic " + base64.b64encode(raw.encode()).decode()

    def headers(self) -> dict:
        return {"Authorization": self._header}


class ApiKeyAuth:
    def __init__(self, profile: dict):
        self._headers = {profile.get("header", "X-API-Key"): get_env(profile["key_env"])}

    def headers(self) -> dict:
        return dict(self._headers)


def get_auth(cfg: dict, profile_name: str | None):
    """Authorization by profile name from cfg['auth']['profiles']; None -> no authorization.

    A new kind (mTLS header, signed requests) is a class with headers() and a branch here.
    """
    if profile_name is None:
        return None
    profile = cfg["auth"]["profiles"][profile_name]
    kind = profile.get("type", "oauth2")
    if kind == "basic":
        return BasicAuth(profile)
    if kind == "api_key":
        return ApiKeyAuth(profile)
    return TokenAuth(profile.get("token_url") or cfg["auth"]["token_url"], profile, cfg.get("verify_ssl", True))
