import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .repository import BoardRepository
from .sql_models import Base
from .sql_repository import SqlBoardRepository

# Swapping to Postgres later means changing this URL (and running Postgres),
# not changing any application code — SqlBoardRepository only uses portable
# SQLAlchemy constructs.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./hex_tracker.db")

# check_same_thread=False is needed because FastAPI runs sync dependencies
# in a thread pool, so a single sqlite connection may be used from more than
# one thread; this option is a no-op (and ignored) for non-sqlite backends.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
_engine = create_engine(DATABASE_URL, connect_args=_connect_args)
Base.metadata.create_all(_engine)
_SessionLocal = sessionmaker(bind=_engine)

_repository: BoardRepository = SqlBoardRepository(_SessionLocal)


def get_repository() -> BoardRepository:
    return _repository
