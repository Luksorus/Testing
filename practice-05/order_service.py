"""Order orchestration with dependencies supplied by the caller."""

from typing import Protocol


class Storage(Protocol):
    def save_order(self, order_id: int, data: dict) -> bool: ...

    def get_order(self, order_id: int) -> dict | None: ...


class Notifier(Protocol):
    def send(self, order_id: int, data: dict) -> None: ...


class OrderService:
    def __init__(self, storage: Storage, notifier: Notifier):
        self.storage = storage
        self.notifier = notifier

    def place_order(self, order_id: int, data: dict) -> bool:
        saved = self.storage.save_order(order_id, data)
        if saved is True:
            self.notifier.send(order_id, data)
            return True
        return False

    def get_order(self, order_id: int) -> dict | None:
        return self.storage.get_order(order_id)
