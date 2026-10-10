from __future__ import annotations

from ..systems import System
from .base import Adapter
from .deepread import DeepRead
from .extend import Extend
from .landingai import LandingAI
from .reducto import Reducto

ADAPTERS = {"deepread": DeepRead, "reducto": Reducto, "extend": Extend, "landingai": LandingAI}


def adapter(system: System) -> Adapter:
    return ADAPTERS[system.adapter](system.settings)


__all__ = ["ADAPTERS", "Adapter", "adapter"]
