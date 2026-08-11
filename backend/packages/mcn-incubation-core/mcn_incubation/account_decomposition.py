"""Traceable account observations that support, but never decide, incubation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from math import isfinite
from re import fullmatch
from urllib.parse import urlsplit, urlunsplit


def _required(value: str, *, field_name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} cannot be blank")
    return normalized


def _optional(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _required(value, field_name=field_name)


def _texts(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_required(value, field_name=field_name) for value in values))


def _aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _hash(value: str, *, field_name: str) -> str:
    normalized = value.strip().lower()
    if fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise ValueError(f"{field_name} must be a SHA-256 hex digest")
    return normalized


def _canonical_https_url(value: str, *, field_name: str) -> str:
    normalized = _required(value, field_name=field_name)
    parsed = urlsplit(normalized)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} must be a canonical HTTPS URL without credentials, query, or fragment")
    host = parsed.hostname.casefold()
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit(("https", host, parsed.path or "/", "", ""))


def _confidence(value: float | None) -> None:
    if value is not None and (not isfinite(value) or not 0.0 <= value <= 1.0):
        raise ValueError("confidence must be between 0 and 1")


def _same_scope(value: object, *, owner_id: str, project_id: str, label: str) -> None:
    if getattr(value, "owner_id") != owner_id or getattr(value, "project_id") != project_id:
        raise ValueError(f"{label} crosses the account evidence owner or project boundary")


class SocialPlatform(StrEnum):
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    WECHAT_CHANNELS = "wechat_channels"
    KUAISHOU = "kuaishou"
    BILIBILI = "bilibili"
    TIKTOK = "tiktok"


class AccountIdentityStatus(StrEnum):
    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    AMBIGUOUS = "ambiguous"


class MediaExecutionMode(StrEnum):
    LOCAL = "local"
    CLOUD = "cloud"


@dataclass(frozen=True, slots=True)
class EvidenceWarning:
    code: str
    message: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required(self.code, field_name="warning code"))
        object.__setattr__(self, "message", _required(self.message, field_name="warning message"))
        object.__setattr__(
            self,
            "evidence_refs",
            _texts(self.evidence_refs, field_name="warning evidence_ref"),
        )


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    snapshot_id: str
    owner_id: str
    project_id: str
    platform: SocialPlatform
    platform_account_id: str | None
    canonical_profile_url: str
    identity_status: AccountIdentityStatus
    captured_at: datetime
    source_ref: str
    content_hash: str
    display_name: str | None = None
    bio: str | None = None
    verification_labels: tuple[str, ...] = field(default_factory=tuple)
    region: str | None = None
    identity_evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("snapshot_id", "owner_id", "project_id", "source_ref"):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        if not isinstance(self.platform, SocialPlatform):
            raise ValueError("platform must be a supported SocialPlatform")
        if not isinstance(self.identity_status, AccountIdentityStatus):
            raise ValueError("identity_status must be an AccountIdentityStatus")
        object.__setattr__(
            self,
            "platform_account_id",
            _optional(self.platform_account_id, field_name="platform_account_id"),
        )
        if self.identity_status is AccountIdentityStatus.CONFIRMED and self.platform_account_id is None:
            raise ValueError("confirmed identity requires a platform_account_id")
        object.__setattr__(
            self,
            "canonical_profile_url",
            _canonical_https_url(self.canonical_profile_url, field_name="canonical_profile_url"),
        )
        _aware(self.captured_at, field_name="captured_at")
        object.__setattr__(self, "content_hash", _hash(self.content_hash, field_name="content_hash"))
        for name in ("display_name", "bio", "region"):
            object.__setattr__(self, name, _optional(getattr(self, name), field_name=name))
        for name in ("verification_labels", "identity_evidence_refs", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))


@dataclass(frozen=True, slots=True)
class SamplingFrame:
    frame_id: str
    owner_id: str
    project_id: str
    snapshot_id: str
    captured_at: datetime
    selection_basis: tuple[str, ...]
    inclusion_rules: tuple[str, ...]
    exclusion_rules: tuple[str, ...]
    visible_post_count: int | None
    attempted_post_count: int
    included_post_ids: tuple[str, ...]
    excluded_post_ids: tuple[str, ...] = field(default_factory=tuple)
    missing_reasons: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    source_refs: tuple[str, ...] = field(default_factory=tuple)
    window_start: datetime | None = None
    window_end: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("frame_id", "owner_id", "project_id", "snapshot_id"):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        _aware(self.captured_at, field_name="captured_at")
        for name in (
            "selection_basis",
            "inclusion_rules",
            "exclusion_rules",
            "included_post_ids",
            "excluded_post_ids",
            "missing_reasons",
            "limitations",
            "source_refs",
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))
        if not self.selection_basis:
            raise ValueError("sampling frame requires a selection_basis")
        for name in ("visible_post_count", "attempted_post_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or (value is not None and (not isinstance(value, int) or value < 0)):
                raise ValueError(f"{name} must be a non-negative integer when supplied")
        if self.attempted_post_count < len(self.included_post_ids):
            raise ValueError("attempted_post_count cannot be smaller than included posts")
        if self.visible_post_count is not None and len(self.included_post_ids) > self.visible_post_count:
            raise ValueError("included posts cannot exceed the visible post count")
        overlap = set(self.included_post_ids).intersection(self.excluded_post_ids)
        if overlap:
            raise ValueError("a sampled post cannot be both included and excluded")
        for name in ("window_start", "window_end"):
            value = getattr(self, name)
            if value is not None:
                _aware(value, field_name=name)
        if self.window_start is not None and self.window_end is not None and self.window_end < self.window_start:
            raise ValueError("window_end cannot precede window_start")

    @property
    def coverage_ratio(self) -> float | None:
        if self.visible_post_count in {None, 0}:
            return None
        return len(self.included_post_ids) / self.visible_post_count


@dataclass(frozen=True, slots=True)
class MetricObservation:
    name: str
    value: int | float
    captured_at: datetime
    source_ref: str
    definition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required(self.name, field_name="metric name"))
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError("metric value must be numeric")
        if not isfinite(float(self.value)) or self.value < 0:
            raise ValueError("metric value must be finite and non-negative")
        _aware(self.captured_at, field_name="metric captured_at")
        object.__setattr__(self, "source_ref", _required(self.source_ref, field_name="metric source_ref"))
        object.__setattr__(self, "definition", _optional(self.definition, field_name="metric definition"))


@dataclass(frozen=True, slots=True)
class PostObservation:
    post_observation_id: str
    owner_id: str
    project_id: str
    snapshot_id: str
    platform_post_id: str
    author_platform_account_id: str | None
    canonical_post_url: str
    captured_at: datetime
    content_hash: str
    source_ref: str
    published_at: datetime | None = None
    title: str | None = None
    caption: str | None = None
    metrics: tuple[MetricObservation, ...] = field(default_factory=tuple)
    missing_metrics: tuple[str, ...] = field(default_factory=tuple)
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in (
            "post_observation_id",
            "owner_id",
            "project_id",
            "snapshot_id",
            "platform_post_id",
            "source_ref",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "author_platform_account_id",
            _optional(
                self.author_platform_account_id,
                field_name="author_platform_account_id",
            ),
        )
        object.__setattr__(
            self,
            "canonical_post_url",
            _canonical_https_url(self.canonical_post_url, field_name="canonical_post_url"),
        )
        _aware(self.captured_at, field_name="captured_at")
        if self.published_at is not None:
            _aware(self.published_at, field_name="published_at")
        object.__setattr__(self, "content_hash", _hash(self.content_hash, field_name="content_hash"))
        for name in ("title", "caption"):
            object.__setattr__(self, name, _optional(getattr(self, name), field_name=name))
        object.__setattr__(self, "metrics", tuple(self.metrics))
        metric_names = [metric.name for metric in self.metrics]
        if len(set(metric_names)) != len(metric_names):
            raise ValueError("post metrics must have unique names")
        for name in ("missing_metrics", "artifact_refs", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))
        overlap = set(metric_names).intersection(self.missing_metrics)
        if overlap:
            raise ValueError("an observed metric cannot also be marked missing")


@dataclass(frozen=True, slots=True)
class MediaAtomReceipt:
    capability: str
    execution_mode: MediaExecutionMode
    tool_version: str
    schema_hash: str
    input_hash: str
    output_hash: str
    task_id: str
    completed_at: datetime
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float | None = None
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("capability", "tool_version", "task_id"):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        if not isinstance(self.execution_mode, MediaExecutionMode):
            raise ValueError("execution_mode must be a MediaExecutionMode")
        for name in ("schema_hash", "input_hash", "output_hash"):
            object.__setattr__(self, name, _hash(getattr(self, name), field_name=name))
        _aware(self.completed_at, field_name="completed_at")
        for name in ("artifact_refs", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))
        _confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class MediaAtomGap:
    capability: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability", _required(self.capability, field_name="capability"))
        object.__setattr__(self, "reason", _required(self.reason, field_name="gap reason"))


@dataclass(frozen=True, slots=True)
class MediaAtomSet:
    atom_set_id: str
    owner_id: str
    project_id: str
    post_observation_id: str
    created_at: datetime
    input_hash: str
    rights_basis: tuple[str, ...]
    cloud_processing_consent: bool
    receipts: tuple[MediaAtomReceipt, ...] = field(default_factory=tuple)
    gaps: tuple[MediaAtomGap, ...] = field(default_factory=tuple)
    conflicts: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("atom_set_id", "owner_id", "project_id", "post_observation_id"):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        _aware(self.created_at, field_name="created_at")
        object.__setattr__(self, "input_hash", _hash(self.input_hash, field_name="input_hash"))
        object.__setattr__(self, "rights_basis", _texts(self.rights_basis, field_name="rights_basis"))
        if not self.rights_basis:
            raise ValueError("media atoms require a rights_basis")
        if not isinstance(self.cloud_processing_consent, bool):
            raise ValueError("cloud_processing_consent must be boolean")
        object.__setattr__(self, "receipts", tuple(self.receipts))
        object.__setattr__(self, "gaps", tuple(self.gaps))
        receipt_capabilities = [receipt.capability for receipt in self.receipts]
        if len(set(receipt_capabilities)) != len(receipt_capabilities):
            raise ValueError("media atom receipts must have unique capabilities")
        gap_capabilities = [gap.capability for gap in self.gaps]
        if len(set(gap_capabilities)) != len(gap_capabilities):
            raise ValueError("media atom gaps must have unique capabilities")
        if set(receipt_capabilities).intersection(gap_capabilities):
            raise ValueError("a media capability cannot be both complete and missing")
        for receipt in self.receipts:
            if receipt.input_hash != self.input_hash:
                raise ValueError("media atom receipt input_hash does not match its set")
            if receipt.execution_mode is MediaExecutionMode.CLOUD and not self.cloud_processing_consent:
                raise ValueError("cloud processing consent is required for cloud media atoms")
        for name in ("conflicts", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))


@dataclass(frozen=True, slots=True)
class AccountPatternHypothesis:
    pattern_hypothesis_id: str
    owner_id: str
    project_id: str
    snapshot_id: str
    frame_id: str
    dimension: str
    statement: str
    supporting_post_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    counterexample_post_ids: tuple[str, ...] = field(default_factory=tuple)
    applicable_from: datetime | None = None
    applicable_to: datetime | None = None
    confidence: float | None = None
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in (
            "pattern_hypothesis_id",
            "owner_id",
            "project_id",
            "snapshot_id",
            "frame_id",
            "dimension",
            "statement",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        for name in (
            "supporting_post_ids",
            "evidence_refs",
            "counterexample_post_ids",
            "unknowns",
            "limitations",
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))
        if not self.supporting_post_ids:
            raise ValueError("pattern hypothesis requires supporting posts")
        if not self.evidence_refs:
            raise ValueError("pattern hypothesis requires evidence_refs")
        if set(self.supporting_post_ids).intersection(self.counterexample_post_ids):
            raise ValueError("one post cannot support and contradict the same pattern")
        for name in ("applicable_from", "applicable_to"):
            value = getattr(self, name)
            if value is not None:
                _aware(value, field_name=name)
        if self.applicable_from is not None and self.applicable_to is not None and self.applicable_to < self.applicable_from:
            raise ValueError("applicable_to cannot precede applicable_from")
        _confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class TransferCandidate:
    transfer_candidate_id: str
    owner_id: str
    project_id: str
    source_snapshot_id: str
    pattern_hypothesis_ids: tuple[str, ...]
    function_to_transfer: str
    required_conditions: tuple[str, ...]
    adaptation_notes: tuple[str, ...]
    originality_boundaries: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    rights_constraints: tuple[str, ...] = field(default_factory=tuple)
    unknowns: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in (
            "transfer_candidate_id",
            "owner_id",
            "project_id",
            "source_snapshot_id",
            "function_to_transfer",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        for name in (
            "pattern_hypothesis_ids",
            "required_conditions",
            "adaptation_notes",
            "originality_boundaries",
            "evidence_refs",
            "rights_constraints",
            "unknowns",
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))
        for name in (
            "pattern_hypothesis_ids",
            "required_conditions",
            "originality_boundaries",
            "evidence_refs",
        ):
            if not getattr(self, name):
                raise ValueError(f"transfer candidate requires {name}")


@dataclass(frozen=True, slots=True)
class AccountEvidenceBundle:
    snapshot: AccountSnapshot
    sampling_frame: SamplingFrame
    posts: tuple[PostObservation, ...]
    media_atom_sets: tuple[MediaAtomSet, ...] = field(default_factory=tuple)
    pattern_hypotheses: tuple[AccountPatternHypothesis, ...] = field(default_factory=tuple)
    transfer_candidates: tuple[TransferCandidate, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        owner_id = self.snapshot.owner_id
        project_id = self.snapshot.project_id
        _same_scope(
            self.sampling_frame,
            owner_id=owner_id,
            project_id=project_id,
            label="sampling frame",
        )
        if self.sampling_frame.snapshot_id != self.snapshot.snapshot_id:
            raise ValueError("sampling frame references a different account snapshot")

        object.__setattr__(self, "posts", tuple(self.posts))
        object.__setattr__(self, "media_atom_sets", tuple(self.media_atom_sets))
        object.__setattr__(self, "pattern_hypotheses", tuple(self.pattern_hypotheses))
        object.__setattr__(self, "transfer_candidates", tuple(self.transfer_candidates))

        posts_by_id = {post.post_observation_id: post for post in self.posts}
        if len(posts_by_id) != len(self.posts):
            raise ValueError("post observation ids must be unique")
        if set(posts_by_id) != set(self.sampling_frame.included_post_ids):
            raise ValueError("bundle posts must match the sampling frame included posts")
        for post in self.posts:
            _same_scope(post, owner_id=owner_id, project_id=project_id, label="post observation")
            if post.snapshot_id != self.snapshot.snapshot_id:
                raise ValueError("post observation references a different account snapshot")
            if post.author_platform_account_id is not None and self.snapshot.platform_account_id is not None and post.author_platform_account_id != self.snapshot.platform_account_id:
                raise ValueError("post author identity does not match the account snapshot")

        for atom_set in self.media_atom_sets:
            _same_scope(atom_set, owner_id=owner_id, project_id=project_id, label="media atom set")
            if atom_set.post_observation_id not in posts_by_id:
                raise ValueError("media atom set references a post outside the sampled posts")
            if atom_set.input_hash != posts_by_id[atom_set.post_observation_id].content_hash:
                raise ValueError("media atom input_hash does not match the sampled post")

        known_evidence_refs = {
            self.snapshot.snapshot_id,
            self.snapshot.source_ref,
            self.sampling_frame.frame_id,
            *self.snapshot.identity_evidence_refs,
            *self.sampling_frame.source_refs,
        }
        for post in self.posts:
            known_evidence_refs.update(
                (
                    post.post_observation_id,
                    post.source_ref,
                    *post.artifact_refs,
                    *(metric.source_ref for metric in post.metrics),
                )
            )
        for atom_set in self.media_atom_sets:
            known_evidence_refs.add(atom_set.atom_set_id)
            for receipt in atom_set.receipts:
                known_evidence_refs.update(receipt.artifact_refs)

        patterns_by_id = {pattern.pattern_hypothesis_id: pattern for pattern in self.pattern_hypotheses}
        if len(patterns_by_id) != len(self.pattern_hypotheses):
            raise ValueError("pattern hypothesis ids must be unique")
        for pattern in self.pattern_hypotheses:
            _same_scope(pattern, owner_id=owner_id, project_id=project_id, label="pattern hypothesis")
            if pattern.snapshot_id != self.snapshot.snapshot_id or pattern.frame_id != self.sampling_frame.frame_id:
                raise ValueError("pattern hypothesis references a different snapshot or sampling frame")
            referenced_posts = set(pattern.supporting_post_ids).union(pattern.counterexample_post_ids)
            if not referenced_posts.issubset(posts_by_id):
                raise ValueError("pattern hypothesis references posts outside the sampled posts")
            if not set(pattern.evidence_refs).issubset(known_evidence_refs):
                raise ValueError("pattern hypothesis references unknown evidence refs")

        transfer_evidence_refs = known_evidence_refs.union(patterns_by_id)

        for candidate in self.transfer_candidates:
            _same_scope(candidate, owner_id=owner_id, project_id=project_id, label="transfer candidate")
            if candidate.source_snapshot_id != self.snapshot.snapshot_id:
                raise ValueError("transfer candidate references a different source snapshot")
            if not set(candidate.pattern_hypothesis_ids).issubset(patterns_by_id):
                raise ValueError("transfer candidate references an unknown pattern hypothesis")
            if not set(candidate.evidence_refs).issubset(transfer_evidence_refs):
                raise ValueError("transfer candidate references unknown evidence refs")

    @property
    def warnings(self) -> tuple[EvidenceWarning, ...]:
        warnings: list[EvidenceWarning] = []
        if self.snapshot.identity_status is not AccountIdentityStatus.CONFIRMED:
            warnings.append(
                EvidenceWarning(
                    code="identity_not_confirmed",
                    message="Account identity remains provisional or ambiguous.",
                    evidence_refs=(self.snapshot.snapshot_id,),
                )
            )
        if self.snapshot.platform_account_id is None or any(post.author_platform_account_id is None for post in self.posts):
            warnings.append(
                EvidenceWarning(
                    code="author_identity_unverified",
                    message="The profile or one of its sampled posts lacks a verifiable platform account id.",
                    evidence_refs=(
                        self.snapshot.snapshot_id,
                        *(post.post_observation_id for post in self.posts if post.author_platform_account_id is None),
                    ),
                )
            )
        coverage = self.sampling_frame.coverage_ratio
        if coverage is None:
            warnings.append(
                EvidenceWarning(
                    code="coverage_unknown",
                    message="Visible account inventory is unknown, so sample coverage cannot be calculated.",
                    evidence_refs=(self.sampling_frame.frame_id,),
                )
            )
        elif coverage < 1:
            warnings.append(
                EvidenceWarning(
                    code="partial_capture",
                    message=f"The sample covers {coverage:.3f} of the visible inventory at capture time.",
                    evidence_refs=(self.sampling_frame.frame_id,),
                )
            )
        if self.sampling_frame.missing_reasons:
            warnings.append(
                EvidenceWarning(
                    code="capture_gap",
                    message=" ".join(self.sampling_frame.missing_reasons),
                    evidence_refs=(self.sampling_frame.frame_id,),
                )
            )
        for post in self.posts:
            if post.missing_metrics:
                warnings.append(
                    EvidenceWarning(
                        code="missing_public_metrics",
                        message=f"Missing metrics: {', '.join(post.missing_metrics)}.",
                        evidence_refs=(post.post_observation_id,),
                    )
                )
            if len({metric.captured_at for metric in post.metrics}) > 1:
                warnings.append(
                    EvidenceWarning(
                        code="metric_capture_time_mismatch",
                        message="Public metrics were captured at different times and must not be compared as one snapshot.",
                        evidence_refs=(post.post_observation_id,),
                    )
                )
        for atom_set in self.media_atom_sets:
            if atom_set.gaps:
                warnings.append(
                    EvidenceWarning(
                        code="media_atom_gap",
                        message="; ".join(f"{gap.capability}: {gap.reason}" for gap in atom_set.gaps),
                        evidence_refs=(atom_set.atom_set_id,),
                    )
                )
            if atom_set.conflicts:
                warnings.append(
                    EvidenceWarning(
                        code="modality_conflict",
                        message=" ".join(atom_set.conflicts),
                        evidence_refs=(atom_set.atom_set_id,),
                    )
                )
        for pattern in self.pattern_hypotheses:
            if not pattern.counterexample_post_ids:
                warnings.append(
                    EvidenceWarning(
                        code="pattern_without_counterexample",
                        message="No sampled counterexample is attached; keep the pattern provisional.",
                        evidence_refs=(pattern.pattern_hypothesis_id,),
                    )
                )
        return tuple(warnings)


__all__ = [
    "AccountEvidenceBundle",
    "AccountIdentityStatus",
    "AccountPatternHypothesis",
    "AccountSnapshot",
    "EvidenceWarning",
    "MediaAtomGap",
    "MediaAtomReceipt",
    "MediaAtomSet",
    "MediaExecutionMode",
    "MetricObservation",
    "PostObservation",
    "SamplingFrame",
    "SocialPlatform",
    "TransferCandidate",
]
