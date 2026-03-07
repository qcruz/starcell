# StarCell — Development Strategy & Branch Map

> **Maintained by @qcruz.**
> This document defines commit discipline, branch naming, the full feature branch roadmap, and work session sizing. It is a living plan — variance is expected, but return to it after each session to stay on track.

---

## 1. Commit Discipline

### Core Rule
**One logical change per commit.** If you can describe a commit with "and", it should be two commits.

### When to Commit
Commit at the completion of each of these:
- A new data entry (one new NPC type, one new item, one new recipe)
- One function or method added or modified
- One UI element wired up
- One bug fixed
- Before switching to a different subsystem

### Commit Message Format
```
System: short imperative description

Optional body if context is needed.
```

**Examples of good commits:**
```
Audio: add pygame.mixer init and volume constants
Audio: add ambient music loader with biome-keyed track map
Audio: wire forest ambient track to zone entry event
NPC: add Werewolf entity type to ENTITY_TYPES and constants
NPC: add Werewolf day/night transformation state in npc_ai
Combat: add Poisoned status effect and decay timer
Combat: apply Poisoned on goblin hit
```

**Examples of bad commits (too broad):**
```
Audio system
Add new enemies and status effects
Lots of fixes
```

### What Never Goes on `main`
- Broken or untested code
- Partial features mid-implementation
- Debug prints left in intentionally

---

## 2. Branch Structure

```
main          ← stable, tested releases only; tagged at milestones
└── dev       ← integration branch; features merge here when complete
    └── system/subsystem-name   ← all feature work
```

### Naming Convention
`system/subsystem-specific-work`

Examples:
- `audio/foundation`
- `combat/status-effects`
- `entities/werewolf`
- `content/desert-biome-pass`

### Branch Lifecycle
1. Branch off `dev`: `git checkout -b audio/foundation dev`
2. Commit small and often while working
3. When complete and tested, merge back to `dev`
4. Periodically, when `dev` is stable, merge `dev` → `main` and tag a version

---

## 3. Session Sizing

Work sessions are estimated in two units:

| Size | Time | What fits |
|---|---|---|
| **Micro** | 30–60 min | One data entry, one small function, one bug fix |
| **Standard** | 1–2 hrs | One subsystem chunk, one complete mechanic |
| **Extended** | 2–4 hrs | Foundation/scaffolding work that other features depend on |

Sessions naturally produce 3–10 commits. If a session produces 1 commit it was too big. If it produces 20+ it was probably too scattered.

---

## 4. Full Branch Roadmap

Organized by system. Each entry shows: branch name → what it delivers → estimated session size.

Work these in **cycles** (see Section 5) rather than finishing one system before starting the next. This keeps all game areas moving and avoids bottlenecks.

---

### AUDIO
Foundation must land before any sub-branches.

| Branch | Delivers | Size |
|---|---|---|
| `audio/foundation` | pygame.mixer init, volume constants, biome/event hook points, mute toggle | Extended |
| `audio/ambient-music` | Long ambient tracks keyed to biome; crossfade on zone change | Standard |
| `audio/combat-sfx` | Hit, death, and block sound effects wired to combat events | Standard |
| `audio/spell-sfx` | Sound per spell type (fireball crack, ice chime, lightning boom) | Standard |
| `audio/footstep-sfx` | Footstep sounds varying by cell type (grass, stone, water) | Standard |
| `audio/npc-vocal-sfx` | Short NPC audio cues: combat bark, greeting, pain | Standard |
| `audio/dynamic-intensity` | Music intensity scales with nearby hostile count | Standard |

---

### COMBAT DEPTH

| Branch | Delivers | Size |
|---|---|---|
| `combat/status-effects` | Poisoned, Burning, Frozen, Stunned — timers, tick damage, cure items | Extended |
| `combat/elemental-system` | Element enum, resistance/weakness table per entity type, damage multipliers | Extended |
| `combat/elemental-weapons` | Elemental weapon properties, rune integration into full element system | Standard |
| `combat/ranged-weapons` | Bow + arrow item, projectile system, ammo consumption | Extended |
| `combat/thrown-weapons` | Rocks, knives, bombs; one-use or retrieval; bomb cell destruction | Standard |
| `combat/equipment-slots` | Equipment panel UI, weapon/armor/ring slots, passive stat bonuses | Extended |
| `combat/armor-types` | Cloth, leather, chain, plate — defense values, entity compatibility | Standard |
| `combat/stealth` | Crouch/sneak mode, detection radius reduction, sneak attack bonus | Standard |

---

### ENTITIES — NEW HOSTILE

| Branch | Delivers | Size |
|---|---|---|
| `entities/golem` | Golem type: slow, high defense, attacks only when attacked; blocks entries | Standard |
| `entities/troll` | Troll: health regen, weak to fire; forest/cave spawns | Standard |
| `entities/zombie` | Zombie: slow, contagion on hit, graveyard spawns | Standard |
| `entities/ghost` | Ghost: passes through walls, immune to physical, weak to holy | Standard |
| `entities/werewolf` | Werewolf: human NPC by day, transforms at night; weak to silver | Extended |
| `entities/witch` | Witch: ranged spell attacks, curse on hit | Standard |
| `entities/mimic` | Mimic: chest disguise, attacks on open | Standard |
| `entities/slime` | Slime: splits into smaller slimes on death | Standard |
| `entities/dragon` | Dragon: boss tier, fire breath ranged attack, hoard loot | Extended |

---

### ENTITIES — BOSSES

| Branch | Delivers | Size |
|---|---|---|
| `entities/boss-rooms` | Boss room generation in deep dungeon; high-health enemy + guaranteed rare drop | Extended |
| `entities/boss-lair-actions` | Environmental hazard trigger once per zone update (falling rocks, rising water) | Standard |
| `entities/dragonknight` | Dragonknight: fire breath AoE + heavy melee; fort/keep spawn; rare armor drop | Extended |
| `entities/ancient-mechanica` | Mechanica: shock chain attacks, ruins spawn, unique schematic drop | Extended |

---

### ENTITIES — ANIMALS & LIVESTOCK

| Branch | Delivers | Size |
|---|---|---|
| `entities/sheep-wool` | Sheep produces wool over time; wool item; cloth crafting | Standard |
| `entities/cow-chicken` | Cow → milk; chicken → eggs; artisan goods pipeline | Standard |
| `entities/horse-mount` | Horse tameable, rideable, 2× movement speed, barn required | Extended |
| `entities/tameable-cat` | Cat: tameable via favor; hunts small creatures; reduces pest spawns | Standard |
| `entities/tameable-dog` | Dog: tameable; barks on hostile zone entry; assists in combat | Standard |

---

### STRUCTURES & PROGRESSION

| Branch | Delivers | Size |
|---|---|---|
| `structures/house-upgrade-chain` | House upgrades to stone house given lumberjack + miner conditions | Standard |
| `structures/fort` | Stone house + blacksmith → fort; guards spawn; sprites | Standard |
| `structures/castle` | Fort progression → castle; interior guards; King retreats inside | Extended |
| `structures/castle-defense-event` | Zone attacked → guards + commander spawn from castle | Standard |
| `structures/tavern` | Tavern structure; NPC gathering; rest/skip time; Tavernkeeper | Extended |
| `structures/temple` | Temple/shrine; visit buff; unique quest giver; Identify curse | Extended |
| `structures/beehive` | Beehive: honey production; bee swarm stings hostiles nearby | Standard |
| `structures/campfire` | Campfire: craftable; heals nearby; cooks food; NPCs gather at night | Standard |
| `structures/staircase-sprites` | Distinct descend/ascend graphics per depth level | Micro |
| `structures/chest-variants` | Labeled, locked (key required), trapped chests | Standard |

---

### SEASONAL SYSTEM

| Branch | Delivers | Size |
|---|---|---|
| `seasons/foundation` | Season enum, 7-day cycle, calendar tick counter, HUD day/season display | Extended |
| `seasons/crop-integration` | Crop growth rates and spawn rules keyed to season | Standard |
| `seasons/winter-effects` | Snow overlay, water→ice, reduced crop growth, NPC shelter behavior | Extended |
| `seasons/seasonal-events` | Seasonal quest triggers and world events | Standard |

---

### SPELLS

| Branch | Delivers | Size |
|---|---|---|
| `spells/rain` | Rain toggle spell for current zone | Micro |
| `spells/calcify` | Freeze NPC in place / turn to stone | Micro |
| `spells/charm` | Toggle NPC between friendly and hostile | Micro |
| `spells/heal-extended` | Full stat restore; reverse absorbs HP from target; life drain | Standard |
| `spells/spectral-state` | Player briefly passes through solid cells | Standard |
| `spells/fireball` | Ranged projectile; fire cell type; spread to adjacent flammable | Extended |
| `spells/blizzard` | AoE frost; slows all entities in zone | Standard |
| `spells/lightning` | Instant high damage; chains to metal-wearing nearby entities | Standard |
| `spells/summon` | Temporary powerful ally based on quest focus | Standard |
| `spells/teleport` | Instant travel to visited zone or waypoint | Standard |
| `spells/barrier` | Creates temporary impassable wall cell | Micro |
| `spells/utility` | Identify (reveal item stats/curses), Detect (highlight hidden rooms/traps/loot) | Standard |
| `spells/bard-song` | Passive AoE buff to all friendly entities in zone | Standard |

---

### DUNGEON MECHANICS

| Branch | Delivers | Size |
|---|---|---|
| `dungeon/keys-and-locks` | Small key item, locked door cell, key drops from enemies and chests | Standard |
| `dungeon/boss-key` | Boss key item, boss room door cell | Micro |
| `dungeon/map-item` | Dungeon map item reveals current level layout | Standard |
| `dungeon/compass-item` | Compass item shows chest locations on dungeon map | Micro |
| `dungeon/traps` | Floor spikes, arrow traps; pressure plate trigger cell | Extended |
| `dungeon/hidden-rooms` | Pushable wall cells reveal secret passages | Standard |
| `dungeon/puzzle-rooms` | Pressure plates, levers, locked doors, push-block puzzles | Extended |
| `dungeon/biome-themes` | Crypt, mine, ice cave, volcanic cave — themed generation | Extended |

---

### FISHING

| Branch | Delivers | Size |
|---|---|---|
| `fishing/foundation` | Cast mechanic from water-adjacent cell; catch timer; rod item | Extended |
| `fishing/fish-varieties` | Fish types keyed to biome, season, time of day; rare collectibles | Standard |
| `fishing/fishing-pond` | Fishing pond structure; place fish to farm | Standard |

---

### ANIMAL HUSBANDRY

| Branch | Delivers | Size |
|---|---|---|
| `animals/barn-pen` | Barn/pen structure; houses animals; prevents wandering | Standard |
| `animals/production-goods` | Timed production: milk, eggs, wool per animal type | Standard |
| `animals/needs-system` | Animals need food/water; production declines without it | Standard |

---

### COOKING & FOOD

| Branch | Delivers | Size |
|---|---|---|
| `food/cooking-station` | Campfire/cooking pot as crafting station type | Standard |
| `food/recipes-foundation` | Flour from wheat, bread, cheese from milk, honey goods | Standard |
| `food/stat-buffs` | Cooked food grants temporary buffs (speed, strength, max HP, luck) | Standard |
| `food/recipe-book` | Recipe book UI — tracks known and undiscovered recipes | Standard |

---

### FORAGING

| Branch | Delivers | Size |
|---|---|---|
| `foraging/wild-spawns` | Mushrooms, berries, herbs in forest/cave zones; biome/season rules | Standard |
| `foraging/skill-perk` | Foraging skill increases yield and reveals rare forage | Standard |

---

### SOCIAL & DIALOGUE

| Branch | Delivers | Size |
|---|---|---|
| `social/gift-giving` | Gift item to NPC to increase favor; preferred gift table per type | Standard |
| `social/npc-schedules` | NPCs follow daily routines (field at dawn, tavern at night, temple on rest day) | Extended |
| `social/rumor-system` | NPCs at taverns share zone event info, rare loot hints, hidden locations | Standard |
| `social/guild-membership` | Join faction guilds; perks, special quests, unique items | Extended |
| `social/npc-birthdays` | Calendar events; special interactions on named days | Standard |

---

### CHARACTER PROGRESSION

| Branch | Delivers | Size |
|---|---|---|
| `character/ability-scores` | STR, DEX, CON, INT, WIS, CHA stats; grow with use, decay over time | Extended |
| `character/class-archetypes` | Class choice at new game; starting equipment + perk unlock bias | Standard |
| `character/perk-trees` | Perk system per activity; tiered unlocks; combat/craft/farm/explore/magic | Extended |
| `character/luck-system` | Daily luck value; affects drop rates, encounter chance, fishing quality | Standard |

---

### REPUTATION & FAVOR

| Branch | Delivers | Size |
|---|---|---|
| `reputation/hostile-score` | Global -100 to 100 score; updated by attacking peaceful/hostile; faction reactions | Extended |
| `reputation/favor-system` | Per-NPC -100 to 100 favorability; loyalty threshold → follower conversion | Extended |
| `reputation/bounty-system` | Attacking peaceful NPCs triggers bounty; guards pursue; temple/bribe to clear | Extended |

---

### FOLLOWER IMPROVEMENTS

| Branch | Delivers | Size |
|---|---|---|
| `followers/inventory-interaction` | Select item + Place while follower panel open → goes to follower inventory | Standard |
| `followers/auto-equip` | Follower auto-equips strongest gear type for combat/stats | Standard |
| `followers/commands` | Stay, follow, attack, retreat basic orders | Standard |
| `followers/leveling` | Followers gain XP alongside player; level up | Standard |

---

### KEEPER SYSTEM EXPANSIONS

| Branch | Delivers | Size |
|---|---|---|
| `keeper/zonekeeper` | Zonekeeper role: zone defense quests, resource collection quests | Standard |
| `keeper/tavernkeeper` | Tavernkeeper: sells food/drink, hosts rumors, rents room for rest | Standard |
| `keeper/dungeonkeeper` | Dungeonkeeper: manages dungeon difficulty, depth-based quests | Standard |
| `keeper/towerkeeper` | Towerkeeper: trains warriors, sells weapons, combat quests | Standard |
| `keeper/evergael` | Evergael: zone-exit boss; unique dialogue; drops key/artifact to unlock exit | Extended |

---

### DOMAIN SYSTEM

| Branch | Delivers | Size |
|---|---|---|
| `domain/detection` | 2×2 zone quad detection; faction label check; domain bonus application | Extended |
| `domain/contested-state` | Domain breaks on capture; visual markers on world map | Standard |
| `domain/player-influence` | Player actions shift domain control via NPC/structure aid or attack | Standard |

---

### LOREENGINE EXPANSIONS

| Branch | Delivers | Size |
|---|---|---|
| `lore/migration-events` | LoreEngine triggers NPC migration between zones | Standard |
| `lore/disaster-events` | Natural disaster events (flood, fire spread, earthquake cell destruction) | Standard |
| `lore/invasion-events` | Organized invasion/raid events from distant hostile zones | Standard |
| `lore/zone-name-generation` | Unique flavored zone/NPC name generation; zone gen influenced by name | Standard |
| `lore/prophecy-system` | Occasional prophecy hint pointing player toward rare event or item | Standard |

---

### LIFETIME & PERMADEATH

| Branch | Delivers | Size |
|---|---|---|
| `lifetime/aging-pressure` | Player gradually loses max HP as they age; permadeath pressure | Standard |
| `lifetime/vampirism` | Vampirism mechanic to extend life | Standard |
| `lifetime/fairy-fountain` | Fairy fountain structure grants life extension | Micro |
| `lifetime/philosophers-stone` | Legendary crafted item; halts aging permanently | Standard |

---

### TRAVEL & WORLD MAP

| Branch | Delivers | Size |
|---|---|---|
| `travel/world-map` | Zoomed-out view of explored zones with names and faction colors | Extended |
| `travel/waypoints` | Waypoint stone structure; teleport between owned waypoints | Standard |
| `travel/shadow-realm` | Shadow Realm portal; dark overworld mirror; stronger enemies; unique loot | Extended |
| `travel/sky-zone` | Sky/cloud zone via beanstalk or magic; unique creatures and loot | Extended |

---

### REST & TIME

| Branch | Delivers | Size |
|---|---|---|
| `rest/bed-sleep` | Craftable bed and inn room rest; skip to morning; full stat restore | Standard |
| `rest/campfire-rest` | Partial restore; shorter time skip; requires food | Standard |
| `rest/energy-system` | Actions consume energy; replenished by eating and sleeping | Extended |

---

### UI IMPROVEMENTS

| Branch | Delivers | Size |
|---|---|---|
| `ui/minimap` | Minimap or zone map overlay | Extended |
| `ui/equipment-panel` | Separate equipment display: weapon, armor, ring, amulet slots | Extended |
| `ui/help-overlay` | Context-sensitive in-game help / key reference | Standard |
| `ui/multiple-save-slots` | Multiple save slots selection on menu | Standard |
| `ui/settings-screen` | Difficulty, fullscreen/resolution, volume controls | Standard |

---

### ACHIEVEMENTS & BESTIARY

| Branch | Delivers | Size |
|---|---|---|
| `meta/achievements` | Achievement system; milestone tracking; HUD notifications | Extended |
| `meta/bestiary` | Bestiary log: entity flavor text, stats, weaknesses; filled by defeating/observing | Standard |
| `meta/collection-log` | Tracks all found items, zones explored, fish caught, recipes learned | Standard |

---

### DEBUG & BUGCATCHER

| Branch | Delivers | Size |
|---|---|---|
| `debug/auto-correction` | Tiered auto-correction responses for density/stuck/imbalance states | Extended |
| `debug/zone-density-response` | Zone too dense → re-roll or spawn termite invasion | Standard |

---

### GENETICS & SPRITES

| Branch | Delivers | Size |
|---|---|---|
| `sprites/rainbowmaker` | Sprite color randomization system; rare variant hunting | Extended |
| `genetics/npc-genetics` | Core behaviors numerically determined and mutating via Contagion System | Extended |

---

### CONTENT PASSES (Cyclic/Repeating)
These branches recur regularly as content is added in small batches.

| Branch Pattern | Delivers | Size |
|---|---|---|
| `content/npc-<name>` | One or two new NPC types (data + AI behaviors) | Micro–Standard |
| `content/biome-<name>` | New biome type (generation rules, cell types, entity spawns) | Standard |
| `content/cell-<name>` | New cell types (both `constants.py` and `data/cells.py`) | Micro |
| `content/item-<name>` | New items, recipes, loot table entries | Micro |
| `content/sprite-pass` | New sprite PNGs wired into SpriteManager | Micro |

---

## 5. Rotation Schedule

Work in **cycles** across systems rather than finishing one system before starting another. This keeps the game feeling complete at each milestone and avoids deep rabbit holes.

### Cycle Structure (repeat indefinitely)
Each cycle = roughly 4–6 sessions.

```
Cycle slot 1 — Foundation / Infrastructure
  Pick the highest-priority unstarted foundation branch from any system.
  (audio/foundation, seasons/foundation, fishing/foundation, etc.)

Cycle slot 2 — Content Pass
  One content/npc-*, content/biome-*, content/item-* branch.
  Keep these small and ship them fast.

Cycle slot 3 — Combat / Entities
  One branch from Combat Depth or New Entities.

Cycle slot 4 — World / Social
  One branch from Structures, Social, Lore, Travel, or Domain.

Cycle slot 5 — UI / Polish
  One branch from UI Improvements, Achievements, or Debug.

Cycle slot 6 — Bug Fix / Debt
  Anything from the bug backlog. No new features — fixes only.
```

### Suggested First 3 Cycles

**Cycle 1**
1. `audio/foundation` — Extended
2. `content/npc-werewolf` + `entities/werewolf` — Standard
3. `combat/status-effects` — Extended
4. `structures/campfire` — Standard
5. `ui/help-overlay` — Standard
6. Bug fix pass on dev

**Cycle 2**
1. `seasons/foundation` — Extended
2. `content/item-potions` — Standard
3. `combat/ranged-weapons` — Extended
4. `social/gift-giving` — Standard
5. `ui/minimap` — Extended
6. Bug fix pass on dev

**Cycle 3**
1. `audio/ambient-music` — Standard
2. `content/biome-volcanic-cave` — Standard
3. `dungeon/keys-and-locks` — Standard
4. `structures/tavern` — Extended
5. `meta/achievements` — Extended
6. Bug fix pass on dev

---

## 6. Milestone Tags

Tag `main` at major stable points:

| Tag | Milestone |
|---|---|
| `v0.2` | Audio foundation + status effects + seasonal foundation complete |
| `v0.3` | Dungeon mechanics + boss rooms + equipment slots |
| `v0.4` | Social systems + tavern + reputation/favor |
| `v0.5` | World map + travel + domain system |
| `v0.6` | Character progression + perk trees |
| `v1.0` | All roadmap systems implemented at foundation level |

---

*Last updated: 2026-03-06*
