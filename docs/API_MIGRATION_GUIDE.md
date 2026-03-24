# API Migration Guide

This guide helps you migrate between API versions in Omni-Test-Labs.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Migrating from v1 to v2](#migrating-from-v1-to-v2)
- [Migrating from v2 to v3](#migrating-from-v2-to-v3)
- [Backward Compatibility](#backward-compatibility)

---

## Prerequisites

Before migrating, ensure you:
1. Review the [API_CHANGELOG.md](./API_CHANGELOG.md) for all changes
2. Test migration in a non-production environment
3. Update authentication tokens if required

---

## Migrating from v1 to v2

### Changes Overview

| Area | v1 Behavior | v2 Behavior | Action Required |
|------|-----------|-------------|-----------------|
| Task List | Returns all tasks | Pagination (default 100) | Add pagination to your code |
| Dependencies | Not available | Task dependencies supported | Optional enhancement |
| Resource Locks | Manual coordination | Device lock API | Optional enhancement |
| Auth | Basic headers | OAuth2 tokens | Update auth mechanism |

### Step-by-Step Migration

#### 1. Update Request URLs

```python
# v1
response = requests.get("https://api.example.com/api/v1/tasks")

# v2
response = requests.get("https://api.example.com/api/v2/tasks")
```

#### 2. Add Pagination

```python
# v1 - returns all tasks
response = requests.get("/api/v1/tasks")
tasks = response.json()

# v2 - paginated
response = requests.get("/api/v2/tasks?limit=50")
tasks = response.json()

# Get next page
if len(tasks) == 50:
    response = requests.get("/api/v2/tasks?limit=50&offset=50")
    more_tasks = response.json()
```

#### 3. Use Batch Operations (new in v2)

```python
# v1 - one at a time
for task_data in tasks:
    requests.post("/api/v1/tasks", json=task_data)

# v2 - batch
response = requests.post("/api/v2/tasks/batch", json={
    "tasks": tasks
})
result = response.json()
print(f"Created {result['successful']}, Failed {result['failed']}")
```

#### 4. Use Device Locks (new in v2)

```python
# Acquire lock
requests.post(
    f"/api/v2/devices/{device_id}/lock",
    json={"task_id": task_id, "lock_timeout_seconds": 300}
)

# ... perform operations ...

# Release lock
requests.delete(
    f"/api/v2/devices/{device_id}/lock",
    params={"task_id": task_id}
)
```

### Breaking Changes to Handle

#### Task Response Format Update

v1 task response includes flat structure:
```json
{
  "task_id": "task-123",
  "status": "assigned",
  "assigned_device_id": "device-1"
}
```

v2 maintains the same core format (backward compatible).

#### Authentication Update

If using legacy header-based auth, update to OAuth2:
```python
# v1 (deprecated)
headers = {"Authorization": "Bearer token"}

# v2 (recommended)
headers = {"Authorization": "Bearer oauth2-token"}
```

---

## Migrating from v2 to v3

### Changes Overview

| Area | v2 Behavior | v3 Behavior | Action Required |
|------|-----------|-------------|-----------------|
| Data Queries | REST endpoints | GraphQL | Update for GraphQL |
| Real-time | WebSocket limited | Full subscriptions | Optional enhancement |
| State History | Not available | Event sourcing replay | Optional enhancement |
| Auth | OAuth2 | OAuth2 with scopes | Update scopes |

### Step-by-Step Migration

#### 1. GraphQL Introduction

GraphQL offers flexible querying:
```graphql
# v2 - REST
GET /api/v2/tasks?status=running

# v3 - GraphQL
query {
  tasks(status: "running") {
    task_id
    status
    assigned_device_id
    device {
      device_id
      name
    }
  }
}
```

#### 2. Real-time Subscriptions

```graphql
# v3 - Subscribe to task updates
subscription {
  taskUpdated(taskId: "task-123") {
    task_id
    status
    result
  }
}
```

#### 3. Event Sourcing History

```python
# v3 - Replay task state at specific version
response = requests.get(
    "/api/v3/eventsourcing/task/task-123/replay",
    params={"to_version": 5}
)
history_state = response.json()
```

#### 4. Update OAuth2 Scopes

```python
# v2
token = get_token("openid email")

# v3
token = get_token("openid email tasks:read tasks:write devices:read")
```

---

## Backward Compatibility

### Version Negotiation

The API supports automatic version negotiation:

```python
# Request with latest version
headers = {"API-Version": "latest"}

# Request defaults to latest
# If not specified, defaults to v3
```

### Deprecation Headers

Deprecated endpoints include warning headers:
```
X-API-Deprecation-Warning: API version v1 is deprecated and will be sunset in 90 days. Please migrate to v2.
```

### Sunset Policy

- **v1 Sunset**: 2025-06-17
- **v2 Sunsetting**: Not scheduled
- **v3**: Current stable version

---

## Testing Your Migration

### Automated Tests

```python
def test_migration_v1_to_v2():
    # Test v1 endpoint
    v1_response = requests.get("/api/v1/tasks")
    assert v1_response.status_code == 200
    
    # Test v2 endpoint
    v2_response = requests.get("/api/v2/tasks")
    assert v2_response.status_code == 200
    
    # Compare data structure
    assert "tasks" in v2_response.json()
```

### Health Check

```python
# Check API version support
response = requests.get("/health")
version = response.headers.get("X-API-Latest")
assert version in ["v1", "v2", "v3"]
```

---

## Rollback Procedure

If issues arise during migration:

1. Revert to previous version in headers:
   ```python
   headers = {"API-Version": "v1"}
   ```

2. Monitor logs for deprecation warnings

3. Contact support with specific error details

---

## Additional Resources

- [API Documentation](./rca-system/API.md)
- [Architecture Documentation](./ARCHITECTURE.md)
- [Deprecation Guide](./DEPRECATION.md) (when available)
