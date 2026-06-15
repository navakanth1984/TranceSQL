import re
import os
import json
import time
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types

class TranceSQLTranslator:
    def __init__(
        self, 
        db_schema: str, 
        db_type: str = "SQLite", 
        model: str = "gemini-2.5-pro", 
        temperature: float = 0.0,
        api_key: str = None,
        telemetry_log_path: str = None
    ):
        """
        Initialize the TranceSQL Translator.
        
        :param db_schema: The text-based database schema grounding context.
        :param db_type: The target database system (e.g. SQLite, SparkSQL, PostgreSQL, BigQuery).
        :param model: The Gemini model name (default is gemini-2.5-pro).
        :param temperature: Generation temperature (default 0.0 for deterministic generation).
        :param api_key: Gemini API Key (optional, defaults to environment variable GEMINI_API_KEY).
        :param telemetry_log_path: Path to write local R&D telemetry and logs (optional).
        """
        # If API key is provided, set it in environment for the SDK
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
            
        self.client = genai.Client()
        self.model = model
        self.temperature = temperature
        self.db_schema = db_schema
        self.db_type = db_type
        self.telemetry_log_path = telemetry_log_path
        
        self.system_instruction = f"""
        You are an expert database assistant that translates natural language questions into valid, executable {self.db_type} SQL queries.

        Here is the database schema grounding:
        {self.db_schema}

        Guidelines:
        1. Generate ONLY the executable {self.db_type} SQL query.
        2. Do NOT include any markdown formatting like ```sql or ```.
        3. Do NOT include any explanation, greeting, or extra text. Output only the raw SQL.
        4. Use only the tables and columns defined in the schema grounding.
        5. The database connection is configured as READ-ONLY. Generate only SELECT statements. Do not attempt INSERT, UPDATE, DELETE, or DROP.
        """

    def clean_sql(self, raw_response: str) -> str:
        """Strip out markdown formatting or backticks from the model's response."""
        cleaned = re.sub(r"```(?:sql)?\s*(.*?)\s*```", r"\1", raw_response, flags=re.DOTALL | re.IGNORECASE)
        cleaned = cleaned.strip("` \t\r\n")
        return cleaned

    def _log_telemetry(self, session_data: dict):
        """Append session data to the telemetry log file if configured."""
        if not self.telemetry_log_path:
            return
            
        try:
            log_file = Path(self.telemetry_log_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(session_data) + "\n")
        except Exception as e:
            # Prevent logging failure from breaking query execution
            print(f"[TranceSQL Warning] Failed to log telemetry: {e}")

    def translate(self, question: str, exec_callback, max_retries: int = 3, verbose: bool = True) -> dict:
        """
        Translates a natural language question into SQL, executes it using the provided callback,
        and handles self-correction turns if exceptions are raised.
        
        :param question: The natural language question to translate.
        :param exec_callback: A callback function taking a single SQL string argument, 
                              executing it, and returning a tuple/list: (columns, rows).
        :param max_retries: Maximum number of correction attempts (default 3).
        :param verbose: Print internal logs to stdout.
        :return: A dictionary containing execution status, final SQL, results, and retry count.
        """
        # Start a chat session to maintain conversational memory for corrections
        chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                system_instruction=self.system_instruction
            )
        )
        
        session_id = f"trance-{int(time.time())}"
        start_time = time.time()
        
        if verbose:
            print(f"\n[TranceSQL Session: {session_id}] Translating: '{question}'")
            
        message = question
        attempts_log = []
        final_result = None
        
        for attempt in range(1, max_retries + 1):
            if verbose:
                print(f"[TranceSQL] Attempt {attempt} of {max_retries}...")
                
            response = chat.send_message(message)
            raw_sql = response.text
            sql_query = self.clean_sql(raw_sql)
            
            if verbose:
                print(f"[TranceSQL] Generated SQL: {sql_query}")
                
            attempt_record = {
                "attempt": attempt,
                "sql_generated": sql_query,
                "timestamp": datetime.now().isoformat()
            }
            
            try:
                # Run user-supplied database connection execution callback
                columns, results = exec_callback(sql_query)
                
                if verbose:
                    print("[TranceSQL] Database query execution succeeded!")
                    
                attempt_record["success"] = True
                attempts_log.append(attempt_record)
                
                final_result = {
                    "session_id": session_id,
                    "success": True,
                    "sql": sql_query,
                    "columns": list(columns),
                    "results": list(results),
                    "attempts": attempt,
                    "execution_time_seconds": round(time.time() - start_time, 3)
                }
                break
                
            except Exception as e:
                error_msg = str(e)
                if verbose:
                    print(f"[TranceSQL Database Error]: {error_msg}")
                    
                attempt_record["success"] = False
                attempt_record["error_encountered"] = error_msg
                attempts_log.append(attempt_record)
                
                if attempt == max_retries:
                    if verbose:
                        print("[TranceSQL] Max retries reached. Exiting safely.")
                    final_result = {
                        "session_id": session_id,
                        "success": False,
                        "error": error_msg,
                        "sql": sql_query,
                        "attempts": attempt,
                        "execution_time_seconds": round(time.time() - start_time, 3)
                    }
                    break
                
                # Feedback error to Gemini in the next chat turn
                if verbose:
                    print("[TranceSQL] Initiating self-correction feedback loop...")
                message = (
                    f"Executing the generated query failed with the following database error:\n"
                    f"{error_msg}\n\n"
                    f"Please analyze the error, review the schema grounding, fix the query, "
                    f"and output ONLY the corrected SQL query without any formatting or markdown."
                )

        # Log session telemetry
        telemetry_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "db_type": self.db_type,
            "success": final_result["success"],
            "final_sql": final_result.get("sql"),
            "attempts": final_result["attempts"],
            "execution_time": final_result["execution_time_seconds"],
            "attempts_history": attempts_log
        }
        self._log_telemetry(telemetry_data)
        
        return final_result

    def save_manual_feedback(self, session_id: str, rating: int, comment: str = None) -> bool:
        """
        Save manual user feedback for a given session.
        
        :param session_id: The session identifier returned by translate().
        :param rating: Integer rating (e.g., 1-5).
        :param comment: Optional comment or correction from user.
        :return: True if successfully logged.
        """
        if not self.telemetry_log_path:
            return False
            
        feedback_record = {
            "type": "user_feedback",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "rating": rating,
            "comment": comment
        }
        
        try:
            with open(self.telemetry_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(feedback_record) + "\n")
            return True
        except Exception as e:
            print(f"[TranceSQL Warning] Failed to log user feedback: {e}")
            return False
