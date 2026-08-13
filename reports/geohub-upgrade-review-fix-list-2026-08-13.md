# GEOHub 升级复审与修复清单

日期：2026-08-13  
范围：GEOHub 0.5.0 升级工作树、七个 Active Skill、Meta Skill 治理面、质量评测、工作流、测量、策略、知识、制品与发布链路  
复审深度：Deep

## 结论

本轮复审覆盖安全、架构、对抗性输入、数据完整性、外部证据边界、发布供应链和安装面。复审确认的代码级问题均已进入修复；真实平台效果、人类盲审、正式 CI 证明、商业法律复核、生产知识库评测仍属于外部证据，继续保持 `missing evidence`，不会转写为确定性通过。

## 已修复清单

| # | 等级 | 模块 | 发现 | 修复 | 验证 |
| ---: | --- | --- | --- | --- | --- |
| 1 | High | Retention | 多 run 搬移在进程崩溃后可能滞留隐藏 staging | 增加 durable intent journal、目录 fsync、启动恢复、全局 no-follow retention lock、可重入恢复进度记录 | 崩溃 staging 和 split recovery 测试 |
| 2 | High | Measurement | 缺失观察可把 headline rate 放大到 1.0 | mention/source/position 指标改用 expected slots；citation share 将缺失槽位计入保守分母 | 1/20 正样本得到 0.05 |
| 3 | High | Measurement | 单条 live observation 可掩盖大量 recorded fixture | 禁止同一 bundle 混合 collection method | mixed-method 拒绝测试 |
| 4 | High | Review | 单 reviewer 可得到 completed | completed 要求全量主审、至少 20% 独立复审、有效 Cohen's kappa ≥ 0.60 | single-reviewer 返回 warn |
| 5 | High | Strategy | promotion 仅依赖 caller Boolean 与 delta | promotion 改为绑定 Fidelity、Experiment、Handoff、Publication Receipt、Visibility Report；校验 query panel、window、digests，计算 weighted delta，并原子刷新 memory | 正向 promotion 完整链路测试 |
| 6 | High | Workflow | 外部 publication/observation 可凭 checkpoint 越过 | 新增 `resume_external`，强制 schema、semantic digest、文件 digest 和 artifact reference；generic resume 拒绝外部边界 | 无证据 resume 拒绝测试 |
| 7 | High | Router | workflow 匹配硬编码两节点和三个 Skill | 改为按 Registry DAG 泛化匹配；新增三节点和 Strategy→Measure recipe | 3-step 与新 Skill workflow 测试 |
| 8 | High | Router Shadow | shadow scorer 异常可中断 lexical production route | 捕获 shadow 故障并记录 bounded unavailable metadata | broken scorer 测试 |
| 9 | High | Knowledge | 相同 hash 的 payload 漂移可返回旧图，partial delta 可丢数据 | source index 增加 payload digest；same-hash drift 和 partial snapshot fail closed | 两类回归测试 |
| 10 | High | Provenance | artifact 子集、伪造 SBOM facts、source/archive 分离均可能通过 | exact archive-name set、disk inventory、重建 SBOM facts、staged index digest、source ZIP 逐文件 inventory parity | subset、subject、SBOM forged facts 测试 |
| 11 | High | Release CI | OIDC 权限与 mutable build inputs 处于同一 job | build/attest 分 job；build 无 OIDC；Actions 固定 commit SHA；checkout 不持久化凭据；hash-lock 安装；传输 digest 校验 | workflow 静态审查与 release gate |
| 12 | Medium | Eval Privacy | private holdout 可在 provider mode 自动外发 | 默认阻止；要求 consent、classification、approved provider；报告只保存 consent digest | 无 consent 拒绝测试 |
| 13 | Medium | Eval Cost | provider task/call/token/cost 缺乏边界 | suite≤25、task input/output limits、显式模型价格、默认 $25、超额审批、调用前 worst-case preflight、真实 cost 汇总 | pricing/budget fail-closed 测试 |
| 14 | Medium | Eval Inputs | `input_files` 校验后未进入 runner，custom suite 不可移植 | suite 声明 `input_root`；snapshot UTF-8 payload、hash 和 content 进入 runner request | deterministic/command suite 回归 |
| 15 | Medium | Eval Runner | stdout/stderr 可无界占用内存 | 改用 temporary files，解析前执行 4 MiB 上限 | runner contract 回归 |
| 16 | Medium | Wheel Eval | dependency digest 描述宿主环境，runner 继承全部 secrets | digest 改为 isolated target file set；进程环境改为 allowlist；安装增加 `--no-index` | distinct-wheel command 测试 |
| 17 | Medium | Schemas | 多个公开 JSON output 缺少规范 validator | 新增 Strategy Candidates、Fidelity、Experiment、Publication Receipt、Knowledge Query Result、Content Pipeline 六个 schema，并在写入前验证 | 全 schema meta-test |
| 18 | Medium | Packaging | release topology 分散硬编码，source ZIP 缺 tests/evals | 新增 canonical release manifest；source ZIP 纳入 tests/evals/lockfile；runtime adapters继续保持精简 | package/install/source inventory gates |
| 19 | Medium | Blind Review | deterministic blind pack 与 adjudicator contract 不兼容 | blind pack/key 改用统一 `{suite_id, pairs}` contract | eval generation 与 adjudicator兼容性检查 |
| 20 | Medium | Atomic IO | workflow/eval/report 临时文件路径和 durability 不一致 | 使用随机 `mkstemp`、fsync、atomic replace；关键目录 fsync | workflow concurrency 与持久化回归 |

## 仍保持 Missing Evidence 的项目

| 项目 | 当前状态 | 完成条件 |
| --- | --- | --- |
| CI artifact attestation | missing evidence | 正式 workflow 运行，并独立执行 `gh attestation verify` |
| 人类 blind review | missing evidence | 完成主审、≥20% 独立复审、kappa gate |
| 真实平台 benchmark | missing evidence | 使用固定 panel、相同 collection policy、真实平台 observation |
| Strategy external effect | missing evidence | 验证 publication receipt、完整 observation window、同 panel visibility report |
| Knowledge production eval | missing evidence | 真实知识库 snapshot、人工实体/关系 gold set、增量一致性 benchmark |
| Adoption evidence | missing evidence | 真实团队安装、执行、失败恢复和留存数据 |
| Commercial legal review | missing evidence | 法律责任人签署复核记录 |

## 发布边界

- 目标成熟度：Experimental / Library。
- Production promotion：继续 blocked。
- 本轮未创建 tag、未发布 GitHub Release、未推送远端、未生成可信构建声明。
- 本地 provenance 继续声明 `local-unsigned`、`trusted: false`、无 SLSA level claim。

## 最终门禁结果

| Gate | 结果 |
| --- | --- |
| Pytest | 通过，1 项环境条件性 skip |
| Router / Shadow / Trigger / Output Eval | precision 1.0、recall 1.0、trigger 1.0、contract 1.0、fabricated citations 0 |
| Package Verification | 11/11，通过；双构建 hash 一致 |
| Install Simulation | source CLI 8 项、10 个非 source ZIP 独立安装与 provider smoke 通过 |
| SBOM / Local Provenance | 2 个声明依赖、11 个 release artifacts，通过；builder 仍为 local-unsigned |
| yao-meta Library Gates | 92/92 deterministic commands 通过；17 项 missing-evidence waiver；release blocking 0 |
| Repository Verify | 通过 |
| Diff Hygiene | `git diff --check` 通过 |

当前测试集合收集到 557 项测试，其中 1 项按环境条件跳过。

## 最终验收命令

```bash
python -m pytest -q
python scripts/run_evals.py
python scripts/verify_packages.py
python scripts/install_simulation.py --target all
python scripts/generate_sbom.py
python scripts/generate_provenance.py
python scripts/verify_provenance.py
python scripts/render_production_readiness.py
python scripts/run_yao_meta_gates.py --verify-existing
python scripts/verify_repository.py
```

本文件记录本轮复审完成时的最后验收状态。门禁报告中的时间戳和 digest 已在最后一次运行后刷新。
