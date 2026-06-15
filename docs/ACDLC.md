# ACDLC Blueprint for TranceSQL

This document defines the **Agentic Context Development Life Cycle (ACDLC)** specifications and quality gates for **TranceSQL**, ensuring safety, deterministic execution, cost efficiency, and continuous self-learning.

---

## 🔄 The 7-Stage ACDLC Engine

### STAGE 0: GPS FOUNDATION (Alignment & Intent)
*   **Core Goal**: Deliver a lightweight, database-agnostic Python package that translates natural language queries into SQL with 100% database-conforming syntax.
*   **Primary Scope**:
    *   Target platforms: Local CLI, Databricks Notebooks, Microsoft Fabric Notebooks, and custom Python apps.
    *   Exclusion: Does not manage database drivers, connection strings, or cloud secrets. It consumes execution handlers provided by the caller.
*   **Success Metrics**:
    *   *Accuracy*: >95% query execution success rate on valid schema grounding.
    *   *Self-Correction Speed*: Fix errors within 1 additional turn; maximum 3 total turns.
    *   *Safety*: 0% destructive command executions (guaranteed via read-only driver callbacks).

### STAGE 1: CONTEXT ENGINEERING (Schema Grounding)
*   **System Prompt Grounding**: TranceSQL forces the model into a strictly defined role. It inserts the schema description directly into the system context.
*   **Pruning & Token Bounds**: If the schema context exceeds 50KB, it must be compressed or mapped before sending to Gemini. The model is instructed to ONLY query the fields provided.

### STAGE 2: AGENTIC ENGINEERING (Execution star-pattern)
*   **Delegation Flow**:
    ```
    User Question (Notebook / CLI)
          │
          ▼
    TranceSQL Engine (Chat Session Kernel)
          │
      ┌───┴───────────────┐
      ▼                   ▼
    Gemini (Pro 2.5)   Local Exec Callback (Lakehouse / SQLite / DW)
    ```
*   **Boundary Policy**: The AI does not execute SQL directly. The local Python notebook environment handles database execution, preventing prompt injection attacks from running host-level system commands.

### STAGE 3: CONTROLLED EXECUTION (Try-Except and Limits)
*   **Error Catching**: Database queries are executed in a standard `try-except Exception` block.
*   **Self-Correction Turns**: If an error is caught:
    1.  The error is captured as a raw string.
    2.  The error is sent as a user message in the active Gemini chat thread.
    3.  A maximum of 3 turns is permitted. If the 3rd attempt fails, the execution terminates safely and returns the final failure record.

### STAGE 4: KARPATHY DEVELOPMENT (Coding Guidelines)
*   **Explicit > Clever**: No magical metadata mappings. The callback functions are pure Python callables that return a tuple of `(columns, rows)`.
*   **Dependencies Pruning**: Zero dependencies on databases or visual layers. The runtime uses only standard Python libraries and the lightweight `google-genai` SDK.

### STAGE 5: VERIFICATION & VALIDATION (Testing)
*   **Unit Tests**: Local SQLite databases are used in R&D / Non-Prod to run regression tests on query translations.
*   **Validation Gate**: The build outputs must be validated using `python -m build` and `twine check` before uploading to TestPyPI.

### STAGE 6: OBSERVABILITY & EVOLUTION (The Feedback Loop)
*   **Telemetry Logs**: Every execution records run details into a local JSONL log file:
    ```json
    {
      "session_id": "trance-1718445600",
      "timestamp": "2026-06-15T13:21:00",
      "question": "Show failed jobs",
      "db_type": "SQLite",
      "success": true,
      "final_sql": "SELECT * FROM jobs WHERE status = 'failed'",
      "attempts": 1,
      "execution_time": 0.42
    }
    ```
*   **Feedback Mechanism**: Users can capture ratings and remarks using:
    ```python
    translator.save_manual_feedback(session_id="trance-1718445600", rating=5, comment="Spot on!")
    ```
*   **Evolutionary Iteration**: R&D engineers review sessions where `attempts > 1` or `success = False` to tune the schema instruction prompts or adjust Gemini model configuration settings.
