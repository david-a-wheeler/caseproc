# verocase library API Review

`verocase.py` can be imported as a Python module.  This document describes
the public API, how to use it, and what remains to be done.

---

## Current state: what works today

The module is safe to import.  All top-level code is constant or regex
definitions; there are no file I/O, network calls, or environment reads at
import time.  The `if __name__ == '__main__': main()` guard is in place.

`__all__` declares the intended public surface (40 names).  Running
`help(verocase)` after import shows docstrings for every public function
and class.

---

## Session state

Two module-level variables track per-session state:

| Name | Type | Meaning |
|------|------|---------|
| `had_error` | `bool` | Set to `True` by `error()` on any validation problem |
| `strict` | `bool` | When `True`, escalates warnings to errors (`--error` flag) |

Call `reset()` before each independent processing session to clear both.
`main()` calls `reset()` automatically.

---

## Typical usage pattern

```python
import verocase, io, sys

# 1. Reset session state
verocase.reset()

# 2. Load
config = verocase.load_config(None)          # or path to case.config
all_roots, registry, id_info = verocase.load_ltac_file('case.ltac', config=config)

# 3. Validate
verocase.check_id_info(id_info)
verocase.check_circularities(registry, all_roots)
verocase.check_reachability(all_roots, registry)

if verocase.had_error:
    sys.exit(1)

# 4. Query / render
for root in all_roots:
    print(root.identifier, ':', root.text)

buf = io.StringIO()
verocase.render_info('SomeClaim', all_roots, registry, id_info, buf)
print(buf.getvalue())
```

---

## Public API reference

### Exceptions and session

```python
class VerocaseError(Exception): ...   # raised by panic() on fatal errors
had_error: bool                       # True after any error() call
strict:    bool                       # True when warnings escalate to errors
reset()                               # clear had_error and strict
```

### Data types

```python
@dataclass class Node: ...      # one node in the LTAC tree; see docstring for fields
  node.is_citation    # True if introduced with ^ (cross-package citation)
  node.is_definition  # True if neither a citation nor a Link (property)
                      # Every node is exactly one of: citation, Link, or definition.
@dataclass class DocState: ...  # per-document rendering state
DEFAULT_CONFIG: dict            # default configuration values
```

### Loading and serialization

```python
config = load_config(path_or_None)
all_roots, registry, id_info = load_ltac_file(path, config=config)
all_roots, registry, id_info = parse_ltac_lines(lines, config=config)
path  = find_ltac_file(ltac_arg, config)
text  = write_ltac(all_roots)          # serialize forest back to LTAC text
fmt   = detect_doc_format(path)        # 'markdown' or 'html'
```

### Validation (call after loading; set `had_error` on problems)

```python
check_id_info(id_info)
check_circularities(registry, all_roots)
check_reachability(all_roots, registry)
```

### Tree traversal

```python
# Generators (yield Node)
all_nodes(roots)       # DFS, LTAC written order (first child first) — prefer this
all_nodes_fast(roots)  # DFS, consistent but not LTAC order; ~2-3x faster;
                       # use only when order doesn't matter; do not depend on
                       # the specific order produced

# Returns list
collect_bfs(roots)              # BFS, roots first

# Single-node helpers
subtree_count(node) -> int
get_pkg_root(node) -> Node
find_citation_parents(ident, all_roots) -> List[Node]
resolve_element(element_id, registry, all_roots, current) -> List[Node]
ltac_node_line(node, depth_offset=0) -> str
compute_ltac_stats(all_roots, registry, id_info) -> dict

# Tree copy
copy_forest(roots) -> List[Node]   # deep copy; originals untouched
```

### Analysis (return structured data; caller prints)

```python
analysis_missing(all_roots, registry, document_files) -> List[Node]
analysis_empty(document_files, registry)               -> List[str]
analysis_orphans(document_files, registry)             -> List[str]
analysis_misplaced(document_files, all_roots, registry)-> List[tuple]
analysis_leaves(all_roots)                             -> List[Node]
needs_support(nodes)                                   -> List[Node]
analysis_packages(all_roots, out=sys.stdout)           -> None
print_stats(ltac_stats, doc_stats, out=sys.stdout)     -> None
```

`analysis_misplaced` returns `(ident, lineno, filepath, pred_ident, pred_lineno)` tuples.

### Rendering to a stream

All rendering functions write to a caller-supplied `out: TextIO` and return
`True` if anything was written.

```python
render_selector(selector, registry, all_roots, config, id_info, out,
                current_element=None, doc_format='markdown', state=None) -> bool
render_info(element_id, all_roots, registry, id_info, out) -> bool
render_ltac_txt(node_list, config, out) -> bool
render_element_selector(node_id, registry, all_roots, id_info, config, state, out) -> bool
render_package_selector(pkg_id_or_star, all_roots, registry, id_info, config, state, out) -> bool
process_document_stream(src, out, registry, all_roots, config, id_info,
                        seen_element_ids, doc_format='markdown',
                        add_missing=False, strip=False) -> None
```

Useful `render_selector` selector strings:

| Selector | Renders |
|----------|---------|
| `element ID` | Heading + cross-reference links for one element |
| `package ID` or `package *` | Heading + diagram + cross-reference links |
| `ltac/txt ID` | Raw LTAC subtree |
| `info ID` | Ancestry, children, descendant count, citation info |
| `sacm/mermaid ID` | SACM/Mermaid diagram block |
| `gsn/mermaid ID` | GSN/Mermaid diagram block |

Create a fresh `DocState` for standalone rendering passes:

```python
state = verocase.DocState(doc_format='markdown')
```

### `main()`

```python
success: bool = main()   # parses sys.argv, runs full CLI pipeline
```

Returns `True` on clean success, `False` if any errors were encountered.
Raises `VerocaseError` on fatal errors.  Calls `reset()` on entry.

For full parameter-level detail on any function, import the module and run:

```
python3 -c "import verocase; help(verocase)"
```

---

## Traversing LTAC data

### `all_roots` — the package forest

A `List[Node]` where each entry is a package root (depth 0).

```python
# LTAC written order — use for ordered reports and document comparison
for node in verocase.all_nodes(all_roots):
    print(node.node_type, node.identifier, node.text)

# Unordered — slightly faster
for node in verocase.all_nodes_fast(all_roots):
    ...

# BFS — useful for level-by-level processing (diagrams, etc.)
for node in verocase.collect_bfs(all_roots):
    ...
```

Common filters:

```python
# All definition nodes in LTAC order (excludes citations and Links):
elements = [n for n in all_nodes(all_roots) if n.is_definition]

# Leaf claims:
leaves = [n for n in elements
          if n.node_type == 'Claim' and not n.children]

# Elements carrying a specific option:
needs_support_elems = verocase.needs_support(elements)
```

### `registry` — lookup by ID

```python
node = registry.get('SomeClaimId')
```

### `id_info` — cross-reference metadata

Each entry has:

```python
{
    'declarations':   int,        # number of non-citation nodes with this ID (should be 1)
    'citations':      int,        # number of ^cited nodes with this ID
    'statement':      str|None,   # first text seen for this ID
    'decl_lineno':    int|None,   # line number of first declaration
    'decl_pkg_id':    str|None,   # identifier of the declaring package root
    'citing_pkg_ids': List[str],  # identifiers of packages that cite this ID
}
```

### Useful helper patterns

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
pkg_root = verocase.get_pkg_root(node)

# Subtree size:
size = verocase.subtree_count(node)

# Who cites element X?
citers = verocase.find_citation_parents('X', all_roots)

# Stats dict (same data as --stats, without printing):
stats = verocase.compute_ltac_stats(all_roots, registry, id_info)

# Serialize a (possibly modified) forest back to LTAC:
text = verocase.write_ltac(all_roots)

# Copy forest before modifying (keeps original intact):
import_roots = verocase.copy_forest(all_roots)
```

---

## Remaining friction points

### `error()` and `warn()` write to stderr unconditionally

Diagnostic output is not redirectable.  A library caller cannot intercept
warnings or errors without patching the module.  Low priority for typical
single-threaded use: `had_error` indicates whether problems occurred, and
the stderr output is informational.  If structured diagnostic collection
is needed, the right fix is a `DiagnosticSink` context object passed to
every public function — a medium-scope change.

---

## What to add before stabilising the API

### Add `--help-api`

A `--help-api` flag that prints a curated usage summary and points callers
to `python3 -c "import verocase; help(verocase)"` for full detail.
Alongside `__all__` and docstrings, this makes the library discoverable
from the CLI alone.
