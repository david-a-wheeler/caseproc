# API improvement candidates (second pass)

*2026-03-15. Successor to ,api-improvements.md.*

Items 1–5, 8, 9, 19, 20, 21, 27 are done; 17 and 18 were dropped.
Items A, B, C, E, H, I, N, O, P are also done or dropped (see below).
H was implemented as `Case.load_ltac_string()` (a Case method using
`self.config`).  N is moot: `load_ltac_file` was deleted; `Case.load()`
validates by default and `load_ltac_string()` intentionally does not.
B and I dropped: `Union[str, bool]` return type is a maintenance headache;
callers that need string capture use `io.StringIO()` directly.
This document covers what remains: the items that still apply, updated
for the current code (Case class, instance methods, new names).

---

## D. Rename `find_citation_parents` → `citing_nodes` (was item 11)

**Current state:** `case.find_citation_parents(ident) -> List[Node]`.

**Proposed change:** Rename to `case.citing_nodes(ident)`.
Keep old name as alias.

---

## F. Rename `collect_bfs` → `nodes_bfs` (was item 13)

**Current state:** `collect_bfs(roots) -> List[Node]`; free function and
Case shim both named `collect_bfs`.

**Proposed change:** Rename to `nodes_bfs` (consistent with `all_nodes`,
`all_nodes_fast`).  Keep `collect_bfs` as alias and in `__all__`.

**Notes:** Grep `collect_bfs` in verocase.py and tests to find callers.

---

## G. Audit `render_ltac_txt`: drop unused `config` param (was item 14)

**Current state:** `render_ltac_txt(node_list, config, out, sep='')`.
The `config` parameter was carried over from an era when it may have been
used; current inspection suggests it is not referenced in the body.

**Proposed change:** Verify by reading `render_ltac_txt` and
`_write_ltac_node_normalized`.  If `config` is indeed unused:
- Remove it from the free function and the Case shim.
- Consider renaming to `write_ltac_normalized` to distinguish from
  `write_ltac` (which writes the full forest preserving depth).
- Update `__all__` and `--help-api`.

---

## J. Add `case.needs_support()` Case shim (was item 22)

**Current state:** `needs_support(nodes)` is a public free function; callers
must write `needs_support(list(case.all_nodes()))`.

**Proposed change:**

```python
def needs_support(self) -> List['Node']:
    return needs_support(list(self.all_nodes()))
```

Trivial shim; free function stays in `__all__`.

---

## K. Add `case.update_documents()` (was item 23)

**Current state:** No Case method processes all document files in-place with
the backup+atomic-replace machinery.

**Proposed change:**

```python
case.update_documents(add_missing=False, strip=False) -> bool
```

Processes every path in `self.document_files`, writes output to temp files,
calls `commit_updates` once.  Returns `not self.had_error`.

**Notes:**
- `_detect_line_ending` (or equivalent) determines CRLF handling per file —
  grep the file for how `main()` handles this before calling `_make_temp`.
- `commit_updates` and `_make_temp` are defined late in the file; Python
  resolves method body names at call time so forward references are fine.
- Consider also returning the `seen` set (like item A) so callers can
  check element coverage.
- This is the most valuable remaining high-level method: it lets library
  callers do `Case().load()` + `case.update_documents()` to mirror the CLI.

---

## L. Add `case.update_files()` — LTAC + documents atomically (was item 24)

**Current state:** No single call serializes a modified LTAC *and* updates
all documents in one atomic, backed-up operation.

**Proposed change:**

```python
case.update_files(add_missing=False, strip=False) -> bool
```

If `case.ltac_path` is set, includes the LTAC in the `(tmp, final)` pairs.
Includes all `case.document_files`.  Calls `commit_updates` once.
Clears `case.modified` on success.

**Notes:**
- Builds on `save_ltac` (now done) and `update_documents` (item K above).
- The backup snapshot covering LTAC + all docs together is the key value:
  individual snapshots of each file are internally inconsistent.
- Pairs naturally with `case.modified`:
  `if case.modified: case.update_files()`

---

## M. Expose safe file writing for non-Case files (was item 25 option C)

**Current state:** `_make_temp`, `make_backup`, `commit_updates` are private.
Items K and L expose them indirectly via Case methods.

**Recommended future design (when a concrete need arises):** A `SafeWriter`
context manager:

```python
with verocase.SafeWriter(anchor_path, case.config) as w:
    w.write('output.ltac', ltac_content)
    w.write('docs/case.md', doc_content)
# On exit: backup created, all files atomically replaced.
# On exception: temps cleaned up, nothing replaced.
```

Defer until a caller needs to include files verocase doesn't know about
in the same atomic backup.  Option A (Case methods only) is sufficient now.

---

## Summary table

| # | Change | Size | Priority |
|---|--------|------|----------|
| D | `find_citation_parents` → `citing_nodes` | Trivial | Low |
| F | `collect_bfs` → `nodes_bfs` | Trivial | Low |
| G | Audit + drop unused `config` param from `render_ltac_txt` | Small | Medium |
| J | Add `case.needs_support()` shim | Trivial | Low |
| K | Add `case.update_documents()` | Medium | High |
| L | Add `case.update_files()` (LTAC + docs atomic) | Medium | High |
| M | `SafeWriter` context manager | Large | Defer |
