"""
TranceSQL Stress Test Suite — Real-World E-Commerce SQL Scenarios

Schema models a normalized e-commerce database (customers, orders, products,
order_items, payments, reviews) — the kind found on Mode Analytics, LeetCode SQL,
StackOverflow, and dbt community challenge posts.

Scenarios cover:
  - Multi-table JOINs
  - Window functions (RANK, LAG, LEAD, RUNNING TOTAL)
  - CTEs (Common Table Expressions)
  - Correlated subqueries
  - Date arithmetic
  - Conditional aggregation (CASE WHEN)
  - Cohort analysis
  - Self-joins
  - NULL handling
  - Percentage and ratio calculations
"""

import os
import sys
import sqlite3
import time
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from trancesql import TranceSQLTranslator

# ─── CONFIG ──────────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).parent.parent.parent / ".env")

DB_PATH = Path(__file__).parent.parent / "logs" / "stress_test.db"
LOG_PATH = str(Path(__file__).parent.parent / "logs" / "stress_telemetry.jsonl")
RESULTS_PATH = Path(__file__).parent.parent / "logs" / "stress_results.json"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ─── SCHEMA GROUNDING ─────────────────────────────────────────────────────────

DB_SCHEMA = """
Table: customers
Columns:
  - customer_id (INTEGER, PRIMARY KEY)
  - full_name (TEXT)
  - email (TEXT)
  - country (TEXT)
  - signup_date (DATE)  -- Format: YYYY-MM-DD
  - loyalty_tier (TEXT) -- Values: 'bronze', 'silver', 'gold', 'platinum'

Table: products
Columns:
  - product_id (INTEGER, PRIMARY KEY)
  - name (TEXT)
  - category (TEXT)      -- e.g. 'Electronics', 'Clothing', 'Books', 'Home'
  - unit_price (REAL)
  - cost_price (REAL)
  - stock_quantity (INTEGER)

Table: orders
Columns:
  - order_id (INTEGER, PRIMARY KEY)
  - customer_id (INTEGER, FK -> customers.customer_id)
  - order_date (DATE)    -- Format: YYYY-MM-DD
  - status (TEXT)        -- Values: 'completed', 'pending', 'cancelled', 'refunded'
  - shipping_country (TEXT)

Table: order_items
Columns:
  - item_id (INTEGER, PRIMARY KEY)
  - order_id (INTEGER, FK -> orders.order_id)
  - product_id (INTEGER, FK -> products.product_id)
  - quantity (INTEGER)
  - unit_price (REAL)    -- Price at time of purchase (may differ from current product price)

Table: payments
Columns:
  - payment_id (INTEGER, PRIMARY KEY)
  - order_id (INTEGER, FK -> orders.order_id)
  - payment_date (DATE)
  - amount (REAL)
  - method (TEXT)        -- Values: 'credit_card', 'paypal', 'bank_transfer', 'crypto'
  - status (TEXT)        -- Values: 'success', 'failed', 'refunded'

Table: reviews
Columns:
  - review_id (INTEGER, PRIMARY KEY)
  - product_id (INTEGER, FK -> products.product_id)
  - customer_id (INTEGER, FK -> customers.customer_id)
  - rating (INTEGER)     -- 1 to 5
  - review_date (DATE)
  - verified_purchase (INTEGER) -- 1 = verified, 0 = unverified
"""

# ─── REAL-WORLD STRESS TEST CASES ─────────────────────────────────────────────
# Each case mirrors the kind of query asked on StackOverflow, Mode Analytics,
# Metabase community, dbt Slack, and LeetCode SQL problem sets.

STRESS_CASES = [
    {
        "id": "ST-01",
        "source": "StackOverflow — 'running total of revenue by date'",
        "question": "Show each order date and the cumulative total revenue from payments up to and including that date, ordered chronologically.",
        "category": "Window Function / Running Total",
        "complexity": "Medium"
    },
    {
        "id": "ST-02",
        "source": "LeetCode SQL — 'second highest salary' variant",
        "question": "Find the customer who spent the second highest total amount across all their completed orders. Return their full name and total spend.",
        "category": "Subquery / Ranking",
        "complexity": "Medium"
    },
    {
        "id": "ST-03",
        "source": "Mode Analytics — 'cohort retention'",
        "question": "For each month of customer signup, count how many customers placed at least one order in the same calendar month they signed up.",
        "category": "Cohort Analysis / Date Grouping",
        "complexity": "Hard"
    },
    {
        "id": "ST-04",
        "source": "dbt Community — 'revenue by category with margin'",
        "question": "Show each product category, total revenue generated (quantity * unit_price from order_items), total cost (quantity * cost_price from products), and gross margin percentage. Include only completed orders.",
        "category": "Multi-table JOIN / Margin Calculation",
        "complexity": "Hard"
    },
    {
        "id": "ST-05",
        "source": "StackOverflow — 'customers who never ordered'",
        "question": "List all customers who have never placed any order. Return their full name, email, and signup date.",
        "category": "Anti-JOIN / NULL Handling",
        "complexity": "Easy"
    },
    {
        "id": "ST-06",
        "source": "Metabase Community — 'month over month growth'",
        "question": "Show total payment revenue per month and the percentage change compared to the previous month. Only include successful payments.",
        "category": "Window Function / LAG / MoM Growth",
        "complexity": "Hard"
    },
    {
        "id": "ST-07",
        "source": "LeetCode SQL 1484 — 'group sold products by date' variant",
        "question": "For each product category, show the number of unique customers who purchased from that category and the total units sold across completed orders.",
        "category": "GROUP BY / COUNT DISTINCT",
        "complexity": "Medium"
    },
    {
        "id": "ST-08",
        "source": "StackOverflow — 'top N per group'",
        "question": "Find the top 3 best-selling products (by total units sold in completed orders) within each product category. Return category, product name, and total units sold.",
        "category": "Window Function / RANK / Top-N Per Group",
        "complexity": "Hard"
    },
    {
        "id": "ST-09",
        "source": "dbt Community — 'payment method breakdown'",
        "question": "Show the count and total amount of successful payments broken down by payment method, and what percentage each method contributes to the overall total payment volume.",
        "category": "Conditional Aggregation / Percentage",
        "complexity": "Medium"
    },
    {
        "id": "ST-10",
        "source": "Mode Analytics — 'product review quality'",
        "question": "List all products that have at least 1 review, showing the product name, category, average rating, percentage of 5-star reviews, and the count of verified purchase reviews.",
        "category": "Aggregation / CASE WHEN / Filter",
        "complexity": "Medium"
    },
    {
        "id": "ST-11",
        "source": "StackOverflow — 'repeat vs new customers'",
        "question": "For each calendar month in the orders table, count how many distinct customers placed their very first order that month (new customers) versus how many were returning customers.",
        "category": "Cohort / Self-join / Conditional Count",
        "complexity": "Hard"
    },
    {
        "id": "ST-12",
        "source": "LeetCode SQL — 'immediate food delivery' variant",
        "question": "What percentage of orders were placed by platinum loyalty tier customers? Show the count of platinum orders, total orders, and the percentage.",
        "category": "JOIN / Percentage / Conditional",
        "complexity": "Easy"
    },
    {
        "id": "ST-13",
        "source": "dbt Community — 'failed payment rate per country'",
        "question": "For each shipping country with at least 5 orders, show the total orders, number of orders that had at least one failed payment, and the failed payment rate as a percentage.",
        "category": "Multi-table JOIN / Subquery / Ratio",
        "complexity": "Hard"
    },
    {
        "id": "ST-14",
        "source": "StackOverflow — 'price change detection'",
        "question": "Find all products where the current unit_price in the products table is higher than the average unit_price charged in order_items for that product. Return product name, current price, and average historical price.",
        "category": "Correlated Subquery / Self-comparison",
        "complexity": "Medium"
    },
    {
        "id": "ST-15",
        "source": "Mode Analytics — 'gold/platinum customer LTV'",
        "question": "Calculate the lifetime value (total completed order revenue) for each loyalty tier. Show the tier name, number of customers in that tier, average LTV per customer, and the maximum single-customer LTV in the tier.",
        "category": "CTE / Multi-level Aggregation",
        "complexity": "Hard"
    },
]

# ─── DATABASE SETUP ───────────────────────────────────────────────────────────

def create_stress_db(db_path: Path):
    """Build a realistic e-commerce SQLite database with seed data."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    c.executescript("""
    DROP TABLE IF EXISTS reviews;
    DROP TABLE IF EXISTS payments;
    DROP TABLE IF EXISTS order_items;
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS customers;

    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        full_name TEXT,
        email TEXT,
        country TEXT,
        signup_date DATE,
        loyalty_tier TEXT
    );

    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        unit_price REAL,
        cost_price REAL,
        stock_quantity INTEGER
    );

    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER REFERENCES customers(customer_id),
        order_date DATE,
        status TEXT,
        shipping_country TEXT
    );

    CREATE TABLE order_items (
        item_id INTEGER PRIMARY KEY,
        order_id INTEGER REFERENCES orders(order_id),
        product_id INTEGER REFERENCES products(product_id),
        quantity INTEGER,
        unit_price REAL
    );

    CREATE TABLE payments (
        payment_id INTEGER PRIMARY KEY,
        order_id INTEGER REFERENCES orders(order_id),
        payment_date DATE,
        amount REAL,
        method TEXT,
        status TEXT
    );

    CREATE TABLE reviews (
        review_id INTEGER PRIMARY KEY,
        product_id INTEGER REFERENCES products(product_id),
        customer_id INTEGER REFERENCES customers(customer_id),
        rating INTEGER,
        review_date DATE,
        verified_purchase INTEGER
    );
    """)

    # ── Customers ──
    customers = [
        (1,  'Alice Johnson',   'alice@mail.com',   'US', '2022-01-15', 'platinum'),
        (2,  'Bob Smith',       'bob@mail.com',     'UK', '2022-03-20', 'gold'),
        (3,  'Clara Diaz',      'clara@mail.com',   'US', '2022-03-28', 'silver'),
        (4,  'David Park',      'david@mail.com',   'DE', '2022-06-10', 'bronze'),
        (5,  'Elena Rossi',     'elena@mail.com',   'IT', '2022-06-22', 'gold'),
        (6,  'Frank Müller',    'frank@mail.com',   'DE', '2022-08-05', 'silver'),
        (7,  'Grace Kim',       'grace@mail.com',   'KR', '2022-09-01', 'platinum'),
        (8,  'Hiro Tanaka',     'hiro@mail.com',    'JP', '2022-10-11', 'bronze'),
        (9,  'Ingrid Berg',     'ingrid@mail.com',  'SE', '2023-01-03', 'silver'),
        (10, 'James Carter',    'james@mail.com',   'US', '2023-02-14', 'gold'),
        (11, 'Kavya Nair',      'kavya@mail.com',   'IN', '2023-03-30', 'bronze'),
        (12, 'Liam O\'Brien',   'liam@mail.com',    'IE', '2023-04-15', 'silver'),
        # Customer with no orders — for ST-05
        (13, 'Maria Santos',    'maria@mail.com',   'BR', '2023-05-20', 'bronze'),
        (14, 'Nour Hassan',     'nour@mail.com',    'EG', '2023-06-01', 'bronze'),
    ]
    c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)

    # ── Products ──
    products = [
        (1,  'iPhone 15',          'Electronics', 999.99, 720.00, 50),
        (2,  'MacBook Air M3',     'Electronics', 1299.99, 950.00, 30),
        (3,  'Sony WH-1000XM5',   'Electronics', 349.99, 210.00, 100),
        (4,  'Levi 501 Jeans',     'Clothing',    59.99,  22.00,  200),
        (5,  'Nike Air Max',       'Clothing',    129.99, 55.00,  150),
        (6,  'Atomic Habits',      'Books',       16.99,  5.00,   500),
        (7,  'Clean Code',         'Books',       39.99,  12.00,  300),
        (8,  'Dyson V15 Vacuum',   'Home',        599.99, 380.00, 40),
        (9,  'Instant Pot 7-in-1', 'Home',        99.99,  42.00,  120),
        (10, 'Kindle Paperwhite',  'Electronics', 139.99, 80.00,  200),
    ]
    c.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", products)

    # ── Orders ──
    orders = [
        (101, 1,  '2022-02-10', 'completed',  'US'),
        (102, 1,  '2022-05-20', 'completed',  'US'),
        (103, 1,  '2022-11-25', 'completed',  'US'),
        (104, 2,  '2022-04-15', 'completed',  'UK'),
        (105, 2,  '2022-12-01', 'refunded',   'UK'),
        (106, 3,  '2022-03-28', 'completed',  'US'),  # ST-03: same month as signup
        (107, 4,  '2022-07-04', 'completed',  'DE'),
        (108, 5,  '2022-07-19', 'cancelled',  'IT'),
        (109, 5,  '2022-08-30', 'completed',  'IT'),
        (110, 6,  '2022-09-12', 'completed',  'DE'),
        (111, 7,  '2022-09-01', 'completed',  'KR'),  # ST-03: same month as signup
        (112, 7,  '2023-01-15', 'completed',  'KR'),
        (113, 8,  '2022-11-11', 'completed',  'JP'),
        (114, 9,  '2023-01-05', 'completed',  'SE'),  # ST-03: same month as signup
        (115, 10, '2023-02-14', 'completed',  'US'),  # ST-03: same month as signup
        (116, 10, '2023-06-20', 'completed',  'US'),
        (117, 11, '2023-04-01', 'pending',    'IN'),
        (118, 12, '2023-05-10', 'completed',  'IE'),
        (119, 1,  '2023-07-01', 'completed',  'US'),
        (120, 2,  '2023-08-15', 'completed',  'UK'),
        (121, 6,  '2023-09-10', 'completed',  'DE'),
        (122, 4,  '2023-09-22', 'completed',  'DE'),
        (123, 3,  '2023-10-05', 'cancelled',  'US'),
        (124, 5,  '2023-11-20', 'completed',  'IT'),
        (125, 8,  '2023-12-12', 'completed',  'JP'),
    ]
    c.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)

    # ── Order Items ──
    order_items = [
        (1001, 101, 1,  1, 999.99),
        (1002, 101, 6,  2, 16.99),
        (1003, 102, 2,  1, 1299.99),
        (1004, 102, 3,  1, 349.99),
        (1005, 103, 5,  2, 129.99),
        (1006, 103, 9,  1, 99.99),
        (1007, 104, 7,  3, 39.99),
        (1008, 104, 6,  1, 16.99),
        (1009, 105, 8,  1, 599.99),  # refunded
        (1010, 106, 4,  2, 59.99),
        (1011, 107, 10, 1, 139.99),
        (1012, 107, 6,  1, 16.99),
        (1013, 109, 3,  1, 349.99),
        (1014, 110, 9,  2, 99.99),
        (1015, 111, 1,  1, 999.99),
        (1016, 111, 2,  1, 1299.99),
        (1017, 112, 5,  1, 129.99),
        (1018, 113, 4,  3, 59.99),
        (1019, 113, 6,  2, 16.99),
        (1020, 114, 7,  1, 39.99),
        (1021, 115, 3,  2, 349.99),
        (1022, 116, 10, 1, 139.99),
        (1023, 116, 9,  1, 99.99),
        (1024, 118, 1,  1, 999.99),
        (1025, 119, 2,  1, 1299.99),
        (1026, 120, 3,  1, 349.99),
        (1027, 121, 8,  1, 599.99),
        (1028, 122, 10, 2, 139.99),
        (1029, 124, 5,  1, 129.99),
        (1030, 125, 9,  1, 99.99),
    ]
    c.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", order_items)

    # ── Payments ──
    payments = [
        (201, 101, '2022-02-10', 1033.97, 'credit_card',    'success'),
        (202, 102, '2022-05-20', 1649.98, 'paypal',         'success'),
        (203, 103, '2022-11-25', 359.97,  'credit_card',    'success'),
        (204, 104, '2022-04-15', 136.96,  'bank_transfer',  'success'),
        (205, 105, '2022-12-01', 599.99,  'credit_card',    'refunded'),
        (206, 106, '2022-03-28', 119.98,  'paypal',         'success'),
        (207, 107, '2022-07-04', 156.98,  'credit_card',    'success'),
        (208, 109, '2022-08-30', 349.99,  'paypal',         'success'),
        (209, 110, '2022-09-12', 199.98,  'bank_transfer',  'success'),
        (210, 111, '2022-09-01', 2299.98, 'credit_card',    'success'),
        (211, 112, '2023-01-15', 129.99,  'paypal',         'success'),
        (212, 113, '2022-11-11', 213.95,  'crypto',         'success'),
        (213, 114, '2023-01-05', 39.99,   'credit_card',    'success'),
        (214, 115, '2023-02-14', 699.98,  'paypal',         'success'),
        (215, 116, '2023-06-20', 239.98,  'credit_card',    'success'),
        (216, 118, '2023-05-10', 999.99,  'bank_transfer',  'success'),
        (217, 119, '2023-07-01', 1299.99, 'credit_card',    'success'),
        (218, 120, '2023-08-15', 349.99,  'paypal',         'success'),
        (219, 121, '2023-09-10', 599.99,  'bank_transfer',  'success'),
        (220, 122, '2023-09-22', 279.98,  'credit_card',    'success'),
        (221, 124, '2023-11-20', 129.99,  'paypal',         'success'),
        (222, 125, '2023-12-12', 99.99,   'credit_card',    'success'),
        # Failed payments for ST-13
        (223, 108, '2022-07-19', 349.99,  'credit_card',    'failed'),
        (224, 117, '2023-04-01', 139.99,  'credit_card',    'failed'),
    ]
    c.executemany("INSERT INTO payments VALUES (?,?,?,?,?,?)", payments)

    # ── Reviews ──
    reviews = [
        (301, 1,  1,  5, '2022-02-20', 1),
        (302, 2,  1,  5, '2022-06-01', 1),
        (303, 3,  2,  4, '2022-05-01', 1),
        (304, 6,  2,  3, '2022-05-02', 1),
        (305, 4,  3,  4, '2022-04-05', 1),
        (306, 10, 4,  5, '2022-07-20', 1),
        (307, 6,  4,  2, '2022-07-21', 0),
        (308, 3,  5,  5, '2022-09-10', 1),
        (309, 9,  6,  4, '2022-09-20', 1),
        (310, 1,  7,  5, '2022-09-05', 1),
        (311, 2,  7,  4, '2022-09-06', 1),
        (312, 6,  8,  5, '2022-11-20', 1),
        (313, 4,  8,  3, '2022-11-25', 0),
        (314, 7,  9,  5, '2023-01-10', 1),
        (315, 3,  10, 4, '2023-02-20', 1),
        (316, 10, 10, 5, '2023-06-25', 1),
        (317, 9,  12, 3, '2023-05-15', 1),
        (318, 5,  1,  5, '2022-10-01', 1),
        (319, 8,  6,  2, '2023-01-01', 0),
        (320, 7,  6,  1, '2023-01-12', 0),
    ]
    c.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?)", reviews)

    conn.commit()
    conn.close()
    print(f"[DB] Stress test database created at: {db_path}")


# ─── CALLBACK ─────────────────────────────────────────────────────────────────

def make_callback(db_path: Path):
    def run_query(sql: str):
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [d[0] for d in cursor.description] if cursor.description else []
            return columns, rows
        finally:
            conn.close()
    return run_query


# ─── RUNNER ───────────────────────────────────────────────────────────────────

def run_stress_tests():
    print("=" * 70)
    print("  TranceSQL — Real-World SQL Stress Test Suite")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Build DB
    create_stress_db(DB_PATH)

    translator = TranceSQLTranslator(
        db_schema=DB_SCHEMA,
        db_type="SQLite",
        telemetry_log_path=LOG_PATH
    )

    callback = make_callback(DB_PATH)

    results_summary = []
    passed = 0
    failed = 0
    correction_triggered = 0

    for case in STRESS_CASES:
        print(f"\n{'-'*70}")
        print(f"  [{case['id']}] {case['category']} | Complexity: {case['complexity']}")
        print(f"  Source: {case['source']}")
        print(f"  Q: {case['question']}")
        print(f"{'-'*70}")

        result = translator.translate(case["question"], callback, verbose=True)

        status = "[PASS]" if result["success"] else "[FAIL]"
        if result["success"]:
            passed += 1
            print(f"\n  {status} | Attempts: {result['attempts']} | Time: {result['execution_time_seconds']}s")
            print(f"  SQL  : {result['sql']}")
            print(f"  Cols : {result['columns']}")
            # Show first 5 rows only
            preview = result['results'][:5]
            print(f"  Rows ({min(len(result['results']),5)} of {len(result['results'])}): {preview}")
            if result["attempts"] > 1:
                correction_triggered += 1
                print(f"  [!] Self-correction triggered on attempt {result['attempts']}")
        else:
            failed += 1
            print(f"\n  {status} | Attempts: {result['attempts']} | Time: {result['execution_time_seconds']}s")
            print(f"  SQL  : {result.get('sql', 'N/A')}")
            print(f"  ERR  : {result.get('error', 'Unknown')}")

        results_summary.append({
            "id": case["id"],
            "category": case["category"],
            "complexity": case["complexity"],
            "source": case["source"],
            "question": case["question"],
            "success": result["success"],
            "sql": result.get("sql"),
            "attempts": result["attempts"],
            "execution_time_seconds": result["execution_time_seconds"],
            "row_count": len(result.get("results", [])),
            "columns": result.get("columns", []),
            "error": result.get("error")
        })

    # ── Summary Report ──
    print(f"\n{'='*70}")
    print("  STRESS TEST COMPLETE")
    print(f"  Total : {len(STRESS_CASES)} | Pass: {passed} | Fail: {failed}")
    print(f"  Self-correction triggered: {correction_triggered} case(s)")
    print(f"  Pass rate: {round(passed / len(STRESS_CASES) * 100, 1)}%")
    print(f"{'='*70}\n")

    # Breakdown by complexity
    for level in ["Easy", "Medium", "Hard"]:
        subset = [r for r in results_summary if next(c["complexity"] for c in STRESS_CASES if c["id"] == r["id"]) == level]
        p = sum(1 for r in subset if r["success"])
        print(f"  {level:8s}: {p}/{len(subset)} passed")

    # Save full results JSON
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "run_timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(STRESS_CASES),
                "passed": passed,
                "failed": failed,
                "pass_rate_pct": round(passed / len(STRESS_CASES) * 100, 1),
                "self_corrections": correction_triggered
            },
            "cases": results_summary
        }, f, indent=2)

    print(f"\n  Full results saved to: {RESULTS_PATH}")
    print(f"  Telemetry log saved to: {LOG_PATH}")

    return passed, failed


if __name__ == "__main__":
    run_stress_tests()
