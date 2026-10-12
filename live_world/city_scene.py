"""Read-only city scene projection for the isometric City View.

Contract (matches docs/DETROIT_3D_WORLD_ROADMAP.md): the Python simulation is
authoritative. This module only *reads* persisted engine state -- mobility
schedules and trips, careers, housing, health, world context -- and publishes
one versioned scene document. It never writes world state and never invents
events; the viewer animates the schedules the engine already reported.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "agentopia.city.scene.v1"


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _latest_profile(persona_dir: Path) -> dict[str, Any]:
    prof_dir = persona_dir / "profile"
    files = sorted(prof_dir.glob("year=*.json")) if prof_dir.exists() else []
    return _read(files[-1], {}) if files else {}


def _zone_kind(name: str, institution_zones: set[str], work_zones: set[str]) -> str:
    if name in institution_zones:
        return "campus"
    if name in {"O'Hare", "Midway"}:
        return "airport"
    if name in work_zones:
        return "work"
    return "residential"


def build_scene(root: Path, run: str = "detroit_persistent") -> dict[str, Any]:
    root = Path(root)
    scripts = root / "scripts"
    for p in (str(root), str(scripts)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import agentopia_city as city  # noqa: E402
    import detroit_mobility_time as mob  # noqa: E402  (constants only; no side effects)

    world = root / "data" / run
    mstate = _read(world / "mobility" / "state.json", {})
    msum = _read(world / "mobility" / "summary.json", {})
    career = (_read(world / "career" / "state.json", {}) or {}).get("citizens", {})
    health = (_read(world / "healthcare" / "state.json", {}) or {}).get("citizens", {})
    edu = (_read(world / "education" / "state.json", {}) or {}).get("citizens", {})
    hh = (_read(world / "human_economy" / "households.json", {}) or {}).get("households", {})
    housing = (_read(world / "human_economy" / "housing.json", {}) or {}).get("units", {})
    ctx = _read(world / "world_context" / "summary.json", {}) or _read(world / "world_context" / "state.json", {})

    member_hh = {}
    for hid, rec in hh.items():
        for n in (rec.get("members") or []):
            member_hh[n] = rec

    institution_zones = set(mob.INSTITUTION_ZONE.values())
    work_zones = set(mob.SECTOR_ZONE.values())
    neighborhoods = {}
    try:
        import detroit_human_economy as he  # noqa: E402
        neighborhoods = {n: float(i) for n, i in he.NEIGHBORHOODS}
    except Exception:
        pass

    zones = []
    for name, (x, y) in mob.ZONES.items():
        zones.append({
            "name": name, "x": float(x), "y": float(y),
            "kind": _zone_kind(name, institution_zones, work_zones),
            "rent_index": neighborhoods.get(name),
        })

    residents = []
    citizens = (mstate.get("citizens") or {}) if isinstance(mstate, dict) else {}
    persona_root = world / "persona"
    names = sorted(set(citizens) | {p.name for p in persona_root.iterdir() if p.is_dir()} if persona_root.exists() else set(citizens))
    for name in names:
        m = citizens.get(name, {})
        c = career.get(name, {})
        h = health.get(name, {})
        e = edu.get(name, {})
        prof = _latest_profile(persona_root / name)
        state = _read(persona_root / name / "state.json", {})
        house = member_hh.get(name, {})
        unit = housing.get(house.get("property_id"), {}) if house else {}
        deposit = state.get("deposit")
        if deposit is None:
            deposit = (prof.get("init_assets") or {}).get("deposit")
        residents.append({
            "id": hashlib.sha1(name.encode()).hexdigest()[:10],
            "name": name,
            "age": m.get("age") or h.get("age"),
            "gender": prof.get("gender"),
            "title": c.get("current_title") or (prof.get("position") or {}).get("role"),
            "organization": c.get("organization") or (prof.get("position") or {}).get("organization"),
            "sector": c.get("sector"),
            "status": c.get("status"),
            "education": e.get("education"),
            "enrollment": (e.get("active_enrollment") or {}).get("title") if isinstance(e.get("active_enrollment"), dict) else None,
            "home": m.get("home") or unit.get("neighborhood"),
            "home_type": unit.get("type"),
            "work": m.get("work_destination"),
            "school": m.get("school_destination"),
            "mode": m.get("primary_mode"),
            "vehicle": m.get("vehicle_label"),
            "shift": m.get("shift"),
            "avg_commute_minutes": m.get("avg_commute_minutes"),
            "economic_class": m.get("economic_class") or house.get("economic_class"),
            "health": {
                "physical": h.get("physical_health"), "mental": h.get("mental_wellbeing"),
                "stress": h.get("stress"), "sleep": h.get("sleep_quality"), "fitness": h.get("fitness"),
            },
            "money": deposit,
            "intro": (prof.get("brief_introduction") or "")[:280],
            "schedule": m.get("schedule") or [],
            "trips": m.get("trips") or [],
            "reported": bool(m),
        })

    lines = city.get("transit_lines", {}) or {}
    return {
        "ok": True,
        "schema": SCHEMA,
        "authority": "read-only projection of persisted engine state",
        "city": {
            "id": city.CITY_ID, "name": city.name(), "world_name": city.world_name(),
            "tagline": city.CITY.get("tagline", ""),
        },
        "engine": {
            "world_week": msum.get("world_week") or mstate.get("last_processed_week"),
            "engine_time": msum.get("engine_time"), "phase": msum.get("phase"),
            "city_clock": msum.get("city_clock"),
            "updated_at": msum.get("updated_at"),
        },
        "context": {
            "date_label": ((ctx.get("calendar_week") or {}).get("today_label")),
            "calendar_week": ctx.get("calendar_week"),
            "season": (ctx.get("season") or {}).get("name"),
            "weather": ctx.get("weather"),
            "daily_weather": ctx.get("daily_weather"),
            "holidays_this_week": [h.get("native_name") for h in (ctx.get("holidays_this_week") or [])],
        },
        "mobility": {
            "avg_commute_minutes": msum.get("avg_commute_minutes"),
            "transit_share_pct": msum.get("transit_share_pct"),
            "busiest_corridors": msum.get("busiest_corridors"),
            "modes": mob.MODES,
        },
        "map": city.get("map", {}),
        "transit_lines": lines.get("lines", []),
        "zones": zones,
        "residents": residents,
    }
