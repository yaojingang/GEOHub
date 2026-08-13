from __future__ import annotations

from typing import Any, Protocol


class Judge(Protocol):
    """Public seam for an independent rubric judge."""

    def judge(self, pair: dict[str, Any]) -> dict[str, Any] | None: ...


class MissingEvidenceJudge:
    """Default judge that preserves the absence of independent evidence."""

    def judge(self, pair: dict[str, Any]) -> None:
        del pair
        return None
