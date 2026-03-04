# Implementation Plan for caseproc

This plan implements `caseproc` incrementally. After each step the result is
reviewed before proceeding. The design spec is `docs/design-spec.md`.

All code lives in a single executable file `caseproc` at the project root.
Tests live under `tests/`; test input fixtures under `tests/fixtures/`.

---

## Step 1: Initial script skeleton

Create `caseproc` as an executable Python 3 script.

**File: `caseproc`**

- Shebang: `#!/usr/bin/env python3`
- Module docstring describing the script.
- Imports: `sys` only (nothing else yet).
- `main()` function that prints `"caseproc: not yet implemented"` and returns.
- Standard `if __name__ == '__main__': main()` guard at the bottom.
- Run `chmod +x caseproc` to make it executable.

### 1b: Error reporting functions

Add a module-level error flag and three reporting functions (all that is needed
is `sys`, already imported):

```python
_had_error = False

def warn(msg: str) -> None:
    """Print a warning to stderr. Does not set the error flag."""
    print(f"caseproc: warning: {msg}", file=sys.stderr)

def error(msg: str) -> None:
    """Print an error to stderr and set the error flag."""
    global _had_error
    print(f"caseproc: error: {msg}", file=sys.stderr)
    _had_error = True

def panic(msg: str) -> None:
    """Print a fatal error to stderr and exit immediately."""
    print(f"caseproc: fatal: {msg}", file=sys.stderr)
    sys.exit(1)
```

In `main()`, at the very end (after all processing), add:
```python
if _had_error:
    sys.exit(1)
```

The `--error` flag (added in Step 2) makes `warn()` behave like `error()`:
after parsing args, if `args.error` is set, replace the body of `warn()` with
a call to `error()` (or use a module-level `_strict` flag checked inside
`warn()`).

**Verify:**
```
./caseproc
```
Prints: `caseproc: not yet implemented`

---

## Step 2: Option processing

Add `argparse`-based CLI option parsing matching the spec's synopsis:

```
caseproc [--help] [--config JSON] [--error] [--ltac|-l FILENAME]
         [--validate | (--select|-s) SELECTOR | (--inline|-i)] [files]
```

**Add to `caseproc`:**

- Import `argparse`.
- Build `ArgumentParser` with `prog='caseproc'`.
- Add arguments:
  - `--config` (type `str`, metavar `JSON`)
  - `--error` (store_true)
  - `--ltac` / `-l` (type `str`, metavar `FILENAME`)
  - `files` (nargs `*`)
  - Mutually exclusive group (all optional):
    - `--validate` (store_true)
    - `--select` / `-s` (type `str`, metavar `SELECTOR`)
    - `--inline` / `-i` (store_true)
- In `main()`: parse args, then print `repr(args)` so we can see what was
  captured. (This debug print will be removed in a later step.)

**Verify:**
```
./caseproc --error --config '{}' somefile.md    # prints args
./caseproc --validate --select foo              # error: mutually exclusive
./caseproc --invalid                            # error: unrecognised argument
```

---

## Step 3: Help text

Polish all argument descriptions so `--help` is useful.

**Changes:**

- Add `description=` to `ArgumentParser` (one-sentence summary of the tool).
- Add `help=` strings to every argument matching the spec's `Meaning:` section.
- Add `epilog=` pointing to `docs/design-spec.md` for full details.
- Remove the debug `print(repr(args))` added in Step 2 and replace with a
  temporary stub: `print("caseproc: options parsed OK")`.

**Verify:**
```
./caseproc --help
```
Produces readable, complete help output. All flags are listed with descriptions.

---

## Step 4: Configuration (`--config`)

Load and validate the JSON configuration passed on the command line.

**Add to `caseproc`:**

- Define `DEFAULT_CONFIG`:
  ```python
  DEFAULT_CONFIG = {
      'base_url': '',
      'markdown_base_url': '',
  }
  ```
- Write `load_config(json_str: str) -> dict`:
  - If `json_str` is `None`, return a copy of `DEFAULT_CONFIG`.
  - Parse JSON; call `panic()` if the string is not valid JSON.
  - Call `warn()` for any key not in `DEFAULT_CONFIG`.
  - Merge parsed values over defaults and return.
- Call `load_config(args.config)` in `main()`; store result as `config`.
- Replace the stub print with `print("config:", config)`.

**Verify:**
```
./caseproc
# config: {'base_url': '', 'markdown_base_url': ''}

./caseproc --config '{"base_url": "https://example.com"}'
# config: {'base_url': 'https://example.com', 'markdown_base_url': ''}

./caseproc --config '{"unknown_key": 1}'
# warning on stderr; config uses defaults
```

---

## Step 5: Data model, parser, and `--ltac`

Implement the `Node` dataclass, utility functions, the LTAC parser, and the
`--ltac` flag so we can load raw LTAC files.

### 5a: Utility functions

Add (in order) to `caseproc`:

```python
def to_github_fragment(text: str) -> str: ...
def make_diagram_id(identifier: str, counter: list) -> str: ...
def escape_html(text: str) -> str: ...
def parse_options(raw: str) -> set: ...
```

Implement each per the docstrings in `docs/design-spec.md` §Utility Functions.

### 5b: Node dataclass

Add the `Node` dataclass exactly as specified in `docs/design-spec.md`
§Data Model. Include the `from dataclasses import dataclass, field` and
`from typing import Dict, List, Optional, Set, Tuple` imports at the top.

### 5c: LTAC parser

Add `import re` at the top. Define a **module-level compiled constant** (evaluated once on import):

```python
_LTAC_LINE_RE = re.compile(
    r'^(?P<indent>(?:  )*)'
    r'[-*] '
    r'(?P<nodetype>Claim|Strategy|Evidence|Justification'
    r'|Context|Assumption|Relation|Link)'
    r'(?:\s+(?P<identifier>[^:{\n(]+))?'
    r'(?::\s*(?P<text>[^({]*))?'
    r'(?:\s*\((?P<ref>[^)\n]*)\))?'
    r'(?:\s*\{(?P<options>[^}\n]*)\})?'
    r'\s*$'
)
```

Implement `LTACParser` and the module-level wrapper:

```python
class LTACParser:
    def parse(self, lines: List[str]) -> List[Node]: ...

def parse_ltac_lines(lines: List[str]) -> Tuple[List[Node], Dict[str, Node]]: ...
```

The parser loops over `lines` **one at a time**:

- **Blank/comment line**: a line is blank if it is empty after stripping, or if
  the stripped line starts with `//`. Blank lines are package separators: if a
  package is in progress (depth stack non-empty), finalize it (append roots to
  results; clear stack). Blank lines at the start, end, or between packages are
  silently ignored.
- **Non-blank line**: try `_LTAC_LINE_RE.match(line)`. If no match, call
  `error()` with the line number and offending text; skip the line and continue.
  Otherwise extract groups (all stripped of surrounding whitespace):
  - `depth = len(m.group('indent')) // 2`
  - `nodetype`, `identifier` (or `''`), `text` (or `''`), `ref` (or `''`)
  - `options`: `parse_options(m.group('options') or '')`
  - If `identifier` starts with `^`: set `is_cited = True`; parse `cited_pkg`
    and local ID from the `^[PkgName]LocalId` format.
- Build Node; compute `diagram_id`; if identifier is non-empty, add to
  `self.registry` — call `warn()` if the identifier is already present
  (duplicate). Auto-identifier `_auto{N}` if no identifier.
- Pop depth stack until top's depth < current depth.
- If stack non-empty: add node as child of stack top.
  If stack empty:
  - If current package already has a root, call `panic()`:
    `"package starting at line N already has a top-level element; only one allowed"`.
  - Otherwise add node as the package root.
- Push `(depth, node)` onto stack.
- After all lines, finalize any open package.
- For `Link` nodes: look up `self.registry[identifier]`; if found set
  `link_target`; if not found call `warn()`.

`parse_ltac_lines` is a module-level wrapper: create an `LTACParser`, call
`parse()`, return `(roots, parser.registry)`.

### 5d: LTAC file loading

Write `load_ltac_file(path: str, all_roots: List[Node], registry: Dict[str, Node]) -> None`:
- Open the file and pass its lines to `parse_ltac_lines()`.
- Merge the returned roots and registry entries into the provided
  `all_roots` and `registry` (the function mutates them in place).

In `main()`, after loading config, determine the LTAC source:
- If `args.ltac` is set, use that path.
- Otherwise try `case.ltac`, then `docs/case.ltac`.
- If no file is found, call `panic()`:
  `"no LTAC file found; use --ltac or create case.ltac"`.
- Call `load_ltac_file(path, all_roots, registry)`.
- Print a debug summary: number of packages and nodes parsed.

After loading, scan every node in the registry for external references:
for any node where `is_cited` is `True` and `cited_pkg` is non-empty,
check whether a package with that name exists in the loaded registry
(package names are formed as `"Package " + root.identifier` for each root).
Call `warn()` for any cited package name that was not found.

### 5e: Test fixture

Create `tests/fixtures/simple.ltac`:

```
- Claim C1: The software is acceptably safe
  - Strategy AR1: Argue safety by hazard category
    - Claim C2: All hazards have been identified
      - Evidence E1: Hazard analysis (hara.pdf)
    - Claim C3: All hazards have been mitigated
      - Link E1
  - Assumption A1: Threat model is current
  - Context X1: Scope is release v1.0 (release-notes.md)
```

**Verify:**
```
./caseproc --ltac tests/fixtures/simple.ltac
# debug line: "Loaded 1 package(s), 8 node(s)"
```

---

## Step 6: `--select` with `ltac/markdown`

Implement the SELECTOR mechanism and the first renderer so `--select` produces
real output.

### 6a: SELECTOR parsing

Write `parse_selector(selector: str) -> tuple`:
- Split on the first space to get `display_type` and optional `element_id`.
- `element_id` of `*` is kept as the literal string `'*'` (handled at
  dispatch time — see 6c).
- Return `(display_type, element_id_or_None)`.
- Call `error()` on unknown `display_type`; the selector region is left empty.

Valid display types at this stage: `ltac/markdown`. (Others added later.)

### 6b: `render_markdown` renderer

Implement `render_markdown(roots: List[Node], base_url: str = '') -> str`:
- Walk the tree recursively.
- Produce an indented bullet list (2 spaces per depth level).
- Each item: `- NodeType ID: text` where ID is a markdown hyperlink if a
  URL can be determined.
- URL = `ext_ref` if set; otherwise `base_url + '#' + to_github_fragment(...)`.
- Omit hyperlink if no URL is available.
- Skip Link nodes (they are citations, not new bullets).

### 6c: Element resolution and `*` dispatch

Write `resolve_element(element_id: Optional[str], registry, all_roots,
current_element) -> List[Node]`:
- If `element_id` given (and not `'*'`): look up in registry; if not found
  call `error()` and return `[]`.
- If no `element_id`: use `current_element` if set, else return `all_roots`.

Write `render_all_packages(all_roots: List[Node], render_fn, base_url: str) -> str`:
- For each root in `all_roots` (in order):
  - Emit `## Package {root.identifier}` (or `## Package` if no identifier).
  - Emit a blank line.
  - Emit `render_fn([root], base_url)`.
- Join package blocks with a blank line between them.

In the SELECTOR dispatch (6d and later), if `element_id == '*'`, call
`render_all_packages` instead of `resolve_element` + renderer directly.

### 6d: Wire up `--select` in `main()`

- After loading all input sources, parse SELECTOR from `args.select`.
- Resolve the element.
- Dispatch to the right renderer.
- Print result to stdout.
- Remove the debug summary print from Step 5d (or guard it behind `--error`
  verbose mode).

**Verify:**
```
./caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown"
```
Produces an indented markdown bullet list of the parsed LTAC tree.

```
./caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown C2"
```
Produces the subtree rooted at C2 only.

---

## Step 7: Test framework and first tests

Establish a repeatable test suite before the codebase grows further.

### 7a: Test runner

Create `tests/run_tests.py` using Python `unittest`. Python is already
required to run `caseproc`, making this fully portable across Linux, macOS,
and Windows without needing a shell, Git Bash, or WSL.

Key design points:

- Locate `caseproc` relative to the test file using `os.path`:
  ```python
  import os, sys, subprocess, unittest
  LTACPROC = [sys.executable,
              os.path.join(os.path.dirname(__file__), '..', 'caseproc')]
  ```
  Using `sys.executable` ensures the same Python interpreter is used
  everywhere and avoids any reliance on shebangs or `PATH`.

- Run commands with `subprocess.run(LTACPROC + args, capture_output=True,
  text=True)`. The `text=True` flag opens stdout/stderr in text mode,
  normalising line endings on Windows.

- Provide a helper that compares output to an expected file, normalising
  line endings before comparison so CRLF vs LF differences don't cause
  spurious failures:
  ```python
  def normalise(s):
      return s.replace('\r\n', '\n')
  ```

- Each test is a `unittest.TestCase` method. Run with:
  ```
  python tests/run_tests.py
  ```
  or `python -m unittest tests.run_tests`, or any standard test runner.

- Exit with non-zero if any test failed (standard `unittest` behaviour).

### 7b: Expected output fixtures

Run (use `python caseproc` on all platforms; on Unix `./caseproc` also works):
```
python caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown" \
  > tests/fixtures/simple.ltac.md.expected
python caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown C2" \
  > tests/fixtures/simple-c2.md.expected
python caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown *" \
  > tests/fixtures/simple-star.md.expected
```
Inspect and adjust each file if anything looks wrong, then commit them.
Ensure the committed files use LF line endings so comparisons are consistent.
`simple-star.md.expected` should contain `## Package C1` followed by a blank
line, then the same content as `simple.ltac.md.expected`.

### 7c: First tests

- **Test 1**: `./caseproc --help` exits 0.
- **Test 2**: `./caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown"`
  matches `tests/fixtures/simple.ltac.md.expected`.
- **Test 3**: `./caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown C2"`
  matches `tests/fixtures/simple-c2.md.expected` (just the C2 subtree).
- **Test 4**: `./caseproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown *"`
  matches `tests/fixtures/simple-star.md.expected` (all packages with headers).

**Verify:**
```
python tests/run_tests.py
# All tests PASS (or similar unittest summary)
```

---

## Step 8: Default filter mode and simple selectors

Implement streaming document processing and the simpler selectors
(`statement`, `references`, `info`, `ltac/html`). `sacm/mermaid` is deferred
to Step 9.

### 8a: Streaming document processor

Implement `process_document_stream(f, out, registry, all_roots, config)` where
`f` is an open file-like line iterator and `out` is an output stream.

LTAC data is already loaded; no LTAC parsing occurs here.
Process one line at a time — non-special lines are written to `out`
immediately. For each line:

- **Non-special line**: write to `out` immediately.
- **`<!-- ltac SELECTOR -->`** (SELECTOR non-empty):
  Write the marker to `out`.
  Read and discard lines in a simple loop until the line (stripped) equals
  `<!-- end ltac -->`. If EOF is reached first, call `error()` reporting the
  unclosed region and the file/line where the marker appeared.
  Render SELECTOR using the loaded `registry`; write rendered output to `out`.
  Write `<!-- end ltac -->` to `out`.
- **Markdown header** (`^#+ `): update current-element context; record the
  matched element identifier in a `seen_headers` set; write to `out`.

### 8b: Default mode in `main()`

If no mode flag (`--validate`, `--select`, `--inline`) is given:
- For each file in `args.files` (or stdin if none given), open it and call
  `process_document_stream(f, sys.stdout, registry, all_roots, config)`.
- The LTAC registry is already fully loaded before document processing begins.

### 8c: `statement`, `references`, and `info` selectors

Implement and wire into SELECTOR dispatch:

- `render_statement(node: Node) -> str`
  Returns `"Statement: " + node.text`.
- `render_references(node: Node, registry, config) -> str`
  Finds all packages in `all_roots` whose registry contains the node's
  identifier. Returns `"References: "` followed by a comma-separated list of
  markdown links to each package, using `markdown_base_url`. If none found,
  returns `"References: None"`.
- `info` is composed as `render_statement(...) + "\n\n" + render_references(...)`.

### 8d: `ltac/html` selector

Implement `render_html(roots: List[Node], base_url: str = '') -> str`:
- Produces a nested `<ul>/<li>` list mirroring the LTAC tree structure.
- Each `<li>` wraps the node type, identifier, and text; identifier is an
  `<a href="...">` when a URL is available.
- Omit Link nodes from the output (same as `render_markdown`).

Wire into SELECTOR dispatch.

### 8e: Post-processing header coverage check

After all document files have been processed in `main()` (in default or
`--inline` mode), call `warn()` for every identifier in `registry` that
does not appear in the `seen_headers` set accumulated during processing.
Message format: `"element C2 has no corresponding header in any processed file"`.

This catches elements that exist in the LTAC file but are never documented in
any of the processed Markdown/HTML files, helping authors keep their
documentation in sync with their assurance case.

Skip this check when running `--select` (no documents are being processed).

### 8f: Test fixtures for default mode


Create `tests/fixtures/doc-simple.md` (no `sacm/mermaid` regions yet).
This file references elements from `tests/fixtures/simple.ltac`:

```markdown
# Package C1

## Claim C1: The software is acceptably safe

<!-- ltac statement C1 -->
Statement: The software is acceptably safe
<!-- end ltac -->

<!-- ltac references C1 -->
References: None
<!-- end ltac -->
```

Generate and commit `tests/fixtures/doc-simple.md.expected`.

### 8g: Tests for default mode

Add to the test suite:
- **Test 5**: `./caseproc --ltac tests/fixtures/simple.ltac tests/fixtures/doc-simple.md`
  matches `doc-simple.md.expected`.
- **Test 6**: `./caseproc --ltac tests/fixtures/simple.ltac --validate tests/fixtures/doc-simple.md`
  exits 0 and produces no stdout.
- **Test 7**: A fixture with a deliberate structural warning (e.g., Evidence
  as parent of a Claim); `./caseproc --ltac ... --error` on it exits non-zero.
- **Test 8**: Process `doc-simple.md` with a `simple.ltac` that contains an
  extra element not referenced by any header; confirm a warning appears on
  stderr (and exit is non-zero when run with `--error`).

**Verify:**
```
python tests/run_tests.py
# All tests PASS
```

---

## Step 9: `sacm/mermaid` renderer

Implement `render_sacm()` in substeps, verifying the diagram visually at each
stage. The full spec is in `docs/design-spec.md` §SACM Renderer,
with more information in `docs/sacm-mermaid.md`.

### 9a: Node declaration strings

Implement node shape strings for each LTAC type per the spec's table:
- Claim (normal, needsSupport, axiomatic, defeated, assumed, abstract,
  is_cited)
- Strategy, Evidence, Context, Assumption, Justification
- Connector (`ID((&hairsp;)):::connector`)
- Relation and Link produce no node declaration of their own.

Produce just the node declarations (no edges yet). The full label is
`<b>ID</b><br>TEXT`; use `escape_html()` on text. Assertion-state suffixes
are mutually exclusive; apply in priority order: defeated > axiomatic >
assumed > needsSupport.

### 9b: Simple (unreified) edges

Add edge generation for the case where a node has exactly one inference source
and `metaClaim` is not set: emit `src_id --> parent_id` directly (no dot).
Context children always connect with `--o`.

Test by rendering a simple two-node tree and inspecting the output.

### 9c: Inference group algorithm (sacmDot)

Implement the full inference group algorithm for multiple inference sources:
- Collect `inference_sources` and `context_children` (and
  `context_children_of_strategy`) as specified.
- When `len(inference_sources) >= 2` or `metaClaim` is set, create a
  `DotN((&hairsp;)):::sacmDot` node and emit `src --- DotN` edges followed by
  `DotN --> parent`.
- Recurse into children.

### 9d: Context edges and Connector nodes

- Context children of a plain node: `ctx --o node`.
- Context children of a Strategy: `ctx --o strategy_node`.
- Connector nodes appear in mermaid as `:::connector`; their children connect
  to the Connector with `---`, and the Connector participates in the parent's
  inference group.

### 9e: Counter, abstract flags, and Relation semantics

- `counter` option on a relationship: replace `-->` with `-->|⊖|` and
  `--o` with `--o|⊖|`.
- `abstract` option on a Relation node: replace `---` with `-.-` and
  `-->` with `-.->`
- Relation node semantics: a Relation child of X contributes its own children
  as inference sources for X, with its options applied to those edges. Relation
  produces no mermaid node declaration.

### 9f: Edge/node output order and full mermaid header

Assemble complete mermaid output per the spec's §Full mermaid output structure:
1. YAML config header (theme, flowchart settings).
2. `classDef` declarations (invisible, sacmDot, connector, abstractClaim).
3. Node declarations in BFS order (roots first).
4. Dot/Connector node declarations (collected during edge generation).
5. Edges in DFS post-order (deepest leaves first).
6. `BottomPadding[ ]:::invisible ~~~ FIRST_ROOT_ID`.

### 9g: Click lines

For each node that has a URL (from `ext_ref` or constructed from `base_url`),
emit a `click ID href "URL"` line after all node declarations.

### 9h: Wire in, extend fixture, and test

- Add `sacm/mermaid` to SELECTOR dispatch.
- Add a `<!-- ltac sacm/mermaid C1 -->` region to `doc-simple.md` and
  generate updated `doc-simple.md.expected`.
- Add expected output file `tests/fixtures/simple.sacm.mermaid.expected`
  generated from `--select sacm/mermaid` on `simple.ltac`.
- **Test 9**: `--select sacm/mermaid` on `simple.ltac` matches expected.
- **Test 10**: default mode on updated `doc-simple.md` matches expected.

**Verify:**
```
python tests/run_tests.py
# All tests PASS
```
Also render the mermaid output in a viewer and confirm the diagram looks
correct before proceeding.

---

## Step 10: `--inline` mode with tests

Implement in-place file rewriting and add tests that safely reset fixtures.

### 10a: `--inline` in `main()`

For each file in `args.files`:
1. Open the file, run `process_document_stream` writing to a `StringIO` buffer.
2. If processing completed without a serious error **and** the buffer content
   differs from the original, write atomically: write to a temp file in the
   same directory, then `os.replace(tmp, path)`.
3. If a serious error occurred, leave the file unchanged and report to stderr.

### 10b: Test fixtures for `--inline`

Create `tests/fixtures/inline-input.md` (a file with stale selector regions
that need updating) and `tests/fixtures/inline-expected.md` (the correct
state after `--inline` runs).

### 10c: Tests for `--inline`

Because `--inline` overwrites files, tests **must** copy fixtures to a
temporary location before running:

```sh
# In the test runner, for each inline test:
cp tests/fixtures/inline-input.md /tmp/caseproc-test-inline.md
./caseproc --inline /tmp/caseproc-test-inline.md
diff /tmp/caseproc-test-inline.md tests/fixtures/inline-expected.md
```

Add to the test suite:
- **Test 11**: `--inline` on a fresh copy of `inline-input.md` produces
  content matching `inline-expected.md`.
- **Test 12**: Running `--inline` twice on the same copy is idempotent
  (second run makes no changes to the file).
- **Test 13**: `--inline` on a file with a serious parse error leaves the
  file unchanged.

**Verify:**
```
python tests/run_tests.py
# All tests PASS
```

---

## Summary of deliverables after all steps

| Artifact | Description |
|---|---|
| `caseproc` | Single executable Python 3 script |
| `tests/run_tests.py` | Test runner (all tests pass) |
| `tests/fixtures/simple.ltac` | Raw LTAC fixture |
| `tests/fixtures/simple.ltac.md.expected` | Expected `ltac/markdown` output |
| `tests/fixtures/simple-c2.md.expected` | Expected subtree output |
| `tests/fixtures/simple-star.md.expected` | Expected `ltac/markdown *` output (all packages) |
| `tests/fixtures/simple.sacm.mermaid.expected` | Expected `sacm/mermaid` output |
| `tests/fixtures/doc-simple.md` | Markdown document fixture |
| `tests/fixtures/doc-simple.md.expected` | Expected substituted output |
| `tests/fixtures/inline-input.md` | Input for `--inline` test |
| `tests/fixtures/inline-expected.md` | Expected result after `--inline` |
