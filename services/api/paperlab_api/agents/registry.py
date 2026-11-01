"""Explicit agent definitions: role, capabilities and optional delegation."""

from dataclasses import dataclass

from ..research_prompts import PROMPTS


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    tools: tuple[str, ...]
    can_write_draft: bool = False
    can_delegate: bool = False

    def instructions(self, stage):
        return PROMPTS[stage]


READ_TOOLS = ("search_paper", "read_paper_page", "read_artifact")
AGENTS = {
    "analysis": AgentDefinition("research-analyst", READ_TOOLS, can_delegate=True),
    "plan": AgentDefinition("experiment-planner", READ_TOOLS, can_delegate=True),
    "implementation": AgentDefinition(
        "implementation-author", (*READ_TOOLS, "validate_project"), can_write_draft=True
    ),
    "review": AgentDefinition(
        "methodology-reviewer", (*READ_TOOLS, "validate_project"), can_delegate=True
    ),
    "results": AgentDefinition("results-analyst", (*READ_TOOLS, "get_run_metrics")),
    "extensions": AgentDefinition("extension-researcher", READ_TOOLS),
    "report": AgentDefinition("report-author", (*READ_TOOLS, "get_run_metrics")),
    "chat": AgentDefinition("learning-assistant", READ_TOOLS),
}
