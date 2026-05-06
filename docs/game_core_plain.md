# game_core.py — Plain Language Guide

**What this file is:**
The foundational mixin (`GameCoreMixin`) that owns game state initialization, the main loop, player movement, input handling, cell/entity update scheduling, and structural navigation (entering/exiting caves and houses). Everything else in the codebase is a mixin stacked on top of this one. It has no AI logic — that lives in `npc_ai.py` and `ai/` — but it owns the tick counter, the event loop, autosave, and all direct player interactions.

**Why it's a mixin and not a standalone class:**
`GameCoreMixin` is mixed into `Game` alongside `NpcAiMixin`, `NpcAiActionsMixin`, `NpcAiMovementMixin`, and the world/systems mixins. Python's MRO resolves method lookup across all of them so every mixin sees `self.entities`, `self.screens`, `self.player`, etc. without passing arguments. The alternative — a single 10,000-line class — was the original design; the mixin extraction is ongoing refactoring.

---

## Section 1 — `__init__` and State Initialization (line 22)

### `__init__`
Sets up the entire game state from scratch. Every dict, list, flag, and timer used anywhere in the game is initialized here to a known value. There is no lazy initialization — all state exists from the moment the constructor runs, even if some of it is overwritten by `new_game()` or `load_game()` moments later.

Key structures initialized:
- **`self.player`**: a plain dict (not an object) holding position, stats, inventory, and flags. Uses a dict rather than a class so it serializes cleanly to JSON without a custom encoder.
- **`self.entities`**: `{entity_id: Entity}` — the global entity registry. Every entity that exists anywhere in the world is in here.
- **`self.screens`**: `{zone_key: grid}` — stores the 2D cell grid for every generated zone. Zones not yet visited are absent; they're generated on first access.
- **`self.screen_entities`**: `{zone_key: [entity_id, ...]}` — buckets entities by which zone they're in. The source of truth for rendering and per-zone AI updates.
- **`self.structures`**: `{structure_key: struct_dict}` — virtual zone metadata for caves, houses, and mineshafts. Keyed by negative-x zone strings (e.g. `"-1000,5"`).
- **`self.followers`**: list of entity IDs currently following the player.
- **`self.follower_items`**: `{entity_id: item_name}` — maps each follower to the item name that "produced" it, used to clean up inventory when a follower dies.

Sound, font, and UI managers are also created here. The tick counter starts at 0.

### `load_sprites`
Loads all visual assets from disk. It searches 12+ candidate directories for each sprite file (the game can run from several paths — the dev copy, the installed launcher copy, etc.) so hard-coded absolute paths are avoided. The search tries each path in order and uses the first match found.

Three loading strategies coexist:
1. **Spritesheet slicing**: `SpriteManager.load_sprite_sheet()` for the main tileset; specific cell types reference rows/cols into the sheet.
2. **Individual PNGs by convention**: entity types (WOLF, GOBLIN, etc.) follow a naming convention — `wolf_right_1.png`, `wolf_right_2.png`, `wolf_still.png` — and `create_structure_sprites()` discovers them automatically.
3. **Explicit sprite dict**: items and special cells (IRON_ORE, WELL, etc.) have non-standard filenames. These are mapped in an `explicit_sprites` dict so the loader knows which file corresponds to which key.

Entity animation frames (2 or 3) are loaded per direction. The sprite manager stores everything in `self.sprites` so the HUD can draw any cell or entity type by key lookup.

---

## Section 2 — Update Scheduling (line 614)

### `update_cells`
Calls `update_screen_cells` for zones near the player at different frequencies:
- **Player's current zone** (`screen_distance == 0`): every 60 ticks — carrot growth, cobblestone decay, water spread happen here.
- **Adjacent zones** (`screen_distance == 1`): every 180 ticks.
- **Two zones out** (`screen_distance == 2`): every 600 ticks.

This throttling is the core performance strategy for cell simulation. Cells in zones the player can't see don't need to tick every frame — they just need to tick often enough that the world doesn't feel static when the player arrives.

### `update_entities`
**Legacy function — entity AI no longer runs here.** All NPC AI updates now run through `probabilistic_zone_updates` in `world/zones.py`, which ticks entities per-zone at distance-scaled intervals. `update_entities` still exists but is not called in the main loop; entity removal and heal_boost application have been absorbed into the zone update path.

The original design (documented here for reference) called `update_entity_ai` for each entity at:
- **Same zone** (`screen_distance == 0`): every tick.
- **Adjacent zone** (`screen_distance == 1`): every 60 ticks.
- **Two zones out** (`screen_distance == 2`): every 90 ticks.

If you are tracing an AI bug and don't find the entry point in `update_entities`, look in `world/zones.py:probabilistic_zone_updates`.

### `remove_entity`
The central death handler. It:
1. Records cause of death (`old_age`, `starvation`, `dehydration`, `combat`) for Watchdog logging.
2. Frees any keeper slot the entity held.
3. Broadcasts the death to the quest system (`quest_watcher_broadcast`).
4. Removes the entity from `self.followers` and `self.follower_items`.
5. Calls `process_entity_drop` to scatter loot at the entity's position.
6. Calls `_maybe_spawn_gravestone` for named humanoids.
7. Removes the entity from `self.entities` and `self.screen_entities`.

The order matters: loot is dropped before the entity is removed from `screen_entities` so the drop lands in the correct zone bucket.

### `_maybe_spawn_gravestone`
Named humanoid NPCs in zones that contain at least one house have a chance to leave a gravestone on death. Conditions:
- Entity must have a non-generic name (the `is_named` flag).
- The zone must have ≥ 1 house cell (not just any structure — specifically a residential zone).
- Maximum 5 gravestones per zone. When the cap is hit, the name is appended to an existing gravestone instead.
- New stones only appear near existing gravestone clusters, so they don't scatter randomly across the zone.

This creates natural-looking cemetery areas over time without explicit cemetery generation.

---

## Section 3 — Follower and Inspection Systems (line 923)

### `check_follower_integrity`
Run every tick. Enforces three invariants for all followers:
1. The follower entity still exists and is alive.
2. The follower is not hostile (hostile=False is forced — it can't be fighting the player).
3. The follower's current target is not the player.

If any invariant is violated, the entity is removed from `self.followers` and `self.follower_items`. This is a safety net, not the primary cleanup path — normal follower removal happens in `remove_entity`.

### `check_npc_inspection`
Handles the Shift-held or inspect-tool overlay that freezes a nearby NPC and shows its stats. Suppressed if any hostile entity is within 2 cells of the player — you can't inspect during combat. When a valid non-hostile NPC is selected, its `idle_timer` is set to 30 so it holds position for the inspection duration. The selected entity ID is stored in `self.inspected_npc` so the HUD can draw the stat panel on top of the entity.

---

## Section 4 — Cell Simulation (line 1072)

### `update_screen_cells`
Runs cell automata for a zone's grid. Most logic is probabilistic (random chance per cell per update) rather than deterministic:

- **Carrot growth**: CARROT1 → CARROT2 → CARROT3 at fixed per-tick probabilities, but accelerated 50x when near cobblestone (established farming zones) and 10x when near sand (desert farms are slower). This means farm plots in developed zones produce food significantly faster, creating an incentive to build roads near farms.
- **Cobblestone decay**: COBBLESTONE → DIRT at very low probability, but only outside the zone's center lanes and away from structures. Center-lane cobblestone (the main road) is protected from decay so roads persist. Off-road cobblestone — placed incidentally by travelers — eventually reverts.
- **Water spread**: WATER cells can spread to adjacent DIRT at low probability, simulating shoreline expansion. Capped per update to prevent runaway flooding.
- **Grass spread**: DIRT adjacent to GRASS has a chance to become GRASS over time, restoring disturbed terrain.

### `update_enchanted_cells`
Tracks cells that have been enchanted by the player (e.g., enchanted floor tiles that deal damage). Each enchanted cell has a duration counter; when it expires, the cell reverts to its pre-enchantment type. The `enchanted_cells` dict maps `(x, y, zone_key)` → remaining ticks.

---

## Section 5 — Input Handling (line 1153)

### `handle_input`
The main keyboard event processor. Reads from `pygame.event.get()` and dispatches to action handlers. Most actions have multiple keybinding aliases to support different play styles.

Key bindings:
| Key | Action |
|---|---|
| Arrow keys / WASD | `move_player` |
| SPACE | `interact` (context-sensitive: attack → pick up → use cell) |
| L | Cast selected spell (star spell, rain, day, keeper, summon, transform) |
| K | Release / reverse all enchantments |
| J | Release selected follower |
| B | Toggle blocking (90% damage reduction) |
| V | Toggle friendly fire |
| C | Open crafting tab |
| I | Open items tab |
| T | Open tools tab |
| M | Open magic tab |
| F | Open followers tab |
| Shift+F | Attempt to recruit inspected NPC as follower |
| Shift+G | Gift selected item to inspected NPC |
| Shift+T | Open inventory trade window with inspected NPC |
| Shift+Q | Get / turn in quest from inspected NPC |
| Shift+A | Toggle autopilot |
| N | NPC trade interaction (N key, adjacent trader) |
| P | Place selected item as a cell |
| Q | Toggle quest panel |
| D | Drop selected item |
| 1–9, 0 | Select inventory slot |

The autopilot overrides this function entirely when active — it drains its own input queue (`self.autopilot_input_queue`) instead of reading from pygame events.

### `handle_inventory_click` / `handle_quest_ui_click`
Mouse click handlers for the inventory and quest panels. These translate pixel coordinates into grid slot indices and dispatch to inventory actions (equip, drop, use) or quest actions (accept, abandon).

---

## Section 6 — Settings, Spells, Social (line 1621)

### Settings handlers
Volume sliders, keybinding overrides, and display options live in a settings dict persisted to a separate JSON file. Handlers validate input (volume clamped 0–1, key strings validated against pygame key names) before writing.

### Spell casting (`cast_spell`, `player_cast_spell`)
Player spell flow:
1. `player_cast_spell` checks energy cost, cooldown, and equipped spell.
2. Calls `cast_spell` with the spell name and target.
3. `cast_spell` applies the spell effect (damage, freeze, teleport, area-of-effect) and deducts energy.
4. Spell XP is awarded regardless of whether the target died.

Wizard NPCs share `cast_wizard_spell` (in `npc_ai.py`) — the player and NPC paths diverge only at step 1 (the player has a UI gate; NPCs don't).

### Social interactions
Pressing F near a non-hostile humanoid NPC toggles the follow/unfollow relationship. The NPC's hostility flag is checked first — hostile NPCs can't be recruited. Gold cost is checked for paid followers (guards, etc.). The entity is added to `self.followers` and `self.follower_items` with the item consumed from inventory.

---

## Section 7 — Quest and Trade (line 1780)

### `update_quests`
Called every tick. Scans active quests for completion conditions (cell count, entity kill count, item delivery) and awards XP/items on completion. Quest state is stored in `self.player['quests']` as a list of dicts with `type`, `target`, `progress`, and `reward` fields.

### `npc_trade_interaction`
Called when the player presses N near a trader. Opens a fixed-recipe trade panel if adjacent to a TRADER entity, or executes the first available recipe if the panel is already open. Recipe ingredients are checked against the trader's inventory — the player pays gold by proximity-dropping it and the trader dispenses goods from its own stock.

### `open_npc_trade_window`
Called on Shift+T when an NPC is being inspected. Opens an inventory-style grid UI above the NPC showing every item in their inventory with a randomized gold price (5–10 per item, generated fresh each open). This is the newer trade system, distinct from the N-key recipe panel — it lets the player browse and buy individual items rather than fixed recipes.

### `handle_npc_trade_click`
Mouse-click handler for the inventory trade window opened by `open_npc_trade_window`. Maps screen coordinates to item slots, deducts gold from the player, transfers the item to player inventory, and refreshes the panel. Closes the panel automatically when the NPC's inventory is empty. Stored in `self.trader_display` dict; cleared on zone cross, panel close, or NPC departure.

---

## Section 8 — Item UID and Inventory Slots (line 2085)

### `generate_item_uid`
Each item placed in the world (dropped, chest-stored) gets a unique integer ID so the save system can round-trip items without collisions. The UID counter is stored in `self.item_uid_counter` and increments monotonically. UIDs are never reused in a session.

### Inventory slot management
`get_slot_for_item`, `equip_item`, `unequip_item` handle the 9-slot hotbar and separate body-slot equipment (weapon, armour, ring, etc.). Equipping an item that doesn't fit its slot raises a UI notification rather than silently failing. The body-slot system is separate from the hotbar so body equipment doesn't consume action slots.

---

## Section 9 — Player Movement (line 2115)

### `move_player`
Moves the player one cell in the requested direction, subject to:
1. **Autopilot input drain**: if autopilot is active, movement commands come from `self.autopilot_input_queue` rather than the keyboard — the function drains the queue before processing keyboard input.
2. **Structure exits**: walking off the bottom edge of a house interior calls `exit_structure`. Walking onto STAIRS_UP in a cave calls `ascend_cave`.
3. **Overworld zone crossing**: exits are only open when the player is in the center corridor of the edge (±1 cell of the zone center line). This keeps the player from accidentally leaving a zone while walking along a wall.
4. **Entity collision**: checks `screen_entities` for entities at the target cell. Autopilot proxy bypasses this check (the proxy is the player, so it can't collide with itself).
5. **Walk cell effects**: `_apply_walk_cell_effects` runs after a successful step, applying any cell-type environmental effects (mud slowing, road speed bonuses, etc.).

### `get_target_cell`
Returns the cell coordinates in the direction the player is facing. Used by `interact` and tool actions to identify what the player is pointing at without requiring a direction argument.

---

## Section 10 — Interact and Tool Actions (line 2335)

### `interact`
The context-sensitive action bound to SPACE. Priority order:
1. **Attack**: if a hostile entity is adjacent in the facing direction, deal melee damage.
2. **Pick up dropped items**: if items are on the player's cell, collect them.
3. **Cell interaction**: dispatched by the cell type at the target cell:
   - **STAIRS_UP / STAIRS_DOWN**: `ascend_cave` / `descend_cave`.
   - **CHEST**: open the chest panel and list contents.
   - **WELL / WATER**: fill the player's water.
   - **Enterable structures** (HOUSE, CAVE, MINESHAFT): `enter_structure`.
   - **Tool-specific**: axe → chop tree; pickaxe → mine rock or dig down; hoe → till soil; bare hands → harvest crop, plant carrot, place bones.

The priority order is deliberate: you can't accidentally open a chest if a hostile is in front of you; you can't till soil if you're standing on items. Each tier short-circuits if it fires — the first applicable action runs and the rest are skipped.

---

## Section 11 — Structure Navigation (line 2519)

### `enter_structure`
Transitions the player into a house, cave, or mineshaft interior. It:
1. Looks up or generates the structure's virtual zone (negative-x zone key).
2. Sets `self.player['in_structure'] = True` and `self.player['structure_key']`.
3. Updates `self.player['screen_x/y']` to the virtual zone coordinates.
4. Places the player at the structure's entrance position.
5. Teleports all followers to the entrance (they can't navigate structure transitions on their own).
6. Stores the originating overworld zone key in `self.player['origin_zone']` for correct exit routing.

The `_pending_structure_entry` flag is set so the run loop knows to re-render the new zone on the next tick without a one-tick stale-frame flash.

### `exit_structure`
Moves the player back to the overworld. Clears `in_structure`, restores `screen_x/y` to the origin zone, and places the player near the structure's door cell. Followers are teleported to the exit position. The exit area is added to the player's recent-steps memory to prevent immediately re-entering.

### `descend_cave` / `ascend_cave`
Multi-level cave navigation. `descend_cave` generates the next level if it doesn't exist and transitions the player down, incrementing `self.player['cave_depth']`. `ascend_cave` decrements depth and transitions up — at depth 1 it calls `exit_structure` to return to the overworld.

### `_exit_secret_cave_entrance`
Handles the edge case where a cave was entered via a MINESHAFT cell inside a house interior (not via the overworld CAVE cell). Two fallback paths:
1. If the originating structure's door cell is known, exit to that structure's interior.
2. If not, exit directly to the nearest walkable overworld cell.

This case arises because house interiors can contain MINESHAFT cells that lead deeper — the player entered a structure from the overworld, then descended into a cave from inside the structure, and now ascending must return them to the structure interior rather than the overworld.

---

## Section 12 — Chest Interaction (line 2608)

### Chest open/close/loot
Chests store items in `self.chest_contents` keyed by `(x, y, zone_key)`. Opening a chest renders a panel listing its contents. Items can be taken individually or all-at-once. Closing the panel without taking items leaves them in place.

`chest_backgrounds` stores what cell type was under each chest before placement so the cell can be correctly restored if the chest is destroyed (e.g., by `on_house_collapsed`).

---

## Section 13 — `new_game` and World Aging (line 2992)

### `new_game`
Resets all game state to defaults and sets up a fresh world. Two details separate this from `__init__`:

1. **Follower spawn deferral**: the starting follower is not spawned in `new_game`. Instead, `self._pending_follower_type` is set to a randomly selected peaceful animal type (chosen from SHEEP, DEER, RED_BIRD, BUTTERFLY, CHICKEN). The actual spawn happens in the run loop after time-pass simulation completes. This prevents the follower from being killed during the 150-250 year world-aging simulation that runs before the player starts.

2. **Stale follower item purge**: `follower_items` may contain entries from a previous game session (save-load edge cases). `new_game` explicitly clears this dict before populating it.

3. **Time-pass trigger**: after resetting, `self.state = 'death'` is set which triggers the death screen / time-passage cutscene. The world ages 150-250 simulated years (randomized) before the player's first tick. This populates zones with NPCs, structures, and resources before play begins rather than starting in a freshly-generated empty world.

---

## Section 14 — `run` — Main Loop (line 3136)

### `run`
The pygame event loop. Each iteration:
1. `handle_input` — keyboard/mouse events
2. `move_player` — apply queued movement
3. `check_follower_integrity` — safety net for follower state
4. `sound.update` — tick sound manager (fade-outs, queued tracks)
5. `check_npc_inspection` — Shift-held overlay
6. `reconcile_screen_entities` — every 600 ticks: walk all entities and verify their `screen_entities` bucket matches their `screen_x/y` coordinates. Repairs the desync bug where an entity is registered in the wrong zone bucket.
7. **Freeze detector** — every 300 ticks: checks if the tick counter advanced since last check. If not, logs a stall event to the Watchdog. This detects infinite loops or deadlocks that would otherwise be invisible.
8. **Health/energy regen** — every 60 ticks: player passive regeneration.
9. `update_quests` — check completion conditions
10. `update_enchanted_cells` — decrement enchantment timers
11. **Probabilistic zone updates** — `update_cells`, `update_entities` with distance-based throttling
12. `watchdog.update(tick, self)` — Watchdog snapshot cycle
13. **Autosave** — every 30 seconds real time
14. `_auto_debug_shutdown` — check if the session timer has expired (observation sessions)
15. `tick += 1`
16. `draw` — HUD render

The frame rate is capped at 60 FPS via `pygame.time.Clock.tick(60)`. The `time_pass_speed` multiplier is applied during world-aging simulation to run through many ticks per frame without rendering each one.

---

## Notes for Contributors

**Player is a dict, not an Entity:** `self.player` is `{}` — it doesn't inherit from `Entity`. This means it won't have `gain_xp`, `take_damage`, or other Entity methods. All player-specific stat changes go through dedicated functions in `game_core.py` (`player_take_damage`, `player_gain_xp`, etc.).

**`new_game` vs `__init__`:** `__init__` runs once at process start. `new_game` can run multiple times (start fresh, load from save-select screen). State that must be truly fresh on every new game belongs in `new_game`; state that only initializes at process start belongs in `__init__`. When in doubt, both.

**`screen_entities` desync:** The most common class of entity bugs. An entity's `screen_x/y` fields say one zone; its `screen_entities` entry is in another. `reconcile_screen_entities` heals this every 600 ticks, but the root cause is any code that updates one without the other. Every zone transition must write both.

**Autopilot input queue:** When `self.autopilot_active = True`, `handle_input` and `move_player` drain `self.autopilot_input_queue` (a list of direction strings). This is the only way the autopilot controls the player — it never calls movement functions directly. To add a new player capability to the autopilot, push direction strings or action codes onto the queue from `autopilot.py`.
