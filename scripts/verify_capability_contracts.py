#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.control.capabilities import verify_capability_contracts  # noqa: E402


def main() -> int:
    result = verify_capability_contracts(ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
