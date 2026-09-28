"""Application version exposed by the API and dashboard.

The project version is defined once in pyproject.toml. Runtime code reads the
installed package metadata first, with a source-tree fallback for development.
"""

from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
import tomllib


def _project_version() -> str:
    try:
        return package_version("ManubisGuard")
    except PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with pyproject.open("rb") as file:
            return tomllib.load(file)["project"]["version"]


__version__ = _project_version()
