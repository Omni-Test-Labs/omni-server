# RCA System Operations and Troubleshooting

This guide explains how to monitor, troubleshoot, and maintain the AI-powered Root Cause Analysis (RCA) system in production.

## Table of Contents

- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)
- [Common Issues](#common-issues)

---

## Monitoring

### Key Metrics to Track

#### 1. RCA Health Metrics

```sql
-- Total RCA analyses performed
SELECT COUNT(*) as total_analyses, 
       COUNT(CASE WHEN cache_hit = true THEN 1 END) as cache_hits,
       AVG(total_tokens) as avg_tokens
FROM task_rca;

-- RCA analyses per day
SELECT DATE(analyzed_at) as date,
       COUNT(*) as total,
       AVG(total_tokens) as avg_tokens,
       SUM(input_tokens) as total_input_tokens,
       SUM(output_tokens) as total_output_tokens
FROM task_rca
WHERE analyzed_at > DATE('now', '-30 days')
GROUP BY DATE(analyzed_at)
ORDER BY date DESC;
```

#### 2. Performance Metrics

```python
# Average analysis duration (ms)
db.execute("""
    SELECT AVG(duration * 1000) as avg_duration_ms
    FROM task_rca
    WHERE analyzed_at > DATE('now', '-7 days')
""")

# P95 duration
db.execute("""
    SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration) * 1000 as p95_duration_ms
    FROM task_rca
    WHERE analyzed_at > DATE('now', '-7 days')
""")
```

#### 3. Cache Effectiveness

```sql
-- Cache hit rate
SELECT 
    COUNT(CASE WHEN cache_hit = true THEN 1 END) as cache_hits,
    COUNT(*) as total_queries,
    CAST(COUNT(CASE WHEN cache_hit = true THEN 1 END) AS FLOAT) / COUNT(*) as hit_rate
FROM task_rca
WHERE analyzed_at > DATE('now', '-30 days');
```

#### 4. Error Distribution

```sql
-- Severity distribution
SELECT 
    severity,
    COUNT(*) as count
FROM task_rca
WHERE analyzed_at > DATE('now', '-30 days')
GROUP BY severity
ORDER BY count DESC;
```

---

### Logging

#### Enable RCA Debug Logging

```python
# In settings or config
import logging

logging.getLogger("omni_server.ai").setLevel(logging.DEBUG)
logging.getLogger("omni_server.queue").setLevel(logging.DEBUG)
```

#### Log Messages to Monitor

```python
# Success logs
"RCA analysis completed for task {task_id}"
"RCA auto-trigger on task failure is enabled"
"Cached RCA result returned for task {task_id}"

# Warning logs
"RCA cache expired for task {task_id}"
"RCA rate limit exceeded: {count}/{limit} per hour"
"No event loop available for task {task_id}, skipping RCA"

# Error logs
"RCA analysis failed for task {task_id}: {error}"
"Failed to parse RCA response: {error}"
"LLM response is not valid JSON: {content}"
```

---

## Troubleshooting

### Issue 1: RCA Not Triggering on Task Failure

**Symptoms**:
- Tasks fail in database but no RCA results generated
- No log entries about RCA triggering
- Task status is `failed`/`crashed`/`timeout` but no `task_rca` records

**Diagnosis Steps**:

1. Check configuration:
```bash
# Check environment variables
echo $RCA_ENABLED
echo $AUTO_RCA_ON_FAILURE
```

2. Verify server logs:
```bash
tail -f logs/omni-server.log | grep -i rca
```

**Solutions**:

- **Enable RCA**: Set `RCA_ENABLED=true` and restart server
- **Enable auto-trigger**: Set `AUTO_RCA_ON_FAILURE=true`
- **Check event loop**: Verify async event loop is handling background tasks

---

### Issue 2: API Key Errors

**Symptoms**:
- HTTP 401/403 errors when calling LLM API
- Logs show "Failed to connect toOpenAI API"
- RCA results contain "Failed to parse LLM response"

**Diagnosis**:

```bash
# Test API key manually
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY"

# Check logs
grep -i "api.*error" logs/omni-server.log
```

**Solutions**:

1. **Verify API key**:
   ```bash
   echo $LLM_API_KEY  # Should start with "sk-"
   ```

2. **Check key permissions**:
   - Ensure key has access to GPT-4o-mini model
   - Generate a new key if uncertain

3. **Verify network connectivity**:
   ```bash
   curl -I https://api.openai.com/v1/models
   ```

4. **Check key format**:
   - Remove leading/trailing whitespace
   - Don't include quotes in environment variable

---

### Issue 3: Rate Limit Exceeded

**Symptoms**:
- HTTP 429 errors
- Logs show "RCA rate limit exceeded"
- Some tasks get RCA results while others don't

**Diagnosis**:

```sql
-- Check recent RCA count in last hour
SELECT COUNT(*) as recent_analyses
FROM task_rca
WHERE analyzed_at > DATETIME('now', '-1 hour');
```

**Solutions**:

1. **Increase limit**:
   ```bash
   export MAX_RCA_PER_HOUR=200
   ```

2. **Enable caching** (should already be enabled):
   ```bash
   export ENABLE_RCA_CACHE=true
   export RCA_CACHE_TTL_SECONDS=86400
   ```

3. **Clear rate limit cache**: Restart server to reset

---

### Issue 4: High Token Usage

**Symptoms**:
- Unexpected costs from LLM provider
- Daily usage reports show high token consumption
- Cache not working properly

**Diagnosis**:

```sql
-- Find high-token analyses
SELECT 
    task_id,
    total_tokens,
    duration,
    root_cause
FROM task_rca
WHERE analyzed_at > DATE('now', '-7 days')
ORDER BY total_tokens DESC
LIMIT 10;
```

**Solutions**:

1. **Reduce token limit**:
   ```bash
   export MAX_TOKENS_PER_REQUEST=1000  # Down from 2000
   ```

2. **Optimize prompts**:
   - Remove verbose logging from context
   - Limit log entries included (already limited to 20)
   - Reduce artifact details

3. **Increase cache TTL**:
   ```bash
   export RCA_CACHE_TTL_SECONDS=604800  # 7 days instead of 1 day
   ```

4. **Review failed tasks**: Identify which tasks are consuming most tokens and optimize context for similar tasks

---

### Issue 5: Low Confidence Results

**Symptoms**:
- RCA results often have confidence < 0.5
- Findings are generic or unrelated
- Recommendations don't match actual issue

**Diagnosis**:

```sql
-- Average confidence by severity
SELECT 
    severity,
    AVG(confidence) as avg_confidence
FROM task_rca
GROUP BY severity
ORDER BY avg_confidence;
```

**Solutions**:

1. **Improve log quality**: Add more context to task execution logs
2. **Add error details**: Include stack traces, error codes, specific messages
3. **Adjust prompts**: Customize prompts for your specific error patterns (see Developer Guide)
4. **Provide device context**: Ensure device status and resources are captured

---

### Issue 6: Cache Not Working

**Symptoms**:
- Every analysis calls LLM API despite caching enabled
- `cache_hit` field is `false` in all results
- Cost higher than expected

**Diagnosis**:

```bash
# Check cache configuration
echo $ENABLE_RCA_CACHE
echo $RCA_CACHE_TTL_SECONDS

# Check cache TTL in database
SELECT 
    task_id,
    analyzed_at,
    expires_at,
    cache_hit,
    DATE_PART('epoch', expires_at) - DATE_PART('epoch', analyzed_at) as cache_duration_seconds
FROM task_rca
ORDER BY analyzed_at DESC
LIMIT 10;
```

**Solutions**:

1. **Verify cache is enabled**: `ENABLE_RCA_CACHE=true`
2. **Check cache TTL**: Should be > 0 (default: 86400s = 24h)
3. **Check logs for cache warnings**: Look for "cache expired" messages
4. **Verify database persistence**: Ensure `task_rca` table is not being wiped

---

### Issue 7: Slow Performance

**Symptoms**:
- RCA analysis takes > 30 seconds
- User complaints about slow RCA refresh
- Timeout errors in UI

**Diagnosis**:

```sql
-- Find slow analyses
SELECT 
    task_id,
    duration as duration_seconds,
    total_tokens,
    llm_model
FROM task_rca
ORDER BY duration DESC
LIMIT 20;
```

**Solutions**:
1. **Increase timeout**: Adjust LLM and database timeout settings
2. **Optimize context**: Reduce log entries sent to LLM
3. **Use faster model**: GPT-4o-mini is already fastest GPT-4 model
4. **Check network latency**: Test connection to LLM API
5. **Add pre-computation**: Pre-analyze common failure patterns

---

## Maintenance

### Database Maintenance

#### Purge Old RCA Results

```sql
-- Delete RCA results older than 90 days
DELETE FROM task_rca 
WHERE analyzed_at < DATE('now', '-90 days');

-- Optimize database
VACUUM ANALYZE;
REINDEX TABLE task_rca;
```

#### Performance Optimization

```sql
-- Create indexes for common queries
CREATE INDEX idx_task_rca_analyzed_at ON task_rca(analyzed_at DESC);
CREATE INDEX idx_task_rca_severity ON task_rca(severity);
CREATE INDEX idx_task_rca_cache_hit ON task_rca(cache_hit);

-- Update statistics
ANALYZE task_rca;
```

### Configuration Review

#### Monthly Configuration Checklist

- [ ] Review and update rate limits based on usage patterns
- [ ] Adjust cache TTL based on failure recurrence patterns
- [ ] Verify API keys are valid and have sufficient quota
- [ ] Check token usage trends and adjust limits if needed
- [ ] Review LLM model availability and pricing changes
- [ ] Update prompts if new error patterns emerge

### Monitoring Setup

#### Prometheus Metrics (Future Enhancement)

```python
# Custom metrics for RCA
from prometheus_client import Counter, Histogram, Gauge

rca_analyses_total = Counter(
    'rca_analyses_total',
    'Total number of RCA analyses performed',
    ['cache_hit', 'status']
)

rca_tokens_total = Histogram(
    'rca_tokens_total',
    'Total tokens used for RCA analysis',
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000]
)

rca_duration_seconds = Histogram(
    'rca_duration_seconds',
    'RCA analysis duration in seconds',
    buckets=[5, 10, 20, 30, 60, 120, 300]
)

rca_cache_hit_rate = Gauge(
    'rca_cache_hit_rate',
    'RCA cache hit rate percentage'
)
```

---

## Common Issues

### "RCA results are generic"

**Cause**: Limited context in task logs or generic error messages

**Solution**: Improve log quality by adding:
- Stack traces
- Error codes and messages
- Environment context (OS version, dependencies)
- Device resource snapshots

### "Confidence is always low"

**Cause**: Insufficient evidence for conclusive analysis

**Solution**:
- Add more detailed error information
- Increase context window (more history logs)
- Consider providing system-wide context (recent failures, patterns)

### "Recommendations don't make sense"

**Cause**: Prompt not aligned with your use case

**Solution**: Customize prompts (see Developer Guide) for your specific error patterns

### "Cache keeps expiring"

**Cause**: Cache TTL too short or tasks have varying failure causes

**Solution**: Increase `RCA_CACHE_TTL_SECONDS` to match your failure patterns

---

## Alerting

### Critical Alerts

- **RCA disabled**: When `rca_enabled=false` but configured as ON
- **Rate Limit**: When approaching rate limit threshold (>80%)
- **API Key Invalid**: When LLM API returns authentication errors
- **High Error Rate**: When >20% of analyses fail

### Warning Alerts

- **Low Confidence**: When average confidence drops below 0.5
- **Cache Miss**: When cache hit rate drops below 80%
- **Slow Performance**: When average duration > 30 seconds
- **High Token Usage**: When tokens per analysis exceeds 500

---

## Backup and Recovery

### Backing Up RCA Results

```bash
# Dump RCA results
pg_dump -U postgres -d omnidb -f rca_results_$(date +%Y%m%d).sql task_rca

# Archive old results
SELECT COUNT(*) as old_results
FROM task_rca
WHERE analyzed_at < DATE('now', '-90 days');
```

### Restoring from Backup

```bash
# Restore RCA results
psql -U postgres -d omnidb -f rca_results_20240322.sql task_rca
```

---

## Next Steps

- [Costs and Performance Guide](./COSTS_AND_PERFORMANCE.md) - Optimize costs and improve performance
- [Developer Guide](./DEVELOPER_GUIDE.md) - Extend and customize RCA functionality
- [Setup Guide](./SETUP.md) - Initial configuration and troubleshooting
