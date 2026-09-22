import pytest
from starlette.websockets import WebSocketDisconnect


def _create_board(client) -> str:
    return client.post("/boards", json={}).json()["id"]


def test_websocket_closes_for_unknown_board(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/boards/does-not-exist/ws"):
            pass
    assert exc_info.value.code == 4004


def test_websocket_receives_card_created_event(client):
    board_id = _create_board(client)

    with client.websocket_connect(f"/boards/{board_id}/ws") as ws:
        response = client.post(
            f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Write tests"}
        )
        assert response.status_code == 201

        event = ws.receive_json()
        assert event["type"] == "board_updated"
        titles = [card["title"] for card in event["board"]["columns"][0]["cards"]]
        assert titles == ["Write tests"]


def test_websocket_receives_card_moved_event(client):
    board_id = _create_board(client)
    card = client.post(
        f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Card"}
    ).json()

    with client.websocket_connect(f"/boards/{board_id}/ws") as ws:
        client.patch(f"/boards/{board_id}/cards/{card['id']}", json={"column_id": "done"})

        event = ws.receive_json()
        done_column = next(c for c in event["board"]["columns"] if c["id"] == "done")
        assert [card["id"] for card in done_column["cards"]] == [card["id"]]


def test_websocket_receives_card_deleted_event(client):
    board_id = _create_board(client)
    card = client.post(
        f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Gone"}
    ).json()

    with client.websocket_connect(f"/boards/{board_id}/ws") as ws:
        client.delete(f"/boards/{board_id}/cards/{card['id']}")

        event = ws.receive_json()
        assert event["board"]["columns"][0]["cards"] == []


def test_websocket_receives_board_renamed_event(client):
    board_id = _create_board(client)

    with client.websocket_connect(f"/boards/{board_id}/ws") as ws:
        client.patch(f"/boards/{board_id}", json={"name": "New name"})

        event = ws.receive_json()
        assert event["board"]["name"] == "New name"


def test_all_connected_sessions_receive_the_same_broadcast(client):
    """The two-session scenario from docs/SPEC.md: a change made by one
    client is seen by every other client connected to the same board."""
    board_id = _create_board(client)

    with client.websocket_connect(f"/boards/{board_id}/ws") as interviewer_ws:
        with client.websocket_connect(f"/boards/{board_id}/ws") as candidate_ws:
            client.post(
                f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Shared card"}
            )

            interviewer_event = interviewer_ws.receive_json()
            candidate_event = candidate_ws.receive_json()

    assert interviewer_event == candidate_event
