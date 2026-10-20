# Git Lifecycle v1 — 跨项目防遗留方案（P0 已实施范围）

## 目标与 SSOT

本能力属于 AI 开发协作基础设施，**不属于任何单个业务项目**。源码由 `my-agent-skills/skills/git-lifecycle` 管理，面向 Personal System、GameChat、其他 Git 仓库与后续客户端。保留已有个人 Skill 仓库、安装器、审查能力，不复制一套到每个项目。

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

| 阶段 | 范围 | 本轮状态 |
| --- | --- | --- |
| P0 | Git 分支、工作树、递归子模块只读盘点；多项目显式登记输入；有限远端证明；离线夹具测试；真实项目只读验证 | 本轮实施 |
| P1 | AI 客户端全局规则 + Skill 安装 / 受控生命周期 Hooks + 创建时归属登记；保留已存在配置，先仅报告 | 隔离适配器预览已获实现授权；全局 Hook 启用/持久任务登记另需批准 |
| P2 | 明确批准的合并、发布、安全清理；独立的目标身份复核、并发占用与重新检查；禁止强制删除和不明归属 | 未授权、未实现 |
| P3 | macOS launchd 登记项目巡检；异常中断发现、汇总与回报；初期只读，不自动删除 | 未授权、未实现 |

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

## 后续 P1 技术方案

统一复用本仓库的单一检查器，各客户端只部署适配与薄入口。Codex 使用用户级指令/Skill/受信任的 Hooks；Claude Code 用增量 Hook 配置，保留现有 `cc-status` 事件处理器。技能选择不是强制触发的保证；Stop 事件也不必然代表任务完成，因此 Hook 仅作只读检查、不能据此执行删除。

创建分支或工作树时，未来登记：稳定仓库 ID、规范化路径、Task ID、Agent/会话、创建时目标分支与基线、到期/结束信号、归属/活跃性证据。记录需独立于临时 worktree 生命周期，避免工作树被移动/删除后失去关联。老分支没有登记时必须保守处理。

## 后续 P2 清理门槛

任何写入操作须另获 Human 授权并进行临执行前独立复核：

1. 精确目标仓库、分支、工作树、路径身份、关联任务及所有权；未知 / 仍在使用就停止。
2. 所有有价值修改已保存，基线及提交经必要 Review；不得擅自合并未批准实验成果。
3. 目标提交已进入获批准主线且在远端可恢复，子模块引用先满足独立发布/采用顺序。
4. 无未提交、未跟踪或其他 Agent 占用；工作树已停止且无保留需求。
5. 允许的操作尽量只用非强制形式（如 `git branch -d`），绝不对未知路径强制清理；远端分支删除单独授权。
6. 执行后回读远端和工作树状态；失败停止并报告，不绕过检查或无界重试。

不因用户一次性同意“正常开发”而拥有跨项目合并、删除、改变 Hooks 或远端管理的永久权限。

## P0 验收与非目标

- 在临时 Git fixture 中覆盖干净、离线误判防护、实时远端确认、未合并分支、额外 Worktree、未跟踪文件、子模块引用不匹配、registry 成功/失败、Tag/Branch 同名、主工作树及额外 Worktree 的 Detached HEAD 独有提交、额外 Worktree 未跟踪文件/子模块、裸仓库管理目录排除、Fsmonitor 禁用、祖先比较超时/批量错误隔离、嵌套子模块扫描失败传播、禁止 Lazy Fetch 环境、环境变量与配置注入隔离、恶意远端 uploadpack 禁止执行、无效协议及带凭据本地 URL 拒绝、Replace Objects 禁用、Askpass 禁用、分支枚举告警失败关闭、旧式 grafts 检测、外部 Git Clean/Process Filter 检测、父仓库对子模块外部 Filter 的防隔离、暂存 Gitlink 更新识别、测试夹具环境隔离等场景。
- 按现有 `validate_skills.py`、`test_install.py` 和 `skill-reviewer` 进行一致性/安全检查；独立 Review 不能由编写者自查代替。
- 真实项目仅只读盘点。**项目实际状态可能并发变化**，每个报告为观察快照，不表示获得清理锁。
- P0 不负责 GitHub PR 内容 Review、跨仓库编排、AI 并发锁、系统级通知、删除逻辑，也不保证旧项目全量自动发现。后续需求需重新确认阶段及权限。
