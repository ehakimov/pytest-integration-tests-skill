"""Signing in to the web interface."""
import allure
import pytest

from asserts.web.web_asserts import assert_text
from modules.web.web_test_steps import WebSteps

pytestmark = [pytest.mark.ui, allure.epic("Web interface"), allure.feature("Sign-in")]


@allure.story("Successful sign-in")
@allure.title("An operator signs in with a username and password")
def test_operator_login(page, cfg):
    """An operator with the right password sees a greeting with their username."""
    steps = WebSteps(page, cfg)

    username = steps.login_as("operator")

    assert_text(steps.greeting, f"Welcome, {username}", "the greeting")
