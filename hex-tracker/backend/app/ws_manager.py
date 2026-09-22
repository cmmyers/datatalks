from collections import defaultdict
from typing import Iterable

from fastapi import WebSocket

from .models import Board


class BoardConnectionManager:
    """Tracks open WebSocket connections per board and broadcasts board
    state to all of them.

    In-process only (a plain dict, not backed by Redis/pubsub) — fine for
    the single-instance deployment this app targets. A multi-instance
    deployment would need a shared broadcast layer instead.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, board_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[board_id].add(websocket)

    def disconnect(self, board_id: str, websocket: WebSocket) -> None:
        self._connections[board_id].discard(websocket)
        if not self._connections[board_id]:
            del self._connections[board_id]

    async def broadcast(self, board_id: str, board: Board) -> None:
        message = {"type": "board_updated", "board": board.model_dump(mode="json")}
        for websocket in self._connections_snapshot(board_id):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(board_id, websocket)

    def _connections_snapshot(self, board_id: str) -> Iterable[WebSocket]:
        return list(self._connections.get(board_id, ()))


manager = BoardConnectionManager()
