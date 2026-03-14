# StarCell Bug Report — Auto-Debug Sessions

Each run: autopilot plays a new game, saves, quits. Session cap: 180–300s (extended 2026-03-14 for quest/keeper observation).
Reviewed from `debug/bugcatcher.log` after each session.

---

## Session 22 — 2026-03-14 (observation runs, quest/keeper focus)

### Run 1 — 270s, new game, tick 15130

**Focus:** NPC quest queue system, LoreEngine random assignment, keeper no-target flags.

#### CONFIRMED — LoreEngine random quest assignment working
LoreEngine assigned MINE quest to MINER(id=249). Quest appeared in watchdog_npc_quests with `base: false` at front of queue, STONE cell as quest_target. Functional.

#### OBSERVATION — Two quest focus systems coexisting
At tick 516, early entities show `quest_focus='farming'` (lowercase, old entity.py system) and `quest_queue=null`. By tick 2916 most have uppercase focus and initialized queues. npc_ai.py queue init runs on first AI update and overwrites. No functional damage but dual-system is confusing in early-game window.

#### BUG — Some NPCs (FARMER, MINER, LUMBERJACK) get wrong base quest type
FARMER(id=4,15) show `quest_queue=[{"type":"COMBAT_HOSTILE","base":true}]` across all 5 watchdog cycles. MINER/LUMBERJACK similarly get EXPLORE as base quest. `NPC_BASE_QUEST['FARMER']='FARM'` — this should not be possible. Both FARMERs remain `ai_state='wandering'` with no active combat. Root cause not isolated after code review of npc_ai.py:2271, game_core.py:1522, lore/engine.py:836 — all correctly use `NPC_BASE_QUEST[entity.type]`. **Carried to Run 2 for confirmation.**

#### OBSERVATION — Entity count approaching bloat threshold
Shutdown entity_count: **588** (threshold: 600). 270s / 15130 ticks. Monitoring.

#### OBSERVATION — 468 keeper_no_target flags at tick 2616
Normal early-game transient — keepers just assigned, haven't completed first search cycle. Not present in later ticks.

#### OBSERVATION — 60 ghost entities reconciled on respawn
`reconcile_screen_entities()` caught 60 ghosts at respawn. Root desync site not yet isolated.

---

### Run 2 — ~210s, tick 11837

**Focus:** Confirm wrong base quest bug, autopilot shovel crafting loop, entity count.

#### CONFIRMED — Wrong base quest bug is reproducible across new-game sessions
New session, new entity IDs: FARMER(id=154) → COMBAT_HOSTILE base=True; MINER(id=16,158,228,250) → EXPLORE base=True; LUMBERJACK(id=150,209,240,257) → EXPLORE base=True. Pattern: FARMER→COMBAT_HOSTILE, MINER/LUMBERJACK→EXPLORE, consistently across sessions. Added to bug report for fix.

#### BUG — Autopilot crafting shovel in tight loop
Terminal output shows repeated `[AP] press C → click shovel → SPACE → Crafted Shovel!` with no delay between cycles. Proxy accumulating multiple shovels, not switching to other actions. Likely the shovel craft is cheap/fast and the autopilot craft-trigger condition keeps re-firing. Low gameplay impact but wastes ticks.

#### OBSERVATION — Proxy stuck at zone exit again
"Stuck at exit (0,9) — entering wander cooldown" logged. Exit-crossing stall persists but wander cooldown recovery mechanism is working.

#### OBSERVATION — NPC built forge
"Zephyr Meadowbrook built a forge!" — MINER NPC self-built a structure. `try_build_well` or similar action. Organic NPC behavior working.

---

## Session 21 — 2026-03-14 (live player review + balance work)

### FIXED — Ghost entities invisible after zone cross / player death
**Root cause:** `screen_entities` remove/append pairs during zone crossing, structure entry/exit, time-pass simulation, or player death can desync from `self.entities`. Ghosts exist in the master dict but are absent from `screen_entities` — invisible, never AI-updated. Save/load recovered them but runtime ghosts persisted until restart.
**Fix:** `reconcile_screen_entities()` added to CombatMixin. Called at load time, after every respawn, and every 600 ticks during normal play.

### FIXED — Quest HUNT target pointing to cell instead of entity
**Root cause:** Multiple compounding issues: live-tracking loop was clearing `is_dead` before `check_quest_completion` could fire; kill handler in game_core.py was calling `quest.clear_target()` directly (bypassing XP + sound); old saves had stale cell coords in target fields.
**Fix:** Kill handler removed (let `check_quest_completion` own detection via `entity.is_dead`); live-tracking guard resets quests with no `target_entity_id`; entity health clamped to `min(saved, max_health)` on load.

### FIXED — Quest arrow pointing wrong location when target inside cave
**Root cause:** `entity.screen_x/y` are virtual coords (−1000,N) when `in_structure=True`. Live-tracking was copying these directly into `quest.target_zone`.
**Fix:** `get_surface_pos_for_entity()` added to LoreEngine — traces `parent_screen` chain recursively up to the overworld surface. Quest arrow and HUD now show the cave entrance cell.

### FIXED — NPC stall at zone exits when pursuing cross-zone target
**Root cause:** `_try_targeting_zone_cross` was calling `try_entity_zone_transition` (1800-tick cooldown), causing 30-second stalls. Should use `try_entity_screen_crossing` (30-tick cooldown, OOB coordinates).
**Fix:** Rewrote `_try_targeting_zone_cross` to derive OOB coords from `is_at_exit()` direction and call the fast path.

### FIXED — TypeError: keeper_type None comparison
**Root cause:** `getattr(entity, 'keeper_type', 3)` doesn't catch explicit `None` values stored in save data.
**Fix:** `ktype = getattr(entity, 'keeper_type', None) or 3`

### FIXED — Chest destruction plank feedback loop
**Root cause:** Empty chests dropped a `planks` item when harvested. NPCs harvested chests, picked up the plank, had "full" inventory, then placed a new chest — infinite loop.
**Fix:** Empty chest destruction leaves nothing. Only chests with stored contents scatter items. Goblin chest-placement chance also reduced 0.5% → 0.05%.

### BALANCE — Rain/biome desertification
**Root cause (rain too rare):** `RAIN_FREQUENCY_*` are `update_weather` call-counts (called every 30 ticks), not raw ticks. Old values (1800–18000) = 15–150 min between rains.
**Root cause (time-pass, no rain):** Time-pass sim is only 600 ticks total — old minimum (1800) was never reached, so zero rain fired during 200-year simulation.
**Root cause (rain coverage):** `apply_rain` gated to distance ≤ 2 from player, so most zones never got rain during time-pass.
**Fixes applied:** Frequency tuned to 120–600 calls (~1–5 min); duration 30–180 calls (~15–90 s); distance limit removed during `time_pass_active`; sand→dirt grass-reclaim rule added at 0.05× base rate; water evaporation 0.005 → 0.02; deep water evaporation condition corrected to mirror formation rule (cardinal_water < 4), rate 0.03 → 0.3.

---

## Session 20 — 2026-03-13 (live player review)

### OBSERVATION — Houses spawning with no lumberjack in zone
**Severity:** Low / polish
**Root cause:** HOUSE placement (world/generation.py ~line 158) and LUMBERJACK spawning are completely independent. A HOUSE is placed at 30% chance per zone (random choice of HOUSE or CAVE), with no lumberjack spawn guarantee. House interiors have a 50% chance to spawn any NPC, and only ever pick FARMER or TRADER — never LUMBERJACK. Lumberjacks only appear via the probabilistic zone spawn table.
**Result:** A HOUSE can exist with an empty interior and no lumberjack anywhere in the zone.
**Suggested fix:** When placing a HOUSE, guarantee at least one LUMBERJACK in the zone's spawn list, or prefer placing the house only when the zone spawn table has already produced a LUMBERJACK.

### OBSERVATION — Bandits crowding zones
**Severity:** Medium
**Root cause:** Multiple independent systems stack bandit counts:
1. Initial spawn: 20–50% per zone (desert 50%), up to 2 per zone
2. Continuous spawn: desert 15% weight — highest of any entity
3. Raid events: spawn 2 bandits at once when 6+ peaceful NPCs present; TRADER+GUARD always spawn so threshold is frequently met; raid cooldown is only 600 ticks (~10s)
4. Cave spawns: 20% of cave hostile spawns are bandits — continuous low-rate
5. Zone crossing: bandits in targeting state cross zone boundaries at 100% travel rate with no block
**Bandit stats are also aggressive:** strength 20, speed 1.3, aggressiveness 0.90, attacks_structures True.
**Suggested angles:** Reduce desert continuous spawn weight, raise raid threshold or increase raid cooldown, add per-zone bandit hard cap, or reduce aggressiveness so bandits don't chain-trigger pursuit across zones.

---

## Session 19 — 2026-03-10 (live player session)

### FIXED — BLACK_SPIDER step animation not playing
**Root cause:** Still-frame sprites for BLACK_SPIDER (and BUTTERFLY, CHICKEN, COW) were renamed from `blackSpider_down_still_1.png` → `blackSpider_down_still.png` in the dev folder but never committed to git. The live game dir (`~/StarCell/`) only had the old `_still_1` format. The sprite loader looks for `blackSpider_down_still.png` — it was silently failing, falling back to frame `1` for the still step. Walk frames `_1` and `_2` were present and loading correctly.
**Fix:** Committed renamed still sprites for spider, butterfly, chicken, cow. All four entity types now have correct still frames in the live game dir.
**Note:** `is_combat_idle` animation during combat stance was separately proposed and reverted twice — confirmed by user as incorrect behavior. Entities correctly freeze at still when not physically moving.

### BUG — Entity spawn bloat: 2,736 entities observed vs ~294 in session 18
**Severity:** High
**Confirmed cause:** `spawn_single_entity_at_entrance` in `systems/spawning.py` has a missing `break` after successful spawn. The `for attempt in range(10)` loop spawns an entity each time it finds a non-solid cell, only exiting on a 5% random roll (`if random.random() < 0.05: return True`). Expected: 1 entity per call. Actual: ~9-10 entities per call.
`check_zone_spawning` calls this up to 3 times per cycle across a 5×5 zone grid around the player, and runs continuously. This compounds: each call spawns ~9 entities instead of 1.
**Fix:** Replace `if random.random() < 0.05: return True` with `return True` to exit after the first successful spawn.

---

## Session 18 — 2026-03-09 (~2,233 ticks, ~37s, NEW GAME)

### FOCUS: Autopilot UI close fix — real fix confirmed

### CONFIRMED — open_menus clear at player sample (tick 1557)
Watchdog player sample (new fields added this session): `open_menus: [], quest_ui_open: false, trader_display: false, inspected_npc: null, ap_input_queue_len: 0`. All panels clear while proxy is walking. Fix is confirmed working.

**Proxy:** wandering, grid moved from [18,16] at tick 657 to [15,10] at tick 1557. Zone 0,0 only (short session).
**Shutdown (tick 2233):** 294 entities, 114 zones, 1 structure, 1 follower (TERMITE id=275, zone_match=true, healthy).

### BUG-08 RECONFIRMED → escalated to held_back.md (HB-01)
BAT id=392 at grid [15,7] targeting `["cell", 16, 7, "structure"]` for 50+ ticks (observed ticks 2161–2211). Grid unchanged, `in_subscreen=false`, `ai_timer=3` on every sample. Third session this behavior is observed (sessions 11, 16, 18). Moved to `debug/held_back.md` as HB-01 — full code review due on next fix attempt.

### OBSERVATION — Watchdog player category fires once per ~2100 ticks
With 7 categories rotating at 300-tick intervals, the player sample appears once every 2100 ticks. A 37s session at 60fps = ~2233 ticks → exactly one player sample. For future short sessions, consider reducing `SAMPLE_INTERVAL` or weighting player category more frequently to get more UI state snapshots per run.

---

## Session 17 — 2026-03-09 (~1,545 ticks, ~79s, NEW GAME)  ⚠ RETRACTION

### ~~CONFIRMED — Fix working~~ — INCORRECT. Fix was NOT working.
The confirmation in this session was wrong. The Watchdog did not log `open_menus`, `trader_display`, or `inspected_npc` at the time — those fields were not yet in `_sample_player`. The "no stuck UI panels" conclusion was based on the absence of fields that were never captured. The bug persisted, as confirmed by direct visual observation.

**Actual root cause (found session 18):** `move_player()` returns early at line 1502 when `open_menus` is non-empty. `update_autopilot()` at line 1545 is unreachable while any menu is open, so all close logic in it was dead code under the exact conditions needed. Additionally, the crafting close step queued a C key pygame event that re-opened `items`/`tools`/`magic` panels on the next frame.

**Fix applied before session 18:**
1. `game_core.py move_player()`: force-close block added before the `open_menus` early-return.
2. `autopilot.py _autopilot_try_craft()`: closing step changed from queued C key event to direct `close_all_menus()` callable.

---

## Session 16 — 2026-03-08 (~3,108 ticks, ~52s, NEW GAME)

### CONFIRMED — Clean run, no exceptions
No tracebacks, no backup_save_error. Crafting (seeds) confirmed. Proxy moving. SHEEP follower (id=265) zone-matched and healthy throughout.

### BUG-06 — 33 entities frozen: hunger/thirst/health unchanged for 2100 ticks [INVESTIGATE]
**Severity:** Medium
Entity samples at ticks 708 and 2808 show 33 entities with bitwise-identical hunger, thirst, health, and grid position. Affected types include SKELETON, BANDIT, TRADER, FARMER, GOBLIN, TERMITE, DEER, MINER, SHEEP — spread across multiple zones including the player's own zone 0,0. Hunger counter not advancing means the entity update loop is **not running for these entities** (not just that they are physically stuck).
Notable: SKELETON id=171 in zone 0,0 grid (10,3) targeting GOBLIN id=0 — frozen mid-combat.
**Suspected cause:** Entities accumulate in `self.entities` but are not present in any active `screen_entities` zone bucket, so the AI update loop never reaches them. Requires investigation of how entities fall out of `screen_entities`.

### BUG-07 — 4 entities permanently stuck targeting EXIT cells [INVESTIGATE]
**Severity:** Medium
Three TERMITEs and one SKELETON are stuck in `targeting` state pointed at a zone EXIT cell, with zero movement across the full 2100-tick window:
- TERMITE id=56 zone -1,-1 → EXIT [1,9]
- TERMITE id=65 zone 0,-1 → EXIT [12,1]
- SKELETON id=81 zone -1,-1 → EXIT [1,9]
- TERMITE id=112 zone -1,0 → EXIT [12,16]
These entities cannot reach or use the exit. Likely a pathfinding failure where EXIT cell is in a position the entity cannot path to (surrounded by walls or unreachable from spawn location).

### BUG-08 — BAT id=280 trapped in cave structure for 900+ ticks [INVESTIGATE]
**Severity:** Low-Medium
BAT id=280 inside cave structure at zone -1000,0 targeting exit cell [11,6,'structure'] at both ticks 1908 and 2808. Cannot exit. May be related to the known bat subscreen transition issue — bat gets into the cave but the exit portal pathfinding fails. Monitor to confirm it persists across sessions.

### OBSERVATION-29 — FARMER id=274 at 18% HP and near-max hunger, no flee/eat behavior
At tick 2808: health=12.88/70, hunger=98.86, thirst=99.14, ai_state=wandering, no combat, no target. Entity is critically injured and nearly starved but the AI is not triggering flee or food-seek behavior. May indicate the self-preservation check threshold is not firing, or the entity has no reachable food/water source.

### OBSERVATION-30 — 76% of sampled entities near hunger/thirst cap
276 of 362 entity samples show hunger or thirst >= 98. NPC population (53 → 317 entities over ~52s) is outpacing food generation. Not a crash risk but world is in permanent near-starvation. Likely driven by TRADER mass-spawning settling as farmers who haven't yet had time to grow food.

### OBSERVATION-31 — 2 Bandits (id=53, id=60) with max_health=100 (level-2 scaling)
All other bandits are max_health=50, level=1. These two are level=2, max_health=100. Consistent with the level scaling table but worth verifying the BANDIT level-2 entry in ENTITY_TYPES is intentional.

---

## Session 15 — 2026-03-08 (~5,900 ticks, ~119s, NEW GAME)

### CONFIRMED — Clean run, no errors
No exceptions, no backup_save_error. Two successful backup saves (ticks 606 and 4206).
Entity count: 290 at tick 2706 → 373 at tick 4806 (well under 600 bloat threshold).

### CONFIRMED — Crafting still working
`[AP] press C → [AP] click slot 'seeds' → [AP] press SPACE → [Craft] Crafted Seeds! → [AP] press C (close crafting)`.

### CONFIRMED — New spells in magic inventory
`rain_spell` and `day_spell` appear in player magic inventory at tick 1506 — `new_game()` item grants working.

### CONFIRMED — Follower stable
TERMITE follower (id=270) healthy, zone=0,0 matching player zone, `hostile=False` at both sample points (ticks 2106, 4206).

### CONFIRMED — NPC combat active
GOBLIN (id=307) targeting MINER at tick 2406 (`ai_state=targeting`), in combat at tick 4506 (`ai_state=combat, in_combat=True`).

### OBSERVATION-26 — Player never leaves zone 0,0
All 3 player samples (ticks 1506, 3606, 5706) show zone=0,0. Autopilot does not cross zone boundaries. Zone travel is not yet implemented in autopilot.

### OBSERVATION-27 — Inventory stagnant
Items identical across all 3 samples: `carrot×3, tree_sapling×3, magic_rune×1, seeds×1`. No resource accumulation. Autopilot wanders and crafts but does not actively harvest cells or pick up items. Expected until harvest behaviour is added to autopilot.

### OBSERVATION-28 — Quest stuck on FARM all session
Same FARM quest at ticks 1506, 3606, 5706. Quest rotation requires player to complete or fail a quest, which requires active play. Not a bug — autopilot doesn't yet perform quest-related actions.

---

## Session 13 — 2026-03-08 (~3,328 ticks, ~63s, NEW GAME)

### CONFIRMED — Full crafting sequence fires end-to-end [BUG-04 FIXED ✓]
Three-part fix for autopilot simulated input:
1. **`_ap_synthetic=True` event tagging** — synthetic pygame events skip `mark_input()` so autopilot cannot be disengaged by its own key presses.
2. **Flush before menu guard** — `move_player()` now drains the autopilot input queue BEFORE the `open_menus` early-return, so click and Space events fire even while the crafting menu is open.
3. **Closing C press** — sequence ends with a C keypress to leave the menu closed.

Log confirms: `[AP] press C → [AP] click slot 'shovel' → [AP] press SPACE → [Craft] Crafted Shovel! → [AP] press C (close crafting)`.

### CONFIRMED — Session cap reduced to 60–120s
Bugs were appearing in the first seconds; shorter sessions catch them faster.

### BUG-05 — `NameError: entity_structure_key` in `find_and_attack_enemy` [FIXED ✓]
**File:** `npc_ai.py:1735`
**Error:** `entity_structure` was assigned at line 1733, but line 1735 referenced the nonexistent `entity_structure_key`. Crashed whenever a hostile NPC tried to attack the player while the player was inside a structure. Side effect: the exception also prevented the backup save from completing (backup_save_error in Sessions 11–12 with `'bool' object has no attribute 'items'` — the exception path corrupted state before save).
**Fix:** Renamed the variable at line 1733 to `entity_structure_key`.
**Confirmed:** Session 14 backup save at tick 738 logged successfully (both backup1 and backup2).

---

## Session 11 — 2026-03-08 (~6,558 ticks, ~120s)

### CONFIRMED — Smooth movement snap eliminated
Max grid-world delta across all entity log entries: **1.00 cells** (zero snap events; snap threshold = 2.5).
Speed-calibrated rate limiter on `wander_entity` and `move_toward_position` works correctly:
- Entities move once per ~29 ticks (speed=1.0), giving smooth interpolation (0.034 cells/tick) exactly enough time to traverse one cell before the next grid step.
- BAT 518 example: moved grid=[2,2] at t=6271 with world=[2.0,1.0]; world reached [2.0,2.0] by t=6291 (20 ticks). Clean.
- Zone-crossing artifact: BAT 300 at t=6511 had grid=[20,9] world=[21.0,9.0] (1.0 cell difference from zone transition). World interpolated smoothly to [20.0,9.0] by t=6538. Normal.

### CONFIRMED — iron_ingot in inventory at t=5658
Proxy inventory at t=5658 showed `iron_ingot: 1`. Crafting system active (or IRON_ORE loot table). rain_spell and day_spell present in magic inventory confirming new_game spell seeding works.

### CONFIRMED — BAT follower persisted entire session
BAT id=300 remained in followers list across all three watchdog samples (t=1458, t=3558, t=5658). Follower death fix holds.

### CONFIRMED — Bat animation cycling while stationary (not the subscreen bug)
BAT entities (300, 518) in zone 0,0 spent extended time in `targeting` state aimed at cell [1,1,"structure"] while `moving=false`. Animation cycled still→1→still→2→still normally. Entities are NOT in_subscreen. This is a separate issue: bats are targeting a structure cell they can't enter or reach, oscillating in idle/targeting. Non-critical — no snap, no freeze.

### OBSERVATION-24 — Proxy didn't craft iron_sword despite having iron_ingot + bone_sword
At t=5658: `iron_ingot: 1` in items, `bone_sword: 1` in tools. Recipe `hilt + hilt → iron_sword`? Check recipe requirements. Autopilot `_autopilot_try_craft` would have attempted if recipe was satisfied. Either recipe needs `iron_ingot + hilt` and hilt is missing, or crafting UI menu open check is blocking the craft call. Investigate `attempt_craft_selected()` — may require 'crafting' to be in `open_menus`.

### OBSERVATION-25 — Bats stuck targeting structure cell they cannot enter
BAT 300 and BAT 518 cycled between `targeting` (target=["cell",1,1,"structure"]) and `idle` for hundreds of ticks without making progress. Bats can't enter structure zones from the overworld without using an EXIT cell. The targeting AI should check whether the entity can actually reach the target type, or add a timeout to abandon unreachable structure targets. Low priority.

---

## Session 10 — 2026-03-08 (~8,065 ticks, ~122s, CONTINUE)

### CONFIRMED — Resource collection dramatically improved
Inventory grew steadily across all four watchdog samples:
- t=1641: `stone: 3, iron_ore: 1`
- t=3741: `stone: 10, iron_ore: 1`
- t=5841: `stone: 14, iron_ore: 3, bones: 1`
- t=7941: `stone: 17, iron_ore: 4, bones: 1`

Stone +14 and iron_ore +3 across ~6300 ticks. Cardinal-only scan in both `_autopilot_opportunistic_harvest` and `try_mine_rock` eliminated position jumps; proxy now collects steadily while traversing.

### CONFIRMED — Zero integrity anomalies, zero fix events
All prior watchdog fixes continue to hold.

### CONFIRMED — Quest rotation: FARM → GATHER → MINE → SLAY across 4 watchdog cycles
Quest switching working normally.

### CONFIRMED — Zone travel: proxy crossed from 0,0 → 0,-1 (sample at t=7941)
Cross-zone travel confirmed for second consecutive session.

### CONFIRMED — Obstacle-clear in wandering state fired: `mining rock at (11,16) stuck=120t`
At ~t=8040 the proxy had been stuck at (11,16) in `wandering` state for 120 ticks; obstacle-clear extended to wandering state triggered `try_mine_rock`. OBSERVATION-21 fix confirmed working.

### CONFIRMED — 3 followers at shutdown (up from 1)
`follower_count: 3` at shutdown. NPC follow interaction (`_autopilot_try_npc_interact`) is recruiting followers.

### OBSERVATION-22 — Proxy remained at (11,16) for remaining 25 ticks after obstacle-clear
After obstacle-clear fired at ~t=8040, proxy stayed at (11,16) until shutdown at t=8065. Two possible causes: (1) mine roll failed (20% success rate) — first clear at 60t may have also failed; (2) mine succeeded but wandering picked another blocked direction. Not a bug — 25 ticks is insufficient recovery time. Will monitor in future sessions.

### OBSERVATION-23 — 872 `entity` log entries (up from 12 in Session 9)
`bug_catcher.log_bat_state` transitioned 872 times. Session 9 had 12. Likely due to more entities in zone 0,-1 and more state changes during combat/flee encounters with hostiles in new zone. Not a bug but worth monitoring for log size growth as world entity count rises (547 entities at shutdown).

---

## Design Philosophy

**Goal of bug fixes:** Ensure game systems work correctly with minimal special-case handling code.

- We do **not** want to patch around broken behavior with autopilot heuristics — we want **quest targeting, pathfinding, and tool use** to naturally get the character to its goal.
- The autopilot is a test harness: stress-test code paths, surface bugs, and gather gameplay data. Long-term it will be ported as the baseline AI for all NPCs, giving every NPC rich, complex behavior.
- Bug fixes should remove the need for special handling, not add more of it.

**Macro picture to watch:**
- Are structures and factions forming across the world?
- Are followers staying near the player and helping in combat?
- Are NPC economies (trading, farming, mining) self-sustaining?
- Are hostile factions raiding / escalating?
- Quest variety: does the autopilot/player cycle through diverse activities?

---

## Session 1 — 2026-03-07 (~7431 ticks, ~2 min, NEW GAME)

### BUG-01 — Watchdog integrity check was 100% false positives [FIXED ✓]
**Category:** `integrity_anomaly` — `entity_not_in_subscreen_but_in_subscreen_entities`
**Count:** 6770 entries, 470 unique entities, zero true positives
**Root cause:** Reverse-map was built from ALL `screen_entities` keys; both overworld and structure zones share that dict, so every overworld entity got flagged as "found in subscreen."
**Fix:** Filter to only keys present in `game.structures`. Applied and confirmed fixed in Session 2.

### ~~BUG-02~~ — RETRACTED: Ghost follower entries were analysis script artifact
The `{'note': 'no followers'}` entries had no id/type/zone fields; analysis script printed None for missing keys. No actual ghost follower.

### OBSERVATION-01 — Player never leveled up
Expected — XP intentionally not awarded while autopilot is on.

### OBSERVATION-02 — FARM quest never completed (see Session 2 for follow-up)

### OBSERVATION-03 — Player always sampled at zone 0,0
Sampling coincidence — see Session 2 confirmation.

---

## Session 2 — 2026-03-07 (~6150 ticks, ~1–2 min, NEW GAME)

### CONFIRMED — BUG-01 fix working
Zero integrity anomalies. False-positive flood eliminated.

### BUG-03 — Watchdog Check 1 was a false positive [FIXED ✓]
**Category:** `fix_entity_subscreen_flag` — 4 occurrences (Session 2), 8 (Session 3)
**Affected:** MINER, TRADER, LUMBERJACK, FARMER, GUARD — all shelter-seeking NPC types
**Root cause:** Watchdog Check 1 condition: `entity.in_structure=True AND entity in screen_entities[entity.screen_x/y]`. For a properly-entered entity, `entity.screen_x/y` is the *virtual structure key* (e.g., `-1000,0`). That key IS in screen_entities and entity IS in that list — so Check 1 fired on every properly-entered entity, incorrectly kicking them out of their structure each watchdog cycle (every 300 ticks).
**Fix:** Added `zone_key not in structure_keys` guard to Check 1 in `debug/watchdog.py`. Structure virtual keys are in `game.structures`; overworld keys are not. Now Check 1 only fires when `entity.screen_x/y` points to an *overworld* zone with `in_structure=True`, which is the true anomaly case. Applied in Session 4 — expect zero `fix_entity_subscreen_flag` events.

### OBSERVATION-04 — FARM quest never completes across both sessions
Active quest stays FARM from tick 1 to end in both runs. Autopilot earns carrots (seen in inventory: `{'carrot': 5}`) but the quest never triggers completion. Either the completion check isn't firing for the proxy, or the quest target count is higher than what autopilot can farm in the session window.

### OBSERVATION-05 — Per-frame entity logger very noisy
4320 log entries per session, all WOLF/BAT, no active anomalies showing. Consider gating to state-transition-only logging to reduce noise.

### OBSERVATION-06 — CONFIRMED: Player does travel extensively (115 zones visited)
Including structure interiors (virtual keys like `-1000,0`, `-1010,0`). Player samples landing at 0,0 is sampling coincidence. Not a bug.

---

## Session 3 — 2026-03-07 (NEW GAME)

### CONFIRMED — OBSERVATION-04 fix (FARM quest) working
Quest changed from FARM to EXPLORE by tick 3579. Fix confirmed: local FARM targets now store `_original_cell` from a real farm cell in the zone grid.

### CONFIRMED — OBSERVATION-05 fix (logger noise) working
Zero entity transition log entries. State-transition gating in `log_bat_state` is effective.

### BUG-03 — 8 occurrences (up from 4), root cause diagnosed and fixed
All 8 events were peaceful NPCs that had *correctly* entered structures at night. The watchdog was incorrectly identifying them as anomalies and kicking them out. Fix applied to `debug/watchdog.py` Check 1.

### OBSERVATION-07 — Goblin follower (id=314) persisted entire session
No integrity issues on follower. Expected behavior.

---

## Session 4 — 2026-03-08 (~14,106 ticks logged, NEW GAME)

### CONFIRMED — BUG-03 fix working
Zero `fix_entity_subscreen_flag` events. Zero integrity anomalies. Watchdog Check 1 is no longer a false positive.

### OBSERVATION-08 — Auto-debug timer reliability issue
The session was cut off by the bash process timeout (~500s) before `_auto_debug_shutdown()` fired. Root cause: the game runs at ~28fps (NPC AI load) rather than the expected 60fps. At 28fps, a 420s session = ~14,000 ticks — just past the 500s bash window. **Fix needed:** increase bash timeout to 700s, or better, run the game in background and poll for completion.

### OBSERVATION-09 — Autopilot proxy never left zone 0,0 (14,000 ticks)
The proxy (FARMER type, FARM quest) wandered in-zone the entire session. Only SEARCH/RESCUE/EXPLORE force zone travel via `_nudge_toward_zone`. FARM/GATHER quests with local targets leave the proxy at the starting zone. Quests still completed (FARM → RESCUE → GATHER) — the local farming behavior works. Not a bug but limits autopilot coverage of the world map.

### OBSERVATION-10 — Termite follower recruited (id=293, item=termite_293)
Player acquired a TERMITE follower. Follower system functioning normally for non-humanoid types.

### OBSERVATION-11 — Quest completions working normally
Multiple quest types completed: FARM → RESCUE → GATHER across ~230 seconds of play.

---

## Session 5 — 2026-03-08 (~15,095 ticks, NEW GAME)

### CONFIRMED — OBSERVATION-08 fix: timer now fires correctly
`[AutoDebug] Timer expired at tick 15095` printed cleanly; `auto_debug_shutdown` entry in log. Increasing bash timeout to 720s resolved the cutoff.

### CONFIRMED — Zero integrity anomalies, zero fix events
BUG-03 fix continues to hold across sessions.

### CONFIRMED — OBSERVATION-09 fix: proxy now crosses zones
Proxy traveled from zone `0,0` → `0,-1` (crossed at some point between tick 5652 and tick 7752). Zone travel working with 35% nudge rate (up from 10%).

### CONFIRMED — Quest variety improved dramatically
7 different quest types sampled across session (one per ~2100-tick watchdog cycle): FARM → SLAY → RESCUE → GATHER → MINE → COMBAT_HOSTILE → EXPLORE. Forced 30-second rotation and 80% switch-on-completion working.

### OBSERVATION-12 — Proxy stuck targeting exit corridor for extended periods
After crossing into zone `0,-1`, the proxy spent the remainder of the session (~7,000+ ticks) targeting the east exit cell `(23,9)` to travel to zone `1,-1`. It made slow progress (x: 13 → 14) but never crossed. Root cause: the 2% bail-on-stuck check fires but every 120-tick nudge immediately reassigns the same exit target if the quest zone is still east. The proxy oscillates between bail and re-nudge without ever escaping the loop. **Fix needed:** track consecutive same-exit-target nudge cycles; after N stuck cycles, suspend travel nudges for several cycles to let natural wandering reach the exit.

### OBSERVATION-13 — watchdog_player_sample `pos` fields are None
Player samples log `pos=(None,None)` for x/y. The watchdog is reading `player['x']` / `player['y']` which are not set on the `player` dict at sample time (the proxy coordinates are in `proxy.x` / `proxy.y`). Minor logging gap — zone field is correct. Not a gameplay bug.

---

## Session 6 — 2026-03-08 (~18,617 ticks, NEW GAME)

### CONFIRMED — Zero integrity anomalies (BUG-03 fix still holding)

### CONFIRMED — Quest rotation: 9 different quest types across 9 watchdog samples
FARM → EXPLORE → RESCUE → SLAY → MINE → COMBAT_HOSTILE → FARM → SLAY → RESCUE. All quest types cycling correctly; forced-rotation every 1800 ticks working.

### CONFIRMED — NPC inspection action firing
`[Autopilot] Inspecting BANDIT (id=882) dist=3` — action system exercised NPC inspection code path.

### CONFIRMED — Timer reliable: fired at tick 18617

### OBSERVATION-14 — Stuck-at-exit fix not yet exercised
Proxy stayed in zone 0,0 all session. Flee state blocked nudge calls (flee is correctly not overridden). Stuck-exit logic requires nudge to fire, so it never triggered. Will be exercised in future sessions when proxy avoids hostile zones.

### OBSERVATION-15 — Proxy can be pinned against zone edge during prolonged flee
Proxy entered flee state at ~t=18540 (BANDIT within dist=3) and stayed at grid cell (1,11) for 75+ ticks until session end. The proxy is invulnerable but flee logic persists while threat is nearby; x=1 means it's against the left wall. Normal NPC behavior, not a bug. The proxy's `flee_chance=0.95` means it almost always tries to flee; the MINER/MINE-quest proxy type doesn't fight back.

---

## Session 7 — 2026-03-08 (~7,681 ticks, NEW GAME)

Session ran ~274s (near the 270s random draw from 60–420s range). Proxy stuck in `wandering` state at grid (5,12) for many ticks at session end — possibly surrounded by solid cells in wandering mode.

### NOTE — Log overwritten by next session
Session 8 was run immediately after Session 7. Session 8's `bug_catcher.clear()` call overwrote the Session 7 log. `auto_debug_state.json` incremented (run=6→7) confirming shutdown fired correctly. Not a bug; the log retains only the most recent session by design.

### OBSERVATION-17 — Obstacle clearing not yet exercised (wandering state)
The new `_autopilot_try_clear_obstacle()` only fires in `targeting` state. When proxy gets stuck in `wandering` state surrounded by solid cells, obstacle clearing never triggers. **Fix needed (future):** extend stuck detection to also fire in wandering state.

---

## Session 8 — 2026-03-08 (~8,646 ticks, ~129s, NEW GAME)

First session with 3-minute cap + real proxy HP (100/100).

### CONFIRMED — 3-minute cap working
Session duration 129s (random within 120–180s range). Timer fired at tick 8646. Shutdown entry logged cleanly.

### CONFIRMED — All action types exercised in one session
- `[Autopilot] Spell → rain_spell` — spell casting code path hit
- `[Autopilot] Dropped carrot/tree_sapling/wood` — drop_item code path hit
- `[Autopilot] Tool → hoe` — tool selection code path hit
- `[Autopilot] Inspecting TERMITE (id=433)` — NPC inspection code path hit

### CONFIRMED — Obstacle-clear fired: `chopping tree adjacent to proxy (10,13) stuck=60t`
After 60 ticks stuck in `targeting` state at (10,13), the autopilot called `try_chop_tree()` on the adjacent tree. This cleared the path. Shortly after, proxy crossed into zone `0,1`. Fix is working as designed.

### CONFIRMED — Stuck-exit wander cooldown fired: `Stuck at exit (12, 0)`
After 5 consecutive nudges to the same north exit cell, proxy entered 10-cycle wander cooldown.

### CONFIRMED — Zone travel: proxy reached zone 0,1
Player samples at tick 5799 and 7899 both show zone=0,1 — confirming cross-zone travel working reliably now (obstacle-clear + stuck-exit wander both contributing).

### OBSERVATION-18 — Proxy HP not visibly reduced (player_health=100 at shutdown)
Proxy had real HP (100/100) this session but no combat damage was observed. Either no hostile NPCs attacked, or proxy fled before contact. The real-HP change enables future damage tracking — will monitor in subsequent sessions.

---

## Session 9 — 2026-03-08 (~7,678 ticks, ~115s, CONTINUE)

First session with all three new fixes applied: CLIFF protection, sword_swing combat sound, opportunistic harvest.

### CONFIRMED — Zero integrity anomalies, zero fix events
All prior watchdog fixes continue to hold.

### CONFIRMED — Opportunistic harvest working
Inventory grew between watchdog samples:
- t=1623: `stone: 10, tree_sapling: 3`
- t=3723: `stone: 12, tree_sapling: 4`
- t=5823: `stone: 12, tree_sapling: 4` (capped — no new harvestable cells adjacent)

Stone and saplings accumulated passively while proxy wandered. Confirms `_autopilot_opportunistic_harvest()` fires correctly in wandering/targeting states every 30 ticks.

### CONFIRMED — World activity robust
131 unique zones sampled, 7 structures, 479 entities at shutdown. 2 NPC settlements mid-session (Bram Wildrose/Greta Clearwater settled as miners at zones [2,2] and [-2,1]). TRADER (142), FARMER (124), MINER (94), GUARD (81), LUMBERJACK (56), BANDIT (47), WOLF (37), GOBLIN (33) all active across world zones.

### CONFIRMED — Sheep follower (id=368) persisted from CONTINUE save
Follower system and save/load path working. Inventory included `sheep_368` follower entry.

### OBSERVATION-19 — Active quest stuck at FARM all session
This was a CONTINUE session (saved game had FARM quest active). Quest did not rotate during the ~115s session. Log field is `active_quest` (not `quest`) — analysis script had a label mismatch, not a game bug. Quest rotation requires the 1800-tick forced switch; session ended at tick 7678 so only ~4 forced-switch windows occurred. The FARM quest kept the proxy in zone 0,0 the entire session (same as OBSERVATION-09 — FARM targets are local).

### ~~OBSERVATION-20~~ — RETRACTED: watchdog entries are correct, analysis script bug
Post-session analysis script queried `e.get('zone')`, `e.get('npc_action_counts')`, etc. — fields that don't exist on per-entity `watchdog_npc_actions` entries. Similarly, `count`/`types` don't exist on `watchdog_structure_sample` entries. All three watchdog samplers are correctly emitting per-item entries with the right fields. No game bug.

### OBSERVATION-21 — Proxy stuck in wandering at (6,4) for final 73 ticks [FIXED ✓]
From t=7605 to shutdown t=7678, proxy position was frozen at (6,4) in `wandering` state. Obstacle clearing only fired in `targeting` state. **Fix:** extended stuck detection in `update_autopilot()` from `proxy.ai_state == 'targeting'` to `proxy.ai_state in ('targeting', 'wandering')`. Obstacle-clear (chop/mine) now fires after 60 stuck ticks in either state.

---
