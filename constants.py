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
pygame.init()

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
AI_STATE_IDLE_DURATION = 60     # Ticks for idle state (1 second)
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
ZONE_CHANGE_COOLDOWN = 1800  # Ticks (30 seconds at 60 FPS) before entity can change zones again
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
    'FLOWER': (255, 100, 200)
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
                'degrades_to': 'GRASS', 'degrade_rate': 0.0001,  # Very slow decay
                'harvest': {'item': 'carrot', 'amount': 2}},
    'CARROT3': {'color': COLORS['CARROT3'], 'label': 'Crt3', 'solid': False,
                'degrades_to': 'GRASS', 'degrade_rate': 0.00005,  # Very slow decay
                'harvest': {'item': 'carrot', 'amount': 3}},
    'SAND': {'color': COLORS['SAND'], 'label': 'Snd', 'solid': False},
    'COBBLESTONE': {'color': COLORS['COBBLESTONE'], 'label': 'Cob', 'solid': False, 'degrades_to': 'DIRT', 'degrade_rate': 0.00001},  # Very persistent
    'WALL': {'color': COLORS['WALL'], 'label': '█', 'solid': True},
    'HOUSE': {'color': COLORS['HOUSE'], 'label': 'Hos', 'solid': True, 'enterable': True, 'subscreen_type': 'HOUSE_INTERIOR', 'degrades_to': 'PLANKS', 'degrade_rate': 0.0001},
    'FORGE': {'color': COLORS['FORGE'], 'label': 'Frg', 'solid': True, 'degrades_to': 'STONE', 'degrade_rate': 0.0001},
    'CAVE': {'color': COLORS['CAVE'], 'label': 'Cav', 'solid': True, 'enterable': True, 'subscreen_type': 'CAVE'},
    'MINESHAFT': {'color': (90, 70, 50), 'label': 'Mine', 'solid': True, 'enterable': True, 'subscreen_type': 'CAVE', 'sprite_name': 'mineshaft'},
    'HIDDEN_CAVE': {'color': (40, 35, 30), 'label': 'HCav', 'solid': False, 'degrades_to': 'CAVE', 'degrade_rate': 0.005},
    'CAMP': {'color': (200, 100, 50), 'label': 'Camp', 'solid': False, 'grows_to': 'HOUSE', 'growth_rate': 0.001},
    'SOIL': {'color': COLORS['SOIL'], 'label': 'Soil', 'solid': False},
    'FLOWER': {'color': COLORS['FLOWER'], 'label': 'Flwr', 'solid': False, 'degrades_to': 'GRASS', 'degrade_rate': 0.0001},  # Very slow decay
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
    'STAIRS_UP': {'color': (120, 100, 80), 'label': '↑', 'solid': False, 'exits_subscreen': True}
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
    'bone_sword': {'color': (220, 220, 200), 'name': 'Bone Sword', 'is_tool': True, 'damage': 15},
    'club': {'color': (101, 67, 33), 'name': 'Club', 'is_tool': True, 'damage': 8},
    
    # Magic items
    'star_spell': {'color': (255, 215, 0), 'name': 'Star Spell', 'is_spell': True, 
                   'description': 'Enchants cells and entities'},
    'magic_stone': {'color': (138, 43, 226), 'name': 'Magic Stone', 'is_spell': True, 'damage': 12},
    'magic_wand': {'color': (255, 140, 255), 'name': 'Magic Wand', 'is_spell': True, 'damage': 10},
    'enchanted_sword': {'color': (147, 112, 219), 'name': 'Enchanted Sword', 'is_tool': True, 'damage': 25},
    'enchanted_axe': {'color': (148, 0, 211), 'name': 'Enchanted Axe', 'is_tool': True, 'damage': 20},
    
    # Materials
    'rope': {'color': (139, 119, 101), 'name': 'Rope'},
    'leather': {'color': (139, 90, 43), 'name': 'Leather'},
    'leather_armor': {'color': (160, 82, 45), 'name': 'Leather Armor', 'is_tool': True, 'armor': 5},
    'chest': {'color': (139, 69, 19), 'name': 'Chest'},
    'seeds': {'color': (205, 133, 63), 'name': 'Seeds'},
    
    # Food
    'cooked_meat': {'color': (139, 69, 19), 'name': 'Cooked Meat'},
    'stew': {'color': (165, 42, 42), 'name': 'Stew'},
    
    # Building
    'floor': {'color': (160, 120, 80), 'name': 'Floor'},
    'sandstone': {'color': (210, 180, 140), 'name': 'Sandstone'},
    
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
        {'item': 'stone_pickaxe', 'min': 1, 'max': 1, 'chance': 0.3}
    ],
    'CAVE_DEEP_CHEST': [
        {'item': 'gold', 'min': 50, 'max': 200, 'chance': 1.0},
        {'item': 'enchanted_sword', 'min': 1, 'max': 1, 'chance': 0.4},
        {'item': 'leather_armor', 'min': 1, 'max': 1, 'chance': 0.3},
        {'item': 'magic_stone', 'min': 1, 'max': 1, 'chance': 0.2}
    ]
}

# Biome definitions
BIOMES = {
    'FOREST': {'GRASS': 0.5, 'DIRT': 0.2, 'TREE1': 0.15, 'TREE2': 0.05, 'WATER': 0.1},
    'PLAINS': {'GRASS': 0.6, 'DIRT': 0.2, 'WATER': 0.05, 'CARROT1': 0.1, 'TREE1': 0.05},
    'DESERT': {'SAND': 0.7, 'DIRT': 0.2, 'WATER': 0.05, 'STONE': 0.05},
    'MOUNTAINS': {'STONE': 0.5, 'DIRT': 0.3, 'GRASS': 0.15, 'TREE1': 0.05}
}

# Entity types and properties
ENTITY_TYPES = {
    # Animals
    'SHEEP': {
        'color': (230, 230, 230),
        'symbol': 'S',
        'max_health': 20,
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
        'strength': 15,
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
            'target_types': ['food', 'water', 'hostile']
        }
    },
    'DEER': {
        'color': (139, 90, 43),
        'symbol': 'D',
        'max_health': 30,
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
        'max_health': 80,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 13,
        'speed': 1.0,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
            'aggressiveness': 0.05,  # Very low - farmers flee from danger
            'passiveness': 0.40,     # Somewhat passive - focus on work
            'idleness': 0.15,        # Moderately idle - take breaks
            'flee_chance': 0.70,
            'combat_chance': 0.30,
            'target_types': ['food', 'water', 'resource']
        }
    },
    'GUARD': {
        'color': (100, 100, 150),
        'symbol': 'G',
        'max_health': 130,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 31,
        'speed': 1.2,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
            'target_types': ['hostile', 'water', 'food']  # What to target
        }
    },
    'WARRIOR': {
        'color': (150, 50, 50),
        'symbol': 'W',
        'max_health': 100,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 26,
        'speed': 1.2,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
            'flee_chance': 0.05,     # 5% flee when threatened
            'combat_chance': 0.95,   # 95% fight when threatened
            'target_types': ['hostile', 'water', 'food', 'structure']  # What to target
        }
    },
    'COMMANDER': {
        'color': (180, 50, 50),
        'symbol': 'C',
        'max_health': 120,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 31,
        'speed': 1.2,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
            'flee_chance': 0.03,
            'combat_chance': 0.97,
            'target_types': ['hostile', 'water', 'food', 'structure']
        }
    },
    'KING': {
        'color': (220, 180, 50),
        'symbol': 'K',
        'max_health': 150,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 41,
        'speed': 1.0,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
            'target_types': ['hostile', 'water', 'food', 'structure']
        }
    },
    'TRADER': {
        'color': (218, 165, 32),
        'symbol': 'T',
        'max_health': 70,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 11,
        'speed': 0.8,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
        'max_health': 90,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 25,
        'speed': 0.7,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
        'max_health': 60,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 13,
        'speed': 1.0,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
        'max_health': 100,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 19,
        'speed': 0.9,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
        'max_health': 110,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 21,
        'speed': 0.8,
        'food_sources': ['CARROT1', 'CARROT2', 'CARROT3'],
        'water_sources': ['WATER'],
        'hostile': False,
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
            'aggressiveness': 0.10,  # Low but not fleeing
            'passiveness': 0.35,     # Focused on mining
            'idleness': 0.20,        # Take breaks between mining
            'flee_chance': 0.65,
            'combat_chance': 0.35,
            'target_types': ['food', 'water', 'resource']
        }
    },
    # Enemies
    'BANDIT': {
        'color': (150, 50, 50),
        'symbol': 'B',
        'max_health': 50,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 20,
        'speed': 1.3,
        'food_sources': [],
        'water_sources': ['WATER'],
        'hostile': True,
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
            'target_types': ['hostile', 'structure', 'resource']
        }
    },
    'GOBLIN': {
        'color': (100, 150, 50),
        'symbol': 'g',
        'max_health': 35,
        'max_hunger': 100,
        'max_thirst': 100,
        'strength': 12,
        'speed': 1.1,
        'food_sources': [],
        'water_sources': ['WATER'],
        'hostile': True,
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
            'target_types': ['hostile', 'structure', 'resource']
        }
    },
    'SKELETON': {
        'color': (200, 200, 200),
        'symbol': 'K',
        'max_health': 35,
        'max_hunger': 50,
        'max_thirst': 50,
        'strength': 12,
        'speed': 1.0,
        'food_sources': [],
        'water_sources': [],
        'hostile': True,
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
        'strength': 3,
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
        'strength': 4,       # Very low damage per hit
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
            'target_types': ['hostile']  # Attacks other NPCs
        }
    }

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

# ============================================================================
# ITEM DECAY SYSTEM - General decay rules for dropped items
# ============================================================================

# Item decay configuration - defines how dropped items decay over time
ITEM_DECAY_CONFIG = {
    'bones': {
        'decay_rate': 0.05,  # 5% chance per update cycle (per bone)
        'decay_results': {
            # Cell type → [(result_cell, weight), ...]
            'DIRT': [('GRASS', 0.7), ('TREE1', 0.3)],
            'SAND': [('GRASS', 0.7), ('TREE1', 0.3)],
            'GRASS': [('TREE1', 0.5), (None, 0.5)],  # None = just disappears
            'default': [(None, 1.0)]  # Already good terrain, just disappear
        }
    },
    'meat': {
        'decay_rate': 0.10,  # 10% chance to decay (meat spoils faster)
        'decay_results': {
            'default': [(None, 1.0)]  # Meat just disappears (eaten by animals)
        }
    },
    'carrot': {
        'decay_rate': 0.03,  # 3% chance to decay
        'decay_results': {
            'DIRT': [('CARROT1', 0.2), (None, 0.8)],  # Small chance to replant
            'SOIL': [('CARROT1', 0.5), (None, 0.5)],  # Better on soil
            'default': [(None, 1.0)]
        }
    }
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
    'wood': 'WOOD',
    'planks': 'PLANKS',
    'meat': 'MEAT',
    'fur': 'FUR',
    'bones': 'BONES',
    'flower': 'FLOWER'
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
        # Mine stone
        {'action': 'harvest_cell', 'cells': ['STONE'],
         'rate': 0.3, 'success': 0.7,
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