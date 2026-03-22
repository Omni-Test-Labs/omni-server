"""Core RCA analysis service with caching and rate limiting."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from omni_server.ai.context_extractor import RCAContextExtractor
from omni_server.ai.llm_client import LLMConfig, LLMResponse
from omni_server.ai.openai_client import OpenAIClient
from omni_server.ai.rca_prompt_builder import RCAContext, RCAPromptBuilder
from omni_server.config import Settings
from omni_server.models import TaskQueueDB, TaskRCADB

logger = logging.getLogger(__name__)


class RCAResult:
    """Result from RCA analysis."""

    def __init__(
        self,
        root_cause: str,
        confidence: float,
        severity: str,
        findings: list[str],
        recommendations: list[str],
        cache_hit: bool = False,
        llm_provider: str = "unknown",
        llm_model: str = "unknown",
        duration_ms: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ):
        self.root_cause = root_cause
        self.confidence = confidence
        self.severity = severity
        self.findings = findings
        self.recommendations = recommendations
        self.cache_hit = cache_hit
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.duration_ms = duration_ms
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "severity": self.severity,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "cache_hit": self.cache_hit,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


class RCAnalysisService:
    """Core service for RCA analysis with caching and rate limiting."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._prompt_builder = RCAPromptBuilder()
        self._context_extractor = RCAContextExtractor()
        llm_config = LLMConfig(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
        )
        self._llm_client = OpenAIClient(config=llm_config)

    async def analyze_task(
        self,
        db: Session,
        task_id: str,
        force_refresh: bool = False,
    ) -> RCAResult:
        """Analyze a failed task and provide root cause analysis.

        Args:
            db: Database session
            task_id: ID of the task to analyze
            force_refresh: If True, bypass cache and force re-analysis

        Returns:
            RCAResult with analysis findings

        Raises:
            ValueError: If RCA is disabled or task not found
        """
        if not self._settings.rca_enabled:
            raise ValueError("RCA analysis is disabled in settings")

        task = db.query(TaskQueueDB).filter(TaskQueueDB.task_id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if not force_refresh:
            cached_result = self._get_cached_result(db, task_id)
            if cached_result:
                logger.info(f"Returning cached RCA result for task {task_id}")
                return cached_result

        check_rate_limit(self._settings)

        start_time = datetime.utcnow()

        try:
            extracted = self._context_extractor.extract_context_from_task(db, task_id)
            context = self._build_rca_context(extracted)
            system_prompt, user_prompt = self._prompt_builder.build_prompt(context)

            response_data = await self._llm_client.complete_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000.0
            result = self._build_result_from_response(response_data, duration_ms)

            self._save_result(db, task_id, result, cache_hit=False)

            return result

        except Exception as e:
            logger.error(f"RCA analysis failed for task {task_id}: {e}")
            raise

    def _get_cached_result(self, db: Session, task_id: str) -> RCAResult | None:
        """Check for valid cached result."""
        if not self._settings.enable_rca_cache:
            return None

        rca_db = db.query(TaskRCADB).filter(TaskRCADB.task_id == task_id).first()
        if not rca_db or not rca_db.cache_hit:
            return None

        ttl = timedelta(seconds=self._settings.rca_cache_ttl_seconds)
        if rca_db.expires_at and datetime.utcnow() > rca_db.expires_at:
            logger.info(f"RCA cache expired for task {task_id}")
            return None

        return RCAResult(
            root_cause=str(rca_db.root_cause) if rca_db.root_cause else "",
            confidence=float(rca_db.confidence) if rca_db.confidence else 0.0,
            severity=str(rca_db.severity) if rca_db.severity else "medium",
            findings=json.loads(str(rca_db.findings)) if rca_db.findings else [],
            recommendations=json.loads(str(rca_db.recommendations))
            if rca_db.recommendations
            else [],
            cache_hit=True,
            llm_provider=str(rca_db.llm_provider) if rca_db.llm_provider else "",
            llm_model=str(rca_db.llm_model) if rca_db.llm_model else "",
            duration_ms=0.0,
            input_tokens=int(rca_db.input_tokens) if rca_db.input_tokens else 0,
            output_tokens=int(rca_db.output_tokens) if rca_db.output_tokens else 0,
            total_tokens=int(rca_db.total_tokens) if rca_db.total_tokens else 0,
        )

    def _build_rca_context(self, extracted: dict[str, Any]) -> RCAContext:
        """Map extracted context to RCAContext."""
        task_info = extracted.get("task", {})
        device_info = extracted.get("device") or {}
        execution_info = extracted.get("execution") or {}
        artifacts_info = extracted.get("artifacts") or {}

        return RCAContext(
            task_id=task_info.get("id", ""),
            task_name=task_info.get("name", ""),
            task_description=task_info.get("description", ""),
            task_type=task_info.get("type", ""),
            task_params=task_info.get("params", {}),
            device_id=device_info.get("id"),
            device_hostname=device_info.get("hostname"),
            device_ip=device_info.get("ip_address"),
            device_status=device_info.get("status"),
            status=task_info.get("status", "unknown"),
            started_at=task_info.get("started_at"),
            completed_at=task_info.get("completed_at"),
            error_message=task_info.get("error_message"),
            retry_count=task_info.get("retry_count", 0),
            max_retries=task_info.get("max_retries", 3),
            total_steps=execution_info.get("total_steps", 0),
            completed_steps=execution_info.get("completed_steps", 0),
            failed_steps=execution_info.get("failed_steps", []),
            logs=artifacts_info.get("logs", []),
            artifacts=artifacts_info.get("files", []),
        )

    def _build_result_from_response(self, data: dict[str, Any], duration_ms: float) -> RCAResult:
        """Build RCAResult from LLM response data."""
        try:
            return RCAResult(
                root_cause=data.get("root_cause", "Unknown cause"),
                confidence=float(data.get("confidence", 0.0)),
                severity=data.get("severity", "medium"),
                findings=data.get("findings", []),
                recommendations=data.get("recommendations", []),
                cache_hit=False,
                llm_provider=self._llm_client.provider_name,
                llm_model=self._llm_client.config.model,
                duration_ms=duration_ms,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            )
        except Exception as e:
            logger.error(f"Failed to parse RCA response: {e}")
            return RCAResult(
                root_cause="Failed to parse LLM response",
                confidence=0.0,
                severity="high",
                findings=[f"Parse error: {str(e)}"],
                recommendations=["Check LLM response format"],
                cache_hit=False,
                llm_provider=self._llm_client.provider_name,
                llm_model=self._llm_client.config.model,
                duration_ms=duration_ms,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            )

    def _save_result(
        self,
        db: Session,
        task_id: str,
        result: RCAResult,
        cache_hit: bool = False,
    ) -> None:
        """Save or update RCA result in database."""
        rca_db = db.query(TaskRCADB).filter(TaskRCADB.task_id == task_id).first()

        if rca_db:
            rca_db.root_cause = result.root_cause
            rca_db.confidence = result.confidence
            rca_db.severity = result.severity
            rca_db.findings = json.dumps(result.findings)
            rca_db.recommendations = json.dumps(result.recommendations)
            rca_db.analyzed_at = datetime.utcnow()
            rca_db.llm_provider = result.llm_provider
            rca_db.llm_model = result.llm_model
            rca_db.duration_seconds = result.duration_ms / 1000.0
            rca_db.input_tokens = result.input_tokens
            rca_db.output_tokens = result.output_tokens
            rca_db.total_tokens = result.total_tokens
            rca_db.cache_hit = cache_hit
            rca_db.expires_at = None

        else:
            rca_db = TaskRCADB(
                task_id=task_id,
                root_cause=result.root_cause,
                confidence=result.confidence,
                severity=result.severity,
                findings=json.dumps(result.findings),
                recommendations=json.dumps(result.recommendations),
                analyzed_at=datetime.utcnow(),
                llm_provider=result.llm_provider,
                llm_model=result.llm_model,
                duration_seconds=result.duration_ms / 1000.0,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                related_patterns=json.dumps([]),
                next_steps=json.dumps([]),
                cache_hit=True,
            )
            db.add(rca_db)

        db.commit()


_rate_limit_cache: dict[str, list[datetime]] = {}


def check_rate_limit(settings: Settings) -> None:
    """Check if RCA rate limit has been exceeded.

    Raises:
        ValueError: If rate limit exceeded
    """
    if settings.max_rca_per_hour <= 0:
        return

    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)

    if "rca_requests" not in _rate_limit_cache:
        _rate_limit_cache["rca_requests"] = []

    requests = _rate_limit_cache["rca_requests"]
    recent_requests = [t for t in requests if t > one_hour_ago]

    if len(requests) >= settings.max_rca_per_hour:
        raise ValueError(
            f"RCA rate limit exceeded: {len(recent_requests)}/{settings.max_rca_per_hour} per hour"
        )

    requests.append(now)
    _rate_limit_cache["rca_requests"] = requests
