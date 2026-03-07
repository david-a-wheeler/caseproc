# Handling identifiers (ids) in caseproc

This document defines how element identifiers are represented and used
throughout the tool: in LTAC source, in mermaid diagrams, in document
headers, and as URL fragment anchors.

## What is an id?

Every LTAC element has an **id** — the identifier that appears immediately
after the element type keyword on an LTAC line:

```
- Claim C1: The software is acceptably safe
- Evidence Hazard Analysis: (hara-2025.pdf)
```

Here `C1` and `Hazard Analysis` are ids.
Ids must be unique across the entire assurance case (all packages).
Ids may contain spaces and most printable characters;
they may not contain `:`, `^`, or newline
(per the LTAC grammar — see `docs/ltac-extended.txt`).

Ids are the single source of truth for identifying an element.
They correspond to SACM `gid` and also serve as SACM `name`
(since SACM requires a `name` but the id already uniquely identifies
the element in a human-readable way).
The element's statement/description text is the SACM `description`.

## Mermaid node id

Mermaid does not allow spaces or many special characters in node identifiers.
The **mermaid node id** is derived from the element id by the function
`make_mermaid_id` in `caseproc`:

1. Replace any character that is not an ASCII letter or digit with `_`.
2. If the result starts with a digit, prepend `n`.
3. If the result is a reserved mermaid keyword, append `_`.
4. If the result collides with an already-assigned mermaid id, append
   a numeric suffix using a global counter.

The mermaid node id is used only inside mermaid diagram source.
It is never shown to users and never used in URLs.

## Document headers

Each element that has a corresponding document section gets a heading
of the form:

```
## {Type} {id}: {statement}
```

For example:

```
## Claim C1: The software is acceptably safe
## Evidence Hazard Analysis: (hara-2025.pdf)
```

Package-level diagram sections use a different heading form to avoid
colliding with the element's own detail section:

```
## Package {id}
```

For example: `## Package C1`.

The `--update` flag (and matching `update` config key) rewrites stale
header statements to match the LTAC, treating the LTAC as authoritative.

## Stable anchors

GitHub derives fragment ids from heading text using its own algorithm
(lowercase, remove non-alphanumerics except hyphens and spaces,
spaces → hyphens, collapse and strip hyphens).
Fragment ids derived from full heading text are **fragile**: if the
statement changes, the fragment changes, silently breaking external links.

To give each element a **stable anchor** independent of its statement,
`caseproc` inserts an explicit HTML anchor immediately before each
element heading:

```html
<a id="{type}-{id-slugified}"></a>
## Claim C1: The software is acceptably safe
```

The stable anchor id is:

1. Lowercase the type keyword (e.g. `claim`, `evidence`, `package`).
2. Append a hyphen.
3. Append the element id, lowercased, with spaces converted to hyphens
   and any character that is not alphanumeric or hyphen removed.

Examples:

| Type + id             | Stable anchor            |
|-----------------------|--------------------------|
| Claim `C1`            | `claim-c1`               |
| Evidence `Hazard Analysis` | `evidence-hazard-analysis` |
| Package `C1`          | `package-c1`             |

Mermaid `click` lines and "Referenced by" links use the stable anchor,
not the GitHub auto-generated fragment:

```
click C1 "https://github.com/org/repo/blob/main/doc.md#claim-c1"
```

```markdown
Referenced by: [Package C1](#package-c1)
```

## Summary table

| Concept          | Example                        | Used for                          |
|------------------|--------------------------------|-----------------------------------|
| id               | `Hazard Analysis`              | LTAC source, cross-references     |
| mermaid node id  | `Hazard_Analysis`              | Inside mermaid diagram source     |
| document header  | `## Evidence Hazard Analysis: ...` | Displayed heading in document |
| stable anchor    | `evidence-hazard-analysis`     | URLs, `click` lines, "Referenced by" |
