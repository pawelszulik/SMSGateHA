"""
Platforma notify do wysyłania SMS przez SMS Gate.

- resolve_recipients_and_message: mapuje nazwy odbiorców na numery (z options),
  renderuje szablon Jinja2 z options (placeholdery: message, entity_id, data).
- SMSGateNotifyEntity: encja notify; async_send_message przyjmuje data.recipients,
  data.template, data.data i wywołuje API send_sms.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template

from .api import SMSGateAPI
from .const import CONF_RECIPIENTS, CONF_TEMPLATES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def resolve_recipients_and_message(
    hass: HomeAssistant,
    entry: ConfigEntry,
    message: str,
    recipients: list[str],
    template_name: str | None,
    template_data: dict[str, Any],
) -> tuple[list[str], str]:
    """
    Rozwiązuje odbiorców (nazwy -> numery z options) i renderuje treść (szablon + message).
    Zwraca (lista numerów telefonów, finalna treść wiadomości).
    """
    options = entry.options or {}
    recipients_map: dict[str, str] = options.get(CONF_RECIPIENTS) or {}
    templates_map: dict[str, str] = options.get(CONF_TEMPLATES) or {}

    phone_numbers: list[str] = []
    for r in recipients:
        r = (r or "").strip()
        if not r:
            continue
        if r in recipients_map:
            phone_numbers.append(recipients_map[r].strip())
        else:
            phone_numbers.append(r)

    if template_name and template_name in templates_map:
        template_str = templates_map[template_name]
        ctx = {"message": message, **template_data}
        try:
            tpl = Template(template_str, hass)
            final_text = tpl.async_render(ctx)
        except Exception as e:
            _LOGGER.warning("Błąd renderowania szablonu %s: %s", template_name, e)
            final_text = message
    else:
        final_text = message

    return phone_numbers, final_text


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja platformy notify z config entry."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return
    api = data["api"]
    coordinator = data["coordinator"]
    entity = SMSGateNotifyEntity(entry, api)
    async_add_entities([entity])


class SMSGateNotifyEntity(NotifyEntity):
    """Encja notify wysyłająca SMS przez SMS Gate."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, api: SMSGateAPI) -> None:
        super().__init__()
        self._entry = entry
        self._api = api
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title or "SMS Gate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "SMS Gate",
            "manufacturer": "SMS Gate",
        }

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Wysyła SMS. Odbiorcy i szablon z data."""
        data = kwargs.get("data") or {}
        recipients = data.get("recipients", [])
        if isinstance(recipients, str):
            recipients = [recipients]
        template_name = data.get("template")
        template_data = data.get("data") or {}
        phone_numbers, final_text = await resolve_recipients_and_message(
            self.hass, self._entry, message, recipients, template_name, template_data
        )
        if not phone_numbers:
            _LOGGER.warning("Brak odbiorców do wysłania SMS")
            return
        success, result = await self._api.async_send_sms(
            phone_numbers, final_text, priority=100
        )
        if not success:
            _LOGGER.error("Wysłanie SMS nie powiodło się: %s", result)
            raise ValueError(result or "Send failed")
