# verocase: Simple Makefile to simplify local checking (run "make")
#
# The CI/CD process on the shared site is defined in
# .github/workflows/ci.yml

.PHONY: verify test lint typecheck

verify: lint typecheck test

lint:
	ruff check verocase.py

typecheck:
	pyright verocase.py

test:
	python3 -m unittest tests.run_tests
