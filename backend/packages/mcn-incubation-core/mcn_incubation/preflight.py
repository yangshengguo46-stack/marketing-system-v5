"""Append-only local evidence for small, real-model incubation preflights."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from mcn_incubation.evaluation import EvalCase

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DuplicatePreflightRecord(ValueError):
    """A trial already has a sealed result in this run."""


class IncompletePreflightRun(ValueError):
    """A run cannot be completed until every declared trial has a result."""


class PreflightTamperDetected(ValueError):
    """Stored content no longer matches its recorded integrity hash."""


@dataclass(frozen=True, slots=True)
class PreflightRunManifest:
    run_id: str
    model_id: str
    trial_ids: tuple[str, ...]
    system_prompt_sha256: str
    corpus_sha256: str
    created_at: str


@dataclass(frozen=True, slots=True)
class PreflightRecord:
    run_id: str
    trial_id: str
    status: str
    input_sha256: str
    output_sha256: str | None
    started_at: str
    completed_at: str
    duration_ms: int
    usage: Mapping[str, int | float]
    error_code: str | None


@dataclass(frozen=True, slots=True)
class PreflightCompletion:
    run_id: str
    status: str
    succeeded: int
    failed: int
    records_sha256: str
    completed_at: str


@dataclass(frozen=True, slots=True)
class PreflightVerification:
    run_id: str
    record_count: int
    completed: bool


def _require_text(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_sha256(value: str, *, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


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
            raise PreflightTamperDetected(f"sealed file already exists with different content: {path.name}") from None


def build_preflight_prompt(case: EvalCase, *, include_mutation: bool) -> str:
    """Render one natural user request without embedding a scoring template."""

    sections = [
        "这是一次 MCN 孵化预检。请直接判断这个主体应该怎么起号、持续生产内容并形成变现闭环。",
        f"情境：{case.scenario}",
        f"已知事实：{' ；'.join(case.facts) or '无'}",
        f"现实限制：{' ；'.join(case.constraints) or '无'}",
        f"经营目标：{' ；'.join(case.goals) or '无'}",
        f"当前产品或服务：{' ；'.join(case.offers) or '暂无'}",
    ]
    if include_mutation:
        sections.append(f"新补充证据：{case.mutation}")
        sections.append("请根据新证据修正原本可能成立的方向，并说明改了什么。")
    sections.append(
        "只使用上述事实。不要联网补造调研、客户、收入或爆款结果；"
        "不得为主体新增身份、经历、客户案例或产品效果。可以提出创意方案，"
        "但输入中没有的价格、预算、频率和指标阈值必须明确写成待验证变量，"
        "不能写成行业事实、结果承诺或需求成立的证明；仅标成待验证并不能让任意数字变得有依据，"
        "若没有成本、产能、历史基线或明确取舍，就保留为空并说明如何确定。信息不足时可以做暂定判断，"
        "但要标明假设、关键未知和替代方案。"
    )
    return "\n".join(sections)


class PreflightLedger:
    """Write each preflight input and outcome once under an ignored local root."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def create_run(
        self,
        *,
        run_id: str,
        model_id: str,
        trial_ids: Sequence[str],
        system_prompt_sha256: str,
        corpus_sha256: str,
        created_at: datetime,
    ) -> PreflightRunManifest:
        _require_text(run_id, field_name="run_id")
        _require_text(model_id, field_name="model_id")
        _require_aware(created_at, field_name="created_at")
        _require_sha256(system_prompt_sha256, field_name="system_prompt_sha256")
        _require_sha256(corpus_sha256, field_name="corpus_sha256")
        canonical_ids = tuple(dict.fromkeys(trial_ids))
        if not canonical_ids or len(canonical_ids) != len(trial_ids):
            raise ValueError("trial_ids must be non-empty and unique")
        if len({_trial_filename(trial_id) for trial_id in canonical_ids}) != len(canonical_ids):
            raise ValueError("trial ids collide after filename normalization")
        for trial_id in canonical_ids:
            _require_text(trial_id, field_name="trial_id")
        manifest = PreflightRunManifest(
            run_id=run_id,
            model_id=model_id,
            trial_ids=canonical_ids,
            system_prompt_sha256=system_prompt_sha256,
            corpus_sha256=corpus_sha256,
            created_at=created_at.isoformat(),
        )
        manifest_text = _canonical_json(asdict(manifest))
        run_dir = self._run_dir(run_id)
        _write_new(run_dir / "manifest.json", manifest_text)
        _write_new(run_dir / "manifest.sha256", _digest(manifest_text) + "\n")
        return manifest

    def record_success(
        self,
        *,
        run_id: str,
        trial_id: str,
        prompt: str,
        output: str,
        started_at: datetime,
        completed_at: datetime,
        usage: Mapping[str, int | float] | None = None,
    ) -> PreflightRecord:
        _require_text(output, field_name="output")
        return self._record(
            run_id=run_id,
            trial_id=trial_id,
            prompt=prompt,
            output=output,
            error_code=None,
            started_at=started_at,
            completed_at=completed_at,
            usage=usage,
        )

    def record_failure(
        self,
        *,
        run_id: str,
        trial_id: str,
        prompt: str,
        error_code: str,
        started_at: datetime,
        completed_at: datetime,
    ) -> PreflightRecord:
        _require_text(error_code, field_name="error_code")
        return self._record(
            run_id=run_id,
            trial_id=trial_id,
            prompt=prompt,
            output=None,
            error_code=error_code,
            started_at=started_at,
            completed_at=completed_at,
            usage=None,
        )

    def _record(
        self,
        *,
        run_id: str,
        trial_id: str,
        prompt: str,
        output: str | None,
        error_code: str | None,
        started_at: datetime,
        completed_at: datetime,
        usage: Mapping[str, int | float] | None,
    ) -> PreflightRecord:
        _require_text(prompt, field_name="prompt")
        _require_aware(started_at, field_name="started_at")
        _require_aware(completed_at, field_name="completed_at")
        if completed_at < started_at:
            raise ValueError("completed_at cannot precede started_at")
        manifest = self._load_manifest(run_id)
        if trial_id not in manifest.trial_ids:
            raise ValueError(f"trial is not declared by this run: {trial_id}")
        records = self._load_records(run_id)
        if trial_id in {record.trial_id for record in records}:
            raise DuplicatePreflightRecord(f"trial already recorded: {trial_id}")
        normalized_usage = self._normalize_usage(usage or {})
        filename = _trial_filename(trial_id)
        run_dir = self._run_dir(run_id)
        _write_new(run_dir / "inputs" / f"{filename}.txt", prompt)
        if output is not None:
            _write_new(run_dir / "outputs" / f"{filename}.md", output)
        duration_ms = round((completed_at - started_at).total_seconds() * 1000)
        record = PreflightRecord(
            run_id=run_id,
            trial_id=trial_id,
            status="succeeded" if output is not None else "failed",
            input_sha256=_digest(prompt),
            output_sha256=_digest(output) if output is not None else None,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=duration_ms,
            usage=normalized_usage,
            error_code=error_code,
        )
        records_path = run_dir / "records.jsonl"
        records_path.parent.mkdir(parents=True, exist_ok=True)
        with records_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(asdict(record)))
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def complete_run(self, run_id: str, *, completed_at: datetime) -> PreflightCompletion:
        _require_aware(completed_at, field_name="completed_at")
        manifest = self._load_manifest(run_id)
        verification = self.verify_run(run_id)
        if verification.record_count != len(manifest.trial_ids):
            raise IncompletePreflightRun("not every declared trial has a result")
        records = self._load_records(run_id)
        succeeded = sum(record.status == "succeeded" for record in records)
        failed = sum(record.status == "failed" for record in records)
        records_text = (self._run_dir(run_id) / "records.jsonl").read_text(encoding="utf-8")
        completion = PreflightCompletion(
            run_id=run_id,
            status="completed" if failed == 0 else "completed_with_failures",
            succeeded=succeeded,
            failed=failed,
            records_sha256=_digest(records_text),
            completed_at=completed_at.isoformat(),
        )
        _write_new(self._run_dir(run_id) / "completion.json", _canonical_json(asdict(completion)))
        return completion

    def verify_run(self, run_id: str) -> PreflightVerification:
        manifest = self._load_manifest(run_id)
        records = self._load_records(run_id)
        seen: set[str] = set()
        for record in records:
            if record.trial_id in seen:
                raise PreflightTamperDetected(f"duplicate record: {record.trial_id}")
            seen.add(record.trial_id)
            if record.trial_id not in manifest.trial_ids:
                raise PreflightTamperDetected(f"undeclared record: {record.trial_id}")
            filename = _trial_filename(record.trial_id)
            input_path = self._run_dir(run_id) / "inputs" / f"{filename}.txt"
            if not input_path.exists() or _digest(input_path.read_text(encoding="utf-8")) != record.input_sha256:
                raise PreflightTamperDetected(f"input hash mismatch: {record.trial_id}")
            if record.status == "succeeded":
                output_path = self._run_dir(run_id) / "outputs" / f"{filename}.md"
                if not output_path.exists() or _digest(output_path.read_text(encoding="utf-8")) != record.output_sha256:
                    raise PreflightTamperDetected(f"output hash mismatch: {record.trial_id}")
        completion_path = self._run_dir(run_id) / "completion.json"
        if completion_path.exists():
            raw_completion = json.loads(completion_path.read_text(encoding="utf-8"))
            records_text = (self._run_dir(run_id) / "records.jsonl").read_text(encoding="utf-8")
            if raw_completion.get("records_sha256") != _digest(records_text):
                raise PreflightTamperDetected("completion records hash mismatch")
        return PreflightVerification(
            run_id=run_id,
            record_count=len(records),
            completed=completion_path.exists(),
        )

    def _load_manifest(self, run_id: str) -> PreflightRunManifest:
        run_dir = self._run_dir(run_id)
        manifest_path = run_dir / "manifest.json"
        digest_path = run_dir / "manifest.sha256"
        if not manifest_path.exists() or not digest_path.exists():
            raise FileNotFoundError(f"preflight run does not exist: {run_id}")
        manifest_text = manifest_path.read_text(encoding="utf-8")
        if digest_path.read_text(encoding="utf-8").strip() != _digest(manifest_text):
            raise PreflightTamperDetected("manifest hash mismatch")
        raw = json.loads(manifest_text)
        return PreflightRunManifest(
            run_id=str(raw["run_id"]),
            model_id=str(raw["model_id"]),
            trial_ids=tuple(str(value) for value in raw["trial_ids"]),
            system_prompt_sha256=str(raw["system_prompt_sha256"]),
            corpus_sha256=str(raw["corpus_sha256"]),
            created_at=str(raw["created_at"]),
        )

    def _load_records(self, run_id: str) -> tuple[PreflightRecord, ...]:
        path = self._run_dir(run_id) / "records.jsonl"
        if not path.exists():
            return ()
        records: list[PreflightRecord] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                raw = json.loads(line)
                records.append(
                    PreflightRecord(
                        run_id=str(raw["run_id"]),
                        trial_id=str(raw["trial_id"]),
                        status=str(raw["status"]),
                        input_sha256=str(raw["input_sha256"]),
                        output_sha256=(None if raw["output_sha256"] is None else str(raw["output_sha256"])),
                        started_at=str(raw["started_at"]),
                        completed_at=str(raw["completed_at"]),
                        duration_ms=int(raw["duration_ms"]),
                        usage=self._normalize_usage(raw.get("usage", {})),
                        error_code=None if raw["error_code"] is None else str(raw["error_code"]),
                    )
                )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PreflightTamperDetected("records ledger is malformed") from exc
        return tuple(records)

    @staticmethod
    def _normalize_usage(usage: Mapping[str, int | float]) -> dict[str, int | float]:
        normalized: dict[str, int | float] = {}
        for name, value in usage.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("usage names must be non-blank strings")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError("usage values must be non-negative numbers")
            normalized[name] = value
        return normalized

    def _run_dir(self, run_id: str) -> Path:
        _require_text(run_id, field_name="run_id")
        if Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError("run_id must be a single safe path component")
        return self._root / run_id


__all__ = [
    "DuplicatePreflightRecord",
    "IncompletePreflightRun",
    "PreflightCompletion",
    "PreflightLedger",
    "PreflightRecord",
    "PreflightRunManifest",
    "PreflightTamperDetected",
    "PreflightVerification",
    "build_preflight_prompt",
]
