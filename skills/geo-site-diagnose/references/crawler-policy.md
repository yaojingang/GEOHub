# Governed crawler policy

- Public HTTP(S) only; credentials, localhost, non-public IP addresses, and unsafe redirects fail closed.
- The canonical homepage redirect establishes the approved host. Expanded discovery cannot leave that host.
- Expanded page fetching honors robots.txt with the declared `GEOHubSiteAudit/0.7` user-agent family; the exact HTTP user-agent is preserved in `crawl-manifest.json`.
- Budgets: 500 inventory URLs, five sitemap files, ten representative pages, 2 MB per resource, 15 MB total, 90 seconds total.
- DTD and entity-bearing sitemap XML is rejected. Unsupported content types stay source gaps.
- Browser rendering is optional and never widens the network boundary.
- No authentication, cookies, forms, checkout actions, downloads, publication, or website modification.
- OAI-SearchBot, Googlebot, and Bingbot inform search access. GPTBot and Google-Extended remain training-control information.
