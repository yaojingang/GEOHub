# Evidence policy

Evidence inputs require a unique label, claim, and absolute source URI. Labels serve only as input handles; normalized briefs replace them with deterministic content-derived IDs. Entity, dimension, and numeric score fields may support comparisons and rankings.

Only input evidence claims enter `content.json.factual_claims`. Each claim carries one or more ledger-resolvable `evidence_ids`. Refine profiles bind each preserved source claim only when NFKC normalization, case folding, whitespace normalization, and trailing-punctuation normalization produce strict equality. Substring and overlap matches never unlock a draft. Unmatched source claims retain empty `evidence_ids`, remain `unverified`, and keep the content specification in draft. General methods, templates, and editorial suggestions carry a `guidance` marker. Comparison and ranking never fill evidence gaps by inference.

`content-evidence-units.json` classifies input evidence, preserved source claims, research-method controls, operational guidance, and evidence gaps. Research-method units use source IDs from `research-context.json`; they remain method guidance and do not become factual claims or effect promises.
