# API (MVP)

## Conventions
- JSON only. Timestamps ISO-8601 UTC (e.g., "2025-09-01T21:15:00Z").
- IDs are UUID strings.
- Error format:
{ "error": { "code": "VALIDATION_ERROR", "message": "detail", "fields": { "field": "why" } } }

## Users
POST /users
- body: { "name": "Angelina", "email": "angelina@example.com", "timezone": "America/Phoenix" }
- 201 → created user
GET /users/{id}
- 200 → user
PUT /users/{id}
- body: { "name": "...", "email": "...", "timezone": "..." }
- 200 → updated user
DELETE /users/{id}
- 204

## Habits
POST /habits
- body: { "user_id": "uuid", "title": "Drink water", "description": "optional", "status": "active|paused" }
- 201 → habit
GET /habits/{id}
- 200 → habit
PUT /habits/{id}
- 200 → updated habit
DELETE /habits/{id}
- 204
PATCH /habits/{id}/pause
- (optional) body: { "reason": "travel" }
- 200 → { "id": "...", "status": "paused" }

## Events
POST /events
- body: { "habit_id": "uuid", "timestamp": "2025-09-01T21:15:00Z", "note": "optional", "context_id": "uuid?" }
- 201 → event
GET /events/{id}
- 200 → event

## Contexts
POST /contexts
- body: { "name": "travel", "description": "Travel mode—reduced expectations" }
- 201 → context
GET /contexts/{id}
- 200 → context
