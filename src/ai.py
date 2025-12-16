"""
AI Bot opponent for single player mode.
"""

import math
import random
from typing import List, Optional, Tuple, TYPE_CHECKING

from .constants import (
    UnitType, BuildingType, Team,
    UNIT_COSTS, BUILDING_COSTS, MAP_WIDTH, MAP_HEIGHT,
    Difficulty, DIFFICULTY_SETTINGS
)
from .entities import Unit, Building, Resources

if TYPE_CHECKING:
    from .game import Game


class AIBot:
    """AI opponent for single player mode."""

    def __init__(self, game: 'Game', difficulty: Difficulty = Difficulty.NORMAL):
        """
        Initialize AI bot.

        Args:
            game: Reference to main game instance
            difficulty: AI difficulty level
        """
        self.game = game
        self.difficulty = difficulty
        self.settings = DIFFICULTY_SETTINGS[difficulty]

        # Timing
        self.think_timer = 0
        self.think_interval = 2.0  # Base think interval in seconds

        # AI state
        self.state = 'building'  # building, attacking, defending
        self.aggression = self.settings['aggression']
        self.attack_target: Optional[Tuple[float, float]] = None

        # Resource bonus timer
        self.resource_bonus_timer = 0

        # Queues
        self.build_queue: List[BuildingType] = []
        self.unit_queue: List[UnitType] = []

        # Defense line positions for military units (calculated once castle is known)
        self.defense_positions: List[Tuple[float, float]] = []

    @property
    def resources(self) -> Resources:
        """Get AI resources."""
        return self.game.enemy_resources

    @property
    def my_units(self) -> List[Unit]:
        """Get all AI-controlled units."""
        return [u for u in self.game.units if u.team == Team.ENEMY]

    @property
    def my_buildings(self) -> List[Building]:
        """Get all AI-controlled buildings."""
        return [b for b in self.game.buildings if b.team == Team.ENEMY]

    @property
    def enemy_units(self) -> List[Unit]:
        """Get all player units."""
        return [u for u in self.game.units if u.team == Team.PLAYER]

    @property
    def enemy_buildings(self) -> List[Building]:
        """Get all player buildings."""
        return [b for b in self.game.buildings if b.team == Team.PLAYER]

    @property
    def my_castle(self) -> Optional[Building]:
        """Get AI's castle."""
        return next(
            (b for b in self.my_buildings if b.building_type == BuildingType.CASTLE),
            None
        )

    @property
    def military_units(self) -> List[Unit]:
        """Get AI's military (non-peasant) units."""
        return [u for u in self.my_units if u.unit_type != UnitType.PEASANT]

    @property
    def my_peasants(self) -> List[Unit]:
        """Get AI's peasant units."""
        return [u for u in self.my_units if u.unit_type == UnitType.PEASANT]

    @property
    def idle_peasants(self) -> List[Unit]:
        """Get peasants not assigned to buildings."""
        return [u for u in self.my_peasants if not u.assigned_building]

    def _are_all_buildings_staffed(self) -> bool:
        """Check if all buildings have their maximum workers assigned."""
        for building in self.my_buildings:
            max_workers = building.get_max_workers()
            if max_workers > 0:  # Only check buildings that can have workers
                current_workers = building.count_workers(self.game.units)
                if current_workers < max_workers:
                    return False
        return True

    def _calculate_defense_positions(self) -> List[Tuple[float, float]]:
        """Calculate defensive line positions in front of the castle (towards player base)."""
        castle = self.my_castle
        if not castle:
            return []

        positions = []
        # AI castle is in top-right, player is in bottom-left
        # Defense line should be south-west of castle
        defense_distance = 200  # Distance from castle to defense line
        line_spacing = 80  # Space between units in the line

        # Calculate direction towards player (south-west)
        # Castle is at top-right, so defense line points towards bottom-left
        center_x = castle.x - defense_distance * 0.7  # Move towards left
        center_y = castle.y + defense_distance * 0.7  # Move towards bottom

        # Create a line of positions perpendicular to the attack direction
        num_positions = 8  # Support up to 8 units in the defense line
        for i in range(num_positions):
            offset = (i - num_positions // 2) * line_spacing
            # Line runs from top-left to bottom-right (perpendicular to SW direction)
            pos_x = center_x + offset * 0.7
            pos_y = center_y + offset * 0.7
            # Clamp to map bounds
            pos_x = max(100, min(MAP_WIDTH - 100, pos_x))
            pos_y = max(100, min(MAP_HEIGHT - 100, pos_y))
            positions.append((pos_x, pos_y))

        return positions

    def update(self, dt: float):
        """Update AI logic."""
        self.think_timer += dt

        # Think at intervals adjusted by difficulty
        think_speed = self.settings['think_speed']
        effective_interval = self.think_interval / think_speed
        if self.think_timer >= effective_interval:
            self.think_timer = 0
            self.think()

        # Apply resource bonus for harder difficulties
        self._apply_resource_bonus(dt)

        # Always execute current orders
        self.execute_orders(dt)

    def _apply_resource_bonus(self, dt: float):
        """Apply resource bonus based on difficulty."""
        self.resource_bonus_timer += dt
        if self.resource_bonus_timer >= 10.0:  # Every 10 seconds
            self.resource_bonus_timer = 0
            bonus = self.settings['resource_bonus']
            if bonus > 1.0:
                # Give bonus resources on harder difficulties
                extra = int((bonus - 1.0) * 50)
                self.resources.gold += extra
                self.resources.food += extra // 2

    def think(self):
        """Main AI decision making."""
        # Assess situation
        self._assess_threats()

        # Assign idle peasants to buildings
        self._assign_workers()

        # Economic decisions
        self._economic_decisions()

        # Military decisions
        self._military_decisions()

    def _assess_threats(self):
        """Assess threats to AI base."""
        castle = self.my_castle
        if not castle:
            return

        # Check for nearby enemies
        nearby_enemies = [
            u for u in self.enemy_units
            if u.distance_to(castle.x, castle.y) < 300
        ]

        if len(nearby_enemies) >= 2:
            self.state = 'defending'
            self.attack_target = (castle.x, castle.y)
        elif len(self.military_units) >= int(4 * self.aggression + 2) and self.state != 'defending':
            self.state = 'attacking'

    def _assign_workers(self):
        """Assign idle peasants to buildings that need workers."""
        idle = list(self.idle_peasants)  # Make a copy

        if not idle:
            return

        # Prioritize farms first (for food), then other buildings
        buildings_by_priority = sorted(
            self.my_buildings,
            key=lambda b: 0 if b.building_type == BuildingType.FARM else 1
        )

        # Find buildings that need workers
        for building in buildings_by_priority:
            if not idle:
                break

            max_workers = building.get_max_workers()
            current_workers = building.count_workers(self.game.units)

            while current_workers < max_workers and idle:
                # Assign an idle peasant
                peasant = idle.pop(0)
                peasant.assign_to_building(building)
                current_workers += 1

    def _economic_decisions(self):
        """Make economic decisions."""
        # Count buildings by type
        farms = len([b for b in self.my_buildings if b.building_type == BuildingType.FARM])
        houses = len([b for b in self.my_buildings if b.building_type == BuildingType.HOUSE])
        peasants = len(self.my_peasants)

        # Calculate total worker slots needed
        total_slots = sum(b.get_max_workers() for b in self.my_buildings)

        # Max buildings based on difficulty
        max_farms = 3 + int(self.aggression * 2)
        max_houses = 2 + int(self.aggression * 2)

        # For Normal+ difficulties, only build new buildings if all current ones are fully staffed
        # Easy mode (aggression ~0.3) can build freely
        can_build_new = self.difficulty == Difficulty.EASY or self._are_all_buildings_staffed()

        # Build farms first if low on food (priority)
        if self.resources.food < 150 and farms < max_farms and can_build_new:
            self._try_build_building(BuildingType.FARM)

        # Build houses for gold generation
        if houses < max_houses and self.resources.gold >= 100 and can_build_new:
            self._try_build_building(BuildingType.HOUSE)

        # Train peasants if we have building slots to fill
        max_peasants = 6 + int(self.aggression * 4)
        if peasants < total_slots + 1 and peasants < max_peasants:
            self._try_train_unit(UnitType.PEASANT)
        # Always have at least some peasants
        elif peasants < 3:
            self._try_train_unit(UnitType.PEASANT)

    def _military_decisions(self):
        """Make military decisions."""
        military_count = len(self.military_units)
        military_cap = self.settings['military_cap']

        # Build military based on resources and current army size
        if military_count < military_cap:
            # More aggressive AIs build more cavalry
            if self.resources.gold >= 200 and random.random() < self.aggression:
                self._try_train_unit(UnitType.CAVALRY)
            elif self.resources.gold >= 150:
                self._try_train_unit(UnitType.KNIGHT)

        # Add cannons occasionally (more on harder difficulties)
        cannons = len([u for u in self.my_units if u.unit_type == UnitType.CANNON])
        max_cannons = 1 + int(self.aggression * 3)
        if military_count >= 4 and cannons < max_cannons and random.random() < self.aggression * 0.3:
            self._try_train_unit(UnitType.CANNON)

        # Attack decision - more aggressive on harder difficulties
        attack_threshold = max(3, int(5 - self.aggression * 3))
        if military_count >= attack_threshold and self.state != 'defending':
            self.state = 'attacking'
            self._choose_attack_target()

    def _choose_attack_target(self):
        """Choose a target to attack."""
        # Prioritize buildings
        if self.enemy_buildings:
            # More aggressive AIs go for castle earlier
            if self.aggression > 0.7 and random.random() < 0.3:
                castles = [b for b in self.enemy_buildings if b.building_type == BuildingType.CASTLE]
                if castles:
                    target = castles[0]
                    self.attack_target = (target.x, target.y)
                    return

            # Prefer non-castle buildings first
            non_castles = [
                b for b in self.enemy_buildings
                if b.building_type != BuildingType.CASTLE
            ]
            target = random.choice(non_castles if non_castles else self.enemy_buildings)
            self.attack_target = (target.x, target.y)
        elif self.enemy_units:
            target = random.choice(self.enemy_units)
            self.attack_target = (target.x, target.y)

    def _try_build_building(self, building_type: BuildingType):
        """Attempt to build a building."""
        cost_key = building_type.name.lower()
        cost = BUILDING_COSTS.get(cost_key, {'gold': 100, 'wood': 50})

        if not self.resources.can_afford(cost):
            return

        castle = self.my_castle
        if not castle:
            return

        # Find a spot near castle
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(150, 300)
        x = castle.x + math.cos(angle) * dist
        y = castle.y + math.sin(angle) * dist

        # Clamp to map bounds
        x = max(100, min(MAP_WIDTH - 100, x))
        y = max(100, min(MAP_HEIGHT - 100, y))

        # Spend resources and create building
        self.resources.spend(cost)
        building = Building(x, y, building_type, Team.ENEMY)
        building.uid = self.game.next_uid()
        self.game.buildings.append(building)

    def _try_train_unit(self, unit_type: UnitType):
        """Attempt to train a unit."""
        cost_key = unit_type.name.lower()
        cost = UNIT_COSTS.get(cost_key, {'gold': 50, 'food': 25})

        if not self.resources.can_afford(cost):
            return

        castle = self.my_castle
        if not castle:
            return

        # Spawn near castle
        angle = random.uniform(0, 2 * math.pi)
        x = castle.x + math.cos(angle) * 80
        y = castle.y + math.sin(angle) * 80

        # Spend resources and create unit
        self.resources.spend(cost)
        unit = Unit(x, y, unit_type, Team.ENEMY)
        unit.uid = self.game.next_uid()
        self.game.units.append(unit)

    def execute_orders(self, dt: float):
        """Execute current orders for AI units."""
        if self.state == 'attacking' and self.attack_target:
            self._execute_attack_orders()
        elif self.state == 'defending':
            self._execute_defend_orders()
        elif self.state == 'building' and self.difficulty != Difficulty.EASY:
            # For Normal+ difficulties, maintain defensive line while building up
            self._execute_defense_line()

    def _execute_attack_orders(self):
        """Execute attack orders for military units."""
        for unit in self.military_units:
            # Skip if already has a valid target
            if unit.target_unit and unit.target_unit.is_alive():
                continue
            if unit.target_building and not unit.target_building.is_destroyed():
                continue

            # Find nearest enemy unit
            nearest_enemy = self._find_nearest_enemy(unit)

            if nearest_enemy and unit.distance_to_unit(nearest_enemy) < 200:
                unit.set_attack_target(nearest_enemy)
            elif self.attack_target:
                # Check if we should attack a building at target location
                target_building = self._find_building_at(self.attack_target)
                if target_building:
                    unit.set_building_target(target_building)
                else:
                    unit.set_move_target(*self.attack_target)

    def _find_building_at(self, pos: Tuple[float, float]) -> Optional[Building]:
        """Find an enemy building near the given position."""
        for building in self.enemy_buildings:
            dist = math.sqrt((building.x - pos[0])**2 + (building.y - pos[1])**2)
            if dist < 100:
                return building
        return None

    def _execute_defend_orders(self):
        """Execute defense orders."""
        castle = self.my_castle
        if not castle:
            return

        for unit in self.military_units:
            # Find enemies near castle
            enemies_near_castle = [
                e for e in self.enemy_units
                if e.distance_to(castle.x, castle.y) < 400
            ]

            if enemies_near_castle:
                # Attack nearest enemy to castle
                nearest = min(
                    enemies_near_castle,
                    key=lambda e: e.distance_to(castle.x, castle.y)
                )
                unit.set_attack_target(nearest)
            else:
                # Return to defensive position
                self.state = 'building'

    def _execute_defense_line(self):
        """Position military units in a defensive line in front of castle (Normal+ only)."""
        castle = self.my_castle
        if not castle:
            return

        # Calculate defense positions if not already done
        if not self.defense_positions:
            self.defense_positions = self._calculate_defense_positions()

        military = self.military_units
        if not military:
            return

        # Check for nearby enemies first - if enemies approach, engage them
        for unit in military:
            # Skip if already engaged with a target
            if unit.target_unit and unit.target_unit.is_alive():
                continue

            # Look for enemies within engagement range of the defense line
            enemies_nearby = [
                e for e in self.enemy_units
                if unit.distance_to_unit(e) < 250  # Engage enemies that get close
            ]

            if enemies_nearby:
                # Attack the nearest enemy
                nearest = min(enemies_nearby, key=lambda e: unit.distance_to_unit(e))
                unit.set_attack_target(nearest)
            else:
                # No enemies nearby - hold position in defense line
                # Assign each unit to a position in the line
                unit_index = military.index(unit) % len(self.defense_positions)
                target_pos = self.defense_positions[unit_index]

                # Only move if not already at position (with some tolerance)
                dist_to_pos = unit.distance_to(target_pos[0], target_pos[1])
                if dist_to_pos > 30:
                    # Move to defensive position
                    unit.set_move_target(target_pos[0], target_pos[1])

    def _find_nearest_enemy(self, unit: Unit) -> Optional[Unit]:
        """Find the nearest enemy unit to the given unit."""
        if not self.enemy_units:
            return None

        return min(
            self.enemy_units,
            key=lambda e: unit.distance_to_unit(e)
        )
