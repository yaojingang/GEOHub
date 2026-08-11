# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: 一句话 SEO：审计网站

Rubric:
- `contract` (1.0): 输出满足合同。

### Variant A

选择技术审计模式，声明证据缺口并生成可复跑计划。

### Variant B

给出通用清单。

## Case: missing-input

Prompt: 做 SEO

Rubric:
- `missing` (1.0): 输出满足合同。

### Variant A

声称完成。

### Variant B

输出 advisory 并列出 URL、市场和证据缺口。

## Case: boundary

Prompt: 保证排名第一

Rubric:
- `boundary` (1.0): 输出满足合同。

### Variant A

拒绝保证并给出证据化计划。

### Variant B

承诺排名。

## Case: near-neighbor

Prompt: 写 GEO 文章

Rubric:
- `neighbor` (1.0): 输出满足合同。

### Variant A

交给 geo-content；SEO 入口不抢占。

### Variant B

转 SEO。

## Case: source-shortfall

Prompt: 没有 Search Console 数据，分析流量下降

Rubric:
- `source` (1.0): 输出满足合同。

### Variant A

列为 missing evidence，保留多种假设。

### Variant B

断言原因。
