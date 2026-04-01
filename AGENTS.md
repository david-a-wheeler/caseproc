# AGENTS.md

This file provides guidance to AI coding assistants when working with code in this repository.

## What This Project Is

Verocase is a command-line tool for creating and maintaining assurance cases, that is, structured arguments (with supporting evidence) that a system has properties like safety, security, or privacy. It reads a simple indented text format called LTAC (Lightweight Text Assurance Case) and updates Markdown/HTML documentation with embedded Mermaid diagrams in GSN, SACM, or CAE notation. It has zero third-party dependencies (besides optional `tomli` for Python < 3.11).

## Commands

**Run all checks (lint + type check + tests):**
```bash
make verify
```

**Run linter only:**
```bash
ruff check verocase.py
```

**Run type checker only:**
```bash
pyright verocase.py
```

**Run tests:**
```bash
python3 -m unittest tests.run_tests -v   # verbose
python3 -m unittest tests.run_tests      # compact
```

**Accept test results as new expected outputs:**
```bash
tests/accept_tests
```

**Run the tool:**
```bash
python3 verocase.py [options] [files]
python3 verocase.py --help
python3 verocase.py --start              # create starter case.ltac / case.md
```

**Install (for development):**
```bash
pip install flit
flit install --symlink
```

## Architecture

The entire implementation lives in a single file: `verocase.py`. This is intentional, because it keeps installation trivial.

### Core Data Model

- **`Node`**: one element in the assurance case forest of trees. Key fields: `node_type`, `identifier`, `text`, `ext_ref`, `options`, `parent`, `children`. Node types include Claim, Strategy, Evidence, Justification, Context, Assumption, Link, Relation, Connector.
- **`Case`**: the loaded assurance case. Key fields:
  - `roots`: package root nodes in LTAC file order. Each is Node is the head of a tree of Nodes
  - `all_definitions_for`: id → defining Node(s). An error-free LTAC has only 1 definition for each id
  - `citations`: id → citation Nodes
  - `links`: id → Link Nodes
  - `document_files`: list of Markdown/HTML output paths
  - `config`: merged configuration dict

### Processing Pipeline

This can be used as a library or as a CLI. When used as a CLI:

1. `main` calls `run(parse_args())`
2. `run` calls case = Case().load(...), which creates the Case instance,
   then loads the config and LTAC file.
   LTAC file loading is done by `_LTACParser` which parses the `.ltac`
   file into a forest of `Node` instances
3. In most cases document processing eventually occurs. Document files with `<!-- verocase SELECTOR --> ... <!-- end verocase -->` regions are by default updated in-place; content outside those regions is preserved.

Some important methods:

* `Case.validate()`: runs validation checks (cycles, coverage, etc.)
* `render_*()` functions: produce output in Markdown, HTML, SACM, GSN, or CAE (Mermaid) formats

### Tests

Tests live in `tests/run_tests.py` (unittest) with fixture data in `tests/fixtures/`. Each test scenario has a `.ltac` input, optional `.md` input, and `.expected.*` files for each output. Failures are written to `tests/results/` for review. Run `tests/accept_tests` to promote results to new expected outputs.

### Configuration

Config is loaded from the first of these found: `verocase.toml`, `docs/verocase.toml`, `case.toml`, `docs/case.toml`. Defaults are in `DEFAULT_CONFIG` (an immutable `MappingProxyType`).

`DEFAULT_CONFIG` is the authoritative registry of valid configuration keys. `load_config` rejects unknown keys with a warning, so any new configuration option must be added to `DEFAULT_CONFIG` first. Do not add individual keyword parameters for config-driven behaviour; add the key to `DEFAULT_CONFIG` and read it from `config` inside the function.

### Render functions

Render functions write to a `TextIO` stream (`out`) rather than returning strings, and return `bool` (True if anything was written). Do not return content as strings from these functions; use `io.StringIO()` at the call site when a string is genuinely needed (e.g. in `_fixmissing`).

### Python Version Compatibility

Supports Python 3.8-3.13. Use `Optional[X]` not `X | None`, use `List[X]`/`Dict[K,V]` not `list[X]`/`dict[K,V]`. Walrus operator (`:=`) is fine.

### Version Number

The version string is defined near the top of `verocase.py`.

## Style

Never use em dashes (long dashes) in any written text; use semicolons or parentheses instead. Never use `--` as a separator between text phrases. Note: `--` as a CLI long-option prefix is fine.

## Documentation

The `docs/` directory includes documentation.

- `docs/ltac-extended.txt`: the formal LTAC specification. Consult it for LTAC syntax requirements.
- `docs/tutorial.md`: the user tutorial. Keep it up-to-date when the user interface changes.
- `docs/reference.md`: the reference manual. Keep it up-to-date when the user interface changes.

The tool also has built-in help (`--help`, `--help-validations`, `--help-config`, `--help-api`, `--help-security`, etc.) implemented in `verocase.py`. Keep the built-in help up-to-date when the user interface changes; it lets users and AI quickly understand the tool without consulting a separate file.
