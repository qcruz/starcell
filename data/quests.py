from data.settings import *

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
