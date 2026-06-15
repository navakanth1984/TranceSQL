# Contributing to TranceSQL

Thank you for your interest in contributing to TranceSQL! We welcome all contributions, from bug reports and documentation fixes to major new features.

---

## 🚀 Setting Up the Development Environment

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/navakanth1984/TranceSQL.git
    cd TranceSQL
    ```
2.  **Create a Virtual Environment**:
    We recommend using Python 3.9 or higher:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install Dependencies & Package**:
    Install the package in editable mode along with testing requirements:
    ```bash
    pip install -e .
    pip install build twine dotenv
    ```
4.  **Configure API Key**:
    Copy `.env.example` to `.env` and insert your Google AI Studio API key:
    ```bash
    cp .env.example .env
    ```

---

## 🧪 Running Unit Tests

Before submitting a Pull Request, please ensure all local tests pass:

```bash
python tests/test_translator.py
```

Ensure `logs/telemetry_test.jsonl` is populated and no assertions fail.

---

## 📚 Writing Documentation

Our documentation is powered by **MkDocs** and the **material** theme.

1.  Install documentation dependencies:
    ```bash
    pip install mkdocs mkdocs-material
    ```
2.  Run the local development server:
    ```bash
    mkdocs serve
    ```
    Open `http://127.0.0.1:8000` in your browser to view live edits.

---

## 📬 Pull Request Process

1.  Create a feature branch from `main` (e.g. `feat/self-correction-tuning`).
2.  Make your changes, keeping coding style clean and adhering to **Karpathy development mandates** (explicit > clever).
3.  Write tests verifying the fix or feature.
4.  Submit a Pull Request targeting `main`. Describe the changes clearly and link any related issues.
