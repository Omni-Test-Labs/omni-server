# RCA System REST API Reference

Complete API reference for the AI-powered Root Cause Analysis (RCA) system.

## Table of Contents

- [Base URL](#base-url)
- [Endpoints](#endpoints)
  - [Get RCA Results](#get-rca-results)
  - [Trigger RCA Analysis](#trigger-rca-analysis)
  - [Get RCA Status](#get-rca-status)
- [Response Formats](#response-formats)
- [Error Codes](#error-codes)
- [Client Examples](#client-examples)

---

## Base URL

```
http://localhost:8000/api/v1
```

For production, replace `localhost:8000` with your server address.

---

## Endpoints

### Get RCA Results

Retrieve cached RCA analysis results for a task.

**Endpoint**:
```
GET /api/v1/tasks/{task_id}/rca
```

**Path Parameters**:
- `task_id` (string, required) - The ID of the task

**Query Parameters**: None

**Caching**: Returns cached results if available (24h TTL by default). Does not trigger new LLM analysis.

**Response** (200 OK):
```json
{
  "task_id": "task-001",
  "rca": {
    "root_cause": "Task failed due to network timeout",
    "confidence": 0.85,
    "severity": "high",
    "findings": [
      "Task attempted to connect to external API",
      "Network timeout after 30 seconds",
      "Retry policy not configured"
    ],
    "recommendations": [
      "Increase timeout threshold to 60 seconds",
      "Implement retry logic with exponential backoff",
      "Add network connection checks before API calls"
    ],
    "cache_hit": true,
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "duration_ms": 1245.67,
    "input_tokens": 250,
    "output_tokens": 150,
    "total_tokens": 400
  }
}
```

**Error Responses**:
- `404 Not Found`: Task does not exist
- `503 Service Unavailable`: RCA is disabled

**Example**:
```bash
curl -X GET http://localhost:8000/api/v1/tasks/task-001/rca
```

---

### Trigger RCA Analysis

Manually trigger RCA analysis for a task. Bypasses cache and forces new LLM analysis.

**Endpoint**:
```
POST /api/v1/tasks/{task_id}/rca
```

**Path Parameters**:
- `task_id` (string, required) - The ID of the task

**Request Body**:
```json
{
  "force_refresh": true  // Optional, default: false
}
```

**Parameters**:
- `force_refresh` (boolean, optional) - If `true`, bypasses cache and forces new analysis

**Rate Limiting**: Applies to analysis requests (default: 100 analyses/hour)

**Response** (200 OK):
```json
{
  "task_id": "task-001",
  "rca": {
    "root_cause": "Task failed due to insufficient permissions",
    "confidence": 0.92,
    "severity": "critical",
    "findings": [
      "Task attempted to write to /etc/config",
      "Permission denied for user 'test-runner'",
      "No sudo escalation configured"
    ],
    "recommendations": [
      "Run task with appropriate user permissions",
      "Use sudoers configuration to allow specific commands",
      "Consider moving config writes to /tmp directory"
    ],
    "cache_hit": false,
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "duration_ms": 1834.22,
    "input_tokens": 320,
    "output_tokens": 180,
    "total_tokens": 500
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid request body
- `404 Not Found`: Task does not exist
- `503 Service Unavailable`: RCA is disabled
- `429 Too Many Requests`: Rate limit exceeded

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/tasks/task-001/rca \
  -H "Content-Type: application/json" \
  -d '{"force_refresh": true}'
```

---

### Get RCA Status

Check if RCA analysis is available for a task without retrieving the full results.

**Endpoint**:
```
GET /api/v1/tasks/{task_id}/rca/status
```

**Path Parameters**:
- `task_id` (string, required) - The ID of the task

**Query Parameters**: None

**Response** (200 OK):
```json
{
  "rca_enabled": true,
  "rca_available": true,
  "analyzed_at": "2024-03-22T14:30:00Z"
}
```

When `rca_available` is `false`:
```json
{
  "rca_enabled": true,
  "rca_available": false
}
```

**When RCA is disabled**:
```json
{
  "rca_enabled": false,
  "rca_available": false
}
```

**Error Responses**:
- `404 Not Found`: Task does not exist

**Example**:
```bash
curl -X GET http://localhost:8000/api/v1/tasks/task-001/rca/status
```

---

## Response Formats

### RCA Result Object

| Field | Type | Description |
|-------|------|-------------|
| `root_cause` | string | Brief statement of the primary issue |
| `confidence` | float | Confidence level (0.0-1.0) |
| `severity` | string | One of: `critical`, `high`, `medium`, `low` |
| `findings` | array[string] | Key observations from the analysis |
| `recommendations` | array[string] | Actionable steps to fix or prevent |
| `cache_hit` | boolean | Whether result came from cache |
| `llm_provider` | string | LLM provider used (`openai`, `anthropic`) |
| `llm_model` | string | Model used for analysis |
| `duration_ms` | float | Analysis duration in milliseconds |
| `input_tokens` | integer | Tokens sent to LLM |
| `output_tokens` | integer | Tokens received from LLM |
| `total_tokens` | integer | Total tokens used |

### Severity Levels

- **`critical`**: Production-blocking issue, immediate action required
- **`high`**: Significant issue, should be addressed soon
- **`medium`**: Moderate issue, can be scheduled for later
- **`low`**: Minor issue, informational only

---

## Error Codes

| HTTP Code | Error | Description |
|-----------|-------|-------------|
| `400` | Bad Request | Invalid request parameters or body |
| `404` | Not Found | Task does not exist |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Server error during analysis |
| `503` | Service Unavailable | RCA is disabled |

### Error Response Format

```json
{
  "detail": "Error message description"
}
```

---

## Client Examples

### Python (using requests)

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Get RCA results
def get_rca_results(task_id: str) -> dict:
    response = requests.get(f"{BASE_URL}/tasks/{task_id}/rca")
    response.raise_for_status()
    return response.json()

# Trigger RCA analysis
def trigger_rca_analysis(task_id: str, force_refresh: bool = False) -> dict:
    response = requests.post(
        f"{BASE_URL}/tasks/{task_id}/rca",
        json={"force_refresh": force_refresh}
    )
    response.raise_for_status()
    return response.json()

# Check RCA status
def get_rca_status(task_id: str) -> dict:
    response = requests.get(f"{BASE_URL}/tasks/{task_id}/rca/status")
    response.raise_for_status()
    return response.json()

# Example usage
if __name__ == "__main__":
    try:
        status = get_rca_status("task-001")
        print(f"RCA Available: {status['rca_available']}")
        
        if status['rca_available']:
            rca = get_rca_results("task-001")
            print(f"Root Cause: {rca['rca']['root_cause']}")
            print(f"Confidence: {rca['rca']['confidence']}")
    except requests.HTTPError as e:
        print(f"Error: {e}")
```

### JavaScript (using fetch)

```javascript
const BASE_URL = "http://localhost:8000/api/v1";

async function getRcaResults(taskId) {
  const response = await fetch(`${BASE_URL}/tasks/${taskId}/rca`);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

async function triggerRcaAnalysis(taskId, forceRefresh = false) {
  const response = await fetch(`${BASE_URL}/tasks/${taskId}/rca`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

async function getRcaStatus(taskId) {
  const response = await fetch(`${BASE_URL}/tasks/${taskId}/rca/status`);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

// Example usage
async function main() {
  try {
    const status = await getRcaStatus('task-001');
    console.log(`RCA Available: ${status.rca_available}`);
    
    if (status.rca_available) {
      const rca = await getRcaResults('task-001');
      console.log(`Root Cause: ${rca.rca.root_cause}`);
      console.log(`Confidence: ${rca.rca.confidence}`);
    }
  } catch (error) {
    console.error(`Error: ${error.message}`);
  }
}

main();
```

### TypeScript (React API service)

```typescript
interface RCAResult {
  task_id: string;
  rca: {
    root_cause: string;
    confidence: number;
    severity: string;
    findings: string[];
    recommendations: string[];
    cache_hit: boolean;
    llm_provider: string;
    llm_model: string;
    duration_ms: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
}

interface RCAStatus {
  rca_enabled: boolean;
  rca_available: boolean;
  analyzed_at?: string;
}

const BASE_URL = "/api/v1";

export const rcaApi = {
  async getRcaResults(taskId: string): Promise<RCAResult> {
    const response = await fetch(`${BASE_URL}/tasks/${taskId}/rca`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  },

  async triggerRcaAnalysis(
    taskId: string,
    forceRefresh = false
  ): Promise<RCAResult> {
    const response = await fetch(`${BASE_URL}/tasks/${taskId}/rca`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ force_refresh: forceRefresh }),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  },

  async getRcaStatus(taskId: string): Promise<RCAStatus> {
    const response = await fetch(`${BASE_URL}/tasks/${taskId}/rca/status`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  },
};
```

### cURL Examples

```bash
# Get RCA results (cached)
curl -X GET http://localhost:8000/api/v1/tasks/task-001/rca

# Trigger new analysis
curl -X POST http://localhost:8000/api/v1/tasks/task-001/rca \
  -H "Content-Type: application/json" \
  -d '{"force_refresh": true}'

# Check RCA status
curl -X GET http://localhost:8000/api/v1/tasks/task-001/rca/status

# With authentication (if required)
curl -X GET http://localhost:8000/api/v1/tasks/task-001/rca \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Rate Limiting

All RCA analysis requests are subject to rate limiting:

- **Default limit**: 100 analyses per hour
- **Configurable**: Set via `MAX_RCA_PER_HOUR` environment variable
- **Response**: HTTP 429 with `detail` message when exceeded

### Rate Limit Error Response

```json
{
  "detail": "RCA rate limit exceeded: 101/100 per hour"
}
```

---

## Caching Behavior

### Read (GET /rca)

- Returns cached results if available
- Does not trigger new LLM analysis
- Cache TTL: 24 hours (default, configurable via `RCA_CACHE_TTL_SECONDS`)

### Write (POST /rca)

- Bypasses cache when `force_refresh=true`
- Stores new results in cache
- Updates `cache_hit=false` in response

### Status Check (GET /rca/status)

- Does not consume rate limit quota
- Returns cache availability information
- Lightweight operation

---

## Next Steps

- [User Guide](./USER_GUIDE.md) - Learn how to use the RCA results in the UI
- [Developer Guide](./DEVELOPER_GUIDE.md) - Integrate RCA into your own applications
- [Operations Guide](./OPERATIONS.md) - Monitor and troubleshoot RCA in production
- [Costs Guide](./COSTS_AND_PERFORMANCE.md) - Optimize costs and performance
