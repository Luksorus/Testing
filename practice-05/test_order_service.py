from unittest.mock import create_autospec

import pytest

from order_service import Notifier, OrderService, Storage


@pytest.fixture
def storage():
    return create_autospec(Storage, instance=True, spec_set=True)


@pytest.fixture
def notifier():
    return create_autospec(Notifier, instance=True, spec_set=True)


@pytest.fixture
def service(storage, notifier):
    return OrderService(storage, notifier)


@pytest.mark.parametrize(
    "order_id, data",
    [(1, {"item": "Book", "price": 500}),
     (2, {"item": "Pen", "price": 50}),
     (3, {"item": "Laptop", "price": 80000})],
    ids=["book", "pen", "laptop"],
)
def test_place_order_saved_notifies_once(service, storage, notifier, order_id, data):
    storage.save_order.return_value = True

    result = service.place_order(order_id, data)

    assert result is True
    storage.save_order.assert_called_once_with(order_id, data)
    notifier.send.assert_called_once_with(order_id, data)


def test_place_order_failed_does_not_notify(service, storage, notifier):
    data = {"item": "Book", "price": 500}
    storage.save_order.return_value = False

    result = service.place_order(1, data)

    assert result is False
    storage.save_order.assert_called_once_with(1, data)
    notifier.send.assert_not_called()


def test_place_order_storage_exception_propagates_without_notification(service, storage, notifier):
    data = {"item": "Book", "price": 500}
    error = RuntimeError("Storage unavailable")
    storage.save_order.side_effect = error

    with pytest.raises(RuntimeError) as caught:
        service.place_order(1, data)

    assert caught.value is error
    storage.save_order.assert_called_once_with(1, data)
    notifier.send.assert_not_called()


def test_get_order_existing_returns_storage_data(service, storage, notifier):
    data = {"item": "Book", "price": 500}
    storage.get_order.return_value = data

    result = service.get_order(1)

    assert result is data
    storage.get_order.assert_called_once_with(1)
    storage.save_order.assert_not_called()
    notifier.send.assert_not_called()


def test_get_order_missing_returns_none(service, storage, notifier):
    storage.get_order.return_value = None

    result = service.get_order(404)

    assert result is None
    storage.get_order.assert_called_once_with(404)
    storage.save_order.assert_not_called()
    notifier.send.assert_not_called()


def test_get_order_storage_error_propagates(service, storage, notifier):
    storage.get_order.side_effect = RuntimeError("Read failed")

    with pytest.raises(RuntimeError, match="Read failed"):
        service.get_order(1)

    storage.get_order.assert_called_once_with(1)
    notifier.send.assert_not_called()
