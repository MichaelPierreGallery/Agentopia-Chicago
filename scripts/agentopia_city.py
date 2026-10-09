"""Shim so ``scripts/`` modules can ``import agentopia_city as city``."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.city_pack import *  # noqa: E402,F401,F403
from src.city_pack import CITY, CITY_ID, IS_DEFAULT, get, localize, localize_text, name, world_name, localize_ui  # noqa: E402,F401
