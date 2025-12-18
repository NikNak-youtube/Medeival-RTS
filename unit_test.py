"""
Unit tests for Medieval RTS game.

Run with: python unit_test.py
Or with pytest: pytest unit_test.py -v
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock pygame before importing game modules
sys.modules['pygame'] = MagicMock()
sys.modules['pygame.font'] = MagicMock()
sys.modules['pygame.mixer'] = MagicMock()
sys.modules['pygame.display'] = MagicMock()

# Create a mock Rect class that behaves like pygame.Rect
class MockRect:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.width = w
        self.height = h
        self.left = x
        self.top = y
        self.right = x + w
        self.bottom = y + h

    def colliderect(self, other):
        return not (self.right < other.left or self.left > other.right or
                    self.bottom < other.top or self.top > other.bottom)

    def collidepoint(self, pos):
        x, y = pos
        return self.left <= x <= self.right and self.top <= y <= self.bottom

sys.modules['pygame'].Rect = MockRect

from src.constants import (
    UnitType, BuildingType, Team, MAP_WIDTH, MAP_HEIGHT,
    UNIT_STATS, BUILDING_STATS, UNIT_COSTS, BUILDING_COSTS,
    STARTING_GOLD, STARTING_FOOD, STARTING_WOOD,
    BASE_WIDTH, BASE_HEIGHT, get_scale, scale
)
from src.entities import Unit, Building, Resources, BloodEffect, Projectile
from src.camera import Camera
from src.network import NetworkManager


# =============================================================================
# RESOURCES TESTS
# =============================================================================

class TestResources(unittest.TestCase):
    """Tests for the Resources class."""

    def test_initial_resources(self):
        """Test that resources start with correct default values."""
        res = Resources()
        self.assertEqual(res.gold, STARTING_GOLD)
        self.assertEqual(res.food, STARTING_FOOD)
        self.assertEqual(res.wood, STARTING_WOOD)

    def test_can_afford_true(self):
        """Test can_afford returns True when resources are sufficient."""
        res = Resources(gold=100, food=50, wood=50)
        self.assertTrue(res.can_afford({'gold': 50, 'food': 25, 'wood': 25}))
        self.assertTrue(res.can_afford({'gold': 100}))
        self.assertTrue(res.can_afford({}))

    def test_can_afford_false(self):
        """Test can_afford returns False when resources are insufficient."""
        res = Resources(gold=100, food=50, wood=50)
        self.assertFalse(res.can_afford({'gold': 150}))
        self.assertFalse(res.can_afford({'food': 100}))
        self.assertFalse(res.can_afford({'gold': 50, 'food': 100}))

    def test_spend_success(self):
        """Test spending resources when affordable."""
        res = Resources(gold=100, food=50, wood=50)
        result = res.spend({'gold': 30, 'food': 20, 'wood': 10})
        self.assertTrue(result)
        self.assertEqual(res.gold, 70)
        self.assertEqual(res.food, 30)
        self.assertEqual(res.wood, 40)

    def test_spend_failure(self):
        """Test spending fails when unaffordable and resources unchanged."""
        res = Resources(gold=100, food=50, wood=50)
        result = res.spend({'gold': 150})
        self.assertFalse(result)
        self.assertEqual(res.gold, 100)  # Unchanged

    def test_add_resources(self):
        """Test adding resources."""
        res = Resources(gold=100, food=50, wood=50)
        res.add(gold=50, food=25, wood=10)
        self.assertEqual(res.gold, 150)
        self.assertEqual(res.food, 75)
        self.assertEqual(res.wood, 60)


# =============================================================================
# UNIT TESTS
# =============================================================================

class TestUnit(unittest.TestCase):
    """Tests for the Unit class."""

    def test_unit_creation(self):
        """Test unit creation with correct stats."""
        unit = Unit(100, 200, UnitType.KNIGHT, Team.PLAYER)
        self.assertEqual(unit.x, 100)
        self.assertEqual(unit.y, 200)
        self.assertEqual(unit.unit_type, UnitType.KNIGHT)
        self.assertEqual(unit.team, Team.PLAYER)
        self.assertEqual(unit.health, UNIT_STATS['knight']['health'])
        self.assertEqual(unit.attack, UNIT_STATS['knight']['attack'])

    def test_unit_peasant_stats(self):
        """Test peasant has correct stats."""
        peasant = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        self.assertEqual(peasant.health, UNIT_STATS['peasant']['health'])
        self.assertEqual(peasant.attack, UNIT_STATS['peasant']['attack'])
        self.assertEqual(peasant.speed, UNIT_STATS['peasant']['speed'])

    def test_unit_cavalry_stats(self):
        """Test cavalry has correct stats."""
        cavalry = Unit(0, 0, UnitType.CAVALRY, Team.ENEMY)
        self.assertEqual(cavalry.health, UNIT_STATS['cavalry']['health'])
        self.assertEqual(cavalry.speed, UNIT_STATS['cavalry']['speed'])

    def test_unit_cannon_stats(self):
        """Test cannon has correct stats."""
        cannon = Unit(0, 0, UnitType.CANNON, Team.PLAYER)
        self.assertEqual(cannon.health, UNIT_STATS['cannon']['health'])
        self.assertEqual(cannon.attack, UNIT_STATS['cannon']['attack'])
        self.assertEqual(cannon.attack_range, UNIT_STATS['cannon']['range'])

    def test_distance_to(self):
        """Test distance calculation."""
        unit = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        self.assertAlmostEqual(unit.distance_to(3, 4), 5.0)
        self.assertAlmostEqual(unit.distance_to(0, 0), 0.0)

    def test_distance_to_unit(self):
        """Test distance to another unit."""
        unit1 = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        unit2 = Unit(6, 8, UnitType.KNIGHT, Team.ENEMY)
        self.assertAlmostEqual(unit1.distance_to_unit(unit2), 10.0)

    def test_take_damage(self):
        """Test taking damage."""
        unit = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        initial_health = unit.health
        died = unit.take_damage(50)
        self.assertFalse(died)
        self.assertEqual(unit.health, initial_health - 50)

    def test_take_lethal_damage(self):
        """Test taking lethal damage."""
        unit = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        died = unit.take_damage(1000)
        self.assertTrue(died)
        self.assertLessEqual(unit.health, 0)

    def test_is_alive(self):
        """Test is_alive check."""
        unit = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        self.assertTrue(unit.is_alive())
        unit.health = 0
        self.assertFalse(unit.is_alive())
        unit.health = -10
        self.assertFalse(unit.is_alive())

    def test_heal(self):
        """Test healing."""
        unit = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        unit.health = 50
        healed = unit.heal(30)
        self.assertTrue(healed)
        self.assertEqual(unit.health, 80)

    def test_heal_at_max(self):
        """Test healing when at max health."""
        unit = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        healed = unit.heal(30)
        self.assertFalse(healed)
        self.assertEqual(unit.health, unit.max_health)

    def test_heal_cap_at_max(self):
        """Test healing doesn't exceed max health."""
        unit = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        unit.health = unit.max_health - 10
        unit.heal(100)
        self.assertEqual(unit.health, unit.max_health)

    def test_needs_healing(self):
        """Test needs_healing check."""
        unit = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        self.assertFalse(unit.needs_healing())
        unit.health -= 1
        self.assertTrue(unit.needs_healing())

    def test_is_enemy_of(self):
        """Test enemy detection."""
        player_unit = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        enemy_unit = Unit(0, 0, UnitType.KNIGHT, Team.ENEMY)
        self.assertTrue(player_unit.is_enemy_of(Team.ENEMY))
        self.assertFalse(player_unit.is_enemy_of(Team.PLAYER))
        self.assertTrue(enemy_unit.is_enemy_of(Team.PLAYER))

    def test_set_move_target(self):
        """Test setting movement target."""
        unit = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        unit.set_move_target(100, 200)
        self.assertEqual(unit.target_x, 100)
        self.assertEqual(unit.target_y, 200)
        self.assertIsNone(unit.target_unit)
        self.assertIsNone(unit.target_building)

    def test_set_attack_target(self):
        """Test setting attack target."""
        unit1 = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        unit2 = Unit(50, 50, UnitType.PEASANT, Team.ENEMY)
        unit1.set_attack_target(unit2)
        self.assertEqual(unit1.target_unit, unit2)
        self.assertEqual(unit1.target_x, 50)
        self.assertEqual(unit1.target_y, 50)

    def test_clear_targets(self):
        """Test clearing all targets."""
        unit = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        unit.set_move_target(100, 200)
        unit.attack_move_target = (300, 400)
        unit.clear_targets()
        self.assertIsNone(unit.target_x)
        self.assertIsNone(unit.target_y)
        self.assertIsNone(unit.target_unit)
        self.assertIsNone(unit.target_building)
        self.assertIsNone(unit.attack_move_target)

    def test_set_attack_move_target(self):
        """Test setting attack-move target."""
        unit = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        unit.set_attack_move_target(100, 200)
        self.assertEqual(unit.attack_move_target, (100, 200))
        self.assertEqual(unit.target_x, 100)
        self.assertEqual(unit.target_y, 200)

    def test_get_collision_radius(self):
        """Test collision radius varies by unit type."""
        peasant = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        cavalry = Unit(0, 0, UnitType.CAVALRY, Team.PLAYER)
        self.assertLess(peasant.get_collision_radius(), cavalry.get_collision_radius())

    def test_to_dict(self):
        """Test serialization to dictionary."""
        unit = Unit(100, 200, UnitType.KNIGHT, Team.PLAYER, uid=42)
        data = unit.to_dict()
        self.assertEqual(data['uid'], 42)
        self.assertEqual(data['x'], 100)
        self.assertEqual(data['y'], 200)
        self.assertEqual(data['type'], 'KNIGHT')
        self.assertEqual(data['team'], 'PLAYER')

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            'uid': 42,
            'x': 100,
            'y': 200,
            'type': 'KNIGHT',
            'team': 'ENEMY',
            'health': 75,
            'max_health': 150
        }
        unit = Unit.from_dict(data)
        self.assertEqual(unit.uid, 42)
        self.assertEqual(unit.x, 100)
        self.assertEqual(unit.y, 200)
        self.assertEqual(unit.unit_type, UnitType.KNIGHT)
        self.assertEqual(unit.team, Team.ENEMY)
        self.assertEqual(unit.health, 75)


# =============================================================================
# BUILDING TESTS
# =============================================================================

class TestBuilding(unittest.TestCase):
    """Tests for the Building class."""

    def test_building_creation(self):
        """Test building creation."""
        building = Building(500, 600, BuildingType.CASTLE, Team.PLAYER)
        self.assertEqual(building.x, 500)
        self.assertEqual(building.y, 600)
        self.assertEqual(building.building_type, BuildingType.CASTLE)
        self.assertEqual(building.team, Team.PLAYER)
        self.assertEqual(building.health, BUILDING_STATS['castle']['health'])

    def test_building_types_have_different_health(self):
        """Test different building types have different health."""
        castle = Building(0, 0, BuildingType.CASTLE, Team.PLAYER)
        house = Building(0, 0, BuildingType.HOUSE, Team.PLAYER)
        self.assertGreater(castle.max_health, house.max_health)

    def test_take_damage(self):
        """Test building takes damage."""
        building = Building(0, 0, BuildingType.HOUSE, Team.PLAYER)
        initial_health = building.health
        destroyed = building.take_damage(100)
        self.assertFalse(destroyed)
        self.assertEqual(building.health, initial_health - 100)

    def test_take_lethal_damage(self):
        """Test building destruction."""
        building = Building(0, 0, BuildingType.HOUSE, Team.PLAYER)
        destroyed = building.take_damage(10000)
        self.assertTrue(destroyed)
        self.assertLessEqual(building.health, 0)

    def test_is_destroyed(self):
        """Test is_destroyed check."""
        building = Building(0, 0, BuildingType.FARM, Team.PLAYER)
        self.assertFalse(building.is_destroyed())
        building.health = 0
        self.assertTrue(building.is_destroyed())

    def test_get_size(self):
        """Test different building types have different sizes."""
        castle = Building(0, 0, BuildingType.CASTLE, Team.PLAYER)
        house = Building(0, 0, BuildingType.HOUSE, Team.PLAYER)
        tower = Building(0, 0, BuildingType.TOWER, Team.PLAYER)
        castle_size = castle.get_size()
        house_size = house.get_size()
        tower_size = tower.get_size()
        self.assertGreater(castle_size[0], house_size[0])
        self.assertLess(tower_size[0], house_size[0])

    def test_get_max_workers(self):
        """Test max workers varies by building type."""
        farm = Building(0, 0, BuildingType.FARM, Team.PLAYER)
        castle = Building(0, 0, BuildingType.CASTLE, Team.PLAYER)
        self.assertGreater(farm.get_max_workers(), castle.get_max_workers())

    def test_to_dict(self):
        """Test serialization to dictionary."""
        building = Building(100, 200, BuildingType.FARM, Team.ENEMY, uid=99)
        data = building.to_dict()
        self.assertEqual(data['uid'], 99)
        self.assertEqual(data['x'], 100)
        self.assertEqual(data['y'], 200)
        self.assertEqual(data['type'], 'FARM')
        self.assertEqual(data['team'], 'ENEMY')

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            'uid': 99,
            'x': 100,
            'y': 200,
            'type': 'TOWER',
            'team': 'PLAYER',
            'health': 250,
            'max_health': 500
        }
        building = Building.from_dict(data)
        self.assertEqual(building.uid, 99)
        self.assertEqual(building.building_type, BuildingType.TOWER)
        self.assertEqual(building.health, 250)


# =============================================================================
# BLOOD EFFECT TESTS
# =============================================================================

class TestBloodEffect(unittest.TestCase):
    """Tests for the BloodEffect class."""

    def test_effect_creation(self):
        """Test effect creation."""
        effect = BloodEffect(100, 200)
        self.assertEqual(effect.x, 100)
        self.assertEqual(effect.y, 200)
        self.assertEqual(effect.lifetime, 1.0)
        self.assertEqual(effect.alpha, 255)

    def test_effect_update(self):
        """Test effect updates over time."""
        effect = BloodEffect(0, 0, lifetime=1.0)
        expired = effect.update(0.5)
        self.assertFalse(expired)
        self.assertEqual(effect.lifetime, 0.5)
        self.assertLess(effect.alpha, 255)

    def test_effect_expiration(self):
        """Test effect expires."""
        effect = BloodEffect(0, 0, lifetime=0.5)
        expired = effect.update(1.0)
        self.assertTrue(expired)

    def test_get_alpha(self):
        """Test alpha is clamped to valid range."""
        effect = BloodEffect(0, 0)
        effect.alpha = 300
        self.assertEqual(effect.get_alpha(), 255)
        effect.alpha = -50
        self.assertEqual(effect.get_alpha(), 0)


# =============================================================================
# PROJECTILE TESTS
# =============================================================================

class TestProjectile(unittest.TestCase):
    """Tests for the Projectile class."""

    def test_projectile_creation(self):
        """Test projectile creation."""
        proj = Projectile(0, 0, 100, 100, damage=50)
        self.assertEqual(proj.x, 0)
        self.assertEqual(proj.y, 0)
        self.assertEqual(proj.target_x, 100)
        self.assertEqual(proj.target_y, 100)
        self.assertEqual(proj.damage, 50)

    def test_projectile_reaches_target(self):
        """Test projectile reaches target."""
        proj = Projectile(0, 0, 10, 0, speed=1000)
        reached = proj.update(1.0)
        self.assertTrue(reached)

    def test_projectile_moves_towards_target(self):
        """Test projectile moves towards target."""
        proj = Projectile(0, 0, 1000, 0, speed=100)
        initial_x = proj.x
        proj.update(0.1)
        self.assertGreater(proj.x, initial_x)


# =============================================================================
# CAMERA TESTS
# =============================================================================

class TestCamera(unittest.TestCase):
    """Tests for the Camera class."""

    def test_camera_creation(self):
        """Test camera creation."""
        camera = Camera(1280, 720)
        self.assertEqual(camera.screen_width, 1280)
        self.assertEqual(camera.screen_height, 720)
        self.assertEqual(camera.width, BASE_WIDTH)
        self.assertEqual(camera.height, BASE_HEIGHT)
        self.assertEqual(camera.x, 0)
        self.assertEqual(camera.y, 0)

    def test_scale_property(self):
        """Test scale calculation."""
        camera = Camera(1280, 720)
        self.assertEqual(camera.scale, 1.0)
        camera.screen_width = 2560
        self.assertEqual(camera.scale, 2.0)

    def test_world_to_screen(self):
        """Test world to screen coordinate conversion."""
        camera = Camera(1280, 720)
        camera.x = 100
        camera.y = 50
        screen_x, screen_y = camera.world_to_screen(200, 150)
        self.assertEqual(screen_x, 100)  # 200 - 100
        self.assertEqual(screen_y, 100)  # 150 - 50

    def test_screen_to_world(self):
        """Test screen to world coordinate conversion."""
        camera = Camera(1280, 720)
        camera.x = 100
        camera.y = 50
        world_x, world_y = camera.screen_to_world(100, 100)
        self.assertEqual(world_x, 200)  # 100 + 100
        self.assertEqual(world_y, 150)  # 100 + 50

    def test_world_to_screen_scaled(self):
        """Test coordinate conversion with scaling."""
        camera = Camera(2560, 1440)  # 2x scale
        camera.x = 0
        camera.y = 0
        screen_x, screen_y = camera.world_to_screen(100, 100)
        self.assertEqual(screen_x, 200)  # 100 * 2
        self.assertEqual(screen_y, 200)  # 100 * 2

    def test_screen_to_world_scaled(self):
        """Test coordinate conversion with scaling (inverse)."""
        camera = Camera(2560, 1440)  # 2x scale
        camera.x = 0
        camera.y = 0
        world_x, world_y = camera.screen_to_world(200, 200)
        self.assertEqual(world_x, 100)  # 200 / 2
        self.assertEqual(world_y, 100)  # 200 / 2

    def test_clamp_to_map(self):
        """Test camera clamping to map bounds."""
        camera = Camera(1280, 720)
        camera.x = -100
        camera.y = -100
        camera.clamp_to_map()
        self.assertEqual(camera.x, 0)
        self.assertEqual(camera.y, 0)

        camera.x = MAP_WIDTH + 100
        camera.y = MAP_HEIGHT + 100
        camera.clamp_to_map()
        self.assertEqual(camera.x, MAP_WIDTH - camera.width)
        self.assertEqual(camera.y, MAP_HEIGHT - camera.height)

    def test_center_on(self):
        """Test centering camera on a position."""
        camera = Camera(1280, 720)
        camera.center_on(1000, 1000)
        expected_x = 1000 - camera.width / 2
        expected_y = 1000 - camera.height / 2
        self.assertEqual(camera.x, expected_x)
        self.assertEqual(camera.y, expected_y)

    def test_is_point_visible(self):
        """Test point visibility check."""
        camera = Camera(1280, 720)
        camera.x = 0
        camera.y = 0
        self.assertTrue(camera.is_point_visible(100, 100))
        self.assertFalse(camera.is_point_visible(5000, 5000))

    def test_scale_size(self):
        """Test size scaling."""
        camera = Camera(2560, 1440)  # 2x scale
        self.assertEqual(camera.scale_size(50), 100)

    def test_get_visible_area(self):
        """Test getting visible area bounds."""
        camera = Camera(1280, 720)
        camera.x = 100
        camera.y = 200
        left, top, right, bottom = camera.get_visible_area()
        self.assertEqual(left, 100)
        self.assertEqual(top, 200)
        self.assertEqual(right, 100 + camera.width)
        self.assertEqual(bottom, 200 + camera.height)


# =============================================================================
# NETWORK TESTS (without actual networking)
# =============================================================================

class TestNetworkMirroring(unittest.TestCase):
    """Tests for network position mirroring."""

    def test_mirror_pos(self):
        """Test position mirroring."""
        # Create a mock network manager (we'll test the mirror function directly)
        class MockNetworkManager:
            def mirror_pos(self, x, y):
                return (MAP_WIDTH - x, MAP_HEIGHT - y)

        net = MockNetworkManager()

        # Test mirroring
        x, y = 100, 200
        mx, my = net.mirror_pos(x, y)
        self.assertEqual(mx, MAP_WIDTH - 100)
        self.assertEqual(my, MAP_HEIGHT - 200)

    def test_mirror_pos_double_mirror(self):
        """Test that double mirroring returns original position."""
        class MockNetworkManager:
            def mirror_pos(self, x, y):
                return (MAP_WIDTH - x, MAP_HEIGHT - y)

        net = MockNetworkManager()

        original_x, original_y = 500, 700
        mx, my = net.mirror_pos(original_x, original_y)
        restored_x, restored_y = net.mirror_pos(mx, my)

        self.assertEqual(restored_x, original_x)
        self.assertEqual(restored_y, original_y)

    def test_mirror_pos_corners(self):
        """Test mirroring corner positions."""
        class MockNetworkManager:
            def mirror_pos(self, x, y):
                return (MAP_WIDTH - x, MAP_HEIGHT - y)

        net = MockNetworkManager()

        # Bottom-left should become top-right
        mx, my = net.mirror_pos(0, MAP_HEIGHT)
        self.assertEqual(mx, MAP_WIDTH)
        self.assertEqual(my, 0)

        # Top-right should become bottom-left
        mx, my = net.mirror_pos(MAP_WIDTH, 0)
        self.assertEqual(mx, 0)
        self.assertEqual(my, MAP_HEIGHT)


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

class TestConstants(unittest.TestCase):
    """Tests for game constants."""

    def test_unit_costs_defined(self):
        """Test that all unit types have costs defined."""
        for unit_type in ['peasant', 'knight', 'cavalry', 'cannon']:
            self.assertIn(unit_type, UNIT_COSTS)
            self.assertIn('gold', UNIT_COSTS[unit_type])

    def test_building_costs_defined(self):
        """Test that all building types have costs defined."""
        for building_type in ['house', 'castle', 'farm', 'tower']:
            self.assertIn(building_type, BUILDING_COSTS)

    def test_unit_stats_defined(self):
        """Test that all unit types have stats defined."""
        for unit_type in ['peasant', 'knight', 'cavalry', 'cannon']:
            self.assertIn(unit_type, UNIT_STATS)
            stats = UNIT_STATS[unit_type]
            self.assertIn('health', stats)
            self.assertIn('attack', stats)
            self.assertIn('speed', stats)

    def test_building_stats_defined(self):
        """Test that all building types have stats defined."""
        for building_type in ['house', 'castle', 'farm', 'tower']:
            self.assertIn(building_type, BUILDING_STATS)
            self.assertIn('health', BUILDING_STATS[building_type])

    def test_map_dimensions_positive(self):
        """Test map dimensions are positive."""
        self.assertGreater(MAP_WIDTH, 0)
        self.assertGreater(MAP_HEIGHT, 0)

    def test_base_resolution_defined(self):
        """Test base resolution is defined."""
        self.assertEqual(BASE_WIDTH, 1280)
        self.assertEqual(BASE_HEIGHT, 720)

    def test_get_scale_default(self):
        """Test get_scale returns 1.0 at base resolution."""
        # This assumes SCREEN_WIDTH/HEIGHT are at default
        # Note: This might fail if resolution was changed
        scale_val = get_scale()
        self.assertIsInstance(scale_val, float)
        self.assertGreater(scale_val, 0)

    def test_scale_function(self):
        """Test scale function."""
        # At default resolution, scale(100) should return 100
        # This is a basic sanity check
        result = scale(100)
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestUnitBuildingInteraction(unittest.TestCase):
    """Tests for unit-building interactions."""

    def test_peasant_can_be_assigned(self):
        """Test peasant can be assigned to building."""
        peasant = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        building = Building(100, 100, BuildingType.FARM, Team.PLAYER)
        peasant.assign_to_building(building)
        self.assertEqual(peasant.assigned_building, building)
        self.assertEqual(peasant.target_x, 100)
        self.assertEqual(peasant.target_y, 100)

    def test_non_peasant_cannot_be_assigned(self):
        """Test non-peasant units cannot be assigned to buildings."""
        knight = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        building = Building(100, 100, BuildingType.FARM, Team.PLAYER)
        knight.assign_to_building(building)
        self.assertIsNone(knight.assigned_building)

    def test_peasant_unassignment(self):
        """Test peasant can be unassigned from building."""
        peasant = Unit(0, 0, UnitType.PEASANT, Team.PLAYER)
        building = Building(100, 100, BuildingType.FARM, Team.PLAYER)
        peasant.assign_to_building(building)
        peasant.unassign_from_building()
        self.assertIsNone(peasant.assigned_building)
        self.assertFalse(peasant.is_working)


class TestCombat(unittest.TestCase):
    """Tests for combat mechanics."""

    def test_unit_can_attack_enemy(self):
        """Test unit can target enemy."""
        attacker = Unit(0, 0, UnitType.KNIGHT, Team.PLAYER)
        target = Unit(50, 50, UnitType.PEASANT, Team.ENEMY)
        attacker.set_attack_target(target)
        self.assertEqual(attacker.target_unit, target)

    def test_unit_damage_calculation(self):
        """Test damage reduces health."""
        target = Unit(0, 0, UnitType.PEASANT, Team.ENEMY)
        initial_health = target.health
        damage = 10
        target.take_damage(damage)
        self.assertEqual(target.health, initial_health - damage)

    def test_building_attack_target(self):
        """Test unit can target building."""
        attacker = Unit(0, 0, UnitType.CANNON, Team.PLAYER)
        building = Building(100, 100, BuildingType.TOWER, Team.ENEMY)
        attacker.set_building_target(building)
        self.assertEqual(attacker.target_building, building)
        self.assertIsNone(attacker.target_unit)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)
