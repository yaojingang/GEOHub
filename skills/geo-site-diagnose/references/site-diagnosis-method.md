# Website GEO diagnosis method

The capability starts from one public URL and creates a bounded, replayable website diagnosis. It fetches the homepage, robots.txt, at most five same-host XML sitemaps, and homepage links. The inventory is capped at 500 canonical URLs. Query strings, fragments, login and checkout paths, file downloads, unsupported media, off-host links, private addresses, and unsafe redirects are excluded.

The sampler recognizes ten page families: homepage, organization, offering, collection, editorial, knowledge, proof, comparison, transaction, and support. It selects at most one page per family and never analyzes more than ten pages. Every selected record retains the type confidence, representativeness score, inventory sources, sitemap lastmod, and selection reason.

HTTP is the primary renderer. In `auto` mode, a page with fewer than 200 visible characters and script-shell signals may use the optional Playwright renderer. Browser traffic stays on the validated host, blocks media, fonts, downloads, and off-host requests, and maps the host to a validated public address. Missing browser support becomes `render_gap`.

Every fetched resource is snapshotted under `input/sources/` with a SHA-256-bound evidence ID. Unavailable or blocked representative pages remain `source_gap`; the implementation does not infer their content. The run publishes atomically through the Artifact Bus.
