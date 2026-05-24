# Chrona × ArkClaw / OpenClaw Skill 适配计划

> 用途：按本清单推进「主项目可调用层」与「Skill 包」；完成一项勾一项。  
> 原则：**先 CLI/服务层，后 Skill**；Skill 只教 Agent 调用，不重复实现调度算法。

---

## 0. 决策记录（动手前填完）

| 项 | 选择（填 ✅） | 备注 |
|----|-------------|------|
| Agent 平台 | ✅ ArkClaw / OpenClaw ☐ 其他：_______ | Skill 已放在 `skills/chrona/` |
| 集成方式 | ✅ CLI（推荐 P0） ☐ 本地 HTTP ☐ 仅改 JSON（不推荐） | 已新增 `chrona_cli.py` |
| 默认用户 | `CHRONA_USER=admin` | 对应 `data/users/admin/` |
| 项目根变量 | `CHRONA_ROOT=C:\Users\Lenovo\Desktop\Hackthon0` | 脚本可从仓库内自动探测 |
| LLM | ✅ DeepSeek；✅ `--offline` mock | 无 Key 时 live `schedule` / `task add` 明确失败，`--offline` 可演示 |
| 与 Streamlit 并发 | ✅ CLI 写、网页刷新 ☐ 禁止同时操作 | Skill 要求不手改 JSON |

**P0 能力（必选）**

- [x] `status` — 待办 + 最近排程摘要
- [x] `task list` — 列出 pending 任务
- [x] `schedule` — 完整调度流水线
- [x] `profile show` — 用户画像摘要

**P1 能力（Skill v1 可选）**

- [x] `task add` — 自然语言或 JSON 添加任务
- [x] `task done` / `task missed` — 状态变更
- [x] `recover` — 错过任务后重排
- [x] `profile set` — 更新作息/权重

**P2（后续）**

- [ ] FastAPI 网关
- [ ] 多用户 token 鉴权
- [ ] ClawHub 公开发布

---

## 1. 现状与目标

### 1.1 现状

| 模块 | 路径 | Agent 可用性 |
|------|------|----------------|
| Web UI | `app.py`, `web_ui/*` | ❌ 依赖 Streamlit session |
| 调度流水线 | `web_ui/auto_scheduler.py` | ⚠️ 含 `st.progress` / `st.spinner` |
| 持久化 | `web_ui/archive.py` | ⚠️ 读写多经 `st.session_state` |
| 用户数据 | `data/users/{user}/session_archive.json` | ✅ 可直接读，不宜手改 |
| 画像 | `data/users/{user}/user_profile_memory.json` | ✅ 可直接读 |
| 认证 | `data/auth_users.json` | CLI 可绕过（指定 user） |
| 算法/Agent | `agents/`, `algorithms/`, `models.py` | ✅ 可复用 |
| 契约文档 | `AGENTS.md` | ✅ Skill reference 来源 |

### 1.2 目标架构

```
ArkClaw Agent
    → 读取 Skill (SKILL.md)
    → 执行 scripts/chrona.ps1 | chrona.sh
        → python -m chrona_cli <subcommand>
            → chrona_service (无 Streamlit)
                → agents / algorithms
                → data/users/{user}/*.json
```

---

## 2. 主项目改造清单（必须先做）

### 2.1 新建模块

| 文件 | 状态 | 职责 |
|------|------|------|
| `chrona_cli.py` | ✅ | `argparse` 入口，`main()` 分发子命令 |
| `chrona_service/__init__.py` | ✅ | 包初始化 |
| `chrona_service/store.py` | ✅ | 按 `username` 读写 archive / profile_memory |
| `chrona_service/config.py` | ✅ | 解析 `CHRONA_ROOT`, `CHRONA_USER`, `DEEPSEEK_API_KEY` |
| `chrona_service/scheduler.py` | ✅ | headless 版 `run_scheduler_pipeline` |
| `chrona_service/tasks.py` | ✅ | 任务 CRUD（dict 层，不写 Streamlit） |
| `chrona_service/profile.py` | ✅ | 从 memory 构建 `UserProfile` + `profile_config` |

### 2.2 修改现有文件（小改 / 抽函数）

| 文件 | 状态 | 改动要点 |
|------|------|----------|
| `web_ui/archive.py` | ☐ | 增加 `load_archive_for_user(username)`、`save_archive_for_user(username, payload)`；序列化函数已可复用 |
| `web_ui/auto_scheduler.py` | ☐ | 抽出 `run_scheduler_pipeline_headless(...)`，无 `st.*`；Streamlit 版改为调用它 |
| `web_ui/task_data.py` | ☐ | 或将 `remove_task` 等改为接受 `pending_tasks: list` 参数；service 层调用 |
| `web_ui/profile_soft.py` | ☐ | CLI 复用 `build_algorithm_profile` / `build_profile_soft_hints` |
| `web_ui/user_memory.py` | ☐ | 增加 `load_profile_memory_for_user(username)`（或 store 包一层） |
| `web_ui/auth.py` | ☐ | P0 可不改；CLI 用环境变量指定 user |
| `app.py` | ☐ | P0 可不改 |

### 2.3 CLI 子命令规格（实现时对照）

| 命令 | 状态 | 输入 | 输出 | 依赖 LLM |
|------|------|------|------|----------|
| `status` | ✅ | `--user` | JSON/Markdown：待办数、末次排程时间、今日 blocks 摘要 | 否 |
| `task list` | ✅ | `--user`, `--status pending` | 任务 JSON 数组 | 否 |
| `task add` | ✅ | `--user`, 文本或 `--file tasks.json` | 新建 task_id 列表 | 是（TaskParser） |
| `task done` | ✅ | `--user`, `--id` | 更新后状态 | 否 |
| `task remove` | ✅ | `--user`, `--id` | ok / error | 否 |
| `schedule` | ✅ | `--user`, `--ensemble-size` | scores + schedule blocks + unscheduled | 是 |
| `profile show` | ✅ | `--user` | profile_memory + 算法用 UserProfile 摘要 | 否 |
| `profile set` | ✅ | `--user`, `--file profile.json` | ok | 否 |
| `recover` | ✅ | `--user`, `--missed <task_id>` | affected task set + 新 schedule | 是/部分 |

**统一约定**

- 成功：exit code `0`，stdout 为 JSON（`--format json` 默认）或 `--format text`
- 失败：exit code `非0`，stderr 中文/英文错误信息
- 所有写操作后写入 `session_archive.json`（与网页同一文件）

### 2.4 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `CHRONA_ROOT` | 推荐 | 仓库根；默认 CLI 自动探测 |
| `CHRONA_USER` | 推荐 | 默认 `admin` |
| `DEEPSEEK_API_KEY` | schedule/task add 时 | 同 `.env.example` |
| `DEEPSEEK_BASE_URL` | 否 | 默认 `web_ui/constants.py` |
| `CHRONA_LLM_MODEL` | 否 | 默认 `deepseek-chat` |

### 2.5 验收测试（主项目，Skill 之前）

- [x] 终端：`python -m chrona_cli status --user admin` 能读出与网页一致的任务数
- [x] 终端：`python -m chrona_cli schedule --user codex_smoke --offline` 后 `session_archive.json` 含 `last_result.blocks`
- [ ] 网页刷新后能看到 CLI 生成的排程（或先关网页再测）
- [x] 无 `DEEPSEEK_API_KEY` 时 `schedule` 明确失败并提示
- [x] `tests/` 中增加 1 个 smoke test（可选）

---

## 3. Skill 包清单（CLI 通过后再做）

### 3.1 目录结构

```
skills/chrona/                    # 或 ~/.openclaw/skills/chrona/
├── SKILL.md                      # ✅ 必需
├── reference.md                  # ✅ 推荐
├── examples.md                   # ✅ 可选
└── scripts/
    ├── chrona.ps1                # ✅ Windows 入口
    ├── chrona.sh                 # ✅ Unix 入口
    └── check_setup.py            # ✅ 检查 python / 密钥 / 数据目录
```

### 3.2 `SKILL.md` 内容检查项

- [x] YAML frontmatter：`name`, `description`（第三人称 + 触发词）
- [x] `metadata.openclaw` 单行 JSON：`requires.bins`, `primaryEnv`, 可选 `install`
- [x] **何时使用** / **何时不要用**
- [x] 前置条件：`CHRONA_ROOT`, `CHRONA_USER`, `DEEPSEEK_API_KEY`
- [x] 标准工作流：`status` → `task add` → `schedule` → `status`
- [x] 禁止：手改 `session_archive.json`、猜测 task_id
- [x] 失败处理：无任务、无 Key、不可行、未排入 `unscheduled_task_ids`
- [x] 正文 < 500 行；细节链到 `reference.md`

**description 草稿（可改）：**

```text
Operates Chrona cognitive scheduling: list tasks, add tasks, run AI scoring and constraint scheduling, read timetable. Use when the user mentions Chrona, schedule, deadline, todo, time blocks, or cognitive load planning.
```

### 3.3 `reference.md` 内容检查项

- [x] 数据路径表（见 §4）
- [x] `pending_tasks[]` 字段表（对齐 `web_ui/task_data.materialize_task`）
- [x] `last_result.blocks[]` 字段表
- [x] CLI 子命令完整参数与退出码
- [x] 与 `AGENTS.md` 的 `Task_Object` / `User_Profile` / `Schedule_Result` 对照
- [x] `operation_history` 是否暴露给 Agent（建议只读或不暴露）

### 3.4 `examples.md` 场景

- [x] 用户：「明天下午交作业，大约 2 小时」
- [x] 用户：「把我今天的待办排一下」
- [x] 用户：「高数复习错过了，帮我重排」
- [x] 用户：「我上午效率高，以后优先上午排难任务」（profile）

### 3.5 `scripts/` 行为

- [x] `chrona.ps1` / `chrona.sh`：`cd` 到 `$CHRONA_ROOT`，调用 `python -m chrona_cli "$@"`
- [x] `check_setup.py`：打印缺失项（python、密钥、user 目录）
- [x] Skill 正文写：**优先用 `{baseDir}/scripts/chrona.ps1`，不要临时拼 Python 路径**

### 3.6 OpenClaw 安装与配置

- [ ] 复制/链接 skill 到 `skills/chrona/` 或 `openclaw skills install`（若发布）
- [ ] `~/.openclaw/openclaw.json` → `skills.entries.chrona`（enabled、env 注入）
- [ ] Agent allowlist 含 `chrona`（若使用 `agents.list[].skills`）
- [ ] 新开会话，用触发句测试是否加载 skill

---

## 4. 数据契约速查（写入 reference.md）

### 4.1 路径

| 资源 | 路径 |
|------|------|
| 会话存档 | `{CHRONA_ROOT}/data/users/{user}/session_archive.json` |
| 用户画像 | `{CHRONA_ROOT}/data/users/{user}/user_profile_memory.json` |
| 账号库 | `{CHRONA_ROOT}/data/auth_users.json`（CLI 通常不碰） |

### 4.2 `session_archive.json` 顶层键

| 键 | 类型 | Agent 读 | Agent 写（经 CLI） |
|----|------|----------|-------------------|
| `pending_tasks` | array | ✅ | ✅ |
| `last_scores` | object \| null | ✅ | schedule 时 |
| `last_result` | object \| null | ✅ | schedule 时 |
| `last_profile` | object \| null | ✅ | schedule 时 |
| `last_run_at` | ISO string \| null | ✅ | schedule 时 |
| `operation_history` | array | 可选 | CLI 追加 |

### 4.3 `pending_tasks[]` 单条（常用字段）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | ✅ | 唯一 |
| `title` | string | ✅ | |
| `description` | string | | |
| `duration_min` | int | ✅ | ≥5 |
| `deadline` | ISO datetime | ✅ | |
| `earliest_start` | ISO \| null | | |
| `status` | string | | `pending`/`done`/`missed`/`cancelled` |
| `series_id` | string \| null | | |
| `dependencies` | string[] | | task_id |
| `required_environment` | string[] | | 如 `desk`, `library` |
| `required_quietness` | float | | 0–1 |
| `must_be_contiguous` | bool | | 默认 true |
| `deadline_type` | string | | `strict` / `flexible` |
| `manual_start` / `manual_end` | ISO \| null | | 手动锁定时段 |

### 4.4 `last_result.blocks[]`

| 字段 | 说明 |
|------|------|
| `task_id`, `title` | |
| `start`, `end` | ISO datetime |
| `priority` | float |
| `reason` | 可读解释（Agent 应答用户时可引用） |

---

## 5. 调度流水线（headless 应对齐的逻辑）

与 `web_ui/auto_scheduler.run_scheduler_pipeline` 一致：

1. [x] `materialize_tasks(pending_tasks)` → `active_schedulable_tasks`
2. [x] `build_algorithm_profile` + `build_profile_soft_hints`
3. [x] `ScoringAgent.score_task`（每个任务）
4. [x] `LocalSeriesAgent.order_tasks`
5. [x] `WeightedScheduler.schedule`
6. [x] `refine_schedule`（LLM）
7. [x] 写回 `last_scores`, `last_result`, `last_profile`, `last_run_at`
8. [x] 追加 `operation_history`：`schedule_updated`

---

## 6. 分阶段里程碑

### Milestone A — 只读（1–2 天）

- [x] `chrona_service/store.py` 读 archive + profile
- [x] `chrona_cli status` + `task list` + `profile show`
- [x] 空 Skill 目录 + `SKILL.md` 仅描述 status 流程（可先不测 Agent）

### Milestone B — 可排程（核心）

- [x] headless scheduler
- [x] `chrona_cli schedule`
- [ ] 与网页结果对比验收
- [x] 完整 `SKILL.md` + `scripts/chrona.ps1`

### Milestone C — 任务写入

- [x] `task add` / `task done` / `recover`
- [x] `reference.md` + `examples.md`
- [ ] ArkClaw 端到端对话测试

### Milestone D — 发布与加固

- [x] `check_setup.py`
- [ ] README 一节「Agent / OpenClaw 使用」
- [ ] （可选）ClawHub 发布、`.gitignore` 确认 `data/` 不入库

---

## 7. 风险与约束（Skill 正文须体现）

| 风险 | 缓解 |
|------|------|
| Streamlit 与 CLI 同时写 JSON | 约定单写者；或文档要求关网页 |
| 无 API Key | `schedule` 失败；Skill 提示用户配置 |
| 任务不可行 | 检查 `unscheduled_task_ids`，勿编造时间 |
| 澄清对话 (`task_clarification`) | P1 `task add` 需定义：CLI 跳过 / 交互 / 写死答案 |
| 敏感数据 | Skill 禁止上传 `data/`、禁止 commit 密钥 |

---

## 8. 与 AGENTS.md 对齐检查

- [x] Task_Object 字段与 `core.models.Task` / `pending_tasks` JSON 一致
- [x] Score_Matrix 五维 + confidence 与 `TaskScore` 一致（项目另含 `quietness_need` 扩展维度）
- [x] User_Profile 与 `UserProfile` + `user_profile_memory.json` 一致
- [x] Schedule_Result 与 `ScheduleResult` 一致
- [x] 未来 HTTP API 路径与 CLI 子命令 1:1 映射（便于 Phase 2）

---

## 9. 完成定义（Definition of Done）

**主项目完成：**

- [x] 所有 P0 CLI 子命令可用且文档化
- [x] 不 import Streamlit 即可跑 `schedule`
- [ ] 至少一次与 `app.py` 网页数据交叉验证

**Skill 完成：**

- [x] `skills/chrona/SKILL.md` + `reference.md` + `scripts/chrona.ps1`
- [ ] ArkClaw 在触发句下能自动执行 `status` → `schedule` 并用人话总结 `blocks`
- [x] `skillplan.md` 本文件中 Phase 0 决策表已填写

---

## 10. 进度总表（复制到 PR / 周报）

| 阶段 | 进度 | 负责人 | 完成日 |
|------|------|--------|--------|
| 0 决策 | ✅ | Codex | 2026-05-24 |
| 1 主项目 store + CLI 只读 | ✅ | Codex | 2026-05-24 |
| 2 headless schedule | ✅（offline smoke 已过，live 需 Key） | Codex | 2026-05-24 |
| 3 Skill 包 | ✅（本地 CLI/脚本/文档/smoke 完成） | Codex | 2026-05-24 |
| 4 Agent 联调 | ☐ | | |
| 5 发布/文档 | ☐ | | |

---

*文档版本：v1 · 项目：Chrona (Hackthon0) · 随实现更新 §0 决策表与 §10 进度*
