from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .paths import repository_root


def package_version() -> str:
    """Return the installed distribution version, with a source-tree fallback."""

    try:
        return version("geo-seo-hub")
    except PackageNotFoundError:
        version_file = repository_root() / "VERSION"
        if not version_file.is_file():
            raise RuntimeError("geo-seo-hub version metadata is unavailable") from None
        value = version_file.read_text(encoding="utf-8").strip()
        if not value:
            raise RuntimeError("VERSION must not be empty")
        return value
