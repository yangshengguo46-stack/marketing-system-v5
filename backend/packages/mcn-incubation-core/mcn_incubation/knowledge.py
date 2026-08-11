"""Reviewed source metadata for incubation methods and external evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

V4_STRATEGY_SOURCE_ID = "V4@58f4e0c9:skills/public/ip-strategy-director/SKILL.md"
V4_JUDGMENT_SOURCE_ID = "V4@58f4e0c9:skills/public/ip-strategy-director/references/strategy-judgment.md"
V4_PILOT_SOURCE_ID = "V4@58f4e0c9:skills/public/ip-strategy-director/references/benchmark-and-launch.md"
V4_ASSET_SOURCE_ID = "V4@58f4e0c9:product/research/ip-agent/IP_AGENT_INFLUENCE_ASSET_FIRST_PRINCIPLES_RESEARCH.md"
V5_PREFLIGHT_SOURCE_ID = "V5:docs/mcn-incubation-v5/evidence/2026-08-10-preflight-quality-review.md"
V5_M01_AGENT_EVAL_SOURCE_ID = "V5:docs/mcn-incubation-v5/evidence/2026-08-11-m01-agent-evaluation.md"
XHS_MCN_INTRO_SOURCE_ID = "url:https://creator.xiaohongshu.com/mcn-introduce?source=agora"
MCN_GATEKEEPING_RESEARCH_SOURCE_ID = "doi:10.1080/1369118X.2024.2396614"
TIKTOK_COMMERCIAL_QUALITY_SOURCE_ID = "url:https://ads.tiktok.com/help/article/about-tiktoks-content-quality-standard-for-creator-commercial-content"

_LOCAL_REVIEWED_AT = datetime(2026, 8, 10, 16, 0, tzinfo=UTC)
_WEB_REVIEWED_AT = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
_PLATFORM_REFRESH_AFTER = datetime(2026, 9, 10, 10, 0, tzinfo=UTC)


def _required(value: str, *, field_name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} cannot be blank")
    return normalized


def _texts(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(_required(value, field_name=field_name) for value in values))
    return normalized


def _aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class KnowledgeSourceKind(StrEnum):
    OFFICIAL_PLATFORM = "official_platform"
    PEER_REVIEWED_RESEARCH = "peer_reviewed_research"
    AUDITED_LOCAL_METHOD = "audited_local_method"
    INTERNAL_EVIDENCE = "internal_evidence"


class KnowledgeSourceStatus(StrEnum):
    ACTIVE = "active"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class UnknownKnowledgeSource(ValueError):
    """A method cites a source absent from the reviewed catalog."""


class InactiveKnowledgeSource(ValueError):
    """A method cites a source that has been superseded or retired."""


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    source_id: str
    kind: KnowledgeSourceKind
    title: str
    locator: str
    publisher: str
    retrieved_at: datetime
    reviewed_at: datetime
    supported_claims: tuple[str, ...]
    limitations: tuple[str, ...]
    status: KnowledgeSourceStatus = KnowledgeSourceStatus.ACTIVE
    applicable_platforms: tuple[str, ...] = field(default_factory=tuple)
    applicable_regions: tuple[str, ...] = field(default_factory=tuple)
    source_updated_label: str | None = None
    refresh_after: datetime | None = None
    supersedes_source_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "locator", "publisher"):
            object.__setattr__(self, name, _required(getattr(self, name), field_name=name))
        _aware(self.retrieved_at, field_name="retrieved_at")
        _aware(self.reviewed_at, field_name="reviewed_at")
        if self.reviewed_at < self.retrieved_at:
            raise ValueError("reviewed_at cannot precede retrieved_at")
        for name in (
            "supported_claims",
            "limitations",
            "applicable_platforms",
            "applicable_regions",
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), field_name=name))
        if not self.supported_claims:
            raise ValueError("knowledge source requires at least one supported claim")
        if not self.limitations:
            raise ValueError("knowledge source requires at least one limitation")
        if self.kind is KnowledgeSourceKind.OFFICIAL_PLATFORM and not self.applicable_platforms:
            raise ValueError("official platform source requires applicable_platforms")
        if self.source_updated_label is not None:
            object.__setattr__(
                self,
                "source_updated_label",
                _required(self.source_updated_label, field_name="source_updated_label"),
            )
        if self.refresh_after is not None:
            _aware(self.refresh_after, field_name="refresh_after")
            if self.refresh_after <= self.retrieved_at:
                raise ValueError("refresh_after must follow retrieved_at")
        if self.supersedes_source_id is not None:
            object.__setattr__(
                self,
                "supersedes_source_id",
                _required(self.supersedes_source_id, field_name="supersedes_source_id"),
            )

    def is_refresh_due(self, *, as_of: datetime) -> bool:
        """Return whether a time-sensitive source needs another review."""
        _aware(as_of, field_name="as_of")
        return self.refresh_after is not None and as_of >= self.refresh_after


class KnowledgeCatalog:
    """Resolve reviewed sources without treating retrieval rank as truth."""

    def __init__(self, sources: tuple[KnowledgeSource, ...]) -> None:
        if len({source.source_id for source in sources}) != len(sources):
            raise ValueError("knowledge source ids must be unique")
        self._sources = sources
        self._by_id = {source.source_id: source for source in sources}
        for source in sources:
            if source.supersedes_source_id is not None and source.supersedes_source_id not in self._by_id:
                raise UnknownKnowledgeSource(source.supersedes_source_id)

    @property
    def sources(self) -> tuple[KnowledgeSource, ...]:
        return self._sources

    def get(self, source_id: str) -> KnowledgeSource:
        try:
            return self._by_id[source_id]
        except KeyError as exc:
            raise UnknownKnowledgeSource(source_id) from exc

    def resolve(self, source_ids: tuple[str, ...]) -> tuple[KnowledgeSource, ...]:
        resolved: list[KnowledgeSource] = []
        for source_id in dict.fromkeys(source_ids):
            source = self.get(source_id)
            if source.status in {KnowledgeSourceStatus.SUPERSEDED, KnowledgeSourceStatus.RETIRED}:
                raise InactiveKnowledgeSource(source_id)
            resolved.append(source)
        return tuple(resolved)


def default_knowledge_sources() -> tuple[KnowledgeSource, ...]:
    """Return the reviewed source manifest used by the default method cards."""

    return (
        KnowledgeSource(
            source_id=V4_STRATEGY_SOURCE_ID,
            kind=KnowledgeSourceKind.AUDITED_LOCAL_METHOD,
            title="IP strategy director",
            locator=V4_STRATEGY_SOURCE_ID,
            publisher="Audited V4 repository snapshot",
            retrieved_at=_LOCAL_REVIEWED_AT,
            reviewed_at=_LOCAL_REVIEWED_AT,
            supported_claims=(
                "Use supplied facts before generic intake and separate the IP subject from its expression carrier.",
                "Keep facts, inference, creative hypotheses, and unknowns distinct while recommending one working direction.",
            ),
            limitations=("This is an audited method artifact from the failed V4 system, not an observed business outcome or mandatory workflow.",),
        ),
        KnowledgeSource(
            source_id=V4_JUDGMENT_SOURCE_ID,
            kind=KnowledgeSourceKind.AUDITED_LOCAL_METHOD,
            title="Strategy judgment reference",
            locator=V4_JUDGMENT_SOURCE_ID,
            publisher="Audited V4 repository snapshot",
            retrieved_at=_LOCAL_REVIEWED_AT,
            reviewed_at=_LOCAL_REVIEWED_AT,
            supported_claims=(
                "Compare paid problem, proof, perceptible difference, offer fit, content supply, conversion continuity, and durability.",
                "Prefer observed sales, delivery, audience behavior, and demonstrated work over untested hypotheses.",
            ),
            limitations=("The dimensions are decision lenses, not causal proof, a numeric score, or an admission gate.",),
        ),
        KnowledgeSource(
            source_id=V4_PILOT_SOURCE_ID,
            kind=KnowledgeSourceKind.AUDITED_LOCAL_METHOD,
            title="Benchmark and pilot reference",
            locator=V4_PILOT_SOURCE_ID,
            publisher="Audited V4 repository snapshot",
            retrieved_at=_LOCAL_REVIEWED_AT,
            reviewed_at=_LOCAL_REVIEWED_AT,
            supported_claims=(
                "Verify the exact profile and representative works before claiming an account pattern.",
                "Transfer a benchmark's function into an original pilot instead of copying its expression or identity signals.",
            ),
            limitations=("The reference does not guarantee platform access, metric availability, or that any benchmark mechanism transfers to a new subject.",),
        ),
        KnowledgeSource(
            source_id=V4_ASSET_SOURCE_ID,
            kind=KnowledgeSourceKind.AUDITED_LOCAL_METHOD,
            title="Influence asset first-principles research",
            locator=V4_ASSET_SOURCE_ID,
            publisher="Audited V4 repository snapshot",
            retrieved_at=_LOCAL_REVIEWED_AT,
            reviewed_at=_LOCAL_REVIEWED_AT,
            supported_claims=(
                "People, brands, products, methods, and organizations can accumulate distinct attribution, meaning, relationships, and behavior effects.",
                "Reach or one transaction alone does not prove a durable IP asset.",
            ),
            limitations=("The source is explicitly research_quarantined; historical implementation claims are stale and its product definitions are not legal or financial advice.",),
        ),
        KnowledgeSource(
            source_id=V5_PREFLIGHT_SOURCE_ID,
            kind=KnowledgeSourceKind.INTERNAL_EVIDENCE,
            title="Fifth-version preflight quality review",
            locator="docs/mcn-incubation-v5/evidence/2026-08-10-preflight-quality-review.md",
            publisher="Fifth-version local evaluation ledger",
            retrieved_at=_LOCAL_REVIEWED_AT,
            reviewed_at=_LOCAL_REVIEWED_AT,
            supported_claims=("The evaluated model invented unsupported assets, effects, fulfillment details, and thresholds under several prompt-only variants.",),
            limitations=("This is a small model- and case-specific evaluation; it identifies regressions but does not establish a universal causal law.",),
        ),
        KnowledgeSource(
            source_id=V5_M01_AGENT_EVAL_SOURCE_ID,
            kind=KnowledgeSourceKind.INTERNAL_EVIDENCE,
            title="M01 full-agent evaluation review",
            locator="docs/mcn-incubation-v5/evidence/2026-08-11-m01-agent-evaluation.md",
            publisher="Fifth-version local evaluation ledger",
            retrieved_at=_LOCAL_REVIEWED_AT,
            reviewed_at=_LOCAL_REVIEWED_AT,
            supported_claims=(
                "The evaluated Lead Agent read project facts and relevant methods but still inferred platform fit, camera willingness, publishable cases, sustainable supply, and arbitrary metric thresholds.",
                "The evaluated answer treated exposure, interaction, and inquiry thresholds as interchangeable proof that paid demand existed.",
            ),
            limitations=("This is one sealed case and model run; it is regression evidence, not a general causal law or a successful incubation outcome.",),
        ),
        KnowledgeSource(
            source_id=XHS_MCN_INTRO_SOURCE_ID,
            kind=KnowledgeSourceKind.OFFICIAL_PLATFORM,
            title="Xiaohongshu MCN introduction",
            locator="https://creator.xiaohongshu.com/mcn-introduce?source=agora",
            publisher="Xiaohongshu Creator Service Platform",
            retrieved_at=_WEB_REVIEWED_AT,
            reviewed_at=_WEB_REVIEWED_AT,
            supported_claims=("Xiaohongshu describes official MCN cooperation around creator incubation, content incubation, and content monetization.",),
            limitations=("This is a platform program description. It does not establish audience composition, category demand, platform fit, or platform priority for a project, and features and terms can change.",),
            applicable_platforms=("xiaohongshu",),
            applicable_regions=("CN",),
            refresh_after=_PLATFORM_REFRESH_AFTER,
        ),
        KnowledgeSource(
            source_id=MCN_GATEKEEPING_RESEARCH_SOURCE_ID,
            kind=KnowledgeSourceKind.PEER_REVIEWED_RESEARCH,
            title="Manufacturing influencers: the gatekeeping roles of MCNs in cultural production",
            locator="https://doi.org/10.1080/1369118X.2024.2396614",
            publisher="Information, Communication & Society",
            retrieved_at=_WEB_REVIEWED_AT,
            reviewed_at=_WEB_REVIEWED_AT,
            supported_claims=(
                "The study conceptualizes MCN influencer manufacturing as interdependent talent incubation, content optimization, and platform monetization.",
                "MCNs can professionalize creators while also restricting creative autonomy and creating power asymmetry.",
            ),
            limitations=("This is descriptive research on Chinese MCN gatekeeping, not a causal recipe or justification for overriding creator agency.",),
            applicable_regions=("CN",),
            source_updated_label="2024 journal publication",
        ),
        KnowledgeSource(
            source_id=TIKTOK_COMMERCIAL_QUALITY_SOURCE_ID,
            kind=KnowledgeSourceKind.OFFICIAL_PLATFORM,
            title="TikTok content quality standard for creator commercial content",
            locator="https://ads.tiktok.com/help/article/about-tiktoks-content-quality-standard-for-creator-commercial-content",
            publisher="TikTok For Business",
            retrieved_at=_WEB_REVIEWED_AT,
            reviewed_at=_WEB_REVIEWED_AT,
            supported_claims=("TikTok's commercial-content standard emphasizes authentic actual use or empirical evidence, useful product context, and coherent image, sound, and content quality.",),
            limitations=("The page concerns creator commercial content reviewed through TikTok Creator Marketplace or TikTok One; it is not a universal ranking formula and availability can vary by market.",),
            applicable_platforms=("tiktok",),
            source_updated_label="May 2026",
            refresh_after=_PLATFORM_REFRESH_AFTER,
        ),
    )


def default_knowledge_catalog() -> KnowledgeCatalog:
    return KnowledgeCatalog(default_knowledge_sources())


__all__ = [
    "InactiveKnowledgeSource",
    "KnowledgeCatalog",
    "KnowledgeSource",
    "KnowledgeSourceKind",
    "KnowledgeSourceStatus",
    "MCN_GATEKEEPING_RESEARCH_SOURCE_ID",
    "TIKTOK_COMMERCIAL_QUALITY_SOURCE_ID",
    "UnknownKnowledgeSource",
    "V4_ASSET_SOURCE_ID",
    "V4_JUDGMENT_SOURCE_ID",
    "V4_PILOT_SOURCE_ID",
    "V4_STRATEGY_SOURCE_ID",
    "V5_PREFLIGHT_SOURCE_ID",
    "V5_M01_AGENT_EVAL_SOURCE_ID",
    "XHS_MCN_INTRO_SOURCE_ID",
    "default_knowledge_catalog",
    "default_knowledge_sources",
]
