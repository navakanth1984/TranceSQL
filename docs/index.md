# TranceSQL Documentation Hub

Welcome to **TranceSQL**, a database-agnostic, self-correcting natural language to SQL translator powered by **Gemini 2.5 Pro**.

TranceSQL is designed to run in environments where built-in AI tools (like Copilot or Genie) are unavailable or require expensive premium licensing plans.

---

## ⚡ Core Features

*   **Self-Correcting Execution**: Wraps database calls in an execution loop. If the query fails, TranceSQL feeds the raw database error back to Gemini for up to 3 turns to automatically repair the SQL.
*   **Database-Agnostic**: Connects to any database using a **Callback Pattern** (SQLite, Databricks Spark SQL, Fabric, PostgreSQL, BigQuery, Snowflake, etc.).
*   **Strict Security**: Enforces connections to run in read-only mode, blocking prompt injections from executing destructive commands (such as `DROP` or `DELETE`).
*   **Observability telemetry**: Automatically logs execution runs and parses user feedback (1-5 star ratings) to track performance.

---

## 🚀 Quick Start Example

```python
import os
import sqlite3
from trancesql import TranceSQLTranslator

# 1. Define your table schema grounding context
schema = "Table: users (id INTEGER PRIMARY KEY, email TEXT, active BOOLEAN)"

# 2. Initialize TranceSQL
os.environ["GEMINI_API_KEY"] = "your-google-ai-studio-key"
translator = TranceSQLTranslator(db_schema=schema, db_type="SQLite")

# 3. Create a read-only database query callback
def execute_query(query):
    conn = sqlite3.connect("file:data.db?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        cur.execute(query)
        results = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return columns, results
    finally:
        conn.close()

# 4. Translate and Run!
result = translator.translate("Find active users with a Gmail address", execute_query)
print("Corrected SQL Query:", result["sql"])
```

---

## 📖 Navigating the Docs

To learn more about deploying TranceSQL in production, check out:
*   [Database Connectors](connectors.md): Custom templates for Databricks Delta Lakes, Fabric, PostgreSQL, BigQuery, and more.
*   [Telemetry & Feedback](telemetry.md): Telemetry log structures, feedback hooks, and R&D metrics analysis.
*   [Developer & Publishing Guide](development.md): Workspace setup, test execution, and PyPI/TestPyPI publishing.
