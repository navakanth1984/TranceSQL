# TranceSQL Database Connectors Guide

TranceSQL works with any database that can be queried in Python. You only need to supply an execution callback function that matches this signature:
`def callback(query_string: str) -> (columns: list[str], rows: list[tuple])`

Below are templates for connecting TranceSQL to various databases.

---

## 1. Local SQLite
```python
import sqlite3
from trancesql import TranceSQLTranslator

translator = TranceSQLTranslator(db_schema="Table: users (id INT, name TEXT)", db_type="SQLite")

def run_sqlite(query):
    # Enable uri=True for secure read-only mode connection
    conn = sqlite3.connect("file:database.db?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return columns, results
    finally:
        conn.close()

result = translator.translate("Show all users", run_sqlite)
```

---

## 2. Azure Databricks (Spark SQL)
```python
from trancesql import TranceSQLTranslator

translator = TranceSQLTranslator(db_schema="Table: delta_table (id INT, value STRING)", db_type="SparkSQL")

def run_databricks(query):
    # 'spark' session is pre-configured on Databricks clusters
    df = spark.sql(query)
    return df.columns, df.collect()

result = translator.translate("Show values from delta_table", run_databricks)
```

---

## 3. Microsoft Fabric (Lakehouse / SQL Endpoint)
For Fabric notebooks running PySpark:
```python
from trancesql import TranceSQLTranslator

translator = TranceSQLTranslator(db_schema="Table: fabric_lh.sales (id INT, revenue DOUBLE)", db_type="SparkSQL")

def run_fabric(query):
    # Standard PySpark executor in Fabric notebooks
    df = spark.sql(query)
    return df.columns, df.collect()

result = translator.translate("Find total revenue in sales", run_fabric)
```

---

## 4. PostgreSQL (psycopg2)
```python
import psycopg2
from trancesql import TranceSQLTranslator

translator = TranceSQLTranslator(db_schema="Table: customers (customer_id INT, email VARCHAR)", db_type="PostgreSQL")

def run_postgres(query):
    # Connect with read-only transaction mode
    conn = psycopg2.connect(
        host="localhost",
        database="production",
        user="read_only_user",
        password="securepassword"
    )
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return columns, results
    finally:
        conn.close()

result = translator.translate("Show emails for all customers", run_postgres)
```

---

## 5. Google BigQuery
```python
from google.cloud import bigquery
from trancesql import TranceSQLTranslator

translator = TranceSQLTranslator(
    db_schema="Table: dataset.logs (log_id STRING, severity STRING)", 
    db_type="BigQuery"
)

def run_bigquery(query):
    client = bigquery.Client()
    query_job = client.query(query)
    results = query_job.result()
    columns = [field.name for field in results.schema]
    rows = [tuple(row.values()) for row in results]
    return columns, rows

result = translator.translate("Find severity from dataset.logs", run_bigquery)
```
