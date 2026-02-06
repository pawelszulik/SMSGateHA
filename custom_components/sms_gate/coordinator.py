"""
Coordinator odświeżający status i listę wiadomości SMS Gate.

Co UPDATE_INTERVAL sekund pobiera health (available) oraz GET /messages (limit 20).
Wynik w coordinator.data: {"available": bool, "messages": list[dict]}.
Używane przez sensory: status, ostatnie wiadomości, liczba oczekujących.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import SMSGateAPI
from .const import MESSAGES_LIMIT_DEFAULT, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SMSGateDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Odświeża dane z bramki: health (available) oraz lista ostatnich wiadomości.
    coordinator.data = {"available": bool, "messages": list[dict]}
    """

    def __init__(self, hass: HomeAssistant, api: SMSGateAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="SMS Gate",
            update_interval=UPDATE_INTERVAL,
        )
        self._api = api
        self.data = {"available": False, "messages": []}

    async def _async_update_data(self) -> dict[str, Any]:
        """Pobiera health i listę wiadomości; przy błędzie health ustawia available=False."""
        available = False
        messages: list[dict[str, Any]] = []

        try:
            health = await self._api.async_get_health()
            available = health is not None
        except Exception as e:
            _LOGGER.debug("Health check failed: %s", e)

        try:
            messages = await self._api.async_get_messages(limit=MESSAGES_LIMIT_DEFAULT)
        except Exception as e:
            _LOGGER.debug("Get messages failed: %s", e)
            # Zachowaj poprzednią listę przy błędzie, jeśli mamy
            if self.data and isinstance(self.data.get("messages"), list):
                messages = self.data["messages"]

        return {"available": available, "messages": messages}
