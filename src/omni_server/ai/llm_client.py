"""Abstract base class and interfaces for LLM client implementations."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for LLM client."""

    provider: str  # openai, anthropic, ollama
    model: str
    api_key: str
    base_url: Optional[str] = None  # For alternative providers
    timeout_seconds: int = 30
    max_tokens: int = 4000


@dataclass
class LLMResponse:
    """Response from LLM API."""

    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_seconds: float
    model_used: str
    cached: bool = False


class BaseLLMClient(ABC):
    """Abstract base class for LLM client implementations.

    Implementations:
    - OpenAIClient (primary, gpt-4o-mini)
    - AnthropicClient (fallback, claude-3-5-sonnet)
    - OllamaClient (cost control, local models)
    """

    def __init__(self, config: LLMConfig):
        """Initialize LLM client with configuration."""
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate required configuration."""
        if not self.config.api_key:
            raise ValueError(f"{self.config.provider} requires API key")

    @abstractmethod
    async def complete(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Send completion request to LLM API.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt to set context

        Returns:
            LLMResponse with content and token usage

        Raises:
            ConnectionError: If API request fails
            ValueError: If response format is invalid
        """
        pass

    @abstractmethod
    async def complete_json(self, prompt: str, system_prompt: str | None = None) -> dict[str, Any]:
        """Send completion request and parse JSON response.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt to set context

        Returns:
            Parsed JSON object from LLM response

        Raises:
            ConnectionError: If API request fails
            ValueError: If response is not valid JSON
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this LLM provider."""
        pass

    async def health_check(self) -> bool:
        """Check if LLM provider is accessible.

        Returns:
            True if provider responds successfully
        """
        try:
            start_time = datetime.utcnow()
            response = await self.complete("test", system_prompt="test")
            duration = (datetime.utcnow() - start_time).total_seconds()
            return duration < 10 and response.content != ""
        except Exception:
            return False
