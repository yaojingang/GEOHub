from __future__ import annotations

import json
import math
import os
import stat
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .paths import repository_root


class ArtifactValidationError(ValueError):
    """Raised when an artifact does not satisfy its protocol schema."""


def strict_json_loads(value: str | bytes | bytearray) -> Any:
    def reject_constant(constant: str) -> Any:
        raise ValueError(f"non-standard JSON constant is not allowed: {constant}")

    parsed = json.loads(value, parse_constant=reject_constant)
    pending = [parsed]
    while pending:
        item = pending.pop()
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("non-finite JSON number is not allowed")
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return parsed


def _trusted_absolute_components(candidate: Path) -> tuple[str, ...]:
    components = candidate.parts[1:]
    if not components or components[0] != "var":
        return components
    alias = Path("/var")
    target = Path("/private/var")
    try:
        alias_stat = os.lstat(alias)
        target_stat = os.lstat(target)
        link_target = os.readlink(alias)
    except OSError:
        return components
    lexical_target = Path("/") / link_target if not Path(link_target).is_absolute() else Path(link_target)
    if (
        stat.S_ISLNK(alias_stat.st_mode)
        and stat.S_ISDIR(target_stat.st_mode)
        and not stat.S_ISLNK(target_stat.st_mode)
        and os.path.normpath(lexical_target) == str(target)
    ):
        return ("private", "var", *components[1:])
    return components


def read_bounded_regular_file(path: Path, *, max_bytes: int, field: str) -> bytes:
    """Read one lexical path through no-follow directory/file descriptors."""
    candidate = Path(path)
    if max_bytes < 0 or ".." in candidate.parts:
        raise ValueError(f"{field} path is unsafe")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    descriptors: list[int] = []
    try:
        if candidate.is_absolute():
            current = os.open(candidate.anchor, directory_flags)
            components = _trusted_absolute_components(candidate)
        else:
            current = os.open(".", directory_flags)
            components = candidate.parts
        descriptors.append(current)
        if not components or any(component in {"", ".", ".."} for component in components):
            raise ValueError(f"{field} path is unsafe")
        for component in components[:-1]:
            current = os.open(component, directory_flags, dir_fd=current)
            descriptors.append(current)
        file_descriptor = os.open(components[-1], file_flags, dir_fd=current)
        descriptors.append(file_descriptor)
        file_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError(f"{field} must be a regular file")
        if file_stat.st_size > max_bytes:
            raise ValueError(f"{field} exceeds {max_bytes} bytes")
        chunks: list[bytes] = []
        count = 0
        while True:
            chunk = os.read(file_descriptor, min(64 * 1024, max_bytes + 1 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
            if count > max_bytes:
                raise ValueError(f"{field} exceeds {max_bytes} bytes")
        return b"".join(chunks)
    except OSError as exc:
        raise ValueError(f"{field} is unavailable or unsafe: {path}") from exc
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def load_json(
    path: Path,
) -> dict[str, Any]:
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactValidationError(f"Unable to load JSON from {path}: {exc}") from exc


def load_bounded_json(path: Path, *, max_bytes: int, field: str) -> dict[str, Any]:
    try:
        return strict_json_loads(
            read_bounded_regular_file(path, max_bytes=max_bytes, field=field).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise ArtifactValidationError(f"Unable to load JSON from {path}: {exc}") from exc


def load_schema(name: str) -> dict[str, Any]:
    return load_json(repository_root() / "schemas" / f"{name}.schema.json")


def validate_artifact(name: str, artifact: dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema(name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ArtifactValidationError(f"{name} validation failed: {details}")
