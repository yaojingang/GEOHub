# Report design system 2

The generated report is a high-trust diagnostic dashboard on a pure white `#FFFFFF` canvas. White applies to the document, modules, chart panels, page sections, mobile menu, and print surface. Ink blue carries primary data and navigation focus. Green, amber, and rust encode observed status with labels or values, so color never carries meaning alone. Whitespace, spacing, and type hierarchy establish depth. One-pixel rules are reserved for sticky navigation, chart containers, dense data tables, and explicit gap states. Gradients, glass effects, decorative backgrounds, and drop shadows are excluded.

## Reading structure

The report follows a summary, evidence, page validation, and remediation sequence. It contains ten primary modules: overall conclusion, access and discovery, architecture coverage, entity clarity, answerability, evidence and citability, authority and trust, structure and freshness, page diagnosis, and remediation roadmap. Each module has one bounded objective, one short verdict, one to three charts, an evidence note, an action note, and an adjacent data table or explicit gap state.

The desktop navigation keeps the GEOHub brand at left and ten section links at right. It remains sticky while scrolling and marks the active section. Below 1024 px, a native `details` menu keeps the same anchors and works without custom controls.

## Layout and type

- Use a 12-column grid with a 1360 px maximum content width
- Keep chart panels in one row equal in height; content sections grow naturally
- Separate primary modules with whitespace instead of full-width horizontal rules
- Keep verdicts, chart insights, evidence notes, and page audits free of decorative divider lines
- Use 420 px for the top radar row and 320 px for standard charts
- Place each two-digit module index above its title. Align the index, title, description, verdict label, verdict text, and chart grid to one shared left edge
- Stack module title and description across the full available text width
- Render the verdict label as its own line and start the verdict text on the next line
- Use system and offline CJK fallback fonts only
- Apply tabular numerals to scores, metrics, and numeric table cells
- Keep Chinese module titles within 18 characters, descriptions within 30 to 56 characters, and chart captions within 14 to 28 characters when the language permits
- Omit the final full stop or period from controlled titles, descriptions, verdicts, and captions
- Preserve punctuation in source excerpts, limitations, and remediation evidence

## Chart grammar

- Use solid fills only. Keep ECharts ARIA enabled with `decal.show` disabled. Exclude hatching, diagonal stripes, dotted textures, decorative background symbols, gradients, and ornamental chart marks
- Encode comparison primarily through position, length, and aligned numeric labels. Use green, amber, rust, and critical red only with a visible status or value label
- Use one circular symbol for scatter plots. Aggregate actions that share the same coordinates and display the aggregate count. Do not repeat severity through triangles, diamonds, or other competing shapes
- Wrap axis labels into complete readable segments. Prefer horizontal wrapped labels over rotated labels, and never truncate controlled chart labels with an ellipsis. When a full action title cannot fit, show rank plus diagnostic dimension and keep the full title in the tooltip and adjacent table
- Keep the top eight-dimension radar free of vertex symbols. Put each score in its axis label and reserve the filled polygon for the readiness profile
- Use horizontal status bars for page-family coverage, a numbered heatmap for representative-page links, and stacked horizontal bars for issue severity. Dense sunburst sectors and force-directed link clusters are excluded from the standard report
- Render the readiness funnel as aligned retention bars. The first valid stage is `100%`; each later width is `stage value / first-stage value`; the visible remainder represents loss; amber appears only on a stage with observed loss. Never map a small numeric loss to an arbitrary minimum funnel width
- Every chart keeps exact values in its visible labels, interpretation line, tooltip, or adjacent table. Visual polish never changes the underlying score, count, denominator, or missing-evidence state

## Responsive and print behavior

Desktop, 375 px, and 320 px surfaces must have no horizontal page overflow. Multi-column charts collapse to one column on narrow screens. Dense tables scroll inside their own containers. Keyboard focus remains visible, section anchors account for the sticky navigation offset, and reduced-motion preferences disable smooth scrolling. Print opens every evidence table, hides navigation, resizes charts, and retains the white canvas.

## Security and portability

The renderer inlines the packaged template, CSS, JavaScript, and Apache ECharts runtime into one HTML file. A restrictive Content Security Policy blocks network connections, external assets, base URL changes, and form submission. All site content is escaped, chart JSON escapes closing script sequences and Unicode line separators, and the generated file contains no absolute local path.
