# StarCell Bug Report — Auto-Debug Sessions

Each run: autopilot plays a new game, saves, quits. Session cap: 180–300s (extended 2026-03-14 for quest/keeper observation).
Reviewed from `debug/bugcatcher.log` after each session.

---

## Session 60 — 2026-03-26 (zone-exit resource target_type clear)

**Fixes applied before this run:**
- Clear `target_type`/`current_target`/`ai_state` to wandering on successful zone transition when `target_type` is food/water (`ai/movement.py:559`)

**Run stats:** Tick 42720→54628 (CONTINUE). ~213s. Clean shutdown.

**Population (latest snapshot, tick 51420):**
- alive=1035, spawned_this_session=211
- death_counts: {combat:58, dehydration:34} — no starvation deaths

**Level distribution (tick 54120):**
- L1=1053, L2=9, L3=6, L5=1 (total 1069)
- Still only ~1.5% of population above L1. No humanoid leveling from activity observed.

**Resource health:** both_bars_80pct=678/1069 (63%), health_80pct=664/1069 (62%). Consistent with prior sessions.

**State histogram (tick 54120, total 1069):**
```
targeting|hostile: 197   wandering|none: 173   flee|none: 156
combat|hostile: 146      targeting|water: 58   wandering|water: 56
idle|hostile: 44         flee|hostile: 33      targeting|keeper_target: 32
idle|water: 28           targeting|food: 24    wandering|clearing_action: 21
flee|water: 14           ...
```
- Combat+flee: (156+33+146+14+3+3+1)=356+146 = ~47% of population (slightly up from 44% session 59)
- `wandering|water: 56` unchanged from session 59 (55). Zone-exit fix didn't visibly reduce the cluster yet — likely because entities loaded from save already had stale state; fix prevents new accumulation going forward.

**Integrity:**
- `keeper_no_target` (type 2): WOLF ids 211, 573, 678, 679, 969, WOLF_double 1259, LUMBERJACK 625 — persistent type-2 keepers with no target across both integrity snapshots
- `entity_not_in_subscreen_but_in_subscreen_entities: 175` (NEW) — LUMBERJACK 555 in zone -1060,0 has `in_subscreen=False` but is still listed in `subscreen_entities` for that zone. Same flag/data-structure desync as bat animation bug.

**OBSERVATION:** `wandering|water: 56` unchanged. Zone-exit fix prevents new accumulation but pre-existing entities from save carry stale `target_type`. Will clear naturally as entities die and respawn.

**OBSERVATION:** Level distribution stagnant. 1.5% above L1 despite 54k+ ticks of world time. Root cause: XP is only awarded at a few specific call sites (combat hits, rare harvest rolls), not for the full range of NPC actions. Need to award XP for all non-walking actions.

**CONFIRMED BUG:** `entity_not_in_subscreen_but_in_subscreen_entities` — 175 events all pointing to LUMBERJACK 555. Entity exited subscreen but `subscreen_entities` dict was not cleaned up. Cousin of the bat animation rendering bug. Needs subscreen exit path audit.

---

## Session 59 — 2026-03-26 (flee window + enemy radius tightened)

**Fixes applied before this run:**
- Flee exit: `recently_attacked` window 60→30 ticks; `enemy_nearby` radius 8→5 cells

**Run stats:** Tick 29811→42720 (CONTINUE). ~213s. Clean shutdown.

**Population:**
- tick 34611: alive=852, deaths={combat:47, dehydration:13}
- tick 38511: alive=916, deaths={combat:59, dehydration:42}
- tick 42411: alive=925, deaths={combat:99, dehydration:65, starvation:1}

**Level distribution:**
- tick 37311: L1=891, L2=12, L3=4 (total 907)
- tick 41211: L1=907, L2=12, L3=6 (total 925)

L2 count tripled from session 58 (5→12). L3 growing slowly (2→6). Still only TERMITEs leveling from activity (8 level-ups, all TERMITE 1→2/2→3).

**Resource health:** both_bars_80pct=588/925 (64%), health_80pct=595/925 (64%).

**State histogram (tick 41211):**
```
targeting|hostile: 161   wandering|none: 146   flee|none: 136
combat|hostile: 106      wandering|water: 55   targeting|water: 44
```

Combat+flee states: 403/925 = 44% (down from 48% in session 58). Trend improving slowly.

**Death balance:** combat:99, dehydration:65, starvation:1 — first starvation death. Old age deaths dropped to 0 (short run window).

### OBSERVATION — Humanoid NPCs still not leveling via activity

Level gains are exclusively from TERMITEs because they complete mining actions frequently. Humanoid NPCs have three barriers:
1. **Combat/flee locks them out of role tasks** (still 44% of population in combat states)
2. **Role resources may be depleted** — FARMERs need CARROT3, LUMBERJACKs need TREEs; long-running world may have depleted farmland in active zones
3. **Zone travel XP** should be firing but may not be frequent enough to accumulate 100 XP

### OBSERVATION — `wandering|water` growing (46→55)

Despite target_type clear in wandering handler, water-seeking entities accumulate because new entities keep spawning into water-scarce zones and the zone-exit fallback (`seek_zone_exit`) doesn't clear target_type. Entities cycle: targeting(water)→exit→new zone→targeting(water)→exit... without clearing target_type between cycles.

**Fix planned:** Clear `target_type` in the zone-exit success path when the resource target type is food/water (the entity found no resource in old zone, entering new zone with a fresh start).

---

## Session 58 — 2026-03-26 (hunger overflow fix, continued world)

**Fixes applied before this run:**
- `save_load.py`: hunger/thirst clamped to [0, max] on load (fixes BLACKSMITH overflow)
- `entity.py`: `decay_stats()` clamps to [0, max]; `regenerate_health()` clamps fractions to [0, 1]
- Watchdog: `hunger_exceeds_max` / `thirst_exceeds_max` integrity checks added
- Save files sanitized

**Run stats:** Tick 19032→29811 (CONTINUE). ~180s. Clean shutdown.

**Population over time:**
- tick 20532: alive=624, deaths={combat:25, dehydration:9, old_age:1, other:1}
- tick 24432: alive=714, deaths={combat:53, dehydration:35, old_age:1}
- tick 28332: alive=783, deaths={combat:79, dehydration:55, old_age:1}

**Resource health:** `both_bars_80pct`=528/760 (69%), `health_80pct`=533/760 (70%). Food/water fixes are holding well — most entities stay fed and hydrated.

**Death balance:** Combat (79) now exceeds dehydration (55). Old age deaths appearing (1). Improving balance.

**Level distribution (tick 27132):** L1=750, L2=5, L3=2, L5=3 — still 98%+ at L1. 8 level-ups this session, ALL TERMITEs.

**State histogram:** `flee|none: 146`, `targeting|hostile: 131`, `combat|hostile: 91` → **368/760 entities (48%) in combat or flee at any given tick.** Peaceful NPCs can't complete role actions when half their ticks go to combat states.

**Integrity:** 5x `entity_not_in_subscreen_but_in_subscreen_entities` — pre-existing issue, not new.

### OBSERVATION — Combat pressure is blocking level gain for humanoid NPCs

TERMITEs are the only entities leveling because they complete mining actions quickly and aren't pulled into combat (they're not targeted by most hostiles). Humanoid NPCs (FARMER, LUMBERJACK, MINER) spend nearly half their time in flee/combat states, meaning they rarely complete enough role actions (harvest, chop, mine) to accumulate 100 XP for L2.

**Primary bottleneck:** Too many hostile entities per zone → peaceful NPCs constantly engage. Need to reduce hostile spawn density or shrink hostile aggro range so friendly NPCs can work without being pulled in.

### OBSERVATION — `wandering|water: 48-49` persists after fix

The `target_type` clear in wandering state reduced this (was 58 at session 56), but 48-49 remain. Entities must be entering `wandering` via a path that bypasses the `elif entity.ai_state == 'wandering':` handler (e.g., directly from targeting state with no tick before the handler runs). Cosmetic — doesn't affect gameplay but obscures histogram signal.

### CONFIRMED — Hunger overflow fully fixed

No `hunger_exceeds_max` integrity events logged. Entity 165 (BLACKSMITH) functioning normally.

---

## Session 57 — 2026-03-26 (level-up restore + continue-save mode)

**Fixes applied before this run:**
- `level_up_from_activity`: full health/hunger/thirst restore on integer level crossing
- Zone-exit urgency threshold: 0.6 → 0.4 (entities seek exits earlier when dehydrated)
- `flee` state: clears `target_type` to prevent stale resource type in histogram
- Watchdog `ai_state_cycling`: now logs `level_histogram`, `both_bars_80pct`, `health_80pct_count`
- Auto-debug: always continues from `savegame.json` when it exists (was 50/50)
- Auto-debug shutdown: also saves to `savegame.json` so next session continues from same world

**Run stats:** Tick 12630→15630 (CONTINUE from Session 56). ~50s extension. Clean shutdown.

**Population (tick 13530):** alive=512, spawned=45 (session-delta), deaths={combat:4, dehydration:2}

**Level-up events:** 8 level-ups logged — all TERMITEs (1→2 and one 2→3). No humanoid NPC level-ups observed. TERMITEs level faster because they complete mining actions more frequently.

**AI state cycling not sampled** — session too short to hit the cycling category.

### CRITICAL BUG FOUND — BLACKSMITH entity hunger=9955/max=100

Entity eid=165 (BLACKSMITH) had `hunger=9955.279` with `max_hunger=100` in the save file. This caused:
- `regenerate_health()` to compute `h_frac=99.55` → `regen ≈ 7500/tick` → entity invincible
- HUD bar to render food width at 99× the bar_width, creating a visually massive bar

**Root causes identified:**
1. `save_load.py` loaded `entity.hunger = entity_data['hunger']` with no cap — bad value from older save persisted
2. `regenerate_health()` did not clamp `h_frac` to [0, 1] — glitched hunger caused superhuman regen
3. `decay_stats()` decremented without capping at `max_hunger` — glitched value took thousands of ticks to decay naturally

**Fixes applied immediately after session:**
- `save_load.py`: `entity.hunger = min(entity.max_hunger, max(0, entity_data['hunger']))` on load
- `engine/entity.py`: `decay_stats` clamps both values to `[0, max]`; `regenerate_health` clamps fractions to `[0, 1]`
- Watchdog: new integrity check `hunger_exceeds_max` / `thirst_exceeds_max` (also flags `is_hard_cap` at 9999)
- Both save files sanitized in-place (entity 165 hunger/thirst reset to max)

---

## Session 56 — 2026-03-26 (spawned counter + stale target_type)

**Fixes applied before this run:**
- `entities_spawned_total` incremented at all 6 previously missed spawn sites:
  `spawn_skeleton()`, hostile skeleton spawn, termite spawn, zone-arrival spawn
  (spawning.py), subscreen enemy spawn (game_core.py), entity transformation (ai/movement.py)
- `wandering` state now clears `target_type` to stop stale values persisting in histogram

**Run stats:** Tick 12630 (~210s). Clean shutdown.

**Population over time:**
- tick 1449: alive=159, spawned=205, deaths={combat:20, dehydration:27} → alive+deaths=206 ≈ spawned ✓
- tick 5349: alive=334, spawned=402, deaths={combat:31, dehydration:36} → 401 ≈ 402 ✓
- tick 9249: alive=444, spawned=565, deaths={combat:43, dehydration:63} → alive+deaths=550, spawned=565 (15 gap, acceptable)

**ai_state_cycling histogram (tick 11949, 475 alive):**
```
wandering|none: 137    targeting|hostile: 60   combat|hostile: 39
flee|none: 28          flee|hostile: 27        idle|hostile: 26
targeting|keeper_target: 25   wandering|water: 20   idle|none: 19
```

**Level distribution (tick 12249, n=200 sampled):** L1=199, L3=1 — completely flat.

**Integrity events:** 2 — `keeper_no_target` for SKELETON_double (id=470) and TRADER (id=538)

### CONFIRMED FIX — spawned counter integrity check passing

alive+deaths ≤ spawned at all three snapshots. Counter is now accurate. Dev screen integrity check will show green.

### CONFIRMED FIX — stale target_type eliminated from wandering

`wandering|none` now 137 (was ~5 before). `wandering|water` dropped from 58 to 20 — most of the remaining 20 are entities that just entered wandering and haven't been processed yet (cleared next tick).

### BUG — Level distribution completely flat

199 of 200 sampled entities at L1, one at L3. Entities almost never gain XP. Likely causes:
(a) XP only gained at very specific moments (quest completion, kill) and quests aren't completing, or
(b) XP gain amounts are too small relative to thresholds, or
(c) entities cycle through states without ever landing the XP-triggering action.
Needs investigation of `entity.gain_xp()` call sites and XP thresholds.

### BUG — keeper_no_target still fires for SKELETON_double and TRADER

After the type-3 fix, two type-1/2 keepers still fire the integrity check. These entities have `keeper=True` but no `keeper_target` at the sample tick. Likely newly-promoted keepers during the lore assignment cycle that haven't yet had a target assigned. May be a timing issue rather than a true bug — need to confirm by checking if the same entity IDs repeat across consecutive samples or only appear once.

### OBSERVATION — Dehydration still dominant death cause

63 dehydration vs 43 combat. Population still growing rapidly (565 spawned, 106 dead = 84% still alive). Spawn rate likely needs capping or death rates need tuning. Old age deaths = 0, starvation = 0.

---

## Session 55 — 2026-03-26 (zone-exit fallback + death tracking)

**Fixes applied before this run:**
- `keeper_no_target` integrity check: now skips keeper_type=3 (zone wanderers naturally have no target)
- Targeting state: food/water miss with urgency≥60% now calls `seek_zone_exit` instead of wandering in place
- Watchdog `_sample_player`: now logs `death_counts`, `entities_spawned_total`, `entities_alive`

**Run stats:** Tick 10446 (~174s). Clean shutdown.

**Population over time:**
- tick 1596: alive=162, spawned=93, deaths={dehydration:56, combat:31}
- tick 5496: alive=331, spawned=126, deaths={dehydration:61, combat:34}
- tick 9396: alive=389, spawned=157, deaths={dehydration:89, combat:53}

**ai_state_cycling histogram (tick 8196, 373 alive):**
```
wandering|water: 58     targeting|hostile: 29   targeting|water: 27
targeting|keeper_target:21  wandering|clearing_action:21  idle|hostile:20
targeting|food: 17      idle|keeper_target:13   idle|water:13
```

**food_behavior (tick 7896):** Only 1 hungry NPC (BLACKSMITH hunger=60/100 targeting keeper). Food fixes working well.

**Integrity events:** 0 (keeper_no_target false positive eliminated)

### CONFIRMED — Death tracking working; dehydration dominant

Death counts are logged correctly. Dehydration is the dominant cause (89 vs 53 combat by tick 9396), starvation=0. This is expected — food fixes from previous session resolved starvation, but water scarcity remains (FARMERs in zones with no water source). Zone-exit fallback should help but may need more time to observe impact.

### BUG — `entities_spawned_total` severely undercounts

At tick 1596: alive=162, deaths=87 → total ever alive ≥249, but `entities_spawned_total`=93. The counter is missing most spawn events. Likely cause: initial `new_game()` entity creation and/or some spawn paths in `spawning.py` that don't hit the 4 incremented sites. Needs full grep of entity creation calls.

### OBSERVATION — `wandering|water: 58` large cluster

58 entities stuck in `wandering` with stale `target_type='water'` — these are entities that couldn't find water in their zone. Zone-exit fix fires at urgency≥60% but many may be below that threshold, or seek_zone_exit may put them into the exit/wander path which shows as `wandering`. The stale `target_type` after transitioning to wandering is also a cosmetic issue — `target_type` should be cleared on wandering transition.

### OBSERVATION — `targeting|keeper_target: 21` persists

Still 21 entities in `targeting|keeper_target`. These may be legitimate (outside range returning to anchor), but the count is higher than expected. Will monitor next session.

---

## Session 54 — PENDING → SUPERSEDED (AI priority cycling + death balance)

**Current dev phase goal:** Tune entity behavior so all three death types occur in
roughly balanced proportions (starvation ≈ combat ≈ old age), level distribution
shows a slowly growing tail of L2+ NPCs, and quest completions accumulate steadily.
Current + dead should always equal all-time spawned total (integrity check).

**Fixes applied before this run:**
- `_try_adjacent_consume`: probabilistic gate (% missing = chance), checks own cell
  first so NPCs walking over food fill bar; fills to max_hunger/max_thirst.
- Targeting state food/water handler: fills to max_hunger/max_thirst (not fixed 40).
- `find_and_move_to_water`: fills to max_thirst on drink.
- Keeper score: excluded from candidates when within range (was score=1, could win
  when entity had nothing else to do).
- Passive grazers skip cell decay when eating.
- Swipe animation positioned at attacker cell (was at target cell).
- Death cause tracking: `death_counts` dict in `game_core.remove_entity`.
- `entities_spawned_total` counter incremented at all 4 spawn sites in spawning.py.
- Watchdog: new `ai_state_cycling` category — logs all entities with full priority
  stack state + histogram of ai_state × target_type combinations.
- Dev screen: new DEATHS section (starvation/dehydration/combat/old_age/other),
  spawned total, alive count, and alive+dead≤spawned integrity check.

**Watchdog focus this run:**
- `watchdog_ai_state_cycling` → `state_histogram`: check for excess idle/wandering
  with low hunger (should be food or water), or keeper_target dominating when
  entities should be on quests or role tasks
- `watchdog_ai_state_cycling` → individual entries: look for entities with
  `hunger_pct < 0.4` and `target_type` not 'food'; or `keeper_in_range: true` and
  `target_type = keeper_target`
- `watchdog_food_behavior`: confirm hungry entities are reaching food cells
- Dev screen DEATHS section: note starvation vs combat vs old age split each run

**Run stats:** Tick 15461 (~257s). Clean shutdown. Population 268→367→451 over session. 0 deaths logged (death_counts not yet in watchdog at this point). Level distribution flat: L1=191, L2=6-7.

---

## Session 53 — 2026-03-20 (proxy death → respawn)

**Fixes applied before this run:**
- Proxy death now triggers full death/respawn sequence (3–10 years time pass)
- `update_autopilot()` re-enables `autopilot=True` when locked but flag cleared

**Run stats:** Tick 16049 (~267s). Clean shutdown. Quest: FARM entire session.

- **FARM**: ✅ **×2 completions** — `Quest [FARM] completed (autopilot)!` twice
- **Quest advance broken**: `active_quest` stayed 'FARM' for the entire session (tick 1500–14700). After FARM completed, the quest never advanced to LUMBER. FARM appears to complete and then immediately re-cycle or the advance logic is not firing.
- **Proxy survival**: LUMBERJACK id=262 survived all 16049 ticks. HP restored to 160 (proxy leveled up). No proxy death triggered.
- **Proxy in combat/flee**: Samples show combat/flee at ticks 4800–14700. Quest nudge is suppressed during combat/flee — proxy spends most of the session fighting, not farming.
- **Session 52 crash**: Not reproduced in Session 53. Session 52 likely a one-off (window close or transient error).

### CONFIRMED BUG — Quest cycle not advancing after completion

FARM completed twice in this session but `active_quest` never changed from FARM. The `_autopilot_advance_quest()` call should move to LUMBER after FARM completes. Either:
(a) FARM is completing but `_autopilot_advance_quest()` isn't being reached (status check condition failing), or
(b) FARM completes → advances → GATHER/FARM re-selected because loreEngine assigns FARM again on the new cycle

### OBSERVATION — Proxy combat dominates quest time

Proxy in flee/combat for all 5 watchdog samples (ticks 4800–14700). Quest nudge is skipped during these states, so the proxy effectively stops pursuing the quest goal while fighting. This is by design but worth noting — high combat pressure zones prevent quest progress.

### CONFIRMED FIX — Proxy death respawn not needed this session

No proxy death occurred, so the new respawn path wasn't exercised. Proxy HP was restored correctly by the 300-tick restore check. Respawn path will be observed in a future session.

---

## Session 52 — 2026-03-20 (proxy death respawn — crash session)

**Run stats:** Tick ~3816. Crashed without shutdown event (no traceback captured). Session 53 confirmed this was a one-off.

- Proxy (COMMANDER id=293) alive throughout, in targeting state
- FARM quest active, proxy using wander priority at tick 2316
- No proxy death triggered
- Crash cause unknown (not reproduced)

---

## Session 51 — 2026-03-20 (quest timeout removed + proxy re-spawn fix)

**Fixes applied before this run:**
- Removed `QUEST_MAX_TICKS` / quest timeout entirely — quests run until natural completion
- Proxy re-spawn fix applied after session (see confirmed bug below)

**Run stats:** Tick ~15231 (~4.2 min). Quest sequence: FARM → HUNT (proxy died mid-HUNT, autopilot froze)

- **FARM**: ✅ Completed naturally between tick 4728–8028 — first FARM completion observed
- **HUNT**: Proxy (id=312) died between tick 4728 and 8028; `_autopilot_disengage()` set `autopilot=False` but left `autopilot_locked=True`; player stuck at (21,7) for ~7000 ticks taking passive damage
- **LUMBER/MINE/etc.**: Never reached — session spent in frozen state

### CONFIRMED FIX — FARM completed naturally

With timeout removed, FARM completed between ticks 4728 and 8028 (~55 seconds). Previous sessions it was timing out at the 60s cap. Quest is achievable; it just needs time.

### CONFIRMED BUG — Proxy death freezes player (autopilot_locked desync)

**Root cause:** When proxy entity is externally removed (killed), `_autopilot_disengage()` sets `self.autopilot=False`. On the next tick, `game_core.py` sees `autopilot_locked=True` → calls `update_autopilot()` → but `update_autopilot()` early-returns on `if not self.autopilot`. Proxy is never respawned. Player is locked indefinitely.

**Fix applied:** `update_autopilot()` now re-enables `self.autopilot=True` when `autopilot_locked=True` before the early-return check, allowing the spawn path to re-engage immediately.

### OBSERVATION — Enemy facing while autopilot stuck

User observed enemies attacking the player were not facing the player while the proxy was dead and autopilot was frozen. Likely a visual artifact of `world_x/world_y` diverging from grid `x/y` at proxy death time (smooth interpolation left mid-flight). The re-spawn fix resolves the root cause (no more frozen state). Will confirm facing in next session.

---

## Session 50 — 2026-03-20 (snap fix + zone exit fix)

**Fixes applied before this run:**
- `_autopilot_opportunistic_harvest`: skip harvest if proxy `world_x/y` lag > 0.3 cells (prevents facing change mid-interpolation causing visual snap)
- `_autopilot_try_harvest_cell`: hard `dist == 1` adjacency guard before any action
- `try_entity_zone_transition`: removed center ±1 corridor constraint — any edge position can now cross if exit is open
- `try_entity_screen_crossing`: removed corridor position checks — only exit-open flag gates crossing

**Run stats:** Tick 14757 (~4 min). Quest sequence: FARM → LUMBER → MINE → HUNT → SLAY (session end)

- **FARM**: Timeout — no completion
- **LUMBER**: ✅ **2 completions** — `Quest [LUMBER] completed (autopilot)!` ×2 — consistent with Session 49
- **MINE**: Timeout — proxy (WARRIOR id=748) entered combat state at ticks 8157 and 11457; never able to mine
- **HUNT**: Timeout — proxy (GUARD id=868) logged "Stuck at exit (12,17) — entering wander cooldown" but **DID cross to zone 0,-1** by tick 14757 ✅
- **SLAY**: Session ended before observation

### CONFIRMED FIX — Zone crossing working

Proxy (GUARD id=868) crossed from zone 0,0 to zone 0,-1 during HUNT quest. Previous sessions never left the starting zone. Zone exit fix confirmed.

### OBSERVATION — Stuck-at-exit message still appears

"Stuck at exit (12,17) — entering wander cooldown" logged during HUNT. Proxy DID eventually cross (zone 0,-1 confirmed), so the corridor fix resolved the blocking issue. The stuck message is from autopilot's own exit-stuck detection (`_autopilot_nudge_zone_explore`) which triggered before the crossing completed — likely the anti-bounce cooldown (30 ticks) delayed it. Not a blocker.

### CONFIRMED BUG — MINE timing out (combat interference)

MINE proxy (WARRIOR id=748) was in combat state at both watchdog samples (ticks 8157, 11457). The proxy's aggression as a WARRIOR type pulls it into fights before it can mine. The quest target cell never gets mined because the proxy keeps fighting instead of executing the MINE behavior. Needs either: (a) spawn a MINER for MINE quests, or (b) suppress combat for quest proxies when in quest-action range.

### CONFIRMED BUG — FARM still timing out

FARM has not completed across any session. Likely the quest target is being modified by a different entity (cell changes to something other than what's expected) before the proxy arrives, or the `try_till_soil`/`try_harvest_crop` priority path still has an issue. Needs a dedicated run focused on FARM with closer logging.

---

## Session 49 — 2026-03-20 (quest target priority fix)

**Fixes applied before this run:**
- `try_chop_tree` and `try_mine_rock` now prioritize `quest_nav_target` cell when it is adjacent — root cause of zero quest completions across sessions 43-48
- Added same priority to `try_harvest_crop` and `try_till_soil` for FARM quests

**Root cause identified:** Both harvest functions scanned 4 cardinal directions and returned after the FIRST matching adjacent cell. In dense forests/stone fields, a different adjacent cell always won the scan before the specific quest target cell. `check_quest_completion` requires the EXACT `(tx, ty)` cell to change, so quests always timed out.

**Run stats:** Session killed early (user intervention), but captured:
- Quest sequence: FARM (FARMER id=276) → LUMBER (WARRIOR id=463) → MINE (LUMBERJACK id=608)
- **FARM timed out** — FARM quest probably targeted SOIL/DIRT/TREE, not CARROT3. FARMER proxy's `try_harvest_crop` only looks for CARROT3; `try_till_soil` fix not yet committed.
- **LUMBER COMPLETED** ✅ — `Quest [LUMBER] completed (autopilot)! +1 XP` — first quest completion ever logged
- MINE not observed (session killed during MINE quest)

### CONFIRMED BUG — FARM still timing out

The FARM quest can target CARROT1/2/3, SOIL, DIRT, TREE1/2. When target is DIRT, the proxy needs `try_till_soil` to change it to SOIL. Same priority problem existed there. Priority fix added to `try_harvest_crop` and `try_till_soil` in this session. Not yet verified — needs another run.

### CONFIRMED FIX — LUMBER completing

Priority fix to `try_chop_tree` is confirmed working. WARRIOR proxy for LUMBER reached and chopped the quest target cell successfully.

---

## Session 48 — 2026-03-20 (quest_nav_target — navigation confirmed, completion still 0)

**Fixes applied before this run:**
- `quest_nav_target` field on entities: highest-priority navigation, checked before keeper block in `npc_ai.py`
- `_try_complete_assigned_quest`: skips keeper reset when `quest_nav_target` is set
- `assign_zone_keepers` (world/zones.py): skips autopilot proxies to prevent keeper_type=2 override
- CACTUS drops added: `{'cell': 'SAND', 'chance': 0.8}` — was empty, proxy stalled forever on CACTUS cells

**Run stats:** 5 quests advanced (GATHER→FARM→LUMBER→MINE→HUNT), no stagnation, no crashes.

### OBSERVATION — keeper_type=1 confirmed holding via watchdog

MINER proxy (id=585) npc_quest snapshot: `keeper_type=1`. The quest_nav_target block is overriding all other keeper resets and holding type=1 between nudge cycles. Navigation is working as intended.

### OBSERVATION — HUNT proxy entered real combat

COMMANDER proxy for HUNT: `ai_state=combat`, `quest_target='WOLF(id=526) HP:14/30'`. Proxy is engaging the quest target in combat. Combat engagement path working.

### OBSERVATION — All quests still timing out, 0 completions

All 5 quests advanced via `QUEST_MAX_TICKS=3600` timeout, not completion. Stdout: `[Autopilot] Quest timeout: HUNT — advancing`. Zero `quest_complete` events in bugcatcher.log across any category.

### UNRESOLVED — quest_complete not firing despite navigation working

Root cause not yet identified. Three candidates:
1. Proxy reaches dist≤1 but `try_chop_tree`/`try_mine_rock` chops a DIFFERENT adjacent cell instead of the quest target
2. `check_quest_completion` distance check fails (player position not synced)
3. `_original_cell` mismatch (cell changed by world update before proxy arrives)

---

## Session 47 — 2026-03-20 (quest_nav_target first run — killed early)

**Fixes applied before this run:** Same as Session 48 batch (quest_nav_target approach, CACTUS drops, assign_zone_keepers proxy skip).

**Run stats:** Session killed immediately after LUMBERJACK proxy spawned — insufficient data.

### OBSERVATION — loreEngine diagnostic never appeared (correct behavior)

Added diagnostic print to `_autopilot_nudge_quest_target` to fire when loreEngine found no target. Never appeared. Root cause: `update_quests()` calls `loreEngine(quest)` for any inactive quest every tick. After `clear_target()` in `_autopilot_advance_quest`, the quest is reassigned within 1 game tick — already active before the first nudge fires (120 ticks later). Diagnostic removed. This is correct behavior.

---

## Session 46 — 2026-03-20 (random proxy types + keeper fix)

**Fixes applied before this run:**
- `try_chop_tree` now handles CACTUS/BUSH (was TREE1/TREE2 only) — MINER no longer stuck on BUSH
- Proxy excluded from `assign_zone_keepers` to prevent keeper_type=2 override on tick 1
- `proxy.keeper=True` set alongside keeper_type=1 in nudge (was False — keeper block was skipped)
- Proxy spawns at nearest walkable cell (avoids water/wall spawn)
- `_autopilot_explore_for_target` fallback added: when loreEngine finds no target, push proxy toward adjacent unloaded zones
- Random proxy type per quest: `AUTOPILOT_PROXY_TYPES` pool replaces `QUEST_NPC_TYPE` mapping

**Run stats:** tick 10878, no crashes.

### OBSERVATION — No proxy stagnation

Previous sessions had proxy stuck at same position for 3000+ ticks. This session: zero stagnation events. Proxy moved across zone (positions changed each snapshot). The walkable-spawn + keeper fixes are working.

### OBSERVATION — Quest sequence advancing correctly

- Tick 1422: FARM (proxy id=260), pos=[17,5] zone=0,0
- Tick 4722: LUMBER (proxy id=445), pos=[4,9] zone=0,0
- Tick 8022: MINE (proxy id=606), pos=[2,10] zone=0,0

GATHER→FARM→LUMBER→MINE all advanced within one session. Proxy ids differ each quest = fresh spawns working.

### OBSERVATION — Quests still advancing via timeout (~3300 ticks), not completion

Gap between quest advances is ~3300 ticks (close to QUEST_MAX_TICKS=3600). Quests are timing out rather than completing. Root cause not yet confirmed — could be:
1. NPC's own keeper_type reset overriding the nudge's keeper_type=1 (confirmed below)
2. Quest completion check not triggering (distance, cell change not detected)
3. loreEngine finding targets too far from proxy

### OBSERVATION — NPC's own behavior resets keeper_type between nudges

LUMBER proxy was COMMANDER (id=445). At tick 6222: `keeper_type=3`, `quest_focus='COMBAT_ALL'`. The nudge sets `keeper_type=1` every 120 ticks, but COMMANDER's `_try_complete_assigned_quest` (called on each combat contact) resets `keeper_type = _base_keeper_type = 3`. So the proxy orbits in zone-keeper mode between nudges instead of walking to the quest cell. This is the **primary blocker for cell quest completion** — needs a different approach (see next section).

### OBSERVATION — Random proxy types working as designed

Different NPC types assigned per quest. COMMANDER doing LUMBER is intentional — reveals that NPC types with combat-focused base quests (COMMANDER, WARRIOR, GUARD) won't navigate to resource cells effectively. This data is useful for identifying which NPC types need quest-steering improvements.

### CONFIRMED BUG — NPC's own keeper management overrides nudge-set keeper_type

**Impact:** Cell quests (LUMBER, MINE, FARM) never complete because the proxy's NPC AI resets keeper_type after every state transition. The nudge sets keeper_type=1 for 120 ticks, but any NPC completing a "base quest" sub-step resets it to 3 (the `_base_keeper_type` fallback). Needs investigation — either anchor the keeper_type more persistently or use a different mechanism to steer the proxy to quest cells.

---

## Sessions 43–45 — 2026-03-20 (keeper_target navigation + combat aggression fixes)

Fixes applied across these runs — results fed into Session 46:

### FIXED — Proxy position jumping from nudge state overrides

The nudge was forcing `proxy.ai_state = 'targeting'` and `proxy.current_target` every 120 ticks, externally overriding the NPC's own state machine. This caused visible jerking. Fix: nudge now uses `proxy.keeper_target` / `proxy.keeper_target_pos` / `proxy.keeper_type = 1` for cell quests — the NPC AI navigates naturally without state interruption. For combat quests: `proxy.quest_target = target_entity_id`, NPC AI handles combat.

### FIXED — WARRIOR proxy never attacked (aggressiveness=0.0)

All proxy types had `aggressiveness=0.0`, `combat_chance=0.0` — the proxy never initiated combat, so `_proxy_damaged_target` was never set, and combat quests could never complete. Fix: combat quests get `aggressiveness=0.6`, `combat_chance=0.5`, `flee_chance=0.05`. Non-combat quests keep low aggression (0.1) with high flee (0.85).

### FIXED — Obstacle-clear and harvest were stopping the proxy mid-navigation

`proxy.ai_state = 'wandering'` and `proxy.current_target = None` were set in both `_autopilot_try_harvest_cell` and `_autopilot_try_clear_obstacle`, cancelling the keeper_target navigation. Removed. Proxy now just faces the cell and executes the action without interrupting its navigation state.

### FIXED — loreEngine picking first tree/stone in grid scan (row 0 first)

LUMBER/MINE quest targets were assigned as the first cell found scanning from (0,0), often at the opposite side of the zone. Fix: loreEngine now finds the nearest tree/stone to the player position (Manhattan distance) for local-zone assignments.

---

## Session 42 — 2026-03-20 (run 26 — harvest stop + combat gate)

Two fixes applied before this run:

### FIXED — Proxy movement snap during mining/chopping

`_autopilot_try_harvest_cell` was calling `try_chop_tree`/`try_mine_rock` while proxy was still in targeting state — caused visible snap as proxy moved into the cell. Fix: explicitly stop proxy (clear current_target, set ai_state='wandering', call `update_facing_toward`) before executing the harvest action. Same fix applied to `_autopilot_try_clear_obstacle`.

### FIXED — Obstacle-clear only handled TREE/STONE, missing CACTUS/BUSH

Expanded `_CHOPPABLE` to include CACTUS, BUSH. Added `_MINABLE`, `_PLANTABLE`, `_TILLABLE`, `_CROPPABLE` constants. Obstacle-clear and harvest now reference shared frozensets.

### FIXED — Combat quests completing on NPC dehydration deaths

`check_quest_completion` was crediting completion whenever the entity died in the same zone, including from dehydration. Proxy combat was irrelevant.

Fix: two-part:
1. `update_autopilot` now tracks `proxy.combat_target == quest.target_entity_id` each tick. When true, updates `quest.progress` and sets `quest._proxy_damaged_target = True`.
2. `check_quest_completion` (lore/engine.py) now requires `quest._proxy_damaged_target == True` before crediting completion when entity is dead. If entity died without proxy damage, clears target and reassigns.

`_proxy_damaged_target` is reset to False on `_autopilot_advance_quest()`.

---

## Sessions 38–41 — 2026-03-20 (runs 25–28 — cell quest targeting chain)

Session 41: 11368 ticks. FARM/LUMBER/MINE all timed out again. Zero harvest_cell calls. MINE completed once in session 39 (likely by chance — obstacle-clear mining a rock adjacent to the quest target). Several bugs found and fixed in sequence:

### FIXED — Proxy spawn location (user reported proxy spawning in lake)

Proxy spawns at `self.player['x'], self.player['y']`. Player position is not checked for walkability before spawn. Proxy can land on water/impassable tiles and be stuck immediately. Needs spawn location validation — pick nearest walkable cell to player. Not yet fixed — adding to next_up.

### FIXED — 65% natural-behavior skip was cancelling cell-quest steering

The nudge returned early 65% of the time AND explicitly cleared `ai_state = 'wandering'` for any in-progress targeting. For FARM/LUMBER/MINE/GATHER, the natural NPC AI chops random cells, not the specific quest target. Completion requires the SPECIFIC target cell to change. Fix: skip the 65% early-return when the proxy is in the same zone as the target cell (`in_same_zone` flag).

### FIXED — Wrong current_target format (2-tuple vs ('cell', tx, ty))

Nudge was setting `proxy.current_target = (tx, ty)` (2-tuple). The NPC AI targeting code checks `len >= 3 and current_target[0] in ['cell', 'entity']`. A 2-tuple hits a fallback path that walks ONTO the cell (not adjacent), getting stuck on blocking tiles (trees, stone). Fix: use `('cell', tx, ty)` so NPC AI stops at dist==1 (adjacent).

### FIXED — _autopilot_try_harvest_cell missing SOIL/DIRT handlers

For FARM quests targeting SOIL/DIRT cells, `_autopilot_try_harvest_cell` printed "already changed?" and did nothing. Fix: added `SOIL → try_plant_seed()`, `DIRT/GRASS/SAND → try_till_soil()`.

### BUG — harvest_cell still never fires despite fixes

After all three fixes, no `[AP] harvest_cell:` prints appear across sessions 40–41. The proxy navigates (obstacle-clear triggers when adjacent to target), but the nudge's `dist <= 1` branch never fires `_autopilot_try_harvest_cell`. Root cause under investigation:
- Proxy may reach dist==1, NPC AI idles, obstacle-clear chops the target cell — but `check_quest_completion` doesn't detect because player was not within dist≤2 at that tick
- OR: the nudge fires at dist > 1 (proxy hasn't arrived yet), sets targeting, but by next nudge the proxy has moved away again

Next step: add dist print to the nudge's same-zone branch to observe proxy distance to target at each nudge cycle.

### OBSERVATION — loreEngine called by update_quests within 1 tick of clear_target

`update_quests()` calls `loreEngine(quest)` for any inactive quest every tick (line 665-666 in lore/engine.py). So after `clear_target()` in `_autopilot_advance_quest`, the quest is reassigned to a nearby target within 1 game tick — BEFORE the first nudge fires (120 ticks later). The diagnostic loreEngine print in the nudge never appeared because quest was already 'active' again. This is correct behavior; diagnostic print removed.

---

## Session 37 — 2026-03-20 (run 26 — diagnosing loreEngine target assignment)

Session killed immediately after LUMBERJACK spawned — insufficient data. Confirmed: loreEngine print never appeared because `update_quests()` re-activates the quest within 1 tick of clear_target, so quest is already 'active' when the nudge runs.

---

## Session 36 — 2026-03-20 (run 25 — stale target clear fix)

Session ran ~190s. FARM timed out, LUMBER timed out, MINE started (MINER spawned). Zero quest completions.

### BUG — clear_target on quest advance may leave quest permanently inactive

After `_autopilot_advance_quest()` clears the new quest's target, the quest status becomes 'inactive'. The nudge calls `loreEngine(quest)` to re-assign. If loreEngine can't find a nearby tree/stone (or the proxy is in a barren zone), it returns False and the quest stays 'inactive' forever — nudge exits early every cycle, no steering, no harvest, timeout fires.

Session confirmed: zero `[AP] harvest_cell:` prints across all three quest types. The nudge is not reaching the target_cell steering block.

Next step: diagnostic print after loreEngine call to confirm whether it assigns or fails.

---

## Session 35 — 2026-03-20 (run 25 — verify proxy respawn fix)

FARM timed out, LUMBER timed out, MINE started. Zero harvest_cell calls. Proxy types spawned correctly (FARMER → LUMBERJACK → MINER) confirming session 34 fix holds. But quest targets from game-start are stale by the time those quests become active — proxy is in a different zone than the original target.

---

## Session 34 — 2026-03-19 (run 24 — proxy respawn fix for quest type transitions)

10228 ticks. Session ran ~190s.

### FIXED — LUMBERJACK/MINER proxy never spawning after FARM→LUMBER or LUMBER→MINE advance

Root cause: `_autopilot_advance_quest()` calls `_autopilot_disengage()` when the new quest requires a different NPC type. `_autopilot_disengage()` sets `self.autopilot = False` (designed for player takeover), which prevents `update_autopilot()` from ever calling `_autopilot_engage()` again. The LUMBERJACK proxy was never created; LUMBER quest ran its full 3600-tick timeout with no activity.

Fix: In `_autopilot_advance_quest()`, immediately after `_autopilot_disengage()`, set `self.autopilot = True` to keep the autopilot running through the proxy swap.

### CONFIRMED — Quest progression working across multiple types

Results this session:
- FARM completed ×2, then timed out (quest re-assigned after completions but stalled)
- LUMBER completed ×1 (proxy spawned, navigated to target tree, chopped)
- MINE started (MINER proxy spawned at tick ~10000+, session ended before completion)

Previous sessions: LUMBER/MINE/GATHER always timed out (0 completions). Now working.

### OBSERVATION — FARM "already changed?" repeated calls after completions

`[AP] harvest_cell: target (11,3) is now 'SOIL' — already changed?` fires repeatedly on same (11,3) target after FARM completes. This is the FARM quest target_cell still pointing to a now-tilled cell. Harmless but noisy — suggest clearing or refreshing FARM target on quest status change to 'cooldown'.

### OBSERVATION — LUMBER timed out on 2nd cycle

After first LUMBER completion, quest re-assigned. The new LUMBER target was not reached before the 3600-tick timeout. Likely the second target was in a different zone and cross-zone travel didn't complete in time. Worth watching in future sessions.

---

## Session 33 — 2026-03-19 (run 23 — diagnostic run, LUMBER failure mode)

Session run to observe diagnostic prints in `_autopilot_try_harvest_cell`. No harvest_cell prints appeared for LUMBER quest — LUMBERJACK proxy was never spawned after FARM→LUMBER advance (see Session 34 root cause above).

---

## Session 29 — 2026-03-19 (run 19 — quest completion steering)

13907 ticks. 467 entities. 75 zones. Player zone 0,0. 0 stagnations. Player took combat damage (health 82).

### CONFIRMED — Quest completions now happening in autopilot sessions

3 quests completed this session: COMBAT_HOSTILE, HUNT, SLAY. Previous sessions had 0 completions. Change: proxy now actively steers toward specific target cell within the quest's zone rather than wandering randomly. XP at tick 11385: 2 (2 combat completions credited before SLAY at end).

### CONFIRMED — Tools persisting and accumulating across full session

axe:1, hoe:1, shovel:1, pickaxe:1, bucket:1 all present from tick 1485 through shutdown. Tool slots progressively filled: 7 at tick 3237, 8 at 6537, 9 at 9885 (all slots filled). Weapon slot equipped (enchanted_sword crafted again).

### CONFIRMED — Persistent flee respawn working

"Persistent flee — switching EXPLORE → SLAY, respawning as WARRIOR" fired. Proxy re-engaged as WARRIOR and completed SLAY quest shortly after.

### OBSERVATION — Zero stagnations

No stagnation events logged. Flee detection + flee-stuck escape fully preventing lock-in states.

### OBSERVATION — XP progression: 0→2 over session

Level stayed at 1 (XP reward=1 per quest, 3 completed = 3 XP, but level threshold not reached). Quest completion is now driving forward. Next focus: getting more non-combat quest completions (GATHER/LUMBER/MINE) and accumulating wood/stone for crafting.

---

## Session 28 — 2026-03-19 (run 18 — tool-seeding fix verification)

10320 ticks. 394 entities. 76 zones. Player zone 0,0. Player health 81.3 (took damage in combat).

### CONFIRMED FIXED — Tools now persist across full session

Inventory at tick 1437: axe:1, hoe:1, shovel:1, pickaxe:1, bucket:1, enchanted_sword:1. Same tools present at tick 8037 (none lost). Tool-seeding fix confirmed: proxy no longer consumes player tools through the sync.

### CONFIRMED — Enchanted sword crafted and equipped to weapon slot

`equip enchanted_sword → weapon` fired. Inventory state at tick 3237 shows `equip=['weapon']`. enchanted_sword assigned to tool slot 5. Gear equip and tool slot assignment both working end-to-end.

### CONFIRMED — Tool slots progressively filling

By tick 9837: 7 slots filled (axe, hoe, shovel, pickaxe, bucket, enchanted_sword, hoe). Multiple assignment sequences executed correctly.

### OBSERVATION — One stagnation event (proxy position stuck)

Single proxy stagnation logged. Proxy still spending time in flee state (tick 8037: flee). Persistent flee detection (1800 ticks) is the escape hatch — not yet visible in this session since flee ticks were spread across movement.

### OBSERVATION — Quest cycle active but resource accumulation slow

Quest switches: FARM→GATHER→LUMBER→COMBAT_HOSTILE→SEARCH→RESCUE→FARM. Carrot appeared at tick 4737, seeds at tick 8037. No stone/wood/iron yet — proxy is FARMER type for most of the session, prioritizing farming over mining/chopping.

---

## Session 27 — 2026-03-19 (run 17 — persistent flee + tool seeding fix)

16680 ticks. 471 entities. 83 zones. Player zone 0,0. No proxy stagnation.

### CONFIRMED BUG — Proxy seeding tools caused player to lose them via sync

**Symptom:** Initial inventory at tick 1437: axe:1, hoe:1, shovel:1, tree_sapling:3, seeds:1. By tick 4737: only seeds:1, carrot:1. All tools and saplings disappeared within ~3300 ticks.

**Root cause:** `_autopilot_engage()` seeded ALL player items (including tools) into `proxy.inventory`. When the NPC AI proxy used a hoe (till action) or shovel (dig action), it removed the item from `proxy.inventory`. The `_sync_inventory_to_player` then applied delta=-1 → player lost the tool.

**Fix (applied):** Proxy seeding now skips items where `is_tool`, `is_spell`, or `is_action` is True. Only resource/consumable items are seeded into the proxy. Tools remain in the player's inventory exclusively.

### CONFIRMED FIXED — Persistent flee detection working

"Persistent flee — switching GATHER → SLAY, respawning as WARRIOR" triggered near end of session (tick ~16400). Proxy disengaged and would have re-engaged as WARRIOR. Session timer expired before re-engage completed — expected behavior.

### OBSERVATION — Tool slots clearing over session

At tick 3237: slots had shovel in slot 2. By tick 6537: all slots empty. Shovel disappeared (confirmed caused by tool-seeding bug above). With the seeding fix applied, tools should persist through sessions.

### OBSERVATION — Resource accumulation still minimal

seeds:1, carrot:1 unchanged from tick 4737 to shutdown. Proxy was mostly fleeing. Persistent flee fix triggers re-engage as WARRIOR — next sessions should show WARRIOR proxy accumulating combat drops (meat, bones) rather than staying in flee.

---

## Session 26 — 2026-03-19 (run 16 — flee-state fix verification)

11888 ticks. 474 entities. 95 zones. Player crossed to zone 1,0. Player health 110.8 (healed above base).

### CONFIRMED FIXED — Proxy flee-state stagnation

Zero stagnation events logged. Proxy moved between grid positions across the session (zone 0,0 → 1,0). Flee-state stuck detection now fires correctly.

### OBSERVATION — Proxy spends ~80% of session in flee state

Player samples at ticks 4911, 8211, 11511 all show proxy_state=flee. Proxy is FARMER type (spawned for GATHER quest), which has low combat rating and flees from hostiles. As entity count grows (~474) and the player zone accumulates bandits/goblins/skeletons/wolves, the FARMER proxy gets into persistent flee loops. Proxy does still move and cross zones; resource accumulation is minimal (seeds:2→3, meat:1 appeared). Not a crash; documented for future proxy-role-assignment improvement.

### OBSERVATION — `selected_tools` transient mismatch during multi-step sequences

At tick 10011, `selected_tools='carrot'` with `tool_slots[2]=None`. This is a mid-sequence transient state captured by the watchdog between an unequip and the matching equip queued action. Not player-visible (player is not controlling during autopilot). No gameplay impact — number keys read `tool_slots` directly.

### OBSERVATION — One MINER keeper_no_target integrity hit (id=345, tick 6111)

Humanoid filter working correctly — this is a legitimate anomaly (MINER with keeper=True briefly without a target). Single occurrence, likely during zone transition. No action needed.

### OBSERVATION — Tool slot assignment sequences executing

Console confirmed: T+I+number+click sequences firing correctly. Carrot and seeds assigned to slots. `close_menus post-action` firing after each sequence.

---

## Session 25 — 2026-03-19 (run 15 — toolbar/reference architecture stress test)

11935 ticks. 486 entities at shutdown. 86 zones explored. Player stayed zone 0,0.

### CONFIRMED BUG — Proxy stagnation in `flee` state

**Symptom:** Proxy stuck at grid [1,1] for ~3300 ticks (tick ~8200 to 11517). Proxy ai_state was `flee` the entire time. `last_input_tick` was 1617, meaning no new inputs were generated for nearly the full session duration.

**Root cause:** Stuck detection in `update_autopilot()` (autopilot.py:147) only checks `targeting` and `wandering` states. When hostile NPCs cornered the proxy at [1,1] and forced it into `flee`, neither obstacle clearing nor stuck counter increments fired. The proxy remained frozen with menus open.

**Fix (applied):** Extended stuck detection to include `flee` state. After 300+ ticks stuck in flee, force proxy ai_state back to `wandering` so it can resume normal movement.

### OBSERVATION — Tool slot assignment working

Tool slots progressively filled: slot 1 (shovel) at tick 3417, slots 0+1 (seeds+shovel) at tick 6717, slots 0+1+2 at tick 10017. Assignment sequence (T→I→number→click) confirmed functional.

### OBSERVATION — Actions dict correct

All four actions present throughout: attack, block, inspect, shove. `selected_actions` cycled between block and inspect across samples — action selection working.

### OBSERVATION — New watchdog categories firing

`watchdog_inventory_state` and `watchdog_favor` both sampled correctly (3 entries each). Favor values correct: peaceful NPCs at 0, hostiles (WOLF, SKELETON, BANDIT, GOBLIN, TERMITE) at -50.

### OBSERVATION — Equipment slots never filled

All equipment slots null across all three inventory state samples. No equippable items (weapons, armor) appeared in inventory during this session — autopilot harvested only seeds/shovel/carrot. Not a bug; need combat/crafting paths to yield equippable gear before this can be tested.

### OBSERVATION — `selected_items` pointing to missing item

Player sample at tick 11517 shows `selected_items: 'axe'` but axe not present in `items_top5` or `items_count=3`. Stale selection reference when item leaves inventory. Low priority cosmetic issue — doesn't affect gameplay.

### OBSERVATION — No resource accumulation

items_count stayed at 3 (seeds:1, shovel:1, carrot:1) from early session through end. No wood/stone/iron harvested. Related to proxy being stuck in flee/cornered for most of the session — opportunistic harvesting never fired.

---

## Session 24 — 2026-03-19 (run 14 — prior session, pre-watchdog-category additions)

Session ran before `watchdog_inventory_state` and `watchdog_favor` categories were wired in. No category data available for those samplers.

### CONFIRMED (fixed before this run) — keeper_no_target integrity flood

242 false-positive integrity entries from non-humanoid types (animals, hostiles). Fixed by filtering `keeper_no_target` check to `_KEEPER_HUMANOIDS` set.

### CONFIRMED (fixed before this run) — Proxy sync reversing crafted items

Proxy sync compared `proxy_flat` vs `player_flat`; items crafted by player (not in proxy) generated negative delta → removed from player inventory. Fixed by using `proxy._sync_baseline` (proxy's own previous state) as the comparison baseline.

### CONFIRMED (fixed before this run) — Tool slot double-counting in crafting

`get_craftable_recipes` and `get_all_craftable_items` counted tool_slots separately when tools already live in `items` dict. Removed tool_slots counting from both methods.

---

## Session 23 — 2026-03-15 (live player review — chest/faction/NPC behavior fixes)

### FIXED — WOOD and PLANKS appearing as overworld grid cells

**Root cause:** `ITEM_TO_CELL` in both `constants.py` and `data/cells.py` contained `'wood': 'WOOD'` and `'planks': 'PLANKS'`, causing `place_selected_item()` to stamp WOOD/PLANKS as permanent terrain cells.

**Fix:** Removed `'wood'` and `'planks'` entries from `ITEM_TO_CELL` in both files. Wood and planks now only exist as inventory items — they drop as item overlays rather than grid cells.

---

### FIXED — WOOD cells appearing when NPC empties a chest (time-pass)

**Root cause:** In `world/zones.py` time-pass entity loop, when an NPC picked up all items from a chest, the code set `grid[cy][cx] = 'WOOD'` instead of leaving the chest cell intact.

**Fix:** Removed the erroneous cell assignment. The chest cell is left in place; the empty-chest decay system handles cleanup.

---

### FIXED — Empty chests not decaying (dead code — wrong `elif` level)

**Root cause:** The `elif cell == 'CHEST':` branch in `update_zone_with_coverage()` was at the outer `if/elif` level rather than inside `if cell in CELL_TYPES:`. Since CHEST is in CELL_TYPES, the outer branch was never reached — the decay code was effectively dead.

**Fix:** Moved `elif cell == 'CHEST':` inside the `if cell in CELL_TYPES:` block so it fires correctly each zone update.

---

### FIXED — Empty chests decaying to GRASS in desert/mountain biomes

**Root cause 1:** Fallback cell hardcoded to `'GRASS'` instead of the zone's biome base cell.
**Root cause 2:** `base_cell` variable referenced before it was defined (computed later in the biome reversion block), causing `UnboundLocalError`.

**Fix:** Computed `base_cell` from a biome→cell map before the cell loop so it is available to the chest decay branch. Fallback now uses `base_cell` (SAND for desert, DIRT for mountains/tundra/swamp, GRASS otherwise). Structure zone chests fall back to `FLOOR_WOOD`.

---

### FIXED — Too many chests accumulating across zones

**Root cause:** NPCs depositing items into nearby chests, then creating a new chest on inventory overflow, with no mechanism to merge nearby chests or remove empty ones quickly enough.

**Fix (two parts):**
1. `consolidate_chests(zone_key)` added to `systems/crafting.py`: each zone update, finds all CHEST cells, merges contents of chests within 5 cells of each other into the chest with the most items, leaves secondaries empty (for decay). Called alongside `consolidate_dropped_items()` in `update_zone_with_coverage()`.
2. Empty chest decay rate increased to 50% per zone update (from 5–10%) in both overworld and structure zone loops.

---

### FIXED — Commander faction not appearing on dev info screen after save/load

**Root cause:** `self.factions` was never serialized. Entities retained `entity.faction` through save/load, but `self.factions` was always empty after any reload — so the dev screen found no registered factions.

**Fix:** Added factions to `systems/save_load.py` save/load: zones stored as lists (JSON-safe), restored as sets on load.

---

### FIXED — Faction name on entity not registered in `self.factions` (hostile factions)

**Root cause:** Multiple code paths set `entity.faction` without guaranteeing the faction name appears in `self.factions` — particularly after save/load or when `create_hostile_faction()` reverse-lookup fails. The dev screen reads `self.factions`, so unregistered factions are invisible even when present on entities.

**Fix:** Added `_lore_sync_faction_registry()` to `lore/engine.py`, called each lore cycle (600 ticks). Scans all live entities with `entity.faction` set; registers any faction name missing from `self.factions` and ensures the entity is in the warriors list.

---

### FIXED — `_lore_ensure_commander_factions` skipping already-factionless Commanders after reload

**Root cause:** Skip condition was `if getattr(entity, 'faction', None): continue` — this skipped any Commander that had `entity.faction` set, even if that faction name was not in `self.factions`. It also only scanned a 9×9 radius around the player, missing Commanders in loaded but distant zones.

**Fix:** Skip condition changed to require both `entity.faction` non-None AND the faction name present in `self.factions`. Now also scans all `self.entities` (not just the 9×9 radius).

---

### FIXED — NPCs standing still while in wandering state

**Root cause:** The wandering state block had a hardcoded `if random.random() < 0.6: self.wander_entity(entity)` — meaning 40% of wandering ticks did nothing. Standing still is meant to be handled exclusively by the `idle` state.

**Fix:** Removed the conditional; `wander_entity()` is always called in the wandering block. Transition to idle is controlled by the `idleness` prop and inventory scaling as intended.

---

### FIXED — Instantiated zones never shrinking (dead zone accumulation)

**Root cause:** `self.instantiated_zones` is an append-only set. Evicted zones (removed from `self.screens` to free memory) were never removed from `instantiated_zones`, causing the count to grow unboundedly and inflating zone-wide loops.

**Fix:** Added a 600-tick cleanup in `world/zones.py`: `self.instantiated_zones &= set(self.screens.keys())` — syncs the set against active screens each cleanup cycle.

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

### FIXED — Wrong base quest type on FARMER/MINER/LUMBERJACK

**Root cause (confirmed via debug tracking):** Entity type is changed by multiple code paths AFTER `quest_queue` is already initialized with the old type's base quest. The type-change paths were:
- `world/zones.py` (settlement logic): TRADER→FARMER/LUMBERJACK/MINER, GUARD→FARMER/MINER — no quest reset
- `systems/factions.py` `promote_to_commander()`: WARRIOR→COMMANDER — no quest reset
- `npc_ai.py:1115` warrior promotion (already had partial fix from prior session)
- `npc_ai.py:3171` `check_npc_transformation` settlement transform (already had fix from prior session)

Debug trace confirmed entity 24 was type=GUARD when quest_queue initialized (COMBAT_HOSTILE), later became FARMER via `world/zones.py:586`. `engine/entity.py` `level_up()` GUARD→WARRIOR also found but WARRIOR has same base quest (COMBAT_HOSTILE) — no mismatch.

**Fix:** Added quest reset block (`del quest_queue`, clear `quest_focus`/`quest_target`) immediately after every `entity.type = <new_type>` assignment in:
- `world/zones.py:574–600` (trader and guard settlement rewrites)
- `systems/factions.py:456` (warrior→commander promotion)

Removed debug tracking attributes (`_quest_init_type`, `_quest_init_eid`) and `[QuestBug]` print from `npc_ai.py`.

**Verification run (Session 22, Run 3 — 2026-03-14, ~10,991 ticks, NEW GAME):**
Zero `[QuestBug]` prints. No wrong-quest entries in watchdog samples. Entity count at shutdown: 485 (well below 600 threshold). World healthy: 128 zones, 7 structures, 1 follower. Bug confirmed resolved.

---

### FIXED — Autopilot gaining XP from synthetic key events

**Root cause:** `gain_xp(1)` is called in `game_core.py` inside the KEYDOWN/MOUSEBUTTONDOWN event handler for every action key (SPACE, E, N, P, D, X, L, etc.). Synthetic autopilot events (`_ap_synthetic=True`) correctly skip idle detection but were NOT skipping XP grants.

**Fix:** Added early return in `gain_xp()` in `systems/combat.py`:
```python
if getattr(self, 'autopilot', False):
    return  # Autopilot proxy does not earn XP
```
This gates all XP from any source during autopilot mode.

### FIXED — Autopilot damage not visible in HUD/watchdog

**Root cause:** NPCs attack the proxy entity (real Entity object in `self.entities`), reducing `proxy.health`. But `self.player['health']` was never synced from `proxy.health`, so the HUD and watchdog always showed 100 HP regardless of combat damage taken.

**Fix:** Added health sync in `_sync_player_from_proxy()` in `autopilot.py`:
```python
self.player['health']     = proxy.health
self.player['max_health'] = proxy.max_health
```
Damage is now visible in the HUD and logged correctly by the watchdog.

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
