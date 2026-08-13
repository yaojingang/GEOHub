#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_seo_hub.quality.release import build_provenance  # noqa: E402
from geo_seo_hub.release_manifest import build_release_manifest  # noqa: E402
from geo_seo_hub.validation import strict_json_loads  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--sbom", type=Path, default=ROOT / "reports" / "release-sbom.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "release-provenance.json")
    args = parser.parse_args()
    release = build_release_manifest(ROOT)
    version = release["version"]
    artifacts = sorted(args.dist / name for name in release["archive_names"] if (args.dist / name).is_file())
    if len(artifacts) != release["archive_count"]:
        raise SystemExit(f"provenance generation requires {release['archive_count']} version {version} ZIPs; found {len(artifacts)}")
    sbom = strict_json_loads(args.sbom.read_text(encoding="utf-8"))
    payload = build_provenance(ROOT, artifacts, sbom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "artifacts": len(artifacts), "builder": "local-unsigned", "output": args.output.relative_to(ROOT).as_posix()}, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
