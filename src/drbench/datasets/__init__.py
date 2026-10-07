from __future__ import annotations

from .base import Column, Dataset, Doc
from .charity import Charity
from .docile import Docile
from .longextract import LongExtract

DATASETS: dict[str, Dataset] = {d.name: d for d in (Charity(), Docile(), LongExtract())}

__all__ = ["DATASETS", "Column", "Dataset", "Doc"]
