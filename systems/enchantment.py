import random

from constants import ITEMS


class EnchantmentMixin:
    """Handles star spell casting, cell/entity enchantments, and follower management."""

    # -------------------------------------------------------------------------
    # Legendary item naming
    # -------------------------------------------------------------------------

    def generate_legendary_item_name(self, item_name, entity):
        """Generate a legendary name for a high-level item"""
        prefixes = ['Legendary', 'Epic', 'Mythic', 'Ancient', 'Eternal', 'Divine', 'Cursed', 'Blessed']
        suffixes = ['of Power', 'of the Ancients', 'of Destiny', 'of Glory', 'of Ruin', 'of the Stars',
                    'of Thunder', 'of Fire', 'of Ice', 'of Shadow', 'of Light']

        # Add magic type suffix if entity has runes
        magic_types = []
        for rune_type in ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']:
            if rune_type in entity.inventory and entity.inventory[rune_type] > 0:
                magic_name = rune_type.replace('_rune', '').capitalize()
                magic_types.append(f"of {magic_name}")

        # Use magic type if available, otherwise random suffix
        suffix = random.choice(magic_types) if magic_types else random.choice(suffixes)

        # Get base item name from ITEMS dict
        base_name = ITEMS.get(item_name, {}).get('name', item_name.capitalize())

        return f"{random.choice(prefixes)} {base_name} {suffix}"

    # -------------------------------------------------------------------------
    # Enchantment queries
    # -------------------------------------------------------------------------

    def is_cell_enchanted(self, x, y, screen_key):
        """Check if a cell is enchanted"""
        if screen_key not in self.enchanted_cells:
            return False
        return (x, y) in self.enchanted_cells[screen_key]

    def is_entity_enchanted(self, entity_id):
        """Check if an entity is enchanted"""
        return entity_id in self.enchanted_entities

    # -------------------------------------------------------------------------
    # Star spell
    # -------------------------------------------------------------------------

    def cast_star_spell(self):
        """Cast star spell on target cell or entity (L key)"""
        # Check if player has spell selected
        if not self.inventory.selected_magic or self.inventory.selected_magic != 'star_spell':
            print("Star spell not selected!")
            return

        # Check if player has magic available
        if self.player['magic_pool'] <= 0:
            print("No magic available!")
            return

        # Check energy (costs 3 per cast); default to max_energy if key missing (old save)
        _cur_energy = self.player.get('energy', self.player.get('max_energy', 100))
        if _cur_energy < 3:
            print("Not enough energy!")
            return
        self.player['energy'] = max(0, _cur_energy - 3)

        target = self.get_target_cell()
        if not target:
            return

        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"

        # Check if there's an entity at target
        entity_at_target = None
        if screen_key in self.screen_entities:
            for entity_id in self.screen_entities[screen_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    if entity.x == check_x and entity.y == check_y:
                        entity_at_target = (entity_id, entity)
                        break

        # If entity at target, enchant entity and make it a follower
        if entity_at_target:
            entity_id, entity = entity_at_target
            current_enchant = self.enchanted_entities.get(entity_id, 0)
            self.enchanted_entities[entity_id] = current_enchant + 1
            self.player['magic_pool'] -= 1

            # Add to followers list if not already a follower
            if entity_id not in self.followers:
                self.followers.append(entity_id)
                # Add follower item to ITEMS dict dynamically
                follower_name = f"{entity.type.lower()}_{entity_id}"
                if follower_name not in ITEMS:
                    ITEMS[follower_name] = {
                        'color': entity.props['color'],
                        'name': f"{entity.type} Follower",
                        'is_follower': True,
                        'entity_id': entity_id
                    }
                # Add to follower inventory
                self.inventory.add_follower(follower_name, 1)
                print(f"Enchanted {entity.type} - now following you! (enchant level {self.enchanted_entities[entity_id]})")
            else:
                print(f"Increased {entity.type} enchant to level {self.enchanted_entities[entity_id]}")
            return

        # Otherwise, enchant cell
        cell = self.current_screen['grid'][check_y][check_x]

        # Initialize enchanted_cells for this screen if needed
        if screen_key not in self.enchanted_cells:
            self.enchanted_cells[screen_key] = {}

        # Increase enchant level
        current_enchant = self.enchanted_cells[screen_key].get((check_x, check_y), 0)
        self.enchanted_cells[screen_key][(check_x, check_y)] = current_enchant + 1

        # Decrease magic pool permanently
        self.player['magic_pool'] -= 1

        print(f"Enchanted {cell} at ({check_x}, {check_y}) to level {self.enchanted_cells[screen_key][(check_x, check_y)]}")

    def release_enchantments(self):
        """Release enchantment from target cell/entity (K key) - decreases by 1 level"""
        target = self.get_target_cell()
        if not target:
            return

        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"

        # Check if there's an entity at target
        entity_at_target = None
        if screen_key in self.screen_entities:
            for entity_id in self.screen_entities[screen_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    if entity.x == check_x and entity.y == check_y:
                        entity_at_target = entity_id
                        break

        # Release entity enchantment if entity is targeted
        if entity_at_target and entity_at_target in self.enchanted_entities:
            self.enchanted_entities[entity_at_target] -= 1

            # Remove from dict if enchant level reaches 0
            if self.enchanted_entities[entity_at_target] <= 0:
                del self.enchanted_entities[entity_at_target]
                print(f"Fully released enchantment from entity {entity_at_target}")
            else:
                print(f"Decreased entity {entity_at_target} enchant to level {self.enchanted_entities[entity_at_target]}")

            # Restore 1 magic and 3 energy
            self.player['magic_pool'] = min(
                self.player['magic_pool'] + 1,
                self.player['max_magic_pool']
            )
            self.player['energy'] = min(
                self.player.get('energy', 0) + 3,
                self.player.get('max_energy', 100)
            )
            return

        # Otherwise release cell enchantment
        if screen_key in self.enchanted_cells:
            cell_key = (check_x, check_y)
            if cell_key in self.enchanted_cells[screen_key]:
                self.enchanted_cells[screen_key][cell_key] -= 1

                # Remove from dict if enchant level reaches 0
                if self.enchanted_cells[screen_key][cell_key] <= 0:
                    del self.enchanted_cells[screen_key][cell_key]
                    print(f"Fully released enchantment from cell at ({check_x}, {check_y})")
                else:
                    print(f"Decreased cell ({check_x}, {check_y}) enchant to level {self.enchanted_cells[screen_key][cell_key]}")

                # Restore 1 magic and 3 energy
                self.player['magic_pool'] = min(
                    self.player['magic_pool'] + 1,
                    self.player['max_magic_pool']
                )
                self.player['energy'] = min(
                    self.player.get('energy', 0) + 3,
                    self.player.get('max_energy', 100)
                )
                return

        print("Target is not enchanted!")

    # -------------------------------------------------------------------------
    # Follower management
    # -------------------------------------------------------------------------

    def release_follower(self):
        """Release selected follower (J key)"""
        # Check if a follower is selected
        selected_follower = self.inventory.selected_follower
        if not selected_follower:
            print("No follower selected!")
            return

        # Extract entity_id from follower name (format: "type_id")
        try:
            entity_id = int(selected_follower.split('_')[-1])
        except (ValueError, IndexError):
            print("Invalid follower selection!")
            return

        # Check if entity exists and is a follower
        if entity_id not in self.followers:
            print("Entity is not a follower!")
            return

        if entity_id not in self.entities:
            print("Entity no longer exists!")
            return

        entity = self.entities[entity_id]

        # Remove from followers list
        self.followers.remove(entity_id)

        # Remove from follower inventory
        self.inventory.remove_item(selected_follower, 1)

        # Remove enchantment
        if entity_id in self.enchanted_entities:
            magic_restored = self.enchanted_entities[entity_id]
            del self.enchanted_entities[entity_id]

            # Restore magic
            self.player['magic_pool'] = min(
                self.player['magic_pool'] + magic_restored,
                self.player['max_magic_pool']
            )

            print(f"Released {entity.type} follower! Restored {magic_restored} magic.")
        else:
            print(f"Released {entity.type} follower!")
