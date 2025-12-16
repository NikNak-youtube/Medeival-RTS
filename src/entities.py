"""
Game entities: Units, Buildings, Resources, and Effects.
"""

import math
import pygame
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

from .constants import (
    UnitType, BuildingType, Team, MAP_WIDTH, MAP_HEIGHT,
    UNIT_STATS, BUILDING_STATS, STARTING_GOLD, STARTING_FOOD, STARTING_WOOD,
    WORKER_RANGE, BUILDING_RESOURCE_GENERATION
)
from typing import List

if TYPE_CHECKING:
    from .assets import ModManager


# =============================================================================
# RESOURCES
# =============================================================================

@dataclass
class Resources:
    """Player resources."""
    gold: int = STARTING_GOLD
    food: int = STARTING_FOOD
    wood: int = STARTING_WOOD

    def can_afford(self, costs: dict) -> bool:
        """Check if player can afford a cost."""
        return (self.gold >= costs.get('gold', 0) and
                self.food >= costs.get('food', 0) and
                self.wood >= costs.get('wood', 0))

    def spend(self, costs: dict) -> bool:
        """Spend resources if affordable. Returns True if successful."""
        if not self.can_afford(costs):
            return False
        self.gold -= costs.get('gold', 0)
        self.food -= costs.get('food', 0)
        self.wood -= costs.get('wood', 0)
        return True

    def add(self, gold: int = 0, food: int = 0, wood: int = 0):
        """Add resources."""
        self.gold += gold
        self.food += food
        self.wood += wood


# =============================================================================
# UNIT
# =============================================================================

@dataclass
class Unit:
    """Represents a game unit."""
    x: float
    y: float
    unit_type: UnitType
    team: Team
    uid: int = 0

    # Stats (set in __post_init__)
    health: int = 100
    max_health: int = 100
    attack: int = 10
    defense: int = 5
    speed: float = 2.0
    attack_range: int = 30
    attack_cooldown: float = 1.0

    # State
    last_attack: float = 0
    selected: bool = False
    target_x: Optional[float] = None
    target_y: Optional[float] = None
    target_unit: Optional['Unit'] = None
    target_building: Optional['Building'] = None

    # Attack-move state
    attack_move_target: Optional[Tuple[float, float]] = None

    # Worker assignment (for peasants)
    assigned_building: Optional['Building'] = field(default=None, repr=False)
    is_working: bool = False

    # Building assignment (for peasants constructing)
    constructing_building: Optional['Building'] = field(default=None, repr=False)

    # Reference to mod manager for stat lookups
    _mod_manager: Optional['ModManager'] = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize unit stats based on type."""
        self._apply_stats()

    def _apply_stats(self):
        """Apply stats from constants or mod overrides."""
        # Map UnitType enum to string key
        type_key = self.unit_type.name.lower()

        if self._mod_manager:
            stats = self._mod_manager.get_unit_stats(type_key)
        else:
            stats = UNIT_STATS.get(type_key, UNIT_STATS['peasant'])

        self.health = stats.get('health', 100)
        self.max_health = stats.get('health', 100)
        self.attack = stats.get('attack', 10)
        self.defense = stats.get('defense', 5)
        self.speed = stats.get('speed', 2.0)
        self.attack_range = stats.get('range', 30)
        self.attack_cooldown = stats.get('cooldown', 1.0)

    def get_rect(self) -> pygame.Rect:
        """Get unit collision rectangle."""
        size = 48 if self.unit_type == UnitType.CAVALRY else 40
        return pygame.Rect(self.x - size // 2, self.y - size // 2, size, size)

    def get_size(self) -> int:
        """Get unit visual size."""
        return 48 if self.unit_type == UnitType.CAVALRY else 40

    def get_collision_radius(self) -> float:
        """Get unit collision radius for soft collisions."""
        if self.unit_type == UnitType.CAVALRY:
            return 20.0
        elif self.unit_type == UnitType.CANNON:
            return 18.0
        elif self.unit_type == UnitType.KNIGHT:
            return 16.0
        else:  # Peasant
            return 14.0

    def distance_to(self, other_x: float, other_y: float) -> float:
        """Calculate distance to a point."""
        return math.sqrt((self.x - other_x) ** 2 + (self.y - other_y) ** 2)

    def distance_to_unit(self, other: 'Unit') -> float:
        """Calculate distance to another unit."""
        return self.distance_to(other.x, other.y)

    def distance_to_building(self, building: 'Building') -> float:
        """Calculate distance to a building."""
        return self.distance_to(building.x, building.y)

    def move_towards(self, target_x: float, target_y: float, dt: float, speed_multiplier: float = 1.0):
        """Move towards a target position.

        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            dt: Delta time
            speed_multiplier: Speed multiplier (e.g., 0.6 for 40% slowdown)
        """
        dist = self.distance_to(target_x, target_y)
        if dist > 5:
            dx = (target_x - self.x) / dist
            dy = (target_y - self.y) / dist
            effective_speed = self.speed * speed_multiplier
            self.x += dx * effective_speed * dt * 60
            self.y += dy * effective_speed * dt * 60
            # Clamp to map bounds
            self.x = max(20, min(MAP_WIDTH - 20, self.x))
            self.y = max(20, min(MAP_HEIGHT - 20, self.y))
        else:
            self.target_x = None
            self.target_y = None

    def set_move_target(self, x: float, y: float):
        """Set a movement target."""
        self.target_x = x
        self.target_y = y
        self.target_unit = None
        self.target_building = None

    def set_attack_target(self, target: 'Unit'):
        """Set a unit attack target."""
        self.target_unit = target
        self.target_building = None
        self.target_x = target.x
        self.target_y = target.y

    def set_building_target(self, building: 'Building'):
        """Set a building attack target."""
        self.target_building = building
        self.target_unit = None
        self.target_x = building.x
        self.target_y = building.y

    def clear_targets(self):
        """Clear all targets."""
        self.target_x = None
        self.target_y = None
        self.target_unit = None
        self.target_building = None
        self.attack_move_target = None

    def set_attack_move_target(self, x: float, y: float):
        """Set attack-move target - will attack enemies encountered while moving."""
        self.attack_move_target = (x, y)
        self.target_x = x
        self.target_y = y
        self.target_unit = None
        self.target_building = None

    def assign_to_building(self, building: 'Building'):
        """Assign this peasant to work at a building."""
        if self.unit_type != UnitType.PEASANT:
            return
        self.assigned_building = building
        self.is_working = False
        # Move to the building
        self.set_move_target(building.x, building.y)

    def unassign_from_building(self):
        """Remove this peasant from building assignment."""
        self.assigned_building = None
        self.is_working = False

    def update_work_status(self):
        """Update whether this peasant is actively working."""
        if self.unit_type != UnitType.PEASANT or not self.assigned_building:
            self.is_working = False
            return

        # Check if close enough to work
        dist = self.distance_to_building(self.assigned_building)
        self.is_working = dist <= WORKER_RANGE

        # If not working and not moving, move back to building
        if not self.is_working and self.target_x is None:
            self.set_move_target(self.assigned_building.x, self.assigned_building.y)

    def take_damage(self, damage: int) -> bool:
        """Take damage. Returns True if unit dies."""
        self.health -= damage
        return self.health <= 0

    def heal(self, amount: int) -> bool:
        """Heal the unit. Returns True if any healing was done."""
        if self.health >= self.max_health:
            return False
        self.health = min(self.max_health, self.health + amount)
        return True

    def needs_healing(self) -> bool:
        """Check if unit needs healing."""
        return self.health < self.max_health

    def is_alive(self) -> bool:
        """Check if unit is alive."""
        return self.health > 0

    def is_enemy_of(self, other_team: Team) -> bool:
        """Check if this unit is an enemy of the given team."""
        return self.team != other_team

    def to_dict(self) -> dict:
        """Serialize unit to dictionary for networking."""
        return {
            'uid': self.uid,
            'x': self.x,
            'y': self.y,
            'type': self.unit_type.name,
            'team': self.team.name,
            'health': self.health,
            'max_health': self.max_health
        }

    @classmethod
    def from_dict(cls, data: dict, mod_manager: Optional['ModManager'] = None) -> 'Unit':
        """Create unit from dictionary."""
        unit = cls(
            x=data['x'],
            y=data['y'],
            unit_type=UnitType[data['type']],
            team=Team[data['team']],
            uid=data['uid'],
            _mod_manager=mod_manager
        )
        unit.health = data.get('health', unit.max_health)
        return unit


# =============================================================================
# BUILDING
# =============================================================================

@dataclass
class Building:
    """Represents a game building."""
    x: float
    y: float
    building_type: BuildingType
    team: Team
    uid: int = 0

    # Stats
    health: int = 500
    max_health: int = 500

    # State
    selected: bool = False
    completed: bool = True
    build_progress: float = 100.0

    # Tower attack state
    last_attack: float = 0

    # Reference to mod manager
    _mod_manager: Optional['ModManager'] = field(default=None, repr=False)

    def get_max_workers(self) -> int:
        """Get maximum number of workers this building can have."""
        type_key = self.building_type.name.lower()
        gen_data = BUILDING_RESOURCE_GENERATION.get(type_key, {})
        return gen_data.get('max_workers', 1)

    def count_workers(self, units: List['Unit']) -> int:
        """Count how many peasants are working at this building."""
        count = 0
        for unit in units:
            if (unit.unit_type == UnitType.PEASANT and
                unit.team == self.team and
                unit.assigned_building == self and
                unit.is_working):
                count += 1
        return count

    def get_production_multiplier(self, units: List['Unit']) -> float:
        """Get production multiplier based on workers (0.0 to 1.0)."""
        max_workers = self.get_max_workers()
        if max_workers == 0:
            return 0.0
        workers = self.count_workers(units)
        return min(1.0, workers / max_workers)

    def get_resource_generation(self, units: List['Unit']) -> dict:
        """Get actual resource generation based on workers."""
        type_key = self.building_type.name.lower()
        base_gen = BUILDING_RESOURCE_GENERATION.get(type_key, {})
        multiplier = self.get_production_multiplier(units)

        return {
            'gold': int(base_gen.get('gold', 0) * multiplier),
            'food': int(base_gen.get('food', 0) * multiplier),
            'wood': int(base_gen.get('wood', 0) * multiplier)
        }

    def __post_init__(self):
        """Initialize building stats based on type."""
        self._apply_stats()

    def _apply_stats(self):
        """Apply stats from constants or mod overrides."""
        type_key = self.building_type.name.lower()

        if self._mod_manager:
            stats = self._mod_manager.get_building_stats(type_key)
        else:
            stats = BUILDING_STATS.get(type_key, BUILDING_STATS['house'])

        self.health = stats.get('health', 500)
        self.max_health = stats.get('health', 500)

    def get_rect(self) -> pygame.Rect:
        """Get building collision rectangle."""
        sizes = {
            BuildingType.HOUSE: (80, 80),
            BuildingType.CASTLE: (128, 128),
            BuildingType.FARM: (96, 96),
            BuildingType.TOWER: (64, 64)
        }
        w, h = sizes.get(self.building_type, (64, 64))
        return pygame.Rect(self.x - w // 2, self.y - h // 2, w, h)

    def get_size(self) -> tuple:
        """Get building visual size."""
        sizes = {
            BuildingType.HOUSE: (80, 80),
            BuildingType.CASTLE: (128, 128),
            BuildingType.FARM: (96, 96),
            BuildingType.TOWER: (64, 64)
        }
        return sizes.get(self.building_type, (64, 64))

    def take_damage(self, damage: int) -> bool:
        """Take damage. Returns True if building is destroyed."""
        self.health -= damage
        return self.health <= 0

    def is_destroyed(self) -> bool:
        """Check if building is destroyed."""
        return self.health <= 0

    def to_dict(self) -> dict:
        """Serialize building to dictionary for networking."""
        return {
            'uid': self.uid,
            'x': self.x,
            'y': self.y,
            'type': self.building_type.name,
            'team': self.team.name,
            'health': self.health,
            'max_health': self.max_health
        }

    @classmethod
    def from_dict(cls, data: dict, mod_manager: Optional['ModManager'] = None) -> 'Building':
        """Create building from dictionary."""
        building = cls(
            x=data['x'],
            y=data['y'],
            building_type=BuildingType[data['type']],
            team=Team[data['team']],
            uid=data['uid'],
            _mod_manager=mod_manager
        )
        building.health = data.get('health', building.max_health)
        return building


# =============================================================================
# VISUAL EFFECTS
# =============================================================================

@dataclass
class BloodEffect:
    """Visual effect for combat."""
    x: float
    y: float
    lifetime: float = 1.0
    max_lifetime: float = 1.0
    alpha: int = 255

    def update(self, dt: float) -> bool:
        """Update effect. Returns True if effect should be removed."""
        self.lifetime -= dt
        self.alpha = int(255 * (self.lifetime / self.max_lifetime))
        return self.lifetime <= 0

    def get_alpha(self) -> int:
        """Get current alpha value."""
        return max(0, min(255, self.alpha))
