import threading
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import anyio
import pytest

from deerflow.agents.lead_agent import prompt as prompt_module
from deerflow.config.app_config import AppConfig
from deerflow.config.subagents_config import CustomSubagentConfig, SubagentsAppConfig
from deerflow.skills.types import Skill, SkillCategory


def _set_skills_cache_state(*, skills=None, active=False, version=0):
    prompt_module._get_cached_skills_prompt_section.cache_clear()
    with prompt_module._enabled_skills_lock:
        prompt_module._enabled_skills_cache = skills
        prompt_module._enabled_skills_by_config_cache.clear()
        prompt_module._enabled_skills_refresh_active = active
        prompt_module._enabled_skills_refresh_version = version
        prompt_module._enabled_skills_refresh_event.clear()
        prompt_module._enabled_skills_refresh_waiters.clear()


def test_build_self_update_section_empty_for_default_agent():
    assert prompt_module._build_self_update_section(None) == ""


def test_build_self_update_section_present_for_custom_agent():
    section = prompt_module._build_self_update_section("my-agent")

    assert "<self_update>" in section
    assert "my-agent" in section
    assert "update_agent" in section
    assert '"null"' in section


def test_build_custom_mounts_section_returns_empty_when_no_mounts(monkeypatch):
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=[]))
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)

    assert prompt_module._build_custom_mounts_section() == ""


def test_build_custom_mounts_section_lists_configured_mounts(monkeypatch):
    mounts = [
        SimpleNamespace(container_path="/home/user/shared", read_only=False),
        SimpleNamespace(container_path="/mnt/reference", read_only=True),
    ]
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=mounts))
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)

    section = prompt_module._build_custom_mounts_section()

    assert "**Custom Mounted Directories:**" in section
    assert "`/home/user/shared`" in section
    assert "read-write" in section
    assert "`/mnt/reference`" in section
    assert "read-only" in section


def test_build_custom_mounts_section_uses_explicit_app_config_without_global_read(monkeypatch):
    mounts = [SimpleNamespace(container_path="/home/user/shared", read_only=False)]
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=mounts))

    def fail_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.get_app_config", fail_get_app_config)

    section = prompt_module._build_custom_mounts_section(app_config=config)

    assert "`/home/user/shared`" in section
    assert "read-write" in section


def test_apply_prompt_template_includes_custom_mounts(monkeypatch):
    mounts = [SimpleNamespace(container_path="/home/user/shared", read_only=False)]
    config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=mounts),
        skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
    )
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "_get_enabled_skills", lambda: [])
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda **kwargs: "")


def test_apply_prompt_template_includes_relative_path_guidance(monkeypatch):
    config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=[]),
        skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
    )
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "_get_enabled_skills", lambda: [])
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_get_memory_context", lambda agent_name=None, **kwargs: "")
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    prompt = prompt_module.apply_prompt_template()

    assert "Treat `/mnt/user-data/workspace` as your default current working directory" in prompt
    assert "`hello.txt`, `../uploads/data.csv`, and `../outputs/report.md`" in prompt


def test_apply_prompt_template_includes_memory_tool_guidance_only_in_tool_mode(monkeypatch):
    tool_config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=[]),
        skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=True, mode="tool", injection_enabled=False),
        acp_agents={},
    )
    middleware_config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=[]),
        skills=tool_config.skills,
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=True, mode="middleware"),
        acp_agents={},
    )
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_or_new_user_skill_storage", lambda user_id, app_config=None: SimpleNamespace(load_skills=lambda *, enabled_only: []))
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda **kwargs: "")
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    tool_prompt = prompt_module.apply_prompt_template(app_config=tool_config)
    middleware_prompt = prompt_module.apply_prompt_template(app_config=middleware_config)

    assert "<memory_tool_system>" in tool_prompt
    assert "memory_search" in tool_prompt
    assert "memory_add" in tool_prompt
    assert "agent facts are not injected automatically" in tool_prompt
    assert "When present, the injected <memory> block contains only global user and history summaries" in tool_prompt
    assert "<memory_tool_system>" not in middleware_prompt


def test_apply_prompt_template_threads_explicit_app_config_without_global_config(monkeypatch):
    mounts = [SimpleNamespace(container_path="/home/user/shared", read_only=False)]
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(mounts=mounts),
        skills=SimpleNamespace(container_path="/mnt/explicit-skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/explicit-skills")),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )

    def fail_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    def fail_get_memory_config():
        raise AssertionError("ambient get_memory_config() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.get_app_config", fail_get_app_config)
    monkeypatch.setattr("deerflow.config.memory_config.get_memory_config", fail_get_memory_config)
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_or_new_user_skill_storage", lambda user_id, app_config=None: SimpleNamespace(load_skills=lambda *, enabled_only: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    prompt = prompt_module.apply_prompt_template(app_config=explicit_config)

    assert "`/home/user/shared`" in prompt
    assert "Custom Mounted Directories" in prompt


def test_apply_prompt_template_threads_explicit_app_config_to_subagents_without_global_config(monkeypatch):
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(
            custom_agents={
                "researcher": CustomSubagentConfig(
                    description="Research agent\nwith details",
                    system_prompt="You research.",
                )
            }
        ),
        skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )

    def fail_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    def fail_get_subagents_app_config():
        raise AssertionError("ambient get_subagents_app_config() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.get_app_config", fail_get_app_config)
    monkeypatch.setattr("deerflow.config.subagents_config.get_subagents_app_config", fail_get_subagents_app_config)
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    prompt = prompt_module.apply_prompt_template(subagent_enabled=True, app_config=explicit_config)

    assert "**researcher**: Research agent" in prompt
    assert "**bash**" not in prompt


def test_apply_prompt_template_includes_subagent_total_limit(monkeypatch):
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(),
        skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    prompt = prompt_module.apply_prompt_template(
        subagent_enabled=True,
        max_concurrent_subagents=3,
        max_total_subagents=5,
        app_config=explicit_config,
    )

    assert "MAXIMUM 3 `task` CALLS PER RESPONSE" in prompt
    assert "MAXIMUM 5 `task` CALLS PER RUN" in prompt
    assert "Default to direct execution" in prompt
    assert "DELEGATION CHECK" in prompt
    assert "expected benefit from real parallel latency" in prompt
    assert "HARD LIMITS ARE NON-NEGOTIABLE" in prompt


def test_apply_prompt_template_clamps_subagent_limits_to_enforced_bounds(monkeypatch):
    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(),
        skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    prompt = prompt_module.apply_prompt_template(
        subagent_enabled=True,
        max_concurrent_subagents=99,
        max_total_subagents=99,
        app_config=explicit_config,
    )

    assert "MAXIMUM 4 `task` CALLS PER RESPONSE" in prompt
    assert "MAXIMUM 50 `task` CALLS PER RUN" in prompt


def test_apply_prompt_template_single_subagent_limit_matches_middleware(monkeypatch):
    """Regression test for single-subagent mode (MIN_CONCURRENT_SUBAGENT_CALLS = 1).

    Before the floor was lowered to 1, a user-configured limit of 1 was silently
    bumped to 2 by both the prompt path and the middleware. This renders the real
    system prompt with max_concurrent_subagents=1 and asserts the advertised
    HARD LIMITS value equals the middleware-enforced max_concurrent, so the two
    paths cannot drift apart on the newly-allowed value.
    """
    from deerflow.agents.middlewares.subagent_limit_middleware import SubagentLimitMiddleware

    explicit_config = SimpleNamespace(
        sandbox=SimpleNamespace(
            use="deerflow.sandbox.local:LocalSandboxProvider",
            allow_host_bash=False,
            mounts=[],
        ),
        subagents=SubagentsAppConfig(),
        skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    enforced = SubagentLimitMiddleware(max_concurrent=1).max_concurrent
    assert enforced == 1  # 1 must pass through, not be bumped to 2

    prompt = prompt_module.apply_prompt_template(
        subagent_enabled=True,
        max_concurrent_subagents=1,
        max_total_subagents=6,
        app_config=explicit_config,
    )

    assert f"MAXIMUM {enforced} `task` CALLS PER RESPONSE" in prompt
    assert f"HARD LIMITS ARE NON-NEGOTIABLE: max {enforced} `task` calls per response" in prompt
    assert "Expected benefit = specialist capability + context isolation" in prompt
    assert "delegate only for material specialist or context-isolation benefit" in prompt
    assert "expected benefit from real parallel latency" not in prompt
    assert "material within-batch parallel savings" not in prompt
    assert "Multi-batch example" not in prompt


def test_build_acp_section_uses_explicit_app_config_without_global_config(monkeypatch):
    explicit_config = SimpleNamespace(acp_agents={"codex": object()})

    def fail_get_acp_agents():
        raise AssertionError("ambient get_acp_agents() must not be used when app_config is explicit")

    monkeypatch.setattr("deerflow.config.acp_config.get_acp_agents", fail_get_acp_agents)

    section = prompt_module._build_acp_section(app_config=explicit_config)

    assert "ACP Agent Tasks" in section
    assert "/mnt/acp-workspace/" in section


def test_get_memory_context_uses_explicit_app_config_without_global_config(monkeypatch):
    explicit_config = SimpleNamespace(
        memory=SimpleNamespace(enabled=True, injection_enabled=True, max_injection_tokens=1234, token_counting="tiktoken"),
    )
    captured: dict[str, object] = {}

    def fail_get_memory_config():
        raise AssertionError("ambient get_memory_config() must not be used when app_config is explicit")

    def fake_get_context(user_id, *, agent_name=None, thread_id=None):
        captured["agent_name"] = agent_name
        captured["user_id"] = user_id
        return "remember this"

    manager = SimpleNamespace(get_context=fake_get_context)
    monkeypatch.setattr("deerflow.config.memory_config.get_memory_config", fail_get_memory_config)
    monkeypatch.setattr("deerflow.runtime.user_context.resolve_runtime_user_id", lambda runtime: "user-1")
    monkeypatch.setattr("deerflow.agents.memory.get_memory_manager", lambda: manager)

    context = prompt_module._get_memory_context("agent-a", app_config=explicit_config)

    assert "<memory>" in context
    assert "remember this" in context
    assert captured == {
        "agent_name": "agent-a",
        "user_id": "user-1",
    }


def test_get_memory_context_propagates_fail_closed_manager_error(monkeypatch):
    from deerflow.agents.memory import MemoryManagerError

    explicit_config = SimpleNamespace(
        memory=SimpleNamespace(
            enabled=True,
            injection_enabled=True,
            backend_config={"failure_policy": {"read": "fail_closed"}},
        ),
    )
    manager = SimpleNamespace(get_context=lambda *args, **kwargs: (_ for _ in ()).throw(MemoryManagerError("down")))
    monkeypatch.setattr("deerflow.agents.memory.get_memory_manager", lambda: manager)
    monkeypatch.setattr("deerflow.runtime.user_context.get_effective_user_id", lambda: "user-1")

    with pytest.raises(MemoryManagerError, match="down"):
        prompt_module._get_memory_context("agent-a", app_config=explicit_config)


def test_get_memory_context_swallows_manager_error_without_fail_closed(monkeypatch):
    from deerflow.agents.memory import MemoryManagerError

    explicit_config = SimpleNamespace(
        memory=SimpleNamespace(enabled=True, injection_enabled=True, backend_config={}),
    )
    manager = SimpleNamespace(get_context=lambda *args, **kwargs: (_ for _ in ()).throw(MemoryManagerError("down")))
    monkeypatch.setattr("deerflow.agents.memory.get_memory_manager", lambda: manager)
    monkeypatch.setattr("deerflow.runtime.user_context.get_effective_user_id", lambda: "user-1")

    assert prompt_module._get_memory_context("agent-a", app_config=explicit_config) == ""


def test_get_memory_context_prefers_explicit_user_id(monkeypatch):
    explicit_config = SimpleNamespace(
        memory=SimpleNamespace(enabled=True, injection_enabled=True),
    )
    captured: dict[str, object] = {}

    def fail_resolve_runtime_user_id(runtime):
        raise AssertionError("explicit user_id must bypass ambient identity resolution")

    def fake_get_context(user_id, *, agent_name=None, thread_id=None):
        captured["agent_name"] = agent_name
        captured["user_id"] = user_id
        return "remember this"

    monkeypatch.setattr("deerflow.runtime.user_context.resolve_runtime_user_id", fail_resolve_runtime_user_id)
    monkeypatch.setattr(
        "deerflow.agents.memory.get_memory_manager",
        lambda: SimpleNamespace(get_context=fake_get_context),
    )

    context = prompt_module._get_memory_context(
        "agent-a",
        app_config=explicit_config,
        user_id="runtime-user",
    )

    assert "<memory>" in context
    assert captured == {
        "agent_name": "agent-a",
        "user_id": "runtime-user",
    }


def test_refresh_skills_system_prompt_cache_async_reloads_immediately(monkeypatch, tmp_path):
    def make_skill(name: str) -> Skill:
        skill_dir = tmp_path / name
        return Skill(
            name=name,
            description=f"Description for {name}",
            license="MIT",
            skill_dir=skill_dir,
            skill_file=skill_dir / "SKILL.md",
            relative_path=skill_dir.relative_to(tmp_path),
            category=SkillCategory.CUSTOM,
            enabled=True,
        )

    state = {"skills": [make_skill("first-skill")]}
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda **kwargs: __import__("types").SimpleNamespace(load_skills=lambda *, enabled_only: list(state["skills"])))
    _set_skills_cache_state()

    try:
        prompt_module.warm_enabled_skills_cache()
        assert [skill.name for skill in prompt_module._get_enabled_skills()] == ["first-skill"]

        state["skills"] = [make_skill("second-skill")]
        anyio.run(prompt_module.refresh_skills_system_prompt_cache_async)

        assert [skill.name for skill in prompt_module._get_enabled_skills()] == ["second-skill"]
    finally:
        _set_skills_cache_state()


def test_explicit_config_enabled_skills_are_cached_by_config_identity(monkeypatch, tmp_path):
    def make_skill(name: str) -> Skill:
        skill_dir = tmp_path / name
        return Skill(
            name=name,
            description=f"Description for {name}",
            license="MIT",
            skill_dir=skill_dir,
            skill_file=skill_dir / "SKILL.md",
            relative_path=skill_dir.relative_to(tmp_path),
            category=SkillCategory.CUSTOM,
            enabled=True,
        )

    config = cast(
        AppConfig,
        cast(
            object,
            SimpleNamespace(
                skills=SimpleNamespace(container_path="/mnt/skills", use="deerflow.skills.storage.local_skill_storage:LocalSkillStorage", get_skills_path=lambda: Path("/tmp/skills")),
                skill_evolution=SimpleNamespace(enabled=False),
            ),
        ),
    )
    load_count = 0

    def fake_get_or_new_skill_storage(**kwargs):
        nonlocal load_count
        assert kwargs == {"app_config": config}

        def load_skills(*, enabled_only):
            nonlocal load_count
            if enabled_only:
                load_count += 1
            return [make_skill("cached-skill")]

        return SimpleNamespace(load_skills=load_skills)

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", fake_get_or_new_skill_storage)
    monkeypatch.setattr(prompt_module, "get_or_new_user_skill_storage", lambda user_id, **kwargs: SimpleNamespace(load_skills=lambda *, enabled_only: [make_skill("cached-skill")] if kwargs.get("app_config") is config else []))
    _set_skills_cache_state()

    try:
        first = prompt_module.get_skills_prompt_section(app_config=config)
        second = prompt_module.get_skills_prompt_section(app_config=config)

        assert "cached-skill" in first
        assert "cached-skill" in second
        assert load_count == 1
    finally:
        _set_skills_cache_state()


def test_clear_cache_does_not_spawn_parallel_refresh_workers(monkeypatch, tmp_path):
    started = threading.Event()
    release = threading.Event()
    active_loads = 0
    max_active_loads = 0
    call_count = 0
    lock = threading.Lock()

    def make_skill(name: str) -> Skill:
        skill_dir = tmp_path / name
        return Skill(
            name=name,
            description=f"Description for {name}",
            license="MIT",
            skill_dir=skill_dir,
            skill_file=skill_dir / "SKILL.md",
            relative_path=skill_dir.relative_to(tmp_path),
            category=SkillCategory.CUSTOM,
            enabled=True,
        )

    def fake_load_skills(enabled_only=True):
        nonlocal active_loads, max_active_loads, call_count
        with lock:
            active_loads += 1
            max_active_loads = max(max_active_loads, active_loads)
            call_count += 1
            current_call = call_count

        started.set()
        if current_call == 1:
            release.wait(timeout=5)

        with lock:
            active_loads -= 1

        return [make_skill(f"skill-{current_call}")]

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda **kwargs: __import__("types").SimpleNamespace(load_skills=lambda *, enabled_only: fake_load_skills(enabled_only=enabled_only)))
    _set_skills_cache_state()

    try:
        prompt_module.clear_skills_system_prompt_cache()
        assert started.wait(timeout=5)

        prompt_module.clear_skills_system_prompt_cache()
        release.set()
        prompt_module.warm_enabled_skills_cache()

        assert max_active_loads == 1
        assert [skill.name for skill in prompt_module._get_enabled_skills()] == ["skill-2"]
    finally:
        release.set()
        _set_skills_cache_state()


def test_warm_enabled_skills_cache_logs_on_timeout(monkeypatch, caplog):
    event = threading.Event()
    monkeypatch.setattr(prompt_module, "_ensure_enabled_skills_cache", lambda: event)

    with caplog.at_level("WARNING"):
        warmed = prompt_module.warm_enabled_skills_cache(timeout_seconds=0.01)

    assert warmed is False
    assert "Timed out waiting" in caplog.text


def test_system_prompt_template_contains_file_editing_workflow_rule():
    """The File Editing Workflow rule must remain in the system prompt
    template so the planner picks the right tool (str_replace for edits,
    write_file + append=True for long new content) and avoids mid-stream
    chunk-gap timeouts on oversized single-shot writes. See issue #3189
    / PR #3195.

    We deliberately do NOT assert on any specific byte / word threshold
    here — that would re-introduce the docstring-lock-in pattern the
    reviewers flagged. The numeric cap lives in the server-side guard
    (see test_write_file_tool_size_guard.py), which is where it belongs.
    """
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE
    # Section anchor — keeps the rule discoverable in the assembled prompt.
    assert "File Editing Workflow" in template
    # Behavioural anchors — if either of these disappears, the model will
    # silently regress to single-shot write_file calls for long content.
    assert "str_replace" in template
    assert "append=True" in template


def test_system_prompt_template_requires_virtual_paths_for_output_images():
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE

    assert "![Chart](/mnt/user-data/outputs/chart.png)" in template
    assert "Never use a bare or workspace-relative filename" in template
    assert "Call `present_files` for the image before referencing it" in template


def test_system_prompt_template_preserves_placeholders():
    """Ensure the chunking-rule edit didn't drop any f-string placeholder
    consumed by apply_prompt_template(). A missing placeholder would
    crash prompt rendering at runtime.
    """
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE
    for ph in (
        "{agent_name}",
        "{soul}",
        "{self_update_section}",
        "{business_semantics_section}",
        "{content_world_explorer_section}",
        "{subagent_thinking}",
        "{skills_section}",
        "{deferred_tools_section}",
        "{subagent_section}",
        "{acp_section}",
        "{subagent_reminder}",
        "{skill_first_reminder}",
    ):
        assert ph in template, f"placeholder {ph} accidentally removed"


def test_system_prompt_template_uses_one_compact_mcn_incubation_core():
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE

    for marker in (
        "个人、品牌、产品或组织",
        "唯一面向用户作出孵化判断的 Lead Agent",
        "信息采集只是输入，营销推演才是核心",
        "从名词看动作，从产品看用途，从用途看关系、人性与长期需求",
        "定位、内容与表现形式是相互影响但不同的判断",
        "内容是讲什么；表现形式是怎么呈现",
        "回答用户当前真正提出的问题",
        "不得为了显得具体而补造",
        "只有缺失信息会实质反转当前判断时，才问一个聚焦问题",
    ):
        assert marker in template

    for retired_rule in (
        "an open-source super agent",
        "CLARIFY → PLAN → ACT",
        "Clarification First",
        "ALWAYS clarify unclear/missing/ambiguous requirements BEFORE starting work",
        "Clarification ALWAYS comes BEFORE action",
        "If anything is unclear, missing, or has multiple interpretations, you MUST ask",
        "最小试验",
        "具体首轮实验",
    ):
        assert retired_rule not in template

    for leaked_case_answer in ("黄金礼品", "送礼", "水果", "宝妈", "70%", "10 天"):
        assert leaked_case_answer not in template

    assert "analyze_business_semantics" not in template
    assert "explore_content_worlds" not in template


def test_business_semantics_guidance_is_capability_gated():
    section = prompt_module.BUSINESS_SEMANTICS_PROMPT_SECTION

    assert "按需调用 `analyze_business_semantics`" in section
    assert "语义材料，不替你选择账号主语" in section
    assert "每轮调用 `analyze_business_semantics`" not in section
    assert "必须调用 `analyze_business_semantics`" not in section


def test_content_world_guidance_is_capability_gated_and_narrowly_triggered():
    section = prompt_module.CONTENT_WORLD_EXPLORER_PROMPT_SECTION

    assert "调用 `explore_content_worlds`" in section
    assert "起号、账号定位、长期讲什么或内容方向" in section
    assert "只问一个能确定商业对象的问题" in section
    assert "不要先用其他模块事项组成问卷" in section
    assert "不是每轮必经步骤" in section
    assert "最终营销判断仍由你负责" in section


def test_content_world_trigger_does_not_confuse_a_clear_object_with_downstream_ambiguity():
    section = prompt_module.CONTENT_WORLD_EXPLORER_PROMPT_SECTION

    assert "能识别主体实际提供、经营、加工或服务的产品/服务对象" in section
    assert "经营方式、生产方式和素材" in section
    assert "不等于商业对象不明确" in section
    assert "不得因此先调用 `ask_clarification`" in section
    assert "不得为澄清而补造选项" in section
    assert "不再解释模块外信息" in section


def test_content_world_guidance_selects_the_largest_effective_world_without_sales_collapse():
    section = prompt_module.CONTENT_WORLD_EXPLORER_PROMPT_SECTION

    assert "最大有效内容世界" in section
    assert "离原始对象最近" in section
    assert "宽品类本身" in section
    assert "向下的种类" in section
    assert "历史、地域、文化" in section
    assert "别人也能讲" in section
    assert "生产方式" in section
    assert "不得擅自建议拆号" in section
    assert "不接收模型改写的业务事实" in section
    assert "`content_world_map.root_subject`" in section
    assert "词法主词" in section
    assert "商品形态" in section
    assert "商业表达中已出现的具体对象或活动" in section
    assert "地域、材质或风格修饰" in section
    assert "泛化的体验或生活方式" in section
    assert "最小完整根" in section
    assert "`modifier_handling`" in section
    assert "`branch_lens`" in section
    assert "三项反事实" in section
    assert "已校验商业语义" in section
    assert "不重新评分或翻案" in section
    assert "修饰词专属工艺" in section
    assert "对具体商品很重要" in section
    assert "不得再黏回根主语" in section
    assert "国家、地区、民族与文化群体" in section
    assert "`cross_cultural_comparison`" in section
    assert "资源与环境" in section
    assert "规则与禁忌" in section
    assert "仪式与社交组织" in section
    assert "缺少现成事例" in section
    assert "标准编号" in section
    assert "不得直接转述" in section
    assert "不得以问句结尾" in section
    assert "`root_world` 的各轴属于同一张地图" in section
    assert "一手经验更少" in section
    assert "不能因此从内容世界删除" in section
    assert "所有有结构关系的非空轴" in section
    assert "未定义简称" in section
    assert "不得展开成用户没有陈述的具体事实" in section
    assert "只有 `fact_boundary.allowed_subject_claims`" in section
    assert "`coverage_contract` 中的每个非空轴" in section
    assert "明确说出轴的名称和它为何属于这个世界" in section
    assert "不能用相邻轴代替" in section
    assert "`fact_boundary.do_not_infer`" in section
    assert "一般知识和待研究方向" in section
    assert "不得改写成主体已经拥有" in section
    assert "地图只能证明可讲范围" in section
    assert "不能证明主体亲历、掌握或拥有" in section
    assert "当前内容世界回答不展开其他模块" in section
    assert "不得举例补全" in section
    assert "源头、生产者或专业身份" in section
    assert "只能形成条件化的可信视角" in section


def test_content_world_guidance_does_not_shift_attention_to_selling_or_monetization():
    section = prompt_module.CONTENT_WORLD_EXPLORER_PROMPT_SECTION

    for out_of_scope_term in (
        "卖货",
        "销售",
        "广告",
        "变现",
        "成交",
        "转化",
        "客单",
        "复购",
        "带货",
    ):
        assert out_of_scope_term not in section
    assert "B/C" not in section
    assert "不得推成具体场地、一手经历、供应能力" in section
    assert "回答前最后读取 `response_contract`" in section
    assert "本轮回答范围" in section
    assert "不得擅自扩成完整起号方案" in section
    assert "不再解释模块外信息" in section
    assert "不追问" in section
    assert "完成 `output_shape` 后立即停止" in section


def test_incubation_core_does_not_default_an_expression_form_when_subject_capability_is_unknown():
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE

    assert "不把任何具体表现形式设为默认方案" in template
    assert "仍先完成当前营销判断，不因此启动问卷" in template


def test_incubation_core_keeps_unconfirmed_resources_conditional():
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE

    assert "只能标为条件或未知" in template
    assert "不得写成主体已经拥有的优势" in template


def test_incubation_core_separates_content_theme_from_evidence_and_available_material():
    template = prompt_module.SYSTEM_PROMPT_TEMPLATE

    assert "区分内容母题与能力证明、可拍素材" in template
    assert "有视觉冲击不等于应当成为账号主语" in template
    assert "先由内容世界的结构与容量决定讲什么" in template
    assert "不把向上抽象当成唯一正确方向" in template


def _make_minimal_app_config():
    return SimpleNamespace(
        sandbox=SimpleNamespace(mounts=[]),
        skills=SimpleNamespace(container_path="/mnt/skills"),
        skill_evolution=SimpleNamespace(enabled=False),
        tool_search=SimpleNamespace(enabled=False),
        memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
        acp_agents={},
    )


def test_apply_prompt_template_legacy_path_does_not_mention_describe_skill(monkeypatch):
    """When skill_names is None (legacy path), critical_reminders must not
    reference describe_skill (the tool is not registered in legacy mode)."""
    config = _make_minimal_app_config()
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    prompt = prompt_module.apply_prompt_template(app_config=config)

    # Legacy wording — tool-agnostic
    assert "Always load the relevant skill" in prompt
    # Must NOT reference the deferred tool
    assert "describe_skill(name)" not in prompt


def test_apply_prompt_template_deferred_path_mentions_describe_skill(monkeypatch):
    """When skill_names is provided (deferred path), critical_reminders must
    reference describe_skill so the LLM knows how to discover skills."""
    config = _make_minimal_app_config()
    monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only=True: []))
    monkeypatch.setattr(prompt_module, "get_agent_soul", lambda agent_name=None, **kwargs: "")

    prompt = prompt_module.apply_prompt_template(
        app_config=config,
        skill_names=frozenset({"data-analysis"}),
    )

    # Deferred wording — references describe_skill
    assert "describe_skill(name)" in prompt
    # Must NOT contain the legacy wording
    assert "Always load the relevant skill" not in prompt
