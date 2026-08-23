# Learn Python

Notes on setting a small Python application up so it does not surprise you later. One document at the
moment, [Safe Setup for Simple Python Apps](./safe-setup-simple-apps.md), which is a checklist rather
than a tutorial: it assumes you can already write the program and is about everything around it, the
parts that only announce themselves at 3am.

It is opinionated where the obvious answer is wrong. Three of its sections exist because the pattern
everyone reaches for first does not work, and each of those says what actually happens rather than
just what to do instead:

- **[Preventing concurrent runs](./safe-setup-simple-apps.md#3-prevent-concurrent-execution)** with a
  lock file. Checking whether the file exists and then creating it is a race, and the usual advice to
  clean up in a `finally` block turns that race into a crash. Measured: three processes started at
  once all entered the critical section, and two of them died on the way out deleting a file a sibling
  had already deleted.
- **[Rotating logs](./safe-setup-simple-apps.md#2-structured-logging)**. `logging.FileHandler` never
  rotates anything, so "keep 14 days" and that handler are not the same instruction.
- **[Joining paths](./safe-setup-simple-apps.md#15-file-paths)**. An absolute second component throws
  the first away, so `os.path.join("/srv/app/data", "/etc/passwd")` is `/etc/passwd`, and a config
  value you assumed was relative is not.

## Checking the advice

The checks here verify the advice, not just its syntax, which for a document like this is the only
thing worth automating:

```bash
make check              # all three
make check-samples      # ast.parse every python block, bash -n every shell block
make check-gitignore    # the RECOMMENDED .gitignore, applied and tested with git check-ignore
make check-links        # every relative link and #anchor resolves
```

The middle one is the interesting one. It lifts the `.gitignore` block out of the document, writes it
into a throwaway git repository, and asks git whether it ignores 21 things a Python project must never
commit and leaves 6 things committable. That second list is what stops a `.gitignore` of `*` from
passing. Run against the first version of this document it reported 13 problems, including one nobody
had noticed: `.env.*` ignores `.env.example`, which is the file you are supposed to commit.

It also checks this repository's own `.gitignore` against the same lists, because a document that
recommends a `.gitignore` and does not use one is advice nobody has tried.

No dependencies, no virtualenv, no network. Standard library and git, which is the same reasoning the
checklist itself applies to a small app.

## Contents

- [1. Use a Virtual Environment](./safe-setup-simple-apps.md#1-use-a-virtual-environment)
    - [Pinning, and why `pip freeze` is the wrong tool for it](./safe-setup-simple-apps.md#pinning-and-why-pip-freeze-is-the-wrong-tool-for-it)
- [2. Structured Logging](./safe-setup-simple-apps.md#2-structured-logging)
- [3. Prevent Concurrent Execution](./safe-setup-simple-apps.md#3-prevent-concurrent-execution)
    - [Use flock, which the kernel releases for you](./safe-setup-simple-apps.md#use-flock-which-the-kernel-releases-for-you)
    - [If you need a readable PID, create the file atomically](./safe-setup-simple-apps.md#if-you-need-a-readable-pid-create-the-file-atomically)
- [4. Configuration and State Files](./safe-setup-simple-apps.md#4-configuration-and-state-files)
- [5. Dry Run Mode](./safe-setup-simple-apps.md#5-dry-run-mode)
- [6. Command-Line Argument Handling](./safe-setup-simple-apps.md#6-command-line-argument-handling)
    - [Graceful Exception Handling](./safe-setup-simple-apps.md#graceful-exception-handling)
- [7. File Permissions (Optional)](./safe-setup-simple-apps.md#7-file-permissions-optional)
- [8. Project Structure](./safe-setup-simple-apps.md#8-project-structure)
- [9. README.md](./safe-setup-simple-apps.md#9-readmemd)
- [10. Dependency Auditing](./safe-setup-simple-apps.md#10-dependency-auditing)
- [11. Environment Variables and `.env` Support](./safe-setup-simple-apps.md#11-environment-variables-and-env-support)
- [12. Testing](./safe-setup-simple-apps.md#12-testing)
- [13. CLI Usage Examples](./safe-setup-simple-apps.md#13-cli-usage-examples)
- [14. Running External Commands](./safe-setup-simple-apps.md#14-running-external-commands)
- [15. File Paths](./safe-setup-simple-apps.md#15-file-paths)
- [16. Recommended Project Structure](./safe-setup-simple-apps.md#16-recommended-project-structure)
