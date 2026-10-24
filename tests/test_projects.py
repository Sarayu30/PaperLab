from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from paperlab_api.main import create_app


@pytest.fixture
def url(tmp_path, monkeypatch):
    value = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("PAPERLAB_DATABASE_URL", value)
    command.upgrade(Config("alembic.ini"), "head")
    return value


@pytest.fixture
def client(url):
    with TestClient(create_app(url)) as client:
        yield client


@pytest.fixture
def setup():
    return {
        "name": "Image classification reproduction",
        "paper_url": "https://arxiv.org/abs/1512.03385",
        "target_result": "Reproduce one selected CIFAR-10 result",
        "dataset": "CIFAR-10",
        "metric": "test_error",
        "reproduction_mode": "reimplement",
        "control_mode": "guided",
        "learning_mode": True,
        "max_gpu_hours": 2,
        "max_llm_cost_usd": 5,
        "hardware": "Local GPU, feasibility to be checked",
    }


def test_project_survives_restart(url, setup):
    with TestClient(create_app(url)) as first:
        response = first.post("/projects", json=setup)
        assert response.status_code == 201
        project = response.json()
    with TestClient(create_app(url)) as second:
        assert second.get("/health").status_code == 200
        restored = second.get(f"/projects/{project['id']}").json()
        assert restored["setup"] == setup
        assert restored["revision"] == 1
        assert restored["status"] == "draft"
        assert second.get("/projects").json() == [restored]


def test_revision_retains_original_and_rejects_stale_write(client, setup):
    project = client.post("/projects", json=setup).json()
    path = f"/projects/{project['id']}/revisions"
    update = {
        "expected_revision": 1,
        "setup": {**setup, "metric": "accuracy"},
        "note": "Use accuracy for the selected table row",
    }
    assert client.post(path, json=update).status_code == 201
    assert client.post(path, json=update).status_code == 409
    history = client.get(path).json()
    assert [entry["revision"] for entry in history] == [2, 1]
    assert history[0]["setup"]["metric"] == "accuracy"
    assert history[1]["setup"]["metric"] == "test_error"
    assert client.get(f"/projects/{project['id']}").json()["revision"] == 2


def test_simultaneous_edits_only_one_wins(client, setup):
    project = client.post("/projects", json=setup).json()
    path = f"/projects/{project['id']}/revisions"

    def change(metric):
        return client.post(
            path,
            json={
                "expected_revision": 1,
                "setup": {**setup, "metric": metric},
                "note": "Correct metric from paper",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(change, ["accuracy", "macro_f1"]))
    assert sorted(statuses) == [201, 409]
    assert len(client.get(path).json()) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "   "),
        ("paper_url", "javascript:alert(1)"),
        ("max_gpu_hours", -1),
        ("max_llm_cost_usd", -10),
        ("control_mode", "anything"),
        ("metric", " "),
    ],
)
def test_invalid_setup_is_not_saved(client, setup, field, value):
    assert client.post("/projects", json={**setup, field: value}).status_code == 422
    assert client.get("/projects").json() == []


def test_unchanged_revision_rolls_back(client, setup):
    project = client.post("/projects", json=setup).json()
    path = f"/projects/{project['id']}/revisions"
    response = client.post(
        path, json={"expected_revision": 1, "setup": setup, "note": "No fields were changed"}
    )
    assert response.status_code == 422
    assert client.get(f"/projects/{project['id']}").json()["revision"] == 1
    assert len(client.get(path).json()) == 1


def test_missing_project(client):
    assert client.get(f"/projects/{uuid4()}").status_code == 404
    assert client.get(f"/projects/{uuid4()}/revisions").status_code == 404
