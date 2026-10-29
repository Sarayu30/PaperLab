"""Bounded Groq calls with validated outputs and redacted provider failures."""

import json

import httpx
from pydantic import BaseModel, ValidationError

from .config import groq_settings


class ModelError(Exception):
    pass


class GroqClient:
    def __init__(self, transport=None):
        self.transport = transport

    def generate(self, system: str, context: dict, schema: type[BaseModel]) -> tuple[dict, dict]:
        key, model = groq_settings()
        if not key:
            raise ModelError("Set GROQ_API_KEY in the project .env, then restart the API.")
        response_format = {"type": "json_object"}
        # JSON-object mode also supports user-selected Groq models without strict-schema support.
        instructions = system + "\nReturn only JSON matching this schema:\n" + json.dumps(
            schema.model_json_schema()
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            "response_format": response_format,
            "temperature": 0.2,
            "max_completion_tokens": 6000,
        }
        try:
            with httpx.Client(
                timeout=httpx.Timeout(150, connect=15), transport=self.transport, trust_env=False
            ) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
            if response.status_code in (401, 403):
                raise ModelError("Groq rejected the key or model permission. Check your Groq project.")
            if response.status_code == 429:
                raise ModelError("Groq rate or token limit reached. Wait, then retry this step.")
            if response.status_code >= 400:
                raise ModelError(
                    f"Groq returned HTTP {response.status_code}. Check GROQ_MODEL and account access."
                )
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ModelError("The model output was truncated. Narrow the task and retry.")
            result = schema.model_validate_json(choice["message"]["content"])
            usage = data.get("usage", {})
            return result.model_dump(mode="json"), {
                "model": model,
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
            }
        except ModelError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as from_error:
            raise ModelError("Groq could not be reached. Check the connection and retry.") from from_error
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            raise ModelError("Groq returned an invalid response. No artifact was accepted; retry.") from exc
