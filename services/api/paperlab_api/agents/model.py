"""Groq permits tool actions or a schema-validated JSON final answer."""

from langchain_groq import ChatGroq


class ResearchChatGroq(ChatGroq):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        # ToolStrategy requests `any`, which Groq rejects when GPT-OSS emits its
        # final artifact as plain JSON. Keep named first-action choices enforced.
        if tool_choice in ("any", "required"):
            tool_choice = "auto"
        return super().bind_tools(tools, tool_choice=tool_choice, **kwargs)
