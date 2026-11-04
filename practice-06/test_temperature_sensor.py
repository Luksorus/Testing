import logging
from unittest.mock import Mock, call

import pytest

from temperature_sensor import TemperatureSensor


@pytest.fixture
def sensor():
    return TemperatureSensor()


@pytest.fixture
def ready_sensor(sensor):
    sensor.set_temperature(20)
    return sensor


def test_initial_temperature_is_zero(sensor):
    assert sensor.temperature == 0.0


def test_changed_temperature_notifies_once(ready_sensor):
    callback = Mock()
    ready_sensor.subscribe(callback)

    ready_sensor.set_temperature(21)

    assert ready_sensor.temperature == 21
    callback.assert_called_once_with(21)


def test_same_temperature_does_not_notify(ready_sensor):
    callback = Mock()
    ready_sensor.subscribe(callback)

    ready_sensor.set_temperature(20)

    assert ready_sensor.temperature == 20
    callback.assert_not_called()


def test_multiple_subscribers_receive_same_value(ready_sensor):
    callbacks = [Mock(), Mock(), Mock()]
    for callback in callbacks:
        ready_sensor.subscribe(callback)

    ready_sensor.set_temperature(25)

    for callback in callbacks:
        callback.assert_called_once_with(25)


def test_unsubscribed_callback_is_skipped_and_others_notified(ready_sensor):
    removed, remaining = Mock(), Mock()
    ready_sensor.subscribe(removed)
    ready_sensor.subscribe(remaining)
    ready_sensor.unsubscribe(removed)

    ready_sensor.set_temperature(22)

    removed.assert_not_called()
    remaining.assert_called_once_with(22)


@pytest.mark.parametrize("value", [-15, 0, 20.5, 1000],
                         ids=["negative", "zero", "fraction", "large"])
def test_temperature_changes_are_delivered(ready_sensor, value):
    callback = Mock()
    ready_sensor.subscribe(callback)

    ready_sensor.set_temperature(value)

    assert ready_sensor.temperature == value
    callback.assert_called_once_with(value)


def test_unsubscribe_unknown_callback_is_safe(ready_sensor):
    remaining = Mock()
    ready_sensor.subscribe(remaining)

    ready_sensor.unsubscribe(Mock())
    ready_sensor.set_temperature(23)

    remaining.assert_called_once_with(23)


def test_repeated_unsubscribe_is_safe(ready_sensor):
    callback = Mock()
    ready_sensor.subscribe(callback)
    ready_sensor.unsubscribe(callback)
    ready_sensor.unsubscribe(callback)

    ready_sensor.set_temperature(23)

    callback.assert_not_called()


def test_failing_subscriber_does_not_stop_others(ready_sensor, caplog):
    first, last = Mock(), Mock()
    failing = Mock(side_effect=RuntimeError("Callback error"))
    for callback in [first, failing, last]:
        ready_sensor.subscribe(callback)

    with caplog.at_level(logging.ERROR, logger="temperature_sensor"):
        ready_sensor.set_temperature(30)

    for callback in [first, failing, last]:
        callback.assert_called_once_with(30)
    assert ready_sensor.temperature == 30
    assert "Temperature subscriber failed" in caplog.text
    assert "Callback error" in caplog.text


def test_duplicate_subscription_does_not_duplicate_event(ready_sensor):
    callback = Mock()
    ready_sensor.subscribe(callback)
    ready_sensor.subscribe(callback)

    ready_sensor.set_temperature(24)

    callback.assert_called_once_with(24)


def test_only_real_changes_are_delivered_in_order(ready_sensor):
    callback = Mock()
    ready_sensor.subscribe(callback)

    for value in [21, 21, 22]:
        ready_sensor.set_temperature(value)

    assert callback.call_args_list == [call(21), call(22)]


def test_unsubscription_during_event_applies_to_next_event(ready_sensor):
    remaining = Mock()
    remover = Mock(side_effect=lambda value: ready_sensor.unsubscribe(remaining))
    ready_sensor.subscribe(remover)
    ready_sensor.subscribe(remaining)

    ready_sensor.set_temperature(21)
    ready_sensor.set_temperature(22)

    assert remover.call_args_list == [call(21), call(22)]
    remaining.assert_called_once_with(21)
