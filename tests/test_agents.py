"""Exercise the real Deep Agents/LangGraph loop with a deterministic chat model."""

import time
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite import SqliteSaver
from paperlab_api.agents.guard import (
    MAX_MODEL_CALLS,
    MAX_RATE_RETRIES,
    AgentFailure,
    rate_limit_delay,
)
from paperlab_api.agents.model import ResearchChatGroq as ChatGroq
from paperlab_api.agents.runtime import DeepResearchAgent
from paperlab_api.agents.tools import make_tools
from paperlab_api.research_schemas import AgentOutput
from pydantic import Field


class ScriptedGroq(ChatGroq):
    responses: list[Any] = Field(exclude=True)
    requests: list[Any] = Field(default_factory=list, exclude=True)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append({"messages": messages, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])


def action(name, args):
    return {"name": name, "args": args, "id": str(uuid4()), "type": "tool_call"}


def message(*calls, content=""):
    return AIMessage(
        content=content,
        tool_calls=list(calls),
        usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    )


def finish():
    return message(
        action("agent_output", AgentOutput(title="Test artifact", summary="Grounded.").model_dump())
    )


def context(stage="analysis"):
    return {
        "current_stage": stage,
        "agent_run_id": str(uuid4()),
        "contract": {"target_result": "Test a linear classifier"},
        "human_feedback": "CPU only",
        "paper_name": "Fixture",
        "source_pages": [{"page": 1, "text": "Use a linear classifier."}],
        "source_digest": "fixture",
        "prior_artifacts": {},
    }


def runner(tmp_path, responses, **kwargs):
    model = ScriptedGroq(model="openai/gpt-oss-120b", api_key="unit-test-key", responses=responses)
    runtime = DeepResearchAgent(
        model_factory=lambda: model, checkpoint_path=tmp_path / "checkpoints.db", **kwargs
    )
    return runtime, model


def test_real_graph_uses_tool_and_persists_checkpoint(tmp_path):
    runtime, model = runner(tmp_path, [message(action("read_paper_page", {"page": 1})), finish()])
    ctx = context()
    output, usage = runtime.generate("Analyze the paper.", ctx, AgentOutput)
    assert output["summary"] == "Grounded."
    assert usage["model_calls"] == 2
    assert usage["total_tokens"] == 300
    assert any(e["detail"] == "read_paper_page" for e in usage["agent_trace"])
    names = {t["function"]["name"] for t in model.requests[0]["tools"]}
    assert "execute" not in names and "write_file" not in names
    with SqliteSaver.from_conn_string(str(tmp_path / "checkpoints.db")) as saver:
        saved = saver.get_tuple({"configurable": {"thread_id": ctx["agent_run_id"]}})
        assert saved.checkpoint["channel_values"]["structured_response"].title == "Test artifact"


def test_agent_writes_and_repairs_virtual_code_without_execution(tmp_path):
    runtime, model = runner(
        tmp_path,
        [
            message(action("read_paper_page", {"page": 1})),
            message(
                action("write_file", {"file_path": "/draft/README.md", "content": "Run model.py"}),
                action(
                    "write_file", {"file_path": "/draft/requirements.txt", "content": "# stdlib"}
                ),
                action("write_file", {"file_path": "/draft/model.py", "content": "def broken(:\n"}),
            ),
            message(action("validate_project", {})),
            message(
                action(
                    "edit_file",
                    {
                        "file_path": "/draft/model.py",
                        "old_string": "def broken(:",
                        "new_string": "value = 1",
                    },
                )
            ),
            message(action("validate_project", {})),
            finish(),
        ],
    )
    output, usage = runtime.generate("Write code.", context("implementation"), AgentOutput)
    files = {f["path"]: f["content"] for f in output["files"]}
    assert files["model.py"].strip() == "value = 1"
    assert not (tmp_path / "model.py").exists()
    assert usage["model_calls"] == 6
    results = [
        m.content
        for r in model.requests
        for m in r["messages"]
        if getattr(m, "name", "") == "validate_project"
    ]
    assert any('"valid": false' in r for r in results)
    assert any('"valid": true' in r for r in results)


def test_specialist_delegation_shares_model_budget(tmp_path):
    runtime, _ = runner(
        tmp_path,
        [
            message(action("read_paper_page", {"page": 1})),
            message(
                action(
                    "task",
                    {
                        "subagent_type": "evidence-auditor",
                        "description": "Check classifier evidence",
                    },
                )
            ),
            message(action("read_paper_page", {"page": 1})),
            message(content="The paper says use a linear classifier on page 1."),
            finish(),
        ],
    )
    _, usage = runtime.generate("Audit evidence.", context(), AgentOutput)
    assert usage["model_calls"] == 5
    assert usage["total_tokens"] == 750
    assert any(e["agent"] == "evidence-auditor" for e in usage["agent_trace"])


def test_plain_json_final_answer_is_schema_validated(tmp_path):
    runtime, model = runner(
        tmp_path,
        [
            message(action("read_paper_page", {"page": 1})),
            message(
                content=AgentOutput(title="JSON artifact", summary="Grounded.").model_dump_json()
            ),
        ],
    )
    output, _ = runtime.generate("Analyze.", context(), AgentOutput)
    assert output["title"] == "JSON artifact"
    assert model.requests[1]["tool_choice"] == "auto"
    runtime, _ = runner(
        tmp_path,
        [
            message(action("read_paper_page", {"page": 1})),
            message(content="unstructured prose"),
        ],
    )
    with pytest.raises(AgentFailure, match="artifact schema"):
        runtime.generate("Analyze.", context(), AgentOutput)


def test_cancellation_stops_next_model_call(tmp_path):
    active = True

    def observe(run_id, event, usage):
        nonlocal active
        if event["kind"] == "tool_finished":
            active = False

    runtime, model = runner(
        tmp_path,
        [message(action("read_paper_page", {"page": 1})), finish()],
        on_event=observe,
        check_active=lambda _: active,
    )
    with pytest.raises(AgentFailure, match="cancelled"):
        runtime.generate("Analyze.", context(), AgentOutput)
    assert len(model.requests) == 1


def test_model_loop_is_bounded(tmp_path):
    runtime, model = runner(
        tmp_path,
        [message(action("read_paper_page", {"page": 1})) for _ in range(MAX_MODEL_CALLS + 2)],
    )
    with pytest.raises(AgentFailure, match=f"{MAX_MODEL_CALLS}-model-call") as error:
        runtime.generate("Analyze.", context(), AgentOutput)
    assert len(model.requests) == MAX_MODEL_CALLS
    assert error.value.usage["total_tokens"] == MAX_MODEL_CALLS * 150


def test_tools_only_see_attached_snapshot():
    tools = make_tools(context())
    assert "No current artifact" in tools["read_artifact"].invoke({"stage": "../../.env"})
    assert "invalid" in tools["read_paper_page"].invoke({"page": 99})
    assert "linear classifier" in tools["read_paper_page"].invoke({"page": 1})


def test_api_uses_graph_and_saves_action_trace(client, setup, tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    service = client.app.state.research
    runtime, _ = runner(
        tmp_path,
        [message(action("read_paper_page", {"page": 1})), finish()],
        on_event=service.record_agent_event,
        check_active=service.agent_active,
    )
    service.provider = runtime
    pid = client.post("/projects", json=setup).json()["id"]
    root = f"/projects/{pid}/research"
    state = client.get(root).json()
    state = client.post(
        root + "/source/text",
        json={
            "expected_version": state["version"],
            "text": "We evaluate a linear classifier on a held-out split. " * 5,
        },
    ).json()
    response = client.post(
        root + "/runs",
        json={
            "expected_version": state["version"],
            "stage": "analysis",
            "request_id": str(uuid4()),
        },
    )
    assert response.status_code == 202
    for _ in range(200):
        state = client.get(root).json()
        if not state["active_run"]:
            break
        time.sleep(0.01)
    run = state["runs"][0]
    assert run["status"] == "completed", run["error"]
    assert run["usage"]["runtime"] == "deepagents"
    assert run["usage"]["model_calls"] == 2
    assert run["usage"]["estimated_usd"] < run["usage"]["reserved_usd"]
    assert any(e["kind"] == "tool_finished" for e in run["usage"]["agent_trace"])


def test_virtual_filesystem_denies_writes_outside_draft(tmp_path):
    runtime, model = runner(
        tmp_path,
        [
            message(action("read_paper_page", {"page": 1})),
            message(action("write_file", {"file_path": "/secret.py", "content": "test"})),
            finish(),
            finish(),
            finish(),
        ],
    )
    with pytest.raises(AgentFailure, match="static checks"):
        runtime.generate("Write files.", context("implementation"), AgentOutput)
    results = [
        m.content
        for r in model.requests
        for m in r["messages"]
        if getattr(m, "name", "") == "write_file"
    ]
    assert any("denied" in r.lower() for r in results)


def test_premature_submission_returns_missing_files_to_agent(tmp_path):
    runtime, model = runner(
        tmp_path,
        [
            message(action("read_paper_page", {"page": 1})),
            message(
                action("write_file", {"file_path": "/draft/README.md", "content": "Demo"}),
                action("write_file", {"file_path": "/draft/model.py", "content": "value = 1"}),
            ),
            finish(),
            message(
                action(
                    "write_file",
                    {"file_path": "/draft/requirements.txt", "content": "# Standard library only"},
                )
            ),
            message(action("validate_project", {})),
            finish(),
        ],
    )
    output, usage = runtime.generate("Implement.", context("implementation"), AgentOutput)
    assert len(output["files"]) == 3
    assert any(e["kind"] == "validation_repair" for e in usage["agent_trace"])
    assert any("Missing dependency file" in str(m.content) for m in model.requests[3]["messages"])


def test_default_model_can_be_constructed_without_network(tmp_path, monkeypatch):
    from paperlab_api.agents import runtime as module

    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    instance = DeepResearchAgent(checkpoint_path=tmp_path / "checkpoint.db")

    def inspect_build(model, *args):
        assert isinstance(model, module.ChatGroq)
        assert model.reasoning_effort == "low"
        assert model.max_retries == 0
        raise module.ModelError("construction verified")

    monkeypatch.setattr(instance, "build", inspect_build)
    with pytest.raises(AgentFailure, match="construction verified"):
        instance.generate("Analyze.", context(), AgentOutput)


def test_rate_limit_wait_respects_retry_cap_and_records_uncertain_usage(tmp_path, monkeypatch):
    import groq
    import httpx
    from paperlab_api.agents import guard

    monkeypatch.setattr(guard.time, "sleep", lambda _: None)
    error = groq.RateLimitError(
        "rate limited",
        response=httpx.Response(
            429, headers={"retry-after": "1"}, request=httpx.Request("POST", "https://api.groq.com")
        ),
        body={},
    )
    runtime, model = runner(
        tmp_path, [error, message(action("read_paper_page", {"page": 1})), finish()]
    )
    _, usage = runtime.generate("Analyze.", context(), AgentOutput)
    assert usage["model_calls"] == 3
    assert usage["rate_limit_retries"] == 1
    assert usage["incomplete_usage"] is True
    assert any(e["kind"] == "rate_limit_wait" for e in usage["agent_trace"])
    runtime, model = runner(tmp_path, [error] * (MAX_RATE_RETRIES + 1) + [finish()])
    with pytest.raises(AgentFailure, match="rate limit"):
        runtime.generate("Analyze.", context(), AgentOutput)
    assert len(model.requests) == MAX_RATE_RETRIES + 1
    error.body = {"message": "Please try again in 20.805s."}
    assert rate_limit_delay(error) == pytest.approx(22.805)
