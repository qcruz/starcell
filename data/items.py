from data.settings import *
from data.cells import COLORS

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

    # Iron pipeline
    'iron_ore':   {'color': (139, 90, 43),   'name': 'Iron Ore'},
    'iron_ingot': {'color': (180, 140, 100),  'name': 'Iron Ingot'},
    'iron_sword': {'color': (200, 200, 220),  'name': 'Iron Sword', 'is_tool': True, 'damage': 20, 'sprite_name': 'iron_sword'},

    # Special
    'skeleton_bones': {'color': (240, 240, 230), 'name': 'Skeleton Bones', 'is_follower': True},

    # Runestones - Magic damage types
    'lightning_rune': {'color': (100, 149, 237), 'name': 'Lightning Rune', 'magic_damage': 'lightning', 'damage': 3},
    'fire_rune': {'color': (255, 69, 0), 'name': 'Fire Rune', 'magic_damage': 'fire', 'damage': 3},
    'ice_rune': {'color': (173, 216, 230), 'name': 'Ice Rune', 'magic_damage': 'ice', 'damage': 3},
    'poison_rune': {'color': (50, 205, 50), 'name': 'Poison Rune', 'magic_damage': 'poison', 'damage': 3},
    'shadow_rune': {'color': (75, 0, 130), 'name': 'Shadow Rune', 'magic_damage': 'shadow', 'damage': 3, 'sprite_name': 'magic_rune'}
}

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
