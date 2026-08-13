from __future__ import annotations

import inspect
import json
import os
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

_PLATFORM_COOKIE_DOMAINS: dict[str, tuple[str, ...]] = {
    "douyin": ("douyin.com", "iesdouyin.com"),
    "xiaohongshu": ("xiaohongshu.com",),
    "wechat_channels": ("weixin.qq.com", "qq.com"),
    "kuaishou": ("kuaishou.com", "gifshow.com"),
    "bilibili": ("bilibili.com",),
    "tiktok": ("tiktok.com",),
}


class LocalBrowserCredentialError(RuntimeError):
    """Base error for a local browser credential reference."""


class LocalBrowserCredentialNotFound(LocalBrowserCredentialError):
    """Raised when no local login state is registered for an account reference."""


class InvalidLocalBrowserCredential(LocalBrowserCredentialError):
    """Raised when a registered local state file cannot be used."""


def _platform_value(platform: object) -> str:
    value = getattr(platform, "value", platform)
    return str(value).strip().lower()


def _host_matches(host: str, allowed_domains: tuple[str, ...]) -> bool:
    normalized = host.strip().lower().lstrip(".")
    return any(normalized == domain or normalized.endswith(f".{domain}") for domain in allowed_domains)


def _filter_storage_state(platform: object, raw: object) -> dict[str, list[dict[str, Any]]]:
    platform_value = _platform_value(platform)
    allowed_domains = _PLATFORM_COOKIE_DOMAINS.get(platform_value)
    if allowed_domains is None:
        raise InvalidLocalBrowserCredential("unsupported platform credential scope")
    if not isinstance(raw, dict):
        raise InvalidLocalBrowserCredential("browser storage state must be a JSON object")

    raw_cookies = raw.get("cookies", [])
    raw_origins = raw.get("origins", [])
    if not isinstance(raw_cookies, list) or not isinstance(raw_origins, list):
        raise InvalidLocalBrowserCredential("browser storage state cookies and origins must be arrays")

    cookies: list[dict[str, Any]] = []
    for item in raw_cookies:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "")
        name = str(item.get("name") or "")
        value = str(item.get("value") or "")
        if not name or not value or not _host_matches(domain, allowed_domains):
            continue
        cookies.append(deepcopy(item))

    origins: list[dict[str, Any]] = []
    for item in raw_origins:
        if not isinstance(item, dict):
            continue
        origin = str(item.get("origin") or "")
        host = urlsplit(origin).hostname or ""
        if host and _host_matches(host, allowed_domains):
            origins.append(deepcopy(item))

    return {"cookies": cookies, "origins": origins}


@dataclass(frozen=True, slots=True)
class LocalBrowserCredentials:
    """Process-local browser login state whose representation never includes values."""

    platform: str
    session_ref: str
    _storage_state: dict[str, list[dict[str, Any]]] = field(repr=False)

    def playwright_storage_state(self) -> dict[str, list[dict[str, Any]]]:
        """Return an isolated copy for creating the platform browser context."""
        return deepcopy(self._storage_state)

    @property
    def cookie_count(self) -> int:
        return len(self._storage_state["cookies"])

    def __repr__(self) -> str:
        return f"LocalBrowserCredentials(platform={self.platform!r}, session_ref={self.session_ref!r}, cookie_count={self.cookie_count}, storage_state=<redacted>)"


class LocalBrowserCredentialProvider:
    """Resolve account-scoped Playwright storage states from local files."""

    def __init__(self, state_files: Mapping[tuple[object, str], Path | str]) -> None:
        self._state_files = {(_platform_value(platform), str(session_ref)): Path(path).expanduser().resolve() for (platform, session_ref), path in state_files.items()}

    def load(self, platform: object, session_ref: str) -> LocalBrowserCredentials:
        platform_value = _platform_value(platform)
        key = (platform_value, str(session_ref))
        path = self._state_files.get(key)
        if path is None or not path.is_file():
            raise LocalBrowserCredentialNotFound("local browser session is not connected")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InvalidLocalBrowserCredential("local browser session cannot be read") from exc
        storage_state = _filter_storage_state(platform_value, raw)
        return LocalBrowserCredentials(
            platform=platform_value,
            session_ref=str(session_ref),
            _storage_state=storage_state,
        )


@dataclass(frozen=True, slots=True)
class LocalBrowserSessionRecord:
    platform: str
    session_ref: str
    state_path: Path
    cookie_count: int
    updated_at: datetime


class LocalBrowserSessionCapture(Protocol):
    def capture_storage_state(
        self,
        *,
        platform: object,
        session_ref: str,
    ) -> object: ...


CdpConnector = Callable[[str], object | Awaitable[object]]


class CdpLocalBrowserSessionCapture:
    """Read storage state from an already-running, trusted local Chrome."""

    def __init__(
        self,
        *,
        cdp_url: str = "http://127.0.0.1:9222",
        connector: CdpConnector | None = None,
    ) -> None:
        parsed = urlsplit(cdp_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("cdp_url must use a local loopback browser endpoint")
        if parsed.username or parsed.password:
            raise ValueError("cdp_url must not contain credentials")
        self.cdp_url = cdp_url
        self._connector = connector

    async def capture_storage_state(
        self,
        *,
        platform: object,
        session_ref: str,
    ) -> object:
        del platform, session_ref
        playwright_manager = None
        if self._connector is None:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError("Playwright browser support is not installed") from exc
            playwright_manager = await async_playwright().start()
            connector = playwright_manager.chromium.connect_over_cdp
        else:
            connector = self._connector
        try:
            raw_browser = connector(self.cdp_url)
            browser = await raw_browser if inspect.isawaitable(raw_browser) else raw_browser
            contexts = getattr(browser, "contexts", ())
            if not contexts:
                raise RuntimeError("local Chrome has no readable browser context")
            raw_state = contexts[0].storage_state()
            return await raw_state if inspect.isawaitable(raw_state) else raw_state
        finally:
            # Browser.close() terminates the user's Chrome, not just this CDP client.
            if playwright_manager is not None:
                await playwright_manager.stop()


def _validate_session_ref(value: str) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > 160:
        raise ValueError("session_ref must be between 1 and 160 characters")
    if any(part in {"", ".", ".."} for part in normalized.replace("\\", "/").split("/")):
        raise ValueError("session_ref must be a single local account reference")
    if not all(character.isalnum() or character in {"-", "_", "."} for character in normalized):
        raise ValueError("session_ref contains unsupported characters")
    return normalized


class LocalBrowserSessionRegistry:
    """Persist local account login state outside model-visible configuration."""

    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.index_path = self.root / "index.json"

    def _state_path(self, platform: object, session_ref: str) -> Path:
        platform_value = _platform_value(platform)
        if platform_value not in _PLATFORM_COOKIE_DOMAINS:
            raise ValueError("unsupported platform session")
        return self.root / platform_value / f"{_validate_session_ref(session_ref)}.json"

    def store(
        self,
        *,
        platform: object,
        session_ref: str,
        storage_state: object,
    ) -> LocalBrowserSessionRecord:
        platform_value = _platform_value(platform)
        session_ref = _validate_session_ref(session_ref)
        filtered = _filter_storage_state(platform_value, storage_state)
        state_path = self._state_path(platform_value, session_ref)
        state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(state_path.parent, 0o700)
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(filtered, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(state_path)
        os.chmod(state_path, 0o600)
        updated_at = datetime.now(UTC)
        self._write_index_record(
            platform=platform_value,
            session_ref=session_ref,
            state_path=state_path,
            cookie_count=len(filtered["cookies"]),
            updated_at=updated_at,
        )
        return LocalBrowserSessionRecord(
            platform=platform_value,
            session_ref=session_ref,
            state_path=state_path,
            cookie_count=len(filtered["cookies"]),
            updated_at=updated_at,
        )

    def _write_index_record(
        self,
        *,
        platform: str,
        session_ref: str,
        state_path: Path,
        cookie_count: int,
        updated_at: datetime,
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        try:
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            index = {"sessions": []}
        sessions = index.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        record = {
            "platform": platform,
            "session_ref": session_ref,
            "state_path": str(state_path.relative_to(self.root)),
            "cookie_count": cookie_count,
            "updated_at": updated_at.isoformat(),
        }
        sessions = [item for item in sessions if not (isinstance(item, dict) and item.get("platform") == platform and item.get("session_ref") == session_ref)]
        sessions.append(record)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"sessions": sessions}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(self.index_path)
        os.chmod(self.index_path, 0o600)

    def credential_provider(self) -> LocalBrowserCredentialProvider:
        try:
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            index = {"sessions": []}
        state_files: dict[tuple[str, str], Path] = {}
        for item in index.get("sessions", []):
            if not isinstance(item, dict):
                continue
            platform = str(item.get("platform") or "")
            session_ref = str(item.get("session_ref") or "")
            relative = Path(str(item.get("state_path") or ""))
            if not platform or not session_ref or relative.is_absolute() or ".." in relative.parts:
                continue
            state_files[(platform, session_ref)] = self.root / relative
        return LocalBrowserCredentialProvider(state_files)


async def register_local_browser_session(
    *,
    platform: object,
    session_ref: str,
    registry: LocalBrowserSessionRegistry,
    capture: LocalBrowserSessionCapture,
) -> LocalBrowserSessionRecord:
    session_ref = _validate_session_ref(session_ref)
    raw = capture.capture_storage_state(platform=platform, session_ref=session_ref)
    storage_state = await raw if inspect.isawaitable(raw) else raw
    return registry.store(
        platform=platform,
        session_ref=session_ref,
        storage_state=storage_state,
    )


__all__ = [
    "InvalidLocalBrowserCredential",
    "CdpLocalBrowserSessionCapture",
    "LocalBrowserCredentialError",
    "LocalBrowserCredentialNotFound",
    "LocalBrowserCredentialProvider",
    "LocalBrowserCredentials",
    "LocalBrowserSessionCapture",
    "LocalBrowserSessionRecord",
    "LocalBrowserSessionRegistry",
    "register_local_browser_session",
]
