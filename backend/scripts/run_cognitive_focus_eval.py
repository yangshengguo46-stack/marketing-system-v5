"""Run the isolated E13 cognitive-focus architecture comparison.

This is an evaluation-only utility. It calls the configured model directly so
memory, tools, MCP, registered Skills, and subagents cannot change the sealed
comparison. It never mutates DeerFlow's production prompt or runtime state.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import random
import re
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from deerflow.agents.lead_agent.prompt import apply_prompt_template
from deerflow.config.app_config import get_app_config
from deerflow.models.factory import create_chat_model
from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".deer-flow" / "cognitive-focus-eval"

ATOMIC_LENS_SKILL = """<evaluation_only_skill name="marketing-semantic-reframing">
这是一组可选的营销思考镜头，不是行业答案、固定流程、输出模板或完整度要求。

为当前问题选择少数真正能改变判断的镜头，不得全部执行：
- 分辨对象的品类、材质或修饰、用途、动作、关系与社会功能，比较哪个语义主语更值得被长期经营。
- 当对象本身已是宽品类或世界时，保留当前尺度并向下拆分子世界；当对象只是窄单品或载体时，才考虑沿用途和动作向上寻找更稳定的需求世界。
- 可按人物、时间、空间、事件和冲突横向展开，或连接现实、历史、文化和未来；广度本身不等于正确。
- 检查主体凭什么可信、可持续地拥有这个内容世界，以及内容如何自然归因回真实生意。
- 主动对比一个反向解释，防止把上一个案例的语义尺度机械迁移到本题。

只能把用户明说的信息当作用户事实。常见客户、经历、素材、能力、场景和外部知识均只能是待核验候选，不得为了完整而补造。
</evaluation_only_skill>"""

FOCUS_FRAME_PROMPT = """你只为另一次 Lead 回答生成一份简短的私有认知聚焦帧。

这不是营销方案、内容选题、调研结果、用户事实或最终决定。不得提出人设、赛道、平台、表现形式、变现方案、执行计划或任何数字，不得补造主体已有经历、客户、素材、能力、渠道和案例。

用自然语言简短写出：
- 这次真正要判断的问题；
- 用户已明说的事实和会反转判断的未知；
- 模型最容易滑入的熟悉模板；
- 本题值得比较的少数语义主语或尺度；
- 一个防止机械迁移的反向检查。

允许不完整，不要为了填满栏目而新增内容。"""

FOCUS_FRAME_CONTEXT = """<evaluation_only_focus_frame>
以下文本是上一次同模型产生的非约束性聚焦线索，不是用户事实、外部证据或已批准决定。你必须自行判断，可以忽略其中任何或全部内容，不得将它的新假设写成事实。
{focus_frame}
</evaluation_only_focus_frame>"""

DEFAULT_CASES = (
    ("gold-gift", "narrow-composite", "我是一个做黄金礼品加工的，你有什么起号建议？"),
    ("flower-shop", "broad-category", "我是开花店的，你有什么起号建议？"),
    ("fruit-shop", "broad-category", "我是一个开水果店的，有什么起号建议？"),
    ("industrial-packaging", "professional-near-demand", "我是做工业设备防护包装的，有什么起号建议？"),
    ("mother", "identity-insufficient", "我是一个宝妈，想做账号，你有什么起号建议？"),
)


class EvalVariant(StrEnum):
    BASELINE = "baseline"
    ATOMIC_SKILL = "atomic-skill"
    FOCUS_FRAME = "focus-frame"


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    category: str
    question: str


class AsyncModel(Protocol):
    async def ainvoke(self, messages: Sequence[object]) -> AIMessage: ...


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def default_cases() -> tuple[EvalCase, ...]:
    return tuple(EvalCase(*case) for case in DEFAULT_CASES)


def _user_message(question: str) -> HumanMessage:
    wrapped = f"--- BEGIN USER INPUT ---\n{question}\n--- END USER INPUT ---"
    return HumanMessage(
        content=wrapped,
        additional_kwargs={ORIGINAL_USER_CONTENT_KEY: question},
    )


def build_base_prompt() -> str:
    config = get_app_config()
    isolated_config = config.model_copy(
        update={
            "memory": config.memory.model_copy(update={"enabled": False, "injection_enabled": False}),
            "skill_evolution": config.skill_evolution.model_copy(update={"enabled": False}),
        }
    )
    return apply_prompt_template(
        subagent_enabled=False,
        available_skills=set(),
        app_config=isolated_config,
        deferred_names=frozenset(),
        mcp_routing_hints_section="",
        user_id="e13-evaluation",
    )


def build_answer_messages(
    *,
    base_prompt: str,
    question: str,
    variant: EvalVariant,
    focus_frame: str | None = None,
) -> list[object]:
    additions: list[str] = []
    if variant in {EvalVariant.ATOMIC_SKILL, EvalVariant.FOCUS_FRAME}:
        additions.append(ATOMIC_LENS_SKILL)
    if variant is EvalVariant.FOCUS_FRAME:
        if not focus_frame:
            raise ValueError("focus-frame variant requires a non-empty focus frame")
        additions.append(FOCUS_FRAME_CONTEXT.format(focus_frame=html.escape(focus_frame, quote=False)))
    elif focus_frame is not None:
        raise ValueError("focus frame is only valid for the focus-frame variant")

    system_content = "\n\n".join([base_prompt, *additions])
    return [SystemMessage(content=system_content), _user_message(question)]


def build_focus_messages(question: str) -> list[object]:
    system_content = "\n\n".join([FOCUS_FRAME_PROMPT, ATOMIC_LENS_SKILL])
    return [SystemMessage(content=system_content), _user_message(question)]


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
            parts.append(str(item.get("text") or ""))
    return "".join(parts)


def extract_visible_answer(message: AIMessage) -> tuple[str, dict[str, int]]:
    usage = dict(message.usage_metadata or {})
    return _content_to_text(message.content).strip(), {str(key): int(value) for key, value in usage.items() if isinstance(value, int)}


def calculate_max_calls(*, case_count: int, variants: Sequence[EvalVariant]) -> int:
    return case_count * sum(2 if variant is EvalVariant.FOCUS_FRAME else 1 for variant in variants)


async def run_trial(
    *,
    model: AsyncModel,
    base_prompt: str,
    case: EvalCase,
    variant: EvalVariant,
) -> dict[str, Any]:
    started = time.monotonic()
    focus_frame: str | None = None
    focus_usage: dict[str, int] = {}
    if variant is EvalVariant.FOCUS_FRAME:
        focus_message = await model.ainvoke(build_focus_messages(case.question))
        focus_frame, focus_usage = extract_visible_answer(focus_message)
        if not focus_frame:
            raise RuntimeError(f"empty focus frame for {case.case_id}")

    answer_message = await model.ainvoke(
        build_answer_messages(
            base_prompt=base_prompt,
            question=case.question,
            variant=variant,
            focus_frame=focus_frame,
        )
    )
    answer, answer_usage = extract_visible_answer(answer_message)
    if not answer:
        raise RuntimeError(f"empty answer for {case.case_id}/{variant}")

    return {
        "case_id": case.case_id,
        "category": case.category,
        "variant": variant.value,
        "question": case.question,
        "question_sha256": _sha256_text(case.question),
        "focus_frame": focus_frame,
        "focus_frame_sha256": _sha256_text(focus_frame) if focus_frame else None,
        "answer": answer,
        "answer_sha256": _sha256_text(answer),
        "focus_usage": focus_usage,
        "answer_usage": answer_usage,
        "call_count": 2 if variant is EvalVariant.FOCUS_FRAME else 1,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _parse_variants(value: str) -> tuple[EvalVariant, ...]:
    try:
        variants = tuple(EvalVariant(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not variants or len(set(variants)) != len(variants):
        raise argparse.ArgumentTypeError("variants must be a non-empty unique comma-separated list")
    return variants


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-.")
    if not normalized:
        raise ValueError("run id cannot be empty")
    return normalized


async def run_experiment(args: argparse.Namespace) -> Path:
    cases = default_cases()
    variants = args.variants
    expected_calls = calculate_max_calls(case_count=len(cases), variants=variants)
    if args.max_calls != expected_calls:
        raise ValueError(f"--max-calls must equal the sealed call count {expected_calls}")
    if not args.execute:
        raise ValueError("live model evaluation requires the explicit --execute flag")

    base_prompt = build_base_prompt()
    model = create_chat_model(name=args.model, thinking_enabled=True, attach_tracing=False)
    order = [(case, variant) for case in cases for variant in variants]
    random.Random(args.seed).shuffle(order)

    records: list[dict[str, Any]] = []
    output_dir = args.output_root / _slug(args.run_id)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    manifest = {
        "schema_version": 1,
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "thinking_enabled": True,
        "seed": args.seed,
        "variants": [variant.value for variant in variants],
        "max_calls": args.max_calls,
        "case_count": len(cases),
        "base_prompt_sha256": _sha256_text(base_prompt),
        "atomic_lens_sha256": _sha256_text(ATOMIC_LENS_SKILL),
        "focus_prompt_sha256": _sha256_text(FOCUS_FRAME_PROMPT),
        "cases": [asdict(case) | {"question_sha256": _sha256_text(case.question)} for case in cases],
        "isolation": {
            "memory": False,
            "registered_skills": False,
            "tools": False,
            "mcp": False,
            "subagents": False,
            "production_state_writes": False,
            "reasoning_content_persisted": False,
        },
    }
    write_json_atomic(output_dir / "manifest.json", manifest)

    try:
        for case, variant in order:
            record = await run_trial(model=model, base_prompt=base_prompt, case=case, variant=variant)
            records.append(record)
            write_json_atomic(output_dir / "results.json", {"status": "running", "records": records})
    except BaseException as exc:
        write_json_atomic(
            output_dir / "completion.json",
            {"status": "failed", "completed_calls": sum(record["call_count"] for record in records), "error_type": type(exc).__name__, "error": str(exc)},
        )
        raise

    write_json_atomic(
        output_dir / "results.json",
        {"status": "completed", "records": sorted(records, key=lambda item: (item["case_id"], item["variant"]))},
    )
    write_json_atomic(
        output_dir / "completion.json",
        {"status": "completed", "completed_calls": sum(record["call_count"] for record in records), "record_count": len(records)},
    )
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default="glm-5-2-260617")
    parser.add_argument("--variants", type=_parse_variants, default=(EvalVariant.BASELINE, EvalVariant.ATOMIC_SKILL))
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--execute", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = asyncio.run(run_experiment(args))
    print(output_dir)


if __name__ == "__main__":
    main()
