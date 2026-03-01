"""Test suite for ltacproc.

Run with:
    python tests/run_tests.py
or:
    python -m unittest tests.run_tests
"""

import os
import subprocess
import sys
import unittest

# Locate ltacproc relative to this file so tests work from any directory.
LTACPROC = [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'ltacproc')]
FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def run(*args):
    """Run ltacproc with the given arguments and return the CompletedProcess."""
    return subprocess.run(LTACPROC + list(args), capture_output=True, text=True)


def fixture(name):
    """Return the path to a fixture file."""
    return os.path.join(FIXTURES, name)


def read_fixture(name):
    """Read and return the contents of a fixture file, normalising line endings."""
    with open(fixture(name)) as f:
        return normalise(f.read())


def normalise(s):
    """Normalise line endings to LF so CRLF vs LF differences don't fail tests."""
    return s.replace('\r\n', '\n')


class TestHelp(unittest.TestCase):
    def test_help_exits_zero(self):
        """--help should print usage and exit with code 0."""
        result = run('--help')
        self.assertEqual(result.returncode, 0)


class TestSelectMarkdown(unittest.TestCase):
    def test_full_tree(self):
        """ltac/markdown with no element id renders the full tree."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('simple.ltac.md.expected'))

    def test_subtree_c2(self):
        """ltac/markdown C2 renders only the subtree rooted at C2."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown C2')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('simple-c2.md.expected'))

    def test_all_packages(self):
        """ltac/markdown * renders all packages with ## Package headers."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown *')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('simple-star.md.expected'))


if __name__ == '__main__':
    unittest.main()
