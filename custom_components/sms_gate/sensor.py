"""
Sensory SMS Gate: status połączenia, ostatnie wiadomości, liczba oczekujących.

- Status: available/unavailable z coordinator.data["available"].
- Ostatnie wiadomości: liczba + atrybut messages (id, state, recipients) z coordinator.
- Liczba oczekujących: liczba wiadomości w stanie Pending (w kolejce).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SMSGateDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_STATUS = SensorEntityDescription(
    key="status",
    translation_key="status",
    name="Status",
)

SENSOR_MESSAGES = SensorEntityDescription(
    key="recent_messages",
    translation_key="recent_messages",
    name="Ostatnie wiadomości",
)

SENSOR_PENDING = SensorEntityDescription(
    key="pending_count",
    translation_key="pending_count",
    name="Liczba oczekujących",
)


def _message_attributes(msg: dict[str, Any]) -> dict[str, Any]:
    """Uproszczone atrybuty jednej wiadomości do wyświetlenia."""
    recipients = msg.get("recipients") or []
    phones = [
        r.get("phoneNumber", r) if isinstance(r, dict) else str(r)
        for r in recipients
    ]
    return {
        "id": msg.get("id"),
        "state": msg.get("state"),
        "recipients": ", ".join(phones) if phones else "",
        "device_id": msg.get("deviceId"),
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja sensorów z config entry."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return
    coordinator: SMSGateDataUpdateCoordinator = data["coordinator"]
    entities = [
        SMSGateStatusSensor(entry, coordinator, SENSOR_STATUS),
        SMSGateMessagesSensor(entry, coordinator, SENSOR_MESSAGES),
        SMSGatePendingSensor(entry, coordinator, SENSOR_PENDING),
    ]
    async_add_entities(entities)


class SMSGateBaseSensor(CoordinatorEntity[SMSGateDataUpdateCoordinator], SensorEntity):
    """Bazowa encja sensora SMS Gate."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: SMSGateDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "SMS Gate",
            "manufacturer": "SMS Gate",
        }


class SMSGateStatusSensor(SMSGateBaseSensor):
    """Sensor statusu połączenia (available/unavailable)."""

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        return "available" if data.get("available") else "unavailable"


class SMSGateMessagesSensor(SMSGateBaseSensor):
    """Sensor z listą ostatnich wiadomości (atrybut messages)."""

    @property
    def native_value(self) -> int:
        data = self.coordinator.data or {}
        messages = data.get("messages") or []
        return len(messages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        messages = data.get("messages") or []
        return {
            "messages": [_message_attributes(m) for m in messages],
        }


class SMSGatePendingSensor(SMSGateBaseSensor):
    """Sensor liczby wiadomości w kolejce (stan Pending)."""

    @property
    def native_value(self) -> int:
        data = self.coordinator.data or {}
        messages = data.get("messages") or []
        return sum(1 for m in messages if (m.get("state") or "").lower() == "pending")
