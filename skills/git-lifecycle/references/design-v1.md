# Git Lifecycle v1 — 跨项目防遗留方案（P0 已实施范围）

## 目标与 SSOT

本能力属于 AI 开发协作基础设施，**不属于任何单个业务项目**。源码由 `my-agent-skills/skills/git-lifecycle` 管理，面向需要共享 Git 生命周期检查的各类 Git 仓库和客户端。保留已有个人 Skill 仓库、安装器、审查能力，不复制一套到每个项目。

问题：Agent 创建 Branch / Worktree 后，任务结束或跨会话时没有负责合并、归档、验证和清理，Human 需要主动检查。目标是生命周期 **可检查、可交接、可受控收尾**，而非自动删除一切非 main 资源。

## Reuse-First / Build vs Reuse 设计复核（2026-10-20）

**真实目标：** 跨项目、跨会话对 Git Branch / Worktree / Submodule 做**严格只读、失败关闭、可审计**的清单；不执行删除或合并。首轮技术基础和源码仓库 `my-agent-skills` 已经获得 Human 的 P0 分阶段实施批准。本节补录方案比较，**不构成 P1/P2 自动收尾的新授权**。

| 方案 | 已确认能力 | 当前差异 / 风险 | P0 决策 |
| --- | --- | --- | --- |
| **Git 原生 CLI** `worktree list --porcelain`、`for-each-ref`、`merge-base`、`ls-files`、`ls-remote` | 标准机器可读元数据，安装环境现成；由 Git 负责仓库对象/Worktree 管理 | 需要薄包装来组合多仓库、子模块、远端已发布判定和严格失败关闭；`status` 可能隐式执行过滤器 | **复用作为核心引擎**，只维护薄只读编排层 |
| 已安装的 **superpowers / using-git-worktrees、finishing-a-development-branch** | 已有 Agent 操作/完成分支的人工决策流程 | 不是跨项目、异常会话遗留资源的自动枚举与结构化审计器 | P1 规则/流程优先复用，P0 不直接替代 |
| [gregkop/worktree-cleanup](https://github.com/gregkop/worktree-cleanup) | 可只读扫描多个 Agent 工作树、识别脏文件/合并状态，删除前需批准 | 现场仓库页面只有 1 次提交记录；长期维护/脚本副作用未验证；分类可能基于空闲时长及本地 Git 而不是实时远端发布，安全边界不同 | 候选：后续可比较/借鉴，不直接安装 |
| [noirbizarre/git-wipe](https://github.com/noirbizarre/git-wipe) | `git wipe status` 只读分支和 Worktree 盘点；提供可选交互式清理 | 当前 Mac 未安装，Rust 分发为额外依赖；未验证严格远端确认、递归子模块和禁用外部 Git 命令的行为 | 保留候选，P0 不增加依赖 |
| [epicserve/git-cleanup](https://github.com/epicserve/git-cleanup) | 分支/Worktree/Stash TUI，`--dry-run` 和 `--no-fetch` | 默认交互及可写清理流程；依赖 Python 3.14+，跨电脑版本约束；未验证严格无外部进程及子模块行为 | 不作为 P0 后台/Hook 扫描器 |
| [Tokenbooks/wt](https://github.com/Tokenbooks/wt) | `wt audit --json --no-fetch`，也有 Worktree 生命周期管理 | 涉及数据库/Docker/PR 的多服务管理，超过本轮最小只读范围 | 当前不引入 |

**选择：Reuse + 最小适配**，不是自研 Git 工作树系统：调用原生 Git 标准命令，仅编写必要的 Python 检查编排、风险分类和严格配置隔离。与现有 Skill 安装器复用；不创建业务项目专属脚本/数据库。选择依据是当前环境已有 Git/Python、P0 无外部依赖、需对子模块/并发 Worktree/远端证明进行一致性报告，且复核/回归已覆盖已知失效路径。

**证据边界：** 此比较依据为官网和仓库公开说明，以及本机已安装工具列表；没有下载、安装或执行上述第三方项目，不能声称它们不安全、不维护或不适合 P1/P2。下阶段若要实现自动清理，必须重新考虑复用现成工具或相应子流程（Build-Last），并独立验证依赖、维护状态、权限和与本工具的安全条件兼容性。

参考：[Git worktree 机器可读文档](https://git-scm.com/docs/git-worktree.html)、[Git attributes/filter 外部命令](https://git-scm.com/docs/gitattributes)、以上工具公开 README。该记录解决设计证据缺失，不替代独立代码安全 Review。

## 阶段及授权边界

| 阶段 | 范围 | 实施状态与证据边界 |
| --- | --- | --- |
| P0 | Git 分支、工作树、递归子模块只读盘点；多项目显式登记输入；有限远端证明 | 已实施并验证；不执行清理 |
| P1 | Codex / Claude Code 共用规则、Skill 和只读 SessionStart / Stop Hooks | 适配器已纳入源码；示例不自行启用。既有本机部署及本次检查范围见下方带日期记录，不代表任意安装环境默认启用；强制任务归属登记已取消为前置要求 |
| P2 | 人工审批式 Git 资源收尾：先只读检查、再按精确对象分开审批和非强制操作；不设自动执行器 | 历史记录包含一例本地分支删除及隔离夹具观察，原始输出未归档，不能视为完整验收或自动执行授权；现行步骤见独立 P2 流程 |
| P3 | 可选的本机定期只读巡检和异常遗留提醒 | 未授权、未实施；视后续实际收益决定 |

P0 不修改全局 `~/.codex/AGENTS.md`、Claude Hooks、Git 配置、Git refs、定时任务，也不在业务项目创建文件。工具 Python 标准库 + Git CLI，无数据库、无第三方依赖。

## P0 判断规则

- `CLEAN`：未发现非目标分支、额外工作树、非正常子模块引用、工作区修改或 HEAD 独有未合并提交；**不表示仓库内容已经独立 Review**。
- `CLEANUP_READY`：名称匹配预设临时前缀、分支未在任何 Worktree checkout、提交包含在本地目标分支，且实时 `ls-remote` 返回的远端目标分支也包含这些提交。仅表示**技术上具备清理候选条件**；不能证明无人使用、归属合法或具备删除授权。P0 永不删除。
- `ACTIVE`：分支在某个 Worktree 上处于 checkout 状态，或发现额外 Worktree。包括干净但无法证实停用的工作树；额外 Worktree 也必须读取其未提交/未跟踪内容和子模块引用，遇到未保存修改、子模块异常或不可检查时升级为 `NEEDS_DECISION`；Detached HEAD 另记录其 HEAD SHA 与是否被本地 base 包含，存在独有提交时升级为 `NEEDS_DECISION`。裸仓库仅作为管理存储，不当作活动 Worktree。
- `NEEDS_DECISION`：未合并提交（包括 Detached HEAD 未被本地 base 包含的提交）、工作区修改、子模块 gitlink 不一致、目标分支缺失、远端发布未验证、非临时命名或其他无法安全归类的情况。

优先级（仓库汇总）：`NEEDS_DECISION > ACTIVE > CLEANUP_READY > CLEAN`。分支和额外 Worktree 分别展示状态，避免聚合误导。所有非 base 分支都纳入检查，前缀仅影响是否可列为候选，**不能作为删除依据**。默认 `main`；仅当该仓库没有 `main` 而有 `master` 时自动兼容旧式默认分支，结果中注明实际 base；可用 `--base` 覆盖。

### 远端的证据边界

默认只读本地元数据，不能把本地 `origin/main` 视为实时 GitHub 状态。显式 `--verify-remote` 才调用 `git ls-remote --heads origin <base>`，且只在远端 SHA 对应本地已知 commit 时做祖先验证；网络失败、未经 fetch 的未知 SHA、认证失败都归类为 `UNAVAILABLE`。它不 fetch，不更新引用，不向远端写入。每个 Git 子进程都会清除继承的 `GIT_*` 及 `SSH_ASKPASS*` 环境变量，隔离全局/系统 Git 配置，显式设置 `GIT_NO_LAZY_FETCH=1` 与 `GIT_NO_REPLACE_OBJECTS=1`，通过命令行覆盖 `core.fsmonitor=false`、`core.hooksPath=/dev/null`。因此调用者环境不会重定向显式仓库；对残存的旧式 `info/grafts` 和任何分支枚举告警都失败关闭，不依据被污染或不完整的祖先/引用关系生成清理候选。远端验证先只读取仓库的 `remote.origin.url`，拒绝带用户名/密码的 HTTPS、`file://` URL 或不安全协议的 URL；对 **HTTPS（不调用凭据助手）和绝对路径本地仓库 / `file://`**，在仓库外的隔离 Git 上下文用字面 URL 执行 `ls-remote`，不使用可能执行外部 `uploadpack` 命令的 remote 名称。**SSH、需要凭据的私有 HTTPS 仓库、相对路径和其他 URL 暂记 `UNAVAILABLE`**，不产生虚假的 `CLEANUP_READY`。

### Registry 与跨项目范围

`check --repo PATH` 可重复，单次按显式路径检查多个仓库；`check --all` 仅使用由 Human 准备/批准的 JSON 文件，格式为 `{"version":1,"repositories":["/absolute/repo"]}`。默认读取 `~/.config/git-lifecycle/projects.json`，**P0 不创建或改写这个文件**。对已初始化的嵌套 Submodule 递归扫描；对子模块 HEAD 与宿主 gitlink 不一致或未初始化则明确报告。若嵌套子模块扫描抛出 Git 错误，父节点标注 `UNKNOWN`，同时将错误并入顶层 `errors`，令 CLI 返回退出码 1；绝不以完整扫描成功报告。工作树列表以每个 Git 仓库自身的 `git worktree list --porcelain` 为准，不将 Codex 目录下的空标记文件误判为 Git Worktree。

### 外部 Git filter 的严格只读边界

`git status` 可能运行仓库配置的 `filter.<driver>.clean` 或 `filter.<driver>.process` 命令，还可能间接检查子模块内部文件。P0 在**每个**主/关联 Worktree 的状态检测之前，读取有效 Git 配置键（不输出命令值）；一旦发现这些可执行转换过滤器，即返回扫描错误并停止，禁止以 `CLEAN`/候选清理代替。状态检查显式使用 `--ignore-submodules=all`，阻止父仓库提前进入未校验的子模块；随后独立递归检查子模块的配置/工作区/HEAD。为避免忽略暂存的 Gitlink 更新，再使用不执行外部 diff/textconv 的只读 cached diff 对比 index 与 HEAD。此保守策略可能拒绝含有合法本地过滤器配置的仓库；如后续需要支持 Git LFS 等情况，必须另行设计只读状态识别，不得放宽为执行任意过滤器。

隔离测试使用干净的临时仓库以及受控 Git 环境，禁用继承的 `GIT_*` 配置、系统/全局设置、Hook 与提交签名；避免测试自身误操作生产仓库。

## P1 集成及部署边界

统一复用本仓库的单一检查器，各客户端只部署适配与薄入口。Codex 使用用户级指令/Skill/受信任的 Hooks；Claude Code 用增量 Hook 配置，保留现有 `cc-status` 事件处理器。技能选择不是强制触发的保证；Stop 事件也不必然代表任务完成，因此 Hook 仅作只读检查、不能据此执行删除。

### P1 部署记录与当前证据边界

- **2026-10-21 历史记录：** 当时记录称本机已启用并在先前会话验收；本仓库未保留完整运行日志，不能仅凭该记录独立复验。
- **2026-11-03 只读复核：** 本机 Codex 与 Claude Code 均配置了 Git Lifecycle 的 `SessionStart` / `Stop`；两端安装链接都解析到本仓库，并包含 `hook_bridge.py`。当前 Codex 会话实际收到启动快照。本次没有重新验证 Claude 的运行时事件或两端全部 Stop 行为，不能据此宣称完整端到端验收。
- **适用边界：** 上述记录仅描述已检查机器和时点，不是所有使用者的部署状态。仓库参考 JSON 不会自行激活；新安装或修改既有部署需遵守 [P1 激活门槛](p1-hook-integration.md)。源码已包含适配器，不再沿用“仅在隔离预览分支、安装链接仍只指向 P0”的旧阶段描述。

任务归属登记（Task ID / Agent 会话索引）已由 Human 决定**暂缓**：Git Lifecycle 的核心结果是发现、审计、提醒及 Human 受控收尾；不以能否查到 Task ID 为清理前置条件。没有任务标签不等于资源不再被使用，客户端的停止事件或进程消失也不证明任务已完成。如未来要实现跨会话任务恢复，必须另行按 Outcome-First / Reuse-First 评审，不在本 P2 范围内新建登记库。

## P2 — 人工审批式安全收尾：最小流程（2026-10-21）

**Outcome-First / Reuse-First 决策：** 暂不开发 P2 执行器、自动清理服务或任务归属数据库。复用现有 P0 只读检查器和标准 Git 命令；`finishing-a-development-branch` Skill 仅为可选的“验证 → 选项 → Human 选择”结构参考，缺失时直接遵循 [P2 完整流程](p2-closeout.md)，无需安装。该 Skill 中的 `git pull`、`git worktree prune`、`-D` 强制丢弃等步骤不是默认批准动作。P0 标签不构成清理许可。

### 历史演练记录与证据局限

以下保留的是历史会话报告，不是本轮重新验证的 Git 行为，也不能推广为所有版本的行为保证。安全门槛见独立 P2 流程；这些观察不授予清理权限。

- 根据 **2026-10-21 操作会话记录**（原始执行输出不保存在本仓库，故不能在这里独立重放）：曾在 Human 针对精确目标审批后，核对本地分支、主线、Worktree、子模块和远端实时包含关系，仅执行非强制 `git branch -d` 并回读成功。为避免把业务项目标识复制到共享 Skill，本记录不保存其具体路径、分支和 SHA。该案例**没有 Worktree 删除**，不能升级为 P2 全面验收。
- 根据 **2026-10-21 隔离夹具会话记录**（未随仓库存档的历史实测，非本仓库可直接重放的证据）：在 Apple Git 2.39.5 上，`git worktree remove` 非强制模式仍可删除**仅含 ignored 文件**的 Worktree；也可删除有**独有提交的干净 Detached HEAD** 的 Worktree，导致工作树引用丢失。它对一般已修改/未跟踪文件与被锁的 Worktree 会拒绝。`git branch -d` 即使未验证远端发布也可删除已合并的本地分支。另外，`assume-unchanged` / `skip-worktree` 可使普通 status 不显示已跟踪文件的本地更改，而 `ls-files -t -v -z` 可显式发现这些标记。因此“不带 `--force`”和“status 为空”均**不是充分的数据保留保证**。
- 状态变化夹具：分支批准后产生新提交，P0 可能同时把已检出的分支与 Worktree 标 `ACTIVE`、但明确给出 `merged_into_local_base=false`。核对**批准快照的 HEAD 和保留 ref 祖先关系**才可拒绝错误收尾。夹具均已清理，没有对真实项目实施删除。

### P2 手工评估与审批门槛

现行操作要求集中维护于 [P2 完整流程](p2-closeout.md)。请求清理时必须先完整阅读该流程，核对精确目标与全部可能丢失的内容，分别取得工作树和分支审批，并在每项操作紧前独立复核；失败或中断即停止、报告并重新规划。本设计记录不再复制第二份操作清单。

2026-11-03 文档整理将详细步骤从 `SKILL.md` 与本设计记录集中到上述参考文件，并将历史观察与现行指令分开；脚本和测试未修改。独立设计 Review 不等于代码安全 Review；若未来引入清理执行器，仍须另行论证收益、解决并发与远端验证边界，经 Human 单独授权及独立代码 Review。

以上是**手工受控流程说明**，不授予 Hook、定时器、Skill 或 Agent 自动删除权，也不允许对其他并行项目执行跨仓库写入。

## P0 验收与非目标

- 在临时 Git fixture 中覆盖干净、离线误判防护、实时远端确认、未合并分支、额外 Worktree、未跟踪文件、子模块引用不匹配、registry 成功/失败、Tag/Branch 同名、主工作树及额外 Worktree 的 Detached HEAD 独有提交、额外 Worktree 未跟踪文件/子模块、裸仓库管理目录排除、Fsmonitor 禁用、祖先比较超时/批量错误隔离、嵌套子模块扫描失败传播、禁止 Lazy Fetch 环境、环境变量与配置注入隔离、恶意远端 uploadpack 禁止执行、无效协议及带凭据本地 URL 拒绝、Replace Objects 禁用、Askpass 禁用、分支枚举告警失败关闭、旧式 grafts 检测、外部 Git Clean/Process Filter 检测、父仓库对子模块外部 Filter 的防隔离、暂存 Gitlink 更新识别、测试夹具环境隔离等场景。
- 按现有 `validate_skills.py`、`test_install.py` 和 `skill-reviewer` 进行一致性/安全检查；独立 Review 不能由编写者自查代替。
- 真实项目仅只读盘点。**项目实际状态可能并发变化**，每个报告为观察快照，不表示获得清理锁。
- P0 不负责 GitHub PR 内容 Review、跨仓库编排、AI 并发锁、系统级通知、删除逻辑，也不保证旧项目全量自动发现。后续需求需重新确认阶段及权限。
