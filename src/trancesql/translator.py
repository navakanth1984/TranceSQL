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
        schema_linker_model: str = "gemini-2.5-flash",
        temperature: float = 0.0,
        api_key: str = None,
        telemetry_log_path: str = None,
        enable_schema_linking: bool = True,
        enable_value_sampling: bool = True,
    ):
        """
        Initialize the TranceSQL Translator.

        :param db_schema: Full text-based database schema grounding context.
        :param db_type: Target database system (SQLite, SparkSQL, PostgreSQL, BigQuery, etc.).
        :param model: Gemini model for SQL generation (default: gemini-2.5-pro).
        :param schema_linker_model: Gemini model for schema pruning (default: gemini-2.5-flash).
        :param temperature: Generation temperature (default 0.0 for deterministic output).
        :param api_key: Gemini API Key — falls back to GEMINI_API_KEY env var if omitted.
        :param telemetry_log_path: Path to write JSONL telemetry logs (optional).
        :param enable_schema_linking: Use Flash to prune schema before generation (default True).
        :param enable_value_sampling: Auto-sample column values on empty results (default True).
        """
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key

        self.client = genai.Client()
        self.model = model
        self.schema_linker_model = schema_linker_model
        self.temperature = temperature
        self.full_schema_raw = db_schema
        self.db_type = db_type
        self.telemetry_log_path = telemetry_log_path
        self.enable_schema_linking = enable_schema_linking
        self.enable_value_sampling = enable_value_sampling

        # Pre-parse table blocks from the schema for selective pruning
        self._table_blocks = self._parse_table_blocks(db_schema)

    # ─── SCHEMA PARSING ──────────────────────────────────────────────────────

    def _parse_table_blocks(self, schema: str) -> dict:
        """
        Split a multi-table schema string into a dict keyed by table name.
        Handles the format: 'Table: <name>\nColumns:\n  - ...'
        """
        blocks = {}
        # Split on 'Table:' boundaries
        parts = re.split(r"(?=\bTable:\s)", schema.strip(), flags=re.IGNORECASE)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            match = re.match(r"Table:\s*(\w+)", part, re.IGNORECASE)
            if match:
                table_name = match.group(1).lower()
                blocks[table_name] = part
        return blocks

    # ─── PHASE 1: SCHEMA LINKING (DDL PRUNING) ───────────────────────────────

    def _link_schema(self, question: str, verbose: bool) -> str:
        """
        Use gemini-2.5-flash to identify which tables are relevant to the question,
        then return a pruned schema string containing only those tables.
        Falls back to the full schema if linking fails or returns nothing useful.
        """
        if not self._table_blocks:
            return self.full_schema_raw

        table_list = ", ".join(self._table_blocks.keys())
        linker_prompt = (
            f"You are a database schema routing assistant.\n\n"
            f"Available tables: {table_list}\n\n"
            f"User question: {question}\n\n"
            f"Return ONLY a JSON array of the table names that are needed to answer this question. "
            f"Include tables required for JOINs. Example: [\"orders\", \"customers\"]\n"
            f"Output only the JSON array. No explanation."
        )

        try:
            response = self.client.models.generate_content(
                model=self.schema_linker_model,
                contents=linker_prompt,
                config=types.GenerateContentConfig(temperature=0.0),
            )
            raw = response.text.strip()
            # Extract JSON array from response
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if not match:
                raise ValueError("No JSON array found in schema linker response.")

            selected = json.loads(match.group())
            selected_lower = [t.lower() for t in selected]

            pruned_blocks = [
                self._table_blocks[t]
                for t in selected_lower
                if t in self._table_blocks
            ]

            if not pruned_blocks:
                if verbose:
                    print("[TranceSQL] Schema linker returned no matches — using full schema.")
                return self.full_schema_raw

            pruned_schema = "\n\n".join(pruned_blocks)
            if verbose:
                print(f"[TranceSQL] Schema linked — using tables: {selected_lower}")
            return pruned_schema

        except Exception as e:
            if verbose:
                print(f"[TranceSQL] Schema linking failed ({e}) — using full schema.")
            return self.full_schema_raw

    # ─── PHASE 3: VALUE AUTO-SAMPLING ────────────────────────────────────────

    def _extract_string_filters(self, sql: str) -> list:
        """
        Extract (table_or_alias, column, value) tuples from WHERE clause string
        comparisons in a SQL query, e.g. WHERE country = 'US' -> [('country', 'US')]
        """
        pattern = re.findall(
            r"(\w+)\s*=\s*'([^']+)'",
            sql,
            re.IGNORECASE
        )
        return pattern  # list of (column_or_alias, value)

    def _sample_column_values(self, column: str, exec_callback, schema: str) -> list:
        """
        Try to discover the actual stored values for a given column by querying
        the most likely table containing it from the pruned schema.
        """
        # Find which table owns this column from schema text
        match = re.search(
            rf"Table:\s*(\w+).*?-\s*{re.escape(column)}\s*\(",
            schema,
            re.IGNORECASE | re.DOTALL
        )
        if not match:
            return []

        table_name = match.group(1)
        sample_sql = f"SELECT DISTINCT {column} FROM {table_name} LIMIT 10"
        try:
            _, rows = exec_callback(sample_sql)
            return [str(r[0]) for r in rows if r[0] is not None]
        except Exception:
            return []

    # ─── SYSTEM PROMPT BUILDER ───────────────────────────────────────────────

    def _build_system_instruction(self, schema: str, knowledge_evidence: str = None) -> str:
        evidence_block = ""
        if knowledge_evidence:
            evidence_block = (
                f"\n\nSemantic Knowledge Evidence (use this to resolve ambiguous values, "
                f"abbreviations, or business definitions):\n{knowledge_evidence}"
            )

        return (
            f"You are an expert database assistant that translates natural language questions "
            f"into valid, executable {self.db_type} SQL queries.\n\n"
            f"Database schema grounding:\n{schema}"
            f"{evidence_block}\n\n"
            f"Guidelines:\n"
            f"1. Generate ONLY the executable {self.db_type} SQL query.\n"
            f"2. Do NOT include any markdown formatting like ```sql or ```.\n"
            f"3. Do NOT include any explanation, greeting, or extra text. Output only the raw SQL.\n"
            f"4. Use only the tables and columns defined in the schema grounding.\n"
            f"5. The database connection is READ-ONLY. Generate only SELECT statements. "
            f"Never attempt INSERT, UPDATE, DELETE, or DROP.\n"
            f"6. If filtering on string values, match the exact casing and spelling used in "
            f"the schema evidence or sample values provided."
        )

    # ─── TELEMETRY ───────────────────────────────────────────────────────────

    def _log_telemetry(self, session_data: dict):
        if not self.telemetry_log_path:
            return
        try:
            log_file = Path(self.telemetry_log_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(session_data) + "\n")
        except Exception as e:
            print(f"[TranceSQL Warning] Failed to log telemetry: {e}")

    # ─── SQL CLEANUP ─────────────────────────────────────────────────────────

    def clean_sql(self, raw_response: str) -> str:
        cleaned = re.sub(
            r"```(?:sql)?\s*(.*?)\s*```", r"\1", raw_response,
            flags=re.DOTALL | re.IGNORECASE
        )
        return cleaned.strip("` \t\r\n")

    # ─── MAIN TRANSLATE METHOD ───────────────────────────────────────────────

    def translate(
        self,
        question: str,
        exec_callback,
        max_retries: int = 3,
        knowledge_evidence: str = None,
        verbose: bool = True,
    ) -> dict:
        """
        Translate a natural language question into SQL and execute it.

        Pipeline:
          1. Schema Linking  — Flash prunes the full schema to relevant tables only.
          2. Evidence Injection — Optional semantic hints injected into system prompt.
          3. SQL Generation  — Pro generates the query inside a stateful chat session.
          4. Execution       — User callback runs the query on the real database.
          5. Value Sampling  — On empty results, sample actual column values and retry.
          6. Error Correction — On DB exceptions, feed error back to Pro and retry.

        :param question: Natural language question to translate.
        :param exec_callback: fn(sql: str) -> (columns: list, rows: list)
        :param max_retries: Max correction attempts on error (default 3).
        :param knowledge_evidence: Optional string with semantic hints, value mappings,
                                   or business definitions to ground ambiguous terms.
        :param verbose: Print execution log to stdout.
        :return: Dict with session_id, success, sql, columns, results, attempts,
                 execution_time_seconds, and schema_linked flag.
        """
        session_id = f"trance-{int(time.time())}"
        start_time = time.time()

        if verbose:
            print(f"\n[TranceSQL Session: {session_id}] Translating: '{question}'")

        # ── Phase 1: Schema Linking ──
        if self.enable_schema_linking and len(self._table_blocks) > 1:
            if verbose:
                print("[TranceSQL] Running schema linker...")
            active_schema = self._link_schema(question, verbose)
            schema_linked = active_schema != self.full_schema_raw
        else:
            active_schema = self.full_schema_raw
            schema_linked = False

        # ── Phase 2: Build system instruction with evidence ──
        system_instruction = self._build_system_instruction(active_schema, knowledge_evidence)
        if knowledge_evidence and verbose:
            print(f"[TranceSQL] Evidence injected: {knowledge_evidence[:80]}...")

        # Start stateful chat session for correction loop
        chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                system_instruction=system_instruction,
            ),
        )

        message = question
        attempts_log = []
        final_result = None
        value_sample_triggered = False

        for attempt in range(1, max_retries + 1):
            if verbose:
                print(f"[TranceSQL] Attempt {attempt} of {max_retries}...")

            response = chat.send_message(message)
            sql_query = self.clean_sql(response.text)

            if verbose:
                print(f"[TranceSQL] Generated SQL: {sql_query}")

            attempt_record = {
                "attempt": attempt,
                "sql_generated": sql_query,
                "timestamp": datetime.now().isoformat(),
            }

            try:
                columns, results = exec_callback(sql_query)

                # ── Phase 3: Value Auto-Sampling on empty results ──
                if (
                    self.enable_value_sampling
                    and len(results) == 0
                    and attempt < max_retries
                    and not value_sample_triggered
                ):
                    value_sample_triggered = True
                    filters = self._extract_string_filters(sql_query)
                    sample_hints = []

                    for col, val in filters:
                        samples = self._sample_column_values(col, exec_callback, active_schema)
                        if samples:
                            sample_hints.append(
                                f"  Column '{col}': actual stored values are {samples}"
                            )

                    if sample_hints and verbose:
                        print("[TranceSQL] Empty result — auto-sampling column values...")

                    if sample_hints:
                        attempt_record["success"] = False
                        attempt_record["empty_result_correction"] = True
                        attempts_log.append(attempt_record)
                        message = (
                            f"Your query executed without error but returned 0 rows. "
                            f"The string filter values may not match what is actually stored. "
                            f"Here are the actual sampled values from the database:\n"
                            + "\n".join(sample_hints)
                            + "\n\nPlease correct the filter values and output ONLY the fixed SQL query."
                        )
                        continue

                if verbose:
                    print("[TranceSQL] Execution succeeded!")

                attempt_record["success"] = True
                attempts_log.append(attempt_record)

                final_result = {
                    "session_id": session_id,
                    "success": True,
                    "sql": sql_query,
                    "columns": list(columns),
                    "results": list(results),
                    "attempts": attempt,
                    "schema_linked": schema_linked,
                    "execution_time_seconds": round(time.time() - start_time, 3),
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
                        "schema_linked": schema_linked,
                        "execution_time_seconds": round(time.time() - start_time, 3),
                    }
                    break

                if verbose:
                    print("[TranceSQL] Initiating self-correction feedback loop...")

                message = (
                    f"Executing the generated query failed with the following database error:\n"
                    f"{error_msg}\n\n"
                    f"Please analyze the error, review the schema grounding, fix the query, "
                    f"and output ONLY the corrected SQL query without any formatting or markdown."
                )

        # Log telemetry
        telemetry_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "db_type": self.db_type,
            "knowledge_evidence_used": knowledge_evidence is not None,
            "schema_linked": schema_linked,
            "value_sample_triggered": value_sample_triggered,
            "success": final_result["success"],
            "final_sql": final_result.get("sql"),
            "attempts": final_result["attempts"],
            "execution_time": final_result["execution_time_seconds"],
            "attempts_history": attempts_log,
        }
        self._log_telemetry(telemetry_data)

        return final_result

    # ─── MANUAL FEEDBACK ─────────────────────────────────────────────────────

    def save_manual_feedback(self, session_id: str, rating: int, comment: str = None) -> bool:
        """
        Save manual user feedback for a given session to the telemetry log.

        :param session_id: Session ID returned by translate().
        :param rating: Integer rating 1–5.
        :param comment: Optional correction or comment.
        :return: True if successfully logged.
        """
        if not self.telemetry_log_path:
            return False

        feedback_record = {
            "type": "user_feedback",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "rating": rating,
            "comment": comment,
        }

        try:
            with open(self.telemetry_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(feedback_record) + "\n")
            return True
        except Exception as e:
            print(f"[TranceSQL Warning] Failed to log user feedback: {e}")
            return False
