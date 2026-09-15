from .mock_repository import InMemoryBoardRepository
from .repository import BoardRepository

_repository: BoardRepository = InMemoryBoardRepository()


def get_repository() -> BoardRepository:
    return _repository
