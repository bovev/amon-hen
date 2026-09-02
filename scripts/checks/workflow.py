"""The workflow's own invariants: task state, agent frontmatter, agent policy.

These guard the process rather than the monitoring stack. `local-coder` cannot
write this file — it defines the rules the coder is held to.
"""

from __future__ import annotations

import re

from .common import fail, git, ok, parse_frontmatter, rel, skip, yaml, ROOT

ORDER = 70

# --------------------------------------------------------------------------
# Task state — the frontmatter of tasks/task-NN-*.md is the record of what is
# done. Commit subjects are prose and have been wrong; this is the state store,
# and only the orchestrator writes it.
# --------------------------------------------------------------------------

TASK_STATUSES = ("todo", "in-progress", "done")
TASK_KEYS = {"task", "status", "accepted_at"}
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def check_task_state() -> None:
    """AGENTS.md: task frontmatter records status; the sequence completes in order."""
    directory = ROOT / "tasks"
    files = sorted(directory.glob("task-*.md")) if directory.exists() else []
    if not files:
        skip("task state", "no task files")
        return

    problems = []
    entries = []

    for path in files:
        name = rel(path)
        match = re.match(r"task-(\d+)-", path.name)
        if not match:
            problems.append(f"{name}: filename must be task-NN-<slug>.md")
            continue

        meta, error = parse_frontmatter(path)
        if meta is None:
            problems.append(f"{name}: {error}")
            continue

        for key in meta:
            if key not in TASK_KEYS:
                problems.append(f"{name}: unknown frontmatter key {key!r}")

        number = int(match.group(1))
        if meta.get("task") != number:
            problems.append(f"{name}: 'task' must be {number}, got {meta.get('task')!r}")

        status = meta.get("status")
        if status not in TASK_STATUSES:
            problems.append(f"{name}: status must be {'|'.join(TASK_STATUSES)}, got {status!r}")
            continue

        accepted = meta.get("accepted_at")
        if status == "done":
            if not accepted:
                problems.append(f"{name}: status 'done' requires an 'accepted_at' commit")
            elif not SHA_RE.match(str(accepted)):
                problems.append(f"{name}: accepted_at {accepted!r} is not a commit sha")
        elif accepted:
            problems.append(f"{name}: only a 'done' task may set accepted_at (status {status!r})")

        entries.append((number, name, status, accepted))

    entries.sort()

    in_progress = [name for _, name, status, _ in entries if status == "in-progress"]
    if len(in_progress) > 1:
        problems.append("more than one task in-progress: " + ", ".join(in_progress))

    open_task = None
    for _, name, status, _ in entries:
        if status in ("todo", "in-progress") and open_task is None:
            open_task = name
        elif status == "done" and open_task is not None:
            problems.append(f"{name}: marked done but {open_task} before it is not")

    # Only meaningful inside a checkout; skipped silently elsewhere.
    if git("rev-parse", "--git-dir") == 0:
        for _, name, status, accepted in entries:
            if status != "done" or not accepted or not SHA_RE.match(str(accepted)):
                continue
            if git("cat-file", "-e", f"{accepted}^{{commit}}") != 0:
                problems.append(f"{name}: accepted_at {accepted} is not a commit in this repository")
            elif git("merge-base", "--is-ancestor", str(accepted), "HEAD") != 0:
                problems.append(f"{name}: accepted_at {accepted} is not an ancestor of HEAD")

    if problems:
        fail("task state", "; ".join(problems))
    else:
        done = sum(1 for _, _, status, _ in entries if status == "done")
        current = in_progress[0] if in_progress else "none"
        ok("task state", f"{done}/{len(entries)} done, in-progress: {current}")


# --------------------------------------------------------------------------
# Agent definitions — catches the frontmatter mistakes that silently disable
# an agent's permission rules.
# --------------------------------------------------------------------------

AGENT_TOP_LEVEL_KEYS = {
    "description",
    "mode",
    "model",
    "temperature",
    "top_p",
    "prompt",
    "tools",
    "permission",
    "disable",
    "color",
    "hidden",
    "steps",
    "variant",
    "options",
    "name",
}

PERMISSION_KEYS = {
    "bash",
    "edit",
    "read",
    "write",
    "task",
    "webfetch",
    "websearch",
    "external_directory",
    "question",
    "doom_loop",
}


def check_agents() -> None:
    directory = ROOT / ".opencode" / "agents"
    files = sorted(directory.glob("*.md")) if directory.exists() else []
    if not files:
        skip("agent frontmatter", "no agents defined")
        return

    problems = []
    for path in files:
        name = rel(path)
        lines = path.read_text(encoding="utf-8").split("\n")
        if not lines or lines[0].strip() != "---":
            problems.append(f"{name}: must start with a '---' frontmatter fence")
            continue

        try:
            end = next(i for i, line in enumerate(lines[1:], start=1) if line.rstrip() == "---")
        except StopIteration:
            stray = next(
                (line for line in lines[1:] if set(line.strip()) == {"-"} and line.strip()),
                None,
            )
            hint = f" (found {stray.strip()!r})" if stray else ""
            problems.append(f"{name}: frontmatter is not closed by a '---' line{hint}")
            continue

        try:
            meta = yaml.safe_load("\n".join(lines[1:end])) or {}
        except yaml.YAMLError as exc:
            problems.append(f"{name}: frontmatter does not parse: {exc}")
            continue

        for key in ("description", "mode", "model"):
            if not meta.get(key):
                problems.append(f"{name}: missing '{key}'")
        if meta.get("mode") not in (None, "primary", "subagent", "all"):
            problems.append(f"{name}: mode must be primary|subagent|all, got {meta['mode']!r}")

        for key in meta:
            if key in PERMISSION_KEYS and key not in AGENT_TOP_LEVEL_KEYS:
                problems.append(f"{name}: '{key}' is at the top level; nest it under 'permission:'")
            elif key not in AGENT_TOP_LEVEL_KEYS:
                problems.append(f"{name}: unknown frontmatter key {key!r}")

        permission = meta.get("permission")
        if permission is None:
            problems.append(f"{name}: no 'permission' block")
        elif not isinstance(permission, dict):
            problems.append(f"{name}: 'permission' must be a mapping")
        else:
            for key, rules in permission.items():
                if key not in PERMISSION_KEYS:
                    problems.append(f"{name}: unknown permission key {key!r}")
                if isinstance(rules, dict) and rules and next(iter(rules)) != "*":
                    problems.append(
                        f"{name}: permission.{key} must list '*' first - rules are last-match-wins"
                    )

    if problems:
        fail("agent frontmatter", "; ".join(problems))
    else:
        ok("agent frontmatter", f"{len(files)} agent(s)")


# --------------------------------------------------------------------------
# Agent policy — the three role definitions share a deny list and have already
# drifted apart once by hand. These are the invariants the workflow depends on,
# not general frontmatter hygiene (check_agents covers that).
# --------------------------------------------------------------------------

SHARED_BASH_DENY = (
    "*--version*",
    "python*",
    "python3*",
    "pip*",
    "py -m*",
    "*-m pip*",
    "node*",
    "npm*",
    "npx*",
    "docker*",
    "ssh*",
    "scp*",
    "curl*",
    "wget*",
    "which*",
    "where*",
    "git push*",
    "git reset*",
    "git checkout*",
    "git restore*",
    "git clean*",
    "git rebase*",
    "git stash*",
)

# agent file -> (mode, git add/commit, delegates it may spawn)
AGENT_ROLES = {
    "orchestrator.md": ("primary", "allow", ("local-coder", "code-reviewer")),
    "local-coder.md": ("subagent", "deny", ()),
    "code-reviewer.md": ("subagent", "deny", ()),
}

# The coder is the only role that writes, so its allowlist is pinned exactly.
# It may add task acceptance checks; the invariant modules under scripts/checks/
# define the rules it is graded against and stay out of reach.
CODER_EDIT_ALLOW = ("monitoring/**", "scripts/checks/task_*.py")


def check_agent_policy() -> None:
    directory = ROOT / ".opencode" / "agents"
    problems = []

    for filename, (mode, git_write, delegates) in AGENT_ROLES.items():
        path = directory / filename
        if not path.exists():
            problems.append(f"{filename}: missing")
            continue

        meta, error = parse_frontmatter(path)
        if meta is None:
            problems.append(f"{filename}: {error}")
            continue

        if meta.get("mode") != mode:
            problems.append(f"{filename}: mode must be {mode!r}, got {meta.get('mode')!r}")

        permission = meta.get("permission")
        if not isinstance(permission, dict):
            problems.append(f"{filename}: needs a 'permission' mapping")
            continue

        for key in ("webfetch", "external_directory"):
            if permission.get(key) != "deny":
                problems.append(f"{filename}: permission.{key} must be 'deny'")

        bash = permission.get("bash")
        if not isinstance(bash, dict):
            problems.append(f"{filename}: permission.bash must be a mapping")
        else:
            missing = [rule for rule in SHARED_BASH_DENY if bash.get(rule) != "deny"]
            if missing:
                problems.append(f"{filename}: bash must deny " + ", ".join(missing))
            for rule in ("git add*", "git commit*"):
                if bash.get(rule) != git_write:
                    problems.append(
                        f"{filename}: bash {rule!r} must be {git_write!r}, got {bash.get(rule)!r}"
                    )

        task = permission.get("task")
        if not isinstance(task, dict) or task.get("*") != "deny":
            problems.append(f"{filename}: permission.task must deny '*' first")
        else:
            allowed = tuple(sorted(k for k, v in task.items() if v == "allow"))
            if allowed != tuple(sorted(delegates)):
                problems.append(
                    f"{filename}: may spawn {tuple(sorted(delegates))}, frontmatter allows {allowed}"
                )

        edit = permission.get("edit")
        if filename == "code-reviewer.md":
            if edit != "deny":
                problems.append(f"{filename}: permission.edit must be 'deny' (review writes nothing)")
        elif not isinstance(edit, dict):
            problems.append(f"{filename}: permission.edit must be a mapping")
        elif edit.get("*") != "deny":
            problems.append(
                f"{filename}: permission.edit must deny '*' first - an allowlist, not a denylist"
            )
        elif filename == "local-coder.md":
            allowed = tuple(k for k, v in edit.items() if v == "allow")
            if allowed != CODER_EDIT_ALLOW:
                problems.append(
                    f"{filename}: edit allowlist must be {CODER_EDIT_ALLOW}, got {allowed}"
                )
            if edit.get("**/.env") != "deny":
                problems.append(f"{filename}: edit must deny '**/.env' after the allowlist")

    if problems:
        fail("agent policy", "; ".join(problems))
    else:
        ok("agent policy", f"{len(AGENT_ROLES)} role(s), shared deny list intact")
