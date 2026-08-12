"""Shared privacy and usage helpers for bounded internal model tools."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.constants import TAG_NOSTREAM

from deerflow.agents.middlewares.input_sanitization_middleware import neutralize_untrusted_tags
from deerflow.tools.types import Runtime


def serialize_tool_payload(payload: Mapping[str, Any]) -> str:
    return neutralize_untrusted_tags(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def build_private_invoke_config(
    runtime: Runtime,
    *,
    run_name: str,
    tags: Sequence[str],
) -> dict[str, Any]:
    config = dict(runtime.config or {})
    merged_tags = list(config.get("tags") or [])
    for tag in (*tags, TAG_NOSTREAM):
        if tag not in merged_tags:
            merged_tags.append(tag)
    config["tags"] = merged_tags
    config["run_name"] = run_name
    # The validated structure is returned through the outer tool result. The
    # nested model must not persist private reasoning in the parent journal.
    config["callbacks"] = []
    return config


def record_private_model_usage(
    runtime: Runtime,
    response: AIMessage,
    *,
    fallback_model_name: str,
    caller: str,
    source_prefix: str,
) -> None:
    context = runtime.context if isinstance(runtime.context, dict) else {}
    journal = context.get("__run_journal")
    recorder = getattr(journal, "record_external_llm_usage_records", None)
    usage = dict(response.usage_metadata or {})
    if not callable(recorder) or not usage:
        return

    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    input_details = usage.get("input_token_details") or {}
    cache_read_tokens = int(input_details.get("cache_read") or 0) if isinstance(input_details, Mapping) else 0
    response_metadata = response.response_metadata or {}
    provider_model = response_metadata.get("model_name") or response_metadata.get("model") if isinstance(response_metadata, Mapping) else None
    source_suffix = runtime.tool_call_id or str(id(response))
    recorder(
        [
            {
                "source_run_id": f"{source_prefix}:{source_suffix}",
                "caller": caller,
                "model_name": provider_model or fallback_model_name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cache_read_tokens": cache_read_tokens,
            }
        ]
    )
