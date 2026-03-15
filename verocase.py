#!/usr/bin/env python3
"""verocase - process assurance case LTAC file and update Markdown/HTML

(C) Copyright David A. Wheeler and verocase contributors

SPDX-License-Identifier: MIT
"""

import argparse
import copy
import datetime
import io
import os
import re
import shutil
import statistics
import sys
import tempfile
import types
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TextIO, Tuple

# TOML support: tomllib is in the standard library since Python 3.11.
# On older Python versions, the third-party 'tomli' package is a drop-in
# replacement.  If neither is available, config files cannot be loaded, but
# the module still works fine when no config file is present.
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

__version__ = '0.1.0'

__all__ = [
    # Exceptions
    'VerocaseError',
    # Data types
    'Node',
    'Case',
    'DEFAULT_CONFIG',
    # Standalone analysis helpers
    'print_stats',
]

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

# Module-level error/reporting

class VerocaseError(Exception):
    """Raised by panic() for fatal errors; catch in main() to exit, or handle in library code."""


def panic(msg: str) -> None:
    """Print a fatal error to stderr and raise VerocaseError."""
    print(f"verocase: fatal: {msg}", file=sys.stderr)
    raise VerocaseError(msg)


def notify(msg: str) -> None:
    """Print an informational notification to stderr."""
    print(f"verocase: {msg}", file=sys.stderr)


_DEFAULT_ELEMENT_SELECTIONS = 'referenced_by,supported_by,supports,ext_ref'
_DEFAULT_PACKAGE_SELECTIONS = 'representation,pkg_defines,pkg_citing,pkg_cited'

# Default configuration values.  Case().load_config() merges a TOML file over these.
# Pass to functions that accept a config dict when no config file is needed.
DEFAULT_CONFIG = types.MappingProxyType({
    'base_url': '',
    'bottom_padding': True,
    'default_renderer': 'mermaid',
    'max_mermaid_children': 8,
    'narrowed_mermaid_children': 6,
    'default_representation': 'sacm',
    'document_files': [],
    'element_level': 3,
    'element_selections': _DEFAULT_ELEMENT_SELECTIONS,
    'ltac_file': '',
    'markdown_base_url': '',
    'mermaid_js_url': 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs',
    'package_level': 3,
    'package_selections': _DEFAULT_PACKAGE_SELECTIONS,
    'pkg_header_prefix': '### ',
    'pkg_header_suffix': '\n',
    'pkg_label': 'Package ',
    'max_backups': 20,
    'stats': False,
    'warn_dubious_reference': True,
})



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
_EMPTY: dict = {}           # shared empty dict for .get(key, _EMPTY).get(...)


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
    Raises VerocaseError for unrecognised extensions.

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
    """A single node in the parsed LTAC tree.

    Nodes form a doubly-linked tree via `children` and `parent`.  Every node
    in a loaded forest is reachable by walking `all_roots` recursively, or by
    iterating with `case.all_nodes()` or `case.all_nodes_fast()`.

    Fields
    ------
    node_type : str
        Element kind: one of Claim, Strategy, Justification, Evidence,
        Context, Assumption, Link, Relation, Connector.
    identifier : str
        Declared identifier (e.g. ``'C1'``); empty string when absent.
        When ``id_inferred`` is True this was derived from ``text``, not
        written explicitly in the LTAC file.
    text : str
        Descriptive statement or title text; empty string when absent.
    ext_ref : str
        Text from a trailing ``(...)`` reference clause; empty when absent.
    options : List[str]
        Zero or more option keywords in lower-case, e.g. ``['needssupport']``,
        ``['axiomatic']``, ``['defeated']``.
    children : List[Node]
        Direct child nodes in LTAC written order.
    is_citation : bool
        True when the node was introduced with a ``^`` prefix, meaning it
        is a cross-package citation rather than a declaration.
    is_definition : bool (property)
        True when the node is neither a citation nor a Link; i.e. it is a
        substantive declared element.  Equivalent to
        ``not is_citation and node_type != 'Link'``.
    depth : int
        Zero-based indentation level; 0 for package roots.
    parent : Optional[Node]
        Parent node, or None for package roots (depth 0).
    link_target : Optional[Node]
        For Link nodes: the node this link points to.  None for all other
        node types.
    diagram_id : str
        A stable identifier suitable for use in Mermaid diagram node IDs.
    id_inferred : bool
        True when ``identifier`` was auto-generated from ``text`` rather than
        declared explicitly.  Defaults to False.
    pkg_root : Node (property)
        The package root (depth 0) ancestor of this node, found by walking
        parent links.  For package root nodes, ``pkg_root is self``.
    """
    node_type: str
    identifier: str
    text: str
    ext_ref: str
    options: List[str]
    children: List['Node']
    is_citation: bool
    depth: int
    parent: Optional['Node']
    link_target: Optional['Node']
    diagram_id: str
    id_inferred: bool = False

    @property
    def is_definition(self) -> bool:
        """True when this node is a substantive declared element.

        A definition is any node that is neither a citation (``^`` prefix) nor
        a Link.  It is the natural complement to ``is_citation``: every node
        in the tree is exactly one of citation, Link, or definition.
        Prefer this over spelling out ``not is_citation and node_type != 'Link'``
        at every call site.
        """
        return not self.is_citation and self.node_type != 'Link'

    @property
    def pkg_root(self) -> 'Node':
        """The package root (depth 0) of this node, found by walking parent links."""
        node = self
        while node.parent is not None:
            node = node.parent
        return node

    @property
    def subtree_count(self) -> int:
        """Total number of nodes in this node's subtree, including itself."""
        count = 0
        stack = [self]
        while stack:
            n = stack.pop()
            count += 1
            stack.extend(n.children)
        return count

    def to_ltac_line(self, depth_offset: int = 0) -> str:
        """Format this node as an LTAC source line (without trailing newline).

        The indentation is ``self.depth - depth_offset`` levels of two spaces.
        Pass ``depth_offset=self.depth`` to render at column 0 regardless of
        actual depth.  Inferred identifiers are suppressed when they match the
        auto-generated form so the output round-trips cleanly.
        """
        indent = '  ' * (self.depth - depth_offset)
        line = f'{indent}- {self.node_type}'
        write_id = (self.identifier or self.is_citation) and not (
            self.id_inferred and _infer_id(self.text) == self.identifier
        )
        if write_id:
            line += ' '
            if self.is_citation:
                line += '^'
            line += self.identifier
        if self.text:
            line += f': {self.text}'
        if self.options:
            line += ' {' + ', '.join(self.options) + '}'
        elif self.text and self.text.endswith('}'):
            line += ' {}'
        if self.ext_ref:
            line += f' ({self.ext_ref})'
        elif self.text and self.text.endswith(')') and not self.options:
            line += ' ()'
        return line


class Case:
    """A fully loaded LTAC assurance case: the node forest, lookup tables, and documents.

    Construct cheaply with Case(), then call load() to read files:

        case = Case().load()                        # auto-discover everything
        case = Case().load(ltac_file='my.ltac')     # explicit LTAC, auto rest
        case = Case(stderr=buf).load(validate=False) # redirect errors, skip validation

    Attributes set by __init__ (all have safe defaults; no I/O):
        roots          List[Node]       Package root nodes in file order.
        registry       Dict[str,Node]   Maps every declared identifier to its Node.
        id_info        Dict[str,dict]   Cross-reference metadata per identifier.
        document_files List[str]        Document paths associated with this case.
        config         dict             Active configuration dict.
        had_error      bool             True if any error() was called.
        strict         bool             True if warnings are escalated to errors.
        modified       bool             True if any mutation method was called.
        ltac_path      Optional[str]    Path of the loaded LTAC file.
        config_path    Optional[str]    Path of the loaded config file.
        stderr         TextIO           Stream for error/warning/notify output.
    """

    def __init__(self, stderr=None):
        self.roots:          List['Node']       = []
        self.registry:       Dict[str, 'Node']  = {}
        self.id_info:        Dict[str, dict]    = {}
        self.document_files: List[str]          = []
        self.config:         dict               = dict(DEFAULT_CONFIG)
        self.had_error:      bool               = False
        self.strict:         bool               = False
        self.modified:       bool               = False
        self.ltac_path:      Optional[str]      = None
        self.config_path:    Optional[str]      = None
        self.stderr:         'TextIO'           = stderr or sys.stderr

    # ------------------------------------------------------------------
    # Error reporting
    # ------------------------------------------------------------------

    def error(self, msg: str) -> None:
        """Print an error to stderr and set the error flag."""
        print(f"verocase: error: {msg}", file=self.stderr)
        self.had_error = True

    def warn(self, msg: str) -> None:
        """Print a warning; if strict mode is on, escalate to error()."""
        if self.strict:
            self.error(msg)
        else:
            print(f"verocase: warning: {msg}", file=self.stderr)

    def panic(self, msg: str) -> None:
        """Print a fatal error to stderr and raise VerocaseError."""
        print(f"verocase: fatal: {msg}", file=self.stderr)
        raise VerocaseError(msg)

    def notify(self, msg: str) -> None:
        """Print an informational notification to stderr."""
        print(f"verocase: {msg}", file=self.stderr)

    # ------------------------------------------------------------------
    # Construction: load from files
    # ------------------------------------------------------------------

    def load_config(self, filename: Optional[str] = None) -> 'Case':
        """Load configuration from filename, or auto-discover verocase.toml.

        If filename is given, load it (panic if not found). If None, search for
        verocase.toml / docs/verocase.toml; keep defaults if not found.
        Sets self.config and self.config_path. Returns self for chaining.
        """
        self.config_path = self._find_config(filename)
        self.config = self._load_config(self.config_path)
        return self

    def load_ltac_string(self, text: str) -> 'Case':
        """Parse LTAC from a string, using self.config.

        Does not read any files. Parses text, setting self.roots, self.registry,
        and self.id_info. Sets self.ltac_path = None (no backing file). Does not
        run validation; call validate_ltac() separately if needed.
        Returns self for chaining.

        Call load_config() first if you need non-default configuration::

            case = Case().load_config('myconfig.toml').load_ltac_string(ltac_text)
        """
        self.ltac_path = None
        _LTACParser(self).parse(text.splitlines(keepends=True), config=self.config)
        return self

    def load(self, ltac_file: Optional[str] = None,
             config_file: Optional[str] = None,
             document_files: Optional[List[str]] = None,
             strict: bool = False,
             validate: bool = True) -> 'Case':
        """Discover and load config, LTAC, and document files; return self.

        All parameters are optional; with no arguments, auto-discovers
        verocase.toml, case.ltac, and case.md from well-known paths,
        mirroring the CLI with no arguments.

        Parameters
        ----------
        ltac_file : str, optional
            Path to the LTAC file; auto-discovered if omitted.
        config_file : str, optional
            Path to the TOML config file; auto-discovered if omitted.
        document_files : list of str, optional
            Document paths; auto-discovered if omitted.
        strict : bool, default False
            When True, warnings are treated as errors.
        validate : bool, default True
            When True, run structural validation after loading.

        Returns
        -------
        Case
            self, allowing fluent use: ``case = Case().load(...)``.
        """
        self.strict = strict
        self.load_config(config_file)
        ltac_path = self._find_ltac_file(ltac_file)
        self.ltac_path = ltac_path
        self._parse_ltac_file(ltac_path)
        self.document_files = (
            document_files if document_files is not None
            else self._find_document_files(ltac_path)
        )
        if validate:
            self.validate_ltac()
        return self

    def _find_config(self, path: Optional[str] = None) -> Optional[str]:
        """Return the config file path to use, or None if not found.

        Search order: explicit path → verocase.toml → docs/verocase.toml → None.
        Panics if an explicit path is given but the file does not exist.
        """
        if path is not None:
            if os.path.exists(path):
                return path
            self.panic(f"config file not found: {path!r}")
        if os.path.exists('verocase.toml'):
            return 'verocase.toml'
        if os.path.exists('docs/verocase.toml'):
            return 'docs/verocase.toml'
        return None

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load and validate a TOML config file; return a config dict.

        Returns DEFAULT_CONFIG copy if config_path is None.
        """
        if config_path is None:
            return dict(DEFAULT_CONFIG)
        if tomllib is None:
            self.error(
                f"cannot load config file {config_path!r}: "
                "TOML support requires Python 3.11+ (tomllib) or "
                "'pip install tomli' for older Python versions"
            )
            return dict(DEFAULT_CONFIG)
        try:
            with open(config_path, 'rb') as f:
                parsed = tomllib.load(f)
        except FileNotFoundError:
            self.panic(f"config file not found: {config_path!r}")
        except PermissionError:
            self.panic(f"config file not readable: {config_path!r}")
        except Exception as e:
            self.panic(f"invalid TOML in config file {config_path!r}: {e}")
        if not isinstance(parsed, dict):
            self.panic(f"config file must contain a TOML table, not {type(parsed).__name__}")
        for key in parsed:
            if key not in DEFAULT_CONFIG:
                self.warn(f"unknown config key: {key!r}")
        cfg = dict(DEFAULT_CONFIG)
        cfg.update({k: v for k, v in parsed.items() if k in DEFAULT_CONFIG})
        mb = cfg.get('max_backups')
        if not isinstance(mb, int) or mb < 0:
            self.warn(f"invalid value for max_backups: {mb!r}; using default {DEFAULT_CONFIG['max_backups']}")
            cfg['max_backups'] = DEFAULT_CONFIG['max_backups']
        return cfg

    def _find_ltac_file(self, ltac_arg: Optional[str]) -> str:
        """Return the LTAC file path to load; panics if not found.

        Search order: ltac_arg → config['ltac_file'] → case.ltac → docs/case.ltac.
        """
        if ltac_arg:
            return ltac_arg
        ltac_from_config = self.config.get('ltac_file', '')
        if ltac_from_config:
            return ltac_from_config
        if os.path.exists('case.ltac'):
            return 'case.ltac'
        if os.path.exists('docs/case.ltac'):
            return 'docs/case.ltac'
        self.panic("no LTAC file found; use --ltac, set ltac_file in config, or create case.ltac. See --help")

    def _find_document_files(self, ltac_path: Optional[str] = None) -> List[str]:
        """Find document files associated with this case; return a list.

        Search order: config['document_files'] → adjacent to ltac_path → cwd → docs/.
        Returns [] if none found.
        """
        from_config = list(self.config.get('document_files', []))
        if from_config:
            return from_config
        candidates: List[str] = []
        if ltac_path:
            ltac_dir = os.path.dirname(os.path.abspath(ltac_path))
            cwd = os.path.abspath('.')
            if ltac_dir != cwd:
                for ext in ('md', 'markdown', 'html'):
                    candidates.append(os.path.join(ltac_dir, f'case.{ext}'))
        for name in ('case.md', 'case.markdown', 'case.html',
                     'docs/case.md', 'docs/case.markdown', 'docs/case.html'):
            candidates.append(name)
        for candidate in candidates:
            if os.path.exists(candidate):
                return [candidate]
        return []

    def _detect_doc_format(self, path: str) -> str:
        """Return 'markdown' or 'html' based on the file extension; panics on unknown."""
        low = path.lower()
        if low == '-' or low.endswith('.md') or low.endswith('.markdown'):
            return 'markdown'
        if low.endswith('.html') or low.endswith('.htm'):
            return 'html'
        self.panic(f"cannot determine document format from filename {path!r}; "
                   f"expected .md, .markdown, .html, or .htm")

    def _parse_ltac_file(self, path: str) -> None:
        """Open path and parse its LTAC content into this Case."""
        try:
            with open(path) as f:
                lines = f.readlines()
        except OSError as e:
            self.panic(f"cannot open {path!r}: {e}")
        _LTACParser(self).parse(lines, config=self.config)

    def validate_ltac(self) -> bool:
        """Run all LTAC structural validation checks; return True if no errors.

        Covers: identifier usage (check_id_info), circular dependencies
        (check_circularities), and package reachability (check_reachability).
        Document-level checks (missing(), orphans(), etc.) are separate and
        require document_files to be set.
        """
        self.check_id_info()
        self.check_circularities()
        self.check_reachability()
        return not self.had_error

    # ------------------------------------------------------------------
    # Identifier lookups
    # ------------------------------------------------------------------

    def definition_for(self, ident: str) -> Optional['Node']:
        """Return the definition Node for ident, or None if absent or duplicated.

        Returns None when there are zero declarations (ident unknown) or more
        than one declaration (broken LTAC).  Callers that need to handle
        duplicate declarations explicitly should use definitions_for() instead.
        """
        if self.id_info.get(ident, _EMPTY).get('declarations', 0) != 1:
            return None
        return self.registry.get(ident)

    def definitions_for(self, ident: str) -> List['Node']:
        """Return all definition Nodes for ident, including duplicates.

        A well-formed LTAC has exactly one definition per identifier; load
        warnings flag extras.  This method walks the full forest so it can
        return every declaration node even when the registry only holds the
        first one.  Returns [] when ident is unknown.
        """
        return [n for n in _all_nodes_fast(self.roots)
                if n.identifier == ident and n.is_definition]

    def declaring_package_for(self, ident: str) -> Optional['Node']:
        """Return the package root Node that declares ident, or None.

        Returns None when ident is unknown or has duplicate declarations
        (definition_for returns None in both cases).  If you have a Node
        that's the definition already, use node.pkg_root directly instead.
        """
        node = self.definition_for(ident)
        return node.pkg_root if node is not None else None

    def statement_for(self, ident: str) -> Optional[str]:
        """Return the canonical statement text for ident, or None."""
        return self.id_info.get(ident, _EMPTY).get('statement')

    def find_citation_parents(self, ident: str) -> List['Node']:
        """Return all nodes that have a cited child (^ident) anywhere in the forest."""
        parents = []
        for node in _all_nodes_fast(self.roots):
            if node.identifier == ident and node.is_citation and node.parent is not None:
                if node.parent not in parents:
                    parents.append(node.parent)
        return parents

    def nodes_for(self, element_id: Optional[str],
                  current: Optional['Node'] = None) -> List['Node']:
        """Return the node(s) for element_id, with fallback to current or all roots.

        If element_id is given, look it up in the registry (error and return []
        if not found).  If element_id is None, return [current] when current is
        set, else return all roots.  ('*' is handled at dispatch time before
        calling here.)
        """
        return _resolve_element(element_id, self, current)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def check_id_info(self) -> None:
        """Validate identifier usage; warn about IDs cited but never declared."""
        for ident, info in self.id_info.items():
            if info['citations'] > 0 and info['declarations'] == 0:
                self.warn(f"{ident}: cited but never declared")

    def check_circularities(self) -> None:
        """Panic if any circular dependency exists in the LTAC model.

        Performs an iterative DFS over the logical dependency graph.  For each
        node, its logical successors are its structural children (non-citation,
        non-Link), any cited child's declared node (^ID → registry[ID]), and
        any Link child's link_target.  A node encountered while already on the
        current DFS path (a back-edge) means circular reasoning is possible.
        """
        visiting: Set[int] = set()  # id(node) of nodes on the current DFS path
        done: Set[int] = set()      # id(node) of fully-explored nodes

        def successors(node: Node):
            for child in node.children:
                if child.is_citation:
                    target = self.definition_for(child.identifier)
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
                        self.panic(f"circularity detected: {trail}")
                    visiting.add(key)
                    path.append(succ)
                    stack.append((succ, successors(succ)))
                except StopIteration:
                    stack.pop()
                    path.pop()
                    visiting.discard(id(node))
                    done.add(id(node))

        for root in self.roots:
            if id(root) not in done:
                dfs(root)
        for node in self.registry.values():
            if id(node) not in done:
                dfs(node)

    def check_reachability(self) -> None:
        """Error for any package whose root is unreachable from the first element.

        Skipped when there is only one package (everything is trivially reachable).
        Uses iterative DFS following structural children, citation declarations, and
        Link targets.  Because all structural children of a reachable node are also
        reachable, an unreachable package root implies the whole package is
        unreachable; reporting just the root is sufficient.
        """
        if len(self.roots) < 2:
            return

        reachable: Set[int] = set()
        stack = [self.roots[0]]
        while stack:
            node = stack.pop()
            if id(node) in reachable:
                continue
            reachable.add(id(node))
            for child in node.children:
                if child.is_citation:
                    target = self.definition_for(child.identifier)
                    if target is not None:
                        stack.append(target)
                elif child.node_type == 'Link':
                    if child.link_target is not None:
                        stack.append(child.link_target)
                else:
                    stack.append(child)

        for root in self.roots[1:]:
            if id(root) not in reachable:
                label = f"{root.node_type} {root.identifier}" if root.identifier else root.node_type
                self.error(f"{label}: package root is unreachable from {self.roots[0].node_type}"
                           f" {self.roots[0].identifier}")

    # ------------------------------------------------------------------
    # Forest traversal
    # ------------------------------------------------------------------

    def all_nodes(self):
        """Yield every node in the forest in LTAC written order (DFS, first child first)."""
        return _all_nodes(self.roots)

    def all_nodes_fast(self):
        """Yield every node in the forest faster than all_nodes(), in arbitrary DFS order.

        Children are pushed in forward order onto a list-stack and popped in
        reverse, so the traversal order differs from LTAC written order but
        is fully deterministic.  Prefer all_nodes() when order matters;
        use this when building lookup sets or computing aggregates.
        See the _all_nodes_fast() implementation for the full performance
        rationale (reversed() vs C-level extend).
        """
        return _all_nodes_fast(self.roots)

    def collect_bfs(self) -> List['Node']:
        """Return all nodes in the forest in BFS order."""
        return _collect_bfs(self.roots)

    def copy_forest(self) -> List['Node']:
        """Return a deep copy of the forest; originals are untouched."""
        return _copy_forest(self.roots)

    def write_ltac(self, out: 'TextIO') -> None:
        """Serialize the full forest to LTAC text, writing to out."""
        _write_ltac(self.roots, out)

    def needs_support(self) -> List['Node']:
        """Return all nodes in the forest that carry the {needssupport} option."""
        return [n for n in _all_nodes_fast(self.roots) if 'needssupport' in n.options]

    def save_ltac(self, path: Optional[str] = None) -> None:
        """Write the LTAC forest to disk using the safe backup+atomic-replace mechanism.

        If path is given, writes to that path; otherwise writes to self.ltac_path.
        Panics if no path is available.  On success, clears self.modified.
        """
        target = path or self.ltac_path
        if target is None:
            self.panic("save_ltac: no path given and case.ltac_path is not set")
        buf = io.StringIO()
        self.write_ltac(buf)
        tmp = _make_temp(target, buf.getvalue())
        if tmp is None:
            return  # error already reported
        commit_updates([(tmp, target)], target, self.config, self.config_path)
        self.modified = False

    # ------------------------------------------------------------------
    # Analysis — data-returning
    # ------------------------------------------------------------------

    def leaves(self) -> List['Node']:
        """Return all definition nodes with no children, in LTAC order."""
        return [node for node in _all_nodes(self.roots)
                if node.is_definition and not node.children]

    def stats(self) -> dict:
        """Compute and return a statistics dict for the loaded LTAC forest."""
        from collections import Counter
        def_type_counts: Counter = Counter()
        option_counts: Counter = Counter()
        total_citations = 0
        total_links = 0
        leaf_definitions = 0
        leaf_claims = 0
        bottommost_claims = 0
        pkg_sizes_full = []

        for root in self.roots:
            size_full = 0
            for node in _all_nodes_fast([root]):
                size_full += 1
                if node.is_citation:
                    total_citations += 1
                elif node.node_type == 'Link':
                    total_links += 1
                else:
                    def_type_counts[node.node_type] += 1
                    for opt in node.options:
                        option_counts[opt] += 1
                    if not node.children:
                        leaf_definitions += 1
                        if node.node_type == 'Claim':
                            leaf_claims += 1
                    if node.node_type == 'Claim':
                        seen = {node.identifier} if node.identifier else set()
                        if not _has_claim_descendant(node, self.registry, seen):
                            bottommost_claims += 1
            pkg_sizes_full.append((size_full, root.identifier or '(unnamed)'))

        pkg_sizes_sorted = sorted(pkg_sizes_full, key=lambda x: x[0], reverse=True)
        num_packages = len(pkg_sizes_full)
        total_full = sum(s for s, _ in pkg_sizes_full)
        median_per_pkg = statistics.median(s for s, _ in pkg_sizes_full) if pkg_sizes_full else 0
        avg_per_pkg = total_full / num_packages if num_packages else 0.0
        total_definitions = sum(def_type_counts.values())
        return {
            'num_packages':      num_packages,
            'pkg_sizes_sorted':  pkg_sizes_sorted,
            'avg_per_pkg':       avg_per_pkg,
            'median_per_pkg':    median_per_pkg,
            'total_full':        total_full,
            'total_citations':   total_citations,
            'total_links':       total_links,
            'total_definitions': total_definitions,
            'def_type_counts':   def_type_counts,
            'leaf_definitions':  leaf_definitions,
            'leaf_claims':       leaf_claims,
            'bottommost_claims': bottommost_claims,
            'option_counts':     option_counts,
        }

    def missing(self) -> List['Node']:
        """Return LTAC elements that have no selector region in the document(s)."""
        ordered_ids, _ = _scan_document_elements(self.document_files)
        seen = {ident for ident, _, _ in ordered_ids}
        all_ids_ordered = [node for node in _all_nodes(self.roots)
                           if node.is_definition and node.identifier]
        return [node for node in all_ids_ordered if node.identifier not in seen]

    def empty(self) -> List[str]:
        """Return identifiers of elements whose selector region contains no prose."""
        _, elem_info = _scan_document_elements(self.document_files)
        return [
            ident for ident, info in elem_info.items()
            if not info['has_prose']
            and not ((node := self.definition_for(ident)) and node.ext_ref)
        ]

    def orphans(self) -> List[str]:
        """Return identifiers of document selector regions not present in the LTAC."""
        _, elem_info = _scan_document_elements(self.document_files)
        return [ident for ident in elem_info if ident not in self.registry]

    def misplaced(self) -> list:
        """Return elements whose document order differs from LTAC order."""
        ltac_order = [node.identifier for node in _all_nodes(self.roots)
                      if node.is_definition and node.identifier]
        ltac_pos = {ident: i for i, ident in enumerate(ltac_order)}

        ordered_ids, elem_info = _scan_document_elements(self.document_files)
        doc_entries = [(ident, filepath, lineno) for ident, filepath, lineno in ordered_ids
                       if ident in self.registry]

        if not doc_entries:
            return []

        doc_ids = [ident for ident, _, _ in doc_entries]
        ranks = [ltac_pos.get(ident, -1) for ident in doc_ids]
        from bisect import bisect_left
        tails = []
        tail_idx = []
        predecessor = [-1] * len(doc_ids)

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

        misplaced_entries = []
        for i, (ident, filepath, lineno) in enumerate(doc_entries):
            if i not in lis_indices:
                misplaced_entries.append((ident, lineno, filepath))

        if not misplaced_entries:
            return []

        doc_id_to_entry = {ident: (lineno, filepath) for ident, filepath, lineno in doc_entries}
        result = []
        for ident, lineno, filepath in misplaced_entries:
            ltac_idx = ltac_pos.get(ident, -1)
            pred_ident = None
            pred_lineno = None
            for j in range(ltac_idx - 1, -1, -1):
                candidate = ltac_order[j]
                if candidate in doc_id_to_entry:
                    pred_ident = candidate
                    pred_lineno = doc_id_to_entry[candidate][0]
                    break
            result.append((ident, lineno, filepath, pred_ident, pred_lineno))
        return result

    # ------------------------------------------------------------------
    # Analysis — output-printing
    # ------------------------------------------------------------------

    def packages(self) -> List[dict]:
        """Return a list of dicts, one per package root.

        Each dict has keys: 'root' (the Node), 'total' (root.subtree_count),
        'children' (list of root.children).
        """
        return [
            {'root': root, 'total': root.subtree_count, 'children': list(root.children)}
            for root in self.roots
        ]

    def render_packages(self, out: 'TextIO' = sys.stdout) -> None:
        """Print package structure with element counts to out."""
        print("Packages:", file=out)
        for pkg in self.packages():
            root = pkg['root']
            pkg_count = pkg['total']
            root_line = root.to_ltac_line(depth_offset=0)
            print(f"Package {root.identifier} ({pkg_count} elements)", file=out)
            print(root_line, file=out)
            for child in pkg['children']:
                child_count = child.subtree_count
                child_line = child.to_ltac_line(depth_offset=0)
                print(f"{child_line} ({child_count} elements)", file=out)
            print(file=out)

    # ------------------------------------------------------------------
    # Info rendering
    # ------------------------------------------------------------------

    def render_info(self, element_id: str, out: 'TextIO', sep: str = '') -> bool:
        """Write a human-readable context report for element_id to out.

        Returns False and calls error() if element_id is not in registry.
        sep is written before the report when non-empty.
        """
        node = self.definition_for(element_id)
        if node is None:
            self.error(f"info: element {element_id!r} not found")
            return False

        out.write(sep)

        header = f"{node.node_type} {node.identifier}"
        if node.text:
            header += f": {node.text}"
        out.write(f"Element: {header}")

        out.write(f"\nPackage: {node.pkg_root.identifier or '(unnamed)'}")

        ancestors = []
        anc = node.parent
        while anc is not None:
            ancestors.append(anc)
            anc = anc.parent
        ancestors.reverse()

        if not ancestors:
            out.write("\nAncestors: (package root)")
        else:
            out.write("\nAncestors (root first):")
            for anc in ancestors:
                out.write("\n  " + anc.to_ltac_line(depth_offset=anc.depth))

        if not node.children:
            out.write("\nChildren: (none)")
        else:
            out.write("\nChildren:")
            for child in node.children:
                out.write("\n  " + child.to_ltac_line(depth_offset=child.depth))

        desc_count = node.subtree_count
        out.write(f"\nDescendants: {desc_count} (including self, all descendants, citations, and links in subtree)")

        info = self.id_info.get(element_id, {})
        citation_count = info.get('citations', 0)
        citing_pkg_ids = info.get('citing_pkg_ids', [])
        out.write(f"\nCitations: {citation_count}")
        if citation_count > 0:
            for citing_pkg_id in citing_pkg_ids:
                citing_root = self.definition_for(citing_pkg_id)
                if citing_root is None:
                    continue
                for n in _all_nodes_fast([citing_root]):
                    if n.is_citation and n.identifier == element_id:
                        parent_node = n.parent
                        if parent_node:
                            parent_desc = f"{parent_node.node_type} {parent_node.identifier}"
                            cp_name = parent_node.pkg_root.identifier or '(unnamed)'
                            out.write(f"\n  Cited as ^{element_id} by: {parent_desc} (Package {cp_name})")
                        else:
                            out.write(f"\n  Cited as ^{element_id} (package root)")
        return True

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def rename_id(self, old: str, new: str) -> None:
        """Rename identifier old to new throughout the LTAC forest.

        Panics if old is not declared or new is already declared.
        Updates all node identifiers, the registry, id_info, and cross-references.
        """
        if old not in self.registry:
            self.panic(f"--rename: {old!r} is not a declared identifier")
        if new in self.registry:
            self.panic(f"--rename: {new!r} is already declared")
        for node in _all_nodes_fast(self.roots):
            if node.identifier == old:
                node.identifier = new
        self.registry[new] = self.registry.pop(old)
        self.id_info[new] = self.id_info.pop(old)
        for entry in self.id_info.values():
            if entry.get('decl_pkg_id') == old:
                entry['decl_pkg_id'] = new
            entry['citing_pkg_ids'] = [new if x == old else x
                                       for x in entry.get('citing_pkg_ids', [])]
        self.modified = True

    def restate_id(self, label: str, stmt: str) -> None:
        """Update the statement text for label on all nodes and in id_info.

        Panics if label is not declared.
        """
        if label not in self.registry:
            self.panic(f"--restate: {label!r} is not a declared identifier")
        for node in _all_nodes_fast(self.roots):
            if node.identifier == label:
                node.text = stmt
        self.id_info[label]['statement'] = stmt
        self.modified = True

    def detach_id(self, target_id: str) -> None:
        """Replace target_id's definition with a citation; promote subtree to new package.

        Panics if target_id is not defined, or if its definition is already a
        top-level package root (has no parent).
        """
        node = self.definition_for(target_id)
        if node is None:
            self.panic(f"--detach: {target_id!r} is not defined")
        if node.parent is None:
            self.panic(f"--detach: {target_id!r} is a top-level package root; cannot detach")

        parent = node.parent
        idx = parent.children.index(node)

        cited = Node(
            node_type=node.node_type,
            identifier=node.identifier,
            text=node.text,
            ext_ref='',
            options=[],
            children=[],
            is_citation=True,
            depth=node.depth,
            parent=parent,
            link_target=None,
            diagram_id=None,
        )
        parent.children[idx] = cited

        node.parent = None
        _recalc_depths(node, 0)
        self.roots.append(node)

        new_pkg_id = node.identifier
        old_pkg_id = _decl_pkg_id_for(self.id_info, node.identifier)
        _update_pkg_id_for_subtree(node, old_pkg_id, new_pkg_id, self.id_info)

        self.id_info[target_id]['citations'] = self.id_info[target_id].get('citations', 0) + 1
        citing_pkg = cited.pkg_root.identifier
        if citing_pkg and citing_pkg not in self.id_info[target_id].get('citing_pkg_ids', []):
            self.id_info[target_id].setdefault('citing_pkg_ids', []).append(citing_pkg)
        self.modified = True

    def move_id(self, moving_id: str, dest_id: str) -> None:
        """Move moving_id's definition to be a child of dest_id.

        ID may be top-level or nested anywhere in the tree. No citation is left
        at the original location. Panics if moving_id or dest_id is not defined.
        """
        node = self.definition_for(moving_id)
        if node is None:
            self.panic(f"--move: {moving_id!r} is not defined")
        dest = self.definition_for(dest_id)
        if dest is None:
            self.panic(f"--move: {dest_id!r} is not defined")

        old_pkg_id = _decl_pkg_id_for(self.id_info, moving_id)

        if node.parent is None:
            self.roots.remove(node)
        else:
            node.parent.children.remove(node)
            node.parent = None

        cited_idx = None
        for i, child in enumerate(dest.children):
            if child.is_citation and child.identifier == moving_id:
                cited_idx = i
                break

        if cited_idx is not None:
            dest.children[cited_idx] = node
            self.id_info[moving_id]['citations'] = max(
                0, self.id_info[moving_id].get('citations', 1) - 1)
        else:
            dest.children.append(node)

        node.parent = dest
        _recalc_depths(node, dest.depth + 1)

        new_pkg_id = dest.pkg_root.identifier
        _update_pkg_id_for_subtree(node, old_pkg_id, new_pkg_id, self.id_info)
        self.modified = True

    def sync_citations(self) -> int:
        """Update cited/Link node text to match declaration text; return count changed."""
        count = 0
        for node in _all_nodes_fast(self.roots):
            if not node.identifier or node.is_definition:
                continue
            decl = self.definition_for(node.identifier)
            canonical = decl.text if decl is not None else None
            if node.text and canonical is not None and node.text != canonical:
                node.text = canonical
                count += 1
        return count

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_selector(self, selector: str, out: 'TextIO',
                        current_element: Optional['Node'] = None,
                        doc_format: str = 'markdown',
                        state: 'DocState' = None) -> bool:
        """Parse selector and write the rendered output to out; return True if anything written.

        selector is a string of the form ``"DISPLAY_TYPE [ID]"``.
        doc_format must be ``'markdown'`` or ``'html'``.
        state carries per-document rendering context.
        """
        display_type, element_id = parse_selector(selector, doc_format, self.config)

        if display_type == 'config':
            self.error("use '<!-- verocase-config KEY = VALUE -->' (not '<!-- verocase config ...-->')")
            return False
        elif display_type == 'warning':
            if element_id is not None:
                self.error("'warning' selector takes no parameters")
                return False
            out.write(_WARNING_TEXT)
            return True
        elif display_type == 'stop':
            if element_id is not None:
                self.error("'stop' selector takes no parameters")
                return False
            out.write("<!-- Content from here is not part of any element's full content "
                      "and will not be repositioned by --fixmisplaced. -->")
            return True
        elif display_type == 'epilogue':
            if element_id is not None:
                self.error("'epilogue' selector takes no parameters")
                return False
            out.write("<!-- Content from here is epilogue: not part of any element's full content, "
                      "will not be repositioned by --fixmisplaced, and new element stubs "
                      "from --fixmissing are inserted before this point. -->")
            return True
        elif display_type in ('sacm/mermaid', 'sacm/mermaid/markdown'):
            return _render_or_all(element_id, self, render_sacm, current_element, self.config, out)
        elif display_type in ('gsn/mermaid', 'gsn/mermaid/markdown'):
            return _render_or_all(element_id, self, render_gsn, current_element, self.config, out)
        elif display_type == 'sacm/mermaid/html':
            if state is not None:
                _maybe_inject_mermaid_js(self.config, state, out)
            return _render_or_all(element_id, self, render_sacm_html, current_element, self.config, out)
        elif display_type == 'gsn/mermaid/html':
            if state is not None:
                _maybe_inject_mermaid_js(self.config, state, out)
            return _render_or_all(element_id, self, render_gsn_html, current_element, self.config, out)
        elif display_type == 'ltac/markdown':
            return _render_or_all(element_id, self, render_markdown, current_element, self.config, out)
        elif display_type == 'ltac/html':
            return _render_or_all(element_id, self, render_html, current_element, self.config, out)
        elif display_type == 'ltac/txt':
            nodes = _resolve_element(element_id, self, current_element)
            if not nodes:
                return False
            return _render_ltac_txt(nodes, self.config, out)
        elif display_type == 'info':
            if element_id is None or element_id == '*':
                self.error("'info' selector requires an explicit element ID")
                return False
            return self.render_info(element_id, out)
        elif display_type == 'element':
            if element_id is None:
                self.error("'element' selector requires an explicit ID")
                return False
            _state = state or DocState(doc_format=doc_format)
            return self.render_element(element_id, out, state=_state)
        elif display_type == 'package':
            _state = state or DocState(doc_format=doc_format)
            pkg_id = element_id if element_id is not None else '*'
            return self.render_package(pkg_id, out, state=_state)
        else:
            if element_id == '*':
                self.error(f"'*' is not valid with the '{display_type}' selector")
                return False
            nodes = _resolve_element(element_id, self, current_element)
            if not nodes:
                return False
            node = nodes[0]
            if display_type == 'statement':
                out.write(render_statement(node))
                return True
            return False

    def render_element(self, node_id: str, out: 'TextIO', *,
                       state: 'DocState' = None, sep: str = '') -> bool:
        """Write a full element section (heading + configured sub-selections) to out.

        Renders the element heading and any sub-selections listed in
        config['element_selections']. Updates state.current_id and
        state.seen_element_ids as a side-effect.
        Returns False and calls error() if node_id is not in registry.
        """
        if state is None:
            state = DocState()
        node = self.definition_for(node_id)
        if node is None:
            self.error(f"element {node_id!r} not found")
            return False
        state.current_id = node_id
        state.seen_element_ids.add(node_id)

        level = self.config.get('element_level', 3)
        anchor = _component_anchor_id(node.node_type, node_id)
        stmt = self.statement_for(node_id) or node.text or ''
        heading_text = f'{node.node_type} {node_id}'
        if stmt:
            heading_text += f': {stmt}'
        fmt = state.doc_format

        out.write(sep)
        out.write(_WARNING_TEXT_SELECTOR)
        out.write('\n\n')
        out.write(_make_heading(anchor, level, heading_text, fmt))
        _apply_sel(self.config.get('element_selections', _DEFAULT_ELEMENT_SELECTIONS),
                   _ELEMENT_RENDER_MAP, node, self, self.config, fmt, out, pending_sep='\n\n')
        return True

    def render_package(self, pkg_id_or_star: str, out: 'TextIO', *,
                       state: 'DocState' = None) -> bool:
        """Write a full package section (heading + diagram + sub-selections) to out.

        pkg_id_or_star is either a package root identifier or ``'*'`` to render
        all packages in sequence. Returns True if anything was written.
        """
        if state is None:
            state = DocState()
        if pkg_id_or_star == '*':
            out.write(_WARNING_TEXT_SELECTOR)
            pending_sep = '\n\n'
            for root in self.roots:
                state.current_id = root.identifier
                _render_single_package(root, self, self.config, state, out, pending_sep)
                pending_sep = '\n\n'
            return True
        pkg_root = self.definition_for(pkg_id_or_star)
        if pkg_root is None or pkg_root.depth != 0:
            self.error(f"package {pkg_id_or_star!r} not found or is not a root element")
            return False
        state.current_id = pkg_id_or_star
        out.write(_WARNING_TEXT_SELECTOR)
        out.write('\n\n')
        _render_single_package(pkg_root, self, self.config, state, out)
        return True

    def process_document(self, f, out,
                         doc_format: str = 'markdown',
                         add_missing: bool = False,
                         strip: bool = False,
                         existing_ids: Optional[set] = None,
                         seen_ids: Optional[set] = None) -> set:
        """Process a document file line by line, replacing LTAC selector regions.

        Writes all output to `out`. Performs no LTAC parsing.

        Returns the set of element identifiers rendered via 'element' selectors
        during this call, seeded from `seen_ids` if provided (useful for
        accumulating across multiple documents).

        When `add_missing` is True, inserts skeleton element regions for every
        declared LTAC element not yet seen via an 'element' selector.
        When `strip` is True, generated content is omitted from all selector
        regions except 'warning', leaving the markers in place with empty bodies.
        """
        _doc_state = DocState(doc_format=doc_format, seen_element_ids=set(seen_ids) if seen_ids is not None else set())
        filename = getattr(f, 'name', '<stream>')

        config = dict(self.config)  # local copy so directives don't affect self.config

        if add_missing:
            _ltac_ordered = [node for node in _all_nodes(self.roots)
                             if node.is_definition and node.identifier]
            _ltac_index: Dict[str, int] = {n.identifier: i for i, n in enumerate(_ltac_ordered)}
            _doc_ids = existing_ids if existing_ids is not None else set()
            _missing_set: set = ({n.identifier for n in _ltac_ordered}
                                 - _doc_state.seen_element_ids - _doc_ids)
            _inj_state = DocState(doc_format=doc_format,
                                  seen_element_ids=_doc_state.seen_element_ids)
            _last_placed_id: Optional[str] = None
            _stubs_added = [0]

            _stub_case = Case()
            _stub_case.registry = self.registry
            _stub_case.id_info = self.id_info
            _stub_case.config = config

            def _write_stub(ident: str) -> None:
                out.write('\n<!-- verocase element ' + ident + ' -->\n')
                _stub_case.render_element(ident, out, state=_inj_state)
                out.write('\n<!-- end verocase -->\n')
                _stubs_added[0] += 1

            def _emit_stubs_after(placed_id: Optional[str]) -> None:
                if placed_id is None or placed_id not in _ltac_index:
                    return
                for node in _ltac_ordered[_ltac_index[placed_id] + 1:]:
                    if node.identifier not in _missing_set:
                        break
                    _write_stub(node.identifier)
                    _missing_set.discard(node.identifier)

            def _emit_all_remaining() -> None:
                if not _missing_set:
                    return
                for node in _ltac_ordered:
                    if node.identifier in _missing_set:
                        _write_stub(node.identifier)
                _missing_set.clear()

        line_iter = enumerate(f, 1)
        for lineno, line in line_iter:
            text = line.rstrip('\r\n')

            if add_missing and '</body>' in text.lower():
                _emit_all_remaining()
                out.write(text + '\n')
                continue

            cm = _CASEPROC_CONFIG_RE.match(text)
            if cm:
                if add_missing:
                    _emit_stubs_after(_last_placed_id)
                    _last_placed_id = None
                apply_config_directive(cm.group(1), cm.group(2), config, filename, lineno)
                out.write(text + '\n')
                continue

            m = _CASEPROC_REGION_RE.match(text)
            if m:
                selector = m.group(1)
                _sel_parts = selector.split(None, 1)
                _sel_kind = _sel_parts[0] if _sel_parts else ''
                if _sel_kind == 'element' and _doc_state.after_epilogue:
                    self.error(f"'element' selector found after 'epilogue' in {filename}:{lineno}; "
                               "element selectors must not appear after an epilogue marker")
                if _sel_kind == 'epilogue':
                    _doc_state.after_epilogue = True
                if add_missing:
                    if _sel_kind == 'element':
                        _emit_stubs_after(_last_placed_id)
                    elif _sel_kind in ('stop', 'epilogue'):
                        _emit_all_remaining()
                found_end = _consume_region(line_iter, filename, lineno, selector, self)
                if strip and selector.strip() not in ('warning', 'stop', 'epilogue'):
                    out.write(text + '\n')
                    if found_end:
                        out.write('<!-- end verocase -->\n')
                else:
                    out.write(text + '\n')
                    if found_end:
                        _saved_config = self.config
                        self.config = config
                        try:
                            wrote = self.render_selector(selector, out,
                                                         doc_format=doc_format, state=_doc_state)
                        finally:
                            self.config = _saved_config
                        if wrote:
                            out.write('\n')
                        out.write('<!-- end verocase -->\n')
                if add_missing and _sel_kind == 'element' and len(_sel_parts) == 2:
                    _last_placed_id = _sel_parts[1]
                continue

            if 'verocase' in text and text.lstrip().startswith('<!-- end verocase -->'):
                self.panic(f"{filename}:{lineno}: unexpected '<!-- end verocase -->' "
                           "with no open region; check for a missing "
                           "'<!-- verocase ...' opener above this line")
                out.write(text + '\n')
                continue

            out.write(text + '\n')

        if add_missing:
            _emit_all_remaining()
            if _stubs_added[0]:
                self.notify(f"Added {_stubs_added[0]} missing element(s) to {filename}")

        return _doc_state.seen_element_ids

    def render_ltac_txt(self, node_list, out: 'TextIO', sep: str = '') -> bool:
        """Write node_list as raw LTAC text to out, normalizing indentation to depth 0.

        Uses self.config.
        """
        return _render_ltac_txt(node_list, self.config, out, sep)

    def _check_no_existing_case_files(self) -> None:
        """Panic if any well-known case file already exists."""
        for path in _START_CANDIDATES:
            if os.path.exists(path):
                self.panic(f"--start: {path!r} already exists; remove it before using --start")

    def _write_start_stubs(self) -> None:
        """Write initial case.ltac and case.md stubs for --start."""
        try:
            with open('case.ltac', 'w', encoding='utf-8') as f:
                f.write(_START_LTAC)
        except OSError as e:
            self.panic(f"--start: cannot write case.ltac: {e}")
        try:
            with open('case.md', 'w', encoding='utf-8') as f:
                f.write(_START_DOC)
        except OSError as e:
            self.panic(f"--start: cannot write case.md: {e}")
        self.notify("created case.ltac and case.md")


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


class _LTACParser:
    def __init__(self, case: 'Case') -> None:
        self._case = case

    def parse(self, lines: List[str], config: Optional[dict] = None) -> None:
        """Parse LTAC lines and populate the Case passed to __init__.

        Populates self._case.roots, self._case.registry, self._case.id_info.
        Also sets self.registry and self.id_info for internal use during parsing.
        """
        self._warn_dubious_reference: bool = (config or {}).get('warn_dubious_reference', True)
        self.registry: Dict[str, Node] = {}
        self._anchor_seen: Dict[str, str] = {}  # anchor id -> first label that claimed it
        # id_info[ident] = {
        #   'declarations': int,       count of non-citation nodes with this ID
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
        # carry a statement (non-Link, non-Relation, non-citation) and whether
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
                self._case.warn(f"line {ln}: {ident!r}: declaration has no statement"
                                f" (other declarations do)")

        self._case.roots = self.results
        self._case.registry = self.registry
        self._case.id_info = self.id_info

    def _parse_line(self, lineno: int, line: str) -> None:
        """Process a single LTAC source line, updating parser state."""
        stripped = line.strip()
        if not stripped:
            if self._stack or self._current_pkg:
                self._finalize_package()
            return

        leading = len(line) - len(line.lstrip(' '))
        if leading % 2 != 0:
            self._case.error(f"line {lineno}: indentation must be an even number of spaces"
                             f" (got {leading}): {line.rstrip()!r}")
            return

        m = _LTAC_LINE_RE.match(line)
        if not m:
            self._case.error(f"line {lineno}: unrecognized syntax: {line.rstrip()!r}")
            return

        node = self._build_node(m, lineno)
        self._attach_node(node, lineno)

    def _build_node(self, m, lineno: int) -> Node:
        """Construct a Node from a successful regex match."""
        depth = len(m.group('indent')) // 2
        nodetype = m.group('nodetype')
        is_citation = bool(m.group('cited'))
        identifier = (m.group('identifier') or '').strip()
        has_colon = m.group('text') is not None
        text = (m.group('text') or '').strip()
        ref = (m.group('ref') or '').strip()
        options = parse_options(m.group('options') or '')

        if is_citation and not identifier:
            self._case.error(f"line {lineno}: citation requires an identifier (e.g. '- {nodetype} ^ID:')")
        elif not is_citation and nodetype not in ('Link', 'Connector') and not has_colon:
            self._case.error(f"line {lineno}: element requires ':' after the identifier (e.g. '- {nodetype} ID: text')")
        elif not is_citation and nodetype not in ('Link', 'Connector') and not identifier and not text:
            self._case.error(f"line {lineno}: {nodetype} element has no identifier and no statement;"
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
            is_citation=is_citation,
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
        if is_citation:                 active = active | {'ascited'}
        if len(active) >= 2:
            label = identifier or f'(unnamed {nodetype})'
            self._case.error(f"line {lineno}: {label}: conflicting assertion status:"
                             f" {', '.join(sorted(active))} (mutually exclusive per SACM spec section 11)")

        # Dubious reference: warn if the reference looks like a parenthetical comment.
        if self._warn_dubious_reference and _is_dubious_reference(ref):
            label = f"{nodetype} {identifier}" if identifier else nodetype
            self._case.warn(f"line {lineno}: {label}: dubious reference ({ref!r}):"
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
                self._case.error(f"line {lineno}: {node.identifier!r}: type {node.node_type!r}"
                                 f" conflicts with earlier use as {info['node_type']!r}")
            if node.is_citation:
                info['citations'] += 1
                if pkg_root_id and pkg_root_id not in info['citing_pkg_ids']:
                    info['citing_pkg_ids'].append(pkg_root_id)
            else:
                if info['declarations'] > 0:
                    self._case.warn(f"line {lineno}: duplicate declaration {node.identifier!r}")
                else:
                    info['decl_lineno'] = lineno
                    info['decl_pkg_id'] = pkg_root_id
                    self.registry[node.identifier] = node
                    anchor = _component_anchor_id(node.node_type, node.identifier)
                    label = f"{node.node_type} {node.identifier}"
                    if anchor in self._anchor_seen:
                        self._case.error(f"line {lineno}: anchor id collision on {anchor!r}:"
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
                    hint = "; use --update to sync" if (node.is_citation or info['citations'] > 0) else ""
                    self._case.warn(f"line {lineno}: {node.identifier!r}: statement {node.text!r}"
                                    f" differs from earlier statement {info['statement']!r}{hint}")

        # Pop stack until top's depth < current depth
        while self._stack and self._stack[-1][0] >= node.depth:
            self._stack.pop()

        # Validate depth: must not jump more than one level deeper than parent.
        if self._stack:
            parent_depth = self._stack[-1][0]
            if node.depth > parent_depth + 1:
                self._case.error(f"line {lineno}: indentation jumps from depth {parent_depth}"
                                 f" to depth {node.depth} (increase must be exactly 2 spaces / 1 level)")
        elif node.depth > 0:
            self._case.error(f"line {lineno}: indentation is {node.depth * 2} spaces but"
                             f" there is no parent node to attach to")

        if self._stack:
            parent_node = self._stack[-1][1]
            if (node.node_type in ('Claim', 'Strategy')
                    and parent_node.node_type in _NON_INFERENTIAL_TYPES):
                self._case.warn(f"line {lineno}: {node.node_type} should not be"
                                f" a child of {parent_node.node_type}")
            # Evidence is a leaf node; non-metadata children are invalid.
            # Claim and Strategy are excluded here because the _NON_INFERENTIAL_TYPES
            # check above already warns when they appear under Evidence, avoiding
            # a duplicate warning for the same issue.
            if (parent_node.node_type == 'Evidence'
                    and node.node_type not in ('Claim', 'Strategy',
                                               'Context', 'Relation', 'Link')):
                self._case.warn(f"line {lineno}: {node.node_type} should not be a child of"
                                f" Evidence (Evidence is a leaf node)")
            node.parent = parent_node
            if node.identifier:
                parent_label = (f" under {parent_node.identifier!r}"
                                if parent_node.identifier else "")
                for sib in parent_node.children:
                    if sib.identifier == node.identifier:
                        self._case.warn(f"line {lineno}: duplicate sibling identifier"
                                        f" {node.identifier!r}{parent_label}")
            if node.is_citation and node.node_type not in ('Claim', 'Justification'):
                self._case.warn(f"line {lineno}: external citation ^{node.identifier!r} has type"
                                f" {node.node_type!r}; only Claim and Justification are"
                                f" recommended for cross-package citations")
            parent_node.children.append(node)
        else:
            if self._current_pkg:
                self._case.panic(
                    f"package starting at line {self._pkg_root_lineno} "
                    f"already has a top-level element; only one allowed"
                )
            if node.node_type not in ('Claim', 'Justification'):
                self._case.warn(f"line {lineno}: {node.node_type} {node.identifier!r}:"
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
            canonical = _statement_for(self.id_info, target_id)
            if node.text and canonical is not None and node.text != canonical:
                self._case.warn(f"line {lineno}: Link {target_id!r}: statement {node.text!r}"
                                f" differs from declaration; use --update to sync")
        else:
            self._case.warn(f"line {lineno}: Link target {target_id!r} not found")

    def _finalize_package(self) -> None:
        """Flush the current package's root into results and reset package state."""
        self.results.extend(self._current_pkg)
        self._current_pkg = []
        self._pkg_root_lineno = None
        self._stack = []



def _all_nodes_fast(roots: List[Node]):
    """Yield every node in the forest faster than _all_nodes(), but not in LTAC order.

    Traversal is DFS with children pushed in forward order onto a list-stack,
    so they are popped and visited in reverse order (last child first, recursively).
    The order is fully deterministic for a given tree; it is simply not the order
    a reader would expect from the LTAC source file.

    Do not write code that depends on this specific order; a future implementation
    may change it.  Use only when order does not matter (e.g. building a lookup
    set, computing aggregate counts) and throughput is a concern.

    **Why this is a separate function, not a flag on _all_nodes():**

    _all_nodes() visits children in LTAC written order (first child first) using
    ``stack.extend(reversed(node.children))``.  The ``reversed()`` call creates a
    Python-level iterator that extend() must consume element-by-element, incurring
    per-element interpreter overhead.  _all_nodes_fast() instead calls
    ``stack.extend(node.children)`` — a direct list-to-list bulk copy at the C
    level — which is roughly 2-3x faster.

    The obvious fixes do not work:
    - Storing children in reverse order would make _all_nodes_fast() correct but
      break every caller that reads node.children[0] as the first child.
    - Using a deque with popleft() still requires reversed() for first-child-first
      order, and deque has worse cache locality than a list for this workload.
    - An iterator-stack approach (push iter(node.children) rather than the children
      themselves) eliminates reversed() but replaces it with per-element iter()/
      next() overhead — a wash at best, and more complex.

    The speed difference is therefore fundamental to storing children in natural
    order and wanting correct DFS order.  _all_nodes_fast() accepts the trade-off:
    arbitrary (but deterministic) order in exchange for maximum throughput.
    """
    stack = list(roots)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children)


def _all_nodes(roots: List[Node]):
    """Yield every node in the forest in LTAC written order (depth-first, first child first).

    Nodes appear in the same order as their declarations in the LTAC file.
    Prefer this generator by default; use _all_nodes_fast() only when order
    genuinely does not matter and throughput is a concern.
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
# id_info accessors (private; use Case.declaring_package_for / Case.statement_for)
# ---------------------------------------------------------------------------

def _decl_pkg_id_for(id_info: Dict[str, dict], ident: str) -> Optional[str]:
    """Return the package root identifier string where ident is declared, or None.

    Private helper used by render functions that need the string ID directly.
    Public callers should use Case.declaring_package_for() which returns a Node.
    """
    return id_info.get(ident, _EMPTY).get('decl_pkg_id')


def _statement_for(id_info: Dict[str, dict], ident: str) -> Optional[str]:
    """Return the canonical statement text for ident, or None.

    Internal implementation for Case.statement_for().
    """
    return id_info.get(ident, _EMPTY).get('statement')


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
    if node.is_citation:
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

    NOTE: Mermaid click statements use _node_anchor_url directly so that
    clicking always navigates to the element section, not to its ext_ref.
    The ext_ref is shown separately in the rendered document text.
    """
    if node.ext_ref:
        return _resolve_ext_ref(node.ext_ref, base_url)
    if not base_url:
        return ''
    return _node_anchor_url(node, base_url, pkg_label)


def _render_markdown_node(node: Node, indent: int, base_url: str,
                          out: TextIO, pkg_label: str,
                          first: list) -> None:
    """Write a markdown bullet for node directly to out, recurse into children.

    The full 'Type ID: text' label links to its document anchor.  If the node
    has an ext_ref, it is appended as a separate parenthetical link.
    Link nodes are silently skipped (they are citations, not new bullets).
    `first` is a one-element list used as a mutable bool: True until the first
    line is written, then False (so subsequent lines get a leading newline).
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
    if not first[0]:
        out.write('\n')
    out.write('  ' * indent + f'- {main}{ref_part}')
    first[0] = False
    for child in node.children:
        _render_markdown_node(child, indent + 1, base_url, out, pkg_label, first)


def render_markdown(roots: List[Node], config: dict, out: TextIO) -> bool:
    """Write a list of nodes as an indented markdown bullet list with hyperlinks.

    Each item is '- NodeType ID: text' where the label is a hyperlink to
    the element's document anchor when base_url is set.  If an ext_ref is
    present it is shown as an additional parenthetical link.
    Link nodes are skipped.
    """
    base_url = config.get('markdown_base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    first = [True]
    for root in roots:
        _render_markdown_node(root, 0, base_url, out, pkg_label, first)
    return not first[0]


def render_statement(node: Node) -> str:
    """Return a markdown 'Statement:' line for the node's text."""
    return f"Statement: {node.text}"


def _render_html_node(node: Node, indent: int, base_url: str, out: TextIO,
                      pkg_label: str = DEFAULT_CONFIG['pkg_label']) -> None:
    """Write an HTML li element for node directly to out, recurse into children.

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
    prefix = '  ' * indent
    visible_children = [c for c in node.children if c.node_type != 'Link']
    if visible_children:
        out.write(f'\n{prefix}<li>{main}')
        out.write(f'\n{prefix}<ul>')
        for child in node.children:
            _render_html_node(child, indent + 1, base_url, out, pkg_label)
        out.write(f'\n{prefix}</ul>')
        out.write(f'\n{prefix}</li>')
    else:
        out.write(f'\n{prefix}<li>{main}</li>')


def render_html(roots: List[Node], config: dict, out: TextIO) -> bool:
    """Write a list of nodes as a nested HTML ul/li list with hyperlinks.

    Link nodes are skipped. Identifiers are hyperlinked when a URL is available.
    """
    base_url = config.get('markdown_base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    out.write('<ul>')
    for root in roots:
        _render_html_node(root, 1, base_url, out, pkg_label)
    out.write('\n</ul>')
    return True


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
    """Return every node in the forest as a list in breadth-first order.

    Roots appear first, then their children left-to-right, then
    grandchildren, and so on.  Useful for diagram layout and any algorithm
    that needs to process ancestors before descendants.
    """
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
        is_citation=False,
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
        elif node.is_citation:
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
    write_edge,
) -> None:
    """Write sacmDot declarations and edges for *node* and its subtree.

    Edges are written (via write_edge) in DFS post-order (deepest leaves first,
    so the last edge written connects to the top-level root).

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
                _sacm_collect_edges(child, dot_counter, dot_decls, write_edge)
        for child in node.children:
            if child.node_type != 'Link':
                write_edge(f'    {child.diagram_id} --- {node.diagram_id}')
        return

    if node.node_type in ('Strategy', 'Relation'):
        # Just recurse; the enclosing Claim handles edge emission for this group.
        for child in node.children:
            if child.node_type != 'Link':
                _sacm_collect_edges(child, dot_counter, dot_decls, write_edge)
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
            _sacm_collect_edges(child, dot_counter, dot_decls, write_edge)

    # Emit inference edges for this node.
    if len(inference_sources) == 1:
        src, is_counter, is_abstract = inference_sources[0]
        write_edge(_edge_line(
            src.diagram_id, node.diagram_id, False, is_counter, is_abstract))
    elif len(inference_sources) >= 2:
        dot_id = f'Dot{dot_counter[0]}'
        dot_counter[0] += 1
        any_counter = any(c for _, c, _ in inference_sources)
        any_abstract = any(a for _, _, a in inference_sources)
        dot_decls.append(f'    {dot_id}(("{_HAIR_SPACE}")):::sacmDot')
        for src, _, is_abstract in inference_sources:
            write_edge(_sacm_source_edge(src.diagram_id, dot_id, is_abstract))
        dot_arrow = (
            '-.->|⊖|' if (any_abstract and any_counter) else
            '-.->'     if any_abstract else
            '-->|⊖|'   if any_counter  else '-->'
        )
        write_edge(f'    {dot_id} {dot_arrow} {node.diagram_id}')

    # Emit context edges: direct Context children → this node.
    for ctx, is_counter, is_abstract in context_children:
        write_edge(
            _edge_line(ctx.diagram_id, node.diagram_id, True, is_counter, is_abstract))

    # Emit context edges: Context children of Strategy children → that Strategy.
    for s in strategy_children:
        for ctx, is_counter, is_abstract in strategy_ctx.get(s.diagram_id, []):
            write_edge(
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


def _sacm_diagram_body(roots: List['Node'], config: dict, out: TextIO) -> None:
    """Write the SACM diagram content without opening/closing fence markers."""
    base_url = config.get('base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    bottom_padding = config.get('bottom_padding', DEFAULT_CONFIG['bottom_padding'])
    roots = _copy_forest(roots)
    syn_counter = [0]
    _apply_sacm_width_transform(roots, config, syn_counter)

    body_header = _SACM_HEADER[len('```mermaid\n'):]
    out.write(body_header)

    # Node declarations (BFS); write directly.
    for node in _collect_bfs(roots):
        decl = _sacm_node_decl(node)
        if decl:
            out.write('\n')
            out.write(decl)

    # Single DFS pass: collect dot declarations and edge lines together.
    # Dot declarations must appear before edge lines in the Mermaid output,
    # so edges are buffered here and written after.
    dot_counter = [1]
    dot_decls: list = []
    edge_lines: list = []
    for root in roots:
        _sacm_collect_edges(root, dot_counter, dot_decls, edge_lines.append)
    for decl in dot_decls:
        out.write('\n')
        out.write(decl)

    # Click lines (BFS); write directly.
    # Link to the element anchor; never directly to ext_ref.
    # When base_url is empty, fragment-only links (#id) are used so that
    # clicks still work on platforms that resolve them within the same page.
    for node in _collect_bfs(roots):
        if node.node_type not in ('Relation', 'Link'):
            url = _node_anchor_url(node, base_url, pkg_label)
            if url:
                out.write('\n')
                out.write(f'    click {node.diagram_id} "{url}"')

    # Edges: BottomPadding first, then DFS edges; blank separator before first edge.
    _first_edge = [True]

    def _write_edge(line: str) -> None:
        if _first_edge[0]:
            out.write('\n')  # blank line between declarations and edges
            _first_edge[0] = False
        out.write('\n')
        out.write(line)

    if bottom_padding and roots:
        bottom_node = _sacm_leftmost_leaf(roots[0])
        _write_edge(f'    BottomPadding[ ]:::invisible ~~~ {bottom_node.diagram_id}')

    for edge_line in edge_lines:
        _write_edge(edge_line)


def render_sacm(roots: List['Node'], config: dict, out: TextIO) -> bool:
    """Write package roots as a complete SACM/mermaid code block to out.

    Output structure: header → node declarations (BFS) → sacmDot declarations
    → click lines → blank line → BottomPadding + edges (DFS post-order, deepest first).
    The original nodes are not modified; a deep copy is used internally.
    """
    out.write('```mermaid\n')
    _sacm_diagram_body(roots, config, out)
    out.write('\n```')
    return True


def render_sacm_html(roots: List['Node'], config: dict, out: TextIO,
                     state: 'DocState' = None) -> bool:
    """Write SACM diagram as a <pre class="mermaid"> block to out."""
    _maybe_inject_mermaid_js(config, state, out)
    out.write('<pre class="mermaid">\n')
    _sacm_diagram_body(roots, config, out)
    out.write('\n</pre>')
    return True


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
    elif node.is_citation:
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


def _gsn_collect_edges(node, write_edge, leaf_nodes):
    """Write GSN edges for *node* and its subtree (DFS pre-order) via write_edge.

    Nodes with no outgoing edges are appended to leaf_nodes.
    """
    if node.node_type in ('Link', 'Relation'):
        return
    edges_before = [0]  # track whether this node emits any edges
    _had_edge = [False]

    def _we(line: str) -> None:
        _had_edge[0] = True
        write_edge(line)

    for child in node.children:
        if child.node_type == 'Link':
            if child.link_target is not None:
                tgt = child.link_target
                _we(_edge_line(
                    node.diagram_id, tgt.diagram_id,
                    _gsn_is_incontextof(tgt),
                    'counter' in child.options, False))
        elif child.node_type == 'Connector':
            _we(_edge_line(node.diagram_id, child.diagram_id,
                           False, False, False))
            _gsn_collect_edges(child, write_edge, leaf_nodes)
        elif child.node_type == 'Relation':
            rc = 'counter' in child.options
            ra = 'abstract' in child.options
            for gc in child.children:
                if gc.node_type == 'Link':
                    if gc.link_target is not None:
                        tgt = gc.link_target
                        _we(_edge_line(
                            node.diagram_id, tgt.diagram_id,
                            _gsn_is_incontextof(tgt), rc, ra))
                else:
                    _we(_edge_line(
                        node.diagram_id, gc.diagram_id,
                        _gsn_is_incontextof(gc), rc, ra))
                    _gsn_collect_edges(gc, write_edge, leaf_nodes)
        else:
            _we(_edge_line(
                node.diagram_id, child.diagram_id,
                _gsn_is_incontextof(child),
                'counter' in child.options, False))
            _gsn_collect_edges(child, write_edge, leaf_nodes)
    if not _had_edge[0]:
        leaf_nodes.append(node)


def _gsn_diagram_body(roots: List['Node'], config: dict, out: TextIO) -> None:
    """Write the GSN diagram content without opening/closing fence markers."""
    base_url = config.get('base_url', '')
    pkg_label = config.get('pkg_label', DEFAULT_CONFIG['pkg_label'])
    bottom_padding = config.get('bottom_padding', DEFAULT_CONFIG['bottom_padding'])
    roots = _copy_forest(roots)
    syn_counter = [0]
    _apply_gsn_width_transform(roots, config, syn_counter)

    body_header = _GSN_HEADER[len('```mermaid\n'):]
    out.write(body_header)

    # Node declarations (BFS); write directly.
    for node in _collect_bfs(roots):
        decl = _gsn_node_decl(node)
        if decl:
            out.write('\n')
            out.write(decl)

    # Click lines (BFS); write directly.
    # Link to the element anchor; never directly to ext_ref.
    # When base_url is empty, fragment-only links (#id) are used so that
    # clicks still work on platforms that resolve them within the same page.
    for node in _collect_bfs(roots):
        if node.node_type not in ('Relation', 'Link', 'Connector'):
            url = _node_anchor_url(node, base_url, pkg_label)
            if url:
                out.write('\n')
                out.write(f'    click {node.diagram_id} "{url}"')

    # Edges (DFS pre-order); write directly and collect leaf nodes for BottomPadding.
    leaf_nodes: list = []
    _first_edge = [True]

    def _write_edge(line: str) -> None:
        if _first_edge[0]:
            out.write('\n')  # blank line between declarations and edges
            _first_edge[0] = False
        out.write('\n')
        out.write(line)

    for root in roots:
        _gsn_collect_edges(root, _write_edge, leaf_nodes)

    # BottomPadding (after edges): all leaves link to an invisible padding node
    # that prevents GitHub's diagram controls from obscuring the bottom.
    if bottom_padding:
        first_bp = True
        seen: set = set()
        for leaf in leaf_nodes:
            if leaf.diagram_id not in seen:
                seen.add(leaf.diagram_id)
                bp = 'BottomPadding[ ]:::invisible' if first_bp else 'BottomPadding'
                _write_edge(f'    {leaf.diagram_id} ~~~ {bp}')
                first_bp = False


def render_gsn(roots: List['Node'], config: dict, out: TextIO) -> bool:
    """Write package roots as a complete GSN/mermaid code block to out.

    Output structure: header → node declarations (BFS) → click lines
    → blank line → BottomPadding lines + edges (DFS pre-order).
    The original nodes are not modified; a deep copy is used internally.
    """
    out.write('```mermaid\n')
    _gsn_diagram_body(roots, config, out)
    out.write('\n```')
    return True


def render_gsn_html(roots: List['Node'], config: dict, out: TextIO,
                    state: 'DocState' = None) -> bool:
    """Write GSN diagram as a <pre class="mermaid"> block to out."""
    _maybe_inject_mermaid_js(config, state, out)
    out.write('<pre class="mermaid">\n')
    _gsn_diagram_body(roots, config, out)
    out.write('\n</pre>')
    return True


def _resolve_element(
    element_id: Optional[str],
    case: 'Case',
    current_element: Optional[Node],
) -> List[Node]:
    """Return the list of nodes to render for the given element_id.

    If element_id is given: look up via definition_for(); call error() and return []
    if not found.  If element_id is None: use current_element if set, else
    return case.roots.  ('*' is handled at dispatch time before calling here.)
    """
    if element_id is not None:
        node = case.definition_for(element_id)
        if node is None:
            case.error(f"element {element_id!r} not found")
            return []
        return [node]
    if current_element is not None:
        return [current_element]
    return list(case.roots)


def render_all_packages(all_roots: List[Node], render_fn, config: dict,
                        out: TextIO) -> bool:
    """Write every package preceded by a configurable header to out.

    Package blocks are separated by a blank line.
    Header format: {pkg_header_prefix}{pkg_label}{id}{pkg_header_suffix}{content}
    """
    prefix = config.get('pkg_header_prefix', '### ')
    suffix = config.get('pkg_header_suffix', '\n')
    pkg_label = config.get('pkg_label', 'Package ')
    pending_sep = ''
    for root in all_roots:
        label = f"{pkg_label}{root.identifier}" if root.identifier else pkg_label.rstrip()
        out.write(pending_sep)
        out.write(f"{prefix}{label}{suffix}")
        render_fn([root], config, out)
        pending_sep = '\n\n'
    return pending_sep != ''


_VALID_DISPLAY_TYPES = {
    'ltac/markdown', 'ltac/html', 'ltac/txt',
    'sacm/mermaid', 'sacm/mermaid/markdown', 'sacm/mermaid/html',
    'gsn/mermaid',  'gsn/mermaid/markdown',  'gsn/mermaid/html',
    'statement',
    'element', 'package',
    'info',
    'warning',
    'stop',
    'epilogue',
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
        print(f"verocase: error: unknown selector type {display_type!r}", file=sys.stderr)
    return display_type, element_id


def _render_or_all(
    element_id: Optional[str],
    case: 'Case',
    render_fn,
    current_element: Optional[Node],
    config: dict,
    out: TextIO,
) -> bool:
    """Resolve element_id and render to out, or render all packages if element_id is '*'."""
    if element_id == '*':
        return render_all_packages(case.roots, render_fn, config, out)
    nodes = _resolve_element(element_id, case, current_element)
    if not nodes:
        return False
    return render_fn(nodes, config, out)


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
    """Return all nodes that have a cited child (^ident) anywhere in the forest.

    A "citation parent" is a node whose direct children include a Node with
    is_citation=True and identifier==ident.  The same parent appears at most
    once; multiple packages may each contribute a parent.
    """
    parents = []
    for node in _all_nodes_fast(all_roots):
        if node.identifier == ident and node.is_citation and node.parent is not None:
            if node.parent not in parents:
                parents.append(node.parent)
    return parents


def render_referenced_by(node: Node, case: 'Case',
                         config: dict, fmt: str,
                         out: TextIO, sep: str = '') -> bool:
    """Write 'Referenced by: ...' line to out; return False if no packages to list."""
    ident = node.identifier
    info = case.id_info.get(ident, {})
    pkg_ids = []
    if info.get('decl_pkg_id'):
        pkg_ids.append(info['decl_pkg_id'])
    for cid in info.get('citing_pkg_ids', []):
        if cid not in pkg_ids:
            pkg_ids.append(cid)
    if not pkg_ids:
        return False
    pairs = [(f'Package {pid}', _pkg_anchor_url(pid, config)) for pid in pkg_ids]
    out.write(sep)
    out.write('Referenced by: ' + _linked_list(pairs, fmt))
    return True


def render_supported_by(node: Node, config: dict, fmt: str,
                        out: TextIO, sep: str = '') -> bool:
    """Write 'Supported by: ...' line to out; return False if no children."""
    children = [c for c in node.children if c.node_type != 'Link'
                or c.link_target is not None]
    if not children:
        return False
    pairs = []
    for child in children:
        target = child.link_target if child.node_type == 'Link' else child
        if target is None or not target.identifier:
            continue
        pairs.append((f'{target.node_type} {target.identifier}',
                      _element_anchor_url(target.node_type, target.identifier, config)))
    if not pairs:
        return False
    out.write(sep)
    out.write('Supported by: ' + _linked_list(pairs, fmt))
    return True


def render_supports(node: Node, case: 'Case',
                    config: dict, fmt: str,
                    out: TextIO, sep: str = '') -> bool:
    """Write 'Supports: ...' line to out; return False if no parents at all."""
    pairs = []
    has_direct_parent = node.parent is not None
    if has_direct_parent:
        p = node.parent
        pairs.append((f'{p.node_type} {p.identifier}',
                      _element_anchor_url(p.node_type, p.identifier, config)))
    for parent in case.find_citation_parents(node.identifier):
        if not parent.identifier:
            continue
        pairs.append((f'{parent.node_type} {parent.identifier}',
                      _element_anchor_url(parent.node_type, parent.identifier, config)))
    if not pairs:
        return False
    out.write(sep)
    out.write('Supports: ' + _linked_list(pairs, fmt, bold_first=has_direct_parent))
    return True


def _render_ext_ref(node: Node, config: dict, fmt: str,
                   out: TextIO, sep: str = '') -> bool:
    """Write 'External Reference: <link>' to out; return False if no ext_ref.

    The hyperlink URL is resolved via _resolve_ext_ref (so relative paths are
    joined with base_url when present); the visible link text is the raw
    ext_ref value without any base_url prefix.
    """
    if not node.ext_ref:
        return False
    url = _resolve_ext_ref(node.ext_ref, config.get('base_url', ''))
    out.write(sep)
    out.write('External Reference: ' + hyperlink(node.ext_ref, url, fmt))
    return True


# Map selection name -> fn(node, all_roots, id_info, config, fmt, out, sep).
# render_referenced_by and render_supports already match (primary, case, config, fmt, out, sep).
_ELEMENT_RENDER_MAP: Dict[str, callable] = {
    'referenced_by': render_referenced_by,
    'supported_by':  lambda node, case, config, fmt, o, s: render_supported_by(node, config, fmt, o, s),
    'supports':      render_supports,
    'ext_ref':       lambda node, case, config, fmt, o, s: _render_ext_ref(node, config, fmt, o, s),
}


def render_pkg_defines(pkg_root: Node, case: 'Case',
                       config: dict, fmt: str,
                       out: TextIO, sep: str = '') -> bool:
    """Write 'Defines: ...' list for a package to out."""
    pkg_id = pkg_root.identifier
    defined = []
    for node in _all_nodes_fast([pkg_root]):
        if (node.is_definition and node.identifier
                and _decl_pkg_id_for(case.id_info, node.identifier) == pkg_id):
            defined.append(node)
    if not defined:
        return False
    pairs = [(f'{node.node_type} {node.identifier}',
              _element_anchor_url(node.node_type, node.identifier, config))
             for node in defined]
    out.write(sep)
    out.write('Defines: ' + _linked_list(pairs, fmt))
    return True


def render_pkg_citing(pkg_root: Node, case: 'Case',
                      config: dict, fmt: str,
                      out: TextIO, sep: str = '') -> bool:
    """Write 'Citing: ...' list for a package to out; return False if none."""
    cited_nodes = [n for n in _all_nodes_fast([pkg_root])
                   if n.is_citation and n.identifier]
    if not cited_nodes:
        return False
    links = []
    for node in cited_nodes:
        decl_pkg = _decl_pkg_id_for(case.id_info, node.identifier) or ''
        label = f'{node.node_type} {node.identifier}'
        url = _pkg_anchor_url(decl_pkg, config) if decl_pkg else ''
        links.append(hyperlink(label, url, fmt) if url else label)
    out.write(sep)
    out.write('Citing: ' + ', '.join(links))
    return True


def render_pkg_cited(pkg_root: Node, case: 'Case',
                     config: dict, fmt: str,
                     out: TextIO, sep: str = '') -> bool:
    """Write 'Cited by: ...' list for a package to out; return False if none."""
    pkg_id = pkg_root.identifier
    citing_pkgs = []
    for ident, info in case.id_info.items():
        if info.get('decl_pkg_id') == pkg_id:
            for cpid in info.get('citing_pkg_ids', []):
                if cpid not in citing_pkgs:
                    citing_pkgs.append(cpid)
    if not citing_pkgs:
        return False
    pairs = [(f'Package {cpid}', _pkg_anchor_url(cpid, config)) for cpid in citing_pkgs]
    out.write(sep)
    out.write('Cited by: ' + _linked_list(pairs, fmt, bold_first=False))
    return True


def render_representation(pkg_root: Node, all_roots: List[Node],
                          config: dict, fmt: str, out: TextIO,
                          sep: str = '', state: 'DocState' = None,
                          case: 'Case' = None) -> bool:
    """Write the default diagram representation for a package to out."""
    notation = config.get('default_representation', 'sacm')
    renderer = config.get('default_renderer', 'mermaid')
    selector = f'{notation}/{renderer}/{fmt}'
    if selector in ('sacm/mermaid/markdown', 'sacm/mermaid'):
        out.write(sep)
        return render_sacm([pkg_root], config, out)
    elif selector == 'sacm/mermaid/html':
        out.write(sep)
        return render_sacm_html([pkg_root], config, out, state)
    elif selector in ('gsn/mermaid/markdown', 'gsn/mermaid'):
        out.write(sep)
        return render_gsn([pkg_root], config, out)
    elif selector == 'gsn/mermaid/html':
        out.write(sep)
        return render_gsn_html([pkg_root], config, out, state)
    elif selector == 'ltac/markdown':
        out.write(sep)
        return render_markdown([pkg_root], config, out)
    elif selector == 'ltac/html':
        out.write(sep)
        return render_html([pkg_root], config, out)
    else:
        if case is not None:
            case.error(f"unsupported representation {selector!r}")
        else:
            print(f"verocase: error: unsupported representation {selector!r}", file=sys.stderr)
        return False


# render_pkg_defines/citing/cited now match (primary, case, config, fmt, out, sep); representation needs an adapter.
_PACKAGE_RENDER_MAP: Dict[str, callable] = {
    'representation': lambda pkg, case, config, fmt, o, s: render_representation(pkg, case.roots, config, fmt, o, s, case=case),
    'pkg_defines':    render_pkg_defines,
    'pkg_citing':     render_pkg_citing,
    'pkg_cited':      render_pkg_cited,
}


def _apply_sel(sel_str: str, render_map: Dict[str, callable],
               primary: Node, case: 'Case',
               config: dict, fmt: str,
               out: TextIO, pending_sep: str = '') -> bool:
    """Apply sub-selections from a comma-separated string, writing each separated by blank lines.

    Each entry in render_map must accept (primary, case, config, fmt, out, sep).
    Returns True if anything was written.
    """
    wrote_any = False
    for sel in sel_str.split(','):
        sel = sel.strip()
        if not sel:
            continue
        fn = render_map.get(sel)
        if fn is None:
            case.warn(f"unknown selection name {sel!r}")
            continue
        if fn(primary, case, config, fmt, out, pending_sep):
            pending_sep = '\n\n'
            wrote_any = True
    return wrote_any


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


def _render_single_package(pkg_root: Node, case: 'Case',
                            config: dict, state: 'DocState',
                            out: TextIO, sep: str = '') -> bool:
    """Write one package heading + its package_selections to out."""
    fmt = state.doc_format
    level = config.get('package_level', 3)
    anchor = _component_anchor_id('Package', pkg_root.identifier)
    stmt = case.statement_for(pkg_root.identifier) or pkg_root.text or ''
    heading_text = f'Package {pkg_root.identifier}'
    if stmt:
        heading_text += f': {stmt}'

    out.write(sep)
    out.write(_make_heading(anchor, level, heading_text, fmt))
    _apply_sel(config.get('package_selections', _DEFAULT_PACKAGE_SELECTIONS),
               _PACKAGE_RENDER_MAP, pkg_root, case, config, fmt, out, pending_sep='\n\n')
    return True


_WARNING_TEXT = (
    '<!-- WARNING: DO NOT EDIT text within verocase SELECTOR ... end verocase. -->\n'
    '<!-- Those regions are regenerated. -->'
)

_WARNING_TEXT_SELECTOR = '<!-- DO NOT EDIT text from here until "end verocase" -->'


def render_warning(element_id: Optional[str]) -> str:
    """Render the warning selector.  Refuses any element_id argument."""
    if element_id is not None:
        print("verocase: error: 'warning' selector takes no parameters", file=sys.stderr)
        return ''
    return _WARNING_TEXT


# ---------------------------------------------------------------------------
# Document processor
# ---------------------------------------------------------------------------

@dataclass
class DocState:
    """Mutable rendering state threaded through a single document processing pass.

    Create a fresh instance for each independent rendering pass.  When calling
    case.render_selector() outside of process_document(), a default
    ``DocState()`` is sufficient for most uses.

    Attributes
    ----------
    current_id : Optional[str]
        Identifier of the element region currently being rendered; None
        between regions.  Used to resolve bare (no-ID) selectors.
    doc_format : str
        Output format: ``'markdown'`` (default) or ``'html'``.
    mermaid_injected : bool
        True once the Mermaid JS <script> block has been written for this
        document; prevents duplicate injection.
    seen_element_ids : set
        Identifiers of elements rendered via ``element`` selectors so far;
        updated by render_element() as a side-effect.
    after_epilogue : bool
        True once an ``epilogue`` selector has been encountered; subsequent
        element output is suppressed.
    """
    current_id: Optional[str] = None
    doc_format: str = 'markdown'
    mermaid_injected: bool = False
    seen_element_ids: set = field(default_factory=set)
    after_epilogue: bool = False  # True once an 'epilogue' selector has been seen


def _maybe_inject_mermaid_js(config: dict, state: 'DocState', out: TextIO) -> None:
    """Write the Mermaid JS <script> block to out if not yet injected.

    Only acts when:
    - state is not None and doc_format is 'html'
    - state.mermaid_injected is False
    - mermaid_js_url is non-empty
    """
    if state is None or state.doc_format != 'html' or state.mermaid_injected:
        return
    url = config.get('mermaid_js_url', DEFAULT_CONFIG['mermaid_js_url'])
    if not url:
        return
    out.write(
        f'<script type="module">\n'
        f"  import mermaid from '{url}';\n"
        f'  mermaid.initialize({{ startOnLoad: true }});\n'
        f'</script>\n'
    )
    state.mermaid_injected = True


# Matches '<!-- verocase SELECTOR -->' lines (SELECTOR is captured in group 1).
_CASEPROC_REGION_RE = re.compile(r'^<!--\s*verocase\s+(.+?)\s*-->\s*$')

# Matches '<!-- verocase-config KEY = VALUE -->' directives.
_CASEPROC_CONFIG_RE = re.compile(r'^<!--\s*verocase-config\s+(\S+)\s*=\s*(.*?)\s*-->\s*$')

# Allowed dynamically-settable config keys and their validation patterns.
_ALLOWED_CONFIG_VALUES = {
    'base_url': re.compile(r'.*'),
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
        print(f"verocase: warning: {filename}:{lineno}: verocase-config: unknown key {key!r}", file=sys.stderr)
        return
    pattern = _ALLOWED_CONFIG_VALUES.get(key)
    if pattern is None:
        print(f"verocase: warning: {filename}:{lineno}: verocase-config: key {key!r} is not dynamically settable", file=sys.stderr)
        return
    elif not pattern.match(value):
        print(f"verocase: warning: {filename}:{lineno}: verocase-config: invalid value {value!r} for {key!r}", file=sys.stderr)
        return
    if key in ('element_level', 'package_level',
               'max_mermaid_children', 'narrowed_mermaid_children'):
        config[key] = int(value)
    else:
        config[key] = value
    if key in ('max_mermaid_children', 'narrowed_mermaid_children'):
        config_invariant_checker(config, filename, lineno)


def _consume_region(line_iter, filename: str, start_lineno: int, selector: str,
                    case: 'Case' = None) -> bool:
    """Consume lines from line_iter until '<!-- end verocase -->', return True if found.

    If EOF is reached before finding the end marker, calls error() and returns False.
    Panics immediately if a nested directive is found before the end marker.
    """
    for lineno, line in line_iter:
        # Pre-filter: 'verocase' only appears in our directives, so skip the
        # strip()/startswith() work on the vast majority of prose lines.
        if 'verocase' in line:
            stripped = line.strip()
            if stripped.startswith('<!-- end verocase -->'):
                return True
            if stripped.startswith('<!-- verocase'):
                msg = (f"{filename}:{lineno}: directive nested inside "
                       f"'<!-- verocase {selector} -->' region "
                       f"(opened at {filename}:{start_lineno}); "
                       "directives cannot be nested. Check for a missing "
                       "'<!-- end verocase -->' before this line")
                if case is not None:
                    case.panic(msg)
                else:
                    panic(msg)
    msg = f"{filename}:{start_lineno}: unclosed '<!-- verocase {selector} -->' region"
    if case is not None:
        case.error(msg)
    else:
        print(f"verocase: error: {msg}", file=sys.stderr)
    return False


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

<!-- verocase epilogue -->
<!-- end verocase -->

## Notes

Add notes, conclusions, or any content here that should remain in place
regardless of how the LTAC is reorganized.  New element stubs added by
`--fixmissing` are placed before the `epilogue` selector, not after it.
"""

_START_CANDIDATES = (
    'case.ltac', 'docs/case.ltac',
    'case.md', 'case.markdown', 'case.html',
    'docs/case.md', 'docs/case.markdown', 'docs/case.html',
)


_HELP_VALIDATIONS = """\
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

Additional checks when document files are processed:
  - Every declared LTAC element should have a corresponding 'element' selector
    in a document (used to generate the element's heading and cross-references;
    use --fixmissing to add the missing ones)
  - A '<!-- end verocase -->' that appears outside any '<!-- verocase ... -->'
    region is a fatal error (panic): the document is *not* changed.
  - A '<!-- verocase ...' or '<!-- verocase-config ...' directive found inside
    an open '<!-- verocase ... -->' region is a fatal error (panic): directives
    cannot be nested and the document is *not* changed
"""

_HELP_CONFIGURATION = """\
Configuration keys (--config FILE, TOML file; auto-discovered as verocase.toml):
  document_files     list of document file paths to process (default: auto-discover)
  ltac_file          LTAC file path (alternative to --ltac; default: auto-discover)
  max_backups        number of timestamped backup snapshots to keep (default: 20)
  base_url           base URL for hyperlinks in sacm/gsn mermaid output (default: "")
  markdown_base_url  base URL for hyperlinks in ltac/markdown and ltac/html output (default: "")
  default_renderer   renderer for 'sacm'/'gsn' shorthands: "mermaid" (default)
  default_representation  content for 'package' selector: "sacm" (default)
  element_level      heading level (1-6) for 'element' selector (default: 3)
  element_selections comma-separated list for element sub-sections (default: referenced_by,supported_by,supports,ext_ref)
  max_mermaid_children      max visual children before width narrowing (default: 8; 0 disables)
  mermaid_js_url     URL for Mermaid JS script in HTML output (default: CDN URL; "" disables)
  narrowed_mermaid_children children kept (left+right) when narrowing (default: 6; must be >=2 and <max)
  package_level      heading level (1-6) for 'package' selector (default: 3)
  package_selections comma-separated list for package sub-sections (default: representation,pkg_defines,pkg_citing,pkg_cited)
  pkg_label          word used to identify packages in output (default: "Package ")
  warn_dubious_reference  warn when a reference looks like a parenthetical comment (default: true)

Configuration values that can be changed by verocase-config are:
""" + ", ".join(sorted(_ALLOWED_CONFIG_VALUES)) + "\n"

_HELP_API = """\
verocase.py can be imported as a Python module. All top-level code is
constant/regex definitions; there are no file I/O, network calls, or
environment reads at import time. The if __name__ == '__main__': guard
is in place. __all__ declares the intended public surface.

Typical usage (simple):
  import verocase, sys, io

  case = verocase.Case().load()   # auto-discovers config, LTAC, and documents
  if case.had_error:
      sys.exit(1)

  buf = io.StringIO()
  case.render_info('SomeClaim', buf)
  print(buf.getvalue())

  # Render to a stream using self.config automatically:
  import sys
  case.render_selector('element SomeClaim', sys.stdout)

  # Walk the tree to collect (identifier, statement) tuples for definitions
  # (not citations or Links) that are Claims and have no children:
  unsupported = [
      (node.identifier, node.text)
      for node in case._all_nodes()
      if node.is_definition and node.node_type == 'Claim' and not node.children
  ]

Usage for explicit control over loading (ADVANCED):
  import verocase, io, sys

  case = verocase.Case()
  case.load_config('myconfig.toml') # or omit filename to auto-discover
  case.load_ltac_string(open('my.ltac').read()) # parse from string
  case.document_files = ['docs/case.md']

  case.validate_ltac()

  if case.had_error:
      sys.exit(1)

Exceptions:
  class VerocaseError(Exception)  raised by panic() on fatal errors

Data types and examples of their methods/properties:
  @dataclass Node       one node in the LTAC tree. Some operations:
    node.identifier     str: declared identifier, or '' if absent
    node.is_citation    True if introduced with ^ (cross-package citation)
    node.is_definition  True if neither a citation nor a Link (property)
    node.pkg_root       package root Node (property)
    node.subtree_count  total nodes in subtree including self (property)
    node.to_ltac_line(depth_offset=0)  format node as an LTAC source line
  class Case  the full assurance case (LTAC + documents):
    case.document_files List[str] (set by caller after loading)
    case.config         dict (config used to load)
    case.id_info        Dict[str, dict] (per-identifier metadata)
    # Lookups
    case.definition_for(ident) -> Optional[Node]  (None if 0 or >1 declarations)
    case.declaring_package_for(ident) -> Optional[Node]
    case.statement_for(ident) -> Optional[str]
    case.needs_support() -> List[Node]  (nodes with {needssupport} option)
    case.all_nodes()         DFS generator, LTAC order
    case.all_nodes_fast()    DFS generator, fast order (order unspecified)

Standalone helpers:
  print_stats(ltac_stats, doc_stats, out=sys.stdout)

main():
  success: bool = main()   # parses sys.argv, runs full CLI pipeline
  Returns True on clean success, False if errors. Raises VerocaseError
  on fatal errors.

Use --help-api-details to display full docstrings for all public names.
import verocase; help(verocase) will also display those same docstrings.
"""


class _NullWriter:
    """Write sink that discards all output; equivalent to /dev/null for streams."""
    def write(self, s): pass
    def writelines(self, lines): pass
    def flush(self): pass


class _HelpTopicAction(argparse.Action):
    """Custom action for --help-validations / --help-config: record that the flag was given.

    All requested help sections are collected during parsing and printed together
    at the end of parse_args() before exiting, so multiple --help* flags can be
    freely combined.
    """
    def __init__(self, option_strings, dest, **kwargs):
        kwargs.setdefault('default', False)
        kwargs.setdefault('nargs', 0)
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)


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
        add_help=False,
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

A node that is neither a citation (^) nor a Link is called a 'definition'.
Every node is exactly one of: citation, Link, or definition.
Each ID must have exactly one definition; duplicates and omissions are errors.

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
    - Claim ChangeAuth: Changes only permitted if authorized
  - Claim Availability: Availability is maintained

- Claim Design: Security is implemented in design
  - Claim SandS: Saltzer and Schroeder principles met

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
  --read-only (suppresses the default document-update pass; use with --stats
    or any read-only option to avoid triggering document rewrites)
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
  stop                 sentinel: ends the preceding element's full content; prose
                       after this marker is not part of any element and will not
                       be repositioned by --fixmisplaced (no ID)
  epilogue             like stop, but also directs --fixmissing to insert new
                       element stubs before this point rather than at end of
                       file; element selectors must not appear after epilogue (no ID)
Use * to render all packages (package/ltac/sacm/gsn selectors).

Shortcuts for common selectors:
  --info ID          same as --select "info ID"
  --descendants ID   same as --select "ltac/txt ID"

By default a number of validations are run. For example, they ensure
that there are no circularities, that all elements are reachable from the
first node of the first package, that a package must start with
Claim or Justification, and that each identifier must be declared
(no ^ prefix) exactly once.

Run --help-validations for the full list of LTAC and document validations.
Run --help-config for the full list of configuration keys.
Run --help-api for the public Python API summary (for library use).
""",
    )
    parser.add_argument(
        '-h', '--help', action='store_true', default=False, dest='help_main',
        help='show this help message and exit',
    )
    parser.add_argument(
        '--version', action='version', version=__version__,
        help='print version and exit',
    )
    parser.add_argument(
        '--help-validations', action=_HelpTopicAction, default=False, dest='help_validations',
        help='print full list of LTAC and document validations, then exit',
    )
    parser.add_argument(
        '--help-config', action=_HelpTopicAction, default=False, dest='help_config',
        help='print full list of configuration keys, then exit',
    )
    parser.add_argument(
        '--help-api', action=_HelpTopicAction, default=False, dest='help_api',
        help='print public Python API summary for library use, then exit',
    )
    parser.add_argument(
        '--help-api-details', action=_HelpTopicAction, default=False, dest='help_api_details',
        help='print full Python help() output for all public names, then exit',
    )
    parser.add_argument(
        '--config', type=str, metavar='FILE',
        help='path to a TOML config file (default: auto-discover verocase.toml)',
    )
    parser.add_argument(
        '--error', action='store_true',
        help='treat warnings as errors (non-zero exit on any warning)',
    )
    parser.add_argument(
        '--stats', action='store_true', default=False,
        help='print statistics about the LTAC structure and documents; '
             'may be combined with any mode (does not itself modify files; '
             'combine with --read-only if you *only* want to see stats)',
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
        help='[READ-ONLY] list all definition nodes with no children (citations and '
             'Links excluded); leads with the {needssupport} subset',
    )
    parser.add_argument(
        '--packages', action='store_true', default=False,
        help='[READ-ONLY] list each package with element counts and the direct children '
             'of its root',
    )
    parser.add_argument(
        '--read-only', action='store_true', default=False, dest='read_only',
        help='[READ-ONLY] suppress the default document-update pass; load and validate only. '
             'Useful for combining with --stats or analysis options without '
             'triggering document rewrites. '
             'Cannot be combined with any file-modifying mode '
             '(--fixmissing, --fixmisplaced, --start, --update, '
             '--rename, --restate, --detach, --move).',
    )

    args = parser.parse_args()

    # Handle --help / --help-validations / --help-config / --help-api / --help-api-details.
    # All requested sections are printed together so the flags are freely combinable.
    if args.help_main or args.help_validations or args.help_config or args.help_api or args.help_api_details:
        sep = False
        if args.help_main:
            parser.print_help()
            sep = True
        if args.help_validations:
            if sep:
                print()
            print(_HELP_VALIDATIONS, end='')
            sep = True
        if args.help_config:
            if sep:
                print()
            print(_HELP_CONFIGURATION, end='')
            sep = True
        if args.help_api:
            if sep:
                print()
            print(_HELP_API, end='')
            sep = True
        if args.help_api_details:
            if sep:
                print()
            help(sys.modules[__name__])
        sys.exit(0)

    return args



# SACM spec section 11 defines AssertionStatus as a mutually exclusive
# enumeration: Asserted (default), NeedsSupport, Assumed, Axiomatic, Defeated,
# AsCited.  An Assumption node implicitly carries Assumed; a cross-citation
# (^ID) implicitly carries AsCited.


def _is_dubious_reference(ref: str) -> bool:
    """Return True if ref is non-empty, has no '.' anywhere, and doesn't start with '#'.

    Such references are likely to be parenthetical comments accidentally parsed
    as references rather than genuine file paths or URLs.
    """
    return bool(ref) and '.' not in ref and not ref.startswith('#')





def _process_files(
    files: List[str],
    out,
    case: 'Case',
    config: dict,
    strip: bool = False,
    seen_ids: Optional[set] = None,
) -> set:
    """Open each file and call process_document; fall back to stdin if none given."""
    seen = seen_ids if seen_ids is not None else set()
    if files:
        for path in files:
            try:
                with open(path, newline='') as f:
                    seen = case.process_document(f, out, detect_doc_format(path), strip=strip, seen_ids=seen)
            except OSError as e:
                case.error(f"cannot open {path!r}: {e}")
    else:
        seen = case.process_document(sys.stdin, out, 'markdown', strip=strip, seen_ids=seen)
    return seen



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


def _check_element_coverage(registry: Dict[str, Node], seen_element_ids: set,
                            case: 'Case' = None) -> None:
    """Warn about every registry element with no corresponding element selector."""
    for ident in registry:
        if ident not in seen_element_ids:
            msg = f"element {ident!r} has no 'element' selector in any processed file"
            if case is not None:
                case.warn(msg)
            else:
                print(f"verocase: warning: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _has_claim_descendant(node: Node, registry: Dict[str, Node], seen: set) -> bool:
    """Return True if node has any Claim descendant, following citations.

    `seen` tracks visited declaration identifiers to avoid re-traversal
    (circularity has already been checked before stats are computed).
    """
    for child in node.children:
        if child.node_type == 'Claim':
            return True
        if child.is_citation and child.identifier:
            decl = registry.get(child.identifier)
            if decl is not None and child.identifier not in seen:
                seen.add(child.identifier)
                if decl.node_type == 'Claim':
                    return True  # citation IS a Claim; no need to follow further
                if _has_claim_descendant(decl, registry, seen):
                    return True
        elif child.is_definition and _has_claim_descendant(child, registry, seen):
            return True
    return False


def _compute_ltac_stats(case: 'Case') -> dict:
    """Compute and return a statistics dict for the loaded LTAC forest."""
    return case.stats()


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
                if 'verocase' in t and t.lstrip().startswith('<!-- end verocase -->'):
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


def print_stats(ltac_stats: dict, doc_stats: Optional[dict],
                out: TextIO = sys.stdout) -> None:
    """Print a statistics report to out (default stdout)."""
    print('=== verocase statistics ===', file=out)
    print(file=out)
    print('LTAC structure:', file=out)

    # Packages (sizes include links and citations)
    pkgs = ltac_stats['pkg_sizes_sorted']
    num_packages = ltac_stats['num_packages']
    print('- Packages (element numbers include links and citations)', file=out)
    print(f'  - Number of packages: {num_packages}', file=out)
    if pkgs:
        print(f'  - Largest package: {pkgs[0][1]} ({pkgs[0][0]} elements)', file=out)
        if num_packages >= 2:
            print(f'  - Second largest package: {pkgs[1][1]} ({pkgs[1][0]} elements)', file=out)
        if num_packages >= 3:
            print(f'  - Smallest package: {pkgs[-1][1]} ({pkgs[-1][0]} elements)', file=out)
    print(f"  - Average package size: {ltac_stats['avg_per_pkg']:.1f}", file=out)
    print(f"  - Median package size: {ltac_stats['median_per_pkg']:.1f}", file=out)

    # Elements including links and citations
    print('- Elements including links and citations:', file=out)
    print(f"  - Total all elements including links and citations: {ltac_stats['total_full']}", file=out)
    print(f"  - Total Citations: {ltac_stats['total_citations']}", file=out)
    print(f"  - Total Links: {ltac_stats['total_links']}", file=out)

    # Definitions (excluding links and citations)
    print('- Definitions (excluding links and citations):', file=out)
    print(f"  - Total definitions: {ltac_stats['total_definitions']}", file=out)
    def_type_counts = ltac_stats['def_type_counts']
    if def_type_counts:
        print('  - Definitional elements by type:', file=out)
        for node_type, count in sorted(def_type_counts.items()):
            print(f'    - {node_type}: {count}', file=out)
    print(f"  - Total leaf definitions (no children): {ltac_stats['leaf_definitions']}", file=out)
    print(f"  - Total leaf Claim definitions (no children): {ltac_stats['leaf_claims']}", file=out)
    print(f"  - Total bottommost Claim definitions (no Claim descendants): {ltac_stats['bottommost_claims']}", file=out)
    option_counts = ltac_stats['option_counts']
    if option_counts:
        print('  - Definitions with each option:', file=out)
        for opt, count in sorted(option_counts.items()):
            print(f'    - {opt}: {count}', file=out)

    if doc_stats is not None:
        print(file=out)
        print('Documents:', file=out)
        pkg_r = doc_stats['pkg_regions']
        typical = '  (typical)' if pkg_r == 1 else ''
        print(f"  Package regions:         {pkg_r}{typical}", file=out)
        print(f"  Element regions:         {doc_stats['elem_regions']}", file=out)
        if doc_stats['config_stmts']:
            print(f"  Config statements:       {doc_stats['config_stmts']}", file=out)
        print(f"  Elements with no prose:  {doc_stats['empty_elem_regions']}", file=out)


def _write_ltac_node(node: 'Node', out: 'TextIO', first: list) -> None:
    """Write LTAC lines for *node* and all its descendants to *out*."""
    if not first[0]:
        out.write('\n')
    first[0] = False
    out.write(node.to_ltac_line())
    for child in node.children:
        _write_ltac_node(child, out, first)


def _write_ltac(roots: List['Node'], out: 'TextIO') -> None:
    """Serialize a Node forest to LTAC text, writing to out.

    Packages are separated by blank lines; the result ends with a newline.
    To collect the result as a string, pass an io.StringIO() instance.

    >>> import io
    >>> case = Case()
    >>> _LTACParser(case).parse(['- Claim C1: The software is safe',
    ...                         '  - Evidence E1: Test results (tests.pdf)'])
    >>> buf = io.StringIO()
    >>> case.write_ltac(buf)
    >>> buf.getvalue()
    '- Claim C1: The software is safe\\n  - Evidence E1: Test results (tests.pdf)\\n'
    """
    first = [True]
    for i, root in enumerate(roots):
        if i > 0:
            out.write('\n')
            first = [True]
        _write_ltac_node(root, out, first)
    if roots:
        out.write('\n')


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


def _print_analysis_list(header, items, fmt=str) -> None:
    """Print a labelled analysis list, or '(none)' if empty.

    header  -- label printed before the list
    items   -- iterable of items to print
    fmt     -- callable that converts each item to a display string (default: str)
    """
    print(header)
    items = list(items)
    if not items:
        print("  (none)")
    else:
        for item in items:
            print(fmt(item))


def _render_ltac_txt(node_list, config, out: TextIO, sep: str = '') -> bool:
    """Write a list of nodes as raw LTAC text to out, normalizing indentation to depth 0.

    Each node in node_list is treated as a root; its subtree is rendered
    with the node at depth 0 regardless of its actual tree depth.
    Returns False if node_list is empty.
    """
    if not node_list:
        return False
    out.write(sep)
    first = [True]
    for root in node_list:
        _write_ltac_node_normalized(root, out, first, root.depth)
    return True

def _write_ltac_node_normalized(node, out: TextIO, first: list, depth_offset: int) -> None:
    """Write LTAC lines for node and all its descendants to out, normalizing depth."""
    if not first[0]:
        out.write('\n')
    out.write(node.to_ltac_line(depth_offset=depth_offset))
    first[0] = False
    for child in node.children:
        _write_ltac_node_normalized(child, out, first, depth_offset)


# ---------------------------------------------------------------------------
# --fixmisplaced implementation
# ---------------------------------------------------------------------------

def _is_element_region_terminator(line: str) -> bool:
    """Return True if line begins a boundary that ends the current element's full content.

    An element's "full content" runs from its <!-- verocase element ID --> marker
    through <!-- end verocase --> and then continues through any following prose
    and embedded non-element selectors (info, ltac/markdown, etc.) until one of
    these terminators appears:

      - Another element selector:   <!-- verocase element ID -->
      - A stop sentinel:            <!-- verocase stop -->
      - An epilogue sentinel:       <!-- verocase epilogue -->
      - A per-document config line: <!-- verocase-config KEY = VALUE -->

    All other <!-- verocase ... --> selectors (info, package, ltac/markdown, …)
    are considered part of the preceding element's content and are moved along
    with it by --fixmisplaced.

    Why: authors often embed supplemental selectors (e.g. <!-- verocase info X -->
    or <!-- verocase ltac/markdown X -->) immediately after an element's prose.
    Treating them as terminators would silently sever them from the element they
    annotate during --fixmisplaced moves.  The 'stop' and 'epilogue' sentinels
    let authors write stable inter-element or end-of-document sections that
    should never be repositioned.
    """
    if _CASEPROC_CONFIG_RE.match(line):
        return True
    m = _CASEPROC_REGION_RE.match(line)
    if m:
        sel = m.group(1)
        parts = sel.split(None, 1)
        kind = parts[0] if parts else ''
        return (kind == 'element' and len(parts) == 2) or kind in ('stop', 'epilogue')
    return False


def _fixmisplaced_document(path, case, config, doc_format):
    """Move misplaced element regions to their correct LTAC order positions.

    Returns a (tmp_path, final_path) pair, or None if no changes or error.
    """
    try:
        with open(path, newline='') as f:
            original = f.read()
    except OSError as e:
        case.error(f"cannot open {path!r}: {e}")
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

        # While in element prose, check whether this line terminates the region
        # or starts a non-terminating embedded selector to skip over.
        if after_end and current_ident is not None:
            if _is_element_region_terminator(text):
                # Close current element's full region just before this line
                region_map[current_ident] = (region_start, i - 1)
                after_end = False
                current_ident = None
                # If the terminator is 'stop', scan past its <!-- end verocase -->
                # then continue the outer loop (do not fall through to normal handling)
                m2 = _CASEPROC_REGION_RE.match(text)
                if m2 and m2.group(1).split(None, 1)[0] in ('stop', 'epilogue'):
                    i += 1
                    while i < len(lines):
                        t = lines[i].rstrip('\r\n')
                        if 'verocase' in t and t.lstrip().startswith('<!-- end verocase -->'):
                            i += 1
                            break
                        i += 1
                    continue
                # Fall through: handle this line (may start a new element)
            else:
                m = _CASEPROC_REGION_RE.match(text)
                if m:
                    # Non-terminating embedded selector in prose: skip over its region
                    i += 1
                    while i < len(lines):
                        t = lines[i].rstrip('\r\n')
                        if 'verocase' in t and t.lstrip().startswith('<!-- end verocase -->'):
                            i += 1
                            break
                        i += 1
                    continue
                i += 1
                continue

        # Top-level line (not inside element prose)
        m = _CASEPROC_REGION_RE.match(text)
        if m:
            selector = m.group(1)
            parts = selector.split(None, 1)
            kind = parts[0] if parts else ''
            if kind in ('stop', 'epilogue'):
                # Scan past the stop/epilogue region without starting any element
                i += 1
                while i < len(lines):
                    t = lines[i].rstrip('\r\n')
                    if 'verocase' in t and t.lstrip().startswith('<!-- end verocase -->'):
                        i += 1
                        break
                    i += 1
                continue
            if kind == 'element' and len(parts) == 2:
                current_ident = parts[1].strip()
                region_start = i
                region_order.append(current_ident)
            else:
                current_ident = None
            i += 1
            while i < len(lines):
                t = lines[i].rstrip('\r\n')
                if 'verocase' in t and t.lstrip().startswith('<!-- end verocase -->'):
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
    ltac_order = [node.identifier for node in _all_nodes(case.roots)
                  if node.is_definition and node.identifier]
    ltac_pos = {ident: i for i, ident in enumerate(ltac_order)}

    # Find elements that are in both LTAC and document
    doc_with_regions = [ident for ident in region_order if ident in case.registry]

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
                    # Consume trailing prose until the next element/stop/config
                    # terminator.  Non-terminating embedded selectors (info,
                    # ltac/markdown, etc.) are skipped over and treated as part
                    # of this element's full content.
                    while i < len(lines_list):
                        t = lines_list[i].rstrip('\r\n')
                        if _is_element_region_terminator(t):
                            break
                        inner_m = _CASEPROC_REGION_RE.match(t)
                        if inner_m:
                            # Non-terminating selector: skip over its region
                            i += 1
                            while i < len(lines_list):
                                inner = lines_list[i].rstrip('\r\n')
                                if inner.strip() == '<!-- end verocase -->':
                                    i += 1
                                    break
                                i += 1
                            continue
                        if t.strip() == '<!-- end verocase -->':
                            break  # orphan end marker
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


def _update_pkg_id_for_subtree(node: Node, old_pkg_id: str, new_pkg_id: str,
                                id_info: Dict[str, dict]) -> None:
    """Update decl_pkg_id in id_info for node and all its descendants."""
    for n in _all_nodes_fast([node]):
        if n.identifier and n.identifier in id_info:
            info = id_info[n.identifier]
            if info.get('decl_pkg_id') == old_pkg_id:
                info['decl_pkg_id'] = new_pkg_id


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
        print(f"verocase: error: cannot write temp file for {path!r}: {e}", file=sys.stderr)
        return None


def _collect_document_element_ids(path: str) -> set:
    """Fast pre-scan: return the set of element IDs in path's element selector markers."""
    ids = set()
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = _CASEPROC_REGION_RE.match(line.rstrip('\r\n'))
                if m:
                    parts = m.group(1).split(None, 1)
                    if len(parts) == 2 and parts[0] == 'element':
                        ids.add(parts[1])
    except OSError:
        pass
    return ids


# I/O buffer size for reading and writing document files.
# 256 KiB is large enough to hold most documents in a single buffer,
# reducing the number of OS-level read/write calls.
# This only affects inline rewriting (temp file path); --stdout writes
# directly to sys.stdout and is not affected.
_DOC_IO_BUFSIZE = 256 * 1024  # 262144 bytes = 256 KiB


def _inline_rewrite_file(
    path: str,
    case: 'Case',
    config: dict,
    add_missing: bool = False,
    strip: bool = False,
    seen_ids: Optional[set] = None,
) -> Tuple[Optional[Tuple[str, str]], set]:
    """Process a single document file, streaming updated content to a temp file.

    Returns a ``(pair, seen_ids)`` tuple where pair is ``(tmp_path, final_path)``
    or None on error, and seen_ids is the set of element identifiers rendered.

    Streams directly to a temp file (no whole-document buffer).

    When add_missing is True, uses a single-pass smart-placement algorithm to
    insert new element stubs near their natural LTAC order position.
    """
    error_before = case.had_error

    # Detect line endings by scanning only the first chunk (avoids reading all).
    try:
        with open(path, 'rb') as bf:
            first_chunk = bf.read(4096)
    except OSError as e:
        case.error(f"cannot open {path!r}: {e}")
        return None, seen_ids if seen_ids is not None else set()
    line_ending = '\r\n' if b'\r\n' in first_chunk else '\n'
    doc_format = detect_doc_format(path)

    # Pre-scan for existing element IDs used by single-pass smart placement.
    existing_ids = _collect_document_element_ids(path) if add_missing else None

    dir_ = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(dir=dir_)
    except OSError as e:
        case.error(f"cannot create temp file for {path!r}: {e}")
        return None, seen_ids if seen_ids is not None else set()

    try:
        nl = '\r\n' if line_ending == '\r\n' else ''
        with os.fdopen(fd, 'w', encoding='utf-8', newline=nl, buffering=_DOC_IO_BUFSIZE) as out_f:
            with open(path, encoding='utf-8', newline='', buffering=_DOC_IO_BUFSIZE) as src_f:
                seen = case.process_document(src_f, out_f, doc_format,
                                             add_missing=add_missing, strip=strip,
                                             existing_ids=existing_ids, seen_ids=seen_ids)
    except Exception as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        case.error(f"error processing {path!r}: {e}")
        return None, seen_ids if seen_ids is not None else set()
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    if case.had_error and not error_before:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return None, seen_ids if seen_ids is not None else set()

    return (tmp, path), seen


def run_selftests() -> None:
    """Run all doctests embedded in this module and exit.

    Exits with code 0 if every test passes, 1 if any fail.
    Failed tests are shown with ndiff output so differences are easy to spot.
    """
    import doctest
    failures, _ = doctest.testmod(optionflags=doctest.REPORT_NDIFF)
    return failures == 0


def main() -> bool:
    """Entry point: parse arguments, load configuration and LTAC data, then dispatch.

    Returns True on clean success, False if any errors were encountered.
    Raises VerocaseError on fatal errors.
    """
    args = parse_args()

    if args.selftest:
        return run_selftests()

    # --start must fire before _find_ltac_file() because it creates case.ltac.
    # After writing the stubs, execution falls through to the normal LTAC
    # loading below, which will find the newly created case.ltac.
    if args.start:
        _tmp_case = Case()
        _tmp_case._check_no_existing_case_files()
        _tmp_case._write_start_stubs()

    # Load config, discover LTAC, parse LTAC — all via Case().load().
    case = Case().load(
        ltac_file=args.ltac,
        config_file=args.config,
        strict=args.error,
        validate=False,  # validate manually below
    )
    config = case.config
    config_path = case.config_path
    ltac_path = case.ltac_path
    config_invariant_checker(config)

    try:
        with open(ltac_path, newline='') as _f:
            ltac_line_ending = detect_line_ending(_f.read())
    except OSError:
        ltac_line_ending = '\n'

    # LTAC parse complete. Perform validations needing all LTAC data
    case.check_id_info()
    case.check_circularities()
    case.check_reachability()

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

    if args.read_only:
        _file_modifying_modes = ('fixmissing', 'fixmisplaced', 'start')
        if any(getattr(args, f, False) for f in _file_modifying_modes):
            panic("--read-only cannot be combined with file-modifying modes "
                  "(--fixmissing, --fixmisplaced, --start)")
        if args.update:
            panic("--read-only cannot be combined with --update")
        if getattr(args, 'mutations', []):
            panic("--read-only cannot be combined with --rename/--restate/--detach/--move")

    if args.update:
        changed = case.sync_citations()
        if changed:
            buf = io.StringIO()
            case.write_ltac(buf)
            tmp = _make_temp(ltac_path, buf.getvalue(), ltac_line_ending)
            if tmp is None:
                panic("cannot write updated LTAC file")
            commit_updates([(tmp, ltac_path)], ltac_path, config, config_path)

    # Apply ordered mutations (--rename / --restate).
    ltac_pair: Optional[Tuple[str, str]] = None
    if args.mutations:
        for op, a, b in args.mutations:
            if op == 'rename':
                case.rename_id(a, b)
            elif op == 'restate':
                case.restate_id(a, b)
            elif op == 'detach':
                case.detach_id(a)
            elif op == 'move':
                case.move_id(a, b)
        case.check_id_info()
        case.check_circularities()
        case.check_reachability()
        if case.had_error:
            panic("LTAC validation failed after mutations; no files updated")
        buf = io.StringIO()
        case.write_ltac(buf)
        tmp = _make_temp(ltac_path, buf.getvalue())
        if tmp is None:
            panic("cannot write updated LTAC file")
        ltac_pair = (tmp, ltac_path)

    # Resolve document files: CLI args > config > auto-discover.
    document_files = (
        list(args.files) if args.files
        else case._find_document_files(ltac_path)
    )

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
        case.document_files = analysis_doc_files
        if args.missing:
            if not first:
                print()
            _print_analysis_list(
                "Elements missing a selector region in the document(s):",
                case.missing(),
                lambda n: f"{n.node_type} {n.identifier}")
            first = False
        if args.empty:
            if not first:
                print()
            _print_analysis_list(
                "Elements with no prose in the document(s):",
                case.empty(),
                lambda i: f"{case.registry[i].node_type if i in case.registry else '?'} {i}")
            first = False
        if args.orphans:
            if not first:
                print()
            _print_analysis_list(
                "Orphaned selector regions in the document(s) (not in LTAC):",
                case.orphans(),
                lambda i: f"element {i}")
            first = False
        if args.misplaced:
            if not first:
                print()
            misplaced = case.misplaced()
            def _fmt_misplaced(t):
                ntype = case.registry[t[0]].node_type if t[0] in case.registry else '?'
                if t[3]:
                    ptype = case.registry[t[3]].node_type if t[3] in case.registry else '?'
                    return (f"{ntype} {t[0]}: at line {t[1]},"
                            f" expected after {ptype} {t[3]} (line {t[4]})")
                return f"{ntype} {t[0]}: at line {t[1]}, expected at start of document"
            _print_analysis_list(
                "Misplaced elements (document order differs from LTAC order):",
                misplaced, _fmt_misplaced)
            first = False
        if args.leaves:
            if not first:
                print()
            leaves = case.leaves()
            ns_leaves = [n for n in leaves if 'needssupport' in n.options]
            print("Leaf elements:")
            if ns_leaves:
                _print_analysis_list(
                    "Leaves with {needssupport}:", ns_leaves,
                    lambda n: n.to_ltac_line(depth_offset=n.depth))
                print()
            _print_analysis_list(
                "All leaves:", leaves,
                lambda n: n.to_ltac_line(depth_offset=n.depth))
            first = False
        if args.packages:
            if not first:
                print()
            case.render_packages()
            first = False

        return not case.had_error

    if args.info:
        wrote = case.render_selector(f'info {args.info}', sys.stdout,
                                     doc_format='markdown')
        if wrote:
            sys.stdout.write('\n')
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.descendants:
        wrote = case.render_selector(f'ltac/txt {args.descendants}', sys.stdout,
                                     doc_format='markdown')
        if wrote:
            sys.stdout.write('\n')
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.select:
        wrote = case.render_selector(args.select, sys.stdout,
                                     doc_format='markdown')
        if wrote:
            sys.stdout.write('\n')
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.validate:
        if document_files:
            seen_element_ids = _process_files(document_files, _NullWriter(), case, config, strip=args.strip)
            # This validation requires that we read all document files
            _check_element_coverage(case.registry, seen_element_ids, case)
        if ltac_pair:
            commit_updates([ltac_pair], ltac_path, config, config_path)
    elif args.stdout:
        if not document_files:
            panic(_NO_FILES_MSG)
        seen_element_ids = _process_files(document_files, sys.stdout, case, config, strip=args.strip)
        _check_element_coverage(case.registry, seen_element_ids, case)
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
            pair, seen_element_ids = _inline_rewrite_file(path, case, config,
                                                          add_missing=is_last,
                                                          seen_ids=seen_element_ids)
            if pair:
                pairs.append(pair)
        # Mark needsSupport on all leaf elements that lack an assertion status.
        all_ids_ordered = [node.identifier for node in _all_nodes_fast(case.roots)
                           if node.is_definition and node.identifier]
        changed = _mark_needs_support(all_ids_ordered, case.registry)
        if changed:
            buf = io.StringIO()
            case.write_ltac(buf)
            tmp = _make_temp(ltac_path, buf.getvalue(), ltac_line_ending)
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
            pair, seen_element_ids = _inline_rewrite_file(path, case, config,
                                                           add_missing=False,
                                                           seen_ids=seen_element_ids)
            if pair:
                pairs.append(pair)
        # Second pass: fix misplaced regions
        # Need to work on the current file content (updated or original)
        for path in document_files:
            pair = _fixmisplaced_document(path, case, config, detect_doc_format(path))
            if pair:
                pairs.append(pair)
        if ltac_pair:
            pairs.append(ltac_pair)
        if pairs:
            commit_updates(pairs, ltac_path, config, config_path)
    elif args.read_only:
        # --read-only: load, validate, and optionally report stats, but do not
        # rewrite any document files.  Any ltac_pair from mutations is also
        # suppressed (mutations are already blocked above, so ltac_pair is None
        # here; the guard is kept for clarity).
        if document_files:
            seen_element_ids = _process_files(document_files, _NullWriter(), case, config, strip=args.strip)
            _check_element_coverage(case.registry, seen_element_ids, case)
    else:
        # Default mode: rewrite document files in place.
        if not document_files and not ltac_pair:
            panic(_NO_FILES_MSG)
        seen_element_ids: set = set()
        pairs = ([ltac_pair] if ltac_pair else [])
        for path in document_files:
            pair, seen_element_ids = _inline_rewrite_file(path, case, config,
                                                           strip=args.strip,
                                                           seen_ids=seen_element_ids)
            if pair is not None:
                pairs.append(pair)
        if pairs:
            commit_updates(pairs, ltac_path, config, config_path)
        if document_files:
            _check_element_coverage(case.registry, seen_element_ids, case)

    if args.stats:
        ltac_stats = case.stats()
        if document_files:
            doc_totals: dict = {'pkg_regions': 0, 'elem_regions': 0,
                                'config_stmts': 0, 'empty_elem_regions': 0}
            for path in document_files:
                ds = _scan_doc_stats(path)
                for k in doc_totals:
                    doc_totals[k] += ds.get(k, 0)
            print_stats(ltac_stats, doc_totals)
        else:
            print_stats(ltac_stats, None)

    return not case.had_error


if __name__ == '__main__':
    try:
        if not main():
            sys.exit(1)
    except VerocaseError:
        sys.exit(1)
