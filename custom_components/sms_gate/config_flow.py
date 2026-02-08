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
        _LOGGER.info(
            "Opcje flow: otwarcie dla entry_id=%s",
            config_entry.entry_id,
        )
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
        _LOGGER.debug("Opcje flow init: entry_id=%s", config_entry.entry_id)

    def _current(self) -> tuple[dict[str, str], dict[str, str]]:
        # Opcje z rejestru – ten sam klucz co przy zapisie: "recipients", "templates"
        entries = self.hass.config_entries.async_entries(DOMAIN)
        entry = next(
            (e for e in entries if e.entry_id == self._entry.entry_id),
            self._entry,
        )
        raw_options = entry.options or {}
        options = dict(raw_options)
        # Opis options bez treści (klucze + długości wartości)
        options_desc = {
            k: len(v) if isinstance(v, (dict, list, str)) else type(v).__name__
            for k, v in options.items()
        }
        _LOGGER.debug(
            "Opcje odczyt entry_id=%s: options_keys=%s raw_options_desc=%s",
            entry.entry_id,
            list(options.keys()),
            options_desc,
        )
        # Zawsze słowniki (np. po JSON ze storage)
        recipients = options.get(CONF_RECIPIENTS)
        templates = options.get(CONF_TEMPLATES)
        if not isinstance(recipients, dict):
            recipients = {}
        if not isinstance(templates, dict):
            templates = {}
        _LOGGER.debug(
            "Opcje odczyt: recipients=%s templates=%s",
            list(recipients.keys()),
            list(templates.keys()),
        )
        return recipients, templates

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edycja odbiorców i szablonów. Format: linie 'nazwa: wartość'."""
        recipients, templates = self._current()
        if user_input is not None:
            _LOGGER.info(
                "Opcje: zapis entry_id=%s",
                self._entry.entry_id,
            )
            r_text = user_input.get("recipients_text") or ""
            t_text = user_input.get("templates_text") or ""
            _LOGGER.debug(
                "Opcje: user_input keys=%s recipients_text len=%s templates_text len=%s preview_r=%s preview_t=%s",
                list(user_input.keys()),
                len(r_text),
                len(t_text),
                (r_text[:80] + "…") if len(r_text) > 80 else r_text or "(puste)",
                (t_text[:80] + "…") if len(t_text) > 80 else t_text or "(puste)",
            )
            new_recipients = {}
            for line in (r_text).strip().splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                parts = line.split(":", 1)
                name = parts[0].strip()
                num = parts[1].strip() if len(parts) > 1 else ""
                if name:
                    new_recipients[name] = num
            new_templates = {}
            for line in (t_text).strip().splitlines():
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
            _LOGGER.debug(
                "Opcje: parsed new_recipients=%s new_templates=%s",
                list(new_recipients.keys()),
                list(new_templates.keys()),
            )
            _LOGGER.debug(
                "Opcje: final_recipients=%s final_templates=%s",
                list(final_recipients.keys()),
                list(final_templates.keys()),
            )
            new_options = {
                CONF_RECIPIENTS: final_recipients,
                CONF_TEMPLATES: final_templates,
            }
            # Aktualizuj wpis z rejestru (ten sam obiekt, z którego potem czytamy)
            entries = self.hass.config_entries.async_entries(DOMAIN)
            entry_to_update = next(
                (e for e in entries if e.entry_id == self._entry.entry_id),
                self._entry,
            )
            _LOGGER.debug(
                "Opcje: entry_to_update entry_id=%s",
                entry_to_update.entry_id,
            )
            result = self.hass.config_entries.async_update_entry(entry_to_update, options=new_options)
            _LOGGER.debug(
                "Opcje: async_update_entry wywołane result=%s",
                result,
            )
            return self.async_create_entry(title="", data=new_options)
        recipients_default = "\n".join(f"{k}: {v}" for k, v in recipients.items())
        templates_default = "\n".join(f"{k}: {v}" for k, v in templates.items())
        _LOGGER.info(
            "Opcje: pokazanie formularza entry_id=%s",
            self._entry.entry_id,
        )
        _LOGGER.debug(
            "Opcje: suggested recipients_text len=%s templates_text len=%s preview_r=%s preview_t=%s",
            len(recipients_default),
            len(templates_default),
            (recipients_default[:80] + "…") if len(recipients_default) > 80 else recipients_default or "(puste)",
            (templates_default[:80] + "…") if len(templates_default) > 80 else templates_default or "(puste)",
        )
        suggested = {
            "recipients_text": recipients_default,
            "templates_text": templates_default,
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, suggested),
        )


