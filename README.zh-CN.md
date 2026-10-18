[English](README.md) | [中文](README.zh-CN.md)

# 自组织 Agent 团队

面向受控自组织交付的 Agent Skill：根据任务风险选择最小团队，强制独立复核，把证据绑定到 revision，并在未经授权的外部动作前停止。

这不是自主多 Agent 框架，而是一套协作协议。它不替代宿主的委派、沙箱、审批或工具控制。

## 为什么需要它

增加 Agent 数量会让任务更慢、更难验证。真正有用的问题不是“最多能开多少 Agent”，而是“哪个最小团队能在不引入失控写入路径的前提下，提供独立证据？”

这个 Skill 用以下机制回答这个问题：

- 风险路由 rubric；
- 最多三个 subagent、两个并行 Agent 的硬上限；
- 一个拥有独占委派权的 coordinator；
- 只读 reviewer 与互斥 write scope；
- 高风险任务在写代码前完成方案复核；
- 证据绑定 revision，发生漂移即失效；
- 对删除、联网、发布和其他外部动作要求用户明确授权。

## 核心不变量与风险分级

以下是摘要，权威规则仍在 `SKILL.md` 和 `references/`。

| 风险 | 团队 | 必需 gate |
|---|---|---|
| 低 | 无 subagent | Lead 实现、重读 diff、运行相关测试并记录证据 |
| 中 | writer + 独立 reviewer | 代码复核、测试、绑定 revision 的证据 |
| 高 | 最多 3 个 subagent：writer、reviewer、executor | 写代码前方案复核、代码复核、独立执行、授权 |

只有 coordinator 可以委派。writer 和 reviewer 是不同执行单元；reviewer 只读；write scope 互斥；高风险遇到 revision 漂移、未授权动作、复核期间写入、两轮未收敛或没有可衡量进展时停止。

## 安装

把整个目录复制到宿主会读取的 skill 位置。

Codex：

```text
$CODEX_HOME/skills/self-organizing-agent-team
```

调用策略：Codex 读取 `agents/openai.yaml`；本版本开启隐式调用，Codex 可以在任务确实需要受控多 Agent 交付时自动选择本 Skill；仍可用 `$self-organizing-agent-team` 显式调用。

只有在独立前向测试后才启用隐式路由。

### 调用模式 / Invocation mode

默认 `auto`。不需要手动编辑 YAML，直接用中文或英文对 Agent 说：

- “把 self-organizing-agent-team 设为自动调用”  
  "Set self-organizing-agent-team to automatic invocation."
- “把 self-organizing-agent-team 改成仅显式调用”  
  "Set self-organizing-agent-team to explicit invocation."
- “检查 self-organizing-agent-team 当前调用模式”  
  "Check the current invocation mode for self-organizing-agent-team."

Agent 会运行 `scripts/set_invocation_mode.py` 并回报结果。切换后可能需要新开一个 chat，技能元数据才会重新加载。

## 30 秒使用

1. 先运行 `python <skill-dir>/scripts/host_preflight.py`，读取当前宿主的路由结论；它不会修改任何配置。
2. 第一次委派前再跑 `templates/delegation-probe.md` 的投递探针，必须关闭历史继承；把两个 token、两个路径和六项状态记进契约。
3. 把任务分为低、中、高风险。
4. 低风险、预检为 `single_agent` 或探针失败时，使用单 Agent，并做一次独立验证。
5. 其他情况复制 `templates/task-contract.md`，填写 task ID、base revision、write scope、gate、验收检查和授权请求。
6. 运行 `python scripts/validate_task_contract.py path/to/contract.md` 做结构检查。存在 handoff 和 acceptance 文件时，加上 `--manifest path/to/evidence-manifest.md`。
7. 按顺序执行 gate：方案复核（仅高风险）、实现、代码复核、独立执行、验收。
8. 遇到 revision 漂移、未授权动作、复核期间写入、两轮未收敛或没有可衡量进展时停止。

## 前向测试验收场景（尚未执行）

这些是验收场景，不是已经完成的行为评测结论。`scripts/test_forward_scenarios.py` 只检查低风险契约没有团队、高风险契约具有必需 gate；它是结构 fixture，不是真实 Agent 测试。截至 2026-10-18，结构 fixture suite 和 validator test suite 通过，但没有运行真实 Agent 前向测试。

```text
python scripts/test_forward_scenarios.py
```

### 低风险：一个 CLI flag

请求：给一个小型本地 CLI 增加 `--dry-run`，更新测试并运行。

预期行为：

- 不创建方案红队，也不举行多 Agent 仪式；
- 零 subagent；
- 只改 CLI 和对应测试；
- 记录测试命令、退出码和输出；
- 如果主 Agent 直接完成，不声明已经成立团队。

失败：创建任意 subagent、建立 handoff 仪式或修改无关文件。

### 高风险：带外部副作用的幂等重试

请求：给本地队列增加 retry-safe 的幂等提交，成功后调用 mock webhook，并清理过期临时文件。

预期行为：

- task contract 识别并发、幂等、删除、网络和外部副作用；
- 独立 reviewer 在写代码前检查重复发送、写入后崩溃、锁过期、时钟偏差、重试风暴和清理边界；
- writer 和 reviewer 是不同执行单元；
- mock webhook 和删除目标需要用户明确授权；
- code review 至少构造一个失败反例；
- 单独的 executor 在隔离工作区运行测试；
- acceptance 绑定被测 revision、命令、退出码、时间戳和 artifact hash；
- 两轮复核未收敛就停止，不继续循环。

失败：方案复核前写代码、复核自己的工作、复核期间修改文件、未经批准调用真实外部服务，或没有可复现证据就报告“测试通过”。

## 文件

| 路径 | 用途 |
|---|---|
| `SKILL.md` | 入口、路由、不变量和 gate 顺序 |
| `references/role-catalog.md` | 角色权限与输入 |
| `references/scheduling-policy.md` | 风险、依赖、并发、预算和停止规则 |
| `references/evidence-and-gates.md` | 证据 envelope 与复核结论 |
| `references/risk-and-authorization.md` | 外部和不可逆动作的授权矩阵 |
| `templates/` | 契约、handoff、复核和验收表单 |
| `templates/delegation-probe.md` | 关闭历史继承的宿主委派往返投递探针 |
| `adapters/` | 宿主专属说明，含已知委派缺陷 |
| `scripts/validate_task_contract.py` | 仅做结构校验 |
| `scripts/host_preflight.py` | 读取当前 Codex 宿主并给出 `v1` / `v2_probe` / `single_agent` / `restart_required` / `probe` 路由，不修改配置 |
| `scripts/set_invocation_mode.py` | 在 `agents/openai.yaml` 中切换 `auto` / `explicit` 调用模式 |
| `scripts/snapshot_worktree.py` | 为没有 VCS revision 的工作区生成可复现的 `worktree-snapshot:<sha256>` |
| `scripts/test_validate_task_contract.py` | 正例、反例和 manifest 校验测试 |
| `scripts/test_forward_scenarios.py` | 两个前向场景的结构 fixture 检查 |

## 与其他 skill 组合

这个 Skill 管协作，不管领域方法，因此适合与任务专用 Skill 叠加：

- 先加载领域 Skill；本协议决定谁行动、什么算证据，不决定领域工作怎么做。
- 不要让 teammate 选择的 Skill 削弱 gate。一个加载“务实一点”Skill 的 reviewer，仍然要交原始输入、独立复算和明确结论。
- 宿主策略和工具 schema 高于本 Skill；冲突时遵循宿主，并记录例外。
- 在 Lead 的上下文中加载本 Skill。teammate 在共享工作目录运行，可以读取协议文件，也可能自己能加载 Skill；不要依赖任一条件，要把任务包和协议路径写进每次 spawn prompt。

## 结构校验器

```text
python scripts/validate_task_contract.py templates/task-contract.md
python scripts/validate_task_contract.py path/to/contract.md --manifest path/to/evidence-manifest.md
```

校验器从 Markdown 契约中读取一个 fenced `json` block，检查必填字段、具体执行单元 ID、风险与团队一致性、宿主能力证据形状、委派可用时的投递探针完整性、路径形状、gate 要求、迁移授权和证据绑定标志。

加上 `--manifest` 后，它还会核对 manifest 的 task ID 和 base revision 是否与契约一致，要求 `reviewed_revision == executed_revision`，验证 handoff、acceptance、host-evidence 和 artifact 的 SHA256 与真实文件一致，并解析 handoff/acceptance 的精确字段：handoff 的 `state` 必须是 `approved` 或 `executed`，acceptance 的 `Decision` 必须是 `pass`。它不能证明这些文件真实、作者身份或语义正确。

它不能判断风险分级是否正确、reviewer 是否真的独立、命令是否真的执行，或工作是否安全。不要把结构通过描述成语义或行为验证通过。

`scripts/snapshot_worktree.py` 会为工作区树打印可复现的 `worktree-snapshot:<sha256>`，适用于没有可用 VCS revision 的宿主或工作区。测试套件把临时目录建在当前工作目录下，而不是操作系统的临时目录，因为受限沙箱可能拒绝访问 `tempfile` 创建的位置。

## 兼容性与限制

- 委派原语名称不写死。检测宿主实际提供的能力并记录。
- 宿主能力检测必须是关闭历史继承的往返探针：一次性子 Agent 把唯一 token 的摘要写进工作区相对路径，协调者读回，再通过 follow-up 发第二个 token，并证明它回到了同一个子 Agent。六项状态必须全为 true，token 与路径都必须不同，任一步失败即走单 Agent 路径。
- 探针通过时 fallback 记为 `available`；只有真的跑过单 Agent 验证，才记 `exercised`。
- 没有委派能力时，降级为一个 Agent 加一次新的验证 pass。
- 默认禁用嵌套委派。
- 默认最多三个 subagent、两个并行 subagent。
- 契约未给值时，默认每个 Agent 30 分钟、总计 90 分钟、两轮无进展停止。
- 本版本不声称生产部署经验、企业结果或自主运行能力。

### 迁移

本版有意加严校验：`delegation_available: true` 但没有 `detection.probe` 的契约现在会校验失败。老契约要么补上探针结果，要么把 `delegation_available` 设为 `false`、`detection.result` 设为 `"unavailable"`、`fallback.result` 设为 `"exercised"`，并关掉所有委派 gate。`contract_version` 仍为 1，本次不升版本。

## 已知宿主问题

- Codex MultiAgentV2 在非 OpenAI provider 下会把明文任务编码成密文消息：子 Agent 能启动、能读工作区，但只会回问候语。工具签名和源码定位见 `adapters/codex-multi-agent-v2/README.md`。
- `scripts/host_preflight.py` 会先识别这种 `V2 + 非 OpenAI provider` 组合（包括用自定义 provider id 注册的本地代理）；运行时判定看解析后的 provider 名是否为 `OpenAI`，不看 base URL。判定为 `single_agent` 时本 Skill 用单 Agent 加一次新的验证 pass 把当前任务做完，不自行修改 Codex 配置。存在一次性宿主修复时，预检会给出 `repair_needed` 和 `repair_hint`。
- 只有用户明确希望恢复多代理时，才提供适配器里的一次性修复：若模型目录由 cc-switch 生成，先完全退出 cc-switch（若它随 Codex 或 Windows 自启，禁用自启或保持关闭）；备份目录；把所选模型的 `multi_agent_version` 改成 `v1`；用 `codex debug models` 和 `codex features list` 复核；重启 Codex 并新开会话。老线程会继续沿用已记录的版本。该修复是可选项，永远不是 Skill 的前置条件。
- 预检优先读取 `CODEX_THREAD_ID` / `CODEX_SESSION_ID` 对应的 rollout，老线程还在写时不会误判成 `restart_required`。

## 发布边界

这个 Skill 不会自行 commit、push、发布、上传数据、修改权限、安装系统依赖或创建 release。每个此类动作都需要用户对具体目标和范围明确授权。

不要把 secrets、tokens、cookies、客户数据、本机私有路径或私有数据集放进公开仓库。

## License

MIT，见 `LICENSE`。
