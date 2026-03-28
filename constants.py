#!/usr/bin/env python3
"""
StarCell v1.1.37 - Top-down 2D Procedural Survival RPG
Beta Version 1.37 - AI System Timer Fix

CHANGELOG v1.37:
- CRITICAL FIX: AI state system now works properly with timers:
  * Added ai_state_timer to prevent constant state switching
  * State changes only happen every 1-3 seconds (not 60x/sec)
  * Warriors stay locked on targets for at least 2 seconds
  * Combat state persists - only 5% chance to disengage every 2 seconds
  * Targeting state persists - entities focus for 3 seconds before checking again
  
- Improved AI behavior flow:
  * Entities start in 'wandering' state (not idle)
  * State transitions respect timers - no more flickering
  * Warriors with 80% aggression + 5% passive = hunt hostiles effectively
  * When targeting hostile: scan zone → find enemy → enter combat → stay locked
  
- Timer durations:
  * Idle: 60 ticks (1 second) between checks
  * Wandering: 120 ticks (2 seconds) between checks
  * Targeting: 180 ticks (3 seconds) focus time
  * Combat: 60-120 ticks, locked until target dies or disengage roll
  
- Warriors should now actively hunt and eliminate hostiles!
"""

import pygame
import random
import json
import os

# Initialize Pygame
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

# Constants
CELL_SIZE = 40
GRID_WIDTH = 24
GRID_HEIGHT = 18
SCREEN_WIDTH = GRID_WIDTH * CELL_SIZE
SCREEN_HEIGHT = GRID_HEIGHT * CELL_SIZE + 80
FPS = 60
# Catch-up system constants
MAX_CATCHUP_PER_FRAME = 2  # Max zones to catch up at once
MAX_CYCLES_TO_SIMULATE = 100  # Cap at 100 cycles (6000 ticks ~= 100 seconds)

# Faction System
FACTION_COLORS = ['Red', 'Blue', 'Gold', 'Silver', 'Crimson', 'Jade', 'Onyx', 'Azure', 'Emerald', 'Scarlet']
FACTION_SYMBOLS = ['Lion', 'Dragon', 'Wolf', 'Bear', 'Eagle', 'Serpent', 'Tiger', 'Phoenix', 'Raven', 'Hawk']

# AI Behavior Timers (in ticks at 60 FPS)
# Adjust this base value to speed up or slow down all AI state transitions
AI_TIMER_BASE = 10  # Base unit for all AI timers
# Derived timer constants:
# - 1x base (10 ticks) = 0.17 seconds - quick reactions
# - 3x base (30 ticks) = 0.5 seconds - moderate delay
# - 6x base (60 ticks) = 1 second - standard delay
# - 12x base (120 ticks) = 2 seconds - longer focus
# - 18x base (180 ticks) = 3 seconds - extended focus

# AI Behavior Traits (all entities must have these in ai_params):
# - aggressiveness: Chance to enter targeting from idle/wander (0.0-1.0)
# - passiveness: Chance to drop target and wander (0.0-1.0)
# - idleness: Chance to stop and idle while wandering (0.0-1.0)
# - flee_chance: When threatened, chance to flee vs fight (0.0-1.0)
# - combat_chance: When threatened, chance to fight (typically 1.0 - flee_chance)
# - target_types: List of what to target ['hostile', 'food', 'water', 'structure', 'resource']

# Hostile NPC Faction System
HOSTILE_FACTION_COLORS = ['Shadow', 'Black', 'Dark', 'Night', 'Crimson', 'Blood', 'Pale', 'Cursed', 'Rotten', 'Twisted']
HOSTILE_FACTION_SYMBOLS = ['Fang', 'Claw', 'Knife', 'Death', 'Hunger', 'Blade', 'Skull', 'Bone', 'Thorn', 'Venom']

# ============================================================================
# GAME BALANCE CONFIGURATION - Adjust these to tune gameplay
# ============================================================================

# Weather System
# weather_timer increments once per update_weather() call (every UPDATE_FREQUENCY=30 ticks
# during normal play; every tick during time-pass). So RAIN_FREQUENCY_* are in
# update_weather call-counts, not raw ticks.
# Normal play: MIN=120 → ~1 min between rains; MAX=600 → ~5 min between rains.
# Time-pass (600 sim ticks, no gate): MIN=120 → rain fires ~4-5 times during sim.
RAIN_FREQUENCY_MIN = 120    # minimum zone updates between rains (per zone)
RAIN_FREQUENCY_MAX = 2000   # maximum zone updates between rains — long drought periods possible
RAIN_DURATION_MIN = 30      # rain lasts ≥30 zone updates
RAIN_DURATION_MAX = 180     # rain lasts ≤180 zone updates
RAIN_WATER_SPAWNS = 5      # Water cells created per rain tick per screen
RAIN_GRASS_SPAWNS = 8      # Dirt→Grass conversions per rain tick

# Day/Night Cycle
DAY_LENGTH = 150          # Day duration in ticks (2.5 minutes at 60 FPS)
NIGHT_LENGTH = 150        # Night duration in ticks (2.5 minutes at 60 FPS)
NIGHT_OVERLAY_ALPHA = 40  # Darkness overlay opacity (0-255, subtle at 40)

# Quest System
QUEST_COOLDOWN = 300      # Ticks before new quest target assigned after completion (5 seconds)
QUEST_XP_MULTIPLIER = 10  # XP reward = target_level × this value

# ═══════════════════════════════════════════════════════════════════════════════
# CELLULAR AUTOMATA — RATE HIERARCHY
# See docs/ca_rules.md for full rule descriptions and firing conditions.
#
# Structure:
#   CA_BASE_RATE          — master knob, scales the entire CA system
#   Tier 1 class rates    — CA_GROWTH_RATE, CA_DECAY_RATE, CA_SPREAD_RATE,
#                           CA_WATER_EVAP_RATE — tune a whole class of rules
#   Tier 1 named rules    — global rules expressed as N × class rate
#   Tier 2 cross-biome    — rules that fire at biome-type boundaries
#   Tier 3 biome-specific — rules that only apply inside one biome
#   Constructed / Agri.   — placed-cell decay, crop drought tiers
# ═══════════════════════════════════════════════════════════════════════════════

CA_BASE_RATE = 0.001            # master knob — tune to speed/slow all CA at once
BASE_DECAY_RATE = CA_BASE_RATE  # legacy alias — do not use in new code

# ── Tier 1 class rates ──────────────────────────────────────────────────────
# Adjust these to shift a whole class of rules simultaneously.
# CA_GROWTH_RATE and CA_DECAY_RATE should stay roughly equal;
# set CA_DECAY_RATE slightly above CA_GROWTH_RATE to cause long-term natural
# drift toward decay — combined with the rain boost to _growth this creates
# zones that green up during rain and slowly dry without it.
CA_GROWTH_RATE     = 0.1 * CA_BASE_RATE   # 0.0001 — base cell upgrade rate
CA_DECAY_RATE      = 0.1 * CA_BASE_RATE   # 0.0001 — base cell downgrade rate
CA_SPREAD_RATE     = 2   * CA_BASE_RATE   # 0.002  — natural neighbor-copy diffusion
CA_WATER_EVAP_RATE = 8   * CA_BASE_RATE   # 0.008  — water → biome base cell baseline

# ── Tier 1: Global growth rules (× CA_GROWTH_RATE) ──────────────────────────
DIRT_TO_GRASS_RATE          = 20.0 * CA_GROWTH_RATE  # 0.002 — dirt → grass with 2+ water neighbors
DIRT_TO_GRASS_WATER_RATE = 10.0 * CA_GROWTH_RATE  # 0.001 — dirt → grass with 1 water neighbor
GRASS_TO_TREE_RATE       = 1.0 * CA_GROWTH_RATE  # 0.0001 — grass → tree (needs water + tree neighbor, not desert)
GRASS_TO_FLOWER_RATE     = 1.0 * CA_GROWTH_RATE  # 0.0001 — flowers spread to grass near water
GRASS_TO_FLOWER_PATTERN_RATE = 5.0 * CA_GROWTH_RATE  # 0.0005 — grass near water spontaneously grows flower patterns
SAND_TO_DIRT_STONE_RATE  = 2.0 * CA_GROWTH_RATE  # 0.0002 — sand weathers to dirt near stone/cobblestone

# ── Tier 1: Global decay rules (× CA_DECAY_RATE) ────────────────────────────
GRASS_TO_DIRT_RATE         = 0.1  * CA_DECAY_RATE  # 0.00001  — grass withers to dirt without water
DIRT_TO_SAND_DROUGHT_RATE  = 0.05 * CA_DECAY_RATE  # 0.000005 — dirt → sand in severe drought (no water, no grass)
TREE_TO_GRASS_RATE         = 5.0  * CA_DECAY_RATE  # 0.0005   — tree → grass in crowded zones (zones.py)
TREE_TO_GRASS_CROWD_RATE   = 10   * CA_DECAY_RATE  # 0.001    — tree thins when touching any adjacent tree
TREE_TO_GRASS_DROUGHT_RATE = 3.0  * CA_DECAY_RATE  # 0.0003   — tree dies to grass in drought (severity > 0.5, no water)
CACTUS_TO_SAND_DROUGHT_RATE = 3.0 * CA_DECAY_RATE  # 0.0003   — cactus dies to sand in drought (mirrors tree)
FLOWER_TO_GRASS_RATE       = 5.0  * CA_DECAY_RATE  # 0.0005   — flowers die from overcrowding (4+) or no water

# ── Tier 1: Water dynamics (× CA_WATER_EVAP_RATE) ───────────────────────────
WATER_TO_BASE_ISOLATED_RATE = 2    * CA_BASE_RATE         # 0.002 — isolated water (≤1 neighbor) → biome base cell
DEEP_WATER_TO_WATER_RATE    = 0.5  * CA_WATER_EVAP_RATE  # 0.004 — deep water recedes when edge exposed
WATER_TO_DEEP_WATER_RATE    = 2.5  * CA_WATER_EVAP_RATE  # 0.02  — water deepens when all 4 cardinals are water
SAND_TO_DIRT_WATER_RATE     = 10   * CA_WATER_EVAP_RATE  # 0.08  — sand → dirt near any water (universal)
DIRT_TO_WATER_RAIN_RATE     = 0.75 * CA_WATER_EVAP_RATE  # 0.006 — rain floods dirt/sand near 3+ water cells
GRASS_TO_WATER_RAIN_RATE    = 1.0  * CA_WATER_EVAP_RATE  # 0.008 — grass → water during rain near water
DIRT_TO_FLOWER_WATER_RATE   = 0.4  * CA_WATER_EVAP_RATE  # 0.003 — dirt at water boundary → flower pattern

# ── Tier 1: Spread (× CA_SPREAD_RATE) ───────────────────────────────────────
BIOME_BORDER_SPREAD_RATE  = 2.0 * CA_SPREAD_RATE   # 0.004 — zone-edge cells copy adjacent zone's primary biome cell
TERRAIN_DIFFUSION_RATE    = 1.0 * CA_GROWTH_RATE   # 0.0001 — slow catch-all: base terrain bleeds into unlike neighbors

# ── Tier 2: Cross-biome — desert edge interactions ──────────────────────────
# Fire when desert-type cells (SAND) are adjacent to non-desert terrain.
GRASS_TO_DIRT_SAND_RATE  = 1.5 * CA_SPREAD_RATE  # 0.003 — grass erodes to dirt near sand
DIRT_TO_SAND_SPREAD_RATE = 2.0 * CA_SPREAD_RATE  # 0.004 — dry dirt converts to sand near sand

# ── Tier 1: Ambient erosion (very slow background decay, all biomes) ─────────
DIRT_TO_SAND_AMBIENT_RATE        = 0.03 * CA_DECAY_RATE  # 0.000003 — global baseline dirt→sand erosion
DIRT_TO_SAND_DESERT_AMBIENT_RATE = 0.10 * CA_DECAY_RATE  # 0.00001  — slightly faster in desert
SAND_TO_STONE_AMBIENT_RATE       = 0.01 * CA_DECAY_RATE  # 0.000001 — very slow sand lithification (global)
STONE_SAND_TO_DIRT_RATE          = 0.05 * CA_DECAY_RATE  # 0.000005 — sand adjacent to stone weathers to dirt

# Entity Survival
HUNGER_DECAY_RATE = 0.02        # Base hunger loss per decay call (humanoids get 6× this)
THIRST_DECAY_RATE = 0.5         # Base thirst loss per decay call — drains in ~200 calls (~half max rain gap)
HUMANOID_DRAIN_MULTIPLIER = 6.0 # Humanoid hunger multiplier
HUMANOID_THIRST_MULTIPLIER = 2.0 # Humanoid thirst multiplier (2× base — drain in ~100 calls)
STARVATION_DAMAGE = 1.0         # HP loss per decay call when hunger==0
DEHYDRATION_DAMAGE = 1.5        # HP loss per decay call when thirst==0
BASE_HEALING_RATE = 1.5         # HP regen per tick when fed/hydrated
CAMP_HEALING_MULTIPLIER = 2.0   # Healing boost near camps
HOUSE_HEALING_MULTIPLIER = 3.0  # Healing boost near houses

# NPC Behavior Rates (chance per second, tick % 60 == 0)
FARMER_HARVEST_RATE = 0.3       # Probability to harvest mature crops (farmer_behavior)
FARMER_TILL_RATE = 0.1          # Probability to till grass/dirt (farmer_behavior)
FARMER_PLANT_RATE = 0.5         # Probability to plant seeds (increased for food sustainability)
LUMBERJACK_BASE_CHOP_RATE = 0.5 # Base tree chopping probability (further increased for visible work)
LUMBERJACK_DENSITY_BONUS = 0.02 # Bonus per nearby tree (max +30%) (lumberjack_behavior)
LUMBERJACK_BUILD_RATE = 0.05    # Probability to build house with 10 wood (lumberjack_behavior)
GOBLIN_CAMP_ATTACK_RATE = 0.05  # Probability to attack camp (hostile_structure_behavior)
GOBLIN_HOUSE_ATTACK_RATE = 0.01 # Probability to attack house (hostile_structure_behavior)
NPC_CAMP_PLACE_RATE = 0.01      # Probability to place camp per second (npc_place_camp)

# NPC Movement Timing
NPC_BASE_MOVE_INTERVAL = 180    # Base ticks between NPC movements (3 seconds)
NPC_MOVE_VARIANCE = 60          # Random variance in movement timing (±1 second)
NPC_COMBAT_MOVE_INTERVAL = 18   # Fast movement during combat (~0.3 seconds)

# AI State Timing
AI_STATE_IDLE_DURATION = 90     # Ticks for idle state (1.5 seconds — slightly longer idle)
AI_STATE_WANDER_DURATION = 120  # Ticks for wander state (2 seconds)
AI_STATE_TARGETING_DURATION = 180  # Ticks for targeting state (3 seconds)
AI_STATE_COMBAT_DURATION = 120  # Ticks for combat state (2 seconds)
AI_STATE_FLEE_DURATION = 120    # Ticks for flee state (2 seconds)

# Combat Constants
HEALTH_LOW_THRESHOLD = 0.5      # 50% health - considered low
HEALTH_CRITICAL_THRESHOLD = 0.3  # 30% health - critical condition
ADJACENT_DISTANCE = 1           # Distance considered adjacent for actions
COMBAT_FLEE_CHANCE = 0.4        # 40% chance to flee when health critical
COMBAT_DISENGAGE_CHANCE = 0.05  # 5% chance to disengage from combat
HOSTILE_DETECTION_RANGE = 8     # Cells within which to detect hostiles (for fleeing)

# NPC Structure Behavior
NPC_STRUCTURE_EXIT_CHANCE = 0.60  # 60% chance per update to try exiting structure

# Wizard System
WIZARD_SPELL_COOLDOWN = 180     # Ticks between spell casts (3 seconds)
WIZARD_CAVE_EXPLORE_CHANCE = 0.5  # 50% chance to explore caves
WIZARD_FACTION_JOIN_CHANCE = 0.3  # 30% chance to join faction
WIZARD_SPELL_RANGE = 6          # Maximum spell casting range

# Action Success Rates
FARMER_HARVEST_SUCCESS = 0.4    # 40% harvest success
FARMER_TILL_SUCCESS = 0.25      # 25% till success
FARMER_PLANT_SUCCESS = 0.45     # 45% plant success (increased)
LUMBERJACK_CHOP_SUCCESS = 0.85   # 85% chop success (increased for much faster work)
LUMBERJACK_BUILD_SUCCESS = 0.35 # 35% build success
MINER_MINE_SUCCESS = 0.5        # 50% mine success (increased for aggression)
PEACEFUL_NPC_MIGRATE_RATE = 0.05 # Chance to migrate if duplicate type in zone (update_entity_ai)
ZONE_CHANGE_COOLDOWN = 1800  # Ticks (30 seconds at 60 FPS) before entity can change zones again (seek_zone_exit path)
NPC_SEAMLESS_CROSS_COOLDOWN = 30   # Ticks (0.5 s) anti-bounce cooldown for seamless zone crossing
NPC_PEACEFUL_WANDER_CHANCE = 0.60  # Probability a peaceful NPC actually wanders when idle (was implicit 1.0)
TARGET_STUCK_THRESHOLD = 180  # Ticks (3 seconds) before target is considered stuck and added to memory_lane
NPC_TREE_CLEAR_RATE = 0.05  # Non-lumberjack NPCs can clear trees (no wood collected)
ENHANCED_SETTLEMENT_RATE = 0.25 # Settlement rate when zone needs specific role (farmer/lumberjack/miner)

# Trader Path Building (Cellular Automata)
TRADER_PATH_BUILD_RATE = 0.6    # Chance to convert cell to dirt while walking (increased for traders/guards/miners)
TRADER_COBBLE_RATE = 0.35       # Chance to upgrade dirt to cobblestone
TRADER_TRAVEL_MODE = True       # Traders prioritize traveling between zone exits

# Entity Movement & Exploration
ZONE_TRANSITION_BASE_RATE = 0.03    # Chance per update for animals/hostiles to migrate (update_entity_ai)
ENTITY_MEMORY_LENGTH = 8           # Pathfinding memory (cells remembered) (move_entity_towards)
EATING_CHANCE_CATCHUP = 0.6         # Chance to eat per cycle during catch-up (catch_up_entities)
DRINKING_CHANCE_CATCHUP = 0.6       # Chance to drink per cycle during catch-up (catch_up_entities)
WATER_DECAY_ON_DRINK = 0.7          # Chance water becomes dirt when drunk (find_and_move_to_water)
GRASS_DECAY_ON_EAT = 0.6            # Chance grass becomes dirt when eaten (find_and_move_to_food)
OLD_AGE_DAMAGE = 2.0                # Health loss per zone-update tick when age exceeds max_age

# Entity Spawning
SPAWN_CHANCE_MULTIPLIER = 1.0   # Global spawn rate multiplier (1.0 = normal) (spawn_entities_for_screen)
FOREST_BIOME_CHANCE = 0.60      # 60% of zones are forest (generate_screen)
PLAINS_BIOME_CHANCE = 0.20      # 20% of zones are plains (generate_screen)
MOUNTAINS_BIOME_CHANCE = 0.15   # 15% of zones are mountains (generate_screen)
DESERT_BIOME_CHANCE = 0.05      # 5% of zones are desert (generate_screen)

# Raid Event System
RAID_CHANCE_BASE = 0.025        # 2.5% base raid chance (halved; structures lower it further)
RAID_POPULATION_THRESHOLD = 4   # Minimum entities in zone to trigger raid check
HIDDEN_CAVE_SPAWN_CHANCE = 0.50 # 50% chance to spawn hidden cave during raid (caves primary source)
NATURAL_CAVE_ZONE_CHANCE = 0.08 # 8% chance a zone gets a natural cave on generation
PLAYER_MINESHAFT_BASE_CHANCE = 0.05 # 5% base chance for player mining to create mineshaft
MINESHAFT_DEPTH_DIVISOR = 2.0  # Each depth level halves the mineshaft creation chance
MINER_MINESHAFT_CHANCE = 0.03  # 3% chance per mine action for NPC miners
MINESHAFT_MAX_PER_ZONE = 2     # Max mineshafts NPCs can create in one zone
MINER_WELL_BUILD_RATE = 0.02   # 2% chance per action for miner to build a well
DESERT_ROCK_FORMATION_RATE = 0.00008  # Sand slowly forms into stone in deserts
DESERT_ORE_FORMATION_RATE  = 0.00002  # Stone very rarely yields ore in deserts
WARRIOR_PROMOTION_CHANCE = 0.60 # 60% chance highest level entity becomes warrior after raid clear
KEEPER_ASSIGNMENT_RATE = 0.02  # 2% chance per zone update to assign a vacant keeper slot

# NPC quest queue system
NPC_QUEST_QUEUE_MAX = 3  # Max quests per NPC including base quest
# Base quest per NPC type — permanent, never removed from queue.
# All peaceful humanoids included. Later, quest assignment will be
# gated by per-NPC favor score — for now all are assignable freely.
NPC_BASE_QUEST = {
    'FARMER':     'FARM',
    'LUMBERJACK': 'LUMBER',
    'MINER':      'MINE',
    'TRADER':     'EXPLORE',
    'GUARD':      'COMBAT_HOSTILE',
    'WARRIOR':    'COMBAT_HOSTILE',
    'COMMANDER':  'COMBAT_ALL',
    'BLACKSMITH': 'GATHER',
    'WIZARD':     'SEARCH',
}

# Keeper patrol types and their movement radii (Manhattan distance from keeper_target_pos).
# Type 1 (guard): stands within 1 cell of target — door guard, escort
# Type 2 (patrol): roams within 5 cells of target — area patrol
# Type 3 (zone): anchored to zone but no specific target — full-zone roam (default)
KEEPER_RANGE = {1: 1, 2: 5, 3: None}

# ── NPC targeting priority scoring constants ─────────────────────────────────
# See ai/targeting_overview.md for full design doc and rationale.
KEEPER_BASE          = {1: 50, 2: 35, 3: 20, 4: 10}  # base score per keeper type
KEEPER_URGENCY_SCALE = {1: 8,  2: 5,  3: 0,  4: 0}   # score added per cell of drift past range
QUEST_BASE           = 100   # flat score for active assigned/lore quest target
ROLE_BASE            = 15    # flat score for archetype work (farming, mining, etc.)
SPECIAL_BASE         = 50    # flat score per eligible special-pool candidate
SPECIAL_LOCK_TICKS   = 60    # ticks a chosen special type stays locked within the special pool
TARGET_LOCK_TICKS    = 200   # ticks a chosen target type is held before re-rolling
RESOURCE_BASE        = 100   # max resource score (at 0% remaining); quadratic urgency curve
MIN_RESOURCE_URGENCY = 0.30  # stat must be below 70% full before food/water enters candidates

# Maps quest focus type → role target type for the role tier of targeting.
ROLE_TARGET_BY_QUEST = {
    'FARM':   'crop',
    'LUMBER': 'tree',
    'MINE':   'stone',
    'GATHER': 'resource',
}

# Cells that clearing_action will NOT attack (structures, furniture, terrain walls).
CLEARING_EXEMPT = frozenset({
    'WALL', 'HOUSE', 'STONE_HOUSE', 'FORT', 'CAVE', 'CLIFF',
    'GRAVESTONE', 'BROKEN_GRAVESTONE',
    'LOCKED_CHEST', 'CHEST', 'OPEN_CHEST',
    'BOOKSHELF', 'WOOD_CHAIR', 'WOOD_TABLE', 'BED_BLUE', 'BED_WHITE',
    'WATER_TROUGH', 'SMALL_POTTED_PLANT',
    'WELL', 'DESERT_WELL',
    'WATER', 'DEEP_WATER',
})

# Maps entity type → keeper patrol type.  Defaults to 3 for anything not listed.
# Type 1: cell guard — stays within 1 tile of anchor
# Type 2: patrol    — stays within 5 tiles of anchor
# Type 3: zone      — stays within home zone (assigned on first zone entry for a faction)
# Type 4: domain    — stays within home domain (crosses zone boundaries within domain)
KEEPER_TYPE_BY_ENTITY = {
    'GUARD':      1,
    'WARRIOR':    1,
    'COMMANDER':  1,
    'BLACKSMITH': 2,
    'WIZARD':     2,
    'FARMER':     2,
    'LUMBERJACK': 2,
    'MINER':      2,
    'TRADER':     2,
}

# Maps entity type → keeper slot name for keeper assignment.
# KING intentionally omitted — singular, always traveling.
# All peaceful worker humanoids share one slot so a zone doesn't accumulate one of every type.
KEEPER_ENTITY_TYPE = {
    'WOLF':         'wolf',
    'BAT':          'bat',
    'GOBLIN':       'goblin',
    'BANDIT':       'bandit',
    'SKELETON':     'skeleton',
    'TERMITE':      'termite',
    'SHEEP':        'sheep',
    'DEER':         'deer',
    'RED_BIRD':     'red_bird',
    'BUTTERFLY':    'butterfly',
    'CHICKEN':      'chicken',
    'BLACK_SPIDER': 'black_spider',
    # Peaceful worker types share one 'humanoid' slot per zone
    'FARMER':     'humanoid',
    'GUARD':      'humanoid',
    'WARRIOR':    'humanoid',
    'COMMANDER':  'humanoid',
    'BLACKSMITH': 'humanoid',
    'WIZARD':     'humanoid',
    'LUMBERJACK': 'humanoid',
    'MINER':      'humanoid',
    'TRADER':     'humanoid',
}

# Miner & Structure Systems
MINER_CAVE_CREATE_CHANCE = 0.10 # 10% chance to create cave when mining at zone corners
CAMP_UPGRADE_CHANCE = 0.001     # 0.1% chance per update for camp to upgrade to house
CAVE_HOSTILE_SPAWN_CHANCE = 0.007 # 0.7% chance per cave per update to spawn hostile
TERMITE_SPAWN_CHANCE = 0.001      # 0.1% chance per zone per update to spawn termite (near trees) - reduced spawn rate
NIGHT_SKELETON_SPAWN_CHANCE = 0.007 # 0.7% chance per zone at night to spawn skeleton
SKELETON_DAYLIGHT_DAMAGE = 1       # HP damage per update to skeletons during daytime
HOUSE_DECAY_RATE = 0.0001       # 0.01% chance per update for house to decay naturally
WARRIOR_HOME_RETURN_INTERVAL = 600 # Ticks (10 seconds) between warrior home zone checks

# Zone Update System (simplified linear with probabilistic skipping)
UPDATE_FREQUENCY = 30               # Ticks between update cycles (30 = 0.5 sec)
MAX_ZONES_PER_UPDATE = 20           # Maximum zones to update per cycle
CURRENT_ZONE_UPDATE_CHANCE = 1.0    # 100% chance to update player's zone
CURRENT_ZONE_CELL_COVERAGE = 1.0    # Update 100% of cells in current zone
CURRENT_ZONE_ENTITY_COVERAGE = 1.0  # Update 100% of entities in current zone
BASE_ADJACENT_UPDATE_CHANCE = 0.5   # Base chance for adjacent zones (decreased from 0.8 for longer tail)
DISTANCE_1_CELL_COVERAGE = 0.9      # Update 90% of cells at distance 1
DISTANCE_1_ENTITY_COVERAGE = 0.9    # Update 90% of entities at distance 1
DISTANCE_2_CELL_COVERAGE = 0.8      # Update 80% of cells at distance 2
DISTANCE_2_ENTITY_COVERAGE = 0.8    # Update 80% of entities at distance 2
DISTANCE_3_CELL_COVERAGE = 0.6      # Update 60% of cells at distance 3+
DISTANCE_3_ENTITY_COVERAGE = 0.6    # Update 60% of entities at distance 3+
NEW_ZONE_INSTANTIATE_CHANCE = 0.025  # 2.5% chance to instantiate a new random zone per update cycle
ZONE_SOFT_CAP = 200                  # Overworld zone count above which new instantiation drops sharply

# ============================================================================
# END GAME BALANCE CONFIGURATION
# ============================================================================

# Colors
COLORS = {
    'GRASS': (74, 124, 58),
    'DIRT': (139, 111, 71),
    'WATER': (74, 144, 226),
    'DEEP_WATER': (50, 100, 180),
    'TREE1': (45, 80, 22),
    'TREE2': (35, 70, 18),
    'STONE': (107, 114, 128),
    'COBBLESTONE': (120, 120, 130),
    'CARROT1': (255, 140, 66),
    'CARROT2': (255, 120, 46),
    'CARROT3': (255, 100, 26),
    'SAND': (218, 165, 32),
    'WALL': (31, 41, 55),
    'HOUSE': (139, 69, 19),
    'FORGE': (80, 80, 80),  # Gray for forge
    'CAVE': (17, 24, 39),
    'MINESHAFT': (90, 70, 50),
    'SOIL': (101, 67, 33),
    'BLACK': (0, 0, 0),
    'WHITE': (255, 255, 255),
    'YELLOW': (251, 191, 36),
    'CYAN': (0, 255, 255),
    'UI_BG': (30, 30, 30),
    'GRAY': (128, 128, 128),
    'WOOD': (139, 90, 43),
    'PLANKS': (205, 133, 63),
    'INV_BG': (20, 20, 20),
    'INV_BORDER': (100, 100, 100),
    'INV_SELECT': (255, 215, 0),
    'FLOWER': (255, 100, 200),
    'IRON_ORE': (139, 90, 43),
    'WELL': (100, 80, 60),
    'GRAVESTONE': (130, 125, 135),
    'BED_BLUE': (70, 130, 180),
    'DESERT_WELL': (180, 140, 80),
    'CACTUS': (50, 120, 50),
    'BARREL': (120, 80, 40),
    'STONE_HOUSE': (110, 110, 120),
    'RUINED_SANDSTONE_COLUMN': (200, 160, 90),
    'CLIFF': (90, 80, 75),
    'BUSH': (34, 100, 34),
    'EMPTY_CRATE': (100, 65, 25),
    # New cells
    'BROKEN_GRAVESTONE': (105, 100, 108),
    'LOCKED_CHEST':      (100, 50, 10),
    'OPEN_CHEST':        (160, 100, 40),
    'BOOKSHELF':         (130, 90, 50),
    'WOOD_CHAIR':        (150, 100, 55),
    'WOOD_TABLE':        (145, 95, 50),
    'WATER_TROUGH':      (80, 110, 130),
    'SMALL_POTTED_PLANT':(60, 120, 60),
    'BED_WHITE':         (230, 225, 215),
    'BLUE_MUSHROOM':     (60, 90, 180),
    'APPLE_CRATE':       (180, 80, 30),
}

# Cell type properties with drop probabilities
# Add to CELL_TYPES dictionary
# Cell type properties with drop probabilities
CELL_TYPES = {
    'GRASS': {'color': COLORS['GRASS'], 'label': 'Grs', 'solid': False, 'grows_to': 'TREE1', 'growth_rate': 0.0005,
              'variants': {
                  'GRASS': 0.40,       # Default grass (40%)
                  'grass1': 0.10,      # Common variant
                  'grass2': 0.09,
                  'grass3': 0.08,
                  'grass4': 0.07,
                  'grass5': 0.06,
                  'grass6': 0.05,
                  'grass7': 0.04,
                  'grass8': 0.04,
                  'grass9': 0.03,      # Rare variants
                  'grass10': 0.02,     # Rarest
              }},
    'DIRT': {'color': COLORS['DIRT'], 'label': 'Drt', 'solid': False, 'grows_to': 'GRASS', 'growth_rate': 0.003},
    'WATER': {'color': COLORS['WATER'], 'label': 'Wtr', 'solid': False},
    'DEEP_WATER': {'color': COLORS['DEEP_WATER'], 'label': 'DWtr', 'solid': True, 'degrades_to': 'WATER', 'degrade_rate': 0.001},
    'TREE1': {'color': COLORS['TREE1'], 'label': 'Tre1', 'solid': True, 
              'drops': [{'item': 'wood', 'amount': 2, 'chance': 0.6}, 
                       {'cell': 'GRASS', 'chance': 0.25},
                       {'cell': 'DIRT', 'chance': 0.15}]},
    'TREE2': {'color': COLORS['TREE2'], 'label': 'Tre2', 'solid': True,
              'drops': [{'item': 'wood', 'amount': 3, 'chance': 0.7},
                       {'cell': 'GRASS', 'chance': 0.2},
                       {'cell': 'DIRT', 'chance': 0.1}]},
    'STONE': {'color': COLORS['STONE'], 'label': 'Stn', 'solid': True},
    'CARROT1': {'color': COLORS['CARROT1'], 'label': 'Crt1', 'solid': False, 
                'grows_to': 'CARROT2', 'growth_rate': 0.02,  # 2% (was 1%, not 5%)
                'degrades_to': 'GRASS', 'degrade_rate': 0.0001,  # Very slow decay
                'harvest': {'item': 'carrot', 'amount': 1}},
    'CARROT2': {'color': COLORS['CARROT2'], 'label': 'Crt2', 'solid': False,
                'grows_to': 'CARROT3', 'growth_rate': 0.015,  # 1.5% (was 0.8%, not 4%)
                'degrades_to': 'CARROT1', 'degrade_rate': 0.0001,  # Step down, not straight to GRASS
                'harvest': {'item': 'carrot', 'amount': 2}},
    'CARROT3': {'color': COLORS['CARROT3'], 'label': 'Crt3', 'solid': False,
                'degrades_to': 'CARROT2', 'degrade_rate': 0.00005,  # Step down
                'harvest': {'item': 'carrot', 'amount': 3}},
    'SAND': {'color': COLORS['SAND'], 'label': 'Snd', 'solid': False, 'grows_to': 'CACTUS', 'growth_rate': 0.0001},
    'COBBLESTONE': {'color': COLORS['COBBLESTONE'], 'label': 'Cob', 'solid': False, 'degrades_to': 'DIRT', 'degrade_rate': 0.00001},  # Very persistent
    'WALL': {'color': COLORS['WALL'], 'label': '█', 'solid': True},
    'HOUSE': {'color': COLORS['HOUSE'], 'label': 'Hos', 'solid': True, 'enterable': True, 'interior_type': 'HOUSE_INTERIOR', 'grows_to': 'STONE_HOUSE', 'growth_rate': 0.00002},
    'FORGE': {'color': COLORS['FORGE'], 'label': 'Frg', 'solid': True},
    'CAVE': {'color': COLORS['CAVE'], 'label': 'Cav', 'solid': True, 'enterable': True, 'interior_type': 'CAVE'},
    'MINESHAFT': {'color': (90, 70, 50), 'label': 'Mine', 'solid': True, 'enterable': True, 'interior_type': 'CAVE', 'sprite_name': 'mineshaft'},
    'HIDDEN_CAVE': {'color': (40, 35, 30), 'label': 'HCav', 'solid': False, 'degrades_to': 'CAVE', 'degrade_rate': 0.005},
    'CAMP': {'color': (200, 100, 50), 'label': 'Camp', 'solid': False, 'grows_to': 'HOUSE', 'growth_rate': 0.001},
    'SOIL': {'color': COLORS['SOIL'], 'label': 'Soil', 'solid': False},
    'FLOWER': {'color': COLORS['FLOWER'], 'label': 'Flwr', 'solid': False, 'degrades_to': 'GRASS', 'degrade_rate': 0.0001},  # Very slow decay
    'FLOWER_PATTERN1': {'color': (255, 200, 50), 'label': 'Fp1', 'solid': True, 'degrades_to': 'GRASS', 'degrade_rate': 0.00015},
    'FLOWER_PATTERN2': {'color': (180, 100, 220), 'label': 'Fp2', 'solid': True, 'degrades_to': 'GRASS', 'degrade_rate': 0.00015},
    'FLOWER_PATTERN3': {'color': (255, 100, 100), 'label': 'Fp3', 'solid': True, 'degrades_to': 'GRASS', 'degrade_rate': 0.00015},
    # Placeable item cells
    'WOOD': {'color': COLORS['WOOD'], 'label': 'Wood', 'solid': False},
    'PLANKS': {'color': COLORS['PLANKS'], 'label': 'Plnk', 'solid': False},
    'MEAT': {'color': (180, 50, 50), 'label': 'Meat', 'solid': False},
    'FUR': {'color': (100, 100, 100), 'label': 'Fur', 'solid': False},
    'BONES': {'color': (220, 220, 200), 'label': 'Bone', 'solid': False},
    # Interior cell types
    'FLOOR_WOOD': {'color': (101, 67, 33), 'label': 'Flr', 'solid': False},
    'CAVE_FLOOR': {'color': (50, 50, 50), 'label': 'Cfl', 'solid': False},
    'CAVE_WALL': {'color': (30, 30, 30), 'label': 'Cw', 'solid': True},
    'CHEST': {'color': (139, 69, 19), 'label': 'Chst', 'solid': True, 'interactable': True},
    'STAIRS_DOWN': {'color': (100, 80, 60), 'label': '↓', 'solid': False, 'goes_deeper': True},
    'STAIRS_UP': {'color': (120, 100, 80), 'label': '↑', 'solid': False, 'exits_structure': True},
    'IRON_ORE': {
        'color': COLORS['IRON_ORE'],
        'label': 'Fe',
        'solid': True,
        'drops': [{'item': 'iron_ore', 'amount': 1, 'chance': 1.0}],
    },
    'WELL': {
        'color': COLORS['WELL'],
        'label': 'Wel',
        'solid': True,
        'interactable': True,
    },
    'GRAVESTONE': {
        'color': COLORS['GRAVESTONE'],
        'label': 'GS',
        'solid': True,
        'degrades_to': 'BROKEN_GRAVESTONE',
        'degrade_rate': 0.000005,
    },
    'BROKEN_GRAVESTONE': {
        'color': COLORS['BROKEN_GRAVESTONE'],
        'label': 'BGS',
        'solid': True,
    },
    'LOCKED_CHEST': {
        'color': COLORS['LOCKED_CHEST'],
        'label': 'LCh',
        'solid': True,
        'interactable': True,
    },
    'OPEN_CHEST': {
        'color': COLORS['OPEN_CHEST'],
        'label': 'Chst',
        'solid': False,
        'interactable': True,
    },
    'BOOKSHELF': {
        'color': COLORS['BOOKSHELF'],
        'label': 'Bkshlf',
        'solid': True,
    },
    'WOOD_CHAIR': {
        'color': COLORS['WOOD_CHAIR'],
        'label': 'Chr',
        'solid': True,
    },
    'WOOD_TABLE': {
        'color': COLORS['WOOD_TABLE'],
        'label': 'Tbl',
        'solid': True,
    },
    'WATER_TROUGH': {
        'color': COLORS['WATER_TROUGH'],
        'label': 'WTrg',
        'solid': True,
        'interactable': True,
    },
    'SMALL_POTTED_PLANT': {
        'color': COLORS['SMALL_POTTED_PLANT'],
        'label': 'Plt',
        'solid': True,
    },
    'BED_WHITE': {
        'color': COLORS['BED_WHITE'],
        'label': 'BedW',
        'solid': True,
    },
    'BLUE_MUSHROOM': {
        'color': COLORS['BLUE_MUSHROOM'],
        'label': 'BMsh',
        'solid': True,
        'drops': [{'item': 'blue_mushroom', 'amount': 1, 'chance': 1.0}],
    },
    'BED_BLUE': {
        'color': COLORS['BED_BLUE'],
        'label': 'Bed',
        'solid': True,
    },
    'DESERT_WELL': {
        'color': COLORS['DESERT_WELL'],
        'label': 'DWel',
        'solid': True,
        'interactable': True,
    },
    'CACTUS': {
        'color': COLORS['CACTUS'],
        'label': 'Cct',
        'solid': True,
        'degrades_to': 'SAND',
        'degrade_rate': 0.00002,  # Very low — cacti persist in deserts
        'drops': [{'cell': 'SAND', 'chance': 0.8}],
    },
    'BARREL': {
        'color': COLORS['BARREL'],
        'label': 'Brl',
        'solid': True,
        'interactable': True,
    },
    'STONE_HOUSE': {
        'color': COLORS['STONE_HOUSE'],
        'label': 'StH',
        'solid': True,
        'enterable': True,
        'interior_type': 'HOUSE_INTERIOR',
    },
    'EMPTY_CRATE': {
        'color': COLORS['EMPTY_CRATE'],
        'label': 'ECrt',
        'solid': True,
        'interactable': True,
    },
    'RUINED_SANDSTONE_COLUMN': {
        'color': COLORS['RUINED_SANDSTONE_COLUMN'],
        'label': 'RSC',
        'solid': True,
    },
    'CLIFF': {
        'color': COLORS['CLIFF'],
        'label': 'Clf',
        'solid': True,
    },
    'BUSH': {
        'color': COLORS['BUSH'],
        'label': 'Bush',
        'solid': True,
        'drops': [{'item': 'wood', 'amount': 1, 'chance': 0.6},
                  {'cell': 'GRASS', 'chance': 0.8}],
    },
    'APPLE_CRATE': {
        'color': COLORS['APPLE_CRATE'],
        'label': 'AplCrt',
        'solid': True,
        'interactable': True,
        'infinite_food': True,
        'food_value': 30,
    },
}

# Item definitions
ITEMS = {
    # Basic resources
    'wood': {'color': COLORS['WOOD'], 'name': 'Wood'},
    'planks': {'color': COLORS['PLANKS'], 'name': 'Planks'},
    'carrot': {'color': COLORS['CARROT1'], 'name': 'Carrot'},
    'gold': {'color': (255, 215, 0), 'name': 'Gold'},
    'bones': {'color': (220, 220, 200), 'name': 'Bones', 'is_placeable': True},  # Placeable decoration
    'stone': {'color': (128, 128, 128), 'name': 'Stone'},
    'fur': {'color': (100, 100, 100), 'name': 'Fur'},
    'meat': {'color': (180, 50, 50), 'name': 'Meat'},
    
    # Basic tools
    'axe': {'color': (192, 192, 192), 'name': 'Axe', 'is_tool': True, 'damage': 5},
    'hoe': {'color': (160, 82, 45), 'name': 'Hoe', 'is_tool': True},
    'shovel': {'color': (150, 150, 150), 'name': 'Shovel', 'is_tool': True},
    'pickaxe': {'color': (100, 100, 120), 'name': 'Pickaxe', 'is_tool': True, 'damage': 4},
    'bucket': {'color': (180, 180, 180), 'name': 'Bucket', 'is_tool': True},
    
    # Advanced tools
    'stone_pickaxe': {'color': (120, 120, 140), 'name': 'Stone Pickaxe', 'is_tool': True, 'damage': 8},
    'stone_axe': {'color': (140, 140, 160), 'name': 'Stone Axe', 'is_tool': True, 'damage': 10},
    'watering_can': {'color': (100, 150, 200), 'name': 'Watering Can', 'is_tool': True},
    
    # Weapons
    'hilt': {'color': (139, 90, 43), 'name': 'Weapon Hilt'},
    'bone_sword': {'color': (220, 220, 200), 'name': 'Bone Sword', 'is_tool': True, 'is_weapon': True, 'damage': 15, 'equipment_slot': 'weapon'},
    'club': {'color': (101, 67, 33), 'name': 'Club', 'is_tool': True, 'is_weapon': True, 'damage': 8, 'equipment_slot': 'weapon'},
    
    # Magic items
    'star_spell': {'color': (255, 215, 0), 'name': 'Star Spell', 'is_spell': True,
                   'description': 'Enchants cells and entities'},
    'rain_spell': {'color': (100, 150, 220), 'name': 'Rain Spell', 'is_spell': True,
                   'description': 'Toggles rain on and off'},
    'day_spell':  {'color': (255, 230, 100), 'name': 'Day Spell',  'is_spell': True,
                   'description': 'Toggles day and night'},
    'keeper_spell': {'color': (100, 220, 180), 'name': 'Keeper Spell', 'is_spell': True,
                     'spell_type': 'keeper', 'description': 'Assigns inspected NPC as zone keeper'},
    'magic_stone': {'color': (138, 43, 226), 'name': 'Magic Stone', 'is_spell': True, 'damage': 12},
    'magic_wand': {'color': (255, 140, 255), 'name': 'Magic Wand', 'is_spell': True, 'damage': 10},

    # Dev summon spells
    'summon_sheep':        {'color': (230, 230, 230), 'name': 'Summon Sheep',        'is_spell': True, 'spell_type': 'summon',    'npc_type': 'SHEEP'},
    'summon_wolf':         {'color': (80,  80,  80),  'name': 'Summon Wolf',         'is_spell': True, 'spell_type': 'summon',    'npc_type': 'WOLF'},
    'summon_deer':         {'color': (139, 90,  43),  'name': 'Summon Deer',         'is_spell': True, 'spell_type': 'summon',    'npc_type': 'DEER'},
    'summon_farmer':       {'color': (139, 69,  19),  'name': 'Summon Farmer',       'is_spell': True, 'spell_type': 'summon',    'npc_type': 'FARMER'},
    'summon_guard':        {'color': (100, 100, 150), 'name': 'Summon Guard',        'is_spell': True, 'spell_type': 'summon',    'npc_type': 'GUARD'},
    'summon_warrior':      {'color': (150, 50,  50),  'name': 'Summon Warrior',      'is_spell': True, 'spell_type': 'summon',    'npc_type': 'WARRIOR'},
    'summon_commander':    {'color': (180, 50,  50),  'name': 'Summon Commander',    'is_spell': True, 'spell_type': 'summon',    'npc_type': 'COMMANDER'},
    'summon_king':         {'color': (220, 180, 50),  'name': 'Summon King',         'is_spell': True, 'spell_type': 'summon',    'npc_type': 'KING'},
    'summon_trader':       {'color': (218, 165, 32),  'name': 'Summon Trader',       'is_spell': True, 'spell_type': 'summon',    'npc_type': 'TRADER'},
    'summon_blacksmith':   {'color': (105, 105, 105), 'name': 'Summon Blacksmith',   'is_spell': True, 'spell_type': 'summon',    'npc_type': 'BLACKSMITH'},
    'summon_wizard':       {'color': (138, 43,  226), 'name': 'Summon Wizard',       'is_spell': True, 'spell_type': 'summon',    'npc_type': 'WIZARD'},
    'summon_lumberjack':   {'color': (139, 90,  43),  'name': 'Summon Lumberjack',   'is_spell': True, 'spell_type': 'summon',    'npc_type': 'LUMBERJACK'},
    'summon_miner':        {'color': (105, 105, 105), 'name': 'Summon Miner',        'is_spell': True, 'spell_type': 'summon',    'npc_type': 'MINER'},
    'summon_bandit':       {'color': (150, 50,  50),  'name': 'Summon Bandit',       'is_spell': True, 'spell_type': 'summon',    'npc_type': 'BANDIT'},
    'summon_goblin':       {'color': (100, 150, 50),  'name': 'Summon Goblin',       'is_spell': True, 'spell_type': 'summon',    'npc_type': 'GOBLIN'},
    'summon_skeleton':     {'color': (200, 200, 200), 'name': 'Summon Skeleton',     'is_spell': True, 'spell_type': 'summon',    'npc_type': 'SKELETON'},
    'summon_termite':      {'color': (255, 215, 0),   'name': 'Summon Termite',      'is_spell': True, 'spell_type': 'summon',    'npc_type': 'TERMITE'},
    'summon_bat':          {'color': (40,  30,  50),  'name': 'Summon Bat',          'is_spell': True, 'spell_type': 'summon',    'npc_type': 'BAT'},
    'summon_red_bird':     {'color': (200, 60,  40),  'name': 'Summon Red Bird',     'is_spell': True, 'spell_type': 'summon',    'npc_type': 'RED_BIRD'},
    'summon_butterfly':    {'color': (180, 120, 220), 'name': 'Summon Butterfly',    'is_spell': True, 'spell_type': 'summon',    'npc_type': 'BUTTERFLY'},
    'summon_chicken':      {'color': (255, 220, 100), 'name': 'Summon Chicken',      'is_spell': True, 'spell_type': 'summon',    'npc_type': 'CHICKEN'},
    'summon_black_spider': {'color': (20,  20,  20),  'name': 'Summon Spider',       'is_spell': True, 'spell_type': 'summon',    'npc_type': 'BLACK_SPIDER'},

    # Dev transform spells
    'transform_sheep':        {'color': (230, 230, 230), 'name': 'Transform: Sheep',        'is_spell': True, 'spell_type': 'transform', 'npc_type': 'SHEEP'},
    'transform_wolf':         {'color': (80,  80,  80),  'name': 'Transform: Wolf',         'is_spell': True, 'spell_type': 'transform', 'npc_type': 'WOLF'},
    'transform_deer':         {'color': (139, 90,  43),  'name': 'Transform: Deer',         'is_spell': True, 'spell_type': 'transform', 'npc_type': 'DEER'},
    'transform_farmer':       {'color': (139, 69,  19),  'name': 'Transform: Farmer',       'is_spell': True, 'spell_type': 'transform', 'npc_type': 'FARMER'},
    'transform_guard':        {'color': (100, 100, 150), 'name': 'Transform: Guard',        'is_spell': True, 'spell_type': 'transform', 'npc_type': 'GUARD'},
    'transform_warrior':      {'color': (150, 50,  50),  'name': 'Transform: Warrior',      'is_spell': True, 'spell_type': 'transform', 'npc_type': 'WARRIOR'},
    'transform_commander':    {'color': (180, 50,  50),  'name': 'Transform: Commander',    'is_spell': True, 'spell_type': 'transform', 'npc_type': 'COMMANDER'},
    'transform_king':         {'color': (220, 180, 50),  'name': 'Transform: King',         'is_spell': True, 'spell_type': 'transform', 'npc_type': 'KING'},
    'transform_trader':       {'color': (218, 165, 32),  'name': 'Transform: Trader',       'is_spell': True, 'spell_type': 'transform', 'npc_type': 'TRADER'},
    'transform_blacksmith':   {'color': (105, 105, 105), 'name': 'Transform: Blacksmith',   'is_spell': True, 'spell_type': 'transform', 'npc_type': 'BLACKSMITH'},
    'transform_wizard':       {'color': (138, 43,  226), 'name': 'Transform: Wizard',       'is_spell': True, 'spell_type': 'transform', 'npc_type': 'WIZARD'},
    'transform_lumberjack':   {'color': (139, 90,  43),  'name': 'Transform: Lumberjack',   'is_spell': True, 'spell_type': 'transform', 'npc_type': 'LUMBERJACK'},
    'transform_miner':        {'color': (105, 105, 105), 'name': 'Transform: Miner',        'is_spell': True, 'spell_type': 'transform', 'npc_type': 'MINER'},
    'transform_bandit':       {'color': (150, 50,  50),  'name': 'Transform: Bandit',       'is_spell': True, 'spell_type': 'transform', 'npc_type': 'BANDIT'},
    'transform_goblin':       {'color': (100, 150, 50),  'name': 'Transform: Goblin',       'is_spell': True, 'spell_type': 'transform', 'npc_type': 'GOBLIN'},
    'transform_skeleton':     {'color': (200, 200, 200), 'name': 'Transform: Skeleton',     'is_spell': True, 'spell_type': 'transform', 'npc_type': 'SKELETON'},
    'transform_termite':      {'color': (255, 215, 0),   'name': 'Transform: Termite',      'is_spell': True, 'spell_type': 'transform', 'npc_type': 'TERMITE'},
    'transform_bat':          {'color': (40,  30,  50),  'name': 'Transform: Bat',          'is_spell': True, 'spell_type': 'transform', 'npc_type': 'BAT'},
    'transform_red_bird':     {'color': (200, 60,  40),  'name': 'Transform: Red Bird',     'is_spell': True, 'spell_type': 'transform', 'npc_type': 'RED_BIRD'},
    'transform_butterfly':    {'color': (180, 120, 220), 'name': 'Transform: Butterfly',    'is_spell': True, 'spell_type': 'transform', 'npc_type': 'BUTTERFLY'},
    'transform_chicken':      {'color': (255, 220, 100), 'name': 'Transform: Chicken',      'is_spell': True, 'spell_type': 'transform', 'npc_type': 'CHICKEN'},
    'transform_black_spider': {'color': (20,  20,  20),  'name': 'Transform: Spider',       'is_spell': True, 'spell_type': 'transform', 'npc_type': 'BLACK_SPIDER'},

    'enchanted_sword': {'color': (147, 112, 219), 'name': 'Enchanted Sword', 'is_tool': True, 'is_weapon': True, 'damage': 25, 'equipment_slot': 'weapon'},
    'enchanted_axe': {'color': (148, 0, 211), 'name': 'Enchanted Axe', 'is_tool': True, 'damage': 20},

    # Weapons (ranged / polearm / blunt)
    'bow':          {'color': (139, 90,  43),  'name': 'Bow',         'is_tool': True, 'is_weapon': True, 'damage': 12, 'equipment_slot': 'weapon'},
    'bow_metal':    {'color': (150, 150, 150),  'name': 'Metal Bow',   'is_tool': True, 'is_weapon': True, 'damage': 15, 'equipment_slot': 'weapon'},
    'staff_red':    {'color': (180,  50,  50),  'name': 'Red Staff',   'is_tool': True, 'is_weapon': True, 'damage': 14, 'equipment_slot': 'weapon'},
    'spear':        {'color': (150, 120,  80),  'name': 'Spear',       'is_tool': True, 'is_weapon': True, 'damage': 16, 'equipment_slot': 'weapon'},
    'warhammer':    {'color': ( 80,  80, 100),  'name': 'Warhammer',   'is_tool': True, 'is_weapon': True, 'damage': 22, 'equipment_slot': 'weapon'},

    # Shields
    'shield':        {'color': (150, 150, 160), 'name': 'Shield',        'is_tool': True, 'is_shield': True, 'equipment_slot': 'offhand'},
    'shield_bronze': {'color': (180, 120,  50), 'name': 'Bronze Shield', 'is_tool': True, 'is_shield': True, 'equipment_slot': 'offhand'},

    # Armour pieces
    'armour_chest': {'color': (150, 150, 160), 'name': 'Chest Armour', 'is_armor': True, 'armor': 8,  'equipment_slot': 'armor'},
    'armour_helm':  {'color': (150, 150, 160), 'name': 'Helm',         'is_armor': True, 'armor': 4,  'equipment_slot': 'armor'},
    'armour_legs':  {'color': (150, 150, 160), 'name': 'Leg Armour',   'is_armor': True, 'armor': 5,  'equipment_slot': 'armor'},
    'armour_shoes': {'color': (150, 150, 160), 'name': 'Armour Shoes', 'is_armor': True, 'armor': 2,  'equipment_slot': 'armor'},

    # Materials
    'rope': {'color': (139, 119, 101), 'name': 'Rope'},
    'leather': {'color': (139, 90, 43), 'name': 'Leather'},
    'leather_armor': {'color': (160, 82, 45), 'name': 'Leather Armor', 'is_tool': True, 'is_armor': True, 'armor': 5, 'equipment_slot': 'armor'},
    'chest': {'color': (139, 69, 19), 'name': 'Chest'},
    'seeds': {'color': (205, 133, 63), 'name': 'Seeds'},
    
    # Food
    'cooked_meat': {'color': (139, 69, 19), 'name': 'Cooked Meat'},
    'stew': {'color': (165, 42, 42), 'name': 'Stew'},
    
    # Building
    'floor': {'color': (160, 120, 80), 'name': 'Floor'},
    'sandstone': {'color': (210, 180, 140), 'name': 'Sandstone'},
    
    # Iron pipeline
    'iron_ore':   {'color': (139, 90, 43),   'name': 'Iron Ore'},
    'iron_ingot': {'color': (180, 140, 100),  'name': 'Iron Ingot'},
    'iron_sword': {'color': (200, 200, 220),  'name': 'Iron Sword', 'is_tool': True, 'is_weapon': True, 'damage': 20, 'equipment_slot': 'weapon', 'sprite_name': 'iron_sword'},

    # World structures / placeable cells
    'well':                    {'color': (100, 80, 60),    'name': 'Well'},
    'cactus':                  {'color': (50, 120, 50),    'name': 'Cactus'},
    'barrel':                  {'color': (120, 80, 40),    'name': 'Barrel'},
    'stone_house':             {'color': (110, 110, 120),  'name': 'Stone House'},
    'ruined_sandstone_column': {'color': (200, 160, 90),   'name': 'Ruined Column'},
    'forge':                   {'color': (180, 60, 20),    'name': 'Forge'},

    # Actions
    'attack':  {'color': (220, 80,  60),  'name': 'Attack',  'is_action': True, 'description': 'Strike the target'},
    'block':   {'color': (80,  100, 220), 'name': 'Block',   'is_action': True, 'description': 'Raise guard to reduce damage'},
    'sneak':   {'color': (60,  80,  60),  'name': 'Sneak',   'is_action': True, 'description': 'Move quietly'},
    'dig':     {'color': (139, 90,  43),  'name': 'Dig',     'is_action': True, 'description': 'Dig soft cells'},
    'talk':    {'color': (100, 180, 220), 'name': 'Talk',    'is_action': True, 'description': 'Speak with target NPC'},
    'inspect': {'color': (200, 180, 100), 'name': 'Inspect', 'is_action': True, 'description': 'Examine target'},
    'shove':   {'color': (220, 120, 60),  'name': 'Shove',   'is_action': True, 'description': 'Push target back one cell'},

    # Special
    'skeleton_bones': {'color': (240, 240, 230), 'name': 'Skeleton Bones', 'is_follower': True},

    # Runestones - Magic damage types
    'lightning_rune': {'color': (100, 149, 237), 'name': 'Lightning Rune', 'magic_damage': 'lightning', 'damage': 3},
    'fire_rune': {'color': (255, 69, 0), 'name': 'Fire Rune', 'magic_damage': 'fire', 'damage': 3},
    'ice_rune': {'color': (173, 216, 230), 'name': 'Ice Rune', 'magic_damage': 'ice', 'damage': 3},
    'poison_rune': {'color': (50, 205, 50), 'name': 'Poison Rune', 'magic_damage': 'poison', 'damage': 3},
    'shadow_rune': {'color': (75, 0, 130), 'name': 'Shadow Rune', 'magic_damage': 'shadow', 'damage': 3, 'sprite_name': 'magic_rune'}
}

# Wizard spell effects
WIZARD_SPELLS = {
    'heal': {'type': 'heal', 'amount': 20, 'range': 6, 'color': (100, 255, 100), 'hostile_only': False},
    'fireball': {'type': 'damage', 'amount': 15, 'element': 'fire', 'range': 6, 'color': (255, 69, 0), 'hostile_only': True},
    'lightning': {'type': 'damage', 'amount': 15, 'element': 'lightning', 'range': 6, 'color': (100, 149, 237), 'hostile_only': True},
    'ice': {'type': 'damage', 'amount': 15, 'element': 'ice', 'range': 6, 'color': (173, 216, 230), 'hostile_only': True},
    'enchant': {'type': 'enchant', 'range': 6, 'color': (200, 150, 255), 'hostile_only': False},
}

# Crafting recipes: (item1, item2) -> result
# Recipe format: ('ingredient1', 'ingredient2'): 'result_item'
# Order doesn't matter - ('wood', 'stone') == ('stone', 'wood')
RECIPES = {
    # Basic tools from resources
    ('wood', 'stone'): 'stone_pickaxe',
    ('wood', 'wood'): 'hoe',  # Two wood makes hoe
    ('stone', 'stone'): 'shovel',  # Two stone makes shovel
    
    # Weapons and advanced tools
    ('wood', 'hoe'): 'hilt',  # Hoe + wood = weapon handle
    ('hilt', 'bone'): 'bone_sword',
    ('hilt', 'bones'): 'bone_sword',  # Alternative spelling
    ('hilt', 'stone'): 'stone_axe',
    ('hilt', 'fur'): 'club',  # Fur-wrapped club
    
    # Material processing
    ('axe', 'wood'): 'planks',
    ('wood', 'wood'): 'planks',  # Can also make planks without axe
    ('planks', 'planks'): 'chest',
    
    # Farming tools
    ('wood', 'bucket'): 'watering_can',
    ('carrot', 'carrot'): 'seeds',
    ('grass', 'grass'): 'rope',
    
    # Magical items (spell + item)
    ('star_spell', 'stone'): 'magic_stone',
    ('star_spell', 'wood'): 'magic_wand',
    ('star_spell', 'bone_sword'): 'enchanted_sword',
    ('star_spell', 'stone_axe'): 'enchanted_axe',
    ('star_spell', 'bones'): 'skeleton_bones',  # Creates skeleton follower
    
    # Armor (future expansion)
    ('fur', 'fur'): 'leather',
    ('leather', 'leather'): 'leather_armor',
    
    # Food combinations
    ('meat', 'meat'): 'cooked_meat',
    ('carrot', 'meat'): 'stew',
    
    # Building materials
    ('stone', 'planks'): 'wall',
    ('planks', 'dirt'): 'floor',
    ('wood', 'sand'): 'sandstone',

    # Iron pipeline
    ('iron_ore', 'iron_ore'):     'iron_ingot',
    ('iron_ingot', 'hilt'):       'iron_sword',
    ('iron_ingot', 'iron_ingot'): 'iron_sword',
}

# Loot tables for chests
LOOT_TABLES = {
    'HOUSE_CHEST': [
        {'item': 'gold', 'min': 5, 'max': 20, 'chance': 0.8},
        {'item': 'wood', 'min': 3, 'max': 10, 'chance': 0.6},
        {'item': 'carrot', 'min': 1, 'max': 5, 'chance': 0.5},
        {'item': 'axe', 'min': 1, 'max': 1, 'chance': 0.2}
    ],
    'CAVE_CHEST': [
        {'item': 'gold', 'min': 10, 'max': 50, 'chance': 0.9},
        {'item': 'stone', 'min': 5, 'max': 15, 'chance': 0.7},
        {'item': 'bones', 'min': 1, 'max': 3, 'chance': 0.5},
        {'item': 'stone_pickaxe', 'min': 1, 'max': 1, 'chance': 0.3},
        {'item': 'iron_ore', 'min': 1, 'max': 3, 'chance': 0.40},
    ],
    'CAVE_DEEP_CHEST': [
        {'item': 'gold', 'min': 50, 'max': 200, 'chance': 1.0},
        {'item': 'enchanted_sword', 'min': 1, 'max': 1, 'chance': 0.4},
        {'item': 'leather_armor', 'min': 1, 'max': 1, 'chance': 0.3},
        {'item': 'magic_stone', 'min': 1, 'max': 1, 'chance': 0.2},
        {'item': 'iron_ingot', 'min': 1, 'max': 2, 'chance': 0.30},
        {'item': 'iron_sword', 'min': 1, 'max': 1, 'chance': 0.20},
    ]
}

# Biome definitions
BIOMES = {
    'FOREST': {'GRASS': 0.5, 'DIRT': 0.2, 'TREE1': 0.15, 'TREE2': 0.05, 'WATER': 0.1},
    'PLAINS': {'GRASS': 0.70, 'DIRT': 0.10, 'WATER': 0.05, 'CARROT1': 0.10, 'TREE1': 0.05},
    'DESERT': {'SAND': 0.67, 'DIRT': 0.2, 'WATER': 0.05, 'STONE': 0.05, 'CACTUS': 0.03},
    'MOUNTAINS': {'DIRT': 0.45, 'STONE': 0.20, 'GRASS': 0.20, 'TREE1': 0.10, 'WATER': 0.05},
    'LAKE': {'WATER': 0.90, 'DEEP_WATER': 0.10},
}

# Entity types and properties
ENTITY_TYPES = {
    # Animals
    'SHEEP': {
        'color': (230, 230, 230),
        'symbol': 'S',
        'max_health': 16,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 6,
        'speed': 1.0,
        'food_sources': ['GRASS'],
        'water_sources': ['WATER'],
        'hostile': False,
        'edible': True,
        'drops': [
            {'item': 'meat', 'amount': 2, 'chance': 0.8},
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.02,
            'passiveness': 0.70,
            'idleness': 0.25,
            'flee_chance': 0.95,
            'combat_chance': 0.05,
            'target_types': ['food', 'water']
        }
    },
    'WOLF': {
        'color': (80, 80, 80),
        'symbol': 'W',
        'max_health': 30,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 17,
        'speed': 1.5,
        'food_sources': ['SHEEP', 'DEER'],
        'water_sources': ['WATER'],
        'hostile': True,
        'edible': True,
        'drops': [
            {'item': 'fur', 'amount': 1, 'chance': 0.9},
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.80,
            'passiveness': 0.10,
            'idleness': 0.05,
            'flee_chance': 0.20,
            'combat_chance': 0.80,
            'attack_chance': 0.60,
            'target_types': ['food', 'water', 'hostile']
        }
    },
    'DEER': {
        'color': (139, 90, 43),
        'symbol': 'D',
        'max_health': 24,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 9,
        'speed': 2.0,
        'food_sources': ['GRASS', 'CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
        'edible': True,
        'drops': [
            {'item': 'meat', 'amount': 3, 'chance': 0.8},
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.05,
            'passiveness': 0.60,
            'idleness': 0.20,
            'flee_chance': 0.90,
            'combat_chance': 0.10,
            'target_types': ['food', 'water']
        }
    },
    # NPCs
    'FARMER': {
        'color': (139, 69, 19),
        'symbol': 'F',
        'max_health': 64,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 13,
        'speed': 1.0,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'can_trade': True,
        'inventory': {'carrot': 5, 'wood': 3},
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'behavior_config': {
            'actions': ['harvest', 'till', 'plant'],
            'can_place_camp': True,
            'wander_when_idle': True
        },
        'ai_params': {
            'aggressiveness': 0.65,  # High — farmers actively seek crops/soil to work
            'passiveness': 0.15,     # Rarely drops task to wander
            'idleness': 0.10,        # Takes occasional breaks
            'flee_chance': 0.70,
            'combat_chance': 0.30,
            'target_types': ['food', 'water', 'resource']
        }
    },
    'GUARD': {
        'color': (100, 100, 150),
        'symbol': 'G',
        'max_health': 104,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 31,
        'speed': 1.2,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'attacks_hostile': True,
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'behavior_config': {
            'actions': ['patrol', 'build_path'],
            'patrol_center': True,
            'wander_when_idle': False
        },
        'ai_params': {
            'aggressiveness': 0.95,  # 95% chance to acquire/pursue targets (matched to warriors)
            'passiveness': 0.02,     # 2% chance to drop target and wander (matched to warriors)
            'idleness': 0.01,        # 1% chance to enter idle state (matched to warriors)
            'flee_chance': 0.10,
            'combat_chance': 0.90,
            'attack_chance': 0.40,
            'target_types': ['hostile', 'water', 'food']  # What to target
        }
    },
    'WARRIOR': {
        'color': (150, 50, 50),
        'symbol': 'W',
        'max_health': 80,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 26,
        'speed': 1.2,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'attacks_hostile': True,
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'behavior_config': {
            'actions': ['patrol', 'build_path'],
            'patrol_center': True,
            'wander_when_idle': False
        },
        'ai_params': {
            'aggressiveness': 0.95,  # 95% chance to acquire/pursue hostile targets (matched to guards)
            'passiveness': 0.02,     # 2% chance to drop target and wander (matched to guards)
            'idleness': 0.01,        # 1% chance to enter idle state (matched to guards)
            'flee_chance': 0.005,    # 0.5% base flee — near-zero, scales up only vs much higher-level enemies
            'combat_chance': 0.95,   # 95% fight when threatened
            'attack_chance': 0.55,
            'target_types': ['hostile', 'water', 'food', 'structure']  # What to target
        }
    },
    'COMMANDER': {
        'color': (180, 50, 50),
        'symbol': 'C',
        'max_health': 96,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 31,
        'speed': 1.2,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'attacks_hostile': True,
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.2},
            {'item': 'gold', 'amount': 1, 'chance': 0.3}
        ],
        'behavior_config': {
            'actions': ['patrol', 'build_path'],
            'patrol_center': True,
            'wander_when_idle': False
        },
        'ai_params': {
            'aggressiveness': 0.75,  # 75% - strong leadership/combat
            'passiveness': 0.08,     # 8% - very focused
            'idleness': 0.07,        # 7% - rarely idle
            'flee_chance': 0.002,    # 0.2% base flee — commanders almost never flee
            'combat_chance': 0.97,
            'attack_chance': 0.55,
            'target_types': ['hostile', 'water', 'food', 'structure']
        }
    },
    'KING': {
        'color': (220, 180, 50),
        'symbol': 'K',
        'max_health': 120,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 41,
        'speed': 1.0,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'attacks_hostile': True,
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.2},
            {'item': 'gold', 'amount': 3, 'chance': 0.8}
        ],
        'behavior_config': {
            'actions': ['patrol', 'build_path'],
            'patrol_center': True,
            'wander_when_idle': False
        },
        'ai_params': {
            'aggressiveness': 0.70,  # 70% - royal authority
            'passiveness': 0.10,     # 10% - regal bearing
            'idleness': 0.15,        # 15% - sits on throne
            'flee_chance': 0.05,
            'combat_chance': 0.95,
            'attack_chance': 0.50,
            'target_types': ['hostile', 'water', 'food', 'structure']
        }
    },
    'TRADER': {
        'color': (218, 165, 32),
        'symbol': 'T',
        'max_health': 56,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 11,
        'speed': 0.8,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'can_trade': True,
        'inventory': {'wood': 10, 'planks': 5, 'axe': 1},
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'behavior_config': {
            'actions': ['travel', 'build_path'],
            'seek_exits': True,
            'wander_when_idle': False
        },
        'ai_params': {
            'aggressiveness': 0.10,
            'passiveness': 0.50,
            'idleness': 0.30,
            'flee_chance': 0.80,
            'combat_chance': 0.20,
            'target_types': ['food', 'water', 'structure']
        }
    },
    'BLACKSMITH': {
        'color': (105, 105, 105),  # Dark gray
        'symbol': 'S',
        'max_health': 72,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 25,
        'speed': 0.7,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'can_trade': True,
        'is_blacksmith': True,
        'inventory': {'gold': 20, 'stone': 10, 'bone_sword': 1, 'axe': 2},
        'drops': [
            {'item': 'gold', 'amount': 5, 'chance': 0.8},
            {'item': 'stone', 'amount': 3, 'chance': 0.6}
        ],
        'behavior_config': {
            'actions': ['build_forge'],
            'wander_when_idle': True
        },
        'ai_params': {
            'aggressiveness': 0.25,  # 25% - focused on crafting
            'passiveness': 0.25,     # 25% - takes breaks
            'idleness': 0.30,        # 30% - often at forge/idle
            'target_types': ['food', 'water', 'structure']
        }
    },
    'WIZARD': {
        'color': (138, 43, 226),  # Blue-violet
        'symbol': 'Z',
        'max_health': 48,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 13,
        'speed': 1.0,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'attacks_hostile': True,
        'can_trade': True,
        'inventory': {},
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'behavior_config': {
            'actions': ['seek_rune', 'cast_spell', 'travel', 'explore_cave'],
            'seek_exits': True,
            'wander_when_idle': True
        },
        'ai_params': {
            'aggressiveness': 0.20,  # Low — only fights when attacked
            'passiveness': 0.10,     # Stays on task
            'idleness': 0.05,        # Almost always active
            'flee_chance': 0.50,
            'combat_chance': 0.50,
            'target_types': ['food', 'water', 'structure']  # No 'hostile' — won't seek fights
        }
    },
    'LUMBERJACK': {
        'color': (139, 90, 43),
        'symbol': 'L',
        'max_health': 80,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 19,
        'speed': 0.9,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'can_trade': False,
        'inventory': {'wood': 5, 'axe': 1},
        'drops': [
            {'item': 'wood', 'amount': 3, 'chance': 0.8},
            {'item': 'axe', 'amount': 1, 'chance': 0.3}
        ],
        'behavior_config': {
            'actions': ['chop_trees', 'build_house'],
            'can_place_camp': True,
            'wander_when_idle': True  # Changed back to True - they wander between chopping
        },
        'ai_params': {
            'aggressiveness': 0.95,  
            'passiveness': 0.30,     
            'idleness': 0.20,
            'flee_chance': 0.60,
            'combat_chance': 0.40,
            'target_types': ['hostile', 'food', 'water', 'structure']
        }
    },
    'MINER': {
        'color': (105, 105, 105),
        'symbol': 'M',
        'max_health': 88,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 21,
        'speed': 0.8,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3', 'APPLE_CRATE'],
        'water_sources': ['WATER', 'WELL', 'WATER_TROUGH'],
        'hostile': False,
        'humanoid': True,
        'edible': False,
        'can_trade': True,
        'inventory': {'stone': 5, 'pickaxe': 1},
        'drops': [
            {'item': 'stone', 'amount': 4, 'chance': 0.9},
            {'item': 'pickaxe', 'amount': 1, 'chance': 0.3}
        ],
        'behavior_config': {
            'actions': ['mine_rocks'],
            'can_place_camp': True,
            'wander_when_idle': True  # Wander between mining
        },
        'ai_params': {
            'aggressiveness': 0.75,  # High — miners consistently seek rocks/ore/caves
            'passiveness': 0.10,     # Rarely drops task
            'idleness': 0.05,        # Rarely idles
            'flee_chance': 0.65,
            'combat_chance': 0.35,
            'target_types': ['food', 'water', 'stone', 'resource']
        }
    },
    # Enemies
    'BANDIT': {
        'color': (150, 50, 50),
        'symbol': 'B',
        'max_health': 50,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 22,
        'speed': 1.3,
        'food_sources': [],
        'water_sources': ['WATER'],
        'hostile': True,
        'humanoid': True,
        'edible': False,
        'attacks_structures': True,
        'drops': [
            {'item': 'meat', 'amount': 2, 'chance': 0.8},
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.90,  # Nearly as aggressive as Guards (was 0.80)
            'passiveness': 0.03,     # Very alert (was 0.10)
            'idleness': 0.02,        # Always hunting (was 0.05)
            'flee_chance': 0.10,
            'combat_chance': 0.90,
            'attack_chance': 0.45,
            'target_types': ['hostile', 'structure', 'resource']
        }
    },
    'GOBLIN': {
        'color': (100, 150, 50),
        'symbol': 'g',
        'max_health': 35,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 13,
        'speed': 1.1,
        'food_sources': [],
        'water_sources': ['WATER'],
        'hostile': True,
        'humanoid': True,
        'edible': False,
        'attacks_structures': True,
        'drops': [
            {'item': 'meat', 'amount': 1, 'chance': 0.7},  # Drop meat
            {'item': 'stone', 'amount': 1, 'chance': 0.7},
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.85,  # Very aggressive (was 0.70)
            'passiveness': 0.05,     # More alert (was 0.15)
            'idleness': 0.03,        # More active (was 0.10)
            'flee_chance': 0.15,
            'combat_chance': 0.85,
            'attack_chance': 0.50,
            'target_types': ['hostile', 'structure', 'resource']
        }
    },
    'SKELETON': {
        'color': (200, 200, 200),
        'symbol': 'K',
        'max_health': 35,
        'max_hunger': 50,
        'max_thirst': 50,
        'strength': 13,
        'speed': 1.0,
        'food_sources': [],
        'water_sources': [],
        'hostile': True,
        'humanoid': True,
        'edible': False,
        'drops': [
            {'item': 'meat', 'amount': 1, 'chance': 0.5},  # Drop meat (rotten but edible)
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.60,  # More passive than others (was 0.75)
            'passiveness': 0.20,     # More likely to disengage (was 0.10)
            'idleness': 0.10,        # Takes more breaks (was 0.05)
            'flee_chance': 0.05,
            'combat_chance': 0.95,
            'attack_chance': 0.35,
            'target_types': ['hostile', 'structure']
        }
    },
    'TERMITE': {
        'color': (255, 215, 0),  # Yellow/gold
        'symbol': 'T',
        'sprite_name': 'yellow termite',  # Maps to sprite files named "yellow termite_direction_frame.png"
        'max_health': 25,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 4,
        'speed': 1.1,
        'food_sources': ['TREE1', 'TREE2'],  # Eats trees
        'water_sources': ['WATER'],
        'hostile': True,
        'edible': False,
        'attacks_structures': True,
        'attacks_trees': True,
        'drops': [
            {'item': 'sand', 'amount': 1, 'chance': 0.6},
            {'item': 'bones', 'amount': 1, 'chance': 0.2},
            {'cell': 'SAND', 'chance': 0.3}
        ],
        'behavior_config': {
            'actions': ['chop_trees'],
            'wander_when_idle': False  # Stay focused on eating trees
        },
        'ai_params': {
            'aggressiveness': 0.95,  # VERY aggressive on trees (was 0.50)
            'passiveness': 0.02,     # Never distracted from wood (was 0.60!!!)
            'idleness': 0.01,        # Constantly eating trees (was 0.20)
            'flee_chance': 0.80,
            'combat_chance': 0.20,
            'attack_chance': 0.15,
            'target_types': ['food']  # Trees are their food source
        }
    },
    'BAT': {
        'color': (40, 30, 50),
        'symbol': 'b',
        'sprite_name': 'black bat',  # Maps to "black bat_direction_frame.png"
        'max_health': 10,
        'max_hunger': 80,
        'max_thirst': 80,
        'strength': 5,       # Very low damage per hit
        'speed': 1.6,        # Fast flyers
        'food_sources': [],
        'water_sources': ['WATER'],
        'hostile': True,
        'edible': False,
        'flying': True,       # Can pass over trees, houses, etc.
        'nocturnal': True,    # Active at night, shelters during day
        'cave_spawner': True, # Spawns inside caves
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.3}
        ],
        'ai_params': {
            'aggressiveness': 0.40,   # Moderate — attacks opportunistically
            'passiveness': 0.35,      # High chance to disengage from combat
            'idleness': 0.15,         # Sometimes just hangs around
            'flee_chance': 0.20,      # Will flee if threatened
            'combat_chance': 0.80,    # Usually fights back
            'attack_chance': 0.30,
            'target_types': ['hostile']  # Attacks other NPCs
        }
    },
    'RED_BIRD': {
        'color': (200, 60, 40),
        'symbol': 'r',
        'sprite_name': 'red bird',
        'max_health': 6,
        'max_hunger': 60,
        'max_thirst': 60,
        'strength': 2,
        'speed': 1.8,
        'food_sources': ['GRASS', 'FLOWER'],
        'water_sources': ['WATER', 'LAKE'],
        'hostile': False,
        'edible': True,
        'flying': True,
        'drops': [
            {'item': 'meat', 'amount': 1, 'chance': 0.5},
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.02,
            'passiveness': 0.60,
            'idleness': 0.30,
            'flee_chance': 0.95,
            'combat_chance': 0.05,
            'target_types': ['food', 'water']
        }
    },
    'BUTTERFLY': {
        'color': (180, 120, 220),
        'symbol': 'u',
        'sprite_name': 'butterfly',
        'max_health': 3,
        'max_hunger': 40,
        'max_thirst': 40,
        'strength': 1,
        'speed': 1.4,
        'food_sources': ['FLOWER', 'GRASS'],
        'water_sources': ['WATER'],
        'hostile': False,
        'edible': False,
        'flying': True,
        'drops': [],
        'ai_params': {
            'aggressiveness': 0.01,
            'passiveness': 0.70,
            'idleness': 0.25,
            'flee_chance': 0.99,
            'combat_chance': 0.01,
            'target_types': ['food', 'water']
        }
    },
    'CHICKEN': {
        'color': (240, 220, 160),
        'symbol': 'c',
        'sprite_name': 'chicken',
        'max_health': 12,
        'max_hunger': 80,
        'max_thirst': 80,
        'strength': 3,
        'speed': 0.9,
        'food_sources': ['GRASS', 'CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER', 'WELL'],
        'hostile': False,
        'edible': True,
        'drops': [
            {'item': 'meat', 'amount': 1, 'chance': 0.7},
            {'item': 'bones', 'amount': 1, 'chance': 0.2}
        ],
        'ai_params': {
            'aggressiveness': 0.02,
            'passiveness': 0.65,
            'idleness': 0.25,
            'flee_chance': 0.90,
            'combat_chance': 0.10,
            'target_types': ['food', 'water']
        }
    },
    'BLACK_SPIDER': {
        'color': (20, 20, 30),
        'symbol': 's',
        'sprite_name': 'blackSpider',
        'max_health': 30,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 17,
        'speed': 1.5,
        'food_sources': ['SHEEP', 'DEER', 'CHICKEN'],
        'water_sources': ['WATER'],
        'hostile': True,
        'edible': False,
        'cave_spawner': True,
        'drops': [
            {'item': 'bones', 'amount': 1, 'chance': 0.4}
        ],
        'ai_params': {
            'aggressiveness': 0.80,
            'passiveness': 0.10,
            'idleness': 0.05,
            'flee_chance': 0.20,
            'combat_chance': 0.80,
            'attack_chance': 0.60,
            'target_types': ['food', 'water', 'hostile']
        }
    },

}

# Quest Types
QUEST_TYPES = {
    'FARM': {
        'name': 'Farm',
        'description': 'Build and tend a village',
        'color': (139, 105, 20),
        'symbol': '🌾',
        'target_types': ['SOIL', 'CARROT1', 'TREE', 'CAMP', 'HOUSE'],
    },
    'HUNT': {
        'name': 'Hunt',
        'description': 'Hunt down a hostile creature',
        'color': (200, 50, 50),
        'symbol': '⚔',
        'target_types': ['HOSTILE_NPC'],
    },
    'SLAY': {
        'name': 'Slay',
        'description': 'Defeat a specific enemy type',
        'color': (150, 0, 0),
        'symbol': '☠',
        'target_types': ['GOBLIN', 'BANDIT', 'WOLF', 'SKELETON', 'TERMITE'],
    },
    'EXPLORE': {
        'name': 'Explore',
        'description': 'Find a specific location',
        'color': (100, 150, 200),
        'symbol': '◉',
        'target_types': ['HOUSE', 'CAVE', 'CAMP'],
    },
    'GATHER': {
        'name': 'Gather',
        'description': 'Collect specific resources',
        'color': (100, 200, 100),
        'symbol': '✿',
        'target_types': ['TREE', 'STONE', 'WATER'],
    },
    'LUMBER': {
        'name': 'Lumber',
        'description': 'Chop trees for wood',
        'color': (160, 100, 40),
        'symbol': '🪓',
        'target_types': ['TREE1', 'TREE2'],
    },
    'MINE': {
        'name': 'Mine',
        'description': 'Mine stone for resources',
        'color': (140, 140, 160),
        'symbol': '⛏',
        'target_types': ['STONE'],
    },
    'RESCUE': {
        'name': 'Rescue',
        'description': 'Find and assist an NPC',
        'color': (255, 200, 50),
        'symbol': '♥',
        'target_types': ['FARMER', 'TRADER', 'LUMBERJACK'],
    },
    'SEARCH': {
        'name': 'Search',
        'description': 'Find a specific item or weapon',
        'color': (200, 180, 255),
        'symbol': '🔍',
        'target_types': ['ITEM'],
    },
    # ── Combat quest types (player + NPC) ────────────────────────────────────
    'COMBAT_HOSTILE': {
        'name': 'Combat (Hostile)',
        'description': 'Hunt and fight hostile entities only',
        'color': (220, 80, 30),
        'symbol': '🗡',
        'target_types': ['HOSTILE_NPC'],
        'requires_friendly_fire': False,   # safe with friendly-fire OFF
    },
    'COMBAT_ALL': {
        'name': 'Combat (All)',
        'description': 'Fight any entity — hostile or peaceful',
        'color': (180, 0, 180),
        'symbol': '💀',
        'target_types': ['ANY_NPC'],
        'requires_friendly_fire': True,    # needs friendly-fire ON; autopilot skips when FF is OFF
    },
}

# ── NPC Quest Focus System ────────────────────────────────────────────────────
# The six NPC quest focuses, in progression order (peaceful → aggressive).
# 'combat_all' is kept separate; all others share equal unlock probability.
NPC_QUEST_TYPES_PEACEFUL = ['farming', 'building', 'mining', 'crafting', 'exploring', 'combat_hostile']
NPC_QUEST_TYPES_ALL      = NPC_QUEST_TYPES_PEACEFUL + ['combat_all']

# Default quest_focus by NPC type (assigned at spawn)
NPC_QUEST_FOCUS_DEFAULT = {
    'FARMER':     'farming',
    'LUMBERJACK': 'building',
    'MINER':      'mining',
    'TRADER':     'exploring',
    'GUARD':      'exploring',
    'WIZARD':     'exploring',
    'WARRIOR':    'combat_hostile',
    'COMMANDER':  'combat_hostile',
    'KING':       'combat_hostile',
    # Hostile types: default to all-combat
    'WOLF':       'combat_all',
    'GOBLIN':     'combat_all',
    'BANDIT':     'combat_all',
    'SKELETON':   'combat_all',
}

# Per-level-up unlock probabilities
NPC_QUEST_UNLOCK_CHANCE          = 0.10   # 10% — equal for all peaceful + combat_hostile
NPC_QUEST_UNLOCK_CHANCE_CMBT_ALL = 0.03   # 3%  — lower for all-combat (even for peaceful NPCs)

# Chance to spontaneously switch focus on level-up (only when >1 focus unlocked)
NPC_QUEST_FOCUS_SWITCH_CHANCE = 0.10      # 10%

# Add new items for entity drops
ITEMS.update({
    'meat': {'color': (180, 50, 50), 'name': 'Meat'},
    'fur': {'color': (100, 100, 100), 'name': 'Fur'},
    'stone': {'color': (100, 100, 100), 'name': 'Stone'},
    'bones': {'color': (220, 220, 200), 'name': 'Bones'},
    'grass': {'color': COLORS['GRASS'], 'name': 'Grass'},
    'dirt': {'color': COLORS['DIRT'], 'name': 'Dirt'},
    'soil': {'color': COLORS['SOIL'], 'name': 'Soil'},
    'water_bucket': {'color': COLORS['WATER'], 'name': 'Water Bucket'},
    'deep_water_bucket': {'color': COLORS['DEEP_WATER'], 'name': 'Deep Water Bucket'},
    'sand': {'color': COLORS['SAND'], 'name': 'Sand'},
    'shovel': {'color': (150, 150, 150), 'name': 'Shovel', 'is_tool': True},
    'pickaxe': {'color': (100, 100, 120), 'name': 'Pickaxe', 'is_tool': True},
    'bucket': {'color': (180, 180, 180), 'name': 'Bucket', 'is_tool': True},
    'tree_sapling': {'color': COLORS['TREE1'], 'name': 'Tree Sapling'},
    'bush': {'color': (34, 100, 34), 'name': 'Bush'},
    'tree1': {'color': COLORS['TREE1'], 'name': 'Tree 1'},
    'tree2': {'color': COLORS['TREE2'], 'name': 'Tree 2'},
    'carrot': {'color': COLORS['CARROT1'], 'name': 'Carrot'},
    'carrot1': {'color': COLORS['CARROT1'], 'name': 'Carrot 1'},
    'carrot2': {'color': COLORS['CARROT2'], 'name': 'Carrot 2'},
    'carrot3': {'color': COLORS['CARROT3'], 'name': 'Carrot 3'},
    'house': {'color': COLORS['HOUSE'], 'name': 'House'},
    'cave': {'color': COLORS['CAVE'], 'name': 'Cave'},
    'mineshaft': {'color': COLORS['MINESHAFT'], 'name': 'Mineshaft'},
    'camp': {'color': (200, 100, 50), 'name': 'Camp'},
    'wall': {'color': COLORS['WALL'], 'name': 'Wall'},
    'flower': {'color': COLORS['FLOWER'], 'name': 'Flower'},
    'flower_pattern1': {'color': (255, 200, 50),  'name': 'Yellow Flower'},
    'flower_pattern2': {'color': (180, 100, 220), 'name': 'Purple Flower'},
    'flower_pattern3': {'color': (255, 100, 100), 'name': 'Red Flower'},
    'gravestone': {'color': COLORS['GRAVESTONE'], 'name': 'Gravestone'},
    'broken_gravestone': {'color': COLORS['BROKEN_GRAVESTONE'], 'name': 'Broken Gravestone'},
    'bed_blue': {'color': COLORS['BED_BLUE'], 'name': 'Bed (Blue)'},
    'bed_white': {'color': COLORS['BED_WHITE'], 'name': 'Bed (White)'},
    'desert_well': {'color': COLORS['DESERT_WELL'], 'name': 'Desert Well'},
    'water_trough': {'color': COLORS['WATER_TROUGH'], 'name': 'Water Trough'},
    'bookshelf': {'color': COLORS['BOOKSHELF'], 'name': 'Bookshelf'},
    'wood_chair': {'color': COLORS['WOOD_CHAIR'], 'name': 'Wood Chair'},
    'wood_table': {'color': COLORS['WOOD_TABLE'], 'name': 'Wood Table'},
    'small_potted_plant': {'color': COLORS['SMALL_POTTED_PLANT'], 'name': 'Potted Plant'},
    'blue_mushroom': {'color': COLORS['BLUE_MUSHROOM'], 'name': 'Blue Mushroom',
                      'is_food': True, 'food_value': 15, 'description': 'A glowing cave fungus. Edible.'},
    'bottle': {'color': (160, 200, 220), 'name': 'Bottle'},
    'bottles': {'color': (140, 180, 200), 'name': 'Bottles'},
    'magic_rune': {'color': (180, 120, 255), 'name': 'Magic Rune', 'magic_damage': 'arcane', 'damage': 5, 'sprite_name': 'magic_rune'},
})

# Cell pickup requirements
CELL_PICKUP = {
    'GRASS': {'tool': None, 'item': 'grass'},
    'DIRT': {'tool': None, 'item': 'dirt'},
    'SOIL': {'tool': None, 'item': 'soil'},
    'SAND': {'tool': None, 'item': 'sand'},
    'WATER': {'tool': None, 'item': 'water_bucket'},
    'STONE': {'tool': None, 'item': 'stone'},
    'TREE1': {'tool': None, 'item': 'tree_sapling', 'amount': 1},
    'TREE2': {'tool': None, 'item': 'tree_sapling', 'amount': 1},
    'BUSH': {'tool': None, 'item': 'bush', 'amount': 1},
    'FLOWER_PATTERN1': {'tool': None, 'item': 'flower'},
    'FLOWER_PATTERN2': {'tool': None, 'item': 'flower'},
    'FLOWER_PATTERN3': {'tool': None, 'item': 'flower'},
    'APPLE_CRATE':     {'tool': None, 'item': 'apple_crate'},
    'WALL': {'tool': None, 'item': 'wall'},
    'HOUSE': {'tool': None, 'item': 'house'},
    'CAVE': {'tool': None, 'item': 'cave'},
    'MINESHAFT': {'tool': None, 'item': 'mineshaft'},
    'CARROT1': {'tool': None, 'item': 'carrot', 'amount': 1},
    'CARROT2': {'tool': None, 'item': 'carrot', 'amount': 2},
    'CARROT3': {'tool': None, 'item': 'carrot', 'amount': 3},
    # Add item cells
    'WOOD': {'tool': None, 'item': 'wood'},
    'PLANKS': {'tool': None, 'item': 'planks'},
    'MEAT': {'tool': None, 'item': 'meat'},
    'FUR': {'tool': None, 'item': 'fur'},
    'BONES': {'tool': None, 'item': 'bones'}
}

# NPC transformation configuration - defines when NPCs change roles
NPC_TRANSFORMATION_CONFIG = {
    'TRADER': {
        'transform_rate': 0.0017,  # ~10% per minute at 60 FPS
        'transform_logic': 'settlement',  # Use settlement logic
        'possible_types': ['FARMER', 'LUMBERJACK'],
        'base_weights': {'FARMER': 0.5, 'LUMBERJACK': 0.5},
        'zone_need_weights': {
            # If zone needs X, increase its weight
            'no_workers': {'FARMER': 0.6, 'LUMBERJACK': 0.4},
            'need_farmer': {'FARMER': 0.8, 'LUMBERJACK': 0.2},
            'need_lumberjack': {'FARMER': 0.2, 'LUMBERJACK': 0.8}
        }
    },
    'WARRIOR': {
        'transform_rate': 0.00025,  # ~1.5% per minute at 60 FPS — rare promotion
        'transform_logic': 'promotion',
        'possible_types': ['COMMANDER'],
        'level_requirement': 2,
    }
}

# Cell placement - what item places what cell
ITEM_TO_CELL = {
    'grass': 'GRASS',
    'dirt': 'DIRT',
    'soil': 'SOIL',
    'sand': 'SAND',
    'water_bucket': 'WATER',
    'deep_water_bucket': 'DEEP_WATER',
    'stone': 'STONE',
    'tree_sapling': 'TREE1',
    'tree1': 'TREE1',
    'tree2': 'TREE2',
    'bush': 'BUSH',
    'carrot': 'CARROT1',
    'carrot1': 'CARROT1',
    'carrot2': 'CARROT2',
    'carrot3': 'CARROT3',
    'house': 'HOUSE',
    'cave': 'CAVE',
    'mineshaft': 'MINESHAFT',
    'camp': 'CAMP',
    'chest': 'CHEST',
    'wall': 'WALL',
    'meat': 'MEAT',
    'fur': 'FUR',
    'bones': 'BONES',
    'flower': 'FLOWER_PATTERN1',
    'flower_pattern1': 'FLOWER_PATTERN1',
    'flower_pattern2': 'FLOWER_PATTERN2',
    'flower_pattern3': 'FLOWER_PATTERN3',
    'gravestone': 'GRAVESTONE',
    'bed_blue': 'BED_BLUE',
    'desert_well': 'DESERT_WELL',
    'iron_ore': 'IRON_ORE',
    'well': 'WELL',
    'cactus': 'CACTUS',
    'barrel': 'BARREL',
    'stone_house': 'STONE_HOUSE',
    'ruined_sandstone_column': 'RUINED_SANDSTONE_COLUMN',
    'forge': 'FORGE',
}

# Colors for entities
COLORS.update({
    'ENTITY_BG': (255, 255, 255, 128)  # Semi-transparent white background
})

# ============================================================================
# NPC BEHAVIOR TABLES — Data-driven NPC actions
# Each behavior is a list of (action_type, params) tried in priority order.
# Action types: 'harvest', 'transform', 'place', 'chop', 'build', 'wander'
# ============================================================================

NPC_BEHAVIORS = {
    'FARMER': [
        # Harvest mature crops → get items
        {'action': 'harvest_cell', 'cells': ['CARROT3', 'CARROT2'],
         'rate': FARMER_HARVEST_RATE, 'success': FARMER_HARVEST_SUCCESS,
         'result_cell': 'SOIL', 'activity': 'harvest'},
        # Till grass/dirt → soil
        {'action': 'transform_cell', 'cells': ['GRASS', 'DIRT'],
         'rate': FARMER_TILL_RATE, 'success': FARMER_TILL_SUCCESS,
         'result_cell': 'SOIL', 'activity': 'till'},
        # Plant on soil (requires carrot/seeds)
        {'action': 'place_cell', 'cells': ['SOIL'],
         'rate': FARMER_PLANT_RATE, 'success': FARMER_PLANT_SUCCESS,
         'result_cell': 'CARROT1', 'consume': ['carrot', 'seeds'],
         'activity': 'plant'},
    ],
    'LUMBERJACK': [
        # Chop trees → get wood
        {'action': 'harvest_cell', 'cells': ['TREE1', 'TREE2', 'TREE3'],
         'rate': LUMBERJACK_BASE_CHOP_RATE, 'success': LUMBERJACK_CHOP_SUCCESS,
         'activity': 'chop'},
        # Build house if enough wood
        {'action': 'build', 'structure': 'HOUSE', 'cost': {'wood': 10},
         'rate': LUMBERJACK_BUILD_RATE, 'max_per_zone': 3,
         'valid_cells': ['GRASS', 'DIRT'], 'prefer_near': 'COBBLESTONE',
         'activity': 'build'},
    ],
    'MINER': [
        # Mine stone and ore — high rate for aggressive targeting
        {'action': 'harvest_cell', 'cells': ['STONE', 'IRON_ORE'],
         'rate': 0.65, 'success': 0.8,
         'activity': 'mine'},
    ],
    'GUARD': [
        # Guards don't have resource actions — they patrol and fight
    ],
    'TRADER': [
        # Traders don't harvest — they trade and wander
    ],
}

# ============================================================================
# SPRITE MANAGER CLASS
# ============================================================================