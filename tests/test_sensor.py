"""Testy sensorów SMS Gate."""

from unittest.mock import MagicMock

import pytest

from custom_components.sms_gate.sensor import (
    _message_attributes,
    SMSGateStatusSensor,
    SMSGateMessagesSensor,
)
from custom_components.sms_gate.coordinator import SMSGateDataUpdateCoordinator


def test_message_attributes():
    """Atrybuty wiadomości są uproszczone do id, state, recipients."""
    msg = {
        "id": "m1",
        "state": "Sent",
        "recipients": [{"phoneNumber": "+48111"}, {"phoneNumber": "+48222"}],
        "deviceId": "dev1",
    }
    attrs = _message_attributes(msg)
    assert attrs["id"] == "m1"
    assert attrs["state"] == "Sent"
    assert "48111" in attrs["recipients"] and "48222" in attrs["recipients"]
    assert attrs["device_id"] == "dev1"


def test_message_attributes_empty():
    """Pusta wiadomość nie rzuca błędu."""
    attrs = _message_attributes({})
    assert attrs["recipients"] == ""


def test_status_sensor_value():
    """Sensor statusu zwraca available/unavailable z coordinator.data."""
    coordinator = MagicMock(spec=SMSGateDataUpdateCoordinator)
    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.title = "SMS Gate"
    from custom_components.sms_gate.sensor import SENSOR_STATUS
    sensor = SMSGateStatusSensor(entry, coordinator, SENSOR_STATUS)
    sensor.coordinator = coordinator
    coordinator.data = {"available": True, "messages": []}
    assert sensor.native_value == "available"
    coordinator.data["available"] = False
    assert sensor.native_value == "unavailable"


def test_messages_sensor_value_and_attributes():
    """Sensor wiadomości zwraca liczbę i atrybut messages."""
    coordinator = MagicMock(spec=SMSGateDataUpdateCoordinator)
    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.title = "SMS Gate"
    from custom_components.sms_gate.sensor import SENSOR_MESSAGES
    sensor = SMSGateMessagesSensor(entry, coordinator, SENSOR_MESSAGES)
    sensor.coordinator = coordinator
    coordinator.data = {
        "available": True,
        "messages": [
            {"id": "m1", "state": "Sent", "recipients": [{"phoneNumber": "+48111"}], "deviceId": "d1"},
        ],
    }
    assert sensor.native_value == 1
    attrs = sensor.extra_state_attributes
    assert "messages" in attrs
    assert len(attrs["messages"]) == 1
    assert attrs["messages"][0]["id"] == "m1"
    assert attrs["messages"][0]["state"] == "Sent"
