# caseproc AGENTS.md

The script `caseproc` is a Python3 script for processing
our extended version of Lightweight Text Assurance Case (LTAC) format
and generating useful results to enable easy documentation and revision
of assurance cases.

To run our test suite, run:

> tests/run_tests.py

Run `./caseproc --help` to see how to execute it.

If you're running on Linux or MacOS, don't add a `python3` or `python`
prefix to run `tests/run_tests.py` or `caseproc`, that's not necessary.

See README.md for more.

## Key architecture notes for AI assistants

`caseproc` is a **single Python3 script**. All logic lives there.
We intentionally avoid adding any dependencies not built into Python to
simplify deployment.

`DEFAULT_CONFIG` is the authoritative registry of valid configuration keys.
`load_config` rejects unknown keys with a warning, so any new configuration
option must be added to `DEFAULT_CONFIG` first.

All top-level render functions (`render_markdown`, `render_html`,
`render_sacm`, `render_gsn`) take `(roots: List[Node], config: dict)` and
extract whatever they need from `config` internally. Do not add individual
keyword parameters for config-driven behaviour; add the key to `DEFAULT_CONFIG`
and read it from `config` inside the function.

Changing rendered output requires updating the corresponding golden files in
`tests/fixtures/`. Run `tests/run_tests.py` to verify. To accept all
differing test results as the new expected values, run `tests/accept_tests`.
