import pygame
import random
import json
import os

# Constants
CELL_SIZE = 40
GRID_WIDTH = 24
GRID_HEIGHT = 18
SCREEN_WIDTH = GRID_WIDTH * CELL_SIZE
SCREEN_HEIGHT = GRID_HEIGHT * CELL_SIZE + 60
FPS = 60
# Catch-up system constants
MAX_CATCHUP_PER_FRAME = 2  # Max zones to catch up at once
MAX_CYCLES_TO_SIMULATE = 100  # Cap at 100 cycles (6000 ticks ~= 100 seconds)

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

# ============================================================================
# GAME BALANCE CONFIGURATION - Adjust these to tune gameplay
# ============================================================================

# Weather System
RAIN_FREQUENCY_MIN = 120  # Minimum zone updates between rains (per zone)
RAIN_FREQUENCY_MAX = 2000 # Maximum zone updates between rains — long drought periods possible
RAIN_DURATION_MIN = 30    # Minimum rain duration in zone updates
RAIN_DURATION_MAX = 180   # Maximum rain duration in zone updates
RAIN_WATER_SPAWNS = 5      # Water cells created per rain tick per screen
RAIN_GRASS_SPAWNS = 8      # Dirt→Grass conversions per rain tick

# Day/Night Cycle
DAY_LENGTH = 150          # Day duration in ticks (2.5 minutes at 60 FPS)
NIGHT_LENGTH = 150        # Night duration in ticks (2.5 minutes at 60 FPS)
NIGHT_OVERLAY_ALPHA = 40  # Darkness overlay opacity (0-255, subtle at 40)

# Quest System
QUEST_COOLDOWN = 300      # Ticks before new quest target assigned after completion (5 seconds)
QUEST_XP_MULTIPLIER = 10  # XP reward = target_level × this value

# ── CA rate hierarchy (mirrors constants.py — constants.py is authoritative) ──
CA_BASE_RATE = 0.001
BASE_DECAY_RATE = CA_BASE_RATE  # legacy alias

# Tier 1 class rates
CA_GROWTH_RATE     = 0.1 * CA_BASE_RATE
CA_DECAY_RATE      = 0.1 * CA_BASE_RATE
CA_SPREAD_RATE     = 2   * CA_BASE_RATE
CA_WATER_EVAP_RATE = 8   * CA_BASE_RATE

# Tier 1 — Growth
DIRT_TO_GRASS_RATE            = 20.0 * CA_GROWTH_RATE
DIRT_TO_GRASS_WATER_RATE      = 10.0 * CA_GROWTH_RATE
GRASS_TO_TREE_RATE            = 1.0 * CA_GROWTH_RATE
GRASS_TO_FLOWER_RATE          = 1.0 * CA_GROWTH_RATE
GRASS_TO_FLOWER_PATTERN_RATE  = 5.0 * CA_GROWTH_RATE
SAND_TO_DIRT_STONE_RATE       = 2.0 * CA_GROWTH_RATE

# Tier 1 — Decay
GRASS_TO_DIRT_RATE          = 0.1  * CA_DECAY_RATE
DIRT_TO_SAND_DROUGHT_RATE   = 0.05 * CA_DECAY_RATE
TREE_TO_GRASS_RATE          = 5.0  * CA_DECAY_RATE
TREE_TO_GRASS_CROWD_RATE    = 10   * CA_DECAY_RATE
TREE_TO_GRASS_DROUGHT_RATE  = 3.0  * CA_DECAY_RATE
CACTUS_TO_SAND_DROUGHT_RATE = 3.0  * CA_DECAY_RATE
FLOWER_TO_GRASS_RATE        = 5.0  * CA_DECAY_RATE

# Tier 1 — Water dynamics
WATER_TO_BASE_ISOLATED_RATE = 2    * CA_BASE_RATE
DEEP_WATER_TO_WATER_RATE    = 0.5  * CA_WATER_EVAP_RATE
WATER_TO_DEEP_WATER_RATE    = 2.5  * CA_WATER_EVAP_RATE
SAND_TO_DIRT_WATER_RATE     = 10   * CA_WATER_EVAP_RATE
DIRT_TO_WATER_RAIN_RATE     = 0.75 * CA_WATER_EVAP_RATE
GRASS_TO_WATER_RAIN_RATE    = 1.0  * CA_WATER_EVAP_RATE
DIRT_TO_FLOWER_WATER_RATE   = 0.4  * CA_WATER_EVAP_RATE

# Tier 1 — Spread
BIOME_BORDER_SPREAD_RATE = 2.0 * CA_SPREAD_RATE
TERRAIN_DIFFUSION_RATE   = 1.0 * CA_GROWTH_RATE

# Tier 2 — Cross-biome: desert edge
GRASS_TO_DIRT_SAND_RATE  = 1.5 * CA_SPREAD_RATE
DIRT_TO_SAND_SPREAD_RATE = 2.0 * CA_SPREAD_RATE

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

# NPC Subscreen Behavior
NPC_SUBSCREEN_EXIT_CHANCE = 0.60  # 60% chance per update to try exiting subscreen

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
MINER_MINE_SUCCESS = 0.2        # 20% mine success
PEACEFUL_NPC_MIGRATE_RATE = 0.05 # Chance to migrate if duplicate type in zone (update_entity_ai)
ZONE_CHANGE_COOLDOWN = 1800  # Ticks (30 seconds at 60 FPS) before entity can change zones again (seek_zone_exit path)
NPC_SEAMLESS_CROSS_COOLDOWN = 30   # Ticks (0.5 s) anti-bounce cooldown for seamless zone crossing
NPC_CROSS_RAMP_TICKS = 300         # Ticks over which crossing probability ramps from 0% to 100% after a zone change
NPC_PEACEFUL_WANDER_CHANCE = 0.60  # Probability a peaceful NPC actually wanders when idle
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
OLD_AGE_DAMAGE = 0.05               # Health loss per tick when age exceeds max_age

# Entity Spawning
SPAWN_CHANCE_MULTIPLIER = 1.0   # Global spawn rate multiplier (1.0 = normal) (spawn_entities_for_screen)
FOREST_BIOME_CHANCE = 0.60      # 60% of zones are forest (generate_screen)
PLAINS_BIOME_CHANCE = 0.20      # 20% of zones are plains (generate_screen)
MOUNTAINS_BIOME_CHANCE = 0.15   # 15% of zones are mountains (generate_screen)
DESERT_BIOME_CHANCE = 0.05      # 5% of zones are desert (generate_screen)

# Raid Event System
RAID_CHECK_INTERVAL = 600       # Ticks between raid checks (10 seconds at 60 FPS)
RAID_CHANCE_BASE = 0.025        # 2.5% base raid chance (halved; structures lower it further)
RAID_POPULATION_THRESHOLD = 4   # Minimum entities in zone to trigger raid check
HIDDEN_CAVE_SPAWN_CHANCE = 0.50 # 50% chance to spawn hidden cave during raid (caves primary source)
NATURAL_CAVE_ZONE_CHANCE = 0.08 # 8% chance a zone gets a natural cave on generation
PLAYER_MINESHAFT_BASE_CHANCE = 0.05 # 5% base chance for player mining to create mineshaft
MINESHAFT_DEPTH_DIVISOR = 2.0  # Each depth level halves the mineshaft creation chance
MINER_MINESHAFT_CHANCE = 0.03  # 3% chance per mine action for NPC miners
MINESHAFT_MAX_PER_ZONE = 2     # Max mineshafts NPCs can create in one zone
WARRIOR_PROMOTION_CHANCE = 0.60 # 60% chance highest level entity becomes warrior after raid clear

# Miner & Structure Systems
MINER_CAVE_CREATE_CHANCE = 0.10 # 10% chance to create cave when mining at zone corners
CAMP_UPGRADE_CHANCE = 0.001     # 0.1% chance per update for camp to upgrade to house
CAVE_HOSTILE_SPAWN_CHANCE = 0.010 # 1.0% chance per cave per update to spawn hostile
TERMITE_SPAWN_CHANCE = 0.001      # 0.1% chance per zone per update to spawn termite (near trees) - reduced spawn rate
NIGHT_SKELETON_SPAWN_CHANCE = 0.01 # 1% chance per zone at night to spawn skeleton (higher near dropped items)
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
NEW_ZONE_INSTANTIATE_CHANCE = 0.05  # 5% chance to instantiate a new random zone per update cycle
ZONE_SOFT_CAP = 200                 # Overworld zone count above which new instantiation drops sharply

# NPC role targeting — maps quest_focus → eligible target cell/entity types.
# Used by find_closest_eligible_target and _resolve_current_target.
ROLE_CELL_TARGETS = {
    'FARM':   ['SAND', 'DIRT', 'SOIL', 'GRASS', 'CARROT1', 'CARROT2', 'CARROT3'],
    'LUMBER': ['TREE1', 'TREE2', 'TREE3'],
    'MINE':   ['STONE', 'IRON_ORE', 'CAVE', 'MINESHAFT'],
    'GATHER': ['STONE', 'TREE1', 'TREE2', 'IRON_ORE'],
}

# Priority order for ROLE targeting — tried one type at a time, first found wins.
# MINE: prefer raw CAVE excavation → IRON_ORE → STONE → MINESHAFT entry.
ROLE_CELL_PRIORITY = {
    'MINE': ['CAVE', 'IRON_ORE', 'STONE', 'MINESHAFT'],
}

# ============================================================================
# END GAME BALANCE CONFIGURATION
# ============================================================================
