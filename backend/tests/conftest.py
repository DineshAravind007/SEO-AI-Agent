import pytest
from backend.main import app
from backend.security.auth import get_current_user
from backend.database.models import User

_DEFAULT_TEST_USER = User(
    id=1,
    email="test@example.com",
    name="Test User",
    is_active=True,
)

@pytest.fixture(autouse=True)
def auto_override_auth(request):
    """
    Ensure all existing test suites that run without authentication headers
    seamlessly receive an authenticated test user, preserving full backward compatibility.
    Dedicated auth tests in test_auth.py are excluded to test real token/unauthenticated behavior.
    """
    if "test_auth" in request.node.nodeid:
        yield
        return

    app.dependency_overrides[get_current_user] = lambda: _DEFAULT_TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)
