def _create_board(client) -> str:
    return client.post("/boards", json={}).json()["id"]


def test_create_card_appends_to_column(client):
    board_id = _create_board(client)

    response = client.post(
        f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Write tests"}
    )

    assert response.status_code == 201
    card = response.json()
    assert card["column_id"] == "todo"
    assert card["title"] == "Write tests"
    assert card["position"] == 0
    assert card["tag"] == "New"


def test_create_card_requires_non_empty_title(client):
    board_id = _create_board(client)

    response = client.post(f"/boards/{board_id}/cards", json={"column_id": "todo", "title": ""})

    assert response.status_code == 422


def test_create_card_404_for_unknown_board(client):
    response = client.post(
        "/boards/does-not-exist/cards", json={"column_id": "todo", "title": "x"}
    )

    assert response.status_code == 404


def test_move_card_between_columns(client):
    board_id = _create_board(client)
    card = client.post(f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Card"}).json()

    response = client.patch(f"/boards/{board_id}/cards/{card['id']}", json={"column_id": "done"})

    assert response.status_code == 200
    moved = response.json()
    assert moved["column_id"] == "done"
    assert moved["position"] == 0


def test_reorder_card_within_column(client):
    board_id = _create_board(client)
    first = client.post(f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "First"}).json()
    client.post(f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Second"})

    response = client.patch(f"/boards/{board_id}/cards/{first['id']}", json={"position": 1})

    assert response.status_code == 200
    board = client.get(f"/boards/{board_id}").json()
    todo_titles = [card["title"] for card in board["columns"][0]["cards"]]
    assert todo_titles == ["Second", "First"]


def test_edit_card_title_and_description(client):
    board_id = _create_board(client)
    card = client.post(f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Old"}).json()

    response = client.patch(
        f"/boards/{board_id}/cards/{card['id']}",
        json={"title": "New", "description": "Updated"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New"
    assert body["description"] == "Updated"


def test_delete_card(client):
    board_id = _create_board(client)
    card = client.post(f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "Gone"}).json()

    response = client.delete(f"/boards/{board_id}/cards/{card['id']}")

    assert response.status_code == 204
    board = client.get(f"/boards/{board_id}").json()
    assert board["columns"][0]["cards"] == []


def test_update_card_404_for_unknown_card(client):
    board_id = _create_board(client)

    response = client.patch(f"/boards/{board_id}/cards/does-not-exist", json={"title": "x"})

    assert response.status_code == 404


def test_update_card_422_for_unknown_column(client):
    board_id = _create_board(client)
    card = client.post(f"/boards/{board_id}/cards", json={"column_id": "todo", "title": "x"}).json()

    response = client.patch(
        f"/boards/{board_id}/cards/{card['id']}", json={"column_id": "not-a-column"}
    )

    assert response.status_code == 422
