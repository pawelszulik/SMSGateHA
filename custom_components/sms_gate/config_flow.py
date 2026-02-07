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
from .const import CONF_RECIPIENTS, CONF_TEMPLATES, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

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

    def _current(self) -> tuple[dict[str, str], dict[str, str]]:
        # Opcje z rejestru – ten sam klucz co przy zapisie: "recipients", "templates"
        entries = self.hass.config_entries.async_entries(DOMAIN)
        entry = next(
            (e for e in entries if e.entry_id == self._entry.entry_id),
            self._entry,
        )
        raw_options = entry.options or {}
        options = dict(raw_options)
        # Zawsze słowniki (np. po JSON ze storage)
        recipients = options.get(CONF_RECIPIENTS)
        templates = options.get(CONF_TEMPLATES)
        if not isinstance(recipients, dict):
            recipients = {}
        if not isinstance(templates, dict):
            templates = {}
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
                parts = line.split(":", 1)
                name = parts[0].strip()
                num = parts[1].strip() if len(parts) > 1 else ""
                if name:
                    new_recipients[name] = num
            new_templates = {}
            for line in (user_input.get("templates_text") or "").strip().splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                parts = line.split(":", 1)
                name = parts[0].strip()
                content = parts[1].strip() if len(parts) > 1 else ""
                if name:
                    new_templates[name] = content
            # Nie nadpisuj istniejących opcji pustymi słownikami
            final_recipients = new_recipients if new_recipients else recipients
            final_templates = new_templates if new_templates else templates
            new_options = {
                CONF_RECIPIENTS: final_recipients,
                CONF_TEMPLATES: final_templates,
            }
            # Wymuszenie zapisu – w tej wersji HA async_update_entry jest synchroniczne (zwraca bool)
            self.hass.config_entries.async_update_entry(self._entry, options=new_options)
            return self.async_create_entry(title="", data=new_options)
        recipients_default = "\n".join(f"{k}: {v}" for k, v in recipients.items())
        templates_default = "\n".join(f"{k}: {v}" for k, v in templates.items())
        _LOGGER.debug(
            "Opcje init entry_id=%s: recipients=%s templates=%s",
            self._entry.entry_id,
            list(recipients.keys()),
            list(templates.keys()),
        )
        suggested = {
            "recipients_text": recipients_default,
            "templates_text": templates_default,
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, suggested),
        )


