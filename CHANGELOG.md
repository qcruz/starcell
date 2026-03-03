# StarCell Changelog

All notable changes to this project are listed here in reverse chronological
order.  Entries are grouped into Features, Fixes, and Systems.

---

## [Unreleased]

### Features
- **LAKE biome** — new zone type (~3% generation chance).  Zone filled with
  WATER, SAND perimeter ring, CLIFF solid border (impassable; no sprite
  file required — falls back to colour).  Exit cells are WATER.  Deep water
  forms in the centre via a stricter all-4-cardinal-neighbors rule.  No
  entity spawns.  `check_zone_biome_shift()` now promotes a zone to LAKE
  when water coverage exceeds 50%.
- **CLIFF cell type** — solid border cell used by LAKE biome; colour `(90,80,75)`;
  added to `data/cells.py` and `constants.py`.
- **Biome spreading — general neighbor-copy rule** — every base terrain cell
  (GRASS / DIRT / SAND / WATER) has a `BIOME_SPREAD_RATE = 0.001` chance
  per update to copy a random NSEW neighbor of a different base type.
  Cells surrounded by the same type never roll.  Replaces the old 8-neighbor
  random-pick spreading block.
- **Pinned zone entrance cells** — exit border cells are seeded with the
  adjacent zone's primary biome type (deterministic) but only when they are
  currently the wrong type — no constant overwrite churn.
- **XP on player actions** — player gains 1 XP when chopping a tree, planting
  a crop, hitting an enemy (via combat system), or casting a star-spell
  enchantment (cell or entity).
- **Debug Watchdog system** (`debug/watchdog.py`) — rotating periodic sampler
  that logs random snapshots of entities, cells, zones, player state, and
  subscreen data every 300 ticks (~5 s).  Runs integrity checks on every cycle
  and logs anomalies (entity flag/tracking-list mismatches) to the BugCatcher
  log for async review.
- **Fix library** (`debug/fixes.py`) — reusable correction functions, each
  documenting a bug class, detection method, and optional safety-net correction.
  First entry: `fix_entity_subscreen_flag` for the in_subscreen/screen_entities
  mismatch class of bugs.

### Fixes
- **Combat — entities now attack the player** — two root causes fixed:
  (1) `update_entity_ai_state()` TARGETING state only checked `isinstance(target, int)`
  for the combat transition; `'player'` (string) was never promoted to combat.
  (2) outer `tick % 30` guard in `update_entities()` throttled all AI including
  combat cooldowns — on-screen entities now run every tick; stat decay stays at
  30-tick intervals.
- **Entity damage tuned** — damage formula changed from `strength + level` to
  `strength // 5`; attack interval reduced from 30 → 18 ticks (~0.3 s).
- **JSON serialization crash on new game** — `cast_wizard_spell()` passed the
  caster's `Entity` object to `take_damage()`, which stored it in `flee_target`
  and failed JSON serialisation.  Fixed by resolving to `entity_id` first.
- **Starting zone dirt accumulation** — biome spreading (0.001 rate) compounded
  into near-uniform DIRT after 150–250 year catch-up simulation.  Fixed by
  assigning variants to spread targets so they develop naturally via automata.
- **Zone entrance overwrite churn** — exit border cells were deterministically
  rewritten every automata pass even when already the correct type; added
  `cell != target` guard so they are only corrected when wrong.
- **WATER elif dead-code bug** — water evaporation rule (`WATER → DIRT when
  total_water <= 1`) was unreachable because the deep-water `elif cell == 'WATER'`
  branch caught it first.  Both rules merged into one WATER block in
  `apply_cellular_automata` and `update_single_cell`.
- **Flee state jumpiness** — flee movement ran every tick with no cooldown,
  outrunning smooth interpolation.  Wrapped in `move_cooldown <= 0` gate.
- **Bat/wolf animation frozen at 'still'** — flying entities that entered a
  subscreen (cave/house) via `npc_enter_subscreen()` could remain in
  `screen_entities` with `in_subscreen=True` if the zone key mismatched at
  removal time.  The render loop in `ui/hud.py` now skips drawing entities
  where the player is in the overworld but `entity.in_subscreen=True`, while
  still running smooth-movement and animation updates to keep internal state
  coherent.
- **BugCatcher: JSON-lines format + in-memory buffer** — replaced per-frame
  disk writes with an in-memory buffer flushed every ~300 ticks.  Log format
  changed from human-readable text to JSON-lines (one JSON object per line)
  for structured analysis.  Added `in_subscreen` and `subscreen_key` fields
  to entity log entries.  Rolling trim preserved.

---

## 2026-02-28 — BugCatcher + Stutter Fix

### Features
- **BugCatcher debug logging system** (`debug/bug_catcher.py`,
  `debug/__init__.py`) — structured logger that tracks bat/wolf entity
  animation and AI state per frame, and HOUSE/STONE_HOUSE cell mutations
  per zone update.  Log clears on every game start (new game or load).
  Rolling 2 MB cap: oldest 25% of lines dropped when limit reached.

### Fixes
- **Entity stutter on first appearance** — entities in adjacent zones receive
  AI updates while off-screen, causing `world_x/y` to lag behind grid `x/y`.
  On first render the visual position slid to catch up.  Fixed by snapping
  `world_x/y` to `float(x/y)` in `ui/hud.py` when an entity was not rendered
  in the previous frame (`tick - _last_render_tick > 1`).
- **Stone house silent decay** — STONE_HOUSE cells were being destroyed by
  termites and goblins off-screen without visible attacks.  Reduced termite
  STONE_HOUSE destruction chance from `0.002 → 0.0002` and goblin from
  `0.001 → 0.0001` in `npc_ai.py`.
- **Combat → wander premature transition** — entities checked for nearby
  threats before dropping to `wandering` state; if a threat was within 2 cells
  they re-enter `targeting` instead of wandering away mid-fight.

---

## 2026-02-27 — Cellular Automata + Entity Merge/Split Tuning

### Fixes
- Merge threshold raised to `> 3` same-type entities; split threshold requires
  `< 5` same-type AND `< 12` total entities in zone.
- Follower teleportation into structures corrected.
- Hostile-to-player combat priority fixed.
- `_double` entity creation/removal logic corrected.

---

## 2026-02-26 — Iron Ore Pipeline, Water Wells, Follower Fixes

### Features
- **Iron ore pipeline** — `IRON_ORE` cave cell (3% at depth 1, 7% at depth 2+)
  drops `iron_ore` item when mined.  Recipes: `iron_ore×2 → iron_ingot`,
  `iron_ingot + hilt → iron_sword`.  Sprites: `ironore.png`, `sword.png`.
- **Water well** — `WELL` cell (10% chance near zone center on generation).
  Humanoid NPCs (FARMER, GUARD, WARRIOR, COMMANDER, KING, TRADER, BLACKSMITH,
  WIZARD, LUMBERJACK, MINER) use WELL as a water source alongside WATER.
  MINER AI can build a well when zone has 2+ houses and no existing well.
- **Iron ore / iron ingot / iron sword** added to loot tables (cave chests).
- **Sprites**: `ironore.png → 'IRON_ORE'`, `well.png → 'WELL'`,
  `sword.png → 'iron_sword'` loaded in `engine/sprite_manager.py`.

### Fixes
- **Follower death item not removed** — skeleton follower item was stored as
  `'skeleton_bones'` but the death handler looked for
  `f"{type.lower()}_{id}"`.  Added `self.follower_items` dict
  (`{entity_id: item_name}`) populated at crafting time; death handler now
  uses `follower_items.pop(entity_id, None)`.
- **Followers attacking each other** — `find_and_attack_enemy()` in
  `npc_ai.py` now skips entity IDs present in `self.followers`.
- **Seamless zone crossing** — overworld zone transitions smoothed.
- **Item pickup / decay guards** added for edge cases.
- **Enchantment marker bugs** fixed.

---

## 2026-02-25 — Energy System, HP/NRG Bars, Structure Decay Removed

### Features
- **Energy system** — replaces `magic_pool`.  Player has `energy` /
  `max_energy`; actions cost energy; passive regeneration at 1/tick.
- **HP and energy bars** rendered in HUD.
- **Structure decay removed** — HOUSE cells no longer degrade automatically;
  only NPC attacks (termites, goblins) can damage them.

### Fixes
- Cactus spawning on water cells prevented.
- Energy fields added to save backward-compatibility loader.
- Deep water shading corrected.

---

## 2026-02-24 — Inventory UI, Weapon Gating, Tool Selection

### Features
- **Inventory name labels** displayed in the inventory panel.
- **Weapon gating** — melee attacks require a weapon item selected.
- **Tool selection** system (hotkeys cycle equipped tool).
- **Mineshaft cave divisor** for multi-level cave depth scaling.

---

## 2026-02-23 — House Growth Rate Tuning

### Fixes
- `HOUSE` cell `growth_rate` reduced from `0.01 → 0.0001` (100× slower stone
  house formation) in `data/cells.py`.

---

## 2026-02-22 — Cactus, Barrel, Stone House, Ruined Sandstone Column Cells

### Features
- `CACTUS`, `BARREL`, `STONE_HOUSE`, `RUINED_SANDSTONE_COLUMN` cell types
  added with sprites.
- Universal sprite base-layer: non-terrain cells render on top of their
  underlying terrain sprite.
- Cactus spread removed after testing (too aggressive).

---

## 2026-02-21 — Layered Cell Rendering

### Fixes
- Layered cells (e.g. IRON_ORE on CAVE_FLOOR) were using the wrong base
  terrain in non-cave biomes.  Base layer now always uses the cell's actual
  underlying terrain.

---

## 2026-02-20 — Sprite System Improvements

### Fixes
- `IRON_ORE` sprite loading corrected to use `ironore.png` filename.
- `ruined_sandstone_column` sprite path fixed.
- Sprites committed to repository.
- Last git push timestamp displayed on pause screen.

---

## 2026-02-19 — Autopilot System

### Features
- **Autopilot** — AI proxy takes over player movement when idle for > 60 ticks
  (Shift+A to toggle; off by default).
- Autopilot grace period: 15-second no-engage window after loading a save.
- Secret cave exit routing fixed with autopilot.
- Autopilot cancels on any player input.

---

## 2026-02-18 — Controls Reference, Pause Screen

### Features
- **Controls reference** panel added to the pause screen.
- In-game controls panel with all keybindings.
- `roadmap.md` added to repo; `current_features_and_planned.md` created.

---

## 2026-02-17 — NPC Behavior Updates (PR #5)

### Features
- Expanded NPC behavior state machines.
- Quest focus system: NPC quest types, unlock progression, `quest_target`
  assignment.
- Faction system for warriors.
- Wizard spell and alignment attributes.
- Trader travel movement pattern.

---

## 2026-02-16 — Autopilot Fixes and Improvements (PR #2)

### Fixes
- Multiple autopilot stability fixes.
- Save/load backward compatibility for new player fields.

---

## 2026-02-15 — Initial Public Release

### Features
- Procedurally generated overworld with biome-based zone generation.
- Subscreen system (house interiors, caves, mineshafts).
- Entity AI: FARMER, GUARD, WARRIOR, LUMBERJACK, MINER, TRADER, BLACKSMITH,
  WIZARD, BANDIT, GOBLIN, TERMITE, BAT, WOLF, SHEEP, DEER, SKELETON.
- Combat system with blocking, evading, attacking states.
- Crafting system.
- Inventory with items, tools, magic, followers tabs.
- Save/load (JSON).
- Sprite-based rendering with fallback to colored circles.
- Day/night cycle, hunger, thirst systems.
