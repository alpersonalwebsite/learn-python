# ✅ Safe Setup for Simple Python Apps

## 1. Use a Virtual Environment

Create and activate a virtual environment to isolate dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Keep `.venv/` in `.gitignore`.

### Pinning, and why `pip freeze` is the wrong tool for it

`pip freeze > requirements.txt` is the usual advice and it produces a file you cannot maintain. It
writes out every package in the environment, direct and transitive alike, at whatever version happens
to be installed, with no record of which ones you actually asked for. A month later there is no way to
tell `requests` (you chose it) from `urllib3` and `certifi` (it chose them), so you cannot upgrade one
thing without re-freezing everything, and if you ever installed something to try it out and did not
uninstall it, it is now a dependency.

Keep the two files apart instead:

`requirements.in`, hand-written, holding only what you actually asked for:

```text
requests>=2.31,<3
python-dotenv>=1.0,<2
```

Then generate the fully-pinned `requirements.txt` from it, and commit both:

```bash
pip install pip-tools
pip-compile requirements.in   # writes requirements.txt, pinning transitives and noting why each is there
pip-sync                      # makes the venv match it exactly, removing what is no longer listed
```

`pip-sync` is the part `pip install -r` cannot do: it *removes* packages that are no longer listed, so
the environment matches the file rather than being a superset of it.

If you would rather not add a tool, `pip freeze` is still better than nothing, and the discipline that
makes it survivable is to never edit the generated file by hand and to keep a separate note of what you
chose deliberately.

#### `.gitignore` suggestion:
```bash
# .gitignore

# Virtual environments. Both spellings, because tooling disagrees about the dot: `python -m venv`
# takes whatever name you give it and the two common ones are these.
.venv/
venv/

# Bytecode and caches.
__pycache__/
*.py[cod]

# Logs. The directory too, not just the extension, so a rotated `app.log.2024-01-01` is covered.
*.log
logs/

# Secrets. BOTH globs, because neither implies the other: `.env*` is a prefix glob and misses
# `audit.env`, while `*.env` is a suffix glob and misses `.env.local`. Verified with
# `git check-ignore` rather than by reading, which is what `make check` does on this very block.
.env*
*.env

# ...but the template is meant to be committed, and `.env*` above would have swallowed it. A
# negation has to come after the pattern it re-includes.
!.env.example

# Key material and credentials.
secrets/
credentials*
*.pem
*.key
id_rsa*

# Local databases and editor or OS noise.
*.sqlite3
*.db
.DS_Store
```

---

## 2. Structured Logging

- Logs should go to both stdout and file.
- Store logs in a dedicated `logs/` directory.
- Rotate logs or delete those older than 14 days.

That last point is the one an example has to actually implement, and `logging.FileHandler` does not:
it is a `StreamHandler` subclass with no `doRollover` method, so it appends to one file forever.
`TimedRotatingFileHandler` is the one that rotates, and its `backupCount` is also how you get the
14 days, so a single handler satisfies both halves of the bullet above.

```python
import logging
import logging.handlers
import pathlib

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        # A new file at midnight, keeping 14, which IS the "older than 14 days" rule rather than
        # something you have to remember to prune separately.
        logging.handlers.TimedRotatingFileHandler(
            LOG_DIR / "app.log", when="midnight", backupCount=14, encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)
```

Two things that are easy to get wrong here. `logging.handlers` needs its own import: `import logging`
alone does not bring it in. And `basicConfig` does nothing at all if the root logger already has
handlers, so call it once, early, before anything else logs.

Rotated files are named `app.log.2026-08-22`, so a `*.log` line in `.gitignore` does not match them.
That is why the block in section 1 ignores `logs/` as well as the extension.

---

## 3. Prevent Concurrent Execution

The obvious pattern for this does not work, and it is worth seeing why before seeing the fix.

```python
# DO NOT USE THIS. Kept here because it is what everyone writes first. It is not marked as a
# fragment: it parses, so it is checked like any other block, and an exemption that changes nothing
# is an exemption that could quietly cover a real defect later.
if os.path.exists(LOCK_FILE):
    logging.warning("Another instance is already running. Exiting.")
    sys.exit(0)
open(LOCK_FILE, "w").close()
```

There is a gap between the check and the create, and two processes that arrive inside that gap both
see no lock and both proceed. Three processes started at once, against exactly the code above:

```text
pid 30201 ENTERED THE CRITICAL SECTION
pid 30202 ENTERED THE CRITICAL SECTION
pid 30203 ENTERED THE CRITICAL SECTION
```

All three. And the usual advice to remove the lock in a `finally` block makes it worse rather than
better: two of those three then died on the way out, because a sibling had already deleted the file
they were about to delete.

```text
FileNotFoundError: [Errno 2] No such file or directory: 'script_running.lock'
```

There is a third failure that has nothing to do with the race. If the process is killed with
`SIGKILL`, or the machine loses power, `finally` never runs and the lock file survives. Every later
run then sees it, logs a warning, and calls `sys.exit(0)`, which is a SUCCESS exit code. So cron or
systemd records a clean run, forever, while nothing actually happens. Of the three failure modes this
is the one most likely to bite, and the hardest to notice.

### Use flock, which the kernel releases for you

```python
import fcntl
import os
import sys

LOCK_FILE = "script_running.lock"

handle = open(LOCK_FILE, "w")

try:
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print(f"another instance holds {LOCK_FILE}, exiting", file=sys.stderr)
    sys.exit(1)

# Keep `handle` referenced for as long as the lock should be held: if it is garbage collected the
# file closes and the lock goes with it.
handle.write(f"{os.getpid()}\n")
handle.flush()
```

`LOCK_EX | LOCK_NB` asks for the lock and gives up immediately rather than blocking, which is what a
scheduled job wants. Same three processes, and one gets in:

```text
pid 13567 ENTERED
pid 13566 refused: another instance holds the lock
pid 13568 refused: another instance holds the lock
```

The property that matters is what happens after a `SIGKILL`. Measured: the lock *file* is still on
disk afterwards, and the next run acquires the lock anyway, because the lock lives on the open file
descriptor and the kernel drops it when the process dies. There is no stale lock to clean up and no
`finally` block needed for correctness. That is the whole argument for `flock` over a PID file.

Note the exit code is `1`, not `0`. Refusing to run because another copy is running is not a
successful run, and a supervisor cannot tell the difference unless you say so.

### If you need a readable PID, create the file atomically

`flock` on a network filesystem is unreliable, and sometimes you genuinely want to look at the lock
and see who holds it. Then do the create atomically, so there is no gap to lose the race in:

```python
import os
import pathlib
import sys

LOCK_FILE = pathlib.Path("script_running.lock")


def holder_alive(path):
    """True unless the recorded PID is definitely gone."""
    try:
        pid = int(path.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return True  # unreadable: assume it is held rather than stealing it
    try:
        os.kill(pid, 0)  # signal 0 tests for existence without sending anything
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it exists, it just is not ours
    return True


def acquire(path):
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if holder_alive(path):
                return False
            path.unlink(missing_ok=True)  # stale, from a run that was killed
            continue
        os.write(fd, f"{os.getpid()}\n".encode())
        os.close(fd)
        return True
    return False


if not acquire(LOCK_FILE):
    print(f"another instance holds {LOCK_FILE}, exiting", file=sys.stderr)
    sys.exit(1)

try:
    ...  # the actual work
finally:
    LOCK_FILE.unlink(missing_ok=True)
```

`O_CREAT | O_EXCL` is one system call that both creates the file and fails if it already exists, so
there is no window. Measured on the same three processes: one entered, two refused. A stale file left
by a killed run is detected and cleared, so the next run proceeds.

Two honest caveats. `missing_ok=True` on the way out is what stops the `FileNotFoundError` the first
pattern produced. And PIDs get recycled, so `os.kill(pid, 0)` can find *a* process where the original
is long gone, which is a small chance of refusing to run for no reason. `flock` has neither problem,
which is why it is first.

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

### Graceful Exception Handling

Wrap your entry point so a crash is logged rather than only printed:

```python
import logging
import sys

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # No `as e`: logging.exception already records the active exception with its traceback, and
        # binding a name you never read is the kind of thing a linter flags (flake8 F841).
        logging.exception("Unhandled exception")
        sys.exit(1)
```

`except Exception` and not `except BaseException` or a bare `except:`, deliberately. The bare form also
catches `KeyboardInterrupt` and `SystemExit`, so Ctrl-C gets logged as an unhandled error and any
`sys.exit()` deeper in the program is swallowed and turned into exit code 1.

This only works if logging is already configured. If `basicConfig` has not run by the time the
exception fires, the message goes to the last-resort handler on stderr with no timestamp and never
reaches the file, so configure logging as the first thing `main()` does, or before it.

---

## 7. File Permissions (Optional)

If handling secrets or running on shared systems, restrict file access:

```bash
chmod -R 700 logs/
```

For files your own code creates, set the mode AT creation rather than with a `chmod` afterwards. A
`chmod` leaves a window in which the file exists with the default mode, and on a shared machine that
window is the whole problem. The lock in section 3 does this already, with the `0o600` argument to
`os.open`, which is why it is not in the list above.

`open()` has no mode parameter, so when it matters, go through `os.open`:

```python
import os

fd = os.open("state.json", os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as handle:
    handle.write("{}")
```

The mode is also masked by the process umask, so `0o600` is a ceiling rather than a guarantee. Verify
with `ls -l` on the machine that will actually run it rather than assuming.

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

Use a `.env` file to keep secrets and configs out of source code. It is ignored by the block in
section 1; `.env.example` is not, and is the only place the required keys are written down.

1. Install `python-dotenv`:
```bash
pip install python-dotenv
```

2. At the top of your script:
```python
import os
import sys

from dotenv import load_dotenv

# load_dotenv() returns False when it found no file, and does not raise. Measured: False with no
# file present, True when it loaded one. Ignoring that return is how a deployment ends up running
# with no configuration at all and no error to show for it.
if not load_dotenv():
    print("no .env file found, relying on the real environment", file=sys.stderr)
```

3. Read REQUIRED values with `os.environ`, not `os.getenv`:

```python
import os

token = os.environ["API_TOKEN"]           # KeyError, immediately, naming the key
maybe = os.getenv("API_TOKEN")            # None, and the failure surfaces somewhere else entirely
timeout = int(os.getenv("TIMEOUT", "30")) # getenv is right when there IS a sensible default
```

That distinction is the whole point. A missing secret should stop the program where the mistake is,
not turn into a `None` that travels three functions before failing as something unrelated. Combined
with the handler in section 6, a `KeyError` here is logged with a traceback naming the variable.

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

## 14. Running External Commands

Pass a list, never a string with `shell=True`. With the shell involved, anything in the interpolated
value is shell syntax, and a filename is enough to get code executed. Measured, with `name` set to
`report.txt; echo INJECTED`:

```python
import subprocess

# WRONG. Measured output: "listing report.txt" then "INJECTED" on the next line.
subprocess.run(f"echo listing {name}", shell=True)

# Right. Measured output: "listing report.txt; echo INJECTED" -- one argument, nothing executed.
subprocess.run(["echo", "listing", name])
```

The list form is not an escaping trick, it skips the shell entirely: the value becomes one `argv` entry
and there is no parser left to abuse. You give up shell features (pipes, globs, `&&`) and that is the
point. When you genuinely need a pipe, build it from two `subprocess` calls rather than reaching for
`shell=True`.

Then check the result, because by default nothing tells you it failed:

```python
import subprocess

# `false` exits 1. Without check=True this raises nothing and returncode is simply ignored if
# you do not look at it, so a failed step reads as a successful run.
result = subprocess.run(["false"], capture_output=True, text=True)
print(result.returncode)  # 1, and no exception

# With check=True the same call raises CalledProcessError, which the section 6 handler will log.
subprocess.run(["false"], check=True, capture_output=True, text=True)
```

Use `check=True` unless you are deliberately handling a non-zero exit, and add `timeout=` for anything
that talks to a network, so a hung command fails the run instead of hanging it forever.

---

## 15. File Paths

Two things bite here, and both are quiet.

**An absolute second component throws the first away.** This is documented behaviour rather than a bug,
and it means a configuration value you expected to be relative can escape the directory you joined it
to. Measured:

```python
import os
import pathlib

os.path.join("/srv/app/data", "/etc/passwd")      # -> '/etc/passwd'
pathlib.Path("/srv/app/data") / "/etc/passwd"     # -> PosixPath('/etc/passwd')
```

**`..` walks out.** So if any part of a path comes from a config file, a CLI argument or a filename you
did not create, resolve it and check it is still where you meant:

```python
import pathlib

BASE = pathlib.Path("/srv/app/data").resolve()


def safe_path(candidate):
    """Resolve `candidate` under BASE, or refuse it."""
    resolved = (BASE / candidate).resolve()
    if not resolved.is_relative_to(BASE):      # Python 3.9+
        raise ValueError(f"path escapes {BASE}: {candidate!r}")
    return resolved
```

Measured against that function, with `BASE` as `/srv/app/data`:

```text
report.txt          -> /srv/app/data/report.txt    accepted
sub/../report.txt   -> /srv/app/data/report.txt    accepted, and correctly so
../../etc/passwd    -> /srv/etc/passwd             REFUSED
/etc/passwd         -> /private/etc/passwd         REFUSED
```

`resolve()` before comparing, not after, and it matters for a reason the last row shows: on macOS
`/etc` is a symlink to `/private/etc`, so a string comparison against the unresolved path would have
compared the wrong thing. `is_relative_to` needs Python 3.9 or newer; before that, compare
`os.path.commonpath([resolved, BASE]) == str(BASE)` rather than using `str.startswith`, which treats
`/srv/app/data-other` as being inside `/srv/app/data`.

---

## 16. Recommended Project Structure

```text
my_app/
├── main.py
├── classes/
│   └── data_handler.py
├── logs/                  # rotated by section 2, ignored by section 1
├── tests/
│   └── test_main.py
├── requirements.in        # what you asked for, hand-written
├── requirements.txt       # generated from it, fully pinned, committed
├── .env                   # NOT committed: section 1 ignores it
├── .env.example           # committed, and the negation in section 1 keeps it that way
├── .gitignore
└── README.md
```

The two `.env` entries are the point of the negation in section 1. The real one holds secrets and must
never be committed; the example holds the same keys with empty or dummy values and is the only
documentation of what the real one needs.