# RCA System Costs and Performance

This guide explains how to estimate, monitor, and optimize costs for the AI-powered Root Cause Analysis (RCA) system.

## Table of Contents

- [Cost Estimation](#cost-estimation)
- [Pricing Models](#pricing-models)
- [Cost Calculator](#cost-calculator)
- [Performance Optimization](#performance-optimization)
- [Cost Optimization](#cost-optimization)
- [Monitoring Costs](#monitoring-costs)

---

## Cost Estimation

### OpenAI GPT-4o-mini (Recommended)

**Pricing (as of March 2024)**:
- Input tokens: $0.15 per 1M tokens
- Output tokens: $0.60 per 1M tokens

**Estimated tokens per RCA analysis**:
- Input: 250-300 tokens (task info + logs + context)
- Output: 150-200 tokens (root cause + findings + recommendations)
- Total: 400-500 tokens per analysis

### Example Scenarios

#### Scenario 1: Low Volume (10 failed tasks/day)

```
Daily:
- New analyses: 10 tasks × 400 tokens = 4,000 tokens
- Cached requests: 0 tokens (after 24h)
- Daily tokens: 4,000 tokens
- Daily cost: 4,000 × ($0.15 + $0.60) / 1M ≈ $0.003

Monthly (30 days):
- Total cost: $0.003 × 30 = $0.09/month
```

#### Scenario 2: Medium Volume (100 failed tasks/day)

```
Daily:
- New analyses: 100 tasks × 400 tokens = 40,000 tokens
- Cached requests: 0 tokens (after 24h)
- Daily tokens: 40,000 tokens
- Daily cost: 40,000 × ($0.15 + $0.60) / 1M ≈ $0.03

Monthly (30 days):
- Total cost: $0.03 × 30 = $0.90/month
```

#### Scenario 3: High Volume (1,000 failed tasks/day)

```
Daily:
- New analyses: 1,000 tasks × 400 tokens = 400,000 tokens
- Cached requests: 0 tokens (after 24h)
- Daily tokens: 400,000 tokens
- Daily cost: 400,000 × ($0.15 + $0.60) / 1M ≈ $0.30

Monthly (30 days):
- Total cost: $0.30 × 30 = $9.00/month
```

### With Aggressive Caching (7-day TTL)

**Scenario 2 (with 7-day cache)**:

```
Week 1:
- New analyses: 100 × 7 = 700 tasks × 400 tokens = 280,000 tokens
- Week 1 cost: 280,000 × $0.75 / 1M ≈ $0.21

Week 2:
- New analyses: 0 (all cached from week 1)
- Week 2 cost: $0.00

Monthly savings: $0.90 → $0.21 (77% savings)
```

---

## Pricing Models

### OpenAI GPT Models Comparison

| Model | Input ($/1M) | Output ($/1M) | Est. Cost/Analysis | Speed | Intelligence |
|-------|--------------|---------------|-------------------|-------|--------------|
| GPT-4o-mini | $0.15 | $0.60 | ~$0.0003 | Fast | Good for RCA |
| GPT-4o | $2.50 | $10.00 | ~$0.003 | Fast | Best quality |
| GPT-4-turbo | $0.30 | $1.20 | ~$0.0006 | Fast | Better analysis |
| GPT-3.5-turbo | $0.01 | $0.02 | ~$0.00002 | Very Fast | Basic analysis |

**Recommendation**: GPT-4o-mini is the sweet spot for RCA - fast, affordable, and sufficient intelligence.

### Anthropic Claude Models (Future Support)

| Model | Input ($/1M) | Output ($/1M) | Est. Cost/Analysis |
|-------|--------------|---------------|-------------------|
| Claude 3.5 Sonnet | $3.00 | $15.00 | ~$0.0045 |
| Claude 3 Opus | $15.00 | $75.00 | ~$0.0225 |
| Claude 3 Haiku | $0.25 | $1.25 | ~$0.0004 |

---

## Cost Calculator

### Interactive Python Calculator

```python
from datetime import datetime, timedelta

def calculate_rca_cost(
    daily_failed_tasks: int,
    cache_ttl_hours: int = 24,
    input_token_cost: float = 0.00015,  # $/token
    output_token_cost: float = 0.00060,  # $/token
    tokens_per_analysis: int = 400,
) -> dict:
    """
    Calculate monthly RCA costs.

    Args:
        daily_failed_tasks: Number of failed tasks per day
        cache_ttl_hours: Cache time-to-live in hours
        input_token_cost: Cost per input token
        output_token_cost: Cost per output token
        tokens_per_analysis: Average tokens per analysis

    Returns:
        Dict with cost breakdown
    """
    tokens_per_analysis = tokens_per_analysis * 0.01  # $ per 100 tokens = input + output

    # Full month (no cache)
    cost_no_cache = daily_failed_tasks * tokens_per_analysis * 30

    # With cache
    days_in_month = 30
    days_without_cache = min(days_in_month, cache_ttl_hours / 24)
    cost_with_cache = daily_failed_tasks * days_without_cache * tokens_per_analysis

    savings = cost_no_cache - cost_with_cache
    savings_percent = (savings / cost_no_cache) * 100 if cost_no_cache > 0 else 0

    return {
        "daily_failed_tasks": daily_failed_tasks,
        "cache_ttl_hours": cache_ttl_hours,
        "cost_per_analysis": tokens_per_analysis,
        "monthly_cost_without_cache": round(cost_no_cache, 2),
        "monthly_cost_with_cache": round(cost_with_cache, 2),
        "monthly_savings": round(savings, 2),
        "savings_percent": round(savings_percent, 2),
    }

# Example usage
print(calculate_rca_cost(daily_failed_tasks=100, cache_ttl_hours=24))
```

### Cost Comparison Table

| Tasks/Day | Cache TTL | No Cache | With Cache | Savings |
|-----------|-----------|----------|------------|---------|
| 10 | 24h | $0.09 | $0.09 | $0 (0%) |
| 10 | 168h (7d) | $0.09 | $0.01 | $0.08 (90%) |
| 100 | 24h | $0.90 | $0.90 | $0 (0%) |
| 100 | 168h (7d) | $0.90 | $0.12 | $0.78 (87%) |
| 1000 | 24h | $9.00 | $9.00 | $0 (0%) |
| 1000 | 168h (7d) | $9.00 | $1.20 | $7.80 (87%) |

---

## Performance Optimization

### 1. Enable and Configure Caching

```bash
# Enable caching
ENABLE_RCA_CACHE=true

# Set cache TTL (24h default, can be 7d for high savings)
RCA_CACHE_TTL_SECONDS=604800  # 7 days
```

**Impact**: Reduces costs by up to 90% with 7-day cache TTL

### 2. Optimize Token Usage

```bash
# Reduce max tokens
MAX_TOKENS_PER_REQUEST=1000  # Down from 2000

# This reduces input/output tokens proportionally
```

**Impact**: 50% reduction in token usage per analysis

### 3. Use Appropriate Rate Limits

```bash
# Adjust based on actual needs
MAX_RCA_PER_HOUR=100  # Default
```

**Impact**: Prevents accidental high costs from error cascades

### 4. Pre-analyze Common Failures

For recurring failures, create manual RCA templates:

```python
# Map common error patterns to pre-defined RCA results
COMMON_PATTERNS = {
    "ConnectionRefused": {
        "root_cause": "Connection refused to service",
        "confidence": 0.95,
        "severity": "high",
        "findings": ["Service not responding"],
        "recommendations": ["Check service status", "Verify network"],
        "cache": True,
    }
}

def get_precomputed_rca(error_message: str) -> dict | None:
    """Check for precomputed RCA for common errors."""
    for pattern, rca in COMMON_PATTERNS.items():
        if pattern in error_message:
            return rca
    return None
```

**Impact**: Eliminates LLM calls for known error patterns

---

## Cost Optimization

### Strategy 1: Aggressive Caching

**When to Use**: High volume of similar failures

**Configuration**:
```bash
RCA_CACHE_TTL_SECONDS=604800  # 7 days
```

**Trade-offs**:
- Pros: 87% cost reduction
- Cons: Stale results for repeated errors, takes 7 days to see new patterns

---

### Strategy 2: Selective Analysis

**When to Use**: Mix of trivial and critical failures

**Implementation**:
```python
def should_trigger_rca(task: TaskQueueDB) -> bool:
    """Only trigger RCA for significant failures."""
    # Skip for known trivial errors
    trivial_errors = ["timeout", "retry", "transient"]

    if task.priority != "critical":
        if any(err in task.error_message.lower() for err in trivial_errors):
            return False

    return True
```

**Trade-offs**:
- Pros: Reduces analysis volume by 50-70%
- Cons: May miss important insights from trivial failures

---

### Strategy 3: Batch Analysis

**When to Use**: Periodic analysis instead of per-task

**Implementation**:
```python
# Collect failed tasks over time period
tasks_to_analyze = get_failed_tasks_since(hours=6)

# Analyze in batch
for task in tasks_to_analyze:
    if not has_cached_result(task.task_id):
        analyze_task_async(task.task_id)
```

**Trade-offs**:
- Pros: Better for rate limiting, can use cheaper models
- Cons: Delayed analysis for recent failures

---

### Strategy 4: Model Tiering

**When to Use**: Vary analysis complexity by priority

**Configuration**:
```python
MODEL_TIER = {
    "critical": "gpt-4o",      # Higher quality, higher cost
    "high": "gpt-4o-mini",    # Good quality, lower cost
    "medium": "gpt-3.5-turbo", # Basic, very low cost
    "low": "gpt-3.5-turbo",   # Basic, very low cost
}

def get_model_for_task(task: TaskQueueDB) -> str:
    """Select model based on task priority."""
    return MODEL_TIER.get(task.priority, "gpt-4o-mini")
```

**Trade-offs**:
- Pros: Optimizes cost by using cheaper models for low-priority tasks
- Cons: Variable quality across tasks

---

## Monitoring Costs

### Daily Cost Tracking

```sql
-- Today's token usage and cost
SELECT 
    DATE(analyzed_at) as date,
    COUNT(*) as total_analyses,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_tokens) as total_tokens
FROM task_rca
WHERE analyzed_at > DATE('now', '-1 day')
GROUP BY DATE(analyzed_at);
```

### Cost per Task Type

```sql
-- Cost by task type
SELECT 
    tm.task_type,
    COUNT(*) as count,
    AVG(tr.total_tokens) as avg_tokens,
    SUM(tr.total_tokens) as total_tokens
FROM task_rca tr
JOIN task_queue tq ON tr.task_id = tq.task_id
JOIN task_manifests tm ON tq.task_id = tm.task_id
WHERE tr.analyzed_at > DATE('now', '-7 days')
GROUP BY tm.task_type
ORDER BY count DESC;
```

### Cache Effectiveness

```sql
-- Cache hit rate over time
SELECT 
    DATE(analyzed_at) as date,
    COUNT(*) as total,
    COUNT(CASE WHEN cache_hit = true THEN 1 END) as cache_hits,
    CAST(COUNT(CASE WHEN cache_hit = true THEN 1 END) AS FLOAT) / COUNT(*) as hit_rate
FROM task_rca
WHERE analyzed_at > DATE('now', '-30 days')
GROUP BY DATE(analyzed_at)
ORDER BY date DESC;
```

---

## Real-World Cost Analysis

### Production Example: 30-Day Analysis

**Environment**:
- Daily failed tasks: Variable (50-200)
- Active cache: 24h TTL
- Model: GPT-4o-mini

**Results**:
```
Week 1:
- Total analyses: 1,100
- New analyses: 380
- Cached: 720 (65%)
- Total tokens: 452,000
- Cost: $0.34

Week 2:
- Total analyses: 2,000
- New analyses: 450
- Cached: 1,550 (78%)
- Total tokens: 516,000
- Cost: $0.39

Week 3:
- Total analyses: 1,800
- New analyses: 420
- Cached: 1,380 (77%)
- Total tokens: 477,000
- Cost: $0.36

Week 4:
- Total analyses: 2,100
- New analyses: 460
- Cached: 1,640 (78%)
- Total tokens: 539,000
- Cost: $0.40

Total Month:
- Analyses: 7,000
- New: 1,710 (24%)
- Cached: 5,290 (76%)
- Total tokens: 1,984,000
- Total cost: $1.49

With no cache: $5.25
Savings: $3.76 (72%)
```

---

## Cost Control Checklist

### Monthly Review

- [ ] Check total token usage in LLM provider dashboard
- [ ] Review cost per failed task (should be < $0.001)
- [ ] Verify cache hit rate (should be > 70%)
- [ ] Identify top token consumers (specific task types)
- [ ] Check for anomalies (sudden spike in cost)

### Quarterly Review

- [ ] Evaluate if caching TTL needs adjustment
- [ ] Consider changing LLM provider/model if better options available
- [ ] Review rate limit settings based on actual usage
- [ ] Update cost estimates based on new pricing
- [ ] Evaluate if RCA should be enabled for all failures

---

## Budget Planning

### Cost Scaling Formula

```
Monthly Cost = (Daily_Failed_Tasks × Tokens_Per_Analysis × 30 × Cost_Per_Token) × Cache_Discount

Where:
- Cache_Discount = 1 - (Cache_Hit_Rate × (1 - 1/Cache_Cycles_Per_Month))
```

### Example: Scaling Calculator

```python
def calculate_monthly_budget(
    daily_tasks: int,
    cache_ttl_days: int = 1,
    tokens_per_analysis: int = 400,
    cost_per_token: float = 0.00000075,  # Average of input/output
) -> dict:
    """Calculate monthly budget for RCA."""
    
    # Cache discount calculation
    cache_cycles = max(1, 30 / cache_ttl_days)
    
    # With cache hit rate estimate (~75%)
    cache_hit_rate = min(0.9, 0.5 + (cache_ttl_days / 30) * 0.4)
    cache_discount = cache_hit_rate * (1 - 1/cache_cycles)
    
    daily_cost = daily_tasks * tokens_per_analysis * cost_per_token
    monthly_cost = daily_cost * 30 * (1 - cache_discount)
    
    return {
        "daily_tasks": daily_tasks,
        "cache_ttl_days": cache_ttl_days,
        "estimated_cache_hit_rate": cache_hit_rate * 100,
        "estimated_cache_discount": cache_discount * 100,
        "monthly_budget": round(monthly_cost, 2),
    }

# Examples
print("100 tasks/day, 1d cache:", calculate_monthly_budget(100))
print("100 tasks/day, 7d cache:", calculate_monthly_budget(100, 7))
print("1000 tasks/day, 7d cache:", calculate_monthly_budget(1000, 7))
```

---

## Cost Optimization Best Practices

1. **Always enable caching** - 24h minimum, extend for high volume
2. **Monitor cache hit rate** - Should be >70%, troubleshoot if <50%
3. **Use appropriate rate limits** - Prevents cascading failures from spiking costs
4. **Select right model** - GPT-4o-mini is optimal for most RCA use cases
5. **Limit token usage** - Default 2000 tokens, reduce if responses are getting generic
6. **Review weekly** - Check for cost anomalies and adjust configuration

---

## Next Steps

- [Setup Guide](./SETUP.md) - Initial configuration and troubleshooting
- [API Documentation](./API.md) - Complete API reference
- [User Guide](./USER_GUIDE.md) - Frontend usage examples
- [Developer Guide](./DEVELOPER_GUIDE.md) - Integration and customization
- [Operations Guide](./OPERATIONS.md) - Monitoring and maintenance
