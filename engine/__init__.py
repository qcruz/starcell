# engine package
# Entity class lives in root entity.py (imported via `from entity import *` in game modules).
# This package exists so `from engine import *` in ai/ modules resolves without error.
from entity import Entity, Inventory, Quest, NpcQuestSlot
