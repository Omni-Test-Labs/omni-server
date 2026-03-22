# RCA System Developer Guide

This guide explains how to customize and extend the AI-powered Root Cause Analysis (RCA) system.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Component Structure](#component-structure)
- [Adding Custom LLM Providers](#adding-custom-llm-providers)
- [Customizing Prompts](#customizing-prompts)
- [Extending Context Extraction](#extending-context-extraction)
- [Integrating RCA into Task Queues](#integrating-rca-into-task-queues)
- [Testing RCA Components](#testing-rca-components)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Omni-Web UI                          │
│                  (RCAViewer Component)                      │
└────────────────────┬─────────────────────────────────────┘
                     │ HTTP API
┌────────────────────▼─────────────────────────────────────┐
│              Omni-Server API Layer                      │
│         (tasks/{id}/rca endpoints)                         │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              RCAnalysisService                           │
│  • Cache management                                         │
│  • Rate limiting                                         │
│  • Context extraction                                        │
└──────┬────────────────────┬───────────────────────────┘
       │                    │
┌──────▼────────┐    ┌──────▼──────────────────────────┐
│ RCAContextExtractor│    │    RCAPromptBuilder       │
│  • Task info       │    │  • System prompt            │
│  • Device context  │    │  • User prompt              │
│  • Execution logs  │    │  • LLMConfig                │
└────────────────────┘    └──────────────────────────────┘
                           │
              ┌──────────────▼──────────────────────┐
              │        BaseLLMClient               │
              │    • complete()                   │
              │    • complete_json()              │
              └──────────────┬───────────────────────┘
                             │
              ┌──────────────▼──────────────────────┐
              │       OpenAIClient                │
              │  • HTTP async calls              │
              │  • JSON parsing                  │
              │  • Token tracking               │
              └──────────────┬──────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   OpenAI API       │
                    │   (GPT-4o-mini)    │
                    └───────────────────┘
```

### Data Flow

1. Task fails → Auto-trigger or manual request
2. `RCAnalysisService` extracts context (task, device, logs)
3. `RCAPromptBuilder` creates prompts
4. `OpenAIClient` calls LLM API
5. Results cached in `TaskRCADB` table
6. Results returned via API to UI

---

## Component Structure

### Directory Layout

```
src/omni_server/ai/
├── __init__.py                 # Module exports
├── llm_client.py              # Abstract LLM client
├── openai_client.py           # OpenAI implementation
├── context_extractor.py       # Context extraction service
├── rca_prompt_builder.py      # Prompt construction
└── rca_service.py            # Main RCA service

src/omni_server/
├── models.py                  # TaskRCADB model
├── config.py                  # RCA configuration fields
└── api/tasks.py               # RCA API endpoints
```

### Key Classes

| Class | File | Responsibility |
|-------|------|-----------------|
| `BaseLLMClient` | `llm_client.py` | Abstract LLM interface |
| `OpenAIClient` | `openai_client.py` | OpenAI API client |
| `RCAContextExtractor` | `context_extractor.py` | Extract task context |
| `RCAPromptBuilder` | `rca_prompt_builder.py` | Build analysis prompts |
| `RCAnalysisService` | `rca_service.py` | Main orchestration |
| `TaskRCADB` | `models.py` | Database model |

---

## Adding Custom LLM Providers

### Step 1: Extend BaseLLMClient

```python
from omni_server.ai.llm_client import BaseLLMClient, LLMConfig, LLMResponse

class CustomLLMClient(BaseLLMClient):
    """Custom LLM client implementation."""

    DEFAULT_BASE_URL = "https://api.custom-llm.com/v1"
    DEFAULT_TIMEOUT = 30

    def __init__(self, config: LLMConfig):
        """Initialize custom LLM client."""
        super().__init__(config)
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.timeout = config.timeout_seconds
        self.max_tokens = config.max_tokens

    async def complete(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Send completion request to custom LLM API."""
        # Implement your API call here
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await client.post(
                f"{self.base_url}/completions",
                json={"messages": messages, "max_tokens": self.max_tokens},
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
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

    async def complete_json(self, prompt: str, system_prompt: str | None = None) -> dict:
        """Send completion request and parse JSON response."""
        response = await self.complete(prompt, system_prompt)
        content = response.content.strip()

        # Handle JSON in markdown code blocks
        if content.startswith('```json'):
            content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
        elif content.startswith('```'):
            content = content[3:]
            if content.endswith('```'):
                content = content[:-3]

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"LLM response is not valid JSON: {content[:500]}")

    @property
    def provider_name(self) -> str:
        """Return the name of this LLM provider."""
        return "custom"

    async def health_check(self) -> bool:
        """Check if LLM provider is accessible."""
        try:
            response = await self.complete("test", system_prompt="test")
            return response.content != ""
        except Exception:
            return False
```

### Step 2: Configure Custom Provider

```python
from omni_server.config import Settings

settings = Settings(
    rca_enabled=True,
    llm_provider="custom",  # Your provider name
    llm_model="custom-model-v1",
    llm_api_key="your-custom-api-key",
    llm_base_url="https://api.custom-llm.com/v1",  # Optional
)

# Create service instance
from omni_server.ai import RCAnalysisService

rca_service = RCAnalysisService(settings)
```

### Step 3: Update Base Class

```python
# In llm_client.py, update __init__ registration
from omni_server.ai.openai_client import OpenAIClient
from omni_server.ai.custom_client import CustomLLMClient

# Provider mapping
LLM_CLIENTS = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,  # Future
    "ollama": OllamaClient,  # Future
    "custom": CustomLLMClient,  # Your provider
}

def get_llm_client(config: LLMConfig) -> BaseLLMClient:
    """Factory function to create LLM client based on provider."""
    client_class = LLM_CLIENTS.get(config.provider)
    if not client_class:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
    return client_class(config)
```

---

## Customizing Prompts

### Modifying System Prompt

```python
from omni_server.ai import RCAPromptBuilder

class CustomPromptBuilder(RCAPromptBuilder):
    """Custom prompt builder with specialized prompts."""

    SYSTEM_PROMPT = """Your custom system prompt here.
    
    Custom instructions for your specific use case...
    """

    def build_prompt(
        self,
        context,
        include_debugging: bool = False,
    ) -> tuple[str, str]:
        """Build custom prompts for your use case."""
        system_prompt = self._get_system_prompt(include_debugging)
        user_prompt = self._build_user_prompt(context)

        return system_prompt, user_prompt

    def _build_user_prompt(self, context) -> str:
        """Build custom user prompt with your context format."""
        prompt_parts = [
            "# Custom Analysis Request",
            "",
            f"Task: {context.task_name}",
            f"Error: {context.error_message}",
            "",
            "## Custom Analysis Sections",
            "",
            "1. **Context Analysis**",
            "   Analyze the execution context...",
            "",
            "2. **Pattern Detection**",
            "   Look for specific patterns...",
            "",
            "## custom Response Format",
            "{...}",
        ]

        return "\n".join(prompt_parts)
```

### Adding Custom Context Fields

```python
from omni_server.ai import RCAContext

class CustomRCAContext(RCAContext):
    """Extended context with custom fields."""

    def __init__(
        self,
        task_id,
        task_name,
        task_description,
        task_type,
        task_params,
        device_id=None,
        device_hostname=None,
        device_ip=None,
        device_status=None,
        status="unknown",
        started_at=None,
        completed_at=None,
        error_message=None,
        retry_count=0,
        max_retries=3,
        total_steps=0,
        completed_steps=0,
        failed_steps=None,
        logs=None,
        artifacts=None,
        # Custom fields
        custom_field_1=None,
        custom_field_2=None,
    ):
        super().__init__(
            task_id, task_name, task_description, task_type, task_params,
            device_id, device_hostname, device_ip, device_status, status,
            started_at, completed_at, error_message, retry_count, max_retries,
            total_steps, completed_steps, failed_steps, logs, artifacts,
        )
        self.custom_field_1 = custom_field_1
        self.custom_field_2 = custom_field_2
```

---

## Extending Context Extraction

### Adding Custom Extraction Logic

```python
from omni_server.ai import RCAContextExtractor

class CustomContextExtractor(RCAContextExtractor):
    """Custom context extractor with additional data sources."""

    def extract_context_from_task(self, db: Session, task_id: str) -> dict:
        """Extract context with custom additions."""
        # Get base context
        context = super().extract_context_from_task(db, task_id)

        # Add custom data
        task = db.query(TaskQueueDB).filter(TaskQueueDB.id == task_id).first()

        # Example: Extract from custom table
        # custom_data = db.query(CustomDataTable).filter(CustomDataTable.task_id == task_id).all()
        # context["custom_data"] = [data.to_dict() for data in custom_data]

        return context

    def _extract_custom_artifacts(self, task: TaskQueueDB) -> list[dict]:
        """Extract custom artifact types."""
        artifacts = []

        if task.result:
            # Example: Extract specific log files
            log_files = task.result.get("artifacts", {}).get("logs", [])
            for log in log_files:
                if log.get("severity") in ["ERROR", "CRITICAL"]:
                    artifacts.append({
                        "type": "error_log",
                        "file": log.get("file"),
                        "message": log.get("message"),
                        "timestamp": log.get("timestamp"),
                    })

        return artifacts
```

---

## Integrating RCA into Task Queues

### Manual Trigger

```python
from omni_server.ai import RCAnalysisService
from omni_server.config import Settings

settings = Settings(rca_enabled=True, ...)
service = RCAnalysisService(settings)

async def handle_task_failure(db: Session, task_id: str):
    """Manually trigger RCA on task failure."""
    try:
        result = await service.analyze_task(db, task_id, force_refresh=True)
        print(f"RCA completed for task {task_id}")
        print(f"Root cause: {result.root_cause}")
    except Exception as e:
        print(f"RCA failed for task {task_id}: {e}")
```

### Auto-Trigger Integration

The `TaskQueueManager.record_result()` method automatically triggers RCA when:

- `auto_rca_on_failure=True` (configuration)
- Task status is `failed`, `crashed`, or `timeout`
- RCA is enabled

```python
# In queue/__init__.py (already implemented)

def record_result(db: Session, task_id: str, result: dict):
    """Record task execution result."""
    task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()

    if task:
        task.result = result
        task.status = result.get("status", "failed")
        task.updated_at = datetime.utcnow()
        db.commit()

        # Auto-trigger RCA on failure
        if task.status in ["failed", "crashed", "timeout"]:
            config = _config_cache or Settings()
            if config.auto_rca_on_failure:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(trigger_rca_analysis(task_id, db))
                    else:
                        loop.run_until_complete(trigger_rca_analysis(task_id, db))
                except RuntimeError:
                    logger.warning(f"No event loop for task {task_id}")

    return task
```

### Custom Trigger Logic

```python
from omni_server.ai import RCAnalysisService

async def custom_trigger_logic(db: Session, task_id: str):
    """Custom trigger logic for specific scenarios."""

    # Only trigger for critical tasks
    task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()
    if task and task.priority != "critical":
        return

    # Only trigger for specific error patterns
    if task.error_message and "timeout" not in task.error_message.lower():
        return

    # Only trigger if this is a recurring issue
    from omni_server.models import TaskRCADB
    recent_rca = db.query(TaskRCADB).filter(
        TaskRCADB.root_cause.contains("timeout")
    ).count()
    if recent_rca < 3:
        return

    # Trigger RCA
    settings = Settings(rca_enabled=True, ...)
    service = RCAnalysisService(settings)
    await service.analyze_task(db, task_id, force_refresh=True)
```

---

## Testing RCA Components

### Unit Testing Context Extractor

```python
import pytest
from sqlalchemy.orm import Session
from omni_server.ai import RCAContextExtractor

def test_context_extractor_with_device(db: Session):
    """Test context extraction with device information."""
    # Create test data
    task = create_test_task(db)
    device = create_test_device(db, task.assigned_device_id)

    # Extract context
    extractor = RCAContextExtractor()
    context = extractor.extract_context_from_task(db, task.task_id)

    # Verify
    assert "device" in context
    assert context["device"]["id"] == device.device_id
    assert context["device"]["hostname"] == device.hostname
```

### Unit Testing Prompt Builder

```python
def test_prompt_builder_custom_context():
    """Test prompt builder with custom context fields."""
    from omni_server.ai import RCAContext, RCAPromptBuilder

    custom_context = RCAContext(
        task_id="test-001",
        task_name="Test Task",
        task_type="test",
        task_params={"test": "value"},
        status="failed",
        error_message="Test error",
        logs=[{"timestamp": "10:00", "level": "ERROR", "message": "Error"}],
        custom_field_1="custom_value_1",
        custom_field_2="custom_value_2",
    )

    builder = RCAPromptBuilder()
    system_prompt, user_prompt = builder.build_prompt(custom_context)

    assert "Test Task" in user_prompt
    assert "Test error" in user_prompt
```

### Testing LLM Client

```python
import pytest
from unittest.mock import AsyncMock, patch
from omni_server.ai import OpenAIClient, LLMConfig
import httpx

@pytest.mark.asyncio
async def test_openai_client_json_parsing():
    """Test OpenAI client parses JSON correctly."""
    config = LLMConfig(
        provider="openai",
        model="gpt-4o-mini",
        api_key="test-key",
    )
    client = OpenAIClient(config)

    # Mock HTTP response with JSON in code blocks
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": '```json\n{"root_cause": "Test", "confidence": 0.8}\n```'
            }
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await client.complete_json("test prompt", "test system")

    assert result["root_cause"] == "Test"
    assert result["confidence"] == 0.8
```

### Integration Testing Full Flow

```python
@pytest.mark.asyncio
async def test_full_rca_flow(db: Session):
    """Test complete RCA flow from task failure to result."""
    from omni_server.models import TaskRCADB
    from omni_server.ai import RCAnalysisService

    # 1. Create failed task
    task = create_failed_task(db)

    # 2. Mock LLM response
    with patch.object(OpenAIClient, "complete_json") as mock_complete_json:
        mock_complete_json.return_value = AsyncMock(return_value={
            "root_cause": "Test failure cause",
            "confidence": 0.9,
            "severity": "high",
            "findings": ["Finding 1"],
            "recommendations": ["Recommendation 1"],
        })

        # 3. Trigger analysis
        settings = Settings(rca_enabled=True, llm_api_key="test")
        service = RCAnalysisService(settings)
        result = await service.analyze_task(db, task.task_id)

        # 4. Verify result
        assert result.root_cause == "Test failure cause"
        assert result.confidence == 0.9

        # 5. Verify database persistence
        rca_db = db.query(TaskRCADB).filter(TaskRCADB.task_id == task.task_id).first()
        assert rca_db is not None
        assert rca_db.root_cause == "Test failure cause"
```

---

## Code Examples Repository

### See Also

- [API.md](./API.md) - Complete API reference
- [USER_GUIDE.md](./USER_GUIDE.md) - Usage examples
- [OPERATIONS.md](./OPERATIONS.md) - Monitoring and troubleshooting
- [COSTS_AND_PERFORMANCE.md](./COSTS_AND_PERFORMANCE.md) - Cost optimization
- [AI_RCA_DESIGN.md](../../AI_RCA_DESIGN.md) - Original design document
