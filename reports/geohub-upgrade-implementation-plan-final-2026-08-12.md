# GEOHub 世界级能力升级最终实施方案

状态：**最终版，待确认后执行**  
计划版本：`2.0 Final`  
基线版本：GEO SEO Hub `0.2.0 Experimental`  
基线提交：`9c21f09ee30998172267eebefcd114b7e6438134`  
计划周期：13 周，约 90 个自然日  
建议执行方式：10 个可独立合并、可独立回滚的实施包  
依据：[GEOHub 世界级对标审计](./geohub-world-class-benchmark-2026-08-12.html) 与 [一手来源证据账本](./geohub-world-class-benchmark-sources-2026-08-12.md)

## 1. 最终建议

建议批准完整的 90 天升级计划，并在第 4 周、第 9 周、第 13 周设置三个继续投入门槛。90 天交付目标锁定为 `0.5.0 Experimental` 和一份 Production Readiness Review。产品状态只由证据门槛决定，日历日期不触发成熟度升级。

本轮升级采用加法式模块化：保留现有四个 Skill、CLI、Artifact Bus `1.0.0` 和公开 Python 入口，在内部逐步建立控制、可信、领域智能、质量运营四个平面。现有 `router.py`、`discover.py`、`diagnose.py`、`content.py` 继续承担兼容入口，新模块通过薄封装接入。每个新能力先以影子、离线或显式启用方式运行，通过评测后再改变默认行为。

计划完成后，GEOHub 应具备以下能力：

1. 用真实模型输出、真实引擎观察和盲评结果证明输出质量。
2. 用结构化运行谱系追踪 route、skill、artifact、metric 与 review。
3. 用研究型查询发现、分层诊断、证据化内容流水线和 MCDA 提升领域能力。
4. 用测量、策略、保真门与策略记忆形成可复盘的优化反馈。
5. 用 Skill IR、Output Lab、Review Studio、信任报告与发布来源证明维持 Library 级工程标准。

### 1.1 本轮 Review 已修正的缺口

| 原计划缺口 | 可能后果 | 最终版处理 |
| --- | --- | --- |
| 64 人日塞满 13 周 | 没有审查、返工和证据采集缓冲 | 核心工程压缩为 54 人日，预留 10 人日评审和风险缓冲 |
| `--profile` 与 content artifact 的 `profile` 重名 | CLI、输入契约和内容模式容易混淆 | 统一改为 `--execution-mode`，取值为 legacy、deterministic、research、provider |
| baseline 没有定义隔离方式 | 当前代码可能污染基线，质量增量失真 | 用已发布 `0.2.0` wheel 或基线提交的隔离环境生成 baseline |
| GEO 引擎样本只要求 5 个 query | 可以做 smoke，无法支撑效果结论 | P0 保留 smoke；Promotion 使用 30 个分层 query、重复观察和置信区间 |
| 策略候选缺少真实曝光路径 | 未发布候选无法得到真实引擎 metric delta | 工作流加入 `awaiting_external_observation`，由用户发布后回填观察包 |
| workflow 恢复能力排在策略之后 | P2 实施包存在反向依赖 | checkpoint、resume 和人工确认前移到控制平面实施包 |
| 契约来源没有定案 | JSON Schema、手写验证与类型可能继续漂移 | 现阶段以 JSON Schema 为唯一规范，增加 typed accessor 与双向一致性测试 |
| 盲评缺少防泄漏和标注一致性 | 位置偏差、judge 偏差和 holdout 污染 | 引入随机顺序、答案密钥隔离、双人抽检与 reviewer agreement |
| 观察数据没有留存与删除规则 | 回答正文、URL 和客户信息可能长期滞留 | 增加数据分级、默认保留期、删除命令与 package exclusion |
| 缺少 owner、reviewer 和决策责任 | 证据采集与 Promotion 容易无人负责 | 增加 RACI、证据负责人和签字规则 |
| 包装、文档、迁移与许可证工作不完整 | source、wheel、ZIP、Skill 包和文档可能不同步 | 新增专门的兼容与发行实施包，覆盖 pyproject、CI、docs、notices 和安装烟测 |
| `0.5.0 Production Candidate` 标签过早 | 时间计划可能被误读成质量承诺 | 改为 `0.5.0 Experimental`，另行出具 Production Readiness Review |

## 2. 批准范围

### 2.1 本计划建设的内容

- 保留并升级 `geo`、`geo-discover`、`geo-diagnose`、`geo-content`。
- 在 P0 阶段激活 `geo-measure` 的“文件导入与测量”模式。
- 在 P2 阶段激活 `geo-strategy` 与 `geo-knowledge`。
- 建立真实 Output Eval、盲评裁决、GEO 引擎观察基准和 claim 级指标。
- 建立 metadata-only 运行谱系、采用信号和漂移报告。
- 建立语义路由影子评分、可恢复工作流状态与人工确认点。
- 建立 HyDE 风格发现策略、Lighthouse 风格诊断架构、STORM 风格内容阶段和 MCDA 排名。
- 建立 MAGEO 风格候选生成、保真评估、早停和策略记忆。
- 建立轻量品牌事实图谱、实体关系、冲突与时效治理。
- 建立 SBOM、构建来源证明、包哈希与独立验证命令。
- 建立版本化 benchmark protocol、数据保留策略、RACI 和架构决策记录。
- 同步 source checkout、wheel、社区 ZIP、provider Skill ZIP 与 Codex/Claude adapter。

### 2.2 本计划明确排除的内容

- `geo-publish` 保持 `planned`，90 天内不连接 CMS、社交平台或自动发布接口。
- 不自动登录或抓取 ChatGPT、Perplexity、Gemini、Claude 等消费级网页。
- 不替用户发布候选页面。真实策略效果只接受用户完成发布后回填的合规观察包。
- 不把客户原始提示词、回答正文、URL、正文内容或凭证写入遥测。
- 不引入常驻数据库、消息队列、独立 Web 服务或第二种服务端语言。
- 不承诺实时搜索量、SERP 排名、转化率、AI 平台份额或商业效果。
- 不直接复制对标项目的整体框架、界面样式、依赖栈或目录结构。
- 不把公开 smoke cases 当作私有 holdout，也不把同一模型的自评结果作为唯一质量证据。
- 不新增 Windows 支持声明。本计划继续以 CI 已覆盖的 Linux 和 macOS 为发布环境。
- 不在证据门槛达成前把产品状态从 `Experimental` 提升为 `Production`。

## 3. 当前基线与升级前提

| 维度 | 当前证据 | 升级判断 |
| --- | --- | --- |
| 路由 | 373 个用例，报告 precision 与 recall 均为 `1.0000` | 保留词法路由为默认基线，语义能力先跑影子模式 |
| Skill 触发 | 27 个触发用例，合规率 `1.0000` | 新 Skill 必须补齐 should-trigger、should-not-trigger、near-neighbor |
| 输出契约 | 20 个确定性用例，契约合规率 `1.0000` | 当前主要证明文件与边界，新增真实内容质量证据 |
| 测试 | 483 收集，482 通过，1 跳过 | 所有阶段保持现有套件无回归 |
| 安全 | 文件 no-follow、SSRF、响应大小、超时、重定向与原子发布均有覆盖 | 安全模块保持共享底座，不在领域模块重复实现 |
| Artifact Bus | 协议 `1.0.0`，文件集校验与原子 rename | 保持协议号；新增能力使用 sidecar artifacts |
| 模型证据 | `missing evidence` | P0 首要工作 |
| 人工盲评 | pack 已生成，裁决待录入 | P0 首要工作 |
| 引擎效果 | 无真实平台基准 | 通过人工或合规 API 导入观察包解决 |
| 采用与漂移 | 四个 Skill 均无遥测样本 | 建立 metadata-only 本地聚合 |

### 3.1 负载前提

本计划假设 GEOHub 的首要使用形态仍是本地 CLI、Skill 包和离线 Artifact Bus，单次任务规模以几十个查询、几十个来源和数百条 claim 为主。多租户在线服务需要单独设计持久化、隔离、并发、费用控制和权限系统，本计划中的本地 sidecar 与文件聚合只承担未来迁移输入。

### 3.2 最脆弱假设

本计划假设可以获得一小批合规的真实引擎观察与人工盲评时间。如果 90 天内仍缺少这些输入，代码与确定性评测可以按阶段合并，产品状态继续保持 `Experimental`，策略记忆不得晋级，Production Readiness Review 输出 `blocked by missing evidence`。

## 4. 架构决策

### 4.1 四平面、十五模块

```text
用户请求 / CLI / Skill 调用
            |
            v
+----------------------- Control Plane -----------------------+
| geo-registry ----> geo-router ----> geo-workflow            |
+----------------------------+--------------------------------+
                             |
                             v
+------------------------ Trust Plane -------------------------+
| geo-contracts -> geo-artifacts -> geo-evidence -> geo-security|
+----------------------------+---------------------------------+
                             |
                             v
+--------------------- Intelligence Plane ---------------------+
| geo-discovery -> geo-audit -> geo-content -> geo-optimize    |
|                                      |              |         |
|                                      +-> geo-knowledge        |
+----------------------------+---------------------------------+
                             |
                             v
+----------------------- Quality Plane ------------------------+
| geo-evals ------> geo-observability ------> geo-release      |
+--------------------------------------------------------------+
```

| 平面 | 模块 | 对标机制 | GEOHub 目标职责 | 对外形态 |
| --- | --- | --- | --- | --- |
| 控制 | `geo-registry` | Backstage Catalog | 能力、所有者、生命周期、依赖、状态与产物目录 | 内部模块与 Registry |
| 控制 | `geo-router` | Semantic Router | 词法主路由、语义影子评分、阈值校准与歧义说明 | `geo` Skill |
| 控制 | `geo-workflow` | LangGraph | 状态、checkpoint、恢复、人工确认与失败边界 | 内部模块 |
| 可信 | `geo-contracts` | Pydantic 的契约纪律 | JSON Schema 唯一规范、typed accessor、验证与序列化一致性 | 内部模块 |
| 可信 | `geo-artifacts` | MLflow Runs | 运行、产物、哈希、状态、降级与回滚 | Artifact Bus |
| 可信 | `geo-evidence` | OpenLineage | claim、source、run、artifact 与 metric 谱系 | sidecar artifacts |
| 可信 | `geo-security` | OWASP SSRF | 文件、网络、凭证、依赖和包边界 | 共享底座 |
| 智能 | `geo-discovery` | HyDE | 多策略查询生成、聚类、新颖度、覆盖与证据 | `geo-discover` Skill |
| 智能 | `geo-audit` | Lighthouse | gatherer、audit、score、report 四层 | `geo-diagnose` Skill |
| 智能 | `geo-content` | STORM | research bundle、outline、draft、polish、claim map | `geo-content` Skill |
| 智能 | `geo-optimize` | MAGEO | preference、candidate、fidelity、measure、memory、early stop | `geo-strategy` Skill |
| 智能 | `geo-knowledge` | GraphRAG | 事实、实体、关系、社区摘要、local/global 查询 | `geo-knowledge` Skill |
| 质量 | `geo-evals` | Inspect AI 与 Ragas | task、runner、scorer、judge、blind review、failure taxonomy | CLI 与报告 |
| 质量 | `geo-observability` | OpenTelemetry | trace、span、metric、cost、drift、adoption | 本地 sidecar 与可选 exporter |
| 质量 | `geo-release` | SLSA | SBOM、provenance、sign、verify、promotion | 发布脚本与报告 |

### 4.2 模块化边界

- 顶层 Skill 只对应用户可理解的重复任务，不为每个内部模块创建 Skill。
- `SKILL.md` 保持 Library 级 `1300` 初始加载 token 预算。
- 领域方法进入 `references/`，确定性逻辑进入 `scripts/` 或 `src/`，证据进入 `reports/`。
- 每个活跃 Skill 必须有 Skill IR、接口、manifest、触发评测、输出评测、trust report 与 Review Studio。
- 新模块通过 Python Protocol 或小型数据类交换信息，禁止内部模块直接读取其他模块的私有文件。
- 现有公开模块继续作为兼容 façade，至少保留到 `1.0.0`。
- `schemas/*.schema.json` 是 `0.x` 阶段的唯一契约规范。Python typed accessor、手写业务校验、Skill output contract 与生成样例都要通过同一组 Schema conformance tests。
- 本计划不直接引入 Pydantic。若未来要用代码生成 Schema，需要单独 ADR、兼容性报告与包体积评测。

### 4.3 Artifact Bus 与协议

- Artifact Bus `protocol_version` 在本计划内保持 `1.0.0`。
- 新增 `run-lineage.json`、`metric-report.json`、`claim-map.json` 等 sidecar，并列入 `run-manifest.json.artifacts`。
- 新 sidecar 使用自己的 `schema_version: 1.0.0`。
- 只有新增必填 manifest 字段或改变既有字段语义时，才启动 Artifact Bus `2.0.0` 设计。
- 每次执行继续使用 staging 目录、精确文件集校验、原子 rename 与单 run 目录回滚。

### 4.4 执行模式与默认行为

- `legacy` 保留 0.2.0 行为，作为算法回归和紧急回滚入口。
- `deterministic` 是 v2 晋级后的默认执行模式，禁止网络访问。
- `research` 消费用户批准并已快照的来源，执行器自身不扩展网络范围。
- `provider` 需要显式参数与已配置凭证，所有模型、引擎、时间、token、费用和失败都进入评测证据。
- CLI 统一使用 `--execution-mode legacy|deterministic|research|provider`。content artifact 现有 `profile` 字段继续表示内容模式，两者含义分开。
- 每个 v2 executor 先以 `legacy` 为默认值。其公开、私有与对抗评测全部通过后，在发布 PR 中把默认值切到 `deterministic`。
- 语义路由只写影子评测结果，P1 门槛通过前不改变真实路由。
- 排名与策略输出始终保留原始分量、缺失值、敏感性和置信边界。
- 可观测 sidecar 中的 duration、cost、created_at 等易变字段不进入 `semantic_digest`。确定性门槛比较语义 payload digest，不比较完整 run 目录字节。

## 5. 公共接口与实体变化

预计影响 70 个以上文件，新增 3 个活跃 Skill、10 个 Schema、4 个内部包、5 个 CLI 能力和 5 份 ADR。计划通过 10 个实施包控制审查范围，不新增常驻服务。

### 5.1 新增 CLI

| 命令 | 计划版本 | 作用 | 默认网络 |
| --- | --- | --- | --- |
| `geo-seo-hub eval` | `0.3.0` | 执行真实输出评测、评分与盲评包生成 | 关闭 |
| `geo-seo-hub measure` | `0.3.0` | 导入引擎观察包并生成可见性基线 | 关闭 |
| `geo-seo-hub data-retention` | `0.3.0` | 预览并执行 GEOHub 运行数据保留策略 | 关闭 |
| `geo-seo-hub strategy` | `0.5.0` | 生成候选策略、保真检查与复盘计划 | 关闭 |
| `geo-seo-hub knowledge` | `0.5.0` | 构建与查询证据化品牌事实图谱 | 关闭 |

现有 `route`、`discover`、`diagnose`、`content` 的参数、返回结构和入口保持兼容。`--execution-mode` 是可选参数；参数缺失时使用该版本已经晋级的安全默认值。`--help`、JSON stdout、JSON stderr、退出码 `0/2` 和非交互执行契约继续保持。

### 5.2 Registry、打包与安装实体

以下 source-of-truth 必须在对应实施包同步更新：

- `registry/skills.yaml` 与 `registry/skills.schema.json`：新增 Skill、workflow 和状态。
- `pyproject.toml`：新增 Schema、Skill、references、scripts、agents 与 optional extras 的 data-files allowlist。
- `scripts/package.py`、`scripts/verify_packages.py`、`scripts/install_simulation.py`：验证每个新增 Skill 的 provider identity、entrypoint 与安装后 CLI。
- `.github/workflows/ci.yml`：Linux Python 3.11-3.14 全矩阵；macOS Python 3.11 执行 package 与 install simulation。
- `THIRD_PARTY_NOTICES.md`：只记录实际引入的依赖、代码或素材及其许可证。
- `docs/architecture.md`、`docs/artifact-contract.md`、`docs/evaluation-policy.md`、`docs/security.md`、`docs/installation.md` 与迁移说明：随行为变化同步更新。

新增 optional extra 只有在代码出现真实 import 且 CI 安装验证通过后才能进入 `pyproject.toml`。预留依赖、未使用 SDK 和浮动 Git 依赖均不进入发布包。

### 5.3 新增 Schema

| 文件 | 核心字段 | 负责模块 |
| --- | --- | --- |
| `schemas/eval-task.schema.json` | task、input_files、variants、rubric、tags、judge_policy | geo-evals |
| `schemas/eval-result.schema.json` | runs、scores、failures、usage、review_status | geo-evals |
| `schemas/engine-observation-bundle.schema.json` | engine、model、query、answer、citations、observed_at、locale | geo-measure |
| `schemas/visibility-report.schema.json` | raw_components、aggregate、coverage、uncertainty、gaps | geo-measure |
| `schemas/run-lineage.schema.json` | trace_id、run_id、parent_run_id、stages、input_hashes、artifact_hashes | geo-observability |
| `schemas/claim-map.schema.json` | claim_id、source_ids、support_status、confidence、location | geo-content |
| `schemas/workflow-state.schema.json` | workflow_id、version、current_step、status、checkpoints、approval | geo-workflow |
| `schemas/publication-handoff.schema.json` | candidate_digest、deployment_requirements、observation_window、query_panel | geo-strategy |
| `schemas/strategy-memory.schema.json` | context_signature、intervention、fidelity、metric_delta、promotion | geo-optimize |
| `schemas/knowledge-graph.schema.json` | entities、relations、communities、source_ids、validity、conflicts | geo-knowledge |

### 5.4 新增顶层 Skill

| Skill | 激活条件 | 输出 | 近邻排除 |
| --- | --- | --- | --- |
| `geo-measure` | P0 真实观察导入、指标与基线门槛通过 | visibility report、baseline、evidence、quality、lineage、manifest | 页面结构诊断、内容生成、自动平台抓取 |
| `geo-strategy` | P2 至少有一份测量基线与保真规则 | candidate strategies、fidelity report、experiment plan、strategy memory | 自动改稿、自动发布、无基线战略判断 |
| `geo-knowledge` | P2 图谱契约、冲突与时效门槛通过 | knowledge graph、query result、evidence、quality、lineage、manifest | 通用 RAG 平台、无来源事实补全 |

`geo-publish` 继续返回 `planned`，最近可用能力保持 `geo-content`。

## 6. 评测、测量与数据治理协议

### 6.1 Baseline 如何冻结

质量增量必须比较两个隔离运行环境：

- baseline 环境安装 `0.2.0` 的已验证 wheel。该 wheel 不可用时，从基线提交 `9c21f09ee30998172267eebefcd114b7e6438134` 在 detached worktree 构建 wheel。
- candidate 环境安装当前 PR 构建的 wheel。
- 两个环境使用同一输入快照、execution mode、provider 配置、随机种子、时间预算和 judge rubric。
- baseline wheel digest、candidate wheel digest、Python 版本、操作系统和依赖锁定摘要进入 `eval-result.json`。
- 当前工作区源码不能直接充当 baseline，避免 candidate import、环境变量或未跟踪文件污染对照组。

确定性输出比较 `semantic_digest`。该摘要排除 created_at、duration、cost、trace ID 和绝对输出路径，保留所有会影响业务含义、证据、排序与分数的字段。

### 6.2 Eval 数据分层与防泄漏

| 数据层 | 存放位置 | 用途 | 是否进入发布包 |
| --- | --- | --- | --- |
| public smoke | `evals/quality/public/` | 开发反馈、契约与快速回归 | 否，保留在 source repo |
| adversarial | `evals/quality/adversarial/` | 越界、提示注入、证据缺失与近邻 | 否，保留在 source repo |
| private holdout | `GEOHUB_PRIVATE_EVAL_ROOT` | Promotion 与防过拟合 | 否，不进入 Git、wheel、ZIP 或报告正文 |
| real observation | 评测负责人批准的文件包 | GEO 引擎测量 | 否，只保存脱敏摘要与 digest |

`GEOHUB_PRIVATE_EVAL_ROOT` 是唯一新增的本地评测路径环境变量。它只服务确有 private holdout 的 reviewer；普通开发和 CI 无需配置。报告保存 case ID、输入 digest、分数和失败分类，不保存 private prompt、客户正文或身份信息。

盲评规则：

- variant 顺序按加密安全随机源打乱，answer key 单独保存。
- reviewer 在提交决定前不能访问 answer key、执行日志中的 variant 身份或生成模型标签。
- 至少 `20%` 的 pair 由第二名 reviewer 复核。
- 双人复核子集报告原始一致率与 Cohen's kappa。kappa 低于 `0.60` 时，rubric 需要校准，相关人审门槛保持 warn。
- 同一模型可以参与生成或 judge 其中一个角色。公开质量结论需要独立 judge 或人审支持，单模型自评只算辅助证据。
- judge 结果必须保留 rubric version、judge provider/model、prompt digest、position order 与原始评分分量。

### 6.3 GEO Benchmark Protocol `1.0`

P0 的 5-query 数据集只验证采集、解析和指标计算。任何公开效果结论必须使用 Promotion 数据集：

- 至少 30 个 query，覆盖品牌、品类、比较、评估、行动五类意图，每类至少 6 个。
- 每个 query 在每个 engine 上至少重复 3 次，降低单次生成波动。
- baseline 与 candidate 在同一 locale、地区、登录状态、会话状态和 24 小时时间窗口内采集。
- query 顺序随机化；采集协议记录 engine、可见 model 名、时间、locale、session policy、collection method 与 collector。
- baseline 和 candidate 使用同一 query panel version。任何 query 改动都生成新的 panel version。
- 每条回答保留原始快照 digest、引用 URI 规范化结果和解析告警。真实正文按数据保留策略管理。
- 报告输出 query 级原始分量、engine 分层结果、均值或中位数、bootstrap 置信区间和 effect size。
- 样本量不足时只输出描述性统计，不输出显著提升结论。
- 引擎间指标不能直接相加成一个无分层总分。跨引擎摘要必须同时展示各引擎结果和权重来源。

采集只允许 `manual_export`、`approved_api`、`recorded_fixture`。采集负责人需要确认服务条款、账号权限和数据使用范围。需要绕过登录、验证码、反自动化或地域限制的数据拒绝进入 accepted evidence。

### 6.4 策略真实效果如何回填

GEOHub 本轮不执行发布。策略工作流分成两个独立时段：

```text
baseline observation
        |
        v
diagnose -> strategy -> candidate -> fidelity
                                  |
                                  v
                    awaiting_external_publication
                                  |
                  用户发布或部署候选页面
                                  |
                                  v
                    awaiting_external_observation
                                  |
                     导入 post-change observation
                                  |
                                  v
                    measure -> compare -> memory decision
```

- 候选通过 fidelity 后，工作流输出 `publication-handoff.json`，状态变为 `awaiting_external_publication`。
- 用户在 GEOHub 外完成发布，记录 publication URI、时间和版本 digest，再显式恢复工作流。
- 达到观察窗口后，用户导入 post-change observation bundle。
- baseline 与 post-change query panel、engine、locale 和采集协议不一致时，只输出不可比说明。
- 只有可比观察显示正向效果且 fidelity 无下降时，strategy memory 才能标记 `promoted`。
- 没有真实发布和 post-change observation 时，candidate 只能标记 `offline-approved`，不得描述为 GEO 效果提升。

### 6.5 数据分级、保留与删除

| 等级 | 内容 | 默认保留 | 处理规则 |
| --- | --- | ---: | --- |
| L0 公共元数据 | Skill ID、版本、状态、时长、hash、失败分类 | 365 天 | 可进入聚合报告 |
| L1 评测摘要 | 分数、rubric、provider/model、token、cost | 180 天 | 禁止包含正文和凭证 |
| L2 回答与来源快照 | engine answer、citation、页面正文、query text | 30 天 | 本地加权限保存，不进入 package 或 telemetry |
| L3 私有客户材料 | 客户 brief、内部来源、身份和业务信息 | 用户指定；默认 7 天 | 只在明确输入范围内处理，默认不进入共享 eval |
| Secret | API key、token、cookie、签名材料 | 0 天 | 只在进程环境或 CI secret 中使用，从不落盘 |

新增 `geo-seo-hub data-retention --runs-root build/runs --apply-policy`，只处理策略明确覆盖且超过保留期的 GEOHub run artifacts。默认输出 JSON dry-run；`--confirm` 只把目标原子移动到 runs root 内的 `.geohub-trash/<batch-id>/`，同时生成 recover manifest。进入 trash 满 7 天后，`--purge-batch` 加第二次 `--confirm` 才执行永久删除。所有阶段复用 no-follow、bounded-root、精确目标和同文件系统校验。该命令属于安全 sink，进入独立测试、CLI 审查和安装后烟测。

### 6.6 角色与签字责任

| 工作 | Accountable | Responsible | Consulted | 必须留下的证据 |
| --- | --- | --- | --- | --- |
| 架构与范围 | 仓库 owner | 主维护者 | GEO 领域 reviewer | ADR 与批准记录 |
| 评测实现 | 主维护者 | 实现者 | 安全 reviewer | 测试、eval result、failure taxonomy |
| 引擎观察采集 | GEO 评测负责人 | 指定 collector | 法务或条款 reviewer | collection manifest、许可范围、digest |
| 人工盲评 | GEO 评测负责人 | 两名 reviewer | 主维护者 | decisions、agreement、rubric version |
| 隐私与安全 | 仓库 owner | 安全 reviewer | 实现者 | trust report、privacy scan、waiver |
| Production Promotion | 仓库 owner | release reviewer | 领域、安全、维护者 | Production Readiness Review 与签字 |

一个人可以承担多个角色，但同一评测 pair 的生成者不能同时作为唯一 reviewer。Production Promotion 至少需要仓库 owner、GEO 领域 reviewer 和安全 reviewer 三项明确同意。

## 7. 90 天实施路线

### 7.1 关键依赖与并行窗口

| 实施包 | 必须先完成 | 可并行工作 | 退出结果 |
| ---: | --- | --- | --- |
| 1 Output Eval Lab | 无 | reviewer 排期、private holdout 准备 | 可复现 baseline/candidate 评测与盲评包 |
| 2 geo-measure | 包 1 的评测结果契约 | 合规 observation source 审批 | 可验证的文件导入式 GEO 测量 |
| 3 lineage / retention | 包 1-2 的 run 与 metric 字段 | 隐私审查、删除演练 | 可审计谱系和可恢复保留策略 |
| 4 control plane | 包 3 的 lineage 契约 | route confusion case 扩充 | 可恢复 workflow 与语义 shadow |
| 5 discovery v2 | 包 4 | 与包 6 并行 | 多策略发现与 gold-label 质量证据 |
| 6 diagnosis v2 | 包 4 | 与包 5 并行 | 分层 audit catalog 与可重算评分 |
| 7 content v2 / MCDA | 包 5-6 | 内容 fixture 与人审准备 | claim map、阶段化内容与可解释排名 |
| 8 strategy / knowledge | 包 2-4、7 | 外部 publication handoff 准备 | 可复盘策略循环与证据图谱 |
| 9 compatibility / docs | 包 1-8 的公共实体冻结 | 许可证核对 | source、wheel、归档和文档一致 |
| 10 provenance / readiness | 包 9 | CI attestation 预演 | 可验证来源与最终 Readiness 决策 |

包 5 与包 6 是唯一计划内代码并行窗口。真实 observation、盲评、许可证审查和 CI 身份准备作为证据轨持续推进；它们不绕过包之间的契约依赖。

### 里程碑 A：可信质量基线，Week 1-4，P0

目标版本：`0.3.0 Experimental`  
核心工程：17 人日；证据采集与评审缓冲：3 人日  
继续投入门槛：真实输出、真实观察、盲评和运行谱系均能生成可审计证据。

#### 实施包 1：真实 Output Eval Lab

优先级：`P0`  
周期：Week 1，6 人日  
价值：把当前 expectation-level 输出检查升级为真实 baseline 与 with-skill 输出比较。

目标文件：

- `src/geo_seo_hub/quality/__init__.py`
- `src/geo_seo_hub/quality/evaluation.py`
- `src/geo_seo_hub/quality/metrics.py`
- `src/geo_seo_hub/quality/review.py`
- `schemas/eval-task.schema.json`
- `schemas/eval-result.schema.json`
- `evals/quality/benchmark-suite.yaml`
- `evals/quality/public/*.json`
- `evals/quality/adversarial/*.json`
- `scripts/run_quality_lab.py`
- `scripts/adjudicate_output_review.py`
- `tests/test_quality_eval.py`
- `tests/test_quality_metrics.py`

执行内容：

1. 定义 task、runner、scorer、judge 与 review decision 五个接口。
2. 从现有 20 个 output cases 中选择 5 个代表性任务，按 6.1 的隔离规则生成真实 baseline 与 with-skill 结果。
3. 覆盖 routing、discover、diagnose、content 和 evidence boundary。
4. 建立 deterministic runner、command runner 与 provider runner。
5. 指标至少包含 contract compliance、claim faithfulness、citation support、answer relevance、boundary safety、latency、token 与 cost。
6. 盲评包随机隐藏 variant 身份，answer key 与 reviewer decisions 分离保存；private holdout 只通过 `GEOHUB_PRIVATE_EVAL_ROOT` 加载。
7. 真实 reviewer、reviewed_at、winner、confidence、rubric reason 缺失时，human review 保持 `missing evidence`。
8. 建立 failure taxonomy：route、contract、evidence、factuality、relevance、style、safety、runtime。

验收门槛：

- 至少 5 个真实任务、20 个盲评 pair，覆盖 public、adversarial 和 private holdout。
- with-skill 确定性断言通过率高于 baseline 至少 15 个百分点。
- 人工盲评胜率至少 `65%`，且无安全或捏造引用失败。
- claim citation support 至少 `0.95`，fabricated citations 必须为 `0`。
- fixture、command、model 三种 execution kind 被准确区分。
- provider 或模型信息缺失时，报告不得标记 model-executed。
- baseline 与 candidate 必须来自两个隔离 wheel，报告记录 wheel digest 和运行环境。
- 第二 reviewer 覆盖至少 `20%` pair；kappa 低于 `0.60` 时保持 warn。

独立回滚：删除新 `quality` 包、Schema、脚本和 CLI 子命令；现有 `scripts/run_evals.py` 与 0.2.0 gate 保留。

#### 实施包 2：`geo-measure` 文件导入模式

优先级：`P0`  
周期：Week 2-3，6 人日  
价值：建立真实 GEO 目标、引擎观察与可重复比较基线。

目标文件：

- `src/geo_seo_hub/measure.py`
- `src/geo_seo_hub/intelligence/measurement.py`
- `schemas/engine-observation-bundle.schema.json`
- `schemas/visibility-report.schema.json`
- `skills/geo-measure/SKILL.md`
- `skills/geo-measure/agents/interface.yaml`
- `skills/geo-measure/manifest.json`
- `skills/geo-measure/references/measurement-method.md`
- `skills/geo-measure/references/output-contract.md`
- `skills/geo-measure/evals/trigger_cases.json`
- `skills/geo-measure/evals/output/cases.jsonl`
- `skills/geo-measure/scripts/run_measure.py`
- `tests/fixtures/engine-observation-bundle.json`
- `tests/test_measure.py`
- `docs/benchmark-protocol.md`

输入契约：

- 每条观察必须包含 engine、model 或 unknown、query_id、query_text、answer_text、citations、observed_at、locale、session_policy、panel_version 和 collection_method。
- `collection_method` 只允许 `manual_export`、`approved_api`、`recorded_fixture`。
- 真实引擎观察不得标记为 recorded fixture。
- 观察包必须有来源说明、许可范围和采集者。

指标：

- `mention_rate`
- `source_inclusion_rate`
- `citation_share`
- `position_weighted_visibility`
- `answer_coverage`
- `observation_coverage`
- `missing_observation_rate`

每个聚合指标必须同时输出分子、分母、缺失条数、分引擎结果和查询级原始分量。缺失观察不参与正向加分。

验收门槛：

- 同一观察包重复运行产生相同 `semantic_digest`；created_at、duration 与 trace ID 可以变化。
- smoke 至少覆盖 2 个引擎、5 个查询和 2 个时间点的合规样本。
- 公开效果结论使用 6.3 的 30-query Promotion 数据集、每引擎 3 次重复观察和置信区间。
- 原始分量可以重算所有聚合指标。
- 缺失、重复、过期、时区错误与 citation URI 异常均有失败测试。
- `geo-measure` 的触发、近邻和输出评测全部通过。
- 默认执行不访问网络。

独立回滚：Registry 将 `geo-measure` 恢复为 `planned`，移除命令和 Skill 包；已有四个 Skill 不受影响。

#### 实施包 3：运行谱系、metadata-only 观测与数据保留

优先级：`P0`  
周期：Week 4，5 人日  
价值：让 route、run、artifact、metric、review 和错误可以串联复盘。

目标文件：

- `src/geo_seo_hub/quality/lineage.py`
- `src/geo_seo_hub/quality/observability.py`
- `schemas/run-lineage.schema.json`
- `scripts/aggregate_adoption_drift.py`
- `src/geo_seo_hub/data_retention.py`
- `tests/test_data_retention.py`
- `tests/test_lineage.py`
- `tests/test_observability.py`
- 四个现有 executor 的薄接入点

事件边界：

- 记录 trace_id、span_id、parent_span_id、run_id、skill_id、stage、status、duration_ms、artifact hashes、metric names、token count、cost 与错误分类。
- 默认排除 prompt、answer、正文、客户名、URL、文件绝对路径、凭证和原始异常 payload。
- `run-lineage.json` 随 run 保存，采用数据由用户显式指定 runs root 后聚合。
- 默认不写全局隐藏目录，不后台上报，不建立远程 collector。
- OpenTelemetry exporter 作为 optional adapter，缺失时本地 sidecar 完整可用。
- `data-retention` 默认 dry-run；第一次确认只移动到可恢复 trash，永久删除需要满 7 天和第二次确认。

验收门槛：

- discover、diagnose、content、measure 均生成合法 lineage sidecar。
- 失败 run 的 staging 仍按 Artifact Bus 边界清理，错误元数据由调用者显式接收。
- 30 个合成 run 可聚合 adoption、failure、duration 与 drift 报告。
- 隐私扫描确认禁止字段未进入 lineage 与 drift 报告。
- 无 exporter 时全部现有命令正常运行。
- L0-L3 保留期、package exclusion、secret zero-retention 与删除审计全部有测试。
- symlink、父目录逃逸、跨文件系统移动、并发处理、损坏 manifest 和非 GEOHub 目录必须拒绝处理。
- trash grace period 内可以按 recover manifest 恢复原 run ID，目标已存在时拒绝覆盖。

独立回滚：关闭 lineage sidecar 写入并移除 optional exporter 和 data-retention 子命令；执行产物与 manifest 的既有必填项保持兼容。

### 里程碑 B：领域算法升级，Week 5-9，P1

目标版本：`0.4.0 Experimental`  
核心工程：23 人日；评测与返工缓冲：2 人日  
继续投入门槛：discover、diagnose、content 在真实任务质量上超过 0.2.0 基线，安全、成本与时延有完整记录。

#### 实施包 4：控制平面与语义路由影子模式

优先级：`P1`  
周期：Week 5，5 人日

目标文件：

- `src/geo_seo_hub/control/registry.py`
- `src/geo_seo_hub/control/routing.py`
- `src/geo_seo_hub/control/workflow.py`
- `src/geo_seo_hub/router.py` 兼容 façade
- `schemas/workflow-state.schema.json`
- `evals/router_shadow_cases.json`
- `tests/test_router_shadow.py`
- `tests/test_workflow_state.py`

执行内容：

1. 把 route candidate、score component、threshold 和 decision reason 变成结构化对象。
2. 词法结果继续驱动生产路由。
3. 语义 scorer 通过 adapter 接口运行，只写影子评测结果。
4. 每个 route 使用正例 utterance、负例、近邻和阈值版本。
5. 工作流状态包含 workflow_id、version、current_step、inputs、artifact refs、checkpoint、approval 和 failure boundary。
6. 实现 checkpoint、resume、retry、abort 与人工确认；状态包括 running、awaiting_approval、awaiting_external_publication、awaiting_external_observation、completed、failed 和 aborted。
7. 现有两个稳定 DAG 通过新 state runner 重放，默认输出保持一致。
8. Registry Schema 的 workflow ID 从固定枚举改为受限 slug，并继续验证拓扑顺序、active Skill 与 required_skills 一致性。

语义路由晋级门槛：

- 公开 smoke、holdout、adversarial 和 route-confusion 四组均无回归。
- precision 至少 `0.97`，recall 至少 `0.93`。
- 新 planned/active 混合请求的误激活数为 `0`。
- 影子路由与词法路由的分歧都有可读原因与人工抽查记录。
- 未达门槛时，语义 scorer 保持评测工具身份。
- checkpoint 损坏、版本不兼容、重复 resume、step 超时和人工拒绝均有确定状态与测试。
- `awaiting_external_*` 状态可以跨进程恢复，不会误判为失败或完成。

独立回滚：现有 `router.py` 直接恢复使用词法实现；现有两个 exact DAG 可以切回顺序执行。Registry 的新增 workflow slug 规则保持向后兼容。

#### 实施包 5：Discovery v2

优先级：`P1`  
周期：Week 6，5 人日

目标文件：

- `src/geo_seo_hub/intelligence/discovery/__init__.py`
- `src/geo_seo_hub/intelligence/discovery/strategies.py`
- `src/geo_seo_hub/intelligence/discovery/clustering.py`
- `src/geo_seo_hub/intelligence/discovery/scoring.py`
- `src/geo_seo_hub/discover.py` 兼容 façade
- `skills/geo-discover/references/discovery-method-v2.md`
- `evals/discovery/gold-labels.json`
- `tests/test_discovery_strategies.py`
- `tests/test_discovery_quality.py`

策略：

- `template_baseline`：保持 0.2.0 确定性模板。
- `hypothetical_document`：借鉴 HyDE，以提供者或输入文件生成假设性高质量回答，再用于查询变体生成。
- `question_graph`：围绕实体、任务、受众、场景、比较和决策阶段扩展问题。
- `cluster_and_prune`：按语义相似、规范化 token 和实体重叠去重。

输出增强：

- 每条 query 标记 generator、parent_query、intent、audience、scenario、novelty、evidence_status 与 score components。
- opportunity score 分解为 coverage、relevance、novelty、evidence、business fit。
- `deterministic` execution mode 只用模板与规则。
- `provider` execution mode 明确记录 provider、model、prompt digest、token、cost 与失败。

验收门槛：

- 相同 deterministic 输入产生相同 ID、排序与 digest。
- 相比 0.2.0，人工标注 intent coverage 提升至少 `20%`。
- coverage 的 gold labels 由两名标注者抽检，分歧进入 adjudication，不用生成模型输出直接充当唯一真值。
- 规范化重复率低于 `10%`。
- source gap 不提高 evidence score。
- provider 不可用时返回明确 degraded，模板基线仍可完成。

独立回滚：`--execution-mode legacy` 回到 `template_baseline`，原 query-map 和 opportunity-map Schema 保持可读。

#### 实施包 6：Diagnosis v2

优先级：`P1`  
周期：Week 7 至 Week 8 前半，6 人日

目标文件：

- `src/geo_seo_hub/intelligence/audit/__init__.py`
- `src/geo_seo_hub/intelligence/audit/gatherers.py`
- `src/geo_seo_hub/intelligence/audit/audits.py`
- `src/geo_seo_hub/intelligence/audit/scoring.py`
- `src/geo_seo_hub/intelligence/audit/reporting.py`
- `src/geo_seo_hub/diagnose.py` 兼容 façade
- `skills/geo-diagnose/references/audit-catalog.md`
- `tests/test_audit_gatherers.py`
- `tests/test_audit_scoring.py`

四层职责：

1. Gatherer 只负责安全读取与结构化观察，不生成判断。
2. Audit 消费观察并产生 status、raw_value、severity、confidence、evidence_ids 和 remediation。
3. Score 聚合已通过质量门槛的 audit，保留权重、分子、分母和缺失项。
4. Report 只负责 JSON、Markdown 和 HTML 呈现。

首批 audit catalog：

- entity clarity
- evidence density
- citation readiness
- authority signals
- freshness signals
- structured data validity
- answerability
- comparison completeness
- source transparency
- content extraction health

验收门槛：

- 每个 audit 至少有 pass、fail、not-applicable、missing-evidence 测试。
- 缺失 evidence 的 audit 不进入正向得分。
- 汇总分可以从 raw components 完整重算。
- audit catalog、权重、阈值和 scoring policy 均带版本；报告记录实际版本。
- SSRF、redirect、content type、size、timeout、fd 和 replay 测试全部保持通过。
- 报告中的 remediation 可以追溯到 audit 与 evidence IDs。

独立回滚：`diagnose.py` façade 切回 0.2.0 analyzer；安全读取和 Artifact Bus 无需回滚。

#### 实施包 7：Content v2 与 MCDA

优先级：`P1`  
周期：Week 8 后半至 Week 9，7 人日

目标文件：

- `src/geo_seo_hub/intelligence/content/__init__.py`
- `src/geo_seo_hub/intelligence/content/research_bundle.py`
- `src/geo_seo_hub/intelligence/content/outline.py`
- `src/geo_seo_hub/intelligence/content/drafting.py`
- `src/geo_seo_hub/intelligence/content/claims.py`
- `src/geo_seo_hub/intelligence/content/mcda.py`
- `src/geo_seo_hub/content.py` 兼容 façade
- `schemas/claim-map.schema.json`
- `skills/geo-content/references/content-pipeline-v2.md`
- `skills/geo-content/references/mcda-policy.md`
- `tests/test_claim_map.py`
- `tests/test_mcda.py`
- `tests/test_content_pipeline.py`
- `tests/fixtures/content-brief.json`

阶段：

1. Research bundle：整理用户提供并已快照的来源、观点、实体与 evidence gaps。
2. Perspective plan：生成受众、角色、决策问题与反方问题。
3. Outline：每节绑定目标、问题、claim 和来源。
4. Draft：只使用已绑定 evidence 或显式标记为推断的内容。
5. Claim verification：逐 claim 输出 support、source IDs、confidence 与修复动作。
6. Polish：处理结构、重复、可读性和 artifact design，不改变 claim 事实边界。

MCDA 规则：

- criterion 必须声明 `benefit` 或 `cost` 极性。
- 每个方法声明 normalization、weighting、missing-value 和 tie policy。
- 同时输出 weighted sum 基线、TOPSIS 风格相对接近度与权重敏感性。
- 权重上下浮动 `10%` 后赢家变化时，报告标记 `sensitive`。
- 缺少同口径数据时，comparison 可以输出差异，ranking 拒绝宣告赢家。

验收门槛：

- claim-map 覆盖所有事实性段落，支持率至少 `0.95`。
- fabricated citations 为 `0`。
- 同一 deterministic research bundle 产生稳定 outline 与 MCDA 数值。
- 所有 ranking 可从原始矩阵、标准化矩阵、权重和方法重算。
- MCDA 增加 polarity、scale invariance、monotonicity、tie、all-missing 和 non-finite property tests。
- HTML 在 390px 与 1440px 均无横向页面溢出，表格容器可独立滚动。
- HTML 使用语义化标题、键盘可操作控件、可见焦点和 WCAG AA 级文字对比；最终 HTML 不包含绝对本地路径。
- DOCX/PDF 缺依赖时继续输出核心 artifacts，并记录 degraded。

独立回滚：七个现有 content mode 保持原实现入口；`--execution-mode legacy` 直接切回 0.2.0 pipeline。

### 里程碑 C：优化学习与可发布性，Week 10-13，P2

目标版本：`0.5.0 Experimental` 与 Production Readiness Review  
核心工程：14 人日；评审与风险缓冲：5 人日  
Promotion 条件：外部证据、人审、采用样本、供应链来源证明全部达标。条件未达成时，Readiness Review 必须输出 blocker，版本继续标记 `Experimental`。

#### 实施包 8：策略优化、保真门与知识图谱

优先级：`P2`  
周期：Week 10-11，7 人日

目标文件：

- `src/geo_seo_hub/intelligence/optimization.py`
- `src/geo_seo_hub/intelligence/knowledge.py`
- `schemas/strategy-memory.schema.json`
- `schemas/knowledge-graph.schema.json`
- `schemas/publication-handoff.schema.json`
- `skills/geo-strategy/` 完整 Library 包
- `skills/geo-knowledge/` 完整 Library 包
- `tests/fixtures/strategy-request.json`
- `tests/fixtures/knowledge-request.json`
- `tests/test_optimization.py`
- `tests/test_knowledge.py`

策略循环：

1. Preference：声明目标、受众、约束、风险、品牌规则与指标权重。
2. Planner：从 diagnosis、content、knowledge 和 measurement baseline 生成干预计划。
3. Candidate：生成 2-4 个候选，每个候选具有 action diff 与预期影响。
4. Fidelity：检查事实、语义、品牌约束、引用与不可变信息。
5. Publication handoff：输出候选 digest、部署要求、观察窗口和 query panel，状态进入 `awaiting_external_publication`。
6. External observation：用户发布后回填 publication 记录和 post-change observation，状态进入可比较测量。
7. Measure：按 GEO Benchmark Protocol 比较 baseline 与 candidate。
8. Memory：只保存通过 fidelity 且有正向 metric delta 的策略记录。
9. Early stop：连续两轮无显著提升、成本超限或 fidelity 失败时停止。

知识图谱：

- entity 至少包含 type、canonical_name、aliases、source_ids、valid_from、reviewed_at。
- relation 至少包含 subject、predicate、object、source_ids、confidence、validity。
- conflicting facts 同时保留并输出冲突，不自动选择胜者。
- local query 返回实体邻域与来源。
- global query 返回社区摘要、覆盖范围与 evidence gaps。
- 图谱增量更新使用 source hash 与 entity identity，避免全量重建成为默认路径。

验收门槛：

- 至少 3 个重复 GEO 任务完成 baseline、candidate、fidelity、publication handoff、external observation、measure 全流程。
- 中位 visibility 指标相对 baseline 提升至少 `5%`，fidelity 无下降。
- 失败策略不得进入 promoted memory。
- 只有 offline evidence 时，策略状态最高为 `offline-approved`。
- 同一 context signature 的策略可以重放并说明适用边界。
- 图谱节点与关系的 source coverage 为 `100%`。
- 过期、冲突、孤立节点和无来源关系均有明确报告。

独立回滚：Registry 将两个 Skill 恢复为 `planned`；测量、发现、诊断和内容能力继续独立工作。已生成 strategy memory 和 knowledge graph 保留为版本化历史 artifact。

#### 实施包 9：兼容迁移、文档与分发矩阵

优先级：`P2`  
周期：Week 12，3 人日

目标文件：

- `pyproject.toml`
- `registry/skills.yaml`
- `registry/skills.schema.json`
- `scripts/package.py`
- `scripts/verify_packages.py`
- `scripts/install_simulation.py`
- `.github/workflows/ci.yml`
- `README.md`、`CHANGELOG.md` 与 `docs/*.md`
- `docs/decisions/0001-four-plane-modularization.md`
- `docs/decisions/0002-artifact-protocol-compatibility.md`
- `docs/decisions/0003-evaluation-and-measurement.md`
- `docs/decisions/0004-provider-privacy-boundary.md`
- `docs/decisions/0005-production-promotion.md`
- `THIRD_PARTY_NOTICES.md`
- `tests/test_installed_smoke.py`

交付要求：

- source checkout、wheel、统一 Skill、每个 active provider Skill、Codex adapter 与 Claude adapter 的 Registry、Schema、wrapper 和版本一致。
- `0.3.0` 有 5 个 active Skill，分发矩阵应生成 9 个归档；`0.5.0` 有 7 个 active Skill，分发矩阵应生成 11 个归档。
- 新 Schema、references、scripts、agents 与 Skill reports 全部进入正确 data-files allowlist。
- CLI `--help`、JSON stdout/stderr、退出码、execution mode 和数据保留确认在 source 与 installed runtime 中一致。
- 0.2.0 输入和公开 Python imports 继续工作；迁移文档列出新增命令、execution mode、artifact sidecars 和回滚方式。
- 每个实际新增依赖完成许可证审查和 third-party notice；没有代码或依赖引入的对标项目只保留研究引用。
- CI 继续覆盖 Linux Python 3.11-3.14 与 macOS install simulation。Windows 保持 unsupported / unclaimed。

验收门槛：

- `scripts/verify_repository.py`、package verification 与 install simulation 全部通过。
- 每个归档在 fresh venv 完成安装、route 与自身 wrapper smoke。
- package 内容不含 evals、私有 holdout、原始观察、客户数据、运行目录、缓存或本地绝对路径。
- README、Registry、manifest、VERSION、CHANGELOG、安装文档和迁移文档的版本与能力状态一致。

独立回滚：Registry 将新增 Skill 恢复为 `planned`，pyproject data-files 与分发矩阵回到上一版本；既有四个 Skill 的归档继续构建。

#### 实施包 10：供应链来源证明与 Production Readiness Review

优先级：`P2`  
周期：Week 13，4 人日

目标文件：

- `src/geo_seo_hub/quality/release.py`
- `scripts/generate_sbom.py`
- `scripts/generate_provenance.py`
- `scripts/verify_provenance.py`
- `scripts/render_production_readiness.py`
- `reports/release-provenance.json`
- `reports/release-sbom.json`
- `reports/production-readiness.json`
- `reports/production-readiness.md`
- `tests/test_release_provenance.py`
- CI release workflow 与 GitHub artifact attestation

发布要求：

- SBOM 列出 Python 依赖、版本、许可证与哈希。
- provenance 绑定 source revision、builder identity、command、artifact digest 和生成时间。
- 包验证从独立目录重算 digest 并核对 provenance。
- 本地构建标记 local builder，不声明 trusted builder。
- CI 发布使用 GitHub 原生 artifact attestation；外部验证使用 `gh attestation verify`。
- 只有 CI 身份、来源与签名可验证时，才允许声明相应 SLSA provenance 等级。
- 社区 ZIP、provider ZIP 与 adapter ZIP 继续执行 fresh venv 安装测试。
- Production Readiness Review 汇总 output eval、GEO benchmark、human review、adoption、trust、permission、package、install、provenance 与开放 waivers。

验收门槛：

- package、SBOM、provenance 和 source revision 的 digest 一致。
- 篡改包、错误 revision、缺失 dependency 和伪造 builder 均会验证失败。
- `gh attestation verify` 对 CI 归档通过，对篡改副本失败。
- Readiness Review 的每个非 pass gate 都有 source fix、owner、evidence 和 verification command。
- 任何缺失外部证据、过期 waiver 或开放 blocker 都使 Production 决策为 blocked。
- `scripts/verify_all.py`、package verification 与 install simulation 全部通过。

独立回滚：provenance 与 attestation 作为发布附加 gate 移除，不改变已生成包内容格式；版本继续保持 `Experimental`。

## 8. 质量门槛矩阵

`H` 是版本合并和发布硬门槛；`E` 是能力晋级与效果声明证据门槛。缺少 `E` 证据时可以发布标记为 `Experimental` 的确定性实现，相关 provider/research 默认行为、策略记忆晋级和效果声明保持 `Hold`。Production Readiness 要求全部 `H` 与 `E` 通过。

| Gate | 类型 | `0.3.0` | `0.4.0` | Production Readiness pass |
| --- | ---: | ---: | ---: | ---: |
| 现有 pytest | H | 100% 通过，允许明确标记的 skip | 同左 | 同左 |
| Router precision / recall | H | `>=0.97 / >=0.93` | 同左，含语义 shadow holdout | 同左 |
| Output contract compliance | H | `1.00` | `1.00` | `1.00` |
| Fabricated citations | H | `0` | `0` | `0` |
| Baseline 隔离 | H | 0.2.0 wheel 与 candidate wheel digest 完整 | 同左 | 同左 |
| 真实任务数 | E | `>=5` | `>=12` | `>=20` |
| Provider/model | E | 2 个 generator model，明确版本 | 同左并增加独立 judge | 至少两个时间点，漂移有记录 |
| GEO query panel | E | 5-query smoke | `>=30` 个分层 query | 同 panel 至少两个时间点 |
| GEO 引擎与重复 | E | `>=2` 个引擎，smoke | `>=2` 个引擎，每 query 3 次 | `>=3` 个引擎，每 query 3 次 |
| 统计证据 | E | 描述统计 | effect size 与 bootstrap CI | 同左，样本不足即 blocker |
| 人工盲评 pair | E | `>=20` | `>=30` | `>=50` |
| with-skill 胜率 | E | `>=65%` | `>=70%` | `>=70%` |
| 双 reviewer 抽检 | E | `>=20%` pair | 同左 | kappa `>=0.60` |
| Claim citation support | H | `>=0.95` | `>=0.95` | `>=0.97` |
| 采用元数据样本 | E | 合成 30 runs | 合规真实样本 `>=20` | 合规真实样本 `>=50` |
| 数据保留与隐私 | H | L0-L3 policy pass | 无禁止字段 | 删除审计与隐私扫描 pass |
| Security / trust | H | pass | pass | pass |
| Review Studio | H | review，无 blocker | review，无 blocker | pass 或仅有已批准、未过期 warn waiver |
| Provenance | H | source + package digest | SBOM draft | 独立 verify 与 attestation pass |
| 分发归档 | H | 9 个归档可安装 | 9 个归档可安装 | 11 个归档可安装 |

质量分数必须标注样本量、评测时间、provider/model/engine 版本和 missing evidence。专家成熟度指数、GitHub stars 与内部 gate 分数不得当作公开效果性能。

## 9. 测试策略

### 9.1 每个实施包必须覆盖

- Happy path：合法输入、预期 artifact、稳定重放。
- Input error：空输入、格式错误、Schema 错误、缺少必填字段。
- Evidence boundary：缺来源、来源冲突、过期来源、引用不存在。
- Security boundary：symlink、FIFO、SSRF、redirect、超限、凭证泄露。
- Determinism：同输入、同 execution mode、同版本产生相同 semantic digest。
- Degradation：provider、renderer、exporter 或 optional dependency 不可用。
- Rollback：`--execution-mode legacy` 或 Registry 状态恢复后，0.2.0 路径继续可用。
- Compatibility：公开 Python import、CLI 和既有 Schema 仍可读取。
- Concurrency：同 run ID、checkpoint resume、数据保留与 package build 的并发冲突有确定结果。
- Scientific validity：panel version、重复采样、不可比观察、置信区间和低样本声明均有测试。

### 9.2 固定验证命令

以下人工命令在干净 worktree 中运行；自动化测试使用临时目录，避免固定 `build/*` 路径让重复执行产生假失败。

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_evals.py
.venv/bin/python scripts/run_yao_meta_gates.py --verify-existing
.venv/bin/python scripts/verify_all.py
.venv/bin/python scripts/package.py --target all --channel community
.venv/bin/python scripts/verify_packages.py
.venv/bin/python scripts/install_simulation.py --target all
```

`0.3.0` gate 完成后加入：

```bash
.venv/bin/python scripts/run_quality_lab.py --suite evals/quality/benchmark-suite.yaml --execution-mode deterministic
.venv/bin/python scripts/adjudicate_output_review.py --decisions reports/output_review_decisions.json
.venv/bin/geo-seo-hub measure --input tests/fixtures/engine-observation-bundle.json --output build/measure-smoke
.venv/bin/geo-seo-hub data-retention --runs-root tests/fixtures/retention-runs --apply-policy
```

`0.4.0` gate 增加：

```bash
.venv/bin/geo-seo-hub discover --input tests/fixtures/brief.json --output build/discover-v2-smoke --execution-mode deterministic
.venv/bin/geo-seo-hub diagnose --input tests/fixtures/diagnosis-brand.json --output build/diagnose-v2-smoke --execution-mode deterministic
.venv/bin/geo-seo-hub content --input tests/fixtures/content-brief.json --output build/content-v2-smoke --execution-mode deterministic
```

`0.5.0` gate 增加：

```bash
.venv/bin/geo-seo-hub strategy --input tests/fixtures/strategy-request.json --output build/strategy-smoke
.venv/bin/geo-seo-hub knowledge --input tests/fixtures/knowledge-request.json --output build/knowledge-smoke
.venv/bin/python scripts/generate_sbom.py
.venv/bin/python scripts/generate_provenance.py
.venv/bin/python scripts/verify_provenance.py
.venv/bin/python scripts/render_production_readiness.py
```

Provider-backed gate 只在环境已配置 generator 与 judge 后运行：

```bash
test -n "${OPENAI_API_KEY:-}"
test -n "${GEOHUB_GENERATOR_MODEL_A:-}"
test -n "${GEOHUB_GENERATOR_MODEL_B:-}"
test -n "${GEOHUB_JUDGE_MODEL:-}"
test "${GEOHUB_MAX_EVAL_COST_USD:-25.00}" != "0"
.venv/bin/python scripts/run_quality_lab.py --suite evals/quality/benchmark-suite.yaml --execution-mode provider --provider openai
```

Provider runner 默认把完整 suite 的费用上限设为 `25.00 USD`。环境变量 `GEOHUB_MAX_EVAL_COST_USD` 可以调低；提高上限需要评测负责人在运行记录中批准。每个 case 在 suite manifest 中显式声明输入、输出 token 上限，runner 在发起下一次调用前预估剩余额度，超限时停止并输出 partial coverage。

## 10. Skill OS 2.0 交付标准

每个新增或重大升级 Skill 必须提交以下证据：

1. Lean `SKILL.md`，Library 初始加载不超过 `1300` tokens。
2. 对齐的 `agents/interface.yaml`。
3. `manifest.json`，含 owner、version、status、maturity、review cadence 与 targets。
4. Skill IR，包含 job、boundary、decision_points、failure_modes、resources、risk 与 eval plan。
5. 触发评测，覆盖 should-trigger、should-not-trigger、near-neighbor 与 route confusion。
6. 输出评测，覆盖 `file-backed fixture`、边界、失败和真实执行证据。
7. `reports/output-risk-profile.md`。
8. `reports/artifact-design-profile.md`。
9. `reports/output_quality_scorecard.md`。
10. `trust report`，覆盖脚本、网络、凭证、依赖、权限和 package hash。
11. Review Studio，所有 warn/block 均有 source fix 与 verification command。
12. Registry、package、install、upgrade、drift 与 waiver gate。

每个 Skill IR 必须明确：

- `input_files`，并标记真实 fixture 为 `file-backed fixture`。
- `output contract`。
- `rollback boundary`。
- owner 与 review cadence。
- 缺失的 telemetry、approval、metric、benchmark 或 human review 使用 `missing evidence`。

## 11. 对标机制的借鉴边界

### 11.1 建议吸收

- Agent Skills：progressive disclosure、跨客户端格式、验证器思路。
- Backstage：typed catalog、owner、lifecycle、dependency 与 discoverability。
- Semantic Router：utterance 集、阈值优化、shadow comparison。
- LangGraph：state、checkpoint、interrupt、resume 与 durable execution。
- Pydantic：单一类型来源驱动验证和 Schema 的方法。
- MLflow 与 OpenLineage：run、artifact、metric 和 evidence lineage。
- HyDE：hypothetical document 作为可选发现策略。
- GEO 与 MAGEO：可见性目标、候选比较、保真门、记忆和早停。
- Lighthouse：gatherer、audit、score、report 分层。
- STORM：perspective、outline、cited draft、polish 阶段。
- Scikit-Criteria：criteria polarity、normalization、method disclosure 和 sensitivity。
- Inspect AI 与 Ragas：task、runner、scorer、judge、claim metrics 与 blind review。
- OpenTelemetry：trace/span/context 的可移植语义。
- GraphRAG：evidence-backed entity graph、community summary、local/global query。
- SLSA：builder、source、artifact digest 与可验证 provenance。

### 11.2 明确不吸收

- 不直接引入 LangGraph、MLflow、GraphRAG 等完整依赖栈作为核心运行前提。
- 不复制对标仓库的命令、私有目录、发布清单或组织治理结构。
- 不把 Semantic Router 的 embedding 结果直接接管当前词法路由。
- 不让 STORM 风格 research 阶段绕过 GEOHub 的离线与批准来源边界。
- 不让 MAGEO 风格 memory 保存未通过 fidelity 或缺少测量证据的策略。
- 不用单一总分隐藏 MCDA 原始矩阵、权重与敏感性。
- 不声称 SLSA 等级，除非 builder 身份与 provenance 可以被独立验证。

## 12. 依赖、账号与权限

### 12.1 实施必需

- Python `3.11-3.14`。
- 现有 `jsonschema`、`PyYAML` 与开发测试依赖。
- 本地文件系统写入测试、报告、构建与临时运行目录的权限。
- GitHub Actions 只用于 CI 与发布来源证明，不参与本地核心执行。

### 12.2 外部证据必需

| 项目 | 用途 | 所有者 | 缺失时行为 |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | provider-backed 输出评测 | 执行评测的人 | provider gate 跳过并保持 `missing evidence` |
| `GEOHUB_GENERATOR_MODEL_A` | 固定第一组生成模型身份 | 评测负责人 | provider gate 拒绝启动 |
| `GEOHUB_GENERATOR_MODEL_B` | 固定第二组生成模型身份 | 评测负责人 | provider gate 拒绝启动 |
| `GEOHUB_JUDGE_MODEL` | 固定独立 judge 身份 | 评测负责人 | 自动 judge gate 拒绝启动，人审仍可继续 |
| `GEOHUB_MAX_EVAL_COST_USD` | 限制单次完整 provider suite 费用 | 评测负责人 | 未设置时采用 `25.00 USD`，非法值拒绝启动 |
| `GEOHUB_PRIVATE_EVAL_ROOT` | 提供私有 holdout | GEO 评测负责人 | public smoke 可运行，Promotion holdout 保持 `missing evidence` |
| 合规引擎观察包 | GEO visibility 基准 | GEO 评测负责人 | `geo-measure` 只通过 fixture gate，产品状态保持 Experimental |
| 人工盲评决定 | 判断真实输出偏好 | 指定 reviewer | human agreement 不计分，Review Studio 保持 warn |
| CI 发布身份 | 可信 builder 与签名 | 仓库 owner | provenance 标记 local builder，不声明 trusted level |

所有 secret 只通过环境变量或 CI secret 注入，不进入输入快照、run artifacts、日志、报告、盲评包或 provenance。

### 12.3 当前可用性与未决证据

2026-08-12 的只读预检结果如下：

| 条件 | 当前状态 | 影响 | 最晚解决点 |
| --- | --- | --- | --- |
| OpenAI key、两个 generator model、judge model | 未配置 | 不影响 deterministic 实施；阻塞 provider-backed gate | 实施包 1 进入 provider 评测前 |
| Private holdout 根目录与内容 | 未配置 | public/adversarial 可运行；阻塞 0.3.0 holdout gate | Week 3 Gate Review 前 |
| 合规 engine 账号、许可范围与 observation source | 尚无已批准证据 | fixture smoke 可运行；阻塞真实 GEO 效果结论 | Week 4 Gate Review 前 |
| 两名盲评 reviewer 与排期 | 尚无签字记录 | 盲评包可生成；阻塞人审胜率和 agreement gate | Week 3 前 |
| GitHub CLI artifact attestation | 本机 `gh 2.87.2` 命令可用 | 本地可开发验证流程；远端 CI 身份仍需 release run 证明 | 实施包 10 |
| 第三方依赖许可证清单 | 随实际 import 生成 | 不影响零新增依赖的实施包；阻塞含新依赖的发布 PR | 每个相关 PR 合并前 |

模型名、账号与 reviewer 由对应负责人按表中时点锁定，并写入 versioned evaluation manifest 或批准记录。未决证据不会改变架构和契约；它们只阻塞依赖该证据的 gate 与成熟度声明。

### 12.4 可选依赖策略

- OpenTelemetry SDK 进入 `telemetry` optional extra。
- Provider SDK 进入 `eval` optional extra，deterministic gate 不依赖它。
- 图算法优先使用标准库数据结构；GraphRAG adapter 在核心图谱契约稳定后单独评审。
- 任何 optional dependency 必须通过 Python 3.11、3.12、3.13、3.14 与 fresh venv 安装验证。

## 13. 发布与分支策略

每个实施包使用一个独立 PR，按顺序合并：

| PR | 分支建议 | 发布点 | 可独立价值 |
| ---: | --- | --- | --- |
| 1 | `codex/geohub-output-eval-lab` | 无 | 真实评测与盲评基础 |
| 2 | `codex/geohub-measure` | `0.3.0-rc1` | 文件导入式 GEO 测量 |
| 3 | `codex/geohub-lineage-retention` | `0.3.0` | 可审计 run 谱系与可恢复数据保留 |
| 4 | `codex/geohub-control-plane` | 无 | 结构化路由与可恢复状态底座 |
| 5 | `codex/geohub-discovery-v2` | 无 | 多策略发现与质量分量 |
| 6 | `codex/geohub-diagnosis-v2` | 无 | 可扩展 audit catalog |
| 7 | `codex/geohub-content-v2` | `0.4.0` | claim map、分阶段内容与 MCDA |
| 8 | `codex/geohub-strategy-knowledge` | `0.5.0-rc1` | 策略反馈与证据图谱 |
| 9 | `codex/geohub-compat-docs` | `0.5.0-rc2` | source、wheel、归档和文档一致性 |
| 10 | `codex/geohub-release-readiness` | `0.5.0` | SBOM、来源证明与 Production Readiness Review |

每个 PR 合并前执行：

1. 目标测试与全量 pytest。
2. `scripts/run_evals.py`。
3. 相关 Skill OS gates。
4. package verification 与 install simulation，凡是修改包内容或入口的 PR 均执行。
5. `/check` 代码与发布门审查。
6. 更新 `VERSION`、Registry、manifest、迁移说明和 release notes，只有发布 PR 执行版本更新。

### 13.1 每个 PR 的完成定义

一个实施包只有同时满足以下条件才算完成：

1. PR 描述列出范围、排除项、公共实体变化、依赖变化和独立回滚步骤。
2. 实现、Schema、fixtures、目标测试和全量回归全部通过，失败与 skip 有明确解释。
3. source checkout、wheel 与受影响的 Skill 归档运行同一组安装后 smoke。
4. Registry、pyproject data-files、Skill manifest、接口、文档和 changelog 与实际行为一致。
5. 生成该包要求的 eval、trust、privacy、compatibility 或 provenance 证据，并记录 evidence digest。
6. reviewer 已检查安全 sink、网络边界、凭证、许可证和数据保留影响。
7. 没有未处理 blocker；warn 具有 owner、到期日、验证命令和书面 waiver。
8. 合并后能够用文档化命令回到上一稳定 execution mode 或 Registry 状态。

## 14. 风险与防变形设计

| 风险 | 早期信号 | 设计响应 | 回滚边界 |
| --- | --- | --- | --- |
| Baseline 污染 | baseline import 到 candidate 源码或 digest 无法复现 | 隔离 wheel、detached worktree、环境摘要和双 digest | 丢弃该次比较并重建 baseline |
| 评测过拟合 | smoke 上升，holdout 不升 | 分离 smoke、holdout、adversarial，真实失败进入 taxonomy | 退回上一套 rubric 与 case version |
| Holdout 或 judge 泄漏 | case 内容出现在开发日志，judge 能看到 variant 身份 | 根目录隔离、答案密钥隔离、随机顺序和 reviewer 抽检 | 作废受污染 suite 并轮换 case version |
| Provider 漂移 | 同任务分数随模型版本波动 | 记录 provider、model、时间、prompt digest 与 raw result hash | 固定上次已批准 evidence snapshot |
| 引擎漂移与测量混杂 | baseline 与 candidate 的 locale、session 或时间窗不同 | panel version、重复采样、24 小时窗口、engine 分层和不可比判定 | 该批次只保留描述记录，不进入 Promotion |
| 引擎采集合规风险 | 需要登录、自动化 UI 或绕过限制 | 只接受 manual export 与 approved API | 停止真实引擎 gate，保留 fixture 模式 |
| 外部发布依赖延迟 | candidate 已批准，publication 或 post-change observation 未回填 | publication handoff、可恢复状态、owner 和观察窗口 | 保持 `offline-approved`，不写入 promoted memory |
| 依赖膨胀 | fresh venv 变慢、Python 兼容失败 | adapter 与 optional extras，核心保持标准库优先 | 移除 optional adapter |
| 许可证或服务条款不清 | 新依赖无许可证记录，采集方式缺许可范围 | third-party notice、条款 reviewer 和 collection manifest | 移除依赖或拒收 observation |
| 模块过度拆分 | 跨层调用增加、职责重复 | 顶层 Skill 按用户任务划分，内部模块按稳定契约划分 | façade 回到单模块实现 |
| 语义路由误激活 | planned 或近邻请求被错误执行 | shadow mode、阈值版本、route confusion gate | 保留词法主路由 |
| 评分被优化游戏化 | 总分上升，事实性或可读性下降 | raw components、fidelity、敏感性与人工盲评 | 禁用 aggregate promotion |
| 策略记忆污染 | 失败策略被复用 | promotion state、fidelity gate、metric delta、expiry | 删除单条 memory artifact |
| 图谱陈旧或冲突 | 同实体出现相互矛盾结论 | valid time、source IDs、conflict report、review cadence | 按 source hash 回滚增量 |
| 隐私泄露 | telemetry 出现正文、URL 或客户名 | metadata allowlist 与隐私扫描 | 删除指定 run lineage 和聚合报告 |
| 数据保留命令误操作 | dry-run 目标过宽、跨根目录或 purge 批次不一致 | bounded root、no-follow、recover manifest、7 天 trash 和二次确认 | 在 purge 前恢复 batch；purge 后依据审计记录处置 |
| 分发矩阵漂移 | Registry active 数与 archive 数不一致 | 由 Registry 生成期望矩阵并在 CI fresh install | 阻塞发布并恢复上一归档清单 |
| 发布来源不可验证 | 包 hash 与 source 不一致 | trusted builder、provenance verify、fresh install | 撤回该 release artifact |
| 进度挤压质量门 | 核心工程消耗超过里程碑预算 25% | scope freeze、10 人日缓冲和 Gate Review | 延后后续包，不降低硬门槛 |

### 14.1 10 倍规模攻击

当单次任务增长到数百查询、数千 claim 或数百来源时，最先承压的是聚类、claim verification、图谱更新和盲评成本。计划要求所有阶段使用流式读取或有界集合，记录 item count、duration 与 cost；`provider` execution mode 必须支持最大 query、claim、token 与费用预算。预算超限时输出 partial、coverage 和 missing items，已验证结果继续可用。

### 14.2 外部依赖失败

Provider、OTel exporter、renderer 和 CI signing 任一不可用时，`deterministic` execution mode、Artifact Bus、基础质量报告和本地包验证继续工作。报告必须显示 degraded、missing dependency 与未完成 gate。

### 14.3 数据回滚

所有执行产物继续以独立 run 目录保存。策略记忆和知识图谱采用版本化 artifact，不原地覆盖已批准版本。算法回滚切换 Registry 或 `--execution-mode legacy`，数据回滚恢复上一版本 artifact ref。数据保留命令先移动到 `.geohub-trash/<batch-id>`，7 天宽限期内可按 recover manifest 恢复；永久 purge 之后只保留删除审计，不承诺内容恢复。客户原始输入始终处于数据操作范围之外。

### 14.4 Gate Review 的 Go、Hold 与 Stop 规则

第 4、9、13 周使用同一套决策规则：

- `Go`：当前里程碑硬门槛全部通过，没有开放 blocker，下一里程碑的 owner、输入和预算已就绪。
- `Hold`：确定性实现与安全门通过，外部账号、真实观察或人审证据仍缺失。代码可以合并，默认行为、active 状态或成熟度不晋级。
- `Stop/Pivot`：现有基线出现回归、权限或隐私边界失守、核心工程超预算 25%、关键依赖在目标 Python 矩阵不兼容，或领域证据显示方案没有预期价值。停止后续包，保留已验证的独立交付物并提交缩减方案。
- 任一 Gate Review 都不能通过降低 precision、citation、security、privacy、holdout 或 provenance 硬门槛换取按期完成。

## 15. 人力与时间预算

| 里程碑 | 实施包 | 人日 | 日历周 |
| --- | --- | ---: | ---: |
| A | Output Eval Lab | 6 | Week 1-2 |
| A | geo-measure | 6 | Week 2-3 |
| A | lineage / observability / retention | 5 | Week 3-4 |
| A | 评审与风险缓冲 | 3 | Week 4 |
| B | control plane | 5 | Week 5 |
| B | discovery v2 | 5 | Week 6 |
| B | diagnosis v2 | 6 | Week 7-8 |
| B | content v2 / MCDA | 7 | Week 8-9 |
| B | 评审与风险缓冲 | 2 | Week 9 |
| C | strategy / knowledge | 7 | Week 10-11 |
| C | compatibility / docs | 3 | Week 12 |
| C | provenance / readiness | 4 | Week 13 |
| C | 评审、外部证据与风险缓冲 | 5 | Week 10-13 |
| 合计 | 10 个实施包，核心工程 54 人日 | **64 人日容量** | **13 周** |

估算假设：一名主维护者持续推进，Codex 辅助研究、实现和验证；真实引擎采集与人工盲评由领域 reviewer 在里程碑内并行完成。54 人日是核心工程上限，10 人日只用于审查、返工、证据采集和风险吸收。外部证据延迟不阻塞确定性代码合并，相关 Promotion gate 保持未通过。里程碑核心工程消耗超过预算 25% 时触发 Stop/Pivot Review。

## 16. 推荐方案与最小方案

### 16.1 推荐方案：完整 90 天计划

执行全部 10 个实施包。第 4 周交付可信质量基线，第 9 周交付领域算法升级，第 13 周交付优化反馈、知识、分发一致性与发布来源证明。核心工程为 54 人日，另有 10 人日评审和风险缓冲。每个里程碑结束后，根据质量增量、成本、风险和 missing evidence 执行 Go、Hold 或 Stop/Pivot 决策。90 天目标版本保持 `0.5.0 Experimental`，Production 状态只接受 Readiness Review 证据。

推荐理由：P0 解决“无法证明质量”，P1 解决“领域算法偏薄”，P2 解决“无法从效果中学习”。三层依赖顺序清晰，每层可以独立交付。

### 16.2 最小方案：只执行 P0

只执行实施包 1-3，发布 `0.3.0 Experimental`。该方案建立真实评测、geo-measure、运行谱系和可恢复数据保留，核心工程 17 人日，另预留 3 人日评审与风险缓冲。Discovery、Diagnosis、Content 的算法结构暂时保持 0.2.0。

适用条件：当前更关注建立可信基线，近期没有资源采集真实引擎观察、完成人工盲评或承担 13 周持续升级。

### 16.3 拒绝方案：一次性全栈重写

拒绝直接采用 LangGraph、Pydantic、MLflow、GraphRAG、OpenTelemetry 和 MAGEO 组成新的运行栈。该方案会同时改变依赖、协议、执行方式、包体积、Python 兼容和安全边界，回归来源难以定位，现有 0.2.0 的强项也会失去稳定基线。

## 17. 最终 Review 结论

| 审查面 | 结论 | 关键证据或处理 |
| --- | --- | --- |
| 架构与依赖 | Pass | 10 个实施包依赖方向单一；包 5 与包 6 可并行；workflow recovery 已前移 |
| 兼容与契约 | Pass | JSON Schema 为 `0.x` 唯一规范；public façade 与 Artifact Bus `1.0.0` 保持兼容 |
| 安全与隐私 | Pass | 网络默认关闭；secret 零落盘；数据删除有 dry-run、trash、7 天宽限与二次确认 |
| 评测科学性 | Pass with missing evidence | baseline 隔离、holdout 防泄漏、重复测量和统计协议已确定；真实 observation 与人审待执行 |
| 发布与供应链 | Pass with execution gate | 分发矩阵、许可证、SBOM、provenance、attestation 和 fresh install 均有责任包与验收门槛 |
| 工期与资源 | Pass | 核心工程 54 人日，评审与风险缓冲 10 人日，设置三次 Gate Review 和 25% Stop/Pivot 线 |
| 回滚与退出 | Pass | 每个包有独立回滚；默认模式分阶段晋级；外部证据缺失时进入 Hold |

本轮文档审查还完成了以下验证：

- 当前仓库测试：`482 passed, 1 skipped`。
- 当前确定性 eval：precision、recall、trigger compliance、contract compliance 均为 `1.0`，fabricated citations 为 `0`。
- 当前 yao-meta gates：`pass-with-waivers`，11 项为明确的 `missing evidence`，release blocker 为 `0`。
- 当前 repository verification、8 个基线归档验证和安装模拟全部通过。
- 最终 Markdown 的相对链接、表格列、代码围栏、中文标点、禁用表达与旧计划残留均已检查通过。

Review 结论：本方案已达到决策确认条件。Production 能力、外部效果与人审质量仍需在执行阶段按 `E` 类证据门槛生成，当前不作预先承诺。

## 18. 待确认的关键决策

请确认以下八项。推荐值已经写在每项首行。

1. **批准完整 90 天方案。** 也可以选择只批准 P0，P1/P2 保留为下一轮提案。
2. **批准加法式四平面架构。** 现有四个 public façade 与 Artifact Bus `1.0.0` 保持兼容。
3. **批准 `geo-measure` 成为第一个新增 active Skill。** 只支持 manual export、approved API 与 recorded fixture 输入。
4. **批准 `geo-publish` 继续保持 planned。** 策略候选通过 publication handoff 交给用户在外部发布，再导入 observation。
5. **批准 provider、telemetry、knowledge 扩展全部采用 optional adapter。** 核心 `deterministic` execution mode 不依赖外部服务，网络默认关闭。
6. **批准数据保留采用两阶段可恢复删除。** 第一次确认移动到 trash，满 7 天后第二次确认才永久 purge。
7. **批准 Production Promotion 使用证据门槛与三方签字。** 外部证据、领域 reviewer、安全 reviewer 或仓库 owner 任一缺失时，Readiness Review 保持 blocked。
8. **批准 `0.5.0` 继续标记 `Experimental`。** 版本号不代表成熟度，Production 需要另行通过 Readiness Review。

确认方式：

- 回复“**确认最终方案**”，表示批准八项推荐值并允许随后按本计划实施。
- 回复“**确认 P0**”，表示只批准实施包 1-3。
- 回复具体编号和修改意见，例如“第 3 项改为先保持 planned”。

## 19. 批准后的执行起点

收到“确认最终方案”后，只启动实施包 1：建立真实 Output Eval Lab，保留现有评测脚本作为兼容 gate。实施包 1 完成后运行全量验证与 `/check`，提交质量证据、风险变化、预算消耗和实施包 2 的进入建议，再继续后续实施。收到“确认 P0”时采用同一节奏，并在实施包 3 完成后停止。当前文档审查阶段不修改 GEOHub 的实现、Registry、版本或发布状态。
