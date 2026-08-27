# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
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
