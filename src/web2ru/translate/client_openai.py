from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from web2ru.translate.schema import TRANSLATIONS_SCHEMA


@dataclass(slots=True)
class OpenAIResponsePayload:
    raw_text: str
    status: str | None
    incomplete_details: str | None
    usage: dict[str, Any] | None


SYSTEM_PROMPT = (
    "You translate English text to Russian. "
    "Return JSON strictly matching schema. "
    "Do not output HTML or Markdown. "
    "Keep IDs exactly as provided and in the same order. "
    "Do not change WEB2RU_TP_* placeholders."
)


class OpenAIClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        reasoning_effort: str,
        timeout_seconds: float = 90.0,
    ) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=2)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._reasoning_effort = reasoning_effort

    def translate_payload(self, payload: dict[str, Any]) -> OpenAIResponsePayload:
        request: dict[str, Any] = {
            "model": self._model,
            "max_output_tokens": self._max_output_tokens,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(payload, ensure_ascii=False),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "web2ru_translations",
                    "strict": True,
                    "schema": TRANSLATIONS_SCHEMA,
                }
            },
        }
        if self._reasoning_effort != "none":
            request["reasoning"] = {"effort": self._reasoning_effort}

        response = self._client.responses.create(**request)
        raw_text = _extract_text_from_response(response)
        incomplete = None
        if getattr(response, "incomplete_details", None):
            incomplete = str(response.incomplete_details)

        usage = None
        if getattr(response, "usage", None):
            usage = dict(response.usage)
        return OpenAIResponsePayload(
            raw_text=raw_text,
            status=getattr(response, "status", None),
            incomplete_details=incomplete,
            usage=usage,
        )


def _extract_text_from_response(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    # Compatibility fallback for older/different SDK response shapes.
    output = getattr(response, "output", None)
    if isinstance(output, list):
        for item in output:
            content = getattr(item, "content", None)
            if not isinstance(content, list):
                continue
            for part in content:
                text = getattr(part, "text", None)
                if isinstance(text, str) and text:
                    return text
    raise RuntimeError("OpenAI response does not contain output text")
