"""GEOHub protocol-first workflow toolkit."""

from .discover import discover
from .content import content
from .router import route
from .version import package_version

__all__ = ["content", "discover", "route"]
__version__ = package_version()
