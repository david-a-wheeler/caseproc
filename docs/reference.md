# caseproc Reference Manual

`caseproc` reads an assurance case written in
[Extended LTAC format](ltac-extended.txt)
and updates one or more Markdown or HTML documentation files with
automatically generated graphics, hyperlinks, and cross-references.
You edit the LTAC file for the argument structure and the document files
for the supporting detail; `caseproc` keeps them in sync.

---

## LTAC Format

LTAC (Lightweight Text Assurance Case) is a plain-text format for
representing an assurance case argument.
We have extended LTAC to handle larger assurance cases
(e.g., by adding support for multiple packages, citations, and various
markings).

Each element occupies exactly one line, indented with two spaces per level.

### LTAC Element types

| Type | Purpose |
|---|---|
| `Claim` | A true-or-false statement that is asserted to hold |
| `Strategy` | An argument explaining how sub-claims or evidence collectively support the parent claim |
| `Evidence` | An artifact (document, test result, etc.) cited in support of a claim |
| `Context` | Background information or a scope constraint for the parent element |
| `Assumption` | A claim accepted as true without further argument at this point |
| `Justification` | A side-claim or rationale that supports a strategy or higher-level claim |
| `Relation` | Represents a relationship that would otherwise be implied by indentation; useful when you need to apply options to the relationship itself |
| `Link` | A citation of an element already defined earlier in the same package |

### LTAC Line syntax

```
INDENT - TYPE [^][IDENTIFIER][: statement text] [(ext_ref)] [{options}]
```

- **`INDENT`** — two spaces per level; the root element of each package has no indentation.
- **`-`** — the bullet marker (hyphens `-` and asterisks `*` are both accepted).
- **`TYPE`** — one of the types in the table above, or `Link`.
- **`^`** — when present, marks this as a *citation* of an element declared elsewhere (another package).
- **`IDENTIFIER`** — optional; must be unique across the entire LTAC file (except for `Link` entries, which re-use an existing identifier).  Any characters except `:` and `^` are permitted.
- **`: statement text`** — optional descriptive text following the colon.  Text may contain colons.
- **`(ext_ref)`** — optional external reference in parentheses, such as a filename or URL.  Used as a hyperlink target in diagram output.
- **`{options}`** — optional comma-separated list of modifier keywords (see [Options](#options) below).

A `Link` line has a simpler form — just the type keyword and the identifier, with no colon or text:

```
    - Link ExistingId
```

A blank line ends the current package and begins the next one.

### LTAC Package structure

An LTAC file consists of one or more *packages* separated by blank lines.
Each package must begin with a `Claim` at indentation level 0 (no indent).
That top-level claim names the package; the package is identified by
the identifier of that claim.

All elements within a package form a tree, rooted at the top-level claim.
`Link` entries allow a previously defined element within the same package
to be referenced again without repeating it.

### Identifiers

Each identifier must be declared (without `^`) exactly once
across all packages.
Identifiers may contain letters, digits, hyphens, dots, and most other
printable characters, but not `:` or `^`.
Note that space is a legal character in identifiers.
There is no mandated identifier convention; meaningful names like
`AuthnClaim` are encouraged alongside traditional GSN-style names like `G1`.

### Cross-package citations

An element in one package may cite a claim from another package using
the `^` prefix:

```
- Claim ^OtherTop
```

The bare form `^ID` resolves to the declared element with identifier `ID`
in any loaded package.

Cross-package citations are rendered as `asCited` in SACM notation
(double-bracket shape) and as away goals in GSN notation (subroutine shape).
In generated diagrams, clicking a citation navigates to the package
section in the document that includes that element's definition
(so you can see it in context).
Clicking on the element where it's defined will bring you to the
more detailed information about that element (if it exists).

### Reachability

All package roots in a multi-package LTAC file must be *reachable* from the
first element of the first package by following structural children,
citation declarations, and Link targets.
An unreachable package is an error.
(Single-package files are trivially reachable and skip this check.)

### Options

Options are listed inside braces at the end of a line, comma-separated:

```
- Claim C1: The system is safe {defeated}
- Claim C2: Residual risk is acceptable {needsSupport}
```

Each element may carry **at most one** assertion-status option (this
mirrors SACM's mutually exclusive `assertionDeclaration` attribute):

| Option | SACM assertionDeclaration |
|---|---|
| *(none)* | `asserted` (default) |
| `needsSupport` | `needsSupport` |
| `assumed` | `assumed` |
| `axiomatic` | `axiomatic` |
| `defeated` | `defeated` |
| `asCited` | `asCited` |

Other options that may be combined with an assertion-status option:

| Option | Effect |
|---|---|
| `isCounter` | Sets `isCounter=true`; marks counter-evidence |
| `abstract` | Sets `isAbstract=true` |
| `metaClaim` | Sets `metaClaim=true` |

### External references

A parenthesized reference `(ref)` on an element is used as the click-target
URL for that element's node in diagram output.
Resolution rules:

| `ref` form | `base_url` set? | Result |
|---|---|---|
| `http://…`, `https://…`, `file:///…` | either | used as-is |
| starts with `/` | either | used as-is |
| relative | no | used as-is |
| relative | yes | `dirname(base_url) + "/" + ref` |

Setting `base_url` to the GitHub URL of the output document therefore
resolves relative references like `hara.pdf` to the correct full URL
alongside the document.

### Permitted parent–child relationships

Not every combination is valid.  The following relationships are permitted
(`->` means "may have as a child"):

- `Claim` → `Claim`, `Strategy`, `Assumption`, `Justification`, `Evidence`
- `Strategy` → `Claim`, `Justification`, `Assumption`
- `Justification` → `Claim`, `Strategy`, `Evidence`
- Any element → `Context`, `Relation`

`Claim` and `Strategy` must not appear as direct children of `Evidence`,
`Context`, or `Assumption`.
Additionally, a claim supported by `Evidence` should not also be supported
by `Justification`, `Assumption`, or `Strategy`
(though `caseproc` warns rather than refusing).

---

## Running caseproc

### Synopsis

```
caseproc [--config FILE] [--error] [--update]
         [--rename OLD NEW] [--restate LABEL STATEMENT]
         [--ltac FILENAME]
         [--validate | --select SELECTOR | --stdout | --selftest | --missing | --start]
         [files ...]
```

### Normal mode (default)

With no mode flag, `caseproc` updates the listed document files in place.
It validates the LTAC, renders fresh content for all marked regions, and
writes the changes back atomically.
If no files are given, it tries the document auto-discovery sequence
(see [Auto-discovery](#auto-discovery)).

This is the intended day-to-day workflow: edit `case.ltac` and your
document files, then run `caseproc` to resync everything.

### --validate

Validates the LTAC and, if document files are given (or auto-discovered),
checks that every declared LTAC element has a corresponding `element`
selector in the documents.
Produces no output and modifies no files.
Exit code is non-zero if any error was reported.
Useful in CI to confirm the assurance case is internally consistent.

### --select SELECTOR

Renders `SELECTOR` to stdout and exits.  Modifies no files.
See [Selectors](#selectors) for the full list of selectors and their formats.

### --stdout

Processes document files the same way as normal mode but writes the
concatenated result to stdout instead of updating files in place.
Useful for previewing output or for piping into other tools.

### --selftest

Runs the built-in doctest suite and exits.
Exit code is 0 if all tests pass, 1 if any fail.

### --missing

Re-renders all marked regions in the document files (the same way normal
mode does) and, for every declared LTAC element that has no corresponding
`element` selector, appends a skeleton
`<!-- caseproc element ID -->…<!-- end caseproc -->` region.
In HTML documents the appended regions are inserted immediately before
`</body>`; in Markdown documents they are appended at EOF.

Also marks every leaf node (no supporting children) that lacks an
assertion-status option with `{needsSupport}` in the LTAC file.

Rewrites document files and the LTAC file in place.

`--missing` is intended as a one-time scaffolding aid when bringing an
existing LTAC file into a new document.  After running it, review and
reorganize the inserted regions as needed.

### --start

Creates a starter `case.ltac` and `case.md` in the current directory and
then populates them (equivalent to running `--missing` on the new files).
Panics if any of the following files already exists:
`case.ltac`, `docs/case.ltac`, `case.md`, `case.markdown`, `case.html`,
`docs/case.md`, `docs/case.markdown`, `docs/case.html`.

After `--start`:
- `case.md` has its `warning` and `package *` regions filled in and
  skeleton `element` regions appended for every node in the LTAC.
- `case.ltac` has `{needsSupport}` added to all leaf claims.

`--start` is intended as a quick on-ramp for new projects and tutorials.
Edit the generated files and run `caseproc` (normal mode) to continue.

### --ltac FILENAME

Specifies the LTAC file to load.
Overrides `ltac_file` in the config and the auto-discovery sequence.

### --config FILE

Loads configuration from a JSON file (an object of key/value pairs).
See [Configuration](#configuration) for the full list of keys.
Unknown keys produce a warning and are ignored.

`caseproc` also auto-discovers a config file if `--config` is not given:
it checks for `case.config` in the current directory, then `docs/case.config`.

### --error

Treats warnings as errors: any warning causes a non-zero exit code.
By default only serious errors (such as unclosed marked regions or
unresolvable LTAC files) cause a non-zero exit.

### --update

Synchronizes citation statement text with declaration statement text in the
LTAC file.  If a `^ID: wrong text` citation does not match `ID: correct text`,
`--update` rewrites the LTAC file so every citation and Link that carries
text uses the declaration's text instead.

Without `--update`, a mismatch between a citation's text and its
declaration's text produces a warning suggesting the use of `--update`.

`--update` modifies the LTAC file (subject to the safe backup mechanism
described in [File handling](#file-handling)).

### --rename OLD NEW

Renames identifier `OLD` to `NEW` throughout the LTAC file and all
document files processed in the same run.
`OLD` must be a declared identifier; `NEW` must not yet exist.
May be given more than once on a single command line; mutations are applied
in the order given.

### --restate LABEL STATEMENT

Updates the statement text for `LABEL` to `STATEMENT` throughout the LTAC
file and all document files processed in the same run.
May be given more than once; mutations are applied in order.

---

## Selectors

A selector identifies what to render and in what format.
Selectors appear after `--select` on the command line or inside marked
regions in document files (see [Marked regions](#marked-regions)).

### Selector syntax

```
KIND [ID | *]
```

**`KIND`** is one of the values in the table below.
Shorthand kinds (`sacm`, `gsn`, `ltac`) are auto-expanded based on
the document format (markdown or HTML) and the `default_renderer` config key.

**`ID`** is the identifier of the element or package to render.
For selectors that accept `*`, all packages are rendered in order.

| Selector | `ID` | Description |
|---|---|---|
| `element ID` | required | Heading + cross-references for one element |
| `package [ID\|*]` | optional | Heading + diagram + index for one or all packages |
| `sacm [ID\|*]` | optional | SACM diagram (auto-detects markdown/HTML format) |
| `sacm/mermaid [ID\|*]` | optional | SACM Mermaid diagram (auto-detects format) |
| `sacm/mermaid/markdown [ID\|*]` | optional | SACM diagram as a fenced Mermaid block |
| `sacm/mermaid/html [ID\|*]` | optional | SACM diagram as `<pre class="mermaid">` |
| `gsn [ID\|*]` | optional | GSN diagram (auto-detects format) |
| `gsn/mermaid [ID\|*]` | optional | GSN Mermaid diagram (auto-detects format) |
| `gsn/mermaid/markdown [ID\|*]` | optional | GSN diagram as a fenced Mermaid block |
| `gsn/mermaid/html [ID\|*]` | optional | GSN diagram as `<pre class="mermaid">` |
| `ltac [ID\|*]` | optional | LTAC argument list (auto-detects format) |
| `ltac/markdown [ID\|*]` | optional | LTAC as an indented Markdown bullet list |
| `ltac/html [ID\|*]` | optional | LTAC as a nested HTML `<ul>` list |
| `statement ID` | required | Single-line statement: `Statement: …` |
| `warning` | none | Fixed "do not edit" comment pair |

The shorthand expansions are:

| Written | Expands to (Markdown doc) | Expands to (HTML doc) |
|---|---|---|
| `sacm` | `sacm/mermaid/markdown` | `sacm/mermaid/html` |
| `sacm/mermaid` | `sacm/mermaid/markdown` | `sacm/mermaid/html` |
| `gsn` | `gsn/mermaid/markdown` | `gsn/mermaid/html` |
| `gsn/mermaid` | `gsn/mermaid/markdown` | `gsn/mermaid/html` |
| `ltac` | `ltac/markdown` | `ltac/html` |

---

## Configuration

Configuration is supplied in a JSON object, either via `--config FILE` or
auto-discovered from `case.config` / `docs/case.config`.
All keys are optional; unrecognized keys produce a warning.

| Key | Default | Description |
|---|---|---|
| `base_url` | `""` | Base URL for hyperlinks in `sacm/mermaid` and `gsn/mermaid` output.  Set to the GitHub URL of the rendered output document so that diagram node `click` targets resolve correctly. |
| `bottom_padding` | `true` | Adds an invisible `BottomPadding` node in Mermaid diagrams to prevent GitHub's floating diagram controls from obscuring the bottom row of nodes. |
| `default_renderer` | `"mermaid"` | Renderer used when expanding the `sacm` and `gsn` shorthand selectors.  Currently only `"mermaid"` is supported. |
| `default_representation` | `"sacm"` | Diagram notation used by the `package` selector.  Accepts `"sacm"` or `"gsn"`. |
| `document_files` | `[]` | List of document files to process; equivalent to listing them on the command line.  Command-line files take priority. |
| `element_level` | `3` | Markdown/HTML heading level (1–6) used by the `element` selector.  Can also be set per-document with `caseproc-config`. |
| `element_selections` | `"referenced_by,supported_by,supports"` | Comma-separated list of sub-sections rendered inside each `element` region.  Valid values: `referenced_by`, `supported_by`, `supports`. |
| `ltac_file` | `""` | Path to the LTAC file; overridden by `--ltac`. |
| `markdown_base_url` | `""` | Base URL for hyperlinks in `ltac/markdown` and `ltac/html` output. |
| `mermaid_js_url` | CDN URL | URL of the Mermaid JS script injected into HTML output.  Set to `""` to disable injection. |
| `package_level` | `3` | Heading level (1–6) used by the `package` selector.  Can also be set per-document with `caseproc-config`. |
| `package_selections` | `"representation,pkg_defines,pkg_citing,pkg_cited"` | Comma-separated list of sub-sections rendered inside each `package` region.  Valid values: `representation`, `pkg_defines`, `pkg_citing`, `pkg_cited`. |
| `pkg_header_prefix` | `"### "` | String prepended to each package header when rendering `*` with `ltac/*` selectors. |
| `pkg_header_suffix` | `"\n"` | String appended after each package header when rendering `*` with `ltac/*` selectors (a newline by default, producing a blank separator line). |
| `pkg_label` | `"Package "` | Word (with trailing space) used to identify packages in rendered output. |

---

## Document integration

### Marked regions

Anywhere in a Markdown or HTML document, the pair:

```
<!-- caseproc SELECTOR -->
…stale content…
<!-- end caseproc -->
```

marks a region whose content `caseproc` replaces with freshly rendered
output for `SELECTOR`.
The opening and closing comment lines are preserved; only the content
between them is replaced.
If `SELECTOR` produces no output, the region is left empty.

Do *NOT* edit text within such regions! Your text will be replaced
then text time it's regenerated!

Marked regions may use any selector.
A common document structure might look like this:

```markdown
# Assurance case introduction

<!-- caseproc warning -->
<!-- end caseproc -->

## Introduction

Some introductory text

## Packages
<!-- caseproc package * -->
<!-- end caseproc -->

<!-- caseproc element C1 -->
<!-- end caseproc -->
... information about C1 ...

<!-- caseproc element C2 -->
<!-- end caseproc -->
... information about C2 ...
```

But you not limited to that. Other examples:

```markdown
<!-- caseproc sacm/mermaid * -->
<!-- caseproc gsn/mermaid * -->
<!-- caseproc ltac/markdown * -->
<!-- caseproc sacm/mermaid C1 -->
<!-- caseproc statement C1 -->
```

### element and package selectors

The `element` and `package` selectors generate structured headings and
cross-reference sub-sections, providing a stable home for each piece of
the assurance case in the document.

**`<!-- caseproc element ID -->`** generates:

- A heading at the level specified by `element_level` (default: `###`),
  using the element's type and identifier as its text, with a stable
  HTML anchor for deep-linking.
- Sub-sections controlled by `element_selections`:
  - `referenced_by` — lists packages that reference this element.
  - `supported_by` — lists the element's direct supporting children.
  - `supports` — lists what this element directly supports.

**`<!-- caseproc package [ID|*] -->`** generates:

- A heading at the level specified by `package_level` (default: `###`),
  with a stable HTML anchor.
- Sub-sections controlled by `package_selections`:
  - `representation` — the default diagram (SACM or GSN per `default_representation`).
  - `pkg_defines` — lists elements defined in this package.
  - `pkg_citing` — lists elements from other packages cited here.
  - `pkg_cited` — lists elements from this package cited elsewhere.

`*` renders all packages in order.

`caseproc` warns if a declared LTAC element has no corresponding `element`
selector in any processed document.  Use `--missing` to scaffold the
missing regions automatically.

### Per-document configuration

A document may override selected configuration keys for itself using
`caseproc-config` directives:

```
<!-- caseproc-config KEY = VALUE -->
```

The directive takes effect from that point in the document onward.
Currently supported keys:

| Key | Accepted values |
|---|---|
| `element_level` | `1`–`6` |
| `package_level` | `1`–`6` |

Example — use level-2 headings for packages and level-3 for elements:

```markdown
<!-- caseproc-config package_level = 2 -->
<!-- caseproc-config element_level = 3 -->
```

Do **not** use `<!-- caseproc config ... -->` (without the hyphen); that
syntax is recognized and produces a helpful error directing you to the
correct form.

### Anchor naming

Anchors for element and package headings are derived from the element type
and identifier only (statement text is excluded so that anchors remain
stable when statements change):

1. Form the string `TYPE ID` (e.g., `Claim C1`, `Package Requirements`).
2. Lowercase everything.
3. Remove characters that are not Unicode letters, digits, hyphens, or spaces.
4. Replace spaces with hyphens.
5. Collapse runs of hyphens; strip leading and trailing hyphens.

Examples:

| Type + Identifier | Anchor id |
|---|---|
| `Claim C1` | `claim-c1` |
| `Package Requirements` | `package-requirements` |
| `Strategy AR1` | `strategy-ar1` |

---

## Diagram output

### SACM/mermaid

The `sacm/mermaid` selector renders SACM notation using a Mermaid `flowchart BT`
(bottom-to-top) diagram.  Child elements appear below their parents;
arrows point upward toward the claim being supported.

#### SACM node shapes

| LTAC type | SACM concept | Mermaid shape |
|---|---|---|
| `Claim` | Claim | Rectangle `["…"]` |
| `Claim` with `assumed` | Claim (assertionDeclaration=assumed) | Rectangle, label appended with `<br>ASSUMED` |
| `Claim` with `needsSupport` | Claim (needsSupport) | Dashed rectangle (`abstractClaim` class) |
| `^`-prefixed Claim | Claim (asCited) | Double bracket `[["…"]]` |
| `Strategy` | ArgumentReasoning | Parallelogram `[/"…"/]` |
| `Evidence` | ArtifactReference | Cylinder `[("…")]`, label includes `↗` |
| `Context` | ArtifactReference (AssertedContext) | Cylinder `[("…")]`, label includes `↗` |
| `Assumption` | Claim (assumed) | Rectangle, label appended with `<br>ASSUMED` |
| `Justification` | Claim | Rectangle |

#### SACM inference arrows and sacmDots

SACM represents a single inference relationship as an `AssertedRelationship`.
When multiple children share the same parent, they all connect to a single
filled black dot (a *sacmDot*) that then connects to the parent.
This matches the SACM graphical notation from Annex C of the SACM specification.

```
    Child1 --- Dot1
    Child2 --- Dot1
    Dot1((" ")):::sacmDot --> Parent
```

`Context` children always use a separate context arrow (`--o`) and are
not grouped into a sacmDot.

When there is exactly one inferential child (and no metaClaim), the
unreified form is used — a direct arrow from child to parent with no dot.

#### Click links in SACM diagrams

Each identified node gets a `click` line.  The URL is determined as:

1. If the node has an `(ext_ref)`: resolved per [External references](#external-references).
2. If `base_url` is set and the node is a **citation** (`^ID`): links to
   the cited package's section header (`base_url + "#package-ID"`).
3. If `base_url` is set and the node is **declared**: links to the element's
   own content heading (`base_url + "#type-id"`).
4. Otherwise: no `click` line.

### GSN/mermaid

The `gsn/mermaid` selector renders GSN notation using a Mermaid `flowchart TD`
(top-down) diagram.  Arrows point **downward** from each goal or strategy
to the elements that support it, matching standard GSN convention.

#### GSN node shapes

| LTAC type | GSN element | Mermaid shape |
|---|---|---|
| `Claim` | Goal | Rectangle `["…"]` |
| `Claim` with `needsSupport` | Undeveloped Goal | Dashed rectangle (`gsnUndev` class), label appended with `<br>◇` |
| `^`-prefixed Claim | Away Goal | Subroutine `[["…"]]` |
| `Strategy` | Strategy | Parallelogram `[/"…"/]` |
| `Evidence` | Solution | Circle `(("…"))` |
| `Context` | Context | Stadium `(["…"])` |
| `Assumption` | Assumption | Rounded rect with Ⓐ |
| `Justification` | Justification | Rounded rect with Ⓙ |

In GSN, each child gets its own direct arrow from the parent (no shared dot).
`Context`, `Assumption`, and `Justification` use the `--o` context arrow.

### ltac/markdown and ltac/html

`ltac/markdown` renders the argument tree as an indented Markdown bullet
list; `ltac/html` renders it as nested HTML `<ul>` lists.
Both add hyperlinks on each element label.  The URL for each element is
determined using `markdown_base_url` (default empty) by the same rules as
SACM/GSN click links.

When `*` is used, all packages are rendered in order, each preceded by a
configurable package header (`pkg_header_prefix` + identifier + `pkg_header_suffix`).

---

## Validations

The following checks always run when an LTAC file is loaded.
Errors cause a non-zero exit; warnings do not (unless `--error` is given).

**Fatal errors:**

- **Circular reasoning** — following children and citations must never form
  a loop.  The full cycle is reported, e.g., `C2 -> C4 -> C2`.

- **Unreachable package** — in a multi-package file, each package root must
  be reachable from the first element of the first package
  (following structural children, citation declarations, and Link targets).

- **Unresolved citation** — a `^ID` citation with no matching declaration.

- **Duplicate declaration** — an identifier declared (without `^`) more than once.

- **Anchor collision** — two identifiers that generate the same HTML anchor
  id (e.g., `Foo < 0` and `foo > 0` both produce `foo--0`).

**Warnings:**

- **Structural violation** — `Claim` or `Strategy` as a direct child of
  `Evidence`, `Context`, or `Assumption`.

- **Inconsistent type** — the same identifier used with different element types.

- **Inconsistent statement** — statement text that differs between the
  declaration and a citation or Link (use `--update` to fix).

- **Multiple assertion statuses** — more than one of `needsSupport`,
  `assumed`, `axiomatic`, `defeated`, `asCited` on the same element.

- **Wrong citation package** — `^[PkgName] ID` where `PkgName` does not
  match the package that declares `ID`.

- **Cited but undeclared** — an identifier cited but never declared
  (distinct from "unresolved": the identifier may exist in an unloaded file).

**Additional checks when document files are processed:**

- A declared LTAC element with no corresponding `element` selector in any
  processed document (each element is expected to have a place for its
  supporting detail).

---

## Updating the LTAC file

By default, `caseproc` treats the LTAC file as read-only.
Several options cause it to write an updated LTAC file.
All of them use the same safe backup mechanism (see [File handling](#file-handling)).

### --update

Walks every citation and Link node in the LTAC tree.
If a node carries statement text that differs from the declaration's text,
the node's text is replaced with the declaration's text.
Reports the count of changed nodes and writes the file if any changes were made.

Example: if `- Claim ^C1: Old statement` is found but the declaration is
`- Claim C1: New statement`, `--update` rewrites the citation to
`- Claim ^C1: New statement`.

### --rename OLD NEW

Renames identifier `OLD` to `NEW` in the LTAC forest and then rewrites the
LTAC file.
When document files are also processed in the same run, all `element` and
`package` selectors and `statement` selectors in those documents are updated
to use the new name.

After renaming, all validations are re-run; if any errors result, no files
are written.

### --restate LABEL STATEMENT

Changes the statement text of `LABEL` to `STATEMENT` in the LTAC forest and
rewrites the LTAC file.

`--rename` and `--restate` may be given more than once per invocation;
mutations are applied in the order specified.
If `--rename` and `--restate` are both given, the LTAC file is written once
with all mutations applied.

---

## File handling

### Auto-discovery

If no `--ltac` option and no `ltac_file` config key are given, `caseproc`
looks for `case.ltac` in the current directory, then `docs/case.ltac`.
If neither exists, it exits with an error.

Similarly, if no document files are given on the command line and no
`document_files` config key is set, it looks for any of the following
(in order): `case.md`, `case.markdown`, `case.html`,
`docs/case.md`, `docs/case.markdown`, `docs/case.html`.

Config file auto-discovery: `case.config` in the current directory, then
`docs/case.config`.

### Safe file updates

All file writes are done atomically to prevent data loss:

1. The updated content is written to a temporary file in the **same
   directory** as the target file.
2. The original file is moved to a `.backup/` subdirectory
   (e.g., `docs/.backup/case.ltac`), overwriting any previous backup for
   that filename.
3. The temporary file is moved into place as the final destination.

If the updated content is identical to the original, the file is not
touched and no backup is created.

If a serious error occurs during processing, the file is left unchanged.

### The `.backup/` directory

Each directory that contains files updated by `caseproc` gets a `.backup/`
subdirectory holding the immediately previous version of each updated file.
Only the most recent backup for each filename is kept.
Add `.backup/` to `.gitignore` if you do not want these files tracked.

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (no errors; any warnings were non-fatal) |
| 1 | One or more errors occurred, or warnings occurred with `--error` |

---

## See also

- [Extended LTAC format specification](ltac-extended.txt)
- [SACM notation in Mermaid — conventions](sacm-mermaid.md)
- [GSN notation in Mermaid — conventions](gsn-in-mermaid.md)
- [Design specification](design-spec.md)
- [README](../README.md)
