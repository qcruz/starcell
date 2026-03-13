# StarCell — Biome Template

A reference for how biomes are structured, what they contain, and how they should behave. All biomes follow a common template. Future biomes should be designed against this template before implementation.

---

## Template

Every biome has the following layers:

| Layer | Description | Typical count |
|---|---|---|
| **Base cell** | Dominant terrain. Most of the zone. | 50–70% coverage |
| **Moderate cell** | Secondary terrain. Transitional or "worked" land. | 15–25% |
| **Low occurrence cells** | Terrain features with ecological or gameplay meaning. | 3–10% each |
| **Rare cells (resources)** | Harvestable or valuable cells. Infrequent. | 1–5% |
| **Structures** | Enterable or interactable objects placed on generation. | 0–3 per zone |
| **Depth / interior** | Sub-zones accessed through structures (caves, floors, etc.). | Varies |
| **Default spawns** | Entities that appear when the zone first generates. | Set per biome |
| **Specialty spawns** | Entities tied to structures, events, or biome-specific triggers. | Conditional |

---

## Cellular Automata Rules (all biomes)

All biomes participate in the same CA simulation. Rates differ but the logic mirrors across desert and lush biomes.

**Rain events:**
- Base cell → WATER puddles (sand at 2× dirt rate; grass at a lower absorption rate)
- Near water + raining: sand → dirt, grass → water
- Rain → lush: dirt → grass quickly around puddles

**Drought progression (no rain over time):**
- High growth (TREE/CACTUS) → moderate (GRASS/SAND) at drought severity > 0.5
- Moderate (GRASS) → base (DIRT) slowly
- Base (DIRT) → barren (SAND) on extended drought
- Barren (SAND) → stone/rock (long-term desert; handled by off-screen simulation)

**Desertification spread:**
- SAND neighbors pull GRASS → DIRT → SAND at the edges

---

## Current Biomes

### FOREST

| Layer | Cells |
|---|---|
| Base | GRASS |
| Moderate | DIRT |
| Low occurrence | TREE1, TREE2, FLOWER, WATER |
| Rare | — |

**CA behavior:** Trees spread on grass near water. Drought kills trees to grass, grass to dirt. Rain creates puddles; grass near water floods temporarily.

**Structures:** HOUSE (→ grows to STONE_HOUSE), CAVE, WELL, CHEST
**Depth / interior:** HOUSE_INTERIOR (single floor), CAVE (goes to cave sub-zone)

**Default spawns:** LUMBERJACK (high), TRADER, GUARD (always), FARMER, DEER, WOLF, SHEEP, GOBLIN, BANDIT, TERMITE, RED_BIRD, BUTTERFLY, BLACK_SPIDER
**Specialty spawns:** WIZARD (moderate chance on generation), BLACKSMITH (moderate chance); TERMITE prefers FOREST/PLAINS at 2× rate

---

### PLAINS

| Layer | Cells |
|---|---|
| Base | GRASS |
| Moderate | DIRT |
| Low occurrence | WATER, TREE1, CARROT1/2/3, FLOWER |
| Rare | — |

**CA behavior:** Grass dominant; trees rare. Crops decay without rain or farmer. Flowers spread near water.

**Structures:** HOUSE, WELL, CHEST, occasional FORGE
**Depth / interior:** HOUSE_INTERIOR

**Default spawns:** FARMER (high), SHEEP (high), TRADER, GUARD (always), CHICKEN, DEER, WOLF, BUTTERFLY, RED_BIRD, GOBLIN, BANDIT
**Specialty spawns:** None specific — highest farmer density of any biome

---

### DESERT

| Layer | Cells |
|---|---|
| Base | SAND |
| Moderate | DIRT |
| Low occurrence | STONE, WATER, CACTUS |
| Rare | IRON_ORE (from STONE via off-screen simulation) |

**CA behavior:** Sand floods to water during rain (2× dirt rate). Rain puddles sink to dirt (oasis pockets form). Cactus dies to sand on drought. Sand slowly hardens to stone over long dry periods (off-screen sim). Desertification pulls adjacent lush cells toward sand.

**Structures:** CAVE, WELL, MINESHAFT, RUINED_SANDSTONE_COLUMN, CHEST
**Depth / interior:** CAVE (cave sub-zone), MINESHAFT (shares CAVE interior type, deeper ore)

**Default spawns:** GOBLIN (high), BANDIT (moderate), MINER (moderate), TRADER, GUARD (always), BLACK_SPIDER, WOLF, SHEEP, DEER, FARMER (low)
**Specialty spawns:** MINER spawns near MINESHAFT; BLACKSMITH near FORGE; hostile density higher than lush biomes

---

### MOUNTAINS

| Layer | Cells |
|---|---|
| Base | DIRT |
| Moderate | STONE |
| Low occurrence | GRASS, TREE1, WATER |
| Rare | IRON_ORE |

**CA behavior:** Grass survives near water but is suppressed by stone. Trees thin quickly (high drought decay, sand/stone proximity). Dirt erodes to stone slowly.

**Structures:** CAVE, MINESHAFT, CHEST, occasional HOUSE
**Depth / interior:** CAVE (multi-depth; deeper = more IRON_ORE, higher mob density)

**Default spawns:** MINER (high), WOLF (high), GOBLIN (high), GUARD, TRADER (always), BANDIT, LUMBERJACK, BLACK_SPIDER, DEER, SHEEP, RED_BIRD
**Specialty spawns:** BLACKSMITH tied to FORGE presence; mine depth scales hostile spawn rate

---

### LAKE

| Layer | Cells |
|---|---|
| Base | WATER |
| Moderate | DEEP_WATER |
| Low occurrence | — |
| Rare | — |

**CA behavior:** Deep water forms where all 4 cardinal neighbors are water. Isolated water evaporates to dirt over time.

**Structures:** None currently
**Depth / interior:** None currently

**Default spawns:** None (lake zones generate empty)
**Specialty spawns:** — (future: fish, water creatures)

---

## Planned Biomes

### VILLAGE *(near-term)*

| Layer | Cells |
|---|---|
| Base | GRASS / COBBLESTONE (roads) |
| Moderate | DIRT |
| Low occurrence | FLOWER, WATER, TREE1 |
| Rare | — |

**CA behavior:** Cobblestone roads persist (very slow degrade). Trees near cobblestone clear. Standard lush drought chain.

**Structures:** HOUSE (clustered, higher density), STONE_HOUSE, MARKET_STALL, WELL, FORGE, CHEST
**Depth / interior:** HOUSE_INTERIOR (multi-NPC), TAVERN_INTERIOR (planned), BLACKSMITH_INTERIOR (planned)

**Default spawns:** GUARD (high, zone-wide patrol), TRADER (high), FARMER, BLACKSMITH, LUMBERJACK, KING or COMMANDER (one per village zone)
**Specialty spawns:** Tavernkeeper at TAVERN, faction NPCs at market, BANDIT (low, crime presence)

**Notes:** Village biome is the first social hub. NPCs have daily schedules (field at dawn, tavern at evening). Higher structure density than any other biome. Serves as the primary trade and quest-assignment zone.

---

### SWAMP *(mid-term)*

| Layer | Cells |
|---|---|
| Base | DIRT |
| Moderate | WATER |
| Low occurrence | GRASS, TREE1, DEEP_WATER |
| Rare | — |

**CA behavior:** Water floods aggressively; very slow evaporation. Grass struggles (surrounded by water/sand). Trees near water survive longer than other biomes.

**Structures:** CAVE, RUINS (planned), CHEST
**Depth / interior:** CAVE, CRYPT (planned)

**Default spawns:** GOBLIN, WOLF, BANDIT; low humanoid NPC density
**Specialty spawns:** Undead types (ZOMBIE, SKELETON) at CRYPT; future WITCH NPC at hut structure

---

### TUNDRA *(mid-term)*

| Layer | Cells |
|---|---|
| Base | DIRT |
| Moderate | STONE |
| Low occurrence | GRASS (sparse), WATER, TREE1 |
| Rare | — |

**CA behavior:** Snow/ice cell types planned. Very slow grass growth; aggressive grass → dirt drought decay.

**Structures:** CAVE, RUINS, occasional HOUSE
**Depth / interior:** CAVE

**Default spawns:** WOLF (high), SHEEP, MINER; very low humanoid density
**Specialty spawns:** GOLEM or TROLL (planned) at RUINS

---

### WIZARD'S TOWER *(planned — structure-biome hybrid)*

| Layer | Cells |
|---|---|
| Base | STONE / COBBLESTONE (ground floor) |
| Moderate | FLOOR_WOOD (upper floors) |
| Low occurrence | BOOKCASE (planned), CHEST, FORGE (arcane) |
| Rare | TOME items, enchanted gear drops |

**CA behavior:** Interior cells; no outdoor CA. Cell degradation only (floor planks decay if no wizard present).

**Structures:** Tower is itself a multi-floor structure — entry arch at ground floor, 3–5 stacked floors via STAIRS_UP/STAIRS_DOWN
**Depth / interior:**
- Ground floor: library, ingredient storage
- Mid floors: study rooms, summoning circles (planned)
- Top floor: Wizard boss room / WIZARD_KEEPER assignment

**Default spawns:** WIZARD (guaranteed, assigned as KEEPER), BLACK_SPIDER (ambient), rare SKELETON_THRALL (guarding)
**Specialty spawns:** Summons triggered by Wizard's cast actions; GHOST SCHOLAR (planned, Library variant); enchanted item loot at top floor chest

**Notes:** Wizard's Tower is the first example of a structure that functions as its own biome — it has a full interior zone stack, its own spawn rules, and a guaranteed named NPC. Entry requires finding the tower on the overworld. Future towers will be assigned to a Wizard NPC by the LoreEngine.

---

## Depth and Interior System

Biomes have multiple vertical "layers" accessed through enterable structures:

| Layer | Cell | Entry | Examples |
|---|---|---|---|
| Overworld | All biome cells | Zone travel | Forest, desert, plains |
| Ground interior | HOUSE_INTERIOR / CAVE_FLOOR | Enter HOUSE or CAVE | House rooms, cave chambers |
| Sub-floor (planned) | STAIRS_DOWN → new zone | Walk onto staircase cell | Mine levels, dungeon floors |
| Upper floor (planned) | STAIRS_UP → new zone | Walk onto staircase cell | Tower floors, castle battlements |
| Side branch (planned) | Passage cell | Walk into opening | Crypt side rooms, secret rooms |

**Current:** Single-depth entry only. HOUSE_INTERIOR and CAVE share one interior zone per structure. MINESHAFT uses CAVE interior type at deeper ore density.

**Planned:** Multi-floor via STAIRS_UP/STAIRS_DOWN cells linking discrete zone instances. Each floor is a full screen. Dungeon depth increases hostile spawn level and resource rarity.

---

## Specialty Spawn System

Specialty spawns are separate from the biome default spawn table. They fire based on:

| Trigger | Example |
|---|---|
| Structure present | FORGE → BLACKSMITH spawns near it |
| Biome + time of day | Night → BAT, GOBLIN, SKELETON at higher weight |
| Biome + depth | Cave depth 2+ → SKELETON, BAT guaranteed |
| LoreEngine event | Raid → hostile wave enters from zone edge |
| Named NPC assignment | WIZARD_KEEPER assigned by LoreEngine to WIZARD'S TOWER |
| Structure type (planned) | TAVERN → TAVERNKEEPER; CRYPT → SKELETON, ZOMBIE |

Specialty spawns are not yet a separate system — they currently blend into the default spawn tables or are handled by LoreEngine keeper assignment. The goal is to separate them into a `specialty_spawns` config per biome/structure so the default table covers ambient life and specialty spawns cover structure-tied or event-tied appearances.

---

## Long-Term Goal: Procedural Biome Generation

The biome template exists so biomes can eventually be procedurally generated rather than hand-authored. The target system:

1. **Template instantiation:** A proc-gen pass selects base/moderate/low/rare cell types from a pool based on climate parameters (wet/dry, hot/cold, altitude).
2. **CA rule selection:** Rate parameters are sampled from ranges (e.g. drought threshold, flood rate) rather than fixed constants.
3. **Structure rules:** Structures are picked from a pool compatible with the selected cell types (no forest structures in a tundra biome unless climate overlaps).
4. **Spawn table generation:** Entities are filtered by compatibility tags (e.g. `biome_tags: ['cold', 'elevated']`) and weighted by climate fit.
5. **Named biomes:** Proc-gen biomes receive generated names from the LoreEngine (e.g. "The Ashfields", "Frozen Reach") and are stored in the world map.

This system would allow the world to extend infinitely without repeating the same 5 hand-authored biomes, while still following the same ecological template that governs cell behavior and NPC density.
