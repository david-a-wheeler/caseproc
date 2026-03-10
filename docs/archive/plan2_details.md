# Plan 2 — Detailed Implementation Plan

See docs/plan2.md for the high-level design.
This file breaks the work into reviewable stages.

---

## Stage A — Config & Discovery

**Goal:** Auto-discover the config file, support new config keys
(`ltac_file`, `content_files`, `update_headers`), and rename the old
`update` key.

### A.1 `DEFAULT_CONFIG` changes
- Rename `'update': False` → `'update_headers': True`
- Add `'ltac_file': ''`
- Add `'content_files': []`

### A.2 `load_config` changes
- Accept the three new keys (`ltac_file`, `content_files`, `update_headers`)
- Remove acceptance of the old `update` key (warn if seen)

### A.3 Config auto-discovery in `main()`
- Before calling `load_config`, if `--config` was not given:
  - Try `case.config`; if it exists, use it
  - Else try `docs/case.config`; if it exists, use it
  - Else pass `None` to `load_config` (defaults only)
- Load config before loading the LTAC file

### A.4 `find_ltac_file` gains a `config` parameter
- Signature: `find_ltac_file(ltac_arg, config)`
- If `ltac_arg` is given, use it (command line wins)
- Else if `config['ltac_file']` is non-empty, use that
- Else auto-discover `case.ltac` / `docs/case.ltac` as before
- Panic with explanation if nothing is found

### A.5 Content file resolution in `main()`
Priority order (highest first):
1. Command-line positional `files` (if any)
2. `config['content_files']` (if non-empty list)
3. Auto-discover: try `case.md`, `case.html`, `docs/case.md`,
   `docs/case.html` in that order; use first found
4. Panic with explanation listing all four paths that were tried

### A.6 `process_document_stream` key rename
- Change `config.get('update', False)` → `config.get('update_headers', True)`

### A.7 Test updates
- Existing tests that set `"update": true` in fixture configs need
  updating to `"update_headers": true`
- Add a test that verifies `update_headers` defaults to `True`
- Add a test that verifies config auto-discovery finds `case.config`

---

## Stage B — CLI Mode Overhaul

**Goal:** Make inline-rewrite the default; add `--stdout`; auto-discover
content files; stub new `--update`.

### B.1 Argparse changes
- Remove `--inline` / `-i` from the mutually exclusive mode group
- Add `--stdout` to the mode group (sends processed content to stdout)
- Change `--update` help text to describe new LTAC-update meaning
  (implementation stubbed: print "LTAC update not yet implemented")

### B.2 `main()` dispatch logic
- Default (no mode flag): inline-rewrite all content files
- `--stdout`: stream processed content to stdout (former filter default)
- `--validate`: unchanged
- `--select`: unchanged
- `--selftest`: unchanged

### B.3 Content file fallback in default and `--stdout` modes
- Apply the A.5 priority order when determining which files to process
- If no files can be found, panic with an explanation listing the
  four auto-discovery candidates

### B.4 Test updates
- Update all tests that previously relied on no-mode (filter) default
- Add tests for `--stdout`

---

## Stage C — LTAC Syntax Cleanup

**Goal:** Remove `//` comment support and `*` bullet support.

### C.1 Regex change
- `_LTAC_LINE_RE`: change `[-*]` → `[-]`

### C.2 Parser change
- `_parse_line`: remove the `stripped.startswith('//')` branch
- Blank lines still finalize the current package (unchanged)

### C.3 Tests
- Add tests confirming that `//` lines and `*` bullets now produce
  "unrecognized syntax" errors

---

## Stage D — Stable Anchors

**Goal:** Insert stable `<a id="type-id">` anchors before component
headers; strip stale ones; use type+ID-only fragments in hyperlinks.

### D.1 New helper: `_component_anchor_id(type_str, ident)`
- Returns `to_github_fragment(f"{type_str} {ident}")` (no statement text)
- Example: `"Claim"`, `"C1"` → `"claim-c1"`

### D.2 Change `_node_anchor_url` for declared nodes
- Use `f"{node.node_type} {node.identifier}"` (no `node.text`) when
  building the fragment for declared nodes
- Cited nodes continue to link to the package header (unchanged)
- This makes mermaid and LTAC hyperlinks stable across statement changes

### D.3 Anchor strip + insert in `process_document_stream`
- Track a `_pending_anchor_strip` flag: when the previous line(s) were
  `<a id="CASE_TYPE-..."></a>` where CASE_TYPE matches a known component
  type prefix, suppress them from output
- When a matching Markdown/HTML header is found, emit
  `<a id="{_component_anchor_id(type_str, ident)}"></a>` immediately
  before the header line
- Idempotent by design: old anchors are stripped before new ones are
  inserted

### D.4 Update expected test outputs
- All fixture expected outputs that contain mermaid/LTAC click URLs
  need updating (statement no longer in fragment)
- Add a test that runs the processor twice and confirms identical output

---

## Stage E — Backup System + LTAC Writer

**Goal:** Safe atomic multi-file replacement; LTAC serializer.

### E.1 `save_with_backup(path, new_content)`
- Write `new_content` to a temp file in the same directory
- Collect (temp_path, final_path) pairs — do NOT move yet

### E.2 `commit_updates(pairs)`
- Takes list of `(tmp_path, final_path)` pairs
- Print to stderr: `"caseproc: Updating FILENAMES"` (all final paths listed)
- Move each `final_path` → `.backup/{basename}` (create `.backup/` if needed)
- Move each `tmp_path` → `final_path`
- This minimizes the window where files are partially updated

### E.3 Refactor `_inline_rewrite_file`
- Collect `(tmp, path)` pair instead of calling `os.replace` directly
- Caller accumulates pairs and calls `commit_updates` once at the end

### E.4 `write_ltac(roots) -> str`
- Serializes the node forest back to LTAC text
- One package per block, separated by blank lines
- Packages in their original order
- Uses only `-` bullets; two-space indentation per depth level
- Format per line:
  `{indent}- {NodeType}[ ^[pkg]?][ ID][ : text][ (ref)][ {opts}]`

### E.5 Tests
- Round-trip test: parse simple.ltac → write_ltac → re-parse → compare
  id_info and roots structure
- Test that `commit_updates` creates `.backup/` and moves files correctly

---

## Stage F — `--update` (Sync LTAC Citations)

**Goal:** Implement `--update` to sync citation/link statements to their
canonical declaration.

### F.1 Warning without `--update`
- In `LTACParser._attach_node`, when a citation/link has a statement
  differing from the canonical one, warn with:
  "To update LTAC statements to match their declarations, use `--update`."

### F.2 `apply_ltac_update(roots, id_info)`
- Walk all nodes; for any cited or Link node with `.text` set that
  differs from `id_info[ident]['statement']`, update `.text` to the
  canonical statement
- Return count of changes made

### F.3 `main()` when `--update` given
- Load and validate LTAC
- Call `apply_ltac_update`; if count > 0, write LTAC via Stage E machinery
- Then proceed to process content files (so they are also updated)

### F.4 Tests
- Test that `--update` rewrites differing citation statements
- Test that without `--update`, the warning is shown instead

---

## Stage G — `--rename` and `--restate`

**Goal:** Ordered mixed LTAC mutation operations.

### G.1 Custom argparse action `_MutationAction`
- Shared destination list `args.mutations`
- `--rename OLD NEW` appends `('rename', old, new)`
- `--restate LABEL STATEMENT` appends `('restate', label, stmt)`
- Both use `nargs` of 2

### G.2 `apply_rename(roots, registry, id_info, old, new)`
- Validate: `old` declared, `new` not declared — panic on failure
- Rename identifier everywhere: Node fields, registry keys, id_info keys,
  parent/child references, link targets
- Returns nothing (mutates in place)

### G.3 `apply_restate(roots, registry, id_info, label, stmt)`
- Validate: `label` declared — panic on failure
- Update `.text` on all nodes with that identifier
- Update `id_info[label]['statement']`

### G.4 `main()` with mutations
- Validate LTAC first (panic on corruption)
- Apply mutations in order from `args.mutations`; each step sees the
  state left by the previous one
- Re-validate after all mutations
- Collect temp files for LTAC + all content files
- Call `commit_updates` once with all pairs

### G.5 Content doc updates after rename/restate
- After mutations, run `process_document_stream` on each content file
- The renamed/restated data is already in `registry`/`id_info`, so
  headers and anchor regions are updated automatically

### G.6 Tests
- Test single rename
- Test single restate
- Test interleaved rename+restate
- Stress test: swap two labels via intermediary
- Test that failure (bad OLD) leaves all files unchanged
