import uuid
from dataclasses import dataclass

from .models import Board, Card, Column, ColumnId
from .repository import BoardNotFoundError, BoardRepository, CardNotFoundError

FIXED_COLUMNS: list[tuple[ColumnId, str]] = [
    (ColumnId.TODO, "To Do"),
    (ColumnId.IN_PROGRESS, "In Progress"),
    (ColumnId.DONE, "Done"),
]


@dataclass
class _CardRecord:
    id: str
    title: str
    description: str
    tag: str


@dataclass
class _BoardRecord:
    id: str
    name: str
    columns: dict[ColumnId, list[_CardRecord]]


class InMemoryBoardRepository(BoardRepository):
    """Mock store: everything lives in a process-local dict.

    A card's position is never stored directly — it's always the card's
    index within its column's list, recomputed on read. That keeps
    positions contiguous (0..n-1) without gap- or float-based reordering
    schemes.
    """

    def __init__(self) -> None:
        self._boards: dict[str, _BoardRecord] = {}

    def create_board(self, name: str) -> Board:
        board_id = str(uuid.uuid4())
        record = _BoardRecord(
            id=board_id,
            name=name,
            columns={column_id: [] for column_id, _ in FIXED_COLUMNS},
        )
        self._boards[board_id] = record
        return self._to_board(record)

    def get_board(self, board_id: str) -> Board:
        return self._to_board(self._require_board(board_id))

    def create_card(
        self, board_id: str, column_id: ColumnId, title: str, description: str
    ) -> Card:
        record = self._require_board(board_id)
        card = _CardRecord(id=str(uuid.uuid4()), title=title, description=description, tag="New")
        record.columns[column_id].append(card)
        return self._to_card(card, column_id, len(record.columns[column_id]) - 1)

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
        record = self._require_board(board_id)
        source_column_id, index, card = self._require_card(record, card_id)

        if title is not None:
            card.title = title
        if description is not None:
            card.description = description

        target_column_id = column_id if column_id is not None else source_column_id
        if target_column_id != source_column_id:
            record.columns[source_column_id].pop(index)
            target_list = record.columns[target_column_id]
            insert_at = len(target_list) if position is None else min(position, len(target_list))
            target_list.insert(insert_at, card)
        elif position is not None:
            target_list = record.columns[source_column_id]
            target_list.pop(index)
            insert_at = min(position, len(target_list))
            target_list.insert(insert_at, card)

        final_column_id, final_index, _ = self._require_card(record, card_id)
        return self._to_card(card, final_column_id, final_index)

    def delete_card(self, board_id: str, card_id: str) -> None:
        record = self._require_board(board_id)
        column_id, index, _ = self._require_card(record, card_id)
        record.columns[column_id].pop(index)

    def _require_board(self, board_id: str) -> _BoardRecord:
        record = self._boards.get(board_id)
        if record is None:
            raise BoardNotFoundError(board_id)
        return record

    def _require_card(
        self, record: _BoardRecord, card_id: str
    ) -> tuple[ColumnId, int, _CardRecord]:
        for column_id, cards in record.columns.items():
            for index, card in enumerate(cards):
                if card.id == card_id:
                    return column_id, index, card
        raise CardNotFoundError(card_id)

    def _to_card(self, card: _CardRecord, column_id: ColumnId, position: int) -> Card:
        return Card(
            id=card.id,
            column_id=column_id,
            title=card.title,
            description=card.description,
            tag=card.tag,
            position=position,
        )

    def _to_board(self, record: _BoardRecord) -> Board:
        return Board(
            id=record.id,
            name=record.name,
            columns=[
                Column(
                    id=column_id,
                    title=title,
                    cards=[
                        self._to_card(c, column_id, i)
                        for i, c in enumerate(record.columns[column_id])
                    ],
                )
                for column_id, title in FIXED_COLUMNS
            ],
        )
