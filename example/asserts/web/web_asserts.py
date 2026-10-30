# asserts/web/web_asserts.py
"""UI assertions through expect: it waits for the state itself, no sleep needed."""
import allure
from playwright.sync_api import Locator, expect


def assert_text(locator: Locator, text: str, what: str):
    with allure.step(f"Checking that {what} is \"{text}\""):
        expect(locator, f"{what}: expected \"{text}\"").to_have_text(text)
