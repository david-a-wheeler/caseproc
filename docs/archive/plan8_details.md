# Plan 8: Detailed Implementation Plan

## Overview

Plan 8 adds three features:
1. `--stats` — print LTAC and document statistics after processing
2. `--detach ID` — extract a subtree into a new top-level package
3. `--move ID DESTINATION` — move ID's definition to be a child of DESTINATION

`--detach` and `--move` join the existing ordered mutation queue shared with
`--rename` and `--restate`.

**Change from original plan:** `--attach` was renamed to `--move` and generalized.
The original required ID to be top-level and a `^ID` citation to already exist under
DESTINATION. `--move` removes both restrictions: ID can be anywhere in the tree, and
no pre-existing citation is required. If a `^ID` citation exists directly under
DESTINATION it is replaced by the definition; otherwise the definition is appended
as DESTINATION's last child. `--move` does **not** leave a citation at ID's original
location. To leave a citation behind when moving a non-top-level node, use
`--detach ID` first (which creates a `^ID` citation in place), then `--move ID DESTINATION`.

---

## Part 1: `--stats`

### 1.1 Config option and flag

Add `'stats': False` to `DEFAULT_CONFIG` (near the other boolean defaults).

Add a `--stats` flag to the argument parser:

```python
parser.add_argument(
    '--stats',
    action='store_true', default=False,
    help='after processing, print statistics about the LTAC structure and documents',
)
```

After parsing, if `args.stats`, set `config['stats'] = True` (consistent with how
other flags override config).

### 1.2 LTAC statistics

Compute these immediately after `load_ltac_file` (i.e., after `all_roots`,
`registry`, and `id_info` are fully populated), so they're available regardless
of whether documents are processed.

**Helper: collect per-type and per-option counts**

```python
def _compute_ltac_stats(all_roots, registry, id_info):
    from collections import Counter
    type_counts = Counter()      # node_type -> count of declarations
    option_counts = Counter()    # option string -> count of elements with it
    total_citations = 0
    leaf_claims = 0             # declared Claims with no children and not cited

    pkg_sizes = []              # (size, pkg_root_identifier) per package
    for root in all_roots:
        size = 0
        for node in _all_nodes([root]):
            if node.is_cited:
                total_citations += 1
            else:
                type_counts[node.node_type] += 1
                size += 1
                for opt in node.options:
                    option_counts[opt] += 1
                if (node.node_type == 'Claim'
                        and not node.children
                        and not node.is_cited):
                    leaf_claims += 1
        pkg_sizes.append((size, root.identifier or '(unnamed)'))

    largest_pkg = max(pkg_sizes, key=lambda x: x[0]) if pkg_sizes else (0, '')
    return {
        'type_counts':     type_counts,
        'total_elements':  sum(type_counts.values()),
        'total_citations': total_citations,
        'leaf_claims':     leaf_claims,
        'largest_pkg':     largest_pkg,
        'option_counts':   option_counts,
    }
```

Note: `_all_nodes` is already defined and yields nodes depth-first. `node.options`
is a `Set[str]`; for the count include every option string present.

### 1.3 Document statistics

To avoid modifying `process_document_stream`, do a **separate lightweight scan**
of each document file. This scan uses `_CASEPROC_REGION_RE` and
`_CASEPROC_CONFIG_RE` (already compiled module-level regexes) to count:

- `pkg_regions`: lines matching `<!-- caseproc package ... -->`
- `elem_regions`: lines matching `<!-- caseproc element ... -->`
- `config_stmts`: lines matching `<!-- caseproc-config ... -->`
- `empty_elem_regions`: element regions where the user has added no
  interesting content (see below)

**"No interesting content" definition:** Between the `<!-- caseproc element ID -->`
line and the matching `<!-- end caseproc -->` line, the only non-blank lines
are the auto-generated content. After the `<!-- end caseproc -->` and before
the *next* `<!-- caseproc ... -->` or EOF, there are no non-blank,
non-HTML-comment lines. In practice: track each element region's end position
and scan the gap to the next region header.

**Simpler acceptable definition for initial implementation:** An element region
has "no interesting content" if the block between its `<!-- caseproc element -->`
and `<!-- end caseproc -->` contains only blank lines (the selector body is
always regenerated, so skip it). The interesting content is lines *outside*
caseproc regions. Count element IDs whose associated out-of-region text (from
`<!-- end caseproc -->` to the next `<!-- caseproc ... -->`) has no non-blank lines.

```python
def _scan_doc_stats(path: str) -> dict:
    """Scan a document file and return document-level statistics."""
    pkg_regions = 0
    elem_regions = 0
    config_stmts = 0
    empty_elem_regions = 0

    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return {}

    i = 0
    in_elem_region = False
    after_end = False   # True between <!-- end caseproc --> and next <!-- caseproc -->
    gap_has_content = False

    while i < len(lines):
        text = lines[i].rstrip('\r\n')
        cm = _CASEPROC_CONFIG_RE.match(text)
        if cm:
            config_stmts += 1
            i += 1
            continue
        m = _CASEPROC_REGION_RE.match(text)
        if m:
            # Close out any gap tracking
            if after_end and not gap_has_content:
                empty_elem_regions += 1
            after_end = False
            gap_has_content = False

            selector = m.group(1)
            kind = selector.split()[0] if selector else ''
            if kind == 'package':
                pkg_regions += 1
            elif kind == 'element':
                elem_regions += 1
                in_elem_region = True
            i += 1
            # Skip until end marker
            while i < len(lines):
                t = lines[i].rstrip('\r\n')
                if t.strip() == '<!-- end caseproc -->':
                    if in_elem_region:
                        after_end = True
                    in_elem_region = False
                    i += 1
                    break
                i += 1
            continue
        # Outside a region
        if after_end and text.strip() and not text.strip().startswith('<!--'):
            gap_has_content = True
        i += 1

    if after_end and not gap_has_content:
        empty_elem_regions += 1

    return {
        'pkg_regions':        pkg_regions,
        'elem_regions':       elem_regions,
        'config_stmts':       config_stmts,
        'empty_elem_regions': empty_elem_regions,
    }
```

Call this for each document file after normal processing, accumulate totals.

### 1.4 Output format

Print to stdout (not stderr) after all file processing completes. Only print
if `args.stats` and we actually did processing (not `--help`, not `--select`,
etc.). Print in the default mode, `--validate`, `--stdout`, `--update`,
`--missing`, and mutation modes.

```
=== caseproc statistics ===

LTAC structure:
  Elements by type:
    Claim      42
    Strategy    7
    Evidence   18
    ...
  Total elements defined: 67
  Total citations:        23
  Leaf Claims (no children, not cited): 14
  Largest package: Security (38 elements)
  Elements with each option:
    needsSupport  3
    undeveloped   1

Documents:
  Package regions:          1  (typical)
  Element regions:         67
  Config statements:        2
  Elements with no prose:  12
```

"(typical)" is appended when package regions == 1, as plan8.md specifies.

### 1.5 Where to insert in main()

After the primary processing block (the `if args.select / elif args.validate /
elif ... / else:` chain), add:

```python
if args.stats:
    ltac_stats = _compute_ltac_stats(all_roots, registry, id_info)
    doc_stats_total = {'pkg_regions': 0, 'elem_regions': 0,
                       'config_stmts': 0, 'empty_elem_regions': 0}
    for path in document_files:
        ds = _scan_doc_stats(path)
        for k in doc_stats_total:
            doc_stats_total[k] += ds.get(k, 0)
    _print_stats(ltac_stats, doc_stats_total if document_files else None)
```

Define `_print_stats(ltac_stats, doc_stats)` as a standalone function that
formats and prints the report. Pass `doc_stats=None` when no document files
were processed, in which case the "Documents:" section is omitted.

---

## Part 2: `--detach ID`

### 2.1 Algorithm: `apply_detach`

```python
def apply_detach(roots: List[Node], registry: Dict[str, Node],
                 id_info: Dict[str, dict], target_id: str) -> None:
    """Replace target_id's definition with a citation; promote subtree to new package.

    Panics if target_id is not defined, or if its definition is already a
    top-level package root (has no parent).
    """
    node = registry.get(target_id)
    if node is None:
        panic(f"--detach: {target_id!r} is not defined")
    if node.parent is None:
        panic(f"--detach: {target_id!r} is a top-level package root; cannot detach")

    parent = node.parent
    idx = parent.children.index(node)

    # Build a cited replacement node at the same position.
    cited = Node(
        node_type=node.node_type,
        identifier=node.identifier,
        text=node.text,
        ext_ref='',
        options=set(),
        children=[],
        is_cited=True,
        depth=node.depth,
        parent=parent,
        link_target=None,
        diagram_id=None,
    )
    parent.children[idx] = cited

    # Detach the definition node and make it a new package root.
    node.parent = None
    _recalc_depths(node, 0)
    roots.append(node)

    # Update id_info: the new package root ID for node and all descendants.
    new_pkg_id = node.identifier
    old_pkg_id = id_info.get(node.identifier, {}).get('decl_pkg_id')
    for n in _all_nodes([node]):
        if n.identifier and n.identifier in id_info:
            info = id_info[n.identifier]
            if info.get('decl_pkg_id') == old_pkg_id:
                info['decl_pkg_id'] = new_pkg_id

    # The citation is now under the old package; record it.
    id_info[target_id]['citations'] = id_info[target_id].get('citations', 0) + 1
    old_pkg_root = roots[0] if roots else None  # original package root
    # Find the actual pkg root for the cited node (walk up from parent)
    pkg_root = cited
    while pkg_root.parent is not None:
        pkg_root = pkg_root.parent
    citing_pkg = pkg_root.identifier
    if citing_pkg and citing_pkg not in id_info[target_id].get('citing_pkg_ids', []):
        id_info[target_id].setdefault('citing_pkg_ids', []).append(citing_pkg)
```

### 2.2 Helper: `_recalc_depths`

```python
def _recalc_depths(node: Node, new_depth: int) -> None:
    """Recursively update depth for node and all descendants."""
    node.depth = new_depth
    for child in node.children:
        _recalc_depths(child, new_depth + 1)
```

This helper is also needed by `apply_graft`.

### 2.3 LTAC output

`write_ltac` (already implemented) serializes `all_roots` to LTAC text.
Since `apply_detach` modifies `all_roots` in-place (appending the new package),
and replaces the definition with a cited node in the existing tree, `write_ltac`
will produce the correct output with no further changes.

The new package appears as a new blank-line-separated block after all existing
packages, which is correct LTAC.

---

## Part 3: `--move ID DESTINATION`

**Change from original plan:** this was `--attach`, which required ID to be top-level
and a citation to pre-exist under DESTINATION. `--move` is fully generalized.

### 3.1 Algorithm: `apply_move`

```python
def apply_move(roots: List[Node], registry: Dict[str, Node],
               id_info: Dict[str, dict], target_id: str, dest_id: str) -> None:
    """Move target_id's definition to be a child of dest_id.

    ID may be top-level or nested anywhere in the tree.
    If a ^ID citation exists as a direct child of dest_id, it is replaced by
    the definition; otherwise the definition is appended as the last child.
    No citation is left at the original location. To leave a citation behind
    when moving a non-top-level node, run --detach ID first, then --move.

    Panics if:
    - target_id is not defined
    - dest_id is not defined
    - dest_id is a descendant of target_id (would create a cycle; caught by
      post-mutation check_circularities, but we can also check eagerly)
    """
    node = registry.get(target_id)
    if node is None:
        panic(f"--move: {target_id!r} is not defined")
    dest = registry.get(dest_id)
    if dest is None:
        panic(f"--move: {dest_id!r} is not defined")

    # Detach node from its current location (no citation left behind).
    if node.parent is None:
        # Top-level package: remove from roots list.
        roots.remove(node)
    else:
        node.parent.children.remove(node)
        node.parent = None

    # Find a pre-existing ^ID citation among dest's direct children.
    cited_idx = None
    for i, child in enumerate(dest.children):
        if child.is_cited and child.identifier == target_id:
            cited_idx = i
            break

    # Insert node under dest.
    if cited_idx is not None:
        # Replace the citation with the definition; citation count decreases by 1.
        dest.children[cited_idx] = node
        id_info[target_id]['citations'] = max(
            0, id_info[target_id].get('citations', 1) - 1)
    else:
        # No pre-existing citation; append as last child.
        dest.children.append(node)

    node.parent = dest
    _recalc_depths(node, dest.depth + 1)

    # Update decl_pkg_id for node and all its descendants to dest's package root.
    dest_pkg_root = dest
    while dest_pkg_root.parent is not None:
        dest_pkg_root = dest_pkg_root.parent
    new_pkg_id = dest_pkg_root.identifier
    old_pkg_id = id_info.get(target_id, {}).get('decl_pkg_id')
    for n in _all_nodes([node]):
        if n.identifier and n.identifier in id_info:
            info = id_info[n.identifier]
            if info.get('decl_pkg_id') == old_pkg_id:
                info['decl_pkg_id'] = new_pkg_id
```

### 3.2 Notes

- **No citation left behind.** `--move` silently removes ID from its original
  location. To leave a `^ID` citation there, run `--detach ID` first (which
  creates the citation), then `--move ID DESTINATION`.
- **Cycle detection.** Moving a node under one of its own descendants would
  create a cycle. The existing `check_circularities` call after all mutations
  catches this; no extra eager check is strictly required, but it is shown in
  the docstring for clarity.
- **Citations elsewhere.** Any `^ID` citations in other parts of the tree
  remain valid — they still refer to the definition, which has just moved.
  Only a direct `^ID` child of DESTINATION (if present) is consumed.

(`_recalc_depths` is shared with `apply_detach`.)

---

## Part 4: Queue integration

### 4.1 `_MutationAction` — no change needed

The `_MutationAction` class already uses `option_string.lstrip('-')` to derive
the op name, so adding `--move` requires no change to the class itself.

### 4.2 Replace `--attach` with `--move` in the argument parser

Remove the `--attach` `add_argument` call and replace with:

```python
parser.add_argument(
    '--move', metavar=('ID', 'DESTINATION'),
    nargs=2, action=_MutationAction, dest='mutations', default=None,
    help=(
        "move ID's definition to be a child of DESTINATION. "
        "ID may be anywhere in the tree (top-level or nested). "
        "If ^ID is already a direct child of DESTINATION it is replaced by "
        "the definition; otherwise the definition is appended as the last child. "
        "No citation is left at the original location — to leave one behind, "
        "run --detach ID first, then --move ID DESTINATION. "
        "Panics if ID or DESTINATION is not defined. "
        "Joins the shared mutation queue with --rename, --restate, and --detach."
    ),
)
```

### 4.3 Update the mutation dispatch loop

Replace `attach` with `move`:

```python
for op, a, b in args.mutations:
    if op == 'rename':
        apply_rename(all_roots, registry, id_info, a, b)
    elif op == 'restate':
        apply_restate(all_roots, registry, id_info, a, b)
    elif op == 'detach':
        apply_detach(all_roots, registry, id_info, a)
    elif op == 'move':
        apply_move(all_roots, registry, id_info, a, b)
```

### 4.4 Update help text and epilog

1. Update `_MutationAction` docstring to mention `--move` instead of `--attach`.

2. In the `parse_args()` epilog, replace `--attach` with `--move` in the list
   of options that may modify the LTAC file.

3. Update the shared-queue paragraph:

   ```
   The options --rename, --restate, --detach, and --move all share a single
   ordered mutation queue. They are applied to the LTAC tree in the order
   they appear on the command line. Order matters: for example,
   '--detach C2 --move C2 C1' detaches C2 first, then moves it under C1.
   ```

---

## Part 5: Tests

### 5.1 `--stats` tests

Add a new `TestStats` class in `run_tests.py`:

- **`test_stats_basic_ltac`**: Run with `--stats` and a simple LTAC (no doc
  files). Capture stdout/stderr. Assert output contains "LTAC structure:",
  element type lines, leaf claim count, and largest package. Assert "Documents:"
  section is absent.
- **`test_stats_with_doc`**: Run `--stats` with a small LTAC and a matching
  `.md` doc that has `<!-- caseproc package * -->` and one `<!-- caseproc element ID -->`.
  Assert "Documents:" section appears with correct pkg_regions=1 "(typical)" and
  elem_regions=1.
- **`test_stats_package_typical`**: Verify "(typical)" appears when exactly 1
  package region, absent when 0 or >1.

### 5.2 `--detach` tests

Add a new `TestDetach` class:

- **`test_detach_basic`**: Three-level LTAC with C1→C2→C3. Run `--detach C2`.
  Read the output LTAC and assert:
  - C1's children contains `^C2` (cited, no grandchildren)
  - A second package exists with C2 as root and C3 as child
- **`test_detach_unknown_id`**: `--detach NoSuch` panics (non-zero exit, error message).
- **`test_detach_top_level`**: `--detach C1` where C1 is the package root — panics.
- **`test_detach_write_ltac`**: Verify serialized LTAC round-trips through the
  parser correctly (no validation errors after detach).

Since `--detach` modifies the LTAC file, use `tempfile`-based fixtures.

### 5.3 `--move` tests

Add a new `TestMove` class:

- **`test_move_from_top_level_with_citation`**: Start with the LTAC produced by
  `test_detach_basic` (C1→^C2 in one package, C2→C3 as its own package). Run
  `--move C2 C1`. Verify the LTAC is back to the original three-level structure
  (C1→C2→C3 in one package, no separate C2 package).
- **`test_move_from_top_level_no_citation`**: C1 and C2 are separate top-level
  packages with no citation relationship. Run `--move C2 C1`. Verify C2 becomes
  a child of C1 (appended as last child) and no separate C2 package remains.
- **`test_move_from_nested`**: C1→C2→C3 in one package. Run `--move C3 C1`.
  Verify C3 is now a direct child of C1 (no citation left behind under C2)
  and C2 has no children.
- **`test_move_no_citation_left`**: Confirm that after `--move` the original
  parent has no `^ID` citation where the definition used to be.
- **`test_move_unknown_target`**: panics.
- **`test_move_unknown_dest`**: panics.

### 5.4 Queue ordering test

- **`test_detach_then_move_queue`**: Single invocation with `--detach C2 --move C2 C1`.
  Verify the result matches the original three-level structure (detach then move
  is identity when citation pre-existed).
- **`test_rename_then_detach_queue`**: `--rename C2 X2 --detach X2`.
  Verify C2 is renamed to X2, then X2 is detached (old name C2 gone,
  new top-level package is X2).

---

## Part 6: Implementation order

1. ~~Add `_recalc_depths` helper~~ — already done.
2. ~~Add `apply_detach` function~~ — already done.
3. ~~Extend `_MutationAction`~~ — already done (uses `option_string.lstrip('-')`).
4. ~~Add `--stats`, `_compute_ltac_stats`, `_scan_doc_stats`, `_print_stats`~~ — already done.
5. Replace `apply_attach` with `apply_move` (generalized algorithm).
6. Replace `--attach` with `--move` in `parse_args()`.
7. Update mutation dispatch loop (`attach` → `move`).
8. Update `_MutationAction` docstring and epilog (`attach` → `move`).
9. Write tests in order: detach, move, queue.

Run `tests/run_tests.py` after each step.
