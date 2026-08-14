"""User-reviewable annotations for marketing semantic development evidence.

These records are evaluation data, not model context or runtime workflow state.
They preserve valid alternatives and distinguish an object map from the
audience-facing account territory.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256

ROOT_KINDS = frozenset({"object", "practice_or_need", "result"})
DECISION_SCOPES = frozenset({"object_world", "audience_world"})
REVIEW_STATUSES = frozenset({"user_reviewed_development", "preregistered_system_hypothesis"})


@dataclass(frozen=True, slots=True)
class RootCandidateAnnotation:
    candidate_id: str
    term: str
    root_kind: str
    derivation: str
    capacity_axes: tuple[str, ...]
    business_return_path: str | None
    conditions: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    scope: str
    preferred_candidate_ids: tuple[str, ...]
    acceptable_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class MarketingSemanticAnnotation:
    case_id: str
    utterance: str
    observed_facts: tuple[str, ...]
    source_object: str
    lexical_head: str
    candidates: tuple[RootCandidateAnnotation, ...]
    scope_decisions: tuple[ScopeDecision, ...]
    unknowns: tuple[str, ...]
    review_status: str
    evidence_refs: tuple[str, ...]

    def decision(self, scope: str) -> ScopeDecision:
        for decision in self.scope_decisions:
            if decision.scope == scope:
                return decision
        raise KeyError(scope)


def _require_text(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _require_text_tuple(value: tuple[str, ...], *, field: str, allow_empty: bool = True) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    if not allow_empty and not value:
        raise ValueError(f"{field} must not be empty")
    for index, item in enumerate(value):
        _require_text(item, field=f"{field}[{index}]")


def validate_annotation(annotation: MarketingSemanticAnnotation) -> MarketingSemanticAnnotation:
    for field in ("case_id", "utterance", "source_object", "lexical_head"):
        _require_text(getattr(annotation, field), field=field)
    _require_text_tuple(annotation.observed_facts, field="observed_facts", allow_empty=False)
    _require_text_tuple(annotation.unknowns, field="unknowns")
    _require_text_tuple(annotation.evidence_refs, field="evidence_refs", allow_empty=False)
    if annotation.review_status not in REVIEW_STATUSES:
        raise ValueError(f"unsupported review_status: {annotation.review_status}")
    if not annotation.candidates:
        raise ValueError("candidates must not be empty")

    candidate_ids: list[str] = []
    for index, candidate in enumerate(annotation.candidates):
        _require_text(candidate.candidate_id, field=f"candidates[{index}].candidate_id")
        _require_text(candidate.term, field=f"candidates[{index}].term")
        _require_text(candidate.derivation, field=f"candidates[{index}].derivation")
        if candidate.root_kind not in ROOT_KINDS:
            raise ValueError(f"unsupported root_kind: {candidate.root_kind}")
        _require_text_tuple(
            candidate.capacity_axes,
            field=f"candidates[{index}].capacity_axes",
            allow_empty=False,
        )
        if candidate.business_return_path is not None:
            _require_text(
                candidate.business_return_path,
                field=f"candidates[{index}].business_return_path",
            )
        _require_text_tuple(candidate.conditions, field=f"candidates[{index}].conditions")
        _require_text_tuple(candidate.risks, field=f"candidates[{index}].risks")
        candidate_ids.append(candidate.candidate_id)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate ids must be unique")

    scopes = [decision.scope for decision in annotation.scope_decisions]
    if set(scopes) != DECISION_SCOPES or len(scopes) != len(DECISION_SCOPES):
        raise ValueError("scope_decisions must contain object_world and audience_world exactly once")
    known_ids = set(candidate_ids)
    for decision in annotation.scope_decisions:
        _require_text(decision.rationale, field=f"{decision.scope}.rationale")
        if not decision.preferred_candidate_ids:
            raise ValueError(f"{decision.scope} preferred_candidate_ids must not be empty")
        groups = (
            set(decision.preferred_candidate_ids),
            set(decision.acceptable_candidate_ids),
            set(decision.rejected_candidate_ids),
        )
        referenced = set().union(*groups)
        unknown_ids = sorted(referenced - known_ids)
        if unknown_ids:
            raise ValueError(f"{decision.scope} references unknown candidate ids: {', '.join(unknown_ids)}")
        if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
            raise ValueError(f"{decision.scope} decision id groups must not overlap")
    return annotation


def annotation_fingerprint(annotation: MarketingSemanticAnnotation) -> str:
    validate_annotation(annotation)
    payload = json.dumps(asdict(annotation), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _candidate(
    candidate_id: str,
    term: str,
    root_kind: str,
    derivation: str,
    capacity_axes: tuple[str, ...],
    business_return_path: str | None,
    *,
    conditions: tuple[str, ...] = (),
    risks: tuple[str, ...] = (),
) -> RootCandidateAnnotation:
    return RootCandidateAnnotation(
        candidate_id=candidate_id,
        term=term,
        root_kind=root_kind,
        derivation=derivation,
        capacity_axes=capacity_axes,
        business_return_path=business_return_path,
        conditions=conditions,
        risks=risks,
    )


def _decision(
    scope: str,
    preferred: tuple[str, ...],
    acceptable: tuple[str, ...],
    rejected: tuple[str, ...],
    rationale: str,
) -> ScopeDecision:
    return ScopeDecision(
        scope=scope,
        preferred_candidate_ids=preferred,
        acceptable_candidate_ids=acceptable,
        rejected_candidate_ids=rejected,
        rationale=rationale,
    )


DEFAULT_DEVELOPMENT_ANNOTATIONS = (
    MarketingSemanticAnnotation(
        case_id="fruit-shop",
        utterance="我是一个开水果店的，有什么起号建议？",
        observed_facts=("主体经营水果店",),
        source_object="水果店经营中的水果",
        lexical_head="水果店",
        candidates=(
            _candidate(
                "fruit",
                "水果",
                "object",
                "去掉经营容器后，实际商品是水果；水果自身已经构成完整且宽阔的对象世界。",
                ("种类", "时令与历史", "地域与饮食习惯", "人物事件与冲突"),
                "水果世界中的具体对象可自然回到店内经营的水果。",
            ),
            _candidate(
                "store-operations",
                "水果店经营流程",
                "practice_or_need",
                "从开店动作可联想到经营，但用户没有说明自己掌握或愿意公开哪些流程。",
                ("选品", "陈列", "损耗"),
                None,
                risks=("把经营载体和卖方操作误当成观众长期进入的世界",),
            ),
            _candidate(
                "generic-consumption",
                "消费生活方式",
                "practice_or_need",
                "从食用水果继续向上抽象得到，但已经丢失水果的品类特异性。",
                ("日常消费", "生活场景"),
                None,
                risks=("过宽且无法解释为什么必须回到水果生意",),
            ),
        ),
        scope_decisions=(
            _decision(
                "object_world",
                ("fruit",),
                (),
                ("store-operations", "generic-consumption"),
                "水果是最小完整对象，门店只是经营容器。",
            ),
            _decision(
                "audience_world",
                ("fruit",),
                (),
                ("store-operations", "generic-consumption"),
                "观众可长期进入水果本身的种类、时空、文化和人物事件世界。",
            ),
        ),
        unknowns=("货品结构", "经营与拍摄资源", "主体希望服务的人群"),
        review_status="user_reviewed_development",
        evidence_refs=("LEDGER:E18-R4", "A34"),
    ),
    MarketingSemanticAnnotation(
        case_id="gold-gift",
        utterance="我是一个做黄金礼品加工的，你有什么起号建议？",
        observed_facts=("主体从事黄金礼品加工",),
        source_object="黄金礼品",
        lexical_head="礼品",
        candidates=(
            _candidate(
                "gift-object",
                "礼品",
                "object",
                "黄金说明材质与价值，礼品说明该商品被作为赠予物使用。",
                ("礼品种类", "场合", "关系", "历史与文化"),
                "不同礼品选择与黄金礼品存在直接品类回路。",
            ),
            _candidate(
                "gifting-practice",
                "送礼与人情往来",
                "practice_or_need",
                "礼品存在的直接社会用途是赠予，赠予跨人物、关系、场合、规则与冲突反复发生。",
                ("人生节点", "关系远近", "礼仪规则", "历史与跨文化赠予"),
                "观众形成送礼需求与判断时，黄金礼品是可承接的解决方案之一。",
            ),
            _candidate(
                "gold-craft",
                "黄金加工工艺",
                "practice_or_need",
                "加工是题目明确的卖方动作，可提供专业证明，但不自动解释礼品为何被需要。",
                ("加工步骤", "工具", "材质处理"),
                None,
                conditions=("用户确实拥有并可公开相应工艺证据",),
                risks=("把能力证明替换成账号的观众世界",),
            ),
            _candidate(
                "generic-emotion",
                "情绪价值",
                "result",
                "从赠礼继续抽象得到，但没有保留具体关系行为与礼品回路。",
                ("情感", "关系"),
                None,
                risks=("过宽且不可操作",),
            ),
        ),
        scope_decisions=(
            _decision(
                "object_world",
                ("gift-object",),
                ("gifting-practice",),
                ("gold-craft", "generic-emotion"),
                "对象地图先保留礼品，送礼是其向上且紧密的社会用途。",
            ),
            _decision(
                "audience_world",
                ("gifting-practice",),
                ("gift-object",),
                ("gold-craft", "generic-emotion"),
                "账号要占领的是送礼与人情判断，礼品对象世界仍是合理的近端内容层。",
            ),
        ),
        unknowns=("客户结构", "可验证工艺与案例", "主体表达和制作条件"),
        review_status="user_reviewed_development",
        evidence_refs=("LEDGER:E18-R4", "A34", "user-thread:019ff0ac-ebbf-7520-bae5-2b91f1c4da57"),
    ),
    MarketingSemanticAnnotation(
        case_id="seafood-source",
        utterance="我是做海鲜源头养殖或者捕捞的，B和C都做，我要怎么起号？",
        observed_facts=("主体从事海鲜源头业务", "养殖或捕捞尚未确认", "同时面向B端和C端"),
        source_object="海鲜",
        lexical_head="海鲜",
        candidates=(
            _candidate(
                "seafood",
                "海鲜",
                "object",
                "海鲜本身已经是由大量物种、地域、历史和饮食文化组成的完整对象世界。",
                ("种类", "海域与地域", "历史", "各地饮食习惯", "人物事件与冲突"),
                "具体海鲜对象可回到主体经营的海鲜业务。",
            ),
            _candidate(
                "source-operations",
                "养殖捕捞与供应链",
                "practice_or_need",
                "题目只说明养殖或捕捞的未决来源身份，不能推出两类能力、现场或稳定素材。",
                ("养殖", "捕捞", "流通"),
                None,
                risks=("把未决卖方动作补成事实并压窄海鲜世界",),
            ),
            _candidate(
                "freshness-proof",
                "新鲜品质证明",
                "result",
                "品质可以是信任议题，但题目没有提供主体的证据或差异。",
                ("品质", "来源"),
                None,
                risks=("退化成挑选避坑或供应链模板",),
            ),
        ),
        scope_decisions=(
            _decision(
                "object_world",
                ("seafood",),
                (),
                ("source-operations", "freshness-proof"),
                "海鲜对象自身具有最大的有效且仍能回到业务的内容容量。",
            ),
            _decision(
                "audience_world",
                ("seafood",),
                (),
                ("source-operations", "freshness-proof"),
                "源头和B/C影响定位、证据与承接，不替换海鲜这一观众内容世界。",
            ),
        ),
        unknowns=("具体品类", "实际生产方式", "可验证来源与素材"),
        review_status="user_reviewed_development",
        evidence_refs=("LEDGER:E18-R4", "A34"),
    ),
    MarketingSemanticAnnotation(
        case_id="chongqing-hotpot-base",
        utterance="我是卖重庆火锅底料的，想做一个账号，内容应该围绕什么展开？",
        observed_facts=("主体销售重庆火锅底料",),
        source_object="重庆火锅底料",
        lexical_head="底料",
        candidates=(
            _candidate(
                "hotpot",
                "火锅",
                "object",
                "底料是完成火锅的中间商品，重庆是地域风味修饰，火锅才是更完整的终端对象世界。",
                ("种类", "历史", "地域与民族", "各国饮食习惯", "人物事件与冲突"),
                "所有火锅内容都可通过做法与风味自然回到重庆火锅底料。",
            ),
            _candidate(
                "hotpot-base",
                "火锅底料",
                "object",
                "它是实际商品形态，但只停在配方、原料和制作会把完整火锅世界压窄。",
                ("原料", "风味", "制作"),
                "直接回到商品，但内容容量小于上层火锅对象。",
                risks=("中间物冒充完整对象",),
            ),
            _candidate(
                "chongqing-cuisine",
                "重庆饮食",
                "object",
                "从地域修饰向外扩张得到，但会把非火锅内容也纳入。",
                ("地域", "菜系"),
                None,
                risks=("地域修饰抢根并稀释火锅",),
            ),
            _candidate(
                "generic-dining",
                "餐饮生活方式",
                "practice_or_need",
                "从吃火锅继续向上抽象得到，但失去品类边界。",
                ("聚餐", "生活"),
                None,
                risks=("空泛且无法解释底料的独特回路",),
            ),
        ),
        scope_decisions=(
            _decision(
                "object_world",
                ("hotpot",),
                (),
                ("hotpot-base", "chongqing-cuisine", "generic-dining"),
                "中间底料应回到完整火锅，重庆保留为重要分支。",
            ),
            _decision(
                "audience_world",
                ("hotpot",),
                (),
                ("hotpot-base", "chongqing-cuisine", "generic-dining"),
                "观众进入的是火锅的完整内容世界，而不是底料说明书或泛餐饮。",
            ),
        ),
        unknowns=("生产方式", "具体产品差异", "主体可验证经验"),
        review_status="user_reviewed_development",
        evidence_refs=("LEDGER:E18-R4", "A34"),
    ),
    MarketingSemanticAnnotation(
        case_id="watch-business",
        utterance="我是做腕表的，该怎么起号？",
        observed_facts=("主体从事腕表相关业务",),
        source_object="腕表",
        lexical_head="腕表",
        candidates=(
            _candidate(
                "watches",
                "腕表",
                "object",
                "腕表自身包含品类、技术、历史、地域、文化、人物、事件与冲突。",
                ("种类", "技术与审美", "历史与地域", "人物事件", "消费与文化冲突"),
                "腕表世界中的判断与故事可自然回到主体的腕表业务。",
            ),
            _candidate(
                "watch-trading",
                "腕表交易与行情",
                "practice_or_need",
                "交易是可能的业务动作，但用户没有说明经营模式或数据能力。",
                ("行情", "买卖"),
                None,
                conditions=("主体确实从事并能验证相关交易业务",),
                risks=("用未确认经营动作压窄完整腕表世界",),
            ),
            _candidate(
                "wealth-lifestyle",
                "财富与奢侈生活方式",
                "practice_or_need",
                "由腕表的部分社会符号继续抽象得到，但不是所有腕表内容的共同根。",
                ("财富", "身份"),
                None,
                risks=("刻板化受众并脱离腕表专业内容",),
            ),
        ),
        scope_decisions=(
            _decision(
                "object_world",
                ("watches",),
                (),
                ("watch-trading", "wealth-lifestyle"),
                "腕表是可长期展开的完整对象。",
            ),
            _decision(
                "audience_world",
                ("watches",),
                (),
                ("watch-trading", "wealth-lifestyle"),
                "账号可用人物化表达进入腕表世界，但表现与内容主语不能混为一层。",
            ),
        ),
        unknowns=("具体业务模式", "主体专业证据", "表达与制作条件"),
        review_status="user_reviewed_development",
        evidence_refs=("LEDGER:E25", "A39"),
    ),
    MarketingSemanticAnnotation(
        case_id="medical-aesthetics-business",
        utterance="我是做医美的，该怎么起号？",
        observed_facts=("主体从事医美业务",),
        source_object="医美",
        lexical_head="医美",
        candidates=(
            _candidate(
                "medical-aesthetics",
                "医美",
                "object",
                "医美是用户明确从事的业务对象，可形成项目、认知、风险与行业对象地图。",
                ("需求类型", "技术与风险研究", "历史与审美观念", "人物事件"),
                "医美知识和判断可直接回到医美服务。",
                conditions=("医学内容必须由合格来源核验",),
            ),
            _candidate(
                "beauty",
                "变美",
                "result",
                "普通人关注医美的直接进展是外貌与美的变化，内容可扩展到保养、衰老、人物和文化审美。",
                ("日常保养", "衰老与抗衰", "人物外貌", "地域与文化审美"),
                "当观众形成变美需求并需要专业解决方案时，可自然回到医美业务。",
                conditions=("具体医学主张和人物事实必须核验",),
            ),
            _candidate(
                "procedure-catalog",
                "医美项目目录",
                "object",
                "由业务中的具体项目向下枚举得到，但不能单独构成最大有效观众世界。",
                ("项目", "步骤"),
                "能回到服务，但容易退化成说明书。",
                risks=("只讲项目和术式，忽略普通人为什么关注",),
            ),
            _candidate(
                "generic-confidence",
                "自信与人生改变",
                "result",
                "从变美继续向上抽象得到，但题目没有证明这种结果。",
                ("情绪", "人生"),
                None,
                risks=("过度承诺且丢失医美边界",),
            ),
        ),
        scope_decisions=(
            _decision(
                "object_world",
                ("medical-aesthetics",),
                ("beauty",),
                ("procedure-catalog", "generic-confidence"),
                "医美是来源对象及对象地图，变美是紧密的结果世界。",
            ),
            _decision(
                "audience_world",
                ("beauty",),
                ("medical-aesthetics",),
                ("procedure-catalog", "generic-confidence"),
                "账号观众首先进入变美议题，医美负责专业解释和业务承接。",
            ),
        ),
        unknowns=("主体资质与专业边界", "可核验项目与案例", "内容制作条件"),
        review_status="user_reviewed_development",
        evidence_refs=("LEDGER:E28", "A42"),
    ),
)


for _annotation in DEFAULT_DEVELOPMENT_ANNOTATIONS:
    validate_annotation(_annotation)


def default_development_annotations() -> tuple[MarketingSemanticAnnotation, ...]:
    return DEFAULT_DEVELOPMENT_ANNOTATIONS
