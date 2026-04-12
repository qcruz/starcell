# world/generation.py + world/zones.py — Plain Language Guide

**What these files are:**
Two mixins that together own procedural world generation and the runtime update loop for all zones:

- **`WorldGenerationMixin`** (`generation.py`): builds zones from scratch — overworld grids, house interiors, cave interiors, chest placement, entity spawning, and the zone connection graph.
- **`ZonesMixin`** (`zones.py`): drives everything after generation — the priority-queue update loop, cell simulation, entity lifecycle, biome shift, domain management, and zone purging.

Both are mixed into `Game` alongside the AI and game-core mixins, so they share `self.screens`, `self.entities`, `self.screen_entities`, and every other piece of game state.

---

## Section 1 — Zone and Structure Naming (generation.py, line 15)

### `generate_zone_name` / `generate_structure_name`
Procedural names are assembled from class-level word lists: an adjective chosen from `_ZONE_ADJECTIVES`, a biome-specific noun from `_ZONE_NOUNS`, and a biome type from `_ZONE_BIOME_TYPES`. The result is something like "Silent Ash Wood" or "Iron Crag Mountains."

House names are personalized: `generate_structure_name` scans the parent zone's entities for any NPC with a name and uses it (`"Aldric's House"`). If no named NPC is found it falls back to `_FALLBACK_HOUSE_NAMES`. Cave names append a modifier ("Mysterious", "Ancient") to the parent zone name at depth 1, then append "Lvl N" for deeper levels, stripping any prior level suffix first.

The word lists live at the class level so they're constructed once and shared across all instances (there is only one `Game`, but it's good practice).

---

## Section 2 — `generate_screen` — Overworld Zone Generation (generation.py, line 78)

### Biome selection
Each new zone picks a biome at random from `BIOMES` (equal weight). The biome dict maps cell types to spawn probabilities — a FOREST biome might be 40% GRASS, 20% TREE1, 15% TREE2, 10% DIRT, etc. There is no biome continuity between adjacent zones by default; continuity emerges over time through the biome-reversion system in `zones.py`.

### Exit generation and bidirectional consistency
Each zone has four potential exits (top, bottom, left, right), each initially a 50/50 coin flip. Before finalizing, the code checks whether each neighboring zone already exists. If it does, the exit is forced to match the neighbor's opposing exit — if the zone to the north has `exits['bottom'] = True`, this zone must have `exits['top'] = True`. This bidirectional consistency means no zone can have a one-way door: if you can walk through, you can walk back.

After consistency enforcement, at least 2 exits are always guaranteed so no zone is a dead end with no way out.

### Grid layout
The grid is filled row by row:
- **Border cells** (row 0, row GRID_HEIGHT-1, col 0, col GRID_WIDTH-1): WALL, except at the exit positions — 2 cells wide at the center of each edge.
- **Exit cells**: the biome's characteristic walkable cell (GRASS for forests, SAND for deserts, etc.) so the transition looks natural.
- **Interior cells**: sampled from the biome probability table using a cumulative probability roll.

### Variant grid
After the main grid, a second `variant_grid` of the same dimensions is filled. Each cell has a chance to roll a cosmetic variant (e.g., a GRASS cell might render as a slightly different shade). Variants are visual only — they don't affect gameplay. Storing variants separately from the main grid means the gameplay logic never has to deal with them.

### Special placements
After the base grid is generated:
- **30% chance**: one HOUSE or CAVE is placed at a random interior cell.
- **Desert only, 60% chance**: 1–4 RUINED_SANDSTONE_COLUMN cells are scattered on SAND/DIRT.
- **10% chance** (non-lake): a WELL is placed near the zone center.
- **Natural cave**: a CAVE is placed on a random solid cell at a low base rate, multiplied 3x in MOUNTAINS and 1.5x in DESERT. The cave uses an existing solid cell rather than replacing a special structure.

### Entity spawning and runestones
`spawn_entities_for_screen` populates the zone with NPCs appropriate to the biome. `spawn_runestones_for_screen` scatters rare RUNESTONE cells. Both are called once at zone generation and never called again for the same zone.

### Why generation is deferred
Zones are generated on first access, not at startup. `screens[key]` is the guard — if the key exists, no generation happens. This means the world is infinite in the sense that the player can keep walking in any direction indefinitely; zones beyond the current view radius simply don't exist yet.

---

## Section 3 — Exit and Cell Helpers (generation.py, line 294)

### `roll_cell_variant`
Single-call helper that samples the variant table for a cell type. Used by `set_grid_cell` so any code that changes a cell automatically gets a fresh variant roll.

### `set_grid_cell`
**Always use this instead of `screen['grid'][y][x] = ...`** for cell changes. It writes to both the grid and the variant_grid simultaneously. Forgetting to update variants causes stale visual artifacts — a GRASS cell at a position that shows a TREE1 variant, for example.

### `update_screen_exits`
Redraws all four border rows/columns of a zone's grid to match its current `exits` dict. Called whenever a neighboring zone is generated and forces a new exit open on the shared edge. This is the mechanism that keeps exit cells visually correct after bidirectional consistency is applied — the exits dict is the source of truth, and this function materializes it into the grid.

### `get_exit_positions`
Returns the two grid coordinates (one zone has 2-cell-wide exits) for a given exit direction. Used by movement code to determine which cells are walkable zone-crossing tiles.

### `get_biome_base_cell`
Returns the primary walkable ground cell for the current zone's biome — GRASS for forests and plains, SAND for desert, DIRT for mountains/tundra/swamp. Used when a cell needs to revert to neutral (a CHEST that decays back to its background, for example).

---

## Section 4 — `generate_structure_zone` — Interior Zone Creation (generation.py, line 418)

### Virtual coordinates
Structure zones don't exist at accessible overworld coordinates. Each gets assigned `vx = -(1000 + structure_id * 10)`, `vy = 0` — deep in the negative-x range where no entity can walk to them naturally. This puts structures in the same coordinate system as the overworld without the risk of collision. `is_overworld_zone` checks `x > -500` to distinguish them.

### CAVE depth 1 deduplication
If a CAVE zone already exists for a parent zone (stored in `zone_cave_systems`), `generate_structure_zone` returns the existing key rather than creating a duplicate. Every overworld zone shares one cave system — entering from different CAVE cells always leads to the same interior.

### Dual registration
Every structure is registered in both `self.structures` (structure metadata) and `self.screens` (the general zone dict). The `screens` dict is how everything else — rendering, entity lookup, cell updates — finds zone data. The `structures` dict is a metadata shortcut for structure-specific lookups (door positions, entrance, depth). Both must stay in sync.

### Door map
`door_map[(parent_key, door_x, door_y)] = (structure_key, entrance_x, entrance_y)` and the reverse entry are both written. This bidirectional mapping is how `enter_structure` and `exit_structure` in `game_core.py` know where to put the player after a zone transition.

### Chests and entities
After grid generation, `place_house_chests` / `place_cave_chests` place locked chests in the layout, and `_spawn_cave_entities` / `spawn_house_npc` add entities. These happen inside `generate_structure_zone` so the interior is ready the moment it's created — the player stepping into a house doesn't see it empty for one tick before NPCs appear.

---

## Section 5 — Interior Layout Generators (generation.py, line 530)

### `generate_house_interior`
Builds a small enclosed room:
- WALL border on all sides except the bottom center (doorway, 3 cells wide).
- Interior: 70% FLOOR_WOOD, 30% WOOD (structural beams).
- One bed against the top wall.
- 0–2 furniture items (bookshelf, table, chair, potted plant) scattered on floor.
- Guaranteed WATER_TROUGH on a random floor cell — NPCs and the player can hydrate indoors.
- Apple crate + 0–2 empty crates placed in corner positions (predictable storage locations).
- 0–3 barrels placed randomly.

The corner-preference for crates and the top-wall preference for beds creates a consistent visual grammar across all houses — furniture isn't truly random, it follows a layout that feels lived-in.

### `generate_cave_interior`
Builds a fully walled cave space:
- CAVE_WALL border.
- Interior cell probabilities: 3% IRON_ORE (7% at depth 2+), 12% STONE (scaled down from 15% by ore chance), rest CAVE_FLOOR. Deeper caves are richer.
- STAIRS_UP placed at the position aligned to the parent entrance cell (so the stairs appear where the player entered). A 3×3 area around the stairs is cleared to ensure walkability.
- 1–3 mushroom seeds on CAVE_FLOOR cells.
- 20% chance for a WATER_TROUGH.
- 70% chance for STAIRS_DOWN (also with 3×3 clearance) — this is what allows multi-level descent. The 30% chance of no STAIRS_DOWN creates dead-end cave levels.

---

## Section 6 — Zone Connection Graph (generation.py, line 802)

### `add_zone_connection` / `remove_zone_connection`
These maintain `zone_connections` — a dict mapping each zone key to a list of `(connected_key, type, cell_x, cell_y)` tuples. Connections are bidirectional; both directions are written or removed together.

The connection graph drives the priority queue: zones connected to the player's current zone get a priority boost so they're updated more often. It also enables `find_hostile_in_connected_structures` to detect enemies in adjacent caves without entering them.

### `register_structure_as_zone`
A legacy path that creates `struct_N` zone keys. The current preferred path uses virtual coordinate keys (the `vx = -(1000 + id * 10)` scheme). Both exist because the virtual coordinate system was added after `register_structure_as_zone` and there hasn't been a full migration.

---

## Section 7 — `probabilistic_zone_updates` — The Update Loop (zones.py, line 83)

This is the main zone driver called from the game's `run` loop every `UPDATE_FREQUENCY` ticks.

### New zone instantiation
Each call has a small chance to generate a new random overworld zone within ±20 of the player. The probability is distance-weighted (zones far from the player are less likely) and rate-limited by `ZONE_SOFT_CAP` — once the overworld reaches the soft cap, the instantiation chance drops sharply to prevent unbounded world growth.

### 600-tick maintenance sweep
Every 600 ticks:
- `cleanup_screen_entities`: removes stale/dead entity IDs from all zone buckets.
- Faction control recomputed for all overworld zones.
- `instantiated_zones` synced with `screens` (belt-and-suspenders desync repair).
- `door_map` validated: entries pointing at non-existent zones are removed.
- Structure zones whose parent entrance cell was destroyed (e.g., a CAVE cell mined out) are de-instantiated.
- **Zone de-instantiation**: overworld zones beyond distance 4 that have been idle >3600 ticks and contain no alive entities are deleted with probability proportional to distance.

### Staleness hard trim
Zones not updated in >20,000 ticks get probabilistically deleted regardless of content. This is the final safety net against world memory growth — zones that are both distant and completely untouched eventually evaporate. Player-adjacent zones (within distance 4) are always protected.

### Mandatory and priority zones
The player zone plus its 4 cardinal neighbors and any connected structure zones are "mandatory" — they always update at full entity coverage (100%) and half cell coverage (50%). All other zones go through the priority queue: queue position determines both whether the zone is updated and at what coverage fraction. Zones at the front of the queue get ~100% coverage; zones 100 positions back get ~5%.

This design ensures the player's immediate surroundings always respond correctly while distant world simulation degrades gracefully under load.

---

## Section 8 — `update_zone_with_coverage` — Per-Zone Tick (zones.py, line 264)

The full per-zone update, called for each zone that wins the priority queue. Everything in the game world that isn't player-driven happens here.

### Cell updates
- **CHEST lifecycle**: chests with contents have a 0.5% chance per update to dump their contents as dropped items and revert the cell to the background type. Empty chests always revert immediately. This prevents chests from accumulating forever and returning cells to the world if they're abandoned.
- **Cell growth/decay**: reads `grows_to` and `degrades_to` from `CELL_TYPES` with their associated rates. All rates are multiplied by `time_pass_speed` so the world evolves visibly during fast-forward simulation.
- **Desert rock/ore formation**: SAND slowly solidifies to STONE; STONE rarely converts to IRON_ORE. This creates a geological feedback loop — desert zones accumulate stone over time.
- **Biome reversion and spreading**: cells foreign to the current biome (e.g., GRASS in a DESERT) revert to the biome's base cell at a rate proportional to how many native-biome neighbors surround them. Three native neighbors = fast revert (cell is stranded); one or zero = slow revert (cell is at a real boundary). Native cells spread to adjacent non-native cells at a low rate, so biomes gradually reclaim territory.

### Distance-based decay factor
`_decay_factor = 1.0 + distance * 0.02` — cells in distant zones decay slightly faster (+2% per zone away). Combined with the catch-up system, this means zones that were idle for a long time come back with visibly more weathered terrain.

### Per-zone rain
Each zone has its own independent weather cycle: a timer counts up to a threshold, then rain starts for a randomized duration. The current zone's rain state is synced to `self.is_raining` for the UI and sound system. Rain accelerates sand reversion in non-desert biomes (sand washes away) and enables `apply_rain` cell effects.

### Entity lifecycle
For each entity in the zone: age increment, `decay_stats` (hunger/thirst drain), NPC item consumption (consuming food items heals in combat recovery), skeleton daylight damage, healing boost near CAMP/HOUSE, health regen if not recently attacked, energy regen by activity state. Then `update_entity_ai`.

Extra `decay_stats` passes are applied for distant zones (`_extra_decay`) and overcrowded zones (`_pop_extra`), making survival harder for NPCs far from the player and in packed zones.

### Inventory overflow
When an entity's inventory stack exceeds 20 items: first tries to deposit into an adjacent existing chest (70% chance); if no chest is nearby, creates a new chest and transfers the overflow (60% chance, no-chest-within-5-cells guard).

### Entity consolidation
Every 300 ticks, if a zone has more than 2 living entities of the same base type, pairs are merged into `_double` variants. The merged entity gets 1.5x max health, absorbs the removed entity's health, and receives a 1.3x strength multiplier. The weaker entity is removed. This keeps zone populations manageable without a hard entity cap.

### Faction dynamics
Two faction events per update cycle:
1. **Warrior defection** (0.1% per warrior per update): a warrior changes faction if there are 3+ warriors and another faction exists.
2. **Zone revolution** (0.05% zone-wide): all warriors in the zone simultaneously switch to a new faction.
3. **Faction raid** (0.1% on high-pop zones with 3+ total faction warriors): 3 warrior raiders spawn at zone entrances, and one low-level NPC is killed to simulate a raid casualty.

### Population maintenance
Every 300 ticks: checks if TRADER, GUARD, and WARRIOR are represented in the zone. Missing types are spawned at zone entrances in priority order (TRADER first, then GUARD). NPC role conversion: if a zone is missing FARMER, LUMBERJACK, or MINER roles, traders and guards have a chance to be converted to fill those roles — this is how villages develop specialized populations organically over time.

---

## Section 9 — `update_structure_zone` (zones.py, line 986)

The same lifecycle as `update_zone_with_coverage` but stripped to what makes sense for interiors: cell growth/decay, entity age/stats/regen, AI updates. No biome reversion, no faction events, no raids. Healing multiplier is `HOUSE_HEALING_MULTIPLIER` for house interiors (peaceful NPCs inside houses heal faster). Overcrowding extra decay applies here too — caves with too many entities drain their stats faster.

---

## Section 10 — Catch-Up System (zones.py, line 1082)

### The problem
Zones that the player hasn't visited in a long time are updated at the lowest priority. When the player eventually returns to a zone, that zone's state might be hundreds of ticks stale — NPCs could be starving, cells would be wrong. The catch-up system advances these zones rapidly to approximate where they should be.

### `catch_up_screen`
Applies catch-up to a zone's cell grid:
- **Tier 1 (< 5 cycles missed)**: runs `apply_cellular_automata` normally, once per missed cycle.
- **Tier 2+ (many cycles missed)**: builds a neighbor count cache (expensive to do cell-by-cell each iteration), then applies bulk CA rules in a single pass with a probability scaled to `cycles_missed`. A cell surrounded by water becomes DEEP_WATER with probability `min(cycles * 0.05, 0.8)`, for example.

The tier split is a performance trade-off: for recently-visited zones, accuracy matters. For heavily stale zones, a single probabilistic pass is far cheaper than N serial CA passes and produces a plausible result.

### `catch_up_entities`
Fast-forward entity simulation. For zones with many missed cycles (> 20): a simplified raid simulation (20% chance to spawn hostiles and kill one NPC, simulating a raid that happened while the player was away); faction simulation (assign factions to warriors, simulate inter-faction casualties). For all zones: entity travel transitions (non-peaceful entities have a chance to move to an adjacent zone, spreading populations during catch-up); eat/drink/heal cycles.

### `on_zone_transition`
Called when the player enters a new zone. Queues the zone and its neighbors for catch-up based on how many ticks they missed. The `catchup_queue` is sorted by proximity so the player's immediate neighbors are caught up first.

---

## Section 11 — Priority Queue (zones.py, line 1447)

### `calculate_zone_priority`
Five components, all scaled as fractions of `total_zones` so the queue remains meaningful regardless of world size:

1. **Distance score**: current player zone = `total_zones * 1.0` (always first); falls off as `0.5 / distance` for other zones.
2. **Staleness**: `(tick - last_update) / 30.0` — uncapped, so every zone eventually climbs to the top.
3. **Connection score**: zones connected to the player zone get `0.4 * total_zones`; zones connected to a player-adjacent zone get `0.2 * total_zones`.
4. **Structure score**: structure zones (caves/houses) get `0.15 * total_zones`; overworld zones containing structures get `0.05 * total_zones`.
5. **Quest score**: zones that are active quest targets get `0.2 * total_zones`.

The staleness component is the most important for distant zones — it ensures that every zone eventually gets updated, even at reduced coverage. Without it, zones beyond update range would never advance at all.

---

## Section 12 — Biome Domains (zones.py, line 1639)

### What domains are
A domain is a named set of connected same-biome zones. When adjacent zones share the same biome and a connecting exit, they belong to the same domain and share a name — "Iron Ash Forest" covers 4 contiguous forest zones, for example. This is what makes the in-game map feel like contiguous regions rather than random isolated patches.

### `update_biome_domain`
Called when a zone's biome changes. The zone leaves its old domain (triggering a contiguity check if the domain splits) and joins or creates a domain among its same-biome exit-connected neighbors. When multiple neighboring domains exist, the largest surviving domain absorbs all the others — merge rather than fragment. Domainless same-biome neighbors are also pulled into the surviving domain.

### `_check_biome_domain_contiguity`
BFS over all zones in a domain. If a zone was removed and caused the domain to split into disconnected fragments, each fragment becomes its own domain. Fragments get directional name modifiers (North/South/East/West) based on their centroid positions to distinguish them.

### Why this matters
Biome domains are how the in-game zone name shown in the HUD reflects the region the player is in, not just the individual zone. "Ancient Ash Forest" persists as the player walks through three connected forest zones; if those zones are separated by a desert crossing, each cluster gets its own name.

---

## Section 13 — Zone Maintenance Helpers (zones.py, line 1551)

### `cleanup_screen_entities`
Walks every bucket in `screen_entities` and removes None entries and entity IDs that no longer exist in `self.entities`. Called every 600 ticks. This is the periodic repair for the desync class of bugs where entity IDs accumulate in zone buckets after removal.

### `ensure_nearby_zones_exist`
Generates all zones within a 4×4 area around the player. Called every update cycle. This guarantees zone crossing never fails because the destination zone doesn't exist yet — the player can always step into any adjacent zone.

### `check_zone_biome_shift`
Counts cell types across the zone grid and updates the `biome` label if the dominant cell type no longer matches. A forest zone that has been deforested (trees chopped down, converted to DIRT) may shift to PLAINS biome. This is what drives `update_biome_domain` in response to NPC activity rather than just world generation.

---

## Notes for Contributors

**`set_grid_cell` is mandatory:** Never write `screen['grid'][y][x] = cell_type` directly. Always use `self.set_grid_cell(screen, x, y, cell_type)` so the variant grid stays in sync.

**Virtual zone keys:** Structure zones have `x <= -1000`. `is_overworld_zone` checks `x > -500`. The two ranges don't overlap, so a simple integer comparison is sufficient.

**Zone generation is idempotent:** `generate_screen` returns early if the key already exists. Call it freely from any code path that needs to ensure a zone exists — it won't regenerate a zone that's already been visited.

**The priority queue doesn't guarantee updates:** Zones beyond `MAX_ZONES_PER_UPDATE` in the queue may not be updated in a given cycle. The staleness score ensures they'll climb the queue in future cycles. This is expected behavior, not a bug.

**Biome domains are best-effort:** They're cosmetic (naming) plus one gameplay use (zone name in HUD). If the domain system gets confused or produces wrong names, it's a minor display issue, not a correctness problem.
