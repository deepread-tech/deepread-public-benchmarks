from __future__ import annotations

from .base import Provider
from .deepread import DeepRead
from .landingai import LandingAI
from .reducto import Reducto

PROVIDERS = {"deepread": DeepRead, "reducto": Reducto, "landingai": LandingAI}


def make(system: str) -> Provider:
    """`<provider>` or `<provider>:<pipeline>`, e.g. `deepread:extract`, `reducto`."""
    provider, _, pipeline = system.partition(":")
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; choose from {', '.join(PROVIDERS)}")
    cls = PROVIDERS[provider]
    return cls(pipeline) if pipeline else cls()


__all__ = ["PROVIDERS", "Provider", "make"]
