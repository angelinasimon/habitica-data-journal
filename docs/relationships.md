# Relationships (MVP)

- users (1) → (∞) habits  
  Reason: one account can own many habits. Enforce via habits.user_id (FK).  
  Invariants: a habit cannot exist without a valid user.

- habits (1) → (∞) events  
  Reason: a habit accrues many log entries over time.  
  Invariants: events.habit_id must exist; events are append-only.

- contexts (1) → (∞) events (optional)  
  Reason: an event may be tagged with the context in which it happened (travel/exam/sick).  
  Invariants: events.context_id is nullable; if present it must reference contexts.id.

Query shapes we will use most:
- `events WHERE habit_id = ? ORDER BY timestamp DESC` (streaks/adherence).
- `events WHERE user_id = ? AND timestamp BETWEEN ? AND ?`.
- `events WHERE context_id = ?` (compare performance in travel vs home).