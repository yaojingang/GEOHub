"""Evidence-bound content pipeline and MCDA utilities."""

from .claims import build_claim_map
from .drafting import build_content_pipeline
from .mcda import evaluate_mcda
from .outline import build_outline, build_perspective_plan
from .research_bundle import build_research_bundle

__all__ = [
    "build_claim_map",
    "build_content_pipeline",
    "build_outline",
    "build_perspective_plan",
    "build_research_bundle",
    "evaluate_mcda",
]
