# Standalone report contract

The run contains the normalized generated brief, replay source snapshots, crawl manifest, sampling plan, site diagnosis, one JSON artifact per selected page, evidence ledger, remediation backlog, quality report, lineage, manifest, and `report.html`.

`report.html` is one offline file with packaged HTML, CSS, JavaScript, and Apache ECharts inlined at generation time. Its internal report format is version `2`; the public Artifact Bus protocol and Skill contract remain `1.0.0`. The report follows the normalized `zh-CN` or `en-US` locale and uses the ten-module structure in `report-module-contract.md`. The full demo renders 23 chart views, with the eight-axis radar at the top. Live reports replace ineligible charts with explicit evidence gaps and never turn missing values into zero.

Every chart has an adjacent table and a visible interpretation line. Every observed page includes all nineteen checks with raw value, threshold, weight, status, score, evidence ID, and remediation. The report supports 1280 px, 375 px, and 320 px viewports, sticky keyboard-accessible navigation, print, reduced motion, escaped source text, restrictive Content Security Policy, and zero runtime network requests. Visual rules are defined in `report-design-system.md`.
