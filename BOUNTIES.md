# Rewards & Bounties

This document lists the most-wanted features and contributions for StarCell, ranked by priority and estimated reward allocation. If you contribute a feature from this list that gets merged into the main repository, it will be considered for a portion of that month's Community Contributor Reward Pool.

**How rewards work:**
- The pool is funded by 90% of Patreon revenue + 100% of CSP partner proceeds
- Allocations below are *estimates* — final amounts are at the Project Manager's discretion
- A single payout period may include multiple contributors sharing a pool
- Percentages reflect the estimated share of the *monthly pool* a completed, quality contribution would be considered for
- Partial implementations and bug fixes are also eligible at lower allocations

See [CONTRIBUTING.md](contributing.md) for the full Contributor License Agreement.

---

## Priority Feature Bounties

### Tier 1 — Highest Impact (12–20% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 1 | **Audio System** | 15–20% | Background music (biome-specific, intensity-scaled to nearby combat), ambient sfx (rain, cave drips, fire, wind), action sfx (combat hits, crafting, spells), short NPC vocal cues. Largest scope on the list — full system earns top allocation. |
| 2 | **Sprite / Art Pass** | 10–15% | Polished character sprites with 4-direction walk animations, improved terrain tiles, structure sprites, UI icons. Placeholder art exists for all entity types — replacements with original polished art earn per-asset credit. Staircase sprites (distinct ascend/descend per depth level) also needed. |
| 3 | **Seasonal System** | 8–12% | Four seasons (~7 in-game days each). Season affects which crops grow and which wild plants appear. Winter: snow biome overlay, water freezes to ice, reduced crop growth, some NPCs shelter indoors. Seasonal events and quests. Calendar / day tracker visible in HUD. |

---

### Tier 2 — Core Systems (5–10% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 4 | **Lifetime System** | 8–10% | Player character gradually loses max life as they age — permadeath pressure. Multiple ways to extend life as emergent quest hooks: vampirism, fairy fountain, blood fountain, Philosopher's Stone (legendary crafted item that halts aging permanently). |
| 5 | **Structure Progression** | 6–9% | Zone with lumberjack + miner → house becomes stone house. Zone with stone house + blacksmith → stone house becomes fort. Guards spawn at and protect the fort. Fort → castle with interior guards; King retreats to castle when health is low. On attack, guards and commander spawn from castle. Tavern and Temple/Shrine as additional structure types. |
| 6 | **Keeper System & Evergaels** | 6–8% | Full Keeper role assignment (zonekeeper, tavernkeeper, towerkeeper, dungeonkeeper) with expanded NPC-specific quest types. Evergael variant: ancient or cursed entity trapped in a zone, blocking the exit until defeated — drops rare key or artifact. Foundation partially implemented; full system needs quest integration and Evergael behavior. |
| 7 | **Domain System** | 5–7% | A contiguous 2×2 block of adjacent zones controlled by the same faction becomes a domain. Domain bonuses: increased resource spawn rate, faster NPC healing, bonus player XP, reduced hostile spawn rate. Domain breaks when one zone is captured. Domain markers visible. |
| 8 | **Reputation & Favor Systems** | 5–7% | Hostile/peaceful score (player-carried, -100 to 100). Updates based on attacking peaceful or hostile entities. Low score causes factions to attack on sight; high hostility + high level causes enemy NPCs to flee. Per-NPC favor score (-100 to 100); loyalty threshold may cause NPCs and animals to become followers. Natural flee system for low-level enemies vs significantly higher-level threats. |

---

### Tier 3 — Content & Depth (3–6% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 9 | **New Spells** | 4–6% | Rain (toggle rain in zone), Calcify (freeze NPC in place), Charm (toggle NPC friendly/hostile), Heal (fill health/food/water; chance to increase max life; reverse absorbs health and may drain years), Spectral State (briefly pass through solid cells, not outer walls). Each spell needs a cast animation and distinct visual effect. |
| 10 | **New NPC Types** | 3–5% | Any of: Golem (stone, very slow/high defense, attacks only when attacked), Birds, Werewolf (human at day, transforms at night, weak to silver), Zombie (spreads contagion on hit, spawns in graveyards), Dragonknight (strong warrior with elemental damage bonus), Ancient Mechanica (golem with strong magic attacks). Priced per entity — sprites, stat definition, and AI behavior required. |
| 11 | **New Peaceful Animals** | 3–4% | Cow, Chicken, Sheep (behavior pass), Horse/Mount (rideable, 2× movement speed). Each needs sprites, stat definition, and basic behavior (grazing, fleeing). Produces goods over time (milk, eggs, wool) for use in crafting. |
| 12 | **New Items & Crops** | 3–4% | Any of: fruit trees (seasonal yield), melons, wheat, ghost fruit (magical effect when eaten), magic crystal (AoE zone effect), peace tree (zone becomes peaceful), fence (cell type, solid), torch (craftable light source, placed as cell, reduces hostile spawn rate), gravestone (marks death location, may spawn ghosts). Priced per item — sprite, cell/item definition, and integration into loot/recipes required. |
| 13 | **LoreEngine Expansions** | 3–5% | Migration events (NPC populations move between zones), natural disaster events, invasion/raid events, zone and NPC name generation (unique flavored names; zone generation influenced by its name), prophecy system (LoreEngine hints at rare events or items), additional secret entrance types. |
| 14 | **Contagion System** | 3–4% | Averages NPC stats and inventory passively based on proximity (invisible to player). Spreads player reputation scores across nearby same-type entities. Factions spread player favorability scores to allied members. Primary use: fast catch-up simulation and emergent stat evolution. |
| 15 | **Follower System Improvements** | 3–4% | When item and follower inventories are both open, selecting an item and pressing Place puts it in the follower's inventory. Follower auto-equips the strongest version of each gear type for stat calculations. Follower commands (stay, follow, attack, retreat). Follower leveling (gains XP alongside player). |

---

### Tier 4 — Mechanics & Polish (1–3% of pool each)

| # | Feature | Est. Pool % | Notes |
|---|---|---|---|
| 16 | **NPC Quest Source** | 2–3% | Shift+Q on an inspected NPC receives a random quest from that NPC (via loreEngine targeting). Up to 3 active NPC quest slots. Turn in to the same NPC on completion for a large XP reward. HUD directional arrow + return hint for completed NPC quests. Save/load persistent. |
| 17 | **Perk System** | 2–3% | Perks earned through natural gameplay — repeatedly killing goblins builds a goblin-damage bonus, etc. Perks decay slowly over time if not maintained. No trees; perks are flat bonuses earned organically per activity. |
| 18 | **RainbowMaker** | 2–3% | Default sprite colors randomizable via a built-in variant system (e.g. white cow with black spots → red cow with gold spots). Rare color variants create hunting and collecting gameplay. |
| 19 | **Entity Genetics** | 2–3% | Core NPC behaviors are numerically determined and mutate slowly over time (via Contagion System). Genetic variation reflected in sprite color variant chances. |
| 20 | **BugCatcher System Expansion** | 1–2% | Tiered auto-correction responses: zone too dense → re-roll or spawn termite invasion; NPC stuck/teleporting/too high level → force full update + trigger invasion; zone population too far out of balance → LoreEngine procs natural disaster or migration. |
| 21 | **Random Pet / Familiar** | 1–2% | Player spawns each life with a random small pet or familiar follower. Needs a sprite, basic follow behavior, and minor passive effect (e.g. cat reduces nearby pest spawns, bird alerts on approaching hostiles). |

---

## Notes for Contributors

- **Partial contributions count.** A single spell, a single new NPC type, or three new item definitions all earn partial credit at the Project Manager's discretion.
- **Bug fixes and code quality improvements** are eligible for small discretionary rewards even if not on this list. The more impactful the fix, the larger the consideration.
- **Art assets** are priced per asset. A polished character sprite set (4 directions × 3 frames) for a new entity type earns credit even without accompanying code.
- **Coordination**: Before starting a large feature, open an issue or reach out to confirm it is not already in progress.
- This document is updated as features ship and priorities evolve.

*Last updated: 2026-03-04*
