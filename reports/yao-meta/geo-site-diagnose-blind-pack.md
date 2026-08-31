# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `6`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: 帮我诊断网站GEO：https://example.com

Rubric:
- `contract` (1.0): 必须满足网站诊断输出契约。

### Variant A

抓取同站典型页面，生成 sampling-plan、site-diagnosis、逐页证据、remediation-backlog 和独立 report.html。

### Variant B

给出通用建议。

## Case: missing-url

Prompt: 帮我诊断网站 GEO

Rubric:
- `input` (1.0): 缺少核心输入时只请求网址。

### Variant A

猜测网站常见问题。

### Variant B

只追问一个公开 HTTP(S) 网址。

## Case: boundary

Prompt: 统计这个网站在 ChatGPT 的真实引用次数

Rubric:
- `boundary` (1.0): 不得虚构平台效果。

### Variant A

路由到 geo-measure，并说明需要真实平台观测数据。

### Variant B

引用次数为 42。

## Case: source-gap

Prompt: robots 阻止抓取时继续诊断

Rubric:
- `gap` (1.0): 抓取缺口必须透明。

### Variant A

把页面标记为 source_gap，降低置信度并保留限制。

### Variant B

假设页面信号。

## Case: neighbor

Prompt: 只检查我提供的一个产品页

Rubric:
- `route` (1.0): 单页请求必须保留旧路径。

### Variant A

自动抓取整个网站。

### Variant B

保留 geo-diagnose 单页诊断路径，仅分析明确提供的页面。

## Case: visual-quality

Prompt: 用演示固件生成网站 GEO 报告并检查图表是否清晰、比例是否准确

Rubric:
- `artifact` (1.0): 必须生成可复现的独立实例报告。
- `encoding` (1.0): 图表编码必须清晰且无装饰性纹理。
- `module-heading` (1.0): 十个模块必须共用清晰的标题与结论对齐规则。
- `funnel-ratio` (1.0): 漏斗必须忠实表达阶段保留比例。
- `responsive` (1.0): 窄屏必须保持可读。

### Variant A

生成 reports/examples/geo-site-diagnose-demo.html，使用纯白画布、无纹理纯色图表、统一圆形散点和完整换行标签；模块编号上置，标题、说明和结论统一左对齐，结论正文另起一行；10 → 9 的诊断漏斗显示 90% 保留率，并在 375 px 与 320 px 下保持无横向溢出。

### Variant B

输出带斜纹、三角形标记、标签省略和比例失真的漏斗图，模块编号与标题错位，诊断结论挤在同一行。
