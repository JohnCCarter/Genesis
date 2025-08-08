import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def disable_auth_for_tests():
    os.environ["AUTH_REQUIRED"] = "False"
    yield
    # optional cleanup
    os.environ.pop("AUTH_REQUIRED", None)


