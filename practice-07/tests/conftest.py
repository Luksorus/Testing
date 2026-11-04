from unittest.mock import create_autospec

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import create_app, get_db
from app.rates import RatesClient, get_rates_client


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("External HTTP is forbidden in tests")
    monkeypatch.setattr(httpx, "get", blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def rates():
    mock = create_autospec(RatesClient, instance=True, spec_set=True)
    mock.get_rate.return_value = 0.01
    return mock


@pytest.fixture
def api(db_session, rates):
    app = create_app(sessionmaker(bind=db_session.bind, expire_on_commit=False))
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_rates_client] = lambda: rates
    yield app
    app.dependency_overrides.clear()
    app.state.tokens.clear()


@pytest.fixture
def client(api):
    with TestClient(api) as test_client:
        yield test_client


def login_headers(client, username):
    response = client.post("/auth/login", json={"username": username, "password": username + "-pass"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def admin_headers(client):
    return login_headers(client, "admin")


@pytest.fixture
def viewer_headers(client):
    return login_headers(client, "viewer")


@pytest.fixture
def make_item(client, admin_headers):
    # Name retained from the assignment; the created resource is a course.
    created = 0
    def create(**overrides):
        nonlocal created
        created += 1
        body = {"name": f"Course {created}", "price": 100.0, "slots": 10}
        body.update(overrides)
        response = client.post("/courses", json=body, headers=admin_headers)
        assert response.status_code == 201, response.text
        return response.json()
    return create
