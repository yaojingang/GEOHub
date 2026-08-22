# GEOHub 意图识别与 Skill 编排升级实施报告

版本：`0.6.0`
日期：2026-08-22
产品状态：Experimental
协议兼容：Artifact Bus `1.0.0` 保持稳定，工作流状态升级至 `2.0.0`

## 1. 实施结论

本轮升级完成了从“路由结果”到“可验证任务计划与可恢复执行”的完整控制链：

`自然语言请求 → 显式意图决策 → Capability Card 校验 → TaskPlan → 持久化工作流 → 审批/外部证据门 → Skill 执行 → checkpoint`

核心安装继续使用确定性词法路由。本地 FastEmbed 缓存提供可选语义增强，模型缺失时自动保留词法基线。发布能力维持 `planned`，其空执行器和审批边界阻止外部写入授权。

## 2. 开源项目借鉴与 GEOHub 落点

| 对标能力 | 参考项目 | GEOHub 0.6 落点 | 采用边界 |
| --- | --- | --- | --- |
| 混合意图路由 | Semantic Router | 正负样例、局部语义评分、阈值版本、OOD 拒答、歧义澄清 | 语义模型仅从显式准备的本地缓存加载；人工标注完成前保留锁定状态 |
| 持久化图执行 | LangGraph | 有序 DAG、checkpoint、interrupt、resume、重试、人工审批、外部证据门 | 核心运行时保持轻量，不增加完整框架依赖 |
| 能力目录 | Backstage | Registry Capability Cards、生命周期、输入输出、权限、副作用、执行策略 | Registry 继续作为唯一能力事实源 |
| Skill 包规范 | Agent Skills | lean `SKILL.md`、manifest、interface、渐进式资源加载、跨目标打包验证 | GEOHub 的 Artifact Bus 与安全边界继续生效 |
| 类型与 Schema | Pydantic 方法论 | JSON Schema 加跨字段语义校验，TaskPlan 和状态均有确定性摘要 | 当前依赖维持 `jsonschema`，避免双重模型源漂移 |
| 运行与证据链 | MLflow / OpenLineage | plan digest、run lineage、artifact digest、checkpoint checksum、provenance | 不声明缺少独立 builder 证明的可信等级 |

完整来源与选择依据见 [世界级对标来源台账](research/world-class-benchmark-sources-2026-08-12.md)。

## 3. 分阶段交付

### P0：执行授权收口

- 路由统一输出 `single_skill`、`workflow`、`clarify`、`abstain`、`unavailable`。
- OOD、全量否定、模糊请求和计划中能力默认关闭执行授权。
- 373 条历史行为通过迁移台账治理；63 条变化均保留原 Skill/工作流选择，只收紧 `runnable`。

### P1：Capability Cards

- 8 条 Registry 路由具备正负样例、typed artifacts、permission、side effects、preconditions、execution 和 routing threshold。
- 新增契约校验器，检查 Schema、manifest、interface 与 Registry 漂移。
- FastEmbed 作为 `semantic` 可选依赖；准备阶段允许联网，运行阶段采用 local-files-only。

### P2：混合路由与评测

- 语义评分以 clause 为单位补充词法证据，词法路由始终可用。
- 新增 600 条分组数据集，覆盖单意图、近邻、多意图、歧义和 OOD。
- 公开 lexical 基线的 macro Skill F1 为 `0.6392`，OOD false-runnable rate 为 `0.0`，clarify recall 为 `0.0`。
- 当前数据标签状态为 `pending-human-review`，语义晋级门保持锁定。

### P3：TaskPlan

- 新增 TaskPlan Schema、确定性 `plan_id` 与 `plan_digest`。
- 节点记录依赖、输入绑定、预期输出、权限、超时、重试次数与幂等声明。
- 编译器只从依赖祖先选择输出，运行时再次校验绑定来源、Schema 和 required inputs。
- `route --plan-output` 采用原子写入并拒绝覆盖既有计划。

### P4：可恢复编排

- 工作流状态升级至 `2.0.0`，绑定 TaskPlan 摘要和节点幂等键。
- 同一状态文件的执行通过独占锁串行化；Skill 进程具备硬超时、输出捕获上限、artifact 数量与大小上限。
- 重试仅用于声明幂等且发生超时的节点，预算耗尽后保持失败边界。
- v1 迁移先验证 checkpoint，再创建 sibling backup，随后原子写入 v2 状态。
- `strategy-observation-loop` 依次执行策略、人工审批、发布凭据、观察包和测量。

## 4. 深审中修复的问题

| 风险 | 修复结果 |
| --- | --- |
| 工作流节点可能绑定到先出现但无依赖关系的分支输出 | 绑定候选限定为依赖祖先，并在运行时执行跨字段校验 |
| 手工构造的 active/planned 状态可能绕过编译权限 | TaskPlan 编译对 Skill、workflow、entry 和 executor 逐项 fail-closed |
| 子进程提前关闭输出流后可能绕过硬超时 | 等待进程退出时继续使用剩余 deadline，并在超时后终止整个进程组 |
| 子进程 stdout/stderr 与 artifact 缺少资源上限 | 增加捕获、文件数量、目录条目和单文件大小边界 |
| 状态中的输出根路径被修改后可能扩大写入范围 | 每次执行前重新解析并验证输出根仍位于状态目录内 |
| 输入或外部证据在状态创建后被替换 | 状态记录 SHA-256；输入绑定和每次 durable state 加载均重新计算并比对 |
| 符号链接目录可绕过非普通产物检查 | 产物遍历先执行 `lstat` 与 symlink 拒绝，再区分目录和普通文件 |
| 已安装源码包未覆盖 TaskPlan 与 workflow CLI | 安装模拟新增 `route --plan-output` 和完整单节点 workflow smoke |
| README 指向未进入源码 ZIP 的实施报告 | 稳定实施报告及来源台账迁入 `docs/`，包验证增加 README 本地链接闭合检查 |
| 外部 Git 索引环境可能污染独立仓库打包 | 独立仓库操作清理 Git 目录、工作树、对象库和索引覆盖变量；治理摘要覆盖全部 `scripts/` |
| checkpoint、current step、依赖完成状态可出现跨字段矛盾 | 新增工作流状态语义校验和幂等键复算 |
| 非幂等或确定性契约错误可能进入自动重试 | 自动重试仅接受 `TimeoutError`、幂等声明和剩余预算同时成立 |
| 审批拒绝缺少明确失败边界 | 状态记录 `approval-rejected`、reviewer 和当前 gate |
| abort 与执行可能竞争写状态 | abort 与 continue 共用执行锁 |

## 5. 验收状态

- Capability contract：通过。
- 确定性 router/output eval：通过；precision `1.0`，recall `1.0`，contract compliance `1.0`，fabricated citations `0`。
- 373 条历史路由迁移：通过。
- TaskPlan、工作流状态、CLI 生命周期、外部证据完整链：通过。
- package、provenance、SBOM、安装模拟和全量测试由 `scripts/verify_all.py` 统一执行。
- Production Readiness：保持 blocked；Experimental 发布通道可用。

## 6. 后续晋级条件

1. 人工复核至少 20% 的 600 条路由样本，并达到 Cohen's kappa `≥ 0.80`。
2. 使用冻结的本地语义模型与独立 holdout 完成阈值校准，重点改善 clarify recall 和 `geo` 路由 F1。
3. 补充进程崩溃、磁盘满、1000 节点压力和多进程恢复测试证据。
4. 获取真实平台观察许可与独立盲评，形成策略效果和可见度结果证据。
5. 执行 CI provenance attestation、法律审查与生产可观测性门禁。

以上条件进入证据库后，再评估从 Experimental 向 Production 候选晋级。
