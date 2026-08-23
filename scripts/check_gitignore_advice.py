#!/usr/bin/env python3
"""Check that the .gitignore this document RECOMMENDS actually ignores what it should.

Every other check in this repository looks at whether a sample parses. This one looks at whether the
advice is correct, which is a different and more useful question for a document whose whole subject is
setting a project up safely. A .gitignore that reads plausibly and leaks is worse than no advice at
all, because the reader stops thinking about it.

How it works: the recommended block is extracted from the markdown, written into a throwaway git
repository, and every path below is put to ``git check-attr``'s sibling ``git check-ignore``. So the
authority is git itself rather than a reimplementation of its pattern rules, which is the part that is
easy to get wrong.

Measured on the version of this document before it was fixed: 13 problems. Twelve were absences and one
was the opposite, an OVER-ignore that this list's second half exists to catch: ``.env.*`` matches
``.env.example``, so the advice ignored the one file you are supposed to commit. The absences were
``venv/`` without the dot, ``.DS_Store``, and MISSED .envrc, the whole suffix form
(audit.env and production.env), every kind of key material, and local databases.

BOTH lists matter. MUST_IGNORE alone can be satisfied by a .gitignore containing a single ``*``, which
would pass while making the repository uncommittable, so MUST_NOT_IGNORE pins the other side.

Standard library only, and no network.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The document may recommend a .gitignore in any file; the block is identified by its first line
# being this comment. That is a contract with the document rather than a guess about its layout, and
# if the comment is renamed this script reports "no recommended block found" instead of passing.
BLOCK_MARKER = "# .gitignore"

# A Python project must never commit these.
MUST_IGNORE = [
    ".venv/pyvenv.cfg",
    "venv/pyvenv.cfg",
    # env/ and ENV/ were missing from this list AND from the recommendation, so the gap was invisible
    # to the check: a list of things to verify is an artifact that can be incomplete like any other,
    # and a checker cannot find what nobody thought to ask it about.
    "env/pyvenv.cfg",
    "ENV/pyvenv.cfg",
    "__pycache__/module.cpython-312.pyc",
    "module.pyc",
    "module.pyo",
    "app.log",
    "logs/app.log",
    ".env",
    ".env.local",
    ".env.production",
    ".envrc",
    "audit.env",
    "production.env",
    "secrets/api-key.txt",
    "credentials.json",
    "server.pem",
    "server.key",
    "id_rsa",
    "app.sqlite3",
    "app.db",
    ".DS_Store",
]

# ...and must still be able to commit these. Without this list a .gitignore of "*" would pass.
MUST_NOT_IGNORE = [
    "main.py",
    "requirements.txt",
    "README.md",
    "classes/data_handler.py",
    "tests/test_main.py",
    ".env.example",
]


def recommended_block() -> tuple[pathlib.Path, int, list[str]] | None:
    """Find the fenced block whose first line is BLOCK_MARKER."""
    for path in sorted(ROOT.glob("*.md")):
        body: list[str] | None = None
        start = 0
        for number, line in enumerate(path.read_text().split("\n"), start=1):
            stripped = line.strip()
            if body is not None:
                if stripped == "```":
                    if body and body[0].strip() == BLOCK_MARKER:
                        return path, start, body
                    body = None
                else:
                    body.append(line)
                continue
            if re.match(r"^```(\w+)?\s*$", stripped):
                body, start = [], number + 1
    return None


def main() -> int:
    found = recommended_block()
    if found is None:
        print(
            f"no recommended block found: expected a fenced block whose first line is "
            f"{BLOCK_MARKER!r}",
            file=sys.stderr,
        )
        return 2

    path, start, body = found
    problems: list[str] = []

    # This repository's OWN .gitignore is checked against the same lists. A document that recommends
    # a .gitignore and does not use one is advice nobody has tried, so the two are held to the same
    # standard and cannot drift apart.
    own = ROOT / ".gitignore"

    with tempfile.TemporaryDirectory() as directory:
        repo = pathlib.Path(directory)
        # Hermetic: a stray core.excludesFile in the caller's global config would otherwise decide
        # the verdict, which would make this pass or fail depending on who ran it.
        env = {"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo), "PATH": "/usr/bin:/bin:/usr/local/bin"}
        run = lambda *args: subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False, env=env
        )

        if run("init", "-q", ".").returncode != 0:
            print("could not create a temporary git repository", file=sys.stderr)
            return 2

        subjects = [("the recommendation", "\n".join(body) + "\n")]
        if own.exists():
            subjects.append(("this repo's own .gitignore", own.read_text()))
        else:
            problems.append(
                "this repository has no .gitignore of its own, while recommending one"
            )

        for label, content in subjects:
            (repo / ".gitignore").write_text(content)

            for candidate in MUST_IGNORE:
                if run("check-ignore", "-q", candidate).returncode != 0:
                    problems.append(f"{label}: NOT IGNORED but must be: {candidate}")

            for candidate in MUST_NOT_IGNORE:
                if run("check-ignore", "-q", candidate).returncode == 0:
                    problems.append(f"{label}: IGNORED but must be committable: {candidate}")

    print(
        f"recommended .gitignore at {path.name}:{start} ({len(body)} lines): "
        f"{len(MUST_IGNORE)} paths must be ignored, {len(MUST_NOT_IGNORE)} must not"
        f"\n  checked against both the recommendation and this repository's own .gitignore"
    )
    sys.stdout.flush()

    if not problems:
        print("the recommended block covers all of them")
        return 0

    print("")
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    print(f"\n{len(problems)} problem(s) with the RECOMMENDED .gitignore", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
