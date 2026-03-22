# RCA System Setup and Configuration Guide

This guide explains how to configure and set up the AI-powered Root Cause Analysis (RCA) system in Omni-Server.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration Options](#configuration-options)
- [LLM Provider Setup](#llm-provider-setup)
- [Database Setup](#database-setup)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- Python 3.10+
- PostgreSQL 14+ (for production)
- SQLite (for development/testing)
- OpenAI API account (for GPT-4o-mini)

### Python Dependencies

The RCA system requires the following packages (already in `pyproject.toml`):

```toml
[dependencies]
fastapi = "^0.104.0"
httpx = "^0.25.0"
sqlalchemy = "^2.0.0"
loguru = "^0.7.0"
```

---

## Quick Start

### 1. Enable RCA System

Add the following environment variables to your `.env` file or system environment:

```bash
# Primary RCA Settings
RCA_ENABLED=true
AUTO_RCA_ON_FAILURE=true

# LLM Provider Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-openai-api-key-here

# Optional: Alternative provider (future)
# LLM_BASE_URL=https://api.openai.com/v1

# Cache and Rate Limiting
RCA_CACHE_TTL_SECONDS=86400
MAX_RCA_PER_HOUR=100
ENABLE_RCA_CACHE=true

# Cost Control
MAX_TOKENS_PER_REQUEST=2000
```

### 2. Start the Server

```bash
# Development
cd omni-server
python -m uvicorn omni_server.main:app --reload

# Production
uvicorn omni_server.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Verify RCA is Running

```bash
# Check RCA status endpoint
curl http://localhost:8000/api/v1/tasks/test-task-001/rca/status
```

Expected response:
```json
{
  "rca_enabled": true,
  "rca_available": false
}
```

---

## Configuration Options

### Primary Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `rca_enabled` | bool | `false` | Master toggle for RCA system |
| `auto_rca_on_failure` | bool | `false` | Automatically trigger RCA on task failure |

### LLM Provider Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `llm_provider` | str | `"openai"` | LLM provider (`openai`, `anthropic`, `ollama`) |
| `llm_model` | str | `"gpt-4o-mini"` | Model to use for analysis |
| `llm_api_key` | str | `""` | API key for the LLM provider |
| `llm_base_url` | str | `""` | Alternative provider URL (optional) |

### Caching Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enable_rca_cache` | bool | `true` | Enable result caching |
| `rca_cache_ttl_seconds` | int | `86400` | Cache time-to-live in seconds (24h default) |

### Rate Limiting

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_rca_per_hour` | int | `100` | Maximum RCA analyses per hour |

### Cost Control

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_tokens_per_request` | int | `2000` | Maximum tokens per RCA request |

### Fallback Configuration (Future)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `llm_fallback_provider` | str | `"anthropic"` | Fallback LLM provider |
| `llm_fallback_model` | str | `"claude-3-5-sonnet-20241022"` | Fallback model |
| `llm_fallback_api_key` | str | `""` | Fallback provider API key |

---

## LLM Provider Setup

### OpenAI (Recommended)

#### 1. Get API Key

1. Go to https://platform.openai.com
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key

#### 2. Configure

```bash
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"
export LLM_API_KEY="sk-your-key-here"
```

#### 3. Verify

```bash
curl https://platform.openai.com/docs/api-reference/authentication
```

### Anthropic (Future Fallback)

```bash
export LLM_PROVIDER="anthropic"
export LLM_MODEL="claude-3-5-sonnet-20241022"
export LLM_API_KEY="your-anthropic-api-key"
```

---

## Database Setup

### TaskRCADB Table

The RCA system requires a `task_rca` table in your database. This table is automatically created when you start the server with the updated schema.

**Schema**:
```sql
CREATE TABLE task_rca (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(255) NOT NULL UNIQUE,
    root_cause TEXT,
    confidence FLOAT,
    severity VARCHAR(50),
    findings TEXT,
    recommendations TEXT,
    analyzed_at DATETIME,
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    duration FLOAT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    cache_hit BOOLEAN,
    expires_at DATETIME
);

CREATE TABLE task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ... existing columns ...
    rca_result_id INTEGER REFERENCES task_rca(id)
);
```

### Migration

If upgrading from an existing installation:

```python
# Run migration to add task_rca table
from omni_server.database import init_db
init_db()
```

---

## Verification

### 1. Check Configuration

```python
from omni_server.config import Settings

settings = Settings()
print(f"RCA Enabled: {settings.rca_enabled}")
print(f"Auto-trigger: {settings.auto_rca_on_failure}")
print(f"LLM Provider: {settings.llm_provider}")
print(f"Model: {settings.llm_model}")
print(f"Cache TTL: {settings.rca_cache_ttl_seconds}s")
```

### 2. Test API Endpoint

```bash
# Create a test task
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-rca-001",
    "device_binding": {"device_id": "device-001", "device_type": "pc"},
    "priority": "normal"
  }'

# Mark task as failed
curl -X POST http://localhost:8000/api/v1/tasks/test-rca-001/result \
  -H "Content-Type: application/json" \
  -d '{"status": "failed", "error": "Test failure"}'

# Check RCA status
curl http://localhost:8000/api/v1/tasks/test-rca-001/rca/status
```

### 3. Check Frontend

1. Navigate to Tasks page
2. Click "View Details" on a failed task
3. Verify "AI Root Cause Analysis" section appears
4. Check for RCA results display

---

## Troubleshooting

### RCA Not Triggering on Task Failure

**Problem**: Tasks are failing but RCA results are not generated.

**Solution**:
1. Verify configuration:
   ```bash
   echo $RCA_ENABLED
   echo $AUTO_RCA_ON_FAILURE
   ```

2. Check logs for errors:
   ```bash
   tail -f logs/omni-server.log | grep -i rca
   ```

3. Verify event loop is running (for auto-trigger):
   - Check server logs for "RCA auto-trigger on task failure is enabled"

### API Key Errors

**Problem**: `ConnectionError: Failed to connect to OpenAI API`

**Solution**:
1. Verify API key is set:
   ```bash
   echo $LLM_API_KEY
   ```

2. Test API key manually:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $LLM_API_KEY"
   ```

3. Check key permissions: Ensure key has access to GPT-4o-mini model

### Rate Limit Exceeded

**Problem**: `ValueError: RCA rate limit exceeded`

**Solution**:
1. Reduce `max_rca_per_hour` in settings
2. Enable caching (should already be enabled):
   ```bash
   export ENABLE_RCA_CACHE=true
   export RCA_CACHE_TTL_SECONDS=86400
   ```
3. Clear rate limit cache (restart server)

### Cache Not Working

**Problem**: Requests always call LLM even with cached results

**Solution**:
1. Verify cache is enabled:
   ```bash
   echo $ENABLE_RCA_CACHE
   ```

2. Check cache TTL is reasonable (default: 86400s = 24h)

3. Manually check database:
   ```sql
   SELECT * FROM task_rca WHERE task_id = 'your-task-id';
   ```

### High Token Usage

**Problem**: RCA costs are higher than expected

**Solution**:
1. Reduce `max_tokens_per_request`:
   ```bash
   export MAX_TOKENS_PER_REQUEST=1000  # Start with 1000
   ```

2. Increase cache TTL:
   ```bash
   export RCA_CACHE_TTL_SECONDS=604800  # 7 days
   ```

3. Review and optimize prompts if needed

---

## Cost Estimation

### Current Configuration (OpenAI GPT-4o-mini)

- Input: $0.15 per 1M tokens
- Output: $0.60 per 1M tokens
- Estimated tokens per analysis: 250 input + 150 output = 400 tokens

**Daily Cost** (100 failed tasks/day, 24h cache):
```
First analysis (100 tasks): 100 × 400 tokens × ($0.15 + $0.60)/1M ≈ $0.03
Cached requests: No cost (cache hit)
Daily total: ~$0.03
Monthly: ~$0.90
```

### With Aggressive Caching (7 days):

**Daily Cost**: ~$0.03 (first day only)
**Monthly**: ~$0.90 (first 7 days), then negligible

---

## Best Practices

### Performance

1. **Enable caching**: Always keep caching enabled in production
2. **Use appropriate TTL**: 24-144 hours depending on failure patterns
3. **Rate limiting**: Prevent accidental high costs with rate limits
4. **Log RCA triggers**: Monitor auto-trigger events

### Security

1. **Never commit API keys**: Use environment variables or secret management
2. **Rotate API keys**: Regularly rotate LLM provider API keys
3. **Monitor usage**: Track token usage to detect anomalies
4. **Fallback provider**: Set up fallback provider for production

### Reliability

1. **Test configuration**: Verify settings in staging before production
2. **Graceful degradation**: RCA should not block task processing
3. **Error logging**: Monitor RCA errors for prompt optimization
4. **Regular cache cleanup**: Implement cache cleanup for old entries

---

## Next Steps

After completing setup:

1. **Read API Documentation**: [API.md](./API.md)
2. **User Guide**: [USER_GUIDE.md](./USER_GUIDE.md)
3. **Developer Guide**: [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)
4. **Operations Guide**: [OPERATIONS.md](./OPERATIONS.md)
5. **Cost Guide**: [COSTS_AND_PERFORMANCE.md](./COSTS_AND_PERFORMANCE.md)
