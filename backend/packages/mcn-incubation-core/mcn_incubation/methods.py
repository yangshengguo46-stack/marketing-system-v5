"""Curated, source-backed methods that the lead agent retrieves on demand."""

from __future__ import annotations

from mcn_incubation.domain import MethodCard
from mcn_incubation.knowledge import (
    MCN_GATEKEEPING_RESEARCH_SOURCE_ID,
    TIKTOK_COMMERCIAL_QUALITY_SOURCE_ID,
    V4_ASSET_SOURCE_ID,
    V4_JUDGMENT_SOURCE_ID,
    V4_PILOT_SOURCE_ID,
    V4_STRATEGY_SOURCE_ID,
    V5_PREFLIGHT_SOURCE_ID,
    XHS_MCN_INTRO_SOURCE_ID,
    KnowledgeCatalog,
    default_knowledge_catalog,
)


def default_method_cards() -> tuple[MethodCard, ...]:
    """Return the small reviewed method set for the first bakeoff."""

    return (
        MethodCard(
            method_card_id="incubation-model-v1",
            version=1,
            capability="incubation_model",
            title="把主体孵化、内容优化与商业化作为一个可修订系统",
            applies_when=("需要为个人、品牌或产品规划起号与持续经营，而不是只完成一次发布",),
            lens=(
                "同时观察主体能力与自主性、内容和受众适配、商业承接与真实结果",
                "任何一项都不能替代另外两项，且顺序由当前证据和目标决定",
                "把 Agent 建议作为可修订经营判断，不把 MCN 方法变成限制创作者自主性的固定指令",
            ),
            evidence_needs=("主体资源与限制", "内容生产条件", "产品或变现条件", "实际结果"),
            counterexamples=("把批量发布等同于孵化", "用机构模板覆盖主体真实能力和创作自主性"),
            source_refs=(XHS_MCN_INTRO_SOURCE_ID, MCN_GATEKEEPING_RESEARCH_SOURCE_ID),
            search_terms=("孵化", "起号", "冷启动", "MCN", "账号经营", "从零开始"),
        ),
        MethodCard(
            method_card_id="positioning-v1",
            version=2,
            capability="positioning",
            title="从专有事实形成可选择的定位",
            applies_when=("需要决定主体因何被记住和选择",),
            lens=(
                "区分 IP 主体与表达载体",
                "连接真实能力、受众问题、可感知差异和可交付价值",
                "价值承诺不得超出已确认的能力、产品证据和效果边界",
                "给出一个主方向并说明取舍",
            ),
            evidence_needs=("用户事实", "能力或产品证明", "经营目标"),
            counterexamples=("只写人设标签", "把定位分数当准入门槛", "公开配方不等于已证明安全性或效果"),
            source_refs=(V4_STRATEGY_SOURCE_ID, V4_JUDGMENT_SOURCE_ID, V4_ASSET_SOURCE_ID, V5_PREFLIGHT_SOURCE_ID),
            search_terms=("定位", "差异", "主体", "人设", "品牌", "产品"),
        ),
        MethodCard(
            method_card_id="audience-problem-v1",
            version=2,
            capability="audience_problem",
            title="以问题和决策情境理解受众",
            applies_when=("人口标签无法解释为什么观看、信任或购买",),
            lens=(
                "描述受众正在处理的张力、欲望或决策",
                "区分目标假设、公开观察和第一方实际受众",
                "优先提出问题情境假设，人口和年龄标签必须保留为未知直到有证据",
            ),
            evidence_needs=("用户目标", "真实提问", "评论或成交观察"),
            counterexamples=("宝妈天然只关心育儿", "把对标粉丝当作本账号实际受众"),
            source_refs=(V4_STRATEGY_SOURCE_ID, V4_JUDGMENT_SOURCE_ID, V5_PREFLIGHT_SOURCE_ID),
            search_terms=("受众", "用户", "人群", "问题", "需求", "购买者"),
        ),
        MethodCard(
            method_card_id="trust-proof-v1",
            version=1,
            capability="trust_proof",
            title="让价值主张停留在真实经验与可核验证明以内",
            applies_when=("需要解释为什么受众应相信人物、品牌、产品或商业内容",),
            lens=(
                "区分亲身经验、产品机制、第三方证据、实际结果和创意演示",
                "只把证据直接支持的主张交给内容，效果与适用范围缺失时保持未知",
                "平台商业内容指南只能说明该场景下的质量要求，不能当成通用流量公式",
            ),
            evidence_needs=("经验或使用记录", "产品证据", "主张适用范围", "来源与时间"),
            counterexamples=("把公开配方推成安全有效", "把平台质量指南推成必爆公式", "虚构客户证言"),
            source_refs=(
                V4_STRATEGY_SOURCE_ID,
                V4_ASSET_SOURCE_ID,
                TIKTOK_COMMERCIAL_QUALITY_SOURCE_ID,
                V5_PREFLIGHT_SOURCE_ID,
            ),
            search_terms=("信任", "可信", "证明", "证据", "实测", "效果", "背书", "商业内容"),
        ),
        MethodCard(
            method_card_id="expression-form-v1",
            version=2,
            capability="expression_form",
            title="让表现形式服从资源、隐私与持续产能",
            applies_when=("需要选择本人、产品、员工、旁白、桌面或混合表达",),
            lens=(
                "主体类型不决定唯一形式",
                "根据镜头表现、可用人物、空间、素材、隐私和制作能力选择载体",
                "未确认的人物、场地、团队和素材只能作为待验证方案",
            ),
            evidence_needs=("可出镜人员", "素材与场景", "每周产能", "隐私边界"),
            counterexamples=("个人 IP 必须正面口播", "产品 IP 必须由创始人出镜"),
            source_refs=(V4_STRATEGY_SOURCE_ID, V4_ASSET_SOURCE_ID, V5_PREFLIGHT_SOURCE_ID),
            search_terms=("表现形式", "表达", "出镜", "口播", "旁白", "拍摄", "隐私"),
        ),
        MethodCard(
            method_card_id="benchmark-adaptation-v1",
            version=1,
            capability="benchmark_adaptation",
            title="验证对标后只迁移功能，不复制表达与身份",
            applies_when=("需要研究对标账号、代表作品、爆款机制或平台表达",),
            lens=(
                "先确认精确账号和可检查作品，再区分账号模式与单条作品观察",
                "说明样本选择、缺失指标、重复观察和解释之间的边界",
                "把开场功能、受众情境、证明方式和行动邀请转成适合本主体的新命题",
            ),
            evidence_needs=("规范主页", "代表作品", "可见指标与采集时间", "本主体可迁移条件"),
            counterexamples=("用搜索摘要代替作品分析", "复制台词、角色、镜头、音乐或品牌识别"),
            source_refs=(V4_STRATEGY_SOURCE_ID, V4_PILOT_SOURCE_ID),
            search_terms=("对标", "竞品", "标杆", "爆款", "拆解", "模仿", "代表作品"),
        ),
        MethodCard(
            method_card_id="content-engine-v1",
            version=2,
            capability="content_engine",
            title="把真实事件供给变成持续内容发动机",
            applies_when=("需要从一次选题扩展为可持续更新系统",),
            lens=(
                "寻找反复出现的问题、判断、过程、冲突和证明",
                "同时支持触达、信任、证明和转化内容",
                "内容供给必须来自已确认可持续获得的真实来源",
            ),
            evidence_needs=("日常事件来源", "专业判断过程", "可公开证明"),
            counterexamples=("列出三个空泛内容支柱", "依赖无法持续的热点或虚构经历", "把尚不存在的客户投稿或团队日常当成现有素材"),
            source_refs=(V4_STRATEGY_SOURCE_ID, V4_JUDGMENT_SOURCE_ID, V5_PREFLIGHT_SOURCE_ID),
            search_terms=("内容", "持续", "更新", "选题", "系列", "发动机", "母题"),
        ),
        MethodCard(
            method_card_id="monetization-v1",
            version=2,
            capability="monetization",
            title="从付费问题与交付能力设计变现",
            applies_when=("需要判断谁为什么付费以及主体能否交付",),
            lens=(
                "区分影响目标、行为目标和经济目标",
                "连接买方、付费问题、产品或服务、价格逻辑与交付负担",
                "新增产品、价格或优惠只能作为待验证方案，不能伪装成现有供给",
            ),
            evidence_needs=("现有成交", "客户问题", "产品能力", "成本与产能"),
            counterexamples=("先涨粉以后再想变现", "把流量直接等同于收入"),
            source_refs=(V4_JUDGMENT_SOURCE_ID, V4_ASSET_SOURCE_ID, V5_PREFLIGHT_SOURCE_ID),
            search_terms=("变现", "收入", "付费", "产品", "服务", "赚钱", "商业"),
        ),
        MethodCard(
            method_card_id="conversion-v1",
            version=2,
            capability="conversion",
            title="设计从内容到成交与交付的连续路径",
            applies_when=("内容有观看或信任但无法承接行动",),
            lens=(
                "明确内容邀请的下一步行为",
                "检查主页、承接物、销售对话、交付和复购是否连续",
                "未确认的平台功能、留资权限、隐私同意和履约能力必须保留为未知",
            ),
            evidence_needs=("现有用户路径", "线索与成交记录", "交付方式"),
            counterexamples=("只写私信我", "用无法交付的高承诺换取线索"),
            source_refs=(V4_JUDGMENT_SOURCE_ID, V5_PREFLIGHT_SOURCE_ID),
            search_terms=("转化", "成交", "私信", "线索", "承接", "复购", "到店"),
        ),
        MethodCard(
            method_card_id="experiment-design-v1",
            version=2,
            capability="experiment_design",
            title="用最小内容实验解决关键未知",
            applies_when=("证据不足但已经可以提出可修订方向",),
            lens=(
                "一次实验只突出一个主要创意或经营假设",
                "预先写观察窗口、成功信号、失败信号和重要限制",
                "平台指标、受众信号和商业信号分开观察",
                "没有基线时先采集范围，不编造行业阈值",
            ),
            evidence_needs=("当前未知", "可控变量", "实际产能", "观察来源"),
            counterexamples=("要求固定三条试验才能继续", "把单条高播放晋升为通用规律", "给任意数字贴上待验证标签"),
            source_refs=(V4_PILOT_SOURCE_ID, V4_JUDGMENT_SOURCE_ID, V5_PREFLIGHT_SOURCE_ID),
            search_terms=("实验", "试拍", "首条", "验证", "假设", "复盘", "学习"),
        ),
    )


class MethodLibrary:
    """Select relevant method cards without turning them into a workflow."""

    def __init__(
        self,
        cards: tuple[MethodCard, ...],
        *,
        source_catalog: KnowledgeCatalog,
    ) -> None:
        identities = {(card.method_card_id, card.version) for card in cards}
        if len(identities) != len(cards):
            raise ValueError("method card identities must be unique")
        for card in cards:
            source_catalog.resolve(card.source_refs)
        self._cards = cards
        self._source_catalog = source_catalog

    @property
    def cards(self) -> tuple[MethodCard, ...]:
        return self._cards

    @property
    def source_catalog(self) -> KnowledgeCatalog:
        return self._source_catalog

    def search(self, *, query: str, limit: int = 4) -> tuple[MethodCard, ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        normalized = query.casefold()
        ranked: list[tuple[int, str, MethodCard]] = []
        for card in self._cards:
            searchable = (
                card.capability,
                card.title,
                *card.search_terms,
                *card.applies_when,
            )
            score = sum(1 for term in searchable if term.casefold() in normalized)
            if score:
                ranked.append((score, card.method_card_id, card))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return tuple(item[2] for item in ranked[:limit])


def default_method_library() -> MethodLibrary:
    return MethodLibrary(
        default_method_cards(),
        source_catalog=default_knowledge_catalog(),
    )


__all__ = ["MethodLibrary", "default_method_cards", "default_method_library"]
