# Changelog

All notable changes to verocase will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-11

Initial release.

### Added

**LTAC file support**
- Parse the verocase extended LTAC (Lightweight Text Assurance Case) format,
  supporting node types: Claim, Strategy, Evidence, Context, Assumption,
  Justification, Link, Relation, and Connector.
- Cross-package citations using `^ID` syntax.
- Node options: `needssupport`, `axiomatic`, `defeated`, `assumed`,
  `abstract`, `counter`.
- External references in parentheses, e.g. `(hazard-analysis.pdf)`.
- Identifier inference from statement text when no explicit ID is given.
- Disambiguation syntax: `()` and `{}` within statement text.
- Auto-discovery of `case.ltac` (and `docs/case.ltac` as fallback); override
  with `--ltac`.

**Document processing**
- Process Markdown (`.md`) and HTML (`.html`) documentation files containing
  `<!-- verocase SELECTOR -->` ... `<!-- end verocase -->` regions.
- Default inline mode: rewrite document files in place, replacing stale region
  content with freshly generated output.
- `--stdout` filter mode: write processed output to stdout without modifying
  any files.
- `--read-only`: load and validate without rewriting document files.
- `--validate`: validate a document without producing any output.
- `--strip`: remove generated content from regions, leaving only the markers.
- Per-document `<!-- verocase-config KEY = VALUE -->` directives to override
  configuration within a document.
- Auto-discovery of `case.md` (and `docs/*.md`, `docs/*.html`); override with
  explicit file arguments.

**Selectors** (used in `<!-- verocase SELECTOR -->` regions and `--select`)
- `element ID` — generate element heading, statement, and cross-reference
  subsections.
- `package ID` / `package *` — generate a diagram for one package or all
  packages.
- `statement ID` — emit the statement text for an element.
- `sacm/mermaid`, `gsn/mermaid` — SACM or GSN diagram in Mermaid syntax.
- `sacm/mermaid/html`, `gsn/mermaid/html` — as above, with a Mermaid JS
  `<script>` tag injected once per HTML document.
- `ltac/markdown`, `ltac/html` — LTAC tree as a formatted list.
- `ltac/txt` — raw LTAC text for an element.
- `referenced_by`, `supported_by`, `supports` — cross-reference subsections.
- `pkg_defines`, `pkg_citing`, `pkg_cited` — package relationship sections.
- `representation` — default representation for a package (configurable).
- `warning` — emit a warning about elements lacking document coverage.
- `stop` — stop inserting stubs after this point (`--fixmissing`).
- `epilogue` — mark the end of main element content.
- Shorthand expansions: `sacm` → `sacm/mermaid`, `gsn` → `gsn/mermaid`,
  `ltac` → `ltac/markdown` (renderer determined by `default_renderer` and
  `default_representation` config keys).

**Diagram rendering**
- SACM diagrams rendered as Mermaid flowcharts, including inference groups
  and Strategy absorption.
- GSN diagrams rendered as Mermaid flowcharts with Connector support.
- Automatic width management for wide packages: narrows diagrams that exceed
  `max_mermaid_children` by keeping only the nearest siblings
  (`narrowed_mermaid_children`) with ellipsis nodes indicating hidden children.
- Hyperlink nodes to anchors in the document via `base_url` /
  `markdown_base_url` configuration.

**LTAC mutation operations**
- `--update`: sync citation statement text from their declarations.
- `--rename OLD NEW`: rename an identifier throughout the LTAC file and all
  document files.
- `--restate ID TEXT`: replace the statement for an identifier.
- `--detach ID`: remove a node from its parent (leaving it parentless).
- `--move ID DEST`: move a node to a new parent.
- All mutations are applied atomically with a timestamped backup snapshot
  created under `.backups/` before any files are modified.

**Document repair**
- `--fixmissing`: insert stub `element` selector regions for LTAC elements
  that have no corresponding document region, positioned near their natural
  order in the document.
- `--fixmisplaced`: reorder `element` selector regions in a document to match
  the order declared in the LTAC file.

**Analysis and reporting**
- `--stats`: print statistics about the LTAC structure (element counts by
  type, package sizes, citations) and processed documents (region counts,
  empty regions).
- `--missing`: report LTAC elements that have no `element` selector in any
  document.
- `--empty`: report `element` selector regions that contain no prose.
- `--orphans`: report stale selector regions referring to identifiers no
  longer in the LTAC file.
- `--misplaced`: report `element` selector regions that are in the wrong
  document order relative to the LTAC file.
- `--leaves`: report leaf elements (no children, not cited).
- `--packages`: report package-level information.

**Validation**
- Structural validation: warn when node types are used in invalid parent
  relationships (e.g. Claim under Evidence).
- Duplicate identifier detection.
- Circularity detection in the LTAC tree.
- Anchor uniqueness checking (no two elements produce the same HTML anchor).
- Citation consistency: cited nodes should have statements matching their
  declaration.
- Indentation error detection in LTAC files.
- Dubious reference heuristic: warn when a parenthetical looks like a prose
  comment rather than an external reference (disable with
  `warn_dubious_reference = false`).
- Element coverage: warn when a declared LTAC element has no `element`
  selector in any processed document.
- `--error` flag to escalate all warnings to errors (non-zero exit).

**Configuration**
- `--config FILE`: load configuration from a JSON file.
- Configuration keys: `base_url`, `markdown_base_url`, `bottom_padding`,
  `default_renderer`, `default_representation`, `document_files`,
  `element_level`, `element_selections`, `ltac_file`, `max_backups`,
  `max_mermaid_children`, `mermaid_js_url`, `narrowed_mermaid_children`,
  `package_level`, `package_selections`, `pkg_label`,
  `warn_dubious_reference`.

**Project bootstrapping**
- `--start`: create initial `case.ltac` and `case.md` stub files.

**Infrastructure**
- CI testing across Python 3.8 through 3.13 via GitHub Actions.
- PyPI publishing via Trusted Publisher (OIDC); no stored API tokens required.
- Reproducible builds: `SOURCE_DATE_EPOCH` is set from the last git commit
  timestamp, producing bit-for-bit identical archives across builds.
- Distributed as a single dependency-free Python script (`verocase.py`) and
  as a PyPI package installable with `pip install verocase`.

[Unreleased]: https://github.com/david-a-wheeler/verocase/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/david-a-wheeler/verocase/releases/tag/v0.1.0
