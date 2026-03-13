# Streaming render architecture

## Problem

Prior to this change all render functions built their output as a Python `str`
and returned it.  The caller would then concatenate or `join` several such
strings to form a larger output, and so on up the call stack until the complete
document section was assembled in memory before being written to disk or
stdout.

For a real assurance case the generated markdown easily exceeds hundreds of
kilobytes.  Every intermediate render call therefore allocated a temporary
string that was immediately discarded once its caller concatenated it with its
siblings.  Profiling confirmed that peak memory was proportional to the total
output size (not just the "current" section), and that a significant fraction
of CPU time was spent in string concatenation.

In addition, `_inline_rewrite_file` (the function that processes document files
in place) buffered the entire rendered document in an `io.StringIO` object in
order to compare it to the original before deciding whether to write a temp
file.  For large documents this meant the whole rendered content existed in
memory at once.

## Goal

Convert every render function to accept an `out: TextIO` stream and write
directly to it.  Eliminate all intermediate string buffers.  Stream directly
from source file to temp file during document processing.

## Separator pattern

The old code used `'\n\n'.join(parts)` to separate sections.  Replacing this
with streaming requires knowing *before* writing a section whether a separator
is needed.  Several approaches were considered:

- **Trailing separator**: write `\n\n` after each section.  Leaves a stray
  blank line at the end of the last section.
- **`_SepWriter` wrapper**: tracks whether anything has been written and
  prepends a separator the next time.  Requires allocation per selection.
- **Forward-passed `pending_sep`** *(chosen)*: each render function receives
  the separator string (`sep: str = ''`) that it should write *before* its
  first byte of content, but only if it actually has content.  Callers set
  `pending_sep = '\n\n'` after each successful write.  The function that
  actually writes knows whether it has content, so no lookahead or wrapper
  object is needed.

```python
# caller side
pending_sep = ''
for item in items:
    if render_item(item, out, pending_sep):
        pending_sep = '\n\n'

# callee side
def render_item(item, out, sep='') -> bool:
    if not item.has_content():
        return False
    out.write(sep)          # write separator only if we have content
    out.write(item.body)
    return True
```

## Changes by function group

### Phase 1 — diagram body builders and leaf renderers

| Function | Old signature | New signature |
|---|---|---|
| `_sacm_diagram_body` | `(roots, config) -> str` | `(roots, config, out) -> None` |
| `_gsn_diagram_body` | `(roots, config) -> str` | `(roots, config, out) -> None` |
| `render_markdown` | `(roots, config) -> str` | `(roots, config, out) -> bool` |
| `render_html` | `(roots, config) -> str` | `(roots, config, out) -> bool` |

`_render_markdown_node` changed from `(node, indent, base_url, lines: list, …)`
to `(node, indent, base_url, out: TextIO, pkg_label, first: list)` where
`first` is a one-element `[bool]` used as a mutable "has anything been written
yet" flag, avoiding a leading `\n` before the very first line.

`_render_html_node` changed from appending to a `lines` list to writing
directly to `out`, with each `<li>` line prefixed by `\n`.

`_sacm_diagram_body` uses two DFS traversal passes: the first collects
`sacmDot` declarations (which must appear before edge lines in the Mermaid
source) into a small in-memory list, then writes them; the second pass calls
`_sacm_collect_edges` with a `write_edge` callback that writes directly to
`out`.  `_sacm_collect_edges` changed from taking `edge_lines: list` to taking
a `write_edge` callable.  BottomPadding is written as the first edge (before
the DFS pass), anchored to the leftmost deepest leaf computed by
`_sacm_leftmost_leaf`.

`_gsn_diagram_body` uses a single DFS pass via `_gsn_collect_edges` which now
takes a `write_edge` callback.  BottomPadding edges are appended *after* the
normal edges, once all leaf nodes have been identified by `_gsn_collect_edges`.
(Previously BottomPadding lines were prepended using `bp_lines + edge_lines`.)
This is a cosmetic ordering change in the Mermaid source; the rendered diagram
is unaffected.

### Phase 2 — diagram wrappers

| Function | Old signature | New signature |
|---|---|---|
| `render_sacm` | `(roots, config) -> str` | `(roots, config, out) -> bool` |
| `render_sacm_html` | `(roots, config) -> str` | `(roots, config, out, state=None) -> bool` |
| `render_gsn` | `(roots, config) -> str` | `(roots, config, out) -> bool` |
| `render_gsn_html` | `(roots, config) -> str` | `(roots, config, out, state=None) -> bool` |
| `render_all_packages` | `(all_roots, render_fn, config) -> str` | `(all_roots, render_fn, config, out) -> bool` |
| `_render_or_all` | `(…) -> str` | `(…, out) -> bool` |
| `render_representation` | `(pkg_root, …, fmt) -> str` | `(pkg_root, …, fmt, out, state=None, sep='') -> bool` |
| `_maybe_inject_mermaid_js` | `(rendered_str, config, state) -> str` | `(config, state, out) -> None` |

`_maybe_inject_mermaid_js` changed from a string transformer (prepended a
`<script>` tag to the rendered string if needed) to a direct writer called
*before* the `<pre class="mermaid">` block.

### Phase 3+4 — selection renderers and assemblers

| Function | Old signature | New signature |
|---|---|---|
| `render_referenced_by` | `(node, …, fmt) -> str` | `(node, …, fmt, out, sep='') -> bool` |
| `render_supported_by` | `(node, config, fmt) -> str` | `(node, config, fmt, out, sep='') -> bool` |
| `render_supports` | `(node, all_roots, config, fmt) -> str` | `(node, all_roots, config, fmt, out, sep='') -> bool` |
| `render_pkg_defines` | `(pkg_root, id_info, config, fmt) -> str` | `(pkg_root, id_info, config, fmt, out, sep='') -> bool` |
| `render_pkg_citing` | `(pkg_root, id_info, config, fmt) -> str` | `(pkg_root, id_info, config, fmt, out, sep='') -> bool` |
| `render_pkg_cited` | `(pkg_root, all_roots, id_info, config, fmt) -> str` | `(pkg_root, all_roots, id_info, config, fmt, out, sep='') -> bool` |
| `render_ltac_txt` | `(node_list, config=None) -> str` | `(node_list, config, out, sep='') -> bool` |
| `render_info` | `(element_id, all_roots, registry, id_info) -> str` | `(element_id, all_roots, registry, id_info, out, sep='') -> bool` |
| `_apply_selections` | `(selections, render_map, config, fmt) -> str` | `(selections, render_map, config, fmt, out, pending_sep='') -> bool` |
| `render_element_selector` | `(node_id, …, state) -> str` | `(node_id, …, state, out, sep='') -> bool` |
| `_render_single_package` | `(pkg_root, …, state) -> str` | `(pkg_root, …, state, out, sep='') -> bool` |
| `render_package_selector` | `(pkg_id_or_star, …, state) -> str` | `(pkg_id_or_star, …, state, out) -> bool` |

`_write_ltac_node_normalized` changed from `(node, lines: list, depth_offset)`
to `(node, out: TextIO, first: list, depth_offset)` — same `first` mutable-bool
pattern as `_render_markdown_node`.

`render_info` now writes directly to `out` using `\n`-prefixed continuation
lines instead of building a `lines` list.

### Phase 5 — render_selector and call sites

| Function | Old signature | New signature |
|---|---|---|
| `render_selector` | `(selector, …) -> str` | `(selector, …, out, …) -> bool` |

### Phase 6 — cleanup

- Removed `_render_to_str` helper.
- Updated `AGENTS.md` to document the streaming API conventions.

### Phase 7 — `_inline_rewrite_file` and `--fixmissing`

`_inline_rewrite_file` was rewritten to stream directly to a temp file:

- Line-ending detection reads only the first 4 KB (binary), not the whole file.
- A temp file is created with `tempfile.mkstemp` and opened with the correct
  line-ending translation (`newline='\r\n'` for CRLF files, `newline=''` for
  LF files).
- `process_document_stream` writes directly to the temp file — no
  `io.StringIO` buffer.
- After streaming, the temp file is moved into place unconditionally.  No
  comparison with the original is performed; updating the mtime on every run is
  acceptable since git (not mtime) determines what actually changed.

The `--fixmissing` two-pass algorithm (`render to StringIO`, then
`_insert_missing_stubs` with list-of-lines manipulation) was replaced by a
**single-pass** algorithm inside `process_document_stream`:

1. **Pre-scan** (`_collect_document_element_ids`): a fast scan of the file
   finds all existing `<!-- verocase element ID -->` markers without parsing
   the full document.
2. **Setup**: the set of missing element IDs is computed as `all_declared −
   already_in_doc − already_seen`.  A `_ltac_index` maps each element ID to
   its position in LTAC order.
3. **Inline insertion** (`_emit_stubs_after`): just before writing any
   `<!-- verocase element … -->` marker, the algorithm emits stubs for any
   consecutive missing elements that come immediately after the previously
   placed element in LTAC order.
4. **Flush** (`_emit_all_remaining`): before any `stop`/`epilogue` marker, any
   HTML `</body>` tag, or at EOF, all remaining missing stubs are emitted in
   LTAC order.  A `verocase-config` directive triggers only `_emit_stubs_after`
   (consecutive stubs), not a full flush, so that the config directive stays
   with the element that immediately follows it.

This eliminates `_scan_region_ends`, `_find_epilogue_line`, and
`_insert_missing_stubs`, as well as the `_inject_missing` nested function.

## Remaining `io.StringIO` uses

After all changes, `io.StringIO` no longer appears in the document-processing
path.  It remains only in test helpers and for small, bounded buffers:

- `render_element_selector` called from `--fixmissing` stub generation in
  `_emit_stubs_after`/`_emit_all_remaining` writes directly to `out` (the temp
  file stream) — no buffer.
- The `io.StringIO` import is still present for doctests and any future use.

## Functions that still return strings

A small number of helper functions still return strings because they produce
short, fixed outputs that are immediately written:

- `render_warning` — returns the short HTML comment
- `render_statement` — returns a single node's statement text
- `_make_heading` — constructs a short heading string
- `_linked_list`, `hyperlink`, `bold` — string formatters

