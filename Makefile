PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHON314 ?= python3.14

.PHONY: install test eval repo-verify verify package package-verify install-smoke release-evidence python314-smoke ci clean

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest
	$(PYTHON) scripts/run_evals.py

eval:
	$(PYTHON) scripts/run_evals.py

repo-verify:
	$(PYTHON) scripts/verify_repository.py

verify:
	$(PYTHON) scripts/verify_all.py

package:
	$(PYTHON) scripts/package.py --target all --channel community

package-verify: package
	$(PYTHON) scripts/verify_packages.py

install-smoke: package-verify
	$(PYTHON) scripts/install_simulation.py --target all

release-evidence: install-smoke
	$(PYTHON) scripts/generate_sbom.py
	$(PYTHON) scripts/generate_provenance.py
	$(PYTHON) scripts/verify_provenance.py
	$(PYTHON) scripts/render_production_readiness.py

python314-smoke:
	$(PYTHON314) -m pytest tests/test_router.py tests/test_library_integration.py
	$(PYTHON314) scripts/run_evals.py

ci: verify

clean:
	rm -rf build dist .pytest_cache htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
