def test_create_board_has_default_empty_columns(client):
    response = client.post("/boards", json={"name": "My Board"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "My Board"
    assert [column["id"] for column in body["columns"]] == ["todo", "in-progress", "done"]
    assert all(column["cards"] == [] for column in body["columns"])


def test_create_board_defaults_name_when_omitted(client):
    response = client.post("/boards", json={})

    assert response.status_code == 201
    assert response.json()["name"] == "Untitled board"


def test_get_board_returns_current_state(client):
    board_id = client.post("/boards", json={}).json()["id"]

    response = client.get(f"/boards/{board_id}")

    assert response.status_code == 200
    assert response.json()["id"] == board_id


def test_get_board_404_for_unknown_id(client):
    response = client.get("/boards/does-not-exist")

    assert response.status_code == 404
    assert "detail" in response.json()
