#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fastembed import TextEmbedding


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _cache_digest(cache_dir: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in cache_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError("semantic model cache is empty after preparation")
    for path in files:
        digest.update(path.relative_to(cache_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True, type=Path)
    args = parser.parse_args()
    cache_dir = args.cache_dir.resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache_dir))
    vectors = list(model.embed(["GEOHub semantic model readiness probe"]))
    if len(vectors) != 1:
        raise ValueError("semantic model readiness probe failed")
    result = {
        "status": "prepared",
        "model_id": MODEL_NAME,
        "cache_dir": str(cache_dir),
        "cache_sha256": _cache_digest(cache_dir),
        "dimension": len(vectors[0]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
