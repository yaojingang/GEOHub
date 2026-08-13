#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.quality.release import verify_release_provenance  # noqa: E402
from geo_seo_hub.release_manifest import build_release_manifest  # noqa: E402
from geo_seo_hub.validation import strict_json_loads  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--sbom", type=Path, default=ROOT / "reports" / "release-sbom.json")
    parser.add_argument("--provenance", type=Path, default=ROOT / "reports" / "release-provenance.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "release-provenance-verification.json")
    args = parser.parse_args()
    try:
        sbom = strict_json_loads(args.sbom.read_text(encoding="utf-8"))
        provenance = strict_json_loads(args.provenance.read_text(encoding="utf-8"))
        result = verify_release_provenance(
            ROOT,
            provenance,
            sbom,
            artifact_root=args.dist,
            expected_artifact_names=build_release_manifest(ROOT)["archive_names"],
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "fail", "message": str(exc)}, ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
