#!/usr/bin/env python3
"""Seed a fresh persistent world for a city pack.

    python scripts/seed_city_world.py --city chicago

What it does:
  1. Writes data/active_city so every engine module and the Live World observer
     load cities/<city>/city.json.
  2. Builds the base world data/<city>/ from the pack's worldview.json and the
     public starter personas (data/<seed.base_world>/persona), rewriting the
     residents' present-day geography with the pack's persona_rewrites.
  3. Creates the persistent world data/detroit_persistent/ (engine-internal
     directory name, kept for upstream compatibility) with a config.json built
     from config.example.json.

It refuses to touch an existing persistent world unless --force is passed, and
--force moves the old world to data/detroit_persistent.bak-<timestamp> first.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PERSISTENT = DATA / "detroit_persistent"

# Profile fields that carry narrative text and should be localized.
TEXT_FIELDS = (
    "appearance_and_impression", "brief_introduction", "details", "conflicts",
    "core_motivation", "preferences", "values", "talents", "personality_traits",
    "position", "init_assets",
)


def load_pack(city: str) -> dict:
    path = ROOT / "cities" / city / "city.json"
    if not path.exists():
        raise SystemExit(f"No city pack at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def compile_rewrites(pack: dict) -> list[tuple[re.Pattern, str]]:
    seed = pack.get("seed", {})
    is_regex = bool(seed.get("persona_rewrites_are_regex"))
    out = []
    for old, new in seed.get("persona_rewrites", []):
        out.append((re.compile(old if is_regex else re.escape(old)), new))
    return out


def rewrite(obj, rules):
    if isinstance(obj, str):
        for pat, new in rules:
            obj = pat.sub(new, obj)
        return obj
    if isinstance(obj, list):
        return [rewrite(x, rules) for x in obj]
    if isinstance(obj, dict):
        return {k: rewrite(v, rules) for k, v in obj.items()}
    return obj


def localize_profile(profile: dict, rules, preamble: str) -> dict:
    out = dict(profile)
    for field in TEXT_FIELDS:
        if field in out:
            out[field] = rewrite(out[field], rules)
    if preamble and isinstance(out.get("details"), str) and preamble not in out["details"]:
        out["details"] = preamble + " " + out["details"]
    return out


def build_base_world(city: str, pack: dict, max_personas: int | None) -> Path:
    seed = pack.get("seed", {})
    base_src = DATA / seed.get("base_world", "apartment")
    if not (base_src / "persona").exists():
        raise SystemExit(f"Starter personas not found: {base_src / 'persona'}")
    dst = DATA / city
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    worldview = ROOT / "cities" / city / "worldview.json"
    shutil.copy2(worldview if worldview.exists() else base_src / "worldview.json", dst / "worldview.json")

    history = pack.get("history")
    if history:
        (dst / "detroit_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    rules = compile_rewrites(pack)
    preamble = seed.get("persona_preamble", "")
    people = sorted(p for p in (base_src / "persona").iterdir() if p.is_dir())
    if max_personas:
        people = people[:max_personas]
    for person in people:
        target = dst / "persona" / person.name
        shutil.copytree(person, target)
        for prof in (target / "profile").glob("*.json"):
            data = json.loads(prof.read_text(encoding="utf-8"))
            prof.write_text(json.dumps(localize_profile(data, rules, preamble), ensure_ascii=False, indent=2), encoding="utf-8")
        for note in (target / "memory").rglob("*.jsonl"):
            lines = []
            for line in note.read_text(encoding="utf-8").splitlines():
                try:
                    lines.append(json.dumps(rewrite(json.loads(line), rules), ensure_ascii=False))
                except Exception:
                    lines.append(line)
            note.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return dst


def build_config(city: str, start_year: int, language: str) -> dict:
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    world = cfg.setdefault("world", {})
    world["name"] = city
    world["data_dir"] = "detroit_persistent"
    world["language"] = language
    t = world.setdefault("time", {})
    t["start_year"] = start_year
    t["n_week"] = 52
    t["n_day"] = 5
    world.setdefault("reward", {})["period_weeks"] = 13
    # Location/position templates are generated per-run by the engine.
    world.setdefault("location", {})["load_from_template"] = False
    world.setdefault("position", {})["load_from_template"] = False
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", required=True, help="city pack id, e.g. chicago")
    ap.add_argument("--start-year", type=int, default=2045)
    ap.add_argument("--language", default="en")
    ap.add_argument("--max-personas", type=int, default=None, help="limit starter personas (smaller first run)")
    ap.add_argument("--force", action="store_true", help="back up and replace an existing persistent world")
    args = ap.parse_args()
    city = args.city.strip().lower()
    pack = load_pack(city)

    if PERSISTENT.exists():
        if not args.force:
            raise SystemExit(
                f"{PERSISTENT} already exists. Re-run with --force to move it aside "
                "(it is backed up, not deleted)."
            )
        backup = PERSISTENT.with_name(f"detroit_persistent.bak-{datetime.now():%Y%m%d-%H%M%S}")
        PERSISTENT.rename(backup)
        print(f"[seed] existing persistent world moved to {backup.relative_to(ROOT)}")

    base = build_base_world(city, pack, args.max_personas)
    shutil.copytree(base, PERSISTENT)
    cfg = build_config(city, args.start_year, args.language)
    (PERSISTENT / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "active_city").write_text(city + "\n", encoding="utf-8")

    n = len(list((PERSISTENT / "persona").iterdir()))
    print(f"[seed] {pack.get('world_name', city)} seeded: {n} founding residents")
    print(f"[seed] base world:       data/{city}/")
    print(f"[seed] persistent world: data/detroit_persistent/  (engine-internal name)")
    print("[seed] active city:      data/active_city")
    print("\nNext:\n  python scripts/select_detroit_backend.py llama\n  bash scripts/start_detroit_llama.sh\n  python scripts/run_detroit_persistent.py")


if __name__ == "__main__":
    sys.exit(main())
