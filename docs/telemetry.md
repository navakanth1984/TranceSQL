# Telemetry, Observability & Feedback Loops

TranceSQL implements **Stage 6 (Observability & Evolution)** of the ACDLC framework by logging execution telemetry and manual ratings to JSONL format files.

---

## Telemetry Format

When `telemetry_log_path` is passed during translator initialization, every run appends a telemetry payload:

```json
{
  "session_id": "trance-1718445600",
  "timestamp": "2026-06-15T13:21:00.123456",
  "question": "Count failed jobs",
  "db_type": "SQLite",
  "success": true,
  "final_sql": "SELECT count(*) FROM jobs WHERE status = 'failed'",
  "attempts": 1,
  "execution_time": 0.421,
  "attempts_history": [
    {
      "attempt": 1,
      "sql_generated": "SELECT count(*) FROM jobs WHERE status = 'failed'",
      "timestamp": "2026-06-15T13:21:00.121300",
      "success": true
    }
  ]
}
```

If a self-correction event occurs, `attempts_history` lists the errors and corrections step-by-step:

```json
"attempts_history": [
  {
    "attempt": 1,
    "sql_generated": "SELECT MY_CUSTOM_UPPER(status) FROM jobs",
    "timestamp": "2026-06-15T13:21:00.121300",
    "success": false,
    "error_encountered": "no such function: MY_CUSTOM_UPPER"
  },
  {
    "attempt": 2,
    "sql_generated": "SELECT UPPER(status) FROM jobs",
    "timestamp": "2026-06-15T13:21:02.341100",
    "success": true
  }
]
```

---

## User Feedback Integration

You can integrate feedback collection into your app or Web Dashboard to continuously collect user rating inputs:

```python
# 1. Translate natural language to SQL
result = translator.translate("Show failed jobs", run_query)

# 2. Render results in your UI
# 3. capture user feedback (e.g. click stars in a dashboard)
translator.save_manual_feedback(
    session_id=result["session_id"],
    rating=5,
    comment="Parsed dates correctly on the first attempt."
)
```

Manual feedback creates a specialized JSONL entry:

```json
{
  "type": "user_feedback",
  "session_id": "trance-1718445600",
  "timestamp": "2026-06-15T13:22:12.987654",
  "rating": 5,
  "comment": "Parsed dates correctly on the first attempt."
}
```

---

## Analyzing logs for Continuous R&D

You can run offline analysis scripts over the log file to identify weak translations:

```python
import json

telemetry_file = "logs/trancesql_telemetry.jsonl"
failed_sessions = []

with open(telemetry_file, "r") as f:
    for line in f:
        data = json.loads(line.strip())
        if data.get("type") == "user_feedback":
            continue
        
        # Check for failures or runs requiring multiple attempts
        if not data.get("success") or data.get("attempts", 1) > 1:
            failed_sessions.append(data)

print(f"Total weak translations found: {len(failed_sessions)}")
for s in failed_sessions[:5]:
    print(f"- Question: {s['question']}")
    print(f"  Attempts needed: {s['attempts']}")
    print(f"  Last SQL: {s['final_sql']}")
```

Use these results to improve column mappings, schema definitions, and instruction sets.
