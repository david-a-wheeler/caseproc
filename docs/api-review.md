# verocase library API Review (by Claude)

`verocase.py` can be imported as a Python module.  This document describes
what works today, what the friction points are, and which functions are the
most useful public API.

---

## Current state: what already works

The module is safe to import.  All top-level code is constant or regex
definitions; there are no file I/O, network calls, or environment reads at
import time.  The `if __name__ == '__main__': main()` guard is in place.

The rendering functions (`render_selector`, `render_info`, `render_ltac_txt`,
`render_element_selector`, `render_package_selector`) all accept an `out:
TextIO` parameter and return a `bool`.  They write directly to a caller-
supplied stream, making them usable from library code without capturing stdout.

---

## Friction points

### 1. Global mutable state

Two module-level globals accumulate state across calls:

| Global | Purpose | Problem |
|--------|---------|---------|
| `_had_error` | Set to `True` by `error()` on any validation problem | Never reset; a prior error contaminates later calls |
| `_strict` | Escalates warnings to errors when `True` | Set once in `main()`; no reset mechanism |

**Workaround (current):** `_inline_rewrite_file` uses `error_before = _had_error`
to detect new errors within a bounded operation.  Library callers can do the
same, but it is fragile and not thread-safe.

**Better fix:** Wrap these in a context object (e.g., `DiagnosticSink`) passed
to every function, eliminating the globals entirely.

### 2. `panic()` calls `sys.exit(1)` unconditionally

`panic()` is used for genuinely fatal situations (cannot open a required file,
circular dependency, etc.).  Any caller that imports the module as a library
will have their process terminated without recourse.

`load_config()`, `load_ltac_file()`, and several validation functions call
`panic()`.

**Better fix:** Raise a specific exception (e.g., `VerocaseError`) instead of
calling `sys.exit()`, and let the caller decide whether to exit.

### 3. Analysis functions print to stdout; no return values

`_analysis_missing`, `_analysis_empty`, `_analysis_orphans`,
`_analysis_misplaced`, `_analysis_leaves`, and `_analysis_packages` all call
`print()` directly and return nothing.  A library caller cannot obtain the
results programmatically.

**Better fix:** Return structured data (lists of nodes or strings) and let the
caller print if desired.  An optional `out: TextIO = sys.stdout` parameter
would cover the common case.

### 4. `error()` and `warn()` write to stderr unconditionally

Diagnostic output is not redirectable.  A library caller cannot intercept
warnings or errors without patching the module.

---

## Using `main()` as a library entry point

`main()` can be called directly after setting `sys.argv`:

```python
import sys
import verocase

sys.argv = ['verocase', '--stats', 'case.ltac', 'docs/case.md']
verocase.main()
# Exits with sys.exit(1) if errors occurred; returns normally on success.
```

This is the simplest integration path when you want the exact CLI behaviour
without subprocess overhead.  Be aware that `main()` may call `sys.exit(1)` on
errors and always calls `sys.exit(1)` at the end if `_had_error` is set.

---

## Recommended API (functions worth documenting and stabilising)

### Loading

```python
config = verocase.load_config(path_or_None)
```
Loads a JSON config file (or returns `DEFAULT_CONFIG` if `None`).
Calls `panic()` on file or parse errors — see friction point 2.

```python
all_roots: List[Node] = []
registry:  Dict[str, Node] = {}
id_info:   Dict[str, dict] = {}
verocase.load_ltac_file(path, all_roots, registry, id_info, config=config)
```
Parses an LTAC file and merges its nodes into the caller-supplied collections.
Calls `panic()` on I/O errors.  Can be called multiple times to load several
LTAC files into the same collections (packages will be merged).

```python
roots, registry, id_info = verocase.parse_ltac_lines(lines, config=config)
```
Lower-level parser; accepts a list of strings already in memory.  Useful for
testing or when you already have the text.  Does not call `panic()`.

### Validation (post-load)

These check the loaded data for consistency and call `error()` on problems
(setting `_had_error`):

```python
verocase.check_id_info(id_info)
verocase.check_circularities(registry, all_roots)
verocase.check_reachability(all_roots, registry)
```

### The `Node` dataclass

```python
@dataclass
class Node:
    node_type:   str             # Claim|Strategy|Evidence|Context|… |Link|Connector
    identifier:  str             # element ID (empty string if absent)
    text:        str             # statement or title text
    ext_ref:     str             # trailing (...) reference, empty if absent
    options:     List[str]       # e.g. ['axiomatic'], ['needssupport']
    children:    List['Node']
    is_cited:    bool            # True when declared with ^ prefix
    depth:       int             # 0 = package root
    parent:      Optional['Node']
    link_target: Optional['Node']
    diagram_id:  str             # stable ID for Mermaid diagrams
    id_inferred: bool            # True when ID was auto-generated from text
```

Walking the tree is straightforward:

```python
def walk(node, depth=0):
    print('  ' * depth, node.node_type, node.identifier, node.text)
    for child in node.children:
        walk(child, depth + 1)

for root in all_roots:
    walk(root)
```

### Rendering to a stream

All rendering functions write to a caller-supplied `out: TextIO` and return
`True` if anything was written.

```python
import io, verocase

buf = io.StringIO()
verocase.render_selector(
    'ltac/txt Requirements',   # selector string
    registry, all_roots, config, id_info,
    buf,                       # output stream
    doc_format='markdown',
)
print(buf.getvalue())
```

Useful selectors:

| Selector string | Renders |
|----------------|---------|
| `element ID` | Heading + cross-reference links for one element |
| `package ID` or `package *` | Heading + diagram + cross-reference links |
| `ltac/txt ID` | Raw LTAC subtree for the element and all descendants |
| `info ID` | Ancestry, children, descendant count, and citation info |
| `sacm/mermaid ID` | SACM/Mermaid diagram block |
| `gsn/mermaid ID` | GSN/Mermaid diagram block |

Lower-level entry points for specific output types:

```python
verocase.render_info(element_id, all_roots, registry, id_info, out)
verocase.render_ltac_txt(node_list, config, out)
verocase.render_element_selector(node_id, registry, all_roots, id_info, config, state, out)
verocase.render_package_selector(pkg_id_or_star, all_roots, registry, id_info, config, state, out)
```

`DocState` carries per-document rendering state (current element, seen IDs,
format, mermaid injection flag).  For standalone rendering passes create a
fresh one:

```python
state = verocase.DocState(doc_format='markdown')
```

### Processing a document stream

```python
verocase.process_document_stream(
    src_file,       # TextIO source (opened document)
    out_file,       # TextIO destination
    registry, all_roots, config, id_info,
    seen_element_ids,   # set(); updated in-place as elements are seen
    doc_format,         # 'markdown' or 'html'
    add_missing=False,  # True to scaffold missing element stubs
    strip=False,        # True to strip generated content (keep markers only)
)
```

---

## Typical usage pattern

```python
import verocase, io, sys

# 1. Load
config = verocase.load_config(None)          # or path to case.config
all_roots, registry, id_info = [], {}, {}
verocase.load_ltac_file('case.ltac', all_roots, registry, id_info, config=config)

# 2. Validate
verocase.check_id_info(id_info)
verocase.check_circularities(registry, all_roots)
verocase.check_reachability(all_roots, registry)

if verocase._had_error:
    sys.exit(1)   # or handle however you like

# 3. Query / render
for root in all_roots:
    print(root.identifier, ':', root.text)

buf = io.StringIO()
verocase.render_info('SomeClaim', all_roots, registry, id_info, buf)
print(buf.getvalue())
```

---

## Traversing LTAC data

This is likely the primary reason to import verocase as a library.  After
loading, the data lives in three structures:

### `all_roots` — the package forest

A `List[Node]` where each entry is a package root (depth 0).  Every element
has a `.parent` back-pointer and a `.children` list, so the whole tree is
navigable in any direction.

```python
# Iterate every element in LTAC (written) order — depth-first, first child first.
for node in verocase._all_nodes_forward(all_roots):
    print(node.node_type, node.identifier, node.text)

# Reverse DFS (useful when order doesn't matter; slightly faster).
for node in verocase._all_nodes(all_roots):
    ...

# BFS — useful for level-by-level processing (diagrams, etc.).
for node in verocase._collect_bfs(all_roots):
    ...
```

All three generators yield every node in the forest, including cited Link nodes
and synthetic nodes.  Filter as needed:

```python
# All declared (non-cited), non-Link elements in LTAC order:
elements = [n for n in verocase._all_nodes_forward(all_roots)
            if not n.is_cited and n.node_type != 'Link']

# Leaf claims:
leaves = [n for n in elements
          if n.node_type == 'Claim' and not n.children]

# Elements carrying a specific option:
needs_support = [n for n in elements if 'needssupport' in n.options]
```

### `registry` — lookup by ID

A `Dict[str, Node]` mapping every declared identifier to its `Node`.  Use this
for O(1) lookup when you already have an element ID:

```python
node = registry.get('SomeClaimId')
if node:
    print(node.text)
```

### `id_info` — cross-reference metadata

A `Dict[str, dict]` with one entry per identifier (both declared and cited).
Each entry has:

```python
{
    'declarations':   int,        # number of non-cited nodes with this ID (should be 1)
    'citations':      int,        # number of ^cited nodes with this ID
    'statement':      str|None,   # first text seen for this ID
    'decl_lineno':    int|None,   # line number of first declaration in the LTAC file
    'decl_pkg_id':    str|None,   # identifier of the package root that declares this ID
    'citing_pkg_ids': List[str],  # identifiers of packages that cite this ID (in order)
}
```

`id_info` is what you need to answer questions like:
- "Which package declares element X?" → `id_info['X']['decl_pkg_id']`
- "Which packages cite element X?" → `id_info['X']['citing_pkg_ids']`
- "Is X cited anywhere?" → `id_info['X']['citations'] > 0`

### Useful helper functions for traversal

These exist in the module today (as private helpers; they work fine from a
library caller):

| Function | What it does |
|----------|-------------|
| `_all_nodes_forward(roots)` | Generator: DFS in LTAC (written) order |
| `_all_nodes(roots)` | Generator: DFS, reversed children (slightly faster) |
| `_collect_bfs(roots)` | Returns `List[Node]` in BFS order |
| `_subtree_count(node)` | Count of node + all descendants |
| `_get_pkg_root(node)` | Walk `.parent` to return the package root |
| `_find_citation_parents(ident, all_roots)` | Return all nodes that cite `^ident` |
| `resolve_element(element_id, registry, all_roots, current)` | Resolve an ID (or `None`/`'*'`) to a node list |
| `_ltac_node_line(node, depth_offset=0)` | Format a single node as a LTAC line string |
| `_compute_ltac_stats(all_roots, registry, id_info)` | Return a stats dict (type counts, leaf counts, largest package, option counts) |

None of these touch `_had_error` or call `panic()` — they are pure tree
operations and safe to call from library code.

### Common traversal patterns

```python
# Walk ancestors of a node (root first):
def ancestors(node):
    path = []
    n = node.parent
    while n is not None:
        path.append(n)
        n = n.parent
    return list(reversed(path))

# Find which package a node belongs to:
pkg_root = verocase._get_pkg_root(node)

# Subtree size:
size = verocase._subtree_count(node)

# Who cites element X?
citers = verocase._find_citation_parents('X', all_roots)

# Stats dict (same data as --stats, without printing):
stats = verocase._compute_ltac_stats(all_roots, registry, id_info)
print(stats['total_elements'], stats['type_counts'], stats['leaf_claims'])
```

---

## What to fix before stabilising the API

### Priority 1 — Replace `panic()` with a raised exception

`panic()` is the single biggest barrier to library use.  Any fatal condition
(file not found, circular dependency, bad JSON config) terminates the process
with `sys.exit(1)`.  There is no way for a library caller to recover.

**Proposed change:** introduce a `VerocaseError(Exception)` and replace every
`panic(msg)` call with `raise VerocaseError(msg)`.  Callers that want the old
CLI behaviour catch it in `main()` and exit:

```python
class VerocaseError(Exception):
    pass

# In main():
try:
    load_ltac_file(...)
except VerocaseError as e:
    print(f"verocase: {e}", file=sys.stderr)
    sys.exit(1)
```

**Scope:** `panic()` is called from `load_config`, `load_ltac_file`,
`check_circularities`, `check_reachability`, and a handful of places in
`main()`.  The change is mechanical and low-risk.

### Priority 2 — Replace `_had_error` / `_strict` globals with a `DiagnosticSink`

A `DiagnosticSink` object replaces the two globals and all direct
`print(..., file=sys.stderr)` calls in `error()` and `warn()`.  Every public
function that can produce diagnostics receives a `diag:` keyword argument:

```python
@dataclass
class DiagnosticSink:
    errors:   List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    strict:   bool = False   # escalate warnings to errors

    def error(self, msg): self.errors.append(msg)
    def warn(self, msg):
        if self.strict:
            self.errors.append(msg)
        else:
            self.warnings.append(msg)

    @property
    def had_error(self): return bool(self.errors)
```

The module-level `error()` and `warn()` functions would become thin wrappers
that delegate to a thread-local default sink (for backward compatibility with
code that doesn't pass one explicitly).

**Benefit:** library callers can inspect collected messages, redirect them to a
logger, or treat warnings as errors selectively, without touching global state.

**Scope:** medium — `error()` and `warn()` are called in ~70 places.  A
find-and-replace with a forwarding default makes it incremental.

### Priority 3 — Give analysis functions return values

The six `_analysis_*` functions and `_print_stats` print directly and return
nothing.  A thin refactor separates the computation from the output:

| Current function | Returns today | Should return |
|-----------------|--------------|---------------|
| `_analysis_missing` | nothing | `List[Node]` |
| `_analysis_empty` | nothing | `List[str]` (identifiers) |
| `_analysis_orphans` | nothing | `List[str]` (identifiers) |
| `_analysis_misplaced` | nothing | `List[dict]` (ident, line, expected_after) |
| `_analysis_leaves` | nothing | `dict` with `'needssupport'` and `'all'` lists |
| `_analysis_packages` | nothing | structured list of package dicts |
| `_compute_ltac_stats` | `dict` ✓ | already good |

The simplest approach: extract the computation into a `_compute_*` helper that
returns data, and keep the `_analysis_*` function as a thin printing wrapper
calling it.  That way the CLI is unchanged and library code calls the compute
variant directly.

### Priority 4 — Declare `__all__` and document the public surface

Most helpers are already prefixed with `_`.  Adding an `__all__` list makes the
intended public API explicit and prevents accidental reliance on internals:

```python
__all__ = [
    # Data types
    'Node', 'DocState', 'DEFAULT_CONFIG',
    # Loading
    'load_config', 'load_ltac_file', 'parse_ltac_lines',
    'find_ltac_file',
    # Validation
    'check_id_info', 'check_circularities', 'check_reachability',
    # Traversal
    'all_nodes_forward', 'all_nodes', 'collect_bfs',
    'subtree_count', 'get_pkg_root', 'find_citation_parents',
    'resolve_element', 'ltac_node_line', 'compute_ltac_stats',
    # Rendering
    'render_selector', 'render_info', 'render_ltac_txt',
    'render_element_selector', 'render_package_selector',
    'process_document_stream',
    # Errors
    'VerocaseError',   # once Priority 1 is done
]
```

Note that the traversal helpers listed here would need their `_` prefix
removed (or re-exported under a public alias) as part of this work.

### Lower priority — minor items

- `load_ltac_file` mutates caller-supplied lists in place (a C-ism).  A
  cleaner signature returns `(roots, registry, id_info)` directly, like
  `parse_ltac_lines` already does.  Both forms could be offered during a
  transition.

- `_process_files` opens files without `newline=''`, unlike `_inline_rewrite_file`.
  Harmless on Linux but worth fixing for correctness on Windows.

- `DocState` is a `@dataclass` but `seen_element_ids` defaults to `None` and is
  replaced with an empty set in `__post_init__`.  Standard `field(default_factory=set)`
  would be cleaner.

---

## Most important things to document for library users

In addition to this file, the following should be documented (docstrings or
reference page) before advertising library use:

1. **`Node` fields** — especially `is_cited`, `id_inferred`, `link_target`, and
   how `depth` / `parent` / `children` form the tree.
2. **`id_info` schema** — the dict keys and what each means (declarations vs.
   citations, `decl_pkg_id`, `citing_pkg_ids`).
3. **Load sequence** — the three-step pattern: `load_config` → `load_ltac_file`
   → `check_*`.  What validations run automatically vs. what the caller must
   invoke.
4. **Error handling contract** — currently "check `_had_error` after each
   phase"; after Priority 2, "catch diagnostics from the sink".
5. **`_compute_ltac_stats` return dict** — already useful; just needs a
   docstring that names every key.
6. **Traversal helpers** — which generator to use and when (`_all_nodes_forward`
   for LTAC order, `_all_nodes` for speed, `_collect_bfs` for level order).
7. **`render_selector` selector string syntax** — the full grammar is in
   `--help`; a summary in the API docs would save callers from reading the CLI
   help.
8. **Thread safety** — currently none (global state); document this explicitly
   until Priority 2 is complete.
