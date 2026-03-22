# RCA System User Guide

This guide explains how to use the AI-powered Root Cause Analysis (RCA) feature in Omni-Web to understand task failures.

## Table of Contents

- [Overview](#overview)
- [Viewing RCA Results](#viewing-rca-results)
- [Understanding RCA Results](#understanding-rca-results)
- [Triggering Manual Analysis](#triggering-manual-analysis)
- [Interpreting Findings and Recommendations](#interpreting-findings-and-recommendations)
- [Common Use Cases](#common-use-cases)

---

## Overview

### What is RCA?

RCA (Root Cause Analysis) uses AI to analyze failed tasks and provide:
- **Root Cause**: The primary reason for the failure
- **Confidence**: How certain the AI is (0.0-1.0)
- **Severity**: Impact level (critical, high, medium, low)
- **Findings**: Key observations from the analysis
- **Recommendations**: Actionable steps to fix or prevent the issue

### Automatic vs Manual

**Automatic**: When `auto_rca_on_failure` is enabled, RCA triggers automatically on task failures (failed, crashed, timeout).

**Manual**: You can manually trigger analysis anytime using the "Refresh" button.

---

## Viewing RCA Results

### Step 1: Navigate to Tasks Page

1. Log in to Omni-Web
2. Click "Tasks" in the navigation menu
3. You'll see a list of all tasks with their status

### Step 2: Open Task Details

1. Find a failed task (status: **red** - failed, crashed, or timeout)
2. Click "View Details" in the Actions column
3. A drawer opens on the right side with task information

### Step 3: Locate RCA Section

Scroll down in the task details drawer to find the **"AI Root Cause Analysis"** section:

```
🤖 AI Root Cause Analysis
[Refresh]
```

---

## Understanding RCA Results

### Result Section

The RCA section displays several key metrics:

| Metric | Description |
|--------|-------------|
| **Confidence** | How certain the AI is (0-100%). Higher is more reliable. |
| **Severity** | Critical (🔴), High (🟠), Medium (🔵), Low (🟢) |
| **Source** | LLM provider and model used |
| **Tokens** | Total tokens used for cost tracking |
| **Cached** | Whether result came from cache (faster, cheaper) |

### Root Cause

The most important section - a clear statement of what went wrong:

```
Root Cause: Task failed due to network timeout while connecting to external API
```

This is the primary issue you should address.

### Confidence Score

- **0.9-1.0**: Very high confidence - AI is certain
- **0.7-0.9**: High confidence - AI is fairly certain
- **0.5-0.7**: Medium confidence - Some uncertainty
- **Below 0.5**: Low confidence - Consider multiple possibilities

**Tip**: If confidence is low, consider:
- Reviewing the findings yourself
- Checking the original logs for more context
- Triggering a new analysis with updated information

### Severity Levels

- **Critical** 🔴: Production-blocking, immediate action required
- **High** 🟠: Significant issue, should be addressed soon
- **Medium** 🔵: Moderate issue, can be scheduled
- **Low** 🟢: Minor issue, informational only

### Findings

Key observations from the failure analysis. Examples:

```
- Task attempted to connect to external API
- Network timeout after 30 seconds
- No retry logic implemented
- Error logs show connection refused
```

These observations help you understand the full context.

### Recommendations

Actionable steps to fix or prevent the issue. Examples:

```
1. Increase timeout threshold to 60 seconds
2. Implement retry logic with exponential backoff
3. Add network connection checks before API calls
4. Consider using a CDN or proxy for external API access
```

These are specific, implementable solutions.

---

## Triggering Manual Analysis

### When to Manually Trigger

- You want updated analysis after fixing the issue
- You suspect the cached result is outdated
- You want to re-analyze with different context
- Cache has expired

### How to Trigger

1. Open the task details drawer (see [Viewing RCA Results](#viewing-rca-results))
2. Click the **"Refresh"** button in the RCA section
3. The analysis runs with updated information

**Note**: Manual refresh bypasses cache and calls the LLM provider.

### Loading State

During analysis, you'll see:

```
Analyzing task failure...
```

This usually takes 5-15 seconds depending on:
- Task complexity
- LLM provider response time
- Network latency

### Cache Indicator

- **"Cached: Yes"**: Result from cache (fast, no cost)
- **"Cached: No"**: Fresh analysis from LLM (slower, incurs cost)

---

## Interpreting Findings and Recommendations

### Prioritizing Recommendations

Order of priority:

1. **Critical severity** findings → Address immediately
2. **High confidence** recommendations → Trust and implement
3. **Medium/low confidence** findings → Verify manually if unsure

### Example Analysis

**Root Cause**: File permission denied

**Findings**:
- Task attempted to write to `/etc/config`
- Permission denied for user 'test-runner'
- No sudo escalation configured

**Recommendations**:
1. ⚠️ Run task with appropriate user permissions
2. Use sudoers configuration to allow specific commands
3. Consider moving config writes to `/tmp` directory

**Action Plan**:
1. **Immediate (Critical)**: Check user permissions in task manifest
2. **Short-term (High)**: Update sudo configuration
3. **Long-term (Medium)**: Review file system usage patterns

### Verifying AI Recommendations

1. **Check the logs**: Look at the original error messages
2. **Compare with findings**: Does AI's analysis match what you see?
3. **Test recommendations**: Implement small changes and re-test
4. **Validate results**: Did the fix work? Re-trigger RCA to confirm

### When to Challenge AI Results

AI is powerful but not perfect. Challenge results when:

- Confidence is low (below 0.5)
- Recommendations don't match your domain knowledge
- Findings seem generic or unrelated
- You have additional context not in the logs

---

## Common Use Cases

### Use Case 1: Network Failures

**Symptom**: Tasks fail with timeout/connection errors

**Typical RCA Output**:
```
Root Cause: Network timeout reaching external API
Severity: High
Findings:
- Connection attempt timed out after 30s
- No retry logic implemented
- Network check shows intermittent connectivity
Recommendations:
1. Implement retry with exponential backoff
2. Add connection health check before API calls
3. Increase timeout threshold
4. Consider using circuit breaker pattern
```

### Use Case 2: Permission Errors

**Symptom**: Tasks fail with "Permission denied"

**Typical RCA Output**:
```
Root Cause: Insufficient file system permissions
Severity: High
Findings:
- Write attempt to /etc/config denied
- User lacks sudo rights
- No sudoers configuration present
Recommendations:
1. Run task with elevated privileges
2. Configure sudoers for specific commands
3. Use alternative location for writes (/tmp)
4. Review permission requirements
```

### Use Case 3: Missing Dependencies

**Symptom**: Tasks fail with module/command not found

**Typical RCA Output**:
```
Root Cause: Missing required Python dependency
Severity: Medium
Findings:
- ImportError for module 'pytest-cov'
- requirements.txt not installed
- Dependency management not automated
Recommendations:
1. Install missing dependencies from requirements.txt
2. Add dependency installation to task pipeline
3. Update Docker image with required packages
4. Consider using virtual environments
```

### Use Case 4: Resource Exhaustion

**Symptom**: Tasks fail with out of memory/CPU errors

**Typical RCA Output**:
```
Root Cause: System memory exhausted during execution
Severity: Critical
Findings:
- OOM killer terminated process
- Memory usage peaked at 8GB limit
- No memory limit configured for task
Recommendations:
1. Set explicit memory limits in task configuration
2. Reduce batch size or optimize memory usage
3. Increase available system memory
4. Add memory monitoring and pre-checks
```

---

## Best Practices

### Using RCA Effectively

1. **Trust but verify**: Review AI recommendations before implementing
2. **Start with high-confidence fixes**: Tackle 0.8-1.0 confidence items first
3. **Address critical issues first**: Priority by severity, not just confidence
4. **Iterate**: After implementing fixes, re-trigger RCA to validate

### Integrating RCA into Workflow

1. **Quick triage**: Check RCA section immediately after task failure
2. **Create tickets**: Copy recommendations into bug tracking system
3. **Assign owners**: Find the right team/person based on recommendations
4. **Track resolution**: Use findings to create acceptance criteria

### Collaborating with Teams

**For Developers**:
- Share RCA results with team chat
- Link to RCA when creating PRs
- Include RCA context in code reviews

**For DevOps**:
- Use RCA findings to update monitoring
- Add alerts for recurring issues
- Automate fixes for common problems

**For QA**:
- Verify recommendations with manual testing
- Report false positives to improve prompts
- Use RCA to prioritize test failures

---

## FAQ

**Q: How accurate is RCA analysis?**
A: Confidence is typically 0.7-0.9 for well-structured log outputs. Low confidence (<0.5) indicates uncertainty.

**Q: Can I trust the recommendations?**
A: Recommendations are based on best practices and common patterns. Verify with your domain knowledge before implementing.

**Q: Why is confidence low sometimes?**
A: Low confidence may indicate: insufficient context, ambiguous error messages, or multiple possible causes.

**Q: How often should I trigger new analysis?**
A: Only when needed (after significant context changes, cache expiration, or to verify fixes).

**Q: What if RCA doesn't match my diagnosis?**
A: Your domain knowledge takes priority. RCA is a tool to help, not replace expert judgment.

---

## Next Steps

- [Developer Guide](./DEVELOPER_GUIDE.md) - Integrate RCA into your applications
- [Operations Guide](./OPERATIONS.md) - Monitor and troubleshoot RCA
- [Costs Guide](./COSTS_AND_PERFORMANCE.md) - Optimize costs and performance
