# Agentopia Chicago

A Chicago build of [Agentopia Detroit](https://github.com/tbates03/Agentopia-Detroit). It runs the same engine and the same right-sized local model pool (Liquid LFM2.5 350M / 1.2B / 2.6B). The city is swapped through a **city pack**, so Professor Bates' upstream Detroit work keeps merging cleanly.

## How it works

`cities/chicago/city.json` is the whole city. The engine modules read it through `src/city_pack.py`:

| Layer | What changes for Chicago |
|---|---|
| Geography | 35 neighborhoods plus 10 campuses on an abstract miles-from-the-Loop grid. Corridors: Lake Shore Drive, Dan Ryan, Kennedy, Eisenhower, Stevenson, Pulaski/Cicero, Western, State/Michigan. |
| Transit | CTA bus, CTA 'L', Metra and Pace replace DDOT, QLINE and SMART. The 'L' and Metra have zone-based rail rules. |
| Economy | Illinois 4.95% flat income tax and no city income tax. 30 neighborhood rent multipliers. Housing types include Two-Flat, Chicago Bungalow and Greystone. |
| Institutions | All fictional: Lakeshore Institute of Technology, West Side Technical & Trades Academy, Medical District Health Sciences College, Pullman Mobility & Logistics Institute and others. |
| Employers / banks / health | Name rewrites, e.g. Windy City Credit Union, Maxwell Street Merchant Services, Lawndale Cyber Defense Cooperative, City of Chicago 2045, Cook Civic Justice Center. |
| Climate | `chicago-lakefront-north`: lake-effect winters, plus a wind condition in every season except summer. |
| Calendar | U.S. federal pack plus a new `us-illinois-civic` pack (Lincoln's Birthday, Casimir Pulaski Day). |
| Culture / factions / history | Chicago culture weights. The ThAI Guardians HQ has a West Side training floor; the Obsidian Network sits on Goose Island. A timeline runs from Du Sable to 2045. |
| Founding residents | 100 starter personas move into **Douglass Park Commons, North Lawndale**. Their present-day geography is rewritten; birthplaces elsewhere are kept so they read as transplants. |

**Prompt localization.** Engine modules still contain Detroit wording in many f-strings. For a non-Detroit city, `src/utils.py` rewrites every outgoing LLM prompt with the pack's ordered name rules. The rules protect "Detroit, Michigan" (a valid migration origin), "Lake Michigan" and "Michigan Avenue". Code identifiers are never touched.

**Detroit is untouched.** With no city pack active, all 207 module constants compare identical to upstream (verified). The growth audit passes 36/36 for both cities.

**Engine plumbing keeps Detroit names on purpose.** That covers `data/detroit_persistent/`, `run_detroit_persistent.py`, the `detroit_*.py` modules and the launchd labels. Renaming them would break merges with upstream. Run Chicago in its own clone folder.

## Run it (Mac, Apple Silicon recommended)

```bash
git clone <this repo> Agentopia-Chicago && cd Agentopia-Chicago
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install llama.cpp                     # provides llama-server

python scripts/seed_city_world.py --city chicago      # 100 founding residents
python scripts/select_detroit_backend.py llama        # point the world at the local pools
bash scripts/start_detroit_llama.sh                   # 350M / 1.2B / 2.6B pools (first run downloads GGUFs)
python scripts/run_detroit_persistent.py              # the city runs
python live_world/server.py                           # observer at http://127.0.0.1:8766
```

For a smaller first run: `python scripts/seed_city_world.py --city chicago --max-personas 24 --force`.
For a lighter machine: `AGENTOPIA_PROFILE=light bash scripts/start_detroit_llama.sh`.

To switch back to Detroit, delete `data/active_city` or set `AGENTOPIA_CITY=detroit`.

## City View: every resident on an isometric map

Open **http://127.0.0.1:8766/city.html**, or click **City View** on the dashboard.

- The city is drawn in isometric view: lakefront, river, expressways, the 'L' and Metra lines, the Loop skyline, and neighborhood blocks. Snow shows in winter.
- Every resident is placed from the engine's own reported weekly schedule and trips. People commute along the 'L' lines or the street grid, and are colored by what they're doing.
- Click any resident, or search by name, to see what they're doing, their destination and ETA, home, work, wellbeing and today's schedule. **Follow** keeps the camera on them.
- The time bar replays the reported week. **Engine clock** jumps to the simulation's current phase-derived time.
- Read-only by design. `GET /api/city/scene` (`live_world/city_scene.py`) projects persisted engine state and never writes it.

`seed_city_world.py` now runs the engine's no-LLM initializers (careers, housing, health, schedules, weather), so the City View has residents before the first model run.

## Make your own city

Copy `cities/chicago/` to `cities/<id>/`, then edit `city.json` and `worldview.json`. Then run `python scripts/seed_city_world.py --city <id>`. Every key is optional; anything you leave out falls back to Detroit.

## Known gaps (draft)

- The starter personas are the upstream NYC "apartment" cast with rule-based rewrites. Some references to boroughs and New Jersey remain. The next step is an LLM rewrite pass that turns each resident into a real Chicagoan.
- No sanitized Chicago `founders.json` yet, so lineage enrichment starts once founders are designated.
- The Live World still shows `detroit_persistent` as the run name (engine plumbing).
- `scripts/detroit_digital_twin.py` runs its CLI on import. That is upstream behavior and unchanged.
