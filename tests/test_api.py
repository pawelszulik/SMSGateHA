"""Testy klienta API SMS Gate."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sms_gate.api import SMSGateAPI


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def api(session):
    return SMSGateAPI("http://192.168.1.10:8080", session, "user", "pass")


@pytest.mark.asyncio
async def test_get_health_returns_dict_on_200(api, session):
    """async_get_health przy 200 zwraca dict."""
    resp = AsyncMock()
    resp.status = 200
    resp.content_length = 10
    resp.json = AsyncMock(return_value={"status": "pass"})
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get.return_value = resp
    result = await api.async_get_health()
    assert result == {"status": "pass"}
    assert session.get.called


@pytest.mark.asyncio
async def test_get_health_returns_none_on_401(api, session):
    """async_get_health przy 401 zwraca None (po próbie obu ścieżek)."""
    resp = AsyncMock()
    resp.status = 401
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get.return_value = resp
    result = await api.async_get_health()
    assert result is None


@pytest.mark.asyncio
async def test_send_sms_success(api, session):
    """async_send_sms przy 202 zwraca (True, message_id)."""
    resp = AsyncMock()
    resp.status = 202
    resp.headers = {"Location": "/messages/msg-123"}
    resp.text = AsyncMock(return_value="")
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.post.return_value = resp
    success, msg_id = await api.async_send_sms(["+48123456789"], "Hello")
    assert success is True
    assert msg_id == "msg-123"
    call_kw = session.post.call_args[1]
    assert call_kw["json"]["textMessage"]["text"] == "Hello"
    assert call_kw["json"]["phoneNumbers"] == ["+48123456789"]


@pytest.mark.asyncio
async def test_send_sms_404_tries_legacy_path(api, session):
    """Przy 404 na /messages próbuje /message."""
    resp_404 = AsyncMock()
    resp_404.status = 404
    resp_404.__aenter__ = AsyncMock(return_value=resp_404)
    resp_404.__aexit__ = AsyncMock(return_value=None)
    resp_202 = AsyncMock()
    resp_202.status = 202
    resp_202.headers = {}
    resp_202.__aenter__ = AsyncMock(return_value=resp_202)
    resp_202.__aexit__ = AsyncMock(return_value=None)
    session.post.side_effect = [resp_404, resp_202]
    success, _ = await api.async_send_sms(["+48111"], "Hi")
    assert success is True
    assert session.post.call_count == 2


@pytest.mark.asyncio
async def test_get_messages_returns_list(api, session):
    """async_get_messages zwraca listę dict."""
    resp = AsyncMock()
    resp.status = 200
    resp.json = AsyncMock(return_value=[
        {"id": "m1", "state": "Sent", "recipients": []},
    ])
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get.return_value = resp
    result = await api.async_get_messages(limit=20)
    assert len(result) == 1
    assert result[0]["id"] == "m1"
    assert result[0]["state"] == "Sent"


@pytest.mark.asyncio
async def test_get_message_returns_dict(api, session):
    """async_get_message zwraca pojedynczy dict."""
    resp = AsyncMock()
    resp.status = 200
    resp.json = AsyncMock(return_value={"id": "m1", "state": "Delivered"})
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get.return_value = resp
    result = await api.async_get_message("m1")
    assert result["id"] == "m1"
    assert result["state"] == "Delivered"
