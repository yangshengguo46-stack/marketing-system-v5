"""Tamper-evident, credential-safe traces for full DeerFlow agent evaluations."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|"
    r"secret|cookie|local[_-]?storage|session[_-]?storage|storage[_-]?state|"
    r"owner[_-]?id|user[_-]?id)",
    re.IGNORECASE,
)
_CREDENTIAL_VALUE_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AKLT[A-Za-z0-9]{16,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
_SAFE_RESULT_TOOLS = frozenset(
    {
        "incubation_context",
        "incubation_project_context",
        "incubation_project_evidence",
    }
)
_MAX_TRACE_STRING_CHARS = 4_000


class AgentTraceTamperDetected(ValueError):
    """A sealed agent trace or its tool-surface snapshot changed."""


@dataclass(frozen=True, slots=True)
class AgentTraceEvent:
    sequence: int
    event_type: str
    tool_name: str
    tool_call_id: str | None
    arguments: Mapping[str, Any] | None = None
    result_sha256: str | None = None
    result_chars: int | None = None
    safe_result: Any | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("trace event sequence must be non-negative")
        if self.event_type not in {"tool_call", "tool_result"}:
            raise ValueError("trace event type is invalid")
        if not self.tool_name.strip():
            raise ValueError("trace tool_name cannot be blank")
        if self.event_type == "tool_call":
            if self.arguments is None:
                raise ValueError("tool call trace requires arguments")
            object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))
            if self.result_sha256 is not None or self.result_chars is not None:
                raise ValueError("tool call trace cannot contain a result")
        else:
            if self.arguments is not None:
                raise ValueError("tool result trace cannot contain call arguments")
            if self.result_sha256 is None or self.result_chars is None:
                raise ValueError("tool result trace requires digest and size")
            _require_sha256(self.result_sha256, field_name="result_sha256")
            if self.result_chars < 0:
                raise ValueError("result_chars must be non-negative")


@dataclass(frozen=True, slots=True)
class AgentRunObservation:
    output: str
    final_message_id: str
    usage: Mapping[str, int | float]
    events: tuple[AgentTraceEvent, ...]
    fallback_error_code: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "usage", MappingProxyType(_normalize_usage(self.usage)))


@dataclass(frozen=True, slots=True)
class AgentTrialTrace:
    trial_id: str
    thread_id: str
    project_id: str
    actor_sha256: str
    events: tuple[AgentTraceEvent, ...]
    final_message_id: str
    usage: Mapping[str, int | float]
    terminal_error_code: str | None

    def __post_init__(self) -> None:
        for name in ("trial_id", "thread_id", "project_id"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} cannot be blank")
        _require_sha256(self.actor_sha256, field_name="actor_sha256")
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "usage", MappingProxyType(_normalize_usage(self.usage)))
        if self.terminal_error_code is not None and not self.terminal_error_code.strip():
            raise ValueError("terminal_error_code cannot be blank when supplied")


@dataclass(frozen=True, slots=True)
class AgentTraceRunManifest:
    run_id: str
    trial_ids: tuple[str, ...]
    actor_sha256: str
    tool_surface_sha256: str
    created_at: str


@dataclass(frozen=True, slots=True)
class AgentTraceVerification:
    run_id: str
    trace_count: int
    complete: bool


def _require_sha256(value: str, *, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _trial_filename(trial_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", trial_id)


def _write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if path.read_text(encoding="utf-8") != text:
            raise AgentTraceTamperDetected(f"sealed trace file already exists with different content: {path.name}") from None


def _normalize_usage(values: Mapping[str, int | float]) -> dict[str, int | float]:
    normalized: dict[str, int | float] = {}
    for name, value in values.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("usage names must be non-blank strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError("usage values must be non-negative numbers")
        normalized[name] = value
    return normalized


def _sanitize_json(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if key is not None and _SENSITIVE_KEY_PATTERN.search(key):
        return "[REDACTED]"
    if depth > 8:
        return "[MAX_DEPTH]"
    if isinstance(value, Mapping):
        return {
            str(child_key): _sanitize_json(
                child_value,
                key=str(child_key),
                depth=depth + 1,
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        if _CREDENTIAL_VALUE_PATTERN.search(value):
            return "[REDACTED]"
        if len(value) > _MAX_TRACE_STRING_CHARS:
            return f"[TRUNCATED sha256={_digest(value)} chars={len(value)}]"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(_sanitize_json(content), ensure_ascii=False, sort_keys=True)


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, Mapping):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
        elif isinstance(block, str):
            parts.append(block)
    return "".join(parts)


def _safe_tool_result(tool_name: str, content: str) -> Any | None:
    if tool_name not in _SAFE_RESULT_TOOLS:
        return None
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None
    return _sanitize_json(parsed)


class AgentEventCollector:
    """Collect model output and a bounded, redacted tool trajectory."""

    def __init__(self) -> None:
        self._chunks: dict[str, list[str]] = {}
        self._last_message_id = ""
        self._usage: dict[str, int | float] = {}
        self._events: list[AgentTraceEvent] = []
        self._seen_calls: set[tuple[str | None, str]] = set()
        self._fallback_error_code: str | None = None

    def consume(self, event: Any) -> None:
        event_type = getattr(event, "type", None)
        data = getattr(event, "data", None)
        if not isinstance(data, Mapping):
            return
        if event_type == "end":
            raw_usage = data.get("usage", {})
            if isinstance(raw_usage, Mapping):
                self._usage = _normalize_usage({str(name): value for name, value in raw_usage.items() if isinstance(name, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0})
            return
        if event_type != "messages-tuple":
            return

        message_type = data.get("type")
        if message_type == "ai":
            self._consume_ai(data)
        elif message_type == "tool":
            self._consume_tool(data)

    def _consume_ai(self, data: Mapping[str, Any]) -> None:
        message_id = str(data.get("id") or "")
        text = _message_text(data.get("content", ""))
        if text:
            self._chunks.setdefault(message_id, []).append(text)
            self._last_message_id = message_id

        additional = data.get("additional_kwargs", {})
        if isinstance(additional, Mapping) and additional.get("deerflow_error_fallback") is True:
            reason = str(additional.get("error_reason") or "error_fallback")
            safe_reason = re.sub(r"[^a-z0-9_]+", "_", reason.casefold()).strip("_")
            self._fallback_error_code = f"llm_{safe_reason or 'error_fallback'}"

        raw_calls = data.get("tool_calls", [])
        if not isinstance(raw_calls, list):
            return
        for raw_call in raw_calls:
            if not isinstance(raw_call, Mapping):
                continue
            tool_name = str(raw_call.get("name") or "").strip()
            if not tool_name:
                continue
            raw_call_id = raw_call.get("id")
            call_id = None if raw_call_id is None else str(raw_call_id)
            identity = (call_id, tool_name)
            if identity in self._seen_calls:
                continue
            self._seen_calls.add(identity)
            sanitized = _sanitize_json(raw_call.get("args", {}))
            arguments = sanitized if isinstance(sanitized, Mapping) else {"value": sanitized}
            self._events.append(
                AgentTraceEvent(
                    sequence=len(self._events),
                    event_type="tool_call",
                    tool_name=tool_name,
                    tool_call_id=call_id,
                    arguments=arguments,
                )
            )

    def _consume_tool(self, data: Mapping[str, Any]) -> None:
        tool_name = str(data.get("name") or "").strip()
        if not tool_name:
            return
        raw_call_id = data.get("tool_call_id")
        call_id = None if raw_call_id is None else str(raw_call_id)
        content = _content_text(data.get("content", ""))
        self._events.append(
            AgentTraceEvent(
                sequence=len(self._events),
                event_type="tool_result",
                tool_name=tool_name,
                tool_call_id=call_id,
                result_sha256=_digest(content),
                result_chars=len(content),
                safe_result=_safe_tool_result(tool_name, content),
            )
        )

    def finish(self) -> AgentRunObservation:
        return AgentRunObservation(
            output="".join(self._chunks.get(self._last_message_id, ())).strip(),
            final_message_id=self._last_message_id,
            usage=self._usage,
            events=tuple(self._events),
            fallback_error_code=self._fallback_error_code,
        )


def _event_payload(event: AgentTraceEvent) -> dict[str, Any]:
    return {
        "sequence": event.sequence,
        "event_type": event.event_type,
        "tool_name": event.tool_name,
        "tool_call_id": event.tool_call_id,
        "arguments": dict(event.arguments) if event.arguments is not None else None,
        "result_sha256": event.result_sha256,
        "result_chars": event.result_chars,
        "safe_result": event.safe_result,
    }


def _trace_payload(trace: AgentTrialTrace) -> dict[str, Any]:
    return {
        "trial_id": trace.trial_id,
        "thread_id": trace.thread_id,
        "project_id": trace.project_id,
        "actor_sha256": trace.actor_sha256,
        "events": [_event_payload(event) for event in trace.events],
        "final_message_id": trace.final_message_id,
        "usage": dict(trace.usage),
        "terminal_error_code": trace.terminal_error_code,
    }


class AgentTraceLedger:
    """Seal the available tool schemas and one redacted trace per trial."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def create_run(
        self,
        *,
        run_id: str,
        trial_ids: Sequence[str],
        actor_sha256: str,
        tool_surface: Sequence[Mapping[str, Any]],
        created_at: datetime,
    ) -> AgentTraceRunManifest:
        _require_aware(created_at, field_name="created_at")
        _require_sha256(actor_sha256, field_name="actor_sha256")
        canonical_ids = tuple(dict.fromkeys(trial_ids))
        if not canonical_ids or len(canonical_ids) != len(trial_ids):
            raise ValueError("trial_ids must be non-empty and unique")
        if len({_trial_filename(value) for value in canonical_ids}) != len(canonical_ids):
            raise ValueError("trial ids collide after filename normalization")
        surface_text = _canonical_json(_sanitize_json(list(tool_surface)))
        manifest = AgentTraceRunManifest(
            run_id=run_id,
            trial_ids=canonical_ids,
            actor_sha256=actor_sha256,
            tool_surface_sha256=_digest(surface_text),
            created_at=created_at.isoformat(),
        )
        manifest_text = _canonical_json(
            {
                "run_id": manifest.run_id,
                "trial_ids": list(manifest.trial_ids),
                "actor_sha256": manifest.actor_sha256,
                "tool_surface_sha256": manifest.tool_surface_sha256,
                "created_at": manifest.created_at,
            }
        )
        run_dir = self._run_dir(run_id)
        _write_new(run_dir / "tool-surface.json", surface_text)
        _write_new(run_dir / "agent-manifest.json", manifest_text)
        _write_new(run_dir / "agent-manifest.sha256", _digest(manifest_text) + "\n")
        return manifest

    def record_trace(self, *, run_id: str, trace: AgentTrialTrace) -> None:
        manifest = self._load_manifest(run_id)
        if trace.trial_id not in manifest.trial_ids:
            raise ValueError(f"trial is not declared by this run: {trace.trial_id}")
        if trace.actor_sha256 != manifest.actor_sha256:
            raise ValueError("trace actor does not match run actor")
        filename = _trial_filename(trace.trial_id)
        trace_text = _canonical_json(_trace_payload(trace))
        run_dir = self._run_dir(run_id)
        _write_new(run_dir / "traces" / f"{filename}.json", trace_text)
        _write_new(run_dir / "traces" / f"{filename}.sha256", _digest(trace_text) + "\n")

    def verify_run(self, run_id: str) -> AgentTraceVerification:
        manifest = self._load_manifest(run_id)
        run_dir = self._run_dir(run_id)
        surface_path = run_dir / "tool-surface.json"
        if not surface_path.exists() or _digest(surface_path.read_text(encoding="utf-8")) != manifest.tool_surface_sha256:
            raise AgentTraceTamperDetected("tool surface hash mismatch")
        trace_count = 0
        for trial_id in manifest.trial_ids:
            filename = _trial_filename(trial_id)
            trace_path = run_dir / "traces" / f"{filename}.json"
            digest_path = run_dir / "traces" / f"{filename}.sha256"
            if not trace_path.exists() and not digest_path.exists():
                continue
            if not trace_path.exists() or not digest_path.exists():
                raise AgentTraceTamperDetected(f"incomplete trace seal: {trial_id}")
            trace_text = trace_path.read_text(encoding="utf-8")
            if digest_path.read_text(encoding="utf-8").strip() != _digest(trace_text):
                raise AgentTraceTamperDetected(f"trace hash mismatch: {trial_id}")
            try:
                raw = json.loads(trace_text)
            except json.JSONDecodeError as exc:
                raise AgentTraceTamperDetected(f"trace is malformed: {trial_id}") from exc
            if raw.get("trial_id") != trial_id or raw.get("actor_sha256") != manifest.actor_sha256:
                raise AgentTraceTamperDetected(f"trace identity mismatch: {trial_id}")
            trace_count += 1
        return AgentTraceVerification(
            run_id=run_id,
            trace_count=trace_count,
            complete=trace_count == len(manifest.trial_ids),
        )

    def _load_manifest(self, run_id: str) -> AgentTraceRunManifest:
        run_dir = self._run_dir(run_id)
        path = run_dir / "agent-manifest.json"
        digest_path = run_dir / "agent-manifest.sha256"
        if not path.exists() or not digest_path.exists():
            raise FileNotFoundError(f"agent trace run does not exist: {run_id}")
        text = path.read_text(encoding="utf-8")
        if digest_path.read_text(encoding="utf-8").strip() != _digest(text):
            raise AgentTraceTamperDetected("agent manifest hash mismatch")
        try:
            raw = json.loads(text)
            manifest = AgentTraceRunManifest(
                run_id=str(raw["run_id"]),
                trial_ids=tuple(str(value) for value in raw["trial_ids"]),
                actor_sha256=str(raw["actor_sha256"]),
                tool_surface_sha256=str(raw["tool_surface_sha256"]),
                created_at=str(raw["created_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AgentTraceTamperDetected("agent manifest is malformed") from exc
        _require_sha256(manifest.actor_sha256, field_name="actor_sha256")
        _require_sha256(manifest.tool_surface_sha256, field_name="tool_surface_sha256")
        return manifest

    def _run_dir(self, run_id: str) -> Path:
        if not run_id.strip() or Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError("run_id must be a single safe path component")
        return self._root / run_id


__all__ = [
    "AgentEventCollector",
    "AgentRunObservation",
    "AgentTraceEvent",
    "AgentTraceLedger",
    "AgentTraceRunManifest",
    "AgentTraceTamperDetected",
    "AgentTraceVerification",
    "AgentTrialTrace",
]
