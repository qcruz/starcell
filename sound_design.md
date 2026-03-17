# StarCell — Sound Design

Sound in StarCell should make the world feel alive and inhabited. The goal is a soundscape that rewards attention — a player who listens should learn things about the world around them: what creatures are nearby, what the weather is doing, what an NPC is working on. Sound is information as much as atmosphere.

> **Note:** This document is a working reference for future collaborators. Specific file selections and mixing targets will be developed with audio contributor input. The existing `sound files/` directory contains a working library of placeholder assets.

---

## Philosophy

- **Diegetic first.** Sounds should feel like they exist in the world, not layered over it. A lumberjack chopping trees should produce wood-chop sounds from their location, not from a UI layer.
- **Spatial audio for NPCs.** NPC action sounds play at reduced volume based on distance from player. The world sounds busy even when the player is standing still.
- **Music as mood, not wallpaper.** Music loops should shift meaningfully with context (zone type, time of day, threat level). Silence is valid — underground zones and late-night overworld can run on ambient SFX alone.
- **Restraint.** Not every action needs a sound. UI sounds especially should be subtle. Audio pile-up kills atmosphere.

---

## Mood Targets by Context

| Context | Target Feel | Notes |
|---|---|---|
| Overworld day | Pastoral, alive | Birds, wind, distant NPC activity |
| Overworld night | Tense, lonely | Crickets, owl calls, hostile ambient cues |
| Cave/underground | Oppressive, curious | Drips, echoes, distant creature sounds |
| Village/settlement | Warm, productive | Ambient smithing, conversation murmur, livestock |
| Combat | Urgent, grounded | Creature-specific hit sounds; no dramatic orchestral swell |
| Rain event | Melancholy, cozy | Rain loop, reduced ambient life sounds |
| Dungeon/ruin | Dread, ancient | Minimal music, heavy atmosphere, distant danger |

---

## SFX vs Music

**SFX** are tied to specific game events: NPC actions, player actions, cell interactions, UI events. They play from a position in the world or from the UI layer, never both simultaneously for the same event.

**Music** is context-driven loops: one per biome type, one for night, one for combat escalation, one for menus. Music should crossfade or cut cleanly on context change — no abrupt stops. Music volume is user-configurable and defaults lower than SFX to keep the world sounds readable.

A per-tick NPC sound budget (max 2 spatial NPC sounds per tick) prevents audio pile-up during high-activity ticks.

---

## Biome Audio

Each biome has an ambient loop and a set of contextual SFX that play during NPC activity in that zone.

| Biome | Ambient Loop | NPC Activity Sounds |
|---|---|---|
| Forest/Grassland | Birds, wind | Wood chop, footsteps on grass |
| Desert | Wind, dry silence | Sand footsteps, distant raptor |
| Cave | Drips, stone echo | Mining, stone footsteps |
| Swamp | Frogs, insects | Water footsteps, creature calls |
| Snow/Tundra | Wind, silence | Snow footsteps, distant howl |
| Settlement | Ambient life murmur | Smithing, trade sounds |

---

## Combat Audio

Combat sounds are entity-type specific where possible, not generic. The intent is that a player with headphones should be able to identify what they're fighting before they see it.

| Entity Type | Hit Sound | Ambient/Presence Sound |
|---|---|---|
| WOLF | Animal yelp | Growl every ~300 ticks within 6 cells |
| GOBLIN / BANDIT | Goblin growl | Snarl every ~200 ticks within range |
| SKELETON | Bone rattle | None (silent until engaged) |
| BAT | Screech | Wing flap on movement |
| GIANT / OGRE | Deep grunt | Footstep thud |
| Default hostile | Sword swing | None |

Player attack sounds draw from the equipped weapon type: unarmed, sword, bow, spell. Spells have distinct casting sounds per school (fire, ice, arcane, nature).

---

## UI Audio

UI sounds should be brief, non-intrusive, and consistent. They communicate state changes — not decorate every click.

| Event | Sound Target |
|---|---|
| Inventory open/close | Soft paper/leather rustle |
| Item pickup | Short chime or clink (material-matched where possible) |
| Item equip | Equip thud (armor heavier than weapon) |
| Level up | Bright rising tone — distinct, memorable |
| Quest received | Short fanfare cue |
| Quest complete | Warm resolution chord |
| Menu navigation | Subtle tick |
| Error / blocked action | Low dull thud |

---

## Asset Pipeline

Sound assets live in `sound files/`. The `SoundManager` (in `game_core.py` or `systems/`) loads files at startup and maps them to string keys used throughout the codebase.

1. Add the audio file to the appropriate subdirectory under `sound files/`
2. Register the key→filepath mapping in `SoundManager`'s load block
3. For spatial NPC sounds: call `SoundManager.play_sfx_spatial(key, dist)` from the action site
4. For UI sounds: call `SoundManager.play_sfx(key)` directly
5. Music loops are registered separately and swapped via `SoundManager.play_music(key)`

Supported formats: `.wav`, `.ogg`, `.mp3`, `.flac`, `.aif`. Prefer `.ogg` for music loops (smaller file, seamless loop support in pygame).
