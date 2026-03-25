# StarCell — Next Up

> Two tiers. Claude works Tier 1 top-to-bottom without asking. Tier 2 items require explicit user sign-off before any code is written — post the item in chat, wait for a clear "go ahead."
> @qcruz manages additions and order.
>Always start by reviewing committ history for recent updates and changes from others. Reconcile project documentation (implemented features, bug report, roadmap, etc) at the begining and end of each session.
---

## Tier 1 — Autonomous

Small additions using existing systems and minimal changes to code.

- [ ] Status effects as a first-class system — add `entity.status_effects = {effect: ticks_remaining}` dict and `tick_status_effects()` pass; wire poisoned/burning/cold/bleeding as entries; replaces per-site hacks and unlocks The Hunger poison water, fire cells, and bleed-on-hit as one-liners
- [ ] Player reputation ripple effects — hostile NPCs in a zone flee when player reputation exceeds threshold; traders offer 10–20% discount at high rep; zone Keeper greets player by name once rep threshold crossed; no new UI, condition checks on existing paths only
- [ ] Zone memory / history scars — after any zone with >10 entity deaths, leave persistent marks: scorched tile variants, non-decaying bone piles, zone name suffix ("the Blighted"); pipe LoreEngine zone-death counts into visible cell state
- [ ] Item durability — `durability` field on equipped items, decremented on each hit; at 0 breaks to `broken_<item>` junk; creates constant economic pressure that makes blacksmith and crafting feel necessary; repair recipes already handled by crafting system
- [ ] Day/night NPC faction shift — at night guards patrol instead of idle, farmers shelter, bandits become aggressive even in neutral zones; one `self.is_night` condition check added to faction behavior dispatch
- [ ] Wandering merchant caravan — TRADER NPC spawns at world edge once every N days, travels a path through several zones, despawns at far edge; carries rare items not in normal loot tables; wires existing travel behavior, trader inventory, and zone transition system
- [ ] Boss concept: The Silence — a zone that has gone completely quiet (no spawns, no ambient, no growth); one ancient high-HP entity inside that ignores the player for ~60 ticks, then pursues zone-to-zone until killed; zero new systems, purely tuned pursuit AI and a suppressed spawn rate flag
- [ ] Boss concept: The Sleeper — deep cave level that looks normal until any item is picked up; massive STONE_GIANT variant wakes and STAIRS_UP becomes blocked by cave-in (CAVE_WALL placed over stair cells); every 30 ticks adds more CAVE_WALL cells, shrinking playable space; player must kill it before the cave collapses; uses existing cave gen + timed cell placement tied to entity alive status
- [ ] Monolith extraction pass — extract in-structure behavior block from npc_ai.py into ai/movement.py; target ~200-line reduction from monolith before status effects and boss zone work begins
- [ ] Review and formalize `dynamic_to_item_conversion` — audit all code paths that convert dynamic follower/entity state to inventory items; ensure consistent naming, cleanup on death, and no stale entries survive between sessions
- [ ] NPC targeting priority function — replace ad-hoc target selection with a scored priority system; each candidate gets a score based on type (hostile, special, resource, quest target, water, food); NPC picks highest-scoring target; scores tunable per entity type via ai_params
- [ ] NPC trader targeting and trade system — when NPC inventory is full, NPC seeks nearby chest (existing dump logic) or nearby TRADER; if TRADER is adjacent, NPC trades surplus inventory items for gold; if NPC gold exceeds threshold, buys a random item from the TRADER's inventory

- [ ] NPC infection system: vampirism and lycanthropy — hostile bats can infect humanoid NPCs with vampirism (transforms to BAT at night, reverts at dawn); hostile wolves can infect with lycanthropy (transforms to WOLF at night, reverts at dawn); silver weapons prevent/cure infection
- [ ] Add item level display in inventory UI — show level badge on leveled items in all tabs

- [ ] Village and dungeon biome — required sprites: fence, stairs up/down
- [ ] Create village biome — VILLAGE zone type; rare spawn; clustered housing with fence cells enclosing plots, market stall, well; higher NPC density (FARMER, GUARD, BLACKSMITH, TRADER, COMMANDER, KING); guard keepers protect zone perimeter. Required sprites: fence.
- [ ] Create dungeon biome — multilevel underground structure; offshoot cave corridors in crucible layout; STAIRS_DOWN/STAIRS_UP cells connect floors; NPC difficulty and loot quality scale with depth; boss room at deepest level. Required sprites: stairs_up, stairs_down.
- [ ] Add multi-floor structures — dungeons and towers with staircase-connected floors; each floor separate structure
- [ ] Connect STAIRS_DOWN/STAIRS_UP cells between structure floors — entry/exit routing via stair cells

- [ ] More sprites, cells, NPCs, and biomes

- [ ] Skeleton doubles (and all doubles) need to process the same as their single counterparts (skeelton doubles should take constant damage during the day while outside)
- [ ] Double entities should have a chance to split back in to singles every update tick if NPC population is low enough. Split inventory, levels, quest, etc randomly for now.
- [ ] Hard cap on total number of same entity in zone - if more than 15 of the same entity type in zone, single or double, singles get 'absorbed' into doubles automatically - double entity gets level increase.
- [ ] Add a few random items to barrels as well, picked up when interacted (same handling as chests, but lower quality loot table)
- [ ] When player drops items on a chest cell, they should move to the chest inventory
- [ ] When butterflies fly over base cells - high chance to grow the cell to next level - sand>dirt>grass>plant (will be adding bush and flowers, etc)(doesn't grow trees)
- [ ] Add ambient rain sound during rain events — play rain_sound loop when is_raining; stop when false
- [ ] Add buried treasure — shovel digs soft cells; chance to uncover cached items; Detect spell reveals locations, dig action works as well (low success chance - takes multiple tries)
- [ ] Boost night-time hostile spawn rate slightly — BAT, GOBLIN, SKELETON have higher spawn weight at night
- [ ] Add spell energy cost — spells draw from energy pool; drain health if insufficient
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
