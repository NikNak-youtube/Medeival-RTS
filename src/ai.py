"""
AI Bot opponent for single player mode.
"""

import math
import random
from typing import List, Optional, Tuple, TYPE_CHECKING

from .constants import (
    UnitType, BuildingType, Team,
    UNIT_COSTS, BUILDING_COSTS, MAP_WIDTH, MAP_HEIGHT,
    WORKER_RANGE
)
from .entities import Unit, Building, Resources

if TYPE_CHECKING:
    from .game import Game


class AIBot:
    """AI opponent for single player mode."""

    def __init__(self, game: 'Game', difficulty: float = 1.0):
        """
        Initialize AI bot.

        Args:
            game: Reference to main game instance
            difficulty: AI difficulty multiplier (0.5=easy, 1.0=normal, 1.5=hard)
        """
        self.game = game
        self.difficulty = difficulty

        # Timing
        self.think_timer = 0
        self.think_interval = 2.0  # Base think interval in seconds

        # AI state
        self.state = 'building'  # building, attacking, defending
        self.aggression = 0.5
        self.attack_target: Optional[Tuple[float, float]] = None

        # Queues
        self.build_queue: List[BuildingType] = []
        self.unit_queue: List[UnitType] = []

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

    def update(self, dt: float):
        """Update AI logic."""
        self.think_timer += dt

        # Think at intervals adjusted by difficulty
        effective_interval = self.think_interval / self.difficulty
        if self.think_timer >= effective_interval:
            self.think_timer = 0
            self.think()

        # Always execute current orders
        self.execute_orders(dt)

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
        elif len(self.military_units) >= 5 and self.state != 'defending':
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
        idle_peasants = len(self.idle_peasants)

        # Calculate total worker slots needed
        total_slots = sum(b.get_max_workers() for b in self.my_buildings)

        # Build farms first if low on food (priority)
        if self.resources.food < 150 and farms < 4:
            self._try_build_building(BuildingType.FARM)

        # Build houses for gold generation
        if houses < 3 and self.resources.gold >= 100:
            self._try_build_building(BuildingType.HOUSE)

        # Train peasants if we have building slots to fill
        if peasants < total_slots + 1 and peasants < 8:
            self._try_train_unit(UnitType.PEASANT)
        # Always have at least some peasants
        elif peasants < 3:
            self._try_train_unit(UnitType.PEASANT)

    def _military_decisions(self):
        """Make military decisions."""
        military_count = len(self.military_units)

        # Build military based on resources and current army size
        if military_count < 8:
            if self.resources.gold >= 200 and random.random() < 0.4:
                self._try_train_unit(UnitType.CAVALRY)
            elif self.resources.gold >= 150:
                self._try_train_unit(UnitType.KNIGHT)

        # Add cannons occasionally
        cannons = len([u for u in self.my_units if u.unit_type == UnitType.CANNON])
        if military_count >= 4 and cannons < 2 and random.random() < 0.2:
            self._try_train_unit(UnitType.CANNON)

        # Attack decision
        if military_count >= 5 and self.state != 'defending':
            self.state = 'attacking'
            self._choose_attack_target()

    def _choose_attack_target(self):
        """Choose a target to attack."""
        # Prioritize buildings
        if self.enemy_buildings:
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

    def _find_nearest_enemy(self, unit: Unit) -> Optional[Unit]:
        """Find the nearest enemy unit to the given unit."""
        if not self.enemy_units:
            return None

        return min(
            self.enemy_units,
            key=lambda e: unit.distance_to_unit(e)
        )
