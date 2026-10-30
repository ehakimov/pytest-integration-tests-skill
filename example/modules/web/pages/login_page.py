# modules/web/pages/login_page.py
"""Page object of the sign-in page: locators and actions, no checks."""
from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page, base_url: str):
        self.page, self.url = page, f"{base_url}/login"
        # locator priority: test id -> role and accessible name / label -> text; no hashed classes or layout XPath
        self.username = page.get_by_test_id("login-username")
        self.password = page.get_by_label("Password")
        self.submit = page.get_by_role("button", name="Sign in")
        self.result = page.get_by_role("status")

    def open(self):
        self.page.goto(self.url)

    def login(self, username: str, password: str):
        self.username.fill(username)
        self.password.fill(password)
        self.submit.click()
