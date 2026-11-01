"""FastMCP 2.x must not reach a Kenning Reach deployment by either route.

A deployment gets its FastMCP from one of two places: the image and `uv sync`
install the version uv.lock pins, and an install from the source resolves the
range pyproject.toml declares. Both are checked, because either one alone can
let 2.x back in while the other looks correct.
"""
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]


def _declared(name: str) -> Requirement:
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    matches = [Requirement(d) for d in deps if Requirement(d).name == name]
    assert len(matches) == 1, f"{name} must be declared exactly once"
    return matches[0]


def _locked(name: str) -> list[Version]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    return [Version(p["version"]) for p in lock["package"] if p["name"] == name]


def test_declared_fastmcp_range_admits_no_2x():
    spec = _declared("fastmcp").specifier
    assert not list(spec.filter(["2.0.0", "2.10.2", "2.14.9", "2.99.99"], prereleases=True))
    # The floor is the first release the critical advisory names as fixed.
    assert "3.1.9" not in spec
    assert "3.2.0" in spec


def test_locked_fastmcp_is_3_or_later():
    versions = _locked("fastmcp")
    assert versions, "fastmcp missing from uv.lock"
    assert all(v >= Version("3.2.0") for v in versions), versions
