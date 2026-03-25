# StarCell — NPC Society Design

NPCs in StarCell are not set dressing. They are participants in a living simulation with their own needs, roles, relationships, and lifecycles. Society emerges from individual NPC behaviors interacting over time — not from scripted events or authored story beats.

The design goal: a player who ignores the NPCs entirely should still watch a world happen around them. A player who invests in that world — protecting it, questing for it, building relationships within it — should find it rewards that investment with depth that authored games cannot replicate.

> **Note:** This document is a working reference for future design work. Systems described here range from implemented to planned. See `current_features.md` and `next_up.md` for current implementation status.

---

## Village Lifecycle

A settlement begins with one or two NPCs and a basic structure. Over time — if the zone is protected and resourced — it grows.

**Growth stages (target model):**
1. **Homestead** — 1–3 NPCs, no formal structure. A farmer, maybe a guard. Vulnerable to raids.
2. **Settlement** — First structure built (house, well, small shop). NPCs have established roles.
3. **Village** — Multiple structure types, mixed NPC roles, market activity, zone defense.
4. **Town** — Faction influence present, named characters, keeper NPCs, quest givers.
5. **City** — Multiple factions, trade routes with other zones, guild or council structure.

Growth is not guaranteed. A zone under sustained hostile pressure will decline rather than grow. Player involvement accelerates or redirects growth but does not script it.

---

## Faction Balance

Factions are groups of NPCs with shared allegiance and emergent political behavior. Each faction has a disposition toward others — neutral, allied, rival, or hostile — that shifts based on events in the world.

Key tensions in the default world:
- **Peaceful vs. hostile factions** — farmers and guards vs. goblins, bandits, wolves. The default state is cold tension — raids happen but are not constant.
- **Rival peaceful factions** — two settlements in the same zone may compete for resources or develop trade relationships. Which outcome depends on player action and random events.
- **Faction power shifts** — a faction that loses its strongest NPCs weakens. One that gains high-level warriors expands. Player choices (who to help, who to hurt) ripple outward.

No faction should be permanently dominant by design. The world should feel like it's in ongoing negotiation.

---

## Society Stages by World Age

The world ages on a tick clock. Early in a run, the world is sparse and dangerous — few settlements, strong hostile presence. Over time, if peaceful factions survive:

| World Age | Typical State |
|---|---|
| Early | Isolated homesteads, frequent raids, scarce resources |
| Developing | First villages form, trade begins, faction territories stabilize |
| Mature | Towns with named characters, cross-zone trade routes, stable power centers |
| Ancient | Old settlements with deep NPC histories, monuments to fallen characters, legendary items in circulation |

NPCs aging and dying is part of this cycle. Second-generation NPCs (NPCs born or transformed in-world from existing populations) should eventually appear as a late-game feature.

---

## NPC Role Interactions

NPC roles are not isolated — they form an interdependent web. A healthy society needs most of these roles functioning together.

| Role | Produces / Does | Depends On |
|---|---|---|
| FARMER | Food, crops, wool, milk | Water source, protection |
| MINER | Stone, iron ore, coal | Tools, safe cave access |
| LUMBERJACK | Wood, lumber | Forest zones, tools |
| BLACKSMITH | Weapons, armor, tools | Iron ore, coal, shelter |
| TRADER | Gold, rare items, cross-zone goods | Safe travel routes, market |
| GUARD | Zone protection, escort | Shelter, weapons |
| WARRIOR | Combat, raids, dungeon clearing | Weapons, armor, food |
| WIZARD | Spells, enchantments, arcane items | Books, magical components |
| KING / COMMANDER | Faction direction, buff to nearby allies | Strong zone, loyal population |

When a role is missing, the society weakens. No blacksmith means degrading weapons. No farmer means NPCs seeking food elsewhere — possibly leaving the zone.

---

## Hostile Society Behavior

Hostile factions are not mindless — they have territory, hierarchy, and goals.

- **Territory:** Hostile groups claim zones and defend them. Entering their zone is provocation.
- **Raids:** Hostile NPCs periodically test peaceful zone defenses. Raid frequency and strength scales with hostile faction power.
- **Retaliation:** Player or NPC actions that harm a hostile faction (killing members, destroying structures) trigger escalating responses. Hunt enough wolves and the pack attacks the village.
- **Power accumulation:** High-level hostile NPCs attract followers. A powerful goblin warlord becomes the nucleus of a warband.
- **Collapse:** A hostile faction reduced below a threshold of living members loses cohesion. Survivors may scatter, join other factions, or go dormant.

---

## Economy & Trade Between NPCs

NPCs produce, consume, and exchange resources as part of their behavior loops. This is not a formal market simulation — it emerges from individual NPC actions.

- NPCs with surplus items will offer them to NPCs of complementary roles when in proximity
- TRADER NPCs actively move between zones seeking exchange opportunities
- Chests and structures accumulate NPC surplus; player can interact with these
- Gold is the medium of exchange; NPC gold accumulation reflects their trade activity
- Player can participate in this economy: completing quests earns gold and favor; gifting items shifts relationships; trading with TRADER NPCs exchanges goods at dynamic rates

The goal is an economy the player can read from observation — a thriving village has full chests and active NPCs; a declining one has empty stores and idle characters.
