from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_repository
from ..models import (
    Board,
    Card,
    CreateBoardRequest,
    CreateCardRequest,
    UpdateBoardRequest,
    UpdateCardRequest,
)
from ..repository import BoardNotFoundError, BoardRepository, CardNotFoundError

router = APIRouter(prefix="/boards", tags=["boards"])


@router.post("", response_model=Board, status_code=201)
def create_board(
    payload: CreateBoardRequest, repository: BoardRepository = Depends(get_repository)
) -> Board:
    return repository.create_board(payload.name or "Untitled board")


@router.get("/{board_id}", response_model=Board)
def get_board(board_id: str, repository: BoardRepository = Depends(get_repository)) -> Board:
    try:
        return repository.get_board(board_id)
    except BoardNotFoundError:
        raise HTTPException(status_code=404, detail=f"No board exists with id '{board_id}'")


@router.patch("/{board_id}", response_model=Board)
def update_board(
    board_id: str,
    payload: UpdateBoardRequest,
    repository: BoardRepository = Depends(get_repository),
) -> Board:
    try:
        return repository.update_board(board_id, name=payload.name)
    except BoardNotFoundError:
        raise HTTPException(status_code=404, detail=f"No board exists with id '{board_id}'")


@router.post("/{board_id}/cards", response_model=Card, status_code=201)
def create_card(
    board_id: str,
    payload: CreateCardRequest,
    repository: BoardRepository = Depends(get_repository),
) -> Card:
    try:
        return repository.create_card(
            board_id, payload.column_id, payload.title, payload.description
        )
    except BoardNotFoundError:
        raise HTTPException(status_code=404, detail=f"No board exists with id '{board_id}'")


@router.patch("/{board_id}/cards/{card_id}", response_model=Card)
def update_card(
    board_id: str,
    card_id: str,
    payload: UpdateCardRequest,
    repository: BoardRepository = Depends(get_repository),
) -> Card:
    try:
        return repository.update_card(
            board_id,
            card_id,
            title=payload.title,
            description=payload.description,
            column_id=payload.column_id,
            position=payload.position,
        )
    except BoardNotFoundError:
        raise HTTPException(status_code=404, detail=f"No board exists with id '{board_id}'")
    except CardNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"No card exists with id '{card_id}' on board '{board_id}'"
        )


@router.delete("/{board_id}/cards/{card_id}", status_code=204)
def delete_card(
    board_id: str, card_id: str, repository: BoardRepository = Depends(get_repository)
) -> None:
    try:
        repository.delete_card(board_id, card_id)
    except BoardNotFoundError:
        raise HTTPException(status_code=404, detail=f"No board exists with id '{board_id}'")
    except CardNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"No card exists with id '{card_id}' on board '{board_id}'"
        )
