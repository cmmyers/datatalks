from enum import Enum

from pydantic import BaseModel, Field


class ColumnId(str, Enum):
    """Fixed set of columns — not user-creatable (see docs/SPEC.md non-goals)."""

    TODO = "todo"
    IN_PROGRESS = "in-progress"
    DONE = "done"


class Card(BaseModel):
    id: str
    column_id: ColumnId
    title: str
    description: str
    tag: str
    position: int


class Column(BaseModel):
    id: ColumnId
    title: str
    cards: list[Card]


class Board(BaseModel):
    id: str
    name: str
    columns: list[Column]


class CreateBoardRequest(BaseModel):
    name: str | None = None


class UpdateBoardRequest(BaseModel):
    name: str = Field(min_length=1)


class CreateCardRequest(BaseModel):
    column_id: ColumnId
    title: str = Field(min_length=1)
    description: str = ""


class UpdateCardRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    column_id: ColumnId | None = None
    position: int | None = Field(default=None, ge=0)
