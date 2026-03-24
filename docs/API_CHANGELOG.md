# API Changelog

This document tracks all changes, features, and deprecations across API versions.

---

## API v3 (In Development)

**Status**: In Progress
**Release Date**: TBD

### New Features
- GraphQL API for flexible data querying
- Real-time subscriptions for task and device events
- Event sourcing with full state history replay
- Advanced filtering and batch operations

### Breaking Changes (from v2)
- Authentication model updated to support OAuth2 scope-based access

### New Endpoints
- `GET /api/v3/graphql` - GraphQL playground
- `WS /api/v3/graphql` - GraphQL subscriptions
- `GET /api/v3/eventsourcing/{entity_type}/{entity_id}/history`
- `POST /api/v3/eventsourcing/{entity_type}/{entity_id}/replay`

### Enhancements
- Optimized database queries for high-volume events
- Enhanced WebSocket event streaming

---

## API v2 (Stable)

**Status**: Stable
**Release Date**: 2025-01-09

### New Features
- Enhanced task filtering and batch operations
- Device lock management for resource coordination
- Task dependency tracking
- Resource-based access control

### Breaking Changes (from v1)
- Updated response format for `/api/v1/tasks` endpoint
- Pagination added to list endpoints (default limit: 100)
- Deprecated legacy authentication header-based auth

### New Endpoints
- `POST /api/v2/tasks/batch` - Create multiple tasks
- `GET /api/v2/tasks/{task_id}/dependencies` - Get task dependencies
- `POST /api/v2/tasks/{task_id}/dependencies` - Create dependency
- `GET /api/v2/devices/locks` - List all device locks
- `POST /api/v2/devices/{device_id}/lock` - Acquire device lock
- `DELETE /api/v2/devices/{device_id}/lock` - Release device lock

### Deprecations
- `GET /api/v1/tasks` without query parameters - Will require pagination in v3

---

## API v1 (Deprecated)

**Status**: Deprecated (sunset in ~90 days)
**Release Date**: 2024-03-18
**Sunset Date**: 2025-06-17

### Breaking Changes (from no versioning)
- Initial API versioning introduced
- Endpoint paths versioned

### Initial Endpoints
- `GET /api/v1/tasks` - List tasks
- `POST /api/v1/tasks` - Create task
- `GET /api/v1/tasks/{task_id}` - Get task details
- `PUT /api/v1/tasks/{task_id}/assign` - Assign task to device
- `POST /api/v1/tasks/{task_id}/result` - Record task result
- `GET /api/v1/tasks/{task_id}/rca` - Get RCA analysis
- `POST /api/v1/tasks/{task_id}/rca` - Trigger RCA analysis
- `GET /api/v1/devices` - List devices
- `POST /api/v1/devices` - Register device
- `GET /api/v1/devices/{device_id}` - Get device details
- `PATCH /api/v1/devices/{device_id}` - Update device
- `POST /api/v1/devices/{device_id}/heartbeat` - Device heartbeat
- `WS /api/v1/ws/tasks/{task_id}` - Task event stream
- `WS /api/v1/ws/devices/{device_id}` - Device event stream

### Deprecation Notices
- `GET /api/v1/tasks` - Use v2 with pagination
- Legacy authentication - Move to OAuth2 in v3

---

## Version Negotiation

### How to specify API version

You can specify the API version in three ways:

1. **URL Path** (recommended):
   ```
   GET /api/v1/tasks
   GET /api/v2/tasks
   GET /api/v3/graphql
   ```

2. **Header**:
   ```
   API-Version: v3
   ```

3. **Query Parameter**:
   ```
   GET /api/tasks?version=v3
   ```

### Response Headers

All API responses include:
- `X-API-Version`: The version that handled the request
- `X-API-Deprecation-Warning`: Deprecation notice if applicable
- `X-API-Latest`: The latest stable version

### Migration Guide

See [API_MIGRATION_GUIDE.md](./API_MIGRATION_GUIDE.md) for detailed migration instructions.
