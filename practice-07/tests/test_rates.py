from unittest.mock import Mock

import httpx
import pytest

from app.rates import RateServiceError, RatesClient, get_rates_client


def test_rate_client_reads_rate_from_stubbed_http(monkeypatch):
    response = httpx.Response(200, json={"rates": {"USD": 0.01}}, request=httpx.Request("GET", "https://example.invalid"))
    get = Mock(return_value=response)
    monkeypatch.setattr(httpx, "get", get)
    assert RatesClient().get_rate("USD") == pytest.approx(0.01)
    get.assert_called_once_with("https://open.er-api.com/v6/latest/RUB", timeout=5)


@pytest.mark.parametrize("payload", [{}, {"rates": {"USD": -1}}, {"rates": {"USD": "bad"}},
                                    {"rates": {"USD": None}}, {"rates": {"USD": float("inf")}}],
                         ids=["missing", "negative", "not-numeric", "null", "infinite"])
def test_invalid_rate_payload_raises_service_error(monkeypatch, payload):
    response = Mock()
    response.json.return_value = payload
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    with pytest.raises(RateServiceError):
        RatesClient().get_rate("USD")


def test_rate_network_error_is_wrapped(monkeypatch):
    monkeypatch.setattr(httpx, "get", Mock(side_effect=httpx.ConnectError("No network")))
    with pytest.raises(RateServiceError):
        RatesClient().get_rate("USD")


def test_rates_dependency_constructs_client():
    assert isinstance(get_rates_client(), RatesClient)
