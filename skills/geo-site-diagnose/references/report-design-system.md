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
- Stack module title and description across the full available text width
- Use system and offline CJK fallback fonts only
- Apply tabular numerals to scores, metrics, and numeric table cells
- Keep Chinese module titles within 18 characters, descriptions within 30 to 56 characters, and chart captions within 14 to 28 characters when the language permits
- Omit the final full stop or period from controlled titles, descriptions, verdicts, and captions
- Preserve punctuation in source excerpts, limitations, and remediation evidence

## Responsive and print behavior

Desktop, 375 px, and 320 px surfaces must have no horizontal page overflow. Multi-column charts collapse to one column on narrow screens. Dense tables scroll inside their own containers. Keyboard focus remains visible, section anchors account for the sticky navigation offset, and reduced-motion preferences disable smooth scrolling. Print opens every evidence table, hides navigation, resizes charts, and retains the white canvas.

## Security and portability

The renderer inlines the packaged template, CSS, JavaScript, and Apache ECharts runtime into one HTML file. A restrictive Content Security Policy blocks network connections, external assets, base URL changes, and form submission. All site content is escaped, chart JSON escapes closing script sequences and Unicode line separators, and the generated file contains no absolute local path.
