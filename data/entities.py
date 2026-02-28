from data.settings import *
from data.cells import COLORS

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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
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
        'water_sources': ['WATER', 'WELL'],
        'hostile': False,
        'edible': False,
        'can_trade': True,
        'inventory': {'stone': 5, 'pickaxe': 1},
        'drops': [
            {'item': 'stone', 'amount': 4, 'chance': 0.9},
            {'item': 'pickaxe', 'amount': 1, 'chance': 0.3}
        ],
        'behavior_config': {
            'actions': ['mine_rocks', 'build_well'],
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
