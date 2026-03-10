# StarCell — Next Up

> Simple ordered work list. Each bullet is roughly one commit or one small PR.
> Claude: start at the top. After each item is done and pushed, run an observation session, then continue down the list.
> @qcruz manages this list — add new items at the right priority position.

---

## Immediate

- [ ] Bird/bat item pickup — flying entities (BIRD, BAT) pick up loose items from the ground while moving; drop the item at a random adjacent cell 10–30 ticks later; affects only small items (no structures or heavy gear)
- [ ] Village biome — new VILLAGE zone type; higher NPC density at spawn; clustered housing generation; market stall structure; starting zone for social/quest arcs
- [ ] Follower energy cost — each active follower reduces player max energy by a flat amount; cost offset by follower loyalty score; tracked and recalculated on follower add/remove
- [ ] Spell energy cost — spells draw from player energy pool (5+ per cast); block cast if insufficient energy; energy HUD reflects spell drain alongside other costs

## Audio

- [ ] `SoundManager.play_sfx_spatial(key, dist, max_dist=8)` — volume falloff by cell distance; silent beyond max_dist; max 2 NPC sounds per tick
- [ ] Harvest sounds in `ai/actions.py` — TREE harvest → `wood_chop`; STONE/IRON_ORE → `rock_hit`; crop → `pickup`
- [ ] NPC combat creature sounds in `npc_ai.py` — WOLF→`wolf_growl`, GOBLIN/BANDIT→`goblin_growl`, BAT→`bat_screech`, SKELETON→`bone_rattle`; others→`sword_swing`
- [ ] Ambient presence sounds — WOLF growl every ~300 ticks within 6 cells of player; GOBLIN every ~200 ticks

## Spells & Actions Tab

- [ ] Add `rain_spell`, `day_spell`, `shove` to `data/items.py` and `constants.py`
- [ ] Add `actions` dict and selected key to Inventory class (`entity.py`)
- [ ] Add `'actions'` to inventory UI categories and color (`ui/inventory.py`)
- [ ] Wire R key → Actions tab toggle (`game_core.py`)
- [ ] Give rain_spell, day_spell, shove at new game start (`game_core.py`)
- [ ] `cast_rain_spell()` — toggle `self.is_raining`
- [ ] `cast_day_spell()` — toggle `self.is_night` via `day_night_timer`
- [ ] `do_shove()` — push entity in player's facing direction one cell (blocked by solid cells)
- [ ] Wire L key → dispatch selected magic spell
- [ ] Wire Space → dispatch selected action when Actions tab is open
- [ ] `handle_npc_follow_interaction()` — Shift+F on inspected NPC; 50% recruit chance; adds to followers and inventory

## NPC AI

- [ ] Port `_autopilot_try_craft()` to `ai/actions.py` as `try_craft_recipe()` — MINER and BLACKSMITH archetypes use it
- [ ] NPC pathfinding: all NPCs use cardinal obstacle-clear logic from autopilot (chop/mine/clear to unblock)
- [ ] Follower NPC behavior — followers use quest-targeting + obstacle-clearing loop; goal type matches NPC archetype
- [ ] Combat follow-through — NPCs complete attack sequence before re-evaluating; fixes oscillation at threshold range

## Code Cleanup

- [ ] Remove dead debug prints outside `autopilot.py` and `debug/`
- [ ] Audit monolith methods fully extracted to mixins — remove duplicates from `game_core.py` / `npc_ai.py`
- [ ] Consolidate duplicate crafting/inventory logic

## Combat & Spells

- [ ] Spell leveling — spells gain proficiency with use; higher level reduces cast cost / increases effect
- [ ] Items level up with use — weapons, tools, and spells track use count; milestone bonuses
- [ ] Poisoned status — HP drain per tick; cured by antidote or milk
- [ ] Burning status — HP drain; spreads to adjacent flammable cells
- [ ] Frozen status — immobile for duration; bonus damage on shatter
- [ ] Stunned status
- [ ] Parry - both take small HP damage and energy damage
- [ ] Equipment panel UI — Weapon, Off-hand/Shield, Armor, Ring ×2, Amulet slots; passive stat bonuses
- [ ] Armor types: cloth, leather, chain, plate — defense values and entity compatibility
- [ ] Bow and arrow — craftable; ranged projectile; ammo consumption
- [ ] Thrown weapons — rocks, knives, spear
- [ ] Stealth / crouch mode — reduced detection radius; sneak attack bonus on first hit

## World & Zones

- [ ] Zone priority scoring in update loop — zones score by proximity to player and time since last update; higher score → updated more frequently; catch-up cycles on delayed zones
- [ ] Zone and NPC name generation — unique generated names; zone gen influenced by name seed
- [ ] Seasonal system — four seasons, ~7 in-game days each; affects crops, NPC behavior, weather
- [ ] Winter effects — snow overlay, water→ice, reduced crop growth, NPCs shelter indoors
- [ ] World map view — zoomed-out explored zone view with names and faction colors
- [ ] Waypoint stone — placeable structure; teleport between owned waypoints

## Structures & Dungeons

- [ ] House upgrade chain — lumberjack + miner → stone house; stone house + blacksmith → fort; fort → castle
- [ ] Tavern — NPC gathering, rest/skip time, Tavernkeeper rumors
- [ ] Temple/Shrine — visit buff, Identify curse, unique quest
- [ ] Blacksmith structure — forge; enables iron/steel recipes; Blacksmith NPC spawn
- [ ] Multi-floor structures — towers and dungeons with multiple floors connected by staircases; each floor is a separate structure
- [ ] NPC travel into structures — NPCs enter and exit structure floors using same logic as player
- [ ] Buried treasure — shovel digs soft cells; chance to uncover cached items
- [ ] Dungeon keys and locks — small key item, locked door cell, boss key
- [ ] Dungeon traps — floor spikes, arrow traps; pressure plate trigger cell
- [ ] Hidden rooms — pushable wall cells reveal secret passages
- [ ] Dungeon themes — Crypt, Dwarven Hall, Ice Cavern, Volcanic Lair, Flooded Ruins, Cursed Library

## Entities

- [ ] Rename WARRIOR → KNIGHT in entity data and all references
- [ ] Blacksmith NPC — seeks forge, crafts tools/weapons, opens trade on inspect, gives smithing quests
- [ ] Golem — slow, high defense, attacks only when attacked; guards dungeon entries
- [ ] Troll — health regen; weak to fire; forest/cave spawns
- [ ] Zombie — slow; contagion on hit; graveyard spawns
- [ ] Ghost — passes through walls; immune to physical; weak to holy
- [ ] Werewolf — human NPC by day, transforms at night; weak to silver; bitten NPC may turn
- [ ] Slime — splits into smaller slimes on death
- [ ] Dragon — boss tier; fire breath; lair hoard accumulation
- [ ] Sheep/Cow/Chicken — produce wool/milk/eggs over time; needs food/water
- [ ] Barn/pen structure — houses animals; prevents wandering
- [ ] Entity genetics — behaviors numerically determined; traits mutate via Contagion System; high-threshold traits generate earned titles

## Social, Quests & Reputation

- [ ] Hostile/peaceful score (-100 to 100) — updated by player actions; affects faction reactions
- [ ] Per-NPC favor system (-100 to 100) — loyalty threshold → follower conversion; works on animals
- [ ] Bounty system — attacking peaceful NPCs triggers bounty; guards pursue; clear at temple or bribe
- [ ] Event witness system — nearby NPCs observe player events; favorable → favor increment; spreads via Contagion
- [ ] Gift giving — offer items to NPCs to increase favor; preferred gift per NPC type
- [ ] NPC schedules — daily routines: field at dawn, tavern at evening, temple on rest days
- [ ] NPC quest type progression — NPC level unlocks more quest types; completing quests levels up the NPC
- [ ] Faction alt naming — goblin groups→warbands, criminal groups→guilds, troupes, packs, orders

## Economy & Crafting

- [ ] Crafting stations — forge (metal), alchemy table (potions), loom (cloth), cooking pot (food)
- [ ] Cooking recipes — flour, bread, cheese, honey goods; cooked food grants stat buffs
- [ ] Recipe book UI — tracks known and undiscovered recipes
- [ ] Trader follower economy — trader follower trades nearby; player earns gold share
- [ ] Silver ore — rare; effective against werewolves and undead
- [ ] Coal/fuel — required to operate forge; found in caves

## Activities

- [ ] Fishing — cast from water-adjacent cell; catch timer; fish variety by biome/season/time
- [ ] Foraging — wild mushrooms, berries, herbs in forest/cave; biome and season rules
- [ ] Archaeology — Archaeologist NPC gives targeted dig quests; shovel reveals buried caches
- [ ] Ancient Map Fragments — combine three to reveal hidden dungeon or treasure zone

## World Simulation

- [ ] Ekistic system — zones accumulate a development score; score unlocks higher-tier structures and denser NPC spawns
- [ ] Sinking city LoreEngine event — zone floods over many updates; NPCs flee; ruins become Flooded Ruins dungeon
- [ ] Named villains — LoreEngine designates high-level hostile NPC with unique dialogue and artifact drop
- [ ] Prophecy system — LoreEngine generates Prophecy fragment pointing toward legendary item or boss
- [ ] Migration events — populations shift between zones based on conditions
- [ ] Natural disaster events — flood, wildfire, earthquake; each creates recovery quests
- [ ] Years passing optimization — probabilistic catch-up updates; speed multipliers during time-pass simulation

## Audio & UI

- [ ] Background music — biome-specific; intensity scales with nearby combat
- [ ] Footstep sounds — vary by cell type (grass, stone, water, sand)
- [ ] Menu toggle for music and debug overlay — accessible from pause menu
- [ ] In-game help overlay / context-sensitive tips
- [ ] Multiple save slots
- [ ] Difficulty settings — combat damage multiplier, permadeath toggle, NPC aggression level
- [ ] Bestiary — logs discovered entity types with flavor text, stats, weaknesses
- [ ] Achievement system — milestone tracking, HUD notifications

## Dev Infrastructure

- [ ] Tiered auto-correction in `debug/fixes.py` — zone too dense → termite invasion; NPC stuck → force update + invasion; population imbalance → LoreEngine disaster or migration
- [ ] Watchdog performance sampler — frame time and entity count per tick; surface FPS-drop zones
- [ ] Sponsor section in main menu or credits
- [ ] Bounties and rewards doc — public list of features/bugs with community bounties
