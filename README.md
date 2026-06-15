# TranceSQL

TranceSQL is a lightweight, database-agnostic Python package that translates natural language questions into valid, executable SQL queries using **Gemini 2.5 Pro**. It contains a built-in **self-correcting retry loop** that catches database engine errors, feeds them back to Gemini, and corrects them in real-time.

By using your own database execution callbacks, TranceSQL does not require database-specific drivers or expensive Premium capacities (like Microsoft Fabric F64+ for Genie/Copilot). It runs anywhere you can execute Python.

---

## Installation

### Install from PyPI (Production)
```bash
pip install TranceSQL
```

### Install directly from GitHub (R&D / Test)
```bash
pip install git+https://github.com/navakanth1984/TranceSQL.git
```

---

## How it Connects to Databases (The Callback Pattern)

TranceSQL does not manage database connections or credentials. Instead, you supply an execution callback function: `exec_callback(sql_query) -> (columns, rows)`. 

If this callback raises an exception during database execution (such as a syntax error or a missing column name), TranceSQL automatically intercepts it and requests a correction from Gemini.

### 1. Connecting to Local SQLite
```python
import sqlite3
import os
from trancesql import TranceSQLTranslator

# 1. Define schema grounding
schema = """
Table: jobs
Columns:
  - job_id (TEXT, PRIMARY KEY)
  - status (TEXT): 'failed', 'completed', 'pending'
  - prompt (TEXT)
  - created_at (TIMESTAMP)
"""

# 2. Initialize TranceSQL
os.environ["GEMINI_API_KEY"] = "your-api-key"
translator = TranceSQLTranslator(
    db_schema=schema, 
    db_type="SQLite",
    telemetry_log_path="logs/trancesql_telemetry.jsonl"
)

# 3. Create a read-only database execution callback
def run_sqlite(query):
    # Connect in read-only mode to prevent injection attacks
    conn = sqlite3.connect("file:jobs.db?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return columns, results
    finally:
        conn.close()

# 4. Translate and Run!
result = translator.translate("List the prompts for all failed jobs", run_sqlite)
if result["success"]:
    print("Columns:", result["columns"])
    print("Rows:", result["results"])
```

### 2. Connecting to Azure Databricks (Spark SQL)
To run this in a Databricks Notebook, install the package using `%pip install` and leverage the built-in PySpark `spark` session:

```python
# Cell 1
%pip install git+https://github.com/navakanth1984/TranceSQL.git
```

```python
# Cell 2
import os
from trancesql import TranceSQLTranslator

# GROUNDING: Define schemas for your Delta tables
lakehouse_schema = """
Table: hive_metastore.sales.orders
Columns:
  - order_id (STRING)
  - customer_id (STRING)
  - amount (DOUBLE)
  - order_date (DATE)
"""

translator = TranceSQLTranslator(db_schema=lakehouse_schema, db_type="SparkSQL")

# Databricks Spark SQL callback
def run_databricks_sql(query):
    # spark is globally available in Databricks notebooks
    df = spark.sql(query)
    return df.columns, df.collect()

# Translate natural language to Spark SQL
result = translator.translate("Show order ids and amounts for orders over 5000", run_databricks_sql)
```

### 3. Connecting to Microsoft Fabric (Lakehouse / Warehouse)
No Premium capacity (F64+) is needed! Fabric Spark notebooks can execute it using the standard `spark` instance in any workspace:

```python
# Cell 1
%pip install git+https://github.com/navakanth1984/TranceSQL.git
```

```python
# Cell 2
import os
from trancesql import TranceSQLTranslator

fabric_schema = """
Table: LH_Sales.customers
Columns:
  - CustomerKey (INT)
  - CustomerName (VARCHAR)
  - Region (VARCHAR)
"""

translator = TranceSQLTranslator(db_schema=fabric_schema, db_type="SparkSQL")

def run_fabric_sql(query):
    # spark runs on your Lakehouse Spark compute
    df = spark.sql(query)
    return df.columns, df.collect()

result = translator.translate("Find customers in the Europe region", run_fabric_sql)
```

---

## Telemetry and R&D Feedback Loops

To continuously improve the accuracy of translations, configure the `telemetry_log_path` argument. TranceSQL will write telemetry objects for each run, which you can load and analyze.

### Recording Manual Feedback
You can capture direct user ratings and comments to fine-tune your grounding context:
```python
# Translate the query
result = translator.translate("List recently added jobs", run_sqlite)

# If you are displaying this in a web UI or dashboard, save user feedback
translator.save_manual_feedback(
    session_id=result["session_id"],
    rating=5,
    comment="Query returned correct columns instantly."
)
```
These ratings are logged directly into the telemetry log file for off-line auditing.
