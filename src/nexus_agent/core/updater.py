"""
Self-updater — version checking against PyPI.

`get_installed_version()` reads the installed `nexus_agent.__version__`
(or falls back to `importlib.metadata` if the attribute is missing).
`check_for_update()` queries the PyPI JSON API with a short timeout and
compares the result. Both functions never raise on network failure —
they return safe defaults so the caller can show a friendly message.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from importlib import metadata as importlib_metadata

import httpx

import nexus_agent

logger = logging.getLogger(__name__)


PYPI_URL = "https://pypi.org/pypi/nexus-agent/json"
DEFAULT_TIMEOUT_S = 10.0


def _parse_version(s: str) -> tuple[int, ...]:
    """Parse a PEP 440 version string into a comparable tuple.

    Falls back to (0,) for anything unparseable so missing values sort
    below real ones.
    """
    if not s:
        return (0,)
    m = re.match(r"^\s*(\d+(?:\.\d+)*)", s)
    if not m:
        return (0,)
    return tuple(int(x) for x in m.group(1).split("."))


def get_installed_version(package: str = "nexus-agent") -> str:
    """Return the installed version of `package`.

    Tries the distribution metadata first (works for editable installs
    too) and falls back to the `nexus_agent.__version__` attribute.
    Raises `OSError`/`ValueError`/`ImportError` on hard failure.
    """
    try:
        return importlib_metadata.version(package)
    except importlib_metadata.PackageNotFoundError:
        pass
    # Fall back to the module's own version attribute.
    version = getattr(nexus_agent, "__version__", None)
    if version:
        return str(version)
    raise ValueError(f"Could not determine installed version of {package!r}")


@dataclass(frozen=True)
class UpdateInfo:
    """Result of a version check."""

    available: bool
    current: str
    latest: str | None = None
    error: str | None = None


def check_for_update(
    current: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    package: str = "nexus-agent",
) -> UpdateInfo:
    """Compare `current` against the latest PyPI release.

    On any network/HTTP/JSON failure, returns `UpdateInfo(available=False)`
    with `error` populated. Never raises.
    """
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return UpdateInfo(
                available=False,
                current=current,
                error=f"HTTP {resp.status_code} from PyPI",
            )
        data = resp.json()
    except (httpx.HTTPError, OSError, ValueError) as e:
        return UpdateInfo(available=False, current=current, error=str(e))

    latest = (data.get("info") or {}).get("version", "")
    if not latest:
        return UpdateInfo(available=False, current=current, error="No version in PyPI response")

    cur_tuple = _parse_version(current)
    new_tuple = _parse_version(latest)
    if new_tuple > cur_tuple:
        return UpdateInfo(available=True, current=current, latest=latest)

    return UpdateInfo(available=False, current=current, latest=latest)
