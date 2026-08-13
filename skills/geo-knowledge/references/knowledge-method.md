# Knowledge governance method

## Source contract

Each approved source carries a stable `source_id`, URI, lowercase SHA-256 hash, review timestamp, entities, facts, and relations. Entity identity uses normalized type plus canonical name. Aliases and source IDs remain attached.

## Graph rules

- Facts retain attribute, value, source IDs, and validity date.
- Relations retain subject, predicate, object, confidence, source IDs, and validity date.
- Multiple values for one entity attribute remain present and create a conflict record.
- A repeated source ID, hash, and normalized payload digest is unchanged.
- Updates carry a complete snapshot of all existing source IDs. Added sources may extend it. Partial snapshots and same-hash payload drift fail closed.
- A changed hash replaces that source contribution during a complete rebuild.
- Local queries return the matching entity neighborhood and sources.
- Global queries return communities, coverage, conflicts, and evidence gaps.

Provided source status records caller-supplied provenance. It does not establish reviewer approval or universal factual truth.
