from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

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
from ..ws_manager import manager

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
async def update_board(
    board_id: str,
    payload: UpdateBoardRequest,
    repository: BoardRepository = Depends(get_repository),
) -> Board:
    try:
        board = repository.update_board(board_id, name=payload.name)
    except BoardNotFoundError:
        raise HTTPException(status_code=404, detail=f"No board exists with id '{board_id}'")
    await manager.broadcast(board_id, board)
    return board


@router.post("/{board_id}/cards", response_model=Card, status_code=201)
async def create_card(
    board_id: str,
    payload: CreateCardRequest,
    repository: BoardRepository = Depends(get_repository),
) -> Card:
    try:
        card = repository.create_card(
            board_id, payload.column_id, payload.title, payload.description
        )
    except BoardNotFoundError:
        raise HTTPException(status_code=404, detail=f"No board exists with id '{board_id}'")
    await manager.broadcast(board_id, repository.get_board(board_id))
    return card


@router.patch("/{board_id}/cards/{card_id}", response_model=Card)
async def update_card(
    board_id: str,
    card_id: str,
    payload: UpdateCardRequest,
    repository: BoardRepository = Depends(get_repository),
) -> Card:
    try:
        card = repository.update_card(
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
    await manager.broadcast(board_id, repository.get_board(board_id))
    return card


@router.delete("/{board_id}/cards/{card_id}", status_code=204)
async def delete_card(
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
    await manager.broadcast(board_id, repository.get_board(board_id))


@router.websocket("/{board_id}/ws")
async def board_updates(
    board_id: str,
    websocket: WebSocket,
    repository: BoardRepository = Depends(get_repository),
) -> None:
    """Live-update subscription for a board room (see docs/SPEC.md, "Share a
    board so others join the same session"). No client -> server messages
    are expected; the socket exists purely to push board_updated events.

    Per docs/SPEC.md's non-goals, there's no reconnect logic here or on the
    client — a dropped connection is resolved by reloading the page.
    """
    try:
        repository.get_board(board_id)
    except BoardNotFoundError:
        await websocket.close(code=4004, reason=f"No board exists with id '{board_id}'")
        return

    await manager.connect(board_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(board_id, websocket)
