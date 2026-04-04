# CONTRIBUTING.md

We love contributions! Please do!

Contributors must agree to the [MIT license](LICENSE.md).

## Set up for development

Install some tools for development. Install Python3, then:

```bash
pip install flit
flit install --symlink
```

## Development commands

You can run all checks with this (if you have make):

**Run all checks (lint + type check + tests):**
```bash
make verify
```

## Architecture

The entire implementation lives in a single file: `verocase.py`. This is intentional, because it keeps installation trivial.

See the file [AGENTS.md](./AGENTS.md) for more about its architecture. We put the information there to ensure that AI agents will find it.

## Documentation

The `docs/` directory includes documentation.

The tool also has built-in help (`--help`, `--help-validations`, `--help-config`, `--help-api`, `--help-security`, etc.) implemented in `verocase.py`. Keep the built-in help up-to-date when the user interface changes; it lets users and AI quickly understand the tool without consulting a separate file.
