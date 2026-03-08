# StarCell Bug Report — Auto-Debug Sessions

Each run: autopilot plays a new game, saves, quits. Time cap doubles per run (60s→120s→240s→420s max).
Reviewed from `debug/bugcatcher.log` after each session.

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

### BUG-03 — `in_structure=True` leaking onto humanoid overworld NPCs [ENTITY STATE]
**Category:** `fix_entity_subscreen_flag` — 4 occurrences
**Affected:** MINER (id=392), TRADER (id=481), LUMBERJACK (id=480), FARMER (id=609)
Entities had `in_structure=True` but were present in their overworld zone's `screen_entities`. Previously thought to be a bat-specific issue — it's broader. Root cause in `try_entity_screen_crossing` or structure entry/exit logic is incorrectly setting the flag on NPCs that walk near a structure entrance. The watchdog reactively clears it (applied=True) but the root cause is unresolved.

### OBSERVATION-04 — FARM quest never completes across both sessions
Active quest stays FARM from tick 1 to end in both runs. Autopilot earns carrots (seen in inventory: `{'carrot': 5}`) but the quest never triggers completion. Either the completion check isn't firing for the proxy, or the quest target count is higher than what autopilot can farm in the session window.

### OBSERVATION-05 — Per-frame entity logger very noisy
4320 log entries per session, all WOLF/BAT, no active anomalies showing. Consider gating to state-transition-only logging to reduce noise.

### OBSERVATION-06 — CONFIRMED: Player does travel extensively (115 zones visited)
Including structure interiors (virtual keys like `-1000,0`, `-1010,0`). Player samples landing at 0,0 is sampling coincidence. Not a bug.

---
