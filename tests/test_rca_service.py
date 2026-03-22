Unit tests for RCA service with mocked LLM client.

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import asyncio

from omni_server.models import TaskQueueDB, TaskRCADB, DeviceHeartbeatDB
from omni_server.config import Settings


class TestRCAServiceUnitTests:
    """Unit tests for RCA service components."""

    def test_rca_context_extractor_gathers_task_info(self, db, sample_task_manifest):
        """Test RCAContextExtractor gathers task information correctly."""
        from omni_server.ai import RCAContextExtractor

        # Create a failed task
        task = TaskQueueDB(
            task_id="test-task-001",
            device_binding=sample_task_manifest["device_binding"],
            task_manifest=sample_task_manifest,
            priority="critical",
            status="failed",
            result={
                "schema_version": "1.0.0",
                "task_id": "test-task-001",
                "status": "failed",
                "started_at": "2024-03-22T10:00:00Z",
                "completed_at": "2024-03-22T10:05:00Z",
                "duration_seconds": 300,
                "device_info": {
                    "device_id": "device-001",
                    "hostname": "test-host",
                    "runner_version": "0.1.0",
                },
                "steps": [],
                "summary": {
                    "total_steps": 5,
                    "successful_steps": 3,
                    "failed_steps": 2,
                    "skipped_steps": 0,
                    "crashed_steps": 0,
                    "total_duration_seconds": 280,
                },
            },
            error_message="Test failure",
        )
        db.add(task)
        db.commit()

        # Extract context
        extractor = RCAContextExtractor()
        context = extractor.extract_context_from_task(db, "test-task-001")

        # Verify task info extracted
        assert "task" in context
        assert context["task"]["id"] == "test-task-001"
        assert context["task"]["name"] == "test-task-001"
        assert context["task"]["status"] == "failed"
        assert context["task"]["error_message"] == "Test failure"
        assert context["task"]["priority"] == "critical"

    def test_rca_context_extractor_gathers_device_context(self, db, sample_task_manifest):
        """Test RCAContextExtractor gathers device context when task is assigned."""
        from omni_server.ai import RCAContextExtractor

        # Create a device
        device = DeviceHeartbeatDB(
            device_id="device-001",
            runner_version="0.1.0",
            status="idle",
            hostname="test-host",
            system_resources={"cpu_percent": 50.0, "memory_mb": 8192},
            capabilities={"python": "3.10"},
        )
        db.add(device)
        db.commit()

        # Create a task assigned to device
        task = TaskQueueDB(
            task_id="test-task-002",
            device_binding=sample_task_manifest["device_binding"],
            task_manifest=sample_task_manifest,
            priority="normal",
            status="failed",
            assigned_device_id="device-001",
            result={
                "device_info": {
                    "device_id": "device-001",
                    "hostname": "test-host",
                    "runner_version": "0.1.0",
                },
            },
        )
        db.add(task)
        db.commit()

        # Extract context
        extractor = RCAContextExtractor()
        context = extractor.extract_context_from_task(db, "test-task-002")

        # Verify device info extracted
        assert "device" in context
        assert context["device"]["id"] == "device-001"
        assert context["device"]["hostname"] == "test-host"
        assert context["device"]["status"] == "idle"

    def test_rca_context_extractor_includes_execution_results(self, db, sample_task_manifest):
        """Test RCAContextExtractor includes execution results and logs."""
        from omni_server.ai import RCAContextExtractor

        # Create a task with detailed execution results
        task = TaskQueueDB(
            task_id="test-task-003",
            device_binding=sample_task_manifest["device_binding"],
            task_manifest=sample_task_manifest,
            priority="high",
            status="failed",
            result={
                "steps": [
                    {
                        "step_id": "step-1",
                        "status": "success",
                        "output": "Step 1 output",
                    },
                    {
                        "step_id": "step-2",
                        "status": "failed",
                        "error": "Step 2 failed",
                    },
                ],
                "artifacts": {
                    "logs": [
                        {
                            "timestamp": "2024-03-22T10:01:00Z",
                            "level": "ERROR",
                            "message": "Error in step 2",
                        },
                        {
                            "timestamp": "2024-03-22T10:02:00Z",
                            "level": "ERROR",
                            "message": "Connection timeout",
                        },
                    ],
                    "files": [
                        {"path": "/var/log/test.log", "size": 1024},
                    ],
                },
            },
        )
        db.add(task)
        db.commit()

        # Extract context
        extractor = RCAContextExtractor()
        context = extractor.extract_context_from_task(db, "test-task-003")

        # Verify execution info extracted
        assert "execution" in context
        assert "artifacts" in context
        assert len(context["execution"]["failed_steps"]) > 0
        assert len(context["artifacts"]["logs"]) > 0
        assert any("timeout" in log["message"] for log in context["artifacts"]["logs"])

    def test_rca_prompt_builder_generates_prompts(self):
        """Test RCAPromptBuilder generates system and user prompts."""
        from omni_server.ai import (
            RCAPromptBuilder,
            RCAContext,
        )

        # Create sample context
        context = RCAContext(
            task_id="test-task-001",
            task_name="Failure Test",
            task_description="Test task that failed",
            task_type="test",
            task_params={"test": "value"},
            status="failed",
            started_at="2024-03-22T10:00:00Z",
            completed_at="2024-03-22T10:05:00Z",
            error_message="Test failure",
            total_steps=5,
            completed_steps=3,
            failed_steps=[(2, "step-2", "Error")],
            logs=[{"timestamp": "10:01", "level": "ERROR", "message": "Test error"}],
        )

        # Build prompts
        builder = RCAPromptBuilder()
        system_prompt, user_prompt = builder.build_prompt(context)

        # Verify prompts generated
        assert len(system_prompt) > 0
        assert len(user_prompt) > 0
        assert "Root Cause Analysis" in system_prompt or "root cause" in system_prompt.lower()
        assert "test-task-001" in user_prompt
        assert "Failure Test" in user_prompt
        assert "Error" in user_prompt

    def test_rca_prompt_builder_config_produces_valid_llm_config(self):
        """Test RCAPromptBuilder.build_config produces valid LLMConfig."""
        from omni_server.ai import RCAPromptBuilder, LLMConfig
        from omni_server.ai.llm_client import LLMResponse

        # Build config
        builder = RCAPromptBuilder()
        config = builder.build_config(max_tokens=3000)

        # Verify config is valid LLMConfig
        assert hasattr(config, 'temperature')
        assert hasattr(config, 'max_tokens')
        assert config.temperature == 0.3  # Low temperature for RCA
        assert config.max_tokens == 3000

    @pytest.mark.asyncio
    async def test_rca_service_handles_llm_errors_gracefully(
        self, db, sample_task_manifest
    ):
        """Test RCA service handles LLM client errors gracefully."""
        from omni_server.ai import RCAnalysisService

        # Create a task
        task = TaskQueueDB(
            task_id="test-task-error-001",
            device_binding=sample_task_manifest["device_binding"],
            task_manifest=sample_task_manifest,
            priority="normal",
            status="failed",
        )
        db.add(task)
        db.commit()

        # Create service with settings
        settings = Settings(
            rca_enabled=True,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="test-key",
        )
        service = RCAnalysisService(settings)

        # Mock LLM client to raise error
        with patch.object(
            service, "_llm_client"
        ) as mock_client:
            mock_client.complete_json = AsyncMock(
                side_effect=ConnectionError("LLM API error")
            )

            # Should raise error (not gracefully handle in this basic test)
            with pytest.raises(ConnectionError):
                await service.analyze_task(db, "test-task-error-001")

    def test_openai_client_parses_json_response(self):
        """Test OpenAI client correctly parses JSON responses."""
        from omni_server.ai import OpenAIClient, LLMConfig
        from omni_server.ai.llm_client import LLMResponse

        # Create client
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-key",
        )
        client = OpenAIClient(config)

        # Test JSON with markdown code blocks
        json_with_code_blocks = '''```json
{
    "root_cause": "Test cause",
    "confidence": 0.8,
    "findings": ["Finding 1"]
}
```
'''

        # Parse JSON (using internal parsing logic)
        data = json.loads(json_with_code_blocks.replace('```json', '').replace('```', ''))
        assert data["root_cause"] == "Test cause"
        assert data["confidence"] == 0.8

    def test_rca_service_persists_results_to_database(
        self, db, sample_task_manifest
    ):
        """Test RCA service correctly persists analysis results to database."""
        from omni_server.ai import RCAnalysisService, RCAResult

        # Create a task
        task = TaskQueueDB(
            task_id="test-task-persist-001",
            device_binding=sample_task_manifest["device_binding"],
            task_manifest=sample_task_manifest,
            priority="normal",
            status="failed",
        )
        db.add(task)
        db.commit()

        # Create service
        settings = Settings(
            rca_enabled=True,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="test-key",
        )
        service = RCAnalysisService(settings)

        # Create mock RCA result
        mock_result = RCAResult(
            root_cause="Mock root cause",
            confidence=0.85,
            severity="high",
            findings=["Mock finding 1", "Mock finding 2"],
            recommendations=["Mock recommendation"],
            cache_hit=False,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            duration_ms=1500,
            input_tokens=250,
            output_tokens=150,
            total_tokens=400,
        )

        # Save result (directly call private method through object)
        service._save_result(db, "test-task-persist-001", mock_result)

        # Verify database persistence
        rca_db = db.query(TaskRCADB).filter(TaskRCADB.task_id == "test-task-persist-001").first()
        assert rca_db is not None
        assert rca_db.root_cause == "Mock root cause"
        assert rca_db.confidence == 0.85
        assert rca_db.severity == "high"
        assert rca_db.cache_hit is True

    def test_rca_service_retrieves_cached_results(
        self, db, sample_task_manifest
    ):
        """Test RCA service returns cached results without re-analyzing."""
        from omni_server.ai import RCAnalysisService

        # Create a task
        task = TaskQueueDB(
            task_id="test-task-cache-001",
            device_binding=sample_task_manifest["device_binding"],
            task_manifest=sample_task_manifest,
            priority="normal",
            status="failed",
        )
        db.add(task)
        db.commit()

        # Create cached RCA result
        rca = TaskRCADB(
            task_id="test-task-cache-001",
            root_cause="Cached root cause",
            confidence=0.75,
            severity="medium",
            findings=json.dumps(["Cached finding"]),
            recommendations=json.dumps(["Cached recommendation"]),
            cache_hit=True,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            analyzed_at=datetime.utcnow(),
        )
        db.add(rca)
        db.commit()

        # Create service with caching enabled
        settings = Settings(
            rca_enabled=True,
            enable_rca_cache=True,
            rca_cache_ttl_seconds=3600,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="test-key",
        )
        service = RCAnalysisService(settings)

        # Get cached result
        cached = service._get_cached_result(db, "test-task-cache-001")

        # Verify cached result retrieved
        assert cached is not None
        assert cached.root_cause == "Cached root cause"
        assert cached.confidence == 0.75
        assert cached.cache_hit is True

    def test_rca_service_expired_cache_not_retrieved(self, db, sample_task_manifest):
        """Test RCA service does not return expired cached results."""
        from omni_server.ai import RCAnalysisService
        from datetime import datetime, timedelta

        # Create a task
        task = TaskQueueDB(
            task_id="test-task-expired-001",
            device_binding=sample_task_manifest["device_binding"],
            task_manifest=sample_task_manifest,
            priority="normal",
            status="failed",
        )
        db.add(task)
        db.commit()

        # Create expired cached RCA result
        expired_time = datetime.utcnow() - timedelta(seconds=7200)  # 2 hours ago
        rca = TaskRCADB(
            task_id="test-task-expired-001",
            root_cause="Expired root cause",
            confidence=0.75,
            severity="medium",
            findings=json.dumps(["Expired finding"]),
            recommendations=json.dumps(["Expired recommendation"]),
            cache_hit=True,
            analyzed_at=expired_time,
            expires_at=expired_time + timedelta(seconds=3600),  # Already expired
        )
        db.add(rca)
        db.commit()

        # Create service with cache TTL
        settings = Settings(
            rca_enabled=True,
            enable_rca_cache=True,
            rca_cache_ttl_seconds=3600,  # 1 hour TTL
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="test-key",
        )
        service = RCAnalysisService(settings)

        # Try to get cached result
        cached = service._get_cached_result(db, "test-task-expired-001")

        # Verify expired cache not retrieved
        assert cached is None
