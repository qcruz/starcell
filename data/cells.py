from data.settings import *

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
    'CACTUS': (50, 120, 50),
    'BARREL': (120, 80, 40),
    'STONE_HOUSE': (110, 110, 120),
    'RUINED_SANDSTONE_COLUMN': (200, 160, 90),
}

# Colors for entities
COLORS.update({
    'ENTITY_BG': (255, 255, 255, 128)  # Semi-transparent white background
})

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
    'HOUSE': {'color': COLORS['HOUSE'], 'label': 'Hos', 'solid': True, 'enterable': True, 'subscreen_type': 'HOUSE_INTERIOR', 'grows_to': 'STONE_HOUSE', 'growth_rate': 0.01},
    'FORGE': {'color': COLORS['FORGE'], 'label': 'Frg', 'solid': True},
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
    'STAIRS_UP': {'color': (120, 100, 80), 'label': '↑', 'solid': False, 'exits_subscreen': True},
    'IRON_ORE': {
        'color': (139, 90, 43),
        'label': 'Fe',
        'solid': True,
        'drops': [{'item': 'iron_ore', 'amount': 1, 'chance': 1.0}],
    },
    'WELL': {
        'color': (100, 80, 60),
        'label': 'Wel',
        'solid': False,
        'interactable': True,
    },
    'CACTUS': {
        'color': (50, 120, 50),
        'label': 'Cct',
        'solid': True,
        'degrades_to': 'SAND',
        'degrade_rate': 0.0002,
    },
    'BARREL': {
        'color': (120, 80, 40),
        'label': 'Brl',
        'solid': True,
        'interactable': True,
    },
    'STONE_HOUSE': {
        'color': (110, 110, 120),
        'label': 'StH',
        'solid': True,
        'enterable': True,
        'subscreen_type': 'HOUSE_INTERIOR',
    },
    'RUINED_SANDSTONE_COLUMN': {
        'color': (200, 160, 90),
        'label': 'RSC',
        'solid': True,
    },
}

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
