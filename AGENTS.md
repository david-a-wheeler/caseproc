# verocase AGENTS.md

The script `verocase` is a Python3 script for processing
our extended version of Lightweight Text Assurance Case (LTAC) format
and generating useful results to enable easy documentation and revision
of assurance cases.

To run our test suite, run:

> tests/run_tests.py

Run `./verocase --help` to see how to execute it.

If you're running on Linux or MacOS, don't add a `python3` or `python`
prefix to run `tests/run_tests.py` or `verocase`, that's not necessary.

See README.md for more.

## Key architecture notes for AI assistants

`verocase` is a **single Python3 script**. All logic lives there.
We intentionally avoid adding any dependencies not built into Python to
simplify deployment.

`DEFAULT_CONFIG` is the authoritative registry of valid configuration keys.
`load_config` rejects unknown keys with a warning, so any new configuration
option must be added to `DEFAULT_CONFIG` first.

All render functions write to a `TextIO` stream (`out`) rather than returning
strings, and return `bool` (True if anything was written).  The call
signatures are:

- Diagram renderers: `render_markdown`, `render_html`, `render_sacm`,
  `render_sacm_html`, `render_gsn`, `render_gsn_html` →
  `(roots: List[Node], config: dict, out: TextIO) -> bool`
- Selection renderers: `render_referenced_by`, `render_supported_by`,
  `render_supports`, `render_pkg_defines`, `render_pkg_citing`,
  `render_pkg_cited`, `render_ltac_txt`, `render_info`,
  `render_representation` → accept `out: TextIO` and `sep: str = ''`
  (the separator to write before the first byte of content, only if
  content is produced).
- Assemblers: `render_element_selector`, `_render_single_package`,
  `render_package_selector`, `render_selector` → accept `out: TextIO`.
- `_apply_selections` accepts `out: TextIO` and `pending_sep: str = ''`.

Do not return content as strings from these functions.  Use `io.StringIO()`
at the call site when a string is genuinely needed (e.g. in `_fixmissing`).

Do not add individual keyword parameters for config-driven behaviour; add
the key to `DEFAULT_CONFIG` and read it from `config` inside the function.

Changing rendered output requires updating the corresponding golden files in
`tests/fixtures/`. Run `tests/run_tests.py` to verify. To accept all
differing test results as the new expected values, run `tests/accept_tests`.
