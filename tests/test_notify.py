"""Testy rozwiązywania odbiorców i szablonów (notify)."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.sms_gate.notify import resolve_recipients_and_message


@pytest.mark.asyncio
async def test_resolve_recipients_by_name():
    """Odbiorcy podani nazwami są mapowani na numery z options."""
    entry = MagicMock()
    entry.options = {
        "recipients": {"alarm": "+48111222333", "dom": "+48444555666"},
        "templates": {},
    }
    hass = MagicMock()
    phone_numbers, text = await resolve_recipients_and_message(
        hass, entry, "Alarm!", ["alarm", "dom"], None, {}
    )
    assert phone_numbers == ["+48111222333", "+48444555666"]
    assert text == "Alarm!"


@pytest.mark.asyncio
async def test_resolve_recipients_raw_numbers():
    """Odbiorcy podani jako numery pozostają bez zmian."""
    entry = MagicMock()
    entry.options = {"recipients": {}, "templates": {}}
    hass = MagicMock()
    phone_numbers, text = await resolve_recipients_and_message(
        hass, entry, "Hi", ["+48123456789"], None, {}
    )
    assert phone_numbers == ["+48123456789"]
    assert text == "Hi"


@pytest.mark.asyncio
async def test_resolve_recipients_mixed():
    """Mieszanka nazw i numerów."""
    entry = MagicMock()
    entry.options = {
        "recipients": {"alarm": "+48111"},
        "templates": {},
    }
    hass = MagicMock()
    phone_numbers, _ = await resolve_recipients_and_message(
        hass, entry, "Msg", ["alarm", "+48999"], None, {}
    )
    assert phone_numbers == ["+48111", "+48999"]


@pytest.mark.asyncio
async def test_resolve_no_template_uses_message():
    """Bez szablonu treść = message."""
    entry = MagicMock()
    entry.options = {"recipients": {}, "templates": {}}
    hass = MagicMock()
    _, text = await resolve_recipients_and_message(
        hass, entry, "Plain text", [], None, {}
    )
    assert text == "Plain text"


@pytest.mark.asyncio
async def test_resolve_template_key_uses_template_string():
    """Z szablonem treść jest renderowana (mock Template)."""
    entry = MagicMock()
    entry.options = {
        "recipients": {},
        "templates": {"alarm": "Alarm: {{ message }}"},
    }
    hass = MagicMock()
    rendered = "Alarm: Fire!"
    tpl_instance = MagicMock()
    tpl_instance.async_render = MagicMock(return_value=rendered)
    with patch("custom_components.sms_gate.notify.Template", return_value=tpl_instance):
        _, text = await resolve_recipients_and_message(
            hass, entry, "Fire!", [], "alarm", {}
        )
    assert text == rendered
