#!/usr/bin/env python3

"""Test suite for ltacproc.

Run with:
    python3 tests/run_tests.py
or:
    python3 -m unittest tests.run_tests
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# Locate ltacproc relative to this file so tests work from any directory.
LTACPROC = [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'ltacproc')]
FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def run(*args):
    """Run ltacproc with the given arguments and return the CompletedProcess."""
    return subprocess.run(
        LTACPROC + list(args), capture_output=True, text=True, encoding='utf-8'
    )


def fixture(name):
    """Return the path to a fixture file."""
    return os.path.join(FIXTURES, name)


def read_fixture(name):
    """Read and return the contents of a fixture file, normalising line endings.

    Opens with newline='' so Python's own CRLF translation is disabled;
    normalise() is the single place that converts any line ending to LF.
    """
    with open(fixture(name), encoding='utf-8', newline='') as f:
        return normalise(f.read())


def read_file(path):
    """Read an arbitrary file and return its contents with normalised line endings."""
    with open(path, encoding='utf-8', newline='') as f:
        return normalise(f.read())


def normalise(s):
    """Normalise line endings to LF so CRLF vs LF differences don't fail tests."""
    return s.replace('\r\n', '\n')


class TestHelp(unittest.TestCase):
    def test_help_exits_zero(self):
        """--help should print usage and exit with code 0."""
        result = run('--help')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '')

    def test_selftests_pass(self):
        """All built-in doctests pass."""
        result = run('--selftest')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')


class TestSelectMarkdown(unittest.TestCase):
    def test_full_tree(self):
        """ltac/markdown with no element id renders the full tree."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('simple.ltac.md.expected'))
        self.assertEqual(result.stderr, '')

    def test_subtree_c2(self):
        """ltac/markdown C2 renders only the subtree rooted at C2."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown C2')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('simple-c2.md.expected'))
        self.assertEqual(result.stderr, '')

    def test_all_packages(self):
        """ltac/markdown * renders all packages with ## Package headers."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown *')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('simple-star.md.expected'))
        self.assertEqual(result.stderr, '')


class TestDefaultMode(unittest.TestCase):
    def test_filter_mode_output(self):
        """Default mode replaces stale ltac regions and passes other lines through."""
        result = run('--ltac', fixture('simple.ltac'), fixture('doc-simple.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('doc-simple.md.expected'))
        self.assertEqual(normalise(result.stderr), read_fixture('doc-simple.md.stderr'))

    def test_validate_exits_zero_no_stdout(self):
        """--validate produces no stdout and exits 0 for a well-formed document."""
        result = run('--ltac', fixture('simple.ltac'), '--validate', fixture('doc-simple.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')

    def test_structural_warning_with_error_flag(self):
        """A structurally invalid LTAC file (Claim under Evidence) exits non-zero with --error."""
        result = run('--ltac', fixture('warn.ltac'), '--select', 'ltac/markdown', '--error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('should not be a child of', result.stderr)

    def test_header_coverage_warning(self):
        """Elements without a matching Markdown header produce warnings; --error makes exit non-zero."""
        result = run('--ltac', fixture('simple.ltac'), fixture('doc-simple.md'), '--error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no corresponding header', result.stderr)

    def test_conflicting_assertion_status_is_error(self):
        """A node with two SACM assertion statuses is always an error (no --error flag needed)."""
        result = run('--ltac', fixture('conflict.ltac'), '--select', 'ltac/markdown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('conflicting assertion status', result.stderr)
        self.assertIn('C1', result.stderr)
        self.assertNotIn('C2', result.stderr)


class TestSelectSacm(unittest.TestCase):
    def test_select_sacm_mermaid(self):
        """sacm/mermaid renders the full SACM mermaid diagram for simple.ltac."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'sacm/mermaid')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('simple.sacm.mermaid.expected'))
        self.assertEqual(result.stderr, '')

    def test_badgeapp_top_sacm_mermaid(self):
        """sacm/mermaid renders the badgeapp top-level assurance case correctly."""
        result = run('--ltac', fixture('badgeapp-top.ltac'), '--select', 'sacm/mermaid')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('badgeapp-top.sacm.mermaid.expected'))
        self.assertEqual(normalise(result.stderr), read_fixture('badgeapp-top.sacm.mermaid.stderr'))

    def test_filter_mode_with_sacm_region(self):
        """Default mode correctly replaces a sacm/mermaid region in doc-simple.md."""
        result = run('--ltac', fixture('simple.ltac'), fixture('doc-simple.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(normalise(result.stdout), read_fixture('doc-simple.md.expected'))
        self.assertEqual(normalise(result.stderr), read_fixture('doc-simple.md.stderr'))


class TestInlineMode(unittest.TestCase):
    def _tmp_copy(self, name):
        """Copy a fixture to a fresh temp file and return its path."""
        fd, path = tempfile.mkstemp(suffix='.md')
        os.close(fd)
        shutil.copy(fixture(name), path)
        return path

    def test_inline_updates_file(self):
        """--inline rewrites a file with stale regions to the correct content."""
        tmp = self._tmp_copy('inline-input.md')
        try:
            result = run('--ltac', fixture('simple.ltac'), '--inline', tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(normalise(result.stderr), read_fixture('inline-expected.stderr'))
            self.assertEqual(read_file(tmp), read_fixture('inline-expected.md'))
        finally:
            os.unlink(tmp)

    def test_inline_idempotent(self):
        """Running --inline twice produces the same result; second run makes no changes."""
        tmp = self._tmp_copy('inline-input.md')
        try:
            run('--ltac', fixture('simple.ltac'), '--inline', tmp)
            mtime_after_first = os.path.getmtime(tmp)
            result = run('--ltac', fixture('simple.ltac'), '--inline', tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(normalise(result.stderr), read_fixture('inline-expected.stderr'))
            self.assertEqual(os.path.getmtime(tmp), mtime_after_first)
            self.assertEqual(read_file(tmp), read_fixture('inline-expected.md'))
        finally:
            os.unlink(tmp)

    def test_inline_error_leaves_file_unchanged(self):
        """--inline on a file with a parse error leaves the file unchanged."""
        tmp = self._tmp_copy('inline-error-input.md')
        try:
            original = read_fixture('inline-error-input.md')
            result = run('--ltac', fixture('simple.ltac'), '--inline', tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertIn('unclosed', result.stderr)
            self.assertEqual(read_file(tmp), original)
        finally:
            os.unlink(tmp)


if __name__ == '__main__':
    unittest.main()
