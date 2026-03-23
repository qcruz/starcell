# StarCell — Cellular Automata Rules Reference

All probabilities are per-cell per CA cycle (every `UPDATE_FREQUENCY` ticks, default 30).
Every rate is expressed as `N × CA_BASE_RATE` where `CA_BASE_RATE = 0.001`.
To speed or slow the whole system, change `CA_BASE_RATE` in `constants.py`.

**Active modifiers applied to most rules:**
- `_growth` — scaled by drought severity (1.0 → 0.1 at max drought). Applied to growth/reclaim rules.
- `_decay` — scaled by drought severity (1.0 → 1.5 at max drought). Applied to decay/spread rules.
- `_tp` — `time_pass_speed` multiplier (1.0 during normal play, higher during time-skip).
- Cell coverage — player zone: 50% of cells checked per cycle. Distant zones: lower fraction.

---

## Rain & Flooding

### DIRT → WATER (rain flood)
- **Rate:** `15 × CA_BASE_RATE` (0.015) × `_tp`
- **Fires when:** raining, 3+ water/deep-water/cave-floor neighbors
- **Notes:** Highest priority rule for dirt — checked before any other dirt rule.

### SAND → WATER (rain flood)
- **Rate:** `30 × CA_BASE_RATE` (0.03) × `_tp`  *(2× dirt rate — sand absorbs faster)*
- **Fires when:** raining, 3+ water/deep-water/cave-floor neighbors

### GRASS → WATER (rain absorption)
- **Rate:** `20 × CA_BASE_RATE` (0.02) × `_tp`
- **Fires when:** raining, 1+ water neighbor

### Rain flood spread (secondary pass)
- **Rate:** `6 × CA_BASE_RATE` (0.006) × `_tp`  *(FLOODING_RATE × 0.4)*
- **Fires when:** raining, cell is DIRT/SAND/COBBLESTONE, 1+ water neighbor, cell unchanged this cycle
- **Notes:** Independent of the main elif chain — a second chance at flooding the same tick.

### CAVE_FLOOR → WATER (overworld, rain)
- **Rate:** `80 × CA_BASE_RATE` (0.08) × `_tp`
- **Fires when:** raining, cell is overworld CAVE_FLOOR (biome is not None)

### CAVE_FLOOR → biome base cell (overworld, dry)
- **Rate:** `100 × CA_BASE_RATE` (0.10) × `_decay`
- **Fires when:** not raining, no water neighbors, overworld CAVE_FLOOR
- **Notes:** CAVE_FLOOR inside actual caves never decays — rule only fires if biome is set.

---

## Water Dynamics

### WATER → DEEP_WATER (deepening)
- **Rate:** `50 × CA_BASE_RATE` (0.05) × `_tp`
- **Fires when:** all 4 cardinal neighbors are WATER/DEEP_WATER/CAVE_FLOOR

### WATER → biome base cell (isolated evaporation)
- **Rate:** `20 × CA_BASE_RATE` (0.02) × `_decay` × stone-shield
- **Fires when:** 1 or fewer water neighbors; biome is not LAKE
- **Notes:** 20% chance to leave CAVE_FLOOR as a dried lake bed instead of the biome base cell.
  Stone/cobblestone neighbors reduce rate (each stone cardinal: ×0.8, min 0.1 — natural grotto walls).

### WATER → biome base cell (volume decay)
- **Rate:** `(zone_water_count − 4) × CA_BASE_RATE` × `_decay` × stone-shield
- **Fires when:** zone has >4 WATER cells; biome target is defined (not LAKE); cell unchanged by above rules
- **Notes:** Small pools (≤4 cells) are rate=0 and fully stable. Larger bodies drain proportionally.
  15% chance to leave CAVE_FLOOR instead of the base cell.

### DEEP_WATER → CAVE_FLOOR/WATER (evaporation)
- **Rate:** `10 × CA_BASE_RATE` (0.01) × `_decay`
- **Fires when:** fewer than 4 cardinal water neighbors; biome is not LAKE
- **Notes:** 80% chance to become CAVE_FLOOR, 20% to become regular WATER.

---

## Dirt Transitions

### DIRT → GRASS (with water)
- **Rate:** `0.1 × CA_BASE_RATE` (0.0001) × `_growth`
- **Fires when:** 2+ water/deep-water/cave-floor neighbors

### DIRT → GRASS (marginal water)
- **Rate:** `0.2 × CA_BASE_RATE` (0.0002) × `_growth`
- **Fires when:** exactly 1 water neighbor, no sand neighbors

### DIRT → FLOWER_PATTERN (water boundary)
- **Rate:** `8 × CA_BASE_RATE` (0.008) × `_growth`
- **Fires when:** 1+ water neighbor AND 1+ non-dirt/non-water neighbor
- **Notes:** Produces decorative flower-pattern cells at water's edge (natural grottos).

### DIRT → SAND (desertification — sand neighbor)
- **Rate:** `8 × CA_BASE_RATE` (0.008) × `_decay`
- **Fires when:** no water neighbors, 1+ sand neighbor
- **Notes:** Intentionally overpowers BIOME_SPREAD_RATE so desert edges advance consistently.

### DIRT → SAND (severe drought)
- **Rate:** `0.005 × CA_BASE_RATE` (0.000005) × `_decay`
- **Fires when:** no water neighbors, no grass neighbors

---

## Grass Transitions

### GRASS → DIRT (drought)
- **Rate:** `0.01 × CA_BASE_RATE` (0.00001) × `_decay`
- **Fires when:** no water neighbors

### GRASS → DIRT (desertification edge)
- **Rate:** `3 × CA_BASE_RATE` (0.003) × `_decay`
- **Fires when:** 1+ sand neighbor

### GRASS → TREE (growth)
- **Rate:** `0.1 × CA_BASE_RATE` (0.0001) × `_growth`
- **Fires when:** biome is not DESERT, no cobblestone neighbors, 1–2 tree neighbors, 1+ water neighbor

---

## Sand Transitions

### SAND → DIRT (near water)
- **Rate:** `50 × CA_BASE_RATE` (0.05) × `_growth`
- **Fires when:** 1+ water/deep-water/cave-floor neighbor

### SAND → DIRT (near grass)
- **Rate:** `2.5 × CA_BASE_RATE` (0.0025) × `_growth`  *(SAND_RECLAIM_RATE × 0.05)*
- **Fires when:** 1+ grass neighbor, no water neighbors

### SAND → DIRT (near stone/cobblestone)
- **Rate:** `0.2 × CA_BASE_RATE` (0.0002) × `_growth`
- **Fires when:** 1+ cobblestone or stone neighbor

---

## Tree Transitions

### TREE → COBBLESTONE (embedded in road)
- **Rate:** `0.5 × CA_BASE_RATE` (0.0005) × `_decay`
- **Fires when:** 5+ cobblestone neighbors

### TREE → GRASS (road edge clearance)
- **Rate:** `1 × CA_BASE_RATE` (0.001) × `_decay`
- **Fires when:** 1+ cobblestone neighbor (but < 5)

### TREE → GRASS (crowding)
- **Rate:** `1 × CA_BASE_RATE` (0.001) × `_decay`
- **Fires when:** 1+ adjacent tree (no cobblestone)
- **Notes:** Produces natural checkerboard spacing; isolated trees survive.

### TREE → SAND (desert exposure)
- **Rate:** `150 × CA_BASE_RATE` (0.15) × `_decay`
- **Fires when:** 1+ sand neighbor

### TREE → GRASS (drought)
- **Rate:** `0.3 × CA_BASE_RATE` (0.0003) × `_decay`
- **Fires when:** drought_severity > 0.5, no water neighbors

### CACTUS → SAND (drought)
- **Rate:** `0.3 × CA_BASE_RATE` (0.0003) × `_decay`
- **Fires when:** drought_severity > 0.5, no water neighbors

---

## Flowers & Vegetation

### GRASS → FLOWER (spread)
- **Rate:** `0.1 × CA_BASE_RATE` (0.0001) × `_growth`
- **Fires when:** 1–2 flower neighbors, 1+ water neighbor

### FLOWER → GRASS (overcrowding or drought)
- **Rate:** `0.5 × CA_BASE_RATE` (0.0005) × `_decay`
- **Fires when:** 4+ flower neighbors OR no water neighbors

### FLOWER_PATTERN decay → biome base cell
- **Rate (near water):** `0.3 × CA_BASE_RATE` (0.0003) × `_decay`
- **Rate (no water):** `4 × CA_BASE_RATE` (0.004) × `_decay`
- **Fires when:** cell is FLOWER_PATTERN1/2/3

### FLOWER_PATTERN natural growth
- **Rate (desert):** `0.003 × CA_BASE_RATE` (0.000003) × `_growth`
- **Rate (other biomes):** `0.015 × CA_BASE_RATE` (0.000015) × `_growth`
- **Fires when:** cell is GRASS/DIRT/SAND/COBBLESTONE and unchanged this cycle

### BUSH → GRASS (decay without water)
- **Rate:** `3 × CA_BASE_RATE` (0.003) × `_decay`
- **Fires when:** no cardinal water neighbors

---

## Cave Cells

### CAVE_FLOOR → BLUE_MUSHROOM (cluster growth, underground only)
- **Rate:** `0.8 × CA_BASE_RATE` (0.0008) × `_growth`
- **Fires when:** cave structure (biome is None), 1–2 adjacent BLUE_MUSHROOM cells

### BLUE_MUSHROOM → CAVE_FLOOR (overcrowding)
- **Rate:** `2 × CA_BASE_RATE` (0.002) × `_decay`
- **Fires when:** 5+ adjacent BLUE_MUSHROOM cells

---

## Placed / Constructed Cells

### EMPTY_CRATE → biome base cell (decay)
- **Rate:** `80 × CA_BASE_RATE` (0.08) × `_tp`
- **Fires when:** always

### WOOD → DIRT (outdoor decay)
- **Rate:** `50 × CA_BASE_RATE` (0.05) × `_tp`
- **Fires when:** not near a structure

### PLANKS → DIRT (outdoor decay)
- **Rate:** `30 × CA_BASE_RATE` (0.03) × `_tp`
- **Fires when:** not near a structure

---

## Crop Decay

### CARROT → DIRT (drought decay)
- **Rate (recently rained, <1200 ticks):** `0.1 × CA_BASE_RATE` (0.0001) × `_tp`
- **Rate (moderate drought, 1200–3600 ticks):** `1 × CA_BASE_RATE` (0.001) × `_tp`
- **Rate (severe drought, >3600 ticks):** `10 × CA_BASE_RATE` (0.01) × `_tp`
- **Notes:** Doubled if no FARMER entity is present in the zone.

---

## General Biome Spread

### Base terrain neighbor-copy
- **Rate:** `4 × CA_BASE_RATE` (0.004) × `_tp`
- **Fires when:** cell is GRASS/DIRT/SAND/WATER, unchanged this cycle; picks one random NSEW neighbor;
  if neighbor is a different base terrain type, cell copies it.
- **Notes:** Runs after all specific rules as a catch-all diffusion pass.

---

## Zone Border Seeding

Cells at zone exit edges (top/bottom/left/right row) are deterministically set to the
adjacent zone's primary biome cell (GRASS for FOREST/PLAINS, SAND for DESERT, WATER for LAKE)
each CA cycle — no probability involved. This ensures smooth biome transitions at borders.

---

## Drought System

The drought modifier is computed per zone each CA cycle:

```
drought_ticks    = tick - zone_last_rain[zone_key]
drought_severity = min(drought_ticks / 9000, 1.0)   # 0.0 = just rained, 1.0 = 9000+ ticks dry
_growth = max(0.1, 1.0 - drought_severity × 0.9) × time_pass_speed   # 1.0 → 0.10
_decay  = (1.0 + drought_severity × 0.5) × time_pass_speed            # 1.0 → 1.50
```

Full drought severity is reached ~2.5 min without rain. At max drought: growth slows to 10%,
decay accelerates to 150% of base rates.
