"""Testy config flow SMS Gate."""

from unittest.mock import patch, AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sms_gate.config_flow import SMSGateConfigFlow, _validate_connection
from custom_components.sms_gate.const import DOMAIN


@pytest.mark.asyncio
async def test_validate_connection_success():
    """_validate_connection przy sukcesie health zwraca None."""
    hass = AsyncMock(spec=HomeAssistant)
    data = {
        "host": "192.168.1.10",
        "port": 8080,
        "username": "user",
        "password": "pass",
    }
    with patch("custom_components.sms_gate.config_flow.SMSGateAPI") as api_cls:
        api = AsyncMock()
        api.async_get_health = AsyncMock(return_value={"status": "pass"})
        api_cls.return_value = api
        with patch("custom_components.sms_gate.config_flow.aiohttp.ClientSession") as session_cls:
            session = AsyncMock()
            session.close = AsyncMock()
            session_cls.return_value = session
            session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
            session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            err = await _validate_connection(hass, data)
    assert err is None


@pytest.mark.asyncio
async def test_validate_connection_fail():
    """_validate_connection przy braku health zwraca cannot_connect."""
    hass = AsyncMock(spec=HomeAssistant)
    data = {"host": "192.168.1.10", "port": 8080, "username": "u", "password": "p"}
    with patch("custom_components.sms_gate.config_flow.SMSGateAPI") as api_cls:
        api = AsyncMock()
        api.async_get_health = AsyncMock(return_value=None)
        api_cls.return_value = api
        with patch("custom_components.sms_gate.config_flow.aiohttp.ClientSession") as session_cls:
            session = AsyncMock()
            session.close = AsyncMock()
            session_cls.return_value = session
            session_cls.return_value.__aenter__ = AsyncMock(return_value=session)
            session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            err = await _validate_connection(hass, data)
    assert err == "cannot_connect"


@pytest.mark.asyncio
async def test_flow_user_form_shown():
    """Pierwszy krok pokazuje formularz."""
    hass = MagicMock()
    flow = SMSGateConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert "data_schema" in result
