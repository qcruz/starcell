# StarCell Bug Report — Auto-Debug Sessions

Each run: autopilot plays a new game for 2–3.5 min, saves, quits.
Reviewed from `debug/bugcatcher.log` after each session.

---

## Session 1 — 2026-03-07  (~7431 ticks, ~2 min)

### BUG-01 — Watchdog integrity check is 100% false positives [CRITICAL / WATCHDOG]
**Category:** `integrity_anomaly` — `entity_not_in_subscreen_but_in_subscreen_entities`
**Count:** 6770 entries, 470 unique entities, zero true positives
**Root cause:** The integrity check builds a reverse map from ALL `screen_entities` keys, but `screen_entities` stores both overworld zones AND structure zones under the same dict. Every overworld entity's own zone key appears as a "found in subscreen" hit.
**Fix needed:** Filter the reverse-map loop to only iterate over keys present in `game.structures` (true structure keys), not all of `screen_entities`.

---

### ~~BUG-02~~ — RETRACTED: Ghost follower entries were false alarm [ANALYSIS SCRIPT]
**Timeline:**
- tick=2031: skeleton id=288 logged correctly, zone=0,0, zone_match=True
- tick=4131: follower entry with `id=None, type=None, zone=None` — ghost
- tick=6231: same ghost entry again

**Player state:** `followers=[]` at tick=3531 (between the two ghost ticks), yet the sampler still iterates and logs null-field entries for two more cycles.
**Root cause:** After the skeleton died/was removed, either a `None` or stale ID remains in `self.followers`, and the referenced entity object has None-valued attributes (`type`, `screen_x`, etc).
**Fix needed:** Follower cleanup on death should ensure `self.followers` is fully purged (no None entries). Also the sampler should guard `if fid is None: continue`.

---

### OBSERVATION-01 — Player never leveled up [XP SYSTEM]
Level stayed at 1 for all 7431 ticks. Autopilot proxy does earn XP (on_attack, harvest) but the player dict `level` never incremented. Could be expected given short run duration, or XP may not be syncing from proxy to player dict.

### OBSERVATION-02 — Active quest (FARM) never completed or cycled
Same quest active at all 3 player sample points (ticks 1431, 3531, 5631). Worth tracking over longer sessions to see if autopilot can complete quest objectives.

### OBSERVATION-03 — All player samples show zone 0,0
Autopilot may not have crossed zone boundaries during this session, or all 3 sample windows happened to catch it at home zone. Not necessarily a bug — track across more sessions.

---
