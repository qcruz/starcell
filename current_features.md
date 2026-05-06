# StarCell — Implemented Features

Reference for all features currently in the game. For planned features see `roadmap.md` and `next_up.md`. Updated end of each session.

---

## Architecture

**MRO (main.py)**
```
Game ← HudMixin, InventoryUIMixin, MenusMixin, DevScreenMixin
      ← WorldGenerationMixin, ZonesMixin, CellsMixin
      ← SaveLoadMixin, CraftingMixin, CombatMixin, EnchantmentMixin, FactionsMixin, SpawningMixin
      ← NpcAiActionsMixin, NpcAiMovementMixin
      ← LoreEngineMixin
      ← GameCoreMixin, NpcAiMixin, AutopilotMixin  (legacy fallbacks)
```

**Dual-Import Rule**: All cell types, items, and entity data must exist in **both** `constants.py` (used by legacy monoliths via `from constants import *`) and the appropriate `data/` module (used by newer mixins). Omitting either causes silent failures.

**File Roles**

| File/Dir | Role |
|---|---|
| `constants.py` | Legacy all-in-one: CELL_TYPES, ITEMS, ENTITY_TYPES, RECIPES, all balance constants |
| `data/cells.py` | COLORS, CELL_TYPES, CELL_PICKUP, ITEM_TO_CELL |
| `data/items.py` | ITEMS, RECIPES, LOOT_TABLES |
| `data/entities.py` | ENTITY_TYPES, NPC_BEHAVIORS, NPC_TRANSFORMATION_CONFIG |
| `data/factions.py` | Faction color/symbol pools |
| `data/quests.py` | Quest type definitions |
| `entity.py` | Entity class, Inventory class, SpriteManager — root-level file; game_core.py imports via `from entity import *` |
| `systems/crafting.py` | CraftingMixin — pickup, place, craft, follower spawn |
| `systems/combat.py` | CombatMixin — attack, death, reconcile_screen_entities |
| `systems/enchantment.py` | EnchantmentMixin — star spell, dev spells, follower release |
| `systems/spawning.py` | SpawningMixin — zone spawning checks |
| `systems/factions.py` | FactionsMixin — faction registration, zone control, triggers faction domain rebuild |
| `world/zones.py` | ZonesMixin — probabilistic_zone_updates, cell CA, entity AI dispatch, chest logic, biome/faction domain management |
| `world/generation.py` | WorldGenerationMixin — screen + cave generation |
| `ai/actions.py` | NpcAiActionsMixin — harvest, build, plant, mine, trade, footstep sounds |
| `ai/movement.py` | NpcAiMovementMixin — wander_entity, move_toward_position, zone crossing |
| `npc_ai.py` | NpcAiMixin — update_entity_ai, state machine, combat, sheltering |
| `game_core.py` | GameCoreMixin — init, run loop, player input, new_game, NPC trade window |
| `autopilot.py` | AutopilotMixin — possession-model autopilot |
| `lore/engine.py` | LoreEngineMixin — keeper assignment, world events, zone history |
| `ui/hud.py` | HudMixin — draw_game, entity rendering, HUD overlay |
| `monolith_extraction_recon.md` | Tracks what has/hasn't been extracted from `game_core.py` and `npc_ai.py`; extraction targets and priority order |

**NPC AI Dispatch**: `probabilistic_zone_updates()` (every 30 ticks) → `update_zone_with_coverage()` → `update_entity_ai()` per entity. `game_core.py`'s `update_entities()` is dead code — all NPC AI runs through zones.py.

---

## Core Game Loop

- 60 FPS tick-based loop
- Game states: `menu`, `playing`, `paused`, `death`
- Grid: 24×18 cells per zone, 40px cell size, 960×720 screen
- `probabilistic_zone_updates()` fires every 30 ticks (UPDATE_FREQUENCY)
- Slow-update block (every 30 ticks): stat decay, healing, energy regen, entity AI off-screen

---

## Player System

**Stats**

| Stat | Base | Notes |
|---|---|---|
| Health | 100 + 8 × level | Regenerates 1.5/tick when fed; 2× near camp, 3× in house |
| XP to level | 100 × level | No level cap |
| Base damage | 5 + level | |
| Hunger | 100 | Decays 0.02/tick; humanoids 6× faster; starvation deals 1 HP/tick |
| Thirst | 100 | Decays 0.015/tick; humanoids 2× faster; dehydration deals 1.5 HP/tick |
| Energy | 100 | Drains 2/step; regens 1/tick stationary, 2/tick idle |

**Starting Inventory (new_game)**
- One of every item in the ITEMS registry (including all dev spells), except `is_follower` items
- Includes: all tools, weapons, magic spells, actions, summon/transform spells for all 22 NPC types
- Starting position: (12, 9), starting quest: FARM

---

## Controls

**Movement**

| Key | Action |
|---|---|
| W / A / S / D or Arrow keys | 4-directional grid movement |

**Actions**

| Key | Action |
|---|---|
| Space | Interact — attack (weapon selected), shove (shove action selected), talk to NPC, enter/exit structure, open chest/pick up chest contents, pick up dropped items |
| E | Pick up cell or dropped items from target tile |
| P | Place selected item as a cell |
| D | Drop selected item |
| B | Toggle blocking (90% damage reduction) |
| V | Toggle friendly fire |
| J | Release selected follower |
| N | Open NPC trade interaction — drops gold near adjacent NPC to trigger a trade; if trade panel already open, executes first available recipe |

**Magic & Spells**

| Key | Action |
|---|---|
| L | Cast selected magic — rain_spell toggles rain; day_spell toggles day/night; keeper_spell assigns inspected NPC as keeper; star_spell enchants target; summon_X spawns NPC; transform_X swaps player sprite |
| K | Reverse spell — removes all active enchantments |

**Inventory & UI**

| Key | Action |
|---|---|
| I | Items tab |
| T | Tools tab + Equipment panel |
| M | Magic tab |
| R | Actions tab |
| F | Followers tab |
| C | Crafting tab |
| X | Attempt craft with selected items |
| Q | Toggle quest panel |
| Shift+Q | Get / turn in quest from inspected NPC |
| Shift+A | Autopilot toggle OR assign quest to NPC (context-sensitive) |
| Shift+G | Gift item to inspected NPC — offers selected item; NPC gains +favor |
| Shift+T | Open inventory trade window with inspected NPC — shows NPC's items with random gold prices (5–10 each); click to buy |
| Shift+F | Attempt to recruit inspected NPC as follower (50% chance) |
| Shift+I | Dev info overlay (zones, entities, followers, domains) |
| 1–9, 0 | Select inventory slot |
| Shift+← / Shift+→ | Cycle inventory slot |

**Menu / Pause**

| Key | Action |
|---|---|
| Escape | Pause / unpause |
| S *(paused)* | Save game |
| M *(paused)* | Return to main menu |
| 1 *(menu)* | New game |
| 2 *(menu)* | Load game |
| Q *(menu)* | Quit |

---

## World Generation & Biomes

**Biome Types**

| Biome | Base Cell | Key Cells | Notes |
|---|---|---|---|
| FOREST | GRASS | TREE1, TREE2, FLOWER, BUSH, WATER | Most common |
| PLAINS | GRASS | FLOWER, BUSH, CARROT | Open terrain |
| MOUNTAINS | DIRT | STONE, GRASS | |
| DESERT | SAND | STONE, CACTUS, BUSH (rare scrub) | |
| LAKE | WATER | DEEP_WATER, SAND, CLIFF | No entity spawns; deep water forms in center; CLIFF border |
| SWAMP | DIRT | WATER, GRASS, BUSH | |

**Zone System**
- Each zone is a 24×18 grid seeded by (screen_x, screen_y)
- Structure zones (houses, caves) are separate zone objects with virtual coordinates
- Priority queue: player zone + 4 cardinal neighbors always updated at 100% entity coverage
- Beyond mandatory zones: probability-weighted by distance, staleness, entity density
- Soft cap: 200 overworld zones; beyond this, instantiation chance drops sharply
- Stale zones (>20k ticks since update, >4 zones from player): probability removal
- Zone name: auto-updates when dominant cell type shifts (LAKE if 50%+ water, etc.)

**Biome Spread**
- Biome base cells spread to neighbors at 0.004/tick
- Foreign revert: non-native cells decay to biome base (e.g. GRASS→SAND in desert at 0.003)
- Entrance cells pinned to adjacent zone's primary cell type

**Zone Connections & Doors**
- door_map: {(src_zone, x, y) → (dest_zone, x, y)} for structure entry/exit
- Validated each 600-tick cleanup; orphan entries removed

---

## Cell Types

**Complete Cell List**

| Category | Cell | Solid | Notes |
|---|---|---|---|
| Terrain | GRASS | No | 10 visual variants; grows to TREE1 at 0.0005 |
| Terrain | DIRT | No | |
| Terrain | WATER | No | Spreads during rain |
| Terrain | DEEP_WATER | No | Forms when 3+ water neighbors |
| Terrain | SAND | No | Spreads in desert |
| Structures | HOUSE | Yes | Interior structure; decays at 0.0001 |
| Structures | STONE_HOUSE | Yes | More durable variant |
| Structures | CAVE | Yes | Multi-depth structure |
| Structures | MINESHAFT | Yes | Cave variant, higher loot density |
| Structures | CAMP | Yes | Healing boost 2× for nearby NPCs |
| Structures | FORGE | Yes | Blacksmith builds; enables forging |
| Structures | WALL | Yes | Player/NPC built |
| Structures | WELL | Yes | Water source; NPCs seek for thirst |
| Farming | SOIL | No | Tilled from GRASS/DIRT |
| Farming | CARROT1 | No | Grows to CARROT2 at 0.02 |
| Farming | CARROT2 | No | Grows to CARROT3 at 0.015 |
| Farming | CARROT3 | No | Harvest stage |
| Farming | FLOWER | No | Spread 0.0001; decay 0.0005 |
| Decorative | FLOWER_PATTERN1 | No | Golden yellow; rare growth from GRASS in forest/plains; decays to GRASS at 0.00015; harvestable for flower item |
| Decorative | FLOWER_PATTERN2 | No | Lavender purple; same rules as FLOWER_PATTERN1 |
| Decorative | FLOWER_PATTERN3 | No | Coral red; same rules as FLOWER_PATTERN1 |
| Farming | CACTUS | Yes | Desert only; decays in non-desert |
| Resources | TREE1 | Yes | Grows to TREE2; drops wood |
| Resources | TREE2 | Yes | Drops more wood; decays 0.0005 |
| Resources | STONE | Yes | Drops stone |
| Resources | IRON_ORE | Yes | Cave cell; drops iron_ore; 3% depth 1 / 7% depth 2+ |
| Vegetation | BUSH | Yes | Rare growth from GRASS (forest/plains/swamp 0.000005, desert 0.0000008); drops wood or reverts to GRASS; pickable as `bush` item, replantable |
| Building | WOOD | No | Item-cell |
| Building | PLANKS | No | Item-cell |
| Building | COBBLESTONE | Yes | Decays unless 5+ cobble neighbors |
| Interior | FLOOR_WOOD | No | House interior floor |
| Interior | CAVE_FLOOR | No | Cave interior floor |
| Interior | CAVE_WALL | Yes | Cave interior wall |
| Interior | CHEST | Yes | Interactable; swaps to EMPTY_CRATE when contents empty; NPC-placed only if no chest within 5 cells |
| Interior | OPEN_CHEST | Yes | Visual variant for an opened chest |
| Interior | LOCKED_CHEST | Yes | Interactable; requires a key item |
| Interior | EMPTY_CRATE | Yes | Interactable; visual state for empty CHEST; swaps back to CHEST if contents added; E-key returns chest item |
| Interior | APPLE_CRATE | Yes | Infinite food source (food_value=30); interactable; placed in house interiors; humanoid NPCs use as food source |
| Interior | WATER_TROUGH | Yes | Solid; water source for NPCs; placed in structures |
| Interior | DESERT_WELL | Yes | Well variant for desert zones; NPCs seek for thirst |
| Interior | STAIRS_UP | Yes | Structure entry/exit |
| Interior | STAIRS_DOWN | Yes | Structure entry/exit |
| Decorative | BARREL | Yes | Contains random loot; interactable |
| Decorative | RUINED_SANDSTONE_COLUMN | Yes | Aesthetic |
| Decorative | CLIFF | Yes | LAKE biome border |
| Item-cells | MEAT, FUR, BONES, COBBLESTONE | Mixed | Drop/place items |

**Cell Growth & Decay Rates** (probability per 30-tick update; scaled by drought multipliers)

| Cell | Rate | Direction |
|---|---|---|
| GRASS → TREE1 | 0.0005 | growth |
| TREE1 → TREE2 | 0.0001 | growth |
| TREE decay | 0.0005 | decay → GRASS/DIRT |
| Tree crowding (adjacent tree) | 0.001 | decay |
| FLOWER spread | 0.0001 | growth |
| FLOWER decay | 0.0005 | decay |
| CARROT1 → 2 | 0.02 | growth |
| CARROT2 → 3 | 0.015 | growth |
| CARROT decay | 0.0001 | → GRASS |
| GRASS → DIRT | 0.00001 | decay |
| DIRT → SAND spread | 0.008 | desert spread |
| GRASS → SAND | 0.003 | desert spread |
| Biome neighbor-copy | 0.004 | spread |
| DEEP_WATER formation | 0.05 | 3+ water neighbors |
| DEEP_WATER evaporation | 0.3 | any exposed cardinal side |
| Water evaporation (isolated) | 0.02 | ≤1 water neighbor |
| Rain flooding | 0.08 | rain only, GRASS→WATER |
| Rain absorption | 0.02 | rain only |
| House decay | 0.0001 | → biome base |
| Cobblestone decay | 0.00001 | <5 cobble neighbors |
| BUSH growth (forest/plains/swamp) | 0.000005 | from GRASS |
| BUSH growth (desert scrub) | 0.0000008 | from SAND |
| FLOWER_PATTERN growth (forest/plains) | 0.000008 | from GRASS; random variant chosen |
| FLOWER_PATTERN1/2/3 decay | 0.00015 | → GRASS |
| CHEST → EMPTY_CRATE | each update | when chest_contents empty |
| EMPTY_CRATE → CHEST | each update | when chest_contents non-empty |

**Drought Scaling**
- `drought_severity = min((tick - zone_last_rain) / 9000, 1.0)`
- `_growth = max(0.1, 1.0 − drought_severity × 0.9)` — floors at 10% of normal
- `_decay = (1.0 + drought_severity × 0.5)` — peaks at 1.5×

---

## Weather & Environment

**Rain**
- 1–5 min between events (120–600 update_weather calls), 15–90 s duration
- update_weather called every 30 ticks; every tick during time-pass simulation
- Per-zone tracking: zone_last_rain timestamp
- Effects: flooding, absorption, drought reset
- **Crop growth scaling**: active rain suppresses crop decay rate and boosts grass/tree spread; `world/cells.py` applies drought_severity scaling (see Cell Growth & Decay table)

**Day/Night Cycle**
- 150 ticks day + 150 ticks night (~5 min total)
- Night: dark overlay (alpha=40)
- Skeleton spawning at night; skeleton daylight damage 1 HP/update
- NPCs seek shelter (HOUSE, CAVE, CAMP) at night

---

## Entity System

**22 Entity Types**

| Category | Types |
|---|---|
| Herbivores/Passive | SHEEP, DEER, RED_BIRD, CHICKEN, BUTTERFLY (grows FLOWER/FLOWER_PATTERN on GRASS; grows GRASS/FLOWER from DIRT) |
| Carnivores | WOLF, BLACK_SPIDER |
| Peaceful NPCs | FARMER, LUMBERJACK, MINER, TRADER, GUARD, WIZARD, BLACKSMITH |
| Combat NPCs | WARRIOR, COMMANDER, KING |
| Hostile | BANDIT, GOBLIN, BAT, TERMITE, SKELETON |

**Entity Stats**

| Stat | Notes |
|---|---|
| Health | 16 (SHEEP) – 120 (KING) base; scales with level |
| Hunger/Thirst | 100 base; animals 0.02/0.015 per tick, humanoids 6×/2×; clamped to [0, max] in `decay_stats` and `regenerate_health` |
| Energy | 100 max; drains 2/step; regen in zones.py off-screen loop |
| Strength | base × level |
| Speed | 0.7–2.0 multiplier (BAT fastest) |
| Age | 65–100 year lifespan; old-age damage 2 HP/zone-update above threshold |
| XP | Gained from every non-walking action (eat, drink, attack, harvest, pickup, deposit); chance = 1/level per roll; 100 XP = L2, 200 XP = L3, etc. |
| Level | `1.0 + xp / 100.0` (continuous float); integer crossings trigger level-up effects |
| tasks_completed | Integer counter incremented each time the entity completes an archetype action (`action_harvest_cell`, `action_transform_cell`, `action_place_cell`) or a quest target arrival; saved/loaded; visible in dev overlay (Shift+I) |

**Level-Up Effects** (`level_up_from_activity`)
- Full health, hunger, and thirst restore
- Age reduced; max_age extended
- 20% chance per item in inventory to level up that item
- 10% chance per unlocked quest type to unlock another
- 10% chance to switch quest focus

**Starting Inventory by Type**
- Humanoids: 0–30 wood, 0–20 stone, 0–10 meat + 0–2 random items
- TRADER: wood 10, planks 5, axe 1
- BLACKSMITH: gold 20, stone 10, bone_sword 1, axe 2
- MINER: stone 5, pickaxe 1
- LUMBERJACK: wood 5, axe 1

**Doubling / Merging**
- Same type + level entities in same zone can merge → `_double` variant
- Merged inventory combines both; level stays same
- Hard cap: 15+ same type in zone → singles absorbed into doubles (double gains level)
- Doubles can split back when population is low (probability check each tick)
- Doubles process same AI as singles (skeleton doubles take daylight damage, etc.)

---

## NPC AI & Behaviors

**AI State Machine** (5 states)

| State | Typical Duration | Behavior |
|---|---|---|
| idle | 90 ticks | Stand still; energy regens 2/tick |
| wandering | 120 ticks | Random walk; energy drains 2/step |
| targeting | 180 ticks | Move toward target |
| combat | 120 ticks | Adjacent attack rolls |
| flee | 120 ticks | Move away from threat |

State transitions: `update_entity_ai_state()` rolls probability table (aggressiveness, passiveness, idleness, flee_chance, combat_chance) — only changes every 1–3 ticks via ai_state_timer.

**Energy Gate**: probabilistic idle scaling — `random.random() > energy/max_energy` — NPCs with low energy are increasingly likely to idle each update. Bypassed during flee.

**Movement Rate Limiter**: `interval = max(5, round(1 / (0.034 × speed)))` ticks between grid steps (~29 ticks at speed=1.0). Prevents render lag.

**Memory Lane**: 8–25 cells remembered; avoids recently visited positions. Clears half on 3+ consecutive failed wander attempts.

**Behavior-Driven Actions** (NPC_BEHAVIORS table in data/entities.py)

| NPC | Rate | Actions |
|---|---|---|
| FARMER | 30% | Harvest CARROT2/3 (40% success), till GRASS/DIRT (25%), plant seeds (30%) |
| LUMBERJACK | 50% + 2%/nearby tree | Chop trees (85% success), build HOUSE (5%/35%), place CAMP |
| MINER | 65% | Mine STONE/IRON_ORE (80% success), build WELL (2%) |
| GUARD | 95% aggression | Patrol center lanes, hunt hostiles, build cobblestone paths |
| TRADER | 60% | Travel zone exits, build paths (25%), trade with peaceful NPCs |
| WIZARD | varies | Seek runestones, cast spells, explore caves (180t cooldown) |
| BLACKSMITH | varies | Build FORGE, trade weapons |
| WARRIOR | 95% aggression | Patrol, hunt hostiles |

**NPC Quest System**
- 7 focus types: farming, building, mining, crafting, exploring, combat_hostile, combat_all
- Unlocked via leveling (10% per level for most; 3% for combat_all)
- 10% chance to switch focus when multiple unlocked
- Permanent base quest per type (FARMER→FARM, LUMBERJACK→LUMBER, MINER→MINE, etc.)
- Quest queue max 3 (including base); assigned quests inserted at front as keeper target

**Keeper System**

| Type | Radius | Assigned NPCs |
|---|---|---|
| 1 — Guard | 1 cell | GUARD, WARRIOR, COMMANDER |
| 2 — Patrol | 5 cells | BLACKSMITH, WIZARD, FARMER, LUMBERJACK, MINER, TRADER |
| 3 — Zone | Full zone | All others (default) |

- One keeper slot per category per zone (humanoid, animal, hostile slots)
- Auto-assigned by LoreEngine (2% per zone update)
- Keepers never leave domain; immune to structure eviction; no night sheltering
- Cross-zone pursuit: routes to exit, crosses seamlessly
- `resolve_keeper_target()` refreshes live position each tick

**Structure Entry/Exit**
- CAVE/MINESHAFT: requires combat/targeting confirmed interior target
- HOUSE/other: 10% random chance when adjacent
- Exit: 60% chance per zone update
- Keepers: never exit; overflow NPCs (>3) have 10% chance per extra to seek exit

**Peaceful NPC Migration**
- 5% chance if duplicate type in zone (population balancing)
- Raid survivors: highest-level entity → WARRIOR (60%)

---

## Combat System

**Player Combat**
- Melee on adjacent cell (Space key when weapon equipped)
- Base damage: 5 + level
- Blocking: 90% damage reduction (B key toggle)

**Weapon Damage**

| Weapon | Damage |
|---|---|
| Pickaxe | +4 |
| Axe | +5 |
| Stone pickaxe | +8 |
| Stone axe | +10 |
| Club | +8 |
| Bone sword | +15 |
| Iron sword | +20 |
| Enchanted sword | 25 total |
| Enchanted axe | 20 total |
| Magic stone | 12 |
| Magic wand | 10 |

**NPC Combat**
- Detection radius: 8 cells
- Damage: `strength // 5` (level-scaled) + weapon bonus + weapon durability bonus + 1.2× hostile multiplier
- Flee when health low; flee_chance scales by threat
- Flee exit: `recently_attacked < 30 ticks` AND nearest enemy within 5 cells (tightened from 60t/8 cells)
- Counterattack (non-combat NPCs): 10%

**Favor System**
- Every NPC has a `favor` score: −100 to 100
- Default: 0 for peaceful NPCs, −50 for hostiles
- Decreases on player attack: −5/hit, −20/kill
- Increases via gift giving (Shift+G while inspecting NPC)
- Displayed when inspecting NPC alongside faction label

**Equipment Panel** (T key, alongside Tools tab)
- Slots: Weapon, Off-hand, Armor, Ring ×2, Amulet
- Stats auto-calculated in combat rolls
- Click equipment slot then item to equip

**Follower System**
- `self.followers` list: entity IDs
- `self.follower_items` dict: {entity_id → item_name} for death cleanup
- Followers never targeted by player attack or friendly NPCs
- Cannot be merged into doubles
- Death handler uses `follower_items.pop(entity_id, None)` for cleanup
- **Energy cost**: each active follower reduces player `max_energy` by 1; recalculates on add/remove (`systems/enchantment.py`)

**Item XP & Durability** (NPC items only)
- Each item in an NPC's inventory has `item_xp[item_name]` and `item_durability[item_name]` dicts on the entity
- Level formula: `item_level = 1 + item_xp // 100` (same as NPC formula)
- On item level-up: durability resets to `0.5 × new_level`; name announcement printed
- **Weapons**: gain 1 XP per attack; durability starts at 0.75 and decays −0.01 per attack to 0; durability bonus is added to damage each attack
- **Armor pieces**: gain 1 XP each time the wearer takes a hit
- **Wizard spells**: gain 1 XP each time `cast_wizard_spell()` fires
- Persisted via `save_load.py`; graceful fallback for entities without attributes (legacy save compatibility)

---

## Sound System

**NPC Combat Creature Sounds** (`ai/actions.py` — `_ENTITY_SOUND` dict)
- WOLF → `wolf_sound` pool
- GOBLIN / BANDIT → `goblin_sound` pool
- BAT → bat sound pool
- SKELETON → skeleton sound pool
- Others → `sword_swing` pool
- Triggered in `find_and_attack_enemy()` on successful attack roll

**Ambient Presence Sounds** (`npc_ai.py`)
- WOLF: growl every ~300 ticks when player within 6 cells (`_ambient_sound_timer`)
- GOBLIN: growl every ~200 ticks when player within 6 cells

---

## Items

**Complete Item List**

| Category | Items |
|---|---|
| Resources | wood, stone, iron_ore, iron_ingot, gold, bones, fur, meat, carrot, grass, dirt, sand, soil, water_bucket, deep_water_bucket |
| Tools | axe, hoe, shovel, pickaxe, bucket, stone_pickaxe, stone_axe, watering_can |
| Weapons | bone_sword, club, iron_sword, enchanted_sword, enchanted_axe |
| Magic | star_spell, magic_stone, magic_wand, rain_spell, day_spell, keeper_spell |
| Actions | shove |
| Building | wall, planks, floor, sandstone, cobblestone, chest, well, forge |
| Farming | seeds, carrot1, carrot2, carrot3, tree_sapling, tree1, tree2, flower |
| Vegetation | bush |
| Materials | rope, leather, leather_armor |
| Food | cooked_meat, stew |
| Special | skeleton_bones (summons skeleton follower) |
| Runestones | lightning_rune, fire_rune, ice_rune, poison_rune, shadow_rune |
| Ore/Stone | iron_ore, iron_ingot, stone_house, ruined_sandstone_column, cactus, barrel |
| Dev Spells | summon_X, transform_X (22 NPC types each) |

**Item Decay** (probability per zone update)
- meat: 10%
- bones: 5%
- carrot: 3%
- All dropped items: 1% (general ground decay)

**E-Key Pickup System — Important Gotcha**
`pickup_cell_or_items()` in `systems/crafting.py` (~line 570) uses a **hardcoded `exact_pickup_map` dict** — it does NOT read from `CELL_PICKUP`. Any new pickable cell requires updates to **three** places:
1. `CELL_PICKUP` in `constants.py`
2. `CELL_PICKUP` in `data/cells.py`
3. `exact_pickup_map` in `systems/crafting.py`

---

## Crafting

**All Recipes (2-item, order-independent) — 28 total**

| Input A | Input B | Output |
|---|---|---|
| wood | stone | stone_pickaxe |
| wood | wood | planks |
| stone | stone | shovel |
| wood | hoe | hilt |
| hilt | bones | bone_sword |
| hilt | bone | bone_sword (alt — `bone` also accepted) |
| hilt | stone | stone_axe |
| hilt | fur | club |
| axe | wood | planks |
| planks | planks | chest |
| wood | bucket | watering_can |
| carrot | carrot | seeds |
| grass | grass | rope |
| star_spell | stone | magic_stone |
| star_spell | wood | magic_wand |
| star_spell | bone_sword | enchanted_sword |
| star_spell | stone_axe | enchanted_axe |
| star_spell | bones | skeleton_bones |
| fur | fur | leather |
| leather | leather | leather_armor |
| meat | meat | cooked_meat |
| carrot | meat | stew |
| stone | planks | wall |
| planks | dirt | floor |
| wood | sand | sandstone |
| iron_ore | iron_ore | iron_ingot |
| iron_ingot | hilt | iron_sword |
| iron_ingot | iron_ingot | iron_sword (alt) |

---

## Quest System

**11 Quest Types**

| Type | Description |
|---|---|
| FARM | Build/tend a farm |
| HUNT | Hunt down a specific creature |
| SLAY | Defeat a type of enemy |
| EXPLORE | Find a location |
| GATHER | Collect specific resources |
| LUMBER | Chop trees |
| MINE | Mine stone/ore |
| RESCUE | Assist an NPC |
| SEARCH | Find an item or weapon |
| COMBAT_HOSTILE | Hunt hostile NPCs only |
| COMBAT_ALL | Fight any entity (requires friendly fire) |

**Mechanics**
- Active quest selected from available list; quest arrow points to target
- Entity-based quests track `target_entity_id`, `target_zone`, `progress`; completion detected when `health ≤ 0`
- XP reward: `target_level × 10`; cooldown 300 ticks before new quest
- Lore text generated by LoreEngine
- Quest HUD: live target HP, zone/cell coordinates

**NPC Interaction**
- Shift+Q: get or turn in quest with inspected NPC
- Shift+A: assign player's active quest to NPC (becomes keeper target)
- Shift+T: trade inventory with NPC

---

## Faction System

**Peaceful Factions**
- 10 color names × 10 symbols = 100 possible combinations
- WARRIOR/COMMANDER/KING form and join factions
- Every COMMANDER guaranteed a named faction
- Faction registry syncs each lore cycle (600 ticks)
- Zone control tracked; max size enforced

**Hostile Factions**
- Goblins/Bandits form clans: hostile color + hostile noun (Shadow Fang, etc.)
- Level 2+ hostiles have per-lore-cycle chance to form faction (scales with level)
- Coordinate raids and territory expansion

**Persistence**
- `self.factions`: {faction_key → {name, warriors[], zones[], hostile_flag}}
- Saved/loaded; post-load sync scans all entities to re-register any gaps

---

## Domain System

Zones are grouped into two overlapping types of domains: **biome domains** and **faction domains**. Both use BFS-based contiguity detection.

**Biome Domains**
- Contiguous zones sharing the same biome type are merged into a single biome domain
- Each domain has a generated name (e.g. "Iron Hills", "Thornwood") shared by all its member zones
- Managed by `update_biome_domain(zone_key)` in `world/zones.py`; called whenever a zone's biome shifts
- When a zone leaves a domain: remaining zones are contiguity-checked; isolated fragments become new domains with fresh names
- When same-biome neighbors exist: zones merge into the largest neighbor domain (or form a new one)
- Single-zone domains get re-rolled names when they shrink to one member
- Per-zone tracking: `screen['biome_domain_id']`

**Faction Domains**
- Contiguous zones under the same `controlling_faction` are grouped into faction domains
- Domain name = faction name + first zone name in group
- Rebuilt from scratch on any zone faction-control change via `update_faction_domain(faction_name)` in `world/zones.py`; triggered by `systems/factions.py`
- BFS groups all controlled zones into contiguous fragments; each fragment becomes a separate faction domain
- Per-zone tracking: `screen['faction_domain_id']`

**Data Structure**
- `self.domains[domain_id] = {'name', 'type' ('biome'|'faction'), 'zones' (set of zone keys), 'biome'/'faction'}`
- Saved/loaded via `systems/save_load.py`
- Visible in dev overlay (Shift+I)

---

## Chest & Loot System

**NPC Chest Placement**
- NPCs dump inventory when any stack > 20 items (60% chance per zone update)
- First tries to fill an adjacent existing chest
- Only places a new chest if no chest within 5 cells (prevents clustering)
- Placed chest initialized with entity's full inventory; entity inventory cleared

**Chest Merging/Consolidation**
- Chests within 5 cells merge contents into the chest with the most items
- Secondary chests emptied (decay quickly)

**CHEST ↔ EMPTY_CRATE Swap**
- Chests with no items: immediately swap to EMPTY_CRATE cell each zone update
- EMPTY_CRATE with items in chest_contents: immediately swap back to CHEST
- EMPTY_CRATE is interactable (spacebar opens same chest handler) and E-key pickable (returns chest item)
- EMPTY_CRATE protected from biome overwrite

**Chest Destruction**
- Scatters contents on ground
- Empty chests leave nothing (no plank drop)

**Loot Tables**

| Chest | Loot |
|---|---|
| HOUSE | Gold 5–20 (80%), Wood 3–10 (60%), Carrot 1–5 (50%), Axe (20%) |
| CAVE | Gold 10–50 (90%), Stone 5–15 (70%), Bones 1–3 (50%), Stone pickaxe (30%), Iron ore 1–3 (40%) |
| CAVE_DEEP | Gold 50–200 (100%), Enchanted sword (40%), Leather armor (30%), Magic stone (20%), Iron ingot 1–2 (30%), Iron sword (20%) |

---

## Enchantment System

**Star Spell**
- Targets cells: freezes growth/decay for duration
- Targets entities: slows/immobilizes
- Legendary item names generated on enchanted tools

**Runestones**: lightning/fire/ice/poison/shadow — 3 damage each

**Keeper Spell** (`systems/enchantment.py`)
- `keeper_spell` — cast on inspected NPC (L key); assigns them as zone keeper anchored to player's current cell
- Uses existing keeper system: sets `entity.keeper=True`, `keeper_type` from KEEPER_TYPE_BY_ENTITY, `keeper_target_pos` at player position
- Guards: no-op if target already a keeper or is a follower
- Available in starting inventory for testing

**Dev Spells** (`systems/enchantment.py`)
- `summon_X` — spawns NPC of type X adjacent to player (22 NPC types)
- `transform_X` — swaps player sprite to NPC type X appearance; recast reverts
- Sprites generated at startup via `create_dev_spell_sprites()` in `entity.py`
- Casting: L key with spell selected in magic/items tab

---

## NPC Trade System

**NPC-to-NPC Passive Barter** (`ai/actions.py:try_npc_trade`)
- All peaceful NPCs have a 2% chance per update tick to swap one random non-spell item with a nearby peaceful NPC (within 3 cells)
- Exchange is symmetric — each entity gives one item, each receives one
- Background economy: redistributes resources between zones over time as traders travel

**Gold-Drop Trade** (`ai/actions.py:process_npc_trade`)
- Fires when an NPC picks up gold the player has dropped while adjacent
- Per-type exchange rates: FARMER→2 carrots/gold, LUMBERJACK→3 wood/gold, MINER→3 stone/gold
- GUARD/GOBLIN accumulate gold until threshold then offer to become followers
- TRADER opens a UI recipe panel showing fixed trade recipes

**Player Inventory Trade Window** (`game_core.py:open_npc_trade_window`)
- Trigger: Shift+T while inspecting an NPC
- Opens a grid UI above the NPC showing all their current inventory items with randomized gold prices (5–10 per item, set fresh on open)
- Click a slot to buy: player pays gold, item moves to player inventory
- Window closes when NPC's inventory is depleted or player moves away
- Backed by `trader_display` dict; click handled by `handle_npc_trade_click`

**N-Key Trade Interaction** (`ai/actions.py:npc_trade_interaction`)
- Trigger: N key while adjacent to a TRADER NPC
- Opens a fixed-recipe panel (leather/leather_armor/planks for gold); executes the first affordable recipe on repeat press
- Older system distinct from the Shift+T inventory window

---

## Structure System

**House Interior**
- FLOOR_WOOD tiles, WALL borders
- 1 NPC resident, 1 CHEST (HOUSE loot table)
- STAIRS_UP/DOWN for entry/exit
- Night shelter for NPCs

**Cave Interior**
- CAVE_FLOOR, CAVE_WALL tiles
- 1–3 depth levels; deeper = more hostile spawns, better loot
- IRON_ORE spawns at depth 1 (3%) and depth 2+ (7%)
- Hostile spawns: 5% per zone update

**Mineshaft**: Cave variant, higher mineral/loot density

**STONE_HOUSE, CAMP, FORGE, BARREL**: Static structures; CAMP grants 2× healing to nearby NPCs

---

## Raid System

- Trigger: 6+ entities in zone + 5-min interval + 8% chance
- Post-raid: highest-level entity → WARRIOR (60%)
- Hidden cave: 20% spawn chance during raid
- Raid tracking per zone: `zone_last_raid_check`

---

## Save / Load System

**Persisted State**
- Player: position, health, XP, inventory, all stats, screen position
- All zone cells (every screen key)
- All entities: full state including inventory, health, level, faction, keeper, quests
- Quests: target_entity_id, target_zone, progress, status
- Factions: full registry
- Enchantments: target entity/cell, duration
- Dropped items: buried_items, dropped_items per zone
- Weather: zone_last_rain per zone
- Day/night cycle state
- follower_items dict
- NPC keeper assignments: zone_keepers

**Load Reconciliation**
- Entity health clamped to max_health
- Ghost entities re-registered: any entity in `self.entities` missing from `screen_entities` recovered
- Faction registry synced post-load
- All persisted zone keys re-instantiated

---

## Time Pass Simulation

- Triggered on: player death (150–250 years), new game (100–200 years)
- Runs full probabilistic zone updates every tick (bypasses 30-tick gate)
- `time_pass_speed = 20×` multiplier on NPC XP/damage/success
- Year counter advances at 20× rate
- 15 update cycles per rendered frame (keeps death screen responsive)
- All loaded zones receive rain and aging during simulation

---

## Autopilot

**Design**: Possession model — real NPC proxy spawned at player position, driven by NPC AI

**Behavior**
- Off by default; Shift+A toggle (any other input disengages)
- Quest rotation: 80% on completion + forced every 30s
- Mirrors proxy inventory to player every 60 ticks
- Zone travel: 35% chance per nudge cycle
- Stuck-exit: after 5 nudges to same exit → wander 10 cycles
- Obstacle clearing: stuck 60+ ticks → try chop_tree / mine_rock
- Opportunistic harvest: every 30 ticks, scans adjacent cells
- Periodic: every 300 ticks → random tool / spell / drop / inspect NPC

**Quest → Proxy Role Mapping**

| Quest | Proxy NPC |
|---|---|
| FARM | FARMER |
| GATHER / LUMBER | LUMBERJACK |
| MINE | MINER |
| HUNT / SLAY / COMBAT_HOSTILE | WARRIOR |
| EXPLORE | TRADER |
| SEARCH / RESCUE | WIZARD |
| Default | FARMER |

---

## Debug & QA Systems

**BugCatcher** (`debug/bug_catcher.py`)
- JSON-lines structured logger; in-memory buffer flushed every 300 ticks
- 2 MB rolling trim; clears on game start
- Output: `debug/bug_catcher.log`

**Watchdog** (`debug/watchdog.py`)
- Rotates across 9 sample categories per 300-tick cycle: entities, cells, zones, player, structures, followers, npc_actions, keepers, npc_quests
- Integrity checks for anomalies (frozen entities, ghost IDs, etc.)
  - Check 6: entity orphaned from screen_entities (in entities dict but missing from any bucket)
  - Check 7: entity stuck targeting EXIT or structure entrance cell for extended period
  - Check 8: entity with in_subscreen=True still in overworld screen_entities bucket
- Rolling 60s/120s backup auto-saves

**AUTO_DEBUG Mode** (`main.py`, `debug/auto_debug.cfg`)
- Enable: write `True` to `debug/auto_debug.cfg` (git-ignored; never committed)
- Headless autopilot session: new game or continue save, 2–5 min duration
- Run counter in `debug/auto_debug_state.json`
- Auto-save and quit at session end

**Freeze Detector** (`game_core.py`)
- Every 300 ticks: logs any entity in player zone with `idle_timer > 0`

**Dev Overlay** (`ui/dev_screen.py`)
- Shift+I: zone info, entity counts, follower list, domain assignments, balance panel

---

## Ghost Entity Reconciliation

- `reconcile_screen_entities()` in `systems/combat.py`
- Scans `self.entities`; re-registers any entity absent from `screen_entities`
- Called at: load time, respawn, every 600 ticks during play

---

## Sound System

**Loaded / Wired**
- Sword swing pool: `sword_swing`
- Footstep pools: `footstep_water`, `footstep_dirt`
- Pickup: `on_pickup()`, inventory select: `on_inventory_select()`
- Ambient music: fades in/out at dawn transitions

**Spatial Audio Infrastructure** (`SoundManager.play_sfx_spatial`)
- Volume = `sfx_volume × max(0, 1 − dist/max_dist)`, max_dist=8 Manhattan cells
- Per-tick budget: 2 NPC spatial sounds max (tracked via `_npc_sounds_this_tick`)
- Only active during gameplay (not time-pass sim)
- NPC footsteps routed through spatial system

**Creature / Ambient Sounds**
- Ambient timers on NPCs: WOLF, GOBLIN, BAT, SKELETON — periodic presence sounds
- Combat sound mapping: entity type → sound pool (partially wired; full mapping pending)

---

## Rendering & Sprites

- Individual PNG files loaded from `sprites/` directory + sprite sheet
- 40px cell size, RGBA transparency
- 10 GRASS visual variants
- Entity animation: 4 directions × 3 frames (still / 1 / 2), 10 ticks/frame
- Fallback: colored rectangle + symbol label for missing sprites
- Sprite lookup: `{type}_{facing}_{frame}` → fallback to `_{facing}_still` → fallback to color block
- Dev spell sprites generated at startup from NPC base sprites

**Sprite Override Map** (entity.py `create_dev_spell_sprites`)
- `termite` → `yellow termite`, `bat` → `black bat`, `black_spider` → `blackspider`, `red_bird` → `red bird`

**Explicit Sprite Filename Map** (game_core.py)
- IRON_ORE → ironore.png, WELL → well.png, iron_sword → sword.png
- RUINED_SANDSTONE_COLUMN, STONE_HOUSE, CACTUS, BARREL, BUSH, EMPTY_CRATE → matching PNG
- FLOWER_PATTERN1/2/3 — use color block fallback (no dedicated sprites yet)

---

## Key Balance Constants

| Constant | Value |
|---|---|
| Screen size | 960×720 (24×18 grid, 40px cells) |
| FPS | 60 |
| Day / Night duration | 150 ticks each |
| Night overlay alpha | 40 |
| Hunger decay (base) | 0.02/tick |
| Thirst decay (base) | 0.015/tick |
| Humanoid hunger multiplier | 6× |
| Humanoid thirst multiplier | 2× |
| Starvation damage | 1 HP/tick |
| Dehydration damage | 1.5 HP/tick |
| Base healing | 1.5 HP/tick |
| Camp healing multiplier | 2× |
| House healing multiplier | 3× |
| Quest cooldown | 300 ticks |
| Quest XP | target_level × 10 |
| Raid trigger | 6+ entities, 8% chance, 5-min interval |
| Keeper auto-assign | 2% per zone update |
| Zone soft cap | 200 overworld zones |
| NPC update frequency | 30 ticks (0.5 s) |
| NPC move interval | ~29 ticks at speed 1.0 |
| Chest dump threshold | any stack > 20 items |
| Chest nearby guard radius | 5 cells |
| Butterfly flower growth rate | 4% per AI update on GRASS/DIRT |
| Skeleton daylight damage | 1 HP/update |
