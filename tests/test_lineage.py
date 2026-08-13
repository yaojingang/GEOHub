import json
from pathlib import Path

from geo_seo_hub.content import content
from geo_seo_hub.diagnose import diagnose
from geo_seo_hub.discover import discover
from geo_seo_hub.measure import measure
from geo_seo_hub.validation import validate_artifact


FIXTURES = Path(__file__).parent / "fixtures"


def test_all_executors_publish_metadata_only_lineage(tmp_path):
    runs = [
        discover(FIXTURES / "brief.json", tmp_path / "discover"),
        diagnose(FIXTURES / "diagnosis-brand.json", tmp_path / "diagnose"),
        content(Path(__file__).parents[1] / "skills/geo-content/references/input-example.json", tmp_path / "content"),
        measure(FIXTURES / "engine-observation-bundle.json", tmp_path / "measure"),
    ]
    forbidden = ("prompt", "answer_text", "customer", "source_uri", str(tmp_path))
    for result in runs:
        run = Path(result["output"])
        lineage = json.loads((run / "run-lineage.json").read_text(encoding="utf-8"))
        validate_artifact("run-lineage", lineage)
        assert lineage["run_id"] == result["run_id"]
        assert lineage["data_class"] == "L2"
        assert lineage["events"][0]["status"] in {"completed", "completed-with-warnings"}
        assert lineage["events"][0]["artifact_hashes"]
        serialized = json.dumps(lineage, ensure_ascii=False)
        assert all(term not in serialized for term in forbidden)
        manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))
        assert "run-lineage.json" in manifest["artifacts"]


def test_lineage_hashes_match_published_artifacts(tmp_path):
    import hashlib

    result = measure(FIXTURES / "engine-observation-bundle.json", tmp_path / "runs")
    run = Path(result["output"])
    lineage = json.loads((run / "run-lineage.json").read_text(encoding="utf-8"))
    hashes = lineage["events"][0]["artifact_hashes"]
    assert hashes == {
        relative: hashlib.sha256((run / relative).read_bytes()).hexdigest()
        for relative in hashes
    }
