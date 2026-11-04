from itertools import count

import pytest
from fastapi.testclient import TestClient

from warmup import app_fixed, app_v0


@pytest.fixture(autouse=True)
def clean_items(monkeypatch):
    app_v0.ITEMS.clear()
    app_fixed.ITEMS.clear()
    monkeypatch.setattr(app_fixed, "NEXT_ID", count(1))
    yield
    app_v0.ITEMS.clear()
    app_fixed.ITEMS.clear()


def check_no_overwrite(app, store):
    with TestClient(app) as client:
        first = client.post("/items", json={"name": "First", "price": 10})
        second = client.post("/items", json={"name": "Second", "price": 20})
        assert first.status_code == second.status_code == 201
        first_id, second_id = first.json()["id"], second.json()["id"]
        assert client.delete(f"/items/{first_id}").status_code == 204
        third = client.post("/items", json={"name": "Third", "price": 30})
        assert third.status_code == 201
        assert third.json()["id"] != second_id
        assert store[second_id] == {"name": "Second", "price": 20}


@pytest.mark.xfail(strict=True, reason="len(ITEMS) + 1 overwrites surviving id=2")
def test_original_id_collision_is_detected():
    check_no_overwrite(app_v0.app, app_v0.ITEMS)


def test_fixed_ids_do_not_overwrite_existing_item():
    check_no_overwrite(app_fixed.app, app_fixed.ITEMS)
