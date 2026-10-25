import pytest
from paperlab_api.models import ContractRevision
from sqlalchemy.orm import Session


def minimal(setup):
    return {
        k: v for k, v in setup.items() if k not in {"max_gpu_hours", "max_llm_cost_usd", "hardware"}
    }


def test_resources_can_be_undecided(client, setup):
    result = client.post("/projects", json=minimal(setup))
    assert result.status_code == 201
    assert result.json()["setup"]["resource_plan"] == {
        "workload": "undecided",
        "environment": "undecided",
        "requirements": [],
    }


def test_optional_custom_and_zero_resources_roundtrip(client, setup):
    payload = {
        **minimal(setup),
        "resource_plan": {
            "workload": "api",
            "environment": "local",
            "requirements": [
                {"kind": "experiment_budget", "label": "Experiment API budget", "value": 0},
                {"kind": "requests_per_minute", "label": "Request quota", "value": None},
                {"kind": "custom", "label": "Dataset license", "value": "Research use only"},
            ],
        },
    }
    project = client.post("/projects", json=payload).json()
    restored = client.get(f"/projects/{project['id']}").json()
    assert restored["setup"]["resource_plan"] == payload["resource_plan"]
    assert restored["setup"]["max_gpu_hours"] is None


@pytest.mark.parametrize(
    "requirement",
    [
        {"kind": "ram_gb", "label": "RAM", "value": -1},
        {"kind": "cpu_cores", "label": "CPU", "value": 1.5},
        {"kind": "gpu_hours", "label": "GPU", "value": "unlimited"},
        {"kind": "ram_gb", "label": "RAM", "value": True},
        {"kind": "custom", "label": " ", "value": "hello"},
        {"kind": "software", "label": "Runtime", "value": 2},
    ],
)
def test_invalid_resource_values_rejected(client, setup, requirement):
    response = client.post(
        "/projects", json={**minimal(setup), "resource_plan": {"requirements": [requirement]}}
    )
    assert response.status_code == 422


def test_duplicate_resources_rejected(client, setup):
    row = {"kind": "ram_gb", "label": "RAM", "value": 16}
    response = client.post(
        "/projects", json={**minimal(setup), "resource_plan": {"requirements": [row, row]}}
    )
    assert response.status_code == 422


def test_legacy_json_is_read_without_rewriting_original(client, setup):
    project = client.post("/projects", json=setup).json()
    with Session(client.app.state.engine) as session, session.begin():
        old = session.get(ContractRevision, (project["id"], 1))
        old.setup = setup  # Exact JSON shape persisted by v0.1.
    path = f"/projects/{project['id']}/revisions"
    history = client.get(path).json()
    assert history[0]["setup"]["resource_plan"]["requirements"][0]["value"] == 2
    assert (
        client.post(
            path, json={"expected_revision": 1, "setup": setup, "note": "Unchanged legacy setup"}
        ).status_code
        == 422
    )
    with Session(client.app.state.engine) as session:
        assert session.get(ContractRevision, (project["id"], 1)).setup == setup
