"""City packs: swap the city an Agentopia world is set in without forking the engine.

The engine was built for Detroit, and Detroit stays the default. A city pack
(``cities/<id>/city.json``) supplies:

* ``names``      -- ordered proper-noun rewrites applied to engine constants
                    (``"Motor City" -> "Windy City"``, then ``"Detroit" -> "Chicago"``).
* structural overrides (zones, corridors, transit modes, neighborhoods, ...)
  that modules read with :func:`get`.

Selection order: ``AGENTOPIA_CITY`` env var, then ``data/active_city`` (one
line, written by ``scripts/seed_city_world.py``), then ``detroit``.

Internal identifiers -- module file names, ``data/detroit_persistent``, ids such
as ``detroit_trades_academy`` -- are engine plumbing and are intentionally left
alone so upstream Detroit changes keep merging cleanly.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CITIES_DIR = ROOT / "cities"
DEFAULT_CITY = "detroit"


def _read_active_city() -> str:
    env = os.environ.get("AGENTOPIA_CITY", "").strip().lower()
    if env:
        return env
    marker = ROOT / "data" / "active_city"
    try:
        value = marker.read_text(encoding="utf-8").strip().lower()
        if value:
            return value
    except Exception:
        pass
    return DEFAULT_CITY


def _load(city_id: str) -> dict[str, Any]:
    path = CITIES_DIR / city_id / "city.json"
    if not path.exists():
        if city_id != DEFAULT_CITY:
            raise FileNotFoundError(f"City pack not found: {path}")
        return {"id": DEFAULT_CITY}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("id", city_id)
    return data


CITY_ID: str = _read_active_city()
CITY: dict[str, Any] = _load(CITY_ID)
IS_DEFAULT: bool = CITY_ID == DEFAULT_CITY

def _compile(rules: Any) -> list[tuple[Any, str]]:
    """Rules are ``[old, new]``. ``old`` starting with ``re:`` is a regex."""
    out: list[tuple[Any, str]] = []
    for a, b in rules or []:
        a, b = str(a), str(b)
        if not a or a == b:
            continue
        out.append((re.compile(a[3:]) if a.startswith("re:") else a, b))
    return out


_NAME_RULES = _compile(CITY.get("names"))


def name() -> str:
    """Display name of the city, e.g. ``Chicago``."""
    return str(CITY.get("name") or CITY_ID.title())


def world_name() -> str:
    """Display name of the world, e.g. ``Agentopia Chicago``."""
    return str(CITY.get("world_name") or f"Agentopia {name()}")


def get(path: str, default: Any = None) -> Any:
    """Dotted lookup into the pack (``get("mobility.zones", ZONES)``).

    Returns a deep copy so callers can mutate freely. Falls back to ``default``
    (the engine's built-in Detroit value) when the pack does not override it.
    """
    node: Any = CITY
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return copy.deepcopy(node)


def localize_text(text: str) -> str:
    if not _NAME_RULES or not isinstance(text, str):
        return text
    return _apply(_NAME_RULES, text)


def _apply(rules: list[tuple[Any, str]], text: str) -> str:
    for old, new in rules:
        if isinstance(old, str):
            if old in text:
                text = text.replace(old, new)
        else:
            text = old.sub(new, text)
    return text


def localize(obj: Any) -> Any:
    """Apply the pack's proper-noun rewrites to every string in ``obj``.

    Dict keys are rewritten too, except keys that look like internal ids
    (lowercase, no spaces) so state lookups such as ``'glcb'`` stay stable.
    """
    if not _NAME_RULES:
        return obj
    if isinstance(obj, str):
        return localize_text(obj)
    if isinstance(obj, list):
        return [localize(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(localize(x) for x in obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = k
            if isinstance(k, str) and (" " in k or k[:1].isupper()):
                key = localize_text(k)
            out[key] = localize(v)
        return out
    return obj


def localize_ui(text: str) -> str:
    """Rewrite Live World static UI text (UI-specific rules first, then names)."""
    return _apply(_compile(CITY.get("ui_replacements")) + _NAME_RULES, text)


__all__ = [
    "CITY", "CITY_ID", "IS_DEFAULT", "get", "localize", "localize_text",
    "name", "world_name", "localize_ui",
]
