# Plan 4

Let's make a few small additions to make it easier for people to
get started.

---

## Stage 1: `warning` selector

Add a new selector `warning` that always generates this fixed text
inside its region (no ID or `*` parameter; treat any parameter as an error):

~~~~
<!-- WARNING: DO NOT EDIT text within caseproc SELECTOR ... end caseproc. -->
<!-- Those regions are regenerated. -->
~~~~

So a document with this region:

~~~~
<!-- caseproc warning -->
<!-- end caseproc -->
~~~~

will be rendered as:

~~~~
<!-- caseproc warning -->
<!-- WARNING: DO NOT EDIT text within caseproc SELECTOR ... end caseproc. -->
<!-- Those regions are regenerated. -->
<!-- end caseproc -->
~~~~

Implementation notes:
- Add `'warning'` to `_VALID_DISPLAY_TYPES`.
- Add a `render_warning()` function that returns the two-line string.
- Dispatch from `render_selector` when `display_type == 'warning'`.
- If an element_id is present (non-None), call `error()` explaining that
  `warning` takes no parameters.
- The output is the same for both markdown and HTML doc formats.

---

## Stage 2: Redesign `--missing` to single-pass re-render + inject

**Current behaviour (two passes, to be replaced):**

1. Scan pass: call `process_document_stream` with output discarded
   (`io.StringIO()`) to collect `seen_element_ids`.
2. Append pass: call `_add_missing_elements` to append stub regions to the
   last document file.
3. Call `_mark_needs_support` on the LTAC.

**Problem:** because the scan pass discards output, the `warning` and
`package *` regions in the document are *not* re-rendered.  The document
accumulates stale region content.

**New behaviour (single pass):**

`--missing` calls `_process_files` the same way default mode does, so all
existing regions are re-rendered.  Then, instead of a separate append step,
missing element regions are injected at the natural end point of each
document by `process_document_stream` itself.

### Changes to `process_document_stream`

Add a parameter `add_missing: bool = False`.

When `add_missing=True`:

- Before writing each line, check whether it matches `</body>` (case-insensitive,
  stripped).  If it does, inject missing element regions immediately before
  that line, then write `</body>`.  Set a flag so this injection only
  happens once per stream.  ("No more element context will occur after
  `</body>`.")
- After the loop ends (EOF), if the `</body>` injection has not already
  fired, inject missing element regions at that point.

The injection logic:

```python
all_ids_in_order = [n.identifier for n in _all_nodes(all_roots)
                    if not n.is_cited and n.identifier]
missing_ids = [i for i in all_ids_in_order
               if i not in _doc_state.seen_element_ids]
```

For each missing ID, emit:

```
<!-- caseproc element ID -->
{rendered element block}
<!-- end caseproc -->
```

Use `render_element_selector(ident, registry, [], id_info, config, state)`
(pass `[]` for `all_roots` so cross-reference sub-sections are empty in
the stub — the user hasn't placed these elements yet).

### Changes to `_process_files`

Pass `add_missing` through to `process_document_stream`.

### Changes to the `--missing` branch in `main()`

Replace the entire two-pass block with a single call to `_process_files`
with `add_missing=True`, followed by `_mark_needs_support`.

The `doc_text_cache` and separate `_add_missing_elements` call are removed.

The `empty_ids` logic (marking `needsSupport` on elements that exist but
have no user content) can be preserved: after the `_process_files` call,
read the newly written files and run `_has_user_content` as before.  Or,
for simplicity, mark `needsSupport` only on `missing_ids` (the IDs that
had no `element` selector at all).  Keep the simpler version for now —
it is easy to restore the `empty_ids` path later if needed.

### `_add_missing_elements` function

This helper becomes unused once `process_document_stream` handles injection
inline.  Remove it.

### `_check_element_coverage`

Still called by default mode, validate, and stdout to produce warnings.
Not called by `--missing` or `--start` (they inject instead of warning).

---

## Stage 3: Add `case.markdown` to auto-discovery

The plan says: "While `.markdown` is less common, if `case.markdown` *does*
exist, we don't want to go any further."  For consistency, add
`case.markdown` and `docs/case.markdown` to every place that enumerates
auto-discovered document files:

- The candidate list in `main()` (currently `'case.md', 'case.html',
  'docs/case.md', 'docs/case.html'`).
- `_NO_FILES_MSG`.
- The `--start` existence-check list (see Stage 4).
- The `--help` text in `parse_args`.

---

## Stage 4: `--start` option

### What it does

1. Checks that no existing case file is present (panics on the first one
   found).  The list to check:
   `case.ltac`, `docs/case.ltac`,
   `case.md`, `case.markdown`, `case.html`,
   `docs/case.md`, `docs/case.markdown`, `docs/case.html`.
2. Writes `case.ltac` with the pre-canned stub:

   ~~~~
   - Claim Top: Top level claim
     - Claim G2: G2 is true
     - Claim G3: G3 is true
   ~~~~

3. Writes `case.md` with the pre-canned stub:

   ~~~~
   # Stub Assurance Case

   This is a sample assurance case for you to edit.

   <!-- caseproc warning -->
   <!-- end caseproc -->

   ## Packages

   <!-- caseproc package * -->
   <!-- end caseproc -->

   ## Elements
   ~~~~

4. Falls through to the normal LTAC loading and validation (which finds the
   just-written `case.ltac`).
5. Dispatches to the same `--missing` code path (re-render + inject missing
   + mark `needsSupport`).

With the stub LTAC above, the expected final state after `--start`:
- `case.md`: `warning` region filled in, `package *` region shows the
  SACM/GSN diagram with G2 and G3 marked `{needsSupport}`, and three
  `element` regions appended under `## Elements` for `Top`, `G2`, `G3`.
- `case.ltac`: G2 and G3 have `{needsSupport}`; Top is unchanged (it has
  children).

### Why `--start` must be dispatched before `find_ltac_file()`

`main()` unconditionally calls `find_ltac_file()` on line ~2649 before
branching to any mode flag.  `find_ltac_file()` calls `panic()` and exits
if no LTAC file is found.  Since `--start` creates `case.ltac`, calling
`find_ltac_file()` before `--start` has had a chance to write the file
would always panic.

Only `--selftest` currently escapes this: it is dispatched via an early
`return` before `find_ltac_file()` is reached.

**Implementation:**  After the `if args.selftest: …` early-return block,
add a parallel early block for `--start`:

```python
if args.start:
    _check_no_existing_case_files()   # panic if any exist
    _write_start_stubs()              # write case.ltac and case.md
    # Do NOT return here; fall through to the normal LTAC loading below.
    # find_ltac_file() will now find the case.ltac we just wrote.
```

After the early `--start` stub-writing, execution continues through the
normal `find_ltac_file()` / `load_ltac_file()` / validation block.  The
mode dispatch at the bottom then treats `args.start` the same as
`args.missing`:

```python
elif args.missing or args.start:
    # single-pass re-render + inject + needsSupport
```

### Adding `--start` to the mode exclusive group

Add `--start` to the existing `mode = parser.add_mutually_exclusive_group()`
in `parse_args`, so it cannot be combined with `--validate`, `--select`,
`--missing`, etc.

---

## Stage 5: Tests

### `warning` selector test

Add a test (probably in a new `TestWarningSelector` class) that:
- Runs `--select warning` and checks stdout contains both warning lines.
- Runs `--select 'warning C1'` (with an ID) and checks that an error is
  reported.

Also add a fixture test: a document with `<!-- caseproc warning -->` region
containing stale content; after processing, the region contains the two
warning lines.

### `--missing` re-render tests

Update `TestMissingOption`:
- Verify that existing `package *` and `warning` regions in the document
  are re-rendered (not left stale) when `--missing` is used.
- The `test_missing_adds_element_regions` test should still pass without
  structural changes, but confirm the output file is fully rendered.

### `--start` tests

Run in a temporary subdirectory of `tests/` (never in the top-level
project directory, which may eventually contain a real `case.ltac`).

Two tests:
1. **Happy path**: create a fresh temp dir, run `caseproc --start` in it,
   verify `case.ltac` and `case.md` exist and contain expected content
   (warning filled, package diagram present, three element regions appended,
   G2/G3 have `{needsSupport}` in the LTAC).
2. **Re-run fails**: run `caseproc --start` a second time in the same temp
   dir; verify it exits non-zero and prints an error naming the existing
   file.
