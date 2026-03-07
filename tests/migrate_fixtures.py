#!/usr/bin/env python3
"""Migrate LTAC fixture documents from header-based format to element/package selectors.

Usage:
    python3 tests/migrate_fixtures.py FILE...

Transforms each FILE in-place:
- Removes stale <a id="TYPE-id..."></a> anchor lines.
- Replaces LTAC-shaped markdown headers with element/package selector regions.
  '# Package ID'       -> <!-- caseproc package ID -->\\n<!-- end caseproc -->
  '## Claim ID: text'  -> <!-- caseproc element ID -->\\n<!-- end caseproc -->
- Adds explicit element IDs to <!-- caseproc SELECTOR --> regions that have no
  ID, using the ID from the most recently seen LTAC header.
"""

import re
import sys

# Matches any markdown header line.
_HEADER_RE = re.compile(r'^(#+) (.+)')

# Parses 'TYPE ID' or 'TYPE ID: statement' from a header string.
_HEADER_TEXT_RE = re.compile(r'^(\S+)\s+([^:\s]+)(?::\s*(.+))?$')

_ELEMENT_TYPE_NAMES = frozenset({
    'Claim', 'Strategy', 'Evidence',
    'Justification', 'Context', 'Assumption',
})

# Stale anchor pattern (produced by old header scanning).
_ANCHOR_RE = re.compile(
    r'^<a\s+id="(?:claim|strategy|evidence|justification|context|assumption|package)-[^"]*"'
    r'\s*></a>\s*$',
    re.IGNORECASE,
)

# Matches a caseproc region start with no element ID (selector only, no ID).
_REGION_NO_ID_RE = re.compile(
    r'^<!--\s*caseproc\s+(statement|references|info|sacm/mermaid|gsn/mermaid'
    r'|ltac/markdown|ltac/html)\s*-->\s*$'
)

# Selectors that benefit from an explicit ID when current_element is set.
_ID_SELECTORS = frozenset({
    'statement', 'references', 'info',
    'sacm/mermaid', 'gsn/mermaid', 'ltac/markdown', 'ltac/html',
})


def migrate(text: str) -> str:
    """Transform *text* and return the migrated content."""
    lines = text.splitlines(keepends=True)
    out = []
    current_id = None  # most recently seen LTAC element ID

    for line in lines:
        stripped = line.rstrip('\r\n')

        # Remove stale anchor lines.
        if _ANCHOR_RE.match(stripped):
            continue

        # Check for a markdown header.
        hm = _HEADER_RE.match(stripped)
        if hm:
            header_text = hm.group(2).strip()
            pm = _HEADER_TEXT_RE.match(header_text)
            if pm:
                type_str = pm.group(1)
                ident = pm.group(2)
                if type_str == 'Package':
                    current_id = ident
                    out.append(f'<!-- caseproc package {ident} -->\n')
                    out.append('<!-- end caseproc -->\n')
                    continue
                elif type_str in _ELEMENT_TYPE_NAMES:
                    current_id = ident
                    out.append(f'<!-- caseproc element {ident} -->\n')
                    out.append('<!-- end caseproc -->\n')
                    continue

        # Add explicit ID to selectors that are missing one, if we know the current element.
        if current_id is not None:
            rm = _REGION_NO_ID_RE.match(stripped)
            if rm:
                selector = rm.group(1)
                out.append(f'<!-- caseproc {selector} {current_id} -->\n')
                continue

        out.append(line)

    return ''.join(out)


def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} FILE...', file=sys.stderr)
        sys.exit(1)

    for path in sys.argv[1:]:
        with open(path, encoding='utf-8', newline='') as f:
            original = f.read()
        migrated = migrate(original)
        if migrated != original:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(migrated)
            print(f'Migrated: {path}')
        else:
            print(f'No change: {path}')


if __name__ == '__main__':
    main()
