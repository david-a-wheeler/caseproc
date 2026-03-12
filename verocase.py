#!/usr/bin/env python3
"""verocase - process assurance case LTAC file and update Markdown/HTML

(C) Copyright David A. Wheeler and verocase contributors

SPDX-License-Identifier: MIT
"""

import argparse
import copy
import datetime
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

__version__ = '0.1.0'

# Python version support: we currently support Python 3.8 and later.
# Python 3.8 reached end-of-life on 2024-10-07, so we will eventually drop it.
# While supporting 3.8 we must avoid features introduced in later versions:
# - No X|Y union type syntax in annotations (e.g. "int | None"),
#   use Optional[X] instead; union syntax requires 3.10.
# - No lowercase built-in generics in annotations (e.g. list[int],
#   dict[str, int]); use typing.List, typing.Dict, etc. instead;
#   lowercase generics require 3.9.
# - No dict merge operator (d1 | d2), requires 3.9; use {**d1, **d2} instead.
# The walrus operator := is fine; it was introduced in 3.8.

# We generally perform validations as soon we have the information needed:
# - Per-line in _parse_line when reading LTAC file (e.g., valid indentation)
# - Per-node, in _build_node and _attach_node (e.g., parent compatibility)
# - After the LTAC is fully read (e.g., cycle detection)
# - After the documents are processed (e.g., to report uncovered elements)
# We want to report problems as soon as we can detect them.

# Implement panic/error/warning/notify reports

_had_error = False # If true, we saw an error during processing
_strict = False # If true, turn warnings into errors

def panic(msg: str) -> None:
    """Print a fatal error to stderr and exit immediately."""
    print(f"verocase: fatal: {msg}", file=sys.stderr)
    sys.exit(1)


def error(msg: str) -> None:
    """Print an error to stderr and set the error flag."""
    global _had_error
    print(f"verocase: error: {msg}", file=sys.stderr)
    _had_error = True


def warn(msg: str) -> None:
    """Print a warning to stderr; if --error is active, escalate to error()."""
    if _strict:
        error(msg)
    else:
        print(f"verocase: warning: {msg}", file=sys.stderr)


def notify(msg: str) -> None:
    """Print an informational notification to stderr."""
    print(f"verocase: {msg}", file=sys.stderr)


DEFAULT_CONFIG = {
    'base_url': '',
    'bottom_padding': True,
    'default_renderer': 'mermaid',
    'max_mermaid_children': 8,
    'narrowed_mermaid_children': 6,
    'default_representation': 'sacm',
    'document_files': [],
    'element_level': 3,
    'element_selections': 'referenced_by,supported_by,supports',
    'ltac_file': '',
    'markdown_base_url': '',
    'mermaid_js_url': 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs',
    'package_level': 3,
    'package_selections': 'representation,pkg_defines,pkg_citing,pkg_cited',
    'pkg_header_prefix': '### ',
    'pkg_header_suffix': '\n',
    'pkg_label': 'Package ',
    'max_backups': 20,
    'stats': False,
    'warn_dubious_reference': True,
}


def load_config(config_path: str) -> dict:
    """Load and validate configuration from a JSON file.

    If config_path is None, return a copy of DEFAULT_CONFIG.
    Unknown keys produce a warning; known keys are merged over the defaults.
    """
    if config_path is None:
        return dict(DEFAULT_CONFIG)
    try:
        with open(config_path, encoding='utf-8') as f:
            parsed = json.load(f)
    except FileNotFoundError:
        panic(f"--config file not found: {config_path!r}")
    except PermissionError:
        panic(f"--config file not readable: {config_path!r}")
    except json.JSONDecodeError as e:
        panic(f"invalid JSON in --config file {config_path!r}: {e}")
    if not isinstance(parsed, dict):
        panic(f"--config file must contain a JSON object, not {type(parsed).__name__}")
    for key in parsed:
        if key not in DEFAULT_CONFIG:
            warn(f"unknown config key: {key!r}")
    config = dict(DEFAULT_CONFIG)
    config.update({k: v for k, v in parsed.items() if k in DEFAULT_CONFIG})
    mb = config.get('max_backups')
    if not isinstance(mb, int) or mb < 0:
        warn(f"invalid value for max_backups: {mb!r}; using default {DEFAULT_CONFIG['max_backups']}")
        config['max_backups'] = DEFAULT_CONFIG['max_backups']
    return config


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _component_anchor_id(type_str: str, ident: str) -> str:
    """Return the stable GitHub anchor id for an assurance case component header.

    Uses only type and identifier (no statement text) so links remain valid
    even when the statement changes.

    >>> _component_anchor_id("Claim", "C1")
    'claim-c1'
    >>> _component_anchor_id("Package", "REQ")
    'package-req'
    """
    return to_github_fragment(f"{type_str} {ident}")


def to_github_fragment(text: str) -> str:
    """Convert heading text to a GitHub anchor fragment id.

    Algorithm (matches GitHub's algorithm):
    1. Lowercase the entire string.
    2. Remove every character that is not a Unicode letter, digit,
       hyphen, or space.
    3. Replace spaces with hyphens.
    4. Collapse runs of multiple hyphens into a single hyphen.
    5. Strip leading and trailing hyphens.

    >>> to_github_fragment("Package C1")
    'package-c1'
    >>> to_github_fragment("Claim C1: The software is acceptably safe")
    'claim-c1-the-software-is-acceptably-safe'
    >>> to_github_fragment("hello  world")
    'hello-world'
    >>> to_github_fragment("well-formed")
    'well-formed'
    """
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


# Mermaid flowchart node ID rules are defined by the NODE_STRING token in the
# flowchart JISON grammar.  Hyphens and dots are permitted in node IDs; only
# characters with syntactic meaning in Mermaid (spaces, brackets, edge markers,
# etc.) must be removed.  The reserved word "end" (all lowercase) breaks the
# parser and must be avoided.  Leading digits require an underscore prefix.
# Sources:
#   https://github.com/mermaid-js/mermaid/blob/develop/packages/mermaid/src/diagrams/flowchart/parser/flow.jison
#   https://mermaid.js.org/syntax/flowchart.html
def make_mermaid_id(identifier: str, counter: list) -> str:
    """Return a valid Mermaid node id for the given LTAC identifier.

    Hyphens and dots are preserved (both are legal in Mermaid node IDs).
    Spaces are converted to underscores; other characters that are syntactically
    meaningful in Mermaid (brackets, angle brackets, parentheses, braces) are
    removed.
    The reserved word 'end' is suffixed with '_' to avoid a Mermaid parse error.
    If the result is empty, generates '_auto{N}' using counter[0]++.
    Prefixes with underscore if the first character is a digit.

    >>> make_mermaid_id("C1", [0])
    'C1'
    >>> make_mermaid_id("AR-1.0", [0])
    'AR-1.0'
    >>> make_mermaid_id("hello world", [0])
    'hello_world'
    >>> make_mermaid_id("1st", [0])
    '_1st'
    >>> make_mermaid_id("end", [0])
    'end_'
    >>> make_mermaid_id("", [0])
    '_auto0'
    >>> make_mermaid_id("", [3])
    '_auto3'
    """
    if not identifier:
        idx = counter[0]
        counter[0] += 1
        return f'_auto{idx}'
    # Spaces become underscores; other Mermaid-syntax characters are removed.
    result = re.sub(r'\s', '_', identifier)
    result = re.sub(r'[()\[\]{}<>]', '', result)
    if not result:
        idx = counter[0]
        counter[0] += 1
        return f'_auto{idx}'
    if result[0].isdigit():
        result = '_' + result
    if result == 'end':
        result = 'end_'
    return result


_HTML_ESCAPE_TABLE = str.maketrans({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})


def escape_html(text: str) -> str:
    """Escape text for safe embedding in mermaid HTML labels.

    Replaces & -> &amp;  < -> &lt;  > -> &gt;  " -> &quot;

    >>> escape_html("safe text")
    'safe text'
    >>> escape_html('<b>Hello & "World"</b>')
    '&lt;b&gt;Hello &amp; &quot;World&quot;&lt;/b&gt;'
    >>> escape_html("a & b & c")
    'a &amp; b &amp; c'
    """
    return text.translate(_HTML_ESCAPE_TABLE)


def escape_html_content(text: str) -> str:
    """Escape text for use as HTML element content, preserving & for HTML entities.

    Only escapes < and >.  Ampersands are deliberately left alone so that
    HTML entities written in the LTAC source (e.g. &alpha;, &le;) survive
    into the rendered HTML output.

    >>> escape_html_content("x < 10 and y > 0")
    'x &lt; 10 and y &gt; 0'
    >>> escape_html_content("&alpha; &le; x &le; &beta;")
    '&alpha; &le; x &le; &beta;'
    >>> escape_html_content("[A] holds")
    '[A] holds'
    """
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def escape_markdown(text: str) -> str:
    """Escape characters that are special in Markdown inline syntax.

    Escapes backslash, [, ], and < so they appear as literals in
    rendered output and do not trigger link or HTML-tag parsing.

    >>> escape_markdown("plain text")
    'plain text'
    >>> escape_markdown("[A] holds")
    '\\\\[A\\\\] holds'
    >>> escape_markdown("x < 10")
    'x \\\\< 10'
    >>> escape_markdown("a & b")
    'a & b'
    """
    text = text.replace('\\', '\\\\')
    text = text.replace('[', '\\[')
    text = text.replace(']', '\\]')
    text = text.replace('<', '\\<')
    return text


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


def hyperlink(content: str, url: str, fmt: str) -> str:
    """Return a hyperlink in the given format ('markdown' or 'html').

    For markdown: [escaped content](url)
    For html:     <a href="url">escaped content</a>
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
        return f'<a href="{escape_html(url)}">{escape_html(content)}</a>'
    return f'[{escape_markdown(content)}]({url})'


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


def parse_options(raw: str) -> list:
    """Parse a {OPTIONS} suffix string into an ordered list of option names.

    raw is the content between { and } (already stripped of braces).
    Splits on commas, strips whitespace, lowercases each token.
    Preserves order; silently drops duplicates (keeping first occurrence).
    Returns a list of lowercase strings.

    >>> parse_options("counter, abstract")
    ['counter', 'abstract']
    >>> parse_options("DEFEATED")
    ['defeated']
    >>> parse_options("")
    []
    >>> parse_options("  ")
    []
    >>> parse_options("a, b, a")
    ['a', 'b']
    """
    if not raw.strip():
        return []
    seen: set = set()
    result = []
    for token in raw.split(','):
        t = token.strip().lower()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


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
    >>> detect_doc_format('case.markdown')
    'markdown'
    """
    low = path.lower()
    if low == '-' or low.endswith('.md') or low.endswith('.markdown'):
        return 'markdown'
    if low.endswith('.html') or low.endswith('.htm'):
        return 'html'
    panic(f"cannot determine document format from filename {path!r}; "
          f"expected .md, .markdown, .html, or .htm")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Node:
    node_type: str           # Claim|Strategy|Justification|Evidence|
                             # Context|Assumption|Link|Relation|Connector
    identifier: str          # e.g. "C1"; empty string if absent
    text: str                # descriptive text (statement / reasoning)
    ext_ref: str             # text from trailing (...), empty if absent
    options: List[str]       # e.g.: needssupport axiomatic defeated
                             #        counter abstract assumed (lowercased, ordered)
    children: List['Node']   # child nodes
    is_cited: bool           # True when identifier had a ^ prefix
    depth: int               # 0-based indentation level (0 = root)
    parent: Optional['Node'] # back-reference; None for roots
    link_target: Optional['Node']  # for Link nodes: referenced node
    diagram_id: str          # computed valid diagram node id for any renderer
    id_inferred: bool = False  # True when identifier was inferred from text


# ---------------------------------------------------------------------------
# LTAC parser
# ---------------------------------------------------------------------------

# Node types that cannot act as inference parents for Claims or Strategies.
# Used to warn about structurally invalid parent-child relationships.
_NON_INFERENTIAL_TYPES = frozenset({'Evidence', 'Context', 'Assumption', 'Justification'})
# Explicit assertion-status options (all lowercase, matching parse_options output).
_STATUS_OPTIONS = frozenset({'assumed', 'needssupport', 'axiomatic', 'defeated'})

def _infer_id(text: str) -> str:
    """Derive an LTAC identifier from element text for nodes with no explicit ID.

    Strips characters that are either illegal in LTAC identifiers per the spec
    (':' and '^') or that our parser treats as delimiters and would misread if
    the identifier were ever written back explicitly ('{', '}', '(', ')').
    Balanced removal of both open and close brackets keeps the set symmetric.
    Newlines are also stripped.  Spaces are preserved.
    """
    return ''.join(c for c in text if c not in ':^{}()\n\r')


# This parses an LTAC line with a regex, and pulls out relevant pieces.
# Compiled regexes perform well in Python.
_LTAC_LINE_RE = re.compile(
    r'^(?P<indent>(?:  )*)'
    r'[-] '
    r'(?P<nodetype>Claim|Strategy|Evidence|Justification'
    r'|Context|Assumption|Relation|Link|Connector)'
    r'(?:\s+(?P<cited>\^)?(?P<identifier>[^:{\n(]*))?'
    r'(?::\s*(?P<text>.*?))?'
    r'(?:\s*\{(?P<options>[^}\n]*)\})?'
    r'(?:\s*\((?P<ref>[^)\n]*)\))?'
    r'\s*$'
)


class LTACParser:
    def parse(self, lines: List[str], config: Optional[dict] = None) -> List[Node]:
        """Parse LTAC lines into a forest (list of root Nodes).

        Returns one root Node per package.
        Also populates self.registry: Dict[str, Node] mapping each
        non-cited identifier to its Node (for Link resolution), and
        self.id_info: Dict[str, dict] tracking per-identifier usage
        stats for post-parse validation.
        """
        self._warn_dubious_reference: bool = (config or {}).get('warn_dubious_reference', True)
        self.registry: Dict[str, Node] = {}
        self._anchor_seen: Dict[str, str] = {}  # anchor id -> first label that claimed it
        # id_info[ident] = {
        #   'declarations': int,       count of non-cited nodes with this ID
        #   'citations':    int,       count of cited (^) nodes with this ID
        #   'statement':    str|None,  first non-empty text seen for this ID
        #   'decl_lineno':  int|None,  line of first declaration
        # }
        self.id_info: Dict[str, dict] = {}
        self.results: List[Node] = []
        self.node_count: int = 0
        self._stack: List[Tuple[int, Node]] = []
        self._current_pkg: List[Node] = []
        self._pkg_root_lineno: Optional[int] = None
        self._id_counter: List[int] = [0]
        self._links: List[Tuple[Node, int]] = []
        # For empty-statement check (item 4): track declarations that usually
        # carry a statement (non-Link, non-Relation, non-cited) and whether
        # any such declaration has a non-empty statement.
        self._empty_decl_ids: List[Tuple[str, int]] = []
        self._has_nonempty_decl: bool = False

        for lineno, line in enumerate(lines, 1):
            self._parse_line(lineno, line)

        # Finalize last open package
        if self._stack or self._current_pkg:
            self._finalize_package()

        # Resolve Link targets (done after full parse so forward refs work)
        for node, lineno in self._links:
            self._resolve_link(node, lineno)

        # Warn about declarations with no statement when some declarations do
        # have statements (i.e. the mix is inconsistent; pure-ID demos are ok).
        if self._has_nonempty_decl and self._empty_decl_ids:
            for ident, ln in self._empty_decl_ids:
                warn(f"line {ln}: {ident!r}: declaration has no statement"
                     f" (other declarations do)")

        return self.results

    def _parse_line(self, lineno: int, line: str) -> None:
        """Process a single LTAC source line, updating parser state."""
        stripped = line.strip()
        if not stripped:
            if self._stack or self._current_pkg:
                self._finalize_package()
            return

        leading = len(line) - len(line.lstrip(' '))
        if leading % 2 != 0:
            error(f"line {lineno}: indentation must be an even number of spaces"
                  f" (got {leading}): {line.rstrip()!r}")
            return

        m = _LTAC_LINE_RE.match(line)
        if not m:
            error(f"line {lineno}: unrecognized syntax: {line.rstrip()!r}")
            return

        node = self._build_node(m, lineno)
        self._attach_node(node, lineno)

    def _build_node(self, m, lineno: int) -> Node:
        """Construct a Node from a successful regex match."""
        depth = len(m.group('indent')) // 2
        nodetype = m.group('nodetype')
        is_cited = bool(m.group('cited'))
        identifier = (m.group('identifier') or '').strip()
        has_colon = m.group('text') is not None
        text = (m.group('text') or '').strip()
        ref = (m.group('ref') or '').strip()
        options = parse_options(m.group('options') or '')

        if is_cited and not identifier:
            error(f"line {lineno}: citation requires an identifier (e.g. '- {nodetype} ^ID:')")
        elif not is_cited and nodetype not in ('Link', 'Connector') and not has_colon:
            error(f"line {lineno}: element requires ':' after the identifier (e.g. '- {nodetype} ID: text')")
        elif not is_cited and nodetype not in ('Link', 'Connector') and not identifier and not text:
            error(f"line {lineno}: {nodetype} element has no identifier and no statement;"
                  f" cannot contribute to the argument")

        id_inferred = False
        if not identifier and nodetype not in ('Link', 'Connector'):
            identifier = _infer_id(text)
            id_inferred = True

        diagram_id = make_mermaid_id(identifier, self._id_counter)

        node = Node(
            node_type=nodetype,
            identifier=identifier,
            text=text,
            ext_ref=ref,
            options=options,
            children=[],
            is_cited=is_cited,
            depth=depth,
            parent=None,
            link_target=None,
            diagram_id=diagram_id,
            id_inferred=id_inferred,
        )
        self.node_count += 1

        # Assertion status: SACM spec section 11 requires mutual exclusivity.
        active = _STATUS_OPTIONS.intersection(options)
        if nodetype == 'Assumption': active = active | {'assumed'}
        if is_cited:                 active = active | {'ascited'}
        if len(active) >= 2:
            label = identifier or f'(unnamed {nodetype})'
            error(f"line {lineno}: {label}: conflicting assertion status:"
                  f" {', '.join(sorted(active))} (mutually exclusive per SACM spec section 11)")

        # Dubious reference: warn if the reference looks like a parenthetical comment.
        if self._warn_dubious_reference and _is_dubious_reference(ref):
            label = f"{nodetype} {identifier}" if identifier else nodetype
            warn(f"line {lineno}: {label}: dubious reference ({ref!r}):"
                 f" has no '.' and doesn't start with '#'"
                 f" (looks like a parenthetical comment);"
                 f" use {{}} escape if intended")

        return node

    def _attach_node(self, node: Node, lineno: int) -> None:
        """Register the node's identifier, attach it to the tree, and push it onto the stack."""
        if node.node_type == 'Link':
            self._links.append((node, lineno))
        elif node.identifier:
            # Package root id: stack[0] is the root if the stack is non-empty;
            # if empty, the current node is (or will become) the package root.
            pkg_root_id = self._stack[0][1].identifier if self._stack else node.identifier
            info = self.id_info.setdefault(node.identifier, {
                'declarations':  0,
                'citations':     0,
                'statement':     None,
                'decl_lineno':   None,
                'decl_pkg_id':   None,   # pkg root id of the declaration
                'citing_pkg_ids': [],    # pkg root ids that cite this id, in order
                'node_type':     None,   # type on first use (declaration or citation)
            })
            # Type must be consistent across all uses of an ID.
            if info['node_type'] is None:
                info['node_type'] = node.node_type
            elif info['node_type'] != node.node_type:
                error(f"line {lineno}: {node.identifier!r}: type {node.node_type!r}"
                      f" conflicts with earlier use as {info['node_type']!r}")
            if node.is_cited:
                info['citations'] += 1
                if pkg_root_id and pkg_root_id not in info['citing_pkg_ids']:
                    info['citing_pkg_ids'].append(pkg_root_id)
            else:
                if info['declarations'] > 0:
                    warn(f"line {lineno}: duplicate declaration {node.identifier!r}")
                else:
                    info['decl_lineno'] = lineno
                    info['decl_pkg_id'] = pkg_root_id
                    self.registry[node.identifier] = node
                    anchor = _component_anchor_id(node.node_type, node.identifier)
                    label = f"{node.node_type} {node.identifier}"
                    if anchor in self._anchor_seen:
                        error(f"line {lineno}: anchor id collision on {anchor!r}:"
                              f" {self._anchor_seen[anchor]!r} and {label!r}")
                    else:
                        self._anchor_seen[anchor] = label
                info['declarations'] += 1
                # Track empty/non-empty statements for declarations that
                # normally carry a statement (not Relation, not Link).
                if node.node_type != 'Relation':
                    if node.text:
                        self._has_nonempty_decl = True
                    else:
                        self._empty_decl_ids.append((node.identifier, lineno))
            if node.text:
                if info['statement'] is None:
                    info['statement'] = node.text
                elif node.text != info['statement']:
                    hint = "; use --update to sync" if (node.is_cited or info['citations'] > 0) else ""
                    warn(f"line {lineno}: {node.identifier!r}: statement {node.text!r}"
                         f" differs from earlier statement {info['statement']!r}{hint}")

        # Pop stack until top's depth < current depth
        while self._stack and self._stack[-1][0] >= node.depth:
            self._stack.pop()

        # Validate depth: must not jump more than one level deeper than parent.
        if self._stack:
            parent_depth = self._stack[-1][0]
            if node.depth > parent_depth + 1:
                error(f"line {lineno}: indentation jumps from depth {parent_depth}"
                      f" to depth {node.depth} (increase must be exactly 2 spaces / 1 level)")
        elif node.depth > 0:
            error(f"line {lineno}: indentation is {node.depth * 2} spaces but"
                  f" there is no parent node to attach to")

        if self._stack:
            parent_node = self._stack[-1][1]
            if (node.node_type in ('Claim', 'Strategy')
                    and parent_node.node_type in _NON_INFERENTIAL_TYPES):
                warn(f"line {lineno}: {node.node_type} should not be"
                     f" a child of {parent_node.node_type}")
            # Evidence is a leaf node; non-metadata children are invalid.
            # Claim and Strategy are excluded here because the _NON_INFERENTIAL_TYPES
            # check above already warns when they appear under Evidence, avoiding
            # a duplicate warning for the same issue.
            if (parent_node.node_type == 'Evidence'
                    and node.node_type not in ('Claim', 'Strategy',
                                               'Context', 'Relation', 'Link')):
                warn(f"line {lineno}: {node.node_type} should not be a child of"
                     f" Evidence (Evidence is a leaf node)")
            node.parent = parent_node
            if node.identifier:
                parent_label = (f" under {parent_node.identifier!r}"
                                if parent_node.identifier else "")
                for sib in parent_node.children:
                    if sib.identifier == node.identifier:
                        warn(f"line {lineno}: duplicate sibling identifier"
                             f" {node.identifier!r}{parent_label}")
            if node.is_cited and node.node_type not in ('Claim', 'Justification'):
                warn(f"line {lineno}: external citation ^{node.identifier!r} has type"
                     f" {node.node_type!r}; only Claim and Justification are"
                     f" recommended for cross-package citations")
            parent_node.children.append(node)
        else:
            if self._current_pkg:
                panic(
                    f"package starting at line {self._pkg_root_lineno} "
                    f"already has a top-level element; only one allowed"
                )
            if node.node_type not in ('Claim', 'Justification'):
                warn(f"line {lineno}: {node.node_type} {node.identifier!r}:"
                     f" package starts with {node.node_type!r};"
                     f" expected Claim or Justification")
            self._current_pkg.append(node)
            self._pkg_root_lineno = lineno

        self._stack.append((node.depth, node))

    def _resolve_link(self, node: Node, lineno: int) -> None:
        """Set link_target on a Link node, warning if the target is unknown."""
        target_id = node.identifier
        if target_id in self.registry:
            node.link_target = self.registry[target_id]
            canonical = self.id_info.get(target_id, {}).get('statement')
            if node.text and canonical is not None and node.text != canonical:
                warn(f"line {lineno}: Link {target_id!r}: statement {node.text!r}"
                     f" differs from declaration; use --update to sync")
        else:
            warn(f"line {lineno}: Link target {target_id!r} not found")

    def _finalize_package(self) -> None:
        """Flush the current package's root into results and reset package state."""
        self.results.extend(self._current_pkg)
        self._current_pkg = []
        self._pkg_root_lineno = None
        self._stack = []


def parse_ltac_lines(lines: List[str], config: Optional[dict] = None) -> Tuple[List[Node], Dict[str, Node], Dict[str, dict]]:
    """Parse LTAC lines and return (roots, registry, id_info)."""
    parser = LTACParser()
    roots = parser.parse(lines, config=config)
    return roots, parser.registry, parser.id_info


def _all_nodes(roots: List[Node]):
    """Yield every node in the forest in depth-first order."""
    stack = list(roots)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children)


def _all_nodes_forward(roots: List[Node]):
    """Yield every node in the forest in LTAC (as-written) depth-first order.

    Unlike _all_nodes, this preserves first-child-first order matching the
    order elements appear in the LTAC file.
    """
    stack = list(reversed(roots))
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _recalc_depths(node: 'Node', new_depth: int) -> None:
    """Recursively update depth for node and all descendants."""
    node.depth = new_depth
    for child in node.children:
        _recalc_depths(child, new_depth + 1)


# ---------------------------------------------------------------------------
# LTAC file loader
# ---------------------------------------------------------------------------

def load_ltac_file(path: str, all_roots: List[Node], registry: Dict[str, Node],
                   id_info: Dict[str, dict], config: Optional[dict] = None) -> None:
    """Parse an LTAC file and merge its roots, registry, and id_info into the given collections."""
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError as e:
        panic(f"cannot open {path!r}: {e}")
    roots, new_registry, new_id_info = parse_ltac_lines(lines, config=config)
    all_roots.extend(roots)
    for ident, node in new_registry.items():
        if ident in registry:
            warn(f"{path}: duplicate declaration {ident!r} (already declared in a previous file)")
        else:
            registry[ident] = node
    for ident, new in new_id_info.items():
        if ident in id_info:
            existing = id_info[ident]
            if new['declarations'] > 0 and existing['declarations'] > 0:
                warn(f"{path}: duplicate declaration {ident!r} (already declared in a previous file)")
            existing['declarations'] += new['declarations']
            existing['citations']    += new['citations']
            if new['statement'] and existing['statement'] and new['statement'] != existing['statement']:
                warn(f"{path}: {ident!r}: statement differs from earlier statement")
            elif new['statement'] and not existing['statement']:
                existing['statement'] = new['statement']
            if new['decl_pkg_id'] and not existing['decl_pkg_id']:
                existing['decl_pkg_id'] = new['decl_pkg_id']
            for pkg_id in new['citing_pkg_ids']:
                if pkg_id not in existing['citing_pkg_ids']:
                    existing['citing_pkg_ids'].append(pkg_id)
        else:
            id_info[ident] = new


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _node_anchor_url(node: Node, base_url: str, pkg_label: str) -> str:
    """Return the anchor URL for a node: base_url + '#' + GitHub fragment.

    Returns '' if the node has no identifier.  Works with base_url='' to
    produce pure fragment links (e.g. '#claim-c1-the-software-is-acceptably-safe').

    Cited nodes (^ID) link to the cited package's section header
    (e.g. '#package-requirements'), since they represent an external reference.
    Declared nodes link to the element's own content heading
    (e.g. '#claim-c1-the-software-is-acceptably-safe'), regardless of depth.
    """
    if not node.identifier:
        return ''
    if node.is_cited:
        heading = f"{pkg_label}{node.identifier}"
    else:
        # No statement text: keeps links stable when statements change.
        heading = f"{node.node_type} {node.identifier}"
    return base_url + '#' + to_github_fragment(heading)


def _resolve_ext_ref(ext_ref: str, base_url: str) -> str:
    """Resolve an ext_ref to its click-target URL.

    Absolute references (http://, https://, file:///, or a leading /) are
    returned unchanged.  A relative reference is resolved against the
    directory portion of base_url when base_url is non-empty, so that
    'hara.pdf' becomes the full URL to that file alongside the document.
    When base_url is empty the relative reference is returned unchanged.
    """
    if (ext_ref.startswith('http://')
            or ext_ref.startswith('https://')
            or ext_ref.startswith('file:///')
            or ext_ref.startswith('/')):
        return ext_ref
    if base_url:
        base_dir = base_url.rsplit('/', 1)[0]
        return base_dir + '/' + ext_ref
    return ext_ref


def _node_url(node: Node, base_url: str, pkg_label: str = DEFAULT_CONFIG['pkg_label']) -> str:
    """Return the hyperlink URL for a node, or '' if none can be determined.

    If the node has an ext_ref, it is resolved via _resolve_ext_ref (relative
    refs are joined with the directory of base_url when base_url is set).
    Otherwise a URL is constructed from base_url and a GitHub-style fragment.
    Returns '' when base_url is empty and no ext_ref is present.
    """
    if node.ext_ref:
        return _resolve_ext_ref(node.ext_ref, base_url)
    if not base_url:
        return ''
    return _node_anchor_url(node, base_url, pkg_label)


def _render_markdown_node(node: Node, indent: int, base_url: str, lines: list,
                          pkg_label: str = DEFAULT_CONFIG['pkg_label']) -> None:
    """Append a markdown bullet for node and recurse into its children.

    The full 'Type ID: text' label links to its document anchor.  If the node
    has an ext_ref, it is appended as a separate parenthetical link.
    Link nodes are silently skipped (they are citations, not new bullets).
    """
    if node.node_type == 'Link':
        return
    label = node.node_type
    if node.identifier:
        label += f' {node.identifier}'
    if node.text:
        label += f': {node.text}'
    # Anchor uses type+ID only (no statement) for stability across statement changes.
    anchor = (base_url + '#' + to_github_fragment(f"{node.node_type} {node.identifier}")) if node.identifier else ''
    display = escape_markdown(label)
    main = f'[{display}]({anchor})' if anchor else display
    ref_ext = node.ext_ref or ''
    ref_part = f' ([{escape_markdown(ref_ext)}]({ref_ext}))' if ref_ext else ''
    lines.append('  ' * indent + f'- {main}{ref_part}')
    for child in node.children:
        _render_markdown_node(child, indent + 1, base_url, lines, pkg_label)


def render_markdown(roots: List[Node], config: dict) -> str:
    """Render a list of nodes as an indented markdown bullet list with hyperlinks.

    Each item is '- NodeType ID: text' where ID is a hyperlink when a URL
    is available (from ext_ref, or constructed from base_url + anchor).
    Link nodes are skipped.
    """
    base_url = config.get('markdown_base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    lines = []
    for root in roots:
        _render_markdown_node(root, 0, base_url, lines, pkg_label)
    return '\n'.join(lines)


def render_statement(node: Node) -> str:
    """Return a markdown 'Statement:' line for the node's text."""
    return f"Statement: {node.text}"


def _render_html_node(node: Node, indent: int, base_url: str, lines: list,
                      pkg_label: str = DEFAULT_CONFIG['pkg_label']) -> None:
    """Append HTML li element for node and recurse into its children.

    The full 'Type ID: text' label links to its document anchor.  If the node
    has an ext_ref, it is appended as a separate parenthetical link.
    Link nodes are silently skipped.
    """
    if node.node_type == 'Link':
        return
    label = node.node_type
    if node.identifier:
        label += f' {node.identifier}'
    if node.text:
        label += f': {node.text}'
    if node.identifier:
        # Anchor uses type+ID only (no statement) for stability across statement changes.
        anchor = base_url + '#' + to_github_fragment(f"{node.node_type} {node.identifier}")
        main = f'<a href="{escape_html(anchor)}">{escape_html_content(label)}</a>'
    else:
        main = escape_html_content(label)
    if node.ext_ref:
        main += (f' (<a href="{escape_html(node.ext_ref)}">'
                 f'{escape_html_content(node.ext_ref)}</a>)')
    content = main
    prefix = '  ' * indent
    visible_children = [c for c in node.children if c.node_type != 'Link']
    if visible_children:
        lines.append(f'{prefix}<li>{content}')
        lines.append(f'{prefix}<ul>')
        for child in node.children:
            _render_html_node(child, indent + 1, base_url, lines, pkg_label)
        lines.append(f'{prefix}</ul>')
        lines.append(f'{prefix}</li>')
    else:
        lines.append(f'{prefix}<li>{content}</li>')


def render_html(roots: List[Node], config: dict) -> str:
    """Render a list of nodes as a nested HTML ul/li list with hyperlinks.

    Link nodes are skipped. Identifiers are hyperlinked when a URL is available.
    """
    base_url = config.get('markdown_base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    lines = ['<ul>']
    for root in roots:
        _render_html_node(root, 1, base_url, lines, pkg_label)
    lines.append('</ul>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Mermaid diagram shared utilities
# ---------------------------------------------------------------------------

def _copy_forest(roots: List['Node']) -> List['Node']:
    """Return an independent deep copy of the node forest.

    Uses copy.deepcopy so all internal back-references (parent, link_target,
    children) are remapped to copied nodes.  The originals are untouched,
    allowing other renderers (ltac/markdown, GSN, …) to use them normally.
    """
    return copy.deepcopy(roots)


def _collect_bfs(roots: List['Node']) -> List['Node']:
    """Return every node in the forest in BFS order (roots first)."""
    result = []
    q = deque(roots)
    while q:
        node = q.popleft()
        result.append(node)
        q.extend(node.children)
    return result


def _make_syn_connector(children: List['Node'], parent: 'Node',
                        counter: list) -> 'Node':
    """Create a synthetic Connector node that groups *children*.

    counter is a one-element list [int] incremented on each call so IDs are
    unique within a rendering pass (e.g. SynConnect_00000000, _00000001, …).
    The returned node is NOT yet inserted into parent.children; the caller
    is responsible for insertion.  Each child's .parent is updated here.
    """
    conn_id = f'SynConnect_{counter[0]:08x}'
    counter[0] += 1
    connector = Node(
        node_type='Connector',
        identifier='',
        text='',
        ext_ref='',
        options=[],
        children=list(children),
        is_cited=False,
        depth=parent.depth + 1,
        parent=parent,
        link_target=None,
        diagram_id=conn_id,
    )
    for child in children:
        child.parent = connector
    return connector


def _sacm_effective_sources(
    node: 'Node',
) -> List[Tuple['Node', 'Node']]:
    """Return (src, tree_parent) for each node in node's SACM inference group.

    Mirrors _sacm_collect_edges inference_sources logic without emitting edges.
    Counter/abstract options are intentionally ignored (only counts matter here).
    """
    sources: List[Tuple['Node', 'Node']] = []
    for child in node.children:
        if child.node_type == 'Context':
            pass
        elif child.node_type == 'Strategy':
            for gc in child.children:
                if gc.node_type == 'Context':
                    pass
                elif gc.node_type == 'Relation':
                    for ggc in gc.children:
                        if ggc.node_type not in ('Context', 'Relation', 'Link'):
                            sources.append((ggc, gc))
                elif gc.node_type not in ('Relation', 'Link'):
                    sources.append((gc, child))
            sources.append((child, node))
        elif child.node_type == 'Relation':
            for gc in child.children:
                if gc.node_type not in ('Context', 'Relation', 'Link'):
                    sources.append((gc, child))
        elif child.node_type != 'Link':
            sources.append((child, node))
    return sources


def _gsn_visual_children(
    node: 'Node',
) -> List[Tuple['Node', 'Node']]:
    """Return (child, tree_parent) for each visually-expressed child in GSN.

    Counts direct non-Link, non-Relation children (with parent=node), plus
    non-Link grandchildren of Relation children (with parent=Relation child).
    Link targets are cross-package citations and are not counted.
    """
    result: List[Tuple['Node', 'Node']] = []
    for child in node.children:
        if child.node_type == 'Link':
            pass
        elif child.node_type == 'Relation':
            for gc in child.children:
                if gc.node_type != 'Link':
                    result.append((gc, child))
        else:
            result.append((child, node))
    return result


def _insert_connectors_for_overflow(
    overflow: List[Tuple['Node', 'Node']],
    counter: list,
) -> None:
    """Group overflow items by tree-parent; create one Connector per group.

    Removes overflow items from their parent's children list and inserts a
    synthetic Connector at the position of the first removed item.
    counter is passed to _make_syn_connector to produce unique IDs.
    """
    groups: Dict[int, Tuple['Node', List['Node']]] = {}
    for src, parent in overflow:
        pid = id(parent)
        if pid not in groups:
            groups[pid] = (parent, [])
        groups[pid][1].append(src)

    for parent, items in groups.values():
        item_ids = {id(n) for n in items}
        first_pos = next(
            i for i, c in enumerate(parent.children) if id(c) in item_ids
        )
        for src in items:
            parent.children.remove(src)
        connector = _make_syn_connector(items, parent, counter)
        parent.children.insert(first_pos, connector)


def _get_width_config(config: dict) -> tuple:
    """Return (max_mermaid_children, narrowed_mermaid_children) from config."""
    return (
        config.get('max_mermaid_children', DEFAULT_CONFIG['max_mermaid_children']),
        config.get('narrowed_mermaid_children', DEFAULT_CONFIG['narrowed_mermaid_children']),
    )


def _apply_sacm_width_transform(roots: List['Node'], config: dict,
                                counter: list) -> None:
    """Narrow SACM inference groups that exceed max_mermaid_children.

    Operates in-place on the deep-copied forest.  Inserts synthetic Connector
    nodes to group middle overflow children.  Recurses into all children so
    that nested over-wide groups are narrowed too.
    counter is a one-element list [int] used to generate unique Connector IDs.
    """
    max_ch, narrowed = _get_width_config(config)
    if max_ch == 0:
        return

    def _transform(node: 'Node') -> None:
        if node.node_type in ('Link', 'Relation'):
            return
        while True:
            sources = _sacm_effective_sources(node)
            if len(sources) <= max_ch:
                break
            n_left = narrowed // 2
            n_right = narrowed - n_left
            overflow = sources[n_left: len(sources) - n_right]
            _insert_connectors_for_overflow(overflow, counter)
        for child in list(node.children):
            _transform(child)

    for root in roots:
        _transform(root)


def _apply_gsn_width_transform(roots: List['Node'], config: dict,
                               counter: list) -> None:
    """Narrow GSN nodes that have too many visual children.

    Operates in-place on the deep-copied forest.
    counter is a one-element list [int] used to generate unique Connector IDs.
    """
    max_ch, narrowed = _get_width_config(config)
    if max_ch == 0:
        return

    def _transform(node: 'Node') -> None:
        if node.node_type in ('Link', 'Relation'):
            return
        while True:
            children = _gsn_visual_children(node)
            if len(children) <= max_ch:
                break
            n_left = narrowed // 2
            n_right = narrowed - n_left
            overflow = children[n_left: len(children) - n_right]
            _insert_connectors_for_overflow(overflow, counter)
        for child in list(node.children):
            _transform(child)

    for root in roots:
        _transform(root)


def _edge_line(src_id: str, tgt_id: str, is_context: bool,
               counter: bool = False, abstract: bool = False) -> str:
    """Return a directed edge line (with arrowhead) from src to tgt.

    is_context → circle head (--o); otherwise arrow head (-->).
    counter    → adds |⊖| label on the edge.
    abstract   → uses dashed line style (-.- prefix).

    >>> _edge_line("A", "B", False)
    '    A --> B'
    >>> _edge_line("A", "B", True)
    '    A --o B'
    >>> _edge_line("A", "B", False, counter=True)
    '    A -->|⊖| B'
    >>> _edge_line("A", "B", True, abstract=True)
    '    A -.-o B'
    >>> _edge_line("A", "B", False, counter=True, abstract=True)
    '    A -.->|⊖| B'
    """
    base = ('-.-o' if abstract else '--o') if is_context else ('-.->' if abstract else '-->')
    arrow = f'{base}|⊖|' if counter else base
    return f'    {src_id} {arrow} {tgt_id}'


# ---------------------------------------------------------------------------
# SACM/mermaid renderer (step 9)
# ---------------------------------------------------------------------------

# Hair space (U+200A): required inside sacmDot and Connector nodes.
_HAIR_SPACE = '\u200a'


def _sacm_assertion_suffix(node_type: str, options: List[str]) -> str:
    """Return the mermaid assertion-state suffix for the given node type and options.

    Valid nodes carry at most one assertion status (enforced by
    check_assertion_status).  The order below is a rendering fallback only.
    Assumption node type is treated as "assumed" regardless of options.

    >>> _sacm_assertion_suffix('Claim', {'defeated'})
    '<br>✗'
    >>> _sacm_assertion_suffix('Claim', {'axiomatic'})
    '<br>━━━'
    >>> _sacm_assertion_suffix('Assumption', set())
    '<br>ASSUMED'
    >>> _sacm_assertion_suffix('Claim', {'assumed'})
    '<br>ASSUMED'
    >>> _sacm_assertion_suffix('Claim', {'needssupport'})
    '<br>...'
    >>> _sacm_assertion_suffix('Claim', set())
    ''
    """
    if 'defeated' in options:
        return '<br>✗'
    elif 'axiomatic' in options:
        return '<br>━━━'
    elif node_type == 'Assumption' or 'assumed' in options:
        return '<br>ASSUMED'
    elif 'needssupport' in options:
        return '<br>...'
    else:
        return ''


def _build_inner_label(eid: str, etxt: str, suffix: str,
                       decorator: str = '') -> str:
    """Build the inner HTML label for a Mermaid node.

    eid:       escaped identifier (may be empty)
    etxt:      escaped statement text (may be empty)
    suffix:    assertion suffix from _sacm/_gsn_assertion_suffix (may be '')
    decorator: optional type badge inserted after the bold ID (e.g. '&nbsp;Ⓐ')
    """
    if eid and etxt:
        return f'<b>{eid}</b>{decorator}<br>{etxt}{suffix}'
    elif eid:
        return f'<b>{eid}</b>{decorator}{suffix}'
    elif etxt:
        return f'{etxt}{suffix}'
    else:
        return suffix.removeprefix('<br>') if suffix else ''


def _sacm_node_decl(node: 'Node') -> str:
    """Return the mermaid node-declaration line for a single LTAC node.

    Returns '' for Relation and Link nodes (they produce no mermaid declaration).
    diagram_id must already be set on the node.
    """
    if node.node_type in ('Relation', 'Link'):
        return ''

    if node.node_type == 'Connector':
        return f'    {node.diagram_id}(("{_HAIR_SPACE}")):::connector'

    did = node.diagram_id
    eid = escape_html(node.identifier) if node.identifier else ''
    etxt = escape_html(node.text) if node.text else ''
    opts = node.options

    suffix = _sacm_assertion_suffix(node.node_type, opts)

    # Evidence and Context use the cylinder shape with a &nbsp;↗ after the ID.
    if node.node_type in ('Evidence', 'Context'):
        inner = _build_inner_label(eid, etxt, suffix, decorator='&nbsp;↗')
        shape = f'[("{inner}")]'
    else:
        # Claim, Strategy, Assumption, Justification
        inner = _build_inner_label(eid, etxt, suffix)
        if node.node_type == 'Strategy':
            shape = f'[/"{inner}"/]'
        elif node.is_cited:
            shape = f'[["{inner}"]]'
        else:
            # Claim, Assumption, Justification all use plain rectangle
            shape = f'["{inner}"]'

    abstract_cls = ':::abstractClaim' if 'abstract' in opts else ''
    return f'    {did}{shape}{abstract_cls}'


# Standard mermaid YAML frontmatter and opening classDef lines shared by all
# sacm/mermaid diagrams.  The closing ``` fence is appended by render_sacm().
_SACM_HEADER = """\
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: linear
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart BT
    classDef invisible opacity:0
    classDef sacmDot fill:#000,stroke:#000
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;
    classDef abstractClaim stroke-width:2px,stroke-dasharray: 5 5;"""


def _sacm_source_edge(src_id: str, dot_id: str, abstract: bool = False) -> str:
    """Return an undirected source edge (--- or -.-) from a node to a sacmDot.

    abstract → dashed (-.-).  Counter is reflected on the Dot→target edge.

    >>> _sacm_source_edge("A", "Dot1")
    '    A --- Dot1'
    >>> _sacm_source_edge("A", "Dot1", abstract=True)
    '    A -.- Dot1'
    """
    return f'    {src_id} {"-.-" if abstract else "---"} {dot_id}'


def _sacm_collect_edges(
    node: 'Node',
    dot_counter: list,
    dot_decls: list,
    edge_lines: list,
) -> None:
    """Collect sacmDot declarations and edges for *node* and its subtree.

    Edges are appended in DFS post-order (deepest leaves first, so the last
    edge written connects to the top-level root).

    Special node-type rules:
    - Connector: children connect to it with '---'; Connector is a source in
      its parent's group.
    - Strategy: children are absorbed into the *grandparent's* inference group;
      no inference edges emitted at the Strategy level.
    - Relation: children are absorbed into the *parent's* inference group with
      Relation's counter/abstract options applied to their edges; Relation
      produces no mermaid node declaration.
    - Link: skipped entirely.
    """
    if node.node_type == 'Connector':
        for child in node.children:
            if child.node_type != 'Link':
                _sacm_collect_edges(child, dot_counter, dot_decls, edge_lines)
        for child in node.children:
            if child.node_type != 'Link':
                edge_lines.append(f'    {child.diagram_id} --- {node.diagram_id}')
        return

    if node.node_type in ('Strategy', 'Relation'):
        # Just recurse; the enclosing Claim handles edge emission for this group.
        for child in node.children:
            if child.node_type != 'Link':
                _sacm_collect_edges(child, dot_counter, dot_decls, edge_lines)
        return

    # --- Build this node's inference group ---
    # Each entry is (node, counter:bool, abstract:bool).

    # context_children: list of (ctx_node, counter, abstract)
    context_children: list = []
    # strategy_children: list of Strategy Node objects (for context-edge emission)
    strategy_children: list = []
    # strategy_ctx: strategy.diagram_id → [(ctx_node, counter, abstract)]
    strategy_ctx: Dict[str, list] = {}
    # inference_sources: list of (node, counter, abstract)
    inference_sources: list = []

    for child in node.children:
        if child.node_type == 'Context':
            context_children.append((child, 'counter' in child.options, False))

        elif child.node_type == 'Strategy':
            strategy_children.append(child)
            ctx_of_s: list = []
            for gc in child.children:
                if gc.node_type == 'Context':
                    ctx_of_s.append((gc, 'counter' in gc.options, False))
                elif gc.node_type == 'Relation':
                    rc, ra = 'counter' in gc.options, 'abstract' in gc.options
                    for ggc in gc.children:
                        if ggc.node_type == 'Context':
                            ctx_of_s.append((ggc, rc, ra))
                        elif ggc.node_type not in ('Relation', 'Link'):
                            inference_sources.append((ggc, rc, ra))
                elif gc.node_type not in ('Relation', 'Link'):
                    inference_sources.append((gc, 'counter' in gc.options, False))
            inference_sources.append((child, 'counter' in child.options, False))
            strategy_ctx[child.diagram_id] = ctx_of_s

        elif child.node_type == 'Relation':
            rc, ra = 'counter' in child.options, 'abstract' in child.options
            for gc in child.children:
                if gc.node_type == 'Context':
                    context_children.append((gc, rc, ra))
                elif gc.node_type not in ('Relation', 'Link'):
                    inference_sources.append((gc, rc, ra))

        elif child.node_type != 'Link':
            inference_sources.append((child, 'counter' in child.options, False))

    # Recurse into all non-Link children first (post-order: deepest edges first).
    for child in node.children:
        if child.node_type != 'Link':
            _sacm_collect_edges(child, dot_counter, dot_decls, edge_lines)

    # Emit inference edges for this node.
    if len(inference_sources) == 1:
        src, is_counter, is_abstract = inference_sources[0]
        edge_lines.append(_edge_line(
            src.diagram_id, node.diagram_id, False, is_counter, is_abstract))
    elif len(inference_sources) >= 2:
        dot_id = f'Dot{dot_counter[0]}'
        dot_counter[0] += 1
        any_counter = any(c for _, c, _ in inference_sources)
        any_abstract = any(a for _, _, a in inference_sources)
        dot_decls.append(f'    {dot_id}(("{_HAIR_SPACE}")):::sacmDot')
        for src, _, is_abstract in inference_sources:
            edge_lines.append(_sacm_source_edge(src.diagram_id, dot_id, is_abstract))
        dot_arrow = (
            '-.->|⊖|' if (any_abstract and any_counter) else
            '-.->'     if any_abstract else
            '-->|⊖|'   if any_counter  else '-->'
        )
        edge_lines.append(f'    {dot_id} {dot_arrow} {node.diagram_id}')

    # Emit context edges: direct Context children → this node.
    for ctx, is_counter, is_abstract in context_children:
        edge_lines.append(
            _edge_line(ctx.diagram_id, node.diagram_id, True, is_counter, is_abstract))

    # Emit context edges: Context children of Strategy children → that Strategy.
    for s in strategy_children:
        for ctx, is_counter, is_abstract in strategy_ctx.get(s.diagram_id, []):
            edge_lines.append(
                _edge_line(ctx.diagram_id, s.diagram_id, True, is_counter, is_abstract))


def _sacm_leftmost_leaf(node: 'Node') -> 'Node':
    """Return the leftmost deepest rendered leaf in the subtree.

    Follows the first non-Link child recursively, so that the result is the
    node that appears at the bottom-left of the BT diagram.
    """
    for child in node.children:
        if child.node_type != 'Link':
            return _sacm_leftmost_leaf(child)
    return node


def _sacm_diagram_body(roots: List['Node'], config: dict) -> str:
    """Return the SACM diagram content without opening/closing fence markers."""
    base_url = config.get('base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    bottom_padding = config.get('bottom_padding', DEFAULT_CONFIG['bottom_padding'])
    roots = _copy_forest(roots)
    syn_counter = [0]
    _apply_sacm_width_transform(roots, config, syn_counter)

    # Node declarations (BFS) and click lines collected in a single pass.
    node_decl_lines = []
    click_lines = []
    for node in _collect_bfs(roots):
        decl = _sacm_node_decl(node)
        if decl:
            node_decl_lines.append(decl)
        if node.node_type not in ('Relation', 'Link'):
            url = _node_url(node, base_url, pkg_label)
            if url:
                click_lines.append(f'    click {node.diagram_id} "{url}"')

    # Collect sacmDot declarations and edges via the inference group algorithm.
    dot_counter = [1]
    dot_decls: list = []
    edge_lines: list = []
    for root in roots:
        _sacm_collect_edges(root, dot_counter, dot_decls, edge_lines)

    # The invisible BottomPadding node prevents GitHub's diagram controls from
    # obscuring the bottom of the diagram; it must be the first edge line.
    # Link it to the leftmost bottommost leaf so it sits at the bottom-left.
    if bottom_padding and roots:
        bottom_node = _sacm_leftmost_leaf(roots[0])
        edge_lines.insert(0, f'    BottomPadding[ ]:::invisible ~~~ {bottom_node.diagram_id}')

    # Build body: header content (minus the opening fence line) + nodes + edges.
    body_header = _SACM_HEADER[len('```mermaid\n'):]
    lines = [body_header]
    lines.extend(node_decl_lines)
    lines.extend(dot_decls)
    lines.extend(click_lines)
    if edge_lines:
        lines.append('')  # blank line between declarations and edges
        lines.extend(edge_lines)
    return '\n'.join(lines)


def render_sacm(roots: List['Node'], config: dict) -> str:
    """Render package roots as a complete SACM/mermaid code block.

    Returns the full mermaid fenced block (opening ```mermaid … closing ```).
    The original nodes are not modified; a deep copy is used internally.
    Output structure: header → node declarations (BFS) → sacmDot declarations
    → click lines → blank line → BottomPadding + edges (DFS post-order, deepest first).
    """
    return '```mermaid\n' + _sacm_diagram_body(roots, config) + '\n```'


def render_sacm_html(roots: List['Node'], config: dict) -> str:
    """Render SACM diagram as a <pre class="mermaid"> block."""
    body = _sacm_diagram_body(roots, config)
    return f'<pre class="mermaid">\n{body}\n</pre>'


# ---------------------------------------------------------------------------
# GSN/mermaid renderer
# ---------------------------------------------------------------------------

def _gsn_is_incontextof(node: 'Node') -> bool:
    """True if node attaches to its parent via InContextOf (--o), not SupportedBy (-->)."""
    return node.node_type in ('Context', 'Assumption', 'Justification') or \
           (node.node_type == 'Claim' and 'assumed' in node.options)


def _gsn_assertion_suffix(node_type: str, options: List[str]) -> str:
    """Return the GSN mermaid assertion-state suffix for the given node type and options.

    >>> _gsn_assertion_suffix('Claim', {'defeated'})
    '<br>✗'
    >>> _gsn_assertion_suffix('Claim', {'needssupport'})
    '<br>◇'
    >>> _gsn_assertion_suffix('Claim', {'axiomatic'})
    '<br>AXIOMATIC'
    >>> _gsn_assertion_suffix('Claim', {'metaclaim'})
    '<br>METACLAIM'
    >>> _gsn_assertion_suffix('Strategy', {'assumed'})
    '<br>ASSUMED'
    >>> _gsn_assertion_suffix('Assumption', set())
    ''
    >>> _gsn_assertion_suffix('Claim', set())
    ''
    """
    if 'defeated' in options:
        return '<br>✗'
    elif 'needssupport' in options:
        return '<br>◇'
    elif 'axiomatic' in options:
        return '<br>AXIOMATIC'
    elif 'metaclaim' in options:
        return '<br>METACLAIM'
    elif 'assumed' in options and node_type not in ('Claim', 'Assumption'):
        return '<br>ASSUMED'
    else:
        return ''


def _gsn_node_decl(node: 'Node') -> str:
    """Return the mermaid node-declaration line for a single LTAC node (GSN style).

    Returns '' for Relation and Link nodes.
    diagram_id must already be set on the node.
    """
    if node.node_type in ('Relation', 'Link'):
        return ''
    if node.node_type == 'Connector':
        return f'    {node.diagram_id}(("{_HAIR_SPACE}")):::connector'

    did = node.diagram_id
    eid = escape_html(node.identifier) if node.identifier else ''
    etxt = escape_html(node.text) if node.text else ''
    opts = node.options

    # Assumed Claim is rendered as an Assumption shape.
    eff_type = 'Assumption' if (node.node_type == 'Claim' and 'assumed' in opts) else node.node_type

    suffix = _gsn_assertion_suffix(eff_type, opts)

    # Build decorator (only Assumption and Justification have one).
    if eff_type == 'Assumption':
        decorator = '&nbsp;Ⓐ'
    elif eff_type == 'Justification':
        decorator = '&nbsp;Ⓙ'
    else:
        decorator = ''

    # Build inner label.
    inner = _build_inner_label(eid, etxt, suffix, decorator)

    # Shape mapping.
    if eff_type in ('Assumption', 'Justification'):
        shape = f'("{inner}")'
    elif eff_type == 'Evidence':
        shape = f'(("{inner}"))'
    elif eff_type == 'Context':
        shape = f'(["{inner}"])'
    elif eff_type == 'Strategy':
        shape = f'[/"{inner}"/]'
    elif node.is_cited:
        shape = f'[["{inner}"]]'
    else:
        shape = f'["{inner}"]'

    abstract_cls = ':::gsnUndev' if 'abstract' in opts else ''
    return f'    {did}{shape}{abstract_cls}'


_GSN_HEADER = """\
```mermaid
---
config:
  theme: neutral
  flowchart:
    curve: linear
    htmlLabels: true
    rankSpacing: 60
    nodeSpacing: 45
    padding: 15
---
flowchart TD
    classDef invisible opacity:0
    classDef gsnUndev stroke-width:2px,stroke-dasharray: 5 5;
    classDef connector fill:none,stroke:#cccccc,stroke-width:1px;"""


def _gsn_collect_edges(node, edge_lines, leaf_nodes):
    """Collect GSN edges for *node* and its subtree (DFS pre-order).

    Appends edge strings to edge_lines.  Nodes with no outgoing edges are
    appended to leaf_nodes.
    """
    if node.node_type in ('Link', 'Relation'):
        return
    edges_before = len(edge_lines)
    for child in node.children:
        if child.node_type == 'Link':
            if child.link_target is not None:
                tgt = child.link_target
                edge_lines.append(_edge_line(
                    node.diagram_id, tgt.diagram_id,
                    _gsn_is_incontextof(tgt),
                    'counter' in child.options, False))
        elif child.node_type == 'Connector':
            edge_lines.append(_edge_line(node.diagram_id, child.diagram_id,
                                         False, False, False))
            _gsn_collect_edges(child, edge_lines, leaf_nodes)
        elif child.node_type == 'Relation':
            rc = 'counter' in child.options
            ra = 'abstract' in child.options
            for gc in child.children:
                if gc.node_type == 'Link':
                    if gc.link_target is not None:
                        tgt = gc.link_target
                        edge_lines.append(_edge_line(
                            node.diagram_id, tgt.diagram_id,
                            _gsn_is_incontextof(tgt), rc, ra))
                else:
                    edge_lines.append(_edge_line(
                        node.diagram_id, gc.diagram_id,
                        _gsn_is_incontextof(gc), rc, ra))
                    _gsn_collect_edges(gc, edge_lines, leaf_nodes)
        else:
            edge_lines.append(_edge_line(
                node.diagram_id, child.diagram_id,
                _gsn_is_incontextof(child),
                'counter' in child.options, False))
            _gsn_collect_edges(child, edge_lines, leaf_nodes)
    if len(edge_lines) == edges_before:
        leaf_nodes.append(node)


def _gsn_diagram_body(roots: List['Node'], config: dict) -> str:
    """Return the GSN diagram content without opening/closing fence markers."""
    base_url = config.get('base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    bottom_padding = config.get('bottom_padding', DEFAULT_CONFIG['bottom_padding'])
    roots = _copy_forest(roots)
    syn_counter = [0]
    _apply_gsn_width_transform(roots, config, syn_counter)

    # Node declarations (BFS) and click lines collected in a single pass.
    node_decl_lines = []
    click_lines = []
    for node in _collect_bfs(roots):
        decl = _gsn_node_decl(node)
        if decl:
            node_decl_lines.append(decl)
        if node.node_type not in ('Relation', 'Link', 'Connector'):
            url = _node_url(node, base_url, pkg_label)
            if url:
                click_lines.append(f'    click {node.diagram_id} "{url}"')

    # Collect edges via DFS pre-order; track leaf nodes.
    edge_lines: list = []
    leaf_nodes: list = []
    for root in roots:
        _gsn_collect_edges(root, edge_lines, leaf_nodes)

    # BottomPadding: all leaves link down to it (invisible node prevents
    # diagram controls from obscuring the bottom).
    bp_lines: list = []
    if bottom_padding:
        first = True
        seen: set = set()
        for leaf in leaf_nodes:
            if leaf.diagram_id not in seen:
                seen.add(leaf.diagram_id)
                bp = 'BottomPadding[ ]:::invisible' if first else 'BottomPadding'
                bp_lines.append(f'    {leaf.diagram_id} ~~~ {bp}')
                first = False
    edge_lines = bp_lines + edge_lines

    body_header = _GSN_HEADER[len('```mermaid\n'):]
    lines = [body_header]
    lines.extend(node_decl_lines)
    lines.extend(click_lines)
    if edge_lines:
        lines.append('')  # blank line between declarations and edges
        lines.extend(edge_lines)
    return '\n'.join(lines)


def render_gsn(roots: List['Node'], config: dict) -> str:
    """Render package roots as a complete GSN/mermaid code block.

    Returns the full mermaid fenced block (opening ```mermaid … closing ```).
    The original nodes are not modified; a deep copy is used internally.
    Output structure: header → node declarations (BFS) → click lines
    → blank line → BottomPadding lines + edges (DFS pre-order).
    """
    return '```mermaid\n' + _gsn_diagram_body(roots, config) + '\n```'


def render_gsn_html(roots: List['Node'], config: dict) -> str:
    """Render GSN diagram as a <pre class="mermaid"> block."""
    body = _gsn_diagram_body(roots, config)
    return f'<pre class="mermaid">\n{body}\n</pre>'


def resolve_element(
    element_id: Optional[str],
    registry: Dict[str, Node],
    all_roots: List[Node],
    current_element: Optional[Node],
) -> List[Node]:
    """Return the list of nodes to render for the given element_id.

    If element_id is given: look up in registry; call error() and return []
    if not found.  If element_id is None: use current_element if set, else
    return all_roots.  ('*' is handled at dispatch time before calling here.)
    """
    if element_id is not None:
        node = registry.get(element_id)
        if node is None:
            error(f"element {element_id!r} not found in registry")
            return []
        return [node]
    if current_element is not None:
        return [current_element]
    return list(all_roots)


def render_all_packages(all_roots: List[Node], render_fn, config: dict) -> str:
    """Render every package preceded by a configurable header.

    Package blocks are separated by a blank line.
    Header format: {pkg_header_prefix}{pkg_label}{id}{pkg_header_suffix}{content}
    """
    prefix = config.get('pkg_header_prefix', '### ')
    suffix = config.get('pkg_header_suffix', '\n')
    pkg_label = config.get('pkg_label', 'Package ')
    blocks = []
    for root in all_roots:
        label = f"{pkg_label}{root.identifier}" if root.identifier else pkg_label.rstrip()
        header = f"{prefix}{label}"
        blocks.append(f"{header}{suffix}{render_fn([root], config)}")
    return '\n\n'.join(blocks)


_VALID_DISPLAY_TYPES = {
    'ltac/markdown', 'ltac/html', 'ltac/txt',
    'sacm/mermaid', 'sacm/mermaid/markdown', 'sacm/mermaid/html',
    'gsn/mermaid',  'gsn/mermaid/markdown',  'gsn/mermaid/html',
    'statement',
    'element', 'package',
    'info',
    'warning',
    'config',  # recognized to give a helpful error directing users to verocase-config
    'referenced_by', 'supported_by', 'supports',
    'representation', 'pkg_defines', 'pkg_citing', 'pkg_cited',
}


def expand_selector(raw: str, doc_format: str, config: dict) -> str:
    """Expand a shorthand selector to its canonical three-part form.

    Rules (fill in missing parts right-to-left using doc_format and
    default_renderer):
      sacm            -> sacm/{renderer}/{doc_format}
      sacm/mermaid    -> sacm/mermaid/{doc_format}
      sacm/mermaid/markdown -> explicit
      sacm/mermaid/html     -> explicit
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


def parse_selector(selector: str, doc_format: str = 'markdown',
                   config: dict = None) -> Tuple[str, Optional[str]]:
    """Parse a SELECTOR string into (display_type, element_id_or_None).

    Format: 'display_type [element_id]'
    An element_id of '*' is kept as the literal string '*'.
    Expands shorthand forms (sacm, gsn, ltac) using doc_format and config.
    Calls error() on unknown display_type.
    """
    config = config or {}
    parts = selector.split(None, 1)
    raw_type = parts[0] if parts else ''
    element_id: Optional[str] = parts[1].strip() if len(parts) > 1 else None
    display_type = expand_selector(raw_type, doc_format, config)
    if display_type not in _VALID_DISPLAY_TYPES:
        error(f"unknown selector type {display_type!r}")
    return display_type, element_id


def _render_or_all(
    element_id: Optional[str],
    all_roots: List[Node],
    render_fn,
    registry: Dict[str, Node],
    current_element: Optional[Node],
    config: dict,
) -> str:
    """Resolve element_id and render, or render all packages if element_id is '*'."""
    if element_id == '*':
        return render_all_packages(all_roots, render_fn, config)
    nodes = resolve_element(element_id, registry, all_roots, current_element)
    return render_fn(nodes, config)


# ---------------------------------------------------------------------------
# Selection renderers (for element/package sub-selections)
# ---------------------------------------------------------------------------

def _pkg_anchor_url(pkg_root_id: str, config: dict) -> str:
    """Return the fragment URL for a package heading."""
    base_url = config.get('markdown_base_url', '')
    anchor = _component_anchor_id('Package', pkg_root_id)
    return base_url + '#' + anchor


def _element_anchor_url(node_type: str, ident: str, config: dict) -> str:
    """Return the fragment URL for an element heading."""
    base_url = config.get('markdown_base_url', '')
    anchor = _component_anchor_id(node_type, ident)
    return base_url + '#' + anchor


def _linked_list(pairs: List[tuple], fmt: str, bold_first: bool = True) -> str:
    """Format (label, url) pairs as a comma-joined string of hyperlinks.

    If bold_first is True (the default), the first link is wrapped in bold.
    """
    links = []
    for i, (label, url) in enumerate(pairs):
        link = hyperlink(label, url, fmt)
        links.append(bold(link, fmt) if (bold_first and i == 0) else link)
    return ', '.join(links)


def _find_citation_parents(ident: str, all_roots: List[Node]) -> List[Node]:
    """Return parent nodes of all citations of ident across all packages."""
    parents = []
    for node in _all_nodes(all_roots):
        if node.identifier == ident and node.is_cited and node.parent is not None:
            if node.parent not in parents:
                parents.append(node.parent)
    return parents


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
    pairs = [(f'Package {pid}', _pkg_anchor_url(pid, config)) for pid in pkg_ids]
    return 'Referenced by: ' + _linked_list(pairs, fmt)


def render_supported_by(node: Node, config: dict, fmt: str) -> str:
    """Render 'Supported by: ...' line or '' if no children."""
    children = [c for c in node.children if c.node_type != 'Link'
                or c.link_target is not None]
    if not children:
        return ''
    pairs = []
    for child in children:
        target = child.link_target if child.node_type == 'Link' else child
        if target is None or not target.identifier:
            continue
        pairs.append((f'{target.node_type} {target.identifier}',
                      _element_anchor_url(target.node_type, target.identifier, config)))
    if not pairs:
        return ''
    return 'Supported by: ' + _linked_list(pairs, fmt)


def render_supports(node: Node, all_roots: List[Node],
                    config: dict, fmt: str) -> str:
    """Render 'Supports: ...' line or '' if no parents at all."""
    pairs = []
    has_direct_parent = node.parent is not None
    if has_direct_parent:
        p = node.parent
        pairs.append((f'{p.node_type} {p.identifier}',
                      _element_anchor_url(p.node_type, p.identifier, config)))
    for parent in _find_citation_parents(node.identifier, all_roots):
        if not parent.identifier:
            continue
        pairs.append((f'{parent.node_type} {parent.identifier}',
                      _element_anchor_url(parent.node_type, parent.identifier, config)))
    if not pairs:
        return ''
    return 'Supports: ' + _linked_list(pairs, fmt, bold_first=has_direct_parent)


def render_pkg_defines(pkg_root: Node, id_info: Dict[str, dict],
                       config: dict, fmt: str) -> str:
    """Render 'Defines: ...' list for a package."""
    pkg_id = pkg_root.identifier
    defined = []
    for node in _all_nodes([pkg_root]):
        if (not node.is_cited and node.identifier
                and id_info.get(node.identifier, {}).get('decl_pkg_id') == pkg_id):
            defined.append(node)
    if not defined:
        return ''
    pairs = [(f'{node.node_type} {node.identifier}',
              _element_anchor_url(node.node_type, node.identifier, config))
             for node in defined]
    return 'Defines: ' + _linked_list(pairs, fmt)


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
    pairs = [(f'Package {cpid}', _pkg_anchor_url(cpid, config)) for cpid in citing_pkgs]
    return 'Cited by: ' + _linked_list(pairs, fmt, bold_first=False)


def render_representation(pkg_root: Node, all_roots: List[Node],
                          config: dict, fmt: str) -> str:
    """Render the default diagram representation for a package."""
    notation = config.get('default_representation', 'sacm')
    renderer = config.get('default_renderer', 'mermaid')
    selector = f'{notation}/{renderer}/{fmt}'
    if selector in ('sacm/mermaid/markdown', 'sacm/mermaid'):
        return render_sacm([pkg_root], config)
    elif selector == 'sacm/mermaid/html':
        return render_sacm_html([pkg_root], config)
    elif selector in ('gsn/mermaid/markdown', 'gsn/mermaid'):
        return render_gsn([pkg_root], config)
    elif selector == 'gsn/mermaid/html':
        return render_gsn_html([pkg_root], config)
    elif selector == 'ltac/markdown':
        return render_markdown([pkg_root], config)
    elif selector == 'ltac/html':
        return render_html([pkg_root], config)
    else:
        error(f"unsupported representation {selector!r}")
        return ''


def _make_heading(anchor: str, level: int, heading_text: str, fmt: str) -> str:
    """Return a format-appropriate heading string with an HTML anchor.

    For markdown: an '<a id=...>' anchor line followed by a '#'-prefixed heading.
    For HTML: a single '<hN id=...>...</hN>' element.
    Returns a single string (lines joined with newline for markdown).
    """
    if fmt == 'markdown':
        return '\n'.join([f'<a id="{anchor}"></a>',
                          '#' * level + ' ' + heading_text])
    else:
        return f'<h{level} id="{anchor}">{escape_html_content(heading_text)}</h{level}>'


def _apply_selections(selections: List[str], render_map: Dict[str, callable],
                      config: dict, fmt: str) -> str:
    """Apply a list of selection names and return their combined output.

    Non-empty outputs are joined with blank lines; trailing blank line suppressed.
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


def render_element_selector(node_id: str, registry: Dict[str, Node],
                             all_roots: List[Node], id_info: Dict[str, dict],
                             config: dict, state: 'DocState') -> str:
    """Render heading + sub-selections for a single element."""
    node = registry.get(node_id)
    if node is None:
        error(f"element {node_id!r} not found")
        return ''
    state.current_id = node_id
    state.seen_element_ids.add(node_id)

    level = config.get('element_level', 3)
    anchor = _component_anchor_id(node.node_type, node_id)
    stmt = id_info.get(node_id, {}).get('statement') or node.text or ''
    heading_text = f'{node.node_type} {node_id}'
    if stmt:
        heading_text += f': {stmt}'
    fmt = state.doc_format

    sel_names = [s.strip() for s in
                 config.get('element_selections', 'referenced_by,supported_by,supports')
                 .split(',') if s.strip()]
    render_map = {
        'referenced_by': lambda: render_referenced_by(node, all_roots, id_info, config, fmt),
        'supported_by':  lambda: render_supported_by(node, config, fmt),
        'supports':      lambda: render_supports(node, all_roots, config, fmt),
    }
    selections_out = _apply_selections(sel_names, render_map, config, fmt)

    parts = [_make_heading(anchor, level, heading_text, fmt)]
    if selections_out:
        parts.append(selections_out)
    return '\n\n'.join(parts)


def _render_single_package(pkg_root: Node, all_roots: List[Node],
                            id_info: Dict[str, dict],
                            config: dict, state: 'DocState') -> str:
    """Render one package heading + its package_selections."""
    fmt = state.doc_format
    level = config.get('package_level', 3)
    anchor = _component_anchor_id('Package', pkg_root.identifier)
    stmt = id_info.get(pkg_root.identifier, {}).get('statement') or pkg_root.text or ''
    heading_text = f'Package {pkg_root.identifier}'
    if stmt:
        heading_text += f': {stmt}'

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

    parts = [_make_heading(anchor, level, heading_text, fmt)]
    if selections_out:
        parts.append(selections_out)
    return '\n\n'.join(parts)


def render_package_selector(pkg_id_or_star: str, all_roots: List[Node],
                             registry: Dict[str, Node],
                             id_info: Dict[str, dict],
                             config: dict, state: 'DocState') -> str:
    """Render heading + sub-selections for one package, or all packages if '*'."""
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


_WARNING_TEXT = (
    '<!-- WARNING: DO NOT EDIT text within verocase SELECTOR ... end verocase. -->\n'
    '<!-- Those regions are regenerated. -->'
)


def render_warning(element_id: Optional[str]) -> str:
    """Render the warning selector.  Refuses any element_id argument."""
    if element_id is not None:
        error("'warning' selector takes no parameters")
        return ''
    return _WARNING_TEXT


def render_selector(
    selector: str,
    registry: Dict[str, Node],
    all_roots: List[Node],
    config: dict,
    id_info: Dict[str, dict],
    current_element: Optional[Node] = None,
    doc_format: str = 'markdown',
    state: 'DocState' = None,
) -> str:
    """Parse SELECTOR and return the rendered string.

    Dispatches to the appropriate renderer based on display_type.
    Returns '' if the display_type is unknown (error already reported).
    """
    display_type, element_id = parse_selector(selector, doc_format, config)

    if display_type == 'config':
        error("use '<!-- verocase-config KEY = VALUE -->' (not '<!-- verocase config ...-->')")
        return ''
    elif display_type == 'warning':
        return render_warning(element_id)
    elif display_type in ('sacm/mermaid', 'sacm/mermaid/markdown'):
        return _render_or_all(element_id, all_roots, render_sacm, registry, current_element, config)
    elif display_type in ('gsn/mermaid', 'gsn/mermaid/markdown'):
        return _render_or_all(element_id, all_roots, render_gsn, registry, current_element, config)
    elif display_type == 'sacm/mermaid/html':
        return _render_or_all(element_id, all_roots, render_sacm_html, registry, current_element, config)
    elif display_type == 'gsn/mermaid/html':
        return _render_or_all(element_id, all_roots, render_gsn_html, registry, current_element, config)
    elif display_type == 'ltac/markdown':
        return _render_or_all(element_id, all_roots, render_markdown, registry, current_element, config)
    elif display_type == 'ltac/html':
        return _render_or_all(element_id, all_roots, render_html, registry, current_element, config)
    elif display_type == 'ltac/txt':
        nodes = resolve_element(element_id, registry, all_roots, current_element)
        if not nodes:
            return ''
        return render_ltac_txt(nodes, config)
    elif display_type == 'info':
        if element_id is None or element_id == '*':
            error("'info' selector requires an explicit element ID")
            return ''
        return render_info(element_id, all_roots, registry, id_info)
    elif display_type == 'element':
        if element_id is None:
            error("'element' selector requires an explicit ID")
            return ''
        _state = state or DocState(doc_format=doc_format)
        return render_element_selector(element_id, registry, all_roots, id_info, config, _state)
    elif display_type == 'package':
        _state = state or DocState(doc_format=doc_format)
        pkg_id = element_id if element_id is not None else '*'
        return render_package_selector(pkg_id, all_roots, registry, id_info, config, _state)
    else:
        # statement operates on a single node
        if element_id == '*':
            error(f"'*' is not valid with the '{display_type}' selector")
            return ''
        nodes = resolve_element(element_id, registry, all_roots, current_element)
        if not nodes:
            return ''
        node = nodes[0]
        if display_type == 'statement':
            return render_statement(node)
        return ''


# ---------------------------------------------------------------------------
# Document processor
# ---------------------------------------------------------------------------

@dataclass
class DocState:
    """Mutable per-document processing state."""
    current_id: Optional[str] = None
    doc_format: str = 'markdown'
    mermaid_injected: bool = False
    seen_element_ids: set = None

    def __post_init__(self):
        if self.seen_element_ids is None:
            self.seen_element_ids = set()


def _maybe_inject_mermaid_js(rendered: str, config: dict, state: 'DocState') -> str:
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
        f"  import mermaid from '{url}';\n"
        f'  mermaid.initialize({{ startOnLoad: true }});\n'
        f'</script>\n'
    )
    state.mermaid_injected = True
    return script + rendered


# Matches '<!-- verocase SELECTOR -->' lines (SELECTOR is captured in group 1).
_CASEPROC_REGION_RE = re.compile(r'^<!--\s*verocase\s+(.+?)\s*-->\s*$')

# Matches '<!-- verocase-config KEY = VALUE -->' directives.
_CASEPROC_CONFIG_RE = re.compile(r'^<!--\s*verocase-config\s+(\S+)\s*=\s*(.*?)\s*-->\s*$')

# Allowed dynamically-settable config keys and their validation patterns.
_ALLOWED_CONFIG_VALUES = {
    'element_level': re.compile(r'^[1-6]$'),
    'package_level': re.compile(r'^[1-6]$'),
    'max_mermaid_children':    re.compile(r'^(0|[1-9][0-9]*)\Z'),
    'narrowed_mermaid_children': re.compile(r'^(0|[1-9][0-9]*)\Z'),
}


def config_invariant_checker(config: dict,
                             filename: str = '',
                             lineno: int = 0) -> None:
    """Panic if max/narrowed_mermaid_children violate required invariants.

    max_mermaid_children == 0 disables the width-management transform entirely;
    the narrowed value is irrelevant in that case.
    When max > 0:
      narrowed_mermaid_children >= 2           (enough room to place a connector)
      narrowed_mermaid_children < max_mermaid_children  (strictly improves)
    """
    mx = config.get('max_mermaid_children',
                    DEFAULT_CONFIG['max_mermaid_children'])
    nr = config.get('narrowed_mermaid_children',
                    DEFAULT_CONFIG['narrowed_mermaid_children'])
    if mx == 0:
        return
    prefix = f'{filename}:{lineno}: ' if filename else ''
    if nr < 2:
        panic(f'{prefix}narrowed_mermaid_children ({nr}) must be >= 2')
    if nr >= mx:
        panic(
            f'{prefix}narrowed_mermaid_children ({nr}) must be less than '
            f'max_mermaid_children ({mx})'
        )


def apply_config_directive(key: str, value: str, config: dict,
                           filename: str, lineno: int) -> None:
    """Apply a verocase-config directive, warning on invalid key or value."""
    if key not in DEFAULT_CONFIG:
        warn(f"{filename}:{lineno}: verocase-config: unknown key {key!r}")
        return
    pattern = _ALLOWED_CONFIG_VALUES.get(key)
    if pattern is None:
        warn(f"{filename}:{lineno}: verocase-config: key {key!r} is not dynamically settable")
        return
    elif not pattern.match(value):
        warn(f"{filename}:{lineno}: verocase-config: invalid value {value!r} for {key!r}")
        return
    if key in ('element_level', 'package_level',
               'max_mermaid_children', 'narrowed_mermaid_children'):
        config[key] = int(value)
    else:
        config[key] = value
    if key in ('max_mermaid_children', 'narrowed_mermaid_children'):
        config_invariant_checker(config, filename, lineno)


def _consume_region(line_iter, filename: str, start_lineno: int, selector: str) -> bool:
    """Consume lines from line_iter until '<!-- end verocase -->', return True if found.

    If EOF is reached before finding the end marker, calls error() and returns False.
    """
    for _, line in line_iter:
        if line.strip() == '<!-- end verocase -->':
            return True
    error(f"{filename}:{start_lineno}: unclosed '<!-- verocase {selector} -->' region")
    return False


def process_document_stream(
    f,
    out,
    registry: Dict[str, Node],
    all_roots: List[Node],
    config: dict,
    id_info: Dict[str, dict],
    seen_element_ids: set,
    doc_format: str = 'markdown',
    add_missing: bool = False,
    strip: bool = False,
) -> None:
    """Process a document file line by line, replacing ltac selector regions.

    Writes all output to `out`.  Updates `seen_element_ids` with identifiers of
    LTAC elements rendered via 'element' selectors.  Uses the already-loaded
    registry and all_roots; performs no LTAC parsing.

    When `add_missing` is True, appends skeleton element regions for every
    declared LTAC element not yet seen via an 'element' selector.  In HTML
    documents the injection happens immediately before the first `</body>` tag;
    in Markdown documents (or HTML without `</body>`) it happens at EOF.

    When `strip` is True, generated content is omitted from all selector
    regions except 'warning', leaving the markers in place with empty bodies.
    """
    _doc_state = DocState(doc_format=doc_format, seen_element_ids=seen_element_ids)
    filename = getattr(f, 'name', '<stream>')

    config = dict(config)  # local copy so directives don't affect caller's config

    _injected = False

    def _inject_missing() -> None:
        nonlocal _injected
        if _injected:
            return
        _injected = True
        all_ids = [node.identifier for node in _all_nodes(all_roots)
                   if not node.is_cited and node.identifier]
        missing = [ident for ident in all_ids if ident not in _doc_state.seen_element_ids]
        if not missing:
            return
        notify(f"Adding {len(missing)} formerly missing element(s) to {filename}")
        inj_state = DocState(doc_format=doc_format, seen_element_ids=_doc_state.seen_element_ids)
        out.write('\n')
        for ident in missing:
            rendered = render_element_selector(ident, registry, [], id_info, config, inj_state)
            out.write(f'<!-- verocase element {ident} -->\n')
            out.write(rendered + '\n')
            out.write('<!-- end verocase -->\n')
            out.write('\n')

    line_iter = enumerate(f, 1)
    for lineno, line in line_iter:
        text = line.rstrip('\r\n')

        if add_missing and '</body>' in text.lower():
            _inject_missing()
            out.write(text + '\n')
            continue

        cm = _CASEPROC_CONFIG_RE.match(text)
        if cm:
            apply_config_directive(cm.group(1), cm.group(2), config, filename, lineno)
            out.write(text + '\n')
            continue

        m = _CASEPROC_REGION_RE.match(text)
        if m:
            selector = m.group(1)
            found_end = _consume_region(line_iter, filename, lineno, selector)
            if strip and selector.strip() != 'warning':
                rendered = ''
            else:
                rendered = render_selector(selector, registry, all_roots, config, id_info,
                                           doc_format=doc_format, state=_doc_state)
                rendered = _maybe_inject_mermaid_js(rendered, config, _doc_state)
            out.write(text + '\n')
            if found_end:
                if rendered:
                    out.write(rendered + '\n')
                out.write('<!-- end verocase -->\n')
            continue

        out.write(text + '\n')

    if add_missing:
        _inject_missing()


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

_START_LTAC = """\
- Claim Security: The system is adequately secure against moderate threats
  - Strategy Processes: Security is argued by examining lifecycle processes
    - Claim ^Requirements
    - Claim ^Design
    - Claim ^Implementation
    - Claim ^Verification

- Claim Requirements: Security requirements are identified and met
  - Strategy SecTriad: Security triad (CIA) and access control address the requirements
    - Claim Confidentiality: Confidentiality is maintained
    - Claim Integrity: Integrity is maintained
    - Claim Availability: Availability is maintained
    - Claim AccessControl: Access control is in place

- Claim Design: Security is implemented in design
  - Claim SimpleDesign: Economy of mechanism: simple design is used
  - Claim STRIDE: STRIDE threat model has been analyzed
  - Claim DesignPrinciples: Secure design principles are applied

- Claim Implementation: Implementation is secure

- Claim Verification: System verified as being secure
"""

_START_DOC = """\
# Sample Assurance Case

This is a sample assurance case for you to edit.

<!-- verocase warning -->
<!-- end verocase -->

## Packages

<!-- verocase package * -->
<!-- end verocase -->

## Elements
"""

_START_CANDIDATES = (
    'case.ltac', 'docs/case.ltac',
    'case.md', 'case.markdown', 'case.html',
    'docs/case.md', 'docs/case.markdown', 'docs/case.html',
)


def _check_no_existing_case_files() -> None:
    """Panic if any well-known case file already exists."""
    for path in _START_CANDIDATES:
        if os.path.exists(path):
            panic(f"--start: {path!r} already exists; remove it before using --start")


def _write_start_stubs() -> None:
    """Write initial case.ltac and case.md stubs for --start."""
    try:
        with open('case.ltac', 'w', encoding='utf-8') as f:
            f.write(_START_LTAC)
    except OSError as e:
        panic(f"--start: cannot write case.ltac: {e}")
    try:
        with open('case.md', 'w', encoding='utf-8') as f:
            f.write(_START_DOC)
    except OSError as e:
        panic(f"--start: cannot write case.md: {e}")
    notify("created case.ltac and case.md")


class _MutationAction(argparse.Action):
    """Accumulate --rename/--restate/--detach/--move operations as ordered tuples.

    All four options share a single ordered queue (dest='mutations').
    Tuples are (op, a, b) where b is None for --detach (single-argument option).
    The order on the command line is the order of application.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        mutations = getattr(namespace, self.dest, None) or []
        op = option_string.lstrip('-')   # 'rename', 'restate', 'detach', or 'move'
        if isinstance(values, list):
            a = values[0]
            b = values[1] if len(values) > 1 else None
        else:
            a, b = values, None
        mutations.append((op, a, b))
        setattr(namespace, self.dest, mutations)


def parse_args() -> argparse.Namespace:
    """Build the argument parser, define all flags, and parse the command line."""
    parser = argparse.ArgumentParser(
        prog='verocase',
        description='Process assurance case LTAC file and update documentation files (Markdown/HTML)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
This program normally reads an LTAC file as input and then updates (modifies)
corresponding document file(s) in Markdown/HTML within their text regions
marked by <!-- verocase SELECTOR --> ... <!-- end verocase -->.

The intended normal use is that you simply edit the LTAC file to express
the high-level assurance case ("why you believe some claim is true") and edit
the Markdown/HTML for all details (the "content" in SACM parlance).
At any time you can re-run this program to validate the
assurance case structure and to update your Markdown/HTML document files.
Those updates will typically include generated graphics, hyperlinks,
and other material. The document files' marked regions will
be updated, but *only* those regions will be updated.

Quick start: run `verocase --start` to create project starter files
case.ltac and case.md. From then on, repeatedly edit those files to
describe your assurance case, run `verocase` to validate and update the
documents, and review the results.

The LTAC input file format must contain a series of 1+ packages.
A package begins with an un-indented line defining its top element,
followed by 0+ lines defining its sub-elements. Each line defines
an element, indented two spaces/level, in this format:
- TYPE [^][ID]: text [{options}] [(reference)]

Types:
  Claim        goal/assertion; text should be a true/false statement you
               want to be true (this is the primary building block)
  Strategy     argument pattern; explains *how* its sub-elements support
               the parent claim (e.g. "argued by examining X and Y").
               Not necessary if it's obvious how a claim is justified
               by its children.
  Evidence     supporting artifact (leaf only; no children allowed)
  Justification  rationale for a design decision or argument choice
  Context      background information (scope, environment, definitions)
  Assumption   claim accepted as true without proof; implicitly 'assumed'
  Relation     explicit relationship between two elements
  Link ID      non-hierarchical cross-reference to element ID; does not
               affect the argument hierarchy

Packages organize top-level claims so you can focus on one part at a time.

IDs are optional but strongly recommended. A bare ID (no `^` prefix) declares
the element; use the prefix `^` to cite (cross-reference) an element declared
elsewhere. If the ID is omitted, the text is the ID (after
stripping ^{}()\\n\\r).

Key options in the LTAC file (these are comma-separated inside {}):
  needssupport  leaf element needs supporting evidence (--missing adds these)
  axiomatic     accepted as foundational; needs no supporting evidence
  defeated      argument is disproved or no longer valid
  assumed       claim is treated as an assumption (no support required)
  metaclaim     claim is about the argument structure itself, not the system

Reference is a file path, URL, or anchor (e.g. (report.pdf)). If you want
to end a statement with a parenthetical comment, use the empty reference `()`
after it to clearly indicate that the text is not a reference.

Here's an example of a simple LTAC file's contents:

- Claim Security: The system is adequately secure against moderate threats
  - Claim ^Requirements
  - Claim ^Design

- Claim Requirements: Security requirements are identified and met
  - Claim Confidentiality: Confidentiality is maintained
  - Claim Integrity: Integrity is maintained
  - Claim Availability: Availability is maintained

- Claim Design: Security is implemented in design

Document files contain marked regions that verocase manages:
  <!-- verocase SELECTOR -->
  ...content regenerated by verocase on every run...
  <!-- end verocase -->

You write everything *outside* these markers; verocase only rewrites inside
them. A typical document uses these selectors:
  <!-- verocase warning -->          placed at top; do-not-edit notice
  <!-- verocase package MyPkg -->    diagram + index for package MyPkg
  <!-- verocase element MyElem -->   heading + cross-refs for element MyElem

Use --fixmissing to scaffold element regions for elements not yet in the document.

Read-only options (marked [READ-ONLY] in --help; never modify any stored file):
  --validate, --select, --info, --descendants, --stdout
  --missing, --empty, --orphans, --misplaced, --leaves, --packages
  (--stats does not itself modify files but combines with any mode)

File-modifying options (modify document files, LTAC, or both):
  default mode, --fixmissing, --fixmisplaced, --start,
  --update, --rename, --restate, --detach, --move

The read-only analysis options listed above may be freely combined with
each other.  They cannot be combined with any file-modifying option;
verocase will exit with an error if you try.

By default the program treats the LTAC file strictly as an input and
it will *not* modify the LTAC file. However, the options --update,
--rename, --restate, --detach, --move, --fixmissing, and --start
*may* modify the LTAC file.

The options --rename, --restate, --detach, and --move all share a single
ordered mutation queue. They are applied to the LTAC tree in the order
they appear on the command line. Order matters: for example,
'--detach C2 --move C2 C1' detaches C2 first (leaving ^C2 in place),
then moves C2 under C1.

All file updates are done carefully. The updated files are generated
first as temporary files, then a timestamped backup snapshot is created
under .backups/ next to the LTAC file, and only then are the generated
files moved to their final destinations. Old snapshots are automatically
rotated (max_backups in config, default 20). Use --stdout to prevent
in-place updates.

Selectors are of format `KIND [ID | *]`, where KIND is:
  element        ID    heading + cross-references for one element
  package        ID|*  heading + diagram + index for one or all packages
  sacm           ID|*  SACM mermaid diagram (auto-detects markdown/HTML output)
  sacm/mermaid/markdown  ID|*  explicit markdown fenced block
  sacm/mermaid/html      ID|*  explicit <pre class="mermaid"> block
  gsn            ID|*  GSN mermaid diagram (auto-detects format)
  ltac           ID|*  LTAC argument list (auto-detects format)
  ltac/markdown  ID|*  LTAC as Markdown bullet list
  ltac/html      ID|*  LTAC as HTML <ul> list
  ltac/txt       ID|*  LTAC as raw text (no Markdown/HTML; shows IDs, options, refs)
  info           ID    full context: ancestors, children, citation parents, counts
  statement      ID    one-line statement for an element
  warning              fixed "do not edit" warning comment (no ID)
Use * to render all packages (package/ltac/sacm/gsn selectors).

Shortcuts for common selectors:
  --info ID          same as --select "info ID"
  --descendants ID   same as --select "ltac/txt ID"

Validations on the LTAC file (always):
  - There must be no circularities (this prevents circular reasoning)
  - All elements must be reachable from the first node of the first package
  - Each package must start with a Claim or Justification (per LTAC spec rule 3)
  - Claim/Strategy must not appear under Evidence, Context, or Assumption
  - Each identifier must be declared (no ^ prefix) exactly once
  - Citing identifiers (^ID) must have a matching declaration (usually to
    a different package, but this is not required)
  - Element type must be consistent across all uses of the same identifier
  - Statement text must be consistent across all uses of the same identifier
    (use --update to make LTAC citations consistent with their declaration)
  - Each element must carry at *most* one assertion status option
    (needsSupport, axiomatic, defeated, assumed); see SACM spec section 11
  - All generated anchor names (e.g., "claim-x-is-secure") must be unique
  - No two siblings may share the same identifier (declared, cited, or Link)
  - Cross-package citations (^ID) should have type Claim or Justification
  - Evidence nodes must not have children (Evidence is a leaf)
  - Elements with neither an identifier nor a statement are reported as errors
  - Declarations missing a statement give warnings if any declaration has one
  - References that look like parenthetical comments (no '.' and no '#') are
    flagged as possibly dubious (disable with warn_dubious_reference=false in
    the --config file); add a `()` afterwards to escape a closing parenthetical

Additional checks when document files are provided:
  - Every declared LTAC element should have a corresponding 'element' selector
    in a document (used to generate the element's heading and cross-references;
    use --fixmissing to fix this)

Configuration keys (--config FILE, JSON object):
  document_files     list of document file paths to process (default: auto-discover)
  ltac_file          LTAC file path (alternative to --ltac; default: auto-discover)
  max_backups        number of timestamped backup snapshots to keep (default: 20)
  base_url           base URL for hyperlinks in sacm/gsn mermaid output (default: "")
  markdown_base_url  base URL for hyperlinks in ltac/markdown and ltac/html output (default: "")
  default_renderer   renderer for 'sacm'/'gsn' shorthands: "mermaid" (default)
  default_representation  content for 'package' selector: "sacm" (default)
  element_level      heading level (1-6) for 'element' selector (default: 3)
  element_selections comma-separated list for element sub-sections (default: referenced_by,supported_by,supports)
  max_mermaid_children      max visual children before width narrowing (default: 8; 0 disables)
  mermaid_js_url     URL for Mermaid JS script in HTML output (default: CDN URL; "" disables)
  narrowed_mermaid_children children kept (left+right) when narrowing (default: 6; must be >=2 and <max)
  package_level      heading level (1-6) for 'package' selector (default: 3)
  package_selections comma-separated list for package sub-sections (default: representation,pkg_defines,pkg_citing,pkg_cited)
  pkg_label          word used to identify packages in output (default: "Package ")
  warn_dubious_reference  warn when a reference looks like a parenthetical comment (default: true)
""",
    )
    parser.add_argument(
        '--version', action='version', version=__version__,
        help='print version and exit',
    )
    parser.add_argument(
        '--config', type=str, metavar='FILE',
        help='path to a JSON file containing configuration key/value pairs',
    )
    parser.add_argument(
        '--error', action='store_true',
        help='treat warnings as errors (non-zero exit on any warning)',
    )
    parser.add_argument(
        '--stats', action='store_true', default=False,
        help='print statistics about the LTAC structure and documents; '
             'may be combined with any mode (does not itself modify files)',
    )
    parser.add_argument(
        '--strip', action='store_true', default=False,
        help=(
            'regenerate documents with empty selector regions '
            '(only "warning" content is preserved); '
            'useful for reviewing document structure without generated content, '
            'especially for AI tools reading the document; '
            'combine with --stdout to write the stripped result to stdout '
            'without modifying the files'
        ),
    )
    parser.add_argument(
        '--update', action='store_true',
        help='update the LTAC file to synchronize citation statements with their declarations',
    )
    parser.add_argument(
        '--rename', nargs=2, metavar=('OLD', 'NEW'),
        dest='mutations', action=_MutationAction,
        help='rename identifier OLD to NEW in LTAC and document files',
    )
    parser.add_argument(
        '--restate', nargs=2, metavar=('LABEL', 'STATEMENT'),
        dest='mutations', action=_MutationAction,
        help='update the statement for LABEL in LTAC and document files',
    )
    parser.add_argument(
        '--detach', metavar='ID',
        nargs=1, action=_MutationAction, dest='mutations', default=None,
        help=(
            "replace ID's definition with a citation (^ID) in its current location "
            "and move its subtree to a new top-level package. "
            "Panics if ID is not defined or is already a top-level package root. "
            "Joins the shared mutation queue with --rename, --restate, and --move."
        ),
    )
    parser.add_argument(
        '--move', metavar=('ID', 'DESTINATION'),
        nargs=2, action=_MutationAction, dest='mutations', default=None,
        help=(
            "move ID's definition to be a child of DESTINATION. "
            "ID may be anywhere in the tree (top-level or nested). "
            "If ^ID is already a direct child of DESTINATION it is replaced by "
            "the definition; otherwise the definition is appended as the last child. "
            "No citation is left at the original location; to leave one behind, "
            "run --detach ID first, then --move ID DESTINATION. "
            "Panics if ID or DESTINATION is not defined. "
            "Joins the shared mutation queue with --rename, --restate, and --detach."
        ),
    )
    parser.set_defaults(mutations=[])
    parser.add_argument(
        '--ltac', '-l', type=str, metavar='FILENAME',
        help='LTAC file to load (default: case.ltac or docs/case.ltac)',
    )
    parser.add_argument(
        'files', nargs='*',
        help='Documentation file(s) (Markdown/HTML) to update in place (default: auto-discover case.md or docs/case.md etc.)',
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--validate', action='store_true',
        help='[READ-ONLY] validate and report warnings/errors; do not modify any file',
    )
    mode.add_argument(
        '--select', '-s', type=str, metavar='SELECTOR',
        help='[READ-ONLY] render SELECTOR to stdout and exit (see selector table below)',
    )
    mode.add_argument(
        '--stdout', action='store_true',
        help='[READ-ONLY] process document files and write result to stdout '
             'without modifying any stored file',
    )
    mode.add_argument(
        '--selftest', action='store_true',
        help='run the built-in doctest suite and exit (0 = all pass, 1 = any fail)',
    )
    mode.add_argument(
        '--fixmissing', action='store_true',
        help='re-render document files and insert element selectors for missing elements '
             'near their natural position in LTAC order; '
             'may modify the LTAC to add needsSupport to some leaf elements',
    )
    mode.add_argument(
        '--fixmisplaced', action='store_true',
        help='move element regions that appear in the wrong order (relative to LTAC order) '
             'to their correct position in the document; use --misplaced first to preview',
    )
    mode.add_argument(
        '--start', action='store_true',
        help='create starter case.ltac and case.md files, then run --fixmissing '
             'to add missing sections for elements and needsSupport markings '
             'to the new LTAC file. After --start, edit case.ltac and case.md '
             'to describe your system, then run verocase normally. '
             '(panics if any case file already exists)',
    )
    mode.add_argument(
        '--info', type=str, metavar='ID',
        help='[READ-ONLY] print full context for element ID: package, ancestors, children, '
             'descendant count, and citation parents. Shorthand for --select "info ID".',
    )
    mode.add_argument(
        '--descendants', type=str, metavar='ID',
        help='[READ-ONLY] print the LTAC definition of element ID and all its descendants '
             'in LTAC source form. Shorthand for --select "ltac/txt ID".',
    )

    # Analysis options: read-only; never modify any file.
    # May be freely combined with each other and with --stats, --validate, --select,
    # --info, --descendants.  Cannot be combined with any file-modifying option
    # (--fixmissing, --fixmisplaced, --start, --update, --rename, --restate,
    # --detach, --move).
    parser.add_argument(
        '--missing', action='store_true', default=False,
        help='[READ-ONLY] list LTAC elements that have no selector region in any document; '
             'use --fixmissing to scaffold them',
    )
    parser.add_argument(
        '--empty', action='store_true', default=False,
        help='[READ-ONLY] list elements whose selector region exists but has no '
             'human-written prose after <!-- end verocase -->',
    )
    parser.add_argument(
        '--orphans', action='store_true', default=False,
        help='[READ-ONLY] list document selector regions that have no matching LTAC '
             'declaration (stale regions left after rename/removal)',
    )
    parser.add_argument(
        '--misplaced', action='store_true', default=False,
        help='[READ-ONLY] list elements whose selector region appears in the document '
             'in a different order than their LTAC declaration order; '
             'use --fixmisplaced to fix them',
    )
    parser.add_argument(
        '--leaves', action='store_true', default=False,
        help='[READ-ONLY] list leaf elements (no children in LTAC) with their options '
             'and references; leads with the {needssupport} subset',
    )
    parser.add_argument(
        '--packages', action='store_true', default=False,
        help='[READ-ONLY] list each package with element counts and the direct children '
             'of its root',
    )

    return parser.parse_args()


def find_ltac_file(ltac_arg: Optional[str], config: dict) -> str:
    """Determine the path of the LTAC file to load.

    Priority: --ltac argument > ltac_file config key > case.ltac > docs/case.ltac.
    Calls panic() (and exits) if no file can be found.
    """
    if ltac_arg:
        return ltac_arg
    ltac_from_config = config.get('ltac_file', '')
    if ltac_from_config:
        return ltac_from_config
    if os.path.exists('case.ltac'):
        return 'case.ltac'
    if os.path.exists('docs/case.ltac'):
        return 'docs/case.ltac'
    panic("no LTAC file found; use --ltac, set ltac_file in config, or create case.ltac. See --help")


# SACM spec section 11 defines AssertionStatus as a mutually exclusive
# enumeration: Asserted (default), NeedsSupport, Assumed, Axiomatic, Defeated,
# AsCited.  An Assumption node implicitly carries Assumed; a cross-citation
# (^ID) implicitly carries AsCited.


def check_id_info(id_info: Dict[str, dict]) -> None:
    """Validate identifier usage across the loaded LTAC.

    Uses the id_info table built during parsing (see LTACParser) to report:
    - IDs cited (^) but never declared (may indicate a missing package)
    """
    for ident, info in id_info.items():
        if info['citations'] > 0 and info['declarations'] == 0:
            warn(f"{ident}: cited but never declared")



def check_circularities(registry: Dict[str, Node], all_roots: List[Node]) -> None:
    """Panic if any circular dependency exists in the LTAC model.

    Performs an iterative DFS over the logical dependency graph.  For each
    node, its logical successors are its structural children (non-cited,
    non-Link), any cited child's declared node (^ID → registry[ID]), and
    any Link child's link_target.  A node encountered while already on the
    current DFS path (a back-edge) means circular reasoning is possible.
    """
    visiting: Set[int] = set()  # id(node) of nodes on the current DFS path
    done: Set[int] = set()      # id(node) of fully-explored nodes

    def successors(node: Node):
        for child in node.children:
            if child.is_cited:
                target = registry.get(child.identifier)
                if target is not None:
                    yield target
            elif child.node_type == 'Link':
                if child.link_target is not None:
                    yield child.link_target
            else:
                yield child

    def dfs(start: Node) -> None:
        path = [start]
        visiting.add(id(start))
        stack = [(start, successors(start))]
        while stack:
            node, children = stack[-1]
            try:
                succ = next(children)
                key = id(succ)
                if key in done:
                    continue
                if key in visiting:
                    start_idx = next(i for i, n in enumerate(path) if id(n) == key)
                    cycle = path[start_idx:] + [succ]
                    trail = ' -> '.join(n.identifier or f'({n.node_type})' for n in cycle)
                    panic(f"circularity detected: {trail}")
                visiting.add(key)
                path.append(succ)
                stack.append((succ, successors(succ)))
            except StopIteration:
                stack.pop()
                path.pop()
                visiting.discard(id(node))
                done.add(id(node))

    for root in all_roots:
        if id(root) not in done:
            dfs(root)
    for node in registry.values():
        if id(node) not in done:
            dfs(node)


def check_reachability(all_roots: List[Node], registry: Dict[str, Node]) -> None:
    """Error for any package whose root is unreachable from the first element.

    Skipped when there is only one package (everything is trivially reachable).
    Uses iterative DFS following structural children, citation declarations, and
    Link targets.  Because all structural children of a reachable node are also
    reachable, an unreachable package root implies the whole package is
    unreachable; reporting just the root is sufficient.
    """
    if len(all_roots) < 2:
        return

    reachable: Set[int] = set()
    stack = [all_roots[0]]
    while stack:
        node = stack.pop()
        if id(node) in reachable:
            continue
        reachable.add(id(node))
        for child in node.children:
            if child.is_cited:
                target = registry.get(child.identifier)
                if target is not None:
                    stack.append(target)
            elif child.node_type == 'Link':
                if child.link_target is not None:
                    stack.append(child.link_target)
            else:
                stack.append(child)

    for root in all_roots[1:]:
        if id(root) not in reachable:
            label = f"{root.node_type} {root.identifier}" if root.identifier else root.node_type
            error(f"{label}: package root is unreachable from {all_roots[0].node_type}"
                  f" {all_roots[0].identifier}")


def _is_dubious_reference(ref: str) -> bool:
    """Return True if ref is non-empty, has no '.' anywhere, and doesn't start with '#'.

    Such references are likely to be parenthetical comments accidentally parsed
    as references rather than genuine file paths or URLs.
    """
    return bool(ref) and '.' not in ref and not ref.startswith('#')





def _process_files(
    files: List[str],
    out,
    registry: Dict[str, Node],
    all_roots: List[Node],
    config: dict,
    id_info: Dict[str, dict],
    seen_element_ids: set,
    strip: bool = False,
) -> None:
    """Open each file and call process_document_stream; fall back to stdin if none given."""
    if files:
        for path in files:
            try:
                with open(path) as f:
                    process_document_stream(f, out, registry, all_roots, config, id_info,
                                            seen_element_ids, detect_doc_format(path),
                                            strip=strip)
            except OSError as e:
                error(f"cannot open {path!r}: {e}")
    else:
        process_document_stream(sys.stdin, out, registry, all_roots, config, id_info,
                                seen_element_ids, 'markdown', strip=strip)



_ASSERTION_STATUSES = frozenset({'needssupport', 'assumed', 'axiomatic', 'defeated', 'ascited'})


def _mark_needs_support(candidate_ids: List[str],
                        registry: Dict[str, Node]) -> int:
    """Add 'needssupport' option to leaf elements with no existing assertion status.

    Only modifies registry nodes that are leaves (no non-Link children), have no
    existing assertion status, and have no ext_ref (a non-empty reference is treated
    as providing support).  Assumption nodes implicitly carry 'assumed' and are
    skipped.  Returns count of elements modified.
    """
    count = 0
    for ident in candidate_ids:
        node = registry.get(ident)
        if node is None:
            continue
        real_children = [c for c in node.children if c.node_type != 'Link']
        if real_children:
            continue
        # Assumption nodes implicitly carry 'assumed'; don't add a conflicting status.
        if node.node_type == 'Assumption':
            continue
        if any(o in _ASSERTION_STATUSES for o in node.options):
            continue
        # A non-empty reference (ext_ref) provides support; no needssupport needed.
        if node.ext_ref:
            continue
        node.options.append('needssupport')
        count += 1
    if count:
        notify(f"Adding {count} needsSupport marking(s) to leaves in the LTAC file")
    return count


def _check_element_coverage(registry: Dict[str, Node], seen_element_ids: set) -> None:
    """Warn about every registry element with no corresponding element selector."""
    for ident in registry:
        if ident not in seen_element_ids:
            warn(f"element {ident!r} has no 'element' selector in any processed file")


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _compute_ltac_stats(all_roots: List['Node'], registry: Dict[str, 'Node'],
                        id_info: Dict[str, dict]) -> dict:
    """Compute statistics from the loaded LTAC forest."""
    from collections import Counter
    type_counts: Counter = Counter()
    option_counts: Counter = Counter()
    total_citations = 0
    leaf_claims = 0
    pkg_sizes = []

    for root in all_roots:
        size = 0
        for node in _all_nodes([root]):
            if node.is_cited:
                total_citations += 1
            else:
                type_counts[node.node_type] += 1
                size += 1
                for opt in node.options:
                    option_counts[opt] += 1
                if node.node_type == 'Claim' and not node.children:
                    leaf_claims += 1
        pkg_sizes.append((size, root.identifier or '(unnamed)'))

    largest_pkg = max(pkg_sizes, key=lambda x: x[0]) if pkg_sizes else (0, '')
    return {
        'type_counts':     type_counts,
        'total_elements':  sum(type_counts.values()),
        'total_citations': total_citations,
        'leaf_claims':     leaf_claims,
        'largest_pkg':     largest_pkg,
        'option_counts':   option_counts,
    }


def _scan_doc_stats(path: str) -> dict:
    """Scan a document file and return document-level statistics."""
    pkg_regions = 0
    elem_regions = 0
    config_stmts = 0
    empty_elem_regions = 0

    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return {}

    i = 0
    in_elem_region = False
    after_end = False
    gap_has_content = False

    while i < len(lines):
        text = lines[i].rstrip('\r\n')
        cm = _CASEPROC_CONFIG_RE.match(text)
        if cm:
            config_stmts += 1
            i += 1
            continue
        m = _CASEPROC_REGION_RE.match(text)
        if m:
            if after_end and not gap_has_content:
                empty_elem_regions += 1
            after_end = False
            gap_has_content = False
            selector = m.group(1)
            kind = selector.split()[0] if selector else ''
            if kind == 'package':
                pkg_regions += 1
            elif kind == 'element':
                elem_regions += 1
                in_elem_region = True
            i += 1
            while i < len(lines):
                t = lines[i].rstrip('\r\n')
                if t.strip() == '<!-- end verocase -->':
                    if in_elem_region:
                        after_end = True
                    in_elem_region = False
                    i += 1
                    break
                i += 1
            continue
        if after_end and text.strip() and not text.strip().startswith('<!--'):
            gap_has_content = True
        i += 1

    if after_end and not gap_has_content:
        empty_elem_regions += 1

    return {
        'pkg_regions':        pkg_regions,
        'elem_regions':       elem_regions,
        'config_stmts':       config_stmts,
        'empty_elem_regions': empty_elem_regions,
    }


def _print_stats(ltac_stats: dict, doc_stats: Optional[dict]) -> None:
    """Print a statistics report to stdout."""
    print('=== verocase statistics ===')
    print()
    print('LTAC structure:')
    print('  Elements by type:')
    type_counts = ltac_stats['type_counts']
    if type_counts:
        max_len = max(len(t) for t in type_counts)
        for node_type, count in sorted(type_counts.items()):
            print(f'    {node_type:<{max_len}}  {count}')
    else:
        print('    (none)')
    print(f"  Total elements defined:               {ltac_stats['total_elements']}")
    print(f"  Total citations:                      {ltac_stats['total_citations']}")
    print(f"  Leaf Claims (no children, not cited): {ltac_stats['leaf_claims']}")
    pkg_size, pkg_name = ltac_stats['largest_pkg']
    print(f'  Largest package: {pkg_name} ({pkg_size} elements)')
    option_counts = ltac_stats['option_counts']
    if option_counts:
        print('  Elements with each option:')
        max_opt = max(len(o) for o in option_counts)
        for opt, count in sorted(option_counts.items()):
            print(f'    {opt:<{max_opt}}  {count}')
    if doc_stats is not None:
        print()
        print('Documents:')
        pkg_r = doc_stats['pkg_regions']
        typical = '  (typical)' if pkg_r == 1 else ''
        print(f"  Package regions:         {pkg_r}{typical}")
        print(f"  Element regions:         {doc_stats['elem_regions']}")
        if doc_stats['config_stmts']:
            print(f"  Config statements:       {doc_stats['config_stmts']}")
        print(f"  Elements with no prose:  {doc_stats['empty_elem_regions']}")


def _write_ltac_node(node: 'Node', lines: list) -> None:
    """Append LTAC lines for *node* and all its descendants to *lines*."""
    indent = '  ' * node.depth
    line = f'{indent}- {node.node_type}'
    write_id = (node.identifier or node.is_cited) and not (
        node.id_inferred and _infer_id(node.text) == node.identifier
    )
    if write_id:
        line += ' '
        if node.is_cited:
            line += '^'
        line += node.identifier
    if node.text:
        line += f': {node.text}'
    if node.options:
        line += ' {' + ', '.join(node.options) + '}'
    elif node.text and node.text.endswith('}'):
        line += ' {}'  # escape: text ends with '}', no real options to disambiguate
    if node.ext_ref:
        line += f' ({node.ext_ref})'
    elif node.text and node.text.endswith(')') and not node.options:
        line += ' ()'  # escape: text ends with ')', no real ref or options to disambiguate
    lines.append(line)
    for child in node.children:
        _write_ltac_node(child, lines)


def write_ltac(roots: List['Node']) -> str:
    """Serialize a Node forest back to LTAC text.

    Packages are separated by blank lines; the result ends with a newline.

    >>> p = LTACParser()
    >>> roots = p.parse(['- Claim C1: The software is safe',
    ...                  '  - Evidence E1: Test results (tests.pdf)'])
    >>> write_ltac(roots)
    '- Claim C1: The software is safe\\n  - Evidence E1: Test results (tests.pdf)\\n'
    """
    lines: List[str] = []
    for i, root in enumerate(roots):
        if i > 0:
            lines.append('')
        _write_ltac_node(root, lines)
    if lines:
        lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _scan_document_elements(paths):
    """Scan document files and return element region info.

    Returns a tuple (ordered_ids, id_info) where:
    - ordered_ids: list of (identifier, filepath, lineno) for element regions,
      in document order
    - id_info: dict mapping identifier ->
      {'has_prose': bool, 'filepath': str, 'lineno': int}
    """
    ordered_ids = []
    id_info = {}

    for path in paths:
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except OSError:
            continue

        i = 0
        in_elem_region = False
        current_ident = None
        current_lineno = None
        after_end = False
        gap_has_content = False

        while i < len(lines):
            text = lines[i].rstrip('\r\n')
            # Skip config lines
            cm = _CASEPROC_CONFIG_RE.match(text)
            if cm:
                i += 1
                continue
            m = _CASEPROC_REGION_RE.match(text)
            if m:
                # If we were tracking prose after an end marker, finalize
                if after_end and current_ident is not None:
                    id_info[current_ident]['has_prose'] = gap_has_content
                after_end = False
                gap_has_content = False
                in_elem_region = False
                current_ident = None
                current_lineno = None

                selector = m.group(1)
                parts = selector.split(None, 1)
                kind = parts[0] if parts else ''
                if kind == 'element' and len(parts) == 2:
                    ident = parts[1].strip()
                    in_elem_region = True
                    current_ident = ident
                    current_lineno = i + 1  # 1-based
                    ordered_ids.append((ident, path, i + 1))
                    id_info[ident] = {'has_prose': False, 'filepath': path, 'lineno': i + 1}

                i += 1
                # Consume until end verocase
                while i < len(lines):
                    t = lines[i].rstrip('\r\n')
                    if t.strip() == '<!-- end verocase -->':
                        if in_elem_region:
                            after_end = True
                        in_elem_region = False
                        i += 1
                        break
                    i += 1
                continue

            # Check for prose after end verocase
            if after_end and text.strip() and not text.strip().startswith('<!--'):
                gap_has_content = True
            i += 1

        # Finalize the last region
        if after_end and current_ident is not None:
            id_info[current_ident]['has_prose'] = gap_has_content

    return ordered_ids, id_info


def _analysis_missing(all_roots, registry, document_files):
    """Print analysis of LTAC elements missing from documents."""
    ordered_ids, _ = _scan_document_elements(document_files)
    seen = {ident for ident, _, _ in ordered_ids}
    all_ids_ordered = [node for node in _all_nodes_forward(all_roots)
                       if not node.is_cited and node.identifier
                       and node.node_type not in ('Link',)]
    missing = [node for node in all_ids_ordered if node.identifier not in seen]
    print("Elements missing a selector region in the document(s):")
    if not missing:
        print("  (none)")
    else:
        for node in missing:
            print(f"{node.node_type} {node.identifier}")


def _analysis_empty(document_files, registry):
    """Print analysis of elements with selector regions but no prose."""
    _, elem_info = _scan_document_elements(document_files)
    empty = [(ident, info) for ident, info in elem_info.items() if not info['has_prose']]
    print("Elements with no prose in the document(s):")
    if not empty:
        print("  (none)")
    else:
        for ident, info in empty:
            node = registry.get(ident)
            type_str = node.node_type if node else '?'
            print(f"{type_str} {ident}")


def _analysis_orphans(document_files, registry):
    """Print analysis of document regions not in LTAC."""
    ordered_ids, elem_info = _scan_document_elements(document_files)
    orphans = [(ident, info) for ident, info in elem_info.items() if ident not in registry]
    print("Orphaned selector regions in the document(s) (not in LTAC):")
    if not orphans:
        print("  (none)")
    else:
        for ident, info in orphans:
            print(f"element {ident}")


def _analysis_misplaced(document_files, all_roots, registry):
    """Print analysis of elements whose document order differs from LTAC order.

    Returns a list of (ident, lineno, filepath, expected_predecessor_ident) tuples
    for misplaced elements.  Prints the analysis report.
    """
    # LTAC order: depth-first forward order, exclude citations and Links
    ltac_order = [node.identifier for node in _all_nodes_forward(all_roots)
                  if not node.is_cited and node.identifier
                  and node.node_type not in ('Link',)]
    ltac_pos = {ident: i for i, ident in enumerate(ltac_order)}

    # Document order: only elements that are also in the registry
    ordered_ids, elem_info = _scan_document_elements(document_files)
    doc_entries = [(ident, filepath, lineno) for ident, filepath, lineno in ordered_ids
                   if ident in registry]

    if not doc_entries:
        print("Misplaced elements (document order differs from LTAC order):")
        print("  (none)")
        return []

    # Find misplaced elements: those not in the LCS of LTAC order within document order.
    # LCS algorithm: find longest subsequence of doc_entries whose LTAC positions are
    # monotonically increasing.
    doc_ids = [ident for ident, _, _ in doc_entries]

    # Compute LCS (patience sorting / LIS in LTAC rank space)
    ranks = [ltac_pos.get(ident, -1) for ident in doc_ids]
    # Longest increasing subsequence indices
    from bisect import bisect_left
    tails = []   # tails[i] = smallest ending rank for an increasing subsequence of length i+1
    tail_idx = []  # index in doc_entries corresponding to each tail
    predecessor = [-1] * len(doc_ids)

    for i, r in enumerate(ranks):
        if r < 0:
            continue  # skip elements not in LTAC (shouldn't happen since we filter above)
        pos = bisect_left(tails, r)
        if pos == len(tails):
            tails.append(r)
            tail_idx.append(i)
        else:
            tails[pos] = r
            tail_idx[pos] = i
        if pos > 0:
            predecessor[i] = tail_idx[pos - 1]

    # Reconstruct LCS indices
    if not tail_idx:
        lis_indices = set()
    else:
        lis_indices = set()
        idx = tail_idx[-1]
        while idx >= 0:
            lis_indices.add(idx)
            idx = predecessor[idx]

    # Misplaced = elements in doc_entries that are NOT in the LIS
    misplaced_entries = []
    for i, (ident, filepath, lineno) in enumerate(doc_entries):
        if i not in lis_indices:
            misplaced_entries.append((ident, lineno, filepath))

    print("Misplaced elements (document order differs from LTAC order):")
    if not misplaced_entries:
        print("  (none)")
        return []

    # For each misplaced element, find expected predecessor in LTAC order
    # (nearest preceding element in LTAC order that has a document entry)
    doc_id_to_entry = {ident: (lineno, filepath) for ident, filepath, lineno in doc_entries}
    result = []
    for ident, lineno, filepath in misplaced_entries:
        ltac_idx = ltac_pos.get(ident, -1)
        pred_ident = None
        for j in range(ltac_idx - 1, -1, -1):
            candidate = ltac_order[j]
            if candidate in doc_id_to_entry:
                pred_ident = candidate
                break
        node = registry.get(ident)
        type_str = node.node_type if node else '?'
        if pred_ident is not None:
            pred_lineno, pred_filepath = doc_id_to_entry[pred_ident]
            pred_node = registry.get(pred_ident)
            pred_type = pred_node.node_type if pred_node else '?'
            print(f"{type_str} {ident}: at line {lineno}, expected after {pred_type} {pred_ident} (line {pred_lineno})")
        else:
            print(f"{type_str} {ident}: at line {lineno}, expected at start of document")
        result.append((ident, lineno, filepath, pred_ident))
    return result


def _ltac_node_line(node, depth_offset=0):
    """Format a single LTAC node as a line string, with depth normalized by depth_offset."""
    indent = '  ' * (node.depth - depth_offset)
    line = f'{indent}- {node.node_type}'
    write_id = (node.identifier or node.is_cited) and not (
        node.id_inferred and _infer_id(node.text) == node.identifier
    )
    if write_id:
        line += ' '
        if node.is_cited:
            line += '^'
        line += node.identifier
    if node.text:
        line += f': {node.text}'
    if node.options:
        line += ' {' + ', '.join(node.options) + '}'
    elif node.text and node.text.endswith('}'):
        line += ' {}'
    if node.ext_ref:
        line += f' ({node.ext_ref})'
    elif node.text and node.text.endswith(')') and not node.options:
        line += ' ()'
    return line


def _analysis_leaves(all_roots):
    """Print list of leaf elements."""
    leaves = []
    for node in _all_nodes_forward(all_roots):
        if node.is_cited or node.node_type in ('Link',):
            continue
        if node.node_type in ('Strategy', 'Context'):
            # Omit Strategy/Context leaves unless they carry a problem flag
            if not node.children:
                has_problem = any(o in ('needssupport', 'defeated') for o in node.options)
                if not has_problem:
                    continue
        if not node.children:
            leaves.append(node)

    ns_leaves = [n for n in leaves if 'needssupport' in n.options]

    print("Leaf elements:")
    if ns_leaves:
        print("Leaves with {needssupport}:")
        for n in ns_leaves:
            print(_ltac_node_line(n, depth_offset=n.depth))
        print()
    print("All leaves:")
    if not leaves:
        print("  (none)")
    else:
        for n in leaves:
            print(_ltac_node_line(n, depth_offset=n.depth))


def _subtree_count(node):
    """Count node and all its descendants."""
    count = 0
    stack = [node]
    while stack:
        n = stack.pop()
        count += 1
        stack.extend(n.children)
    return count


def _analysis_packages(all_roots):
    """Print package structure with element counts."""
    print("Packages:")
    for root in all_roots:
        pkg_count = _subtree_count(root)
        root_line = _ltac_node_line(root, depth_offset=0)
        print(f"Package {root.identifier} ({pkg_count} elements)")
        print(root_line)
        for child in root.children:
            child_count = _subtree_count(child)
            child_line = _ltac_node_line(child, depth_offset=0)
            print(f"{child_line} ({child_count} elements)")
        print()


def render_ltac_txt(node_list, config=None):
    """Render a list of nodes as raw LTAC text, normalizing indentation to depth 0.

    Each node in node_list is treated as a root; its subtree is rendered
    with the node at depth 0 regardless of its actual tree depth.
    """
    lines = []
    for root in node_list:
        depth_offset = root.depth
        _write_ltac_node_normalized(root, lines, depth_offset)
    return '\n'.join(lines)


def _write_ltac_node_normalized(node, lines, depth_offset):
    """Append LTAC lines for node and all its descendants, normalizing depth."""
    lines.append(_ltac_node_line(node, depth_offset=depth_offset))
    for child in node.children:
        _write_ltac_node_normalized(child, lines, depth_offset)


def render_info(element_id, all_roots, registry, id_info):
    """Render full context for a single element ID to a string."""
    node = registry.get(element_id)
    if node is None:
        error(f"info: element {element_id!r} not found")
        return ''

    lines = []

    # Element header line
    header = f"{node.node_type} {node.identifier}"
    if node.text:
        header += f": {node.text}"
    lines.append(f"Element: {header}")

    # Package
    pkg_root = node
    while pkg_root.parent is not None:
        pkg_root = pkg_root.parent
    pkg_name = pkg_root.identifier or '(unnamed)'
    lines.append(f"Package: {pkg_name}")

    # Ancestors
    ancestors = []
    anc = node.parent
    while anc is not None:
        ancestors.append(anc)
        anc = anc.parent
    ancestors.reverse()  # root first

    if not ancestors:
        lines.append("Ancestors: (package root)")
    else:
        lines.append("Ancestors (root first):")
        for anc in ancestors:
            lines.append("  " + _ltac_node_line(anc, depth_offset=anc.depth))

    # Children
    if not node.children:
        lines.append("Children: (none)")
    else:
        lines.append("Children:")
        for child in node.children:
            lines.append("  " + _ltac_node_line(child, depth_offset=child.depth))

    # Descendants count (including self)
    desc_count = _subtree_count(node)
    lines.append(f"Descendants: {desc_count} (including self, all descendants, citations, and links in subtree)")

    # Citations: how many times this element is cited by others
    info = id_info.get(element_id, {})
    citation_count = info.get('citations', 0)
    citing_pkg_ids = info.get('citing_pkg_ids', [])
    lines.append(f"Citations: {citation_count}")
    if citation_count > 0:
        # Find the actual citing nodes
        for citing_pkg_id in citing_pkg_ids:
            citing_root = registry.get(citing_pkg_id)
            if citing_root is None:
                continue
            # Walk the citing package to find nodes that cite element_id
            for n in _all_nodes([citing_root]):
                if n.is_cited and n.identifier == element_id:
                    parent_node = n.parent
                    if parent_node:
                        parent_desc = f"{parent_node.node_type} {parent_node.identifier}"
                        citing_pkg_root = parent_node
                        while citing_pkg_root.parent is not None:
                            citing_pkg_root = citing_pkg_root.parent
                        cp_name = citing_pkg_root.identifier or '(unnamed)'
                        lines.append(f"  Cited as ^{element_id} by: {parent_desc} (Package {cp_name})")
                    else:
                        lines.append(f"  Cited as ^{element_id} (package root)")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Smart missing-element placement
# ---------------------------------------------------------------------------

def _scan_region_ends(lines):
    """Scan a list of lines and return a dict mapping element ident -> last line index.

    The 'last line index' is the index of the last line of the element's full
    region: the <!-- end verocase --> line and all following prose lines up to
    (but not including) the next verocase marker or end of file.
    """
    ident_region_end = {}
    i = 0
    current_ident = None
    after_end = False

    while i < len(lines):
        text = lines[i].rstrip('\r\n')
        cm = _CASEPROC_CONFIG_RE.match(text)
        if cm:
            if after_end and current_ident is not None:
                ident_region_end[current_ident] = i - 1
            after_end = False
            current_ident = None
            i += 1
            continue
        m = _CASEPROC_REGION_RE.match(text)
        if m:
            if after_end and current_ident is not None:
                ident_region_end[current_ident] = i - 1
            after_end = False
            selector = m.group(1)
            parts = selector.split(None, 1)
            kind = parts[0] if parts else ''
            if kind == 'element' and len(parts) == 2:
                current_ident = parts[1].strip()
            else:
                current_ident = None
            i += 1
            while i < len(lines):
                t = lines[i].rstrip('\r\n')
                if t.strip() == '<!-- end verocase -->':
                    if current_ident is not None:
                        after_end = True
                    i += 1
                    break
                i += 1
            continue
        i += 1

    if after_end and current_ident is not None:
        ident_region_end[current_ident] = len(lines) - 1

    return ident_region_end


def _insert_missing_stubs(content, all_roots, registry, id_info, config,
                          seen_element_ids, doc_format):
    """Insert missing element stubs at their natural positions in the document.

    Processes insertions one at a time in LTAC order, updating line positions
    after each insertion so that subsequent elements can find their correct
    predecessor.

    content: document content after normal re-rendering (existing regions updated)
    Returns: (new_content, count_added)
    """
    # Get LTAC order: all declared non-cited non-Link elements
    ltac_ordered = [node for node in _all_nodes_forward(all_roots)
                    if not node.is_cited and node.identifier
                    and node.node_type not in ('Link',)]

    missing = [node for node in ltac_ordered
               if node.identifier not in seen_element_ids]
    if not missing:
        return content, 0

    lines = content.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]
        had_trailing_newline = True
    else:
        had_trailing_newline = False

    placed_ids = set(seen_element_ids)
    inj_state = DocState(doc_format=doc_format, seen_element_ids=set(seen_element_ids))

    for node in missing:
        ident = node.identifier
        ltac_idx = ltac_ordered.index(node)

        # Re-scan the current lines to get up-to-date positions
        ident_region_end = _scan_region_ends(lines)

        # Find nearest predecessor in LTAC order that has a region in current lines
        pred_ident = None
        for j in range(ltac_idx - 1, -1, -1):
            candidate = ltac_ordered[j].identifier
            if candidate in placed_ids and candidate in ident_region_end:
                pred_ident = candidate
                break

        # Build the stub content
        rendered = render_element_selector(ident, registry, [], id_info, config, inj_state)
        stub_lines = ['', f'<!-- verocase element {ident} -->']
        stub_lines.extend(rendered.split('\n'))
        stub_lines.append('<!-- end verocase -->')
        stub_lines.append('')

        if pred_ident is not None:
            after_line = ident_region_end[pred_ident]
        else:
            after_line = len(lines) - 1

        # Insert stub_lines immediately after after_line
        lines[after_line + 1:after_line + 1] = stub_lines
        placed_ids.add(ident)

    new_content = '\n'.join(lines)
    if had_trailing_newline:
        new_content += '\n'

    notify(f"Adding {len(missing)} formerly missing element(s)")
    return new_content, len(missing)


# ---------------------------------------------------------------------------
# --fixmisplaced implementation
# ---------------------------------------------------------------------------

def _fixmisplaced_document(path, all_roots, registry, id_info, config,
                           seen_element_ids, doc_format):
    """Move misplaced element regions to their correct LTAC order positions.

    Returns a (tmp_path, final_path) pair, or None if no changes or error.
    """
    try:
        with open(path, newline='') as f:
            original = f.read()
    except OSError as e:
        error(f"cannot open {path!r}: {e}")
        return None

    line_ending = detect_line_ending(original)
    content = original.replace('\r\n', '\n')
    lines = content.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]
        had_trailing = True
    else:
        had_trailing = False

    # Scan document to find element regions (start line, end line of full region)
    # A "full region" is from <!-- verocase element X --> through the end of
    # following prose (up to but not including the next verocase marker).
    # Format: ident -> (start_line_idx, end_line_idx)  (0-based, inclusive)
    region_map = {}   # ident -> (start_idx, end_idx)
    region_order = [] # ident in document order

    i = 0
    current_ident = None
    region_start = None
    after_end = False
    end_line_idx = None

    while i < len(lines):
        text = lines[i].rstrip('\r\n')
        cm = _CASEPROC_CONFIG_RE.match(text)
        if cm:
            if after_end and current_ident is not None:
                region_map[current_ident] = (region_start, i - 1)
            after_end = False
            current_ident = None
            i += 1
            continue
        m = _CASEPROC_REGION_RE.match(text)
        if m:
            if after_end and current_ident is not None:
                region_map[current_ident] = (region_start, i - 1)
            after_end = False
            current_ident = None
            selector = m.group(1)
            parts = selector.split(None, 1)
            kind = parts[0] if parts else ''
            if kind == 'element' and len(parts) == 2:
                current_ident = parts[1].strip()
                region_start = i
                region_order.append(current_ident)
            i += 1
            while i < len(lines):
                t = lines[i].rstrip('\r\n')
                if t.strip() == '<!-- end verocase -->':
                    if current_ident is not None:
                        after_end = True
                        end_line_idx = i
                    i += 1
                    break
                i += 1
            continue
        i += 1

    if after_end and current_ident is not None:
        region_map[current_ident] = (region_start, len(lines) - 1)

    # Get LTAC order
    ltac_order = [node.identifier for node in _all_nodes_forward(all_roots)
                  if not node.is_cited and node.identifier
                  and node.node_type not in ('Link',)]
    ltac_pos = {ident: i for i, ident in enumerate(ltac_order)}

    # Find elements that are in both LTAC and document
    doc_with_regions = [ident for ident in region_order if ident in registry]

    if not doc_with_regions:
        return None

    # Find misplaced elements (same LIS algorithm as _analysis_misplaced)
    ranks = [ltac_pos.get(ident, -1) for ident in doc_with_regions]
    from bisect import bisect_left
    tails = []
    tail_idx = []
    predecessor = [-1] * len(doc_with_regions)

    for i, r in enumerate(ranks):
        if r < 0:
            continue
        pos = bisect_left(tails, r)
        if pos == len(tails):
            tails.append(r)
            tail_idx.append(i)
        else:
            tails[pos] = r
            tail_idx[pos] = i
        if pos > 0:
            predecessor[i] = tail_idx[pos - 1]

    if not tail_idx:
        lis_indices = set()
    else:
        lis_indices = set()
        idx = tail_idx[-1]
        while idx >= 0:
            lis_indices.add(idx)
            idx = predecessor[idx]

    misplaced = [doc_with_regions[i] for i in range(len(doc_with_regions))
                 if i not in lis_indices]

    if not misplaced:
        return None

    # Process moves in LTAC order (forward through LTAC, not document order)
    # For each misplaced element: remove from current position, insert after predecessor
    # Work with a mutable list of lines
    result = list(lines)

    def find_region(lines_list, ident):
        """Find (start_idx, end_idx) of an element region in lines_list."""
        i = 0
        while i < len(lines_list):
            text = lines_list[i].rstrip('\r\n')
            m = _CASEPROC_REGION_RE.match(text)
            if m:
                selector = m.group(1)
                parts = selector.split(None, 1)
                kind = parts[0] if parts else ''
                if kind == 'element' and len(parts) == 2 and parts[1].strip() == ident:
                    start = i
                    i += 1
                    # Find end verocase
                    while i < len(lines_list):
                        t = lines_list[i].rstrip('\r\n')
                        if t.strip() == '<!-- end verocase -->':
                            i += 1
                            break
                        i += 1
                    # Consume trailing prose until next verocase marker
                    while i < len(lines_list):
                        t = lines_list[i].rstrip('\r\n')
                        next_m = _CASEPROC_REGION_RE.match(t)
                        next_cm = _CASEPROC_CONFIG_RE.match(t)
                        if next_m or next_cm or t.strip() == '<!-- end verocase -->':
                            break
                        i += 1
                    end = i - 1
                    return start, end
            i += 1
        return None, None

    def find_region_end(lines_list, ident):
        """Find the last line index of the full region for ident."""
        start, end = find_region(lines_list, ident)
        return end

    notify(f"Fixing {len(misplaced)} misplaced element region(s) in {path}")

    # Process misplaced elements in LTAC order
    misplaced_set = set(misplaced)
    for ltac_ident in ltac_order:
        if ltac_ident not in misplaced_set:
            continue

        # Find predecessor (nearest preceding element in LTAC order with a region)
        ltac_idx = ltac_pos[ltac_ident]
        pred_ident = None
        for j in range(ltac_idx - 1, -1, -1):
            candidate = ltac_order[j]
            # Check if this candidate has a region in the current result
            s, e = find_region(result, candidate)
            if s is not None:
                pred_ident = candidate
                break

        # Extract the full region for ltac_ident
        start, end = find_region(result, ltac_ident)
        if start is None:
            continue

        region_lines = result[start:end + 1]

        # Remove the region from its current location
        # Also remove a leading blank line before the region if present
        remove_start = start
        if remove_start > 0 and result[remove_start - 1].strip() == '':
            remove_start -= 1
        del result[remove_start:end + 1]

        # Find the new insertion point
        if pred_ident is not None:
            insert_after = find_region_end(result, pred_ident)
            if insert_after is None:
                insert_after = len(result) - 1
        else:
            insert_after = -1  # insert at beginning

        # Insert: blank line separator + region lines
        insert_pos = insert_after + 1
        to_insert = [''] + region_lines
        result[insert_pos:insert_pos] = to_insert

    new_content = '\n'.join(result)
    if had_trailing:
        new_content += '\n'

    if new_content == content:
        return None

    tmp = _make_temp(path, new_content, line_ending)
    if tmp is None:
        return None
    return (tmp, path)


def make_backup(pairs: List[Tuple[str, str]], ltac_path: str,
                config: dict, config_path: Optional[str]) -> None:
    """Create a timestamped backup snapshot of files about to be modified.

    Backs up all final_path files from *pairs*, the LTAC file, and the config
    file (if any) into a single timestamped subdirectory under .backups/ next
    to the LTAC file.  Directory structure relative to the LTAC directory is
    preserved.  Files outside the LTAC directory are stored under absolute/.

    Old snapshots are silently rotated when the count exceeds max_backups.
    Setting max_backups to 0 disables backups entirely.
    """
    max_backups = config.get('max_backups', DEFAULT_CONFIG['max_backups'])
    if max_backups <= 0:
        return

    now = datetime.datetime.now()
    ts = now.strftime('%Y-%m-%dT%H%M%S') + f'.{now.microsecond // 10000:02d}'

    ltac_dir = os.path.dirname(os.path.abspath(ltac_path))
    backups_dir = os.path.join(ltac_dir, '.backups')
    snapshot_dir = os.path.join(backups_dir, ts)

    srcs = {os.path.abspath(f) for _, f in pairs} | {os.path.abspath(ltac_path)}
    if config_path:
        srcs.add(os.path.abspath(config_path))

    try:
        os.makedirs(snapshot_dir, exist_ok=True)
    except OSError:
        return  # best-effort: skip backup if snapshot dir can't be created

    for src in sorted(srcs):
        try:
            rel = os.path.relpath(src, ltac_dir)
            if rel.startswith('..'):
                rel = os.path.join('absolute', src.lstrip(os.sep))
            dst = os.path.join(snapshot_dir, rel)
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            shutil.copy2(src, dst)
        except OSError:
            pass  # best-effort: skip files that can't be read or written

    # Rotate: silently remove oldest snapshots when over the limit.
    try:
        snapshots = sorted(e for e in os.listdir(backups_dir)
                           if os.path.isdir(os.path.join(backups_dir, e)))
        for old in snapshots[:-max_backups]:
            shutil.rmtree(os.path.join(backups_dir, old), ignore_errors=True)
    except OSError:
        pass


def commit_updates(pairs: List[Tuple[str, str]], ltac_path: str,
                   config: dict, config_path: Optional[str]) -> None:
    """Atomically update files by backing up originals and moving in new versions.

    *pairs* is a list of (tmp_path, final_path).  A timestamped backup snapshot
    is first created under .backups/ next to the LTAC file, then the temp files
    are moved to their final locations.  This minimises the window when files
    are absent.
    """
    notify("Updating " + " ".join(os.path.basename(fp) for _, fp in pairs))
    make_backup(pairs, ltac_path, config, config_path)
    for tmp, final in pairs:
        try:
            os.replace(tmp, final)
        except OSError as e:
            panic(f"cannot update {final!r}: {e}")


def _get_pkg_root(node: Node) -> Node:
    """Walk parent links to return the package root of node."""
    while node.parent is not None:
        node = node.parent
    return node


def _update_pkg_id_for_subtree(node: Node, old_pkg_id: str, new_pkg_id: str,
                                id_info: Dict[str, dict]) -> None:
    """Update decl_pkg_id in id_info for node and all its descendants."""
    for n in _all_nodes([node]):
        if n.identifier and n.identifier in id_info:
            info = id_info[n.identifier]
            if info.get('decl_pkg_id') == old_pkg_id:
                info['decl_pkg_id'] = new_pkg_id


def apply_rename(roots: List[Node], registry: Dict[str, Node],
                 id_info: Dict[str, dict], old: str, new: str) -> None:
    """Rename identifier old to new throughout the LTAC forest.

    Panics if old is not declared or new is already declared.
    Updates all node identifiers, the registry, id_info, and cross-references.
    """
    if old not in registry:
        panic(f"--rename: {old!r} is not a declared identifier")
    if new in registry:
        panic(f"--rename: {new!r} is already declared")
    for node in _all_nodes(roots):
        if node.identifier == old:
            node.identifier = new
    registry[new] = registry.pop(old)
    id_info[new] = id_info.pop(old)
    for entry in id_info.values():
        if entry.get('decl_pkg_id') == old:
            entry['decl_pkg_id'] = new
        entry['citing_pkg_ids'] = [new if x == old else x
                                   for x in entry.get('citing_pkg_ids', [])]


def apply_restate(roots: List[Node], registry: Dict[str, Node],
                  id_info: Dict[str, dict], label: str, stmt: str) -> None:
    """Update the statement text for label on all nodes and in id_info.

    Panics if label is not declared.
    """
    if label not in registry:
        panic(f"--restate: {label!r} is not a declared identifier")
    for node in _all_nodes(roots):
        if node.identifier == label:
            node.text = stmt
    id_info[label]['statement'] = stmt


def apply_detach(roots: List[Node], registry: Dict[str, Node],
                 id_info: Dict[str, dict], target_id: str) -> None:
    """Replace target_id's definition with a citation; promote subtree to new package.

    Panics if target_id is not defined, or if its definition is already a
    top-level package root (has no parent).
    """
    node = registry.get(target_id)
    if node is None:
        panic(f"--detach: {target_id!r} is not defined")
    if node.parent is None:
        panic(f"--detach: {target_id!r} is a top-level package root; cannot detach")

    parent = node.parent
    idx = parent.children.index(node)

    # Build a cited replacement node at the same position.
    cited = Node(
        node_type=node.node_type,
        identifier=node.identifier,
        text=node.text,
        ext_ref='',
        options=[],
        children=[],
        is_cited=True,
        depth=node.depth,
        parent=parent,
        link_target=None,
        diagram_id=None,
    )
    parent.children[idx] = cited

    # Detach the definition node and make it a new package root.
    node.parent = None
    _recalc_depths(node, 0)
    roots.append(node)

    # Update id_info: the new package root ID for node and all descendants.
    new_pkg_id = node.identifier
    old_pkg_id = id_info.get(node.identifier, {}).get('decl_pkg_id')
    _update_pkg_id_for_subtree(node, old_pkg_id, new_pkg_id, id_info)

    # Record the new citation under the original package.
    id_info[target_id]['citations'] = id_info[target_id].get('citations', 0) + 1
    citing_pkg = _get_pkg_root(cited).identifier
    if citing_pkg and citing_pkg not in id_info[target_id].get('citing_pkg_ids', []):
        id_info[target_id].setdefault('citing_pkg_ids', []).append(citing_pkg)


def apply_move(roots: List[Node], registry: Dict[str, Node],
               id_info: Dict[str, dict], target_id: str, dest_id: str) -> None:
    """Move target_id's definition to be a child of dest_id.

    ID may be top-level or nested anywhere in the tree. No citation is left
    at the original location. If a ^ID citation already exists as a direct
    child of dest_id it is replaced by the definition (citation count
    decreases by 1); otherwise the definition is appended as the last child.
    To leave a citation behind when moving a non-top-level node, run
    --detach ID first (which creates ^ID in place), then --move ID DESTINATION.

    Panics if target_id or dest_id is not defined.
    """
    node = registry.get(target_id)
    if node is None:
        panic(f"--move: {target_id!r} is not defined")
    dest = registry.get(dest_id)
    if dest is None:
        panic(f"--move: {dest_id!r} is not defined")

    # Remember old decl_pkg_id before detaching.
    old_pkg_id = id_info.get(target_id, {}).get('decl_pkg_id')

    # Detach node from its current location (no citation left behind).
    if node.parent is None:
        roots.remove(node)
    else:
        node.parent.children.remove(node)
        node.parent = None

    # Find a pre-existing ^ID citation among dest's direct children.
    cited_idx = None
    for i, child in enumerate(dest.children):
        if child.is_cited and child.identifier == target_id:
            cited_idx = i
            break

    # Insert node under dest.
    if cited_idx is not None:
        dest.children[cited_idx] = node
        id_info[target_id]['citations'] = max(
            0, id_info[target_id].get('citations', 1) - 1)
    else:
        dest.children.append(node)

    node.parent = dest
    _recalc_depths(node, dest.depth + 1)

    # Update decl_pkg_id for node and all its descendants.
    new_pkg_id = _get_pkg_root(dest).identifier
    _update_pkg_id_for_subtree(node, old_pkg_id, new_pkg_id, id_info)


def _make_temp(path: str, content: str, line_ending: str = '\n') -> Optional[str]:
    """Write content to a temp file in the same directory as path.

    If line_ending is '\\r\\n', converts all '\\n' to '\\r\\n' before writing.
    Returns the temp file path, or None if writing failed (error already reported).
    """
    dir_ = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(dir=dir_)
        try:
            encoded = content.replace('\n', line_ending).encode('utf-8')
            with os.fdopen(fd, 'wb') as f:
                f.write(encoded)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return tmp
    except OSError as e:
        error(f"cannot write temp file for {path!r}: {e}")
        return None


def apply_ltac_update(roots: List[Node], registry: Dict[str, Node]) -> int:
    """Update cited/Link node text to match the declaration's statement text.

    Walks all nodes; for any cited or Link node whose text differs from the
    declaration node's text in registry, replaces it.  Returns the count of
    nodes changed.  Uses the declaration node (registry) rather than id_info
    so the authoritative text is always the declaration regardless of parse order.
    """
    count = 0
    for node in _all_nodes(roots):
        if not node.identifier or not (node.is_cited or node.node_type == 'Link'):
            continue
        decl = registry.get(node.identifier)
        canonical = decl.text if decl is not None else None
        if node.text and canonical is not None and node.text != canonical:
            node.text = canonical
            count += 1
    return count


def _inline_rewrite_file(
    path: str,
    registry: Dict[str, Node],
    all_roots: List[Node],
    config: dict,
    id_info: Dict[str, dict],
    seen_element_ids: set,
    add_missing: bool = False,
    strip: bool = False,
) -> Optional[Tuple[str, str]]:
    """Process a single document file, writing updated content to a temp file.

    Returns a (tmp_path, final_path) pair if the file needs updating, or None
    if the content is unchanged or an error occurred.

    When add_missing is True, uses smart placement to insert new element stubs
    near their natural LTAC order position rather than appending at the end.
    """
    global _had_error
    error_before = _had_error
    try:
        with open(path, newline='') as f:
            original = f.read()
    except OSError as e:
        error(f"cannot open {path!r}: {e}")
        return None
    line_ending = detect_line_ending(original)
    # Normalise to LF for internal processing; restore on write.
    original_lf = original.replace('\r\n', '\n')
    doc_format = detect_doc_format(path)

    if add_missing:
        # Two-pass approach for smart placement:
        # Pass 1: normal re-render of existing regions (no injection)
        buf = io.StringIO()
        with io.StringIO(original_lf) as src:
            src.name = path
            process_document_stream(src, buf, registry, all_roots, config, id_info,
                                    seen_element_ids, doc_format,
                                    add_missing=False, strip=strip)
        if _had_error and not error_before:
            return None
        rendered = buf.getvalue()
        # Pass 2: smart insertion of missing elements
        new_content, _ = _insert_missing_stubs(
            rendered, all_roots, registry, id_info, config, seen_element_ids, doc_format)
    else:
        buf = io.StringIO()
        with io.StringIO(original_lf) as src:
            src.name = path
            process_document_stream(src, buf, registry, all_roots, config, id_info,
                                    seen_element_ids, doc_format,
                                    add_missing=False, strip=strip)
        if _had_error and not error_before:
            return None
        new_content = buf.getvalue()

    if new_content == original_lf:
        return None  # No change needed.
    tmp = _make_temp(path, new_content, line_ending)
    if tmp is None:
        return None
    return (tmp, path)


def run_selftests() -> None:
    """Run all doctests embedded in this module and exit.

    Exits with code 0 if every test passes, 1 if any fail.
    Failed tests are shown with ndiff output so differences are easy to spot.
    """
    import doctest
    failures, _ = doctest.testmod(optionflags=doctest.REPORT_NDIFF)
    sys.exit(0 if failures == 0 else 1)


def main() -> None:
    """Entry point: parse arguments, load configuration and LTAC data, then dispatch."""
    global _strict

    args = parse_args()

    if args.selftest:
        run_selftests()
        return  # run_selftests() calls sys.exit(); this is a safety net

    # --start must fire before find_ltac_file() because it creates case.ltac.
    # After writing the stubs, execution falls through to the normal LTAC
    # loading below, which will find the newly created case.ltac.
    if args.start:
        _check_no_existing_case_files()
        _write_start_stubs()

    if args.error:
        _strict = True

    # Auto-discover config file if --config not given.
    config_path = args.config
    if config_path is None:
        if os.path.exists('case.config'):
            config_path = 'case.config'
        elif os.path.exists('docs/case.config'):
            config_path = 'docs/case.config'
    config = load_config(config_path)
    config_invariant_checker(config)

    all_roots: List[Node] = []
    registry: Dict[str, Node] = {}
    id_info: Dict[str, dict] = {}

    ltac_path = find_ltac_file(args.ltac, config)
    load_ltac_file(ltac_path, all_roots, registry, id_info, config=config)
    try:
        with open(ltac_path, newline='') as _f:
            ltac_line_ending = detect_line_ending(_f.read())
    except OSError:
        ltac_line_ending = '\n'

    # LTAC parse complete. Perform validations needing all LTAC data
    check_id_info(id_info)
    check_circularities(registry, all_roots)
    check_reachability(all_roots, registry)

    # Detect analysis options early, before any file-modifying operations,
    # so we can reject illegal combinations before any writes happen.
    _analysis_flags = ('missing', 'empty', 'orphans', 'misplaced', 'leaves', 'packages')
    _has_analysis = any(getattr(args, f, False) for f in _analysis_flags)
    if _has_analysis:
        _file_modifying_modes = ('fixmissing', 'fixmisplaced', 'start')
        if any(getattr(args, f, False) for f in _file_modifying_modes):
            panic("analysis options (--missing, --empty, --orphans, --misplaced, --leaves, --packages) "
                  "cannot be combined with file-modifying modes (--fixmissing, --fixmisplaced, --start)")
        if args.update:
            panic("analysis options cannot be combined with --update (which modifies the LTAC file)")
        if getattr(args, 'mutations', []):
            panic("analysis options cannot be combined with --rename/--restate/--detach/--move "
                  "(which modify the LTAC file)")

    if args.update:
        changed = apply_ltac_update(all_roots, registry)
        if changed:
            tmp = _make_temp(ltac_path, write_ltac(all_roots), ltac_line_ending)
            if tmp is None:
                panic("cannot write updated LTAC file")
            commit_updates([(tmp, ltac_path)], ltac_path, config, config_path)

    # Apply ordered mutations (--rename / --restate).
    ltac_pair: Optional[Tuple[str, str]] = None
    if args.mutations:
        for op, a, b in args.mutations:
            if op == 'rename':
                apply_rename(all_roots, registry, id_info, a, b)
            elif op == 'restate':
                apply_restate(all_roots, registry, id_info, a, b)
            elif op == 'detach':
                apply_detach(all_roots, registry, id_info, a)
            elif op == 'move':
                apply_move(all_roots, registry, id_info, a, b)
        check_id_info(id_info)

        check_circularities(registry, all_roots)
        check_reachability(all_roots, registry)
        if _had_error:
            panic("LTAC validation failed after mutations; no files updated")
        tmp = _make_temp(ltac_path, write_ltac(all_roots))
        if tmp is None:
            panic("cannot write updated LTAC file")
        ltac_pair = (tmp, ltac_path)

    # Resolve document files: CLI args > config > auto-discover (fallback to [] for now).
    document_files = list(args.files)
    if not document_files:
        document_files = list(config.get('document_files', []))
    if not document_files:
        for candidate in ('case.md', 'case.markdown', 'case.html',
                          'docs/case.md', 'docs/case.markdown', 'docs/case.html'):
            if os.path.exists(candidate):
                document_files = [candidate]
                break

    _NO_FILES_MSG = (
        "no document files found; specify files on the command line, set document_files "
        "in config, or create one of: case.md, case.markdown, case.html, "
        "docs/case.md, docs/case.markdown, docs/case.html"
    )

    if _has_analysis:
        # Analysis-only mode: no document processing, no file modification
        reports = []
        if document_files:
            analysis_doc_files = document_files
        else:
            analysis_doc_files = []

        first = True
        if args.missing:
            if not first:
                print()
            _analysis_missing(all_roots, registry, analysis_doc_files)
            first = False
        if args.empty:
            if not first:
                print()
            _analysis_empty(analysis_doc_files, registry)
            first = False
        if args.orphans:
            if not first:
                print()
            _analysis_orphans(analysis_doc_files, registry)
            first = False
        if args.misplaced:
            if not first:
                print()
            _analysis_misplaced(analysis_doc_files, all_roots, registry)
            first = False
        if args.leaves:
            if not first:
                print()
            _analysis_leaves(all_roots)
            first = False
        if args.packages:
            if not first:
                print()
            _analysis_packages(all_roots)
            first = False

        if _had_error:
            sys.exit(1)
        return

    if args.info:
        result = render_selector(f'info {args.info}', registry, all_roots, config, id_info,
                                 doc_format='markdown')
        if result:
            print(result)
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.descendants:
        result = render_selector(f'ltac/txt {args.descendants}', registry, all_roots, config, id_info,
                                 doc_format='markdown')
        if result:
            print(result)
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.select:
        result = render_selector(args.select, registry, all_roots, config, id_info,
                                 doc_format='markdown')
        if result:
            print(result)
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.validate:
        if document_files:
            seen_element_ids: set = set()
            _process_files(document_files, io.StringIO(), registry, all_roots, config, id_info, seen_element_ids, strip=args.strip)
            # This validation requires that we read all document files
            _check_element_coverage(registry, seen_element_ids)
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.stdout:
        if not document_files:
            panic(_NO_FILES_MSG)
        seen_element_ids: set = set()
        _process_files(document_files, sys.stdout, registry, all_roots, config, id_info, seen_element_ids, strip=args.strip)
        _check_element_coverage(registry, seen_element_ids)
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.fixmissing or args.start:
        if not document_files:
            panic(_NO_FILES_MSG)
        seen_element_ids: set = set()
        # Re-render all files; inject missing element regions (smart placement) into the last file.
        pairs = []
        for i, path in enumerate(document_files):
            is_last = (i == len(document_files) - 1)
            pair = _inline_rewrite_file(path, registry, all_roots, config, id_info,
                                        seen_element_ids, add_missing=is_last)
            if pair:
                pairs.append(pair)
        # Mark needsSupport on all leaf elements that lack an assertion status.
        all_ids_ordered = [node.identifier for node in _all_nodes(all_roots)
                           if not node.is_cited and node.identifier]
        changed = _mark_needs_support(all_ids_ordered, registry)
        if changed:
            tmp = _make_temp(ltac_path, write_ltac(all_roots), ltac_line_ending)
            if tmp is not None:
                pairs.append((tmp, ltac_path))
        if ltac_pair:
            pairs.append(ltac_pair)
        if pairs:
            commit_updates(pairs, ltac_path, config, config_path)
    elif args.fixmisplaced:
        if not document_files:
            panic(_NO_FILES_MSG)
        seen_element_ids: set = set()
        # First pass: re-render existing regions to get current state
        pairs = []
        for path in document_files:
            pair = _inline_rewrite_file(path, registry, all_roots, config, id_info,
                                        seen_element_ids, add_missing=False)
            if pair:
                pairs.append(pair)
        # Second pass: fix misplaced regions
        # Need to work on the current file content (updated or original)
        for path in document_files:
            pair = _fixmisplaced_document(path, all_roots, registry, id_info, config,
                                          seen_element_ids, detect_doc_format(path))
            if pair:
                pairs.append(pair)
        if ltac_pair:
            pairs.append(ltac_pair)
        if pairs:
            commit_updates(pairs, ltac_path, config, config_path)
    else:
        # Default mode: rewrite document files in place.
        if not document_files and not ltac_pair:
            panic(_NO_FILES_MSG)
        seen_element_ids: set = set()
        pairs = ([ltac_pair] if ltac_pair else [])
        for path in document_files:
            pair = _inline_rewrite_file(path, registry, all_roots, config, id_info, seen_element_ids, strip=args.strip)
            if pair is not None:
                pairs.append(pair)
        if pairs:
            commit_updates(pairs, ltac_path, config, config_path)
        if document_files:
            _check_element_coverage(registry, seen_element_ids)

    if args.stats:
        ltac_stats = _compute_ltac_stats(all_roots, registry, id_info)
        if document_files:
            doc_totals: dict = {'pkg_regions': 0, 'elem_regions': 0,
                                'config_stmts': 0, 'empty_elem_regions': 0}
            for path in document_files:
                ds = _scan_doc_stats(path)
                for k in doc_totals:
                    doc_totals[k] += ds.get(k, 0)
            _print_stats(ltac_stats, doc_totals)
        else:
            _print_stats(ltac_stats, None)

    if _had_error:
        sys.exit(1)


if __name__ == '__main__':
    main()
