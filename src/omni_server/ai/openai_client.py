"""OpenAI LLM client implementation."""

import json
import time
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from omni_server.ai.llm_client import BaseLLMClient, LLMConfig, LLMResponse


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client (gpt-4o-mini, gpt-4o, etc.)."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_TIMEOUT = 30

    def __init__(self, config: LLMConfig):
        """Initialize OpenAI client."""
        super().__init__(config)
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.timeout = config.timeout_seconds
        self.max_tokens = config.max_tokens

    async def complete(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Send completion request to OpenAI API."""
        start_time = datetime.utcnow()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

                data = response.json()

                if "choices" not in data or not data["choices"]:
                    raise ValueError("Invalid response format: missing 'choices' field")

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                duration_seconds = (datetime.utcnow() - start_time).total_seconds()

                return LLMResponse(
                    content=content,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    duration_seconds=duration_seconds,
                    model_used=self.config.model,
                    cached=False,
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
                raise ConnectionError(f"OpenAI API request failed: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"OpenAI API connection error: {e}")
                raise ConnectionError(f"Failed to connect to OpenAI API: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from OpenAI API: {e}")
                raise ValueError("Invalid JSON response from OpenAI API")
            except KeyError as e:
                logger.error(f"Missing required field in OpenAI response: {e}")
                raise ValueError(f"Missing required field in OpenAI response: {e}")

    async def complete_json(self, prompt: str, system_prompt: str | None = None) -> dict[str, Any]:
        """Send completion request and parse JSON response."""
        # Request JSON response
        json_prompt = f"{prompt}\n\nRespond with a valid JSON object only, no other text."
        response = await self.complete(json_prompt, system_prompt)

        # Extract JSON from response
        content = response.content.strip()

        # Try to find JSON in the response
        if content.startswith("```json"):
            content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
        elif content.startswith("```"):
            content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"LLM response is not valid JSON: {content[:500]}")

    @property
    def provider_name(self) -> str:
        """Return the name of this LLM provider."""
        return "openai"
