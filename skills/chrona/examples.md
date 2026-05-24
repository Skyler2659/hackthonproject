# Chrona Examples

## Show Current Site

User: "通过 ArkClaw 打开这个项目网站。"

Action:

```powershell
scripts\chrona.ps1 web start --user admin
scripts\chrona.ps1 status --user admin --format text
```

Reply with the local URL and a short status summary.

## Add And Schedule

User: "明天下午交作业，大约 2 小时。"

Action:

```powershell
scripts\chrona.ps1 task add --user admin "明天下午交作业，大约 2 小时"
scripts\chrona.ps1 schedule --user admin
```

Then summarize scheduled blocks and any `unscheduled_task_ids`.

## Reschedule Today

User: "把我今天的待办排一下。"

Action:

```powershell
scripts\chrona.ps1 task list --user admin --status pending
scripts\chrona.ps1 schedule --user admin
```

Mention if `DEEPSEEK_API_KEY` is missing and offer `--offline` as a mock demo.

## Mark Missed

User: "高数复习错过了，帮我重排。"

Action:

```powershell
scripts\chrona.ps1 task list --user admin --status pending
scripts\chrona.ps1 recover --user admin --missed TASK_ID
```

Do not guess `TASK_ID`; list tasks first.

## Profile

User: "我上午效率高，以后优先上午排难任务。"

Action: explain that profile updates require structured `profile set --file profile.json`, or ask the user to update the website's profile questionnaire. Then run `schedule`.
