import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_repository
from app.main import app
from app.mock_repository import InMemoryBoardRepository


@pytest.fixture()
def client():
    """A TestClient backed by a fresh in-memory repository per test, so
    tests can't see each other's boards/cards."""
    repository = InMemoryBoardRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
