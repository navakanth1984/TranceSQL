import os
import sys
import sqlite3
from pathlib import Path

# Add src to python path so we can import trancesql directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from trancesql import TranceSQLTranslator

def test_translation():
    # Load .env explicitly using absolute path relative to this script
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    db_schema = """
    Table: jobs
    Columns:
      - job_id (TEXT, PRIMARY KEY)
      - status (TEXT): 'failed', 'completed', 'pending'
      - prompt (TEXT)
      - created_at (TIMESTAMP)
    """
    
    # Initialize the translator with local telemetry logging
    log_path = str(Path(__file__).parent.parent / "logs" / "telemetry_test.jsonl")
    translator = TranceSQLTranslator(
        db_schema=db_schema,
        db_type="SQLite",
        telemetry_log_path=log_path
    )
    
    # Create the read-only callback
    db_file = Path(__file__).parent.parent.parent / "jobs.db"
    def run_query(query):
        conn = sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro", uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            return columns, results
        finally:
            conn.close()
            
    # Run a simple test query
    print("Testing translation...")
    result = translator.translate("Count the number of failed jobs", run_query)
    
    print("\n--- Test Result ---")
    print("Session ID:", result["session_id"])
    print("Success:", result["success"])
    print("SQL:", result["sql"])
    print("Columns:", result["columns"])
    print("Results:", result["results"])
    print("Attempts:", result["attempts"])
    print("Execution Time:", result["execution_time_seconds"], "s")
    
    # Save manual feedback
    feedback_success = translator.save_manual_feedback(
        session_id=result["session_id"],
        rating=5,
        comment="Auto test passed successfully."
    )
    print("Feedback logged:", feedback_success)
    
    assert result["success"] == True
    assert result["attempts"] == 1
    assert Path(log_path).exists() == True
    print("\nAll assertions passed successfully!")

if __name__ == '__main__':
    test_translation()
