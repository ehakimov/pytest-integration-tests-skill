"""Waiting for asynchronous changes: one Allure step, the polling history and the last response."""
import time

import allure
import requests

from modules.allure_helper import attach_http, attach_json, attach_lines, body_preview, http_attachments_off
from modules.errors import WaitTimeout

__all__ = ["WaitTimeout", "wait_until"]


def wait_until(probe, *, description: str, until=bool, timeout: float = 60, interval: float = 2):
    """Calls probe() every interval seconds until until(result) is true; returns the result.

    probe must not fail before the system is ready (until checks the condition); an exception from probe or
    until stops the wait at once, the history collected so far is still attached.
    """
    with allure.step(f"Waiting: {description} (up to {timeout} s)"):
        started, history, result, done = time.monotonic(), [], None, False
        try:
            while True:
                with http_attachments_off():
                    result = probe()
                history.append(f"{time.monotonic() - started:6.1f} s  {_short(result)}")
                done = until(result)
                if done or time.monotonic() - started + interval > timeout:
                    break
                time.sleep(interval)
        finally:
            attach_lines(history, f"Polling history, attempts: {len(history)}")
            if isinstance(result, requests.Response):
                attach_http(result, force=True)
            elif history:
                attach_json(result, "Last value")
        if not done:
            raise WaitTimeout(f"Timed out after {timeout} s: {description}. Last: {_short(result)}")
        return result


def _short(value) -> str:
    if isinstance(value, requests.Response):
        return f"{value.status_code} {body_preview(value, 200)}"
    return repr(value)[:200]
