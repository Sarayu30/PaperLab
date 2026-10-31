import io
import threading
import time
import zipfile
from uuid import uuid4

import pytest
from paperlab_api.models import AgentRun, ResearchWorkspace
from paperlab_api.paper_intake import pages_from_pdf, paper_url
from paperlab_api.research_schemas import AgentOutput, GeneratedFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

PAPER = "We evaluate a linear classifier on a held-out validation set. " * 12


class FakeProvider:
    def generate(self, system, context, schema):
        return {
            "title": "Research draft",
            "summary": "A grounded draft.",
            "sections": [{"heading": "Method", "body": "Use the validation split."}],
            "citations": [{"page": 1, "quote": "We evaluate a linear classifier"}],
            "tasks": [
                {
                    "id": "load",
                    "title": "Load data",
                    "description": "Load the dataset",
                    "depends_on": [],
                    "acceptance": "Split sizes match",
                }
            ],
            "files": [
                {"path": "src/model.py", "content": "def predict(x):\n    return x\n"},
                {"path": "README.md", "content": "Fixture instructions"},
                {"path": "requirements.txt", "content": "# Standard library only"},
            ],
            "warnings": [],
        }, {"model": "test", "prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}


@pytest.fixture
def research(client, setup, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    client.app.state.research.provider = FakeProvider()
    pid = client.post("/projects", json=setup).json()["id"]
    root = f"/projects/{pid}/research"
    version = client.get(root).json()["version"]
    assert (
        client.post(
            root + "/source/text",
            json={
                "expected_version": version,
                "text": PAPER,
                "name": "Fixture paper",
            },
        ).status_code
        == 200
    )
    return client, pid, root


def run_step(client, root, stage, message=""):
    snapshot = client.get(root).json()
    response = client.post(
        root + "/runs",
        json={
            "expected_version": snapshot["version"],
            "stage": stage,
            "message": message,
            "request_id": str(uuid4()),
        },
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    for _ in range(100):
        snapshot = client.get(root).json()
        run = next(r for r in snapshot["runs"] if r["id"] == run_id)
        if run["status"] not in {"queued", "running"}:
            assert run["status"] == "completed", run
            return snapshot
        time.sleep(0.01)
    raise AssertionError("AI test job did not complete")


def test_guided_workflow_feedback_and_export(research):
    client, pid, root = research
    run_step(client, root, "analysis")
    snapshot = run_step(client, root, "plan")
    plan_id = snapshot["artifacts"]["plan"]["id"]
    denied = client.post(
        root + "/runs",
        json={
            "expected_version": snapshot["version"],
            "stage": "implementation",
            "request_id": str(uuid4()),
        },
    )
    assert denied.status_code == 409
    assert (
        client.post(
            root + "/approve", json={"expected_version": snapshot["version"], "plan_id": plan_id}
        ).status_code
        == 200
    )
    run_step(client, root, "implementation")
    snapshot = run_step(client, root, "review")
    exported = client.get(root + "/export")
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert "project/src/model.py" in archive.namelist()
        assert "paperlab/notebook.ipynb" in archive.namelist()
        assert b"unit-test-key" not in archive.read("paperlab/provenance.json")
    previous_analysis = snapshot["artifacts"]["analysis"]["id"]
    updated = client.post(
        root + "/feedback",
        json={
            "expected_version": snapshot["version"],
            "stage": "plan",
            "message": "Use CPU only and report F1.",
        },
    ).json()
    assert list(updated["artifacts"]) == ["analysis"]
    assert updated["artifacts"]["analysis"]["id"] == previous_analysis
    assert updated["approved_plan"] is None
    assert len(updated["runs"]) == 4
    assert (
        client.post(
            root + "/approve", json={"expected_version": snapshot["version"], "plan_id": plan_id}
        ).status_code
        == 409
    )
    revised = run_step(client, root, "plan")
    with Session(client.app.state.engine) as session:
        saved = session.get(AgentRun, revised["artifacts"]["plan"]["id"])
        assert "Use CPU only" in saved.context["human_feedback"]


def test_setup_revision_invalidates_ai_artifacts(research):
    client, pid, root = research
    before = run_step(client, root, "analysis")
    project = client.get(f"/projects/{pid}").json()
    project["setup"]["metric"] = "F1"
    assert (
        client.post(
            f"/projects/{pid}/revisions",
            json={"expected_revision": 1, "setup": project["setup"], "note": "Correct metric"},
        ).status_code
        == 201
    )
    after = client.get(root).json()
    assert after["version"] > before["version"]
    assert after["artifacts"] == {}
    assert after["project_revision"] == 2


def test_cancellation_discards_late_output_and_duplicate_request_is_idempotent(research):
    client, _, root = research
    entered, release = threading.Event(), threading.Event()

    class BlockingProvider(FakeProvider):
        def generate(self, *args):
            entered.set()
            release.wait(5)
            return super().generate(*args)

    client.app.state.research.provider = BlockingProvider()
    version = client.get(root).json()["version"]
    payload = {"expected_version": version, "stage": "analysis", "request_id": str(uuid4())}
    first = client.post(root + "/runs", json=payload)
    try:
        assert entered.wait(2)
        assert client.post(root + "/runs", json=payload).json()["id"] == first.json()["id"]
        assert client.post(root + "/cancel", json={"expected_version": version}).status_code == 200
    finally:
        release.set()
    time.sleep(0.05)
    state = client.get(root).json()
    assert state["artifacts"] == {}
    assert state["runs"][0]["status"] == "cancelled"


def test_zero_budget_rejects_spend_and_missing_source_rejects_run(client, setup, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    setup["max_llm_cost_usd"] = 0
    pid = client.post("/projects", json=setup).json()["id"]
    root = f"/projects/{pid}/research"
    version = client.get(root).json()["version"]
    payload = {"expected_version": version, "stage": "analysis", "request_id": str(uuid4())}
    assert client.post(root + "/runs", json=payload).status_code == 422
    source = client.post(
        root + "/source/text", json={"expected_version": version, "text": PAPER}
    ).json()
    payload["expected_version"] = source["version"]
    assert client.post(root + "/runs", json=payload).status_code == 422


def test_results_require_real_input_and_revision_clears_evidence(research):
    client, _, root = research
    run_step(client, root, "analysis")
    snapshot = run_step(client, root, "plan")
    client.post(
        root + "/approve",
        json={
            "expected_version": snapshot["version"],
            "plan_id": snapshot["artifacts"]["plan"]["id"],
        },
    )
    run_step(client, root, "implementation")
    snapshot = run_step(client, root, "review")
    assert (
        client.post(
            root + "/runs",
            json={
                "expected_version": snapshot["version"],
                "stage": "results",
                "request_id": str(uuid4()),
            },
        ).status_code
        == 422
    )
    snapshot = client.post(
        root + "/evidence",
        json={
            "expected_version": snapshot["version"],
            "metrics": {"accuracy": 0.8},
            "hardware": "CPU",
            "command": "python train.py",
        },
    ).json()
    assert snapshot["evidence"]["provenance"] == "self-reported"
    results = run_step(client, root, "results")
    with Session(client.app.state.engine) as session:
        saved = session.get(AgentRun, results["artifacts"]["results"]["id"])
        assert saved.context["current_stage"] == "results"
        assert "files" not in saved.context["prior_artifacts"]["implementation"]
        assert saved.context["self_reported_evidence"]["metrics"] == {"accuracy": 0.8}
        assert any("self-reported" in warning for warning in saved.output["warnings"])
    changed = client.post(
        root + "/feedback",
        json={
            "expected_version": snapshot["version"],
            "stage": "implementation",
            "message": "Change the preprocessing",
        },
    ).json()
    assert not changed["evidence"]


@pytest.mark.parametrize(
    "path", ["../secret.py", "/tmp/run.py", "C:/run.py", ".env", "a/../b.py", "CON.py", "dir./x.py"]
)
def test_generated_paths_cannot_escape_export(path):
    with pytest.raises(ValidationError):
        GeneratedFile(path=path, content="")


@pytest.mark.parametrize(
    "url",
    [
        "http://arxiv.org/pdf/x",
        "https://localhost/x.pdf",
        "https://127.0.0.1/x.pdf",
        "https://arxiv.org.evil.test/x",
        "https://user@arxiv.org/x",
        "https://arxiv.org:invalid/x",
    ],
)
def test_url_import_rejects_untrusted_hosts(url):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        paper_url(url)


def test_task_graph_rejects_cycles():
    with pytest.raises(ValidationError):
        AgentOutput(
            title="Plan",
            summary="",
            tasks=[
                {
                    "id": "a",
                    "title": "a",
                    "description": "a",
                    "acceptance": "a",
                    "depends_on": ["a"],
                }
            ],
        )


def test_pdf_preserves_page_numbers_with_blank_page():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(("BT /F1 12 Tf 10 700 Td (" + PAPER + ") Tj ET").encode())
    page[NameObject("/Contents")] = stream
    buffer = io.BytesIO()
    writer.write(buffer)
    pages = pages_from_pdf(buffer.getvalue())
    assert pages[0] == {"page": 1, "text": ""}
    assert pages[1]["page"] == 2
    assert "linear classifier" in pages[1]["text"]


def test_restart_preserves_artifacts_and_interrupts_unfinished_request(research):
    client, pid, root = research
    before = run_step(client, root, "analysis")
    run_id = str(uuid4())
    from paperlab_api.research import now

    with Session(client.app.state.engine) as session, session.begin():
        workspace = session.get(ResearchWorkspace, pid)
        workspace.active_run = run_id
        session.add(
            AgentRun(
                id=run_id,
                project_id=pid,
                workspace_version=workspace.version,
                project_revision=1,
                request_id=str(uuid4()),
                stage="plan",
                status="running",
                context={},
                output={},
                usage={},
                error="",
                created_at=now(),
            )
        )
    client.app.state.research.recover()
    after = client.get(root).json()
    assert after["active_run"] is None
    assert after["artifacts"] == before["artifacts"]
    assert next(r for r in after["runs"] if r["id"] == run_id)["status"] == "interrupted"


def test_invalid_citation_is_removed(research):
    client, _, root = research

    class InvalidCitationProvider(FakeProvider):
        def generate(self, *args):
            output, usage = super().generate(*args)
            output["citations"] = [{"page": 1, "quote": "A quote the source never contained"}]
            return output, usage

    client.app.state.research.provider = InvalidCitationProvider()
    output = run_step(client, root, "analysis")["artifacts"]["analysis"]["output"]
    assert output["citations"] == []
    assert any("removed" in warning for warning in output["warnings"])


@pytest.mark.parametrize("defect", ["missing_files", "invalid_python"])
def test_incomplete_or_invalid_code_does_not_become_an_artifact(research, defect):
    client, _, root = research
    run_step(client, root, "analysis")
    state = run_step(client, root, "plan")
    client.post(
        root + "/approve",
        json={"expected_version": state["version"], "plan_id": state["artifacts"]["plan"]["id"]},
    )

    class BrokenCodeProvider(FakeProvider):
        def generate(self, *args):
            output, usage = super().generate(*args)
            if defect == "missing_files":
                output["files"] = output["files"][:1]
            else:
                output["files"][0]["content"] = "def broken(\n"
            return output, usage

    client.app.state.research.provider = BrokenCodeProvider()
    response = client.post(
        root + "/runs",
        json={
            "expected_version": state["version"],
            "stage": "implementation",
            "request_id": str(uuid4()),
        },
    )
    assert response.status_code == 202
    for _ in range(100):
        state = client.get(root).json()
        if not state["active_run"]:
            break
        time.sleep(0.01)
    assert "implementation" not in state["artifacts"]
    assert state["runs"][0]["status"] == "failed"
    assert "incomplete" in state["runs"][0]["error"] or "syntax" in state["runs"][0]["error"]
