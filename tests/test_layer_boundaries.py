"""Static layer-boundary guard (SC-003/SC-004).

Asserts the domain package stays pure: no imports of ``app`` or
``infrastructure``, no ``subprocess``, no ``os.environ`` reads, no
``os.path.realpath`` calls, and exactly one layer per behavioral module.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "multi_sessionizer"
DOMAIN = SRC / "domain"

LAYER_MODULES = {
    "domain",
    "app",
    "infrastructure",
    "main",
}

FORBIDDEN_IN_DOMAIN = (
    (re.compile(r"\bsubprocess\b"), "subprocess import"),
    (re.compile(r"os\.environ"), "os.environ read"),
    (re.compile(r"os\.path\.realpath"), "os.path.realpath call"),
    (re.compile(r"multi_sessionizer\.app\b"), "app import"),
    (re.compile(r"multi_sessionizer\.infrastructure\b"), "infrastructure import"),
    (re.compile(r"\bfrom\s+\.?\.?\s*app\b"), "app import"),
    (re.compile(r"\bfrom\s+\.?\.?\s*infrastructure\b"), "infrastructure import"),
    (re.compile(r"\bimport\s+app\b"), "app import"),
    (re.compile(r"\bimport\s+infrastructure\b"), "infrastructure import"),
)


def _modules(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.name != "__init__.py")


def test_domain_has_no_side_effects_or_cross_layer_imports():
    modules = _modules(DOMAIN)
    assert modules, "domain package has no behavioral modules"
    for mod in modules:
        text = mod.read_text()
        for pattern, label in FORBIDDEN_IN_DOMAIN:
            assert not pattern.search(text), f"{mod}: {label} forbidden in domain"


def test_every_behavioral_module_has_exactly_one_layer():
    for root in (SRC / "domain", SRC / "app", SRC / "infrastructure"):
        for mod in _modules(root):
            rel = mod.relative_to(SRC).as_posix()
            layers = [layer for layer in LAYER_MODULES if f"/{layer}/" in f"/{rel}"]
            assert len(layers) == 1, f"{mod}: expected exactly one layer, found {layers}"
