#!/usr/bin/env python3
"""Convert all fixture files to LF line endings.

Run after generating new expected-output fixtures to ensure they are
stored with LF endings regardless of the platform used to create them.
This keeps `git diff` output clean when fixtures are committed from
Windows or macOS machines.

Usage:
    python tests/normalise_fixtures.py
"""

import os

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def normalise_file(path):
    """Replace CRLF with LF in-place.  Returns True if the file was changed."""
    with open(path, 'rb') as f:
        original = f.read()
    normalised = original.replace(b'\r\n', b'\n')
    if normalised == original:
        return False
    with open(path, 'wb') as f:
        f.write(normalised)
    return True


if __name__ == '__main__':
    changed = []
    for name in sorted(os.listdir(FIXTURES)):
        path = os.path.join(FIXTURES, name)
        if os.path.isfile(path) and normalise_file(path):
            changed.append(name)
    if changed:
        for name in changed:
            print(f'normalised: {name}')
        print(f'{len(changed)} file(s) updated to LF line endings.')
    else:
        print('All fixture files already use LF line endings.')
