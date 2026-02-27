from data.settings import *

# Wizard spell effects
WIZARD_SPELLS = {
    'heal': {'type': 'heal', 'amount': 20, 'range': 6, 'color': (100, 255, 100), 'hostile_only': False},
    'fireball': {'type': 'damage', 'amount': 15, 'element': 'fire', 'range': 6, 'color': (255, 69, 0), 'hostile_only': True},
    'lightning': {'type': 'damage', 'amount': 15, 'element': 'lightning', 'range': 6, 'color': (100, 149, 237), 'hostile_only': True},
    'ice': {'type': 'damage', 'amount': 15, 'element': 'ice', 'range': 6, 'color': (173, 216, 230), 'hostile_only': True},
    'enchant': {'type': 'enchant', 'range': 6, 'color': (200, 150, 255), 'hostile_only': False},
}
