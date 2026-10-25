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
