#!/usr/bin/env python3

"""Test suite for caseproc.

Run with:
    python3 tests/run_tests.py
or:
    python3 -m unittest tests.run_tests

When a test result differs from the expected fixture it is saved to
tests/results/ with the same filename as the fixture.  Results that
match are removed from that directory so only failures accumulate.
Run the top-level `accept` script to promote all saved results to
their corresponding fixtures.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# Locate caseproc relative to this file so tests work from any directory.
# Use abspath to normalise away any leading ./ that Python adds to __file__
# when the script is invoked as ./run_tests.py from the tests/ directory.
_HERE    = os.path.dirname(os.path.abspath(__file__))
LTACPROC = [sys.executable, os.path.join(_HERE, '..', 'caseproc')]
FIXTURES = os.path.join(_HERE, 'fixtures')
RESULTS  = os.path.join(_HERE, 'results')


def run(*args):
    """Run caseproc with the given arguments and return the CompletedProcess."""
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


def check(actual, fixture_name):
    """Normalise *actual*, write it to results/, then remove if it matches.

    Always writes the result to disk first so a crash mid-suite leaves the
    actual output on disk for inspection.  Removes the file afterwards if it
    matches the fixture so results/ stays clean.  Returns the normalised
    actual string so callers can still pass it to assertEqual for a readable
    failure message.
    """
    actual_n = normalise(actual)
    expected = read_fixture(fixture_name)
    result_path = os.path.join(RESULTS, fixture_name)
    os.makedirs(RESULTS, exist_ok=True)
    with open(result_path, 'w', encoding='utf-8', newline='') as f:
        f.write(actual_n)
    if actual_n == expected:
        os.unlink(result_path)
    return actual_n


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
        self.assertEqual(check(result.stdout, 'simple.ltac.expected.md'),
                         read_fixture('simple.ltac.expected.md'))
        self.assertEqual(result.stderr, '')

    def test_subtree_c2(self):
        """ltac/markdown C2 renders only the subtree rooted at C2."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown C2')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'simple-c2.expected.md'),
                         read_fixture('simple-c2.expected.md'))
        self.assertEqual(result.stderr, '')

    def test_all_packages(self):
        """ltac/markdown * renders all packages with ### Package headers."""
        result = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown *')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'simple-star.expected.md'),
                         read_fixture('simple-star.expected.md'))
        self.assertEqual(result.stderr, '')


class TestDefaultMode(unittest.TestCase):
    def test_filter_mode_output(self):
        """Default mode replaces stale ltac regions and passes other lines through."""
        result = run('--ltac', fixture('simple.ltac'), fixture('doc-simple.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'doc-simple.expected.md'),
                         read_fixture('doc-simple.expected.md'))
        self.assertEqual(check(result.stderr, 'doc-simple.stderr.txt'),
                         read_fixture('doc-simple.stderr.txt'))

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
        self.assertEqual(check(result.stdout, 'simple.sacm.mermaid.expected.md'),
                         read_fixture('simple.sacm.mermaid.expected.md'))
        self.assertEqual(result.stderr, '')

    def test_badgeapp_top_sacm_mermaid(self):
        """sacm/mermaid renders the badgeapp top-level assurance case correctly."""
        result = run('--ltac', fixture('badgeapp-top.ltac'), '--select', 'sacm/mermaid')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'badgeapp-top.sacm.mermaid.expected.md'),
                         read_fixture('badgeapp-top.sacm.mermaid.expected.md'))
        self.assertEqual(check(result.stderr, 'badgeapp-top.sacm.mermaid.stderr.txt'),
                         read_fixture('badgeapp-top.sacm.mermaid.stderr.txt'))

    def test_filter_mode_with_sacm_region(self):
        """Default mode correctly replaces a sacm/mermaid region in doc-simple.md."""
        result = run('--ltac', fixture('simple.ltac'), fixture('doc-simple.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'doc-simple.expected.md'),
                         read_fixture('doc-simple.expected.md'))
        self.assertEqual(check(result.stderr, 'doc-simple.stderr.txt'),
                         read_fixture('doc-simple.stderr.txt'))


class TestSelectGsn(unittest.TestCase):
    def test_select_gsn_mermaid(self):
        r = run('--ltac', fixture('simple.ltac'), '--select', 'gsn/mermaid')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'simple.gsn.mermaid.expected.md')
        self.assertEqual(actual, read_fixture('simple.gsn.mermaid.expected.md'))


class TestBadgeappDoc(unittest.TestCase):
    def test_badgeapp_doc_filter_mode(self):
        """Filter mode renders all three packages via sacm/mermaid * with correct
        BottomPadding targets, click lines for evidence URLs, and context edges."""
        result = run('--ltac', fixture('badgeapp-doc.ltac'), fixture('badgeapp-doc-input.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'badgeapp-doc-input.expected.md'),
                         read_fixture('badgeapp-doc-input.expected.md'))
        self.assertEqual(check(result.stderr, 'badgeapp-doc-input.stderr.txt'),
                         read_fixture('badgeapp-doc-input.stderr.txt'))


class TestConfig(unittest.TestCase):
    def test_config_file_overrides_default(self):
        """--config FILE merges JSON object keys over defaults."""
        cfg = {'pkg_label': 'Module '}
        fd, path = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                import json
                json.dump(cfg, f)
            result = run('--ltac', fixture('simple.ltac'), '--config', path,
                         '--select', 'ltac/markdown *')
            self.assertEqual(result.returncode, 0)
            self.assertIn('Module ', result.stdout)
        finally:
            os.unlink(path)

    def test_config_file_not_found(self):
        """--config with a nonexistent file exits non-zero with an error message."""
        result = run('--ltac', fixture('simple.ltac'), '--config', '/no/such/file.json',
                     '--select', 'ltac/markdown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not found', result.stderr)

    def test_config_file_not_json_object(self):
        """--config file containing a JSON array (not object) exits non-zero."""
        fd, path = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write('[1, 2, 3]')
            result = run('--ltac', fixture('simple.ltac'), '--config', path,
                         '--select', 'ltac/markdown')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('JSON object', result.stderr)
        finally:
            os.unlink(path)

    def test_config_file_invalid_json(self):
        """--config file with invalid JSON exits non-zero."""
        fd, path = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write('{not valid json}')
            result = run('--ltac', fixture('simple.ltac'), '--config', path,
                         '--select', 'ltac/markdown')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid JSON', result.stderr)
        finally:
            os.unlink(path)

    def test_config_unknown_key_warns(self):
        """--config file with an unknown key produces a warning but still exits 0."""
        fd, path = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                import json
                json.dump({'no_such_key': 'value'}, f)
            result = run('--ltac', fixture('simple.ltac'), '--config', path,
                         '--select', 'ltac/markdown')
            self.assertEqual(result.returncode, 0)
            self.assertIn('unknown config key', result.stderr)
        finally:
            os.unlink(path)


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
            self.assertEqual(check(result.stderr, 'inline-expected.stderr.txt'),
                             read_fixture('inline-expected.stderr.txt'))
            self.assertEqual(check(read_file(tmp), 'inline-expected.md'),
                             read_fixture('inline-expected.md'))
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
            self.assertEqual(check(result.stderr, 'inline-expected.stderr.txt'),
                             read_fixture('inline-expected.stderr.txt'))
            self.assertEqual(os.path.getmtime(tmp), mtime_after_first)
            self.assertEqual(check(read_file(tmp), 'inline-expected.md'),
                             read_fixture('inline-expected.md'))
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


class TestUpdate(unittest.TestCase):
    def test_update_header_statement(self):
        """--update rewrites a stale header statement to match the LTAC."""
        r = run('--ltac', fixture('simple.ltac'), '--update',
                fixture('update-input.md'))
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'update-expected.md')
        self.assertEqual(actual, read_fixture('update-expected.md'))
        self.assertIn('updated Claim C1:', r.stderr)
        self.assertIn('Wrong statement here', r.stderr)
        self.assertIn('acceptably safe', r.stderr)

    def test_no_update_without_flag(self):
        """Without --update, a stale header still produces a warning, not a rewrite."""
        r = run('--ltac', fixture('simple.ltac'), fixture('update-input.md'))
        self.assertEqual(r.returncode, 0)
        self.assertIn('differs from LTAC', r.stderr)
        self.assertIn('Wrong statement here', r.stdout)


if __name__ == '__main__':
    unittest.main()
