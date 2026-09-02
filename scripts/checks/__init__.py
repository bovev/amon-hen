"""Verification checks, discovered and run by scripts/verify.py.

Each module here declares an ``ORDER`` and defines ``check_*`` functions.
Adding a check means adding a file; the runner needs no edit.

Module naming carries meaning:

* ``task_NN_*.py`` — acceptance checks written for one task. They stay after the
  task is accepted, because that is when they start earning their keep as
  regression checks against later work.
* everything else — architectural invariants from AGENTS.md that apply to all
  work, forever.

`local-coder` may write the first kind and not the second.
"""
