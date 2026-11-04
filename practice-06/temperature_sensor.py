"""Temperature changes are delivered to independent callback subscribers."""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class TemperatureSensor:
    def __init__(self, initial_temperature: int | float = 0.0):
        self._temperature = initial_temperature
        self._subscribers: list[Callable[[int | float], None]] = []

    @property
    def temperature(self) -> int | float:
        return self._temperature

    def subscribe(self, callback: Callable[[int | float], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[int | float], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def set_temperature(self, value: int | float) -> None:
        if value == self._temperature:
            return
        self._temperature = value
        for callback in tuple(self._subscribers):
            try:
                callback(value)
            except Exception:
                logger.exception("Temperature subscriber failed")
