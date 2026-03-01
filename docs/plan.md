# Implementation Plan for ltacproc

This plan implements `ltacproc` incrementally. After each step the result is
reviewed before proceeding. The design spec is `docs/design-spec.md`.

All code lives in a single executable file `ltacproc` at the project root.
Tests live under `tests/`; test input fixtures under `tests/fixtures/`.

---

## Step 1: Initial script skeleton

Create `ltacproc` as an executable Python 3 script.

**File: `ltacproc`**

- Shebang: `#!/usr/bin/env python3`
- Module docstring describing the script.
- Imports: `sys` only (nothing else yet).
- `main()` function that prints `"ltacproc: not yet implemented"` and returns.
- Standard `if __name__ == '__main__': main()` guard at the bottom.
- Run `chmod +x ltacproc` to make it executable.

**Verify:**
```
./ltacproc
```
Prints: `ltacproc: not yet implemented`

---

## Step 2: Option processing

Add `argparse`-based CLI option parsing matching the spec's synopsis:

```
ltacproc [--help] [--config JSON] [--error] [--ltac|-l FILENAME]
         [--validate | (--select|-s) SELECTOR | (--inline|-i)] [files]
```

**Add to `ltacproc`:**

- Import `argparse`.
- Build `ArgumentParser` with `prog='ltacproc'`.
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
./ltacproc --error --config '{}' somefile.md    # prints args
./ltacproc --validate --select foo              # error: mutually exclusive
./ltacproc --invalid                            # error: unrecognised argument
```

---

## Step 3: Help text

Polish all argument descriptions so `--help` is useful.

**Changes:**

- Add `description=` to `ArgumentParser` (one-sentence summary of the tool).
- Add `help=` strings to every argument matching the spec's `Meaning:` section.
- Add `epilog=` pointing to `docs/design-spec.md` for full details.
- Remove the debug `print(repr(args))` added in Step 2 and replace with a
  temporary stub: `print("ltacproc: options parsed OK")`.

**Verify:**
```
./ltacproc --help
```
Produces readable, complete help output. All flags are listed with descriptions.

---

## Step 4: Configuration (`--config`)

Load and validate the JSON configuration passed on the command line.

**Add to `ltacproc`:**

- Define `DEFAULT_CONFIG`:
  ```python
  DEFAULT_CONFIG = {
      'base_url': '',
      'markdown_base_url': '',
  }
  ```
- Write `load_config(json_str: str) -> dict`:
  - If `json_str` is `None`, return a copy of `DEFAULT_CONFIG`.
  - Parse JSON; warn to stderr for any key not in `DEFAULT_CONFIG`.
  - Merge parsed values over defaults and return.
- Call `load_config(args.config)` in `main()`; store result as `config`.
- Replace the stub print with `print("config:", config)`.

**Verify:**
```
./ltacproc
# config: {'base_url': '', 'markdown_base_url': ''}

./ltacproc --config '{"base_url": "https://example.com"}'
# config: {'base_url': 'https://example.com', 'markdown_base_url': ''}

./ltacproc --config '{"unknown_key": 1}'
# warning on stderr; config uses defaults
```

---

## Step 5: Data model, parser, and `--ltac`

Implement the `Node` dataclass, utility functions, the LTAC parser, and the
`--ltac` flag so we can load raw LTAC files.

### 5a: Utility functions

Add (in order) to `ltacproc`:

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
- **Non-blank line**: try `_LTAC_LINE_RE.match(line)`. If no match, print an
  error to stderr including the line number and the offending text, and return
  an error. Otherwise extract groups (all stripped of surrounding whitespace):
  - `depth = len(m.group('indent')) // 2`
  - `nodetype`, `identifier` (or `''`), `text` (or `''`), `ref` (or `''`)
  - `options`: `parse_options(m.group('options') or '')`
  - If `identifier` starts with `^`: set `is_cited = True`; parse `cited_pkg`
    and local ID from the `^[PkgName]LocalId` format.
- Build Node; compute `diagram_id`; add to `self.registry` if identifier is
  non-empty. Auto-identifier `_auto{N}` if no identifier.
- Pop depth stack until top's depth < current depth.
- If stack non-empty: add node as child of stack top.
  If stack empty: add node to current package roots list.
- Push `(depth, node)` onto stack.
- After all lines, finalize any open package.
- For `Link` nodes: look up `self.registry[identifier]`; if found set
  `link_target`; if not found warn to stderr.

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
- If no file is found, exit with a helpful message:
  `"ltacproc: no LTAC file found; use --ltac or create case.ltac"`.
- Call `load_ltac_file(path, all_roots, registry)`.
- Print a debug summary: number of packages and nodes parsed.

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
./ltacproc --ltac tests/fixtures/simple.ltac
# debug line: "Loaded 1 package(s), 8 node(s)"
```

---

## Step 6: `--select` with `ltac/markdown`

Implement the SELECTOR mechanism and the first renderer so `--select` produces
real output.

### 6a: SELECTOR parsing

Write `parse_selector(selector: str) -> tuple`:
- Split on the first space to get `display_type` and optional `element_id`.
- Return `(display_type, element_id_or_None)`.
- Raise (or print error + exit) on unknown `display_type`.

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

### 6c: Element resolution

Write `resolve_element(element_id: Optional[str], registry, all_roots,
current_element) -> List[Node]`:
- If `element_id` given: look up in registry; return `[node]` or error.
- If no `element_id`: use `current_element` if set, else return `all_roots`.

### 6d: Wire up `--select` in `main()`

- After loading all input sources, parse SELECTOR from `args.select`.
- Resolve the element.
- Dispatch to the right renderer.
- Print result to stdout.
- Remove the debug summary print from Step 5d (or guard it behind `--error`
  verbose mode).

**Verify:**
```
./ltacproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown"
```
Produces an indented markdown bullet list of the parsed LTAC tree.

```
./ltacproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown C2"
```
Produces the subtree rooted at C2 only.

---

## Step 7: Test framework and first tests

Establish a repeatable test suite before the codebase grows further.

### 7a: Test runner

Create `tests/run_tests.sh`:
- Simple shell script; each test is a function.
- Helper `check` function: runs a command, compares stdout to an expected file,
  prints PASS/FAIL with a label.
- Exit with non-zero if any test failed.
- At this stage, register the tests from 7b and 7c.

Alternatively, `tests/test_ltacproc.py` using Python `unittest` is also
acceptable. Choose whichever is simpler; the key requirement is that
`tests/run_tests.sh` (or `python tests/test_ltacproc.py`) can be run
repeatedly and is self-contained.

### 7b: Expected output fixture

Run:
```
./ltacproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown" \
  > tests/fixtures/simple.ltac.md.expected
```
Inspect and adjust the file if anything looks wrong, then commit it.

### 7c: First tests

- **Test 1**: `./ltacproc --help` exits 0.
- **Test 2**: `./ltacproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown"`
  matches `tests/fixtures/simple.ltac.md.expected`.
- **Test 3**: `./ltacproc --ltac tests/fixtures/simple.ltac --select "ltac/markdown C2"`
  matches a `simple-c2.md.expected` file (just the C2 subtree).

**Verify:**
```
./tests/run_tests.sh   # (or python tests/test_ltacproc.py)
# All tests PASS
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
  `<!-- end ltac -->`.
  Render SELECTOR using the loaded `registry`; write rendered output to `out`.
  Write `<!-- end ltac -->` to `out`.
- **Markdown header** (`^#+ `): update current-element context; write to `out`.

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

### 8e: Test fixtures for default mode

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

### 8f: Tests for default mode

Add to the test suite:
- **Test 4**: `./ltacproc --ltac tests/fixtures/simple.ltac tests/fixtures/doc-simple.md`
  matches `doc-simple.md.expected`.
- **Test 5**: `./ltacproc --ltac tests/fixtures/simple.ltac --validate tests/fixtures/doc-simple.md`
  exits 0 and produces no stdout.
- **Test 6**: A fixture with a deliberate structural warning (e.g., Evidence
  as parent of a Claim); `./ltacproc --ltac ... --error` on it exits non-zero.

**Verify:**
```
./tests/run_tests.sh
# All tests PASS
```

---

## Step 9: `sacm/mermaid` renderer

Implement `render_sacm()` in substeps, verifying the diagram visually at each
stage. The full spec is in `docs/design-spec.md` §SACM Renderer.

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
- **Test 7**: `--select sacm/mermaid` on `simple.ltac` matches expected.
- **Test 8**: default mode on updated `doc-simple.md` matches expected.

**Verify:**
```
./tests/run_tests.sh
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
cp tests/fixtures/inline-input.md /tmp/ltacproc-test-inline.md
./ltacproc --inline /tmp/ltacproc-test-inline.md
diff /tmp/ltacproc-test-inline.md tests/fixtures/inline-expected.md
```

Add to the test suite:
- **Test 9**: `--inline` on a fresh copy of `inline-input.md` produces
  content matching `inline-expected.md`.
- **Test 10**: Running `--inline` twice on the same copy is idempotent
  (second run makes no changes to the file).
- **Test 11**: `--inline` on a file with a serious parse error leaves the
  file unchanged.

**Verify:**
```
./tests/run_tests.sh
# All tests PASS
```

---

## Summary of deliverables after all steps

| Artifact | Description |
|---|---|
| `ltacproc` | Single executable Python 3 script |
| `tests/run_tests.sh` | Test runner (all tests pass) |
| `tests/fixtures/simple.ltac` | Raw LTAC fixture |
| `tests/fixtures/simple.ltac.md.expected` | Expected `ltac/markdown` output |
| `tests/fixtures/simple-c2.md.expected` | Expected subtree output |
| `tests/fixtures/simple.sacm.mermaid.expected` | Expected `sacm/mermaid` output |
| `tests/fixtures/doc-simple.md` | Markdown document fixture |
| `tests/fixtures/doc-simple.md.expected` | Expected substituted output |
| `tests/fixtures/inline-input.md` | Input for `--inline` test |
| `tests/fixtures/inline-expected.md` | Expected result after `--inline` |
