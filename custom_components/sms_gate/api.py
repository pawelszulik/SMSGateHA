"""
Klient API SMS Gate (Local Server, Basic Auth).

Komunikacja z aplikacją SMS Gateway for Android w trybie Local:
- GET /health (lub /health/ready) – weryfikacja połączenia,
- POST /messages (fallback /message przy 404) – wysyłanie SMS,
- GET /messages – lista wiadomości (id, state, recipients),
- GET /messages/{id} – pojedyncza wiadomość.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import PATH_HEALTH, PATH_HEALTH_READY, PATH_MESSAGE_LEGACY, PATH_MESSAGES

_LOGGER = logging.getLogger(__name__)


class SMSGateError(Exception):
    """Błąd wywołania API SMS Gate."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SMSGateAPI:
    """Klient HTTP do Local Server SMS Gate (tylko Basic Auth)."""

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Inicjalizacja klienta."""
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._auth = aiohttp.BasicAuth(username, password)

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    async def async_get_health(self) -> dict[str, Any] | None:
        """
        Sprawdza dostępność bramki (GET /health).
        Przy 404 próbuje /health/ready. Zwraca dict z odpowiedzi lub None przy błędzie.
        """
        for path in (PATH_HEALTH, PATH_HEALTH_READY):
            try:
                async with self._session.get(
                    self._url(path),
                    auth=self._auth,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json() if resp.content_length else {}
                    if resp.status == 404:
                        continue
                    _LOGGER.warning("Health %s: status %s", path, resp.status)
                    return None
            except aiohttp.ClientError as e:
                _LOGGER.debug("Health %s failed: %s", path, e)
                continue
        return None

    async def async_send_sms(
        self,
        phone_numbers: list[str],
        text: str,
        *,
        sim_number: int | None = None,
        priority: int = 100,
        ttl: int = 3600,
        skip_validation: bool = True,
    ) -> tuple[bool, str | None]:
        """
        Wysyła SMS (POST /messages, przy 404 fallback na /message).
        Zwraca (success, message_id lub komunikat błędu).
        """
        payload: dict[str, Any] = {
            "phoneNumbers": phone_numbers,
            "textMessage": {"text": text},
        }
        if sim_number is not None:
            payload["simNumber"] = sim_number
        payload["priority"] = priority
        payload["ttl"] = ttl

        params: dict[str, Any] = {}
        if skip_validation:
            params["skipPhoneValidation"] = "true"

        for path in (PATH_MESSAGES, PATH_MESSAGE_LEGACY):
            try:
                async with self._session.post(
                    self._url(path),
                    auth=self._auth,
                    json=payload,
                    params=params or None,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 202:
                        location = resp.headers.get("Location")
                        msg_id = location.split("/")[-1] if location else None
                        return True, msg_id
                    if resp.status == 404:
                        continue
                    body = await resp.text()
                    _LOGGER.warning("Send SMS %s: %s %s", path, resp.status, body[:200])
                    return False, f"HTTP {resp.status}: {body[:100]}"
            except aiohttp.ClientError as e:
                _LOGGER.debug("Send SMS %s failed: %s", path, e)
                return False, str(e)
        return False, "Not found (404) for /messages and /message"

    async def async_get_messages(
        self,
        *,
        state: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Pobiera listę wiadomości (GET /messages).
        Zwraca listę dict (id, deviceId, recipients, state).
        """
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if state:
            params["state"] = state
        try:
            async with self._session.get(
                self._url(PATH_MESSAGES),
                auth=self._auth,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Get messages: status %s", resp.status)
                    return []
                data = await resp.json()
                return data if isinstance(data, list) else []
        except (aiohttp.ClientError, ValueError) as e:
            _LOGGER.debug("Get messages failed: %s", e)
            return []

    async def async_get_message(self, message_id: str) -> dict[str, Any] | None:
        """Pobiera pojedynczą wiadomość (GET /messages/{id})."""
        try:
            async with self._session.get(
                self._url(f"{PATH_MESSAGES}/{message_id}"),
                auth=self._auth,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except (aiohttp.ClientError, ValueError):
            return None
