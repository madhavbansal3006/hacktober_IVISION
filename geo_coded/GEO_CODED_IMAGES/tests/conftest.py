import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.make_fixtures import FIXTURES_DIR, generate_all  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _generate_fixtures():
    """Regenerate synthetic JPEG fixtures once per test session."""
    generate_all()
    yield


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
