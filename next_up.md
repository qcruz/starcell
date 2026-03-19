# StarCell — Next Up

> Two tiers. Claude works Tier 1 top-to-bottom without asking. Tier 2 items require explicit user sign-off before any code is written — post the item in chat, wait for a clear "go ahead."
> @qcruz manages additions and order.
>Always start by reviewing committ history for recent updates and changes from others. Reconcile project documentation (implemented features, bug report, roadmap, etc) at the begining and end of each session.
---

## Tier 1 — Autonomous

Small additions using existing systems and minimal changes to code.

- [x] Add EMPTY_CRATE cell — visual state for empty chests; zones.py swaps CHEST↔EMPTY_CRATE each update based on chest_contents; player can interact with either
- [x] Add FLOWER_PATTERN cells (3 variants) — non-solid walkable cells that rarely grow from grass in forest/plains; degrade back to grass over time; harvestable; placeable
- [x] Butterfly flower growth — when butterfly moves over GRASS/DIRT, small chance to grow it to FLOWER or FLOWER_PATTERN; doesn't grow trees
- [ ] Keeper-status spell — new spell type: cast on inspected NPC to assign them as keeper for a target cell or item; uses existing keeper system
- [ ] NPC infection system: vampirism and lycanthropy — hostile bats can infect humanoid NPCs with vampirism (transforms to BAT at night, reverts at dawn); hostile wolves can infect with lycanthropy (transforms to WOLF at night, reverts at dawn); silver weapons prevent/cure infection
- [ ] Action inventory, equipment inventory, and favor system — one session
- [ ] Add actions inventory tab (R key) — shove and other contextual action items. Start with Attack, Block, Sneak, Dig, and Talk placeholders. Actions not dropped on death, will be starting options for game actions before player has tools.
- [ ] Make actions default on spawn - 'attack', 'block' - allow player to collect resources without tools (low success chance)(actions and spells not dropped on death)
- [ ] Add NPC trait Favor: -100 to 100, default zero for peacful NPCs, default -50 for hostiles. Will increase or decrease for certain actions (we will discuss when implementing)
- [ ] Add faction standing display when inspecting NPC — show NPC favor score and faction label
- [ ] Add per-NPC favor system — -100 to 100 favorability score; reduces follower energy cost
- [ ] Add gift giving — player offers item to NPC to increase favor;
- [ ] Add energy cost for active followers — each follower reduces max energy by 30% of their max energy; recalculates on add/remove
- [ ] Add item level display in inventory UI — show level badge on leveled items in all tabs
- [ ] Add equipment panel UI — Weapon, Off-hand, Armor, Ring ×2, Amulet slots; passive stat bonuses

- [ ] Village and dungeon biome — required sprites: fence, stairs up/down
- [ ] Create village biome — VILLAGE zone type; rare spawn; clustered housing with fence cells enclosing plots, market stall, well; higher NPC density (FARMER, GUARD, BLACKSMITH, TRADER, COMMANDER, KING); guard keepers protect zone perimeter. Required sprites: fence.
- [ ] Create dungeon biome — multilevel underground structure; offshoot cave corridors in crucible layout; STAIRS_DOWN/STAIRS_UP cells connect floors; NPC difficulty and loot quality scale with depth; boss room at deepest level. Required sprites: stairs_up, stairs_down.
- [ ] Add multi-floor structures — dungeons and towers with staircase-connected floors; each floor separate structure
- [ ] Connect STAIRS_DOWN/STAIRS_UP cells between structure floors — entry/exit routing via stair cells

- [ ] More sprites, cells, NPCs, and biomes

- [ ] Skeleton doubles (and all doubles) need to process the same as their single counterparts (skeelton doubles should take constant damage during the day while outside)
- [ ] Double entities should have a chance to split back in to singles every update tick if NPC population is low enough. Split inventory, levels, quest, etc randomly for now.
- [ ] Hard cap on total number of same entity in zone - if more than 15 of the same entity type in zone, single or double, singles get 'absorbed' into doubles automatically - double entity gets level increase.
- [ ] We need to make sure chest content are still picked up by the player on interaction (spacebar)
- [ ] Add a few random items to barrels as well, picked up when interacted (same hadnling as chests, but lower quality loot table)
- [ ] When player drops items on a chest cell, they should move to the chest inventory
- [ ] When butterflys fly over base cells - high chance to grow the cell to next level - sand>dirt>grass>plant (will be adding bush and flowers, ect)(doesn't grow trees)
- [ ] Complete NPC combat creature sound mapping — verify WOLF, GOBLIN, BAT, SKELETON, BANDIT route through _ENTITY_SOUND
- [ ] Add wolf/goblin ambient presence sounds — WOLF growl every ~300 ticks within 6 cells; GOBLIN every ~200 ticks
- [ ] Add ambient rain sound during rain events — play rain_sound loop when is_raining; stop when false
- [ ] Add do_shove() — push entity in facing direction one cell; blocked by solid cells
- [ ] Add handle_npc_follow_interaction() — Shift+F on inspected NPC; 50% recruit chance - maybe an action instead? We will discuss.
- [ ] Add buried treasure — shovel digs soft cells; chance to uncover cached items; Detect spell reveals locations, dig action works as well (low success chance - takes multiple tries)
- [ ] Boost night-time hostile spawn rate slightly — BAT, GOBLIN, SKELETON have higher spawn weight at night
- [ ] Add spell energy cost — spells draw from energy pool; drain health if insufficient
- [ ] Rain affects crop growth — active rain reduces crop decay rate; speeds grass/tree spread
- [ ] Add poisoned status effect — HP drain per tick; cured by antidote or milk
- [ ] Add burning status effect — HP drain per tick; spreads to adjacent flammable cells
- [ ] Add cold status effect — immobile for duration;
- [ ] Remove dead debug prints outside autopilot.py and debug/
- [ ] Add named villains — LoreEngine occasionally designates a high-level hostile NPC with unique stat boost and artifact drop
- [ ] Wire higher NPC level → reduced hostile raid chance in zone and reduced structure destruction probability
- [ ] Port try_craft_recipe() to ai/actions.py — from autopilot; MINER and BLACKSMITH use it
- [ ] Port Autopilot AI — keeper use quest-targeting and obstacle-clearing loop; goal matches NPC archetype
- [ ] Add basic seasonal system — four seasons; season flag used by crop and weather rules
- [ ] Audit monolith methods extracted to mixins — remove duplicates from game_core.py and npc_ai.py
- [ ] Consolidate functionality — code cleanup pass

---

## Tier 2 — Needs Explicit Approval

Post the item in chat before starting. Wait for a clear "go ahead." These introduce new entity types, structure types, UI systems, or world generation systems that require design decisions.

### New Entity Types

### New Structure Types
- [ ] chance for stone house to become fort or belltower - fort spawns traveling soldiers (agressive) of the local faction, belltower spawns guards (relaxed, protect zone)
- [ ] Add Tavern structure — NPC gathering point; rest/time-skip; Tavernkeeper quests, spawn 1-2 'adventurer NPCs (start off with hogh player favorability, will follow player from level 1, low follower energy cost (~30 energy reduction while following)).
- [ ] Add Blacksmith structure — dedicated smithing building; forge enables higher level weapons and echanted weapons.
- [ ] Add Crypt structure — sealed underground zone; undead spawns; Vampire or Lich boss room at depth
- [ ] Add Temple/Shrine structure — visit grants buff; Identify curse; unique quest giver
- [ ] Add Ancient Ruins structure type — crumbling zone; Golem and Mechanica guardians;
- [ ] Add Library/Archive structure — Wizard Keeper; Tome items teach rare spells; ghost scholar guards
- [ ] Add oasis structure to desert zones — water source cell cluster in desert; NPCs and animals seek it
- [ ] Add waypoint stone structure — player teleports between owned waypoints; significant time passes on use
- [ ] Add barn/pen structure — houses livestock; prevents animal wandering

### New UI Systems
- [ ] Add world map view — zoomed-out explored zone overlay with names and faction colors
- [ ] Add achievement system — milestone tracking; HUD notification on unlock

### New World and Game Systems
- [ ] Expand Keeper system - keeper types include different distance ranges and ties to cell, NPC, or item.
- [ ] Add quest assignment - some NPCs can be given quest from player quest inventory, will then pursue quest target
- [ ] Add foraging spawns — wild mushrooms, berries, herbs in forest and cave zones; biome rules
- [ ] Add NPC daily schedules — field at dawn, tavern at evening, temple on rest days
- [ ] Add sheep/cow/chicken production — timed output: wool, milk, eggs; needs food/water
- [ ] Add coal/fuel resource — required to operate forge; found in caves
- [ ] Add steel recipe — iron_ingot + coal → steel_ingot; enables higher-tier weapons and armor
- [ ] Add silver ore — rare cave resource; effective against werewolves and undead
- [ ] Add bow and arrow — craftable; ranged projectile; arrow ammo item
- [ ] Add cooking station and basic recipes — cooking pot→food; alchemy table→potions
- [ ] Add armor types — cloth, leather, chain, plate; defense values and entity compatibility
- [ ] Add bounty system — attacking peaceful NPCs triggers bounty; guards pursue across zones; clear at temple or bribe
- [ ] Add item value system - items automatically valued based on inverse total count in game? Distance from next instance?
- [ ] Add hostile/peaceful reputation score — -100 to 100 global score; updated by actions; affects faction reactions
- [ ] Add event witness system — NPCs near player events gain/lose favor; spreads via proximity
- [ ] Add house upgrade chain — lumberjack+miner → stone house; stone house+blacksmith → fort
- [ ] Add fort → castle progression — castle generates interior guards and King NPC
- [ ] Add expand keeper system — level-based range and behavior: level 1=guard, 2=patrol, 5=ranged follower, 9=zone keeper
- [ ] Add follower command: stay — state toggle; follower stops moving and holds position
- [ ] Add follower command: attack nearest — follower targets closest hostile regardless of range
- [ ] Add Tavernkeeper NPC interaction — buy room (time skip + full stat restore); open rumors dialogue
- [ ] Add trader follower economy — trader in party trades nearby NPCs; player earns gold share
- [ ] Add LoreEngine migration events — populations shift between zones on overcrowding or hostile pressure
- [ ] Add LoreEngine natural disaster events — flood, wildfire, earthquake; each creates recovery quest hooks
- [ ] Add multiple save slots — save slot selection on main menu
- [ ] Add hidden dungeon rooms — pushable wall cells reveal secret passages and bonus vault
- [ ] Add buried treasure — shovel digs soft cells; chance to uncover cached items; Detect spell reveals locations
- [ ] Add parry mechanic — both attacker and defender take small HP and energy damage
- [ ] Add thrown weapons — rocks, knives, spear; knockback on hit
- [ ] Add faction alt naming — goblin groups→warbands; criminal groups→guilds; animal groups→packs; religious groups→orders
- [ ] Add lore_note item type — found in ruins and dungeons; readable; contains generated zone history text
- [ ] Add dungeon keys and locks — small key item, locked door cell, boss key item
- [ ] Add dungeon traps — floor spike cell, arrow trap cell; pressure plate trigger
- [ ] Add stealth/crouch mode — reduced detection radius; sneak attack damage bonus on first hit
- [ ] Add basic fishing — rod item; fish item by water cells; fish variety by biome and season

---

Items that are far-future or speculative (Dragon boss, portals, genetics, prophecy systems, sinking city) are tracked in `roadmap.md` only and do not appear here until the prerequisite systems are in place.
