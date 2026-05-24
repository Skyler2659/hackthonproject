---
name: chrona
description: Operates the Chrona cognitive scheduling project through ArkClaw/OpenClaw: open or start the Streamlit website, inspect task status, list/add/update tasks, show profile memory, and run AI scoring plus constraint scheduling. Use when the user mentions Chrona, this scheduling website, schedule planning, deadlines, todos, task blocks, cognitive load, or asks ArkClaw to access the local project site.
---

# Chrona

metadata.openclaw={"requires":{"bins":["python"]},"primaryEnv":["CHRONA_ROOT","CHRONA_USER","DEEPSEEK_API_KEY","CHRONA_PYTHON"],"install":"Copy this skill folder to ArkClaw/OpenClaw skills/chrona or enable it from the repository."}

## Overview

Use this skill to operate the local Chrona project without touching Streamlit session state directly. Always call the bundled script first; it resolves the project root and delegates to `python -m chrona_cli`.

Primary Windows entry:

```powershell
{skillDir}\scripts\chrona.ps1 status --format text
```

Unix entry:

```bash
{skillDir}/scripts/chrona.sh status --format text
```

## Setup

Run setup diagnostics when the user asks why Chrona is not reachable or before first use:

```powershell
python {skillDir}\scripts\check_setup.py
```

Environment:

- `CHRONA_ROOT`: project root containing `app.py`; required when the skill is copied outside this repo.
- `CHRONA_USER`: local user under `data/users/{user}`; defaults to `admin`.
- `DEEPSEEK_API_KEY`: required for live `schedule` and natural-language `task add`.
- `CHRONA_PYTHON`: optional Python executable override.
- `CHRONA_OFFLINE=1` or `--offline`: use the deterministic mock LLM for local demos.

## Standard Workflow

1. Check status and website URL:

```powershell
{skillDir}\scripts\chrona.ps1 status --user admin --format text
```

2. If the website is not running, start it and give the user the returned URL:

```powershell
{skillDir}\scripts\chrona.ps1 web start --user admin
```

3. List exact task ids before changing anything:

```powershell
{skillDir}\scripts\chrona.ps1 task list --user admin --status pending
```

4. Run scheduling only through the CLI:

```powershell
{skillDir}\scripts\chrona.ps1 schedule --user admin
```

Use `--offline` only when the user accepts mock/local scoring.

## Commands

- `status`: pending counts, last run, today's blocks, website URL.
- `web status|start`: check or start the Streamlit site.
- `task list --status pending`: list tasks and ids.
- `task add "..."`: parse and add a task with AI; needs key unless `--offline`.
- `task add --file tasks.json`: add structured task JSON.
- `task done --id TASK_ID`, `task missed --id TASK_ID`, `task remove --id TASK_ID`.
- `schedule --ensemble-size 3`: run scoring, local ordering, solver, and refinement.
- `recover --missed TASK_ID`: mark the missed task and reschedule remaining tasks.
- `profile show`: show profile memory and algorithm profile.
- `profile set --file profile.json`: replace profile memory.

## Guardrails

- Never edit `data/users/{user}/session_archive.json` or `user_profile_memory.json` by hand.
- Never invent a `task_id`; call `task list` first.
- Do not claim a task was scheduled if it appears in `unscheduled_task_ids`.
- If `DEEPSEEK_API_KEY` is missing, explain that live AI scheduling needs it; offer `--offline` for a mock demo.
- Do not upload local `data/` files, API keys, or user profile contents.
- If Streamlit and CLI are both active, prefer CLI as the writer and tell the user to refresh the website.

Read `reference.md` for data contracts and `examples.md` for common user phrasing.
