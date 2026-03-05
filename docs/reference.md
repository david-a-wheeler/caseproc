# caseproc Reference

`caseproc` processes LTAC (Lightweight Text Assurance Case) files and injects
rendered views into Markdown/HTML documents.

## LTAC syntax

Each element occupies one line, indented with two spaces per level:

```
- TYPE [^][IDENTIFIER][: statement text] [(reference)] [{options}]
```

- The bullet marker is `-` or `*`.
- `TYPE` is one of: `Claim`, `Strategy`, `Evidence`, `Justification`,
  `Context`, `Assumption`, `Relation`, `Link`, `Connector`.
- `^IDENTIFIER` marks a *citation* — a reference to an element defined
  elsewhere (in another package or file).  `^[PkgName] IDENTIFIER` cites
  the element and asserts it belongs to the named package.
- `statement text` is free text following `: `.
- `(reference)` is an external reference URL or filename in parentheses.
  See [External references](#external-references) for resolution rules.
- `{options}` is a space-separated list of assertion-status flags:
  `needsSupport`, `axiomatic`, `defeated`, `assumed`, `counter`, `abstract`.

A blank line or `//`-comment line ends the current package.

### External references

The parenthesized reference `(ref)` on a node becomes a hyperlink in
diagram output.  Resolution depends on whether `ref` is absolute or relative
and whether `base_url` is set:

| `ref` form | `base_url` | Result |
|---|---|---|
| `http://…`, `https://…`, or `file:///…` | any | `ref` used as-is |
| starts with `/` (absolute path) | any | `ref` used as-is |
| relative | empty | `ref` used as-is |
| relative | non-empty | `dirname(base_url) + "/" + ref` |

So with `base_url` set to the GitHub URL of the output document, a relative
reference like `hara.pdf` is automatically resolved to the full URL of that
file alongside the document — making mermaid click targets work on GitHub.

## Selectors

Selectors are used with `--select` or inside document regions.

| Selector | Description |
|---|---|
| `ltac/markdown [ID\|*]` | Indented Markdown bullet list |
| `ltac/html [ID\|*]` | Nested HTML `<ul>` list |
| `sacm/mermaid [ID\|*]` | SACM flowchart (Mermaid, bottom-up) |
| `gsn/mermaid [ID\|*]` | GSN flowchart (Mermaid, top-down) |
| `statement ID` | Single-line statement for an element |
| `references ID` | Markdown links to packages that reference the element |
| `info ID` | Statement followed by references |

Omit `ID` in filter mode to use the element set by the nearest preceding
document header.  Use `*` to render all packages (`ltac/*`,
`sacm/mermaid`, and `gsn/mermaid` only).

### Mermaid click links

In `sacm/mermaid` and `gsn/mermaid` output, each identified node gets a
`click` line linking to a URL determined as follows:

1. If the node has an external reference `(ref)`: resolved as described
   in [External references](#external-references) above.
2. If `base_url` is set and the node is a **citation** (`^ID`): links to
   the package section header in the document
   (`base_url + "#package-id"`).
3. If `base_url` is set and the node is **declared** (not a citation):
   links to the element's own content heading in the document
   (`base_url + "#type-id-statement-text"`).
4. If `base_url` is empty and no external reference: no click line.

## Configuration

Configuration is supplied as a JSON object via `--config FILE`.
All keys are optional; omitted keys use their defaults.

| Key | Default | Description |
|---|---|---|
| `base_url` | `""` | Base URL for hyperlinks in `sacm/mermaid` and `gsn/mermaid` output. Set to the URL of the rendered output file so that diagram node clicks navigate to the right anchors. |
| `markdown_base_url` | `""` | Base URL for hyperlinks in `ltac/markdown` and `ltac/html` output. |
| `pkg_label` | `"Package "` | Word used to identify packages in headers and output. |
| `pkg_header_prefix` | `"### "` | String prepended to each package header when rendering `*`. |
| `pkg_header_suffix` | `"\n"` | String appended after each package header when rendering `*`. |
| `bottom_padding` | `true` | Add an invisible BottomPadding node in mermaid diagrams to prevent GitHub's diagram controls from obscuring the bottom of the diagram. |
| `update` | `false` | If true, rewrite stale document header statements to match the LTAC instead of warning. |

### Config file naming convention (tests)

Test fixture config files follow the pattern `PREFIX.config` in
`tests/fixtures/`.  The prefix matches the LTAC base name when one LTAC maps
to one test scenario (e.g. `badgeapp-top.config` for `badgeapp-top.ltac`).
When a single LTAC is used for multiple scenarios, the prefix matches the
expected output base name (e.g. `simple.sacm.mermaid.config`,
`simple.gsn.mermaid.config`, `doc-simple.config`).

## Validations

The following checks always run when an LTAC file is loaded:

- **No circularities** — following citations and structural children must
  never form a loop (prevents circular reasoning).  A circularity is a fatal
  error showing the full cycle trail (e.g. `C2 -> C4 -> C2`).
- **Structural parents** — `Claim` and `Strategy` must not appear as direct
  children of `Evidence`, `Context`, or `Assumption`.
- **Unique declarations** — each identifier must be declared (without `^`)
  exactly once.
- **Consistent type** — every use of the same identifier (declarations and
  citations) must have the same element type.
- **Consistent statement** — statement text must be the same wherever the
  same identifier appears.
- **Unambiguous assertion status** — a node may carry at most one SACM
  assertion status (`NeedsSupport`, `Assumed`, `Axiomatic`, `Defeated`,
  `AsCited`; SACM spec section 11).
- **Declared citations** — any `^ID` citation must have a matching
  declaration somewhere in the loaded LTAC.
- **Correct citation package** — `^[PkgName] ID` asserts the element belongs
  to the named package; a mismatch is flagged.

Additional checks when document files are also processed:

- Document headers matching `TYPE ID` or `TYPE ID: statement` are
  cross-checked against the LTAC.  An unknown ID is flagged; a mismatched
  statement produces a warning (or is rewritten if `update` is true).
- Every declared LTAC element must have a corresponding document header.

## Document integration

In filter mode (no `--select`), `caseproc` reads Markdown/HTML files and
replaces the content of `<!-- caseproc SELECTOR -->…<!-- end caseproc -->`
regions with fresh rendered output.

Use `--validate` to check the LTAC and document consistency without producing
output.  Use `--inline` to rewrite files in-place atomically.
