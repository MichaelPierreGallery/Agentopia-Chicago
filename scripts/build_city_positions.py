#!/usr/bin/env python3
"""Build positions.json for a seeded city world without a god-model call.

On a fresh world the engine asks the strategy model to design every job in
one JSON reply. Small strategy models cannot finish that inside their token
budget, so world startup fails. This script builds the same file
deterministically instead:

  * every resident keeps the job already in their profile (merged by
    organization/role, with occupied_by filled in), and
  * the city pack's "positions.openings" list adds vacancies, trimmed so total
    capacity stays within the engine's 1.0x-1.5x population band.

It writes data/<city>/positions.json and data/detroit_persistent/positions.json
(the persistent world reads its own copy). Existing files are left alone unless
--force is given.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PERSISTENT = DATA / "detroit_persistent"


def _position_from_profile(pos: dict) -> dict | None:
    org = str(pos.get("organization") or "").strip()
    role = str(pos.get("role") or "").strip()
    if not org or not role:
        return None
    return {
        "organization": org,
        "role": role,
        "type": str(pos.get("type") or "work"),
        "description": str(pos.get("description") or "").strip(),
        "weekly_income": int(round(float(pos.get("weekly_income") or 0))),
        "weekly_delta_skills": dict(pos.get("weekly_delta_skills") or {}),
        "capacity": 0,
        "occupied_by": [],
    }


def build_positions(world: Path, openings: list[dict]) -> list[dict]:
    positions: dict[str, dict] = {}
    residents = 0
    for person in sorted(p for p in (world / "persona").iterdir() if p.is_dir()):
        if (person / "_background.json").exists():
            continue
        residents += 1
        for prof_path in sorted((person / "profile").glob("*.json")):
            prof = json.loads(prof_path.read_text(encoding="utf-8"))
            pos = _position_from_profile(prof.get("position") or {})
            if not pos:
                continue
            key = f"{pos['organization']}/{pos['role']}"
            entry = positions.setdefault(key, pos)
            if person.name not in entry["occupied_by"]:
                entry["occupied_by"].append(person.name)
                entry["capacity"] = len(entry["occupied_by"])
            break

    room = int(residents * 1.5) - sum(p["capacity"] for p in positions.values())
    max_work = max(1, residents // 3)
    for opening in openings:
        if room <= 0:
            break
        key = f"{opening['organization']}/{opening['role']}"
        if key in positions:
            continue
        cap = min(int(opening.get("capacity", 1)), room)
        if opening.get("type", "work") == "work":
            cap = min(cap, max_work)
        if cap <= 0:
            continue
        entry = {
            "organization": opening["organization"],
            "role": opening["role"],
            "type": opening.get("type", "work"),
            "description": opening.get("description", ""),
            "weekly_income": int(opening.get("weekly_income", 200)),
            "weekly_delta_skills": dict(opening.get("weekly_delta_skills") or {}),
            "capacity": cap,
            "occupied_by": [],
        }
        for k in ("min_age", "max_age"):
            if k in opening:
                entry[k] = int(opening[k])
        positions[key] = entry
        room -= cap

    out = []
    for key in sorted(positions):
        p = positions[key]
        out.append({"name": key, **p})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--city", default=(DATA / "active_city").read_text().strip() if (DATA / "active_city").exists() else "chicago")
    ap.add_argument("--force", action="store_true", help="overwrite existing positions.json files")
    args = ap.parse_args()

    pack_path = ROOT / "cities" / args.city / "city.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.exists() else {}
    openings = (pack.get("positions") or {}).get("openings") or []

    source = PERSISTENT if (PERSISTENT / "persona").exists() else DATA / args.city
    if not (source / "persona").exists():
        sys.exit(f"No seeded residents found. Run: python scripts/seed_city_world.py --city {args.city}")

    positions = build_positions(source, openings)
    payload = json.dumps({"positions": positions}, ensure_ascii=False, indent=2) + "\n"

    for target in (DATA / args.city / "positions.json", PERSISTENT / "positions.json"):
        if not target.parent.exists():
            continue
        if target.exists() and not args.force:
            print(f"[positions] kept existing {target.relative_to(ROOT)} (use --force to replace)")
            continue
        target.write_text(payload, encoding="utf-8")
        print(f"[positions] wrote {target.relative_to(ROOT)}")

    filled = sum(len(p["occupied_by"]) for p in positions)
    capacity = sum(p["capacity"] for p in positions)
    print(f"[positions] {len(positions)} positions, {filled} residents placed, {capacity} total slots")


if __name__ == "__main__":
    main()
