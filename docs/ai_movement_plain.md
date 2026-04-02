# ai/movement.py — Plain Language Guide

**What this file is:**
All NPC movement and spatial reasoning lives here. It covers how entities walk, pathfind, cross zone boundaries, enter and exit structures, detect targets, and find food/water/shelter. It is a mixin (`NpcAiMovementMixin`) that is mixed into the main `Game` class alongside `NpcAiMixin`, so all methods have access to `self.entities`, `self.screens`, `self.structures`, `self.screen_entities`, and `self.player`.

**Why it's separate from npc_ai.py:**
`npc_ai.py` handles the state machine — deciding *what* an entity wants to do. This file handles the *how* — the actual spatial operations. Keeping them separate limits the size of each file and makes it possible to reason about movement independently of state logic.

---

## Section 1 — Footstep Audio (line 18)

### `_npc_footstep_sound`
Plays a footstep sound for an entity based on the cell it just stepped on. The volume is scaled by how far the entity is from the player: entities more than 8 cells away are silent, entities within 1 cell are full volume. This is structured as a distance-falloff function rather than a simple "play or don't play" so the world sounds increasingly busy as the player moves through populated zones without any single sound dominating.

---

## Section 2 — Wandering (line 41)

### `wander_entity`
Moves an entity one cell in a random direction, subject to a rate limiter and a memory lane that prevents immediately revisiting the last 6 positions. The rate limiter computes a tick interval based on the entity's speed — faster entities move more frequently, but no entity can move every single tick. When the entity steps out of the grid boundary, it hands off to `try_entity_screen_crossing` for overworld entities, or clamps the step for structure-bound entities.

**Why the rate limiter formula:** `interval ≈ 1/(0.034 * speed)` gives a natural linear relationship between speed stat and movement frequency without requiring fractional-tick math. The constant 0.034 was calibrated so a speed of 5 (average) produces roughly one step every 6 ticks.

**Why memory lane:** Without it, entities get trapped in corners, oscillating between two cells. The last-6-positions blacklist gives enough history to escape local minima without the overhead of true flood-fill pathfinding.

---

## Section 3 — Directed Pathfinding (line 168)

### `move_toward_position`
Moves an entity one cell toward a target `(tx, ty)`. It builds a prioritized list of four candidate directions — primary (the axis with the larger gap), secondary (the other axis), perpendicular (sideways), and backward (away from target as a last resort) — and tries each in order until it finds a walkable, unoccupied cell.

A `reserved_cells` dict (cleared once per tick game-wide) prevents two entities from stepping into the same cell simultaneously. Memory lane is checked here too: cells in the entity's recent history are skipped unless the entity has been stuck for several attempts, in which case it falls back to accepting blacklisted cells.

**Why not A*:** A* requires a complete graph traversal every call, which would be prohibitive for hundreds of entities per tick. The priority-direction approach is O(1) per step and handles most navigable terrain correctly because the world is open with small obstacles. True deadlock (impassable wall spanning the full path) is rare and handled by the stuck counter in the outer loop.

### `_get_exit_toward_zone`
Given a target zone key `(tx, ty)` and the entity's current zone, returns which edge of the current grid the entity should aim for — north wall, south wall, east wall, or west wall. This is used by targeting logic to route entities toward a zone boundary when their target is in a different zone.

### `_try_targeting_zone_cross`
When an entity is in targeting state and its grid position is near a boundary, this attempts an immediate zone crossing via `try_entity_zone_transition`. It exists because `move_toward_position` can carry an entity to the edge of the grid while chasing a cross-zone target, and something needs to complete the actual zone handoff.

### `_find_valid_entrance_cell`
When an entity transitions into a new zone, the computed entrance position (the cell adjacent to the exit) may be solid (a wall, a tree). This scans a small radius around the expected entrance position for the nearest walkable cell. It prevents entities from spawning inside impassable terrain after crossing zone boundaries.

---

## Section 4 — Zone Transitions (line 439)

### `try_entity_zone_transition`
The explicit zone-crossing path. When an entity is standing on an exit cell and the game decides it should cross (based on travel rate and cooldown), this function:
1. Determines the target zone coordinates.
2. Generates the target zone if it hasn't been visited yet.
3. Removes the entity from `screen_entities` for the current zone.
4. Updates `entity.screen_x/screen_y` to the new zone.
5. Adds the entity to `screen_entities` for the new zone.
6. Finds a valid entrance cell in the new zone.
7. Adds the exit area to memory lane so the entity doesn't immediately bounce back.

A per-entity cooldown (`zone_transition_cooldown`) prevents crossing-and-immediately-recrossing, which would create jitter at zone edges.

### `try_entity_screen_crossing`
The seamless crossing path. When `wander_entity` or `move_toward_position` carries an entity's `(x, y)` out of grid bounds (e.g., x < 0 or x >= GRID_WIDTH), this function treats that as a zone crossing attempt — the entity "walked through" the boundary rather than stepping onto an explicit exit cell. It applies the same zone-generation, registry update, and entrance-finding logic as `try_entity_zone_transition`.

Additional logic here: keeper types 1 and 2 are blocked from crossing — they're anchored to their home zone. If the destination zone already has more than 15 entities of the same type, `try_merge_entity` is called first to combine entities before adding more.

---

## Section 5 — Greedy Pathfinder (line 720)

### `move_entity_towards`
An older, simpler pathfinder: for each possible direction, compute which step brings the entity closest to `(tx, ty)`, and take the best one. No priority list, no candidate ranking — just pick the direction that minimizes distance. It has a `TARGET_STUCK_THRESHOLD` of 180: if the entity calls this function 180 consecutive times without changing its `last_target_position`, the target position is added to memory lane (blacklisted) and the counter resets.

**Why both pathfinders exist:** `move_toward_position` is the primary pathfinder used by the state machine. `move_entity_towards` predates it and is still used by legacy code paths like `find_and_move_to_food` and `npc_seek_shelter`. They'll converge over time.

---

## Section 6 — Seeking Zone Exits (line 905)

### `seek_zone_exit`
Finds the nearest exit cell in the entity's current zone and moves toward it. Works for both overworld zones (exit flags on wall cells) and structure zones (the `exit` position stored in the structure dict). This is the single function that should be called whenever an entity wants to leave its current zone, regardless of whether it's indoors or outdoors — structures are zones, zone exits are zone exits.

---

## Section 7 — Structure Entry and Exit (line 970)

### `npc_enter_structure`
Moves an entity into a cave, house, or mineshaft. It:
1. Sets `entity.in_structure = True` and `entity.structure_key` to the virtual zone key.
2. Moves the entity's registration from `screen_entities[overworld_key]` to `screen_entities[structure_key]`.
3. Places the entity at the `entrance` position of the structure.
4. Clears any active targeting state so the entity starts fresh inside.

Structures are pre-built zones with a virtual negative-x coordinate key. From the entity's perspective, entering a structure is the same as crossing a zone boundary — only the zone key changes.

### `npc_exit_structure`
Moves an entity out of a structure. Multi-level caves require ascending one level at a time: an entity at depth > 1 exits to the level above rather than directly to the overworld. At depth 1 (or for houses with no levels), the entity is placed near the door cell in the parent overworld zone and the `in_structure` flag is cleared. The exit area is added to memory lane to prevent immediate re-entry.

### `update_structure_npc_behavior`
Called for entities already inside a structure each tick. For house interiors, entities slowly regenerate health while sheltered. For cave interiors, if the entity has no valid target inside the cave and its health is below a threshold, it triggers exit behavior (flee toward stairs). This is the logic that makes injured NPCs retreat from caves.

### `move_npc_toward_structure_exit`
Steps an entity one cell toward the `STAIRS_UP` cell in a cave. When the entity reaches it, `npc_exit_structure` is called to complete the exit. This is a simple step-toward call, not the full pathfinder, because cave layouts are small and the stairs are always reachable within the same interior.

### `has_target_in_structure`
Returns `True` if the entity's current target is inside a specific structure. Used to decide whether a hostile entity chasing a target should enter the structure to continue the chase.

---

## Section 8 — Opportunistic Structure Entry / Exit (line 1294)

### `try_npc_enter_structure`
Called every tick for overworld entities. Checks whether the entity is adjacent to an enterable cell (HOUSE, CAVE, MINESHAFT) and has a reason to enter:
- **Bats (daytime):** Always try to enter any adjacent cave during daytime.
- **Humanoids (night):** Enter adjacent houses when is_night is True.
- **Hostile entities (chasing):** Enter a cave if the entity's current target is inside it, as reported by `has_target_in_structure`.

This opportunistic check runs even when the entity is wandering or idle, which is why a wandering wolf can walk into a cave on its own.

### `try_npc_exit_structure`
Called every tick for structure-bound entities. Decides if the entity should leave: checks if the entity's goal (targeting state, daytime for bats, etc.) requires it to be outside. If yes, steps toward the structure exit and triggers `npc_exit_structure` when adjacent.

---

## Section 9 — Role-Specific Movement (line 1394)

### `try_travel_behavior`
Used by trader NPCs. Picks a random zone exit and moves toward it, completing the zone crossing when adjacent. Traders don't have a fixed destination — they just keep moving through zone boundaries.

### `try_patrol_behavior`
Used by guard NPCs. Picks a waypoint along the vertical center lane of the current zone and moves toward it. When the waypoint is reached, a new one is chosen. Center-lane patrol keeps guards visible and predictable rather than wandering to corners.

---

## Section 10 — Entity Merge and Split (line 1450)

### `try_merge_entity`
When a zone has more than 3 entities of the same type, combines two of them into a `_double` variant (e.g., `WOLF` + `WOLF` → `WOLF_double`). The double is added to the zone, both originals are removed. This is a visual-density optimization: zones that become overcrowded through natural travel don't render 20 individual sprites — they reduce to doubles. The merged entity inherits the higher level of the two originals.

### `try_split_double_entity`
When a zone is underpopulated (only one or two of a type remain) and a `_double` variant is present, splits it back into two singles. The split entities are placed near the double's position. This balances the world population over time without requiring a global spawner to replenish zones.

---

## Section 11 — Follower Teleport (line 1540)

### `teleport_follower_to_player`
If a follower entity is on a different screen than the player, it is immediately moved to the player's current zone and placed adjacent to the player. This bypasses all zone-crossing logic intentionally — followers should never be stranded on a different screen, and natural zone crossing would be too slow to keep up with the player.

---

## Section 12 — Target Finders (line 1563)

These functions scan the current zone's grid (and sometimes entity lists) to find the nearest instance of a target type. All return a tuple `('cell', x, y, cell_type)` for cell targets, an entity ID integer for entity targets, or `None` if nothing is found. They are called by `find_closest_target_by_type` and directly by `determine_target_type` in `npc_ai.py`.

### `find_closest_food_source`
Scans the grid for cells matching the entity's `food_sources` list (from its props). Also scans `screen_entities` for entity types that are prey (e.g., wolves can eat sheep). When the entity is inside a structure, searches the structure grid instead of the overworld grid so in-structure food (like APPLE_CRATE) is visible.

### `find_closest_water_source`
Scans the grid for cells in the entity's `water_sources` list. Same structure-aware grid selection as `find_closest_food_source`. Most entities use `['WATER']`; humanoids also include `['WELL', 'WATER_TROUGH']`.

### `find_closest_resource`
Scans for TREE1, TREE2, or STONE cells. Used by lumberjacks and miners targeting resource cells. Not structure-aware because resource harvesting is an overworld-only activity.

### `find_closest_structure`
Scans for HOUSE, CAMP, or FORGE cells. Used by entities whose role target is a building (smiths, traders).

### `find_hostile_in_connected_structures`
Scans CAVE and MINESHAFT entrance cells in the current zone, then looks inside each connected structure for hostile entities. Returns the entity ID, the distance to the cave door (not the entity itself), and the door position. This allows overworld entities to detect threats hiding in caves they haven't entered yet — a guard can see that a wolf is inside the cave 3 cells to the east and decide to pursue.

### `find_closest_hostile_entity`
Finds the nearest enemy in the current zone using the three-tier hostility check: hostile vs non-hostile, hostile vs different-species hostile, and faction vs faction. Also includes the player as a potential target if the entity is hostile. Calls `find_hostile_in_connected_structures` afterward and returns the cave-target if it's closer than any overworld target.

### `_is_hostile_target`
A pure predicate: given a target (entity ID, `'player'`, or tuple), returns True if that target is an enemy of the calling entity. Uses the same three-tier hostility check as `find_closest_hostile_entity`. Used by the state machine to validate whether a stored target is still hostile before committing to combat.

### `get_target_distance`
Returns Manhattan distance from an entity to its target. Handles all three target formats: `'player'` (returns inf if different zone), integer entity ID (returns inf if entity no longer exists), and tuple targets in either `('cell', x, y, ...)` or raw `(x, y)` form. Returns `inf` on any error so callers can always do a safe comparison.

---

## Section 13 — Legacy Seek Functions (line 1870)

### `find_and_move_to_food` / `find_and_move_to_water`
Older, self-contained versions of the find-move-eat/drink cycle. They locate food/water, move toward it using `move_entity_towards`, and consume it when adjacent — all in one call. When no food or water is found in the current zone, they set `entity.no_food_in_zone = True` and call `seek_zone_exit` so the entity travels to find resources. Urgency-based multi-step movement is included: critically hungry entities take 3 steps per call instead of 1.

These functions predate the state machine's targeting system, which handles food/water consumption through the idle-action dispatch in `npc_ai.py`. Both paths are still active; the state machine path is preferred for new code.

### `find_nearest_hostile_in_range` / `find_nearest_entity_in_range` / `find_nearest_non_faction_entity`
Utility range-scanners that iterate the global entity dict (not zone-bucketed `screen_entities`) and filter by zone coordinates, hostility, or faction. These are used by specific systems (autopilot, wizard spell targeting) that need a range check without going through the full target-type scoring system.

---

## Section 14 — Target Router (line 2104)

### `find_closest_target_by_type`
The single entry point for resolving a `target_type` string to an actual target. Maps type strings (`'hostile'`, `'food'`, `'water'`, `'shelter'`, `'resource'`, `'role'`, `'travel'`, `'quest_target'`, `'clearing_action'`, `'trade'`, `'any_entity'`) to their respective finder functions. The `'role'` type uses `ROLE_CELL_PRIORITY` and `ROLE_CELL_TARGETS` from constants to determine what cells a miner, blacksmith, or farmer should seek. The `'travel'` type returns the structure's exit position when the entity is inside one. `'trade'` is a stub — the trader-to-trader commerce system is not yet implemented.

### `find_closest_eligible_target`
A flexible multi-type scanner: given a list of target cell types or entity types, finds the nearest match in the current zone. Structure-aware: if the entity is inside a cave and the target only exists in the parent overworld zone, it returns the cave's exit position so the entity navigates out first.

---

## Section 15 — Shelter System (line 2207)

### `_find_nearest_shelter` / `_find_closest_shelter`
Two nearly-identical shelter finders with a key difference: `_find_nearest_shelter` uses the `_SHELTER_CELLS` frozenset (HOUSE, STONE_HOUSE, FORT — no caves), while `_find_closest_shelter` uses `CELL_TYPES[c]['enterable']` to find any enterable non-cave cell. The former is used by the targeting system; the latter by `npc_seek_shelter`. They should probably be unified — they exist because they were written at different times.

### `npc_seek_shelter`
The full shelter-seeking behavior for overworld entities at night. Finds the nearest house or camp, moves toward it, and enters when adjacent. Camp is treated as resting-in-place (no structure entry needed). Once the entity is idle inside/at a camp, it stays idle unless a hostile comes within 5 cells or hunger/thirst drops below 30. This entire function is technically bypassed by the state machine's shelter target type — it's a legacy path used by some older NPC types.

### `_find_closest_any_entity`
Finds the nearest entity of any kind in the current zone, excluding self. Used by quest types that target any NPC (e.g., `combat_all` quests where the objective is to eliminate all entities in a zone).

---

## Notes for Contributors

**Two pathfinders:** `move_toward_position` (primary, prioritized direction list) and `move_entity_towards` (legacy, greedy best-distance). New code should use `move_toward_position`. Both are safe to call every tick.

**Zone keys are strings:** Always `f"{screen_x},{screen_y}"`. Structure zones use large negative x values (≤ -1000) so they never collide with overworld keys.

**`screen_entities` is the ground truth** for what entities are in which zone. Any code that moves an entity between zones must update both `entity.screen_x/screen_y` and the `screen_entities` registry. Failure to do both causes the subscreen-flag desync bug documented in `debug/held_back.md`.

**Memory lane** is a per-entity list of recent positions (last 6 by default). It's checked during movement to avoid oscillation. It's also used to blacklist zone exit cells temporarily after a crossing, preventing bounce-back.
