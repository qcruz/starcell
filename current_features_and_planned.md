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

### World Generation & Structure

**Biome System** (`constants.py` — `BIOMES` dict)
- Forest: 60% grass, 20% dirt, trees, water
- Plains: 60% grass, 20% dirt, carrots, trees
- Desert: 70% sand, 20% dirt, stone
- Mountains: 45% dirt, 20% stone, 20% grass, 10% trees
- Procedurally generated, seeded by zone (screen_x, screen_y)

**Cell Types**

| Category | Cells |
|---|---|
| Terrain | GRASS, DIRT, WATER, DEEP_WATER, SAND |
| Structures | HOUSE, CAVE, MINESHAFT, CAMP, FORGE, WALL |
| Farming | SOIL, CARROT1/2/3, FLOWER |
| Building materials | WOOD, PLANKS, COBBLESTONE |
| Trees | TREE1, TREE2, TREE3 |
| Interior | FLOOR_WOOD, CAVE_FLOOR, CAVE_WALL, CHEST, STAIRS_UP, STAIRS_DOWN |

**Cell Growth/Decay Rates**
- Tree growth: 0.00005 / Flower spread: 0.0001 / Carrot 1→2: 0.02 / 2→3: 0.015
- Grass recovery: 0.0001 / Deep water formation: 0.05
- Grass→Dirt decay: 0.00001 / Dirt→Sand: 0.000005 / Tree decay: 0.0005
- House decay: 0.0001 / Water evaporation: 0.005

---

### Environment & Weather

**Weather System**
- Rain events: 30–250 ticks between events, 10–60 ticks duration
- Effects: 5 water spawns + 8 grass conversions per rain tick
- Per-zone tracking via `zone_last_rain`

**Day/Night Cycle**
- 150 ticks day + 150 ticks night (~5 min total)
- Night: dark overlay (alpha=40), skeleton spawning
- Daylight: skeleton damage (1 HP/update)

**Cellular Automata**
- Offscreen zones updated periodically
- Water spreading, sand/dirt transitions, neighbor-influenced growth/decay

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
- Level & XP (100 × level to next), Type-specific starting inventory

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
- 8-cell detection radius
- Locked combat for 2–3 seconds minimum
- Disengage: 5% chance per 2 seconds
- Flee when health < 30%, 40% flee chance
- Strategies vary by type (warriors attack, traders flee)

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

**Dropped Items**: Cell-based pickup, consolidate to nearest chest, decay over time

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
- Saves: player state, world cells, all entities, quests, factions, enchantments, dropped items, weather, day/night cycle
- Starting inventory: axe, hoe, shovel, pickaxe, bucket, bone_sword, star_spell
- Starting quest: FARM, starting position: (12, 9)

---

### Trading System
- Traders + other peaceful NPCs exchange items for gold/items
- Trade recipes per NPC type
- 2-second interaction window
- Gold as trade currency

---

### Dungeon System (Subscreens)

**Interior Types**
- House: wood floors, walls, 1 chest (random loot), 1 NPC resident, stairs
- Cave: stone floors/walls, multiple depth levels (1–3), hostile spawns (5%/update), chests at depth
- Mineshaft: cave variant by miners, higher mineral/loot density

**Chest Loot**

| Chest | Contents |
|---|---|
| HOUSE_CHEST | Gold 5–20 (80%), Wood 3–10 (60%), Carrot 1–5 (50%), Axe (20%) |
| CAVE_CHEST | Gold 10–50 (90%), Stone 5–15 (70%), Bones 1–3 (50%), Stone pickaxe (30%) |
| CAVE_DEEP_CHEST | Gold 50–200 (100%), Enchanted sword (40%), Leather armor (30%), Magic stone (20%) |

**Exit Mechanics**: NPCs exit dungeons (60% chance/update), items consolidate to chest on exit

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

*Last updated: 2026-02-27*
