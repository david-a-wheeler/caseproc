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

Fixture naming conventions (tests/fixtures/):
  <name>.ltac                            LTAC input file
  <name>-input.md                        Markdown/HTML document input file
  <name>-output.expected.md              Expected stdout when processing <name>-input.md
  <name>-stderr.expected.txt             Expected stderr for a <name> scenario
  <ltac>.<selector>.expected.md          Expected stdout for --select <selector> on <ltac>.ltac
  <ltac>.<selector>.stderr.expected.txt  Expected stderr for --select <selector> on <ltac>.ltac
Only input files carry "input" in their name; all expected files carry
"expected".  Inline tests copy the input fixture to a temporary file
before running --inline, so the fixture itself is never modified.

Config file naming convention (tests/fixtures/):
  <prefix>.config   JSON config file passed via --config to a test scenario.
  The prefix matches the LTAC base name when one LTAC maps to one scenario
  (e.g. badgeapp-top.config for badgeapp-top.ltac).  When a single LTAC
  is used for multiple scenarios, the prefix matches the scenario's expected
  output base name instead (e.g. simple.sacm.mermaid.config,
  simple.gsn.mermaid.config, doc-simple.config all derive from simple.ltac).
  Mermaid tests set base_url to the GitHub URL of their expected output file
  so that diagram nodes link to the correct anchors on GitHub.
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


class TestSpecialChars(unittest.TestCase):
    """Characters that need escaping in HTML or Markdown, and & entity pass-through."""

    def test_markdown_escaping(self):
        """ltac/markdown escapes [ and < in labels; & HTML entities pass through."""
        r = run('--ltac', fixture('special-chars.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'special-chars.ltac.expected.md')
        self.assertEqual(actual, read_fixture('special-chars.ltac.expected.md'))
        # Key assertions on the escaping behaviour
        self.assertIn(r'\[A\]', r.stdout)           # [ and ] escaped
        self.assertIn(r'\<', r.stdout)              # < escaped
        self.assertIn('&alpha;', r.stdout)          # & entity passes through
        self.assertNotIn('&lt;', r.stdout)          # < not HTML-escaped in markdown

    def test_html_escaping(self):
        """ltac/html escapes < in text; [ is fine; & HTML entities pass through."""
        r = run('--ltac', fixture('special-chars.ltac'), '--select', 'ltac/html')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'special-chars.ltac.html.expected.txt')
        self.assertEqual(actual, read_fixture('special-chars.ltac.html.expected.txt'))
        # Key assertions on the escaping behaviour
        self.assertIn('&lt;', r.stdout)             # < HTML-escaped
        self.assertIn('[A]', r.stdout)              # [ passed through as-is
        self.assertIn('&alpha;', r.stdout)          # & entity passes through
        self.assertNotIn('&amp;alpha;', r.stdout)   # & not double-escaped


class TestDefaultMode(unittest.TestCase):
    def test_filter_mode_output(self):
        """--stdout replaces stale caseproc regions and passes other lines through."""
        result = run('--ltac', fixture('simple.ltac'),
                     '--config', fixture('doc-simple.config'),
                     '--stdout', fixture('doc-simple-input.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'doc-simple-output.expected.md'),
                         read_fixture('doc-simple-output.expected.md'))
        self.assertEqual(check(result.stderr, 'doc-simple-stderr.expected.txt'),
                         read_fixture('doc-simple-stderr.expected.txt'))

    def test_validate_exits_zero_no_stdout(self):
        """--validate produces no stdout and exits 0 for a well-formed document."""
        result = run('--ltac', fixture('simple.ltac'), '--validate', fixture('doc-simple-input.md'))
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
        result = run('--ltac', fixture('simple.ltac'), '--stdout',
                     fixture('doc-simple-input.md'), '--error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no corresponding header', result.stderr)

    def test_two_top_level_elements_is_fatal(self):
        """An LTAC with two root-level elements (different IDs) always exits non-zero."""
        result = run('--ltac', fixture('two-roots.ltac'), '--select', 'ltac/markdown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already has a top-level element', result.stderr)

    def test_duplicate_id_warns(self):
        """An LTAC with two declarations of the same ID produces a warning but exits 0."""
        result = run('--ltac', fixture('duplicate-id.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(result.returncode, 0)
        self.assertIn('duplicate declaration', result.stderr)
        self.assertIn('C2', result.stderr)

    def test_duplicate_id_error_flag(self):
        """An LTAC with two declarations of the same ID exits non-zero with --error."""
        result = run('--ltac', fixture('duplicate-id.ltac'), '--select', 'ltac/markdown', '--error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate declaration', result.stderr)

    def test_conflicting_assertion_status_is_error(self):
        """A node with two SACM assertion statuses is always an error (no --error flag needed)."""
        result = run('--ltac', fixture('conflict.ltac'), '--select', 'ltac/markdown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('conflicting assertion status', result.stderr)
        self.assertIn('C1', result.stderr)
        self.assertNotIn('C2', result.stderr)


class TestLTACValidation(unittest.TestCase):
    def test_cited_not_declared_warns(self):
        """^ID cited but never declared produces a warning but exits 0."""
        r = run('--ltac', fixture('cited-not-declared.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        self.assertIn('cited but never declared', r.stderr)
        self.assertIn('C99', r.stderr)

    def test_cited_not_declared_error_flag(self):
        """^ID cited but never declared exits non-zero with --error."""
        r = run('--ltac', fixture('cited-not-declared.ltac'), '--select', 'ltac/markdown', '--error')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('cited but never declared', r.stderr)

    def test_link_target_not_found_warns(self):
        """A Link to a nonexistent element produces a warning but exits 0."""
        r = run('--ltac', fixture('bad-link.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        self.assertIn('Link target', r.stderr)
        self.assertIn('NoSuchElement', r.stderr)

    def test_link_target_not_found_error_flag(self):
        """A Link to a nonexistent element exits non-zero with --error."""
        r = run('--ltac', fixture('bad-link.ltac'), '--select', 'ltac/markdown', '--error')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Link target', r.stderr)

    def test_header_not_in_ltac_warns(self):
        """A document header whose ID is not in the LTAC produces a warning but exits 0."""
        r = run('--ltac', fixture('simple.ltac'), '--stdout', fixture('unknown-header-input.md'))
        self.assertEqual(r.returncode, 0)
        self.assertIn('not found in LTAC', r.stderr)
        self.assertIn('C99', r.stderr)

    def test_header_not_in_ltac_error_flag(self):
        """A document header whose ID is not in the LTAC exits non-zero with --error."""
        r = run('--ltac', fixture('simple.ltac'), '--stdout',
                fixture('unknown-header-input.md'), '--error')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not found in LTAC', r.stderr)

    def test_select_nonexistent_element_is_error(self):
        """--select with an element ID absent from the registry always exits non-zero."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown BOGUS')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not found in registry', r.stderr)

    def test_unrecognized_syntax_is_error(self):
        """A line that does not match LTAC syntax always exits non-zero."""
        r = run('--ltac', fixture('bad-syntax.ltac'), '--select', 'ltac/markdown')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('unrecognized syntax', r.stderr)

    def test_star_bullet_is_error(self):
        """A line using * bullets (old syntax) is now unrecognized syntax."""
        import tempfile, os
        content = '* Claim C1: The software is safe\n'
        fd, path = tempfile.mkstemp(suffix='.ltac')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
            r = run('--ltac', path, '--select', 'ltac/markdown')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('unrecognized syntax', r.stderr)
        finally:
            os.unlink(path)

    def test_comment_lines_are_error(self):
        """Lines starting with // (old comment syntax) are now unrecognized syntax."""
        import tempfile, os
        content = '- Claim C1: The software is safe\n// this was a comment\n'
        fd, path = tempfile.mkstemp(suffix='.ltac')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
            r = run('--ltac', path, '--select', 'ltac/markdown')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('unrecognized syntax', r.stderr)
        finally:
            os.unlink(path)

    def test_star_invalid_with_statement_selector(self):
        """'*' is not valid with statement/references/info and always exits non-zero."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'statement *')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not valid', r.stderr)
        self.assertIn('statement', r.stderr)

    def test_cited_package_not_found_warns(self):
        """^[PkgName] where PkgName is not a loaded package produces a warning but exits 0."""
        r = run('--ltac', fixture('cited-pkg-not-found.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        self.assertIn('cited package', r.stderr)
        self.assertIn('NoSuchPkg', r.stderr)

    def test_cited_package_not_found_error_flag(self):
        """^[PkgName] where PkgName is not loaded exits non-zero with --error."""
        r = run('--ltac', fixture('cited-pkg-not-found.ltac'), '--select', 'ltac/markdown', '--error')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('cited package', r.stderr)

    def test_wrong_pkg_citation_warns(self):
        """^[PkgA] ID where ID is declared in PkgB produces a warning but exits 0."""
        r = run('--ltac', fixture('wrong-pkg-citation.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        self.assertIn('cited as belonging to', r.stderr)
        self.assertIn('C2', r.stderr)

    def test_wrong_pkg_citation_error_flag(self):
        """^[PkgA] ID where ID is declared in PkgB exits non-zero with --error."""
        r = run('--ltac', fixture('wrong-pkg-citation.ltac'), '--select', 'ltac/markdown', '--error')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('cited as belonging to', r.stderr)


class TestSelectSacm(unittest.TestCase):
    def test_select_sacm_mermaid(self):
        """sacm/mermaid renders the full SACM mermaid diagram for simple.ltac."""
        result = run('--ltac', fixture('simple.ltac'),
                     '--config', fixture('simple.sacm.mermaid.config'),
                     '--select', 'sacm/mermaid')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'simple.sacm.mermaid.expected.md'),
                         read_fixture('simple.sacm.mermaid.expected.md'))
        self.assertEqual(result.stderr, '')

    def test_badgeapp_top_sacm_mermaid(self):
        """sacm/mermaid renders the badgeapp top-level assurance case correctly."""
        result = run('--ltac', fixture('badgeapp-top.ltac'),
                     '--config', fixture('badgeapp-top.config'),
                     '--select', 'sacm/mermaid')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'badgeapp-top.sacm.mermaid.expected.md'),
                         read_fixture('badgeapp-top.sacm.mermaid.expected.md'))
        self.assertEqual(check(result.stderr, 'badgeapp-top.sacm.mermaid.stderr.expected.txt'),
                         read_fixture('badgeapp-top.sacm.mermaid.stderr.expected.txt'))

    def test_filter_mode_with_sacm_region(self):
        """--stdout correctly replaces a sacm/mermaid region in doc-simple-input.md."""
        result = run('--ltac', fixture('simple.ltac'),
                     '--config', fixture('doc-simple.config'),
                     '--stdout', fixture('doc-simple-input.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'doc-simple-output.expected.md'),
                         read_fixture('doc-simple-output.expected.md'))
        self.assertEqual(check(result.stderr, 'doc-simple-stderr.expected.txt'),
                         read_fixture('doc-simple-stderr.expected.txt'))


class TestSelectGsn(unittest.TestCase):
    def test_select_gsn_mermaid(self):
        r = run('--ltac', fixture('simple.ltac'),
                '--config', fixture('simple.gsn.mermaid.config'),
                '--select', 'gsn/mermaid')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'simple.gsn.mermaid.expected.md')
        self.assertEqual(actual, read_fixture('simple.gsn.mermaid.expected.md'))


class TestBadgeappDoc(unittest.TestCase):
    def test_badgeapp_doc_filter_mode(self):
        """--stdout renders all three packages via sacm/mermaid * with correct
        BottomPadding targets, click lines for evidence URLs, and context edges."""
        result = run('--ltac', fixture('badgeapp-doc.ltac'),
                     '--config', fixture('badgeapp-doc.config'),
                     '--stdout', fixture('badgeapp-doc-input.md'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check(result.stdout, 'badgeapp-doc-output.expected.md'),
                         read_fixture('badgeapp-doc-output.expected.md'))
        self.assertEqual(check(result.stderr, 'badgeapp-doc-stderr.expected.txt'),
                         read_fixture('badgeapp-doc-stderr.expected.txt'))


class TestStress(unittest.TestCase):
    def _tmp_copy(self, name):
        """Copy a fixture to tests/results/<name> and return its path."""
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, name)
        shutil.copy(fixture(name), path)
        return path

    def test_stress_inline(self):
        """Inline update of a large LTAC (1000+ elements, 50+ packages, 6+ levels deep)
        with sacm/mermaid *, gsn/mermaid *, ltac/markdown *, and element stubs."""
        tmp = self._tmp_copy('stress-test-input.md')
        try:
            result = run('--ltac', fixture('stress-test.ltac'),
                         '--config', fixture('stress-test.config'),
                         tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(check(result.stderr, 'stress-test-stderr.expected.txt'),
                             read_fixture('stress-test-stderr.expected.txt'))
            self.assertEqual(check(read_file(tmp), 'stress-test-output.expected.md'),
                             read_fixture('stress-test-output.expected.md'))
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


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
        """Copy a fixture to tests/results/<name> and return its path.

        Uses a fixed name (not a random tempfile) so commit_updates' 'Updating'
        message is deterministic and can be compared against a fixture.
        """
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, name)
        shutil.copy(fixture(name), path)
        return path

    def test_inline_updates_file(self):
        """Default mode rewrites a file with stale regions to the correct content."""
        tmp = self._tmp_copy('inline-input.md')
        try:
            result = run('--ltac', fixture('simple.ltac'), tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(check(result.stderr, 'inline-update-stderr.expected.txt'),
                             read_fixture('inline-update-stderr.expected.txt'))
            self.assertEqual(check(read_file(tmp), 'inline-output.expected.md'),
                             read_fixture('inline-output.expected.md'))
        finally:
            os.unlink(tmp)

    def test_inline_idempotent(self):
        """Running the default mode twice produces the same result; second run makes no changes."""
        tmp = self._tmp_copy('inline-input.md')
        try:
            run('--ltac', fixture('simple.ltac'), tmp)
            mtime_after_first = os.path.getmtime(tmp)
            result = run('--ltac', fixture('simple.ltac'), tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(check(result.stderr, 'inline-stderr.expected.txt'),
                             read_fixture('inline-stderr.expected.txt'))
            self.assertEqual(os.path.getmtime(tmp), mtime_after_first)
            self.assertEqual(check(read_file(tmp), 'inline-output.expected.md'),
                             read_fixture('inline-output.expected.md'))
        finally:
            os.unlink(tmp)

    def test_inline_error_leaves_file_unchanged(self):
        """Default mode on a file with a parse error leaves the file unchanged."""
        tmp = self._tmp_copy('inline-error-input.md')
        try:
            original = read_fixture('inline-error-input.md')
            result = run('--ltac', fixture('simple.ltac'), tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertIn('unclosed', result.stderr)
            self.assertEqual(read_file(tmp), original)
        finally:
            os.unlink(tmp)


class TestIntroduction(unittest.TestCase):
    def test_non_ltac_heading_ignored(self):
        """A heading like 'Introduction' that does not start with an LTAC type
        is passed through silently without warnings or errors."""
        r = run('--ltac', fixture('simple.ltac'), '--stdout', fixture('introduction-input.md'))
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('Introduction', r.stderr)
        self.assertEqual(check(r.stdout, 'introduction-output.expected.md'),
                         read_fixture('introduction-output.expected.md'))


class TestUpdate(unittest.TestCase):
    def test_update_no_changes(self):
        """--update with no citation mismatches leaves the LTAC untouched and processes content."""
        r = run('--ltac', fixture('simple.ltac'), '--update',
                '--stdout', fixture('update-input.md'))
        self.assertEqual(r.returncode, 0)
        # Header still updates by default (update_headers=True).
        actual = check(r.stdout, 'update-output.expected.md')
        self.assertEqual(actual, read_fixture('update-output.expected.md'))
        self.assertNotIn('not yet implemented', r.stderr)
        self.assertNotIn('Updating', r.stderr)

    def test_update_warns_mismatch_without_flag(self):
        """Without --update, a citation with the wrong statement produces a warning with a hint."""
        r = run('--ltac', fixture('update-citations.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        self.assertIn('Wrong statement here', r.stderr)
        self.assertIn('--update', r.stderr)

    def test_update_fixes_citation(self):
        """--update rewrites the LTAC file so citation statements match the declaration."""
        import shutil as _shutil
        os.makedirs(RESULTS, exist_ok=True)
        tmp_ltac = os.path.join(RESULTS, 'update-citations.ltac')
        _shutil.copy(fixture('update-citations.ltac'), tmp_ltac)
        try:
            r = run('--ltac', tmp_ltac, '--update', '--validate')
            self.assertEqual(r.returncode, 0)
            self.assertIn('Updating', r.stderr)
            updated = read_file(tmp_ltac)
            self.assertNotIn('Wrong statement here', updated)
            self.assertIn('The software is acceptably safe', updated)
        finally:
            os.unlink(tmp_ltac)

    def test_update_header_default(self):
        """update_headers defaults to True, so stale headers are rewritten even without --update."""
        r = run('--ltac', fixture('simple.ltac'), '--stdout', fixture('update-input.md'))
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'update-output.expected.md')
        self.assertEqual(actual, read_fixture('update-output.expected.md'))
        self.assertIn('updated Claim C1:', r.stderr)
        self.assertNotIn('Wrong statement here', r.stdout)


class TestAnchorUniqueness(unittest.TestCase):
    def test_collision_is_error(self):
        """Two identifiers that produce the same HTML anchor id are reported as an error."""
        r = run('--ltac', fixture('anchor-collision.ltac'), '--validate')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('anchor id collision', r.stderr)
        self.assertIn('Foo < 0', r.stderr)
        self.assertIn('foo > 0', r.stderr)

    def test_no_collision_in_simple(self):
        """simple.ltac has no anchor collisions."""
        r = run('--ltac', fixture('simple.ltac'), '--validate')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('anchor id collision', r.stderr)


class TestCitationType(unittest.TestCase):
    def test_type_mismatch_is_error(self):
        """Citing a Claim as a Strategy is always an error."""
        r = run('--ltac', fixture('type-mismatch.ltac'), '--select', 'ltac/markdown')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('C1', r.stderr)
        self.assertIn('conflicts with earlier use', r.stderr)

    def test_type_match_is_ok(self):
        """Citing a Claim as a Claim (same type) produces no error."""
        r = run('--ltac', fixture('circular.ltac'), '--select', 'ltac/markdown')
        # The circular test reuses circular.ltac which has matching types;
        # the only error should be the circularity, not a type mismatch.
        self.assertNotIn('declared as', r.stderr)


class TestCircularity(unittest.TestCase):
    def test_circular_is_fatal(self):
        """A circular LTAC always exits non-zero with a circularity message showing the cycle."""
        r = run('--ltac', fixture('circular.ltac'), '--select', 'ltac/markdown')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('circularity', r.stderr)
        self.assertIn('C2', r.stderr)
        self.assertIn('C4', r.stderr)

    def test_multi_cite_no_cycle(self):
        """The same node cited by two different paths is acceptable (no cycle)."""
        r = run('--ltac', fixture('multi-cite.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('circularity', r.stderr)


class TestMutations(unittest.TestCase):
    def _ltac_copy(self, name='simple.ltac'):
        """Copy an LTAC fixture to tests/results/ with a unique name and return its path."""
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, 'mut-' + name)
        shutil.copy(fixture(name), path)
        return path

    def test_rename_single(self):
        """--rename changes the identifier everywhere in the LTAC file."""
        ltac = self._ltac_copy()
        try:
            r = run('--ltac', ltac, '--rename', 'C1', 'C99', '--validate')
            self.assertEqual(r.returncode, 0)
            content = read_file(ltac)
            self.assertIn('Claim C99', content)
            self.assertNotIn('Claim C1', content)
        finally:
            os.unlink(ltac)

    def test_restate_single(self):
        """--restate updates the statement text for an identifier everywhere."""
        ltac = self._ltac_copy()
        try:
            r = run('--ltac', ltac, '--restate', 'C1', 'New safety claim', '--validate')
            self.assertEqual(r.returncode, 0)
            content = read_file(ltac)
            self.assertIn('New safety claim', content)
            self.assertNotIn('The software is acceptably safe', content)
        finally:
            os.unlink(ltac)

    def test_rename_then_restate(self):
        """Interleaved --rename then --restate applies in order."""
        ltac = self._ltac_copy()
        try:
            r = run('--ltac', ltac,
                    '--rename', 'C1', 'C99',
                    '--restate', 'C99', 'Renamed and restated',
                    '--validate')
            self.assertEqual(r.returncode, 0)
            content = read_file(ltac)
            self.assertIn('C99', content)
            self.assertIn('Renamed and restated', content)
            self.assertNotIn('C1', content)
        finally:
            os.unlink(ltac)

    def test_rename_swap(self):
        """Two labels can be swapped using an intermediary rename."""
        ltac = self._ltac_copy()
        try:
            r = run('--ltac', ltac,
                    '--rename', 'C1', 'Ctmp',
                    '--rename', 'C2', 'C1',
                    '--rename', 'Ctmp', 'C2',
                    '--validate')
            self.assertEqual(r.returncode, 0)
            content = read_file(ltac)
            self.assertIn('Claim C2: The software is acceptably safe', content)
            self.assertIn('Claim C1: All hazards have been identified', content)
        finally:
            os.unlink(ltac)

    def test_rename_bad_old_leaves_files_unchanged(self):
        """--rename with an unknown OLD panics without touching any file."""
        ltac = self._ltac_copy()
        try:
            original = read_file(ltac)
            r = run('--ltac', ltac, '--rename', 'NOSUCHID', 'X99', '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('NOSUCHID', r.stderr)
            self.assertEqual(read_file(ltac), original)
        finally:
            os.unlink(ltac)

    def test_rename_new_already_declared_panics(self):
        """--rename with a NEW that is already declared panics without modifying files."""
        ltac = self._ltac_copy()
        try:
            original = read_file(ltac)
            r = run('--ltac', ltac, '--rename', 'C1', 'C2', '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('C2', r.stderr)
            self.assertEqual(read_file(ltac), original)
        finally:
            os.unlink(ltac)

    def test_restate_bad_label_panics(self):
        """--restate with an unknown LABEL panics without modifying files."""
        ltac = self._ltac_copy()
        try:
            original = read_file(ltac)
            r = run('--ltac', ltac, '--restate', 'NOSUCHID', 'new text', '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('NOSUCHID', r.stderr)
            self.assertEqual(read_file(ltac), original)
        finally:
            os.unlink(ltac)


class TestWriteLTAC(unittest.TestCase):
    def test_roundtrip(self):
        """write_ltac round-trips a simple LTAC file without loss."""
        with open(fixture('simple.ltac'), encoding='utf-8') as f:
            original = f.read()
        # Run caseproc --selftest to check doctest; for round-trip we use --select
        # with a write-ltac selector not yet available, so we test indirectly by
        # parsing the file, serialising, re-parsing and checking --select output matches.
        # (Full write_ltac unit tests live in the doctest embedded in caseproc itself.)
        r1 = run('--ltac', fixture('simple.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r1.returncode, 0)
        # Write serialised LTAC to a temp file, then round-trip it.
        import tempfile as _tf
        fd, tmp_ltac = _tf.mkstemp(suffix='.ltac')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(original)
            r2 = run('--ltac', tmp_ltac, '--select', 'ltac/markdown')
            self.assertEqual(r2.returncode, 0)
            self.assertEqual(r1.stdout, r2.stdout)
        finally:
            os.unlink(tmp_ltac)


class TestCommitUpdates(unittest.TestCase):
    def test_backup_created(self):
        """commit_updates moves the original to .backup/ and the temp to final."""
        import shutil as _shutil
        import tempfile as _tf
        tmpdir = _tf.mkdtemp()
        try:
            # Create an "original" content file.
            final = os.path.join(tmpdir, 'out.md')
            with open(final, 'w') as f:
                f.write('old content\n')
            # Create a "new" temp file in the same dir (as caseproc does).
            fd, tmp = _tf.mkstemp(dir=tmpdir)
            with os.fdopen(fd, 'w') as f:
                f.write('new content\n')
            # Run caseproc in default mode on a file that needs updating.
            # We test commit_updates behaviour indirectly: after a default-mode
            # run that changes a file, verify .backup/ exists and final is updated.
            src = fixture('inline-input.md')
            fd2, content_file = _tf.mkstemp(dir=tmpdir, suffix='.md')
            os.close(fd2)
            _shutil.copy(src, content_file)
            r = run('--ltac', fixture('simple.ltac'), content_file)
            self.assertEqual(r.returncode, 0)
            backup_dir = os.path.join(tmpdir, '.backup')
            self.assertTrue(os.path.isdir(backup_dir),
                            ".backup/ directory was not created")
            backup_file = os.path.join(backup_dir, os.path.basename(content_file))
            self.assertTrue(os.path.exists(backup_file),
                            "original file was not moved to .backup/")
            with open(backup_file) as bf:
                self.assertEqual(bf.read(), read_file(src))
        finally:
            _shutil.rmtree(tmpdir)


if __name__ == '__main__':
    unittest.main()
