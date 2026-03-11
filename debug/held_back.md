# StarCell — Held-Back Issues

Issues land here when they have not been resolved after **3 observation sessions** or a full code review pass and still produce adverse game impact. This is not a graveyard — it is a parking lot. Every entry gets a clear symptom description, a suspected cause, what has already been tried, and a suggested next approach.

---

## Escalation Rules

| Attempt | Action |
|---|---|
| 1st fix attempt | Implement fix, run 1–2 sessions, observe |
| 2nd fix attempt | Revisit root cause, check related systems, re-implement |
| **3rd fix attempt** | **Full code review** — grep all git-tracked files for every call site, data flow, and related system that could be contributing. Look for stopgaps using existing systems before adding new ones. |
| Still unresolved | Move issue here with full history |

A "full code review" means: grep `game_core.py`, `npc_ai.py`, `autopilot.py`, `ai/`, `world/`, `systems/`, and `ui/` for every function and variable involved in the bug. Read them. Then check git log for when the affected code was last changed and what introduced the regression.

---

## Active Held-Back Issues

---

### HB-01 — BAT entities stuck targeting structure entrance cells

**Severity:** Low-Medium
**First seen:** Session 11 (OBSERVATION-25)
**Sessions confirmed:** 11, 16, 18 (3 sessions — escalated here)
**Status:** No fix attempted yet — escalated due to persistence

**Symptom:**
BAT entities in the overworld lock onto structure entrance cells (`["cell", x, y, "structure"]`) and stop moving. They cycle their animation (still→1→2→still) but their grid position does not change. `in_subscreen=False` — they are not inside the structure, just blocked at the entrance. The `ai_state` stays `targeting`, `ai_timer` resets to 3 every sample.

Example from session 18:
```
BAT id=392  zone=0,0  grid=[15,7]
target=["cell", 16, 7, "structure"]
ai_state=targeting  ai_timer=3
in_subscreen=false  moving=false
Observed ticks 2161–2211 (50+ ticks, unchanged)
```

**Suspected cause:**
The BAT AI targets the structure entrance cell as a valid move destination, but the entrance transition logic (`npc_enter_subscreen` or equivalent) either:
- Requires the BAT to be adjacent to a specific EXIT cell type rather than the structure cell itself, or
- Has a distance/position check that fails when the BAT approaches from the current angle

The BAT reaches the cell but the transition never fires, and the AI does not detect failure to transition, so it keeps retargeting the same cell.

**Related known issue:**
MEMORY.md documents the bat animation bug (entity stays in `screen_entities` with `in_subscreen=True`, frozen at 'still'). This is the opposite problem — the BAT never *enters* the structure — but may share root cause in how structure entry eligibility is evaluated.

**What to check on next attempt (full code review due):**
- `npc_ai.py`: where does the entity transition from overworld into a structure? What conditions must be true? Is there a cell-type check that fails for structure entrance cells vs EXIT cells?
- `world/zones.py`: how are structure entrance cells defined and does their cell type match what the NPC AI expects to "enter"?
- `ai/movement.py` or `npc_ai.py`: does the movement toward structure entrances have an adjacency condition before `npc_enter_subscreen` fires?
- **Stopgap idea:** Add a stuck-counter specifically for `target[3] == "structure"` targets. After N ticks at the same grid position targeting a structure cell, clear the target and wander. This prevents the freeze without fixing root cause.

---

### HB-02 — Entities accumulate in `self.entities` but drop out of `screen_entities`

**Severity:** Medium
**First seen:** Session 16 (BUG-06)
**Sessions confirmed:** 16 (1 session — escalated early due to scale: 33 entities affected)
**Status:** No fix attempted yet

**Symptom:**
33 entities across 9 types (SKELETON, BANDIT, TRADER, FARMER, GOBLIN, TERMITE, DEER, MINER, SHEEP) showed bitwise-identical hunger, thirst, health, and grid position across a 2100-tick window in session 16. Since hunger increments every tick in the AI update loop, frozen hunger = the AI loop is not reaching these entities at all — they are not in any `screen_entities` bucket, so `probabilistic_zone_updates` skips them entirely.

One entity (SKELETON id=171) was in zone 0,0 mid-combat, frozen.

**Suspected cause:**
Entities fall out of `screen_entities` without being removed from `self.entities`. Likely candidates:
- Zone transition logic removes entity from old zone's `screen_entities` but fails to add to new zone's bucket
- `on_zone_transition()` or `_sync_player_from_proxy()` partially updates entity zone fields without updating `screen_entities`
- Entity death/removal leaves a stale entry in `self.entities`

**What to check on next attempt:**
- `world/zones.py`: `on_zone_transition` — does it properly move entity IDs between `screen_entities` buckets?
- `npc_ai.py`: when an entity changes `screen_x/y`, is `screen_entities` always updated atomically?
- `game_core.py`: entity death/removal path — is the entity removed from both `self.entities` and `screen_entities`?
- `systems/spawning.py`: new entity spawn — does it always register into `screen_entities`?
- **Stopgap idea:** Watchdog integrity check: each cycle, verify that every entity in `self.entities` appears in exactly one `screen_entities` bucket. Log any orphans. This surfaces the bug without fixing it but gives a count and rate.

---

### HB-03 — NPCs stuck targeting EXIT cells they cannot reach

**Severity:** Medium
**First seen:** Session 16 (BUG-07)
**Sessions confirmed:** 16 (1 session — escalated early due to permanent nature)
**Status:** No fix attempted yet

**Symptom:**
Multiple entities (TERMITEs, SKELETON) locked permanently in `targeting` state pointed at zone EXIT cells they cannot navigate to. Grid position and target unchanged across the entire 2100-tick session window:
- TERMITE id=56 zone -1,-1 → EXIT [1,9]
- TERMITE id=65 zone 0,-1 → EXIT [12,1]
- SKELETON id=81 zone -1,-1 → EXIT [1,9]
- TERMITE id=112 zone -1,0 → EXIT [12,16]

**Suspected cause:**
The EXIT cell is placed at a map position surrounded by WALL or other solid cells, making it unreachable from the entity's spawn location. The pathfinding loop keeps selecting the EXIT as a target (likely for zone travel or exploration) but the A\* or movement step never finds a walkable path. No timeout or stuck detection breaks the loop.

**What to check on next attempt:**
- `world/generation.py` or `world/zones.py`: where are EXIT cells placed? Is there a walkability check verifying the EXIT cell is reachable from the zone interior?
- `npc_ai.py`: does the targeting AI have any timeout on unreachable targets? If a target doesn't change position after N ticks, should the entity abandon it?
- **Stopgap idea:** In the entity AI stuck-counter logic, if `current_target[3] == "EXIT"` and entity hasn't moved for 60+ ticks, clear the target and set `ai_state = "wandering"`. Already partially exists for autopilot proxy; needs porting to NPC AI.

---

## Resolved Issues (formerly held back)

*(None yet — this section tracks issues that were held back and later fixed.)*

---

## Recently Resolved (closed this session, not held back)

### Autopilot UI panels not closing on movement — RESOLVED 2026-03-09

**History:**
- Session 17: Attempted fix (clearing `trader_display`, `inspected_npc` in `update_autopilot`). Reported as confirmed — incorrect. Watchdog did not log `open_menus` so absence of log data was misread as absence of bug. Bug persisted.
- Session 18 (attempt 2): Root cause identified. `move_player()` returns early at line 1502 when `open_menus` is non-empty — `update_autopilot()` at line 1545 was unreachable while any menu was open. Additionally, the crafting close step queued a C key pygame event processed the next frame, where `toggle_menu('crafting')` removed only `'crafting'` leaving `items`/`tools`/`magic` permanently open.

**Fix:**
1. `game_core.py move_player()`: added force-close block before the `open_menus` early-return guard.
2. `autopilot.py _autopilot_try_craft()`: replaced final queued C key with a direct `close_all_menus()` callable to avoid the next-frame pygame event race.

**Confirmed clean:** Session 18 player sample shows `open_menus: [], trader_display: false, inspected_npc: null`.
