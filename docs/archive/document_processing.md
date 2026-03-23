# Document Processing Redesign

## Background

This document records the planned redesign of document processing in `verocase.py`,
capturing decisions made, current state, and open issues.

---

## Current State

### File Discovery and Loading

- `Case.load()` is the entry point — finds LTAC file, config, and document files
  (`.md`, `.html`).
- Document files are processed in order; element IDs are accumulated across files
  into a shared `seen` set.

### Processing Paths (currently separate and divergent)

There are currently **four separate document scanning implementations**, all
re-parsing the same files with slightly different goals:

| Function | Purpose | Creates output? |
|---|---|---|
| `_collect_document_element_ids(path)` | Fast pre-scan: collect existing element IDs (used by `--fixmissing`) | No |
| `_scan_doc_stats(path)` / `doc_files_stats()` | Count regions, empty regions, config stmts | No |
| `_scan_document_elements()` | Full scan: ordered IDs + `has_prose` per element (used by `--missing`, `--empty`, `--orphans`, `--misplaced`, `--stats`) | No |
| `_fix_misplaced_document()` | Inline scan for region bounds (used by `--fixmisplaced`) | Yes (temp file) |
| `process_document(f, out, ...)` | Full rendering pass (used by update, fixmissing, stdout) | Yes (writes to `out`) |

The update path (`_rewrite_document_file` → `process_document`) and the scan
paths (`_scan_document_elements`, etc.) are entirely separate code, computing
overlapping information in different ways. This is a source of potential
divergence bugs over time.

### Per-Element Information Currently Tracked

`_scan_document_elements()` returns a `(ordered_ids, id_info)` tuple where
`id_info` maps identifier → `{'has_prose': bool, 'filepath': str, 'lineno': int}`.
This is **not stored on the `Case` instance** — it is recomputed from scratch
every time any analysis function is called.

### Error Reporting

`error()`, `warn()`, `panic()`, `notify()` always print to `self.stderr`.
There is no mechanism to suppress output while still tracking whether errors
occurred. This causes problems for operations like `--start` that operate on
newly created files where some normally-erroneous conditions are expected.

### Operations and Their Code Paths

| Operation | Code Path |
|---|---|
| Default update | `update_files()` → `_rewrite_document_file()` → `process_document()` |
| `--fixmissing` / `--start` | `fixmissing()` → `_rewrite_document_file(add_missing=True)` → `process_document()` |
| `--fixmisplaced` | `fix_misplaced_documents()` → `_fix_misplaced_document()` (own scan + own rewrite) |
| `--stdout` | `_process_document_files()` → `process_document()` |
| `--missing` | `missing()` → `_scan_document_elements()` |
| `--empty` | `empty()` → `_scan_document_elements()` |
| `--orphans` | `orphans()` → `_scan_document_elements()` |
| `--misplaced` | `misplaced()` → `_scan_document_elements()` |
| `--stats` (doc portion) | `doc_files_stats()` → `_scan_doc_stats()` per file |

---

## Planned Redesign

### Principle: Single Code Path

All document processing — whether updating, writing to stdout, or scanning
without output — runs through a single `_process_document_file()` function.
The only difference is what `out` is:

| Mode | `out` value | Created by |
|---|---|---|
| Update | opened temp file (`tempfile.mkstemp`) | orchestrator (caller) |
| Stdout | `sys.stdout` | orchestrator |
| Scan-only | `_NullWriter()` | orchestrator |

`_NullWriter` is a trivial sink:
```python
class _NullWriter:
    def write(self, s): pass
```

This eliminates divergence: `process_document()` runs identically in all three
cases, including populating `element_doc_info` as a side-effect.

### New Per-File Processing Function

```python
def _process_document_file(self, input_path: str, out,
                            add_missing=False, strip=False,
                            renames: Optional[Dict[str, str]] = None) -> None:
```

- `input_path`: the source document file to read (always on disk)
- `out`: already-opened output sink (temp file, stdout, or NullWriter)
- `renames`: optional old_id → new_id map; when non-empty, any
  `<!-- verocase element OLD_ID -->` marker is rewritten to use the new ID
  in-place during the rendering pass. Zero overhead when empty (the default).
  Only `--rename` passes a non-empty map; all other operations use the default.
- Opens `input_path` for reading (handles encoding, line ending detection)
- Calls `process_document()` to do the rendering (passing `renames` through);
  `process_document()` signature gains `renames: Optional[Dict[str, str]] = None`
- Populates `self.element_doc_info` and `self.doc_pass_stats` directly on
  the `Case` instance as it encounters elements — no return value needed

Note: `input_path` is named explicitly (not just `path`) because callers also
deal with output paths (temp file paths, final destination paths) and the
distinction matters.

Line ending detection (currently reads first 4KB in binary) stays inside
`_process_document_file` since it is inherently tied to reading `input_path`.

### Rich Per-Element Record on `Case`

```python
@dataclass
class ElementDocInfo:
    filepath: str      # document file containing this element region
    start_lineno: int  # 1-based line of <!-- verocase element ID -->
    end_lineno: int    # 1-based last line of full region (including trailing prose)
    has_prose: bool    # region has non-generated content after <!-- end verocase -->
    is_orphan: bool    # present in doc but not in LTAC

@dataclass
class DocPassStats:
    pkg_regions: int   = 0  # count of <!-- verocase package ... --> markers seen
    config_stmts: int  = 0  # count of <!-- verocase-config ... --> directives seen
    # elem_regions and empty_elem_regions are derivable from element_doc_info:
    #   elem_regions       = len(element_doc_info)
    #   empty_elem_regions = sum(1 for e in element_doc_info.values() if not e.has_prose)
```

Stored on `Case`:
```python
self.element_doc_info: Optional[Dict[str, ElementDocInfo]] = None
# None = no pass has run yet; distinct from {} (pass ran, found nothing)
# Reset and repopulated by any document processing pass

self.element_doc_order: Optional[List[Tuple[str, str, int]]] = None
# (ident, filepath, start_lineno) in document order across all files
# None = no pass has run yet
# Reset and repopulated alongside element_doc_info

self.doc_pass_stats: Optional[DocPassStats] = None
# None = no pass has run yet
# Reset and repopulated by any document processing pass

self.important_leaves: Set[str] = set()
# IDs of leaf definition nodes (non-Link, non-Citation, no children,
# no ext_ref) — computed as part of reset_cache() in the same single
# forest walk that builds all_definitions_for, citations, etc.
# Checked at O(1) at report time via `ident in self.important_leaves`.
```

**Populated as we go, including on error paths** — we want to know what was
seen up to the point of failure, which may help debugging. No special handling
needed; just write to `self.element_doc_info` immediately as each element
region is encountered.

**"Covered" means a direct `<!-- verocase element X -->` marker.** Elements
rendered indirectly via a `<!-- verocase package X -->` selector do not count
as covered. The reason: only a direct element marker gives the document a
specific region where element-specific prose can be written; a package
selector produces bulk rendered output with no such space. Consequently, the
existing `seen_element_ids` / `DocState.seen_element_ids` accumulator (which
included package-rendered elements) is no longer needed and will be removed.
`element_doc_info.keys()` is the authoritative set of covered elements.

`has_prose` requires tracking the gap between `<!-- end verocase -->` and the
next marker. This logic currently lives only in `_scan_document_elements()`;
it will be moved into `process_document()` so it works in all modes.

### Orchestrators Remain Thin

Each orchestrator: calls `_reset_doc_processing()`, opens output (temp file,
stdout, or NullWriter), calls `_process_document_file()` per file, handles
temp file cleanup on error, collects `(tmp_path, final_path)` pairs, commits,
then calls `_post_pass_checks()`.

```
update_documents()            ← documents only; LTAC treated as fixed
  _reset_doc_processing()
  for each input_path:
    open temp file → tmp_f
    _process_document_file(input_path, tmp_f, ...)
    on error: cleanup tmp
  commit_updates(pairs)
  _post_pass_checks()

update_files()                ← calls update_documents(), then commits LTAC if ltac_modified

fixmissing()                  ← update_documents(add_missing=True) + _mark_needs_support()

scan_documents()              ← replaces _scan_document_elements, _scan_doc_stats, etc.
  _reset_doc_processing()
  for each input_path:
    _process_document_file(input_path, NullWriter(), ...)
  _post_pass_checks()

stdout_documents()            ← replaces _process_document_files()
  _reset_doc_processing()
  for each input_path:
    _process_document_file(input_path, sys.stdout, ...)
  _post_pass_checks()
```

### Post-Pass Checks: `_post_pass_checks()`

Called by every orchestrator after all files are processed. Reports
conditions that can only be known once the full picture is available:

- **Missing elements:** LTAC definitions not in `element_doc_info` — reported
  as errors with `(use --fixmissing)` hint. Links excluded.
- **Important leaves with no prose:** IDs in `important_leaves` whose
  `element_doc_info` entry has `has_prose=False`.
- **Misplaced elements:** if config `ltac_order=true` or `--misplaced` flag,
  run LIS on `element_doc_order` vs LTAC order and report offenders.

Orphans (`is_orphan=True`) are reported immediately during the pass (at the
line where the unknown ID is encountered), not deferred to `_post_pass_checks()`.

All output from `_post_pass_checks()` goes to `self.stderr`, not stdout —
this applies even when the orchestrator is `stdout_documents()`, which writes
document content to stdout. Errors and warnings are always on stderr.

### `fixmissing()` Simplified

`fixmissing()` collapses to:
1. `update_documents(add_missing=True)` — injects missing element stubs and
   re-renders all regions
2. `_mark_needs_support()` — marks leaf elements lacking assertion status;
   may set `self.ltac_modified = True`
3. If `ltac_modified`, commit the LTAC file explicitly (same step as in
   `update_files()`) — `update_documents()` does not commit the LTAC

Note: `fixmissing()` cannot simply call `update_files(add_missing=True)`
because `update_files()` does not accept `add_missing`. The LTAC commit must
be an explicit step after `_mark_needs_support()`.

No separate document-processing implementation needed; `add_missing` is
already a parameter of `_process_document_file()` → `process_document()`.

### Analysis Functions Simplified

Once `self.element_doc_info` is populated by any pass, analysis functions
become trivial reads from that record — no re-scanning. All return
`List[str]` (element IDs only); callers can look up rich per-element data
in `element_doc_info` for any ID they need:

```python
def missing(self) -> List[str]:   # LTAC definitions not in element_doc_info
def empty(self) -> List[str]:     # element_doc_info entries with has_prose=False
def orphans(self) -> List[str]:   # element_doc_info entries with is_orphan=True
def misplaced(self) -> List[str]: # uses element_doc_order + LTAC order comparison
```

The CLI flags `--missing` and `--orphans` are removed — those conditions are
always reported as errors automatically during any document pass. The methods
remain as internal helpers and for API users.

`check_element_coverage()` no longer needs a `seen_element_ids` parameter;
it reads from `self.element_doc_info`.

### Error Suppression

Add a suppression mechanism so operations like `--start` (which creates files
from scratch) can avoid printing spurious errors for expected conditions, while
still tracking whether errors occurred:

```python
self._suppress_reporting: bool = False
self._suppressed_messages: List[Tuple[str, str]] = []  # ('error'/'warn', msg)

@contextmanager
def suppressed_reporting(self):
    prev = self._suppress_reporting
    self._suppress_reporting = True
    try:
        yield
    finally:
        self._suppress_reporting = prev

def error(self, msg: str) -> None:
    self.had_error = True
    if self._suppress_reporting:
        self._suppressed_messages.append(('error', msg))
    else:
        print(f"verocase: error: {msg}", file=self.stderr)
```

`had_error` is still set even when suppressed — the operation knows something
went wrong. Suppressed messages are collected and can be inspected or replayed
if needed.

### What Gets Removed

| Removed | Replaced by |
|---|---|
| `_collect_document_element_ids(path)` | `element_doc_info` populated by any pass |
| `_scan_doc_stats(path)` / `doc_files_stats()` | `DocPassStats` + derivable counts from `element_doc_info` |
| `_scan_document_elements()` | `scan_documents()` |
| `_process_document_files()` | `stdout_documents()` |
| `_rewrite_document_file()` | per-file temp-file loop inside `update_documents()` |
| Inline scan in `_fix_misplaced_document()` | `element_doc_info` / `element_doc_order` from prior `scan_documents()` |
| `check_element_coverage(seen_element_ids)` | `_post_pass_checks()` reads from `element_doc_info` directly |
| CLI flags `--missing`, `--orphans` | always reported as errors during any pass |

---

### Operation Categories in `run()`

| Category | Needs LTAC | Needs docs | Modifies files |
|---|---|---|---|
| `--leaves`, `--packages` | Yes | No | No |
| `--info`, `--descendants`, `--select` | Yes | No | No |
| `--validate`, `--stdout` | Yes | Yes (read) | No |
| `--read-only` / `scan_documents()` | Yes | Yes (read) | No |
| Default update, `--fixmissing`, `--fixmisplaced` | Yes | Yes | Yes (docs) |
| Mutations (`--rename`, `--restate`, `--detach`, `--move`, `--sync`) | Yes | Yes | Yes (docs + LTAC) |

`--leaves` and `--packages` are early-exit paths in `run()`: load LTAC,
print result, done. No document processing, no `_reset_doc_processing`,
no `_post_pass_checks`. Always fast regardless of document set size.

### Mutations Always Update Documents

After any LTAC mutation, a full `update_files()` pass is forced — the
document files must reflect the new LTAC structure. Before any document
processing, all LTAC-derived values must be recalculated in order:

1. `reset_cache()` — single forest walk that recalculates
   `all_definitions_for`, `citations`, `links`, `link_targets`, and
   `important_leaves` together.

This must complete before any document processing begins, since rendering
and reporting depend on these values being consistent with the new LTAC.

- `--rename` requires passing the rename map to `update_documents()` (and
  down to `_process_document_file()` and `process_document()`), so that
  `<!-- verocase element OLD_ID -->` markers are rewritten to
  `<!-- verocase element NEW_ID -->` in-place during the rendering pass.
- `--restate`, `--detach`, `--move`, `--sync` use a normal update pass
  with no rename map; any side-effects (orphaned markers after `--detach`,
  ordering changes after `--move`) are reported by `_post_pass_checks()`.

`update_documents()` therefore also accepts `renames`:
```python
def update_documents(self, add_missing=False, strip=False,
                     renames: Optional[Dict[str, str]] = None) -> None:
```

---

## On Future Outputs (e.g., SVG)

In the future, in-place updating of the document files might *also*
produce *other* files (SVG files, or files that could be converted
into SVG files).
This wouldn't be a different mode of rewriting the same file.
This would probably involve an additional parameter of the directory to
place these additional files, and shouldn't require massive changes.

---

## Former Open Issues

### 1. `element_doc_info` reset policy

ANSWER:

There needs to be a short method `_reset_doc_processing` that
resets self.element_doc_info and self.element_doc_order.
That way, we can ensure that we reset all relevant values every time
an orchestrator starts up.
This method is called by these orchestrators at the start of each pass:
update_documents(), scan_documents(), stdout_documents()
Note: update_files() calls update_documents() which calls _reset_doc_processing
indirectly; fixmissing() calls update_documents(add_missing=True) similarly.

### 2. `has_prose` tracking in `process_document()`

Currently `process_document()` does not track content after `<!-- end verocase -->`.

This needs to be added. The logic from `_scan_document_elements()` must be
ported in. Edge cases to preserve:
- Blank lines between end marker and next marker do not count as prose
- HTML comment lines do not count as prose
- A `<!-- end verocase -->` with no following content at all → `has_prose=False`

### 3. Fate of `_fix_misplaced_document()` inline scan

`_fix_misplaced_document()` has its own region-bounds scan (tracking
`(start_line, end_line)` per element for physical line manipulation). This is
more detailed than what `element_doc_info` needs to store. Options:
- Keep the inline scan as-is (it's specialized enough to warrant it)
- Add `region_bounds: Dict[str, Tuple[int, int]]` to a per-file scan result
  so `_fix_misplaced_document()` can reuse a shared scan
- Accept that `_fix_misplaced_document()` remains a separate path (it reads
  the whole file into memory rather than streaming, so it's already
  architecturally distinct)

ANSWER: Keep the inline scan and in-memory rewrite on its own path — it is
architecturally distinct (reads the whole file into memory for line
rearrangement) and nothing else needs region-bounds data.

After `fix_misplaced_documents()` commits its rewritten files to disk, it
calls `scan_documents()`. This populates `element_doc_info`,
`element_doc_order`, and triggers all standard post-pass reporting (missing
elements, orphans, etc.) for free, from the actual on-disk state. No tracking
logic needs to be duplicated inside `fix_misplaced_documents()`. The disk
round-trip (write then re-read) is negligible and correct.

**Pass 1 is merged into the regular scan.** `element_doc_order` already
provides the sequence needed for LIS misplacement detection. The only
additional data needed is `end_lineno` — the last line of the full element
region including trailing prose — so `fix_misplaced_documents()` knows the
physical extent of each region for rearrangement. Add `end_lineno: int` to
`ElementDocInfo`; the regular scan already walks past `<!-- end verocase -->`
to track `has_prose`, so recording the last line of that gap costs nothing
extra.

`fix_misplaced_documents(scan_initial_docs=True)` works as follows:

1. If `scan_initial_docs` is `True` (default), call `scan_documents()` first
   to ensure `element_doc_info` reflects the current on-disk state. If
   `scan_initial_docs` is `False`, use the existing `element_doc_info` as-is
   — panic if it is `None`, since there is no data to work with.
2. Run LIS on `element_doc_order` vs LTAC order. If nothing is misplaced,
   stop — files haven't changed, existing `element_doc_info` is still valid.
3. **Pass 2 (only when misplaced found):** read file(s) into memory,
   rearrange using `ElementDocInfo.start_lineno` / `end_lineno` bounds,
   commit to disk.
4. **Pass 3 (only when Pass 2 ran):** call `scan_documents()` to reset and
   repopulate `element_doc_info` from the newly written files, and trigger
   all standard post-pass reporting on the new organisation.

Invariant: after `fix_misplaced_documents()` returns, `element_doc_info`
reflects the current on-disk state and all post-pass reporting has run,
regardless of which path was taken.

### 4. `--stats` display policy

Once `element_doc_info` is always populated by the default update pass, many
analysis results are available for free. Decision needed: which of
`--missing`, `--empty`, `--orphans`, `--misplaced` (or summary counts of
them) should be shown automatically after every update pass vs. only when
explicitly requested? Some options may be dropped entirely in favour of always
showing a summary line.

There's no need for an --orphans flag now, remove it.
Instead, *always* show, as an error, document elements requested via
`<!-- verocase element ... -->` but not
in the LTAC (as determined by a lookup for its ID in all_definitions_for).
What's more, send the output to stderr immediately (with filename and line#)
when reading the line that detects the problem, don't wait until the end.
Of course, the error message can be completely suppressed.
However, if we have errors at all,
we generally want to report errors as soon as we're certain they are errors.

Similarly, let's remove the `--missing` flag.
Instead, *always* show, as an error, document elements that are
defined in the LTAC but never requested via `<!-- verocase element ... -->`.
Don't include Links, those aren't definitions.
Don't report these until all documents are processed, since only then
are you sure about what's missing.
It should note `(use --fixmissing)` on each report to note how to fix it.
This is handled by `_post_pass_checks()`, called by every orchestrator.

Not everyone will want to
put their element definitions in LTAC order.
Let's create a configuration flag
`ltac_order`, default false.
If `ltac_order` is true, or the `--misplaced` flags is sent,
then complain every time elements aren't in LTAC order.
That means we can use `--misplaced` regardless of whether or not
`--read-only` is enabled.

We should always report on every leaf definition node (non-Link,
non-Citation, no children, no `ext_ref`) that has no prose in its document
region. These are tracked via `self.important_leaves` (see issue 7 /
`reset_cache()`) and reported by `_post_pass_checks()`.

The `--empty` situation is interesting.
If `--empty` is provided, or the new configuration option `forbid_empty`
(default false) is true, then report each element that is empty
(has nothing other than blank lines or generated content or HTML comments).
Again, looks like this no longer requires `--read-only`, we just get the
data as we go.

There's still value in the `--read-only` flag, but let's minimize the
number of flags that imply it. In short, make `--read-only` orthogonal
as much as we reasonably can.

`--read-only` routes to `scan_documents()` instead of `update_documents()`.
This means all errors and statistics are still reported (orphans, missing
elements, important leaves, misplaced if configured), but no files are
modified. Many formerly read-only-only flags (`--misplaced`, `--empty`,
`--stats`) now work regardless of `--read-only` since the data is always
available after any pass.

### 5. Error suppression granularity

The proposed `suppressed_reporting()` context manager suppresses all
error/warn output. Is that too coarse? For `--start`, the intent is to suppress
warnings about missing document files and empty case state — not all errors.
Options:
- Suppress by category/tag (e.g., `error('msg', category='no_docs')`)
- Suppress all and rely on the caller to check `_suppressed_messages`
- Keep it coarse for now; refine if a real case for selective suppression
  emerges

Keep it coarse. For --start, we're using internal data, so simply suppressing
is okay for now.

`_suppressed_messages` is cleared at entry to `suppressed_reporting()`, so
each `with case.suppressed_reporting():` block starts clean and the caller
can inspect exactly what was suppressed during that operation after the block
exits. Caveat: nested `suppressed_reporting()` calls would wipe messages
collected by the outer context — this is acceptable since nested suppression
is not expected in practice.

### 6. API exposure

`element_doc_info` and `element_doc_order` will be part of the public `Case`
API. Decide:
- Should `scan_documents()` be public (callable by API users without
  triggering a full update)?
- What guarantees does the API make about when `element_doc_info` is
  populated vs `None`?

Yes, scan_documents() must be public. We generally want to make it possible
for a user to re-implement run() without too much trouble.

The API should guarantee that scan_documents, update_documents, and its
stdio version (stdout_documents), will all reset `element_doc_info` from what it learns from
the document. Warn that the line numbers will be from "what it read" not
"what it wrote" (as those can be different), but that the *sort order*
will be the same. The intent is that API users can *read* from element_doc_info
to learn more info. If the document files change afterwards, then their
values will be out-of-date until another relevant run
(e.g., of scan_documents()).

### 7. `important_leaves` not yet in design section

ANSWER: `important_leaves` is a `Set[str]` stored on `Case`, pre-computed
by `_find_important_leaves()` which walks the LTAC forest once. Definition:
every leaf definition node that is non-Link, non-Citation, has no children,
and has no `ext_ref`. Checking whether a given ID is an important leaf at
report time is then a O(1) set lookup (`ident in self.important_leaves`),
with no repeated LTAC traversal.

`important_leaves` is computed inside `reset_cache()` as part of the same
single forest walk that builds `all_definitions_for`, `citations`, etc. No
separate `_find_important_leaves()` method is needed.

**Chosen approach: Option C** — parser keeps incremental filling for early
error detection; `reset_cache()` is called at end of `_parse_ltac_file()`
and is always the authoritative final state.

**Rationale:** `important_leaves` cannot be determined incrementally (leaf
status is only knowable once the full tree is built), so `reset_cache()` must
be called after parsing regardless. Keeping incremental filling in the parser
preserves early error detection (e.g. duplicate definitions caught with
accurate line numbers). `reset_cache()` overwrites the incremental results
with a clean, consistent computation — it is always the authoritative final
state.

**`recalculate_cache()` expanded** to compute `important_leaves` in the same
single forest walk as `all_definitions_for`, `citations`, `links`,
`link_targets`. It returns all values including `important_leaves`.
`reset_cache()` stores everything `recalculate_cache()` returns.

**Non-incremental fields** — cache fields that cannot be computed
incrementally by the parser — are recorded in a class-level constant:
```python
_NON_INCREMENTAL_CACHE_FIELDS = frozenset({'important_leaves'})
```
Currently only `important_leaves`; future non-incremental fields are added
here without touching call sites.

**`doublecheck_cache()` extended** with a `skip_non_incremental=False`
parameter. When `True`, fields in `_NON_INCREMENTAL_CACHE_FIELDS` are
excluded from the comparison:
```python
def doublecheck_cache(self, skip_non_incremental=False) -> bool:
```

**`recalculate_cache()` is called exactly once per site** — the result is
passed to both `doublecheck_cache()` and `reset_cache()` via their existing
optional `cache` parameter, avoiding redundant tree walks:

```python
# end of _parse_ltac_file():
computed = self.recalculate_cache()
if doublecheck:
    self.doublecheck_cache(cache=computed, skip_non_incremental=True)
self.reset_cache(cache=computed)

# after mutations in run():
computed = self.recalculate_cache()
if doublecheck:
    self.doublecheck_cache(cache=computed)
self.reset_cache(cache=computed)
```

**Two doublecheck moments**, both gated on `--doublecheck`:

1. **Load-time** (inside `_parse_ltac_file()`, after parsing): validates
   that the parser's incremental filling agrees with the full recomputation.
   `skip_non_incremental=True` excludes `important_leaves` since the parser
   never computed it incrementally.

2. **Post-mutation** (end of `run()`): validates mutation code didn't
   introduce inconsistencies. `skip_non_incremental=False` (default) means
   `important_leaves` is fully checked.

**Call sites for `reset_cache()`:**
- End of `_parse_ltac_file()` — always called after full tree is built
- After every LTAC mutation — existing behaviour, unchanged

`important_leaves` is NOT touched by `_reset_doc_processing` — it is purely
LTAC-derived and only changes when the LTAC changes. This keeps the two
concerns cleanly separated.

No `is_important_leaf` field in `ElementDocInfo` — leaf status is a property
of the LTAC node, not the document region. Keeping it as a separate set
avoids inflating `ElementDocInfo` with LTAC-derived data.

### 8. `update_files()` naming and typo

ANSWER: Two distinct methods:

- `update_documents()` — public API method, updates document files only.
  Treats the LTAC as fixed/read-only. Clean building block; named
  consistently with `scan_documents()` and `stdout_documents()`.
- `update_files()` — updates document files AND commits the LTAC file if
  `ltac_modified` is set. Preserves existing combined behaviour. Implemented
  by calling `update_documents()` first, then committing the LTAC file if
  needed.

Also fix the typo `update_docments` → `update_documents` in the API section
(issue 6).

### 9. Pseudocode for `stdout_documents()` is garbled

RESOLVED: the orchestrators pseudocode block in the design section was
corrected — `stdout_documents()` now correctly shows it replaces
`_process_document_files()`.

### 10. "Analysis Functions Simplified" section is partially stale

ANSWER: `missing()` and `orphans()` survive as methods returning `List[str]`
(IDs only — callers use `element_doc_info` for rich data). The CLI flags
`--missing` and `--orphans` are removed; those conditions are always reported
as errors during any document pass. The methods remain for internal use and
for API users.

### 11. `had_error` reset policy

ANSWER: `had_error` is cumulative and not reset by document passes. Add a
`clear_errors()` method that resets `had_error` to `False` and clears
`_suppressed_messages`. `run()` calls this first so each invocation starts
clean. API users can call it explicitly when they want a fresh slate between
operations.

### 12. `_reset_doc_processing` contract not fully specified

ANSWER: `_reset_doc_processing` resets exactly:
- `element_doc_info` → `None`
- `element_doc_order` → `None`
- `doc_pass_stats` → `None`

`None` is the deliberate sentinel meaning "no pass has run". An empty dict
or list would be ambiguous — it could mean a pass ran and found nothing.
These are distinct situations and must have distinct values. Code that
consumes these fields must check for `None` before use.

It does NOT touch:
- `important_leaves` — LTAC-derived, managed by `reset_cache()`
- `had_error` / `_suppressed_messages` — managed by `clear_errors()`

---

## Implementation Guide

This section maps every design decision to specific existing code in `verocase.py`.
Line numbers reference the current state of the file before the redesign is applied.

### New Classes / Dataclasses to Add

These do not exist yet; add near the top of the file (with other dataclasses):

| Name | Description |
|---|---|
| `_NullWriter` | Trivial sink: `def write(self, s): pass`. Used by `scan_documents()` orchestrator. |
| `ElementDocInfo` | Dataclass: `filepath`, `start_lineno`, `end_lineno`, `has_prose`, `is_orphan` |
| `DocPassStats` | Dataclass: `pkg_regions: int = 0`, `config_stmts: int = 0` |

### New Instance Fields on `Case`

Add in `Case.__init__()` (or wherever `had_error` and similar flags are initialised):

```python
self.element_doc_info: Optional[Dict[str, ElementDocInfo]] = None
self.element_doc_order: Optional[List[Tuple[str, str, int]]] = None
self.doc_pass_stats: Optional[DocPassStats] = None
self.important_leaves: Set[str] = set()
self._suppress_reporting: bool = False
self._suppressed_messages: List[Tuple[str, str]] = []
```

### New Class-Level Constant on `Case`

```python
_NON_INCREMENTAL_CACHE_FIELDS = frozenset({'important_leaves'})
```

### New Methods to Add to `Case`

| Method | Notes |
|---|---|
| `_process_document_file(input_path, out, add_missing, strip, renames)` | Core per-file processor; calls `process_document()`; populates `element_doc_info` etc. |
| `update_documents(add_missing, strip, renames)` | Orchestrator for temp-file update pass; calls `_reset_doc_processing()` first |
| `scan_documents()` | Orchestrator for NullWriter scan pass; calls `_reset_doc_processing()` first |
| `stdout_documents()` | Orchestrator for stdout pass; replaces `_process_document_files()` |
| `_post_pass_checks()` | Reports missing elements, important leaves with no prose, misplaced (if configured) |
| `_reset_doc_processing()` | Sets `element_doc_info`, `element_doc_order`, `doc_pass_stats` all to `None` |
| `clear_errors()` | Resets `had_error = False` and clears `_suppressed_messages`; called by `run()` at start |
| `suppressed_reporting()` | Context manager; sets `_suppress_reporting = True`, clears `_suppressed_messages` at entry |

### Existing Methods: Modified

| Method | Line | Change |
|---|---|---|
| `load_ltac_string()` | 811 | **Add `reset_cache()` call at end** — same as `_parse_ltac_file()`. Currently does not call it, so `important_leaves` and other cache fields would be stale after calling this entry point. |
| `_parse_ltac_file()` | 961 | Add `reset_cache()` call at end (likely already present for other cache fields; verify `important_leaves` is included after `recalculate_cache()` is extended). |
| `recalculate_cache()` | 1150 | **Add `important_leaves` computation** to the same forest walk that computes `all_definitions_for`, `citations`, `links`, `link_targets`. Return `important_leaves` in the returned dict. |
| `doublecheck_cache()` | 1211 | **Add `skip_non_incremental=False` parameter.** When `True`, skip fields in `_NON_INCREMENTAL_CACHE_FIELDS` during comparison. |
| `reset_cache()` | 1243 | **Store `important_leaves`** from the dict returned by `recalculate_cache()`. |
| `update_files()` | 1950 | **Reimplement** to call `update_documents()` first, then commit LTAC if `ltac_modified`. The existing per-file loop and `_rewrite_document_file()` call are replaced. |
| `fix_misplaced_documents()` | 1701 | **Add `scan_initial_docs=True` parameter.** Implement 3-pass flow: Pass 1 = call `scan_documents()` (or use existing `element_doc_info`), Pass 2 = rearrange (only if misplaced), Pass 3 = `scan_documents()` (only if Pass 2 ran). The existing inline scan is kept for bounds tracking; `ElementDocInfo.start_lineno` / `end_lineno` supply the line extents. |
| `process_document()` | 2671 | **Remove `seen_ids` parameter and return value** (currently returns `_doc_state.seen_element_ids` at line 2805). **Add `renames` parameter.** **Add `has_prose` tracking** (port logic from `_scan_document_elements()`). **Populate `self.element_doc_info`, `self.element_doc_order`, `self.doc_pass_stats` directly** on `Case` as a side-effect instead of returning data. |
| `missing()` | 2207 | **Simplify**: read from `element_doc_info`; return `List[str]` (IDs only). Currently calls `_scan_document_elements()`. |
| `empty()` | 2216 | **Simplify**: read from `element_doc_info` (entries with `has_prose=False`); return `List[str]`. |
| `orphans()` | 2226 | **Simplify**: read from `element_doc_info` (entries with `is_orphan=True`); return `List[str]`. |
| `misplaced()` | 2232 | **Simplify**: read from `element_doc_order`; return `List[str]`. Currently calls `_scan_document_elements()`. |
| `error()` | (search for `def error`) | **Add suppression check**: if `_suppress_reporting`, append to `_suppressed_messages` and return; otherwise print as before. `had_error = True` always. |
| API docstring block | ~5345 | Update to remove `check_element_coverage(seen_element_ids)` entry; add new public methods. |

### Existing Methods: Removed

| Method | Line | Replacement |
|---|---|---|
| `_collect_document_element_ids()` | 1103 | `element_doc_info` populated by any pass |
| `check_element_coverage()` | 1608 | `_post_pass_checks()` reads `element_doc_info` directly |
| `_process_document_files()` | 1615 | `stdout_documents()` |
| `_rewrite_document_file()` | 1629 | per-file temp-file loop inside `update_documents()` |
| `fixmissing()` | 1724 | Replaced by `update_documents(add_missing=True)` + `_mark_needs_support()` + explicit LTAC commit |
| `_scan_doc_stats()` | 2047 | `DocPassStats` + derivable counts from `element_doc_info` |
| `doc_files_stats()` | 2110 | `DocPassStats` + derivable counts from `element_doc_info` |
| `_scan_document_elements()` | 2128 | `scan_documents()` |
| `_scan_docs()` (local fn in `run()`) | 6120 | `scan_documents()` — this is a nested local function inside `run()`, not a `Case` method; delete it and replace the two call sites at ~6132 and ~6152 |

### `DocState` Changes

`DocState` is defined at line 4909. It has a `seen_element_ids: set` field (line 4926 / 4936)
used by `process_document()` (lines 2614, 2624, 2692, 2703, 2705) and returned at line 2805.

- **Remove `seen_element_ids` from `DocState`** — no longer needed once `process_document()`
  populates `self.element_doc_info` directly.
- Any `add_missing` logic that reads `seen_element_ids` to determine which elements are
  already present must instead read `self.element_doc_info.keys()`.

### `_parse_ltac_file()` / `load_ltac_string()` — `reset_cache()` Call Sites

Both methods parse LTAC into the `Case` instance. Both must call `reset_cache()` at the
end so that `important_leaves` (and all other cache fields) reflect the newly loaded tree:

- `_parse_ltac_file()` — line 961 — **add/verify `reset_cache()` call at end**
- `load_ltac_string()` — line 811 — **add `reset_cache()` call at end** (currently absent)

The pattern is:
```python
computed = self.recalculate_cache()
if doublecheck:
    self.doublecheck_cache(cache=computed, skip_non_incremental=True)
self.reset_cache(cache=computed)
```

### CLI Flags Removed

The following CLI flags are removed from `run()` argument parsing and help text:

| Flag | Reason |
|---|---|
| `--missing` | Always reported as errors by `_post_pass_checks()` after any pass |
| `--orphans` | Always reported as errors immediately during the pass |

The analysis methods `missing()` and `orphans()` remain on `Case` for API use.

The `--read-only` flag routes to `scan_documents()` instead of a read-only variant of
`update_documents()`. Many formerly read-only-only flags (`--misplaced`, `--empty`, `--stats`)
now work regardless of `--read-only` since the data is populated after every pass.

### Tests That Need Updating (`tests/run_tests.py`)

The test suite uses `--missing` and `--orphans` flags extensively. Searches for those
strings in `run_tests.py` show many test methods that will need to be revised:

- Tests using `--missing` as a standalone flag (~lines 2426–2465, 3126–3129, 3185–3221)
  must be updated — the flag no longer exists; missing-element errors now appear on stderr
  automatically during the default update pass.
- Tests using `--orphans` as a standalone flag (~lines 2495–2507, 3136–3139)
  must be updated similarly.
- Tests combining `--missing`/`--orphans` with `--fixmissing` as invalid combinations
  (~lines 2607–2613, 3185–3187) must be removed or reworked.
- `test_analysis_blocked_with_fixmissing` and similar flag-combination tests will need
  rethinking once the flags are removed.

`tests/normalise_fixtures.py` does not reference these methods directly; it should
need minimal changes.

### Summary: Where `element_doc_info` Is Authoritative

After any call to `update_documents()`, `scan_documents()`, or `stdout_documents()`:

- `element_doc_info` is a `Dict[str, ElementDocInfo]` (never `None`; `{}` if nothing found)
- `element_doc_order` is a `List[Tuple[str, str, int]]` (never `None`; `[]` if nothing found)
- `doc_pass_stats` is a `DocPassStats` instance (never `None`)
- Before any of these orchestrators is called, all three fields are `None`

`important_leaves` is separately managed by `reset_cache()` and is `set()` (empty, not
`None`) before the first `reset_cache()` call.
