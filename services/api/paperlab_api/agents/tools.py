"""Tools operate on one immutable run snapshot and an isolated virtual draft."""

import ast
import json
import re

from langchain.tools import ToolRuntime, tool

from ..research_schemas import AgentOutput, GeneratedFile


def draft_files(state):
    return [
        GeneratedFile(
            path=path.removeprefix("/draft/"),
            content=(
                data["content"] if isinstance(data["content"], str) else "\n".join(data["content"])
            ),
        )
        for path, data in state.get("files", {}).items()
        if path.startswith("/draft/") and data is not None
    ]


def project_findings(files):
    """Static validation only. Never import or execute generated Python."""
    problems = []
    by_path = {f.path: f.content for f in files}
    if not by_path.get("README.md", "").strip():
        problems.append("Missing nonempty README.md")
    if not any(by_path.get(p, "").strip() for p in ("requirements.txt", "pyproject.toml")):
        problems.append("Missing dependency file: requirements.txt or pyproject.toml")
    if not any(p.endswith(".py") and c.strip() for p, c in by_path.items()):
        problems.append("Missing Python source")
    for path, content in by_path.items():
        if path.endswith(".py"):
            try:
                ast.parse(content, filename=path)
            except SyntaxError as exc:
                problems.append(f"{path}:{exc.lineno}: {exc.msg}")
    return {"valid": not problems, "problems": problems, "executed": False}


def make_tools(context):
    pages = context.get("source_document", context.get("source_pages", []))
    artifacts = context.get("artifact_documents", context.get("prior_artifacts", {}))

    @tool
    def search_paper(query: str) -> str:
        """Search the attached paper's extracted text. Returns page-numbered evidence snippets."""
        words = set(re.findall(r"[a-z0-9]{3,}", query.lower()))
        ranked = sorted(pages, key=lambda p: -sum(p["text"].lower().count(w) for w in words))
        matches = []
        for page in ranked:
            lower = page["text"].lower()
            positions = [lower.find(w) for w in words if w in lower]
            if positions:
                start = max(0, min(positions) - 150)
                matches.append(
                    {
                        "page": page["page"],
                        "offset": start,
                        "text": page["text"][start : start + 650],
                    }
                )
            if len(matches) == 5:
                break
        return json.dumps({"matches": matches, "source": context.get("source_digest")})

    @tool
    def read_paper_page(page: int, offset: int = 0) -> str:
        """Read up to 3500 characters from a paper page. Increase offset to read more."""
        found = next((p for p in pages if p["page"] == page), None)
        if found is None or offset < 0:
            return "Page or offset is invalid."
        return json.dumps(
            {
                "page": page,
                "offset": offset,
                "text": found["text"][offset : offset + 3500],
                "total_characters": len(found["text"]),
            }
        )

    @tool
    def read_artifact(stage: str, path: str = "", offset: int = 0) -> str:
        """Read a saved stage artifact or a named generated file; paginate by character offset."""
        if offset < 0:
            return "Offset must be nonnegative."
        artifact = artifacts.get(stage)
        if artifact is None:
            return "No current artifact for that stage."
        if path:
            content = next(
                (f["content"] for f in artifact.get("files", []) if f["path"] == path), None
            )
            if content is None:
                return "No such generated file."
        else:
            # File contents are individually retrievable instead of flooding the context.
            content = json.dumps(
                {**artifact, "files": [f["path"] for f in artifact.get("files", [])]}
            )
        return json.dumps(
            {
                "content": content[offset : offset + 5000],
                "offset": offset,
                "total_characters": len(content),
            }
        )

    @tool
    def validate_project(runtime: ToolRuntime) -> str:
        """Check /draft files for completeness and Python syntax; never execute code."""
        try:
            files = draft_files(runtime.state)
            AgentOutput(title="Validation", summary="", files=files)
            return json.dumps(project_findings(files))
        except ValueError:
            return json.dumps(
                {
                    "valid": False,
                    "executed": False,
                    "problems": ["Invalid file path, duplicate or oversized draft."],
                }
            )

    @tool
    def get_run_metrics() -> str:
        """Read user-submitted metrics and provenance. These are not independently verified."""
        return json.dumps(context.get("self_reported_evidence", {}))[:6000]

    return {
        t.name: t
        for t in [search_paper, read_paper_page, read_artifact, validate_project, get_run_metrics]
    }
