"""Shared parent/subagent limits, cancellation checks, accounting and public action events."""

import json
import threading
import time

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, messages_to_dict
from langchain_core.utils.function_calling import convert_to_openai_tool

from ..groq_client import ModelError

MAX_MODEL_CALLS = 8
MAX_TOOL_CALLS = 24
MAX_INPUT_BYTES = 30000
MAX_OUTPUT_TOKENS = 6000
MAX_SECONDS = 600


def reserve_cost(rates):
    return (
        MAX_MODEL_CALLS
        * ((MAX_INPUT_BYTES + 2000) * rates[0] + MAX_OUTPUT_TOKENS * rates[1])
        / 1_000_000
    )


class AgentFailure(ModelError):
    def __init__(self, message, usage):
        super().__init__(message)
        self.usage = usage


class RunControl:
    def __init__(self, model, on_event=None, check_active=None):
        self.lock = threading.RLock()
        self.on_event = on_event or (lambda event, usage: None)
        self.check_active = check_active or (lambda: True)
        self.started = time.monotonic()
        self.usage = {
            "model": model,
            "runtime": "deepagents",
            "model_calls": 0,
            "tool_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "incomplete_usage": False,
            "agent_trace": [],
        }

    def check(self):
        if not self.check_active():
            raise ModelError("Agent stopped because the run was cancelled or its inputs changed.")
        if time.monotonic() - self.started > MAX_SECONDS:
            raise ModelError("Agent reached its ten-minute limit. Narrow the task and retry.")

    def event(self, kind, agent, detail):
        with self.lock:
            event = {
                "sequence": len(self.usage["agent_trace"]) + 1,
                "kind": kind,
                "agent": agent,
                "detail": detail[:300],
            }
            self.usage["agent_trace"].append(event)
            self.on_event(event, dict(self.usage))


class AgentGuard(AgentMiddleware):
    def __init__(self, control, agent, schema=None):
        self.control, self.agent, self.schema = control, agent, schema
        self.evidence_seen = False

    def wrap_model_call(self, request, handler):
        c = self.control
        with c.lock:
            c.check()
            if not self.evidence_seen:
                evidence_tools = [
                    t
                    for t in request.tools
                    if getattr(t, "name", "")
                    in {"search_paper", "read_paper_page", "read_artifact"}
                ]
                request = request.override(
                    tools=evidence_tools, response_format=None, tool_choice="required"
                )
            if c.usage["model_calls"] >= MAX_MODEL_CALLS:
                raise ModelError(
                    "Agent reached its eight-model-call limit. Narrow the task and retry."
                )
            payload = {
                "messages": messages_to_dict(
                    ([request.system_message] if request.system_message else []) + request.messages
                ),
                "tools": [convert_to_openai_tool(t) for t in request.tools],
                "output_schema": self.schema.model_json_schema() if self.schema else None,
            }
            if len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_INPUT_BYTES:
                raise ModelError("Agent context reached its size limit. Narrow the task and retry.")
            c.usage["model_calls"] += 1
            c.event("model_started", self.agent, "Requesting the next action")
        try:
            response = handler(request)
        except Exception:
            with c.lock:
                c.usage["incomplete_usage"] = True
            raise
        with c.lock:
            for message in response.result:
                if isinstance(message, AIMessage):
                    usage = message.usage_metadata
                    if usage is None:
                        c.usage["incomplete_usage"] = True
                        continue
                    c.usage["prompt_tokens"] += usage.get("input_tokens", 0)
                    c.usage["completion_tokens"] += usage.get("output_tokens", 0)
                    c.usage["total_tokens"] += usage.get("total_tokens", 0)
            c.event("model_finished", self.agent, "Model response received")
        return response

    def wrap_tool_call(self, request, handler):
        c = self.control
        name = request.tool_call["name"]
        with c.lock:
            c.check()
            if c.usage["tool_calls"] >= MAX_TOOL_CALLS:
                raise ModelError("Agent reached its tool-call limit. Narrow the task and retry.")
            c.usage["tool_calls"] += 1
            # Do not record code, paper text, raw arguments or model reasoning in the public trace.
            c.event("tool_started", self.agent, name)
        result = handler(request)
        if name in {"search_paper", "read_paper_page", "read_artifact"}:
            self.evidence_seen = True
        c.event("tool_finished", self.agent, name)
        return result
