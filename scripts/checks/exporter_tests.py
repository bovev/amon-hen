"""Runs the Phase 2 exporter's pytest suite and reports it as a single check.

This is the bridge between the two verification worlds. Assertions about files
live in this package; assertions about code are unit tests and live in pytest.
Rather than becoming a second command an agent has to run - which would mean
allowing `py -m ...`, and that is equally how packages get installed and
servers get started - pytest is invoked here and folded into the same table as
every other check.

pytest runs in its own process on purpose. Importing it would let assertion
rewriting, plugin loading and sys.path edits reach the invariant checks, and
those are exactly the checks that must survive a broken exporter.

Not a task module: `local-coder` cannot edit this file. It decides whether test
failures count, and a role that can rewrite how its own tests are graded does
not have tests.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

from .common import ROOT, detail_block, fail, ok, rel, skip

ORDER = 80  # last - the only check that costs more than a few milliseconds

TESTS = ROOT / "monitoring" / "exporters" / "gpu" / "tests"

TIMEOUT = 300

# pytest's documented exit codes. 5 is the treacherous one: an empty or
# mis-pathed suite exits "successfully" having asserted nothing.
NO_TESTS_COLLECTED = 5


def check_exporter_tests() -> None:
    """AGENTS.md: the GPU exporter's unit tests, run through the one command."""
    if not TESTS.is_dir():
        skip("exporter tests", "Phase 2 not started")
        return

    # A missing pytest is a skip, not a failure - but the subprocess cannot tell
    # us that, because sys.executable exists and would exit 1 with "No module
    # named pytest", which is indistinguishable from a failing suite.
    if importlib.util.find_spec("pytest") is None:
        skip("exporter tests", "pytest is not installed for this interpreter")
        return

    # pytest rewrites assertions and would drop __pycache__ inside monitoring/,
    # where the line-ending and YAML checks sweep. Leave the tree as it found it.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    try:
        proc = subprocess.run(
            # -p no:cacheprovider keeps .pytest_cache out of the repository.
            [sys.executable, "-m", "pytest", str(TESTS), "-q", "-p", "no:cacheprovider"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=str(ROOT),
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        fail("exporter tests", f"could not run pytest: {exc!r}")
        return

    output = (proc.stdout or "") + (proc.stderr or "")
    lines = [line for line in output.strip().splitlines() if line.strip()]
    summary = lines[-1] if lines else f"pytest exited {proc.returncode} with no output"

    if proc.returncode == 0:
        ok("exporter tests", summary)
        return

    if proc.returncode == NO_TESTS_COLLECTED:
        # The directory exists, which is the assertion that tests exist in it.
        fail("exporter tests", f"{rel(TESTS)}/ exists but pytest collected no tests")
    else:
        fail("exporter tests", summary)

    # Every other check fits one line; a failing assertion does not. Queue the
    # detail so the runner prints it below the summary table, keeping the table
    # scannable and the verdict last.
    detail_block(
        "\n".join(
            [
                f"----- pytest output ({rel(TESTS)}) -----",
                output.rstrip() or "(no output)",
                "----- end pytest output -----",
            ]
        )
    )
