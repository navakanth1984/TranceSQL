# TranceSQL Developer & Publishing Guide

This guide details how to set up the development environment, execute local tests, compile package wheels, and publish releases to TestPyPI and Production PyPI.

---

## 1. Setup Development Environment

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/navakanth1984/TranceSQL.git
    cd TranceSQL
    ```
2.  **Create a Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install Package in Editable Mode**:
    Installs the package locally, allowing you to edit the source code and run it immediately without reinstalling:
    ```bash
    pip install -e .
    pip install build twine dotenv
    ```

---

## 2. Running Local Unit Tests

We use a local SQLite test database to verify translation accuracy and error correction loops.

1.  Create your `.env` file in the root directory:
    ```text
    GEMINI_API_KEY=AIzaSy...
    ```
2.  Run the test suite:
    ```bash
    python tests/test_translator.py
    ```
3.  Ensure all test assertions pass and the log files are populated in `logs/telemetry_test.jsonl`.

---

## 3. Package Compilation & PyPI Releases

### Step A: Build the Package
Run the python build compiler in the root folder:
```bash
python -m build
```
This generates compiled distribution archives in a new `dist/` directory:
*   `dist/TranceSQL-0.1.0-py3-none-any.whl` (Wheel file)
*   `dist/TranceSQL-0.1.0.tar.gz` (Source distribution)

### Step B: Validate Package Description Format
```bash
twine check dist/*
```

### Step C: Upload to TestPyPI (Staging)
TestPyPI is a sandbox environment for testing uploads.
```bash
twine upload --repository testpypi dist/*
```
Verify that the package installs correctly from the test directory:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ TranceSQL
```

### Step D: Upload to PyPI (Production Release)
Publish the compiled package to the live production index:
```bash
twine upload dist/*
```
*Note: Once published, the library is available globally to anyone running `pip install TranceSQL`.*

---

## 4. Git Tagging

When publishing a new release, tag the matching commit in Git:
```bash
git tag -a v0.1.0 -m "Tag release version 0.1.0"
git push origin v0.1.0
```
