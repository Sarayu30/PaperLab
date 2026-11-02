"""Return premature code submissions to the agent for bounded repair."""

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import HumanMessage

from ..groq_client import ModelError
from .tools import draft_files, project_findings


class DraftValidation(AgentMiddleware):
    def __init__(self, control):
        self.control = control
        self.repairs = 0

    @hook_config(can_jump_to=["model"])
    def after_model(self, state, runtime):
        if state.get("structured_response") is None:
            return None
        findings = project_findings(draft_files(state))
        if findings["valid"]:
            return None
        problems = "; ".join(findings["problems"])[:1500]
        if self.repairs >= 2:
            raise ModelError("Agent draft failed static checks after repair: " + problems)
        self.repairs += 1
        self.control.event(
            "validation_repair", "implementation-author", "Draft incomplete; requesting repair"
        )
        return {
            "structured_response": None,
            "jump_to": "model",
            "messages": [
                HumanMessage(
                    "Application static checks rejected this draft: "
                    + problems
                    + ". Fix the virtual /draft files with tools, call validate_project, "
                    "then submit agent_output again. No code has been executed."
                )
            ],
        }
