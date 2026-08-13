# MCDA Policy 1.0.0

Non-legacy ranking requires a structured evaluation method. Every criterion declares `name`, positive finite `weight`, and `polarity` of `benefit` or `cost`. The supported policies are:

- normalization: `min-max`
- weighting: `normalized-explicit`
- missing value: `reject`
- tie: `no-winner`

The ranking report retains the raw matrix, normalized matrix, normalized weights, weighted-sum result, TOPSIS-style relative closeness, and sensitivity scenarios. Each weight moves by minus and plus ten percent with renormalization. A changed winner marks the result sensitive. Exact top-score ties produce no winner. Missing, non-finite, incomplete, or incomparable matrices remain blocked by evidence.
