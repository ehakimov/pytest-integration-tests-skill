# UI tests with Playwright

Read this when a test drives a browser. The `browser` and `page` fixtures come from the core
(`modules/web/fixtures.py`, the pytest-integration-bootstrap skill): a browser per worker, a clean context per test,
a screenshot and a Playwright trace attached on failure.

Layers are the same as for the API:

- **Page object** (`modules/web/pages/`): locators and actions, no checks.
- **UI steps** (`modules/web/*_test_steps.py`): scenarios over page objects under `allure.step`; they also expose
  what assertions need (the test does not reach into a page object).
- **Assertions** (`asserts/web/`): `expect` inside `assert_*`: it waits for the state itself.

```python
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
```

```python
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
```

```python
# asserts/web/web_asserts.py
"""UI assertions through expect: it waits for the state itself, no sleep needed."""
import allure
from playwright.sync_api import Locator, expect


def assert_text(locator: Locator, text: str, what: str):
    with allure.step(f"Checking that {what} is \"{text}\""):
        expect(locator, f"{what}: expected \"{text}\"").to_have_text(text)
```

A test:

```python
@allure.story("Successful sign-in")
@allure.title("An operator signs in with a username and password")
def test_operator_login(page, cfg):
    """An operator with the right password sees a greeting with their username."""
    steps = WebSteps(page, cfg)

    username = steps.login_as("operator")

    assert_text(steps.greeting, f"Welcome, {username}", "the greeting")
```

## Rules

- Locator priority: test id (agree on `data-testid` with the frontend; the attribute is `ui_test_id_attribute`
  in the config) → role and accessible name / field label → text → a stable attribute (`name=`). Never hashed
  CSS-module classes (`[class*="_button_x7k2p_"]`), `:near()` or XPath along the layout. If the project keeps
  locators as strings, use the engines `data-testid=login`, `role=button[name="Sign in"]`.
- No `wait_for_selector`, `sleep` or `is_*()` methods with `except: return False`: they hide the cause of a failure.
  `expect` waits; a page action waits for actionability.
- Accounts: `cfg["ui_users"][<role>]` with names of environment variables. A visible browser: `--headed`;
  another engine: `ui_browser: firefox` in the config.
- Open a failed test's trace with `playwright show-trace trace.zip` (the attachment of the `page` fixture).
  A trace records typed values, passwords included: UI tests use dedicated test accounts only.
