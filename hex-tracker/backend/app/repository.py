from abc import ABC, abstractmethod

from .models import Board, Card, ColumnId


class BoardNotFoundError(Exception):
    pass


class CardNotFoundError(Exception):
    pass


class BoardRepository(ABC):
    """Storage interface for boards and cards.

    Implementations must raise BoardNotFoundError / CardNotFoundError rather
    than returning None, so route handlers can translate them into 404s
    uniformly regardless of which storage backend is behind this interface.
    """

    @abstractmethod
    def create_board(self, name: str) -> Board: ...

    @abstractmethod
    def get_board(self, board_id: str) -> Board: ...

    @abstractmethod
    def update_board(self, board_id: str, *, name: str) -> Board: ...

    @abstractmethod
    def create_card(
        self, board_id: str, column_id: ColumnId, title: str, description: str
    ) -> Card: ...

    @abstractmethod
    def update_card(
        self,
        board_id: str,
        card_id: str,
        *,
        title: str | None,
        description: str | None,
        column_id: ColumnId | None,
        position: int | None,
    ) -> Card: ...

    @abstractmethod
    def delete_card(self, board_id: str, card_id: str) -> None: ...
