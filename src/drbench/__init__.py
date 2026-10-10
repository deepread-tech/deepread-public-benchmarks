"""drbench — run commercial document extraction APIs on public benchmarks, with
each vendor's default settings and list prices, and score them the same way.

    drbench systems                              what is run: vendor, product, settings, price
    drbench fetch DATASET                        download a benchmark
    drbench run DATASET SYSTEM [SYSTEM ...]      call the APIs on every document (paid)
    drbench grade DATASET                        score the saved outputs (offline)
    drbench report [--readme README.md]          results tables (offline)
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"


def repo_root() -> Path:
    """The checkout this package runs from: the shipped `datasets/` files live there."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "datasets").is_dir():
            return parent
    return Path.cwd()
