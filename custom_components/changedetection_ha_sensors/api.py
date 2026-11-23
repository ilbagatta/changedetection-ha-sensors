"""Client minimo per l'API REST v1 di changedetection.io."""

from __future__ import annotations

from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20)


class ChangedetectionError(Exception):
    """Errore generico dell'API."""


class CannotConnect(ChangedetectionError):
    """Server non raggiungibile."""


class InvalidAuth(ChangedetectionError):
    """Chiave API rifiutata."""


def normalize_url(url: str) -> str:
    """`http://host:5000/`, `http://host:5000/api/v1` -> `http://host:5000`."""
    url = url.strip().rstrip("/")
    if url.endswith("/api/v1"):
        url = url[: -len("/api/v1")]
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


class ChangedetectionClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, api_key: str) -> None:
        self._session = session
        self._base = f"{normalize_url(url)}/api/v1"
        self._headers = {"x-api-key": api_key}

    async def _get(self, path: str, params: dict[str, str] | None = None, *, text: bool = False) -> Any:
        try:
            async with self._session.get(
                f"{self._base}{path}", headers=self._headers, params=params, timeout=TIMEOUT
            ) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuth
                if resp.status >= 400:
                    raise ChangedetectionError(f"{path}: HTTP {resp.status}")
                if text:
                    return await resp.text()
                return await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CannotConnect(str(err)) from err

    async def async_system_info(self) -> dict[str, Any]:
        return await self._get("/systeminfo")

    async def async_get_watches(self) -> dict[str, dict[str, Any]]:
        """{uuid: {title, url, last_changed, last_checked, last_error, viewed, ...}}"""
        data = await self._get("/watch")
        return data if isinstance(data, dict) else {}

    async def async_get_history(self, uuid: str) -> list[str]:
        """Timestamp delle rilevazioni salvate, dal piu' recente."""
        data = await self._get(f"/watch/{uuid}/history")
        if not isinstance(data, dict):
            return []
        return sorted(data, key=lambda ts: int(ts) if str(ts).isdigit() else 0, reverse=True)

    async def async_get_snapshot(self, uuid: str, timestamp: str = "latest") -> str:
        return await self._get(f"/watch/{uuid}/history/{timestamp}", text=True)

    async def async_recheck(self, uuid: str) -> None:
        await self._get(f"/watch/{uuid}", {"recheck": "1"}, text=True)

    async def async_recheck_all(self) -> None:
        await self._get("/watch", {"recheck_all": "1"}, text=True)
