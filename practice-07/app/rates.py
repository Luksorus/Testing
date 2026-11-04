import math

import httpx


class RateServiceError(Exception):
    """External rates could not be retrieved or validated."""


class RatesClient:
    def get_rate(self, currency: str) -> float:
        try:
            response = httpx.get("https://open.er-api.com/v6/latest/RUB", timeout=5)
            response.raise_for_status()
            rate = float(response.json()["rates"][currency])
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError("Rate must be positive and finite")
            return rate
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RateServiceError("Rates unavailable") from exc


def get_rates_client():
    return RatesClient()
