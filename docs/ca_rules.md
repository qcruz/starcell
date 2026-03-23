# StarCell — Cellular Automata Rules Reference

## Three Cell-Mutation Systems

Cell changes in StarCell come from **three independent systems**. All three must be considered
when debugging unexpected terrain changes. The CA rate hierarchy only governs System 1.

| System | Function | Frequency | File |
|---|---|---|---|
| **1 — Cellular Automata** | `apply_cellular_automata` | Every `UPDATE_FREQUENCY` ticks, probabilistic per-cell | `world/cells.py` |
| **2 — Zone Update** | `update_zone_cells` | Every `UPDATE_FREQUENCY` ticks, deterministic + probabilistic per-cell | `world/zones.py` |
| **3 — Rain Spawn** | `apply_rain` | Once per zone per rain tick (not every update) | `world/cells.py` |

Zone Update (System 2) runs immediately after CA each cycle. It contains biome reversion,
CELL_TYPES lifecycle chains, desert formation, and native-cell spreading — **none of which use
the CA rate hierarchy**. Bug source for DIRT→SAND in desert was here, not in CA.

---

## Rate Hierarchy

All CA probabilities derive from a two-level hierarchy:

```
CA_BASE_RATE = 0.001       # master knob — change this to speed/slow the entire system

CA_GROWTH_RATE     = 0.1  × CA_BASE_RATE   (0.0001)
CA_DECAY_RATE      = 0.1  × CA_BASE_RATE   (0.0001)  ← tune slightly above CA_GROWTH_RATE for natural long-term drift
CA_SPREAD_RATE     = 2    × CA_BASE_RATE   (0.002)
CA_WATER_EVAP_RATE = 8    × CA_BASE_RATE   (0.008)
```

**CA_GROWTH_RATE** and **CA_DECAY_RATE** should be roughly equal. Set CA_DECAY_RATE slightly above
CA_GROWTH_RATE to create a natural tendency toward decay. Combined with the rain boost to `_growth`
in cells.py, this produces zones that green up during rain and slowly dry without it — reducing the
need for dedicated drought rules.

Active per-cycle modifiers applied inside `apply_cellular_automata`:
- `_growth` — `max(0.1, 1 − drought_severity × 0.9) × time_pass_speed`; 1.0 just after rain, 0.1 at max drought
- `_decay` — `(1 + drought_severity × 0.5) × time_pass_speed`; 1.0 just after rain, 1.5 at max drought
- `cell_coverage` — fraction of grid cells sampled this cycle (player zone: 50%, distant zones: lower)

---

## Tier 1 — Global Environmental Rules

Universal rules that apply the same way in every biome. Expressed as multiples of the class rates.
CA cycle fires every `UPDATE_FREQUENCY` ticks (default 30).

### Growth rules (× CA_GROWTH_RATE = 0.0001)

| Rule | Variable | Multiplier | Effective rate | Fires when |
|---|---|---|---|---|
| DIRT → GRASS | `DIRT_TO_GRASS_RATE` | 1× | 0.0001 × _growth | 2+ water/deep-water/cave-floor neighbors |
| DIRT → GRASS (marginal) | `DIRT_TO_GRASS_WATER_RATE` | 2× | 0.0002 × _growth | exactly 1 water neighbor, no sand neighbors |
| GRASS → TREE | `GRASS_TO_TREE_RATE` | 1× | 0.0001 × _growth | biome ≠ DESERT, no cobblestone, 1–2 tree neighbors, 1+ water neighbor |
| GRASS → FLOWER (spread) | `GRASS_TO_FLOWER_RATE` | 1× | 0.0001 × _growth | 1–2 flower neighbors, 1+ water neighbor |
| SAND → DIRT (stone weathering) | `SAND_TO_DIRT_STONE_RATE` | 2× | 0.0002 × _growth | 1+ cobblestone or stone neighbor |

### Decay rules (× CA_DECAY_RATE = 0.0001)

| Rule | Variable | Multiplier | Effective rate | Fires when |
|---|---|---|---|---|
| GRASS → DIRT | `GRASS_TO_DIRT_RATE` | 0.1× | 0.00001 × _decay | no water neighbors |
| DIRT → SAND (severe drought) | `DIRT_TO_SAND_DROUGHT_RATE` | 0.05× | 0.000005 × _decay | no water neighbors, no grass neighbors |
| DIRT → SAND (desert reclamation) | `DIRT_TO_SAND_DESERT_RATE` | 1× | 0.0001 × _decay | biome = DESERT, no water neighbors |
| TREE → GRASS (crowding) | `TREE_TO_GRASS_CROWD_RATE` | 10× | 0.001 × _decay | 1+ adjacent tree (no cobblestone) |
| TREE → GRASS (road edge) | `TREE_TO_GRASS_CROWD_RATE` | 10× | 0.001 × _decay | 1+ cobblestone neighbor |
| TREE → GRASS (drought) | `TREE_TO_GRASS_DROUGHT_RATE` | 3× | 0.0003 × _decay | drought_severity > 0.5, no water neighbors |
| CACTUS → SAND (drought) | `CACTUS_TO_SAND_DROUGHT_RATE` | 3× | 0.0003 × _decay | drought_severity > 0.5, no water neighbors |
| FLOWER → GRASS (overcrowding) | `FLOWER_TO_GRASS_RATE` | 5× | 0.0005 × _decay | 4+ flower neighbors OR no water neighbors |
| BUSH → GRASS | inline | 3× | 0.0003 × _decay | no cardinal water neighbors |
| FLOWER_PATTERN → base cell (wet) | inline | 3× | 0.0003 × _decay | FLOWER_PATTERN cell with water adjacent |
| FLOWER_PATTERN → base cell (dry) | inline | 40× | 0.004 × _decay | FLOWER_PATTERN cell without water |
| BLUE_MUSHROOM → CAVE_FLOOR | inline | 2× | 0.0002 × _decay | 5+ adjacent BLUE_MUSHROOM (overcrowding) |

*Note: TREE_TO_GRASS_DROUGHT_RATE and CACTUS_TO_SAND_DROUGHT_RATE are candidates for removal once CA_DECAY_RATE is
tuned slightly above CA_GROWTH_RATE — the drought `_decay` modifier already accelerates all decay
rules during dry periods. Left in for now as a safety net.*

### Water dynamics (× CA_WATER_EVAP_RATE = 0.008)

| Rule | Variable | Multiplier | Effective rate | Fires when |
|---|---|---|---|---|
| WATER → biome base (isolated) | `WATER_TO_BASE_ISOLATED_RATE` | 2× CA_BASE_RATE | 0.002 × _decay × stone-shield | ≤1 water neighbor; biome ≠ LAKE |
| WATER → biome base (volume) | inline | (count−4)× CA_BASE_RATE | scales with pool size | zone water count > 4 |
| DEEP_WATER → CAVE_FLOOR/WATER | `DEEP_WATER_TO_WATER_RATE` | 0.5× | 0.004 × _decay | < 4 cardinal water neighbors; biome ≠ LAKE |
| WATER → DEEP_WATER | `WATER_TO_DEEP_WATER_RATE` | 2.5× | 0.02 × _tp | all 4 cardinal neighbors are water/deep/cave_floor |
| SAND → DIRT (near water) | `SAND_TO_DIRT_WATER_RATE` | 10× | 0.08 × _growth | 1+ water/deep-water/cave-floor neighbor |
| DIRT/SAND → WATER (rain flood) | `DIRT_TO_WATER_RAIN_RATE` | 0.75× | 0.006 × _tp | raining, 3+ water neighbors |
| SAND → WATER (rain, faster) | inline | 1.5× DIRT_TO_WATER_RAIN_RATE | 0.012 × _tp | raining, 3+ water neighbors |
| GRASS → WATER (rain absorption) | `GRASS_TO_WATER_RAIN_RATE` | 1× | 0.008 × _tp | raining, 1+ water neighbor |
| Rain flood spread (secondary) | inline | 0.4× DIRT_TO_WATER_RAIN_RATE | 0.0024 × _tp | raining, DIRT/SAND/COBBLESTONE with 1+ water neighbor, cell unchanged |
| DIRT → FLOWER_PATTERN (water edge) | `DIRT_TO_FLOWER_WATER_RATE` | 0.4× | 0.0032 × _growth | 1+ water neighbor AND 1+ non-dirt/non-water neighbor |

*Stone/cobblestone neighbors reduce water evaporation rate (each stone cardinal: ×0.8, min 0.1)
— natural grotto walls protect small pools.*

*WATER volume-based decay: pools of ≤4 cells have rate 0 (fully stable). Each cell above 4 adds
1× CA_BASE_RATE to the rate. Large bodies drain proportionally.*

*WATER evaporation: 20% chance to leave CAVE_FLOOR as dried lake bed instead of biome base cell.
DEEP_WATER evaporation: 80% chance to become CAVE_FLOOR, 20% to become regular WATER.*

### Spread (× CA_SPREAD_RATE = 0.002)

| Rule | Variable | Multiplier | Effective rate | Fires when |
|---|---|---|---|---|
| FLOWER_PATTERN natural growth | inline | 0.015× (non-desert) | 0.00003 × _growth | GRASS/DIRT/SAND/COBBLESTONE, cell unchanged this cycle |
| FLOWER_PATTERN natural growth | inline | 0.003× (desert) | 0.000006 × _growth | GRASS/DIRT/SAND/COBBLESTONE, cell unchanged, biome=DESERT |
| General terrain neighbor-copy | `TERRAIN_DIFFUSION_RATE` | 1× CA_GROWTH_RATE | 0.0001 × _tp | GRASS/DIRT/SAND/WATER, cell unchanged; picks random NSEW neighbor |
| Zone border biome seeding | `BIOME_BORDER_SPREAD_RATE` | 2× | 0.004 × _tp | Cells at zone exit edges copy adjacent zone's primary biome cell |

*General neighbor-copy: picks one random NSEW neighbor. If that neighbor is a different base
terrain type, cell copies it. Runs after all specific rules as a slow catch-all diffusion pass.
Uses TERRAIN_DIFFUSION_RATE (tied to CA_GROWTH_RATE, not CA_SPREAD_RATE) — 40× slower than before.*

---

## Tier 2 — Cross-Biome Rules

Fire because of adjacency between different biome-type cells, or produce formations that span
any biome. Not limited to a single biome.

### Desert edge interactions (× CA_SPREAD_RATE = 0.002)

| Rule | Variable | Multiplier | Effective rate | Fires when |
|---|---|---|---|---|
| GRASS → DIRT (sand erosion) | `GRASS_TO_DIRT_SAND_RATE` | 1.5× | 0.003 × _decay | 1+ sand neighbor (any biome) |
| DIRT → SAND (desert advance) | `DIRT_TO_SAND_SPREAD_RATE` | 2× | 0.004 × _decay | no water, 1+ sand neighbor, biome ≠ DESERT |

### Water formations (apply in any biome)

| Rule | Variable | Effective rate | Fires when |
|---|---|---|---|
| CAVE_FLOOR → WATER (overworld rain) | inline | 4× CA_WATER_EVAP_RATE × _tp | raining, overworld CAVE_FLOOR |
| CAVE_FLOOR → biome base (overworld dry) | inline | 5× CA_WATER_EVAP_RATE × _decay | not raining, no water neighbors, overworld CAVE_FLOOR |

*CAVE_FLOOR inside actual cave structures never decays — the rule only fires when the cell has a
biome context (i.e., it's exposed on the overworld as a dried lake bed).*

### Cave formations (any biome's caves)

| Rule | Variable | Multiplier | Effective rate | Fires when |
|---|---|---|---|---|
| CAVE_FLOOR → BLUE_MUSHROOM | inline | 0.8× CA_GROWTH_RATE | 0.00008 × _growth | cave zone, 1–2 adjacent BLUE_MUSHROOM |

*Blue mushroom growth only fires inside structure zones (where biome context is None).*

### Cobblestone path (NPC road-building interaction)

| Rule | Variable | Effective rate | Fires when |
|---|---|---|---|
| TREE → GRASS | `TREE_TO_GRASS_CROWD_RATE` | 10× CA_DECAY_RATE × _decay | 1+ cobblestone neighbor (road-edge clearance) |

*Edge trees adjacent to a cobblestone road are cleared over time. The embedded-road rule
(TREE → COBBLESTONE when 5+ neighbors cobblestone) has been removed — road clearance alone is sufficient.*

---

## Tier 3 — Biome-Specific Rules

Apply only inside a single biome. Override or supplement global rules.

### Desert biome

| Rule | Variable | Effective rate | Notes |
|---|---|---|---|
| SAND → WATER (rain flood) | inline | 2× DIRT_TO_WATER_RAIN_RATE = 0.012 × _tp | Sand absorbs rain faster than dirt |
| TREE → SAND (sand neighbor) | inline | 150× CA_DECAY_RATE × _decay | Trees die rapidly at desert edges |
| WATER → SAND (evaporation) | `WATER_TO_BASE_ISOLATED_RATE` | 0.002 × _decay | biome base cell is SAND, not GRASS |
| FLOWER_PATTERN growth | inline | 0.003× CA_GROWTH_RATE | 1/5 the rate of other biomes |
| Tree growth | n/a | Never fires | Blocked by `biome != 'DESERT'` guard in tree spread rule |
| DIRT → SAND (reclamation) | `DIRT_TO_SAND_DESERT_RATE` | 0.0001 × _decay | desert biome, no water neighbors — slow background pressure |

### LAKE biome

| Rule | Effect |
|---|---|
| DEEP_WATER evaporation | Disabled — deep water never evaporates in LAKE biome |
| WATER volume decay | Disabled — no biome base target defined for LAKE |

---

## Constructed Cell Decay

Placed or dropped cells that decay quickly to clean up abandoned structures.
Expressed as multiples of CA_BASE_RATE × _tp (no drought modifier — pure time-based).

| Cell | Variable | Rate | Effective | Target |
|---|---|---|---|---|
| EMPTY_CRATE | inline | 80× CA_BASE_RATE | 0.08 | biome base cell |
| WOOD (outdoor) | inline | 50× CA_BASE_RATE | 0.05 | DIRT |
| PLANKS (outdoor) | inline | 30× CA_BASE_RATE | 0.03 | DIRT |
| BONES | inline | 20× CA_BASE_RATE | 0.02 | biome base cell |

*WOOD and PLANKS only decay when not adjacent to a structure — placed walls and floors inside
houses are protected.*

---

## Agricultural Rules

Crop decay driven by time since last rain. CARROT1/2/3 only.

| Drought tier | Ticks since rain | Variable | Rate | Effective |
|---|---|---|---|---|
| Normal | < 1200 (~20 sec) | `CA_DECAY_RATE` | 0.1× | 0.00001 |
| Moderate | 1200–3600 | `CA_DECAY_RATE` | 1× | 0.0001 |
| Severe | > 3600 (~1 min) | `CA_DECAY_RATE` | 10× | 0.001 |

Rate is doubled if no FARMER entity is present in the zone.

---

## Drought System

Computed per zone each CA cycle:

```
drought_ticks    = tick − zone_last_rain[key]
drought_severity = min(drought_ticks / 9000, 1.0)     # 0.0 = just rained, 1.0 = ~2.5 min dry

_growth = max(0.1, 1.0 − drought_severity × 0.9) × time_pass_speed   # 1.0 → 0.10
_decay  = (1.0 + drought_severity × 0.5) × time_pass_speed            # 1.0 → 1.50
```

At max drought: growth slows to 10% of base, decay rises to 150% of base.
The gap between `_growth` and `_decay` at max drought is 15× — zones naturally dry
without needing explicit drought-specific rules for most cell types.

---

## Zone Border Seeding (deterministic)

Cells at zone exit edges (top/bottom/left/right boundary row) are set each CA cycle to the
adjacent zone's primary biome cell — no probability involved, always overwrites:

| Adjacent biome | Seeded cell |
|---|---|
| FOREST, PLAINS | GRASS |
| DESERT | SAND |
| LAKE | WATER |
| MOUNTAINS, TUNDRA, SWAMP | (no override — cell follows normal rules) |

This ensures clean visual transitions at zone borders.

---

## NPC-Driven Cell Changes

Cell mutations triggered by entity actions, not the CA clock. These fire during entity updates,
not every CA cycle, so their effective rate depends on entity density and AI tick frequency.

### Footstep erosion (all NPCs walking)

| Rule | Variable | Probability | Fires when |
|---|---|---|---|
| GRASS → DIRT (trampling) | inline | 0.5% per step | Any NPC steps onto a GRASS cell |
| GRASS → DIRT (path-building) | `TRADER_PATH_BUILD_RATE` | 60% per step | Trader/guard/miner steps onto GRASS near center axis |
| DIRT → COBBLESTONE | `TRADER_COBBLE_RATE` | 35% per step | Trader/guard on DIRT, within ±1 cell of zone center axis |

*All NPCs have a small (0.5%) chance to wear grass to dirt as they walk — high-traffic areas
brown naturally over time. Traders, guards, and miners additionally apply the full 60% path-build
rate when near the center road corridor, and can upgrade dirt to cobblestone.*

### Termites

| Rule | Variable | Probability | Fires when |
|---|---|---|---|
| TREE1/TREE2 → DIRT | inline | 15% per action | Termite attacks an adjacent tree cell |
| CAMP → GRASS | inline | 8% per action | Termite attacks a camp structure |

*Termites leave dirt when they destroy trees. They also have a separate death drop that sometimes
leaves SAND (handled by entity death loot, not CA).*

### Animal grazing

| Rule | Variable | Probability | Fires when |
|---|---|---|---|
| GRASS → DIRT | `GRASS_DECAY_ON_EAT` | 60% per eat | Herbivore (DEER, SHEEP, CHICKEN, etc.) eats a GRASS cell |
| CARROT → DIRT | `GRASS_DECAY_ON_EAT` | 60% per eat | Any entity eats a CARROT cell (or SOIL on 40% miss) |

*Animals grazing on GRASS have a 60% chance to convert it to DIRT. Heavily grazed zones slowly
brown without rain to re-green them.*

### Dropped bones / debris

| Rule | Variable | Rate | Target |
|---|---|---|---|
| BONES → DIRT (forest/plains/mountains) | inline | 20× CA_BASE_RATE × _tp | BONES cell, biome ≠ DESERT |
| BONES → SAND (desert) | inline | 20× CA_BASE_RATE × _tp | BONES cell, biome = DESERT |

*Bones are placed when entities die and are not picked up. They decay to biome base terrain over
time — equivalent to roughly half the lifespan of a WOOD cell.*

---

## Zone Update System (`update_zone_cells`)

**System 2** — runs in `world/zones.py` immediately after `apply_cellular_automata` each update
cycle. Does **not** use the CA rate hierarchy. Probabilities are hard-coded or come from
`CELL_TYPES` data directly. `_tp` (time_pass_speed) still applies where shown.

### CELL_TYPES lifecycle chains

Cells with `grows_to` or `degrades_to` in `data/cells.py` advance each update cycle at
`cell_info['growth_rate'] * _tp` or `cell_info['degrade_rate'] * _tp * _decay_factor`.

| From | To | Rate | Notes |
|---|---|---|---|
| GRASS | TREE1 | 0.05% | grows_to |
| DIRT | GRASS | 0.3% | grows_to |
| DEEP_WATER | WATER | 0.1% | degrades_to |
| CARROT1 | CARROT2 | 2% | grows_to |
| CARROT2 | CARROT3 | 1.5% | grows_to |
| CARROT1/2 | GRASS | 0.01% | degrades_to (very slow) |
| CARROT3 | GRASS | 0.005% | degrades_to (very slow) |
| COBBLESTONE | DIRT | 0.001% | degrades_to; protected on center road ±2 cells and near HOUSE/CAMP/CAVE/MINESHAFT |
| HOUSE | STONE_HOUSE | 0.002% | grows_to; triggers `process_house_destruction` on old cell |
| HIDDEN_CAVE | CAVE | 0.5% | degrades_to |
| CAMP | HOUSE | 0.1% | grows_to |
| FLOWER | GRASS | 0.01% | degrades_to |
| FLOWER_PATTERN1/2/3 | GRASS | 0.015% | degrades_to |
| GRAVESTONE | BROKEN_GRAVESTONE | 0.0005% | degrades_to |
| RUINED_SANDSTONE_COLUMN | SAND | 0.002% | degrades_to |
| WELL (desert) | DESERT_WELL | 0.002% | inline check, not CELL_TYPES |

### Excess cave decay

CAVE → biome base cell at 1% per update when zone cave count > 2. Prevents cave overgrowth
from repeated raid spawns.

### Chest and crate lifecycle

- **CHEST** → saved background cell (or biome base) when chest_contents is empty
- **EMPTY_CRATE** → CHEST when chest_contents gains items

Neither uses a probability — both fire deterministically each update when the condition is met.

### Stray interior cell reversion

WOOD / PLANKS / FLOOR_WOOD found in the overworld → biome base cell at **10% per update**.
Interior cells placed inside structures are only affected if they end up in an unprotected grid cell.

### Desert formation

Runs only in DESERT biome, each update cycle.

| Rule | Constant | Rate | Notes |
|---|---|---|---|
| SAND → STONE | `DESERT_ROCK_FORMATION_RATE` | 0.008% × _tp | Sand slowly solidifies |
| STONE → IRON_ORE | `DESERT_ORE_FORMATION_RATE` | 0.002% × _tp | Existing stone rarely yields ore |

### Biome reversion (foreign cell purge)

Foreign cells surrounded by native cells are reverted to the biome base. Rate scales with how
many cardinal neighbors are native to the current biome.

| Native cardinal neighbors | Revert rate per update |
|---|---|
| 3+ | 12% |
| 2 | 3.5% |
| 0–1 | 0.3% |

SAND in non-desert biomes gets an additional boost during rain: rate raised to at least 8%.

**Foreign cell definitions per biome** (all others are left alone or handled by CA):

| Biome | Foreign cells | Reverts to |
|---|---|---|
| DESERT | GRASS, TREE1, TREE2, FLOWER | SAND |
| FOREST | SAND | GRASS |
| PLAINS | SAND | GRASS |
| MOUNTAINS | SAND | DIRT |
| TUNDRA | SAND, GRASS | DIRT |
| SWAMP | SAND | DIRT |

*Desert trees have a separate faster path: TREE1/TREE2 → SAND at 8% per update regardless of
neighbor count, handled before the foreign_revert check.*

*DIRT was previously incorrectly listed as foreign in DESERT, causing any newly-created DIRT
(e.g. from sand_to_dirt_water CA) to be reverted to SAND at up to 12% per update. This was the
root cause of the DIRT→SAND flickering bug. Fixed by removing DIRT from foreign_revert['DESERT'].*

### Native cell biome spreading

Every cell that is in `biome_native` for the current biome has a **0.5% chance per update** to
spread a copy of itself to one random cardinal neighbor, if that neighbor is not in
`protected_cells` and not already a native cell.

This is separate from `TERRAIN_DIFFUSION_RATE` in the CA system. Both run each cycle.

**Protected cells** (immune to native spreading): HOUSE, CAVE, MINESHAFT, CAMP, CHEST,
EMPTY_CRATE, WALL, COBBLESTONE, WATER, DEEP_WATER, CAVE_FLOOR, CAVE_WALL, STAIRS_UP,
STAIRS_DOWN, HIDDEN_CAVE, SOIL, CARROT1/2/3, CLIFF, STONE_HOUSE, BUSH, GRAVESTONE,
BROKEN_GRAVESTONE, LOCKED_CHEST, OPEN_CHEST, BOOKSHELF, WOOD_CHAIR, WOOD_TABLE, BED_WHITE,
WATER_TROUGH, SMALL_POTTED_PLANT, BLUE_MUSHROOM, APPLE_CRATE.

### Bush growth

| Rule | Rate | Biomes |
|---|---|---|
| GRASS → BUSH | 0.0005% × _tp | FOREST, PLAINS, SWAMP |
| SAND → BUSH | 0.00008% × _tp | DESERT only |

### Flower pattern growth (forest/plains)

GRASS → FLOWER_PATTERN1/2/3 at **0.0008% × _tp** in FOREST and PLAINS biomes only. Separate
from the CA `GRASS_TO_FLOWER_RATE` rule — both run per cycle, stacking the effective rate.

---

## Rain Spawn (`apply_rain`)

**System 3** — called once per zone per rain tick from `update_zone_cells`. Separate from the
CA cycle. Fires only when the zone's per-zone rain state is active.

### Desert

22% chance per tick to attempt 1–2 SAND→WATER conversions at random positions:
- SAND adjacent to existing water: **75%** success
- Isolated SAND: **40%** success

### Non-desert

Attempts are scaled by biome multiplier (Mountains: ×0.6 water / ×0.3 grass; Plains: ×1.2 / ×1.2).

| Rule | Attempts per tick | Per-attempt rate | Setting |
|---|---|---|---|
| DIRT → WATER | `RAIN_WATER_SPAWNS` (default 5) × biome mult | 30% | overworld rain puddles |
| DIRT → GRASS | `RAIN_GRASS_SPAWNS` (default 8) × biome mult | 40% | rain greening |

*These are random-position scatter conversions — cells are chosen uniformly at random from
the interior grid, not by adjacency rules. High water counts from rain are therefore spread
across the zone rather than pooling from existing water bodies.*

*Both desert and non-desert rain also restore full thirst for all living outdoor entities in
the zone.*
