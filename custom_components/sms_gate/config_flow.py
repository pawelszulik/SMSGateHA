"""
Config flow integracji SMS Gate (Local).

- SMSGateConfigFlow: jeden krok (host, port, username, password), walidacja przez
  GET /health; unique_id = host:port.
- SMSGateOptionsFlow: jedna strona z dwoma polami tekstowymi – odbiorcy (linie
  "nazwa: numer") i szablony (linie "nazwa: treść").
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback

from .api import SMSGateAPI
from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_RECIPIENTS = "recipients"
CONF_TEMPLATES = "templates"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("recipients_text"): str,
        vol.Optional("templates_text"): str,
    }
)


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


async def _validate_connection(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Weryfikuje połączenie (health). Zwraca None przy sukcesie, komunikat błędu w przeciwnym razie."""
    base_url = _base_url(data[CONF_HOST], data[CONF_PORT])
    session = aiohttp.ClientSession()
    try:
        api = SMSGateAPI(
            base_url,
            session,
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        health = await api.async_get_health()
        if health is not None:
            return None
        return "cannot_connect"
    except Exception as e:
        _LOGGER.debug("Validation error: %s", e)
        if "401" in str(e) or "Unauthorized" in str(e):
            return "invalid_auth"
        return "cannot_connect"
    finally:
        await session.close()


class SMSGateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow tylko dla trybu Local (host, port, username, password)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SMSGateOptionsFlow:
        return SMSGateOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Krok: formularz połączenia."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            err = await _validate_connection(self.hass, user_input)
            if err is None:
                return self.async_create_entry(
                    title=f"SMS Gate ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            errors["base"] = err
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class SMSGateOptionsFlow(OptionsFlowWithReload):
    """Options flow: nazwani odbiorcy i szablony (jedna strona z dwoma polami)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._entry = config_entry

    @callback
    def _current(self) -> tuple[dict[str, str], dict[str, str]]:
        options = self._entry.options or {}
        recipients = options.get(CONF_RECIPIENTS) or {}
        templates = options.get(CONF_TEMPLATES) or {}
        return recipients, templates

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edycja odbiorców i szablonów. Format: linie 'nazwa: wartość'."""
        recipients, templates = self._current()
        if user_input is not None:
            new_recipients = {}
            for line in (user_input.get("recipients_text") or "").strip().splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                name, _, num = line.partition(":")
                name, num = name.strip(), num.strip()
                if name:
                    new_recipients[name] = num
            new_templates = {}
            for line in (user_input.get("templates_text") or "").strip().splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                name, _, content = line.partition(":")
                name, content = name.strip(), content.strip()
                if name:
                    new_templates[name] = content
            return self.async_create_entry(
                title="",
                data={
                    CONF_RECIPIENTS: new_recipients,
                    CONF_TEMPLATES: new_templates,
                },
            )
        recipients_default = "\n".join(f"{k}: {v}" for k, v in recipients.items())
        templates_default = "\n".join(f"{k}: {v}" for k, v in templates.items())
        suggested_values = {
            "recipients_text": recipients_default,
            "templates_text": templates_default,
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, suggested_values
            ),
        )


