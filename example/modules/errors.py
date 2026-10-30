"""Exception classes the report categories rely on (conftest.CATEGORIES matches their names).

AssertionError (and WaitTimeout) = the product misbehaved -> failed.
Any other exception = the test could not run -> broken; EnvironmentUnavailable narrows it to the environment.
"""


class EnvironmentUnavailable(Exception):
    """The environment is down or unreachable: gateway 502/503/504, the token server is down."""


class AuthError(Exception):
    """The token server rejected the credentials: check .env / CI variables and config.yml."""


class WaitTimeout(AssertionError):
    """The system did not reach the expected state in time."""
