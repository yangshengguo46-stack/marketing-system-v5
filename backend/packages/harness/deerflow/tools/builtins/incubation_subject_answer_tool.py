"""Record an authenticated clarification reply in the incubation truth ledger."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import quote

from langchain.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from mcn_incubation.domain import ProjectTruth, TruthKind
from mcn_incubation.persistence import IncubationRepository

from deerflow.agents.human_input import read_human_input_response
from deerflow.persistence.engine import get_session_factory
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.tools.types import Runtime

_FACT_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_SUBJECT_FACT_CLARIFICATION_TYPES = frozenset({"missing_info", "ambiguous_requirement", "approach_choice"})


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _fact_key(value: str) -> str:
    normalized = value.strip()
    if _FACT_KEY_PATTERN.fullmatch(normalized) is None:
        raise ValueError("fact_key must be a lowercase semantic key using letters, digits, dots, underscores, or hyphens")
    return normalized


def _current_human_response(
    messages: Sequence[BaseMessage],
    *,
    run_id: str,
) -> tuple[int, dict]:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if not isinstance(message, HumanMessage):
            continue
        response = read_human_input_response(message.additional_kwargs)
        if response is None or response["source"] != "ask_clarification":
            continue
        if message.additional_kwargs.get("run_id") != run_id:
            raise ValueError("the latest clarification response does not belong to the current run")
        return index, dict(response)
    raise ValueError("no answered ask_clarification response exists in the current run")


def _matching_request(
    messages: Sequence[BaseMessage],
    *,
    before_index: int,
    request_id: str,
) -> Mapping[str, object]:
    for message in reversed(messages[:before_index]):
        if not isinstance(message, ToolMessage) or message.name != "ask_clarification":
            continue
        artifact = message.artifact
        if not isinstance(artifact, Mapping):
            continue
        request = artifact.get("human_input")
        if not isinstance(request, Mapping) or request.get("request_id") != request_id:
            continue
        if request.get("kind") != "human_input_request" or request.get("source") != "ask_clarification":
            continue
        question = request.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("matching clarification request has no question")
        clarification_type = request.get("clarification_type")
        if clarification_type not in _SUBJECT_FACT_CLARIFICATION_TYPES:
            raise ValueError("approval or suggestion responses cannot be recorded as subject facts")
        return request
    raise ValueError("no matching clarification request exists for the current human response")


def _truth_result(truth: ProjectTruth) -> dict:
    return {
        "truth_id": truth.truth_id,
        "kind": truth.kind.value,
        "statement": truth.statement,
        "created_at": truth.created_at.isoformat(),
        "source_ref": truth.source_ref,
        "supersedes_truth_id": truth.supersedes_truth_id,
    }


@tool(parse_docstring=True)
async def incubation_record_subject_answer(
    runtime: Runtime,
    project_id: str,
    fact_key: str,
) -> dict:
    """Record the current user's answered incubation question as a versioned fact.

    Call this after the user answers `ask_clarification` with subject information
    that may change an incubation judgment. The answer and original question are
    read directly from the authenticated current-run message pair; neither can be
    supplied or rewritten in tool arguments. Reusing one `fact_key` automatically
    supersedes its earlier current answer.

    Do not use this for publication approval, spending consent, or other
    irreversible authorization. Those are approvals, not subject facts.

    Args:
        project_id: Existing incubation project that owns the answer.
        fact_key: Stable lowercase semantic key such as
            `expression.camera_comfort` or `offer.delivery_scope`.
    """

    normalized_project_id = project_id.strip()
    if not normalized_project_id:
        raise ValueError("project_id cannot be blank")
    normalized_fact_key = _fact_key(fact_key)
    context = runtime.context or {}
    if context.get("is_subagent") is True:
        raise PermissionError("Only the Lead Agent may record project subject answers")
    session_factory = get_session_factory()
    if session_factory is None:
        return {
            "authority": "project_truth_ledger",
            "project_id": normalized_project_id,
            "status": "unavailable",
            "note": "Durable project truth is unavailable; the answer was not recorded and must not be replaced with chat memory or a model summary.",
        }

    run_id = context.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("current run id is required to record a subject answer")
    thread_id = context.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("current thread id is required to record a subject answer")
    state = runtime.state or {}
    raw_messages = state.get("messages", [])
    if not isinstance(raw_messages, Sequence) or isinstance(raw_messages, str | bytes):
        raise ValueError("current run messages are unavailable")
    messages = [message for message in raw_messages if isinstance(message, BaseMessage)]
    response_index, response = _current_human_response(messages, run_id=run_id)
    request = _matching_request(
        messages,
        before_index=response_index,
        request_id=response["request_id"],
    )

    owner_id = resolve_runtime_user_id(runtime)
    repository = IncubationRepository(session_factory)
    encoded_fact_key = quote(normalized_fact_key, safe="._-")
    source_prefix = f"human-input://{encoded_fact_key}/"
    request_digest = sha256(f"{thread_id}\0{response['request_id']}".encode()).hexdigest()
    source_ref = f"{source_prefix}{request_digest}"
    current_truths = await repository.list_current_truths(
        owner_id=owner_id,
        project_id=normalized_project_id,
    )
    matching_truths = [truth for truth in current_truths if truth.kind is TruthKind.USER_FACT and truth.source_ref is not None and truth.source_ref.startswith(source_prefix)]
    for truth in matching_truths:
        if truth.source_ref == source_ref:
            return {
                "authority": "project_truth_ledger",
                "project_id": normalized_project_id,
                "fact_key": normalized_fact_key,
                "status": "unchanged",
                "truth": _truth_result(truth),
            }

    question = str(request["question"])
    answer = response["value"]
    identity_digest = sha256(f"{owner_id}\0{normalized_project_id}\0{source_ref}".encode()).hexdigest()
    truth = ProjectTruth(
        truth_id=f"subject-answer-{identity_digest[:32]}",
        owner_id=owner_id,
        project_id=normalized_project_id,
        kind=TruthKind.USER_FACT,
        statement=f"用户对问题“{question}”的回答：{answer}",
        created_at=_now_utc(),
        source_ref=source_ref,
        supersedes_truth_id=(matching_truths[-1].truth_id if matching_truths else None),
    )
    recorded = await repository.append_truth(
        truth,
        operation_key=f"record-subject-answer-{identity_digest}",
    )
    return {
        "authority": "project_truth_ledger",
        "project_id": normalized_project_id,
        "fact_key": normalized_fact_key,
        "status": "recorded",
        "truth": _truth_result(recorded),
        "note": "This is a user fact from one matched clarification reply, not proof that any incubation route will work.",
    }


incubation_record_subject_answer_tool = incubation_record_subject_answer

__all__ = ["incubation_record_subject_answer_tool"]
