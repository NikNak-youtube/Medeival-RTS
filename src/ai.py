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

        # Flanking strategy (Hard+ only)
        self.flanking_active = False
        self.flank_target_left: Optional[Tuple[float, float]] = None
        self.flank_target_right: Optional[Tuple[float, float]] = None
        self.flank_units_left: List[Unit] = []
        self.flank_units_right: List[Unit] = []
        self.main_force_units: List[Unit] = []

        # Army rally system - gather units before attacking
        self.rally_point: Optional[Tuple[float, float]] = None
        self.army_gathered = False
        self.gather_timer = 0.0  # Time spent waiting for army to gather

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
    def enemy_military_units(self) -> List[Unit]:
        """Get player's military (non-peasant) units."""
        return [u for u in self.enemy_units if u.unit_type != UnitType.PEASANT]

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

    def _calculate_flank_positions(self, target: Tuple[float, float]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Calculate flanking positions around a target (left and right flanks).

        Returns two positions that approach the target from different angles.
        """
        castle = self.my_castle
        if not castle:
            return target, target

        # Calculate the main attack vector (from AI castle to target)
        dx = target[0] - castle.x
        dy = target[1] - castle.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 1:
            return target, target

        # Normalize direction
        nx, ny = dx / dist, dy / dist

        # Perpendicular vectors for flanking (rotate 90 degrees)
        perp_x, perp_y = -ny, nx

        # Flank distance from main attack line
        flank_offset = 250

        # Calculate flank approach points - these are offset from the target
        # Left flank comes from the left side
        left_x = target[0] + perp_x * flank_offset
        left_y = target[1] + perp_y * flank_offset

        # Right flank comes from the right side
        right_x = target[0] - perp_x * flank_offset
        right_y = target[1] - perp_y * flank_offset

        # Clamp to map bounds
        left_x = max(100, min(MAP_WIDTH - 100, left_x))
        left_y = max(100, min(MAP_HEIGHT - 100, left_y))
        right_x = max(100, min(MAP_WIDTH - 100, right_x))
        right_y = max(100, min(MAP_HEIGHT - 100, right_y))

        return (left_x, left_y), (right_x, right_y)

    def _should_use_flanking(self) -> bool:
        """Determine if flanking strategy should be used."""
        # Only Hard and Brutal use flanking
        if self.difficulty not in [Difficulty.HARD, Difficulty.BRUTAL]:
            return False

        # Need at least 6 military units to flank effectively
        military_count = len(self.military_units)
        if military_count < 6:
            return False

        # Late game check - need significant army advantage or large army
        enemy_military = len(self.enemy_military_units)

        # Brutal always tries to flank with enough units
        if self.difficulty == Difficulty.BRUTAL and military_count >= 6:
            return True

        # Hard needs army advantage and more units
        if self.difficulty == Difficulty.HARD and military_count >= 8 and military_count > enemy_military:
            return True

        return False

    def _setup_flanking_attack(self):
        """Set up a flanking attack by dividing forces."""
        if not self.attack_target:
            return

        military = list(self.military_units)
        if len(military) < 6:
            self.flanking_active = False
            return

        # Calculate flank positions
        self.flank_target_left, self.flank_target_right = self._calculate_flank_positions(self.attack_target)

        # Divide forces: cavalry to flanks (fast units), others to main
        cavalry = [u for u in military if u.unit_type == UnitType.CAVALRY]
        knights = [u for u in military if u.unit_type == UnitType.KNIGHT]
        cannons = [u for u in military if u.unit_type == UnitType.CANNON]

        # Clear previous assignments
        self.flank_units_left.clear()
        self.flank_units_right.clear()
        self.main_force_units.clear()

        # Assign cavalry to flanks (split evenly)
        for i, cav in enumerate(cavalry):
            if i % 2 == 0:
                self.flank_units_left.append(cav)
            else:
                self.flank_units_right.append(cav)

        # Knights split between main force and flanks
        flank_knights = len(knights) // 3  # 1/3 to each flank
        for i, knight in enumerate(knights):
            if i < flank_knights:
                self.flank_units_left.append(knight)
            elif i < flank_knights * 2:
                self.flank_units_right.append(knight)
            else:
                self.main_force_units.append(knight)

        # Cannons stay with main force (slow, need protection)
        self.main_force_units.extend(cannons)

        # If flanks are too small, redistribute
        min_flank_size = 2
        if len(self.flank_units_left) < min_flank_size or len(self.flank_units_right) < min_flank_size:
            # Not enough for proper flanking, merge into main attack
            self.main_force_units.extend(self.flank_units_left)
            self.main_force_units.extend(self.flank_units_right)
            self.flank_units_left.clear()
            self.flank_units_right.clear()
            self.flanking_active = False
        else:
            self.flanking_active = True

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
            # Cancel attack when defending
            self._cancel_attack()
            self.attack_target = (castle.x, castle.y)  # Set defense target
        elif len(self.military_units) >= int(4 * self.aggression + 2) and self.state != 'defending':
            self.state = 'attacking'

    def _cancel_flanking(self):
        """Cancel flanking strategy and reset related state."""
        self.flanking_active = False
        self.flank_units_left.clear()
        self.flank_units_right.clear()
        self.main_force_units.clear()
        self.flank_target_left = None
        self.flank_target_right = None

    def _cancel_attack(self):
        """Cancel attack and reset all attack-related state."""
        self._cancel_flanking()
        self.rally_point = None
        self.army_gathered = False
        self.gather_timer = 0.0
        self.attack_target = None

    def _calculate_rally_point(self) -> Optional[Tuple[float, float]]:
        """Calculate a rally point between AI castle and the attack target."""
        castle = self.my_castle
        if not castle or not self.attack_target:
            return None

        # Rally point is partway between castle and target (closer to castle)
        # This gives units time to gather before the assault
        rally_distance = 300  # Distance from castle towards target

        dx = self.attack_target[0] - castle.x
        dy = self.attack_target[1] - castle.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 1:
            return (castle.x, castle.y)

        # Normalize and calculate rally point
        nx, ny = dx / dist, dy / dist
        rally_x = castle.x + nx * rally_distance
        rally_y = castle.y + ny * rally_distance

        # Clamp to map bounds
        rally_x = max(100, min(MAP_WIDTH - 100, rally_x))
        rally_y = max(100, min(MAP_HEIGHT - 100, rally_y))

        return (rally_x, rally_y)

    def _is_army_gathered(self) -> bool:
        """Check if enough military units are gathered at the rally point."""
        if not self.rally_point:
            return True  # No rally point, consider gathered

        military = self.military_units
        if not military:
            return False

        # Count units near rally point
        gather_radius = 150  # Units within this distance are considered gathered
        gathered_count = 0

        for unit in military:
            dist = unit.distance_to(self.rally_point[0], self.rally_point[1])
            if dist < gather_radius:
                gathered_count += 1

        # Need at least 70% of army gathered, or have been waiting too long
        total = len(military)
        gather_threshold = 0.7

        return gathered_count >= total * gather_threshold

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
        enemy_military_count = len(self.enemy_military_units)
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

        # For Normal+ difficulties, also require having more military than the player
        # Easy mode attacks based only on threshold
        if self.difficulty == Difficulty.EASY:
            can_attack = military_count >= attack_threshold
        else:
            # Normal+ requires both threshold AND army advantage over player
            can_attack = military_count >= attack_threshold and military_count > enemy_military_count

        if can_attack and self.state != 'defending':
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
                    self._setup_attack()
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

        self._setup_attack()

    def _setup_attack(self):
        """Set up attack - calculate rally point and reset gather state."""
        # Reset army gather state
        self.army_gathered = False
        self.gather_timer = 0.0

        # Calculate rally point for Normal+ (Easy just attacks directly)
        if self.difficulty == Difficulty.EASY:
            self.rally_point = None
            self.army_gathered = True  # Easy mode doesn't wait to gather
        else:
            self.rally_point = self._calculate_rally_point()

        # Check if we should use flanking for Hard+ difficulties
        if self._should_use_flanking():
            self._setup_flanking_attack()

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
        # Phase 1: Gather army at rally point (Normal+ only)
        if not self.army_gathered and self.rally_point:
            self._execute_gather_phase()
            return

        # Phase 2: Use flanking strategy if active (Hard+ only)
        if self.flanking_active:
            self._execute_flanking_attack()
            return

        # Phase 3: Standard coordinated attack
        for unit in self.military_units:
            self._execute_unit_attack(unit, self.attack_target)

    def _execute_gather_phase(self):
        """Execute the gathering phase - move units to rally point before attacking."""
        military = self.military_units

        # Move all units to rally point
        for unit in military:
            # Skip if already engaged with nearby enemy (allow defensive fighting)
            if unit.target_unit and unit.target_unit.is_alive():
                dist_to_enemy = unit.distance_to_unit(unit.target_unit)
                if dist_to_enemy < unit.attack_range + 100:
                    continue  # Let them finish the fight

            # Check for nearby enemies that are attacking us
            nearest_enemy = self._find_nearest_enemy(unit)
            if nearest_enemy:
                dist = unit.distance_to_unit(nearest_enemy)
                if dist < unit.attack_range + 50:
                    # Enemy in range, fight back
                    unit.set_attack_target(nearest_enemy)
                    continue

            # Move to rally point if not there yet
            dist_to_rally = unit.distance_to(self.rally_point[0], self.rally_point[1])
            if dist_to_rally > 80:
                unit.set_move_target(self.rally_point[0], self.rally_point[1])
            else:
                # At rally point, clear targets and wait
                if unit.target_x is not None and not unit.target_unit:
                    unit.clear_targets()

        # Check if army is gathered
        if self._is_army_gathered():
            self.army_gathered = True
            # Set up flanking now that army is gathered
            if self._should_use_flanking():
                self._setup_flanking_attack()

    def _execute_unit_attack(self, unit: Unit, target_pos: Optional[Tuple[float, float]]):
        """Execute attack logic for a single unit."""
        # Dynamic retargeting: check if there's a closer threat even if we have a target
        nearest_enemy = self._find_nearest_enemy(unit)

        # If an enemy is very close (within attack range + buffer), prioritize them
        # This allows units to respond to being attacked instead of ignoring threats
        if nearest_enemy:
            dist_to_nearest = unit.distance_to_unit(nearest_enemy)

            # Check if we should switch targets
            should_retarget = False

            if dist_to_nearest < unit.attack_range + 50:
                # Enemy is in attack range - definitely engage
                should_retarget = True
            elif unit.target_building and dist_to_nearest < 150:
                # Attacking building but enemy unit is close - switch to unit
                should_retarget = True
            elif unit.target_unit and unit.target_unit.is_alive():
                # Already targeting a unit - switch if new one is much closer
                current_dist = unit.distance_to_unit(unit.target_unit)
                if dist_to_nearest < current_dist * 0.6:  # New target is 40% closer
                    should_retarget = True
            elif not unit.target_unit or not unit.target_unit.is_alive():
                # No valid unit target - engage if enemy is reasonably close
                if dist_to_nearest < 200:
                    should_retarget = True

            if should_retarget:
                unit.set_attack_target(nearest_enemy)
                return

        # Skip if already has a valid target
        if unit.target_unit and unit.target_unit.is_alive():
            return
        if unit.target_building and not unit.target_building.is_destroyed():
            return

        # No immediate threats - proceed to attack target location
        if target_pos:
            # Check if we should attack a building at target location
            target_building = self._find_building_at(target_pos)
            if target_building:
                unit.set_building_target(target_building)
            else:
                unit.set_move_target(*target_pos)

    def _execute_flanking_attack(self):
        """Execute a coordinated flanking attack with multiple groups."""
        # Clean up dead units from groups
        self.flank_units_left = [u for u in self.flank_units_left if u.is_alive() and u in self.game.units]
        self.flank_units_right = [u for u in self.flank_units_right if u.is_alive() and u in self.game.units]
        self.main_force_units = [u for u in self.main_force_units if u.is_alive() and u in self.game.units]

        # Check if flanking is still viable
        total_flankers = len(self.flank_units_left) + len(self.flank_units_right)
        if total_flankers < 2:
            # Not enough flankers remaining, merge into standard attack
            self.flanking_active = False
            return

        # Execute left flank
        for unit in self.flank_units_left:
            # Move to flank position first, then attack
            dist_to_flank = unit.distance_to(self.flank_target_left[0], self.flank_target_left[1])
            if dist_to_flank > 100:
                # Still approaching flank position
                self._execute_unit_attack(unit, self.flank_target_left)
            else:
                # At flank position, attack main target
                self._execute_unit_attack(unit, self.attack_target)

        # Execute right flank
        for unit in self.flank_units_right:
            dist_to_flank = unit.distance_to(self.flank_target_right[0], self.flank_target_right[1])
            if dist_to_flank > 100:
                # Still approaching flank position
                self._execute_unit_attack(unit, self.flank_target_right)
            else:
                # At flank position, attack main target
                self._execute_unit_attack(unit, self.attack_target)

        # Main force attacks directly
        for unit in self.main_force_units:
            self._execute_unit_attack(unit, self.attack_target)

        # Also handle any units not assigned to a group (newly trained)
        all_assigned = set(self.flank_units_left + self.flank_units_right + self.main_force_units)
        for unit in self.military_units:
            if unit not in all_assigned:
                # Assign new units to main force
                self.main_force_units.append(unit)
                self._execute_unit_attack(unit, self.attack_target)

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
