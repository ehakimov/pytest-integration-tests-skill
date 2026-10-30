# modules/web/web_test_steps.py
"""UI steps: scenario actions on top of page objects."""
import allure
from playwright.sync_api import Page

from modules.config import get_env
from modules.web.pages.login_page import LoginPage


class WebSteps:
    def __init__(self, page: Page, cfg: dict):
        self.cfg = cfg
        self.login_page = LoginPage(page, cfg["urls"]["web"])

    @property
    def greeting(self):
        """What the user sees after signing in: assertions take it from the steps, not from the page object."""
        return self.login_page.result

    def login_as(self, user: str = "operator", password: str | None = None) -> str:
        """Sign in with an account from cfg['ui_users']; the login and password come from environment variables."""
        creds = self.cfg["ui_users"][user]
        username = get_env(creds["username_env"])
        with allure.step(f"Signing in as {username}"):
            self.login_page.open()
            self.login_page.login(username, password or get_env(creds["password_env"]))
        return username
