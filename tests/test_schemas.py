"""Tests for schema models."""

import pytest
from omni_server.schemas import HealthResponse, ErrorResponse


class TestHealthResponse:
    """Test HealthResponse schema."""

    def test_health_response_creation(self):
        """Test creating a HealthResponse instance."""
        response = HealthResponse(status="ok", version="1.0.0")
        assert response.status == "ok"
        assert response.version == "1.0.0"

    def test_health_response_serialization(self):
        """Test HealthResponse JSON serialization."""
        response = HealthResponse(status="healthy", version="2.0.1")
        data = response.model_dump()
        assert data["status"] == "healthy"
        assert data["version"] == "2.0.1"

    def test_health_response_model_json(self):
        """Test HealthResponse model_dump_json method."""
        response = HealthResponse(status="ok", version="1.0.0")
        json_str = response.model_dump_json()
        assert '"status":"ok"' in json_str
        assert '"version":"1.0.0"' in json_str


class TestErrorResponse:
    """Test ErrorResponse schema."""

    def test_error_response_creation(self):
        """Test creating an ErrorResponse instance."""
        error = ErrorResponse(detail="An error occurred")
        assert error.detail == "An error occurred"

    def test_error_response_serialization(self):
        """Test ErrorResponse JSON serialization."""
        error = ErrorResponse(detail="Resource not found")
        data = error.model_dump()
        assert data["detail"] == "Resource not found"

    def test_error_response_model_json(self):
        """Test ErrorResponse model_dump_json method."""
        error = ErrorResponse(detail="Invalid input")
        json_str = error.model_dump_json()
        assert '"detail":"Invalid input"' in json_str

    def test_error_response_empty_detail(self):
        """Test ErrorResponse with empty detail."""
        error = ErrorResponse(detail="")
        assert error.detail == ""
