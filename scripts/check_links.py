#!/usr/bin/env python3
"""Resolve every relative markdown link and #anchor in this repository.

A broken anchor is a silent failure: GitHub serves the page with a 200 and ignores the fragment, so
the reader lands at the top of the document with nothing telling them the link was wrong. Nothing but
a mechanical pass finds one.

THE SLUG RULES ARE VERIFIED AGAINST GITHUB, NOT GUESSED. All 23 headings in this repository were
POSTed to GitHub's own markdown renderer (``gh api --method POST /markdown``) and the
``id="user-content-..."`` values it generated were compared against what ``slug`` produces. The
comparison aborts rather than reporting success when the two lists cannot be aligned, because a zip
over an empty response is how a verification passes vacuously, and that abort has already fired once
here for a real reason: a stale token gave HTTP 401 and returned no ids at all.

That run found a rule worth pinning. GitHub does NOT trim whitespace before turning spaces into
hyphens, so a heading beginning with a character that gets deleted keeps the space it leaves behind:

    "\u2705 Safe Setup for Simple Python Apps"  ->  -safe-setup-for-simple-python-apps

with a LEADING HYPHEN. An implementation that strips first produces
``safe-setup-for-simple-python-apps``, which resolves to nothing. This only shows up when a heading
starts with an emoji or similar, which is exactly what the top of the checklist does.

Standard library only, and offline: the GitHub comparison was a one-off verification, not a runtime
dependency, because a checker that needs the network is one that stops being run.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^```")
HEADING = re.compile(r"^#{1,6} +(.*)$")
LINK = re.compile(r"\]\(([^)\s]+)\)")
ABSOLUTE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def slug(heading: str) -> str:
    """GitHub's heading-to-anchor rule, as measured rather than as assumed."""
    text = heading.replace("`", "")
    # Link text inside a heading: keep the text, drop the target.
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.lower()
    text = re.sub(r"[^\w \-]", "", text, flags=re.UNICODE)
    # NO .strip() here. See the module docstring: GitHub keeps the space a deleted leading character
    # leaves behind, and turns it into a hyphen.
    return text.replace(" ", "-")


# Pinned against GitHub's renderer. If slug() drifts, this fails loudly rather than emitting a file
# full of plausible wrong anchors.
SLUG_CASES = [
    ("\u2705 Safe Setup for Simple Python Apps", "-safe-setup-for-simple-python-apps"),
    ("1. Use a Virtual Environment", "1-use-a-virtual-environment"),
    ("7. File Permissions (Optional)", "7-file-permissions-optional"),
    ("9. README.md", "9-readmemd"),
    ("11. Environment Variables and `.env` Support", "11-environment-variables-and-env-support"),
    ("Pinning, and why `pip freeze` is the wrong tool for it",
     "pinning-and-why-pip-freeze-is-the-wrong-tool-for-it"),
]


def anchors_and_links():
    anchors: dict[str, set[str]] = {}
    links: list[tuple[str, int, str]] = []

    for path in sorted(ROOT.glob("*.md")):
        seen: dict[str, int] = {}
        found: set[str] = set()
        in_fence = False

        for number, line in enumerate(path.read_text().split("\n"), start=1):
            if FENCE.match(line.strip()):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            heading = HEADING.match(line)
            if heading:
                base = slug(heading.group(1))
                count = seen.get(base, 0)
                seen[base] = count + 1
                # GitHub appends -1, -2 to repeats within one document.
                found.add(base if count == 0 else f"{base}-{count}")

            for target in LINK.findall(line):
                if ABSOLUTE.match(target) or target.startswith("//"):
                    continue
                links.append((path.name, number, target))

        anchors[path.name] = found

    return anchors, links


def main() -> int:
    for heading, expected in SLUG_CASES:
        got = slug(heading)
        if got != expected:
            print(
                f"slug() self-check failed: {heading!r} -> {got!r}, expected {expected!r}",
                file=sys.stderr,
            )
            return 1

    anchors, links = anchors_and_links()
    problems: list[str] = []

    for source, number, target in links:
        path, _, fragment = target.partition("#")
        resolved = source if path == "" else str((ROOT / path).resolve().relative_to(ROOT))

        if path != "":
            if not (ROOT / path).exists():
                problems.append(f"{source}:{number}  {target}\n      no such file: {path}")
                continue
            if resolved not in anchors and fragment:
                problems.append(
                    f"{source}:{number}  {target}\n      {path} is not markdown, so #{fragment} cannot resolve"
                )
                continue

        if fragment and fragment not in anchors.get(resolved, set()):
            problems.append(
                f"{source}:{number}  {target}\n      no heading in {resolved} with anchor #{fragment}"
            )

    print(f"{len(links)} relative links across {len(anchors)} files")
    sys.stdout.flush()

    if not problems:
        print("all resolve")
        return 0

    print("")
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    print(f"\n{len(problems)} broken link(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
