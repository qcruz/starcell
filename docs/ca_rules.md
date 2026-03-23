# StarCell — Cellular Automata Rules Reference

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

| Rule | Multiplier | Effective rate | Fires when |
|---|---|---|---|
| DIRT → GRASS | 1× | 0.0001 × _growth | 2+ water/deep-water/cave-floor neighbors |
| DIRT → GRASS (marginal) | 2× | 0.0002 × _growth | exactly 1 water neighbor, no sand neighbors |
| GRASS → TREE | 1× | 0.0001 × _growth | biome ≠ DESERT, no cobblestone, 1–2 tree neighbors, 1+ water neighbor |
| GRASS → FLOWER (spread) | 1× | 0.0001 × _growth | 1–2 flower neighbors, 1+ water neighbor |
| SAND → DIRT (stone weathering) | 2× | 0.0002 × _growth | 1+ cobblestone or stone neighbor |

### Decay rules (× CA_DECAY_RATE = 0.0001)

| Rule | Multiplier | Effective rate | Fires when |
|---|---|---|---|
| GRASS → DIRT | 0.1× | 0.00001 × _decay | no water neighbors |
| DIRT → SAND (severe drought) | 0.05× | 0.000005 × _decay | no water neighbors, no grass neighbors |
| TREE → COBBLESTONE (embedded) | 5× | 0.0005 × _decay | 5+ cobblestone neighbors |
| TREE → GRASS (crowding) | 10× | 0.001 × _decay | 1+ adjacent tree (no cobblestone) |
| TREE → GRASS (road edge) | 10× | 0.001 × _decay | 1+ cobblestone neighbor (< 5) |
| TREE → GRASS (drought) | 3× | 0.0003 × _decay | drought_severity > 0.5, no water neighbors |
| CACTUS → SAND (drought) | 3× | 0.0003 × _decay | drought_severity > 0.5, no water neighbors |
| FLOWER → GRASS (overcrowding) | 5× | 0.0005 × _decay | 4+ flower neighbors OR no water neighbors |
| BUSH → GRASS | 3× | 0.0003 × _decay | no cardinal water neighbors |
| FLOWER_PATTERN → base cell | 3× near water | 0.0003 × _decay | FLOWER_PATTERN cell with water adjacent |
| FLOWER_PATTERN → base cell | 40× dry | 0.004 × _decay | FLOWER_PATTERN cell without water |
| BLUE_MUSHROOM → CAVE_FLOOR | 2× | 0.0002 × _decay | 5+ adjacent BLUE_MUSHROOM (overcrowding) |

*Note: TREE_DROUGHT_RATE and CACTUS_DROUGHT_RATE are candidates for removal once CA_DECAY_RATE is
tuned slightly above CA_GROWTH_RATE — the drought `_decay` modifier already accelerates all decay
rules during dry periods. Left in for now as a safety net.*

### Water dynamics (× CA_WATER_EVAP_RATE = 0.008)

| Rule | Multiplier | Effective rate | Fires when |
|---|---|---|---|
| WATER → biome base (isolated) | 2× CA_BASE_RATE | 0.002 × _decay × stone-shield | ≤1 water neighbor; biome ≠ LAKE |
| WATER → biome base (volume) | (count−4)× CA_BASE_RATE | scales with pool size | zone water count > 4 |
| DEEP_WATER → CAVE_FLOOR/WATER | 0.5× CA_WATER_EVAP_RATE | 0.004 × _decay | < 4 cardinal water neighbors; biome ≠ LAKE |
| WATER → DEEP_WATER | 2.5× CA_WATER_EVAP_RATE | 0.02 × _tp | all 4 cardinal neighbors are water/deep/cave_floor |
| SAND → DIRT (near water) | 2.5× CA_WATER_EVAP_RATE | 0.02 × _growth | 1+ water/deep-water/cave-floor neighbor |
| DIRT/SAND → WATER (rain flood) | 0.75× | 0.006 × _tp | raining, 3+ water neighbors |
| SAND → WATER (rain, faster) | 1.5× dirt rate | 0.012 × _tp | raining, 3+ water neighbors |
| GRASS → WATER (rain absorption) | 1× | 0.008 × _tp | raining, 1+ water neighbor |
| Rain flood spread (secondary) | 0.3× | 0.0024 × _tp | raining, DIRT/SAND/COBBLESTONE with 1+ water neighbor, cell unchanged |
| DIRT → FLOWER_PATTERN (water edge) | 0.4× | 0.0032 × _growth | 1+ water neighbor AND 1+ non-dirt/non-water neighbor |

*Stone/cobblestone neighbors reduce water evaporation rate (each stone cardinal: ×0.8, min 0.1)
— natural grotto walls protect small pools.*

*WATER volume-based decay: pools of ≤4 cells have rate 0 (fully stable). Each cell above 4 adds
1× CA_BASE_RATE to the rate. Large bodies drain proportionally.*

*WATER evaporation: 20% chance to leave CAVE_FLOOR as dried lake bed instead of biome base cell.
DEEP_WATER evaporation: 80% chance to become CAVE_FLOOR, 20% to become regular WATER.*

### Spread (× CA_SPREAD_RATE = 0.002)

| Rule | Multiplier | Effective rate | Fires when |
|---|---|---|---|
| FLOWER_PATTERN natural growth | 0.015× (non-desert) | 0.00003 × _growth | GRASS/DIRT/SAND/COBBLESTONE, cell unchanged this cycle |
| FLOWER_PATTERN natural growth | 0.003× (desert) | 0.000006 × _growth | GRASS/DIRT/SAND/COBBLESTONE, cell unchanged, biome=DESERT |
| General terrain neighbor-copy | 1× | 0.002 × _tp | GRASS/DIRT/SAND/WATER, cell unchanged; picks random NSEW neighbor |
| Zone border biome seeding | 2× | 0.004 × _tp | Cells at zone exit edges copy adjacent zone's primary biome cell |

*General neighbor-copy: picks one random NSEW neighbor. If that neighbor is a different base
terrain type, cell copies it. Runs after all specific rules as a catch-all diffusion pass.*

---

## Tier 2 — Cross-Biome Rules

Fire because of adjacency between different biome-type cells, or produce formations that span
any biome. Not limited to a single biome.

### Desert edge interactions (× CA_SPREAD_RATE = 0.002)

| Rule | Multiplier | Effective rate | Fires when |
|---|---|---|---|
| GRASS → DIRT (sand erosion) | 1.5× | 0.003 × _decay | 1+ sand neighbor (any biome) |
| DIRT → SAND (desert advance) | 2× CA_SPREAD_RATE | 0.004 × _decay | no water, 1+ sand neighbor |

*DIRT_SAND_SPREAD_RATE matches BIOME_SPREAD_RATE at 2× CA_SPREAD_RATE — desert edges advance
steadily without overwhelming dirt cells too quickly.*

### Water formations (apply in any biome)

| Rule | Effective rate | Fires when |
|---|---|---|
| CAVE_FLOOR → WATER (overworld rain) | 4× CA_WATER_EVAP_RATE × _tp | raining, overworld CAVE_FLOOR |
| CAVE_FLOOR → biome base (overworld dry) | 5× CA_WATER_EVAP_RATE × _decay | not raining, no water neighbors, overworld CAVE_FLOOR |

*CAVE_FLOOR inside actual cave structures never decays — the rule only fires when the cell has a
biome context (i.e., it's exposed on the overworld as a dried lake bed).*

### Cave formations (any biome's caves)

| Rule | Multiplier | Effective rate | Fires when |
|---|---|---|---|
| CAVE_FLOOR → BLUE_MUSHROOM | 0.8× CA_GROWTH_RATE | 0.00008 × _growth | cave zone, 1–2 adjacent BLUE_MUSHROOM |

*Blue mushroom growth only fires inside structure zones (where biome context is None).*

### Cobblestone path (NPC road-building interaction)

| Rule | Effective rate | Fires when |
|---|---|---|
| TREE → GRASS | 10× CA_DECAY_RATE × _decay | 1+ cobblestone neighbor (road-edge clearance) |

*Edge trees adjacent to a cobblestone road are cleared over time. The embedded-road rule
(TREE → COBBLESTONE when 5+ neighbors cobblestone) has been removed — road clearance alone is sufficient.*

---

## Tier 3 — Biome-Specific Rules

Apply only inside a single biome. Override or supplement global rules.

### Desert biome

| Rule | Effective rate | Notes |
|---|---|---|
| SAND → WATER (rain flood) | 2× FLOODING_RATE = 0.012 × _tp | Sand absorbs rain faster than dirt |
| TREE → SAND (sand neighbor) | 150× CA_DECAY_RATE × _decay | Trees die rapidly at desert edges |
| WATER → SAND (evaporation) | Same as WATER_TO_DIRT_RATE | biome base cell is SAND, not GRASS |
| FLOWER_PATTERN growth | 0.003× CA_GROWTH_RATE | 1/5 the rate of other biomes |
| Tree growth | Never fires | Blocked by `biome != 'DESERT'` guard in tree spread rule |

### LAKE biome

| Rule | Effect |
|---|---|
| DEEP_WATER evaporation | Disabled — deep water never evaporates in LAKE biome |
| WATER volume decay | Disabled — no biome base target defined for LAKE |

---

## Constructed Cell Decay

Placed or dropped cells that decay quickly to clean up abandoned structures.
Expressed as multiples of CA_BASE_RATE × _tp (no drought modifier — pure time-based).

| Cell | Rate | Effective | Target |
|---|---|---|---|
| EMPTY_CRATE | 80× CA_BASE_RATE | 0.08 | biome base cell |
| WOOD (outdoor) | 50× CA_BASE_RATE | 0.05 | DIRT |
| PLANKS (outdoor) | 30× CA_BASE_RATE | 0.03 | DIRT |

*WOOD and PLANKS only decay when not adjacent to a structure — placed walls and floors inside
houses are protected.*

---

## Agricultural Rules

Crop decay driven by time since last rain. CARROT1/2/3 only.

| Drought tier | Ticks since rain | Rate | Effective |
|---|---|---|---|
| Normal | < 1200 (~20 sec) | 0.1× CA_DECAY_RATE | 0.00001 |
| Moderate | 1200–3600 | 1× CA_DECAY_RATE | 0.0001 |
| Severe | > 3600 (~1 min) | 10× CA_DECAY_RATE | 0.001 |

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

| Rule | Probability | Fires when |
|---|---|---|
| GRASS → DIRT (trampling) | 0.5% per step | Any NPC steps onto a GRASS cell |
| GRASS → DIRT (path-building) | `TRADER_PATH_BUILD_RATE` (0.6) | Trader/guard/miner steps onto GRASS near center axis |
| DIRT → COBBLESTONE | `TRADER_COBBLE_RATE` (0.35) | Trader/guard on DIRT, within ±1 cell of zone center axis |

*All NPCs have a small (0.5%) chance to wear grass to dirt as they walk — high-traffic areas
brown naturally over time. Traders, guards, and miners additionally apply the full 60% path-build
rate when near the center road corridor, and can upgrade dirt to cobblestone.*

### Termites

| Rule | Probability | Fires when |
|---|---|---|
| TREE1/TREE2 → DIRT | 15% per action | Termite attacks an adjacent tree cell |
| CAMP → GRASS | 8% per action | Termite attacks a camp structure |

*Termites leave dirt when they destroy trees. They also have a separate death drop that sometimes
leaves SAND (handled by entity death loot, not CA).*

### Animal grazing

| Rule | Probability | Fires when |
|---|---|---|
| GRASS → DIRT | `GRASS_DECAY_ON_EAT` (0.6) | Herbivore (DEER, SHEEP, CHICKEN, etc.) eats a GRASS cell |
| CARROT → DIRT | `GRASS_DECAY_ON_EAT` (0.6) | Any entity eats a CARROT cell (or SOIL on 40% miss) |

*Animals grazing on GRASS have a 60% chance to convert it to DIRT. Heavily grazed zones slowly
brown without rain to re-green them.*

### Dropped bones / debris

| Rule | Rate | Target |
|---|---|---|
| BONES → DIRT (forest/plains) | 20× CA_BASE_RATE × _tp | BONES cell with biome FOREST/PLAINS/MOUNTAINS |
| BONES → SAND (desert) | 20× CA_BASE_RATE × _tp | BONES cell with biome DESERT |

*Bones are placed when entities die and are not picked up. They decay to biome base terrain over
time — equivalent to roughly half the lifespan of a WOOD cell.*
