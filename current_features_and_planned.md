# StarCell — Implemented Features

This document is the reference for all features currently in the game.
For planned and desired future features, see [`roadmap.md`](roadmap.md).

---

## IMPLEMENTED FEATURES

### Core Game Loop & Initialization
- **Main Class** (`main.py`, `game_core.py`): Composed via mixins — GameCoreMixin, NpcAiMixin, AutopilotMixin
- **Tick-based loop**: 60 FPS
- **Game states**: `menu`, `playing`, `paused`, `death`, `subscreen`
- **Grid system**: 24×18 cells per screen, 40px cell size

---

### Player System

**Stats**
- Health (100 base, scales with level)
- Level & Experience (100 × level XP per level)
- Magic pool (10 mana)
- Base damage (5 + level scaling)
- Hunger & Thirst (survival decay)

**Actions**
- 4-directional grid movement with viewport follow
- Melee attack with animation
- Harvesting: chop trees, mine rocks, harvest crops
- Farming: till soil, plant seeds, harvest
- 2-item crafting
- Star Spell casting with enchantment targeting
- Interact: talk to NPCs, enter buildings, open chests, pick up items
- Friendly Fire toggle (V key)
- Blocking state (defensive stance)

**Inventory**
- 20-slot inventory with 5 category tabs: Items, Tools, Magic, Followers, Crafting
- Item pickup/drop mechanics

---

### Controls Reference

**Movement**

| Key | Action |
|---|---|
| W / ↑ | Move up |
| S / ↓ | Move down |
| A / ← | Move left |
| D / → | Move right |

**Actions**

| Key | Action |
|---|---|
| Space | Interact (talk, enter, open chest, pick up) |
| E | Pick up cell or items from target tile |
| P | Place selected item as a cell |
| D | Drop selected item |
| N | Open NPC trade |
| B | Toggle blocking (90% damage reduction) |
| V | Toggle friendly fire |

**Magic & Spells**

| Key | Action |
|---|---|
| L | Cast star spell — enchants targeted cell or entity |
| K | Release / reverse spell — removes all active enchantments |

> `K` is the reverse-spell key. Reserved for future spell mechanic expansion (e.g. reversing specific spell effects, countering enemy magic, inverting enchantment properties).

**Inventory & UI**

| Key | Action |
|---|---|
| I | Items tab |
| T | Tools tab |
| M | Magic tab |
| F | Followers tab |
| C | Crafting tab |
| X | Attempt craft with selected items |
| Q | Toggle quest panel |
| Shift+Q | Get / turn in quest from inspected NPC (NPC Quest Source) |
| 1–9, 0 | Select inventory slot |

**Combat**

| Key | Action |
|---|---|
| J | Release selected follower |

**Autopilot**

| Key | Action |
|---|---|
| Shift+A | Toggle autopilot on/off (off by default; any other input also disengages) |

**Menu / Pause**

| Key | Action |
|---|---|
| Escape | Pause / unpause |
| P | Unpause |
| S *(paused)* | Save game |
| M *(paused)* | Return to main menu |
| 1 *(menu)* | New game |
| 2 *(menu)* | Load game |
| Q *(menu)* | Quit |

---

### World Generation & Structure

**Biome System** (`constants.py` — `BIOMES` dict)
- Forest — grass, dirt, trees, water
- Plains — grass, dirt, carrots, trees
- Mountains — dirt, stone, grass, trees
- Desert — sand, dirt, stone, cactus
- Lake — water interior, SAND perimeter, CLIFF border; no entity spawns; deep water forms in centre
- All biomes have **equal generation chance** (random selection, no weights)
- Procedurally generated, seeded by zone (screen_x, screen_y)
- Zone entrance cells pinned to adjacent zone's primary biome type; base terrain spreads via NSEW neighbor-copy rule (rate 0.004/update)
- Zone biome label auto-updates when dominant cell type shifts (e.g. 50%+ water → LAKE)
- Biome shift thresholds: PLAINS requires `tree_pct < 0.05`; FOREST requires `tree_pct > 0.1`

**Cell Types**

| Category | Cells |
|---|---|
| Terrain | GRASS, DIRT, WATER, DEEP_WATER, SAND |
| Biome borders | CLIFF (LAKE biome border, solid) |
| Structures | HOUSE, STONE_HOUSE, CAVE, MINESHAFT, CAMP, FORGE, WALL, WELL (solid) |
| Farming | SOIL, CARROT1/2/3, FLOWER, CACTUS |
| Building materials | WOOD, PLANKS, COBBLESTONE |
| Trees | TREE1, TREE2 |
| Ore | IRON_ORE (cave cell, drops iron_ore item) |
| Interior | FLOOR_WOOD, CAVE_FLOOR, CAVE_WALL, CHEST, STAIRS_UP, STAIRS_DOWN |
| Decorative | BARREL, RUINED_SANDSTONE_COLUMN |

**Cell Growth/Decay Rates** (base rates; scaled by drought `_growth`/`_decay` multipliers each update)
- Tree growth: 0.0001 / Tree decay: 0.0005 / Tree crowding decay (adjacent tree): 0.001
- Flower spread: 0.0001 / Carrot 1→2: 0.02 / 2→3: 0.015
- Grass recovery: 0.0001 / Deep water formation: 0.05
- Grass→Dirt decay: 0.00001 / Dirt→Sand spread: 0.008 / Grass→Sand decay: 0.003
- Biome neighbor-copy spread: 0.004 / Sand reclamation (1+ water neighbor): 0.05
- Flooding (rain only, 3+ water): 0.08 / Grass→Water absorption (rain only): 0.02
- House decay: 0.0001 / Water evaporation: 0.005

---

### Environment & Weather

**Weather System**
- Rain events: 1800–18000 ticks between events (~30 s to 5 min), 10–60 ticks duration
- Effects: flooding and grass→water absorption only trigger while raining (rain-gated)
- Per-zone tracking via `zone_last_rain`

**Drought System**
- `drought_severity = min((tick - zone_last_rain) / 9000, 1.0)` computed per zone per update
- `_growth = max(0.1, 1.0 - drought_severity × 0.9) × _tp` — floors at 10% of normal rate
- `_decay = (1.0 + drought_severity × 0.5) × _tp` — peaks at 1.5× normal rate
- All cellular automata growth/decay rules use these multipliers instead of raw tick probability

**Day/Night Cycle**
- 150 ticks day + 150 ticks night (~5 min total)
- Night: dark overlay (alpha=40), skeleton spawning
- Daylight: skeleton damage (1 HP/update)

**Cellular Automata**
- Offscreen zones updated periodically
- Water spreading (rain-gated), sand/dirt transitions, drought-scaled growth/decay
- Tree crowding: any tree adjacent to another tree decays at TREE_CROWD_DECAY_RATE (produces checkerboard spacing)
- Cobblestone conversion: trees only convert to cobblestone when 5+ cobblestone neighbors; 1–4 neighbors decay to grass

---

### Entity System (`entity.py`, `constants.py`)

**Entity Types**

| Category | Types |
|---|---|
| Animals | Sheep (herbivore, flees), Wolf (carnivore, hunts), Deer (fast, flees) |
| Peaceful NPCs | Farmer, Lumberjack, Miner, Trader, Guard, Wizard, Blacksmith |
| Combat NPCs | Warrior, Commander, King, Skeleton (player follower) |
| Hostile NPCs | Bandit, Goblin, Black Bat, Yellow Termite |

**Entity Properties**
- Health (scales with level), Hunger/Thirst (decay 0.02/0.015 per tick)
- Strength (base × level), Speed (per-type multiplier)
- Age (65–100 year lifespan, old age damage 0.05 HP/tick)
- Level & XP (100 × level to next)
- Starting inventory: all humanoid NPCs spawn with 0–30 wood, stone, and meat plus 0–2 random items from the full item/cell pool

**AI States**: `idle` (60t), `wandering` (120t), `targeting` (180t), `combat` (120t), `fleeing` (120t)

**AI Parameters per type**: aggressiveness, passiveness, idleness, flee_chance, combat_chance, target_types

**Movement**
- Grid-based with float interpolation (world_x, world_y for rendering)
- Memory lane: 8–25 cells remembered
- BASE_MOVEMENT_SPEED: 0.034 cells/tick × entity speed
- NPC move interval: 180 ticks ±60

**Animation**: 3-frame walk cycle (1/still/2), 4 directions, 10 ticks/frame

**Merging/Doubling**: Same type+level entities can merge → `_double` variant, merged inventory

---

### NPC AI & Behaviors (`npc_ai.py`)

**Behavior-Driven Actions** (data table in `constants.py` — `NPC_BEHAVIORS`)

| NPC | Key Behaviors |
|---|---|
| Farmer | Harvest CARROT2/3 (30% rate, 40% success), till grass/dirt (10%/25%), plant seeds (50%/30%) |
| Lumberjack | Chop trees (50% + 2%/nearby tree, 85% success), build houses (5%/35%), place camps |
| Miner | Mine stone (20% success), create mineshafts at zone corners (10%) |
| Guard/Warrior | Patrol center lanes, hunt hostiles (95% aggression), build cobblestone paths |
| Trader | Travel zone exits, build cobblestone paths (60%/25%), trade with peaceful NPCs |
| Wizard | Seek runestones, cast spells (heal/fireball/lightning/ice/enchant), explore caves, 180t cooldown |
| Blacksmith | Build forges, craft weapons, trade weapons |
| Goblin | Attack camps (5%), attack houses (1%), coordinate raids |

**NPC Quest Focus System** (6 peaceful focus types, 1 hostile)
- farming, building, mining, crafting, exploring, combat_hostile, combat_all
- Unlocked via leveling: 10% chance/level (peaceful), 3% chance/level (combat_all)
- 10% chance to switch focus when multiple unlocked

**Target Assignment**: Cell positions, entity IDs, zone exits — assigned based on quest_focus, nudged by autopilot every 120t

---

### Faction System

**Peaceful Factions**
- 10 colors (Red, Blue, Gold…) × 10 symbols (Lion, Dragon, Wolf…)
- Warriors join factions, have leaders and commanders
- Zone control tracking, max size enforced

**Hostile Factions**
- Goblins/Bandits form clans: Shadow/Black/Dark + Fang/Claw/Knife/Death names
- Coordinate raids, recruit, expand territory

---

### Combat System

**Player Combat**
- Adjacent-cell melee attack
- Damage: base_damage (5) + level
- Blocking: 90% damage reduction
- Tools: Bone sword (15), stone pickaxe (8), stone axe (10), club (8)
- Magic weapons: enchanted sword (25), enchanted axe (20)

**NPC Combat**
- 8-cell detection radius; hostile entities detect and pursue player automatically
- State machine: targeting → adjacent → combat; attack resolved via per-update `attack_chance` probability roll (replaces fixed cooldown)
- Damage: `entity.strength // 5` (level-scaled) + weapon bonus + magic bonus + 1.2× hostile multiplier
- Attack animation shown on hit; `entity.in_combat` flag set immediately on adjacency (combat stance visible between attacks)
- Flee when health low; flee_chance scaled by threat level ratio
- Followers never target the player (guarded in both state machine proximity check and find_and_attack_enemy)
- Non-combat NPCs have 10% chance to counterattack when adjacent; otherwise flee

---

### Crafting System (`constants.py` — `RECIPES`)

| Recipe | Result |
|---|---|
| wood + stone | stone_pickaxe |
| wood + wood | hoe |
| stone + stone | shovel |
| hoe + wood | hilt |
| hilt + bone/bones | bone_sword |
| hilt + stone | stone_axe |
| hilt + fur | club |
| axe + wood OR wood + wood | planks |
| planks + planks | chest |
| wood + bucket | watering_can |
| carrot + carrot | seeds |
| star_spell + stone | magic_stone |
| star_spell + wood | magic_wand |
| star_spell + bone_sword | enchanted_sword |
| star_spell + stone_axe | enchanted_axe |
| star_spell + bones | skeleton_bones |
| fur + fur | leather |
| leather + leather | leather_armor |
| meat + meat | cooked_meat |
| carrot + meat | stew |
| stone + planks | wall |
| planks + dirt | floor |
| wood + sand | sandstone |

- 2-item combination, order-independent, instant success

---

### Items & Inventory

| Category | Items |
|---|---|
| Resources | wood, planks, carrot, gold, bones, stone, fur, meat |
| Tools | axe, hoe, shovel, pickaxe, bucket, watering_can |
| Weapons | bone_sword, stone_axe, club, enchanted_sword, enchanted_axe |
| Magic | star_spell, magic_stone, magic_wand |
| Materials | rope, leather, leather_armor, seeds, floor, sandstone, wall, chest |
| Food | cooked_meat, stew |
| Special | skeleton_bones (summons follower) |
| Runestones | lightning_rune, fire_rune, ice_rune, poison_rune, shadow_rune (3 dmg each) |

**Item Decay** (`ITEM_DECAY_CONFIG`): Bones (5%), Meat (10% — spoils completely), Carrot (3% — can replant)

**Dropped Items**: On entity death, 1–2 items scatter individually near body; remaining drops consolidate into a single itembag pile at entity position.  All pickups decay over time.

---

### Quest System

**Quest Types**
- FARM, HUNT, SLAY, EXPLORE, GATHER, LUMBER, MINE, RESCUE, SEARCH, COMBAT_HOSTILE, COMBAT_ALL

**Mechanics**
- Active quest selected from available list
- Quest arrow pointing to target, updates as player moves
- XP reward: target_level × 10
- Cooldown: 300 ticks before new quest
- Lore text generated by `loreEngine()`

---

### Save / Load System
- JSON save files
- Saves: player state, world cells, all entities, quests, factions, enchantments, dropped items, weather, day/night cycle, follower_items mapping
- Starting inventory: axe, hoe, shovel, pickaxe, bucket, bone_sword, star_spell
- Starting quest: FARM, starting position: (12, 9)

---

### Trading System
- Traders + other peaceful NPCs exchange items for gold/items
- Trade recipes per NPC type
- 2-second interaction window
- Gold as trade currency

---

### Structure System (Unified Zone Model)

Structure interiors (houses, caves, mineshafts) are full zone objects sharing the same
update pipeline as overworld zones.  Each interior has its own cell grid, entity list, item
list, weather state, and cellular automata pass.  Entity AI, spawning, decay, and catch-up
simulation work identically inside and outside structures.

**Interior Types**
- House: wood floors, walls, 1 chest (random loot), 1 NPC resident, stairs
- Cave: stone floors/walls, multiple depth levels (1–3), hostile spawns (5%/update), chests at depth
- Mineshaft: cave variant by miners, higher mineral/loot density

**NPC Structure Entry**
- CAVE / MINESHAFT: entity must be in `targeting` or `combat` state with a confirmed target inside the structure
- HOUSE / other: 10% random chance when adjacent
- Cross-structure targeting: entities detect hostiles inside connected caves and navigate to the door first

**Chest Loot**

| Chest | Contents |
|---|---|
| HOUSE_CHEST | Gold 5–20 (80%), Wood 3–10 (60%), Carrot 1–5 (50%), Axe (20%) |
| CAVE_CHEST | Gold 10–50 (90%), Stone 5–15 (70%), Bones 1–3 (50%), Stone pickaxe (30%) |
| CAVE_DEEP_CHEST | Gold 50–200 (100%), Enchanted sword (40%), Leather armor (30%), Magic stone (20%) |

**Exit Mechanics**: NPCs exit structures (60% chance/update); Keepers never exit their assigned structure; items consolidate to chest on exit

---

### Special Events

**Raid System**
- Trigger: 6+ entities in zone + 5-min interval, 8% chance
- Hostile group attacks peaceful structures
- Post-raid: highest-level entity → WARRIOR (60% chance)

**Hostile Spawning**
- Skeletons: Night, 1%/zone (higher near dropped items)
- Termites: 0.1%/zone (near trees)
- Goblins/Bandits: 5%/cave/update
- Black Bats: Flying, disengages after first hit

**Structure Events**
- Hidden caves: 20% chance during raids
- Camp → House upgrade: 0.1%/update

---

### Autopilot System (`autopilot.py`)

- **Off by default** — toggled on/off with **Shift+A**
- Spawns a proxy Entity at player position using quest-appropriate NPC role
- Nudges proxy toward quest target every 120 ticks
- Mirrors proxy inventory to player every 60 ticks
- Disengages immediately on any player input; player snaps to proxy's position

**Quest → Proxy Role**

| Quest | Proxy |
|---|---|
| FARM | FARMER |
| GATHER / LUMBER | LUMBERJACK |
| MINE | MINER |
| HUNT / SLAY / COMBAT_HOSTILE | WARRIOR |
| EXPLORE | TRADER |
| SEARCH / RESCUE | WIZARD |
| Default | FARMER |

---

### Catch-Up / Zone Simulation System

- Priority queue of zones to update (distance from player, entity density, last update time)
- Max 20 zones updated per tick cycle (every 30 ticks)
- Current zone: 100% / Distance 1: 90% / Distance 2: 80% / Distance 3+: 60%
- Catch-up simulation caps at 100 cycles per zone to prevent runaway computation
- Applies all normal AI/cell updates during catch-up

---

### Time Pass Simulation (Death / New Game)

- On player death and new game start, 100–200 in-game years of world simulation run before play resumes
- Uses the full probabilistic zone update queue (all automata, grows_to, ageing, entity AI) — not simplified custom logic
- `time_pass_active` flag bypasses the tick gate; `time_pass_speed = 20.0` multiplies all probabilistic rates
- NPC XP gain, damage, and action success rates scale by `time_pass_speed` during simulation
- Year counter advances at the same 20× rate; 15 update cycles run per rendered frame to keep the death screen responsive
- Death screen displays years elapsed in real time; simulation stops when the target year count is reached

---

### Keeper System

- A Keeper is an NPC permanently assigned to a zone or structure; Keepers never leave their domain
- LoreEngine assigns Keeper status when a qualifying zone or structure condition is met; assignment persists in save
- Keeper types: WOLF, BAT, GOBLIN, BANDIT, SKELETON, TERMITE, SHEEP, DEER (zone-specific)
- TRADER is eligible as a Keeper (zone trader)
- Shift+inspect on a Keeper NPC shows keeper status; Keepers are exempt from the structure overcrowding eviction mechanic

---

### Structure Overcrowding

- When a structure's local population exceeds 3 NPCs, each NPC beyond that threshold has a 10% chance per extra entity to seek the zone exit each AI update
- Keepers are always exempt from this mechanic
- Prevents structures from accumulating arbitrarily large populations over time

---

### UI / HUD

- Top-left: level, XP bar, health bar
- Center-top: zone name
- Right: inventory icons for selected items
- Bottom: status messages, interaction prompts
- Attack animations on target cells
- Tabbed inventory panel (Items/Tools/Magic/Followers/Crafting)
- Quest panel: list, active quest, target, arrow indicator
- Death screen: cause, respawn, final stats
- NPC inspection: stats, inventory, name, lore (5s timeout)
- Debug flags: `debug_memory_lanes`, `debug_entity_ai`, `debug_visualization`

---

### Enchantment System

- Star Spell targets cells or entities
- Cell enchantment: freezes growth/decay for duration
- Entity enchantment: slows/immobilizes target
- Legendary item creation: enchanted tools get generated names
- Runestones add magic damage types (lightning/fire/ice/poison/shadow, 3 dmg each)

---

### Rendering & Sprites

- Sprite sheet + individual PNG files (`sprites/` directory)
- 40px cell size, RGBA transparency support
- 10 grass variants for visual variety
- Fallback: colored rectangles + symbol text for missing sprites
- All entity types have 4-direction × 3-frame animation sprites

---

### Configuration Reference (`constants.py`)

| Setting | Value |
|---|---|
| Screen | 960×720 (24×18 grid, 40px cells) |
| FPS | 60 |
| Day / Night | 150 ticks each |
| Night overlay | alpha=40 |
| Hunger decay | 0.02/tick |
| Thirst decay | 0.015/tick |
| Starvation damage | 0.1 HP/tick |
| Dehydration damage | 0.15 HP/tick |
| Base healing | 1.5 HP/tick |
| Camp heal multiplier | 2× |
| House heal multiplier | 3× |
| Global spawn multiplier | 1.0 |
| Raid threshold | 6+ entities, 8% chance, 5-min interval |

---

## FILE STRUCTURE REFERENCE

| Path | Role |
|---|---|
| `main.py` | Entry point — assembles `Game` class via mixin MRO |
| `data/` | Game data tables (settings, cells, items, entities, factions, quests, spells, biomes) |
| `engine/` | Core helpers (Entity, Inventory, Quest, SpriteManager) |
| `systems/` | SaveLoad, Crafting, Combat, Enchantment, Factions, Spawning mixins |
| `world/` | WorldGeneration, Zones, Cells mixins |
| `ui/` | HUD, InventoryUI, Menus mixins |
| `ai/` | NpcAiActions, NpcAiMovement mixins |
| `lore/` | LoreEngine mixin (quest targeting, secret entrances, world events) |
| `game_core.py` | Legacy monolith — game loop, input, player movement, subscreen transitions |
| `npc_ai.py` | Legacy monolith — NPC AI states, role behaviors, combat |
| `autopilot.py` | Player autopilot system (Shift+A toggle) |
| `constants.py` | All config constants, recipes, biome definitions |
| `sprites/` | Sprite images (terrain, entities, animated walk cycles) |
| `launcher/` | macOS .app bundle + launch.py for one-click GitHub install |

---

*Last updated: 2026-03-07*
