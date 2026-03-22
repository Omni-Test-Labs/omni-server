# AI RCA (Root Cause Analysis) System Design

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [LLM Provider Selection](#llm-provider-selection)
3. [Prompt Engineering Design](#prompt-engineering-design)
4. [RCA Context Format](#rca-context-format)
5. [Data Models](#data-models)
6. [API Design](#api-design)
7. [Implementation Plan](#implementation-plan)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         omni-server                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐   │
│  │  Task Queue  │──────│   RCA        │──────│   LLM        │   │
│  │  Manager     │      │   Service    │      │   Client     │   │
│  └──────────────┘      └──────────────┘      └──────────────┘   │
│         │                     │                     │             │
│         │ on failure         │                     │             │
│         ▼                     ▼                     │             │
│  ┌──────────────┐      ┌──────────────┐              ▼             │
│  │   Database   │      │   RCA        │      ┌──────────────┐   │
│  │ (Task, RCA   │◄─────┤   Cache      │──────│ OpenAI API   │   │
│  │  Results)    │      │   (Redis)    │      │ / Anthropic   │   │
│  └──────────────┘      └──────────────┘      └──────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          omni-web                                │
├─────────────────────────────────────────────────────────────────┤
│  Task Detail View                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Task Information                                          │  │
│  │ Execution Results                                        │  │
│  │ ┌──────────────────────────────────────────────────────┐ │  │
│  │ │ AI RCA Analysis                                        │ │
│  │ │ Root Cause: ...                                       │ │
│  │ │ Recommendations: ...                                   │ │
│  │ │ Key Findings: ...                                     │ │
│  │ │ [Analyze Again]                                       │ │
│  │ └──────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Automatic RCA Trigger** - When a task fails (status=failed/timeout/crashed), automatically trigger RCA
2. **Cached Results** - Store RCA results to avoid re-analyzing same failure
3. **Multi-LLM Support** - Abstract LLM provider interface for easy switching
4. **Rate Limiting** - Control costs and prevent API abuse
5. **Asynchronous Processing** - Run RCA in background to avoid blocking task completion
6. **Configurable** - Automatic RCA trigger can be toggled on/off

---

## LLM Provider Selection

### Evaluation Criteria

| Provider | Cost | Quality | Speed | Open Source | API Quality | Recommendation |
|----------|------|---------|-------|-------------|-------------|----------------|
| **OpenAI GPT-4** | High | Excellent | Medium | No | Excellent | ✅ Primary (Quality) |
| **Anthropic Claude 3.5** | Medium | Excellent | Fast | No | Excellent | ✅ Alternative (Speed) |
| **Ollama (Local)** | Free | Good | Slow | Yes | Good | 🔧 For Cost Control |
| **DeepSeek** | Very Low | Good | Fast | No (API) | Good | 📦 Cost-Effective |

### Recommended Architecture

```
# Primary Provider (Production)
LLM_PROVIDER = "openai"
LLM_MODEL = "gpt-4o-mini"  # Cost-effective, good quality
LLM_API_KEY = "sk-..."

# Fallback Provider
LLM_FALLBACK_PROVIDER = "anthropic"
LLM_FALLBACK_MODEL = "claude-3-5-sonnet-20241022"

# Cost Control
RCA_ENABLED = true                   # Master toggle
AUTO_RCA_ON_FAILURE = false          # Automatic trigger (default off)
MAX_RCA_PER_HOUR = 100               # Rate limit
RCA_CACHE_TTL_SECONDS = 86400        # 24 hours cache
```

### Provider Comparison

**OpenAI GPT-4o-mini** (Recommended for Production)
- Cost: ~$0.15 / 1M tokens (input), $0.60 / 1M tokens (output)
- Quality: Excellent for log analysis
- Speed: Fast
- API: Best-in-class

**Anthropic Claude 3.5 Sonnet** (Alternative)
- Cost: ~$3 / 1M tokens (input), $15 / 1M tokens (output)
- Quality: Slightly better for complex reasoning
- Speed: Very fast
- API: Excellent

**Ollama (Local)** (Cost Control)
- Cost: Free (runs on own hardware)
- Quality: Depends on model (Llama 3.1 70B, Mixtral)
- Speed: Slow (CPU/GPU dependent)
- API: Simple HTTP wrapper

---

## Prompt Engineering Design

### Prompt Structure

```
SYSTEM PROMPT
↓
TASK CONTEXT (Task manifest, device info, status)
↓
EXECUTION RESULTS (Step-by-step results, logs, errors)
↓
ANALYSIS REQUEST (Root cause, recommendations, severity)
↓
LLM RESPONSE (Structured JSON)
```

### System Prompt Template

```
You are an expert test automation and debugging assistant for Omni-Test-Labs, 
a heterogenerous device testing platform.

Your role is to analyze failed task executions and provide actionable root cause analysis.

## Guidelines

1. Focus on the **most likely root cause** - Be specific, not generic
2. Provide **actionable recommendations** - What should the user do?
3. Consider **device context** - Device type, OS, capabilities matter
4. Analyze **failure patterns** - Look for recurrent issues
5. Prioritize findings** - Number and rank by severity

## Output Format

Return a JSON object with the following structure:
{
  "root_cause": "Specific cause of failure",
  "confidence": 0.0-1.0,
  "severity": "low|medium|high|critical",
  "findings": [
    {
      "category": "category_name",
      "description": "Detailed description",
      "evidence": ["log_line_1", "log_line_2"]
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "Specific action to take",
      "expected_outcome": "What this should achieve"
    }
  ],
  "related_patterns": ["pattern_1", "pattern_2"],
  "next_steps": ["step_1", "step_2"]
}
```

### RCA Request Prompt Template

```
## Task Information

Task ID: {task_id}
Task Status: {status}
Task Priority: {priority}
Created At: {created_at}
Completed At: {completed_at}
Duration: {duration_seconds}s

## Device Context

Device ID: {device_id}
Device Type: {device_type}
Runner Version: {runner_version}
Hostname: {hostname}

## Task Manifest

{task_manifest_json}

## Execution Results

{execution_results_summary}

## Step-by-Step Execution

{steps_execution_details}

## Error Logs and Artifacts

{error_logs}
{artifacts}

## Analysis Required

Please analyze this failed task execution and provide:
1. Root cause of failure
2. Key findings with evidence
3. Actionable recommendations
4. Severity assessment
5. Related patterns or similar issues

Focus on technical details and avoid generic responses.
```

---

## RCA Context Format

### Input Data Structure

```typescript
interface RCAContext {
  task: {
    task_id: string;
    status: 'failed' | 'timeout' | 'crashed';
    priority: string;
    created_at: string;
    completed_at: string;
    duration_seconds: number;
    manifest: TaskManifest;
  };
  device: {
    device_id: string;
    device_type: string;
    runner_version: string;
    hostname: string;
    os: string;
    capabilities: Record<string, unknown>;
  };
  execution: {
    summary: {
      total_steps: number;
      successful_steps: number;
      failed_steps: number;
      crashed_steps: number;
      skipped_steps: number;
    };
    steps: Array<{
      step_id: string;
      type: string;
      status: 'success' | 'failed' | 'timeout' | 'crashed';
      exit_code: number | null;
      stdout: string;
      stderr: string;
      started_at: string;
      completed_at: string;
      duration_seconds: number;
      error_message?: string;
    }>;
  };
  artifacts: {
    files: Array<{
      name: string;
      type: string;
      size: number;
      location: string;
    }>;
    logs: string[];
  };
}
```

### Output Data Structure

```typescript
interface RCAResult {
  analysis_id: string;
  task_id: string;
  analyzed_at: string;
  llm_provider: string;
  llm_model: string;
  duration_seconds: number;
  tokens_used: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  cache_hit: boolean;
  root_cause: string;
  confidence: number; // 0.0 - 1.0
  severity: 'low' | 'medium' | 'high' | 'critical';
  findings: Array<{
    category: string;
    description: string;
    evidence: string[];
  }>;
  recommendations: Array<{
    priority: number; // 1 = highest
    action: string;
    expected_outcome: string;
  }>;
  related_patterns: string[];
  next_steps: string[];
}
```

---

## Data Models

### Database Models

```python
# src/omni_server/models.py

class TaskRCADB(Base):
    """Root Cause Analysis results storage."""
    
    __tablename__ = "task_rca"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    
    # Analysis metadata
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    llm_provider = Column(String, nullable=False)
    llm_model = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    
    # Token usage for cost tracking
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    
    # RCA results (stored as JSON)
    root_cause = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(String, nullable=False)
    findings = Column(JSON, nullable=False)
    recommendations = Column(JSON, nullable=False)
    related_patterns = Column(JSON, nullable=False)
    next_steps = Column(JSON, nullable=False)
    
    # Caching
    cache_hit = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    task = relationship("TaskQueueDB", back_populates="rca_result")
```

### Add relationship to TaskQueueDB

```python
# src/omni_server/models.py

class TaskQueueDB(Base):
    # ... existing fields ...
    
    rca_result = relationship("TaskRCADB", back_populates="task", uselist=False)
```

### Configuration Models

```python
# src/omni_server/config.py

class RCASettings(BaseSettings):
    """Root Cause Analysis configuration."""
    
    # Enable/disable
    rca_enabled: bool = False
    auto_rca_on_failure: bool = False
    
    # LLM Provider
    llm_provider: str = "openai"  # openai, anthropic, ollama
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = ""  # For alternative providers
    
    # Fallback
    llm_fallback_provider: str = "anthropic"
    llm_fallback_model: str = "claude-3-5-sonnet-20241022"
    llm_fallback_api_key: str = ""
    
    # Prompts
    rca_system_prompt: str = "..."  # Default system prompt
    
    # Rate Limiting
    max_rca_per_hour: int = 100
    rca_cache_ttl_seconds: int = 86400  # 24 hours
    
    # Cost Control
    max_tokens_per_request: int = 4000
    enable_rca_cache: bool = True
    
    class Config:
        env_prefix = "OMNI_"
        env_file = ".env"
```

---

## API Design

### New Endpoints

```python
# src/omni_server/api/rca.py

@router.post("/api/v1/rca/analyze/{task_id}", response_model=RCAResponse)
async def analyze_task_failure(
    task_id: str,
    force: bool = False,  # Bypass cache
    db: Session = Depends(get_db),
) -> RCAResponse:
    """
    Trigger RCA analysis for a failed task.
    
    - If cache exists and not force: Return cached result
    - If no cache or force: Perform new analysis
    - Store result in database
    """
    pass


@router.get("/api/v1/rca/{task_id}", response_model=RCAResponse)
async def get_rca_result(
    task_id: str,
    db: Session = Depends(get_db),
) -> RCAResponse:
    """
    Get RCA result for a task.
    
    Returns 404 if not analyzed yet.
    """
    pass


@router.delete("/api/v1/rca/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rca_result(
    task_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete RCA result (forces re-analysis on next trigger).
    """
    pass


@router.get("/api/v1/rca/stats", response_model=RCAStatsResponse)
async def get_rca_stats(
    db: Session = Depends(get_db),
    current_user: Annotated[UserDB, Depends(get_current_user)],
) -> RCAStatsResponse:
    """
    Get RCA statistics (admin only).
    
    - Total analyses performed
    - Cache hit rate
    - Token usage and cost estimate
    - Analysis by severity distribution
    """
    pass


@router.post("/api/v1/rca/settings", response_model=RCASettingsResponse)
async def update_rca_settings(
    settings: RCASettingsUpdate,
    current_user: Annotated[UserDB, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> RCASettingsResponse:
    """
    Update RCA settings (admin only).
    """
    pass
```

### Response Models

```python
# src/omni_server/schemas/rca.py

class RCAResponse(BaseModel):
    """RCA analysis response."""
    
    analysis_id: str
    task_id: str
    analyzed_at: str
    llm_provider: str
    llm_model: str
    duration_seconds: float
    tokens_used: Dict[str, int]
    cache_hit: bool
    root_cause: str
    confidence: float
    severity: str
    findings: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    related_patterns: List[str]
    next_steps: List[str]


class RCAStatsResponse(BaseModel):
    """RCA statistics response."""
    
    total_analyses: int
    cache_hit_rate: float
    total_tokens_used: int
    estimated_cost_usd: float
    severity_distribution: Dict[str, int]
    recent_analyses: List[RCAResponse]


class RCASettingsUpdate(BaseModel):
    """RCA settings update request."""
    
    rca_enabled: Optional[bool] = None
    auto_rca_on_failure: Optional[bool] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    max_rca_per_hour: Optional[int] = None
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Create RCA database models
- [ ] Add RCA configuration
- [ ] Set up LLM client abstraction
- [ ] Implement basic OpenAI client

### Phase 2: Core RCA Service (Week 1-2)
- [ ] Implement RCA context extraction
- [ ] Create prompt builder
- [ ] Implement LLM integration
- [ ] Add caching layer (Redis)

### Phase 3: API Integration (Week 2)
- [ ] Create RCA API endpoints
- [ ] Integrate with task result upload
- [ ] Implement auto-trigger on failure
- [ ] Add rate limiting

### Phase 4: Frontend UI (Week 2-3)
- [ ] Create RCA result display component
- [ ] Add RCA section to task detail view
- [ ] Implement "Analyze Again" button
- [ ] Add RCA settings page

### Phase 5: Enhancement (Week 3)
- [ ] Add multiple LLM provider support
- [ ] Implement Anthropic client
- [ ] Add cost tracking
- [ ] Create RCA statistics dashboard

### Testing Strategy

1. **Unit Tests**: LLM client, prompt builder, context extraction
2. **Integration Tests**: RCA API endpoints, cache layer
3. **E2E Tests**: Failed task → Auto RCA → Result display
4. **Mock Tests**: Mock LLM responses for predictable testing

### Deployment Considerations

1. **Environment Variables**: Secure LLM API keys
2. **Rate Limiting**: Protect against API abuse
3. **Cache Strategy**: Redis for distributed caching
4. **Async Processing**: Use Celery for background RCA tasks
5. **Monitoring**: Track usage, costs, and success rates

---

## Appendix

### A. Example RCA Result

```json
{
  "analysis_id": "rca_abc123",
  "task_id": "test_task_001",
  "analyzed_at": "2026-03-22T10:30:00Z",
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "duration_seconds": 8.5,
  "tokens_used": {
    "input_tokens": 1250,
    "output_tokens": 350,
    "total_tokens": 1600
  },
  "cache_hit": false,
  "root_cause": "SSH connection timeout to device raspberry-pi-001 due to network connectivity issues. The device is not responding to ping and the SSH port is filtered.",
  "confidence": 0.92,
  "severity": "high",
  "findings": [
    {
      "category": "Network Connectivity",
      "description": "Device is unreachable from runner host",
      "evidence": [
        "SSH connection timeout after 30s",
        "Ping failed with 100% packet loss",
        "DNS resolution successful"
      ]
    },
    {
      "category": "Device Availability",
      "description": "Device heartbeat missing for >5 minutes",
      "evidence": [
        "Last heartbeat: 2026-03-22T10:20:00Z",
        "Expected heartbeat: <60s interval",
        "Device status in portal: offline"
      ]
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "Verify device power and network connection",
      "expected_outcome": "Device becomes reachable"
    },
    {
      "priority": 2,
      "action": "Check firewall rules on intermediate network devices",
      "expected_outcome": "SSH port access restored"
    },
    {
      "priority": 3,
      "action": "Review device logs for system crash or network config changes",
      "expected_outcome": "Identify root cause of connectivity loss"
    }
  ],
  "related_patterns": [
    "ssh_timeout_network_issue",
    "device_power_cycle_required",
    "network_partition_detected"
  ],
  "next_steps": [
    "1. Manually ping device from runner host",
    "2. Check device console/serial port for boot messages",
    "3. Verify network routing path to device",
    "4. If device is stuck, perform power cycle",
    "5. Create follow-up task to verify connectivity restoration"
  ]
}
```

### B. Cost Estimate

Assumptions:
- Average failed task: 1500 input tokens + 400 output tokens = 1900 tokens
- GPT-4o-mini: $0.15/M input + $0.60/M output
- 100 failed tasks per day

**Daily Cost**:
- Input: 100 × 1500 × $0.15/1M = $0.0225
- Output: 100 × 400 × $0.60/1M = $0.024
- **Total**: $0.0465/day ≈ $1.40/month

**With 10x Cache Hit Rate**:
- 10 actual analyses/day
- **Total**: $0.00465/day ≈ $0.14/month

**Recommendation**: Start with cache enabled, monitor usage, adjust as needed.
