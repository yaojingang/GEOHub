#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = (
    (sys.executable, "scripts/verify_repository.py"),
    (sys.executable, "scripts/verify_capability_contracts.py"),
    (sys.executable, "scripts/run_yao_meta_gates.py", "--verify-existing"),
    (sys.executable, "-m", "pytest"),
    (sys.executable, "scripts/run_evals.py"),
    (sys.executable, "scripts/package.py", "--target", "all", "--channel", "community"),
    (sys.executable, "scripts/verify_packages.py"),
    (sys.executable, "scripts/install_simulation.py", "--target", "all"),
    (sys.executable, "scripts/generate_sbom.py"),
    (sys.executable, "scripts/generate_provenance.py"),
    (sys.executable, "scripts/verify_provenance.py"),
    (sys.executable, "scripts/render_production_readiness.py"),
)


def main() -> int:
    for step in STEPS:
        print(f"[verify_all] {' '.join(step)}", flush=True)
        subprocess.run(step, cwd=ROOT, check=True)
    print("all repository gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
