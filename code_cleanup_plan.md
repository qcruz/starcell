# StarCell — Code Cleanup Plan

## Summary

Full read-only review of all major source files. The codebase is in active development with a clear extraction-in-progress pattern: legacy monoliths (`game_core.py`, `npc_ai.py`, top-level `entity.py`) are being decomposed into modular mixins (`engine/`, `ai/`, `systems/`, `world/`, `ui/`, `lore/`). This creates several categories of cleanup work. The most urgent issues are a live SCREEN_HEIGHT divergence between the two constant sources (off by 20px), dead NPC behavior methods in `npc_ai.py` that have been silently replaced without removal, and ~60 debug `print()` statements scattered outside the sanctioned debug files.

The dual-import pattern (both `constants.py` and `data/` must stay in sync) is the largest ongoing maintenance burden. The CA rate divergence between the two settings files means world/cells.py and world/zones.py run on constants.py values while data/settings.py values are effectively dead.

---

## 1. Dead Code

### Functions defined but never called

**`npc_ai.py` — four full NPC behavior methods, replaced by `execute_entity_behavior` dispatch:**
- `farmer_behavior(self, entity)` — line 2810 (~55 lines). Never called. Dispatch at line 2434 routes to `ai/actions.py` primitives instead.
- `lumberjack_behavior(self, entity)` — line 2866 (~105 lines). Never called.
- `guard_behavior(self, entity)` — line 2972 (~85 lines). Never called.
- `trader_behavior(self, entity)` — line 3058 (~60 lines). Never called.

These four methods total ~300 lines of dead AI logic. Safe to delete; `execute_entity_behavior` fully replaces them.

**`game_core.py` — three cell/entity update methods, replaced by `probabilistic_zone_updates()`:**
- `update_cells(self)` — line 532. Never called from the run loop. The run loop calls `self.probabilistic_zone_updates()` in `world/zones.py`.
- `update_screen_cells(self)` — line 931. Never called.
- `update_entities(self)` — line 587. Appears never called from the active run loop path.

These are the legacy equivalents of the CA system now in `world/zones.py`. Removal requires verifying no external caller (e.g., autopilot.py) invokes them.

**`world/zones.py`:**
- `update_single_cell(self, x, y, cell_type)` — line 1495. No callers found in any tracked file. The bulk CA path uses `probabilistic_zone_updates()` and `catch_up_zone()`.

**`ai/actions.py`:**
- `execute_npc_behavior(self, entity)` — line 275. Mentioned in a comment at `npc_ai.py:2400` but never actually called. The active dispatch is `execute_entity_behavior` in `npc_ai.py`. This is a ~30-line method plus the NPC_BEHAVIORS data table it reads; if it is truly never invoked, it and the table read are dead.

### Dead constants

**`data/settings.py` — CA rate constants effectively unused by active modules:**
- `world/cells.py` and `world/zones.py` import from `constants`, not from `data/settings.py`. This means the following `data/settings.py` values are never read at runtime:
  - `BASE_DECAY_RATE`, `TREE_GROWTH_RATE`, `TREE_DROUGHT_RATE`, `GRASS_GROWTH_RATE`, `CACTUS_DROUGHT_RATE`, `WATER_SPREAD_RATE`, `LAVA_SPREAD_RATE` and ~15 other CA rates.
- These constants exist in both files with different values; the `data/settings.py` versions are the dead ones.

**`constants.py` — wizard spells and faction constants never imported by modular code:**
- `WIZARD_SPELLS` — only in `constants.py`; `data/spells.py` is nearly empty (10 lines). Spells logic runs from `constants.py` path only.
- `HOSTILE_FACTION_COLORS`, `HOSTILE_FACTION_SYMBOLS` — only in `constants.py`; `data/factions.py` is 7 lines with different content. The active faction render path uses `constants.py`.

### Debug prints outside sanctioned files

Grep found approximately 60 `print()` calls across non-debug files. File-by-file count (approximate):
- `game_core.py`: ~20 prints (includes a `FREEZE-DETECT` print at line 2754)
- `npc_ai.py`: ~12 prints
- `ai/actions.py`: ~15 prints
- `systems/combat.py`: ~10 prints (level-up, death, respawn messages)
- `systems/enchantment.py`: ~15 prints
- `systems/save_load.py`: 4 prints
- `lore/engine.py`: ~6 prints
- `ui/` files: scattered

Per CLAUDE.md rule: "Remove dead debug prints outside `autopilot.py` and `debug/`." All of the above qualify.

---

## 2. Duplicates

### Dual-import data duplicates (constants.py ↔ data/)

Every data table in `data/` is a copy of a corresponding block in `constants.py`. The following pairs are structurally identical or nearly identical:

| constants.py block | data/ mirror | Known divergence |
|---|---|---|
| `CELL_TYPES` | `data/cells.py` CELL_TYPES | SAND missing `grows_to: CACTUS` in data version; IRON_ORE uses hardcoded color in data version |
| `CELL_PICKUP` | `data/cells.py` CELL_PICKUP | Verify identical |
| `ITEM_TO_CELL` | `data/cells.py` ITEM_TO_CELL | Verify identical |
| `ITEMS` + `ITEMS.update(...)` | `data/items.py` ITEMS | The `update()` block in data/items.py appears to be a verbatim copy |
| `RECIPES` | `data/items.py` RECIPES | Verify identical |
| `LOOT_TABLES` | `data/items.py` LOOT_TABLES | Verify identical |
| `ENTITY_TYPES` | `data/entities.py` ENTITY_TYPES | `water_sources` divergence: data has WELL, constants does not |
| `NPC_BEHAVIORS` | `data/entities.py` NPC_BEHAVIORS | Appears identical |
| `NPC_QUEST_FOCUS_DEFAULT` | `data/entities.py` NPC_QUEST_FOCUS_DEFAULT | Verify identical |
| `NPC_TRANSFORMATION_CONFIG` | `data/entities.py` NPC_TRANSFORMATION_CONFIG | Verify identical |
| `BIOMES` | `data/biomes.py` BIOMES | Verify identical |

These are unavoidable under the dual-import pattern described in CLAUDE.md, but every divergence is a latent bug. The WELL/water_sources divergence is a confirmed active bug: `npc_ai.py` (which reads from `constants.py`) will not route humanoid NPCs to wells, while `ai/actions.py` (which reads from `data/entities.py`) will.

### Duplicate method definitions between legacy and modular files

The extraction process leaves legacy methods in place even after equivalents exist in mixins. No full cross-check was done (would require exhaustive grep), but the following are known duplicate zones to audit:

- `game_core.py` item decay methods vs `systems/crafting.py` item decay methods — `update_cells()` in game_core.py calls crafting decay; crafting.py has the canonical versions.
- `game_core.py` respawn / new_game logic vs anything in `systems/` — check for overlap.
- `npc_ai.py` combat methods vs `systems/combat.py` — combat.py is the extraction target; verify no duplicate resolution paths.

### CA rules duplicated between `world/zones.py` and `world/cells.py`

`world/zones.py:catch_up_zone()` contains inline CA spread rules (grass growth, tree spread, water spread, etc.) that duplicate the rules already canonically implemented in `world/cells.py:apply_cellular_automata()`. These should share one implementation. The catch-up path should call `apply_cellular_automata` rather than re-implement spread logic.

### `ITEMS.update({...})` pattern

Both `constants.py` and `data/items.py` use `ITEMS.update({...})` to append additional items after the initial dict definition. This split-definition pattern makes it easy for the two files to drift. The update block in `data/items.py` appears verbatim-identical to the one in `constants.py` — pure duplication.

---

## 3. Over-Specific Code / Generalization Opportunities

### Two Entity classes with different field names

`entity.py` (top-level legacy, 1210 lines) uses `in_structure` / `structure_key` naming.
`engine/entity.py` (modular, 623 lines) uses `in_subscreen` / `subscreen_key` naming.

Both are in active use simultaneously. `ai/movement.py` line 1423 does a local import of the legacy entity: `from entity import Entity as _Entity` inside a method body, to resolve a mixin conflict. `debug/fixes.py` references both naming conventions. This is a latent bug source: any code that checks `entity.in_structure` will silently fail on entities created from `engine/entity.py` and vice versa.

The over-specific issue: both classes represent the same concept (entity inside a sub-area) with different field names. A cleanup pass should pick one convention (`in_subscreen`/`subscreen_key`) and migrate all callsites.

### NPC behavior dispatch: two parallel systems

`execute_entity_behavior` (npc_ai.py line 2434) dispatches based on `entity.behavior_config` dict — the active system.
`execute_npc_behavior` (ai/actions.py line 275) dispatches based on `NPC_BEHAVIORS` data table — apparently never called.

These serve the same purpose. The intent was likely that `execute_npc_behavior` would replace `execute_entity_behavior` as part of the extraction, but it was never wired up. Either wire it or remove it.

### SCREEN_HEIGHT divergence — active bug

`constants.py`: `SCREEN_HEIGHT = GRID_HEIGHT * CELL_SIZE + 80`
`data/settings.py`: `SCREEN_HEIGHT = GRID_HEIGHT * CELL_SIZE + 60`

The 80 vs 60 difference is a 20-pixel discrepancy in the rendered window height. Since `game_core.py` and `npc_ai.py` import from `constants.py`, the active window uses +80. The HUD was likely designed for +60 (the modular value). This may cause a 20px dead zone or clipping at the bottom of the HUD. One value needs to be chosen and propagated to both files.

### Keeper constants only in `constants.py`

`KEEPER_RANGE`, `KEEPER_*` constants are imported explicitly by `world/zones.py` from `constants`. They do not exist in `data/settings.py`. This means any module using `from data import *` cannot access keeper behavior configuration. If keeper behavior is ever extracted to a mixin, these constants must be added to `data/settings.py`.

### SoundManager `play_sfx_spatial` — planned but not implemented

Per MEMORY.md, spatial NPC audio was designed with a full spec but not yet written. The planned method `SoundManager.play_sfx_spatial(key, dist, max_dist=8)` is the entry point. The design doc in MEMORY.md is authoritative. When implementing, avoid per-call volume calculations that bypass the master sfx_volume setting — use `sfx_volume * max(0, 1 - dist/max_dist)`.

---

## 4. Data Derivation Opportunities

### `ITEM_TO_CELL` can be derived from `CELL_TYPES`

`ITEM_TO_CELL` maps item names to the cell type they place when used (e.g., `'seed' → 'CARROT'`). This mapping is redundant with `CELL_TYPES[type]['drops']` going the other direction. Either derive `ITEM_TO_CELL` at startup from CELL_TYPES, or verify there is a reason for explicit duplication (e.g., one-to-many mappings that can't be reversed cleanly). Exists in both `constants.py` and `data/cells.py`.

### `CELL_PICKUP` can be derived from `CELL_TYPES`

`CELL_PICKUP` is a set of cell type strings that the player can pick up. These are cells with a `drops` key in CELL_TYPES. The set could be derived at module load time with a set comprehension over CELL_TYPES rather than maintained as a parallel list. This would eliminate the risk of adding a new droppable cell to CELL_TYPES but forgetting to add it to CELL_PICKUP.

### Loot tables could reference item categories

Several `LOOT_TABLES` entries repeat the same sets of common items (wood, stone, iron_ore) as base drops across multiple entity types. A `base_loot` constant referenced by the tables would reduce repetition and make balancing easier.

### `NPC_QUEST_FOCUS_DEFAULT` can be derived

`NPC_QUEST_FOCUS_DEFAULT` maps NPC types to their preferred quest categories. This is currently a flat dict in both `constants.py` and `data/entities.py`. It could be derived from the `quest_focus` field already present in some `ENTITY_TYPES` entries, eliminating one more parallel structure.

---

## 5. File Organization

### `entity.py` (top-level) should be retired

The top-level `entity.py` is 1210 lines and contains four classes: `SpriteManager`, `Entity`, `Inventory`, `Quest`, `NpcQuestSlot`. The modular equivalents exist:
- `engine/entity.py` — modular Entity (623 lines)
- `engine/sprite_manager.py` — modular SpriteManager (266 lines)
- `Inventory`, `Quest`, `NpcQuestSlot` have no modular counterparts yet

The retire path: port `Inventory`, `Quest`, `NpcQuestSlot` to `engine/` (or a new `engine/inventory.py`), then migrate all callers from `from entity import *` to `from engine import *`. This is a large refactor blocked by the naming convention divergence (see Section 3).

**Current import graph for entity.py:**
- `game_core.py`: `from entity import *`
- `npc_ai.py`: inherits via `from constants import *` which does `from entity import *`
- `autopilot.py`: `from entity import *`
- `systems/combat.py`: explicit import
- `systems/save_load.py`: explicit import
- `world/zones.py`: explicit import
- `systems/spawning.py`: explicit import

### `engine/` lacks `__init__.py`

The `engine/` directory has no `__init__.py`. It works as a namespace package under Python 3, but this is implicit. Adding `engine/__init__.py` that re-exports `Entity`, `SpriteManager`, etc. would make the import contract explicit and match the pattern used by `data/__init__.py`.

### `data/spells.py` and `data/factions.py` are stubs

`data/spells.py` is 10 lines with a comment placeholder; the actual `WIZARD_SPELLS` dict lives only in `constants.py`. `data/factions.py` is 7 lines, minimal. These files exist as placeholders but contain no real content. Either populate them (mirror from constants.py) or document their stub status clearly.

### `ai/` directory imports `engine/entity.py` but moves entities created by `entity.py`

`ai/actions.py` and `ai/movement.py` import `from engine import *` (getting the modular Entity). But the entities they actually operate on at runtime are instances of the legacy `entity.py` Entity class (because `game_core.py` and `npc_ai.py` create entities via the legacy path). This means `ai/` code is type-checked against the modular Entity but operating on legacy Entity instances — any attribute unique to one but not the other will fail silently.

### `lore/engine.py` should probably be `lore/lore_engine.py`

The file name `engine.py` inside `lore/` shadows the `engine/` package name and creates ambiguity in greps and mental models. Rename to `lore_engine.py` or `events.py`.

---

## 6. Git History Patterns

From `git log --stat` on the last 40 commits:

**Highest churn files (most commits touching them):**
1. `world/zones.py` — touched in nearly every recent commit. Contains the probabilistic CA system, NPC chest logic, and structure placement — all actively evolving. This is the current hotspot.
2. `npc_ai.py` — frequent edits for NPC behavior changes. The dead behavior methods (Section 1) likely survived because this file is large enough that the dead code isn't noticed.
3. `constants.py` — modified whenever new items, entities, or cells are added (dual-import maintenance).
4. `data/entities.py` — co-modified with constants.py for dual-import sync, but shows lag (WELL/water_sources divergence was not synced back to constants.py).

**Stable files (rarely touched recently):**
- `engine/sprite_manager.py` — last significant change was IRON_ORE/WELL/sword sprite additions.
- `systems/save_load.py` — stable; 4 print statements but otherwise low risk.
- `world/generation.py` — stable; only touched when new cell types need generation rules.
- `debug/watchdog.py`, `debug/fixes.py` — low churn; used as read-only infrastructure mostly.

**Pattern: constants.py and data/entities.py drift after every entity change.** The WELL/water_sources case shows that when npc_ai.py behavior is added, the constants.py update often happens, but the data/entities.py mirror is not always synced. A commit message discipline of "update both constants.py AND data/" would help, or a startup assertion that compares key tables.

**Pattern: world/zones.py catches all NPC economic behavior.** Chest thresholds, NPC inventory dumps, structure density — all landed in zones.py in recent commits. This file is growing into a second monolith. The NPC economic behavior (chest interaction, inventory management) belongs in `ai/actions.py` long-term.

---

## 7. Planned Feature Adaptation

### Actions inventory tab (next_up.md Tier 1, item 1)

The actions tab will need a new tab key in `ui/inventory.py`. The existing tab switching mechanism (R key cycles tabs) should accommodate a new `'actions'` tab with minimal changes — look at `ui/inventory.py`'s tab list definition. Actions items should be a new item category in `data/items.py` (and `constants.py`) with `droppable: False` flag. The `ITEMS` dict already has item-level flags for some properties; `droppable` needs to be added or repurposed.

Note: actions/spells not dropped on death requires a filter in the death handler in `game_core.py`. Currently the death handler iterates all inventory items and drops them. Add a check for `ITEMS[item_name].get('droppable', True)` before dropping.

### Favor system (next_up.md Tier 1)

NPC favor will be a per-entity field (`entity.favor = 0` default). This field should be added to both `entity.py` (legacy) and `engine/entity.py` (modular) to avoid the naming-convention divergence problem. The `ENTITY_TYPES` entries for hostile NPCs default to -50; this could be set in `__init__` based on the entity's `behavior` classification, or as a field in ENTITY_TYPES itself.

Faction standing display requires reading `entity.favor` in `ui/hud.py`'s inspect panel. The existing inspect code is in `hud.py`; add a line after the existing NPC stat display.

### Double entities / split behavior (next_up.md Tier 1)

The "doubles should process same as singles" item references skeleton doubles taking sun damage. Sun damage for SKELETON is currently keyed on `entity.type == 'SKELETON'`. Extend the check to `entity.type in ('SKELETON', 'SKELETON_DOUBLE')` — or better, add a `'takes_sun_damage': True` flag to ENTITY_TYPES entries so the check is data-driven rather than type-name-specific.

The "split back to singles" behavior needs `entity.type` → `(single_type, single_type)` mapping. This could be a `split_into` field in ENTITY_TYPES for double entity entries.

The "hard cap 15 of same type → absorb into double" logic belongs in `world/zones.py` or `ai/actions.py` as a zone-level check, not per-entity per-tick.

### Chest interaction (next_up.md Tier 1: player drops items on chest cell)

`world/zones.py` currently handles chest fill from NPC side. Player-drop-to-chest needs a handler in the player input section of `game_core.py`: when an item is dropped (current drop key) and the player's current cell or adjacent cell is `'CHEST'`, redirect the item to the chest's inventory rather than the floor. The chest inventory is stored on the entity at that cell (look up entity at `(player.x, player.y)` with type `'CHEST'`).

### Village / dungeon biomes (next_up.md Tier 1)

These are Tier 2 items per CLAUDE.md criteria (new zone/structure types). They appear in the Tier 1 list — flag this to @qcruz before starting. The fence and stairs sprites referenced as "required" will need entries in both `constants.py` CELL_TYPES and `data/cells.py` (dual-import), plus PNG files in `sprites/` registered in `engine/sprite_manager.py:create_structure_sprites()`.

### Wolf/goblin ambient sounds (next_up.md Tier 1)

Spatial audio infrastructure (`play_sfx_spatial`) needs to exist before wiring NPC ambient sounds. Per MEMORY.md design: WOLF every ~300 ticks within 6 cells, GOBLIN every ~200 ticks. The tick counter to throttle per-NPC ambient sounds could be a simple `entity.last_ambient_sound_tick` field checked in `npc_ai.py`'s entity update loop. Do not add per-entity fields without adding them to both Entity classes (see naming divergence issue).

### Spell energy cost (next_up.md Tier 1)

Spells are cast via `game_core.py` input handling. The energy drain should check `player.energy >= spell_cost` before casting, deduct from energy, and if energy < spell_cost, drain from HP instead. `WIZARD_SPELLS` in `constants.py` would need a `'cost'` field per spell. Since `data/spells.py` is a stub, this should go into `constants.py` only until `data/spells.py` is populated.

---

## Priority Order

Ordered by impact-to-effort ratio and risk of leaving unresolved:

1. **Fix SCREEN_HEIGHT divergence** (`constants.py` vs `data/settings.py`): +80 vs +60. One-line fix but active display bug. Pick one value, update both files. **Effort: 5 min. Risk if ignored: HUD clipping.**

2. **Sync WELL/water_sources to `constants.py` ENTITY_TYPES**: humanoid NPCs in `npc_ai.py` path don't route to wells. Add `'WELL'` to `water_sources` in all humanoid entries in `constants.py`. **Effort: 10 min. Risk if ignored: wells are non-functional for npc_ai.py-driven NPCs.**

3. **Remove dead NPC behavior methods** (`npc_ai.py:farmer_behavior`, `lumberjack_behavior`, `guard_behavior`, `trader_behavior`): ~300 lines. Verify no caller, then delete. **Effort: 30 min. Impact: significant file size reduction on a frequently-edited file.**

4. **Remove `~60 debug print() statements`** outside `autopilot.py` and `debug/`: per CLAUDE.md rule. Sweep all non-debug files. **Effort: 1–2 hours. Impact: cleaner output, satisfies CLAUDE.md constraint.**

5. **Remove dead game_core.py methods** (`update_cells`, `update_screen_cells`, `update_entities`): verify no callers, then delete. ~200 lines removed from the largest file. **Effort: 30 min with grep verification.**

6. **Remove `execute_npc_behavior` from `ai/actions.py`** (or wire it): determine intent, then either wire it as the dispatch target or delete it. **Effort: 30 min to decide + implement.**

7. **Remove `world/zones.py:update_single_cell`**: no callers found. **Effort: 5 min.**

8. **Consolidate CA rules**: `world/zones.py:catch_up_zone()` duplicates rules from `world/cells.py:apply_cellular_automata()`. Route catch_up through apply_cellular_automata. **Effort: 2–3 hours. Impact: single source of truth for CA rules.**

9. **Add `engine/__init__.py`**: make engine package explicit; mirrors `data/__init__.py` pattern. **Effort: 15 min.**

10. **Populate `data/spells.py` and `data/factions.py`** from `constants.py`: mirror the WIZARD_SPELLS and faction constants so modular code can access them. **Effort: 30 min.**

11. **Standardize `in_structure`/`in_subscreen` naming**: pick one convention, audit all callsites, migrate. Prerequisite for retiring legacy `entity.py`. **Effort: 3–4 hours. Risk if ignored: latent attribute misses across all entity checks.**

12. **Port `Inventory`, `Quest`, `NpcQuestSlot` to `engine/`** and retire top-level `entity.py`: large refactor, prerequisite for full modular migration. Do after naming convention is unified. **Effort: full session.**
