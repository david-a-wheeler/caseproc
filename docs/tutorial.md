# verocase Tutorial

This is the tutorial for `verocase`.
`verocase` is a simple open source software (OSS) tool
that makes it *easy* and *efficient*
to create and maintain a small or moderately-sized assurance case,
e.g., for justifying why a system is secure against attack.
It's designed to be easy to use for humans *and* AI.

## What's an assurance case?

An assurance case is "a body of evidence organized into an argument demonstrating that some claim about a system holds (i.e., is assured). An assurance case is needed when it is important to show that a system exhibits some complex
property, such as safety, security, privacy, or reliability."
([NIST Special Publication 800-53A Revision 5](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53Ar5.pdf)).

Assurance cases are in theory straightforward.
Typically you have a high-level claim that you repeatedly break down into
smaller claims that together demonstrate that the claim holds.
The problem is that as they get large, they can be painful to follow
or maintain if you just maintain a document.

## Verocase data

`verocase` splits the assurance case data into two parts:

- A compact **LTAC file** (`case.ltac`) holds the argument structure:
  the claims, strategies, evidence, and how they relate.
- One or more **document files** (`case.md` etc.) hold the narrative detail
  and context: everything you'd want to say *about* each element.

`verocase` reads the LTAC file and regenerates the structured portions
of the document automatically (diagrams, headings, cross-reference links).
You write the key information; `verocase` takes care of the boilerplate.

---

## Quick start

Here's a quick start. Create an empty directory and run `--start`:

```sh
mkdir demo && cd demo
verocase --start
```

This creates two files:

- `case.ltac`: a tiny starter argument (three elements)
- `case.md`: a Markdown document with placeholder regions

Open `case.ltac` in your editor. It should look something like this:

```ltac
- Claim Security: The system is adequately secure against moderate threats
  - Strategy Processes: Security is argued by examining lifecycle processes
    - Claim ^Requirements
    - Claim ^Design
    - Claim ^Implementation
    - Claim ^Verification

- Claim Requirements: Security requirements are identified and met
  - Strategy SecTriad: Security triad (CIA) and access control address the requirements
    - Claim Confidentiality: Confidentiality is maintained
    - Claim Integrity: Integrity is maintained
    - Claim Availability: Availability is maintained
    - Claim AccessControl: Access control is in place

- Claim Design: Security is implemented in design
  - Claim SimpleDesign: Economy of mechanism: simple design is used
  - Claim STRIDE: STRIDE threat model has been analyzed
  - Claim DesignPrinciples: Secure design principles are applied

- Claim Implementation: Implementation is secure

- Claim Verification: System verified as being secure
```

Every non-blank line normally begins with a possibly-indented dash, an element
type like "Claim", a unique ID, colon, and a statement.
A claim is a true/false statement that you would *like* to be true.
An ID that begins with `^` is a *citation* to the "real" element somewhere else.
Citations can't have leaves, but you can cite an ID as many times as you want.
You *must* have a single definition (an element without the `^`) for every
ID you cite.

Now open `case.md`. Near the top you'll see:

```markdown
<!-- verocase warning -->
<!-- WARNING: DO NOT EDIT text within verocase SELECTOR ... end verocase. -->
<!-- Those regions are regenerated. -->
<!-- end verocase -->
```

and further down:

```markdown
<!-- verocase package * -->
... generated diagram and index ...
<!-- end verocase -->

<!-- verocase element Top -->
### Claim Top: Top level claim
...
<!-- end verocase -->

... more element regions ...
```

Everything between a `<!-- verocase ... -->` marker and `<!-- end verocase -->`
is managed by `verocase`: **don't edit inside those regions**.
Everything *outside* them is yours to write freely.

Now run `verocase` (no arguments) to regenerate:

```sh
verocase
```

It finds `case.ltac` and `case.md` automatically, validates the LTAC,
and rewrites `case.md` with fresh generated content.
The original `case.md` is backed up to `.backups/` before any change.

---

## The LTAC file

### Element syntax

Every non-blank line in an LTAC file defines or cites one *element*:

```
INDENT - TYPE [^][IDENTIFIER]: statement text [{options}] [(ext_ref)]
```

- **`INDENT`**: two spaces per nesting level (root elements have none).
- **`-`**: the bullet marker.
- **`TYPE`**: the kind of element (see table below).
- **`^`**: if present, this is a *citation* of an element declared elsewhere.
- **`IDENTIFIER`**: a short name for the element, unique across the whole file.
  Identifiers may contain spaces and most printable characters (but not `:` or `^`).
  If omitted, the identifier is inferred from the statement text.
- **`: statement text`**: what this element asserts or describes.
- **`{options}`**: optional modifiers (see [Options](#options) below).
- **`(ext_ref)`**: optional URL or filename pointing to an external
  resource (e.g. a PDF, report, or spec file) that provides the content
  for this element.  Shown as a clickable link in the rendered document.
  Elements with an `ext_ref` are never flagged as empty by `--empty`.

One or more blank lines ends one *package* and begins the next.

### Element types

| Type | Purpose |
|---|---|
| `Claim` | A true-or-false statement asserted to hold |
| `Strategy` | An argument explaining how sub-claims or evidence collectively support a parent claim |
| `Evidence` | An artifact (document, test result, ...) cited in support |
| `Context` | Background information or scope constraint for the parent element |
| `Assumption` | A claim accepted as true without further argument |
| `Justification` | A rationale or side-claim supporting a strategy |
| `Link` | A back-reference to an element already defined earlier in the same package |

The most common types are `Claim`, `Strategy`, and `Evidence`.
`Context` and `Assumption` add background or preconditions.

Here's a richer example:

```ltac
- Claim Secure: The system is adequately secure
  - Strategy SecStrategy: Argue by examining all attack vectors
    - Claim NetworkSafe: Network attacks are mitigated (network-analysis.pdf)
      - Evidence PenTest: Penetration test results (pentest-2024.pdf)
    - Claim AuthSafe: Authentication is robust
      - Evidence Authn: Authentication design review (authn-review.md)
    - Context Threat: Threat model is moderate adversary (threat-model.md)
```

### Options

Options appear in `{...}` near the end of a line and modify the element:

| Option | Meaning |
|---|---|
| `needssupport` | Placeholder; this claim still needs to be developed further |
| `assumed` | Accepted without proof; flags it visually in diagrams |
| `axiomatic` | Treated as a foundational axiom |
| `defeated` | No longer believed to hold |

The most useful option for active development is `needssupport`:
it flags leaves that aren't finished yet.
`--fixmissing` adds `{needssupport}` automatically to any leaf claims.

### Identifiers

Identifiers must be unique across the entire LTAC file.
Use short, memorable names: `AuthnClaim`, `G2`, `PenTest`.
Spaces are legal: `- Claim Login Safe: Login is safe` works.
If you omit the identifier entirely the text becomes the identifier,
but explicit identifiers are easier to work with.

---

## The document file

### Marked regions

The document file is ordinary Markdown.
You can write whatever you like (headings, paragraphs, tables, images),
with one constraint: content between these two comment markers is owned
by `verocase`:

```markdown
<!-- verocase SELECTOR -->
...generated content (do not edit)...
<!-- end verocase -->
```

Each time you run `verocase`, it replaces everything between the markers
with freshly generated content for that `SELECTOR`.
Write your narrative *outside* these regions.

### Common selectors

| Region | What it generates |
|---|---|
| `<!-- verocase warning -->` | A "do not edit" reminder comment |
| `<!-- verocase package * -->` | Heading + diagram + index for every package |
| `<!-- verocase element ID -->` | Heading + cross-references for one element |
| `<!-- verocase sacm/mermaid ID -->` | SACM diagram for one package |
| `<!-- verocase gsn/mermaid * -->` | GSN diagrams for all packages |
| `<!-- verocase ltac/markdown * -->` | Full LTAC as a Markdown bullet list |
| `<!-- verocase statement ID -->` | Single-line statement text for ID |
| `<!-- verocase ltac/txt ID -->` | Raw LTAC source for the element subtree (no generated Markdown) |
| `<!-- verocase info ID -->` | Full context: package, ancestors, children, citations |

See [reference.md](reference.md) for the full selector table.

### A typical document structure

```markdown
# My Assurance Case

<!-- verocase warning -->
<!-- end verocase -->

## Summary diagrams

<!-- verocase package * -->
<!-- end verocase -->

---

## Claim: The system is adequately secure {#claim-secure}

<!-- verocase element Secure -->
<!-- end verocase -->

Write your detailed narrative about this claim here.
Explain the threat model, scope, and any caveats.
This text is yours: verocase never touches it.

## Claim: Network attacks are mitigated

<!-- verocase element NetworkSafe -->
<!-- end verocase -->

More narrative here ...
```

The `element` selector generates a stable heading and cross-reference
links (what supports this element, what it supports, where it's cited).
Your prose goes immediately after the `<!-- end verocase -->` line.

### What belongs to an element: `stop` and `epilogue`

When `--fixmisplaced` moves an element to its correct position, it moves the
element's **full content**: the `<!-- verocase element ID -->` region, the
`<!-- end verocase -->` closing marker, and all the following prose lines right
up to the next element, the next `<!-- verocase-config -->`, or the special
`<!-- verocase stop -->` sentinel described below.

This means you can safely embed supplemental selectors in an element's prose
and they will travel with it:

```markdown
<!-- verocase element AuthnClaim -->
<!-- end verocase -->

Here is the narrative about authentication...

<!-- verocase info AuthnClaim -->
<!-- end verocase -->

<!-- verocase ltac/markdown AuthnClaim -->
<!-- end verocase -->
```

All of the above (narrative, `info` block, and `ltac/markdown` block) are
considered part of `AuthnClaim`'s full content and will be moved together.

**The `stop` sentinel** breaks that association.  Any content after a `stop`
region is not owned by any element and will not be repositioned by
`--fixmisplaced`:

```markdown
<!-- verocase element LastClaim -->
<!-- end verocase -->

Supporting prose for LastClaim...

<!-- verocase stop -->
<!-- end verocase -->

This transition stays put regardless of LTAC reorganization.

<!-- verocase element NextClaim -->
<!-- end verocase -->
```

`stop` can appear anywhere and any number of times.

**The `epilogue` sentinel** is like `stop` but signals end-of-main-content.
Use it once, after the last element, before stable concluding prose:

```markdown
<!-- verocase element LastClaim -->
<!-- end verocase -->

Prose for LastClaim...

<!-- verocase epilogue -->
<!-- end verocase -->

## Conclusions

This section is stable.  --fixmisplaced will never move it, and
--fixmissing inserts any new element stubs above this point.
```

Two extra guarantees come with `epilogue` that `stop` does not provide:

- **`--fixmissing` awareness:** missing element stubs that have no predecessor
  already in the document are placed *before* the `epilogue`, not appended at
  the very end of the file.
- **Error on following element:** if you accidentally place a
  `<!-- verocase element ID -->` after the `epilogue`, verocase reports an
  error on every run until you fix it.

The starter document created by `--start` uses `epilogue` before its
`## Notes` section to illustrate this pattern.

### Using `--fixmissing` to scaffold element regions

If your LTAC has many elements, adding all the `element` regions by hand
is tedious. `--fixmissing` does it for you:

```sh
verocase --fixmissing
```

This re-renders all existing regions *and* inserts a skeleton
`element` region for every LTAC element that has no region yet.
New regions are placed near their natural LTAC position (after their
nearest already-present predecessor in the document), so the resulting
document is already in roughly the right order.
It also marks every leaf claim with `{needssupport}` if it lacks one.

To *preview* which elements are missing without modifying any file, use
the read-only `--missing` analysis option:

```sh
verocase --missing
```

After running `--fixmissing`, add your narrative after each
`<!-- end verocase -->` line and run `verocase` to regenerate.

---

## Running verocase

### Day-to-day workflow

The typical loop is:

1. Edit `case.ltac`: add/remove elements, change statements, restructure.
2. Edit `case.md`: add or revise narrative text *outside* the marked regions.
3. Run `verocase`: it validates the LTAC and regenerates all marked regions.
4. Review the updated document (diagrams, headings, cross-references).
4. In a few cases you may want to run special `verocase` commands, e.g.,
   `--move` will move an LTAC element from one place to another, or
   `--detach` will detach an LTAC element so it's the top of its own package.
   You can also do this by directly editing the LTAC file, but it's
   sometimes easier to let the tool do it for you.
5. Repeat.

```sh
# Edit files, then:
verocase
```

`verocase` exits with code 0 on success and 1 if any error occurs.
Warnings (non-fatal issues) are printed to stderr but do not affect the exit
code unless you pass `--error`.

### Previewing without modifying files

Use `--stdout` to see what `verocase` would produce without changing anything:

```sh
verocase --stdout
```

This is useful for reviewing output or piping it into another tool.

For AI tools or any situation where you want to read the *document structure*
without wading through generated diagrams, use `--strip --stdout`:

```sh
verocase --strip --stdout
```

This produces the document with all selector regions emptied out (except
`warning`), making it much easier to read the outline and your prose.

### Validation only

To check the LTAC for errors without modifying any files:

```sh
verocase --validate
```

This is useful in CI pipelines: it exits non-zero if the LTAC is invalid
or if any declared element lacks an `element` selector in the documents.

### Automatic backups

**You won't lose work.** Every time verocase modifies any file it first
saves a complete snapshot of the state *before* the change: the document
files it is about to update, the LTAC file, and the config file (if any).
Snapshots are stored in a `.backups/` directory next to your LTAC file,
each in a timestamped subdirectory such as `2026-03-11T142305.07/`.

Up to 20 snapshots are kept; older ones are automatically deleted to
keep the directory tidy.  If you ever edit text inside a marked region
by mistake and verocase overwrites it, look in `.backups/` for the most
recent snapshot; your text will be there.

You can adjust the number of snapshots kept with the `max_backups` config
key, or set it to `0` to disable backups entirely.
See the [reference manual](reference.md) for details.

---

## Configuration

### The config file

`verocase` looks for a TOML config file automatically:

1. `verocase.toml` in the current directory
2. `docs/verocase.toml` in the current directory

You can also specify one explicitly:

```sh
verocase --config path/to/myconfig.toml
```

The config file is a TOML file of key/value pairs.  All keys are optional.
Run `verocase --help-config` to print the full list, or see the
[reference manual](reference.md#configuration).

A minimal config file looks like this:

```toml
base_url = "https://github.com/OWNER/REPO/blob/main/docs/case.md"
```

### Making diagram clicks work on GitHub with `base_url`

Mermaid diagrams generated by `verocase` include `click` directives so
that clicking a node navigates to that element's section in the document.
On most platforms (local HTML preview, GitLab, self-hosted Gitea, etc.)
the fragment links that are
produced by default (`#claim-c1`, `#evidence-e1`, ...)
work without any configuration.
Clicking a node scrolls to the right section on the same page.

**GitHub is the exception.**
When GitHub renders a Mermaid diagram, fragment-only `click` targets are
not resolved relative to the current page; they simply do nothing.
That's because the GitHub mermaid renderer renders its result inside
a sandbox, so relatively links work only within that diagram's sandbox.

As a result,
you must supply a full absolute URL as a base
for GitHub rendering to navigate correctly.
This means the links will always point to the stated branch, not the current
branch; that's unfortunate, but at least the result works.

Set `base_url` in your config file to the full GitHub URL of the document
that contains the diagrams:

```toml
base_url = "https://github.com/OWNER/REPO/blob/BRANCH/PATH/TO/case.md"
```

For example, if your repository is `https://github.com/example/myproject`
and your case document is `docs/case.md` on the `main` branch:

```toml
base_url = "https://github.com/example/myproject/blob/main/docs/case.md"
```

Once set, every diagram node click will take the reader directly to the
corresponding section in the document — no GitHub Pages, no separate build
step, no deployment pipeline needed.  The document lives in the repository
and works as-is.

**Trade-offs to be aware of:**

- The URL hard-codes a branch name (typically `main`).  If someone reads
  the document on a feature branch, clicking a diagram node will navigate
  to the `main` version of that section rather than the feature-branch
  version.  In practice this is fine: `main` is where the stable case
  lives, and the feature branch content is usually very similar.

- If you rename the document file or move it to a different path in the
  repository, remember to update `base_url` in the config.

- Relative external references in your LTAC (for example `(hara.pdf)` on
  an Evidence element) are also resolved against `base_url`, so they will
  link correctly to the file alongside the document on GitHub.

You can set `base_url` either in the TOML config file (to apply to all
documents at once) or inline in a specific document with `verocase-config`:

```markdown
<!-- verocase-config base_url = https://github.com/OWNER/REPO/blob/main/docs/case.md -->
```

### Per-document settings with `verocase-config`

For settings that affect how a single document is rendered — heading
levels, diagram width limits, or `base_url` — you can place directives
inline anywhere in the document:

```markdown
<!-- verocase-config base_url = https://github.com/OWNER/REPO/blob/main/docs/case.md -->
<!-- verocase-config package_level = 2 -->
<!-- verocase-config element_level = 3 -->
```

The directive takes effect from that point onward in the file.
Supported inline keys are `base_url`, `element_level`, `package_level`,
`max_mermaid_children`, and `narrowed_mermaid_children`.
Keys that affect LTAC parsing (such as `warn_dubious_reference`) require
the TOML config file instead.

---

## Multi-package cases

Once an assurance case grows large, a single flat list becomes hard to
navigate. Split it into *packages*: separate each top-level tree with a
blank line.

```ltac
- Claim Secure: The system is adequately secure
  - Claim ^NetworkSafe:
  - Claim ^AuthSafe:

- Claim NetworkSafe: Network attacks are mitigated
  - Evidence PenTest: Penetration test results (pentest-2024.pdf)

- Claim AuthSafe: Authentication is robust
  - Strategy AuthnStrategy: Argue by design and testing
    - Evidence AuthnDesign: Authentication design review
    - Evidence AuthnTest: Authentication test results
```

Each top-level `Claim` (with no indentation) begins a new package.
The `^` prefix on `^NetworkSafe` and `^AuthSafe` means those are
*citations*: references to elements defined in other packages.
Citations are how you connect packages together.

All packages must be reachable from the first element of the first package
by following children and citations. An isolated package is an error.

When you run `verocase package *`, each package gets its own section with
a diagram. Citations appear in the diagram as double-bracketed nodes
(SACM notation) or subroutine-box nodes (GSN notation), with links that
navigate to the package where the cited element is defined.

For more on packages and citations, see [reference.md](reference.md).

---

## Keeping things in sync

### Renaming an element

To rename an element everywhere (LTAC file and all document files):

```sh
verocase --rename OldId NewId
```

Identifiers with spaces need quoting:

```sh
verocase --rename "Login Safe" LoginSafe
```

After renaming, run `verocase --orphans` to confirm no stale regions remain
in the document, and `verocase --missing` to confirm the renamed element
now has a region.

### Updating a statement

To change an element's statement text everywhere, you can edit the
LTAC file and regenerate the document.

However, if you know the ID, you can use `--restate` like this:

```sh
verocase --restate AuthSafe "Authentication mechanisms are robust and tested"
```

You can also use `--sync` (next).

### Syncing citation text

When you update a declaration's statement, any citations (`^ID: old text`)
become out of date. If you edit the declaration, you can
run `--sync` to resync them:

```sh
verocase --sync
```

This rewrites any citation whose text doesn't match its declaration.
Without `--sync`, a mismatch produces a warning suggesting you run it.

---

## Analysis options

Analysis options inspect the case without modifying any file.
They can be freely combined with each other but not with file-modifying modes.

| Option | What it reports |
|---|---|
| `--missing` | LTAC elements that have no `element` selector region in any document |
| `--empty` | Element regions that exist in the document but have no human-written prose |
| `--orphans` | Document selector regions whose ID is not declared in the LTAC (stale after rename/removal) |
| `--misplaced` | Elements whose document region is in a different order than their LTAC declaration order |
| `--leaves` | All leaf elements (no children in the LTAC), grouped by flag |
| `--packages` | Each package with its element count and the direct children of its root |

You can combine them freely:

```sh
verocase --missing --empty --orphans --misplaced
```

Each report is printed in turn, separated by a blank line.
No files are changed regardless of what is found.

### Typical workflow after structural changes

After renaming or removing an element from the LTAC:

1. `verocase --orphans`: see which old document regions are now stale.
2. Edit the document to remove (or repurpose) those orphaned regions.
3. `verocase --missing`: confirm no LTAC elements are now unrepresented.
4. Run `verocase --fixmissing` if you need to scaffold any new regions.
5. Run `verocase --misplaced` to check whether new regions need reordering;
   run `verocase --fixmisplaced` to move them automatically.

---

## Inspecting the LTAC structure

### `ltac/txt` selector and `--descendants`

The `ltac/txt ID` format renders a subtree as raw LTAC source
rather than as processed Markdown. This is useful when reviewing a
potential `--detach` target:

```sh
verocase --select "ltac/txt Requirements" --stdout
# or equivalently:
verocase --descendants Requirements
```

Output is the LTAC declaration of the named element and all its
descendants, indented as in `case.ltac`, with no generated Markdown
(no headings, no comment markers, no `[text](url)` link syntax).

### `info` selector and `--info`

The `info ID` selector shows full context for one element in one shot:
its package, ancestors, children, descendant count, and any
cross-package citations that reference it:

```sh
verocase --select "info SpecialAnalysis" --stdout
# or equivalently:
verocase --info SpecialAnalysis
```

Example output:

```
Element: Claim SpecialAnalysis: Reused components with apparent vulnerabilities are analyzed and safe
Package: Implementation
Ancestors (root first):
  - Claim Implementation: Security in implementation
  - Strategy CommonVulns: Most vulnerabilities arise from common categories of error
  - Claim ReuseSec: Reused software is secure
  - Strategy ReuseStrat: Reuse is often appropriate and can be done securely
Children:
  - Claim XXESafe: Nokogiri/libxml2 XXE exception poses no risk in our deployment
  - Claim ErubisSafe: XSS from erubis via pronto poses no production risk
Descendants: 8 (including self, all descendants, citations, and links in subtree)
Citations: 0
```

---

## Tips

**Keep the LTAC focused on the argument.**
The LTAC file expresses the logical structure: claims, strategies, evidence.
Explanatory prose belongs in the document, outside the marked regions.

**Use meaningful identifiers.**
`AuthnClaim` is easier to work with than `G17`, especially for AI tools
that read the document. However, if you really prefer conventional
GSN naming conventions, you *can* use those conventions.

**Put `<!-- verocase warning -->` near the top.**
It reminds readers (and automated tools) that certain regions are generated.

**Use `--validate` in CI.**
A quick `verocase --validate` in your CI pipeline catches errors before
they reach reviewers.

**Use `--strip --stdout` to share the document with AI tools.**
Running `verocase --strip --stdout` produces a version of the document that
omits the bulky generated diagrams and boilerplate, leaving just the
document structure, your prose, and the LTAC markers.
This makes it much easier for an AI to understand and reason about your case.

**After `--fixmissing`, use `--fixmisplaced` to sort the document.**
`--fixmissing` now places new regions near their natural LTAC position,
so most of the time the document is already in order.
If it isn't (e.g., after reorganizing the LTAC), run `verocase --misplaced`
to see what needs moving, then `verocase --fixmisplaced` to fix it.

---

## Where to go from here

- **[Reference manual](reference.md)**: complete documentation of all
  options, selectors, element types, configuration keys, diagram formats,
  validations, and file handling.
- **[Extended LTAC format](ltac-extended.txt)**: the formal specification
  of the LTAC file format.
- **[SACM notation in Mermaid](sacm-mermaid.md)**: how SACM concepts map
  to Mermaid shapes.
- **[GSN notation in Mermaid](gsn-in-mermaid.md)**: how GSN concepts map
  to Mermaid shapes.
- **[README](../README.md)**: project overview and installation.
