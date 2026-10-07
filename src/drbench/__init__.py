"""drbench — run public structured-extraction benchmarks against document AI APIs.

    drbench fetch <dataset>                    download a dataset (your own token where needed)
    drbench run --dataset D --system S         call one API on every document (paid)
    drbench grade --dataset D                  score the saved outputs (offline)
    drbench report                             leaderboard tables from the scores (offline)
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
