# OpenStar / StarCell

Welcome to **OpenStar** — an open, community-driven game engine and fantasy RPG playground built on the **StarCell** demo game. Whether you are here to play, build your own game on top of it, learn how game systems work, or contribute to a growing ecosystem, we are thrilled to have you!

**StarCell** is the included demo: a real-time procedurally generated fantasy world with NPC societies, dungeon exploration, crafting, combat, quests, and an emergent simulation driven entirely by simple rules.

---

## Download & Play

[![Download StarCell](https://img.shields.io/badge/Download-StarCell-blue?style=for-the-badge)](https://github.com/qcruz/starcell/archive/refs/heads/main.zip)

### macOS (Recommended — One-Click Launch)

1. Click the download badge above and unzip the file
2. Open the unzipped folder and double-click **`Launch StarCell.command`**
3. The launcher will automatically install Python and pygame if they are not already present — this may take a minute on first run
4. A branch selection dialog will appear — choose **Stable** for the current release or **Dev** for the latest work-in-progress
5. If macOS says it cannot verify the developer, go to **System Settings → Privacy & Security** and click **Open Anyway**, then re-run the launcher

> Your save file is preserved automatically when switching branches.

### Windows

1. Click the download badge above and unzip the file
2. Install **Python 3.9 or later** if you do not have it: [python.org/downloads](https://www.python.org/downloads/)
   - During installation, check **"Add Python to PATH"**
3. Open a terminal in the unzipped folder and run:
   ```
   pip install pygame
   python main.py
   ```

### Linux

1. Click the download badge above and unzip the file
2. Install Python 3.9+ and pygame via your package manager:
   ```
   sudo apt install python3 python3-pip   # Debian/Ubuntu
   pip3 install pygame
   ```
3. Run from the unzipped folder:
   ```
   python3 main.py
   ```

> **Requirements:** Python 3.9+ and pygame 2.x. No other dependencies.

---

## What Is StarCell?

StarCell is a top-down grid-based fantasy game where the world runs itself. At its core, every cell on every screen is updated every tick by simple probabilistic rules — trees spread, deserts expand, rivers flood when it rains, droughts slow growth, and structures rise and decay on their own.

On top of that living terrain, NPC societies emerge:

- **Farmers** till and plant. **Lumberjacks** harvest trees and build houses. **Miners** dig caves and mineshafts. **Traders** travel between zones trading goods.
- **Guards and Warriors** patrol, form factions, and hunt hostiles. **Commanders and Kings** lead them.
- **Wizards** seek ancient runestones and cast spells. **Blacksmiths** forge weapons and trade them.
- **Goblins and Bandits** form raiding clans and attack villages. **Wolves** hunt. **Bats** lurk in caves.
- Every NPC has its own inventory, quest focus, level, and faction. They age, fight, starve, and die.

The player exists inside this simulation — exploring, fighting, crafting, gathering followers, and pursuing quests — while the world evolves around them whether they are watching or not.

---

## Current Features

### World & Biomes
- Infinite procedurally generated overworld with 5 biome types: Forest, Plains, Mountains, Desert, Lake
- All biomes have equal generation chance — no biome dominates by default
- Cellular automata drives terrain evolution every tick: trees spread and thin, sand reclaims desert borders, water floods during rain, grasslands shift to plains or forest based on tree density
- **Drought system** — growth rates decrease and decay rates increase with every tick without rain; extended dry periods reshape biomes over time
- **Weather** — rain events gate water spreading; longer dry periods between storms (30 seconds to 5 minutes between events)
- Zones auto-reclassify when terrain composition shifts (e.g. 50%+ water → Lake biome)

### Structures & Dungeons
- **Houses** — wood floors, resident NPC, chest with loot
- **Caves** — multi-level stone dungeons with hostile spawns, ore deposits, and deep chests
- **Mineshafts** — miner-built caves with higher ore density
- Structure interiors are full simulation zones: entity AI, cellular automata, spawning, and item decay all run inside just like on the overworld
- NPCs enter caves only when chasing a target inside — they walk to the door and enter in pursuit

### Combat
- Melee attack (weapon required), blocking (90% damage reduction), magic
- NPC combat uses probabilistic attack rolls — no fixed cooldown rhythm
- 8-cell detection radius; NPCs pursue, flank, and flee based on health
- Followers fight alongside you and never target you

### Crafting & Items
- 2-item crafting, order-independent
- Weapons: bone sword, stone axe, club, enchanted sword, enchanted axe
- Tools: axe, hoe, shovel, pickaxe, bucket, watering can
- Magic: star spell, magic stone, magic wand, runestones (lightning, fire, ice, poison, shadow)
- Iron ore pipeline: mine ore → smelt ingots → forge iron sword
- Skeleton follower: craft skeleton bones → summon a skeleton that fights for you

### Other Systems
- Quest system with 11 quest types and a quest arrow pointing to your active target
- Faction system: warriors form colored factions with leaders; goblins/bandits form raiding clans
- Day/night cycle with skeleton spawning at night and daylight damage on undead
- Hunger and thirst survival mechanics
- Enchantment system: star spells freeze cells or slow entities
- Autopilot (Shift+A): an AI proxy plays for you based on your active quest
- Save/load: full game state including world cells, entities, quests, followers, and weather

---

## Controls

### Movement
| Key | Action |
|---|---|
| W / ↑ | Move up |
| S / ↓ | Move down |
| A / ← | Move left |
| D / → | Move right |

### Actions
| Key | Action |
|---|---|
| Space | Interact — talk, enter structure, open chest, pick up |
| E | Pick up cell or items from target tile |
| P | Place selected item as a cell |
| N | Open NPC trade |
| B | Toggle blocking (90% damage reduction) |
| V | Toggle friendly fire |
| L | Cast star spell — enchants targeted cell or entity |
| K | Release / reverse spell |

### Inventory & UI
| Key | Action |
|---|---|
| I | Items tab |
| T | Tools tab |
| M | Magic tab |
| F | Followers tab |
| C | Crafting tab |
| X | Attempt craft with selected items |
| Q | Toggle quest panel |
| Shift+Q | Get / turn in quest from inspected NPC |
| 1–9, 0 | Select inventory slot |
| J | Release selected follower |
| Shift+A | Toggle autopilot |
| Escape | Pause / unpause |

### Pause Menu
| Key | Action |
|---|---|
| S | Save game |
| M | Return to main menu |

---

## Our Unique "Open Core" Model

We want this project to be as accessible as possible while ensuring the core system continually improves for everyone. We operate on an **Open Core with Reciprocity** model.

- **Build & Sell:** You are free to use this project to build and sell your own commercial games or applications. No mandatory royalties or profit-sharing.
- **Keep Your IP:** Your original assets, story, and unique branding belong 100% to you.
- **Share the Upgrades:** If you modify or improve the *base project code*, we require that you grant us the right to roll those improvements back into the main repository for the whole community to enjoy.
- **Official Branding:** Want to use our trademark, get official ecosystem integration, or be promoted on our channels? Check out our [Community Support Program (CSP)](commercial_use.md).

---

## Get Paid to Contribute

We believe open-source contributors should be rewarded. We run a **Community Contributor Reward Pool** funded by our Patreon and proceeds from commercial CSP partners. If you contribute code, art, or fixes that get merged into the base project, you may be eligible for a discretionary cash reward.

See [CONTRIBUTING.md](contributing.md) for the full CLA and reward pool details.

See [BOUNTIES.md](BOUNTIES.md) for a prioritized list of open features with estimated reward allocations.

---

## Quick Links

| Document | Purpose |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | What has changed and when |
| [ROADMAP.md](roadmap.md) | Planned features — the authoritative design wishlist |
| [BOUNTIES.md](BOUNTIES.md) | Open bounties with reward estimates |
| [CONTRIBUTING.md](contributing.md) | Contributor License Agreement and Reward Pool details |
| [COMMERCIAL_USE.md](commercial_use.md) | Rules for indie monetization vs. CSP |
| [Legal Disclosures](Legal%20Disclosures.md) | Full legal terms |
| [current_features_and_planned.md](current_features_and_planned.md) | Full feature reference with all controls and config values |

---

## Support the Project

If you love what we are building, support the project on Patreon:
**https://patreon.com/starcellgame**

Your support goes directly toward funding community contributors.
