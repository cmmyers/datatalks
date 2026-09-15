import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_repository
from app.main import app
from app.mock_repository import InMemoryBoardRepository
from app.repository import BoardRepository
from app.sql_models import Base
from app.sql_repository import SqlBoardRepository


def _make_sql_repository() -> SqlBoardRepository:
    # StaticPool keeps a single connection alive for the engine's lifetime —
    # without it, ":memory:" would hand out a fresh, empty database to each
    # new connection SqlBoardRepository opens per method call.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return SqlBoardRepository(sessionmaker(bind=engine))


@pytest.fixture(params=["memory", "sqlite"])
def client(request: pytest.FixtureRequest):
    """Runs every test that depends on this fixture against both repository
    implementations, to prove the API contract holds regardless of which
    storage backend sits behind it."""
    repository: BoardRepository
    if request.param == "memory":
        repository = InMemoryBoardRepository()
    else:
        repository = _make_sql_repository()

    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
