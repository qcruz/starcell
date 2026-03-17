# StarCell — Art Direction

StarCell uses lo-fi pixel art as a deliberate aesthetic choice. Small sprites, readable tiles, and a minimal UI keep the game legible at a glance and the engine adaptable. Art direction should serve the world-building tone: old, inhabited, consequential — classic high fantasy without being ornate or overwrought.

> **Note:** This document is a working reference for future collaborators. Sections marked with placeholder language will be developed with input from art contributors.

---

## Style & Aesthetic

Classic high fantasy pixel art. Primary references: early Legend of Zelda (top-down tile clarity), RPG Maker 2000-era character sprites (readable at small scale), and dark fantasy palettes from games like Dark Souls. The world should feel lived-in — weathered stone, overgrown ruins, worn wood. Bright colors are reserved for important interactables: loot, spells, status effects. Environmental tiles should read clearly and not compete visually with entities or UI.

Sprites are intentionally simple. A clear silhouette at small scale is more important than detail. Players should be able to identify entity type, threat level, and movement direction at a glance.

---

## Sprite Conventions

- **Tile size:** 16×16 base unit for world cells and small entities
- **Character sprites:** multi-frame sheets covering four directional facing (up, down, left, right) with idle and walk cycles
- **Structure sprites:** individual PNGs per structure type, loaded by `engine/sprite_manager.py`
- **Item icons:** 16×16 or 32×32 inventory icons; should read clearly at small size
- **Naming convention:** lowercase_snake_case matching the key used in `CELL_TYPES`, `ENTITY_TYPES`, or `ITEMS` (e.g. `iron_ore.png`, `well.png`, `iron_sword.png`)
- Sprites live in `sprites/`; structure sprites loaded via `create_structure_sprites()` in `engine/sprite_manager.py`

> Collaborator note: Placeholder sprites are in use. All art is replaceable without touching game logic — swap the file, keep the name.

---

## Color Palette

High fantasy, biome-differentiated. Working palette targets:

- **Overworld:** earthy greens, browns, warm grays; blue-greens for water; yellow-orange for sand/desert
- **Underground/Caves:** deep grays, cool blues, muted reds for iron ore; black voids
- **Structures:** warm stone grays, weathered wood browns; torch-lit interiors with amber warmth
- **Hostile entities:** saturated reds and sickly yellows to read as threatening against neutral backgrounds
- **UI/HUD:** dark near-black backgrounds, off-white text, muted gold accents for important values

Exact hex values and a formal swatch sheet to be developed with art contributor input.

---

## UI Aesthetic

Minimal. The HUD should occupy as little screen space as possible and communicate only what the player needs right now. Inspiration: Zelda-style hearts, minimal text, iconographic shorthand over verbose labels.

- Dark, slightly transparent panel backgrounds — no bright UI chrome
- Icon-first: health, energy, status effects should be glanceable icons, not text readouts
- Inventory and subscreen panels use consistent padding and a flat, bordered style
- No animated UI flourishes beyond item pickup feedback and level-up notification

---

## Animation Standards

- **Idle:** 1–2 frame loop or static; entities at rest should feel alive but not distracting
- **Walk:** 2–4 frame cycle per direction; prioritize clarity of movement direction over smoothness
- **Attack:** 1–2 frame hit pose; brief enough to read as reactive
- **Death:** simple fade or collapse; not elaborate
- **Ambient cells** (water shimmer, fire flicker, growing crops): 2–4 frame loop; subtle

All animation timing is tick-based, not real-time, to stay consistent with the simulation loop.

---

## Asset Pipeline

1. Create PNG in `sprites/` using the correct naming convention
2. For structure sprites: register in `engine/sprite_manager.py` `create_structure_sprites()`
3. For cell sprites: ensure key matches entry in `CELL_TYPES` (both `constants.py` and `data/cells.py`)
4. For item icons: ensure key matches entry in `ITEMS`
5. Sprite sheets for character animations follow the four-direction layout expected by `SpriteManager`

Sprites are loaded at startup. No runtime asset loading — all assets must be present at launch.
