# GEO Citation Lab 对齐审计

状态：确认门前研究资产

审计日期：2026-08-10

研究基线：`yaojingang/geo-citation-lab@90ad40cf059f300f23fd874353767e1d19ccb815`

机器可读矩阵：[research-evidence-matrix.json](../../reports/research-evidence-matrix.json)

## 结论

当前 `geo`、`geo-discover`、`geo-diagnose`、`geo-content` 和共享内核的证据边界总体符合研究材料。它们生成离线、可追溯、带证据状态的工作产物，并且没有宣称引用、排名、流量或转化结果。该边界应当保留。

研究材料能够支持三类产品判断：

1. 语义相关、来源可核验、结构清晰、查询覆盖和证据冲突处理值得作为内容与评估假设。
2. 引擎、界面、语言、地区、时间和竞争环境会改变结果，单次测量不足以表达真实分布。
3. 多项基准给出空结果、负结果或退化结果，内容改写缺少跨平台稳定增益证据。

本审计的交付状态为 `DONE_WITH_CONCERNS`。关注点集中在效果证据：现有研究无法为当前模式提供通用的线上效果承诺，也无法支持将启发式分数解释为真实平台表现。审计确认门冻结 `strategy`、`knowledge`、`publish`、`measure` 的运行状态。

2026-08-11 的用户确认已解除 `measure` 冻结。`geo-measure 1.0` 仅聚合用户提供的离线观测，保留平台范围、时间、分子、分母、缺失回答、排除原因和 Wilson 区间，并统一输出 `causal_status: descriptive`。它不连接平台、不登录账户、不执行持续监测，也不提供效果保证。`strategy`、`knowledge`、`publish` 继续保持 planned。

## 范围与材料

审计仅使用研究仓库固定提交中已跟踪的材料：

- D01 和 D02 两个数据来源。
- P01 至 P54 共 54 篇论文的目录元数据、PDF 摘要、方法、结果、结论和局限。
- 海外实验报告、中文数据报告、质量报告、数据字典和静态报告。
- 已跟踪的 `geo-assessment` 来源映射及问题溯源文件。

研究来源映射冻结于 2026-08-04，共包含 56 个来源。未跟踪材料全部排除。审计范围止于文档和证据矩阵；运行时、Schema、Manifest、Registry、Skill 状态、版本和安装包均不在变更范围内。

## 方法

### 证据核验状态

| 状态 | 含义 | 本次数量 |
| --- | --- | ---: |
| `reproduced` | 使用已提交源数据独立重算描述性结果 | 1 |
| `source-reported` | 在已提交数据报告中核对口径和内部一致性，未重算原始记录 | 1 |
| `paper-reported` | 核对论文方法与结果，本审计未重跑实验 | 43 |
| `not-reproducible` | 概念性材料、私有输入或方法与溯源不足，无法独立复现 | 11 |

`paper-reported` 表示论文中确实存在对应设计与结论。它不代表复现成功。工程单元测试、契约测试和回归测试只证明软件行为，不能充当引用、排名、流量、转化或收入效果证据。

### 声明类型

每个来源使用一个或多个声明类型：

- `causal`：随机实验或准实验估计干预效果。
- `benchmark`：固定任务、语料、模拟器或评估框架的比较。
- `observational-correlation`：无干预分配的观察相关。
- `mechanism`：检索、引用、排序或评估过程的机制分析。
- `governance`：政策、安全、溯源、评估或运营控制。
- `null-result`：缺失、微弱、不一致或负向的结果。

### 核验过程

1. 以固定提交导出已跟踪文件，并核对研究仓库的 `AGENTS.md`、`README.md`、许可证和第三方通知。
2. 核对 54 条论文目录记录与固定 PDF 首页正式标题、方法、实验、结论及局限。机器矩阵的 `title` 保存 PDF 正式标题，`catalog_title` 精确保留 source map 目录别名。
3. 对 D01 的提交 CSV 做标准库独立重算，检查行数、提示词覆盖、引用数、抓取成功率、构造代理分数均值、相关系数和布尔特征对照。
4. 对 D02 核对提交的 release statistics、quality report、数据字典、静态报告和来源映射。原始记录的全量重算不属于本次文档审计。
5. 将每个来源映射至产品表面、证据处置、冲突、局限和升级建议。

## 数据来源核验

### D01：跨平台引用选择与答案吸收实验

独立重算得到：

| 平台 | 提示词数 | 触发提示词 | 引用记录 | 平均引用数 | 中位数 | 最大值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ChatGPT | 587 | 579 | 4,047 | 6.8807 | 6 | 21 |
| Google | 602 | 600 | 7,290 | 12.0598 | 12 | 37 |
| Perplexity | 602 | 602 | 9,844 | 16.3522 | 17 | 27 |

特征表共有 23,745 条记录，其中 18,151 条抓取成功，成功率为 76.4414%。`influence_score` 是构造的答案参与度代理分数，不是独立观测的真实结果变量。它按以下权重合成：引用次数 0.20、首次位置 0.15、回答段落覆盖率 0.20、TF-IDF 余弦相似度 0.25、bigram 与 trigram 重叠均值 0.20。按平台重算的代理分数均值为 ChatGPT 0.2713、Google 0.0584、Perplexity 0.0646。

页面结构、内容体裁、语义对齐和独立 LLM 评分与该代理分数的相关可作为观察性线索。引用次数、首次位置、回答段落覆盖率、TF-IDF 和 n-gram 重叠属于代理分数的定义组件；这些组成变量与代理分数的相关属于机械相关，不能充当独立原因证据。其余重算相关系数中，LLM relevance 为 0.4322、answer-citation embedding 为 0.3561、LLM content quality 为 0.2917、question-citation embedding 为 0.2548。

布尔特征的描述性对照包含定义、数字、比较、how-to 和代码的正向差异。Q&A 格式的均值对照为 0.0947 对 0.1005，差异约为 -5.7%，属于空结果或弱负结果。全部差异都来自观察记录，不能转换为因果内容配方。

发现一处版本冲突：QUICK_REPORT 中的平台代理分数均值为 0.2567、0.0455、0.0548；最终报告和 CSV 重算为 0.2713、0.0584、0.0646。最终报告标记了重算版本，本审计采用 CSV 重算值，并将 QUICK_REPORT 数值登记为过期。

主要局限：

- ChatGPT 比另两个平台少 15 个提示词。
- 原 CSV 含 16 行重复表头，重算时已识别并排除。
- 地区和语言存在 unknown 或 WW 值，网站类型包含噪声。
- 静态快照缺少一致的运行时间、模型版本和重复试验边界。
- `influence_score` 是答案参与度的构造代理，无法独立证明来源对回答的真实影响。
- 组成变量与 `influence_score` 的相关不能解释成独立原因关系。
- P16 使用同一数据家族，不能作为 D01 的独立复现。

### D02：CN-GEO 中文引用数据集

提交报告标记版本 2.0.1，发布日期为 2026-07-14。来源报告包含：

- 214,119 条记录、64 个分片、12 个界面或平台代码。
- 609 个历史 prompt ID、620 个标准化问题。
- 9,878 个来源站点、107,659 个页面。
- 24,274 条额外完全重复记录。
- 211,248 条有效 HTTP URL、1,738 条非空无效 URL、1,133 条空 URL。
- 缺失字段包括 domain 2,802、prompt_id 4,433、published_at 74,509，另有 8,800 个零值时间占位、quote_index 3,545、title 1,981、site 3,573、snippet 7,816。

`responses` 表保持为空，因为数据缺少可靠的回答或运行边界。它也缺少一致的模型版本和 `collected_at`。因此无法计算每次回答的引用位置、推荐率、情绪趋势、时间趋势或内容干预效果。TYQWA 和 TXYBA 的移动端映射来自后缀配对推断，仍需原始来源字典确认。页面特征为确定性字段，不包含嵌入、品牌实体或情绪标注。

P22 使用同一中文数据家族，不能作为 D02 的独立复现。

## 产品表面对齐审计

### `geo`

`geo` 负责路由和模式契约。研究材料不能证明路由本身带来引用或流量效果，当前实现也没有提出此类声明。结论：保留当前证据边界，将路由测试解释为软件行为证据。

### `geo-discover`

P47 支持查询多样性在部分 agentic benchmark 中的价值，P14 支持重复试验，P46 和 P49 支持将检索决策、成本与时机显式化。当前 learn、compare、evaluate、act 四种任务形式属于确定性规划启发式。结论：可以继续输出机会假设；不得推断搜索量、排名、引用率或转化。

P1 建议：未来 artifact 可记录查询来源、变体类型、语言、地区、引擎、界面、运行时间、重复次数和淘汰原因。

### `geo-diagnose`

D01、P12、P16、P18、P19、P21 和 P22 为结构、语义、品牌或来源类型提供观察相关或基准证据。P13、P18 和 P42 同时显示结构或改写可能无效或退化。当前 observed、provided、input_gap、inferred 标签能够约束证据强度。

结论：保留显式 URL、用户 HTML 和已提供证据的输入边界。所有评分只表示 readiness heuristic。它们不能表示引擎真实引用概率、排名或流量。

### `geo-content` 与七种模式

`geo-content` 是 active 聚合表面，下面保留七个 active mode。研究中没有针对该聚合表面或七模式组合的总体效果估计。当前可审计依据集中于证据保真、语义保留、不确定性和安全治理。机器可读矩阵共列 17 个表面条目：12 个 active、4 个 planned、1 个 boundary。

| 模式 | 研究对齐 | 决策 |
| --- | --- | --- |
| `title` | P10、P45 支持语义和表达方式可能影响选取；跨平台稳定效果未成立 | 保留安全标题生成；禁止排名与点击承诺 |
| `explainer` | D01、P16、P25 支持语义相关和可核验证据；格式特征多为观察相关 | 使用证据链接与限定语；格式作为待验证假设 |
| `comparison` | 缺少该模式的效果证据。P13 和 P42 约束效果外推，P25 仅支持冲突与证据治理 | 统一标准、透明方法和禁止无证据胜者属于治理规则；不宣称该模式提升引用或排名 |
| `ranking` | P31、P35、P38、P39、P43 揭示操纵风险，P13 显示竞争会稀释收益 | 强制方法透明、证据追溯和安全警告；禁止外部排名保证 |
| `page-blueprint` | D01、P18、P19、P41 讨论结构和多模态表面；证据依赖基准 | 蓝图作为可测试结构建议；不生成效果百分比 |
| `refine` | P07、P09、P10 提供优化方法，P13、P18、P41、P42 报告退化或小效果 | 优先语义保真、事实准确和可逆编辑；记录空结果 |
| `article-friendly` | D01 和 P16 提供描述性内容特征；发布格式本身没有已验证提升 | 输出适合发布的结构，同时分离格式质量与效果声明 |

### 共享内核

Artifact Bus、Registry 和 resolver、证据与查询结构、机会与内容结构、质量和 run manifest 契约，整体符合 P24、P25、P32、P46、P53、P54 强调的溯源、冲突、政策、校准和可审计要求。

P0 规则：

- 证据来源、输入缺口、推断和冲突必须保留。
- 质量门应检查契约、事实支持、安全和回归。
- 工程测试结果不得写入效果证据字段。
- 自动 judge 的结果要标记模型、策略、校准集和人工检查状态。

### Planned 表面

| 表面 | 研究要求 | 当前决策 |
| --- | --- | --- |
| `strategy` | P03、P12、P14、P17、P21 表明平台和品牌分层明显 | 保持 planned；先定义假设、分层和停止条件 |
| `knowledge` | P25、P32、P34、P36、P37、P50 至 P52 要求来源、冲突、分块和安全控制 | 保持 planned；先定义权利、溯源、冲突、时效和投毒防护 |
| `publish` | P44 的生产结果为私有、平台特定且不可独立核验 | 保持 planned；先定义授权、预览、可逆动作和变更记录 |
| `measure` | P14、P15、P17、P21、P22、P23、P53、P54 要求重复试验、实验标签、缺失回答核算和人工校准 | 用户确认后启用严格离线聚合；每项指标记录合格试验、已回答、缺失原因、分子分母、纳排标准和区间方法 |

### SEO-GEO 边界

P11、P13、P18、P21、P23、P34 和 P40 都表明传统检索、索引、候选排序或安全过滤仍是上游因素。传统 SEO 指标与运营能力继续留在未来独立能力中，具体包括 search volume、keyword difficulty、SERP rank、traffic attribution、indexation、Core Web Vitals、internal-link operations 和 Search Console。

`geo-discover` 继续保留离线 query variant 与 keyword variant 生成，用于任务拆解和研究规划。这些变体不得附带量级、难度、SERP 排名或流量推断。

该边界能够避免把检索排名研究误用为生成式引用效果，也能避免把引用出现误用为商业流量效果。

## 冲突、局限与风险

1. D01 的快速报告含过期代理分数均值，采用 CSV 重算和最终报告值。该代理分数由答案参与度相关组件构成，不能当作独立真实结果变量。
2. P16 与 D01、P22 与 D02 共享数据家族，证据计数需要去重。
3. P01、P05、P07、P09、P10 报告部分基准增益；P13、P18、P41、P42 报告空结果、负结果或结构退化。产品只能表达条件化假设。
4. P14、P17、P21、P23 显示跨日、跨引擎、跨界面和查询措辞的明显变化。单次截图或单次回答不能充当稳定测量。
5. P19 和 P28 的出版元数据、引用或方法支持不足，效果声明排除于产品指导。
6. P17、P44、P53、P54 依赖私有日志、标签、模型或生产系统，独立复现不可用。
7. 多数论文为预印本或快速变化系统的快照。模型版本、检索器、提示、语言和地区都限制外推。
8. 自动 judge 常见于 benchmark。它可能具有位置、表达和模型偏差，必须保留校准与人工复核状态。
9. 对抗研究证明可操纵性和安全风险。它们不能转换为正常内容优化建议。
10. 18 篇固定 PDF 的正式标题与 source map 目录别名存在实质差异。机器矩阵同时保存 `title` 和 `catalog_title`，并以 ID 和 URL 维持稳定来源身份。

## 升级建议

### P0：确认前保持

- 所有 active 模式继续禁止引用、排名、流量、转化和收入保证。
- 观察相关不能写成因果建议，benchmark 结果不能写成线上效果。
- `strategy`、`knowledge`、`publish` 继续不可运行；`measure` 只接受显式离线观测。
- 工程测试只进入契约或回归证据。
- 私有结果和弱溯源材料不得成为核心 tactic 依据。
- 内容生成保留事实支持、语义保真、冲突和安全检查。

### P1：确认后设计

- measure artifact 已增加 intervention、comparator、engine、interface、language、geography、collected_at、model_version、sample_unit、trial_count、eligible_trial_count、answered_count、missing_answer_count、missing_answer_reason、numerator、denominator、inclusion_criteria、exclusion_criteria、interval_lower、interval_upper、interval_method。
- 同时记录提升、空结果、负结果、退化和停止原因。
- 为内容评估增加 prompt injection、retrieval poisoning、rank manipulation 和 semantic drift 检查。
- 为数据快照增加版本、校验和、授权、权利范围和运行边界。

### P2：研究计划

- 预注册随机内容干预，使用重复平台采样、稳定对照、人工事实审查和置信区间。
- 建设带时间戳、模型版本和运行边界的中文纵向基准。
- 对查询多样化、内容结构和证据表达分别做单因素或分阶段干预，降低机制混淆。
- 报告按引擎、界面、语言、地区、品牌层级和查询类型分层的分布。

## 确认门建议

已确认以下研究政策：证据状态词表、声明类型、无效果保证、重复测量要求、SEO-GEO 边界、安全治理和 planned 表面冻结。`measure` 的确认范围仅覆盖离线描述性聚合。

其他运行时扩展仍需单独确认。未来实现必须先定义可验证的 artifact 和失败模式，再将研究假设接入产品。任何线上效果声明都需要独立测量资产和适当实验设计。

## 附录 A：P01 至 P54 逐篇审计

完整正式标题、目录别名、URL、适用表面和许可说明见机器可读矩阵。附录链接文字可以使用短名；方法核验以固定 PDF 的首页正式标题为准，并保留 source map 目录别名。

| ID | 论文与方法 | 主要结果或空结果 | 类型 | 状态与处置 |
| --- | --- | --- | --- | --- |
| P01 | [GEO](https://arxiv.org/pdf/2311.09735)，GEO-Bench 改写与有限线上引擎测试 | 引用、统计和流畅度在部分条件提升指标；关键词堆叠可能退化 | benchmark, mechanism | paper-reported；条件化内容假设 |
| P02 | [Digital Repositories](https://infonomy.scimagoepi.com/index.php/infonomy/en/article/download/115/153/217)，数字仓储概念框架 | 元数据、语义结构和可访问性检查清单；无干预结果 | mechanism, governance | not-reproducible；知识治理参考 |
| P03 | [How to Dominate AI Search](https://arxiv.org/pdf/2509.08919)，跨引擎、语言、地区观察 | 引用模式随引擎、语言和来源类型变化 | observational-correlation, mechanism | paper-reported；发现与测量分层 |
| P04 | [Navigating the Shift](https://arxiv.org/pdf/2601.16858)，搜索和生成回答比较及上下文操纵 | 来源、时效与预训练熟悉度共同影响回答 | benchmark, mechanism | paper-reported；检索边界参考 |
| P05 | [CC-GSEO-Bench](https://arxiv.org/pdf/2509.05607)，内容中心基准与来源移除消融 | 五维为 Exposure、Faithful Credit、Causal Impact、Readability & Structure、Trustworthiness & Safety；strength、coverage、stability 是前三个影响维度的文章级聚合 | benchmark, mechanism | paper-reported；共享质量假设 |
| P06 | [Transformer Content Optimisation](https://arxiv.org/pdf/2507.03169)，1,905 个合成旅行样本 | 模拟可见度提升；无线上验证 | benchmark | paper-reported；不进入效果声明 |
| P07 | [IF-GEO](https://arxiv.org/pdf/2601.13938)，多查询冲突融合 | 联合处理冲突可改善基准稳定性 | benchmark, mechanism | paper-reported；refine 候选 |
| P08 | [RAID](https://arxiv.org/pdf/2508.11158)，意图和角色增强 GEO-Bench | 测试提示下内容对齐改善 | benchmark, mechanism | paper-reported；discover 候选 |
| P09 | [FeatGEO](https://arxiv.org/pdf/2604.19113)，结构、内容和语言特征多目标优化 | 部分基准优于直接改写，成本较高 | benchmark, mechanism | paper-reported；蓝图候选 |
| P10 | [AutoGEO](https://arxiv.org/pdf/2510.11438)，偏好规则提取与改写 | 选定数据和模型上指标提高，规则依赖模型 | benchmark, mechanism | paper-reported；不外推通用配方 |
| P11 | [White Hat SEO](https://arxiv.org/pdf/2502.07315)，稠密和稀疏检索排序 | 改写可改变传统检索位置，并带来保真权衡 | benchmark, mechanism | paper-reported；SEO 边界 |
| P12 | [GEO-16](https://arxiv.org/pdf/2509.10762)，70 个 B2B SaaS 提示、Brave、Google AIO、Perplexity 三引擎和 16 个审计支柱 | 构造的 16 支柱分数与引用相关；未识别引擎或页面信号的因果效应 | observational-correlation | paper-reported；diagnose 仅作启发式 |
| P13 | [C-SEO Bench](https://arxiv.org/pdf/2506.11097)，1,900 查询与 16,000 文档竞争基准 | 多数改写无显著收益或降低排名；检索位置影响强 | benchmark, mechanism, null-result | paper-reported；核心边界证据 |
| P14 | [Don’t Measure Once](https://arxiv.org/pdf/2604.07585)，四引擎约 45 天重复观测 | 来源集合跨日和重复运行变化明显 | observational-correlation, mechanism | paper-reported；measure 需分布 |
| P15 | [AEO Natural Experiment](https://arxiv.org/pdf/2606.04362)，中断时间序列与对照 | 水平变化存在，斜率不显著；预趋势和非随机发布限制归因 | causal, observational-correlation, null-result | paper-reported；因果限定 |
| P16 | [Citation Selection to Absorption](https://arxiv.org/pdf/2604.25707)，D01 同源数据分析 | 语义相关和质量与构造的答案参与度代理分数相关；Q&A 对照弱负 | observational-correlation, mechanism, null-result | paper-reported；不得计独立复现或真实效果 |
| P17 | [GEO at Scale](https://arxiv.org/pdf/2606.20065)，102 品牌私有遥测 | 品牌层级与可见度相关；未识别建议因果效果 | observational-correlation, mechanism | not-reproducible；排除效果声明 |
| P18 | [SAGEO](https://arxiv.org/pdf/2602.12187)，端到端搜索竞技场 | 仅改正文和任意查询变体经常退化；保留结构可缓解 | benchmark, mechanism, null-result | paper-reported；结构保真边界 |
| P19 | [Structural Feature Engineering](https://arxiv.org/pdf/2603.29979)，结构特征实验声明 | 报告聚合提升，元数据含占位且缺少复现材料 | benchmark | not-reproducible；排除效果声明 |
| P20 | [Generative Search Survey](https://generative-rec.github.io/assets/files/survey.pdf)，生成式搜索与推荐综述 | 提供检索、生成、评估与安全机制分类 | mechanism, governance | paper-reported；机制背景 |
| P21 | [Characterizing Web Search](https://arxiv.org/pdf/2510.11560)，传统搜索与五个生成引擎比较 | 生成引擎可使用常规前列之外的来源，稳定性有限 | benchmark, observational-correlation, mechanism | paper-reported；SEO-GEO 边界 |
| P22 | [Chinese-Language Generative Search](https://arxiv.org/pdf/2607.15771v1)，中文界面大规模观察 | 界面间来源与位置差异明显，多项关系微弱或缺失 | observational-correlation, mechanism, null-result | paper-reported；与 D02 同源 |
| P23 | [How Generative AI Disrupts Search](https://web.njit.edu/~borcea/papers/acm-sigir26.pdf)，约 11,500 查询和扰动 | Google 各表面来源组合不同，措辞可改变结果 | benchmark, observational-correlation, mechanism | paper-reported；快照限定 |
| P24 | [NExT-Search](https://arxiv.org/pdf/2505.14680)，细粒度反馈生态提案 | 定义反馈与治理组件，无实证验证 | mechanism, governance | not-reproducible；共享治理参考 |
| P25 | [Convincing Evidence](https://arxiv.org/pdf/2402.11782)，冲突证据 QA 基准 | 语义相关强于多种风格特征；模型受冲突证据影响 | benchmark, mechanism, null-result | paper-reported；证据冲突控制 |
| P26 | [SEO to AEO](https://www.researchgate.net/publication/399872181_From_SEO_to_Answer_Engine_Optimization_AEO_Generative_Ai_and_the_Transformation_of_Search_Visibility)，概念章节 | 提供测量方向，无主实验 | mechanism, governance | not-reproducible；边界参考 |
| P27 | [Integrated SEO, GEO, AEO](https://ijsrem.com/uploads/production/Optimizing-for-the-Artificial-Intelligence-Driven-Search-Era-An-Integrated-Framework-for-Search-Engine-Optimization-Generative-Engine-Optimization-and-Answer-Engine-Optimization.pdf)，综合框架 | 作者承认缺少实证验证 | mechanism, governance | not-reproducible；策略背景 |
| P28 | [Smart Search Optimization](https://lorojournals.com/index.php/emsj/en/article/download/1728/1679/2401)，小规模文章分析声明 | 大幅流量声明缺少可追溯数据与方法支持 | observational-correlation | not-reproducible；排除效果声明 |
| P29 | [Transition from SEO](https://www.ijcrt.org/papers/IJCRT2510315.pdf)，定性综述与案例 | 总结营销变化，无可复现结果 | mechanism | not-reproducible；边界背景 |
| P30 | [Zero-Click Search](https://ejurnal.kampusakademik.co.id/index.php/jiem/article/download/9040/7646/32415)，30 项资料综述 | 汇总零点击与答案引擎背景，来源异质 | observational-correlation, mechanism | paper-reported；测量背景 |
| P31 | [Adversarial SEO for LLMs](https://arxiv.org/pdf/2406.18382)，50 个控制页面与生产探测 | 策略内容可操纵部分设置，并产生竞争动态 | benchmark, mechanism, governance | paper-reported；安全证据 |
| P32 | [CONFLICTBANK](https://openreview.net/pdf?id=wjHVmgBDzc)，知识冲突基准 | 模型处理内部知识和外部证据冲突的方式不同 | benchmark, mechanism, governance | paper-reported；知识溯源 |
| P33 | [Adversarial Attack Dynamics](https://arxiv.org/pdf/2501.00745)，多参与者竞争模拟 | 竞争采用可削弱单一攻击收益 | benchmark, mechanism, governance, null-result | paper-reported；安全与空结果 |
| P34 | [GASLITE](https://openreview.net/pdf?id=LBd87fWerd)，九个嵌入模型检索投毒 | 少量优化注入可提升目标检索 | benchmark, mechanism, governance | paper-reported；检索安全 |
| P35 | [Product Visibility Manipulation](https://arxiv.org/pdf/2404.07981)，十个虚构产品 | 策略文本改变白盒产品排序 | benchmark, mechanism, governance | paper-reported；安全边界 |
| P36 | [Persistent Pre-Training Poisoning](https://arxiv.org/pdf/2410.13722)，600M 至 7B 从头训练 | 多种投毒在指令微调后持续，部分目标减弱 | benchmark, mechanism, governance, null-result | paper-reported；知识安全 |
| P37 | [PoisonArena](https://arxiv.org/pdf/2505.12574)，多攻击者 RAG 基准 | 单攻击者成功在竞争中常下降 | benchmark, governance, null-result | paper-reported；竞争安全 |
| P38 | [RAGDOLL](https://arxiv.org/pdf/2406.03589v1.pdf)，产品页注入与线上探测 | 提示式页面可操纵部分会话搜索排名 | benchmark, mechanism, governance | paper-reported；内容安全 |
| P39 | [StealthRank](https://arxiv.org/pdf/2504.05804)，隐蔽对抗提示优化 | 可改变排名并降低人工可察觉度 | benchmark, mechanism, governance | paper-reported；红队输入 |
| P40 | [LLM Search Resilience](https://arxiv.org/pdf/2603.25500)，1,000 黑帽站点和十系统 | 传统攻击多数被过滤，新型改写和分段仍有效 | benchmark, governance, null-result | paper-reported；SEO 安全边界 |
| P41 | [Caption Injection](https://arxiv.org/pdf/2511.04080)，4,800 多模态样本 | 一个多模态条件小幅正向，多项单模态或基线为负 | benchmark, mechanism, null-result | paper-reported；小效果限定 |
| P42 | [E-GEO](https://arxiv.org/pdf/2511.20867)，电商查询、产品和 15 种改写 | 多数启发式影响小或负向，最佳增益有限 | benchmark, mechanism, null-result | paper-reported；核心空结果 |
| P43 | [MGEO](https://www.researchgate.net/publication/399931268_Multimodal_Generative_Engine_Optimization_Rank_Manipulation_for_Vision-Language_Model_Rankers)，图文联合排序攻击 | 细微图文修改可改变单一 VLM 家族排序 | benchmark, mechanism, governance | paper-reported；多模态安全 |
| P44 | [Pinterest VLM and Agent](https://arxiv.org/pdf/2602.02961)，私有部署案例 | 报告大规模增长结果，日志和归因不可独立核验 | benchmark, observational-correlation, mechanism | not-reproducible；排除效果声明 |
| P45 | [Goliath and David](https://www.researchgate.net/publication/395651066_When_Content_is_Goliath_and_Algorithm_is_David_The_Style_and_Semantic_Effects_of_Generative_Search_Engine)，网站观察、控制 RAG 和随机人类实验 | 风格与语义在测试条件影响选取和偏好 | causal, benchmark, observational-correlation, mechanism | paper-reported；范围限定 |
| P46 | [Decoupled Search Grounding](https://arxiv.org/pdf/2606.18947)，五模型多基准 | 解耦检索契约在部分基准接近原生搜索并降低成本 | benchmark, mechanism | paper-reported；共享契约候选 |
| P47 | [DivInit](https://arxiv.org/pdf/2606.17209)，五开源模型和八基准 | 多样查询改善部分模型，低能力模型增益有限 | benchmark, mechanism, null-result | paper-reported；discover 候选 |
| P48 | [ScholarQuest](https://arxiv.org/pdf/2606.20235)，1,000 个 CS 主题和 arXiv 环境 | agentic search 优于单次搜索，效率和约束稳健性仍弱 | benchmark, mechanism, null-result | paper-reported；学术域限定 |
| P49 | [Streaming Tool Use](https://arxiv.org/pdf/2606.20113)，1,371 个 CRAG 问题和流式 harness | 决定性词较晚时提前检索收益趋近于零 | benchmark, mechanism, null-result | paper-reported；时机条件化 |
| P50 | [MCompassRAG](https://arxiv.org/pdf/2606.18508)，主题元数据与师生检索 | 离线主题元数据提高部分段落检索指标 | benchmark, mechanism | paper-reported；knowledge 候选 |
| P51 | [SCAR](https://arxiv.org/pdf/2606.16661)，语义连续的相邻块扩展 | 在边界碎片条件改善 recall-token 效率 | benchmark, mechanism | paper-reported；相邻连续性限制 |
| P52 | [SproutRAG](https://arxiv.org/pdf/2606.18381)，长文档层级树和渐进嵌入 | 四个离线基准改善检索与 QA 指标 | benchmark, mechanism | paper-reported；无发布效果 |
| P53 | [App Store Relevance](https://arxiv.org/pdf/2602.23234)，私有 LLM 标签、离线排序和全球 A/B | 论文报告离线与线上产品指标改善 | causal, benchmark, governance | not-reproducible；属于传统 App 搜索 |
| P54 | [SAGE](https://arxiv.org/pdf/2602.07840)，政策、先例、师生蒸馏和生产监测 | 显式政策与人工先例可支撑大规模 judge，需持续人工治理 | benchmark, governance | not-reproducible；治理参考 |

## 附录 B：数据集审计

| ID | 来源 | 状态 | 主要用途 | 关键限制 |
| --- | --- | --- | --- | --- |
| D01 | [跨平台引用选择与答案吸收实验](https://github.com/yaojingang/geo-citation-lab/tree/main/01-geo-experiment-data-report) | reproduced | 描述性平台差异、构造的答案参与度代理分数、特征相关和空结果 | 代理分数非独立真实结果变量；静态快照、非因果、时间与版本边界不足 |
| D02 | [CN-GEO 中文引用数据集](https://github.com/yaojingang/geo-citation-lab/tree/main/03-cn-geo-citation-dataset) | source-reported | 中文来源分布、字段质量和治理需求 | 无可靠运行边界、模型版本、采集时间和干预 |

## 许可与归属

GEO Citation Lab 的原创报告、说明文档、可视化和目录元数据按 CC BY 4.0 提供；代码和脚本按 MIT 提供。D02 上游 CN-GEO 数据标记为 WENDAOstudy/cn-geo-citation-dataset 的 CC BY 4.0 内容。论文 PDF 的权利归作者和出版方，研究仓库没有授予论文内容的再许可权。

本审计仅保留必要元数据、短标题、方法和结论的原创概括及来源链接。没有复制论文长段、论文图表、原始数据记录或私有材料。详细归属和修改说明见 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)。
