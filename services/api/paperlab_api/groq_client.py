"""Bounded Groq calls with validated outputs and redacted provider failures."""

import json

import httpx
from pydantic import BaseModel, ValidationError

from .config import groq_settings


class ModelError(Exception):
    pass


def strict_schema(value):
    """Use Groq's supported structural schema; retain all semantic checks locally."""
    if isinstance(value, list):
        return [strict_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {
        key: strict_schema(item)
        for key, item in value.items()
        if key
        not in {
            "default",
            "minLength",
            "maxLength",
            "minItems",
            "maxItems",
            "minimum",
            "maximum",
            "pattern",
        }
    }
    if result.get("type") == "object":
        result["additionalProperties"] = False
        result["required"] = list(result.get("properties", {}))
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate response field")
        result[key] = value
    return result


class GroqClient:
    def __init__(self, transport=None):
        self.transport = transport

    def generate(self, system: str, context: dict, schema: type[BaseModel]) -> tuple[dict, dict]:
        key, model = groq_settings()
        if not key:
            raise ModelError("Set GROQ_API_KEY in the project .env, then restart the API.")
        response_format = {"type": "json_object"}
        if model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "paperlab_output",
                    "strict": True,
                    "schema": strict_schema(schema.model_json_schema()),
                },
            }
        # Other user-selected models retain JSON mode and the same local validation.
        instructions = (
            system
            + "\nReturn only JSON matching this schema:\n"
            + json.dumps(schema.model_json_schema())
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
        if model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
            payload["reasoning_effort"] = "low"
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
                raise ModelError(
                    "Groq rejected the key or model permission. Check your Groq project."
                )
            if response.status_code == 429:
                raise ModelError("Groq rate or token limit reached. Wait, then retry this step.")
            if response.status_code == 400:
                error = response.json().get("error", {})
                if error.get("code") == "json_validate_failed":
                    raise ModelError(
                        "The model did not produce valid structured output. "
                        "Narrow the task and retry; no artifact was accepted."
                    )
            if response.status_code >= 400:
                raise ModelError(
                    f"Groq returned HTTP {response.status_code}. "
                    "Check GROQ_MODEL and account access."
                )
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ModelError("The model output was truncated. Narrow the task and retry.")
            result = schema.model_validate(
                json.loads(choice["message"]["content"], object_pairs_hook=unique_object)
            )
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
            raise ModelError(
                "Groq could not be reached. Check the connection and retry."
            ) from from_error
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            raise ModelError(
                "Groq returned an invalid response. No artifact was accepted; retry."
            ) from exc
