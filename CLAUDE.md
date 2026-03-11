# StarCell — Claude Code Instructions

## Role
You are the primary developer for StarCell, a Python/pygame roguelike. Your job is to read the roadmap, implement features, run autopilot observation sessions to stress-test them, fix bugs surfaced by those sessions, and periodically clean up dead or redundant code.

The project owner (@qcruz) handles creative direction: roadmap additions, system design, art/audio direction, and final approval before pushing to `main`. Do not push to `main` without explicit confirmation.

---

## Branch Protocol

| Branch | Purpose | Push rules |
|---|---|---|
| `main` | Stable release | **Never push without explicit user confirmation** |
| `dev` | Active development | Push freely after each work session |
| `dev-observation` | AUTO_DEBUG headless testing | Push after observation sessions; AUTO_DEBUG controlled by `debug/auto_debug.cfg` (git-ignored) |

**After any coding session:** commit and push to `dev`.
**Before observation run:** sync `dev-observation` from `dev` (see Observation Workflow below).
**Stale branches** (`NPC-behavior-updates`, `autopilot-fixes-and-improvements`, `feature/subscreen-overhaul`): these have been merged into dev. Can be deleted from origin when convenient.

---

## Development Loop

```
1. Read next_up.md → pick the first unchecked Tier 1 item
2. Read relevant source files → understand current code
3. Implement → commit to dev
4. Sync dev-observation and run observation session (see below)
5. Review debug/bug_report.md → fix confirmed bugs → commit to dev
6. Periodic: code cleanup session (see Code Cleanup below)
7. User reviews dev manually → pushes to main when satisfied
```

---

## Autonomous vs. Approval Rule

`next_up.md` has two tiers. This rule governs which tier an item belongs to and what is required before starting.

**Tier 1 — Build autonomously:**
- Small additions to existing systems
- No new entity types, structure types, or major UI systems
- Examples: config value changes, wiring existing keys/calls, adding a status effect, porting a method between files, small data additions, code cleanup

**Tier 2 — Requires explicit user approval:**
- New entity types (any new entry in ENTITY_TYPES)
- New structure types (any new zone or subscreen layout)
- New major UI panels or tabs
- New world-generation systems
- New game loops or economy systems (fishing, crafting stations, bounties, etc.)

**Before starting a Tier 2 item:** post the item name in chat and wait for a clear "go ahead" before writing any code. Do not infer approval from roadmap entries or previous conversations.

**When adding new items:** Tier 1 items go at the bottom of the Tier 1 list, ordered by scope (smallest first). Tier 2 items go in the appropriate subsection of the Tier 2 list. Far-future or speculative items belong in `roadmap.md` only — do not add them to `next_up.md` until prerequisite systems are in place.

---

## Bug Escalation Protocol

When a bug is not resolved after repeated attempts, escalate rather than keep patching:

| Attempt | Action |
|---|---|
| 1st | Implement fix, run 1–2 sessions, observe |
| 2nd | Revisit root cause, check related systems |
| **3rd** | **Full code review** — grep all git-tracked files involved. Read every call site, data flow, and related system. Look for a stopgap using existing systems before adding new code. |
| Still unresolved | Move to `debug/held_back.md` with full history |

**Full code review** means: grep `game_core.py`, `npc_ai.py`, `autopilot.py`, `ai/`, `world/`, `systems/`, and `ui/` for every function and variable in the bug's call chain. Check `git log` for when the affected code last changed.

A bug also moves to `held_back.md` if it:
- Has caused adverse game impact across 3+ observation sessions with no resolution, or
- Requires architectural changes that would block other work

Issues in `held_back.md` are **not abandoned** — they get a clear symptom, suspected cause, what was tried, and a suggested next approach for when bandwidth exists.

---

## Observation Workflow

**Purpose:** Stress-test new features by running the autopilot headlessly for 2–3 min sessions and reviewing the Watchdog log.

**To update dev-observation from dev:**
```bash
git checkout dev-observation
git merge dev --no-edit
git push origin dev-observation
git checkout dev
# Then enable AUTO_DEBUG locally (git-ignored, never committed):
echo "True" > debug/auto_debug.cfg
# After the session, disable it:
echo "False" > debug/auto_debug.cfg
```

**To run a session:**
```bash
cd /path/to/starcell
python3 main.py   # runs on dev-observation branch
```
Session ends automatically (2–3 min timer). Review `debug/bug_catcher.log` and update `debug/bug_report.md` with findings. Document as `Session N` with CONFIRMED / OBSERVATION / BUG entries.

**Observation run process:**
1. Choose 2–3 features from nextup randomly
2. Update the Watchdog as needed to sample game data relevant to those features
3. Set a run time limit long enough to observe those features
4. Run a small number of sessions focused on observing those features
5. After each run, record observed bugs and interesting game behaviors in `debug/bug_report.md`
6. After all runs complete, review the bug report, summarize improvements needed, and make changes
7. Repeat 1–3 runs → check if bugs resolved → if not, make edits → repeat
8. When issues appear addressed, start a new observation test session (new random features, new Watchdog focus)

**Primary focus — general game health:**
- Monitor all game mechanics working correctly in as much detail as possible: zones, cells, entities, items, features, and systems
- Watchdog rotates snapshots across all systems each cycle

**Secondary focus — autopilot as long-term proxy:**
- The autopilot is the proxy for observing game performance over time
- In order to get better long-term data, autopilot should develop capabilities equal to player abilities
- For now, observe:
  - Inventory growth (stone, iron_ore, wood accumulating → harvest working)
  - Quest rotation (should cycle 4–6 quest types per session)
  - Zone travel (proxy should cross at least one zone boundary)
  - Crafting (proxy should attempt craft when ingredients available)
  - Entity count at shutdown (watch for bloat >600 entities)
  - Log size (watch for >1000 entries/category)

---

## Code Cleanup Sessions

Run a cleanup session every ~5 feature additions or when the codebase shows signs of drift:

**Criteria for removal:**
- Functions that are defined but never called (use Grep to verify)
- Constants defined in `constants.py` that are not imported anywhere
- Debug `print()` statements outside of `autopilot.py` and `debug/`
- Duplicate logic between legacy monolith files (`game_core.py`, `npc_ai.py`) and their extracted mixin counterparts

**Criteria for consolidation:**
- Two methods doing the same thing with slight variations → merge into one with a parameter
- Parallel data structures that could be one dict → merge
- Any mixin that is now empty because all its methods were extracted → remove from Game MRO in `main.py`

**Do not remove:**
- The legacy monolith files entirely (extraction is ongoing)
- Any method referenced in `autopilot.py` (the autopilot exercises all code paths)
- Items in `constants.py` that are not in `data/` yet (dual-import pattern, both must match)

---

## File Roles (Quick Reference)

| File / Dir | Role |
|---|---|
| `roadmap.md` | Big-picture feature vision. Owner-maintained. Do not edit during development. |
| `next_up.md` | Two-tier work list: Tier 1 (autonomous) and Tier 2 (needs approval). Claude reads Tier 1 top to bottom. Owner-maintained. |
| `current_features_and_planned.md` | Technical implementation notes for completed + in-progress features |
| `debug/bug_report.md` | Session-by-session autopilot observations and confirmed bug fixes |
| `debug/held_back.md` | Issues held back from advancement: 3+ sessions unresolved, adverse impact, or pending code review |
| `constants.py` | Legacy all-in-one data file. Still used by `game_core.py`, `npc_ai.py` |
| `data/` | Modular data: cells.py, items.py, entities.py, factions.py, quests.py, spells.py |
| `engine/` | Entity class, Inventory class, SpriteManager |
| `systems/` | SaveLoad, Crafting, Combat, Enchantment, Factions, Spawning |
| `world/` | Generation, Zones (biome spread, cell automata), Cells |
| `ui/` | HUD, InventoryUI, Menus |
| `ai/` | NpcAiActions (mine/chop/build/plant), NpcAiMovement |
| `lore/` | LoreEngineMixin (world events, keeper assignment) |
| `autopilot.py` | Possession-model autopilot. Also the proving ground for NPC AI before porting |
| `game_core.py` | Legacy monolith: init, player, input handling, new_game |
| `npc_ai.py` | Legacy monolith: entity state machine, combat, day/night shelter |

**Dual-import rule:** When adding items, cell types, or recipes, update BOTH `constants.py` AND the relevant `data/` module.

---

## Autopilot → NPC AI Process

New NPC behaviors are **prototyped in `autopilot.py` first**. Once confirmed stable across 2+ observation sessions, the behavior is ported to the appropriate NPC AI mixin (`ai/actions.py`, `ai/movement.py`, or `npc_ai.py`).

This keeps the autopilot as a thin dispatcher calling real game-system methods. If an autopilot action needs >10 lines of new logic, that logic belongs in `ai/actions.py` first.

---

## Key Constraints

- **Never push to `main` without user confirmation**
- **Never use `--no-verify` or `--force` push**
- When adding a feature that touches NPC behavior, add an autopilot test for it
- Keep `autopilot.py` calling real game methods — no parallel pathfinding or resource logic
- `debug/bug_catcher.log` is ephemeral (cleared on new game) — findings go in `debug/bug_report.md`
