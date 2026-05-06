# Contributor License Agreement & Reward Policy

By submitting any contribution to this project (via pull request, issue tracker, Discord, or other official channels), you agree to the following terms:

## 1. Definition of Contribution
Contributions include, but are not limited to: Code, technical systems, artwork, animation, audio, narrative design, documentation, bug reports, and community tools.

## 2. Rights Granted (CLA)
You grant the project owner (OpenStar Project) a perpetual, irrevocable, worldwide, royalty-free, and non-exclusive license to:
* Use, modify, and distribute your contribution.
* Integrate it into the base project or related commercial products.
* Sublicense it as part of the project.
* **Note:** You retain the copyright to your original work and the right to use your contribution elsewhere.

## 3. Original Work Requirement
You confirm that your contribution is your original creation, or you have the explicit legal right to submit it under these terms.

## 4. Community Reward Pool
We believe in rewarding the talent that builds this ecosystem. The Contributor Reward Pool is funded by **90% of our Patreon revenue** PLUS **100% of proceeds generated from the Community Support Program (CSP)**.

See **[BOUNTIES.md](BOUNTIES.md)** for a prioritized list of the most-wanted features and the estimated percentage of the monthly pool each would be considered for if contributed.

* **Distribution Model:** The total fund pool is distributed proportionately based on integrated contributions in the current base version, estimated functional impact, and asset scope.
* **Maintainer Discretion:** Final reward allocation decisions and contribution valuations are made at the sole discretion of the Project Manager. Unused funds roll over to future distributions.
* **Payment Nature:** Rewards are discretionary community "thank you" gifts. They do not constitute an employer-employee relationship, royalties, profit-sharing, equity, or a guarantee of future payment.

## 5. Dispute Resolution
Any disputes arising from participation in the project or the contributor reward program shall be resolved through binding arbitration conducted in the State of Texas, United States, under the rules of the American Arbitration Association (AAA). Each party shall bear its own legal costs.

---

# Technical Contributor Guide

Everything below is practical — how to set up, how to submit, and what to watch out for.

---

## Dev Setup

**Requirements:** Python 3.9+ and pygame 2.x. No other dependencies.

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/starcell.git
cd starcell

# 2. Install pygame
pip install pygame        # or: pip3 install pygame

# 3. Run the game
python main.py            # or: python3 main.py
```

The game launches directly from `main.py`. No build step, no virtual environment required.

---

## Branch Workflow

```
main          — stable release; players download this
dev           — integrated work; tested before going to main
your-branch   — your personal feature branch
```

**How to submit a contribution:**

1. Fork the repository on GitHub
2. Create a feature branch off `dev`: `git checkout -b my-feature dev`
3. Make your changes and commit
4. Open a Pull Request targeting the **`dev` branch** (not `main`)
5. Describe what you changed and link to the bounty item if applicable

Your work lands in `dev` first, gets tested, then the project owner promotes it to `main`.

**Before starting a large feature**, open a GitHub issue to confirm it is not already in progress and to discuss your approach. This is especially important for bounty items — it prevents two people building the same thing simultaneously.

---

## Claiming a Bounty

1. Check [BOUNTIES.md](BOUNTIES.md) for open items
2. Open a GitHub issue: "Claiming bounty #N — [Feature Name]"
3. Wait for acknowledgment from the project owner before starting
4. Submit your work as a PR to `dev` with a link to the bounty item

Partial contributions count — a single spell, a single new NPC type, or three new item definitions all earn partial credit.

---

## The Dual-Import Pattern (Critical)

This is the most common first-time contributor mistake. When you add a new **cell type**, **item**, or **recipe**, you must update **two separate places**:

| File | Used by |
|---|---|
| `data/cells.py` | All modular systems (`ai/`, `world/`, `systems/`) |
| `constants.py` | Legacy monolith files (`npc_ai.py`, `game_core.py`) |

These files are **not linked** — editing one does not update the other. If you only update `data/cells.py`, the NPC AI in `npc_ai.py` will not see your new cell type. If you only update `constants.py`, the modular systems won't see it.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full checklist for each data type.

---

## Code Conventions

**No debug prints in main source files.** Debug output belongs in `autopilot.py` or the `debug/` directory only. Use the Watchdog (`debug/watchdog.py`) for persistent logging. Player-facing feedback can use print() as a short-term placeholder but should move to the HUD notification system.

**Docs update rule.** If you change behavior in a file that has a corresponding `docs/*_plain.md` guide, update the guide in the same PR. Documented files: `npc_ai.py`, `ai/movement.py`, `ai/actions.py`, `game_core.py`, `world/generation.py`, `world/zones.py`.

**Actor pattern.** Action primitives in `ai/actions.py` support `actor='player'` or an entity object. Use these shared primitives rather than duplicating harvest/drop/XP logic in player-specific code.

**State machine first.** New NPC behavior goes into the state machine (`npc_ai.py:update_entity_ai_state`) and behavior config (`data/entities.py:NPC_BEHAVIORS`). Avoid adding new dispatch branches to `update_entity_ai`.

**Minimum viable change.** Only modify what the feature requires. Don't clean up surrounding code, add comments to unchanged functions, or refactor things adjacent to your work — those belong in separate PRs.

---

## PR Checklist

Before opening a pull request:

- [ ] Tested by running `python main.py` and exercising the feature in-game
- [ ] Both `constants.py` AND the relevant `data/` module updated (if adding cell/item/recipe)
- [ ] Sprite file added to `sprites/` and registered in `game_core.py:load_sprites` (if adding a visual)
- [ ] Corresponding `docs/*_plain.md` updated (if modifying a documented file)
- [ ] No debug `print()` statements left in non-autopilot, non-debug files
- [ ] PR targets the `dev` branch, not `main`

---

## Understanding the Codebase

Read [ARCHITECTURE.md](ARCHITECTURE.md) for:
- The full MRO chain and what each module handles
- How a game tick flows from input to NPC AI
- Key data structures (`self.entities`, `self.screens`, `self.screen_entities`)
- The dual-import pattern with full checklists
- A "where to start" table by task type

The `docs/` directory has plain-language guides for every major source file. Start with the guide for whichever file your contribution touches.
