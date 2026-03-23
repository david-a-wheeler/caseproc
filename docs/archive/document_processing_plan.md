# Document Processing Redesign — Implementation Plan

This plan implements the redesign described in `document_processing.md`.
Each step is small and focused; the test suite should pass after every step.
Steps within a phase are mostly independent unless noted.

Reference: `verocase.py` line numbers are from the pre-redesign state.

---

## Phase 1 — Pure Additions (no behaviour change)

All steps in this phase only add new code. Existing paths are untouched.
The full test suite must pass after each step.

### Step 1.1 — Add `ElementDocInfo` and `DocPassStats` dataclasses

Add near the other dataclasses (e.g., alongside `DocState`):

```python
@dataclass
class ElementDocInfo:
    filepath: str
    start_lineno: int   # 1-based line of <!-- verocase element ID -->
    end_lineno: int     # 1-based last line of full region (incl. trailing prose)
    has_prose: bool     # region has non-generated content after <!-- end verocase -->
    is_orphan: bool     # present in doc but not in LTAC

@dataclass
class DocPassStats:
    pkg_regions: int  = 0   # count of <!-- verocase package ... --> markers
    config_stmts: int = 0   # count of <!-- verocase-config ... --> directives
    # elem_regions = len(element_doc_info)
    # empty_elem_regions = sum(1 for e in element_doc_info.values() if not e.has_prose)
```

Note: `_NullWriter` already exists at line 5374 — do not add a duplicate.

### Step 1.2 — Add new `Case` instance fields

In `Case.__init__()`, add alongside existing flag fields:

```python
# Document pass results — None means "no pass has run yet"
self.element_doc_info: Optional[Dict[str, ElementDocInfo]] = None
self.element_doc_order: Optional[List[Tuple[str, str, int]]] = None
self.doc_pass_stats: Optional[DocPassStats] = None

# LTAC-derived leaf set — managed by reset_cache(), not _reset_doc_processing()
self.important_leaves: Set[str] = set()

# Error suppression
self._suppress_reporting: bool = False
self._suppressed_messages: List[Tuple[str, str]] = []
```

### Step 1.3 — Add `_NON_INCREMENTAL_CACHE_FIELDS` class constant

Add to the `Case` class body (not `__init__`):

```python
_NON_INCREMENTAL_CACHE_FIELDS = frozenset({'important_leaves'})
```

### Step 1.4 — Add `_reset_doc_processing()`

```python
def _reset_doc_processing(self) -> None:
    """Reset all document-pass results to None (sentinel: no pass has run)."""
    self.element_doc_info = None
    self.element_doc_order = None
    self.doc_pass_stats = None
```

Does NOT touch `important_leaves` (LTAC-derived) or `had_error` (managed by `clear_errors()`).

### Step 1.5 — Add `clear_errors()`

```python
def clear_errors(self) -> None:
    """Reset had_error and clear any suppressed messages."""
    self.had_error = False
    self._suppressed_messages = []
```

### Step 1.6 — Add `suppressed_reporting()` context manager

```python
@contextmanager
def suppressed_reporting(self):
    """Suppress stderr output from error()/warn() within this block.
    had_error is still set. Suppressed messages are collected in
    self._suppressed_messages (cleared at entry, readable after exit)."""
    prev = self._suppress_reporting
    self._suppress_reporting = True
    self._suppressed_messages = []
    try:
        yield
    finally:
        self._suppress_reporting = prev
```

### Step 1.7 — Add suppression check to `error()` and `warn()`

Modify `error()` and `warn()` to respect `_suppress_reporting`. `had_error` is
always set regardless:

```python
def error(self, msg: str) -> None:
    self.had_error = True
    if self._suppress_reporting:
        self._suppressed_messages.append(('error', msg))
    else:
        print(f"verocase: error: {msg}", file=self.stderr)
```

Apply the same pattern to `warn()` (using `'warn'` label; `had_error` is set
only if `warn()` currently sets it — preserve existing semantics).

---

## Phase 2 — Cache Extension

Adds `important_leaves` to the cache machinery. No behaviour change to existing
callers since the new field is additive.

### Step 2.1 — Extend `recalculate_cache()` (line 1150)

In the existing forest walk, add computation of `important_leaves`:
a leaf definition node is one that is a definition (non-Link, non-Citation),
has no children, and has no `ext_ref`. Add `'important_leaves': <set>` to the
returned dict.

### Step 2.2 — Update `reset_cache()` (line 1243)

Store `important_leaves` from the dict returned by `recalculate_cache()`:

```python
self.important_leaves = cache['important_leaves']
```

### Step 2.3 — Add `skip_non_incremental` parameter to `doublecheck_cache()` (line 1211)

```python
def doublecheck_cache(self, cache: Optional[dict] = None,
                      skip_non_incremental: bool = False) -> bool:
```

When `skip_non_incremental=True`, exclude keys in `_NON_INCREMENTAL_CACHE_FIELDS`
from the comparison. All existing call sites pass no argument, so they get
`False` (default) — no behaviour change.

### Step 2.4 — Add `reset_cache()` call to `load_ltac_string()` (line 811)

`load_ltac_string()` calls `_LTACParser` but does not currently call
`reset_cache()`, leaving `important_leaves` and other cache fields stale.
Add the same computed-once pattern used at the end of `_parse_ltac_file()`:

```python
computed = self.recalculate_cache()
if doublecheck:
    self.doublecheck_cache(cache=computed, skip_non_incremental=True)
self.reset_cache(cache=computed)
```

Verify the same pattern is present (or add it) at the end of `_parse_ltac_file()`
(line 961) as well, so `important_leaves` is populated after every LTAC load.

---

## Phase 3 — Extend `process_document()` with Side-Effects

`process_document()` (line 2671) gains new behaviour but keeps its existing
`seen_ids` parameter and return value intact so current callers are unaffected.

### Step 3.1 — Add `renames` parameter

Add `renames: Optional[Dict[str, str]] = None` to the signature.
When non-None, rewrite any `<!-- verocase element OLD_ID -->` marker to
`<!-- verocase element NEW_ID -->` as it is encountered.
When None (the default), no rewriting occurs — zero overhead.

### Step 3.2 — Add `has_prose` tracking and populate `element_doc_info`

Port the `has_prose` tracking logic from `_scan_document_elements()` (line 2128)
into `process_document()`. Definition: a region has prose if there is at least
one non-blank, non-HTML-comment line between `<!-- end verocase -->` and the
next marker (or end of file).

As each element region is encountered, write to `self.element_doc_info`:

```python
if self.element_doc_info is None:
    self.element_doc_info = {}
    self.element_doc_order = []
    self.doc_pass_stats = DocPassStats()
self.element_doc_info[ident] = ElementDocInfo(
    filepath=..., start_lineno=..., end_lineno=...,
    has_prose=..., is_orphan=...)
self.element_doc_order.append((ident, filepath, start_lineno))
```

Orphan detection (`is_orphan`): element ID is not in `self.all_definitions_for`.
Report orphan errors immediately (at the line where the unknown ID appears) via
`self.error(...)` — do not defer to `_post_pass_checks()`.

### Step 3.3 — Count `pkg_regions` and `config_stmts` in `doc_pass_stats`

Increment `self.doc_pass_stats.pkg_regions` each time a
`<!-- verocase package ... -->` marker is encountered, and
`self.doc_pass_stats.config_stmts` for each `<!-- verocase-config ... -->` directive.

Initialise `doc_pass_stats` at the same point as `element_doc_info` in 3.2.

---

## Phase 4 — Add New Orchestrators (alongside existing ones)

New orchestrators are added but not yet wired into any call site. Existing
paths remain fully operational. Tests pass unchanged.

### Step 4.1 — Add `_process_document_file()`

```python
def _process_document_file(self, input_path: str, out,
                            add_missing: bool = False,
                            strip: bool = False,
                            renames: Optional[Dict[str, str]] = None,
                            existing_ids: Optional[set] = None) -> None:
```

- Reads first 4 KB in binary to detect line endings (same as `_rewrite_document_file()`).
- Detects `doc_format` from `input_path`.
- Opens `input_path` with `utf-8` / detected line endings.
- Calls `process_document(f, out, doc_format, add_missing=add_missing,
  strip=strip, renames=renames, existing_ids=existing_ids)`.
- On `OSError`: calls `self.error(...)` and returns without raising.
- Does NOT call `_reset_doc_processing()` — that is the orchestrator's job.

Note: the `existing_ids` parameter bridges the transition period. It is used
by `update_documents()` to pass pre-scanned IDs for `add_missing=True`, until
`_collect_document_element_ids()` can be removed (Phase 8).

### Step 4.2 — Add `_post_pass_checks()`

Called by every orchestrator after all files have been processed:

1. **Missing elements:** for each definition node in LTAC (non-Link, non-Citation,
   non-empty identifier) whose ID is not in `element_doc_info`, emit
   `self.error(f"element {ident!r} has no document region (use --fixmissing)")`.
2. **Important leaves with no prose:** for each `ident` in `self.important_leaves`
   where `element_doc_info[ident].has_prose` is `False`, emit a warning/error.
3. **Misplaced elements:** if config `ltac_order=true` or CLI `--misplaced` flag,
   run LIS on `element_doc_order` vs LTAC order; report offenders.

All output goes to `self.stderr`, even when the orchestrator is `stdout_documents()`.

### Step 4.3 — Add `scan_documents()`

```python
def scan_documents(self) -> bool:
    """Scan all document_files without modifying them.
    Populates element_doc_info, element_doc_order, doc_pass_stats.
    Returns not self.had_error."""
    self._reset_doc_processing()
    for path in self.document_files:
        self._process_document_file(path, _NullWriter())
    self._post_pass_checks()
    return not self.had_error
```

### Step 4.4 — Add `stdout_documents()`

```python
def stdout_documents(self, strip: bool = False) -> bool:
    """Write all document_files to stdout (rendered), without modifying files.
    Returns not self.had_error."""
    self._reset_doc_processing()
    for path in self.document_files:
        self._process_document_file(path, sys.stdout, strip=strip)
    self._post_pass_checks()
    return not self.had_error
```

### Step 4.5 — Add `update_documents()`

```python
def update_documents(self, add_missing: bool = False,
                     strip: bool = False,
                     renames: Optional[Dict[str, str]] = None) -> bool:
    """Rewrite all document_files in place (LTAC treated as fixed).
    Returns not self.had_error."""
```

Implementation:

1. If `add_missing=True`: call `scan_documents()` first to populate
   `element_doc_info`; save `frozenset(self.element_doc_info.keys())` as
   `pre_existing_ids`; then call `_reset_doc_processing()` to start fresh
   for the update pass.
2. Loop over `self.document_files` with `tempfile.mkstemp()` per file:
   - On temp file error: `self.error(...)`, continue.
   - Call `_process_document_file(path, tmp_f, add_missing=is_last,
     strip=strip, renames=renames,
     existing_ids=pre_existing_ids if (add_missing and is_last) else None)`.
   - On write error: clean up temp, `self.error(...)`, continue.
   - Append `(tmp_path, path)` to pairs list.
3. Call `commit_updates(pairs)`.
4. Call `_post_pass_checks()`.
5. Return `not self.had_error`.

`is_last` is `True` only for the final file in `document_files` — `add_missing`
stub injection only applies there (consistent with current behaviour).

---

## Phase 5 — Switch Existing Methods to New Orchestrators

Each step replaces an existing method body with a call to the new orchestrators.
The method signatures are kept unchanged for now.

### Step 5.1 — Reimplement `update_files()` (line 1950)

Replace the body (the per-file `_rewrite_document_file()` loop and the
`check_element_coverage()` call) with:

```python
def update_files(self, add_missing: bool = False, strip: bool = False) -> bool:
    self.update_documents(add_missing=add_missing, strip=strip)
    if self.ltac_modified and self.ltac_path:
        tmp = self._make_ltac_temp(self.ltac_path)
        if tmp is not None:
            self.commit_updates([(tmp, self.ltac_path)])
            self.ltac_modified = False
    return not self.had_error
```

`_post_pass_checks()` is now called inside `update_documents()`, so the
explicit `check_element_coverage()` call is removed here.

### Step 5.2 — Reimplement `fixmissing()` (line 1724)

```python
def fixmissing(self) -> bool:
    self.update_documents(add_missing=True)
    all_ids = [node.identifier for node in self.all_nodes_fast()
               if node.is_definition and node.identifier]
    self._mark_needs_support(all_ids)
    if self.ltac_modified and self.ltac_path:
        tmp = self._make_ltac_temp(self.ltac_path)
        if tmp is not None:
            self.commit_updates([(tmp, self.ltac_path)])
            self.ltac_modified = False
    return not self.had_error
```

### Step 5.3 — Update `fix_misplaced_documents()` (line 1701)

Add `scan_initial_docs: bool = True` parameter. Implement 3-pass flow:

1. **Pass 1:** if `scan_initial_docs=True`, call `scan_documents()` to ensure
   `element_doc_info` and `element_doc_order` reflect on-disk state. If
   `scan_initial_docs=False`, panic if `element_doc_info is None`.
2. Run LIS on `element_doc_order` vs LTAC order. If nothing misplaced, return
   `True` — existing `element_doc_info` is still valid, no files changed.
3. **Pass 2 (only when misplaced found):** for each affected file, read into
   memory; rearrange regions using `ElementDocInfo.start_lineno` / `end_lineno`
   bounds from `element_doc_info`; commit to disk. (The existing
   `_fix_misplaced_document()` inline scan is preserved for this step since
   it reads the whole file into memory for rearrangement.)
4. **Pass 3 (only when Pass 2 ran):** call `scan_documents()` to reset and
   repopulate `element_doc_info` from the newly written files, and trigger
   all standard post-pass reporting.

After this method returns, `element_doc_info` always reflects on-disk state.

### Step 5.4 — Switch `run()` stdout path (line 6137)

Replace:
```python
seen = case._process_document_files(case.document_files, sys.stdout, strip=args.strip)
case.check_element_coverage(seen)
```
with:
```python
case.stdout_documents(strip=args.strip)
```

### Step 5.5 — Remove `_scan_docs()` local function from `run()` (line 6120)

Replace the two call sites (`args.validate` block at ~6132 and `args.read_only`
block at ~6152) with direct calls to `case.scan_documents()`. Then delete the
`_scan_docs()` local function definition.

---

## Phase 6 — Simplify Analysis Functions

After Phase 5, `element_doc_info` is populated by all execution paths.
Analysis functions can now read from it directly instead of re-scanning.

### Step 6.1 — Reimplement `missing()` (line 2207)

```python
def missing(self) -> List[str]:
    """IDs of LTAC definition nodes with no document selector region."""
    if self.element_doc_info is None:
        return []
    defined = {node.identifier for node in self.all_nodes_fast()
               if node.is_definition and node.identifier}
    return [ident for ident in defined if ident not in self.element_doc_info]
```

### Step 6.2 — Reimplement `empty()` (line 2216)

```python
def empty(self) -> List[str]:
    """IDs of element regions that have no prose."""
    if self.element_doc_info is None:
        return []
    return [ident for ident, info in self.element_doc_info.items()
            if not info.has_prose]
```

### Step 6.3 — Reimplement `orphans()` (line 2226)

```python
def orphans(self) -> List[str]:
    """IDs present in documents but not in LTAC."""
    if self.element_doc_info is None:
        return []
    return [ident for ident, info in self.element_doc_info.items()
            if info.is_orphan]
```

### Step 6.4 — Reimplement `misplaced()` (line 2232)

```python
def misplaced(self) -> List[str]:
    """IDs whose document order differs from LTAC order."""
    if self.element_doc_order is None:
        return []
    # Run LIS; return IDs not in the longest increasing subsequence.
    ...
```

Return `List[str]` (IDs only). Update the `_fmt_misplaced` lambda in `run()`
(~line 6086) to look up `ElementDocInfo` for the ID instead of using tuple
indexing. Note: the current `misplaced()` returns a list of tuples containing
line numbers; the new return type changes to `List[str]`. The formatting in
`run()` must be updated at the same time as this step.

---

## Phase 7 — Remove `seen_element_ids` from `process_document()`

By this point, the old `seen_ids` / `seen_element_ids` accumulation is unused
by all callers (old methods not yet deleted, but not called from main paths).

### Step 7.1 — Remove `seen_ids` parameter and return value from `process_document()` (line 2671)

- Remove `seen_ids` parameter.
- Remove `seen_element_ids: set` from `DocState` (line 4926/4936).
- Remove all reads/writes to `_doc_state.seen_element_ids` inside the function.
- Remove the `return _doc_state.seen_element_ids` at line 2805 (make it return `None`).

Check: at this point only the dead methods (`_rewrite_document_file()`,
`_process_document_files()`) still reference `seen_ids` — they will be removed
in Phase 8. If needed, stub out their `seen_ids` usage temporarily to keep
the code syntactically valid until removal.

### Step 7.2 — Remove `seen_ids` parameter from `_process_document_file()`

Remove the `existing_ids` parameter as well, since by now `update_documents()`
passes the pre-scanned set through a local variable rather than via this
parameter (it can call `process_document()` directly with the set, or keep
using `existing_ids` — clean this up as makes sense).

---

## Phase 8 — Remove Dead Methods

By this point, all old methods have no callers from production paths.
Verify with `grep` before each deletion.

### Step 8.1 — Remove `check_element_coverage()` (line 1608)

No callers remain after Phase 5.1.

### Step 8.2 — Remove `_collect_document_element_ids()` (line 1103)

No callers remain after Phase 4.5 (`update_documents()` uses
`element_doc_info.keys()` from its internal scan pass instead).

### Step 8.3 — Remove `_scan_document_elements()` (line 2128)

No callers remain after Phase 6.

### Step 8.4 — Remove `_scan_doc_stats()` and `doc_files_stats()` (lines 2047, 2110)

No callers remain (replaced by `DocPassStats` + derivable counts).

### Step 8.5 — Remove `_process_document_files()` (line 1615)

No callers remain after Phase 5.4.

### Step 8.6 — Remove `_rewrite_document_file()` (line 1629)

No callers remain after Phase 5.1 and 5.2.

---

## Phase 9 — CLI Cleanup in `run()`

### Step 9.1 — Remove `--missing` and `--orphans` from argument parser and `ANALYSIS_FLAGS`

- Remove `'missing'` and `'orphans'` from `ANALYSIS_FLAGS` (line 92).
- Remove `--missing` and `--orphans` from the `argparse` argument definitions.
- Remove the `args.missing` and `args.orphans` handling blocks in the
  `_has_analysis` section (~lines 6065–6082).
- These conditions are now always reported as errors during any pass via
  `_post_pass_checks()` (missing) and immediate `self.error()` calls (orphans).

### Step 9.2 — Split `--leaves` and `--packages` into an early-exit path

`--leaves` and `--packages` are LTAC-only — they do not need document processing.
Split them out of the `_has_analysis` early-exit block into their own
early-return path before the document processing section. They should not
trigger `scan_documents()` or any document pass.

Update `ANALYSIS_FLAGS` to remove `'leaves'` and `'packages'` if they are
no longer treated as document-analysis flags.

### Step 9.3 — Wire `--read-only` to `scan_documents()`

The `_scan_docs()` local function was removed in Step 5.5. Verify the
`args.read_only` block now calls `case.scan_documents()` directly and that
the `--validate` block does too. No additional change needed if 5.5 was done
correctly.

### Step 9.4 — Wire `clear_errors()` into `run()`

Add `case.clear_errors()` (or equivalent reset) near the start of `run()`
after the `Case` instance is loaded, so each CLI invocation starts clean.

### Step 9.5 — Update API docstring block (~line 5345)

- Remove `check_element_coverage(seen_element_ids)` entry.
- Add entries for `scan_documents()`, `update_documents()`,
  `stdout_documents()`, `element_doc_info`, `element_doc_order`,
  `doc_pass_stats`, `important_leaves`.
- Update `--help` / usage text to reflect removed flags.

---

## Phase 10 — Test Updates (`tests/run_tests.py`)

### Step 10.1 — Remove `--missing` flag tests

Remove or rework tests that pass `--missing` as a CLI flag (~lines 2426–2465,
3126–3129, 3185–3221). The underlying condition (missing elements) is still
tested — these tests should become assertions that the error appears on stderr
during a default update pass, not that `--missing` produces specific stdout.

Key tests to rework:
- `test_missing_analysis_lists_missing_elements` → assert stderr contains error after default update
- `test_missing_analysis_none_when_all_present` → assert no stderr error after default update
- `test_missing_analysis_does_not_modify_files` → verify via default `--read-only` pass
- `test_missing_is_readonly` → remove (flag gone)

### Step 10.2 — Remove `--orphans` flag tests

Remove or rework tests using `--orphans` (~lines 2495–2507, 3136–3139).
Orphan errors now appear on stderr immediately during any pass.

### Step 10.3 — Remove illegal-combination tests for removed flags

Remove tests that assert `--missing`/`--orphans` + `--fixmissing` is an error
(~lines 2607–2613, 3185–3187, 3220–3221) since those flags no longer exist.

### Step 10.4 — Add tests for new automatic error reporting

- Test that a missing element error appears on stderr during default update.
- Test that an orphan element error appears on stderr during default update.
- Test that important-leaf-with-no-prose warning appears after any pass.

### Step 10.5 — Add tests for new public API methods

- `scan_documents()` populates `element_doc_info` without modifying files.
- `update_documents()` populates `element_doc_info` and rewrites files.
- `element_doc_info` is `None` before any pass; `{}` or populated after.
- `important_leaves` is populated after LTAC load (not None).
- `suppressed_reporting()` suppresses stderr but still sets `had_error`.
- `clear_errors()` resets `had_error`.

### Step 10.6 — Update `--misplaced` output format tests

`misplaced()` now returns `List[str]` (IDs) instead of a list of tuples.
Any tests asserting on the exact format of `--misplaced` output will need
updating to match the new `_fmt_misplaced` logic in `run()`.

---

## Sequencing Notes

- **Phases 1–2** are purely additive; do them first and run the full test suite.
- **Phase 3** (extending `process_document()`) is the highest-risk step — it
  touches the core rendering function. Do it in the sub-steps listed and run
  tests after each sub-step.
- **Phase 4** adds orchestrators with no callers — safe at any point after Phase 3.
- **Phase 5** is the first time behaviour changes for existing callers. Run the
  full test suite after each step in Phase 5.
- **Phases 6–8** are cleanups; each should be followed by a full test run.
- **Phase 9** changes CLI behaviour; do it only after Phase 6 confirms analysis
  functions work from `element_doc_info`.
- **Phase 10** should be done alongside or immediately after Phase 9.
- The `--rename` renames-in-documents feature (passing `renames` dict down to
  `process_document()`) is structurally ready after Step 3.1 and Step 4.1.
  The mutation wiring in `run()` (building the renames dict and passing it to
  `update_documents()`) can be done in Phase 9 as part of CLI cleanup, or
  deferred to a follow-on task.
