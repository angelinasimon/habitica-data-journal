# Database Model (MVP)

## Entities
- users(id, name, email, created_at, updated_at)
- habits(id, user_id→users.id, title, description, status, created_at, updated_at)
- events(id, habit_id→habits.id, timestamp, note, context_id→contexts.id?)
- contexts(id, name, description)

## Rationale
- events are append-only → analytics-friendly (streaks/adherence).
- status on habit → pause/resume without deleting history.
- optional context on event → compare performance in special modes.

## Access patterns
- by-habit event timeline (desc)
- by-user time window
- by-context filter
