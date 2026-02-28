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
RAIN_FREQUENCY_MIN = 30  # Minimum ticks between rain (1 minute at 60 FPS)
RAIN_FREQUENCY_MAX = 250  # Maximum ticks between rain (2 minutes at 60 FPS)
RAIN_DURATION_MIN = 10    # Minimum rain duration (5 seconds)
RAIN_DURATION_MAX = 60    # Maximum rain duration (15 seconds)
RAIN_WATER_SPAWNS = 5      # Water cells created per rain tick per screen
RAIN_GRASS_SPAWNS = 8      # Dirt→Grass conversions per rain tick

# Day/Night Cycle
DAY_LENGTH = 150          # Day duration in ticks (2.5 minutes at 60 FPS)
NIGHT_LENGTH = 150        # Night duration in ticks (2.5 minutes at 60 FPS)
NIGHT_OVERLAY_ALPHA = 40  # Darkness overlay opacity (0-255, subtle at 40)

# Quest System
QUEST_COOLDOWN = 300      # Ticks before new quest target assigned after completion (5 seconds)
QUEST_XP_MULTIPLIER = 10  # XP reward = target_level × this value

# Cell Growth & Decay Rates (probability per tick) - SLOWED for subtle changes
GRASS_TO_DIRT_RATE = 0.00001    # Grass decays to dirt without water (was 0.0001)
DIRT_TO_SAND_RATE = 0.000005    # Dirt becomes sand in severe drought (was 0.00005)
DIRT_TO_GRASS_RATE = 0.0001     # Dirt becomes grass with water (was 0.0005)
TREE_GROWTH_RATE = 0.00005      # Grass becomes tree (was 0.0001)
TREE_DECAY_RATE = 0.0005        # Trees decay when overcrowded (was 0.001)
SAND_RECLAIM_RATE = 0.0005      # Sand becomes dirt with water (was 0.001)
FLOWER_SPREAD_RATE = 0.0001     # Flowers spread to nearby grass (was 0.0005)
FLOWER_DECAY_RATE = 0.0005      # Flowers die from overcrowding/drought (was 0.002)
DEEP_WATER_FORM_RATE = 0.05     # Water becomes deep water (apply_cellular_automata)
DEEP_WATER_EVAPORATE_RATE = 0.03 # Deep water becomes water (apply_cellular_automata)
WATER_TO_DIRT_RATE = 0.005      # Water slowly evaporates to dirt without neighbors (apply_cellular_automata)
FLOODING_RATE = 0.015           # Water spreads to dirt (apply_cellular_automata)

# Entity Survival
HUNGER_DECAY_RATE = 0.02        # Hunger loss per tick (slowed down further)
THIRST_DECAY_RATE = 0.015       # Thirst loss per tick (slowed down further)
STARVATION_DAMAGE = 0.1         # HP loss per tick when starving (was 0.3)
DEHYDRATION_DAMAGE = 0.15       # HP loss per tick when dehydrated (was 0.5)
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
NPC_COMBAT_MOVE_INTERVAL = 30   # Fast movement during combat (0.5 seconds)

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
FARMER_PLANT_SUCCESS = 0.3      # 30% plant success
LUMBERJACK_CHOP_SUCCESS = 0.85   # 85% chop success (increased for much faster work)
LUMBERJACK_BUILD_SUCCESS = 0.35 # 35% build success
MINER_MINE_SUCCESS = 0.2        # 20% mine success
PEACEFUL_NPC_MIGRATE_RATE = 0.05 # Chance to migrate if duplicate type in zone (update_entity_ai)
ZONE_CHANGE_COOLDOWN = 1800  # Ticks (30 seconds at 60 FPS) before entity can change zones again (seek_zone_exit path)
NPC_SEAMLESS_CROSS_COOLDOWN = 30   # Ticks (0.5 s) anti-bounce cooldown for seamless zone crossing
NPC_PEACEFUL_WANDER_CHANCE = 0.60  # Probability a peaceful NPC actually wanders when idle
TARGET_STUCK_THRESHOLD = 180  # Ticks (3 seconds) before target is considered stuck and added to memory_lane
NPC_TREE_CLEAR_RATE = 0.05  # Non-lumberjack NPCs can clear trees (no wood collected)
ENHANCED_SETTLEMENT_RATE = 0.25 # Settlement rate when zone needs specific role (farmer/lumberjack/miner)

# Trader Path Building (Cellular Automata)
TRADER_PATH_BUILD_RATE = 0.6    # Chance to convert cell to dirt while walking (increased for traders/guards/miners)
TRADER_COBBLE_RATE = 0.25       # Chance to upgrade dirt to cobblestone (increased for faster road building)
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
RAID_CHANCE_BASE = 0.08         # 8% chance for raid when zone has 5+ entities
RAID_POPULATION_THRESHOLD = 6   # Minimum entities in zone to trigger raid check
HIDDEN_CAVE_SPAWN_CHANCE = 0.20 # 20% chance to spawn hidden cave during raid
NATURAL_CAVE_ZONE_CHANCE = 0.08 # 8% chance a zone gets a natural cave on generation
PLAYER_MINESHAFT_BASE_CHANCE = 0.05 # 5% base chance for player mining to create mineshaft
MINESHAFT_DEPTH_DIVISOR = 2.0  # Each depth level halves the mineshaft creation chance
MINER_MINESHAFT_CHANCE = 0.03  # 3% chance per mine action for NPC miners
MINESHAFT_MAX_PER_ZONE = 2     # Max mineshafts NPCs can create in one zone
WARRIOR_PROMOTION_CHANCE = 0.60 # 60% chance highest level entity becomes warrior after raid clear

# Miner & Structure Systems
MINER_CAVE_CREATE_CHANCE = 0.10 # 10% chance to create cave when mining at zone corners
CAMP_UPGRADE_CHANCE = 0.001     # 0.1% chance per update for camp to upgrade to house
CAVE_HOSTILE_SPAWN_CHANCE = 0.005 # 0.5% chance per cave per update to spawn hostile
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

# ============================================================================
# END GAME BALANCE CONFIGURATION
# ============================================================================
