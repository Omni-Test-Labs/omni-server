API integration tests for AI RCA system.

import json
from unittest.mock import patch, AsyncMock
import pytest
from fastapi import status

from omni_server.config import Settings
from omni_server.models import TaskQueueDB, TaskRCADB


class TestRCAAPIEndpoints:
    """Test suite for RCA API endpoints."""

    def test_get_rca_returns_503_when_rca_disabled(self, client, db):
        """Test GET /tasks/{id}/rca returns 503 when RCA disabled."""
        # Mock settings to disable RCA
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = False

            response = client.get("/api/v1/tasks/test-task-001/rca")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "disabled" in response.json()["detail"].lower()

    def test_get_rca_returns_404_for_nonexistent_task(self, client, db):
        """Test GET /tasks/{id}/rca returns 404 for non-existent task."""
        response = client.get("/api/v1/tasks/nonexistent-task/rca")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_rca_status_returns_503_when_rca_disabled(self, client, db):
        """Test GET /tasks/{id}/rca/status returns 503 when RCA disabled."""
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = False

            response = client.get("/api/v1/tasks/test-task-001/rca/status")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_get_rca_status_returns_false_for_nonexistent_task(self, client, db):
        """Test GET /tasks/{id}/rca/status returns 404 for non-existent task."""
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = True

            response = client.get("/api/v1/tasks/nonexistent-task/rca/status")
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_rca_status_not_available_without_cache(self, client, db, sample_task_manifest):
        """Test GET /tasks/{id}/rca/status returns not available when no cached result."""
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = True

            # Create a task
            task = TaskQueueDB(
                task_id="test-task-001",
                device_binding=sample_task_manifest["device_binding"],
                task_manifest=sample_task_manifest,
                priority="normal",
                status="failed",
            )
            db.add(task)
            db.commit()

            response = client.get("/api/v1/tasks/test-task-001/rca/status")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["rca_enabled"] is True
            assert data["rca_available"] is False

    def test_get_rca_status_available_with_cache(self, client, db, sample_task_manifest):
        """Test GET /tasks/{id}/rca/status returns available when cached result exists."""
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = True

            # Create a task
            task = TaskQueueDB(
                task_id="test-task-001",
                device_binding=sample_task_manifest["device_binding"],
                task_manifest=sample_task_manifest,
                priority="normal",
                status="failed",
            )
            db.add(task)
            db.commit()

            # Create cached RCA result
            rca = TaskRCADB(
                task_id="test-task-001",
                root_cause="Test root cause",
                confidence=0.85,
                severity="high",
                findings=json.dumps(["Finding 1", "Finding 2"]),
                recommendations=json.dumps(["Recommendation 1"]),
                cache_hit=True,
            )
            db.add(rca)
            db.commit()

            response = client.get("/api/v1/tasks/test-task-001/rca/status")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["rca_enabled"] is True
            assert data["rca_available"] is True
            assert "analyzed_at" in data

    def test_get_rca_returns_cache_hit_without_calling_llm(self, client, db, sample_task_manifest):
        """Test GET /tasks/{id}/rca returns cached result without calling LLM."""
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = True
            mock_settings.enable_rca_cache = True

            # Mock RCA service to verify it's not called
            with patch("omni_server.api.tasks.RCAnalysisService") as mock_service:
                # Create a task
                task = TaskQueueDB(
                    task_id="test-task-001",
                    device_binding=sample_task_manifest["device_binding"],
                    task_manifest=sample_task_manifest,
                    priority="normal",
                    status="failed",
                )
                db.add(task)
                db.commit()

                # Create cached RCA result
                rca = TaskRCADB(
                    task_id="test-task-001",
                    root_cause="Cached root cause",
                    confidence=0.75,
                    severity="medium",
                    findings=json.dumps(["Cached finding"]),
                    recommendations=json.dumps(["Cached recommendation"]),
                    cache_hit=True,
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                )
                db.add(rca)
                db.commit()

                # Call the API
                response = client.get("/api/v1/tasks/test-task-001/rca")

                # Verify response
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "rca" in data
                assert data["rca"]["root_cause"] == "Cached root cause"
                assert data["rca"]["cache_hit"] is True

                # Verify RCA service was not called (cache hit)
                assert not mock_service.called

    @pytest.mark.asyncio
    async def test_post_rca_calls_llm_when_force_refresh_true(self, client, db, sample_task_manifest):
        """Test POST /tasks/{id}/rca calls LLM when force_refresh=True."""
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = True
            mock_settings.llm_provider = "openai"
            mock_settings.llm_model = "gpt-4o-mini"
            mock_settings.llm_api_key = "test-key"

            # Mock RCA service
            from unittest.mock import MagicMock

            def _make_sync_mock():
                mock_obj = MagicMock()

                def analyze_task(*args, **kwargs):
                    return {
                        "root_cause": "Analyzed root cause",
                        "confidence": 0.9,
                        "severity": "critical",
                        "findings": ["Finding 1"],
                        "recommendations": ["Recommendation 1"],
                        "cache_hit": False,
                        "llm_provider": "openai",
                        "llm_model": "gpt-4o-mini",
                        "duration_ms": 1000,
                        "input_tokens": 200,
                        "output_tokens": 100,
                        "total_tokens": 300,
                    }

                mock_obj.analyze_task = analyze_task
                return mock_obj

            mock_service_instance = _make_sync_mock()

            with patch("omni_server.api.tasks.RCAnalysisService", return_value=mock_service_instance):
                # Create a task
                task = TaskQueueDB(
                    task_id="test-task-001",
                    device_binding=sample_task_manifest["device_binding"],
                    task_manifest=sample_task_manifest,
                    priority="normal",
                    status="failed",
                )
                db.add(task)
                db.commit()

                # Create old cached RCA result
                rca = TaskRCADB(
                    task_id="test-task-001",
                    root_cause="Old cached root cause",
                    confidence=0.7,
                    severity="medium",
                    findings=json.dumps(["Old finding"]),
                    recommendations=json.dumps(["Old recommendation"]),
                    cache_hit=True,
                )
                db.add(rca)
                db.commit()

                # Call the API with force_refresh
                response = client.post("/api/v1/tasks/test-task-001/rca", json={"force_refresh": True})

                # Verify response
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "rca" in data
                # Should return the analyzed result, not the cached one
                assert "Analyzed root cause" in str(data["rca"])

    def test_rate_limiting_exceeded(self, client, db, sample_task_manifest):
        """Test RCA API respects rate limiting."""
        from omni_server.ai.rca_service import _rate_limit_cache, check_rate_limit

        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = True
            mock_settings.max_rca_per_hour = 2  # Very low limit for testing
            mock_settings.enable_rca_cache = True

            # Clear rate limit cache
            _rate_limit_cache.clear()

            # Create a task
            task = TaskQueueDB(
                task_id="test-task-001",
                device_binding=sample_task_manifest["device_binding"],
                task_manifest=sample_task_manifest,
                priority="normal",
                status="failed",
            )
            db.add(task)
            db.commit()

            # First call should succeed
            check_rate_limit(mock_settings)
            # Second call should succeed
            check_rate_limit(mock_settings)

            # Third call should fail (rate limit exceeded)
            with pytest.raises(ValueError, match="rate limit exceeded"):
                check_rate_limit(mock_settings)

            # Clear cache for other tests
            _rate_limit_cache.clear()

    def test_post_rca_returns_503_when_disabled(self, client, db, sample_task_manifest):
        """Test POST /tasks/{id}/rca returns 503 when RCA disabled."""
        with patch("omni_server.api.tasks._settings") as mock_settings:
            mock_settings.rca_enabled = False

            # Create a task
            task = TaskQueueDB(
                task_id="test-task-001",
                device_binding=sample_task_manifest["device_binding"],
                task_manifest=sample_task_manifest,
                priority="normal",
            )
            db.add(task)
            db.commit()

            response = client.post("/api/v1/tasks/test-task-001/rca", json={})
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
