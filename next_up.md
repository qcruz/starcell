# StarCell — Next Up

> Two tiers. Claude works Tier 1 top-to-bottom without asking. Tier 2 items require explicit user sign-off before any code is written — post the item in chat, wait for a clear "go ahead."
> @qcruz manages additions and order.

---

## Tier 1 — Autonomous

Small additions using existing systems. No new entity types, structure types, or major UI systems. One commit per item, ordered smallest to largest.

- [x]  give sand cells a slightly higher chance to
change to water cells during rain. Whatever the rate is for dirt, it should be
double.
- [x] More Keeper types based on range - Keeper type 1 (guard) - stand directly next to keeper target, type 2 small area, type 3 full zone
- [x] Add specific cells, items, and NPCs can be keeper target - keeper moves to keeper target when out of range
- [ ] Add NPC quest assignment - player can assign NPCs quests from their quest inventory.
- [ ] Add NPC level display in inspect panel
- [ ] Add item level display in inventory UI — show level badge on leveled items in all tabs
- [ ] Add faction standing display when inspecting NPC — show favor score and faction label
- [ ] Make actions default on spawn - 'attack', 'block' - allow player to collect resources without tools (low success chance)
- [ ] Add cast_rain_spell() and cast_day_spell() toggle methods
- [ ] Complete NPC combat creature sound mapping — verify WOLF, GOBLIN, BAT, SKELETON, BANDIT route through _ENTITY_SOUND
- [ ] Add wolf/goblin ambient presence sounds — WOLF growl every ~300 ticks within 6 cells; GOBLIN every ~200 ticks
- [ ] Add ambient rain sound during rain events — play rain_sound loop when is_raining; stop when false
- [ ] Add do_shove() — push entity in facing direction one cell; blocked by solid cells
- [ ] Add handle_npc_follow_interaction() — Shift+F on inspected NPC; 50% recruit chance
- [ ] Add buried treasure — shovel digs soft cells; chance to uncover cached items; Detect spell reveals locations
- [ ] Boost night-time hostile spawn rate — BAT, GOBLIN, SKELETON have higher spawn weight at night
- [ ] Add spell energy cost — spells draw from energy pool; drain health if insufficient
- [ ] Rain affects crop growth — active rain reduces crop decay rate; speeds grass/tree spread
- [ ] Add poisoned status effect — HP drain per tick; cured by antidote or milk
- [ ] Add burning status effect — HP drain per tick; spreads to adjacent flammable cells
- [ ] Add cold status effect — immobile for duration; 
- [ ] Add stunned status effect?
- [ ] Remove dead debug prints outside autopilot.py and debug/
- [ ] Add gift giving — player offers item to NPC to increase favor; 
- [ ] Add per-NPC favor system — -100 to 100 favorability score; reduces follower energy cost
- [ ] Add NPC preferred gift tables — each NPC type lists preferred items for favor bonus
- [ ] Add energy cost for active followers — each follower reduces max energy by 30% of their max; recalculates on add/remove
- [ ] Add named villains — LoreEngine occasionally designates a high-level hostile NPC with unique stat boost and artifact drop
- [ ] Wire higher NPC level → reduced hostile raid chance in zone and reduced structure destruction probability
- [ ] Port try_craft_recipe() to ai/actions.py — from autopilot; MINER and BLACKSMITH use it
- [ ] Port follower NPC AI — followers use quest-targeting and obstacle-clearing loop; goal matches NPC archetype
- [ ] Add zone development score (ekistic) — zones accumulate score from NPC and structure count; gates higher-tier upgrades
- [ ] Add basic seasonal system — four seasons ~7 in-game days each; season flag used by crop and weather rules
- [ ] Audit monolith methods extracted to mixins — remove duplicates from game_core.py and npc_ai.py
- [ ] Consolidate duplicate crafting and inventory logic — code cleanup pass

---

## Tier 2 — Needs Explicit Approval

Post the item in chat before starting. Wait for a clear "go ahead." These introduce new entity types, structure types, UI systems, or world generation systems that require design decisions.

### New Entity Types
- [ ] Add bird/bat item pickup — flying entities grab loose ground items; drop after 10–30 ticks at random adjacent cell
- [ ] Add SNAKE entity type — desert biome hostile; poison on hit; first concrete use of poisoned status effect
- [ ] Add SPIDER entity type — cave biome hostile; web cell slows movement; poison on bite
- [ ] Add Troll entity type — health regen; weak to fire; forest and cave spawns
- [ ] Add Werewolf entity type — human NPC by day; transforms at night; weak to silver; bitten NPC may turn
- [ ] Add Ghost entity type — passes through walls; immune to physical; weak to holy
- [ ] Add Golem entity type — slow, very high defense, attacks only when attacked; guards ruins and dungeon entries
- [ ] Add horse/mount entity — tameable via favor; 2× movement speed; low follower energy cost; stabled at barn
- [ ] Add cat entity — tameable via favor; hunts small creatures; reduces pest spawns in zone
- [ ] Add dog entity — tameable; barks when hostiles enter zone; assists in combat
- [ ] Add Lich entity type — immune to hunger/thirst; commands skeleton thralls; requires Phylactery destruction to permanently kill
- [ ] Add Vampire entity type — life drain on hit; retreats to coffin at daylight; transforms to bat when fleeing
- [ ] Add Banshee entity type — wailing spirit; AoE scream stuns nearby entities; immune to physical; night-only
- [ ] Add Basilisk entity type — petrifying gaze applies frozen status

### New Structure Types
- [ ] Create basic village biome — VILLAGE zone type; clustered housing, higher NPC density, market stall structure
- [ ] chance for stone house to become fort or belltower - fort spawns traveling soldiers (agressive) of the local faction, belltower spawns guards (relaxed, protect zone) 
- [ ] Add Tavern structure — NPC gathering point; rest/time-skip; Tavernkeeper quests
- [ ] Add Blacksmith structure — dedicated smithing building; forge enables iron and steel recipes
- [ ] Add Crypt structure — sealed underground zone; undead spawns; Vampire or Lich boss room at depth
- [ ] Add Temple/Shrine structure — visit grants buff; Identify curse; unique quest giver
- [ ] Add Ancient Ruins structure type — crumbling zone; Golem and Mechanica guardians; lore-note drops
- [ ] Add Library/Archive structure — Wizard Keeper; Tome items teach rare spells; ghost scholar guards
- [ ] Add oasis structure to desert zones — water source cell cluster in desert; NPCs and animals seek it
- [ ] Add waypoint stone structure — player teleports between owned waypoints; significant time passes on use
- [ ] Add barn/pen structure — houses livestock; prevents animal wandering

### New UI Systems
- [ ] Add actions inventory tab (R key) — shove and other contextual action items
- [ ] Add equipment panel UI — Weapon, Off-hand, Armor, Ring ×2, Amulet slots; passive stat bonuses
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
- [ ] Add multi-floor structures — dungeons and towers with staircase-connected floors; each floor separate structure
- [ ] Connect STAIRS_DOWN/STAIRS_UP cells between structure floors — entry/exit routing via stair cells
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
