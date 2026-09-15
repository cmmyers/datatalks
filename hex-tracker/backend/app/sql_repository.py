import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Board, Card, Column, ColumnId
from .repository import BoardNotFoundError, BoardRepository, CardNotFoundError
from .sql_models import BoardRow, CardRow

FIXED_COLUMNS: list[tuple[ColumnId, str]] = [
    (ColumnId.TODO, "To Do"),
    (ColumnId.IN_PROGRESS, "In Progress"),
    (ColumnId.DONE, "Done"),
]


class SqlBoardRepository(BoardRepository):
    """Same contract as InMemoryBoardRepository, backed by SQLAlchemy.

    Only plain, portable column types are used (no SQLite-specific
    features), so swapping to Postgres later is a connection-string change
    in app/dependencies.py, not a rewrite of this class.

    Like the mock, a card's position is recomputed from its ordered index
    within a column rather than trusted as stored state — reorders/moves
    reload the affected column(s), splice in Python, and renumber, mirroring
    InMemoryBoardRepository's approach exactly.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create_board(self, name: str) -> Board:
        with self._session_factory() as session:
            row = BoardRow(id=str(uuid.uuid4()), name=name)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_board(row)

    def get_board(self, board_id: str) -> Board:
        with self._session_factory() as session:
            row = session.get(BoardRow, board_id)
            if row is None:
                raise BoardNotFoundError(board_id)
            return self._to_board(row)

    def create_card(
        self, board_id: str, column_id: ColumnId, title: str, description: str
    ) -> Card:
        with self._session_factory() as session:
            if session.get(BoardRow, board_id) is None:
                raise BoardNotFoundError(board_id)

            existing = self._ordered_cards(session, board_id, column_id.value)
            card = CardRow(
                id=str(uuid.uuid4()),
                board_id=board_id,
                column_id=column_id.value,
                title=title,
                description=description,
                tag="New",
                position=len(existing),
            )
            session.add(card)
            session.commit()
            return self._to_card(card)

    def update_card(
        self,
        board_id: str,
        card_id: str,
        *,
        title: str | None,
        description: str | None,
        column_id: ColumnId | None,
        position: int | None,
    ) -> Card:
        with self._session_factory() as session:
            if session.get(BoardRow, board_id) is None:
                raise BoardNotFoundError(board_id)

            card = session.get(CardRow, card_id)
            if card is None or card.board_id != board_id:
                raise CardNotFoundError(card_id)

            if title is not None:
                card.title = title
            if description is not None:
                card.description = description

            source_column = card.column_id
            target_column = column_id.value if column_id is not None else source_column

            if target_column != source_column or position is not None:
                source_cards = self._ordered_cards(
                    session, board_id, source_column, exclude=card_id
                )
                target_cards = (
                    source_cards
                    if target_column == source_column
                    else self._ordered_cards(session, board_id, target_column, exclude=card_id)
                )

                insert_at = len(target_cards) if position is None else min(position, len(target_cards))
                target_cards.insert(insert_at, card)
                card.column_id = target_column

                self._renumber(target_cards)
                if target_column != source_column:
                    self._renumber(source_cards)

            session.commit()
            session.refresh(card)
            return self._to_card(card)

    def delete_card(self, board_id: str, card_id: str) -> None:
        with self._session_factory() as session:
            if session.get(BoardRow, board_id) is None:
                raise BoardNotFoundError(board_id)

            card = session.get(CardRow, card_id)
            if card is None or card.board_id != board_id:
                raise CardNotFoundError(card_id)

            column_id = card.column_id
            session.delete(card)
            session.flush()
            self._renumber(self._ordered_cards(session, board_id, column_id))
            session.commit()

    def _ordered_cards(
        self, session: Session, board_id: str, column_id: str, *, exclude: str | None = None
    ) -> list[CardRow]:
        rows = session.scalars(
            select(CardRow)
            .where(CardRow.board_id == board_id, CardRow.column_id == column_id)
            .order_by(CardRow.position)
        ).all()
        return [row for row in rows if row.id != exclude]

    @staticmethod
    def _renumber(cards: list[CardRow]) -> None:
        for index, card in enumerate(cards):
            card.position = index

    def _to_card(self, row: CardRow) -> Card:
        return Card(
            id=row.id,
            column_id=ColumnId(row.column_id),
            title=row.title,
            description=row.description,
            tag=row.tag,
            position=row.position,
        )

    def _to_board(self, row: BoardRow) -> Board:
        cards_by_column: dict[str, list[CardRow]] = {
            column_id.value: [] for column_id, _ in FIXED_COLUMNS
        }
        for card in row.cards:
            cards_by_column[card.column_id].append(card)
        for cards in cards_by_column.values():
            cards.sort(key=lambda c: c.position)

        return Board(
            id=row.id,
            name=row.name,
            columns=[
                Column(
                    id=column_id,
                    title=title,
                    cards=[self._to_card(c) for c in cards_by_column[column_id.value]],
                )
                for column_id, title in FIXED_COLUMNS
            ],
        )
