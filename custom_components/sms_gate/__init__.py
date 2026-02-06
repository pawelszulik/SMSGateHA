"""
Integracja SMS Gate dla Home Assistant (Local Server).

- async_setup: rejestruje hass.data[DOMAIN].
- async_setup_entry: tworzy aiohttp session, API (Basic Auth), coordinator; ładuje
  platformy notify i sensor; rejestruje serwis sms_gate.send_sms (jedna rejestracja).
- _async_send_sms: wspólna logika dla serwisu i notify; wybór bramki po entity_id
  lub device_id, inaczej pierwszy wpis; resolve_recipients_and_message + api.send_sms.
- async_unload_entry: unload platform, zamknięcie sesji, usunięcie serwisu gdy brak wpisów.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .api import SMSGateAPI
from .const import DEFAULT_PORT, DOMAIN
from .coordinator import SMSGateDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_RECIPIENTS = "recipients"
CONF_TEMPLATES = "templates"

SERVICE_SEND_SMS = "send_sms"
SERVICE_SEND_SMS_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Required("recipients"): vol.Any(cv.string, [cv.string]),
        vol.Optional("template"): cv.string,
        vol.Optional("data"): dict,
        # Opcjonalnie: encja notify lub urządzenie – wybór bramki przy wielu konfiguracjach
        vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        vol.Optional("device_id"): cv.string,
    }
)


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Rejestracja config flow."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Konfiguracja integracji z entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    base_url = _base_url(host, port)

    session = aiohttp.ClientSession()
    api = SMSGateAPI(base_url, session, username, password)
    coordinator = SMSGateDataUpdateCoordinator(hass, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "session": session,
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "notify")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    async def async_send_sms_handler(call: ServiceCall) -> None:
        await _async_send_sms(hass, call)

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_SMS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_SMS,
            async_send_sms_handler,
            schema=SERVICE_SEND_SMS_SCHEMA,
        )

    return True


async def _async_send_sms(hass: HomeAssistant, call: ServiceCall) -> None:
    """Wspólna logika wysyłania SMS (serwis + notify). Wybór bramki: entity_id/device_id lub pierwszy wpis."""
    from .notify import resolve_recipients_and_message

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        _LOGGER.error("Brak skonfigurowanej integracji SMS Gate")
        return

    # Wybór wpisu: entity_id (encja notify) → device_id → pierwszy wpis
    entry_id = None
    entity_ids = call.data.get("entity_id")
    if entity_ids:
        entity_ids = [entity_ids] if isinstance(entity_ids, str) else entity_ids
        reg = hass.helpers.entity_registry.async_get()
        for eid in entity_ids:
            if not eid:
                continue
            ent = reg.async_get(eid)
            if ent and ent.config_entry_id and ent.config_entry_id in (e.entry_id for e in entries):
                entry_id = ent.config_entry_id
                break
    if not entry_id and call.data.get("device_id"):
        dev_reg = hass.helpers.device_registry.async_get()
        dev = dev_reg.async_get(call.data["device_id"])
        if dev and dev.config_entries:
            for eid in dev.config_entries:
                if any(c.domain == DOMAIN for c in entries if c.entry_id == eid):
                    entry_id = eid
                    break
    if not entry_id:
        entry_id = entries[0].entry_id
    entry = next((e for e in entries if e.entry_id == entry_id), entries[0])
    data = hass.data[DOMAIN].get(entry_id)
    if not data:
        _LOGGER.error("Brak konfiguracji SMS Gate dla entry %s", entry_id)
        return
    api: SMSGateAPI = data["api"]
    message = call.data.get("message", "")
    recipients = call.data.get("recipients")
    if isinstance(recipients, str):
        recipients = [recipients]
    template_name = call.data.get("template")
    template_data = call.data.get("data") or {}
    phone_numbers, final_text = await resolve_recipients_and_message(
        hass, entry, message, recipients or [], template_name, template_data
    )
    if not phone_numbers:
        _LOGGER.warning("Brak odbiorców do wysłania SMS")
        return
    success, result = await api.async_send_sms(phone_numbers, final_text, priority=100)
    if not success:
        _LOGGER.error("Wysłanie SMS nie powiodło się: %s", result)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odładowanie integracji."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "notify")
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, "sensor"
    ) and unload_ok

    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data:
        session: aiohttp.ClientSession = data.get("session")
        if session and not session.closed:
            await session.close()

    if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, SERVICE_SEND_SMS):
        hass.services.async_remove(DOMAIN, SERVICE_SEND_SMS)

    return unload_ok
