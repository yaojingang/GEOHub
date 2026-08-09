# Python Compatibility

Status: **pass**

The supported range is Python 3.11-3.14 (`>=3.11,<3.15`). CI declares 3.11, 3.12, 3.13, and 3.14. CI declaration is pending hosted execution for this commit; local fresh-environment evidence is recorded below for 3.12 and 3.14.

- Python 3.12.3: fresh virtual environment, `pip install -e '.[dev]'`, 335 targeted router/library integration tests, 373 router eval cases, and deterministic output gates passed.
- Python 3.14.6: fresh virtual environment, `pip install -e '.[dev]'`, 335 targeted router/library integration tests, 373 router eval cases, and deterministic output gates passed. Recheck with `make python314-smoke`.
