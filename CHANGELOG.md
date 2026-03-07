# StarCell Changelog

All notable changes to this project are listed here in reverse chronological
order.  Entries are grouped into Features, Fixes, and Systems.

---

## 2026-03-07 — Cellular Automata Overhaul, Drought System, Biome Balance

### Features
- **Drought system** — growth multiplier decreases and decay multiplier increases every tick
  without rain.  `drought_severity = min(elapsed_ticks / 9000, 1.0)`; growth floors at 10%
  of normal rate at maximum drought; decay peaks at 1.5×.  All cell automata rules use
  `_growth` / `_decay` multipliers instead of raw tick probability.
- **Extended dry periods** — `RAIN_FREQUENCY_MIN` raised from 30 → 1800 ticks;
  `RAIN_FREQUENCY_MAX` raised from 250 → 18000 ticks.  Zones can now experience sustained
  droughts between rainfall events.
- **Rain-gated water spread** — flooding (DIRT→WATER when 3+ adjacent water) and grass
  absorption (GRASS→WATER when 1+ adjacent water) now only trigger while `is_raining` is
  True, but at much higher base rates (`FLOODING_RATE 0.08`, `GRASS_WATER_ABSORB_RATE 0.02`).
- **Tree crowding decay** — new `TREE_CROWD_DECAY_RATE = 0.001` rule: any tree adjacent to
  another tree has a per-update chance to decay to GRASS, producing naturally spaced
  checkerboard forest patterns.  Replaces the old `tree_count >= 4` overcrowding rule.
- **Desert stability** — `DIRT_SAND_SPREAD_RATE = 0.008` ensures dirt adjacent to sand
  reverts faster than biome spreading can convert it; `GRASS_SAND_DECAY_RATE = 0.003`
  similarly reclaims grass cells on desert edges.
- **Item drop consolidation** — on entity death, 1–2 items scatter individually near the
  body (render as individual item sprites); all remaining drops consolidate into a single
  pile at the entity's position (renders as itembag).
- **Equal biome distribution** — zone biome on generation now selected via
  `random.choice(list(BIOMES.keys()))` instead of a weighted probability roll.  All biomes
  have equal instantiation chance.

### Fixes
- **Cobblestone cascade** — tree→COBBLESTONE conversion now requires 5+ cobblestone
  neighbors; trees with 1–4 cobblestone neighbors decay to GRASS instead.  Prevents a
  single cobblestone cell from triggering a chain reaction across surrounding tree cells.
- **Player float on structure entry/exit** — `world_x/y` now snapped to the new grid
  position in all 5 transition functions (`enter_structure`, `exit_structure`,
  `descend_cave`, `ascend_cave`, `_exit_secret_cave_entrance`), preventing smooth
  interpolation from sliding the player from the old position.
- **Follower cleanup after save/load** — `follower_items` dict was never serialized; after
  loading it was always empty so follower item removal on death was silently skipped.  Both
  save and load now serialize `follower_items` with int↔str key conversion; a fallback
  reconstructs the mapping for old saves.
- **`check_follower_integrity` alive check** — `getattr(entity, 'alive', True)` always
  returned True since Entity uses `is_alive()` method, not an `alive` attribute.  Fixed to
  call `entity.is_alive()`.
- **Biome shift thresholds** — PLAINS threshold tightened to `tree_pct < 0.05` (was
  `< 0.1`); FOREST threshold lowered to `tree_pct > 0.1` (was `> 0.15`) to prevent
  forest-to-plains drift under the new crowding rules.
- **Sand reclamation threshold** — sand-adjacent-to-water threshold lowered from 2+ water
  neighbors to 1+ so desert borders recover from minor flooding without full water
  saturation.

---

## 2026-03-04 — Combat Quality, Keeper Polish, Time Pass, Overcrowding

### Features
- **NPC starting inventory** — all humanoid NPCs (FARMER, GUARD, WARRIOR, COMMANDER,
  KING, TRADER, BLACKSMITH, WIZARD, LUMBERJACK, MINER, BANDIT) spawn with 0–30
  wood, stone, and meat plus 0–2 random items from the full item/cell pickup pool.
- **Time pass overhaul** — death screen and new-game time skip now run the full
  probabilistic zone simulation (real update priority queue, all automata, grows_to,
  entity aging, entity AI) at 20× speed via `time_pass_active` / `time_pass_speed`
  flags.  NPC XP gain, damage, and action success rates scale by `time_pass_speed`
  during the simulation.  Year counter advances 20× faster to match.  15 update
  cycles per rendered frame keeps the death screen responsive.
- **Structure overcrowding mechanic** — when a structure's local population exceeds 3,
  each entity beyond that has a 10% chance per extra entity per AI update to seek the
  zone exit.  Keepers are always exempt.
- **WELL as solid collision cell** — Water Well is now impassable (`solid: True`)
  in both `constants.py` and `data/cells.py`.
- **Keeper system polish** — TRADER is now eligible as a zone Keeper; Shift+inspect
  on a Keeper shows keeper status; Keepers are excluded from the overcrowding eviction
  mechanic.  Fixes: AttributeError on `entity.keeper` resolved via `getattr`; subscreen
  context check (`_same_context_as_player`) corrected for Keeper NPCs inside structures;
  ghost `subscreen_entities` registrations cleared; stale `in_combat` flags reset on
  Keeper exit.

### Fixes
- **NPC player-combat animation and damage** — the state machine inline player-attack
  path was missing `show_attack_animation`, making hits visually invisible.  Formula
  changed from base-strength + level to `entity.strength // 5` (level-scaled) plus
  weapon bonus, magic bonus, and 1.2× hostile multiplier — matching `find_and_attack_enemy`
  quality.  `entity.in_combat` now set before the cooldown check so the combat stance
  is shown while waiting between hits.
- **Follower guard in state machine proximity check** — hostile followers (e.g. GOBLIN)
  could still have `current_target = 'player'` set by `update_entity_ai_state`'s
  proximity check even after the `find_and_attack_enemy` guard was added.  Both paths
  now block followers from targeting the player.
- **Goblin follower friendly-fire** — `find_and_attack_enemy` follower FF guard added
  in a prior session; state machine guard added this session for complete coverage.

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
