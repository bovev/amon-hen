#!/usr/bin/env python3
"""The only verification command in this repository.

    py scripts/verify.py

This file is just the runner. The checks live in ``scripts/checks/``: each
module declares an ``ORDER`` and defines ``check_*`` functions, which are
discovered and run in module order. Adding a check means adding a file — this
runner never changes, and two tasks adding checks never touch the same lines.

Agents must not invent lint, format, schema or build commands — if a check is
worth running, add it to a module under ``scripts/checks/``.

Runtime verification (docker compose up, restarting Grafana, querying
Prometheus targets) happens on the Ubuntu deployment server and is
deliberately out of scope here. Missing files are reported as SKIP so that
early tasks pass before later tasks create them.

Exit code 0 = no failures, 1 = at least one FAIL.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys

import checks
from checks.common import RESULTS, fail


def discover():
    """Every check_* function under scripts/checks/, in a stable order.

    Modules sort by their ORDER attribute, then by name; functions within a
    module keep their definition order, so output stays readable and diffs of
    the output stay small.
    """
    found = []
    for info in pkgutil.iter_modules(checks.__path__):
        if info.name == "common" or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"checks.{info.name}")
        order = getattr(module, "ORDER", 999)
        for name, obj in vars(module).items():
            # __module__ filters out check functions imported from elsewhere,
            # so a shared helper is never run twice.
            if not name.startswith("check_") or not callable(obj):
                continue
            if getattr(obj, "__module__", None) != module.__name__:
                continue
            found.append((order, info.name, obj.__code__.co_firstlineno, obj))

    found.sort(key=lambda item: item[:3])
    return [(module_name, func) for _, module_name, _, func in found]


def main() -> int:
    discovered = discover()
    if not discovered:
        print("FAIL  no checks found under scripts/checks/")
        return 1

    for module_name, check in discovered:
        try:
            check()
        except Exception as exc:  # a broken check must not look like a clean run
            fail(f"{module_name}.{check.__name__}", f"check crashed: {exc!r}")

    width = max(len(name) for _, name, _ in RESULTS)
    for status, name, detail in RESULTS:
        print(f"{status}  {name.ljust(width)}  {detail}")

    failures = [r for r in RESULTS if r[0] == "FAIL"]
    print()
    if failures:
        print(f"FAILED - {len(failures)} check(s) need fixing")
        return 1
    skipped = sum(1 for r in RESULTS if r[0] == "SKIP")
    print(f"OK - {len(RESULTS) - skipped} check(s) passed, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
