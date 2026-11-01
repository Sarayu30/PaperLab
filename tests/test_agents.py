"""Exercise the real Deep Agents/LangGraph loop with a deterministic chat model."""

from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_groq import ChatGroq
from langgraph.checkpoint.sqlite import SqliteSaver
from paperlab_api.agents.guard import MAX_MODEL_CALLS, AgentFailure
from paperlab_api.agents.runtime import DeepResearchAgent
from paperlab_api.agents.tools import make_tools
from paperlab_api.research_schemas import AgentOutput
from pydantic import Field


class ScriptedGroq(ChatGroq):
    responses: list[AIMessage] = Field(exclude=True)
    requests: list[Any] = Field(default_factory=list, exclude=True)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append({"messages": messages, **kwargs})
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])


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
        action("AgentOutput", AgentOutput(title="Test artifact", summary="Grounded.").model_dump())
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
    runtime, model = runner(
        tmp_path, [message(action("search_paper", {"query": "classifier"})), finish()]
    )
    ctx = context()
    output, usage = runtime.generate("Analyze the paper.", ctx, AgentOutput)
    assert output["summary"] == "Grounded."
    assert usage["model_calls"] == 2
    assert usage["total_tokens"] == 300
    assert any(e["detail"] == "search_paper" for e in usage["agent_trace"])
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
            message(
                action(
                    "task",
                    {
                        "subagent_type": "evidence-auditor",
                        "description": "Check classifier evidence",
                    },
                )
            ),
            message(action("search_paper", {"query": "classifier"})),
            message(content="The paper says use a linear classifier on page 1."),
            finish(),
        ],
    )
    _, usage = runtime.generate("Audit evidence.", context(), AgentOutput)
    assert usage["model_calls"] == 4
    assert usage["total_tokens"] == 600
    assert any(e["agent"] == "evidence-auditor" for e in usage["agent_trace"])


def test_cancellation_stops_next_model_call(tmp_path):
    active = True

    def observe(run_id, event, usage):
        nonlocal active
        if event["kind"] == "tool_finished":
            active = False

    runtime, model = runner(
        tmp_path,
        [message(action("search_paper", {"query": "classifier"})), finish()],
        on_event=observe,
        check_active=lambda _: active,
    )
    with pytest.raises(AgentFailure, match="cancelled"):
        runtime.generate("Analyze.", context(), AgentOutput)
    assert len(model.requests) == 1


def test_model_loop_is_bounded(tmp_path):
    runtime, model = runner(
        tmp_path,
        [
            message(action("search_paper", {"query": "classifier"}))
            for _ in range(MAX_MODEL_CALLS + 2)
        ],
    )
    with pytest.raises(AgentFailure, match="eight-model-call") as error:
        runtime.generate("Analyze.", context(), AgentOutput)
    assert len(model.requests) == MAX_MODEL_CALLS
    assert error.value.usage["total_tokens"] == MAX_MODEL_CALLS * 150


def test_tools_only_see_attached_snapshot():
    tools = make_tools(context())
    assert "No current artifact" in tools["read_artifact"].invoke({"stage": "../../.env"})
    assert "invalid" in tools["read_paper_page"].invoke({"page": 99})
    assert "linear classifier" in tools["read_paper_page"].invoke({"page": 1})
