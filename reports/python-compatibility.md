# Python Compatibility

Status: **pass**

The supported range is Python 3.11-3.14 (`>=3.11,<3.15`). CI declares 3.11, 3.12, 3.13, and 3.14. CI declaration is pending hosted execution for this commit; local fresh-environment evidence covers every supported minor.

- Python 3.11.14: fresh virtual environment, `pip install -e '.[dev]'`, 371 targeted router, research, measurement, secure I/O, and schema tests passed.
- Python 3.12.3: the same 371 targeted tests passed in a fresh virtual environment.
- Python 3.13.3: the same 371 targeted tests passed in a fresh virtual environment using the system CA bundle for dependency installation.
- Python 3.14.6: the same 371 targeted tests passed in a fresh virtual environment.

Each environment also passed 373 router cases, 33 trigger cases, and 25 deterministic output cases with precision, recall, trigger compliance, and contract compliance all at 1.0; fabricated citations remained 0.
