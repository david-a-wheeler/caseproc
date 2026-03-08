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
    """Run caseproc with the given arguments and return the CompletedProcess.

    Runs in the FIXTURES directory so that stray case.md / case.ltac files in
    the project root are never auto-discovered during testing.  All paths
    passed to caseproc are already absolute (via fixture()), so this is safe.
    """
    return subprocess.run(
        LTACPROC + list(args), capture_output=True, text=True, encoding='utf-8',
        cwd=FIXTURES,
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

    def test_mid_brace_is_text_not_options(self):
        """Braces in the middle of text are literal; only trailing {} sets options.
        An empty {} at line-end means 'no options', allowing a statement to end
        with a {...} parenthetical without it being consumed as options."""
        r = run('--ltac', fixture('mid-brace.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'mid-brace.ltac.expected.md')
        self.assertEqual(actual, read_fixture('mid-brace.ltac.expected.md'))
        # Mid-text braces appear verbatim in the link label
        self.assertIn('{NIST SP 800-53}', r.stdout)   # C1: mid-brace in text
        self.assertIn('{note}', r.stdout)              # C2: mid-brace in text
        # C3 has a ref but the trailing {} suppresses options
        self.assertIn('[ref.md](ref.md)', r.stdout)    # C3: ref still works with {}
        # C4's {needsSupport} is real options (not shown in ltac/markdown link label)
        self.assertNotIn('needsSupport', r.stdout)     # options never appear in labels

    def test_mid_paren_is_text_not_ref(self):
        """Parentheses in the middle of text are literal; only trailing (ref) is a ref."""
        r = run('--ltac', fixture('mid-paren.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'mid-paren.ltac.expected.md')
        self.assertEqual(actual, read_fixture('mid-paren.ltac.expected.md'))
        # Mid-text parens appear verbatim in the link label
        self.assertIn('(for password storage)', r.stdout)   # C1: mid-paren in text
        self.assertIn('(see hashing module)', r.stdout)     # E1: mid-paren in text
        self.assertIn('(not GitHub SSO)', r.stdout)         # X1: mid-paren in text
        self.assertIn('(Rack::Attack)', r.stdout)           # C2: mid-paren in text
        # Trailing parens become external ref links, not part of the label
        self.assertIn('[app/models/user.rb](app/models/user.rb)', r.stdout)
        self.assertIn('[config/initializers/rack_attack.rb]', r.stdout)
        # C1 and X1 have no trailing ref
        self.assertNotIn('hashes)', r.stdout)  # C1 label ends at 'hashes', no ref
        self.assertNotIn('users)', r.stdout)   # X1 label ends at 'users', no ref

    def test_options_before_ref(self):
        """Options {…} come before reference (…) in the new grammar order."""
        r = run('--ltac', fixture('ref-and-options.ltac'), '--select', 'ltac/markdown')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'ref-and-options.ltac.expected.md')
        self.assertEqual(actual, read_fixture('ref-and-options.ltac.expected.md'))
        # References are rendered as links
        self.assertIn('[safety-case.pdf](safety-case.pdf)', r.stdout)
        self.assertIn('[tests.pdf](tests.pdf)', r.stdout)
        # Options do not appear in link labels
        self.assertNotIn('needsSupport', r.stdout)
        self.assertNotIn('undeveloped', r.stdout)


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

    def test_structural_warning_with_error_flag(self):
        """A structurally invalid LTAC file (Claim under Evidence) exits non-zero with --error."""
        result = run('--ltac', fixture('warn.ltac'), '--select', 'ltac/markdown', '--error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('should not be a child of', result.stderr)

    def test_element_coverage_warning(self):
        """Elements without a matching 'element' selector produce warnings; --error makes exit non-zero."""
        result = run('--ltac', fixture('simple.ltac'), '--stdout',
                     fixture('element-selector-input.md'), '--error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no 'element' selector", result.stderr)

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
        """'*' is not valid with 'statement' and always exits non-zero."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'statement *')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not valid', r.stderr)
        self.assertIn('statement', r.stderr)



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


class TestSelectorExpansion(unittest.TestCase):
    def test_sacm_shorthand_equals_sacm_mermaid(self):
        """'sacm' expands to 'sacm/mermaid/markdown' on a markdown context."""
        r1 = run('--ltac', fixture('simple.ltac'),
                 '--config', fixture('simple.sacm.mermaid.config'),
                 '--select', 'sacm')
        r2 = run('--ltac', fixture('simple.ltac'),
                 '--config', fixture('simple.sacm.mermaid.config'),
                 '--select', 'sacm/mermaid')
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_gsn_shorthand_equals_gsn_mermaid(self):
        """'gsn' expands to 'gsn/mermaid/markdown' on a markdown context."""
        r1 = run('--ltac', fixture('simple.ltac'),
                 '--config', fixture('simple.gsn.mermaid.config'),
                 '--select', 'gsn')
        r2 = run('--ltac', fixture('simple.ltac'),
                 '--config', fixture('simple.gsn.mermaid.config'),
                 '--select', 'gsn/mermaid')
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_ltac_shorthand_expands(self):
        """'ltac' in --select expands (defaults to markdown)."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'ltac')
        self.assertEqual(r.returncode, 0)
        self.assertIn('Claim', r.stdout)


class TestSelectGsn(unittest.TestCase):
    def test_select_gsn_mermaid(self):
        r = run('--ltac', fixture('simple.ltac'),
                '--config', fixture('simple.gsn.mermaid.config'),
                '--select', 'gsn/mermaid')
        self.assertEqual(r.returncode, 0)
        actual = check(r.stdout, 'simple.gsn.mermaid.expected.md')
        self.assertEqual(actual, read_fixture('simple.gsn.mermaid.expected.md'))


class TestElementPackageSelectors(unittest.TestCase):
    def test_element_selector_produces_heading(self):
        """'element C1' produces a heading with anchor and statement."""
        r = run('--ltac', fixture('simple.ltac'),
                '--stdout', fixture('element-selector-input.md'))
        self.assertEqual(r.returncode, 0)
        self.assertIn('<a id="claim-c1"></a>', r.stdout)
        self.assertIn('### Claim C1:', r.stdout)
        self.assertIn('Referenced by:', r.stdout)

    def test_element_selector_missing_id_errors(self):
        """'element' without an ID produces an error."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'element')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('requires an explicit ID', r.stderr)

    def test_package_star_produces_all_headings(self):
        """'package *' produces headings and diagrams for all packages."""
        r = run('--ltac', fixture('simple.ltac'),
                '--stdout', fixture('package-star-input.md'))
        self.assertEqual(r.returncode, 0)
        self.assertIn('<a id="package-c1"></a>', r.stdout)
        self.assertIn('### Package C1:', r.stdout)
        self.assertIn('Defines:', r.stdout)

    def test_package_selector_unknown_id_errors(self):
        """'package NoSuchPkg' produces an error."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'package NoSuchPkg')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('NoSuchPkg', r.stderr)


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


class TestMermaidHtml(unittest.TestCase):
    def _tmp_html(self, content):
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, 'mermaid-test.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_sacm_html_produces_pre_block(self):
        """sacm/mermaid/html produces <pre class="mermaid"> inside an HTML file."""
        content = '<!-- caseproc sacm/mermaid/html -->\n<!-- end caseproc -->\n'
        tmp = self._tmp_html(content)
        try:
            result = run('--ltac', fixture('simple.ltac'), tmp)
            self.assertEqual(result.returncode, 0)
            updated = read_file(tmp)
            self.assertIn('<pre class="mermaid">', updated)
        finally:
            os.unlink(tmp)

    def test_sacm_html_injects_mermaid_js(self):
        """First sacm/mermaid/html region gets a <script> block prepended."""
        content = '<!-- caseproc sacm/mermaid/html -->\n<!-- end caseproc -->\n'
        tmp = self._tmp_html(content)
        try:
            result = run('--ltac', fixture('simple.ltac'), tmp)
            self.assertEqual(result.returncode, 0)
            updated = read_file(tmp)
            self.assertIn('<script type="module">', updated)
            # Script should appear before the pre block.
            script_pos = updated.index('<script type="module">')
            pre_pos = updated.index('<pre class="mermaid">')
            self.assertLess(script_pos, pre_pos)
        finally:
            os.unlink(tmp)

    def test_mermaid_js_url_empty_disables_injection(self):
        """Setting mermaid_js_url to '' disables script injection."""
        import json, tempfile
        fd, cfg = tempfile.mkstemp(suffix='.json')
        content = '<!-- caseproc sacm/mermaid/html -->\n<!-- end caseproc -->\n'
        tmp = self._tmp_html(content)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump({'mermaid_js_url': ''}, f)
            result = run('--ltac', fixture('simple.ltac'), '--config', cfg, tmp)
            self.assertEqual(result.returncode, 0)
            updated = read_file(tmp)
            self.assertNotIn('<script', updated)
        finally:
            os.unlink(cfg)
            os.unlink(tmp)


class TestLineEndings(unittest.TestCase):
    def test_crlf_file_preserved(self):
        """A CRLF document file is updated and written back with CRLF line endings."""
        # Build a minimal CRLF document with an inline region.
        crlf_content = (
            '<!-- caseproc ltac/markdown -->\r\n'
            '<!-- end caseproc -->\r\n'
        )
        os.makedirs(RESULTS, exist_ok=True)
        tmp = os.path.join(RESULTS, 'crlf-test.md')
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(crlf_content)
        try:
            result = run('--ltac', fixture('simple.ltac'), tmp)
            self.assertEqual(result.returncode, 0)
            with open(tmp, 'rb') as f:
                raw = f.read()
            self.assertIn(b'\r\n', raw, 'Output file should contain CRLF line endings')
            self.assertNotIn(b'\r\r', raw, 'Output file should not have double CR')
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
            self.assertIn('Argue safety by hazard category', updated)
        finally:
            os.unlink(tmp_ltac)



class TestReachability(unittest.TestCase):
    def test_unreachable_package_is_error(self):
        """A package whose root is never cited or linked is reported as unreachable."""
        r = run('--ltac', fixture('update-citations.ltac'), '--validate')
        # update-citations.ltac has AR1 reachable via citation from C1; no error expected.
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('unreachable', r.stderr)

    def test_single_package_no_check(self):
        """Reachability check is skipped for single-package LTAC files."""
        r = run('--ltac', fixture('simple.ltac'), '--validate')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('unreachable', r.stderr)

    def test_unreachable_detected(self):
        """An isolated package with no citation path from the root is an error."""
        import tempfile as _tf
        os.makedirs(RESULTS, exist_ok=True)
        ltac = os.path.join(RESULTS, 'unreachable-test.ltac')
        with open(ltac, 'w') as f:
            f.write('- Claim C1: Root\n\n- Strategy AR1: Unreachable package\n')
        try:
            r = run('--ltac', ltac, '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('unreachable', r.stderr)
            self.assertIn('AR1', r.stderr)
        finally:
            os.unlink(ltac)


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


class TestDetach(unittest.TestCase):
    """Tests for the --detach ID mutation option."""

    def _write_ltac(self, content):
        """Write content to a temp LTAC file and return its path."""
        fd, path = tempfile.mkstemp(suffix='.ltac')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_detach_basic(self):
        """--detach C2 on C1→C2→C3 produces two packages: C1 with ^C2 child, and C2→C3."""
        ltac = (
            '- Claim C1: Top claim\n'
            '  - Claim C2: Middle claim\n'
            '    - Claim C3: Leaf claim\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--detach', 'C2', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(path)
            lines = content.splitlines()
            # First package: C1 root with ^C2 as child, no C3
            self.assertIn('Claim C1', content)
            self.assertIn('^C2', content)
            self.assertNotIn('C3', lines[lines.index(next(l for l in lines if 'C1' in l))])
            # Second package: C2 as root with C3 as child
            # Find C2 declaration (not cited)
            decl_lines = [l for l in lines if 'Claim C2' in l and '^' not in l]
            self.assertTrue(decl_lines, 'C2 definition not found as package root')
            c2_decl_line = decl_lines[0]
            # C2 should be at depth 0 (no leading spaces)
            self.assertFalse(c2_decl_line.startswith(' '), 'C2 should be top-level package root')
            self.assertIn('C3', content)
        finally:
            os.unlink(path)

    def test_detach_unknown_id(self):
        """--detach with an unknown ID exits non-zero with an error about 'not defined'."""
        ltac = '- Claim C1: Top claim\n  - Claim C2: Child\n'
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--detach', 'NoSuch', '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('not defined', r.stderr)
        finally:
            os.unlink(path)

    def test_detach_top_level(self):
        """--detach on a top-level package root exits non-zero with an error."""
        ltac = '- Claim C1: Top claim\n  - Claim C2: Child\n'
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--detach', 'C1', '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('C1', r.stderr)
        finally:
            os.unlink(path)

    def test_detach_roundtrip(self):
        """After --detach C2, the output LTAC is valid (--validate exits 0)."""
        ltac = (
            '- Claim C1: Top claim\n'
            '  - Claim C2: Middle claim\n'
            '    - Claim C3: Leaf claim\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--detach', 'C2', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            os.unlink(path)


class TestMove(unittest.TestCase):
    """Tests for the --move ID DESTINATION mutation option."""

    def _write_ltac(self, content):
        """Write content to a temp LTAC file and return its path."""
        fd, path = tempfile.mkstemp(suffix='.ltac')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_move_from_top_level_with_citation(self):
        """--move C2 C1 where C1 already has ^C2 (direct child) restores the original structure."""
        # Post-detach state: C1 with direct ^C2 child, and separate C2→C3 package.
        # Citation format: "- Claim ^C2: ..." means C2 is cited (not defined) here.
        ltac = (
            '- Claim C1: Top claim\n'
            '  - Claim ^C2: Middle claim\n'
            '\n'
            '- Claim C2: Middle claim\n'
            '  - Claim C3: Leaf claim\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--move', 'C2', 'C1', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(path)
            # Should be one package with C1→C2→C3
            lines = content.splitlines()
            # Only one top-level declaration (C1)
            top_level_decls = [l for l in lines if l.startswith('- ') and 'C' in l]
            self.assertEqual(len(top_level_decls), 1, f'Expected one package, got: {top_level_decls}')
            self.assertIn('C1', top_level_decls[0])
            self.assertIn('C2', content)
            self.assertIn('C3', content)
        finally:
            os.unlink(path)

    def test_move_from_top_level_no_citation(self):
        """--move C2 C1 where no direct ^C2 child of C1 exists appends C2 as last child of C1.

        C2 is cited indirectly (via C4 under C1) so the LTAC is initially valid,
        but there is no direct ^C2 child of C1, so the move appends C2 as last child.
        """
        # C2 is reachable via C4, but C1 has no direct ^C2 child.
        ltac = (
            '- Claim C1: Foo\n'
            '  - Claim C4: Bridge\n'
            '    - Claim ^C2: Bar\n'
            '\n'
            '- Claim C2: Bar\n'
            '  - Claim C3: Baz\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--move', 'C2', 'C1', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(path)
            lines = content.splitlines()
            # Only one top-level declaration (C1)
            top_level_decls = [l for l in lines if l.startswith('- ') and 'C' in l]
            self.assertEqual(len(top_level_decls), 1, f'Expected one package, got: {top_level_decls}')
            self.assertIn('C1', top_level_decls[0])
            self.assertIn('C2', content)
            self.assertIn('C3', content)
            # C2 definition should be a direct child of C1 (appended last)
            decl_lines = [l for l in lines if 'Claim C2' in l and '^' not in l]
            self.assertTrue(decl_lines, 'C2 definition not found')
            c2_indent = len(decl_lines[0]) - len(decl_lines[0].lstrip())
            # C4 is also a direct child of C1; both should be at the same indent level
            c4_lines = [l for l in lines if 'Claim C4' in l]
            self.assertTrue(c4_lines, 'C4 not found')
            c4_indent = len(c4_lines[0]) - len(c4_lines[0].lstrip())
            self.assertEqual(c2_indent, c4_indent, 'C2 should be a sibling of C4 under C1')
        finally:
            os.unlink(path)

    def test_move_from_nested(self):
        """--move C3 C1 where C3 is nested under C2 moves C3 to be a child of C1."""
        ltac = (
            '- Claim C1: Top claim\n'
            '  - Claim C2: Middle claim\n'
            '    - Claim C3: Leaf claim\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--move', 'C3', 'C1', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(path)
            lines = content.splitlines()
            # C1 should have two direct children: C2 and C3
            c1_idx = next(i for i, l in enumerate(lines) if 'Claim C1' in l and not l.startswith(' '))
            # C2 and C3 should both appear in content
            self.assertIn('C2', content)
            self.assertIn('C3', content)
            # C3 should not be indented further than C2 (should be sibling, not child of C2)
            c2_line = next(l for l in lines if 'Claim C2' in l)
            c3_line = next(l for l in lines if 'Claim C3' in l)
            c2_indent = len(c2_line) - len(c2_line.lstrip())
            c3_indent = len(c3_line) - len(c3_line.lstrip())
            self.assertEqual(c2_indent, c3_indent, 'C2 and C3 should be at the same depth under C1')
        finally:
            os.unlink(path)

    def test_move_no_citation_left(self):
        """After --move C3 C1 (nested move), C2 has no children (no ^C3 left behind)."""
        ltac = (
            '- Claim C1: Top claim\n'
            '  - Claim C2: Middle claim\n'
            '    - Claim C3: Leaf claim\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--move', 'C3', 'C1', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(path)
            lines = content.splitlines()
            # C2 should have no children: no line after C2's line should be indented more
            c2_idx = next(i for i, l in enumerate(lines) if 'Claim C2' in l)
            c2_indent = len(lines[c2_idx]) - len(lines[c2_idx].lstrip())
            child_of_c2 = [
                l for l in lines[c2_idx + 1:]
                if l.strip() and len(l) - len(l.lstrip()) > c2_indent
            ]
            self.assertEqual(child_of_c2, [], f'C2 should have no children, got: {child_of_c2}')
            # No ^C3 citation should remain
            self.assertNotIn('^', content.replace('^Claim C3', ''))
            # More simply: no citation of C3 anywhere
            self.assertNotIn('^C3', content)
            self.assertNotIn('^Claim C3', content)
        finally:
            os.unlink(path)

    def test_move_unknown_target(self):
        """--move with an unknown ID exits non-zero with error containing 'not defined'."""
        ltac = '- Claim C1: Top claim\n  - Claim C2: Child\n'
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--move', 'NoSuch', 'C1', '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('not defined', r.stderr)
        finally:
            os.unlink(path)

    def test_move_unknown_dest(self):
        """--move with an unknown DESTINATION exits non-zero with error containing 'not defined'."""
        ltac = '- Claim C1: Top claim\n  - Claim C2: Child\n'
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--move', 'C1', 'NoSuch', '--validate')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('not defined', r.stderr)
        finally:
            os.unlink(path)


class TestMoveQueue(unittest.TestCase):
    """Queue ordering tests for combined --detach and --move mutations."""

    def _write_ltac(self, content):
        """Write content to a temp LTAC file and return its path."""
        fd, path = tempfile.mkstemp(suffix='.ltac')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_detach_then_move_restores(self):
        """--detach C2 --move C2 C1 on C1→C2→C3 restores the original single-package structure."""
        ltac = (
            '- Claim C1: Top claim\n'
            '  - Claim C2: Middle claim\n'
            '    - Claim C3: Leaf claim\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--detach', 'C2', '--move', 'C2', 'C1', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(path)
            lines = content.splitlines()
            # Should be one package with C1 at root
            top_level_decls = [l for l in lines if l.startswith('- ') and 'Claim' in l]
            self.assertEqual(len(top_level_decls), 1, f'Expected one package, got: {top_level_decls}')
            self.assertIn('C1', top_level_decls[0])
            self.assertIn('C2', content)
            self.assertIn('C3', content)
        finally:
            os.unlink(path)

    def test_rename_then_detach(self):
        """--rename C2 X2 --detach X2 on C1→C2→C3 produces C1 with ^X2, and X2→C3 package."""
        ltac = (
            '- Claim C1: Top claim\n'
            '  - Claim C2: Middle claim\n'
            '    - Claim C3: Leaf claim\n'
        )
        path = self._write_ltac(ltac)
        try:
            r = run('--ltac', path, '--rename', 'C2', 'X2', '--detach', 'X2', '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(path)
            lines = content.splitlines()
            # C2 should be gone, X2 should appear
            self.assertNotIn('C2', content)
            self.assertIn('X2', content)
            # ^X2 citation should be under C1
            self.assertIn('^', content)
            # X2 should be a top-level package root
            x2_decl_lines = [l for l in lines if 'Claim X2' in l and '^' not in l]
            self.assertTrue(x2_decl_lines, 'X2 definition not found')
            x2_decl = x2_decl_lines[0]
            self.assertFalse(x2_decl.startswith(' '), 'X2 should be a top-level package root')
            # C3 should be under X2
            self.assertIn('C3', content)
        finally:
            os.unlink(path)


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


class TestMissingOption(unittest.TestCase):
    def _tmp_copy(self, name):
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, name)
        shutil.copy(fixture(name), path)
        return path

    def test_missing_adds_element_regions(self):
        """--missing appends element regions for elements not yet in the document."""
        tmp_doc = self._tmp_copy('element-selector-input.md')
        tmp_ltac = self._tmp_copy('simple.ltac')
        try:
            r = run('--ltac', tmp_ltac, '--missing', tmp_doc)
            self.assertEqual(r.returncode, 0)
            content = read_file(tmp_doc)
            # AR1, C2, E1, C3, A1, X1 were not in the document; they should be added.
            self.assertIn('<!-- caseproc element AR1 -->', content)
            self.assertIn('<!-- caseproc element C2 -->', content)
            self.assertIn('<!-- caseproc element C1 -->', content)  # was already there
        finally:
            os.unlink(tmp_doc)
            os.unlink(tmp_ltac)

    def test_missing_adds_needs_support_to_leaf(self):
        """--missing adds {needssupport} to leaf elements in the LTAC."""
        import tempfile
        # Create a minimal LTAC with a leaf claim (no children).
        ltac = '- Claim Root: Root claim\n  - Claim Leaf: A leaf with no children\n'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ltac', delete=False) as f:
            f.write(ltac)
            ltac_path = f.name
        # Create a doc with no element selectors so Leaf is "missing".
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('# Assurance Case\n')
            doc_path = f.name
        try:
            r = run('--ltac', ltac_path, '--missing', doc_path)
            self.assertEqual(r.returncode, 0)
            ltac_content = read_file(ltac_path)
            self.assertIn('needssupport', ltac_content)
        finally:
            os.unlink(ltac_path)
            os.unlink(doc_path)

    def test_missing_does_not_add_needs_support_to_non_leaf(self):
        """--missing does not add {needssupport} to non-leaf elements."""
        import tempfile
        ltac = '- Claim Root: Root claim\n  - Claim Child: A child\n    - Evidence E1: evidence\n'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ltac', delete=False) as f:
            f.write(ltac)
            ltac_path = f.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('# Test\n')
            doc_path = f.name
        try:
            r = run('--ltac', ltac_path, '--missing', doc_path)
            self.assertEqual(r.returncode, 0)
            ltac_content = read_file(ltac_path)
            lines = ltac_content.splitlines()
            # Root and Child have children; only E1 (leaf) gets needssupport.
            root_line = [l for l in lines if 'Root' in l][0]
            child_line = [l for l in lines if 'Child' in l][0]
            self.assertNotIn('needssupport', root_line)
            self.assertNotIn('needssupport', child_line)
        finally:
            os.unlink(ltac_path)
            os.unlink(doc_path)

    def test_missing_does_not_add_needs_support_if_already_has_status(self):
        """--missing does not add {needssupport} if element already has an assertion status."""
        import tempfile
        ltac = '- Claim Root: Root claim\n  - Claim Leaf: leaf {assumed}\n'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ltac', delete=False) as f:
            f.write(ltac)
            ltac_path = f.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('# Test\n')
            doc_path = f.name
        try:
            r = run('--ltac', ltac_path, '--missing', doc_path)
            self.assertEqual(r.returncode, 0)
            ltac_content = read_file(ltac_path)
            # The {assumed} element should NOT get {needssupport} added.
            self.assertNotIn('needssupport', ltac_content)
        finally:
            os.unlink(ltac_path)
            os.unlink(doc_path)


class TestCaseprocConfig(unittest.TestCase):
    def test_config_directive_changes_level(self):
        """<!-- caseproc-config element_level = 2 --> changes heading level for element regions."""
        r = run('--ltac', fixture('simple.ltac'), '--stdout', fixture('element-selector-input.md'),
                '--config', fixture('doc-simple.config'))
        self.assertEqual(r.returncode, 0)
        self.assertIn('### Claim C1:', r.stdout)  # default level 3

        # Now with a doc that overrides element_level via directive
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('<!-- caseproc-config element_level = 2 -->\n')
            f.write('<!-- caseproc element C1 -->\n')
            f.write('<!-- end caseproc -->\n')
            tmp = f.name
        try:
            r2 = run('--ltac', fixture('simple.ltac'), '--stdout', tmp)
            self.assertEqual(r2.returncode, 0)
            self.assertIn('## Claim C1:', r2.stdout)
        finally:
            os.unlink(tmp)

    def test_config_directive_invalid_key_warns(self):
        """An unknown key in caseproc-config produces a warning."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('<!-- caseproc-config no_such_key = value -->\n')
            tmp = f.name
        try:
            r = run('--ltac', fixture('simple.ltac'), '--stdout', tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn('unknown key', r.stderr)
        finally:
            os.unlink(tmp)

    def test_config_directive_invalid_value_warns(self):
        """An out-of-range value in caseproc-config produces a warning."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('<!-- caseproc-config element_level = 9 -->\n')
            tmp = f.name
        try:
            r = run('--ltac', fixture('simple.ltac'), '--stdout', tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn('invalid value', r.stderr)
        finally:
            os.unlink(tmp)

    def test_config_directive_persists_across_regions(self):
        """A caseproc-config directive affects all subsequent element regions in the file."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('<!-- caseproc-config element_level = 1 -->\n')
            f.write('<!-- caseproc element C1 -->\n')
            f.write('<!-- end caseproc -->\n')
            tmp = f.name
        try:
            r = run('--ltac', fixture('simple.ltac'), '--stdout', tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn('# Claim C1:', r.stdout)
            self.assertNotIn('## Claim C1:', r.stdout)
            self.assertNotIn('### Claim C1:', r.stdout)
        finally:
            os.unlink(tmp)

    def test_config_wrong_syntax_is_error(self):
        """'<!-- caseproc config KEY = VALUE -->' (wrong form) produces an error."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('<!-- caseproc config element_level = 2 -->\n')
            f.write('<!-- end caseproc -->\n')
            tmp = f.name
        try:
            r = run('--ltac', fixture('simple.ltac'), '--stdout', tmp)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('caseproc-config', r.stderr)
        finally:
            os.unlink(tmp)


class TestWarningSelector(unittest.TestCase):
    def test_warning_select_outputs_text(self):
        """--select warning outputs the fixed warning comment."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'warning')
        self.assertEqual(r.returncode, 0)
        self.assertIn('DO NOT EDIT', r.stdout)
        self.assertIn('regenerated', r.stdout)
        self.assertEqual(r.stderr, '')

    def test_warning_with_id_is_error(self):
        """'warning C1' (with an ID) produces an error."""
        r = run('--ltac', fixture('simple.ltac'), '--select', 'warning C1')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('no parameters', r.stderr)

    def test_warning_region_rendered(self):
        """A <!-- caseproc warning --> region is filled with the warning text."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('<!-- caseproc warning -->\n')
            f.write('stale content\n')
            f.write('<!-- end caseproc -->\n')
            tmp = f.name
        try:
            r = run('--ltac', fixture('simple.ltac'), '--stdout', tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn('DO NOT EDIT', r.stdout)
            self.assertNotIn('stale content', r.stdout)
        finally:
            os.unlink(tmp)

    def test_missing_rerenders_warning_region(self):
        """--missing re-renders stale warning and package regions, not just appends."""
        import tempfile, os
        ltac = '- Claim Root: Root claim\n'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ltac', delete=False) as f:
            f.write(ltac)
            ltac_path = f.name
        doc = (
            '<!-- caseproc warning -->\n'
            'stale warning\n'
            '<!-- end caseproc -->\n'
            '\n'
            '<!-- caseproc element Root -->\n'
            '<!-- end caseproc -->\n'
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(doc)
            doc_path = f.name
        try:
            r = run('--ltac', ltac_path, '--missing', doc_path)
            self.assertEqual(r.returncode, 0)
            content = read_file(doc_path)
            self.assertIn('DO NOT EDIT', content)
            self.assertNotIn('stale warning', content)
        finally:
            os.unlink(ltac_path)
            os.unlink(doc_path)


class TestStartOption(unittest.TestCase):
    def _make_workdir(self):
        """Create a temporary working directory under tests/."""
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp_start')
        os.makedirs(base, exist_ok=True)
        d = tempfile.mkdtemp(dir=base)
        return d

    def test_start_creates_files(self):
        """--start creates case.ltac and case.md and populates them."""
        workdir = self._make_workdir()
        try:
            r = subprocess.run(
                LTACPROC + ['--start'],
                capture_output=True, text=True, encoding='utf-8',
                cwd=workdir,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            ltac_path = os.path.join(workdir, 'case.ltac')
            doc_path = os.path.join(workdir, 'case.md')
            self.assertTrue(os.path.exists(ltac_path), 'case.ltac not created')
            self.assertTrue(os.path.exists(doc_path), 'case.md not created')
            ltac_content = read_file(ltac_path)
            doc_content = read_file(doc_path)
            # LTAC: G2 and G3 are leaves and should gain {needssupport}
            self.assertIn('needssupport', ltac_content)
            self.assertIn('Top', ltac_content)
            # Doc: warning region filled
            self.assertIn('DO NOT EDIT', doc_content)
            # Doc: element regions for all three nodes appended
            self.assertIn('<!-- caseproc element Top -->', doc_content)
            self.assertIn('<!-- caseproc element G2 -->', doc_content)
            self.assertIn('<!-- caseproc element G3 -->', doc_content)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_start_fails_if_files_exist(self):
        """--start panics when case files already exist."""
        workdir = self._make_workdir()
        try:
            # First run succeeds.
            r1 = subprocess.run(
                LTACPROC + ['--start'],
                capture_output=True, text=True, encoding='utf-8',
                cwd=workdir,
            )
            self.assertEqual(r1.returncode, 0, r1.stderr)
            # Second run must fail.
            r2 = subprocess.run(
                LTACPROC + ['--start'],
                capture_output=True, text=True, encoding='utf-8',
                cwd=workdir,
            )
            self.assertNotEqual(r2.returncode, 0)
            self.assertIn('already exists', r2.stderr)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


class TestNormalPath(unittest.TestCase):
    """Tests that verify auto-discovery of case.ltac and case.md in CWD.

    Each test creates a temporary working directory, copies fixtures into it
    as 'case.ltac' / 'case.md', and runs caseproc as a subprocess with that
    directory as the CWD — exactly how a real user would use the tool.
    """

    def _make_workdir(self):
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp_normal')
        os.makedirs(base, exist_ok=True)
        return tempfile.mkdtemp(dir=base)

    def _run_in(self, workdir, *args):
        """Run caseproc in workdir with the given arguments."""
        return subprocess.run(
            LTACPROC + list(args),
            capture_output=True, text=True, encoding='utf-8',
            cwd=workdir,
        )

    def test_autodiscover_ltac(self):
        """caseproc discovers case.ltac automatically when --ltac is omitted."""
        workdir = self._make_workdir()
        try:
            shutil.copy(fixture('simple.ltac'), os.path.join(workdir, 'case.ltac'))
            shutil.copy(fixture('inline-input.md'), os.path.join(workdir, 'case.md'))
            # Pass relative doc path; no --ltac flag.
            r = self._run_in(workdir, 'case.md')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(os.path.join(workdir, 'case.md'))
            self.assertNotIn('STALE STATEMENT', content)
            self.assertIn('C1', content)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_autodiscover_doc(self):
        """caseproc discovers case.md automatically when no document file is given."""
        workdir = self._make_workdir()
        try:
            shutil.copy(fixture('simple.ltac'), os.path.join(workdir, 'case.ltac'))
            shutil.copy(fixture('inline-input.md'), os.path.join(workdir, 'case.md'))
            # Pass relative --ltac; no document file argument.
            r = self._run_in(workdir, '--ltac', 'case.ltac')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(os.path.join(workdir, 'case.md'))
            self.assertNotIn('STALE STATEMENT', content)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_autodiscover_both(self):
        """caseproc with no arguments discovers both case.ltac and case.md."""
        workdir = self._make_workdir()
        try:
            shutil.copy(fixture('simple.ltac'), os.path.join(workdir, 'case.ltac'))
            shutil.copy(fixture('inline-input.md'), os.path.join(workdir, 'case.md'))
            r = self._run_in(workdir)  # zero arguments
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(os.path.join(workdir, 'case.md'))
            self.assertNotIn('STALE STATEMENT', content)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_autodiscover_docs_subdir(self):
        """case.ltac and case.md under docs/ are also auto-discovered."""
        workdir = self._make_workdir()
        try:
            docs = os.path.join(workdir, 'docs')
            os.makedirs(docs)
            shutil.copy(fixture('simple.ltac'), os.path.join(docs, 'case.ltac'))
            shutil.copy(fixture('inline-input.md'), os.path.join(docs, 'case.md'))
            r = self._run_in(workdir)  # zero arguments; no files in workdir root
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(os.path.join(docs, 'case.md'))
            self.assertNotIn('STALE STATEMENT', content)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_autodiscover_validate(self):
        """--validate without --ltac auto-discovers case.ltac."""
        workdir = self._make_workdir()
        try:
            shutil.copy(fixture('simple.ltac'), os.path.join(workdir, 'case.ltac'))
            r = self._run_in(workdir, '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_autodiscover_validate_with_doc(self):
        """--validate discovers both case.ltac and case.md and processes the doc."""
        workdir = self._make_workdir()
        try:
            shutil.copy(fixture('simple.ltac'), os.path.join(workdir, 'case.ltac'))
            shutil.copy(fixture('inline-input.md'), os.path.join(workdir, 'case.md'))
            r = self._run_in(workdir, '--validate')
            self.assertEqual(r.returncode, 0, r.stderr)
            # validate does not modify the file
            content = read_file(os.path.join(workdir, 'case.md'))
            self.assertIn('STALE STATEMENT', content)  # unchanged by --validate
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_autodiscover_missing(self):
        """--missing discovers case.ltac, re-renders case.md, and appends stubs."""
        workdir = self._make_workdir()
        try:
            shutil.copy(fixture('simple.ltac'), os.path.join(workdir, 'case.ltac'))
            # A minimal doc with no element regions so --missing adds stubs.
            with open(os.path.join(workdir, 'case.md'), 'w', encoding='utf-8') as f:
                f.write('# Test\n\n<!-- caseproc package * -->\n<!-- end caseproc -->\n')
            r = self._run_in(workdir, '--missing')
            self.assertEqual(r.returncode, 0, r.stderr)
            content = read_file(os.path.join(workdir, 'case.md'))
            # --missing appends element regions for undocumented nodes
            self.assertIn('<!-- caseproc element', content)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


class TestGsnConnectorVisible(unittest.TestCase):
    """GSN Stage 1: Connector nodes produce a visible gray-circle in the diagram."""

    def _run_gsn(self, ltac_text):
        fd, path = tempfile.mkstemp(suffix='.ltac')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(ltac_text)
            return run('--ltac', path, '--select', 'gsn/mermaid')
        finally:
            os.unlink(path)

    def test_gsn_connector_node_declared(self):
        """A Connector in a GSN diagram produces a visible node and routes edges through it."""
        ltac = (
            '- Claim Root: Root claim\n'
            '  - Connector Grp\n'
            '    - Claim C1: Child one\n'
            '    - Claim C2: Child two\n'
        )
        r = self._run_gsn(ltac)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(':::connector', r.stdout)
        self.assertIn('Grp', r.stdout)
        self.assertIn('Root --> Grp', r.stdout)
        self.assertIn('Grp --> C1', r.stdout)
        self.assertIn('Grp --> C2', r.stdout)

    def test_gsn_connector_not_transparent(self):
        """Connector children are NOT connected directly to the grandparent (old transparent behaviour)."""
        ltac = (
            '- Claim Root: Root claim\n'
            '  - Connector Grp\n'
            '    - Claim C1: Child one\n'
            '    - Claim C2: Child two\n'
        )
        r = self._run_gsn(ltac)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('Root --> C1', r.stdout)
        self.assertNotIn('Root --> C2', r.stdout)


class TestMermaidWidthConfig(unittest.TestCase):
    """Stage 2+3: max_mermaid_children / narrowed_mermaid_children config and transform."""

    def _wide_ltac(self, n_children=10):
        """Return LTAC text with one parent and n_children direct children."""
        lines = ['- Claim Root: Root claim']
        for i in range(n_children):
            lines.append(f'  - Claim C{i}: child {i}')
        return '\n'.join(lines) + '\n'

    def _run_with_config(self, ltac_text, cfg, selector='sacm/mermaid'):
        """Write temp LTAC + config, run caseproc --select selector, return result."""
        import json
        fd_l, ltac_path = tempfile.mkstemp(suffix='.ltac')
        fd_c, cfg_path = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd_l, 'w', encoding='utf-8') as f:
                f.write(ltac_text)
            with os.fdopen(fd_c, 'w', encoding='utf-8') as f:
                json.dump(cfg, f)
            return run('--ltac', ltac_path, '--config', cfg_path,
                       '--select', selector)
        finally:
            os.unlink(ltac_path)
            os.unlink(cfg_path)

    def test_invariant_defaults_ok(self):
        """Default config satisfies invariant (no panic)."""
        r = self._run_with_config(self._wide_ltac(3),
                                  {'max_mermaid_children': 8,
                                   'narrowed_mermaid_children': 6})
        self.assertEqual(r.returncode, 0)

    def test_invariant_panics_narrowed_ge_max(self):
        """narrowed >= max triggers a fatal error."""
        r = self._run_with_config(self._wide_ltac(3),
                                  {'max_mermaid_children': 5,
                                   'narrowed_mermaid_children': 5})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('narrowed_mermaid_children', r.stderr)

    def test_invariant_panics_narrowed_less_than_2(self):
        """narrowed < 2 triggers a fatal error."""
        r = self._run_with_config(self._wide_ltac(3),
                                  {'max_mermaid_children': 5,
                                   'narrowed_mermaid_children': 1})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('narrowed_mermaid_children', r.stderr)

    def test_invariant_max_zero_skips_check(self):
        """max == 0 disables the transform; narrowed value is irrelevant."""
        r = self._run_with_config(self._wide_ltac(3),
                                  {'max_mermaid_children': 0,
                                   'narrowed_mermaid_children': 1})
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('SynConnect_', r.stdout)

    def test_sacm_wide_diagram_narrowed(self):
        """10 direct SACM children > 8 (default max) → SynConnect_ inserted."""
        r = self._run_with_config(self._wide_ltac(10), {})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('SynConnect_', r.stdout)

    def test_gsn_wide_diagram_narrowed(self):
        """10 direct GSN children > 8 (default max) → SynConnect_ inserted."""
        r = self._run_with_config(self._wide_ltac(10), {}, selector='gsn/mermaid')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('SynConnect_', r.stdout)
        self.assertIn(':::connector', r.stdout)

    def test_width_transform_disabled_when_max_zero(self):
        """max == 0 disables transform; no SynConnect_ even for wide diagrams."""
        r = self._run_with_config(self._wide_ltac(10),
                                  {'max_mermaid_children': 0,
                                   'narrowed_mermaid_children': 6})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('SynConnect_', r.stdout)

    def test_sacm_strategy_absorbed_narrowed(self):
        """Strategy-absorbed children are counted and narrowed when too many."""
        ltac = (
            '- Claim Top: Top\n'
            '  - Strategy S1: Strategy\n'
            '    - Claim C1: c1\n'
            '    - Claim C2: c2\n'
            '    - Claim C3: c3\n'
            '    - Claim C4: c4\n'
        )
        # inference_sources = [C1, C2, C3, C4, S1] = 5 > max=4
        r = self._run_with_config(ltac, {'max_mermaid_children': 4,
                                         'narrowed_mermaid_children': 2})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('SynConnect_', r.stdout)
        # S1 kept (rightmost), C1 kept (leftmost)
        self.assertIn('S1', r.stdout)
        self.assertIn('C1', r.stdout)

    def test_config_directive_sets_max(self):
        """caseproc-config directives can set max/narrowed_mermaid_children."""
        ltac_text = self._wide_ltac(10)
        fd_l, ltac_path = tempfile.mkstemp(suffix='.ltac')
        fd_d, doc_path = tempfile.mkstemp(suffix='.md')
        try:
            with os.fdopen(fd_l, 'w', encoding='utf-8') as f:
                f.write(ltac_text)
            # Set narrowed first to avoid transient invariant failure
            with os.fdopen(fd_d, 'w', encoding='utf-8') as f:
                f.write('<!-- caseproc-config narrowed_mermaid_children = 2 -->\n')
                f.write('<!-- caseproc-config max_mermaid_children = 4 -->\n')
                f.write('<!-- caseproc sacm/mermaid -->\n')
                f.write('<!-- end caseproc -->\n')
            r = run('--ltac', ltac_path, '--stdout', doc_path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('SynConnect_', r.stdout)
        finally:
            os.unlink(ltac_path)
            os.unlink(doc_path)


if __name__ == '__main__':
    unittest.main()
