# Plan 5 — Detailed Implementation

This document provides exact code-level instructions for implementing plan5.md.
The work is divided into four stages; each is independently testable.

---

## Stage 1: GSN Connector Visibility

`_sacm_node_decl` already returns a gray-circle declaration for `Connector`
nodes (line 885–886) and `_SACM_HEADER` already has `classDef connector`
(line 944).  GSN currently does neither.  Stage 1 closes that gap.

### 1.1  `_GSN_HEADER` — add `classDef connector`

**Location:** `_GSN_HEADER` constant, line ~1264.

Current last line of the string:

```
    classDef gsnUndev stroke-width:2px,stroke-dasharray: 5 5;"""
```

Append a new line before the closing `"""`:

```
    classDef gsnUndev stroke-width:2px,stroke-dasharray: 5 5;
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;"""
```

### 1.2  `_gsn_node_decl` — Connector node declaration

**Location:** line ~1201.

Current early-return guard:

```python
if node.node_type in ('Relation', 'Link', 'Connector'):
    return ''
```

Replace with two separate checks — the first handles the truly invisible types,
the second returns a visible gray-circle for `Connector`:

```python
if node.node_type in ('Relation', 'Link'):
    return ''
if node.node_type == 'Connector':
    return f'    {node.diagram_id}(("{_HAIR_SPACE}")):::connector'
```

### 1.3  `_gsn_collect_edges` — route edges through the Connector

**Location:** lines ~1284–1298 (the `elif child.node_type == 'Connector':` branch).

Current code flattens all grandchildren of the Connector directly to the
parent, as if the Connector were transparent:

```python
elif child.node_type == 'Connector':
    for gc in child.children:
        if gc.node_type == 'Link':
            if gc.link_target is not None:
                tgt = gc.link_target
                edge_lines.append(_edge_line(
                    node.diagram_id, tgt.diagram_id,
                    _gsn_is_incontextof(tgt),
                    'counter' in gc.options, False))
        else:
            edge_lines.append(_edge_line(
                node.diagram_id, gc.diagram_id,
                _gsn_is_incontextof(gc),
                'counter' in gc.options, False))
            _gsn_collect_edges(gc, edge_lines, leaf_nodes)
```

Replace with the two-line visible-Connector routing:

```python
elif child.node_type == 'Connector':
    edge_lines.append(_edge_line(node.diagram_id, child.diagram_id,
                                 False, False, False))
    _gsn_collect_edges(child, edge_lines, leaf_nodes)
```

**How it works after the change:**

`_gsn_collect_edges` does not have an early-return guard for `Connector`, so
when called recursively on a Connector node it iterates over its own children.
Each non-Link, non-Relation, non-Connector grandchild gets a
`connector --> grandchild` edge and is recursed into; Link grandchildren get
`connector --> link_target` edges; Relation grandchildren are handled by the
existing Relation branch.  The Connector's leaf status is tracked correctly via
the `edges_before` / `leaf_nodes` mechanism.

LTAC-authored Connectors in GSN are now visible gray circles instead of
transparent pass-throughs.  There are no existing test fixtures that use
Connector, so no fixtures need updating.

### 1.4  Stage 1 Tests

Add class `TestGsnConnectorVisible` in `tests/run_tests.py`.

**Test 1 — `test_gsn_connector_node_declared`**

Write an LTAC file (via `tempfile.NamedTemporaryFile`) containing:

```
- Claim Root: Root claim
  - Connector Grp
    - Claim C1: Child one
    - Claim C2: Child two
```

Run `--select gsn/mermaid`.  Assert `returncode == 0` and that stdout contains:
- `Grp(("` — the Connector node declaration
- `:::connector` — the Connector class
- `Root --> Grp` — parent-to-Connector edge
- `Grp --> C1` — Connector-to-child edge
- `Grp --> C2` — Connector-to-child edge

**Test 2 — `test_gsn_connector_not_transparent`**

Same LTAC.  Assert stdout does **not** contain `Root --> C1` and does **not**
contain `Root --> C2` (edges that the old transparent behaviour would produce).

---

## Stage 2: Configuration Keys and Invariant Check

### 2.1  `DEFAULT_CONFIG` — add two keys

**Location:** `DEFAULT_CONFIG` dict, line ~51.

Add after the existing `bottom_padding` entry:

```python
'max_mermaid_children': 8,
'narrowed_mermaid_children': 6,
```

### 2.2  `_ALLOWED_CONFIG_VALUES` — register new keys

**Location:** `_ALLOWED_CONFIG_VALUES` dict, line ~1932.

Add two entries (integer validation, zero or positive):

```python
'max_mermaid_children':    re.compile(r'^(0|[1-9][0-9]*)\Z'),
'narrowed_mermaid_children': re.compile(r'^(0|[1-9][0-9]*)\Z'),
```

### 2.3  `apply_config_directive` — convert to int and check invariant

**Location:** `apply_config_directive`, line ~1951.

Current integer-conversion block:

```python
if key in ('element_level', 'package_level'):
    config[key] = int(value)
else:
    config[key] = value
```

Replace to include the new keys:

```python
if key in ('element_level', 'package_level',
           'max_mermaid_children', 'narrowed_mermaid_children'):
    config[key] = int(value)
else:
    config[key] = value
```

Then, after that block (still inside `apply_config_directive`, before returning),
call the invariant checker when one of the width-management keys was changed:

```python
if key in ('max_mermaid_children', 'narrowed_mermaid_children'):
    config_invariant_checker(config, filename, lineno)
```

### 2.4  `config_invariant_checker` — new function

Add this function near `apply_config_directive` (e.g. just before it):

```python
def config_invariant_checker(config: dict,
                             filename: str = '',
                             lineno: int = 0) -> None:
    """Panic if max/narrowed_mermaid_children violate required invariants.

    max_mermaid_children == 0 disables the transform entirely; the other
    key is irrelevant in that case.
    Invariants when max > 0:
      narrowed_mermaid_children >= 2          (enough room to split)
      narrowed_mermaid_children < max_mermaid_children  (strictly improves)
    """
    mx = config.get('max_mermaid_children',
                    DEFAULT_CONFIG['max_mermaid_children'])
    nr = config.get('narrowed_mermaid_children',
                    DEFAULT_CONFIG['narrowed_mermaid_children'])
    if mx == 0:
        return
    prefix = f'{filename}:{lineno}: ' if filename else ''
    if nr < 2:
        panic(f'{prefix}narrowed_mermaid_children ({nr}) must be >= 2')
    if nr >= mx:
        panic(
            f'{prefix}narrowed_mermaid_children ({nr}) must be less than '
            f'max_mermaid_children ({mx})'
        )
```

### 2.5  Call `config_invariant_checker` after `load_config`

**Location:** `main()`, line ~2711, immediately after:

```python
config = load_config(config_path)
```

Add:

```python
config_invariant_checker(config)
```

### 2.6  `--help` and `docs/reference.md`

**`parse_args` epilog** — add to the caseproc-config table:

```
  max_mermaid_children      non-negative integer (default 8)
  narrowed_mermaid_children non-negative integer (default 6)
```

**`docs/reference.md`** — in the configuration-key table add two rows:

| Key | Default | Description |
|---|---|---|
| `max_mermaid_children` | `8` | Maximum number of visual children before the width-management transform splits them.  `0` disables the transform. |
| `narrowed_mermaid_children` | `6` | Number of children to keep (left + right) when splitting; the middle overflow goes into a synthetic Connector.  Must be `< max_mermaid_children` and `>= 2`. |

Also add both keys to the `caseproc-config` dynamically-settable-keys table
with accepted values `non-negative integer`.

### 2.7  Stage 2 Tests

Add `TestMermaidWidthConfig` class in `tests/run_tests.py`.

- **`test_invariant_defaults_ok`** — load default config (no file), call
  `config_invariant_checker(config)` directly; assert no exception.
- **`test_invariant_panics_narrowed_too_large`** — set
  `max=5, narrowed=5` in a temp config JSON file, run `caseproc`; assert
  non-zero exit and error message mentioning `narrowed_mermaid_children`.
- **`test_invariant_panics_narrowed_less_than_2`** — set
  `max=5, narrowed=1`; assert non-zero exit.
- **`test_invariant_max_zero_skips_check`** — set `max=0, narrowed=1`
  (would otherwise fail); assert zero exit (transform disabled).
- **`test_config_directive_sets_max`** — in a markdown doc use
  `<!-- caseproc-config max_mermaid_children = 4 -->` followed by
  `<!-- caseproc-config narrowed_mermaid_children = 2 -->` (order: narrowed
  must be set while max is still default 8 to avoid mid-stream invariant
  failure, so set narrowed FIRST); assert `returncode == 0`.

  Alternatively, set `narrowed_mermaid_children = 2` before
  `max_mermaid_children = 4` to avoid the transient invariant violation
  between the two directives.

---

## Stage 3: Width-Management Transform

### 3.1  Helper: `_make_syn_connector`

Add near the other mermaid diagram utilities (around line 800):

```python
def _make_syn_connector(children: List['Node'], parent: 'Node') -> 'Node':
    """Create a synthetic Connector node that groups *children*.

    Uses os.urandom for the ID so repeated calls in the same process do not
    collide.  The returned node is NOT yet inserted into any parent's children
    list; the caller is responsible for insertion and for updating parent.children.
    Each child's .parent back-reference is updated to point to the new Connector.
    """
    conn_id = 'SynConnect_' + os.urandom(4).hex()
    connector = Node(
        node_type='Connector',
        identifier='',
        text='',
        ext_ref='',
        options=set(),
        children=list(children),
        is_cited=False,
        depth=parent.depth + 1,
        parent=parent,
        link_target=None,
        diagram_id=conn_id,
    )
    for child in children:
        child.parent = connector
    return connector
```

`os` is already imported; no new import is needed.

### 3.2  Helper: `_sacm_effective_sources`

Mirrors the `inference_sources`-building logic of `_sacm_collect_edges` but
returns a list of `(source_node, tree_parent)` tuples instead of emitting edges.
`tree_parent` is the direct tree-parent of `source_node` (used to know which
node's `.children` list to modify).

Add near `_sacm_collect_edges`:

```python
def _sacm_effective_sources(
    node: 'Node',
) -> List[Tuple['Node', 'Node']]:
    """Return (src, tree_parent) for each node in node's SACM inference group.

    Mirrors _sacm_collect_edges inference_sources logic without emitting edges.
    Counter/abstract options are intentionally ignored (we only need counts
    and positions, not edge styles).
    """
    sources: List[Tuple['Node', 'Node']] = []
    for child in node.children:
        if child.node_type == 'Context':
            pass
        elif child.node_type == 'Strategy':
            for gc in child.children:
                if gc.node_type == 'Context':
                    pass
                elif gc.node_type == 'Relation':
                    for ggc in gc.children:
                        if ggc.node_type not in ('Context', 'Relation', 'Link'):
                            sources.append((ggc, gc))
                elif gc.node_type not in ('Relation', 'Link'):
                    sources.append((gc, child))
            sources.append((child, node))
        elif child.node_type == 'Relation':
            for gc in child.children:
                if gc.node_type not in ('Context', 'Relation', 'Link'):
                    sources.append((gc, child))
        elif child.node_type != 'Link':
            sources.append((child, node))
    return sources
```

### 3.3  Helper: `_gsn_visual_children`

Returns `(visual_child, tree_parent)` for each node that would generate an
outgoing edge from `node` in a GSN diagram.  Link targets (cross-package
citations) are excluded — they are siblings, not inferential children.

```python
def _gsn_visual_children(
    node: 'Node',
) -> List[Tuple['Node', 'Node']]:
    """Return (child, tree_parent) for each visually-expressed child in GSN.

    Counts direct non-Link, non-Relation children (with parent=node), plus
    non-Link grandchildren of Relation children (with parent=Relation child).
    Link targets are cross-package citations and are not counted.
    """
    result: List[Tuple['Node', 'Node']] = []
    for child in node.children:
        if child.node_type == 'Link':
            pass
        elif child.node_type == 'Relation':
            for gc in child.children:
                if gc.node_type != 'Link':
                    result.append((gc, child))
        else:
            result.append((child, node))
    return result
```

### 3.4  Helper: `_insert_connectors_for_overflow`

Takes the overflow slice of `(src, tree_parent)` pairs, groups by tree-parent,
and for each group removes the items from the parent's children list and
replaces them with a synthetic Connector inserted at the first overflow item's
original position.

```python
def _insert_connectors_for_overflow(
    overflow: List[Tuple['Node', 'Node']],
) -> None:
    """Group overflow items by tree-parent; create one Connector per group.

    Modifies parent.children in-place: removes overflow items, inserts a
    synthetic Connector at the position of the first removed item.
    """
    # Group by tree-parent (use id() as key so Node objects can be dict keys).
    groups: Dict[int, Tuple['Node', List['Node']]] = {}
    for src, parent in overflow:
        pid = id(parent)
        if pid not in groups:
            groups[pid] = (parent, [])
        groups[pid][1].append(src)

    for parent, items in groups.values():
        # Position of the first overflow item in this parent's children.
        item_set = set(id(n) for n in items)
        first_pos = next(
            i for i, c in enumerate(parent.children) if id(c) in item_set
        )
        for src in items:
            parent.children.remove(src)
        connector = _make_syn_connector(items, parent)
        parent.children.insert(first_pos, connector)
```

### 3.5  SACM transform: `_apply_sacm_width_transform`

Applies the narrowing transform recursively to the SACM tree (post-deep-copy).
Uses a while loop so that multiple Connectors created in one pass (due to
overflow items spanning several tree-parents) are re-checked until the count
is within bounds.

```python
def _apply_sacm_width_transform(roots: List['Node'], config: dict) -> None:
    """Narrow SACM inference groups that exceed max_mermaid_children.

    Operates in-place on the deep-copied forest.  Inserts synthetic Connector
    nodes to group middle overflow children.  Recurses into all children so
    that nested over-wide groups are narrowed too.
    """
    max_ch: int = config.get('max_mermaid_children',
                             DEFAULT_CONFIG['max_mermaid_children'])
    narrowed: int = config.get('narrowed_mermaid_children',
                               DEFAULT_CONFIG['narrowed_mermaid_children'])
    if max_ch == 0:
        return

    def _transform(node: 'Node') -> None:
        if node.node_type in ('Link', 'Relation'):
            return
        # Keep narrowing until this node's inference group is within bounds.
        while True:
            sources = _sacm_effective_sources(node)
            if len(sources) <= max_ch:
                break
            n_left = narrowed // 2
            n_right = narrowed - n_left
            overflow = sources[n_left: len(sources) - n_right]
            _insert_connectors_for_overflow(overflow)

        for child in list(node.children):
            _transform(child)

    for root in roots:
        _transform(root)
```

### 3.6  GSN transform: `_apply_gsn_width_transform`

Same pattern but uses `_gsn_visual_children` for the count.

```python
def _apply_gsn_width_transform(roots: List['Node'], config: dict) -> None:
    """Narrow GSN nodes that have too many visual children.

    Operates in-place on the deep-copied forest.
    """
    max_ch: int = config.get('max_mermaid_children',
                             DEFAULT_CONFIG['max_mermaid_children'])
    narrowed: int = config.get('narrowed_mermaid_children',
                               DEFAULT_CONFIG['narrowed_mermaid_children'])
    if max_ch == 0:
        return

    def _transform(node: 'Node') -> None:
        if node.node_type in ('Link', 'Relation'):
            return
        while True:
            children = _gsn_visual_children(node)
            if len(children) <= max_ch:
                break
            n_left = narrowed // 2
            n_right = narrowed - n_left
            overflow = children[n_left: len(children) - n_right]
            _insert_connectors_for_overflow(overflow)

        for child in list(node.children):
            _transform(child)

    for root in roots:
        _transform(root)
```

### 3.7  Integration into `_sacm_diagram_body`

**Location:** `_sacm_diagram_body`, line ~1097, immediately after the deep copy:

```python
roots = _copy_forest(roots)
_apply_sacm_width_transform(roots, config)      # ← add this line
```

The BFS for node declarations follows, so any synthetic Connectors inserted by
the transform will be visited and declared.  `_sacm_collect_edges` then handles
them via its existing Connector branch (lines 982–989).  BottomPadding is added
after edge collection, so it is placed correctly after the transform.

### 3.8  Integration into `_gsn_diagram_body`

**Location:** `_gsn_diagram_body`, line ~1329, immediately after the deep copy:

```python
roots = _copy_forest(roots)
_apply_gsn_width_transform(roots, config)       # ← add this line
```

Same ordering: transform → BFS node decls → edge collection → BottomPadding.

After Stage 1, `_gsn_node_decl` returns a declaration for Connector nodes, so
synthetic Connectors are declared correctly.  `_gsn_collect_edges` routes edges
through them (also Stage 1).

---

## Stage 4: Tests

### Stage 3 tests  —  add to `TestMermaidWidthConfig`

**`test_sacm_wide_diagram_narrowed`**

Build an LTAC (tempfile) with one Claim parent and 10 direct child Claims.
Run with a config file setting `max_mermaid_children = 8, narrowed_mermaid_children = 6`.
Use `--select sacm/mermaid`.  Assert:
- `returncode == 0`
- `SynConnect_` appears in stdout (a synthetic Connector was created)
- At most 7 children are direct children of the single sacmDot in the output
  (8 kept + 1 connector = 7 visible at that level, since 6 kept + 1 connector
  replacing 4 overflowed = 7 total).

**`test_gsn_wide_diagram_narrowed`**

Same LTAC, `--select gsn/mermaid`.  Assert:
- `returncode == 0`
- `SynConnect_` in stdout
- `:::connector` in stdout (the Connector is declared visibly)

**`test_width_transform_disabled_when_max_zero`**

Same wide LTAC, config with `max_mermaid_children = 0`.
Assert `SynConnect_` does NOT appear in stdout.

**`test_width_transform_nested`**

Build an LTAC with 3-level depth where each level has `max+1` children.
Assert `SynConnect_` appears at multiple levels (nested Connectors).
This verifies recursion works.

**`test_sacm_strategy_absorbed_narrowed`**

Build an LTAC:
```
- Claim Top: Top
  - Strategy S1
    - Claim C1: c1
    - Claim C2: c2
    - Claim C3: c3
    - Claim C4: c4
```

Run with `max_mermaid_children = 4, narrowed_mermaid_children = 2`.
The absorbed inference_sources are [C1, C2, C3, C4, S1] = 5 > 4, so
narrowing should occur.  Assert:
- `SynConnect_` in stdout (Connector created)
- `S1` still appears in the diagram (kept as rightmost)
- `C1` still appears (kept as leftmost)

---

## Summary of File Changes

| File | Changes |
|---|---|
| `caseproc` | `DEFAULT_CONFIG`: +2 keys |
| `caseproc` | `_make_syn_connector`: new helper function |
| `caseproc` | `_sacm_effective_sources`: new helper function |
| `caseproc` | `_gsn_visual_children`: new helper function |
| `caseproc` | `_insert_connectors_for_overflow`: new helper function |
| `caseproc` | `_apply_sacm_width_transform`: new function |
| `caseproc` | `_apply_gsn_width_transform`: new function |
| `caseproc` | `config_invariant_checker`: new function |
| `caseproc` | `_ALLOWED_CONFIG_VALUES`: +2 entries |
| `caseproc` | `apply_config_directive`: int conversion + invariant call |
| `caseproc` | `_gsn_node_decl`: Connector visible |
| `caseproc` | `_GSN_HEADER`: `classDef connector` added |
| `caseproc` | `_gsn_collect_edges`: Connector routed visibly |
| `caseproc` | `_sacm_diagram_body`: call `_apply_sacm_width_transform` |
| `caseproc` | `_gsn_diagram_body`: call `_apply_gsn_width_transform` |
| `caseproc` | `main()`: call `config_invariant_checker(config)` after load |
| `caseproc` | `parse_args`: update epilog for new config keys |
| `tests/run_tests.py` | `TestGsnConnectorVisible`: 2 new tests (Stage 1) |
| `tests/run_tests.py` | `TestMermaidWidthConfig`: ~8 new tests (Stages 2–3) |
| `docs/reference.md` | Config-key table: +2 rows; caseproc-config table: +2 rows |

---

## Implementation Order

Implement in this order to allow incremental testing:

1. Stage 1 (three GSN edits) → run `TestGsnConnectorVisible` tests.
2. Stage 2 config keys + invariant checker → run `TestMermaidWidthConfig`
   config/invariant tests.
3. Stage 3 helper functions + transform integration → run all width tests.
4. Update `parse_args` epilog and `docs/reference.md`.
5. Run full test suite to confirm nothing regressed.
