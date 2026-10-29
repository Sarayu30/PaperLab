import httpx
import pytest
from paperlab_api.groq_client import GroqClient, ModelError
from pydantic import BaseModel


class Answer(BaseModel):
    answer: str


def test_provider_validates_json_and_keeps_key_in_header(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")

    def respond(request):
        assert request.headers["authorization"] == "Bearer test-secret"
        assert b"test-secret" not in request.content
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"answer":"ok"}'}}],
            "usage": {"total_tokens": 12},
        })

    result, usage = GroqClient(httpx.MockTransport(respond)).generate("Answer", {}, Answer)
    assert result == {"answer": "ok"}
    assert usage["total_tokens"] == 12


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_provider_does_not_leak_error_body(monkeypatch, status):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    client = GroqClient(httpx.MockTransport(lambda _: httpx.Response(status, text="test-secret")))
    with pytest.raises(ModelError) as error:
        client.generate("Answer", {}, Answer)
    assert "test-secret" not in str(error.value)


def test_provider_rejects_malformed_output(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    client = GroqClient(httpx.MockTransport(lambda _: httpx.Response(200, json={
        "choices": [{"message": {"content": "not json"}}],
    })))
    with pytest.raises(ModelError, match="invalid response"):
        client.generate("Answer", {}, Answer)
