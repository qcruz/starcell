# StarCell — Economy & Balance

StarCell's economy is not a formal market simulation. It is an emergent system — the result of NPCs producing, consuming, and exchanging resources over time, with the player as an active participant. Balance targets are about feel as much as numbers: resources should feel scarce enough to matter, time investment should feel rewarded, and no single path should dominate.

> **Note:** This document is a working reference. Specific numeric values are subject to ongoing tuning via observation sessions. See `debug/bug_report.md` for session data and `constants.py` for current values.

---

## Progression Pacing

Progression should feel deliberate and earned. The player should never feel like they are grinding — but they should feel like time spent in the world compounds. An hour of play should visibly change their position.

**Pacing targets:**
- Basic tools and first tier items: reachable in the first hour through normal play
- First crafted weapon or armor: requires 2–3 hours of resource gathering and NPC interaction
- Enchanted or named items: multiple sessions; require relationship investment, not just crafting
- Legendary items: rare, memorable, tied to specific circumstances (an NPC's gift, a dungeon boss drop, a buried cache)

The gap between tiers should feel meaningful but not punishing. A player who invests time should feel the difference.

---

## Resource Scarcity

Resources are not infinite. This is by design. Scarcity creates decisions, and decisions create stories.

- **Zone depletion:** Harvesting cells (stone, ore, wood) reduces local supply. Zones do not regenerate instantly. Players who strip a zone feel the consequence.
- **Ecological impact:** Large-scale harvesting of living resources (wolves, trees, animals) has cascading effects. A hunted-out wolf population collapses — or retaliates.
- **Seasonal variation (target):** Crop growth, animal activity, and resource regeneration should vary by season. Preparing for lean seasons will be part of mid and late game planning.
- **Rarity gradient:** Common resources (wood, stone) are abundant and renewable with time. Rare resources (iron ore, silver, magical components) are zone-limited and do not regenerate.

---

## Item Tiers & Value

Items exist on a rough tier ladder. Value is not arbitrary — it reflects the time, relationships, and zone access required to obtain the item.

| Tier | Examples | How Obtained |
|---|---|---|
| Common | Wood, stone, food, basic tools | Harvested directly from cells |
| Crafted | Iron sword, leather armor, potions | Crafted from gathered materials |
| Enchanted | Flaming sword, shielding amulet | Crafting + enchantment; NPC gifts |
| Named / Legendary | Blacksmith's family sword, artifact drops | NPC relationship milestones, boss drops, buried caches |

Named and legendary items should feel irreplaceable. When they are lost — stolen, dropped on death, destroyed — the loss should hurt. Recovery quests exist precisely because some items are worth crossing the world to reclaim.

Item value should also be world-contextual: a rare item is more valuable in a zone where it cannot be produced locally. A trader who travels zones arbitrages this naturally.

---

## Crafting Economy

Crafting converts raw resources into higher-tier items. The chain should be visible and learnable — a player should be able to trace the inputs of any item back to harvestable sources.

**Design targets:**
- Each crafting tier should require at least one item from the tier below
- Crafting chains should incentivize NPC role diversity: a blacksmith needs ore from a miner; a wizard needs components only found in caves
- Recipes should be discoverable through play, not buried in menus — players who explore and experiment should find new options naturally
- Crafting should not make resource gathering irrelevant — higher tier crafting requires proportionally more rare inputs

The player and NPCs share the crafting economy. A MINER gathering ore and a BLACKSMITH converting it to weapons is a parallel track to the player doing the same. Player investment accelerates the NPC chain; NPC activity can supplement player supply.

---

## NPC Economy

NPCs participate in the economy as producers, consumers, and traders. Their economic activity is a background simulation — it runs without player input but responds to player action.

- **Production:** NPCs with active jobs (FARMER, MINER, LUMBERJACK) generate resources over time and store them
- **Consumption:** NPCs consume food, water, and tools; a settlement without supply degrades
- **Surplus and trade:** NPCs with excess inventory offer it to nearby complementary roles or deposit to shared chests; TRADER NPCs move surplus between zones
- **Gold:** Gold circulates through quests, trade, and tribute. A wealthy NPC has completed many exchanges or is high-level. A poor settlement signals economic dysfunction.
- **Player participation:** The player earns gold through quests and trade; spends it on items, follower costs, and eventually infrastructure. Gold should feel like a meaningful resource, not an afterthought.

---

## End-Game State

There is no final economic state — the game does not end. End-game economy targets:

- Player has established supply chains across multiple zones
- Named NPC relationships provide access to top-tier crafting and enchanting
- Gold surplus enables follower maintenance, structure upgrades, and trade across zones
- Legendary items in circulation — some held by the player, some by powerful NPCs, some still hidden
- The world economy has matured: factions trade, settlements produce at scale, and disruptions (raids, ecological events) have visible economic consequences

The end-game should feel like stewardship — the player managing a complex, living world rather than grinding toward a fixed endpoint.
