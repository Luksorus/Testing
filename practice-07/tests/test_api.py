import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.rates import RateServiceError


def test_health_returns_ok_without_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_success_returns_bearer_token(client):
    response = client.post("/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type"}
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert client.get("/courses", headers={"Authorization": "Bearer " + body["access_token"]}).status_code == 200


@pytest.mark.parametrize("username,password", [("admin", "wrong"), ("unknown", "admin-pass")],
                         ids=["wrong-password", "unknown-user"])
def test_login_bad_credentials_returns_401(client, username, password):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.parametrize("body", [{}, {"username": "admin"}, {"username": "", "password": "x"}],
                         ids=["empty", "missing-password", "empty-username"])
def test_login_invalid_body_returns_422(client, body):
    assert client.post("/auth/login", json=body).status_code == 422


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer broken"},
                                    {"Authorization": "Basic broken"}],
                         ids=["missing", "invalid-token", "wrong-scheme"])
def test_protected_request_invalid_auth_returns_401(client, headers):
    response = client.get("/courses", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_returns_401(client, api, admin_headers):
    token = admin_headers["Authorization"].split()[1]
    api.state.tokens[token] = ("admin", time.monotonic() - 1)
    assert client.get("/courses", headers=admin_headers).status_code == 401


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"],
                         ids=["create", "replace", "patch", "delete"])
def test_viewer_write_forbidden(client, viewer_headers, admin_headers, make_item, method):
    course = make_item()
    path = "/courses" if method == "POST" else f"/courses/{course['id']}"
    kwargs = {} if method == "DELETE" else {"json": {"name": "Unauthorized", "price": 20, "slots": 1}}
    response = client.request(method, path, headers=viewer_headers, **kwargs)
    assert response.status_code == 403
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == course
    assert len(client.get("/courses", headers=admin_headers).json()) == 1


def test_viewer_cannot_change_slots(client, viewer_headers, admin_headers, make_item):
    course = make_item()
    response = client.post(f"/courses/{course['id']}/slots", json={"delta": 1}, headers=viewer_headers)
    assert response.status_code == 403
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == course


def test_create_course_returns_201_and_exact_fields(client, admin_headers):
    response = client.post("/courses", json={"name": "Python", "price": 500, "slots": 20}, headers=admin_headers)
    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "Python", "price": 500.0, "slots": 20}


def test_create_course_defaults_slots_to_zero(client, admin_headers):
    response = client.post("/courses", json={"name": "Python", "price": 50}, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["slots"] == 0


def test_get_course_returns_saved_data(client, viewer_headers, make_item):
    course = make_item()
    response = client.get(f"/courses/{course['id']}", headers=viewer_headers)
    assert response.status_code == 200
    assert response.json() == course


def test_list_courses_is_sorted_by_id(client, viewer_headers, make_item):
    first = make_item(name="Zebra")
    second = make_item(name="Alpha")
    response = client.get("/courses", headers=viewer_headers)
    assert response.status_code == 200
    assert response.json() == [first, second]


def test_each_test_starts_with_empty_database(client, admin_headers):
    response = client.get("/courses", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_put_replaces_all_fields(client, admin_headers, make_item):
    course = make_item()
    body = {"name": "New", "price": 250, "slots": 30}
    response = client.put(f"/courses/{course['id']}", json=body, headers=admin_headers)
    assert response.status_code == 200
    expected = {"id": course["id"], **body}
    assert response.json() == expected
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == expected


def test_put_requires_all_fields_and_leaves_data_unchanged(client, admin_headers, make_item):
    course = make_item()
    response = client.put(f"/courses/{course['id']}", json={"name": "New", "price": 2}, headers=admin_headers)
    assert response.status_code == 422
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == course


def test_patch_changes_only_provided_field(client, admin_headers, make_item):
    course = make_item()
    response = client.patch(f"/courses/{course['id']}", json={"price": 75}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {**course, "price": 75.0}
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == response.json()


def test_delete_returns_empty_204_and_followup_get_404(client, admin_headers, make_item):
    course = make_item()
    response = client.delete(f"/courses/{course['id']}", headers=admin_headers)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).status_code == 404


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"],
                         ids=["read", "replace", "patch", "delete"])
def test_missing_course_returns_404(client, admin_headers, method):
    kwargs = {} if method in ["GET", "DELETE"] else {"json": {"name": "New", "price": 20, "slots": 1}}
    assert client.request(method, "/courses/999", headers=admin_headers, **kwargs).status_code == 404


@pytest.mark.parametrize("changes", [
    {"name": ""}, {"name": "   "}, {"name": "a" * 101}, {"price": 0},
    {"price": -1}, {"price": "wrong"}, {"slots": -1}, {"slots": 31},
    {"slots": 1.5}, {"slots": True}, {"extra": "not allowed"},
], ids=["empty-name", "blank-name", "long-name", "zero-price", "negative-price",
        "wrong-price-type", "negative-slots", "above-limit", "float-slots", "bool-slots", "extra-field"])
def test_invalid_post_returns_422_without_creating_data(client, admin_headers, changes):
    body = {"name": "Python", "price": 100, "slots": 10, **changes}
    response = client.post("/courses", json=body, headers=admin_headers)
    assert response.status_code == 422
    assert client.get("/courses", headers=admin_headers).json() == []


@pytest.mark.parametrize("body", [{}, {"name": None}, {"slots": None}, {"slots": 31}],
                         ids=["empty", "null-name", "null-slots", "above-limit"])
def test_invalid_patch_returns_422_without_modifying_data(client, admin_headers, make_item, body):
    course = make_item()
    response = client.patch(f"/courses/{course['id']}", json=body, headers=admin_headers)
    assert response.status_code == 422
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == course


def test_duplicate_name_returns_409_and_keeps_original(client, admin_headers, make_item):
    course = make_item(name="Unique")
    response = client.post("/courses", json={"name": "Unique", "price": 200}, headers=admin_headers)
    assert response.status_code == 409
    assert client.get("/courses", headers=admin_headers).json() == [course]


@pytest.mark.parametrize("method", ["PUT", "PATCH"], ids=["replace", "partial-update"])
def test_rename_conflict_rolls_back(client, admin_headers, make_item, method):
    first = make_item(name="First")
    second = make_item(name="Second")
    response = client.request(method, f"/courses/{second['id']}", json={"name": "First", "price": 20, "slots": 2}, headers=admin_headers)
    assert response.status_code == 409
    assert client.get("/courses", headers=admin_headers).json() == [first, second]


@pytest.mark.parametrize("start,delta,expected", [(10, 5, 15), (10, -5, 5), (1, -1, 0), (29, 1, 30)],
                         ids=["return-slots", "enroll", "lower-bound", "upper-bound"])
def test_slots_delta_updates_value(client, admin_headers, make_item, start, delta, expected):
    course = make_item(slots=start)
    response = client.post(f"/courses/{course['id']}/slots", json={"delta": delta}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {**course, "slots": expected}
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json()["slots"] == expected


@pytest.mark.parametrize("start,delta", [(0, -1), (30, 1)], ids=["below-zero", "above-thirty"])
def test_slots_outside_bounds_returns_409_and_keeps_value(client, admin_headers, make_item, start, delta):
    course = make_item(slots=start)
    response = client.post(f"/courses/{course['id']}/slots", json={"delta": delta}, headers=admin_headers)
    assert response.status_code == 409
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == course


@pytest.mark.parametrize("delta", [0, 1.5, "1", True], ids=["zero", "fraction", "string", "boolean"])
def test_invalid_delta_returns_422_without_modifying_data(client, admin_headers, make_item, delta):
    course = make_item()
    response = client.post(f"/courses/{course['id']}/slots", json={"delta": delta}, headers=admin_headers)
    assert response.status_code == 422
    assert client.get(f"/courses/{course['id']}", headers=admin_headers).json() == course


def test_slots_for_missing_course_returns_404(client, admin_headers):
    assert client.post("/courses/999/slots", json={"delta": 1}, headers=admin_headers).status_code == 404


def test_q_filter_is_case_insensitive_including_cyrillic(client, viewer_headers, make_item):
    make_item(name="Python")
    expected = make_item(name="Основы Тестирования")
    response = client.get("/courses", params={"q": "тЕсТ"}, headers=viewer_headers)
    assert response.status_code == 200
    assert response.json() == [expected]


def test_q_filter_treats_wildcards_literally(client, viewer_headers, make_item):
    expected = make_item(name="100% Python")
    make_item(name="Other")
    assert client.get("/courses", params={"q": "%"}, headers=viewer_headers).json() == [expected]


def test_price_filters_include_boundaries(client, viewer_headers, make_item):
    make_item(price=49)
    first = make_item(price=50)
    second = make_item(price=100)
    make_item(price=101)
    response = client.get("/courses", params={"min_price": 50, "max_price": 100}, headers=viewer_headers)
    assert response.status_code == 200
    assert response.json() == [first, second]


def test_limit_offset_paginate_sorted_result(client, viewer_headers, make_item):
    rows = [make_item() for _ in range(4)]
    response = client.get("/courses", params={"limit": 2, "offset": 1}, headers=viewer_headers)
    assert response.status_code == 200
    assert response.json() == rows[1:3]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1},
                                   {"min_price": 20, "max_price": 10}, {"min_price": -1}],
                         ids=["zero-limit", "excess-limit", "negative-offset", "reversed-prices", "negative-price"])
def test_invalid_list_parameters_return_422(client, viewer_headers, params):
    assert client.get("/courses", params=params, headers=viewer_headers).status_code == 422


@pytest.mark.parametrize("currency,rate,expected", [("USD", 0.01, 5.0), ("EUR", 0.02, 10.0)],
                         ids=["dollars", "euros"])
def test_currency_price_uses_stub_rate(client, viewer_headers, make_item, rates, currency, rate, expected):
    course = make_item(price=500)
    rates.get_rate.return_value = rate
    response = client.get(f"/courses/{course['id']}/price", params={"currency": currency}, headers=viewer_headers)
    assert response.status_code == 200
    assert set(response.json()) == {"currency", "price"}
    assert response.json()["currency"] == currency
    assert response.json()["price"] == pytest.approx(expected)
    rates.get_rate.assert_called_once_with(currency)


def test_rate_service_failure_returns_502(client, viewer_headers, make_item, rates):
    course = make_item()
    rates.get_rate.side_effect = RateServiceError("Unavailable")
    response = client.get(f"/courses/{course['id']}/price", params={"currency": "USD"}, headers=viewer_headers)
    assert response.status_code == 502
    rates.get_rate.assert_called_once_with("USD")


def test_unknown_currency_returns_422_without_rate_call(client, viewer_headers, make_item, rates):
    course = make_item()
    response = client.get(f"/courses/{course['id']}/price", params={"currency": "GBP"}, headers=viewer_headers)
    assert response.status_code == 422
    rates.get_rate.assert_not_called()


def test_price_for_missing_course_returns_404_without_rate_call(client, viewer_headers, rates):
    assert client.get("/courses/999/price", params={"currency": "USD"}, headers=viewer_headers).status_code == 404
    rates.get_rate.assert_not_called()


def test_ids_remain_unique_after_deleting_middle_course(client, admin_headers, make_item):
    first, second = make_item(), make_item()
    assert client.delete(f"/courses/{first['id']}", headers=admin_headers).status_code == 204
    third = make_item()
    assert third["id"] > second["id"]
    assert client.get(f"/courses/{second['id']}", headers=admin_headers).json() == second


def test_default_database_dependency_works_without_override():
    app = create_app()
    try:
        with TestClient(app) as client:
            response = client.post("/auth/login", json={"username": "admin", "password": "admin-pass"})
            headers = {"Authorization": "Bearer " + response.json()["access_token"]}
            assert client.get("/courses", headers=headers).json() == []
    finally:
        app.state.session_factory.kw["bind"].dispose()
