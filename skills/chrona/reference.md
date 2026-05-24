# Chrona Skill Reference

## Paths

| Resource | Path |
|---|---|
| Project root | `{CHRONA_ROOT}` or the repository root containing `app.py` |
| User archive | `{CHRONA_ROOT}/data/users/{user}/session_archive.json` |
| User profile | `{CHRONA_ROOT}/data/users/{user}/user_profile_memory.json` |
| CLI module | `{CHRONA_ROOT}/chrona_cli.py` |
| Website | `http://127.0.0.1:8501` by default |

## CLI Contract

All commands exit `0` on success and print JSON by default. Use `--format text` for status summaries.

```powershell
scripts\chrona.ps1 status --user admin
scripts\chrona.ps1 web status --user admin
scripts\chrona.ps1 web start --user admin
scripts\chrona.ps1 task list --user admin --status pending
scripts\chrona.ps1 task add --user admin "明天晚上前写实验报告，大概 2 小时"
scripts\chrona.ps1 task done --user admin --id TASK_ID
scripts\chrona.ps1 schedule --user admin --ensemble-size 3
scripts\chrona.ps1 recover --user admin --missed TASK_ID
scripts\chrona.ps1 profile show --user admin
```

Global options can appear before or after subcommands: `--root`, `--user`, `--offline`, `--format`.

`recover --missed TASK_ID` first marks the named task as `missed`, computes affected downstream/same-series/recovery-window tasks, then runs the normal schedule pipeline.

## Archive Keys

| Key | Type | Agent access |
|---|---|---|
| `pending_tasks` | array | Read/write only through CLI |
| `last_scores` | object/null | Written by `schedule` |
| `last_result` | object/null | Written by `schedule` |
| `last_profile` | object/null | Written by `schedule` |
| `last_run_at` | ISO string/null | Written by `schedule` |
| `operation_history` | array | Append only through CLI |

## Task Fields

| Field | Notes |
|---|---|
| `task_id`, `title`, `duration_min`, `deadline`, `status` | Required for scheduling |
| `deadline_type` | `strict` or `flexible` |
| `earliest_start`, `manual_start`, `manual_end` | ISO datetimes or null |
| `series_id`, `dependencies` | Used by local ordering and solver dependency constraints |
| `required_environment`, `required_quietness` | Used by candidate generation and scoring |
| `must_be_contiguous`, `deep_work_min`, `tags` | Used by scoring and deep-work budget |

## Schedule Result

`last_result.blocks[]` contains `task_id`, `title`, `start`, `end`, `priority`, and `reason`.

Always surface `unscheduled_task_ids` to the user. If this list is non-empty, ask whether to shorten tasks, extend deadlines, or manually adjust availability.

## AGENTS.md Alignment

- `Task_Object` maps to archive `pending_tasks[]` and `core.models.Task`.
- `Score_Matrix` maps to `last_scores` and `core.models.TaskScore`; this project has an extra `quietness_need` dimension.
- `User_Profile` maps to `user_profile_memory.json` plus `core.models.UserProfile`.
- `Schedule_Result` maps to `last_result` and `core.models.ScheduleResult`.

## Website Access

Use `web status` before telling the user the website is usable. Use `web start` to launch Streamlit. If the returned JSON has `"running": false` after start, ask the user to inspect `streamlit.err.log` or run setup diagnostics.
