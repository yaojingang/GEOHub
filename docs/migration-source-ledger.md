# Migration Source Ledger

Read-only source baseline: `yaojingang/yao-geo-skills` commit `201c0c45dcf09bb37bc46a467b4baf4d721db205`. The 21 source skills map as follows.

## Runtime namespace migration

Pre-release 0.1 development snapshots used the distribution and CLI `yao-geo`, Python module `yao_geo`, installed data root `share/yao-geo`, generator prefix `yao-geo-*`, and URN prefix `urn:yao-geo:*`. Version 0.2 replaces those surfaces with `geo-seo-hub`, `geo_seo_hub`, `share/geo-seo-hub`, `geo-seo-hub-*`, and `urn:geo-seo-hub:*` respectively. No runtime alias ships in 0.2.

An existing development environment may remove the retired distribution with `python3 -m pip uninstall yao-geo` before installing 0.2. The `geo-*` Skill IDs and Artifact Bus protocol `1.0.0` remain unchanged.

| # | Source skill | Destination | Decision |
| ---: | --- | --- | --- |
| 1 | yao-geo-intent-miner | geo-discover | implemented |
| 2 | yao-geo-panorama-audit | geo-diagnose | implemented |
| 3 | yao-geo-page-audit | geo-diagnose | implemented |
| 4 | yao-geo-title-optimizer | geo-content | implemented |
| 5 | yao-geo-explainer-builder | geo-content | implemented |
| 6 | yao-geo-comparison-builder | geo-content | implemented |
| 7 | yao-geo-ranking-article-builder | geo-content | implemented |
| 8 | yao-geo-page-blueprint | geo-content | implemented |
| 9 | yao-geo-content-refiner | geo-content | implemented |
| 10 | yao-geo-article-friendly | geo-content | implemented |
| 11 | yao-geo-knowledge-base-builder | geo-knowledge | planned |
| 12 | yao-geo-brand-graph | geo-knowledge | planned |
| 13 | yao-geo-execution-roadmap | geo-strategy | planned |
| 14 | yao-geo-effect-monitor | geo-measure | planned |
| 15 | yao-geo-tracking | geo-measure | planned |
| 16 | yao-chatgpt-crawler | excluded | connector/crawler boundary |
| 17 | yao-deepseek-crawler | excluded | connector/crawler boundary |
| 18 | yao-doubao-crawler | excluded | connector/crawler boundary |
| 19 | yao-geoflow-cli | excluded | GEOFlow boundary |
| 20 | yao-geoflow-design | excluded | GEOFlow boundary |
| 21 | yao-geoflow-template | excluded | GEOFlow boundary |

Publishing remains a planned registry domain even though the baseline has no standalone publish package. Local Explainer and Ranking work improved the deliverable into “内容主体 + 补充说明与参考来源”; this behavior informed `geo-content` while preserving evidence limitations. No historical customer reports, font files, or generated outputs were copied.
