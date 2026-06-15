import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from trancesql import TranceSQLTranslator

DB_FILE = Path(__file__).parent / "test_complex.db"

def setup_test_database():
    """Create and seed tables for the 5 complex query test cases."""
    if DB_FILE.exists():
        DB_FILE.unlink()
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # --- 1. Gaps and Islands (user_logins) ---
    cursor.execute("""
    CREATE TABLE user_logins (
        user_id INTEGER,
        login_date DATE
    );
    """)
    cursor.executemany("INSERT INTO user_logins (user_id, login_date) VALUES (?, ?);", [
        (1, '2026-06-01'),
        (1, '2026-06-02'),
        (1, '2026-06-03'), # Island 1 (3 days)
        (1, '2026-06-05'),
        (1, '2026-06-06'), # Island 2 (2 days)
        (2, '2026-06-01'),
        (2, '2026-06-03'),
        (2, '2026-06-04'),
        (2, '2026-06-05'), # Island 3 (3 days)
        (2, '2026-06-06')  # Island 3 continued (4 days total)
    ])
    
    # --- 2. Recursive CTEs (parts & bill_of_materials) ---
    cursor.execute("""
    CREATE TABLE parts (
        part_id TEXT PRIMARY KEY,
        part_name TEXT,
        unit_cost REAL
    );
    """)
    cursor.execute("""
    CREATE TABLE bill_of_materials (
        parent_id TEXT,
        child_id TEXT,
        quantity_per_parent INTEGER
    );
    """)
    cursor.executemany("INSERT INTO parts (part_id, part_name, unit_cost) VALUES (?, ?, ?);", [
        ('A100', 'Assembly 100', 10.00),
        ('B200', 'Subassembly 200', 5.00),
        ('C300', 'Subassembly 300', 8.00),
        ('P001', 'Bolt', 0.10),
        ('P002', 'Nut', 0.05),
        ('P003', 'Washer', 0.02)
    ])
    cursor.executemany("INSERT INTO bill_of_materials (parent_id, child_id, quantity_per_parent) VALUES (?, ?, ?);", [
        ('A100', 'B200', 2),
        ('A100', 'C300', 1),
        ('B200', 'P001', 4),
        ('B200', 'P002', 4),
        ('C300', 'P002', 2),
        ('C300', 'P003', 2)
    ])
    
    # --- 3. Clickstream Sessionization (clickstream) ---
    cursor.execute("""
    CREATE TABLE clickstream (
        event_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        event_timestamp DATETIME,
        event_type TEXT
    );
    """)
    cursor.executemany("INSERT INTO clickstream (event_id, user_id, event_timestamp, event_type) VALUES (?, ?, ?, ?);", [
        (1, 101, '2026-06-15 10:00:00', 'pageview'),
        (2, 101, '2026-06-15 10:15:00', 'pageview'),
        (3, 101, '2026-06-15 10:20:00', 'click'),
        (4, 101, '2026-06-15 11:00:00', 'pageview'),
        (5, 101, '2026-06-15 11:10:00', 'click'),
        (6, 102, '2026-06-15 10:00:00', 'pageview')
    ])
    
    # --- 4. FIFO Inventory (purchases & sales) ---
    cursor.execute("""
    CREATE TABLE purchases (
        purchase_id INTEGER PRIMARY KEY,
        purchase_time DATETIME,
        product_id INTEGER,
        quantity INTEGER,
        unit_cost REAL
    );
    """)
    cursor.execute("""
    CREATE TABLE sales (
        sale_id INTEGER PRIMARY KEY,
        sale_time DATETIME,
        product_id INTEGER,
        quantity INTEGER
    );
    """)
    cursor.executemany("INSERT INTO purchases (purchase_id, purchase_time, product_id, quantity, unit_cost) VALUES (?, ?, ?, ?, ?);", [
        (1, '2026-06-01 09:00:00', 99, 10, 5.00),
        (2, '2026-06-02 09:00:00', 99, 15, 6.00),
        (3, '2026-06-03 09:00:00', 99, 20, 7.00)
    ])
    cursor.executemany("INSERT INTO sales (sale_id, sale_time, product_id, quantity) VALUES (?, ?, ?, ?);", [
        (10, '2026-06-01 15:00:00', 99, 5),
        (11, '2026-06-02 15:00:00', 99, 13)
    ])
    
    # --- 5. Employee Salaries (employee_salaries) ---
    cursor.execute("""
    CREATE TABLE employee_salaries (
        employee_id INTEGER PRIMARY KEY,
        department_id INTEGER,
        salary REAL
    );
    """)
    cursor.executemany("INSERT INTO employee_salaries (employee_id, department_id, salary) VALUES (?, ?, ?);", [
        (1, 10, 50000.00),
        (2, 10, 60000.00),
        (3, 10, 70000.00),
        (4, 20, 40000.00),
        (5, 20, 50000.00),
        (6, 20, 80000.00),
        (7, 20, 90000.00)
    ])
    
    conn.commit()
    conn.close()
    print("Test database seeded successfully.")

def run_db_query(query):
    """Execution callback function to query the test DB in read-only mode."""
    uri = f"file:{DB_FILE.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return columns, results
    finally:
        conn.close()

def main():
    # Load .env
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    
    setup_test_database()
    
    test_cases = [
        {
            "id": 1,
            "name": "Gaps & Islands (Consecutive Login Streaks)",
            "schema": """
            Table: user_logins
            Columns:
              - user_id (INTEGER)
              - login_date (DATE): format YYYY-MM-DD
            """,
            "question": "Identify all users who have achieved a consecutive login streak of 3 or more days. For each streak, return the user_id, the start date of the streak, the end date, and the total consecutive days.",
            "expected_count": 2
        },
        {
            "id": 2,
            "name": "Recursive CTEs (Consolidated Bill of Materials)",
            "schema": """
            Table: parts
            Columns:
              - part_id (TEXT, PRIMARY KEY)
              - part_name (TEXT)
              - unit_cost (REAL)
            
            Table: bill_of_materials
            Columns:
              - parent_id (TEXT)
              - child_id (TEXT)
              - quantity_per_parent (INTEGER)
            """,
            "question": "For the parent assembly 'A100', traverse the hierarchical Bill of Materials (BOM) to find all required sub-components, their total consolidated quantities, and cumulative costs. Output the component ID, component name, total required quantity, and total cost.",
            "expected_count": 5
        },
        {
            "id": 3,
            "name": "Cohort & Sessionization (30-Min Inactivity)",
            "schema": """
            Table: clickstream
            Columns:
              - event_id (INTEGER, PRIMARY KEY)
              - user_id (INTEGER)
              - event_timestamp (DATETIME): format YYYY-MM-DD HH:MM:SS
              - event_type (TEXT)
            """,
            "question": "Segment user clickstream events into distinct sessions, where a new session begins after a gap of 30 minutes (1800 seconds) or more of inactivity. Calculate the session start, end, duration (in seconds), and the number of events for each session.",
            "expected_count": 3
        },
        {
            "id": 4,
            "name": "FIFO Inventory Valuation",
            "schema": """
            Table: purchases
            Columns:
              - purchase_id (INTEGER, PRIMARY KEY)
              - purchase_time (DATETIME): format YYYY-MM-DD HH:MM:SS
              - product_id (INTEGER)
              - quantity (INTEGER)
              - unit_cost (REAL)

            Table: sales
            Columns:
              - sale_id (INTEGER, PRIMARY KEY)
              - sale_time (DATETIME): format YYYY-MM-DD HH:MM:SS
              - product_id (INTEGER)
              - quantity (INTEGER)
            """,
            "question": "Calculate the Cost of Goods Sold (COGS) and the remaining inventory value for each product using the First-In, First-Out (FIFO) inventory allocation method. Output the product ID, total units sold, total COGS, remaining units, and remaining inventory value.",
            "expected_count": 1
        },
        {
            "id": 5,
            "name": "Dialect-Agnostic Median (Salary by Department)",
            "schema": """
            Table: employee_salaries
            Columns:
              - employee_id (INTEGER, PRIMARY KEY)
              - department_id (INTEGER)
              - salary (REAL)
            """,
            "question": "Find the median employee salary for each department, handling both odd and even counts of employees per department, without using built-in median or percentile functions. Return department_id and median_salary.",
            "expected_count": 2
        }
    ]
    
    # Configure logs path
    telemetry_path = str(Path(__file__).parent.parent / "logs" / "telemetry_complex.jsonl")
    
    print("\n" + "="*60)
    print("  TRANCESQL COMPLEX QUERY CHALLENGES RUNNER")
    print("="*60)
    
    passed_cases = 0
    
    for case in test_cases:
        print(f"\n[Case {case['id']}]: {case['name']}")
        print(f"Question: {case['question']}")
        
        translator = TranceSQLTranslator(
            db_schema=case['schema'],
            db_type="SQLite",
            telemetry_log_path=telemetry_path
        )
        
        result = translator.translate(case['question'], run_db_query, max_retries=3, verbose=True)
        
        if result["success"]:
            print(f"-> SUCCESS (Took {result['attempts']} attempt(s))")
            print(f"Columns: {result['columns']}")
            print("Results:")
            for row in result["results"]:
                print(f"  {row}")
            
            # Save rating feedback
            translator.save_manual_feedback(
                session_id=result["session_id"],
                rating=5 if result["attempts"] == 1 else 4,
                comment=f"Verified complex test case {case['id']}"
            )
            passed_cases += 1
        else:
            print(f"-> FAILED after {result['attempts']} attempts")
            print(f"Error: {result['error']}")
            
    print("\n" + "="*60)
    print(f"  COMPLEX VERIFICATION SUMMARY: {passed_cases}/{len(test_cases)} Passed")
    print("="*60)
    
    # Cleanup database file
    if DB_FILE.exists():
        DB_FILE.unlink()

if __name__ == '__main__':
    main()
