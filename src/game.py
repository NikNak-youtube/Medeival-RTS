"""
Main Game class - orchestrates all game systems.
"""

import pygame
import random
import math
import time
from typing import List, Optional, Tuple

from .constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, MAP_WIDTH, MAP_HEIGHT, TILE_SIZE, FPS,
    WHITE, BLACK, RED, GREEN, GOLD, GRAY, DARK_GRAY, LIGHT_GRAY, BROWN, YELLOW,
    GameState, UnitType, BuildingType, Team,
    UNIT_COSTS, BUILDING_COSTS, RESOURCE_TICK_INTERVAL,
    FOOD_CONSUMPTION_INTERVAL, FOOD_PER_UNIT, STARVATION_DAMAGE
)
from .assets import AssetManager, ModManager, get_unit_asset_name, get_building_asset_name
from .entities import Unit, Building, BloodEffect, Resources
from .camera import Camera
from .ai import AIBot
from .network import NetworkManager
from .ui import (
    Button, TextInput, HUDButton, Minimap, ResourceDisplay, SelectionInfo,
    draw_health_bar
)


class Game:
    """Main game class."""

    def __init__(self):
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Medieval RTS")
        self.clock = pygame.time.Clock()

        # Game state
        self.state = GameState.MAIN_MENU
        self.running = True
        self.dt = 0.0

        # Mod support
        self.mod_manager = ModManager()
        self.mod_manager.load_all_mods()

        # Assets
        self.assets = AssetManager(mod_manager=self.mod_manager)
        self.assets.load_all_assets()

        # Camera
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)

        # Game objects
        self.units: List[Unit] = []
        self.buildings: List[Building] = []
        self.blood_effects: List[BloodEffect] = []

        # Resources
        self.player_resources = Resources()
        self.enemy_resources = Resources()

        # Selection
        self.selected_units: List[Unit] = []
        self.selected_building: Optional[Building] = None
        self.selection_start: Optional[Tuple[int, int]] = None
        self.selection_rect: Optional[pygame.Rect] = None

        # Building placement
        self.placing_building: Optional[BuildingType] = None

        # AI and networking
        self.ai_bot: Optional[AIBot] = None
        self.network = NetworkManager(self)
        self.is_multiplayer = False

        # Timers
        self.resource_timer = 0.0
        self.food_timer = 0.0

        # UID counter
        self._uid_counter = 0

        # Fonts
        self.font = pygame.font.Font(None, 24)
        self.large_font = pygame.font.Font(None, 48)
        self.title_font = pygame.font.Font(None, 72)

        # Initialize UI
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components."""
        # Main menu buttons
        self.menu_buttons = [
            Button(SCREEN_WIDTH // 2 - 150, 250, 300, 50, "Play vs AI"),
            Button(SCREEN_WIDTH // 2 - 150, 320, 300, 50, "Host Multiplayer"),
            Button(SCREEN_WIDTH // 2 - 150, 390, 300, 50, "Join Multiplayer"),
            Button(SCREEN_WIDTH // 2 - 150, 460, 300, 50, "Quit")
        ]

        # Multiplayer UI
        self.ip_input = TextInput(SCREEN_WIDTH // 2 - 150, 350, 300, 40, "Enter IP address")
        self.connect_button = Button(SCREEN_WIDTH // 2 - 75, 410, 150, 40, "Connect")
        self.back_button = Button(SCREEN_WIDTH // 2 - 75, 470, 150, 40, "Back")
        self.accept_button = Button(SCREEN_WIDTH // 2 - 160, 400, 150, 40, "Accept")
        self.decline_button = Button(SCREEN_WIDTH // 2 + 10, 400, 150, 40, "Decline")

        # HUD components
        self.minimap = Minimap(SCREEN_WIDTH - 160, 10, 150, MAP_WIDTH, MAP_HEIGHT)
        self.resource_display = ResourceDisplay(SCREEN_WIDTH - 300, SCREEN_HEIGHT - 95)
        self.selection_info = SelectionInfo(520, SCREEN_HEIGHT - 70)

    def next_uid(self) -> int:
        """Get next unique ID."""
        self._uid_counter += 1
        return self._uid_counter

    # =========================================================================
    # GAME INITIALIZATION
    # =========================================================================

    def init_game(self, vs_ai: bool = True):
        """Initialize a new game."""
        # Clear existing objects
        self.units.clear()
        self.buildings.clear()
        self.blood_effects.clear()
        self.selected_units.clear()
        self.selected_building = None
        self.placing_building = None

        # Reset resources
        self.player_resources = Resources()
        self.enemy_resources = Resources()

        # Reset UID counter
        self._uid_counter = 0

        # Create player base
        self._create_player_base()

        # Create enemy base
        self._create_enemy_base()

        # Setup AI or multiplayer
        if vs_ai:
            self.ai_bot = AIBot(self)
            self.is_multiplayer = False
            self._create_enemy_starting_units()
        else:
            self.ai_bot = None
            self.is_multiplayer = True

        # Position camera at player start
        self.camera.x = 0
        self.camera.y = MAP_HEIGHT - SCREEN_HEIGHT

        self.state = GameState.PLAYING

    def _create_player_base(self):
        """Create player starting base."""
        # Castle
        castle = Building(300, MAP_HEIGHT - 300, BuildingType.CASTLE, Team.PLAYER,
                         _mod_manager=self.mod_manager)
        castle.uid = self.next_uid()
        self.buildings.append(castle)

        # Starting peasants
        for i in range(3):
            peasant = Unit(350 + i * 40, MAP_HEIGHT - 250, UnitType.PEASANT, Team.PLAYER,
                          _mod_manager=self.mod_manager)
            peasant.uid = self.next_uid()
            self.units.append(peasant)

        # Starting knight
        knight = Unit(300, MAP_HEIGHT - 200, UnitType.KNIGHT, Team.PLAYER,
                     _mod_manager=self.mod_manager)
        knight.uid = self.next_uid()
        self.units.append(knight)

    def _create_enemy_base(self):
        """Create enemy starting base."""
        castle = Building(MAP_WIDTH - 300, 300, BuildingType.CASTLE, Team.ENEMY,
                         _mod_manager=self.mod_manager)
        castle.uid = self.next_uid()
        self.buildings.append(castle)

    def _create_enemy_starting_units(self):
        """Create enemy starting units for AI mode."""
        for i in range(3):
            peasant = Unit(MAP_WIDTH - 350 - i * 40, 250, UnitType.PEASANT, Team.ENEMY,
                          _mod_manager=self.mod_manager)
            peasant.uid = self.next_uid()
            self.units.append(peasant)

        knight = Unit(MAP_WIDTH - 300, 200, UnitType.KNIGHT, Team.ENEMY,
                     _mod_manager=self.mod_manager)
        knight.uid = self.next_uid()
        self.units.append(knight)

    # =========================================================================
    # EVENT HANDLING
    # =========================================================================

    def handle_events(self):
        """Handle pygame events."""
        mouse_pos = pygame.mouse.get_pos()
        mouse_clicked = False
        right_clicked = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mouse_clicked = True
                    if self.state == GameState.PLAYING:
                        self.selection_start = mouse_pos
                elif event.button == 3:
                    right_clicked = True

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and self.selection_start:
                    self._finish_selection(mouse_pos)
                    self.selection_start = None
                    self.selection_rect = None

            if event.type == pygame.KEYDOWN:
                if self.state == GameState.PLAYING:
                    self._handle_game_keys(event)

            # Text input events
            if self.state in [GameState.MULTIPLAYER_LOBBY, GameState.CONNECTING]:
                self.ip_input.handle_event(event)

        # State-specific input
        if self.state == GameState.MAIN_MENU:
            self._handle_menu_input(mouse_pos, mouse_clicked)
        elif self.state == GameState.PLAYING:
            self._handle_game_input(mouse_pos, mouse_clicked, right_clicked)
        elif self.state == GameState.MULTIPLAYER_LOBBY:
            self._handle_lobby_input(mouse_pos, mouse_clicked)
        elif self.state == GameState.WAITING_FOR_ACCEPT:
            self._handle_waiting_input(mouse_pos, mouse_clicked)

    def _handle_menu_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle main menu input."""
        for button in self.menu_buttons:
            button.update(mouse_pos)

        if clicked:
            if self.menu_buttons[0].is_clicked(mouse_pos, True):
                self.init_game(vs_ai=True)
            elif self.menu_buttons[1].is_clicked(mouse_pos, True):
                if self.network.host_game():
                    self.state = GameState.WAITING_FOR_ACCEPT
            elif self.menu_buttons[2].is_clicked(mouse_pos, True):
                self.state = GameState.MULTIPLAYER_LOBBY
            elif self.menu_buttons[3].is_clicked(mouse_pos, True):
                self.running = False

    def _handle_lobby_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle multiplayer lobby input."""
        self.connect_button.update(mouse_pos)
        self.back_button.update(mouse_pos)

        if clicked:
            if self.connect_button.is_clicked(mouse_pos, True) and self.ip_input.text:
                if self.network.connect_to_host(self.ip_input.text):
                    self.state = GameState.CONNECTING
            elif self.back_button.is_clicked(mouse_pos, True):
                self.state = GameState.MAIN_MENU

    def _handle_waiting_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle waiting for connection input."""
        self.back_button.update(mouse_pos)

        if self.network.pending_invite:
            self.accept_button.update(mouse_pos)
            self.decline_button.update(mouse_pos)

            if clicked:
                if self.accept_button.is_clicked(mouse_pos, True):
                    self.network.accept_invite()
                    self.init_game(vs_ai=False)
                elif self.decline_button.is_clicked(mouse_pos, True):
                    self.network.decline_invite()

        if clicked and self.back_button.is_clicked(mouse_pos, True):
            self.network.close()
            self.state = GameState.MAIN_MENU

    def _handle_game_input(self, mouse_pos: Tuple[int, int], clicked: bool,
                          right_clicked: bool):
        """Handle in-game input."""
        world_pos = self.camera.screen_to_world(*mouse_pos)

        # Update selection rectangle
        if self.selection_start:
            x1 = min(self.selection_start[0], mouse_pos[0])
            y1 = min(self.selection_start[1], mouse_pos[1])
            x2 = max(self.selection_start[0], mouse_pos[0])
            y2 = max(self.selection_start[1], mouse_pos[1])
            self.selection_rect = pygame.Rect(x1, y1, x2 - x1, y2 - y1)

        # Building placement
        if self.placing_building and clicked:
            self._place_building(world_pos)
            return

        # Right click - move/attack
        if right_clicked and self.selected_units:
            self._issue_command(world_pos)

        # HUD click
        if clicked and mouse_pos[1] > SCREEN_HEIGHT - 100:
            self._handle_hud_click(mouse_pos)

    def _handle_game_keys(self, event: pygame.event.Event):
        """Handle game keyboard input."""
        if event.key == pygame.K_ESCAPE:
            if self.placing_building:
                self.placing_building = None
            else:
                self.state = GameState.MAIN_MENU
                self.network.close()

        # Building hotkeys
        elif event.key == pygame.K_h:
            self.placing_building = BuildingType.HOUSE
        elif event.key == pygame.K_f:
            self.placing_building = BuildingType.FARM

        # Unit training hotkeys
        elif event.key == pygame.K_p:
            self._train_unit(UnitType.PEASANT)
        elif event.key == pygame.K_k:
            self._train_unit(UnitType.KNIGHT)
        elif event.key == pygame.K_c:
            self._train_unit(UnitType.CAVALRY)
        elif event.key == pygame.K_n:
            self._train_unit(UnitType.CANNON)

        # Delete selected
        elif event.key == pygame.K_DELETE:
            for unit in self.selected_units[:]:
                if unit in self.units:
                    self.units.remove(unit)
            self.selected_units.clear()

    def _handle_hud_click(self, mouse_pos: Tuple[int, int]):
        """Handle HUD button clicks."""
        hud_y = SCREEN_HEIGHT - 90
        button_size = 60

        # Unit buttons
        unit_buttons = [
            (50, UnitType.PEASANT),
            (120, UnitType.KNIGHT),
            (190, UnitType.CAVALRY),
            (260, UnitType.CANNON),
        ]

        for bx, unit_type in unit_buttons:
            if pygame.Rect(bx, hud_y, button_size, button_size).collidepoint(mouse_pos):
                self._train_unit(unit_type)
                return

        # Building buttons
        building_buttons = [
            (350, BuildingType.HOUSE),
            (420, BuildingType.FARM),
        ]

        for bx, building_type in building_buttons:
            if pygame.Rect(bx, hud_y, button_size, button_size).collidepoint(mouse_pos):
                self.placing_building = building_type
                return

    # =========================================================================
    # SELECTION
    # =========================================================================

    def _finish_selection(self, end_pos: Tuple[int, int]):
        """Finish box selection."""
        if not self.selection_start:
            return

        # Deselect previous
        for unit in self.selected_units:
            unit.selected = False
        self.selected_units.clear()

        if self.selected_building:
            self.selected_building.selected = False
            self.selected_building = None

        # Calculate selection area in world coords
        start_world = self.camera.screen_to_world(*self.selection_start)
        end_world = self.camera.screen_to_world(*end_pos)

        x1 = min(start_world[0], end_world[0])
        y1 = min(start_world[1], end_world[1])
        x2 = max(start_world[0], end_world[0])
        y2 = max(start_world[1], end_world[1])

        selection_area = pygame.Rect(x1, y1, x2 - x1, y2 - y1)

        # Small click = single selection
        if selection_area.width < 10 and selection_area.height < 10:
            # Try to select unit
            for unit in self.units:
                if unit.team == Team.PLAYER and unit.get_rect().collidepoint(start_world):
                    unit.selected = True
                    self.selected_units.append(unit)
                    return

            # Try to select building
            for building in self.buildings:
                if building.team == Team.PLAYER and building.get_rect().collidepoint(start_world):
                    building.selected = True
                    self.selected_building = building
                    return
        else:
            # Box selection
            for unit in self.units:
                if unit.team == Team.PLAYER and selection_area.colliderect(unit.get_rect()):
                    unit.selected = True
                    self.selected_units.append(unit)

    def _issue_command(self, world_pos: Tuple[float, float]):
        """Issue move/attack command to selected units."""
        target_unit = None
        target_building = None
        friendly_building = None

        # Check for enemy unit target
        for unit in self.units:
            if unit.team == Team.ENEMY and unit.get_rect().collidepoint(world_pos):
                target_unit = unit
                break

        # Check for building target
        if not target_unit:
            for building in self.buildings:
                if building.get_rect().collidepoint(world_pos):
                    if building.team == Team.ENEMY:
                        target_building = building
                    else:
                        friendly_building = building
                    break

        # Issue commands
        for unit in self.selected_units:
            # Unassign peasant from current building when given new orders
            if unit.unit_type == UnitType.PEASANT and unit.assigned_building:
                unit.unassign_from_building()

            if target_unit:
                unit.set_attack_target(target_unit)
            elif target_building:
                unit.set_building_target(target_building)
            elif friendly_building and unit.unit_type == UnitType.PEASANT:
                # Assign peasant to work at friendly building
                unit.assign_to_building(friendly_building)
            else:
                unit.set_move_target(world_pos[0], world_pos[1])

        # Network sync
        if self.is_multiplayer and self.network.connected:
            self.network.send_unit_command(
                [u.uid for u in self.selected_units],
                world_pos,
                target_unit.uid if target_unit else None,
                target_building.uid if target_building else None
            )

    # =========================================================================
    # UNIT/BUILDING ACTIONS
    # =========================================================================

    def _train_unit(self, unit_type: UnitType):
        """Train a new unit."""
        cost_key = unit_type.name.lower()
        cost = self.mod_manager.get_unit_costs(cost_key)

        if not self.player_resources.can_afford(cost):
            return

        # Find player's castle
        castle = next(
            (b for b in self.buildings
             if b.building_type == BuildingType.CASTLE and b.team == Team.PLAYER),
            None
        )

        if not castle:
            return

        self.player_resources.spend(cost)

        # Spawn near castle
        angle = random.uniform(0, 2 * math.pi)
        x = castle.x + math.cos(angle) * 80
        y = castle.y + math.sin(angle) * 80

        unit = Unit(x, y, unit_type, Team.PLAYER, _mod_manager=self.mod_manager)
        unit.uid = self.next_uid()
        self.units.append(unit)

    def _place_building(self, world_pos: Tuple[float, float]):
        """Place a building."""
        if not self.placing_building:
            return

        cost_key = self.placing_building.name.lower()
        cost = self.mod_manager.get_building_costs(cost_key)

        if not self.player_resources.can_afford(cost):
            self.placing_building = None
            return

        self.player_resources.spend(cost)

        building = Building(
            world_pos[0], world_pos[1],
            self.placing_building, Team.PLAYER,
            _mod_manager=self.mod_manager
        )
        building.uid = self.next_uid()
        self.buildings.append(building)

        self.placing_building = None

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update(self):
        """Update game state."""
        self.dt = self.clock.tick(FPS) / 1000.0

        if self.state == GameState.PLAYING:
            self._update_game()
        elif self.state == GameState.CONNECTING:
            result = self.network.wait_for_accept()
            if result is True:
                self.init_game(vs_ai=False)
            elif result is False:
                self.state = GameState.MULTIPLAYER_LOBBY
        elif self.state == GameState.MULTIPLAYER_LOBBY:
            self.ip_input.update(self.dt)

    def _update_game(self):
        """Update game logic."""
        keys = pygame.key.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        self.camera.update(keys, self.dt, mouse_pos)

        # Update AI
        if self.ai_bot:
            self.ai_bot.update(self.dt)

        # Handle network messages
        if self.is_multiplayer:
            self._handle_network_messages()

        # Update units
        self._update_units()

        # Update worker status for peasants
        self._update_workers()

        # Update effects
        self._update_effects()

        # Update resources (based on workers)
        self._update_resources()

        # Update food consumption
        self._update_food_consumption()

        # Check win/lose
        self._check_game_over()

    def _update_units(self):
        """Update all units."""
        current_time = time.time()

        for unit in self.units[:]:
            # Movement and combat
            if unit.target_x is not None:
                if unit.target_unit and unit.target_unit.is_alive():
                    dist = unit.distance_to_unit(unit.target_unit)
                    if dist <= unit.attack_range:
                        if current_time - unit.last_attack >= unit.attack_cooldown:
                            self._do_attack(unit, unit.target_unit)
                            unit.last_attack = current_time
                    else:
                        unit.move_towards(unit.target_unit.x, unit.target_unit.y, self.dt)
                elif unit.target_building and not unit.target_building.is_destroyed():
                    dist = unit.distance_to_building(unit.target_building)
                    if dist <= unit.attack_range + 50:
                        if current_time - unit.last_attack >= unit.attack_cooldown:
                            self._do_attack_building(unit, unit.target_building)
                            unit.last_attack = current_time
                    else:
                        unit.move_towards(unit.target_building.x, unit.target_building.y, self.dt)
                else:
                    unit.move_towards(unit.target_x, unit.target_y, self.dt)

            # Auto-attack nearby enemies
            if unit.target_unit is None and unit.target_building is None:
                for other in self.units:
                    if other.team != unit.team:
                        if unit.distance_to_unit(other) <= unit.attack_range * 1.5:
                            unit.set_attack_target(other)
                            break

            # Remove dead units
            if not unit.is_alive():
                self.blood_effects.append(BloodEffect(unit.x, unit.y))
                self.units.remove(unit)
                for u in self.units:
                    if u.target_unit == unit:
                        u.target_unit = None

    def _do_attack(self, attacker: Unit, defender: Unit):
        """Perform an attack."""
        damage = max(1, attacker.attack - defender.defense // 2)
        damage = int(damage * random.uniform(0.8, 1.2))
        defender.take_damage(damage)
        self.blood_effects.append(BloodEffect(defender.x, defender.y, 0.5, 0.5))

    def _do_attack_building(self, attacker: Unit, building: Building):
        """Attack a building."""
        damage = attacker.attack
        if building.take_damage(damage):
            self.buildings.remove(building)
            for u in self.units:
                if u.target_building == building:
                    u.target_building = None

    def _update_workers(self):
        """Update worker status for all peasants."""
        for unit in self.units:
            if unit.unit_type == UnitType.PEASANT:
                # Check if assigned building still exists
                if unit.assigned_building and unit.assigned_building not in self.buildings:
                    unit.unassign_from_building()
                # Update work status
                unit.update_work_status()

    def _update_effects(self):
        """Update visual effects."""
        for effect in self.blood_effects[:]:
            if effect.update(self.dt):
                self.blood_effects.remove(effect)

    def _update_resources(self):
        """Update resource generation based on workers at buildings."""
        self.resource_timer += self.dt
        if self.resource_timer >= RESOURCE_TICK_INTERVAL:
            self.resource_timer = 0

            for building in self.buildings:
                # Get resource generation based on workers
                gen = building.get_resource_generation(self.units)

                if building.team == Team.PLAYER:
                    self.player_resources.add(
                        gold=gen.get('gold', 0),
                        food=gen.get('food', 0),
                        wood=gen.get('wood', 0)
                    )
                else:
                    self.enemy_resources.add(
                        gold=gen.get('gold', 0),
                        food=gen.get('food', 0),
                        wood=gen.get('wood', 0)
                    )

    def _update_food_consumption(self):
        """Update food consumption and starvation."""
        self.food_timer += self.dt
        if self.food_timer >= FOOD_CONSUMPTION_INTERVAL:
            self.food_timer = 0

            # Count units per team
            player_units = [u for u in self.units if u.team == Team.PLAYER]
            enemy_units = [u for u in self.units if u.team == Team.ENEMY]

            # Player food consumption
            player_food_needed = len(player_units) * FOOD_PER_UNIT
            if self.player_resources.food >= player_food_needed:
                self.player_resources.food -= player_food_needed
            else:
                # Starvation! Units take damage
                self.player_resources.food = 0
                for unit in player_units:
                    unit.take_damage(STARVATION_DAMAGE)

            # Enemy food consumption
            enemy_food_needed = len(enemy_units) * FOOD_PER_UNIT
            if self.enemy_resources.food >= enemy_food_needed:
                self.enemy_resources.food -= enemy_food_needed
            else:
                # Enemy starvation
                self.enemy_resources.food = 0
                for unit in enemy_units:
                    unit.take_damage(STARVATION_DAMAGE)

    def _handle_network_messages(self):
        """Handle incoming network messages."""
        messages = self.network.get_messages()
        for msg in messages:
            if msg['type'] == 'action':
                data = msg['data']
                if data['command'] == 'move':
                    for unit in self.units:
                        if unit.uid in data['units'] and unit.team == Team.ENEMY:
                            unit.set_move_target(*data['target'])

    def _check_game_over(self):
        """Check win/lose conditions."""
        player_castle = any(
            b for b in self.buildings
            if b.building_type == BuildingType.CASTLE and b.team == Team.PLAYER
        )
        enemy_castle = any(
            b for b in self.buildings
            if b.building_type == BuildingType.CASTLE and b.team == Team.ENEMY
        )

        if not player_castle or not enemy_castle:
            self.state = GameState.GAME_OVER

    # =========================================================================
    # DRAWING
    # =========================================================================

    def draw(self):
        """Draw the game."""
        if self.state == GameState.MAIN_MENU:
            self._draw_main_menu()
        elif self.state == GameState.PLAYING:
            self._draw_game()
        elif self.state == GameState.GAME_OVER:
            self._draw_game()
            self._draw_game_over()
        elif self.state == GameState.MULTIPLAYER_LOBBY:
            self._draw_lobby()
        elif self.state in [GameState.WAITING_FOR_ACCEPT, GameState.CONNECTING]:
            self._draw_waiting()

        pygame.display.flip()

    def _draw_main_menu(self):
        """Draw main menu."""
        self.screen.fill(DARK_GRAY)

        # Title
        title = self.title_font.render("Medieval RTS", True, GOLD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 120))
        self.screen.blit(title, title_rect)

        subtitle = self.font.render("A Real-Time Strategy Game", True, WHITE)
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 170))
        self.screen.blit(subtitle, subtitle_rect)

        # Buttons
        for button in self.menu_buttons:
            button.draw(self.screen)

        # Loaded mods info
        if self.mod_manager.loaded_mods:
            mod_text = f"Loaded mods: {len(self.mod_manager.loaded_mods)}"
            mod_surf = self.font.render(mod_text, True, LIGHT_GRAY)
            self.screen.blit(mod_surf, (10, SCREEN_HEIGHT - 30))

        # Instructions
        instructions = [
            "Controls:",
            "WASD/Arrow Keys - Move camera",
            "Left Click - Select units",
            "Right Click - Move/Attack/Assign workers",
            "H - Build House, F - Build Farm",
            "P - Train Peasant, K - Train Knight",
            "",
            "IMPORTANT: Assign peasants to buildings for production!",
            "Units consume food - build farms or starve!"
        ]

        y = 520
        for line in instructions:
            text = self.font.render(line, True, LIGHT_GRAY)
            self.screen.blit(text, (SCREEN_WIDTH // 2 - 180, y))
            y += 22

    def _draw_lobby(self):
        """Draw multiplayer lobby."""
        self.screen.fill(DARK_GRAY)

        title = self.large_font.render("Join Multiplayer Game", True, WHITE)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 200))
        self.screen.blit(title, title_rect)

        label = self.font.render("Host IP Address:", True, WHITE)
        self.screen.blit(label, (SCREEN_WIDTH // 2 - 150, 320))

        self.ip_input.draw(self.screen)
        self.connect_button.draw(self.screen)
        self.back_button.draw(self.screen)

    def _draw_waiting(self):
        """Draw waiting screen."""
        self.screen.fill(DARK_GRAY)

        if self.state == GameState.CONNECTING:
            title = self.large_font.render("Connecting...", True, WHITE)
            subtitle = self.font.render("Waiting for host to accept", True, LIGHT_GRAY)
        else:
            if self.network.pending_invite:
                title = self.large_font.render("Incoming Connection", True, WHITE)
                subtitle = self.font.render(
                    f"Player '{self.network.invite_from}' wants to join",
                    True, LIGHT_GRAY
                )
                self.accept_button.draw(self.screen)
                self.decline_button.draw(self.screen)
            else:
                title = self.large_font.render("Hosting Game", True, WHITE)
                local_ip = self.network.get_local_ip()
                subtitle = self.font.render(
                    f"Your IP: {local_ip} - Waiting for players...",
                    True, LIGHT_GRAY
                )

        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 250))
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 320))
        self.screen.blit(title, title_rect)
        self.screen.blit(subtitle, subtitle_rect)

        self.back_button.draw(self.screen)

    def _draw_game(self):
        """Draw the game world."""
        self._draw_terrain()
        self._draw_buildings()
        self._draw_effects()
        self._draw_units()
        self._draw_selection_rect()
        self._draw_building_preview()
        self._draw_hud()
        self._draw_minimap()

    def _draw_terrain(self):
        """Draw terrain tiles."""
        grass = self.assets.get('terrain_grass')

        start_x = int(self.camera.x // TILE_SIZE) * TILE_SIZE
        start_y = int(self.camera.y // TILE_SIZE) * TILE_SIZE

        for y in range(start_y, int(start_y + SCREEN_HEIGHT + TILE_SIZE * 2), TILE_SIZE):
            for x in range(start_x, int(start_x + SCREEN_WIDTH + TILE_SIZE * 2), TILE_SIZE):
                screen_pos = self.camera.world_to_screen(x, y)
                self.screen.blit(grass, screen_pos)

    def _draw_units(self):
        """Draw all units."""
        for unit in self.units:
            screen_pos = self.camera.world_to_screen(unit.x, unit.y)

            # Get sprite
            asset_name = get_unit_asset_name(unit.unit_type)
            sprite = self.assets.get(asset_name)

            # Tint enemy units
            if unit.team == Team.ENEMY:
                sprite = sprite.copy()
                sprite.fill((255, 100, 100), special_flags=pygame.BLEND_MULT)

            rect = sprite.get_rect(center=screen_pos)
            self.screen.blit(sprite, rect)

            # Selection indicator
            if unit.selected:
                pygame.draw.circle(self.screen, GREEN, screen_pos, 30, 2)

            # Working indicator for peasants
            if unit.unit_type == UnitType.PEASANT and unit.is_working:
                # Draw a small pickaxe/work icon (yellow circle)
                pygame.draw.circle(self.screen, YELLOW,
                                 (screen_pos[0] + 15, screen_pos[1] - 15), 6)
                pygame.draw.circle(self.screen, BLACK,
                                 (screen_pos[0] + 15, screen_pos[1] - 15), 6, 1)

            # Health bar
            draw_health_bar(self.screen, screen_pos, unit.health, unit.max_health, 40)

    def _draw_buildings(self):
        """Draw all buildings."""
        for building in self.buildings:
            screen_pos = self.camera.world_to_screen(building.x, building.y)

            asset_name = get_building_asset_name(building.building_type)
            sprite = self.assets.get(asset_name)

            if building.team == Team.ENEMY:
                sprite = sprite.copy()
                sprite.fill((255, 100, 100), special_flags=pygame.BLEND_MULT)

            rect = sprite.get_rect(center=screen_pos)
            self.screen.blit(sprite, rect)

            if building.selected:
                pygame.draw.rect(self.screen, GREEN, rect.inflate(10, 10), 3)

            # Draw worker count for player buildings
            if building.team == Team.PLAYER:
                workers = building.count_workers(self.units)
                max_workers = building.get_max_workers()
                if max_workers > 0:
                    # Worker indicator
                    worker_text = f"{workers}/{max_workers}"
                    color = GREEN if workers > 0 else RED
                    text_surf = self.font.render(worker_text, True, color)
                    text_rect = text_surf.get_rect(center=(screen_pos[0], screen_pos[1] + rect.height // 2 + 12))
                    # Background for readability
                    bg_rect = text_rect.inflate(4, 2)
                    pygame.draw.rect(self.screen, BLACK, bg_rect)
                    self.screen.blit(text_surf, text_rect)

            draw_health_bar(
                self.screen,
                (screen_pos[0], screen_pos[1] - rect.height // 2 - 10),
                building.health, building.max_health, rect.width
            )

    def _draw_effects(self):
        """Draw visual effects."""
        for effect in self.blood_effects:
            screen_pos = self.camera.world_to_screen(effect.x, effect.y)
            blood = self.assets.get('effect_blood').copy()
            blood.set_alpha(effect.get_alpha())
            rect = blood.get_rect(center=screen_pos)
            self.screen.blit(blood, rect)

    def _draw_selection_rect(self):
        """Draw selection rectangle."""
        if self.selection_rect and self.selection_rect.width > 5:
            pygame.draw.rect(self.screen, GREEN, self.selection_rect, 2)

    def _draw_building_preview(self):
        """Draw building placement preview."""
        if not self.placing_building:
            return

        mouse_pos = pygame.mouse.get_pos()
        asset_name = get_building_asset_name(self.placing_building)
        sprite = self.assets.get(asset_name).copy()
        sprite.set_alpha(128)

        rect = sprite.get_rect(center=mouse_pos)
        self.screen.blit(sprite, rect)

    def _draw_hud(self):
        """Draw the HUD."""
        # Bottom panel
        panel_rect = pygame.Rect(0, SCREEN_HEIGHT - 100, SCREEN_WIDTH, 100)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 2)

        # Resources
        self.resource_display.draw(
            self.screen,
            self.player_resources.gold,
            self.player_resources.food,
            self.player_resources.wood
        )

        # Unit buttons
        hud_y = SCREEN_HEIGHT - 90
        button_size = 60

        units = [
            (50, UnitType.PEASANT, 'unit_peasant', f"P: {UNIT_COSTS['peasant']['gold']}g"),
            (120, UnitType.KNIGHT, 'unit_knight', f"K: {UNIT_COSTS['knight']['gold']}g"),
            (190, UnitType.CAVALRY, 'unit_cavalry', f"C: {UNIT_COSTS['cavalry']['gold']}g"),
            (260, UnitType.CANNON, 'unit_cannon', f"N: {UNIT_COSTS['cannon']['gold']}g"),
        ]

        for bx, unit_type, asset_name, label in units:
            rect = pygame.Rect(bx, hud_y, button_size, button_size)
            pygame.draw.rect(self.screen, GRAY, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

            sprite = self.assets.get_scaled(asset_name, (40, 40))
            self.screen.blit(sprite, (bx + 10, hud_y + 5))

            label_surf = self.font.render(label, True, WHITE)
            self.screen.blit(label_surf, (bx, hud_y + 62))

        # Building buttons
        buildings = [
            (350, BuildingType.HOUSE, 'building_house', f"H: {BUILDING_COSTS['house']['gold']}g"),
            (420, BuildingType.FARM, 'building_farm', f"F: {BUILDING_COSTS['farm']['gold']}g"),
        ]

        for bx, building_type, asset_name, label in buildings:
            rect = pygame.Rect(bx, hud_y, button_size, button_size)
            color = LIGHT_GRAY if self.placing_building == building_type else GRAY
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

            sprite = self.assets.get_scaled(asset_name, (50, 50))
            self.screen.blit(sprite, (bx + 5, hud_y + 5))

            label_surf = self.font.render(label, True, WHITE)
            self.screen.blit(label_surf, (bx, hud_y + 62))

        # Selection info
        self.selection_info.draw(self.screen, self.selected_units, self.selected_building)

    def _draw_minimap(self):
        """Draw minimap."""
        camera_rect = self.camera.get_viewport_rect()
        self.minimap.draw(
            self.screen,
            self.units,
            self.buildings,
            camera_rect,
            Team.PLAYER,
            Team.ENEMY
        )

    def _draw_game_over(self):
        """Draw game over overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill(BLACK)
        overlay.set_alpha(180)
        self.screen.blit(overlay, (0, 0))

        player_castle = any(
            b for b in self.buildings
            if b.building_type == BuildingType.CASTLE and b.team == Team.PLAYER
        )

        if player_castle:
            text = "VICTORY!"
            color = GOLD
        else:
            text = "DEFEAT"
            color = RED

        title = self.title_font.render(text, True, color)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(title, title_rect)

        instruction = self.font.render("Press ESC to return to menu", True, WHITE)
        instruction_rect = instruction.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50))
        self.screen.blit(instruction, instruction_rect)

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    def run(self):
        """Main game loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()

        self.network.close()
        pygame.quit()
