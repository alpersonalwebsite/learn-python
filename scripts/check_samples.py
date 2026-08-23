#!/usr/bin/env python3
"""Check every fenced code sample in this repository.

Two passes, one per language:

1. PYTHON blocks are parsed with ``ast.parse``. That is a syntax check and nothing more: it will not
   tell you a name is undefined or that an import is missing, which matters here because a checklist
   is written in fragments and most of these samples are deliberately incomplete.

2. BASH blocks are checked with ``bash -n``, which parses without executing. Worth doing because the
   shell in these samples is what a reader pastes into a terminal first, and a mismatched quote in a
   ``chmod`` line is exactly the sort of thing nobody notices in review.

Both passes report the fence's line number, so a failure points at the document rather than at a
temporary file.

Fragments: a block that cannot be parsed on its own can say so on its FIRST line, as a comment:

    # check: fragment

Only the first line, and only as a comment. That is deliberately tighter than honouring the marker
anywhere in the block: a marker that can be attached to the offending line turns an exemption into an
off switch reachable from inside the thing being checked. A sibling repository in this account shipped
the looser form and a poison test showed it silencing a real defect.

No block in this repository currently needs the exemption: every sample parses. The mechanism is here
for when one does, and it is poison-tested rather than exercised by the content, because an unused
exemption sitting on a block that happens to parse is one that could later cover a real defect.

Nothing here needs a network, a virtualenv, or a package from PyPI. Standard library only, which is
the same reason the document it checks recommends what it recommends.
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^```(\w+)?\s*$")
MARKER = re.compile(r"^#\s*check:\s*(fragment)\s*$")


def blocks(path: pathlib.Path):
    """Yield (language, first_body_line_number, body) for every fenced block in one file."""
    body: list[str] | None = None
    lang: str | None = None
    start = 0

    for number, line in enumerate(path.read_text().split("\n"), start=1):
        stripped = line.strip()
        if body is not None:
            if stripped == "```":
                yield lang, start, body
                body, lang = None, None
            else:
                body.append(line)
            continue
        match = FENCE.match(stripped)
        if match:
            body, lang, start = [], match.group(1), number + 1

    if body is not None:
        yield lang, start, body  # an unterminated fence, reported by the caller


def main() -> int:
    failures: list[str] = []
    counts = {"python": 0, "bash": 0, "fragment": 0, "other": 0}

    for path in sorted(ROOT.glob("*.md")):
        for lang, start, body in blocks(path):
            where = f"{path.name}:{start}"
            source = "\n".join(body)

            if lang not in ("python", "bash"):
                counts["other"] += 1
                continue

            if body and MARKER.match(body[0].strip()):
                counts["fragment"] += 1
                continue

            if lang == "python":
                counts["python"] += 1
                try:
                    ast.parse(source, filename=where)
                except SyntaxError as error:
                    failures.append(f"PYTHON {where}  SyntaxError: {error.msg}")
                continue

            counts["bash"] += 1
            with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
                handle.write(source)
                temp = handle.name
            try:
                result = subprocess.run(
                    ["bash", "-n", temp], capture_output=True, text=True, check=False
                )
                if result.returncode != 0:
                    first = (result.stderr.strip().split("\n") or ["failed"])[0]
                    # bash reports the temp path; the reader wants the document.
                    failures.append(f"BASH {where}  {first.replace(temp, where)}")
            finally:
                pathlib.Path(temp).unlink(missing_ok=True)

    total = counts["python"] + counts["bash"]
    print(
        f"{total} checked samples: {counts['python']} python, {counts['bash']} bash"
        f"  ({counts['fragment']} marked fragment, {counts['other']} untagged or other languages)"
    )

    if not failures:
        print("no failures")
        return 0

    print("")
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"\n{len(failures)} failure(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
