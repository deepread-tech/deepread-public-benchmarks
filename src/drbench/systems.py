"""Every system the benchmark runs: one vendor product, called with the vendor's
default settings, priced at the vendor's published pay-as-you-go list price.

This file is the whole configuration. A system may set only the one option that
selects a product the vendor sells under its own name and price (for example
Reducto's `deep_extract` flag for Deep Extract); everything else is left to the
vendor's defaults. Nothing here is tuned for a benchmark.

Prices were read from each vendor's public pricing page on `PRICES_CHECKED`.
Vendors that bill per page are costed at `pages × per_1k_pages / 1000`. Vendors
that bill in credits are costed from the credits the API reports for each job,
times the list price of a credit, so the cost is what the vendor actually charged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PRICES_CHECKED = "2026-10-09"


@dataclass(frozen=True)
class Price:
    per_1k_pages: float | None = None  # flat list price, USD per 1,000 pages
    per_credit: float | None = None  # USD per credit, for vendors that bill in credits
    source: str = ""

    def cost(self, pages: int | None, credits: float | None) -> float | None:
        if self.per_credit is not None:
            return None if credits is None else credits * self.per_credit
        if self.per_1k_pages is not None and pages:
            return pages * self.per_1k_pages / 1000
        return None


@dataclass(frozen=True)
class System:
    id: str  # used on the command line and as the run directory name
    vendor: str
    product: str  # the vendor's own name for what is being run
    adapter: str  # module in drbench/providers/
    settings: dict[str, Any] = field(default_factory=dict)  # the only options sent besides file and schema
    price: Price = field(default_factory=Price)
    key_env: str = ""


DEEPREAD_PRICES = "https://deepread.tech/pricing"
REDUCTO_PRICES = "https://reducto.ai/pricing"
EXTEND_PRICES = "https://www.extend.ai/pricing"
LANDINGAI_PRICES = "https://landing.ai/pricing"

SYSTEMS: dict[str, System] = {
    s.id: s
    for s in (
        System(
            "deepread-extract", "DeepRead", "Extract", "deepread",
            settings={"pipeline": "extract"},
            price=Price(per_1k_pages=15, source=DEEPREAD_PRICES), key_env="DEEPREAD_API_KEY",
        ),
        System(
            "deepread-deep-extract", "DeepRead", "Deep Extract", "deepread",
            settings={"pipeline": "deep-extract"},
            price=Price(per_1k_pages=35, source=DEEPREAD_PRICES), key_env="DEEPREAD_API_KEY",
        ),
        System(
            "reducto-extract", "Reducto", "Extract", "reducto",
            price=Price(per_1k_pages=20, source=REDUCTO_PRICES), key_env="REDUCTO_API_KEY",
        ),
        System(
            "reducto-deep-extract", "Reducto", "Deep Extract", "reducto",
            settings={"deep_extract": True},
            price=Price(per_1k_pages=40, source=REDUCTO_PRICES), key_env="REDUCTO_API_KEY",
        ),
        System(
            "extend-performance", "Extend", "Extract (Performance)", "extend",
            price=Price(per_credit=0.0125, source=EXTEND_PRICES), key_env="EXTEND_API_KEY",
        ),
        System(
            "extend-operator", "Extend", "Operator", "extend",
            settings={"baseProcessor": "extraction_operator"},
            price=Price(per_credit=0.0125, source=EXTEND_PRICES), key_env="EXTEND_API_KEY",
        ),
        System(
            "landingai-ade", "LandingAI", "Agentic Document Extraction", "landingai",
            price=Price(per_credit=0.01, source=LANDINGAI_PRICES), key_env="VISION_AGENT_API_KEY",
        ),
    )
}


def get(system_id: str) -> System:
    if system_id not in SYSTEMS:
        raise SystemExit(f"unknown system {system_id!r}; choose from: {', '.join(SYSTEMS)}")
    return SYSTEMS[system_id]
