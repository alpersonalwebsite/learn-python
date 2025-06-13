# ✅ Safe Setup for Simple Python Apps

## 1. Use a Virtual Environment

Create and activate a virtual environment to isolate dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Keep `.venv/` in `.gitignore`.

Update dependencies:
```bash
pip freeze > requirements.txt
```

#### `.gitignore` suggestion:
```bash
# .gitignore
.venv/
__pycache__/
*.py[cod]
*.log
.env
.env.*
```

---

## 2. Structured Logging

- Logs should go to both stdout and file.
- Store logs in a dedicated `logs/` directory.
- Rotate logs or delete those older than 14 days.

Example:
```python
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
```

---

## 3. Prevent Concurrent Execution

Use a lock file (e.g., `script_running.lock`) to prevent overlapping runs:

```python
if os.path.exists(LOCK_FILE):
    logging.warning("Another instance is already running. Exiting.")
    sys.exit(0)
```

Ensure lock file is removed in a `finally` block.

---

## 4. Configuration and State Files

- Use JSON for `mappings.json`, `schedules.json`, `last_run.json`.
- Validate file content before use.
- Optionally back up state files before modifying.

---

## 5. Dry Run Mode

Implement a `--dry-run` mode to simulate actions safely:

```python
if dry_run:
    logging.info("[DRY RUN] Would execute...")
```

💡 Ensure your dry run avoids any irreversible actions like file writes or uploads. Log what would happen instead.

---

## 6. Command-Line Argument Handling

Prefer `argparse` for extensible CLI flags:

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()
```

---

## 6.1 Graceful Exception Handling

Wrap your entry point in a `try`/`except` block to prevent silent crashes:

```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("Unhandled exception")
        sys.exit(1)
```

---

## 7. File Permissions (Optional)

If handling secrets or running on shared systems, restrict file access:

```bash
chmod 600 script_running.lock
chmod -R 700 logs/
```

---

## 8. Project Structure

Keep the project modular:
- `main.py` should orchestrate logic.
- Move helpers and utilities to `classes/`, `lib/`, or `utils/`.

---

## 9. README.md

Include setup, usage, and purpose of each config file.

---

## 10. Dependency Auditing

Keep your environment secure by auditing dependencies:

```bash
pip install pip-audit
pip-audit
```

Also keep pip up to date:
```bash
python -m pip install --upgrade pip
```

---

## 11. Environment Variables and `.env` Support

Use a `.env` file to keep secrets and configs out of source code:

1. Install `python-dotenv`:
```bash
pip install python-dotenv
```

2. At the top of your script:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 12. Testing

Use `unittest` or `pytest`:

```bash
pip install pytest
pytest
```

Place tests in a dedicated folder like `tests/`.

---

## 13. CLI Usage Examples

```bash
# Simulate a run
python main.py --dry-run

# Run with a config
python main.py --config config.json
```

---

## 14. Recommended Project Structure

```text
my_app/
├── main.py
├── classes/
│   └── data_handler.py
├── logs/
├── tests/
│   └── test_main.py
├── .env
├── .gitignore
└── README.md
```