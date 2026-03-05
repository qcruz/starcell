# Rewards & Bounties

This document lists the most-wanted features and contributions for StarCell, ranked by priority and estimated reward allocation. If you contribute a feature from this list that gets merged into the main repository, it will be considered for a portion of that month's Community Contributor Reward Pool.

**How rewards work:**
- The pool is funded by 90% of Patreon revenue + 100% of CSP partner proceeds
- Allocations below are *estimates* — final amounts are at the Project Manager's discretion
- A single payout period may include multiple contributors sharing a pool
- Percentages reflect the estimated share of the *monthly pool* a completed, quality contribution would be considered for
- Partial implementations, bug fixes, and documentation contributions are also eligible at lower allocations

See [CONTRIBUTING.md](contributing.md) for the full Contributor License Agreement.

---

## Priority Feature Bounties

### Tier 1 — High Impact (10–20% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 1 | **Audio System** | 15–20% | Background music (biome-specific, intensity-scaled), ambient sfx (rain, cave, fire, wind), action sfx (combat hits, crafting, spells), NPC vocal cues. Largest scope on the list — full system earns top allocation. |
| 2 | **Sprite / Art Pass** | 10–15% | Character sprites with directional walk animations, improved terrain tiles, structure sprites, UI icons. Placeholder art exists for everything — replacements with polished originals earn per-asset credit. |
| 3 | **Equipment Slots** | 10–12% | Separate equipment panel (weapon, shield/off-hand, armor, ring ×2, amulet). Items in slots apply passive stat bonuses distinct from inventory. Required foundation for much of the combat depth roadmap. |

---

### Tier 2 — Core Gameplay (6–10% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 4 | **Status Effects** | 8–10% | Poisoned, Burning, Frozen, Stunned, Confused, Cursed, Charmed, Sleeping. Each effect needs a distinct visual indicator, timer, and cure path. Foundational for the elemental and spell systems. |
| 5 | **Ranged Combat** | 8–10% | Bow + arrow ammo, thrown weapons (rocks, knives, bombs), bomb cell destruction. Bombs open hidden passages — integrates with dungeon system. |
| 6 | **Social / Dialogue System** | 8–10% | NPC daily schedules (field → tavern → home), gift giving with per-NPC preferences, rumor system at taverns (zone events, rare loot hints), favor score tracking. |
| 7 | **Seasonal System** | 7–9% | Four seasons (~7 in-game days each). Season affects crop growth, wild plant spawns, NPC shelter behavior. Winter: snow overlay, water freezes to ice. Calendar visible in HUD. |
| 8 | **Structure Progression** | 6–8% | Camp → House → Fort → Castle chain. Zone conditions (lumberjack + miner → stone house; stone house + blacksmith → fort). Guards spawn at fort; Castle has interior rooms and a King who retreats inside when health is low. |

---

### Tier 3 — Content & Depth (3–6% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 9 | **Fishing System** | 5–6% | Cast from water-adjacent cell. Fish variety by biome, season, time of day. Common fish as food; rare fish as collectibles. Fishing pond structure for farming. |
| 10 | **Animal Husbandry** | 5–6% | Cow (milk), chicken (eggs), sheep (wool). Animals need food/water or production declines. Barn/pen structure houses them. Artisan products (cheese, cloth, honey) from raw goods. |
| 11 | **Boss Rooms & Boss Enemies** | 4–6% | Boss rooms in deep dungeon levels. Unique high-health enemy with special attack patterns and guaranteed rare loot. Lair action (environmental hazard) once per zone update. Dragonknight and Ancient Mechanica variants planned. |
| 12 | **Character Creation / Classes** | 4–5% | Ability scores (STR, DEX, CON, INT, WIS, CHA) that increase with use and decay over time. Class / archetype choice (Fighter, Wizard, Rogue, Ranger, Cleric, Druid) affects starting gear and perk unlock rates. |
| 13 | **Cooking & Recipe System** | 4–5% | Cooking pot / campfire crafting station. Recipes discovered from NPCs, books, or experimentation. Cooked food provides temp stat buffs beyond basic hunger fill. Recipe book tracks known/undiscovered recipes. |
| 14 | **New Hostile Entity Types** | 3–5% | Any of: Golem, Dragon, Troll, Zombie, Ghost, Werewolf, Mimic, Slime, Witch. Each needs sprites, stat definition, and AI behavior in the entity type table. Priced per entity — full set earns maximum allocation. |
| 15 | **Dungeon Puzzles & Keys** | 3–5% | Pressure plates, levers, locked doors, push-block puzzles. Small keys (found in chests / dropped by enemies), boss key, dungeon map item, compass item. Hidden rooms (pushable wall cells). |
| 16 | **Perk / Skill Trees** | 3–5% | Perks earned through natural gameplay (killing goblins → goblin-damage bonus). Perks decay slowly over time if not maintained. Skill trees per activity: combat, crafting, farming, exploration, magic. |

---

### Tier 4 — Quality of Life & Polish (1–3% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 17 | **NPC Quest Source Mechanic** | 2–3% | Shift+Q on inspected NPC gives a quest (uses loreEngine). Up to 3 active NPC quest slots. Turn in to NPC on completion for XP. HUD arrow + return hint for completed quests. Save/load persistent. |
| 18 | **Fast Travel / Waypoints** | 2–3% | Waypoint stone (placeable structure). Player teleports between owned waypoints. Discovered zone names persist on a world map. |
| 19 | **Building Mode** | 2–3% | Dedicated build mode (no interact-movement conflict). Place any owned cell or structure item freely. Blueprint system for saving and placing multi-cell templates. |
| 20 | **Foraging System** | 2–3% | Wild mushrooms, berries, herbs in forest and cave zones. Seasonal and biome-specific. Some items are ingredients; some are consumable. Foraging skill perk increases yield. |
| 21 | **New Peaceful Animals** | 2–3% | Cow, chicken, horse/mount (rideable, 2× movement speed, requires taming). Cat (hunts small creatures, reduces pest spawns). Dog (barks alert when hostiles enter zone, assists in combat). |
| 22 | **World Map View** | 1–3% | Zoomed-out view of explored zones with generated names. Domain control coloring (faction territory markers). Waypoint markers. |
| 23 | **Reputation & Favor Systems** | 2–3% | Hostile/peaceful score (player-carried, -100 to 100). Per-NPC favor score. Loyalty threshold triggers follower conversion. Bounty/wanted system: guards pursue player across zones until paid. |
| 24 | **Minimap** | 1–2% | Small zone map in corner showing explored cells, entity positions, zone exits. |
| 25 | **Multiple Save Slots** | 1–2% | 3+ save slots selectable from main menu. Slot name, date, and play time shown. |
| 26 | **Difficulty Settings** | 1–2% | Combat damage multiplier, permadeath toggle, NPC aggression level. Selectable at new game start. |
| 27 | **In-Game Help / Tooltips** | 1–2% | Context-sensitive help overlay. Item tooltips on hover. First-time action prompts. |
| 28 | **Documentation / Tutorials** | 1–2% | Written guides, video tutorials, wiki contributions, or in-game tutorial zone. |

---

## Notes for Contributors

- **Partial contributions count.** If you implement 3 of the 8 status effects, you will be considered for a partial allocation of that bounty.
- **Bug fixes and code quality improvements** are eligible for small discretionary rewards even if not on this list. The more impactful the fix, the larger the consideration.
- **Art assets** are priced per asset. A single polished character sprite set (4 directions × 3 frames) for a new entity type earns credit even without accompanying code.
- **Documentation and community tooling** are always welcome and eligible at Tier 4 rates.
- **Coordination**: Before starting a large feature, open an issue or reach out on Discord to confirm it is not already in progress by someone else.
- This document is updated monthly as features ship and priorities evolve.

*Last updated: 2026-03-04*
