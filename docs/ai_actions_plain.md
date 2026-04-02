# ai/actions.py — Plain Language Guide

**What this file is:**
The physical actions NPCs and the player perform on the world. Where `npc_ai.py` decides *what* to do and `ai/movement.py` handles *how to get there*, this file handles *what happens when you arrive*: chopping trees, mining rocks, harvesting crops, planting seeds, building structures, picking up items, dying and dropping loot, and trading. It is a mixin (`NpcAiActionsMixin`) mixed into the `Game` class.

**Why it's separate:**
The action primitives here (`action_harvest_cell`, `action_transform_cell`, `action_place_cell`) are shared by both NPCs and the player. Keeping them in one place means a single function handles the animation, sound, XP, drop, and cell-transform logic regardless of who is doing the harvesting — the caller just passes `actor='player'` or `actor=entity`.

---

## Section 1 — Sound Helpers (line 17)

### `_CELL_SOUND` / `_ENTITY_SOUND`
Two class-level lookup tables mapping cell types and entity types to sound key strings. These are kept at the class level (not inside functions) so they're defined once and reused for every call, avoiding repeated dict construction.

### `_npc_action_sound`
Plays a spatially attenuated sound for an NPC action. Only plays if the NPC is on the same screen as the player and within 4 cells — beyond that, the sound would be inaudible. Volume is halved per cell of distance. This is separate from the footstep sound system because action sounds (chopping, mining) have a different max range and volume curve than movement sounds.

---

## Section 2 — Universal Action Primitives (line 50)

These three functions are the core of the file. They handle the entire lifecycle of any world-modifying action: checking adjacency, facing the target, playing animations and sounds, awarding XP, rolling for success, applying drops, and transforming the cell.

### `action_harvest_cell`
The single function for all destructive cell interactions: chopping trees, mining rocks, harvesting crops. It scans the four cardinal neighbors of the actor for any cell matching the provided `cell_types` list. On success, it applies drops from `CELL_TYPES[cell]['drops']`, transforms the cell (to `result_cell` if specified, otherwise the drop table's cell result, otherwise GRASS), and awards XP.

Several special cases are folded in:
- **Farmer buried items**: Before scanning for trees, farmers collect any buried items at adjacent cells (items buried by the world or other events).
- **House collapse**: If a HOUSE or STONE_HOUSE cell is destroyed, `on_house_collapsed` is called to eject occupants and drop chest contents.
- **Autopilot proxy sound**: The autopilot proxy plays a full-volume pickup sound on harvest rather than a spatial one, because it *is* the player.

This function accepts `actor='player'` or any entity object. The `is_player` flag controls whether items go to `self.inventory` or `entity.inventory`.

**Why one function for everything:** A tree chop, a rock mine, and a carrot harvest are structurally identical operations — check adjacency, roll success, apply drops, transform cell. Using a single function with a `cell_types` parameter avoids three parallel copies of the same loop.

### `action_transform_cell`
Changes an adjacent cell type without producing any drops. Used for tillage (GRASS → SOIL), paving (DIRT → COBBLESTONE), and similar non-harvesting world edits. Same adjacency loop and success roll as `action_harvest_cell`, but simpler: no drops, just overwrite the cell with `result_cell`.

### `action_place_cell`
Places something on an adjacent cell, optionally consuming an item from inventory. Used for planting (SOIL → CARROT1) and similar construction actions. Includes a 20% fallback for NPCs who have no inventory items — this represents "stored seeds not tracked in the inventory dict" rather than building a full inventory-management pipeline for farmers.

### `action_damage` / `action_heal`
Minimal universal wrappers. `action_damage` routes to `player_take_damage` when the target is the player and directly subtracts health for entity targets. `action_heal` clamps health at max. These exist to give callers a single function regardless of whether the target is the player or an NPC.

---

## Section 3 — Data-Driven Behavior Dispatch (line 287)

### `execute_npc_behavior`
Reads the `NPC_BEHAVIORS` dict from `data/entities.py` for the entity's type and runs each behavior in order. Each entry has an `action` string (`'harvest_cell'`, `'transform_cell'`, `'place_cell'`, `'build'`), a `rate` (probability per call), and parameters for the action. The first behavior that fires and succeeds stops the loop.

This is the config-dispatch pattern: adding a new behavior to a FARMER or MINER only requires editing their entry in `NPC_BEHAVIORS`, not this function. The trade-off is that the behavior table is opaque — you have to read `data/entities.py` to see what a FARMER actually does.

### `_try_build_structure`
Called by `execute_npc_behavior` when a behavior entry has `action='build'`. Checks that the entity has the required item costs, that the zone doesn't already have the maximum number of this structure, then places the structure on a valid nearby cell. If the structure is a HOUSE or STONE_HOUSE, it also generates a full interior zone via `generate_structure_zone`.

The placement scans for cells near any `prefer_near` cell type (e.g., builders prefer to place houses near paths), falling back to random spots if no preferred location is found. Up to 10 candidates are collected; one is chosen at random to prevent all builders placing structures in the same spot.

---

## Section 4 — Role-Specific Action Methods (line 397)

These are higher-level wrappers for specific NPC types. They pre-process inputs (compute density bonuses, check quest nav targets, enforce caps) before delegating to the primitives above or to direct grid edits.

### `try_chop_tree`
Lumberjack-specific tree chopping. Before checking adjacency, it counts trees within a 5×5 radius and applies a density bonus to the chop rate — denser forests are faster to chop. Level also scales the rate (10% per level). If the entity has a `quest_nav_target` pointing at an adjacent tree, that direction is checked first.

The tool gate here is an autopilot concession: the proxy character only actually collects wood if the player has an axe equipped. The cell still transforms regardless, so the lumberjack always clears the tree even if the proxy can't collect.

### `on_house_collapsed`
Called when a HOUSE or STONE_HOUSE cell is destroyed by any harvesting action. Finds the interior structure linked to that cell, ejects all entities inside (placing them at the nearest walkable cell adjacent to the door), applies 35–50% health damage to each (collapse injury), and drops 70% of any chest contents at the ejection point (30% are destroyed). This is a consequence system — destroying a building has cascading effects on everything inside.

### `try_mine_rock`
Miner-specific rock mining. Similar density-bonus structure to `try_chop_tree`. Has additional logic for three rock types:
- **IRON_ORE** → drops iron_ore item, replaces with the biome's base cell
- **CAVE entrance** → converts to MINESHAFT (if under the per-zone cap)
- **STONE** → drops stone, has a small chance to create a MINESHAFT or dig deeper (generate a new cave level below, limited to depth 3)

After a successful mine, `entity.current_target = None` is set so the state machine immediately seeks the next rock rather than waiting for the targeting timer.

### `try_build_well`
Miner builds a WELL if the zone has 2+ houses and no existing well. Placed near the zone center. This is the only world-generation action that has a settlement-density prerequisite: wells only appear in zones that have become towns.

### `try_plant_seed`
Farmer places CARROT1 on an adjacent SOIL cell. Consumes one carrot or seeds from inventory; falls back to a 20% chance without items (representing seed supply not tracked in the dict). The 20% fallback prevents farmers from being paralyzed when their inventory is empty — they keep working, just less reliably.

### `try_harvest_crop`
Farmer harvests CARROT3 (the mature stage) from an adjacent cell. Produces 2 carrots and decays the cell back to CARROT1 (not SOIL — the farm plot persists). If the entity has a `quest_nav_target` pointing at adjacent CARROT3, that direction is prioritized.

### `try_till_soil`
Farmer tills GRASS, DIRT, or SAND → SOIL. Sand is significantly harder (15% of the normal success rate) to reflect the difficulty of farming in desert biomes. Quest nav target priority applies here too.

### `try_clear_tree`
Non-lumberjack NPCs (warriors, traders) clearing trees they encounter. No wood is collected — only the cell-transform from the drop table is applied. This is the "incidental" clearing that humanoid NPCs do while patrolling; the trees become grass without producing any inventory items.

### `try_build_house` / `try_build_forge`
Lumberjack builds a house when it has 10+ wood; blacksmith builds a forge when it has 15+ stone. Both have per-zone caps (houses reduce chance as count increases; forge is strictly max 1). Both scan within a small radius of the entity for an open spot. These are the manual equivalents of `_try_build_structure` for specific building types — they predate the data-driven system and do similar things with slightly different spot-selection logic.

### `try_build_path`
Traders and guards passively pave cells they walk on. GRASS → DIRT at low probability; DIRT → COBBLESTONE only in the center lanes of the zone (within 1 cell of the vertical or horizontal center line). This creates the emergent road effect where heavily-traveled routes gradually become cobblestone paths without any explicit road-building intent.

---

## Section 5 — Item Management (line 921)

### `pickup_dropped_items`
Called every tick for entities standing on a cell with dropped items. All items at the position are added to the entity's inventory. Runestones are a special case: they deal damage equal to their count when picked up, and 50% are destroyed in the process. This makes runestone traps functional — hostile entities walking over them take damage.

### `_is_unique_item` / `process_entity_drop`
When an entity dies, its loot is generated from two sources: the props `drops` table (fixed loot table with chance rolls), and the entity's actual inventory. Inventory items are split into unique (tools, spells, magic gear — always drop intact) and common (resources — 40% destruction chance per item). The destruction chance is per-item, not per-stack: an entity with 10 wood will drop roughly 6 of them on average. A 10% chance also spawns runestones at the death location.

### `npc_place_camp`
Called periodically for entities with `can_place_camp` in their behavior config. Places a CAMP cell near the entity if none exists in the zone. If a CAMP already exists, there's a 2% chance it upgrades to HOUSE, and if the zone already has 5+ houses, there's a 5% chance the camp decays to DIRT (the settlement is established and the camp is no longer needed). This gives zones a natural progression from camp → house over time.

### `miner_mine_cave` / `miner_place_mineshaft`
Two miner-specific exploration behaviors. `miner_mine_cave` finds the nearest CAVE entrance cell in the zone and converts it to MINESHAFT when adjacent. `miner_place_mineshaft` excavates a brand-new MINESHAFT at a zone corner when no existing options are found. Both respect a per-zone cap of 2 mineshafts.

---

## Section 6 — Trade System (line 1171)

### `try_npc_trade`
Passive NPC-to-NPC barter. Peaceful NPCs within 3 cells of each other have a 2% chance per tick to swap one random non-spell item. The exchange is symmetric (each gives one, each receives one). This is a background economy simulation — it redistributes resources between zones over time as traders travel.

### `process_npc_trade`
Player-triggered trade. Fires when an NPC picks up gold that the player dropped nearby. Each NPC type has a fixed exchange rate: farmers trade carrots 2-per-gold, lumberjacks trade wood 3-per-gold, miners trade stone 3-per-gold. Guards and goblins accumulate gold until they reach their threshold and then become followers. Traders open a UI panel with fixed recipes.

### `npc_trade_interaction`
Called when the player presses N near a trader NPC. Opens the trader recipe UI if adjacent to a TRADER entity, or executes the first available recipe if a UI is already open. Recipe ingredients are checked against the trader's inventory, not the player's — the player pays with gold (via proximity-drop) and the trader dispenses the goods.

---

## Section 7 — Chest Placement (line 1353)

### `try_place_npc_chest`
When an NPC's inventory exceeds its threshold (checked by the caller), this places a CHEST cell adjacent to the entity and transfers up to 5 items into it. A hard guard prevents placement if any chest already exists within 8 cells — this stops NPCs from carpeting zones with chests. The chest background cell (the cell that was there before) is stored in `chest_backgrounds` so the cell can be correctly restored if the chest is removed.

---

## Notes for Contributors

**actor='player' pattern:** All three primitive functions (`action_harvest_cell`, `action_transform_cell`, `action_place_cell`) support `actor='player'`. When called this way, they use `self.player['x'/'y']` for position and `self.inventory` for items. This means player and NPC harvesting go through the exact same drop/XP logic.

**`time_pass_speed` scaling:** All success rates are multiplied by `getattr(self, 'time_pass_speed', 1.0)`. When the game fast-forwards (time-pass simulation), actions become more likely to succeed so the world evolves visibly during the simulation.

**Quest nav target priority:** `try_chop_tree`, `try_mine_rock`, `try_harvest_crop`, and `try_till_soil` all check `entity.quest_nav_target` before scanning other directions. This is how quest-driven NPCs prioritize the specific cell they've been directed to over the first adjacent match.

**Two build systems:** `execute_npc_behavior` + `_try_build_structure` is the data-driven path (reads from `NPC_BEHAVIORS`). `try_build_house`, `try_build_forge` are older hardcoded methods. They coexist; the data-driven path is preferred for new entity types.
