import random

from constants import (
    FACTION_COLORS, FACTION_SYMBOLS,
    HOSTILE_FACTION_COLORS, HOSTILE_FACTION_SYMBOLS,
    ENTITY_TYPES,
)


class FactionsMixin:
    """Handles faction creation, membership, promotion, and zone control."""

    # -------------------------------------------------------------------------
    # Name generation
    # -------------------------------------------------------------------------

    def generate_faction_name(self):
        """Generate a random unique faction name"""
        max_attempts = 50
        for _ in range(max_attempts):
            color = random.choice(FACTION_COLORS)
            symbol = random.choice(FACTION_SYMBOLS)
            name = f"{color} {symbol}"
            # Ensure this faction name doesn't already exist
            if name not in self.factions:
                return name
        # Fallback: just return a random name even if it exists (shouldn't happen with 100 combinations)
        return f"{random.choice(FACTION_COLORS)} {random.choice(FACTION_SYMBOLS)}"

    def generate_hostile_faction_name(self):
        """Generate a random unique hostile faction name"""
        max_attempts = 50
        for _ in range(max_attempts):
            color = random.choice(HOSTILE_FACTION_COLORS)
            symbol = random.choice(HOSTILE_FACTION_SYMBOLS)
            name = f"{color} {symbol}"
            # Ensure this faction name doesn't already exist
            if name not in self.factions:
                return name
        # Fallback
        return f"{random.choice(HOSTILE_FACTION_COLORS)} {random.choice(HOSTILE_FACTION_SYMBOLS)}"

    # -------------------------------------------------------------------------
    # Faction creation & assignment
    # -------------------------------------------------------------------------

    def create_hostile_faction(self, entity, screen_key):
        """Create new hostile faction and assign to entity"""
        new_faction = self.generate_hostile_faction_name()
        entity.faction = new_faction

        # Find entity_id
        entity_id = None
        for eid, ent in self.entities.items():
            if ent is entity:
                entity_id = eid
                break

        if entity_id:
            self.factions[new_faction] = {'warriors': [entity_id], 'zones': set(), 'hostile': True}
            print(f"{entity.name} formed the {new_faction} hostile faction!")

    def assign_warrior_faction(self, warrior, screen_key):
        """Assign faction to a new warrior based on zone warriors"""
        if screen_key not in self.screen_entities:
            return

        # Find entity_id for this warrior
        warrior_id = None
        for entity_id, entity in self.entities.items():
            if entity is warrior:
                warrior_id = entity_id
                break

        if not warrior_id:
            return

        # Find other warriors in zone with factions
        zone_factions = {}
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.type == 'WARRIOR' and entity.faction:
                    if entity.faction not in zone_factions:
                        zone_factions[entity.faction] = 0
                    zone_factions[entity.faction] += 1

        # If there are warriors with factions, try to join the majority faction
        if zone_factions:
            # Join the most common faction
            majority_faction = max(zone_factions, key=zone_factions.get)

            # Check if faction has room
            max_size = self.get_faction_max_size(majority_faction)
            current_size = len(self.factions.get(majority_faction, {}).get('warriors', []))

            if current_size < max_size:
                # Has room - join
                warrior.faction = majority_faction

                # Add to faction tracking
                if majority_faction not in self.factions:
                    self.factions[majority_faction] = {'warriors': [], 'zones': set()}

                if warrior_id not in self.factions[majority_faction]['warriors']:
                    self.factions[majority_faction]['warriors'].append(warrior_id)

                print(f"{warrior.name} joined {majority_faction} faction!")
                return
            else:
                # Check if this warrior is higher level than lowest member
                members = self.factions[majority_faction].get('warriors', [])
                lowest_level = float('inf')
                for member_id in members:
                    if member_id in self.entities:
                        member = self.entities[member_id]
                        if member.type not in ['KING', 'COMMANDER']:
                            lowest_level = min(lowest_level, member.level)

                if warrior.level > lowest_level:
                    # This warrior is higher level - join and expel lowest
                    warrior.faction = majority_faction
                    if majority_faction not in self.factions:
                        self.factions[majority_faction] = {'warriors': [], 'zones': set()}

                    self.factions[majority_faction]['warriors'].append(warrior_id)
                    self.enforce_faction_max_size(majority_faction)
                    print(f"{warrior.name} joined {majority_faction} faction!")
                    return
                else:
                    # Lower level than lowest - try to start own faction
                    if random.random() < 0.1:  # 10% chance
                        new_faction = self.generate_faction_name()
                        warrior.faction = new_faction
                        self.factions[new_faction] = {'warriors': [warrior_id], 'zones': set()}
                        print(f"{warrior.name} founded the {new_faction} faction!")
                    else:
                        # Become factionless
                        warrior.faction = None
                    return

        # If no factions in zone, check if any factions exist globally
        elif self.factions:
            # Try to join the largest existing faction globally
            largest_faction = max(self.factions.keys(), key=lambda f: len(self.factions[f]['warriors']))

            max_size = self.get_faction_max_size(largest_faction)
            current_size = len(self.factions[largest_faction].get('warriors', []))

            if current_size < max_size or warrior.level > 1:  # Higher level has better chance
                warrior.faction = largest_faction
                if warrior_id not in self.factions[largest_faction]['warriors']:
                    self.factions[largest_faction]['warriors'].append(warrior_id)
                    self.enforce_faction_max_size(largest_faction)

                print(f"{warrior.name} joined {largest_faction} faction (global recruitment)!")
            else:
                # Create new faction
                new_faction = self.generate_faction_name()
                warrior.faction = new_faction
                self.factions[new_faction] = {'warriors': [warrior_id], 'zones': set()}
                print(f"{warrior.name} founded the {new_faction} faction!")

        # If no factions exist at all, create first faction
        else:
            new_faction = self.generate_faction_name()
            warrior.faction = new_faction
            self.factions[new_faction] = {'warriors': [warrior_id], 'zones': set()}
            print(f"{warrior.name} founded the {new_faction} faction!")

    def recruit_to_hostile_faction(self, zone_key):
        """Non-humanoid hostiles can join factions (small chance)"""
        if zone_key not in self.screen_entities:
            return

        # Find hostile factions in zone
        hostile_factions = {}
        for entity_id in self.screen_entities[zone_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.props.get('hostile') and entity.faction:
                    if entity.faction not in hostile_factions:
                        hostile_factions[entity.faction] = []
                    hostile_factions[entity.faction].append(entity_id)

        if not hostile_factions:
            return

        # For each factionless hostile (WOLF, etc - not humanoids)
        for entity_id in self.screen_entities[zone_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if (entity.props.get('hostile') and not entity.faction and
                        entity.type not in ['BANDIT', 'GOBLIN', 'SKELETON']):
                    if random.random() < 0.05:  # 5% chance
                        # Join largest hostile faction in zone
                        faction = max(hostile_factions, key=lambda f: len(hostile_factions[f]))
                        entity.faction = faction
                        self.factions[faction]['warriors'].append(entity_id)
                        print(f"{entity.type} joined {faction}!")

    # -------------------------------------------------------------------------
    # Zone control & membership queries
    # -------------------------------------------------------------------------

    def get_zone_controlling_faction(self, screen_key):
        """Get the faction that controls a zone (majority of warriors/hostiles)"""
        if screen_key not in self.screen_entities:
            return None

        faction_counts = {}
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                # Count warriors, commanders, kings AND hostile faction members
                if entity.faction:
                    if entity.type in ['WARRIOR', 'COMMANDER', 'KING']:
                        if entity.faction not in faction_counts:
                            faction_counts[entity.faction] = 0
                        faction_counts[entity.faction] += 1
                    # Hostile entities with factions also count for control
                    elif entity.props.get('hostile') and entity.faction:
                        if entity.faction not in faction_counts:
                            faction_counts[entity.faction] = 0
                        faction_counts[entity.faction] += 1

        if not faction_counts:
            return None

        # Return faction with most members (simple majority)
        return max(faction_counts, key=faction_counts.get)

    def get_faction_leader(self, faction_name):
        """Get the leader (KING or highest COMMANDER) of a faction"""
        if faction_name not in self.factions:
            return None, None

        leader = None
        leader_id = None
        best_priority = 0  # KING=3, COMMANDER=2, WARRIOR=1
        best_level = 0

        for entity_id in self.factions[faction_name].get('warriors', []):
            if entity_id not in self.entities:
                continue

            entity = self.entities[entity_id]
            priority = 0

            if entity.type == 'KING':
                priority = 3
            elif entity.type == 'COMMANDER':
                priority = 2
            elif entity.type == 'WARRIOR':
                priority = 1

            # Higher priority or same priority but higher level
            if priority > best_priority or (priority == best_priority and entity.level > best_level):
                leader = entity
                leader_id = entity_id
                best_priority = priority
                best_level = entity.level

        return leader, leader_id

    def get_faction_max_size(self, faction_name):
        """Calculate max faction size: 3 + leader_level"""
        leader, _ = self.get_faction_leader(faction_name)
        if not leader:
            return 3  # Default if no leader
        return 3 + leader.level

    def enforce_faction_max_size(self, faction_name):
        """Remove lowest level member if faction exceeds max size"""
        if faction_name not in self.factions:
            return

        max_size = self.get_faction_max_size(faction_name)
        current_members = self.factions[faction_name].get('warriors', [])

        # Remove invalid entity IDs
        current_members = [eid for eid in current_members if eid in self.entities]
        self.factions[faction_name]['warriors'] = current_members

        if len(current_members) <= max_size:
            return  # Within limits

        # Find lowest level member
        lowest_member = None
        lowest_member_id = None
        lowest_level = float('inf')

        for entity_id in current_members:
            entity = self.entities[entity_id]
            # Don't expel leaders
            if entity.type in ['KING', 'COMMANDER']:
                continue

            if entity.level < lowest_level:
                lowest_member = entity
                lowest_member_id = entity_id
                lowest_level = entity.level

        if lowest_member:
            # Expel from faction
            self.factions[faction_name]['warriors'].remove(lowest_member_id)
            old_faction = lowest_member.faction

            # Try to join nearest faction
            screen_key = f"{lowest_member.screen_x},{lowest_member.screen_y}"
            self.try_join_nearest_faction(lowest_member, lowest_member_id, screen_key, exclude_faction=old_faction)

            if lowest_member.faction != old_faction:
                print(f"{lowest_member.name} was expelled from {old_faction} and joined {lowest_member.faction}!")
            else:
                # Failed to join another faction
                lowest_member.faction = None
                print(f"{lowest_member.name} was expelled from {old_faction} and became factionless!")

    def try_join_nearest_faction(self, entity, entity_id, screen_key, exclude_faction=None):
        """Try to join nearest faction, create new faction on failure"""
        # Find nearby factions (within 2 zones)
        nearby_factions = {}

        for dx in range(-2, 3):
            for dy in range(-2, 3):
                check_key = f"{entity.screen_x + dx},{entity.screen_y + dy}"
                if check_key not in self.screen_entities:
                    continue

                for other_id in self.screen_entities[check_key]:
                    if other_id not in self.entities or other_id == entity_id:
                        continue

                    other = self.entities[other_id]
                    if other.type in ['WARRIOR', 'COMMANDER', 'KING'] and other.faction:
                        if exclude_faction and other.faction == exclude_faction:
                            continue

                        if other.faction not in nearby_factions:
                            nearby_factions[other.faction] = 0
                        nearby_factions[other.faction] += 1

        # Try to join nearest faction
        if nearby_factions:
            best_faction = max(nearby_factions, key=nearby_factions.get)

            # Safety check - faction must still exist
            if best_faction not in self.factions:
                return False

            # Check if faction has room
            max_size = self.get_faction_max_size(best_faction)
            current_size = len(self.factions[best_faction].get('warriors', []))

            if current_size < max_size:
                # Join faction
                entity.faction = best_faction
                self.factions[best_faction]['warriors'].append(entity_id)
                return True
            else:
                # Check if this entity is higher level than lowest member
                members = self.factions[best_faction].get('warriors', [])
                lowest_level = float('inf')
                for member_id in members:
                    if member_id in self.entities:
                        member = self.entities[member_id]
                        if member.type not in ['KING', 'COMMANDER']:
                            lowest_level = min(lowest_level, member.level)

                if entity.level > lowest_level:
                    # This entity is higher level, join and expel lowest
                    entity.faction = best_faction
                    self.factions[best_faction]['warriors'].append(entity_id)
                    self.enforce_faction_max_size(best_faction)
                    return True

        # Failed to join nearby faction - small chance to create new faction
        if random.random() < 0.1:  # 10% chance
            new_faction = self.generate_faction_name()
            entity.faction = new_faction
            self.factions[new_faction] = {'warriors': [entity_id], 'zones': set()}
            print(f"{entity.name} founded the {new_faction} faction!")
            return True

        return False

    def get_faction_exploration_target(self, screen_key, faction):
        """Get target zone for faction to explore/expand into"""
        # Parse current position
        current_x, current_y = map(int, screen_key.split(','))

        # Check adjacent zones (4 directions)
        adjacent_zones = [
            (current_x, current_y - 1, 'top'),
            (current_x, current_y + 1, 'bottom'),
            (current_x - 1, current_y, 'left'),
            (current_x + 1, current_y, 'right')
        ]

        # Find zones not controlled by this faction
        expansion_targets = []
        for zone_x, zone_y, direction in adjacent_zones:
            target_key = f"{zone_x},{zone_y}"
            controlling_faction = self.get_zone_controlling_faction(target_key)

            # Target zones that aren't controlled by us
            if controlling_faction != faction:
                expansion_targets.append((zone_x, zone_y, direction))

        # If we have expansion targets, pick one consistently (use hash of faction name for determinism)
        if expansion_targets:
            # Use faction name hash to pick same target for all warriors of this faction
            faction_hash = sum(ord(c) for c in faction)
            target_index = faction_hash % len(expansion_targets)
            return expansion_targets[target_index]

        return None

    # -------------------------------------------------------------------------
    # Promotion
    # -------------------------------------------------------------------------

    def promote_to_commander(self, screen_key):
        """Promote highest level warrior in zone to commander (requires 2+ warriors)"""
        if screen_key not in self.screen_entities:
            return

        # Count warriors by faction in this zone
        faction_warriors = {}
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.type == 'WARRIOR' and entity.faction:
                    if entity.faction not in faction_warriors:
                        faction_warriors[entity.faction] = []
                    faction_warriors[entity.faction].append((entity_id, entity))

        # For each faction with 2+ warriors, promote highest level
        for faction, warriors in faction_warriors.items():
            if len(warriors) >= 2:
                # Find highest level warrior
                best_warrior = None
                best_warrior_id = None
                best_level = 0

                for warrior_id, warrior in warriors:
                    if warrior.level > best_level:
                        best_warrior = warrior
                        best_warrior_id = warrior_id
                        best_level = warrior.level

                if best_warrior and random.random() < 0.5:  # 50% chance to promote
                    old_name = best_warrior.name

                    # Promote to commander
                    best_warrior.type = 'COMMANDER'
                    best_warrior.props = ENTITY_TYPES['COMMANDER']
                    best_warrior.max_health = best_warrior.props['max_health'] * best_warrior.level
                    best_warrior.strength = best_warrior.props['strength'] * best_warrior.level

                    # Full restore
                    best_warrior.health = best_warrior.max_health
                    best_warrior.hunger = best_warrior.max_hunger
                    best_warrior.thirst = best_warrior.max_thirst

                    # Commanders stay in their zone (like guards)
                    best_warrior.home_zone = screen_key

                    print(f"{old_name} promoted to COMMANDER of {faction} in [{screen_key}]!")

    def promote_to_king(self):
        """Promote highest level commander to king if faction controls 4+ zones"""
        for faction, faction_data in self.factions.items():
            # Count zones controlled by this faction
            controlled_zones = 0
            for zone_key in self.instantiated_zones:
                if self.get_zone_controlling_faction(zone_key) == faction:
                    controlled_zones += 1

            # If faction controls 4+ zones, can have a king
            if controlled_zones >= 4:
                # Find highest level commander in this faction
                best_commander = None
                best_commander_id = None
                best_level = 0

                for entity_id in faction_data.get('warriors', []):
                    if entity_id in self.entities:
                        entity = self.entities[entity_id]
                        if entity.type == 'COMMANDER' and entity.level > best_level:
                            best_commander = entity
                            best_commander_id = entity_id
                            best_level = entity.level

                # Check if faction already has a king
                has_king = any(
                    self.entities[eid].type == 'KING'
                    for eid in faction_data.get('warriors', [])
                    if eid in self.entities
                )

                if best_commander and not has_king:
                    old_name = best_commander.name

                    # Promote to king
                    best_commander.type = 'KING'
                    best_commander.props = ENTITY_TYPES['KING']
                    best_commander.max_health = best_commander.props['max_health'] * best_commander.level
                    best_commander.strength = best_commander.props['strength'] * best_commander.level

                    # Full restore
                    best_commander.health = best_commander.max_health
                    best_commander.hunger = best_commander.max_hunger
                    best_commander.thirst = best_commander.max_thirst

                    print(f"{old_name} crowned KING of {faction}! ({controlled_zones} zones controlled)")
