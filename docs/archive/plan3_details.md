# Plan 3 Implementation Details

This document gives a stage-by-stage implementation guide for `docs/plan3.md`.
Each stage is independently committable and testable.
All line numbers refer to the current `caseproc` file unless noted otherwise.

---

## Prerequisite reading

Before starting, read:
- `caseproc` lines 1–2268 (the entire implementation)
- `tests/run_tests.py` (test patterns)
- `docs/plan3.md` (the specification)

Key locations to keep in mind throughout:

| Symbol | File:Line | Purpose |
|---|---|---|
| `DEFAULT_CONFIG` | caseproc:51 | All config defaults |
| `Node` dataclass | caseproc:273 | LTAC element |
| `_LTAC_LINE_RE` | caseproc:301 | LTAC line parser regex |
| `LTACParser._attach_node` | caseproc:401 | Registers ids, builds tree |
| `_write_ltac_node` | caseproc:1956 | Serializes Node back to LTAC |
| `check_id_info` | caseproc:1795 | Cross-validates id usage |
| `render_sacm` / `render_gsn` | caseproc:1068 / 1289 | Mermaid renderers |
| `_SACM_HEADER` / `_GSN_HEADER` | caseproc:904 / 1214 | Mermaid diagram headers |
| `render_markdown` / `render_html` | caseproc:645 / 749 | LTAC list renderers |
| `render_statement` | caseproc:660 | Single-node statement |
| `render_references` | caseproc:672 | Package reference links |
| `_VALID_DISPLAY_TYPES` | caseproc:1384 | Allowed selector kinds |
| `parse_selector` | caseproc:1388 | Parse selector string |
| `render_selector` | caseproc:1418 | Dispatch to renderers |
| `render_all_packages` | caseproc:1367 | Render `*` packages |
| `_CASEPROC_REGION_RE` | caseproc:1468 | Match region start |
| `_HEADER_RE` / `_HTML_HEADER_RE` | caseproc:1471 / 1474 | Header scanning (to remove) |
| `_parse_header_text` | caseproc:1488 | Header parsing (to remove) |
| `process_document_stream` | caseproc:1520 | Main doc processor |
| `_check_header_coverage` | caseproc:1949 | Coverage check (to replace) |
| `_inline_rewrite_file` | caseproc:2103 | Per-file rewrite |
| `commit_updates` | caseproc:1999 | Atomic file writes |
| `parse_args` | caseproc:1625 | CLI argument parsing |
| `main` | caseproc:2150 | Entry point |

---

## Stage 1 — Remove `[PackageIdentifier]` notation

**Goal:** Simplify LTAC syntax; `^ID` replaces `^[PkgName] ID`.

### 1a. Simplify the regex

`caseproc:306` — in `_LTAC_LINE_RE`, remove the `(?:\[(?P<cited_pkg>[^\]]*)\])?`
group from the identifier part.  Before:
```
r'(?:\s+(?P<cited>\^)?(?:\[(?P<cited_pkg>[^\]]*)\])?(?P<identifier>[^:{\n(]*))?'
```
After:
```
r'(?:\s+(?P<cited>\^)?(?P<identifier>[^:{\n(]*))?'
```

### 1b. Remove `cited_pkg` from Node

`caseproc:284` — delete the `cited_pkg: str` field from the `Node` dataclass.

### 1c. Update `_build_node`

`caseproc:371` — remove the line `cited_pkg = (m.group('cited_pkg') or '').strip()`
and remove `cited_pkg=cited_pkg` from the `Node(...)` constructor call.

### 1d. Update `_attach_node`

`caseproc:401` — remove `cited_pkg`-related lines:
- `if node.cited_pkg:` block that appends to `info['cited_pkgs']`
- Remove `'cited_pkgs': set()` from the `id_info` entry template

### 1e. Update `check_id_info`

`caseproc:1795` — remove the inner loop over `info['cited_pkgs']` entirely
(lines 1808–1813); the `cited_pkgs`-not-found and wrong-package checks are gone.

### 1f. Update `_write_ltac_node`

`caseproc:1960` — remove the `if node.cited_pkg:` block that writes `[{node.cited_pkg}]`.

### 1g. Update `docs/ltac-extended.txt`

Change the `ExternalIdentifier` production from:
```
ExternalIdentifier = "^" [ "[" PackageIdentifier "]" ] LocalIdentifier ;
```
to:
```
ExternalIdentifier = "^" LocalIdentifier ;
```
Remove all references to `PackageIdentifier` and `^[PkgName]` throughout.

### 1h. Tests

Remove from `tests/run_tests.py`:
- `TestLTACValidation.test_cited_package_not_found_warns`
- `TestLTACValidation.test_cited_package_not_found_error_flag`
- `TestLTACValidation.test_wrong_pkg_citation_warns`
- `TestLTACValidation.test_wrong_pkg_citation_error_flag`

Remove fixture files:
- `tests/fixtures/cited-pkg-not-found.ltac`
- `tests/fixtures/wrong-pkg-citation.ltac`

Edit any remaining fixtures that use `^[PkgName]` syntax (search with
`grep -r '\^\[' tests/fixtures/`) to use bare `^ID` form.

Also update the help text in `parse_args` (`caseproc:1668`) which mentions
`^[PkgName] ID` citations.

### 1i. Check

`python3 tests/run_tests.py` — all remaining tests pass.
`python3 caseproc --selftest` — doctests pass.

---

## Stage 2 — Line-ending preservation

**Goal:** When writing LTAC or document files, preserve the file's existing
line-ending convention (LF or CRLF).  The first line of the file determines
the convention.

### 2a. Add `detect_line_ending(text: str) -> str`

Add after `escape_markdown` (around `caseproc:245`):

```python
def detect_line_ending(text: str) -> str:
    """Return '\\r\\n' if the first newline in text is CRLF, else '\\n'.

    >>> detect_line_ending('a\\r\\nb\\r\\n')
    '\\r\\n'
    >>> detect_line_ending('a\\nb\\n')
    '\\n'
    >>> detect_line_ending('')
    '\\n'
    """
    idx = text.find('\n')
    if idx > 0 and text[idx - 1] == '\r':
        return '\r\n'
    return '\n'
```

### 2b. Update `_make_temp`

`caseproc:2060` — `_make_temp(path, content)` currently writes `content` with
Python's default line endings.  Change to open the temp file in binary mode and
encode `content` using the detected line ending:

```python
def _make_temp(path: str, content: str, line_ending: str = '\n') -> Optional[str]:
    ...
    encoded = content.replace('\n', line_ending).encode('utf-8')
    # write encoded bytes with os.fdopen in binary mode
```

### 2c. Update `_inline_rewrite_file`

`caseproc:2103` — after reading `original`, detect its line ending:
```python
line_ending = detect_line_ending(original)
```
Pass `line_ending` to `_make_temp`.

### 2d. Update LTAC write path in `main`

`caseproc:2188` — after `write_ltac(all_roots)`, the LTAC content also needs
its line ending preserved.  Read `ltac_path` to detect the convention, then
pass to `_make_temp`.

### 2e. Tests

Add a test in `tests/run_tests.py` (`TestInlineMode` or a new `TestLineEndings`
class) that creates a CRLF file, runs caseproc on it, and confirms the output
file still uses CRLF.

---

## Stage 3 — Utility functions: `hyperlink` and `bold`

**Goal:** Provide two small, reusable formatting helpers that all later stages use.
Place them in the "Utility functions" section (`caseproc:91`), after
`escape_markdown`.

### 3a. `hyperlink(content, url, fmt)`

```python
def hyperlink(content: str, url: str, fmt: str) -> str:
    """Return a hyperlink in the given format ('markdown' or 'html').

    For markdown: [escaped content](url)
    For html:     <a href="escaped_url">escaped content</a>
    content is escaped for the target format.

    >>> hyperlink("Claim C1", "#claim-c1", "markdown")
    '[Claim C1](#claim-c1)'
    >>> hyperlink("Claim C1", "#claim-c1", "html")
    '<a href="#claim-c1">Claim C1</a>'
    >>> hyperlink("A & B", "#x", "markdown")
    '[A & B](#x)'
    >>> hyperlink("A & B", "#x", "html")
    '<a href="#x">A &amp; B</a>'
    """
    if fmt == 'html':
        return f'<a href="{escape_html(url)}">{escape_html_content(content)}</a>'
    return f'[{escape_markdown(content)}]({url})'
```

### 3b. `bold(text, fmt)`

```python
def bold(text: str, fmt: str) -> str:
    """Wrap text in bold markup for the given format.

    >>> bold("Package Foo", "markdown")
    '**Package Foo**'
    >>> bold("Package Foo", "html")
    '<b>Package Foo</b>'
    """
    if fmt == 'html':
        return f'<b>{text}</b>'
    return f'**{text}**'
```

### 3c. Tests

Add doctests (they run via `--selftest`).  No acceptance-test changes needed yet.

---

## Stage 4 — Document format detection

**Goal:** Know whether a file is markdown or HTML when processing it.

### 4a. Add `detect_doc_format(path: str) -> str`

```python
def detect_doc_format(path: str) -> str:
    """Return 'html' for .htm/.html files; 'markdown' for everything else.

    Stdin path '-' is treated as markdown.
    Panics for unrecognised extensions.

    >>> detect_doc_format('case.md')
    'markdown'
    >>> detect_doc_format('CASE.HTML')
    'html'
    >>> detect_doc_format('-')
    'markdown'
    """
    low = path.lower()
    if low == '-' or low.endswith('.md') or low.endswith('.markdown'):
        return 'markdown'
    if low.endswith('.html') or low.endswith('.htm'):
        return 'html'
    panic(f"cannot determine document format from filename {path!r}; "
          f"expected .md, .markdown, .html, or .htm")
```

### 4b. Thread `doc_format` into `process_document_stream`

`caseproc:1520` — add a `doc_format: str = 'markdown'` parameter. Callers in
`_process_files` (`caseproc:1937`) and `_inline_rewrite_file` (`caseproc:2118`)
compute it via `detect_doc_format(path)` before calling.

In `--stdout` mode (`caseproc:2243`), each file determines its own format.
For stdin, use `'markdown'`.

### 4c. Tests

No new tests yet; used by later stages.

---

## Stage 5 — New config keys

**Goal:** Add all new configuration keys required by plan3.

### 5a. Extend `DEFAULT_CONFIG` (caseproc:51)

Add:
```python
'default_renderer':     'mermaid',
'default_representation': 'sacm',
'element_level':        3,
'element_selections':   'referenced_by,supported_by,supports',
'mermaid_js_url':       'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs',
'package_level':        3,
'package_selections':   'representation,pkg_defines,pkg_citing,pkg_cited',
```

Remove from `DEFAULT_CONFIG`:
```python
'update_headers': True,   # removed in Stage 10
```
(defer this removal to Stage 10 to avoid breaking existing tests early)

### 5b. No other code changes

`load_config` (`caseproc:64`) already warns on unknown keys and merges known
ones automatically — no changes needed there.

### 5c. Tests

`TestConfig.test_config_unknown_key_warns` — still passes (unknown keys warn).
Add a test that `element_level=2` is accepted without warning.

---

## Stage 6 — Three-part selector expansion

**Goal:** `sacm` → `sacm/mermaid/markdown` (or `/html`); `ltac` → `ltac/markdown`
(or `/html`).  The `default_renderer` config key is the renderer tier default.

### 6a. Add `expand_selector(raw, doc_format, config) -> str`

Place near `parse_selector` (`caseproc:1388`):

```python
def expand_selector(raw: str, doc_format: str, config: dict) -> str:
    """Expand a shorthand selector to its canonical three-part form.

    Rules (fill in missing parts right-to-left using doc_format and
    default_renderer):
      sacm            -> sacm/{renderer}/{doc_format}
      sacm/mermaid    -> sacm/mermaid/{doc_format}
      gsn             -> gsn/{renderer}/{doc_format}
      gsn/mermaid     -> gsn/mermaid/{doc_format}
      ltac            -> ltac/{doc_format}
      ltac/markdown   -> ltac/markdown  (explicit, no third part)
      ltac/html       -> ltac/html
      everything else -> unchanged

    >>> expand_selector('sacm', 'markdown', {'default_renderer': 'mermaid'})
    'sacm/mermaid/markdown'
    >>> expand_selector('sacm/mermaid', 'html', {'default_renderer': 'mermaid'})
    'sacm/mermaid/html'
    >>> expand_selector('sacm/mermaid/markdown', 'html', {})
    'sacm/mermaid/markdown'
    >>> expand_selector('ltac', 'html', {})
    'ltac/html'
    >>> expand_selector('statement', 'markdown', {})
    'statement'
    """
    renderer = config.get('default_renderer', 'mermaid')
    parts = raw.split('/')
    if parts[0] in ('sacm', 'gsn'):
        if len(parts) == 1:
            return f'{parts[0]}/{renderer}/{doc_format}'
        if len(parts) == 2:
            return f'{parts[0]}/{parts[1]}/{doc_format}'
        return raw  # explicit three-part, pass through
    if parts[0] == 'ltac':
        if len(parts) == 1:
            return f'ltac/{doc_format}'
        return raw  # explicit two-part, pass through
    return raw
```

### 6b. Update `parse_selector`

`caseproc:1388` — add a `doc_format` and `config` parameter, call
`expand_selector` on the raw selector before splitting:

```python
def parse_selector(selector: str, doc_format: str = 'markdown',
                   config: dict = None) -> Tuple[str, Optional[str]]:
    config = config or {}
    parts = selector.split(None, 1)
    raw_type = parts[0] if parts else ''
    element_id = parts[1].strip() if len(parts) > 1 else None
    display_type = expand_selector(raw_type, doc_format, config)
    if display_type not in _VALID_DISPLAY_TYPES:
        error(f"unknown selector type {display_type!r}")
    return display_type, element_id
```

### 6c. Update `_VALID_DISPLAY_TYPES`

`caseproc:1384` — add the three-part explicit forms:
```python
_VALID_DISPLAY_TYPES = {
    'ltac/markdown', 'ltac/html',
    'sacm/mermaid', 'sacm/mermaid/markdown', 'sacm/mermaid/html',
    'gsn/mermaid',  'gsn/mermaid/markdown',  'gsn/mermaid/html',
    'statement', 'references', 'info',
    # new selectors added in later stages:
    'element', 'package',
    'referenced_by', 'supported_by', 'supports',
    'representation', 'pkg_defines', 'pkg_citing', 'pkg_cited',
}
```

(Add `element`, `package` etc. now so they don't trigger "unknown selector" errors
as they are developed in later stages.)

### 6d. Update all `render_selector` callers

`caseproc:1559` (in `process_document_stream`) and `caseproc:2229` (in `main`)
— pass `doc_format` and `config` to `parse_selector`.

### 6e. Update dispatch in `render_selector`

`caseproc:1431` — after expansion, `sacm/mermaid/markdown` and `sacm/mermaid`
both route to `render_sacm`; `sacm/mermaid/html` routes to the new
`render_sacm_html` (added in Stage 7).  Similarly for GSN.

### 6f. Tests

Add a test: `--select sacm` on a markdown file produces the same output as
`--select sacm/mermaid`.

---

## Stage 7 — Mermaid HTML output and JS injection

**Goal:** `sacm/mermaid/html` and `gsn/mermaid/html` produce `<pre class="mermaid">`
blocks; the Mermaid JS `<script>` is injected inside the first mermaid region.

### 7a. Factor out diagram body helpers

Currently `render_sacm` (`caseproc:1068`) builds everything inline.
Extract a `_sacm_diagram_body(roots, config) -> str` that returns the diagram
text between the fences (including YAML frontmatter), without the opening
` ```mermaid ` or closing ` ``` `.  `render_sacm` calls it and wraps in fences.

Similarly extract `_gsn_diagram_body(roots, config) -> str` from `render_gsn`
(`caseproc:1289`).

### 7b. Add `render_sacm_html` and `render_gsn_html`

```python
def render_sacm_html(roots: List[Node], config: dict) -> str:
    """Render SACM diagram as a <pre class="mermaid"> block."""
    body = _sacm_diagram_body(roots, config)
    return f'<pre class="mermaid">\n{body}\n</pre>'

def render_gsn_html(roots: List[Node], config: dict) -> str:
    """Render GSN diagram as a <pre class="mermaid"> block."""
    body = _gsn_diagram_body(roots, config)
    return f'<pre class="mermaid">\n{body}\n</pre>'
```

### 7c. Add `DocState` dataclass

Add near the document-processor section (`caseproc:1463`):

```python
@dataclass
class DocState:
    """Mutable per-document processing state."""
    current_id: Optional[str] = None
    doc_format: str = 'markdown'
    mermaid_injected: bool = False
    seen_element_ids: set = field(default_factory=set)
```

### 7d. Add `_maybe_inject_mermaid_js`

```python
def _maybe_inject_mermaid_js(rendered: str, config: dict, state: DocState) -> str:
    """Prepend the Mermaid JS <script> block to rendered if not yet injected.

    Only acts when:
    - doc_format is 'html'
    - rendered contains '<pre class="mermaid">'
    - state.mermaid_injected is False
    - mermaid_js_url is non-empty
    """
    if (state.doc_format != 'html'
            or state.mermaid_injected
            or '<pre class="mermaid">' not in rendered):
        return rendered
    url = config.get('mermaid_js_url', DEFAULT_CONFIG['mermaid_js_url'])
    if not url:
        return rendered
    script = (
        f'<script type="module">\n'
        f'  import mermaid from \'{url}\';\n'
        f'  mermaid.initialize({{ startOnLoad: true }});\n'
        f'</script>\n'
    )
    state.mermaid_injected = True
    return script + rendered
```

### 7e. Thread `DocState` through `process_document_stream`

`caseproc:1520` — replace the `current_element` local with a `DocState` instance.
After calling `render_selector`, call `_maybe_inject_mermaid_js` on the result
before writing.

### 7f. Update `render_selector` dispatch for HTML mermaid

`caseproc:1431`:
```python
if display_type in ('sacm/mermaid', 'sacm/mermaid/markdown'):
    return _render_or_all(element_id, all_roots, render_sacm, ...)
if display_type == 'sacm/mermaid/html':
    return _render_or_all(element_id, all_roots, render_sacm_html, ...)
# similarly for gsn
```

### 7g. Tests

Add a fixture `tests/fixtures/simple-html.html` with a `sacm/mermaid` region.
Add a test that verifies the output contains `<pre class="mermaid">` and that
the Mermaid JS `<script>` appears before it.

Add a test for `mermaid_js_url: ""` (injection disabled).

---

## Stage 8 — Selection renderers

**Goal:** Implement all the individual selection functions used by `element` and
`package` selectors.  Each returns a string (possibly empty to be suppressed).

### 8a. Helper: `_pkg_anchor_url(pkg_root_id, config)`

```python
def _pkg_anchor_url(pkg_root_id: str, config: dict) -> str:
    """Return the fragment URL for a package heading."""
    base_url = config.get('markdown_base_url', '')
    anchor = _component_anchor_id('Package', pkg_root_id)
    return base_url + '#' + anchor
```

### 8b. Helper: `_element_anchor_url(node_type, ident, config)`

```python
def _element_anchor_url(node_type: str, ident: str, config: dict) -> str:
    """Return the fragment URL for an element heading."""
    base_url = config.get('markdown_base_url', '')
    anchor = _component_anchor_id(node_type, ident)
    return base_url + '#' + anchor
```

### 8c. Helper: `_find_citation_parents(ident, all_roots)`

```python
def _find_citation_parents(ident: str, all_roots: List[Node]) -> List[Node]:
    """Return parent nodes of all citations of ident across all packages."""
    parents = []
    for node in _all_nodes(all_roots):
        if node.identifier == ident and node.is_cited and node.parent is not None:
            if node.parent not in parents:
                parents.append(node.parent)
    return parents
```

### 8d. `render_referenced_by(node, all_roots, id_info, config, fmt)`

```python
def render_referenced_by(node: Node, all_roots: List[Node],
                         id_info: Dict[str, dict], config: dict, fmt: str) -> str:
    """Render 'Referenced by: ...' line or '' if no packages to list."""
    ident = node.identifier
    info = id_info.get(ident, {})
    pkg_ids = []
    if info.get('decl_pkg_id'):
        pkg_ids.append(info['decl_pkg_id'])
    for cid in info.get('citing_pkg_ids', []):
        if cid not in pkg_ids:
            pkg_ids.append(cid)
    if not pkg_ids:
        return ''
    links = []
    for i, pid in enumerate(pkg_ids):
        label = f'Package {pid}'
        url = _pkg_anchor_url(pid, config)
        link = hyperlink(label, url, fmt)
        links.append(bold(link, fmt) if i == 0 else link)
    return 'Referenced by: ' + ', '.join(links)
```

### 8e. `render_supported_by(node, config, fmt)`

```python
def render_supported_by(node: Node, config: dict, fmt: str) -> str:
    """Render 'Supported by: ...' line or '' if no children."""
    children = [c for c in node.children if c.node_type != 'Link'
                or c.link_target is not None]
    if not children:
        return ''
    links = []
    for i, child in enumerate(children):
        # Link nodes: use their target for the label and URL
        target = child.link_target if child.node_type == 'Link' else child
        if target is None or not target.identifier:
            continue
        label = f'{target.node_type} {target.identifier}'
        url = _element_anchor_url(target.node_type, target.identifier, config)
        link = hyperlink(label, url, fmt)
        links.append(bold(link, fmt) if i == 0 else link)
    if not links:
        return ''
    return 'Supported by: ' + ', '.join(links)
```

### 8f. `render_supports(node, all_roots, config, fmt)`

```python
def render_supports(node: Node, all_roots: List[Node],
                    config: dict, fmt: str) -> str:
    """Render 'Supports: ...' line or '' if no parents at all."""
    entries = []
    # Defining parent (bold)
    if node.parent is not None:
        p = node.parent
        label = f'{p.node_type} {p.identifier}'
        url = _element_anchor_url(p.node_type, p.identifier, config)
        entries.append((hyperlink(label, url, fmt), True))  # True = bold
    # Parents of citations in LTAC order
    for parent in _find_citation_parents(node.identifier, all_roots):
        if not parent.identifier:
            continue
        label = f'{parent.node_type} {parent.identifier}'
        url = _element_anchor_url(parent.node_type, parent.identifier, config)
        entries.append((hyperlink(label, url, fmt), False))
    if not entries:
        return ''
    links = [bold(link, fmt) if is_bold else link for link, is_bold in entries]
    return 'Supports: ' + ', '.join(links)
```

### 8g. `render_pkg_defines(pkg_root, registry, id_info, config, fmt)`

```python
def render_pkg_defines(pkg_root: Node, id_info: Dict[str, dict],
                       config: dict, fmt: str) -> str:
    """Render 'Defines: ...' list for a package."""
    pkg_id = pkg_root.identifier
    # Collect defined elements in LTAC (DFS) order; root first.
    defined = []
    for node in _all_nodes([pkg_root]):
        if (not node.is_cited and node.identifier
                and id_info.get(node.identifier, {}).get('decl_pkg_id') == pkg_id):
            defined.append(node)
    if not defined:
        return ''
    links = []
    for i, node in enumerate(defined):
        label = f'{node.node_type} {node.identifier}'
        url = _element_anchor_url(node.node_type, node.identifier, config)
        link = hyperlink(label, url, fmt)
        links.append(bold(link, fmt) if i == 0 else link)
    return 'Defines: ' + ', '.join(links)
```

### 8h. `render_pkg_citing(pkg_root, registry, id_info, config, fmt)`

```python
def render_pkg_citing(pkg_root: Node, id_info: Dict[str, dict],
                      config: dict, fmt: str) -> str:
    """Render 'Citing: ...' list for a package, or '' if none."""
    cited_nodes = [n for n in _all_nodes([pkg_root])
                   if n.is_cited and n.identifier]
    if not cited_nodes:
        return ''
    links = []
    for node in cited_nodes:
        decl_pkg = id_info.get(node.identifier, {}).get('decl_pkg_id', '')
        label = f'{node.node_type} {node.identifier}'
        url = _pkg_anchor_url(decl_pkg, config) if decl_pkg else ''
        links.append(hyperlink(label, url, fmt) if url else label)
    return 'Citing: ' + ', '.join(links)
```

### 8i. `render_pkg_cited(pkg_root, all_roots, id_info, config, fmt)`

```python
def render_pkg_cited(pkg_root: Node, all_roots: List[Node],
                     id_info: Dict[str, dict], config: dict, fmt: str) -> str:
    """Render 'Cited by: ...' list for a package, or '' if none."""
    pkg_id = pkg_root.identifier
    citing_pkgs = []
    for ident, info in id_info.items():
        if info.get('decl_pkg_id') == pkg_id:
            for cpid in info.get('citing_pkg_ids', []):
                if cpid not in citing_pkgs:
                    citing_pkgs.append(cpid)
    if not citing_pkgs:
        return ''
    links = []
    for cpid in citing_pkgs:
        label = f'Package {cpid}'
        url = _pkg_anchor_url(cpid, config)
        links.append(hyperlink(label, url, fmt))
    return 'Cited by: ' + ', '.join(links)
```

### 8j. `render_representation(pkg_root, all_roots, config, fmt)`

```python
def render_representation(pkg_root: Node, all_roots: List[Node],
                          config: dict, fmt: str) -> str:
    """Render the default diagram representation for a package."""
    notation = config.get('default_representation', 'sacm')
    renderer = config.get('default_renderer', 'mermaid')
    selector = f'{notation}/{renderer}/{fmt}'
    # Reuse existing dispatch
    if selector in ('sacm/mermaid/markdown',):
        return render_sacm([pkg_root], config)
    if selector == 'sacm/mermaid/html':
        return render_sacm_html([pkg_root], config)
    if selector in ('gsn/mermaid/markdown',):
        return render_gsn([pkg_root], config)
    if selector == 'gsn/mermaid/html':
        return render_gsn_html([pkg_root], config)
    if selector == 'ltac/markdown':
        return render_markdown([pkg_root], config)
    if selector == 'ltac/html':
        return render_html([pkg_root], config)
    error(f"unsupported representation {selector!r}")
    return ''
```

### 8k. Tests

Add unit tests (inline in `run_tests.py` or via doctests in `caseproc`) for
each renderer.  Use `simple.ltac` as input.

---

## Stage 9 — `element` and `package` selectors

**Goal:** Implement the two new selectors that generate headings and apply
selection lists.

### 9a. Helper: `_apply_selections(selections_str, render_fns, config, fmt)`

```python
def _apply_selections(selections: List[str],
                      render_map: Dict[str, callable],
                      config: dict, fmt: str) -> str:
    """Apply a list of selection names and return their combined output.

    Each selection function returns a string (possibly empty).
    Non-empty outputs are separated by blank lines.
    The very last blank line is suppressed.
    """
    parts = []
    for sel in selections:
        fn = render_map.get(sel)
        if fn is None:
            warn(f"unknown selection name {sel!r}")
            continue
        out = fn()
        if out:
            parts.append(out)
    return '\n\n'.join(parts)
```

### 9b. `render_element_selector(node_id, registry, all_roots, id_info, config, state)`

```python
def render_element_selector(node_id: str, registry: Dict[str, Node],
                             all_roots: List[Node], id_info: Dict[str, dict],
                             config: dict, state: DocState) -> str:
    node = registry.get(node_id)
    if node is None:
        error(f"element {node_id!r} not found")
        return ''
    state.current_id = node_id
    state.seen_element_ids.add(node_id)

    # --- Heading ---
    level = config.get('element_level', 3)
    anchor = _component_anchor_id(node.node_type, node_id)
    stmt = id_info.get(node_id, {}).get('statement') or node.text or ''
    heading_text = f'{node.node_type} {node_id}'
    if stmt:
        heading_text += f': {stmt}'
    fmt = state.doc_format

    if fmt == 'markdown':
        heading_lines = [f'<a id="{anchor}"></a>', '#' * level + ' ' + heading_text]
    else:
        heading_lines = [f'<h{level} id="{anchor}">{escape_html_content(heading_text)}</h{level}>']

    # --- Selections ---
    sel_names = [s.strip() for s in
                 config.get('element_selections', 'referenced_by,supported_by,supports')
                 .split(',') if s.strip()]
    render_map = {
        'referenced_by': lambda: render_referenced_by(node, all_roots, id_info, config, fmt),
        'supported_by':  lambda: render_supported_by(node, config, fmt),
        'supports':      lambda: render_supports(node, all_roots, config, fmt),
    }
    selections_out = _apply_selections(sel_names, render_map, config, fmt)

    parts = ['\n'.join(heading_lines)]
    if selections_out:
        parts.append(selections_out)
    return '\n\n'.join(parts)
```

### 9c. `render_package_selector(pkg_id_or_star, all_roots, registry, id_info, config, state)`

```python
def render_package_selector(pkg_id_or_star: str, all_roots: List[Node],
                             registry: Dict[str, Node],
                             id_info: Dict[str, dict],
                             config: dict, state: DocState) -> str:
    if pkg_id_or_star == '*':
        blocks = []
        for root in all_roots:
            state.current_id = root.identifier
            blocks.append(_render_single_package(root, all_roots, id_info, config, state))
        return '\n\n'.join(blocks)
    pkg_root = registry.get(pkg_id_or_star)
    if pkg_root is None or pkg_root.depth != 0:
        error(f"package {pkg_id_or_star!r} not found or is not a root element")
        return ''
    state.current_id = pkg_id_or_star
    return _render_single_package(pkg_root, all_roots, id_info, config, state)
```

```python
def _render_single_package(pkg_root: Node, all_roots: List[Node],
                            id_info: Dict[str, dict],
                            config: dict, state: DocState) -> str:
    """Render one package heading + its package_selections."""
    fmt = state.doc_format
    level = config.get('package_level', 3)
    anchor = _component_anchor_id('Package', pkg_root.identifier)
    stmt = id_info.get(pkg_root.identifier, {}).get('statement') or pkg_root.text or ''
    heading_text = f'Package {pkg_root.identifier}'
    if stmt:
        heading_text += f': {stmt}'

    if fmt == 'markdown':
        heading_lines = [f'<a id="{anchor}"></a>', '#' * level + ' ' + heading_text]
    else:
        heading_lines = [f'<h{level} id="{anchor}">{escape_html_content(heading_text)}</h{level}>']

    sel_names = [s.strip() for s in
                 config.get('package_selections',
                            'representation,pkg_defines,pkg_citing,pkg_cited')
                 .split(',') if s.strip()]
    render_map = {
        'representation': lambda: render_representation(pkg_root, all_roots, config, fmt),
        'pkg_defines':    lambda: render_pkg_defines(pkg_root, id_info, config, fmt),
        'pkg_citing':     lambda: render_pkg_citing(pkg_root, id_info, config, fmt),
        'pkg_cited':      lambda: render_pkg_cited(pkg_root, all_roots, id_info, config, fmt),
    }
    selections_out = _apply_selections(sel_names, render_map, config, fmt)

    parts = ['\n'.join(heading_lines)]
    if selections_out:
        parts.append(selections_out)
    return '\n\n'.join(parts)
```

### 9d. Wire `element` and `package` into `render_selector`

`render_selector` (`caseproc:1418`) currently does not receive `DocState`.
Change its signature to accept `state: DocState` and pass it from
`process_document_stream`.

Add dispatch:
```python
if display_type == 'element':
    if element_id is None:
        error("'element' selector requires an explicit ID")
        return ''
    return render_element_selector(element_id, registry, all_roots,
                                   id_info, config, state)

if display_type == 'package':
    pkg_id = element_id or '*'
    return render_package_selector(pkg_id, all_roots, registry,
                                   id_info, config, state)
```

### 9e. Update `process_document_stream`

`caseproc:1520` — construct a `DocState` at the top of the function; pass it to
`render_selector`; after the function returns, the caller can read
`state.seen_element_ids`.

### 9f. Tests

Add a fixture `tests/fixtures/element-selector-input.md` with:
```
<!-- caseproc element C1 -->
<!-- end caseproc -->
```
and a corresponding `element-selector-output.expected.md`.

Add a fixture `tests/fixtures/package-star-input.md` with:
```
<!-- caseproc package * -->
<!-- end caseproc -->
```
Test that all packages are rendered with headings, diagrams, and cross-references.

---

## Stage 10 — Remove header scanning

**Goal:** Delete all legacy header-scanning machinery.

### 10a. Remove from `caseproc`

Delete or comment out:
- `_HEADER_RE` (`caseproc:1471`)
- `_HTML_HEADER_RE` (`caseproc:1474`)
- `_ELEMENT_TYPE_NAMES` (`caseproc:1478`)
- `_HEADER_TEXT_RE` (`caseproc:1485`)
- `_parse_header_text` (`caseproc:1488`)
- The anchor-strip regex `_anchor_strip_re` (`caseproc:1542`) and its use
- The entire header-parsing block in `process_document_stream`
  (`caseproc:1567–1609`): the `hm = _HEADER_RE.match(text)` block and everything
  it does (setting `current_element`, inserting anchors, updating headers)

### 10b. Remove `update_headers` config key

`DEFAULT_CONFIG` (`caseproc:51`) — remove `'update_headers': True`.
`process_document_stream` — remove the `do_update = config.get('update_headers', True)` line.

### 10c. Replace `_check_header_coverage` with `_check_element_coverage`

`caseproc:1949`:
```python
def _check_element_coverage(registry: Dict[str, Node],
                            seen_element_ids: set) -> None:
    """Warn about every registry element with no corresponding element selector."""
    for ident in registry:
        if ident not in seen_element_ids:
            warn(f"element {ident!r} has no 'element' selector in any processed file")
```

Update callers in `main` (`caseproc:2244, 2260`).

### 10d. Update `--validate`

`caseproc:2234` — `--validate` now checks for `element` selectors.
Call `_check_element_coverage(registry, state.seen_element_ids)` after processing.

### 10e. Remove `pkg_header_prefix`, `pkg_header_suffix` from `DEFAULT_CONFIG`

These were only used by `render_all_packages` for the `*` rendering path.
The new `package *` selector replaces that.  However, `render_all_packages`
(`caseproc:1367`) is still used for explicit `sacm/mermaid *` in `--select`
mode; either keep these config keys with a notice they are for `--select` only,
or remove `render_all_packages` entirely if `sacm/mermaid *` is no longer needed
as a standalone selector.  Recommendation: keep for now, document as legacy.

### 10f. Tests to remove or rewrite

Tests that rely on header scanning:
- `TestDefaultMode.test_header_coverage_warning` — rewrite to use
  `<!-- caseproc element -->` (missing element selector) pattern
- `TestUpdate.test_update_header_default` — `update_headers` no longer exists;
  rewrite or remove
- `TestIntroduction.test_non_ltac_heading_ignored` — still valid (non-LTAC
  headings should pass through silently); keep but verify no spurious warnings

Fixtures that use LTAC-shaped markdown headers (e.g., `doc-simple-input.md`,
`inline-input.md`, `update-input.md`, `introduction-input.md`) need rewriting
to use `element` and `package` selectors.  See Stage 15 for the transition tool.

---

## Stage 11 — Build a transition tool and update test fixtures

**Goal:** Convert all existing test fixtures from header-based format to
`element`/`package` selector format, restoring the test suite immediately after
the breaking Stage 10 change.

### 11a. Write `tests/migrate_fixtures.py`

A standalone script that:
1. Takes a markdown/HTML document as input.
2. Scans for LTAC-shaped headers (`### Claim C1: ...`, `### Package X`).
3. For each such header, inserts a `<!-- caseproc element ID -->` /
   `<!-- caseproc package ID -->` region immediately after (or replaces the
   header line with the region if desired).
4. Removes stale `<a id="...">` anchor lines.
5. Writes the result in place (or to stdout with `--stdout`).

Port the header-parsing regexes from `caseproc` **before** deleting them in
Stage 10 (or keep a copy in the script):
```python
_HEADER_RE = re.compile(r'^(#+) (.+)')
_HEADER_TEXT_RE = re.compile(r'^(\S+)\s+(\S+)(?::\s*(.+))?$')
_ELEMENT_TYPE_NAMES = {'Claim','Strategy','Evidence',
                       'Justification','Context','Assumption'}
_ANCHOR_RE = re.compile(
    r'^<a\s+id="(?:claim|strategy|evidence|justification|context|assumption|package)-[^"]*"\s*></a>\s*$',
    re.IGNORECASE)
```

For each matching header line, emit:
```
<!-- caseproc element ID -->
<!-- end caseproc -->

### ELEMENT_TYPE ID: statement
```
(The heading itself is now generated inside the region by caseproc; strip the
old heading and let the `element` selector regenerate it.)

For `Package` headers:
```
<!-- caseproc package ID -->
<!-- end caseproc -->
```

### 11b. Run `migrate_fixtures.py` on all fixture documents

```sh
for f in tests/fixtures/*-input.md tests/fixtures/*.html; do
    python3 tests/migrate_fixtures.py "$f"
done
```

Then run caseproc on each migrated input to regenerate `*.expected.*` files:
```sh
python3 tests/run_tests.py   # see which tests fail
tests/accept_tests           # promote new results to fixtures
```

### 11c. Update `stress-test-input.md`

Run `migrate_fixtures.py` on it, then regenerate and accept the expected output.

### 11d. Rewrite affected test methods

Tests that must change after Stage 10 (grep: `header` in `run_tests.py`):
- `test_header_coverage_warning` → `test_element_coverage_warning`
- `test_validate_exits_zero_no_stdout` — update input fixture
- `test_header_not_in_ltac_warns` — remove or rewrite as
  "element selector references unknown ID"
- `test_update_header_default` — remove (`update_headers` gone)
- `test_non_ltac_heading_ignored` — still valid; keep, verify no spurious warnings

### 11e. Check

`python3 tests/run_tests.py` — all tests pass again.

---

## Stage 12 — `caseproc-config` directive

**Goal:** `<!-- caseproc-config KEY = VALUE -->` dynamically modifies a config key.

### 11a. Add regex

After `_CASEPROC_REGION_RE` (`caseproc:1468`):
```python
_CASEPROC_CONFIG_RE = re.compile(
    r'^<!--\s*caseproc-config\s+(\S+)\s*=\s*(.*?)\s*-->\s*$'
)
```
Group 1 = KEY, group 2 = VALUE (already stripped by the `\s*` on both sides).

### 11b. Add `allowed_values` dict and validation

```python
_ALLOWED_CONFIG_VALUES = {
    'element_level': re.compile(r'^[1-6]$'),
    'package_level': re.compile(r'^[1-6]$'),
}
```

```python
def apply_config_directive(key: str, value: str, config: dict,
                           filename: str, lineno: int) -> None:
    """Apply a caseproc-config directive, warning on invalid key or value."""
    if key not in DEFAULT_CONFIG:
        warn(f"{filename}:{lineno}: caseproc-config: unknown key {key!r}")
        return
    pattern = _ALLOWED_CONFIG_VALUES.get(key)
    if pattern is None:
        warn(f"{filename}:{lineno}: caseproc-config: key {key!r} is not dynamically settable")
        return
    if not pattern.match(value):
        warn(f"{filename}:{lineno}: caseproc-config: invalid value {value!r} for {key!r}")
        return
    # Convert to int for numeric keys
    if key in ('element_level', 'package_level'):
        config[key] = int(value)
    else:
        config[key] = value
```

### 11c. Update `process_document_stream`

In the line-processing loop, before the region check, add:
```python
cm = _CASEPROC_CONFIG_RE.match(text)
if cm:
    apply_config_directive(cm.group(1), cm.group(2), config, filename, lineno)
    out.write(text + '\n')
    continue
```

The directive is written as-is and takes effect immediately.

Also check: if someone writes `<!-- caseproc config ... -->` (old syntax),
detect it and emit an error explaining `caseproc-config` is the correct form.
Do this by checking if the selector in a region is `config`:

In `render_selector`, before the dispatch table:
```python
if display_type == 'config':
    error("use '<!-- caseproc-config KEY = VALUE -->' (not '<!-- caseproc config ...-->')")
    return ''
```

### 11d. Tests

Add `TestCaseprocConfig` class:
- `test_config_directive_changes_level` — a document with
  `<!-- caseproc-config element_level = 2 -->` and then an `element` region
  should produce `<h2>` or `##` headings.
- `test_config_directive_invalid_key_warns`
- `test_config_directive_invalid_value_warns`
- `test_config_directive_persists_across_regions`
- `test_config_wrong_syntax_is_error`

---

## Stage 13 — Remove `references` and `info` selectors

**Goal:** Clean up superseded selectors.

### 12a. Remove from `_VALID_DISPLAY_TYPES` (caseproc:1384)

Delete `'references'` and `'info'` from the set.

### 12b. Remove dispatch in `render_selector`

`caseproc:1455–1458` — delete the `references` and `info` branches.

### 12c. Remove `render_references` function

`caseproc:672` — delete entirely.

### 12d. Tests

Remove or rewrite any tests that use `references` or `info` selectors.
Check: `grep -n 'references\|info' tests/run_tests.py`.

---

## Stage 14 — Update `--validate`

**Goal:** `--validate` now checks that every declared LTAC element has a
corresponding `element` selector in a processed document, rather than checking
for markdown headers.

The main change is in `main` (`caseproc:2234`):

```python
elif args.validate:
    state = DocState(doc_format='markdown')  # format varies per file below
    if document_files:
        # Process each file; accumulate seen_element_ids across files
        for path in document_files:
            state.doc_format = detect_doc_format(path)
            try:
                with open(path) as f:
                    process_document_stream(f, io.StringIO(),
                                           registry, all_roots, config,
                                           id_info, state)
            except OSError as e:
                error(f"cannot open {path!r}: {e}")
        _check_element_coverage(registry, state.seen_element_ids)
    if ltac_pair:
        commit_updates([ltac_pair])
```

Also update the `--help` text in `parse_args` (`caseproc:1676`) to describe the
new check.

---

## Stage 15 — `--missing` option

**Goal:** Add `--missing` to insert missing `element` regions and flag leaf
elements without `needsSupport`.

### 14a. Add `--missing` argument

`parse_args` (`caseproc:1694`) — add:
```python
mode.add_argument(
    '--missing', action='store_true',
    help='insert element selectors for missing elements and flag leaf elements '
         'with needsSupport',
)
```

### 14b. Add `_has_user_content(doc_text, element_id)`

```python
def _has_user_content(doc_text: str, element_id: str) -> bool:
    """Return False if the text after an element region contains only blanks
    and caseproc directives before the next element/package directive."""
    # Find the end marker for this element_id
    start_marker = f'<!-- caseproc element {element_id} -->'
    end_marker = '<!-- end caseproc -->'
    next_element_re = re.compile(
        r'<!--\s*caseproc\s+(?:element|package)\s')
    # Find after the end marker of this element's region
    pos = doc_text.find(start_marker)
    if pos == -1:
        return False  # not present at all
    pos = doc_text.find(end_marker, pos)
    if pos == -1:
        return False
    pos += len(end_marker)
    # Scan forward
    rest = doc_text[pos:]
    for line in rest.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if next_element_re.match(stripped):
            return False  # reached next element/package with no content
        if stripped.startswith('<!-- caseproc') or stripped.startswith('<!--caseproc'):
            continue  # other caseproc directives
        return True  # found real content
    return False  # end of file
```

### 14c. Add `_add_missing_elements(doc_text, missing_ids, all_roots, registry, id_info, config, doc_format)`

Appends `element` regions for each missing ID (in LTAC file order).
Inserts before `</body>` if HTML, else at end.

```python
def _add_missing_elements(doc_text: str, missing_ids: List[str],
                          registry, id_info, config, doc_format) -> str:
    state = DocState(doc_format=doc_format)
    insertions = []
    for ident in missing_ids:
        state.current_id = ident
        rendered = render_element_selector(ident, registry, [], id_info, config, state)
        block = (f'<!-- caseproc element {ident} -->\n'
                 f'{rendered}\n'
                 f'<!-- end caseproc -->\n')
        insertions.append(block)
    addition = '\n'.join(insertions)
    if doc_format == 'html':
        idx = doc_text.lower().rfind('</body>')
        if idx != -1:
            return doc_text[:idx] + addition + '\n' + doc_text[idx:]
    return doc_text + '\n' + addition
```

### 14d. Add `_mark_needs_support(missing_or_empty_ids, registry, id_info)`

```python
def _mark_needs_support(candidate_ids: List[str],
                        registry: Dict[str, Node],
                        id_info: Dict[str, dict]) -> int:
    """Add needsSupport to leaf elements with no assertion status.
    Returns count of elements modified."""
    _assertion_statuses = {'needssupport', 'assumed', 'axiomatic', 'defeated', 'ascited'}
    count = 0
    for ident in candidate_ids:
        node = registry.get(ident)
        if node is None:
            continue
        # Must be a leaf in its definition (no non-Link children)
        real_children = [c for c in node.children if c.node_type != 'Link']
        if real_children:
            continue
        # Must have no existing assertion status
        if node.options & _assertion_statuses:
            continue
        node.options.add('needssupport')
        count += 1
    return count
```

### 14e. Wire into `main`

In `main` (`caseproc:2150`), add a `--missing` branch after the default mode
block:

```python
if args.missing:
    # Process documents normally first
    seen_element_ids = set()
    for path in document_files:
        doc_format = detect_doc_format(path)
        # ... process, collect seen_element_ids, detect empty elements

    # Collect IDs not yet in any document (in LTAC order)
    all_ids_in_order = [n.identifier for n in _all_nodes(all_roots)
                        if not n.is_cited and n.identifier]
    missing_ids = [i for i in all_ids_in_order if i not in seen_element_ids]
    empty_ids = [i for i in seen_element_ids
                 if not _has_user_content(doc_text_cache[i], i)]

    # Append missing elements to last document
    if missing_ids and document_files:
        last = document_files[-1]
        # rewrite last file with additions

    # Mark needsSupport
    candidates = missing_ids + empty_ids
    changed = _mark_needs_support(candidates, registry, id_info)
    if changed:
        tmp = _make_temp(ltac_path, write_ltac(all_roots), ...)
        commit_updates([(tmp, ltac_path)])
```

### 14f. Tests

Add `TestMissingOption` class:
- `test_missing_adds_element_regions`
- `test_missing_adds_needs_support_to_leaf`
- `test_missing_does_not_add_needs_support_to_non_leaf`
- `test_missing_does_not_add_needs_support_if_already_has_status`

---

## Stage 16 — Documentation and `--help`

### 16a. Update `parse_args` epilog (`caseproc:1631`)

Replace the old selectors table:
```
Selectors are of format `KIND [ID | *]`, where KIND is:
  element        ID    heading + cross-references for one element
  package        ID|*  heading + diagram + index for one or all packages
  sacm           ID|*  SACM mermaid diagram (auto-detects markdown/HTML)
  sacm/mermaid/markdown  ID|*  explicit markdown fenced block
  sacm/mermaid/html      ID|*  explicit <pre class="mermaid"> block
  gsn            ID|*  GSN mermaid diagram (auto-detects format)
  ltac           ID|*  LTAC argument list (auto-detects format)
  ltac/markdown  ID|*  LTAC as Markdown bullet list
  ltac/html      ID|*  LTAC as HTML <ul> list
  statement      ID    one-line statement for an element
```

Update the "Configuration keys" section to list new keys and remove old ones.

Replace the description of additional document checks:
```
Additional checks when document files are provided:
  - Every declared LTAC element must have a corresponding
    '<!-- caseproc element ID -->' region in a processed document.
```

### 16b. Update `docs/reference.md`

Sections to rewrite:
- **Selectors** table: remove `references`, `info`; add `element`, `package`,
  `sacm`, `gsn`, `ltac` (shorthand forms); document three-part syntax.
- **Document headers**: replace with **Document integration** section describing
  `element`/`package` selectors, `caseproc-config` directives, and the removal
  of header scanning.
- **Configuration**: remove `update_headers`, `pkg_header_prefix`,
  `pkg_header_suffix`; add all new keys with defaults and descriptions.
- **`--validate`**: update to describe element-selector coverage checking.
- **`--missing`**: new section.

### 16c. Update `docs/ltac-extended.txt`

Already done in Stage 1.  Double-check that no other references to `[PkgName]`
remain.

---

## Summary of config key changes

| Key | Action | Default |
|---|---|---|
| `update_headers` | **Remove** | — |
| `default_renderer` | **Add** | `"mermaid"` |
| `default_representation` | **Add** | `"sacm"` |
| `element_level` | **Add** | `3` |
| `element_selections` | **Add** | `"referenced_by,supported_by,supports"` |
| `mermaid_js_url` | **Add** | `"https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"` |
| `package_level` | **Add** | `3` |
| `package_selections` | **Add** | `"representation,pkg_defines,pkg_citing,pkg_cited"` |
| `base_url` | Keep | `""` |
| `bottom_padding` | Keep | `true` |
| `document_files` | Keep | `[]` |
| `ltac_file` | Keep | `""` |
| `markdown_base_url` | Keep | `""` |
| `pkg_label` | Keep | `"Package "` |
| `pkg_header_prefix` | Keep (legacy for `--select sacm *`) | `"### "` |
| `pkg_header_suffix` | Keep (legacy) | `"\n"` |

---

## Summary of function changes

| Function | Action |
|---|---|
| `detect_line_ending` | **Add** (Stage 2) |
| `hyperlink` | **Add** (Stage 3) |
| `bold` | **Add** (Stage 3) |
| `detect_doc_format` | **Add** (Stage 4) |
| `expand_selector` | **Add** (Stage 6) |
| `_sacm_diagram_body` | **Add** (refactor from `render_sacm`, Stage 7) |
| `_gsn_diagram_body` | **Add** (refactor from `render_gsn`, Stage 7) |
| `render_sacm_html` | **Add** (Stage 7) |
| `render_gsn_html` | **Add** (Stage 7) |
| `DocState` dataclass | **Add** (Stage 7) |
| `_maybe_inject_mermaid_js` | **Add** (Stage 7) |
| `_pkg_anchor_url` | **Add** (Stage 8) |
| `_element_anchor_url` | **Add** (Stage 8) |
| `_find_citation_parents` | **Add** (Stage 8) |
| `render_referenced_by` | **Add** (Stage 8) |
| `render_supported_by` | **Add** (Stage 8) |
| `render_supports` | **Add** (Stage 8) |
| `render_pkg_defines` | **Add** (Stage 8) |
| `render_pkg_citing` | **Add** (Stage 8) |
| `render_pkg_cited` | **Add** (Stage 8) |
| `render_representation` | **Add** (Stage 8) |
| `_apply_selections` | **Add** (Stage 9) |
| `render_element_selector` | **Add** (Stage 9) |
| `render_package_selector` | **Add** (Stage 9) |
| `_render_single_package` | **Add** (Stage 9) |
| `_parse_header_text` | **Remove** (Stage 10) |
| `_check_header_coverage` | **Remove/replace** (Stage 10) |
| `_check_element_coverage` | **Add** (Stage 10) |
| `apply_config_directive` | **Add** (Stage 11) |
| `render_references` | **Remove** (Stage 12) |
| `_has_user_content` | **Add** (Stage 14) |
| `_add_missing_elements` | **Add** (Stage 14) |
| `_mark_needs_support` | **Add** (Stage 14) |

---

## Implementation order

| Stage | Topic | Tests after stage |
|---|---|---|
| 1 | Remove `[PackageIdentifier]` | Pass (fewer tests) |
| 2 | Line-ending preservation | Pass |
| 3 | `hyperlink` / `bold` utils | Pass |
| 4 | Doc format detection | Pass |
| 5 | New config keys | Pass |
| 6 | Three-part selector expansion | Pass |
| 7 | Mermaid HTML + JS injection | Pass |
| 8 | Selection renderers | Pass |
| 9 | `element` and `package` selectors | Pass |
| **10** | **Remove header scanning** | **Many tests broken** |
| **11** | **Transition tool + fixture migration** | **Pass again** |
| 12 | `caseproc-config` directive | Pass |
| 13 | Remove `references` / `info` selectors | Pass |
| 14 | Update `--validate` | Pass |
| 15 | `--missing` option | Pass |
| 16 | Docs + `--help` | Pass |

Stages 1–9 are fully additive; the test suite stays green throughout.
Stage 10 is the only breaking point; Stage 11 restores green immediately.
Stages 12–16 are independent of each other and can be done in any order.
