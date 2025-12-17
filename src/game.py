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
    GameState, UnitType, BuildingType, Team, Difficulty, DIFFICULTY_SETTINGS,
    UNIT_COSTS, BUILDING_COSTS, RESOURCE_TICK_INTERVAL, BUILD_TIMES, DECONSTRUCT_REFUND,
    FOOD_CONSUMPTION_INTERVAL, FOOD_PER_UNIT, STARVATION_DAMAGE, WORKER_RANGE, TOWER_STATS
)
from .assets import AssetManager, ModManager, get_unit_asset_name, get_building_asset_name
from .entities import Unit, Building, BloodEffect, Resources, Projectile
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
        self.projectiles: List[Projectile] = []

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

        # Attack-move mode
        self.attack_move_mode = False

        # HUD tab state (0 = Units, 1 = Buildings)
        self.hud_tab = 0

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

        # Settings
        self.fullscreen = False
        self.selected_difficulty = Difficulty.NORMAL
        self.grid_snap = False  # Toggle for grid snapping when placing buildings
        self.grid_size = 64  # Grid cell size for snapping

        # Healing system - units consume food to heal
        self.player_healing_enabled = False
        self.enemy_healing_enabled = False
        self.heal_timer = 0.0
        self.heal_interval = 2.0  # Heal every 2 seconds when enabled
        self.heal_amount = 5  # HP healed per tick
        self.heal_food_cost = 3  # Food cost per unit healed

        # Initialize UI
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components."""
        # Main menu buttons
        self.menu_buttons = [
            Button(SCREEN_WIDTH // 2 - 150, 220, 300, 50, "Play vs AI"),
            Button(SCREEN_WIDTH // 2 - 150, 285, 300, 50, "Host Multiplayer"),
            Button(SCREEN_WIDTH // 2 - 150, 350, 300, 50, "Join Multiplayer"),
            Button(SCREEN_WIDTH // 2 - 150, 415, 300, 50, "How to Play"),
            Button(SCREEN_WIDTH // 2 - 150, 480, 300, 50, "Settings"),
            Button(SCREEN_WIDTH // 2 - 150, 545, 300, 50, "Quit")
        ]

        # How to Play back button
        self.how_to_play_back_button = Button(SCREEN_WIDTH // 2 - 75, SCREEN_HEIGHT - 60, 150, 40, "Back")

        # Difficulty selection buttons (spaced for descriptions)
        self.difficulty_buttons = [
            Button(SCREEN_WIDTH // 2 - 150, 200, 300, 45, "Easy"),
            Button(SCREEN_WIDTH // 2 - 150, 290, 300, 45, "Normal"),
            Button(SCREEN_WIDTH // 2 - 150, 380, 300, 45, "Hard"),
            Button(SCREEN_WIDTH // 2 - 150, 470, 300, 45, "Brutal"),
        ]
        self.difficulty_back_button = Button(SCREEN_WIDTH // 2 - 150, 560, 300, 45, "Back")

        # Settings buttons
        self.fullscreen_button = Button(SCREEN_WIDTH // 2 - 150, 300, 300, 50, "Fullscreen: Off")
        self.grid_snap_button = Button(SCREEN_WIDTH // 2 - 150, 370, 300, 50, "Grid Snap: Off")
        self.settings_back_button = Button(SCREEN_WIDTH // 2 - 150, 440, 300, 50, "Back")

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
        self.projectiles.clear()
        self.selected_units.clear()
        self.selected_building = None
        self.placing_building = None

        # Reset resources
        self.player_resources = Resources()
        self.enemy_resources = Resources()

        # Reset healing state
        self.player_healing_enabled = False
        self.enemy_healing_enabled = False
        self.heal_timer = 0.0

        # Reset UID counter
        self._uid_counter = 0

        # Create player base
        self._create_player_base()

        # Create enemy base
        self._create_enemy_base()

        # Setup AI or multiplayer
        if vs_ai:
            self.ai_bot = AIBot(self, self.selected_difficulty)
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
                elif self.state == GameState.GAME_OVER:
                    if event.key == pygame.K_ESCAPE:
                        self.state = GameState.MAIN_MENU
                        self.network.close()

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
        elif self.state == GameState.DIFFICULTY_SELECT:
            self._handle_difficulty_input(mouse_pos, mouse_clicked)
        elif self.state == GameState.SETTINGS:
            self._handle_settings_input(mouse_pos, mouse_clicked)
        elif self.state == GameState.HOW_TO_PLAY:
            self._handle_how_to_play_input(mouse_pos, mouse_clicked)

    def _handle_menu_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle main menu input."""
        for button in self.menu_buttons:
            button.update(mouse_pos)

        if clicked:
            if self.menu_buttons[0].is_clicked(mouse_pos, True):
                # Go to difficulty selection before starting game
                self.state = GameState.DIFFICULTY_SELECT
            elif self.menu_buttons[1].is_clicked(mouse_pos, True):
                if self.network.host_game():
                    self.state = GameState.WAITING_FOR_ACCEPT
            elif self.menu_buttons[2].is_clicked(mouse_pos, True):
                self.state = GameState.MULTIPLAYER_LOBBY
            elif self.menu_buttons[3].is_clicked(mouse_pos, True):
                self.state = GameState.HOW_TO_PLAY
            elif self.menu_buttons[4].is_clicked(mouse_pos, True):
                self.state = GameState.SETTINGS
            elif self.menu_buttons[5].is_clicked(mouse_pos, True):
                self.running = False

    def _handle_difficulty_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle difficulty selection input."""
        for button in self.difficulty_buttons:
            button.update(mouse_pos)
        self.difficulty_back_button.update(mouse_pos)

        if clicked:
            difficulties = [Difficulty.EASY, Difficulty.NORMAL, Difficulty.HARD, Difficulty.BRUTAL]
            for i, button in enumerate(self.difficulty_buttons):
                if button.is_clicked(mouse_pos, True):
                    self.selected_difficulty = difficulties[i]
                    self.init_game(vs_ai=True)
                    return

            if self.difficulty_back_button.is_clicked(mouse_pos, True):
                self.state = GameState.MAIN_MENU

    def _handle_settings_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle settings menu input."""
        self.fullscreen_button.update(mouse_pos)
        self.grid_snap_button.update(mouse_pos)
        self.settings_back_button.update(mouse_pos)

        if clicked:
            if self.fullscreen_button.is_clicked(mouse_pos, True):
                self._toggle_fullscreen()
            elif self.grid_snap_button.is_clicked(mouse_pos, True):
                self._toggle_grid_snap()
            elif self.settings_back_button.is_clicked(mouse_pos, True):
                self.state = GameState.MAIN_MENU

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
            self.fullscreen_button.text = "Fullscreen: On"
        else:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.fullscreen_button.text = "Fullscreen: Off"

    def _toggle_grid_snap(self):
        """Toggle grid snapping for building placement."""
        self.grid_snap = not self.grid_snap
        if self.grid_snap:
            self.grid_snap_button.text = "Grid Snap: On"
        else:
            self.grid_snap_button.text = "Grid Snap: Off"

    def _handle_how_to_play_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle how to play screen input."""
        self.how_to_play_back_button.update(mouse_pos)

        if clicked:
            if self.how_to_play_back_button.is_clicked(mouse_pos, True):
                self.state = GameState.MAIN_MENU

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

        # Fullscreen toggle
        elif event.key == pygame.K_F11:
            self._toggle_fullscreen()

        # Building hotkeys
        elif event.key == pygame.K_h:
            self.placing_building = BuildingType.HOUSE
        elif event.key == pygame.K_f:
            self.placing_building = BuildingType.FARM
        elif event.key == pygame.K_t:
            self.placing_building = BuildingType.TOWER

        # Grid snap toggle
        elif event.key == pygame.K_g:
            self._toggle_grid_snap()

        # Unit training hotkeys
        elif event.key == pygame.K_p:
            self._train_unit(UnitType.PEASANT)
        elif event.key == pygame.K_k:
            self._train_unit(UnitType.KNIGHT)
        elif event.key == pygame.K_c:
            self._train_unit(UnitType.CAVALRY)
        elif event.key == pygame.K_n:
            self._train_unit(UnitType.CANNON)

        # Attack-move mode
        elif event.key == pygame.K_a:
            if self.selected_units:
                self.attack_move_mode = True

        # Stop/Cancel
        elif event.key == pygame.K_s:
            self.placing_building = None
            self.attack_move_mode = False
            for unit in self.selected_units:
                unit.clear_targets()

        # Toggle healing
        elif event.key == pygame.K_h:
            self._toggle_player_healing()

        # Deconstruct selected building
        elif event.key == pygame.K_x:
            if self.selected_building and self.selected_building.team == Team.PLAYER:
                self._deconstruct_building(self.selected_building)

        # Delete selected
        elif event.key == pygame.K_DELETE:
            for unit in self.selected_units[:]:
                if unit in self.units:
                    self.units.remove(unit)
            self.selected_units.clear()

    def _handle_hud_click(self, mouse_pos: Tuple[int, int]):
        """Handle HUD button clicks."""
        hud_y = SCREEN_HEIGHT - 100
        tab_height = 25
        content_y = hud_y + tab_height + 5
        button_size = 60
        small_btn = 45

        # Tab clicks (Units / Buildings)
        tab_width = 80
        if pygame.Rect(10, hud_y, tab_width, tab_height).collidepoint(mouse_pos):
            self.hud_tab = 0  # Units tab
            return
        if pygame.Rect(95, hud_y, tab_width, tab_height).collidepoint(mouse_pos):
            self.hud_tab = 1  # Buildings tab
            return

        # Content area based on active tab
        if self.hud_tab == 0:
            # Units tab - unit training buttons
            unit_buttons = [
                (10, UnitType.PEASANT),
                (75, UnitType.KNIGHT),
                (140, UnitType.CAVALRY),
                (205, UnitType.CANNON),
            ]

            for bx, unit_type in unit_buttons:
                if pygame.Rect(bx, content_y, button_size, button_size).collidepoint(mouse_pos):
                    self._train_unit(unit_type)
                    return

        elif self.hud_tab == 1:
            # Buildings tab - building placement buttons
            building_buttons = [
                (10, BuildingType.HOUSE),
                (75, BuildingType.FARM),
                (140, BuildingType.TOWER),
            ]

            for bx, building_type in building_buttons:
                if pygame.Rect(bx, content_y, button_size, button_size).collidepoint(mouse_pos):
                    self.placing_building = building_type
                    return

            # Grid snap toggle button
            if pygame.Rect(210, content_y, button_size, button_size).collidepoint(mouse_pos):
                self._toggle_grid_snap()
                return

        # Command buttons (right side of left panel)
        cmd_x = 290

        # Attack-move button
        if pygame.Rect(cmd_x, content_y, small_btn, small_btn).collidepoint(mouse_pos):
            if self.selected_units:
                self.attack_move_mode = not self.attack_move_mode
            return

        # Deconstruct button
        if pygame.Rect(cmd_x + 50, content_y, small_btn, small_btn).collidepoint(mouse_pos):
            if self.selected_building and self.selected_building.team == Team.PLAYER:
                self._deconstruct_building(self.selected_building)
            return

        # Cancel/Stop button
        if pygame.Rect(cmd_x + 100, content_y, small_btn, small_btn).collidepoint(mouse_pos):
            self.placing_building = None
            self.attack_move_mode = False
            for unit in self.selected_units:
                unit.clear_targets()
            return

        # Heal toggle button
        if pygame.Rect(cmd_x + 150, content_y, small_btn, small_btn).collidepoint(mouse_pos):
            self._toggle_player_healing()
            return

        # Menu button
        if pygame.Rect(cmd_x + 200, content_y, small_btn, small_btn).collidepoint(mouse_pos):
            self.state = GameState.MAIN_MENU
            self.network.close()
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
        under_construction = None

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
                    elif not building.completed:
                        under_construction = building
                    else:
                        friendly_building = building
                    break

        # Issue commands
        for unit in self.selected_units:
            # Unassign peasant from current building when given new orders
            if unit.unit_type == UnitType.PEASANT and unit.assigned_building:
                unit.unassign_from_building()
            if unit.unit_type == UnitType.PEASANT and unit.constructing_building:
                unit.constructing_building = None

            if self.attack_move_mode:
                # Attack-move: move towards target, attack enemies along the way
                unit.set_attack_move_target(world_pos[0], world_pos[1])
            elif target_unit:
                unit.set_attack_target(target_unit)
            elif target_building:
                unit.set_building_target(target_building)
            elif under_construction and unit.unit_type == UnitType.PEASANT:
                # Assign peasant to construct building
                unit.constructing_building = under_construction
                unit.set_move_target(under_construction.x, under_construction.y)
            elif friendly_building and unit.unit_type == UnitType.PEASANT:
                # Assign peasant to work at friendly building
                unit.assign_to_building(friendly_building)
            else:
                unit.set_move_target(world_pos[0], world_pos[1])

        # Reset attack-move mode
        self.attack_move_mode = False

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

    def _get_building_placement_pos(self, world_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Get the placement position, with optional grid snapping."""
        x, y = world_pos
        if self.grid_snap:
            # Snap to grid
            x = round(x / self.grid_size) * self.grid_size
            y = round(y / self.grid_size) * self.grid_size
        return (x, y)

    def _can_place_building(self, world_pos: Tuple[float, float], building_type: BuildingType) -> bool:
        """Check if a building can be placed at the given position."""
        # Get building size
        sizes = {
            BuildingType.HOUSE: (80, 80),
            BuildingType.CASTLE: (128, 128),
            BuildingType.FARM: (96, 96),
            BuildingType.TOWER: (64, 64)
        }
        w, h = sizes.get(building_type, (64, 64))

        # Create a rect for the new building
        new_rect = pygame.Rect(world_pos[0] - w // 2, world_pos[1] - h // 2, w, h)

        # Check collision with existing buildings
        for building in self.buildings:
            existing_rect = building.get_rect()
            # Add a small margin to prevent buildings from touching
            existing_rect = existing_rect.inflate(10, 10)
            if new_rect.colliderect(existing_rect):
                return False

        # Check map bounds
        if (world_pos[0] - w // 2 < 0 or world_pos[0] + w // 2 > MAP_WIDTH or
            world_pos[1] - h // 2 < 0 or world_pos[1] + h // 2 > MAP_HEIGHT):
            return False

        return True

    def _place_building(self, world_pos: Tuple[float, float]):
        """Place a building foundation (requires peasant to construct)."""
        if not self.placing_building:
            return

        # Apply grid snapping if enabled
        place_pos = self._get_building_placement_pos(world_pos)

        # Check if placement is valid
        if not self._can_place_building(place_pos, self.placing_building):
            return  # Invalid placement, don't place

        cost_key = self.placing_building.name.lower()
        cost = self.mod_manager.get_building_costs(cost_key)

        if not self.player_resources.can_afford(cost):
            self.placing_building = None
            return

        self.player_resources.spend(cost)

        building = Building(
            place_pos[0], place_pos[1],
            self.placing_building, Team.PLAYER,
            _mod_manager=self.mod_manager
        )
        building.uid = self.next_uid()
        # Building starts incomplete - peasants must construct it
        building.completed = False
        building.build_progress = 0.0
        self.buildings.append(building)

        self.placing_building = None

    def _deconstruct_building(self, building: Building):
        """Deconstruct a building and refund resources."""
        if building.building_type == BuildingType.CASTLE:
            # Cannot deconstruct castle
            return

        cost_key = building.building_type.name.lower()
        cost = self.mod_manager.get_building_costs(cost_key)

        # Refund percentage of resources (scaled by remaining health)
        health_ratio = building.health / building.max_health
        refund_ratio = DECONSTRUCT_REFUND * health_ratio

        refund_gold = int(cost.get('gold', 0) * refund_ratio)
        refund_wood = int(cost.get('wood', 0) * refund_ratio)

        self.player_resources.gold += refund_gold
        self.player_resources.wood += refund_wood

        # Unassign any workers from this building
        for unit in self.units:
            if unit.assigned_building == building:
                unit.unassign_from_building()
            if unit.constructing_building == building:
                unit.constructing_building = None

        # Remove building
        self.buildings.remove(building)
        if self.selected_building == building:
            self.selected_building = None

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

        # Update unit collisions (soft push)
        self._update_unit_collisions()

        # Update worker status for peasants
        self._update_workers()

        # Update building construction
        self._update_construction()

        # Update tower attacks
        self._update_tower_attacks()

        # Update projectiles
        self._update_projectiles()

        # Update effects
        self._update_effects()

        # Update resources (based on workers)
        self._update_resources()

        # Update food consumption
        self._update_food_consumption()

        # Update unit healing
        self._update_healing()

        # Check win/lose
        self._check_game_over()

    def _update_units(self):
        """Update all units."""
        current_time = time.time()

        for unit in self.units[:]:
            # Check if unit is colliding with a building (70% slow for complete, 40% for incomplete)
            speed_mult = self._get_building_collision_slowdown(unit)

            # Movement and combat
            if unit.target_x is not None:
                if unit.target_unit and unit.target_unit.is_alive():
                    dist = unit.distance_to_unit(unit.target_unit)
                    if dist <= unit.attack_range:
                        if current_time - unit.last_attack >= unit.attack_cooldown:
                            self._do_attack(unit, unit.target_unit)
                            unit.last_attack = current_time
                    else:
                        unit.move_towards(unit.target_unit.x, unit.target_unit.y, self.dt, speed_mult)
                elif unit.target_building and not unit.target_building.is_destroyed():
                    dist = unit.distance_to_building(unit.target_building)
                    if dist <= unit.attack_range + 50:
                        if current_time - unit.last_attack >= unit.attack_cooldown:
                            self._do_attack_building(unit, unit.target_building)
                            unit.last_attack = current_time
                    else:
                        unit.move_towards(unit.target_building.x, unit.target_building.y, self.dt, speed_mult)
                else:
                    unit.move_towards(unit.target_x, unit.target_y, self.dt, speed_mult)

            # Auto-attack nearby enemies (military units are more aggressive)
            if unit.target_unit is None and unit.target_building is None:
                # Military units (knights, cavalry, cannons) have larger aggro range
                is_military = unit.unit_type in [UnitType.KNIGHT, UnitType.CAVALRY, UnitType.CANNON]
                # Attack-move units always look for targets
                is_attack_moving = unit.attack_move_target is not None
                aggro_range = unit.attack_range * 4 if is_attack_moving else (
                    unit.attack_range * 3 if is_military else unit.attack_range * 1.5
                )

                # Find nearest enemy in range
                nearest_enemy = None
                nearest_dist = float('inf')
                for other in self.units:
                    if other.team != unit.team:
                        dist = unit.distance_to_unit(other)
                        if dist <= aggro_range and dist < nearest_dist:
                            nearest_dist = dist
                            nearest_enemy = other

                if nearest_enemy:
                    # Save attack-move target so we can resume after killing
                    unit.set_attack_target(nearest_enemy)
                # Military units and attack-moving units also attack nearby buildings
                elif (is_military or is_attack_moving) and not unit.assigned_building:
                    for building in self.buildings:
                        if building.team != unit.team:
                            dist = unit.distance_to_building(building)
                            if dist <= unit.attack_range * 2:
                                unit.set_building_target(building)
                                break

            # Resume attack-move if target was killed
            if unit.attack_move_target:
                if unit.target_unit is None and unit.target_building is None:
                    # Resume moving to attack-move destination
                    if unit.target_x is None:
                        unit.target_x, unit.target_y = unit.attack_move_target
                    # Check if reached destination
                    dest_x, dest_y = unit.attack_move_target
                    if unit.distance_to(dest_x, dest_y) < 20:
                        unit.attack_move_target = None

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

        # Cannons fire projectiles instead of instant damage
        if attacker.unit_type == UnitType.CANNON:
            projectile = Projectile(
                x=attacker.x,
                y=attacker.y,
                target_x=defender.x,
                target_y=defender.y,
                speed=300.0,
                damage=damage,
                target_unit=defender,
                team=attacker.team,
                size=5
            )
            self.projectiles.append(projectile)
        else:
            defender.take_damage(damage)
            self.blood_effects.append(BloodEffect(defender.x, defender.y, 0.5, 0.5))

    def _do_attack_building(self, attacker: Unit, building: Building):
        """Attack a building."""
        damage = attacker.attack

        # Cavalry do reduced damage to buildings (50%)
        if attacker.unit_type == UnitType.CAVALRY:
            damage = damage // 2
        # Cannons do bonus damage to buildings (1.2x) and fire projectiles
        elif attacker.unit_type == UnitType.CANNON:
            damage = int(damage * 1.2)
            # Fire projectile instead of instant damage
            projectile = Projectile(
                x=attacker.x,
                y=attacker.y,
                target_x=building.x,
                target_y=building.y,
                speed=300.0,
                damage=damage,
                target_building=building,
                team=attacker.team,
                size=5
            )
            self.projectiles.append(projectile)
            return  # Don't apply instant damage

        if building.take_damage(damage):
            self.buildings.remove(building)
            for u in self.units:
                if u.target_building == building:
                    u.target_building = None

    def _get_building_collision_slowdown(self, unit: Unit) -> float:
        """Check if a unit is colliding with any building and return speed multiplier.

        Returns:
            1.0 if no collision, 0.3 for completed buildings (70% slow), 0.6 for incomplete (40% slow)
        """
        unit_radius = unit.get_collision_radius()

        for building in self.buildings:
            bw, bh = building.get_size()
            building_radius = max(bw, bh) * 0.4  # Slightly smaller than visual
            min_dist = unit_radius + building_radius

            dx = unit.x - building.x
            dy = unit.y - building.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < min_dist:
                # Completed buildings slow by 70%, incomplete by 40%
                return 0.3 if building.completed else 0.6
        return 1.0

    def _update_unit_collisions(self):
        """Apply soft collision between units to push them apart."""
        push_strength = 2.0  # How strongly units push each other

        for i, unit in enumerate(self.units):
            push_x = 0.0
            push_y = 0.0

            unit_radius = unit.get_collision_radius()

            # Check against other units
            for j, other in enumerate(self.units):
                if i >= j:  # Skip self and already-checked pairs
                    continue

                other_radius = other.get_collision_radius()
                min_dist = unit_radius + other_radius

                dx = unit.x - other.x
                dy = unit.y - other.y
                dist = math.sqrt(dx * dx + dy * dy)

                if dist < min_dist and dist > 0.1:
                    # Units are overlapping - calculate push
                    overlap = min_dist - dist
                    # Normalize direction
                    nx = dx / dist
                    ny = dy / dist
                    # Push force (stronger when more overlap)
                    push_force = overlap * push_strength * self.dt * 60

                    # Apply half push to each unit (equal and opposite)
                    half_push = push_force * 0.5
                    push_x += nx * half_push
                    push_y += ny * half_push

                    # Push the other unit in opposite direction
                    other.x -= nx * half_push
                    other.y -= ny * half_push
                    # Clamp other to map bounds
                    other.x = max(20, min(MAP_WIDTH - 20, other.x))
                    other.y = max(20, min(MAP_HEIGHT - 20, other.y))

            # Apply accumulated push (from unit-to-unit collisions only)
            unit.x += push_x
            unit.y += push_y
            # Clamp to map bounds
            unit.x = max(20, min(MAP_WIDTH - 20, unit.x))
            unit.y = max(20, min(MAP_HEIGHT - 20, unit.y))

    def _update_workers(self):
        """Update worker status for all peasants."""
        for unit in self.units:
            if unit.unit_type == UnitType.PEASANT:
                # Check if assigned building still exists
                if unit.assigned_building and unit.assigned_building not in self.buildings:
                    unit.unassign_from_building()
                # Check if constructing building still exists
                if unit.constructing_building and unit.constructing_building not in self.buildings:
                    unit.constructing_building = None
                # Update work status
                unit.update_work_status()

    def _update_construction(self):
        """Update building construction progress."""
        for building in self.buildings:
            if not building.completed and building.team == Team.PLAYER:
                # Count peasants constructing this building
                builders = 0
                for unit in self.units:
                    if (unit.unit_type == UnitType.PEASANT and
                        unit.constructing_building == building and
                        unit.distance_to_building(building) <= WORKER_RANGE):
                        builders += 1

                if builders > 0:
                    # Each builder adds progress (more builders = faster)
                    type_key = building.building_type.name.lower()
                    build_time = BUILD_TIMES.get(type_key, 10.0)
                    # Progress per second per builder (diminishing returns)
                    progress_rate = (100.0 / build_time) * (1 + 0.5 * (builders - 1))
                    building.build_progress += progress_rate * self.dt

                    if building.build_progress >= 100.0:
                        building.build_progress = 100.0
                        building.completed = True
                        # Unassign builders
                        for unit in self.units:
                            if unit.constructing_building == building:
                                unit.constructing_building = None

    def _update_tower_attacks(self):
        """Update tower attacks against enemy units."""
        current_time = time.time()

        for building in self.buildings:
            # Only completed towers can attack
            if building.building_type != BuildingType.TOWER or not building.completed:
                continue

            # Check if tower has 2 workers (required to operate)
            worker_count = building.count_workers(self.units)
            if worker_count < 2:
                continue

            # Check cooldown
            if current_time - building.last_attack < TOWER_STATS['cooldown']:
                continue

            # Find nearest enemy unit in range
            tower_range = TOWER_STATS['range']
            nearest_enemy = None
            nearest_dist = float('inf')

            for unit in self.units:
                if unit.team != building.team:
                    dx = unit.x - building.x
                    dy = unit.y - building.y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= tower_range and dist < nearest_dist:
                        nearest_dist = dist
                        nearest_enemy = unit

            # Attack if target found - spawn projectile
            if nearest_enemy:
                building.last_attack = current_time
                # Create projectile that travels to target
                projectile = Projectile(
                    x=building.x,
                    y=building.y - 30,  # Spawn from top of tower
                    target_x=nearest_enemy.x,
                    target_y=nearest_enemy.y,
                    speed=350.0,
                    damage=TOWER_STATS['attack'],
                    target_unit=nearest_enemy,
                    team=building.team,
                    size=4,
                    is_tower_projectile=True  # Tower uses hit chance
                )
                self.projectiles.append(projectile)

    def _update_projectiles(self):
        """Update all projectiles and handle hits."""
        for projectile in self.projectiles[:]:
            # Update projectile position
            hit = projectile.update(self.dt)

            if hit:
                # Projectile reached target
                self.projectiles.remove(projectile)

                # Check if target is still valid
                if projectile.target_unit and projectile.target_unit.is_alive():
                    # Tower projectiles have 70% hit chance, cannon projectiles always hit
                    should_hit = True
                    if projectile.is_tower_projectile:
                        should_hit = random.random() < TOWER_STATS['hit_chance']

                    if should_hit:
                        if projectile.target_unit.take_damage(projectile.damage):
                            # Target killed
                            self.blood_effects.append(BloodEffect(projectile.target_unit.x, projectile.target_unit.y))
                            if projectile.target_unit in self.units:
                                self.units.remove(projectile.target_unit)
                                for u in self.units:
                                    if u.target_unit == projectile.target_unit:
                                        u.target_unit = None
                        else:
                            # Hit but not killed
                            self.blood_effects.append(BloodEffect(projectile.target_unit.x, projectile.target_unit.y, 0.5, 0.5))

                elif projectile.target_building and not projectile.target_building.is_destroyed():
                    # Cannon projectile hitting building
                    if projectile.target_building.take_damage(projectile.damage):
                        if projectile.target_building in self.buildings:
                            self.buildings.remove(projectile.target_building)
                            for u in self.units:
                                if u.target_building == projectile.target_building:
                                    u.target_building = None

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
                # Only completed buildings generate resources
                if not building.completed:
                    continue

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

    def _update_healing(self):
        """Update unit healing for both teams."""
        self.heal_timer += self.dt
        if self.heal_timer < self.heal_interval:
            return
        self.heal_timer = 0

        # Player healing
        if self.player_healing_enabled:
            player_units = [u for u in self.units if u.team == Team.PLAYER and u.needs_healing()]
            for unit in player_units:
                if self.player_resources.food >= self.heal_food_cost:
                    if unit.heal(self.heal_amount):
                        self.player_resources.food -= self.heal_food_cost

        # Enemy healing
        if self.enemy_healing_enabled:
            enemy_units = [u for u in self.units if u.team == Team.ENEMY and u.needs_healing()]
            for unit in enemy_units:
                if self.enemy_resources.food >= self.heal_food_cost:
                    if unit.heal(self.heal_amount):
                        self.enemy_resources.food -= self.heal_food_cost

    def _toggle_player_healing(self):
        """Toggle player healing on/off."""
        self.player_healing_enabled = not self.player_healing_enabled

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
        elif self.state == GameState.DIFFICULTY_SELECT:
            self._draw_difficulty_select()
        elif self.state == GameState.SETTINGS:
            self._draw_settings()
        elif self.state == GameState.HOW_TO_PLAY:
            self._draw_how_to_play()

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

    def _draw_difficulty_select(self):
        """Draw difficulty selection screen."""
        self.screen.fill(DARK_GRAY)

        # Title
        title = self.large_font.render("Select Difficulty", True, WHITE)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)

        # Difficulty buttons with descriptions
        descriptions = [
            "Easy - Slow AI, fewer enemies, less aggressive",
            "Normal - Balanced gameplay experience",
            "Hard - Fast AI, resource bonuses, very aggressive",
            "Brutal - Maximum challenge, overwhelming force"
        ]

        for i, button in enumerate(self.difficulty_buttons):
            button.draw(self.screen)
            # Draw description below each button
            desc = self.font.render(descriptions[i], True, LIGHT_GRAY)
            desc_rect = desc.get_rect(center=(SCREEN_WIDTH // 2, button.rect.bottom + 15))
            self.screen.blit(desc, desc_rect)

        self.difficulty_back_button.draw(self.screen)

    def _draw_settings(self):
        """Draw settings menu."""
        self.screen.fill(DARK_GRAY)

        # Title
        title = self.large_font.render("Settings", True, WHITE)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 200))
        self.screen.blit(title, title_rect)

        # Fullscreen button
        self.fullscreen_button.draw(self.screen)

        # Grid snap button
        self.grid_snap_button.draw(self.screen)

        # Back button
        self.settings_back_button.draw(self.screen)

        # Instructions
        hint = self.font.render("Press F11 in-game to toggle fullscreen", True, LIGHT_GRAY)
        hint_rect = hint.get_rect(center=(SCREEN_WIDTH // 2, 540))
        self.screen.blit(hint, hint_rect)

        hint2 = self.font.render("Press G in-game to toggle grid snapping", True, LIGHT_GRAY)
        hint2_rect = hint2.get_rect(center=(SCREEN_WIDTH // 2, 565))
        self.screen.blit(hint2, hint2_rect)

    def _draw_how_to_play(self):
        """Draw how to play screen with game instructions."""
        self.screen.fill(DARK_GRAY)

        # Title
        title = self.large_font.render("How to Play", True, GOLD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 40))
        self.screen.blit(title, title_rect)

        # Two-column layout
        left_x = 60
        right_x = SCREEN_WIDTH // 2 + 40
        y_start = 80

        # Left column - Controls
        y = y_start
        self.screen.blit(self.large_font.render("Controls", True, WHITE), (left_x, y))
        y += 40

        controls = [
            ("Camera", "WASD / Arrow Keys / Mouse Edge"),
            ("Select Units", "Left Click / Drag Box"),
            ("Move/Attack", "Right Click"),
            ("Attack-Move", "A + Right Click"),
            ("Stop/Cancel", "S"),
            ("", ""),
            ("Train Peasant", "P"),
            ("Train Knight", "K"),
            ("Train Cavalry", "C"),
            ("Train Cannon", "N"),
            ("", ""),
            ("Build House", "H"),
            ("Build Farm", "F"),
            ("Build Tower", "T"),
            ("Grid Snap", "G"),
            ("Deconstruct", "X"),
            ("", ""),
            ("Fullscreen", "F11"),
            ("Return to Menu", "ESC"),
        ]

        for action, key in controls:
            if action:
                action_surf = self.font.render(action, True, LIGHT_GRAY)
                key_surf = self.font.render(key, True, WHITE)
                self.screen.blit(action_surf, (left_x, y))
                self.screen.blit(key_surf, (left_x + 140, y))
            y += 22

        # Right column - Game Mechanics
        y = y_start
        self.screen.blit(self.large_font.render("Game Mechanics", True, WHITE), (right_x, y))
        y += 40

        mechanics = [
            "OBJECTIVE:",
            "  Destroy the enemy castle to win!",
            "",
            "RESOURCES:",
            "  Gold - Used for all units/buildings",
            "  Food - Consumed by units over time",
            "  Wood - Used for buildings and cannons",
            "",
            "BUILDINGS:",
            "  Castle - Train units (starting building)",
            "  House - Workers generate gold",
            "  Farm - Workers generate food & wood",
            "  Tower - Attacks enemies (needs 2 workers)",
            "",
            "CONSTRUCTION:",
            "  1. Click building button (H/F/T)",
            "  2. Click to place foundation",
            "  3. Right-click peasant on foundation",
            "  4. Peasant will construct building",
            "",
            "WORKERS:",
            "  Right-click peasant on completed building",
            "  to assign as worker for resources.",
            "",
            "STARVATION:",
            "  If food runs out, units take damage!",
            "  Build farms and assign workers!",
        ]

        for line in mechanics:
            color = GOLD if line.endswith(":") else LIGHT_GRAY
            text_surf = self.font.render(line, True, color)
            self.screen.blit(text_surf, (right_x, y))
            y += 20

        # Back button
        self.how_to_play_back_button.draw(self.screen)

    def _draw_game(self):
        """Draw the game world."""
        self._draw_terrain()
        self._draw_buildings()
        self._draw_effects()
        self._draw_projectiles()
        self._draw_units()
        self._draw_movement_lines()
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

            # Construction indicator for peasants
            if unit.unit_type == UnitType.PEASANT and unit.constructing_building:
                # Draw hammer icon (brown circle with outline)
                pygame.draw.circle(self.screen, BROWN,
                                 (screen_pos[0] + 15, screen_pos[1] - 15), 6)
                pygame.draw.circle(self.screen, BLACK,
                                 (screen_pos[0] + 15, screen_pos[1] - 15), 6, 1)

            # Attack-move indicator
            if unit.attack_move_target:
                pygame.draw.circle(self.screen, RED, screen_pos, 25, 2)

            # Health bar
            draw_health_bar(self.screen, screen_pos, unit.health, unit.max_health, 40)

    def _draw_buildings(self):
        """Draw all buildings."""
        for building in self.buildings:
            screen_pos = self.camera.world_to_screen(building.x, building.y)

            asset_name = get_building_asset_name(building.building_type)
            sprite = self.assets.get(asset_name).copy()

            # Make incomplete buildings semi-transparent
            if not building.completed:
                sprite.set_alpha(128)

            if building.team == Team.ENEMY:
                sprite.fill((255, 100, 100), special_flags=pygame.BLEND_MULT)

            rect = sprite.get_rect(center=screen_pos)
            self.screen.blit(sprite, rect)

            if building.selected:
                pygame.draw.rect(self.screen, GREEN, rect.inflate(10, 10), 3)

            # Draw construction progress for incomplete buildings
            if not building.completed and building.team == Team.PLAYER:
                # Progress bar
                bar_width = rect.width
                bar_height = 8
                bar_x = screen_pos[0] - bar_width // 2
                bar_y = screen_pos[1] + rect.height // 2 + 5
                # Background
                pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, bar_width, bar_height))
                # Progress fill
                progress_width = int(bar_width * building.build_progress / 100)
                pygame.draw.rect(self.screen, YELLOW, (bar_x, bar_y, progress_width, bar_height))
                # Border
                pygame.draw.rect(self.screen, BLACK, (bar_x, bar_y, bar_width, bar_height), 1)
                # Text
                progress_text = f"{int(building.build_progress)}%"
                text_surf = self.font.render(progress_text, True, WHITE)
                text_rect = text_surf.get_rect(center=(screen_pos[0], bar_y + bar_height + 10))
                self.screen.blit(text_surf, text_rect)
            # Draw worker count for completed player buildings
            elif building.team == Team.PLAYER and building.completed:
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

    def _draw_projectiles(self):
        """Draw all projectiles as small black dots."""
        for projectile in self.projectiles:
            screen_pos = self.camera.world_to_screen(projectile.x, projectile.y)
            pygame.draw.circle(self.screen, BLACK, screen_pos, projectile.size)

    def _draw_movement_lines(self):
        """Draw 80% transparent white lines showing where selected units are moving."""
        if not self.selected_units:
            return

        # Create a single surface for all movement lines (more efficient)
        line_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        line_color = (255, 255, 255, 51)  # 80% transparent white (alpha = 51)

        for unit in self.selected_units:
            # Determine the target position
            target_x, target_y = None, None

            if unit.target_unit and unit.target_unit.is_alive():
                # Moving to attack a unit
                target_x, target_y = unit.target_unit.x, unit.target_unit.y
            elif unit.target_building and not unit.target_building.is_destroyed():
                # Moving to attack/interact with a building
                target_x, target_y = unit.target_building.x, unit.target_building.y
            elif unit.attack_move_target:
                # Attack-move destination
                target_x, target_y = unit.attack_move_target
            elif unit.target_x is not None and unit.target_y is not None:
                # Simple move target
                target_x, target_y = unit.target_x, unit.target_y

            if target_x is not None and target_y is not None:
                # Convert to screen coordinates
                start_pos = self.camera.world_to_screen(unit.x, unit.y)
                end_pos = self.camera.world_to_screen(target_x, target_y)

                # Draw line from unit to destination
                pygame.draw.line(line_surface, line_color, start_pos, end_pos, 2)

                # Draw a small circle at the destination
                pygame.draw.circle(line_surface, line_color, end_pos, 8, 2)

        # Blit the line surface once
        self.screen.blit(line_surface, (0, 0))

    def _draw_selection_rect(self):
        """Draw selection rectangle."""
        if self.selection_rect and self.selection_rect.width > 5:
            pygame.draw.rect(self.screen, GREEN, self.selection_rect, 2)

    def _draw_building_preview(self):
        """Draw building placement preview with validity indicator."""
        if not self.placing_building:
            return

        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(*mouse_pos)

        # Apply grid snapping if enabled
        place_pos = self._get_building_placement_pos(world_pos)
        screen_pos = self.camera.world_to_screen(*place_pos)

        # Check if placement is valid
        can_place = self._can_place_building(place_pos, self.placing_building)

        asset_name = get_building_asset_name(self.placing_building)
        sprite = self.assets.get(asset_name).copy()
        sprite.set_alpha(160)

        # Tint based on validity
        if can_place:
            # Green tint for valid placement
            sprite.fill((100, 255, 100), special_flags=pygame.BLEND_MULT)
        else:
            # Red tint for invalid placement
            sprite.fill((255, 100, 100), special_flags=pygame.BLEND_MULT)

        rect = sprite.get_rect(center=screen_pos)
        self.screen.blit(sprite, rect)

        # Draw outline
        outline_color = GREEN if can_place else RED
        pygame.draw.rect(self.screen, outline_color, rect.inflate(4, 4), 2)

        # Draw grid lines if grid snap is enabled
        if self.grid_snap:
            # Draw nearby grid lines faintly
            grid_color = (100, 100, 100, 100)
            cam_x, cam_y = int(self.camera.x), int(self.camera.y)
            # Calculate visible grid area
            start_grid_x = (cam_x // self.grid_size) * self.grid_size
            start_grid_y = (cam_y // self.grid_size) * self.grid_size
            # Draw only a few grid lines around the mouse position for clarity
            for gx in range(int(start_grid_x), int(start_grid_x + SCREEN_WIDTH + self.grid_size * 2), self.grid_size):
                sx, _ = self.camera.world_to_screen(gx, 0)
                pygame.draw.line(self.screen, DARK_GRAY, (sx, 0), (sx, SCREEN_HEIGHT - 100), 1)
            for gy in range(int(start_grid_y), int(start_grid_y + SCREEN_HEIGHT + self.grid_size * 2), self.grid_size):
                _, sy = self.camera.world_to_screen(0, gy)
                pygame.draw.line(self.screen, DARK_GRAY, (0, sy), (SCREEN_WIDTH, sy), 1)

    def _draw_hud(self):
        """Draw the HUD with tabbed interface."""
        hud_y = SCREEN_HEIGHT - 100
        tab_height = 25
        content_y = hud_y + tab_height + 5
        button_size = 60
        small_btn = 45

        # Bottom panel background
        panel_rect = pygame.Rect(0, hud_y, SCREEN_WIDTH, 100)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 2)

        # === LEFT SECTION: Tabbed Build Menu (0-480px) ===
        left_panel = pygame.Rect(0, hud_y, 480, 100)
        pygame.draw.rect(self.screen, (50, 50, 60), left_panel)
        pygame.draw.rect(self.screen, BLACK, left_panel, 2)

        # Tab buttons
        tab_width = 80
        tab_names = ["Units", "Build"]
        for i, name in enumerate(tab_names):
            tab_x = 10 + i * 85
            tab_rect = pygame.Rect(tab_x, hud_y + 2, tab_width, tab_height)
            tab_color = GRAY if self.hud_tab == i else DARK_GRAY
            pygame.draw.rect(self.screen, tab_color, tab_rect)
            pygame.draw.rect(self.screen, BLACK, tab_rect, 1)
            tab_text = self.font.render(name, True, WHITE if self.hud_tab == i else LIGHT_GRAY)
            text_rect = tab_text.get_rect(center=tab_rect.center)
            self.screen.blit(tab_text, text_rect)

        # Tab content
        if self.hud_tab == 0:
            # Units tab - unit training buttons
            units = [
                (10, UnitType.PEASANT, 'unit_peasant', f"{UNIT_COSTS['peasant']['gold']}g"),
                (75, UnitType.KNIGHT, 'unit_knight', f"{UNIT_COSTS['knight']['gold']}g"),
                (140, UnitType.CAVALRY, 'unit_cavalry', f"{UNIT_COSTS['cavalry']['gold']}g"),
                (205, UnitType.CANNON, 'unit_cannon', f"{UNIT_COSTS['cannon']['gold']}g"),
            ]

            for bx, unit_type, asset_name, label in units:
                rect = pygame.Rect(bx, content_y, button_size, button_size)
                pygame.draw.rect(self.screen, GRAY, rect)
                pygame.draw.rect(self.screen, BLACK, rect, 2)

                sprite = self.assets.get_scaled(asset_name, (40, 40))
                self.screen.blit(sprite, (bx + 10, content_y + 5))

                label_surf = self.font.render(label, True, WHITE)
                self.screen.blit(label_surf, (bx + 5, content_y + 47))

        elif self.hud_tab == 1:
            # Buildings tab - building placement buttons
            buildings = [
                (10, BuildingType.HOUSE, 'building_house', f"{BUILDING_COSTS['house']['gold']}g"),
                (75, BuildingType.FARM, 'building_farm', f"{BUILDING_COSTS['farm']['gold']}g"),
                (140, BuildingType.TOWER, 'building_tower', f"{BUILDING_COSTS['tower']['gold']}g"),
            ]

            for bx, building_type, asset_name, label in buildings:
                rect = pygame.Rect(bx, content_y, button_size, button_size)
                color = LIGHT_GRAY if self.placing_building == building_type else GRAY
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, BLACK, rect, 2)

                sprite = self.assets.get_scaled(asset_name, (50, 50))
                self.screen.blit(sprite, (bx + 5, content_y + 2))

                label_surf = self.font.render(label, True, WHITE)
                self.screen.blit(label_surf, (bx + 5, content_y + 47))

            # Grid snap toggle button
            grid_rect = pygame.Rect(210, content_y, button_size, button_size)
            grid_color = GREEN if self.grid_snap else GRAY
            pygame.draw.rect(self.screen, grid_color, grid_rect)
            pygame.draw.rect(self.screen, BLACK, grid_rect, 2)
            grid_text = self.font.render("GRID", True, WHITE)
            self.screen.blit(grid_text, (215, content_y + 10))
            snap_text = self.font.render("G", True, LIGHT_GRAY)
            self.screen.blit(snap_text, (233, content_y + 32))
            # Show On/Off status
            status_text = self.font.render("On" if self.grid_snap else "Off", True, WHITE)
            self.screen.blit(status_text, (223, content_y + 47))

        # Command buttons (right side of left panel)
        cmd_x = 290

        # Attack-move button (A)
        atk_rect = pygame.Rect(cmd_x, content_y, small_btn, small_btn)
        atk_color = RED if self.attack_move_mode else GRAY
        pygame.draw.rect(self.screen, atk_color, atk_rect)
        pygame.draw.rect(self.screen, BLACK, atk_rect, 2)
        atk_text = self.font.render("ATK", True, WHITE)
        self.screen.blit(atk_text, (cmd_x + 8, content_y + 14))
        self.screen.blit(self.font.render("A", True, LIGHT_GRAY), (cmd_x + 18, content_y + 32))

        # Deconstruct button (X)
        dec_rect = pygame.Rect(cmd_x + 50, content_y, small_btn, small_btn)
        dec_enabled = self.selected_building and self.selected_building.team == Team.PLAYER and self.selected_building.building_type != BuildingType.CASTLE
        dec_color = BROWN if dec_enabled else DARK_GRAY
        pygame.draw.rect(self.screen, dec_color, dec_rect)
        pygame.draw.rect(self.screen, BLACK, dec_rect, 2)
        dec_text = self.font.render("DEL", True, WHITE if dec_enabled else GRAY)
        self.screen.blit(dec_text, (cmd_x + 58, content_y + 14))
        self.screen.blit(self.font.render("X", True, LIGHT_GRAY), (cmd_x + 68, content_y + 32))

        # Cancel/Stop button (S)
        stop_rect = pygame.Rect(cmd_x + 100, content_y, small_btn, small_btn)
        pygame.draw.rect(self.screen, GRAY, stop_rect)
        pygame.draw.rect(self.screen, BLACK, stop_rect, 2)
        stop_text = self.font.render("STP", True, WHITE)
        self.screen.blit(stop_text, (cmd_x + 108, content_y + 14))
        self.screen.blit(self.font.render("S", True, LIGHT_GRAY), (cmd_x + 118, content_y + 32))

        # Heal toggle button (H)
        heal_rect = pygame.Rect(cmd_x + 150, content_y, small_btn, small_btn)
        heal_color = GREEN if self.player_healing_enabled else GRAY
        pygame.draw.rect(self.screen, heal_color, heal_rect)
        pygame.draw.rect(self.screen, BLACK, heal_rect, 2)
        heal_text = self.font.render("HEL", True, WHITE)
        self.screen.blit(heal_text, (cmd_x + 156, content_y + 14))
        self.screen.blit(self.font.render("H", True, LIGHT_GRAY), (cmd_x + 168, content_y + 32))

        # Menu button (ESC)
        menu_rect = pygame.Rect(cmd_x + 200, content_y, small_btn, small_btn)
        pygame.draw.rect(self.screen, GRAY, menu_rect)
        pygame.draw.rect(self.screen, BLACK, menu_rect, 2)
        menu_text = self.font.render("ESC", True, WHITE)
        self.screen.blit(menu_text, (cmd_x + 206, content_y + 14))

        # === CENTER SECTION: Resources (480-700px) ===
        res_x = 495
        res_y = hud_y + 10
        gold_text = self.font.render(f"Gold: {self.player_resources.gold}", True, GOLD)
        food_text = self.font.render(f"Food: {self.player_resources.food}", True, GREEN)
        wood_text = self.font.render(f"Wood: {self.player_resources.wood}", True, BROWN)
        self.screen.blit(gold_text, (res_x, res_y))
        self.screen.blit(food_text, (res_x, res_y + 25))
        self.screen.blit(wood_text, (res_x, res_y + 50))

        # Separator line
        pygame.draw.line(self.screen, BLACK, (620, hud_y + 5), (620, hud_y + 95), 2)

        # === RIGHT SECTION: Selection Info (700-1280px) ===
        self._draw_selection_info()

    def _draw_selection_info(self):
        """Draw selection information on the HUD."""
        info_x = 640
        info_y = SCREEN_HEIGHT - 90

        if self.selected_units:
            count = len(self.selected_units)
            text = f"Selected: {count} unit{'s' if count > 1 else ''}"
            self.screen.blit(self.font.render(text, True, WHITE), (info_x, info_y))

            # Show unit types
            types = {}
            for unit in self.selected_units:
                name = unit.unit_type.name.title()
                types[name] = types.get(name, 0) + 1
            y = info_y + 20
            for name, cnt in list(types.items())[:3]:  # Max 3 types to fit
                self.screen.blit(self.font.render(f"  {name}: {cnt}", True, LIGHT_GRAY), (info_x, y))
                y += 16

        elif self.selected_building:
            name = self.selected_building.building_type.name.title()
            health = f"{self.selected_building.health}/{self.selected_building.max_health}"
            self.screen.blit(self.font.render(name, True, WHITE), (info_x, info_y))
            self.screen.blit(self.font.render(f"HP: {health}", True, LIGHT_GRAY), (info_x, info_y + 18))
            if not self.selected_building.completed:
                prog = f"Building: {int(self.selected_building.build_progress)}%"
                self.screen.blit(self.font.render(prog, True, YELLOW), (info_x, info_y + 36))
            elif self.selected_building.building_type != BuildingType.CASTLE:
                workers = self.selected_building.count_workers(self.units)
                max_w = self.selected_building.get_max_workers()
                self.screen.blit(self.font.render(f"Workers: {workers}/{max_w}", True, LIGHT_GRAY), (info_x, info_y + 36))
                # Tower special info
                if self.selected_building.building_type == BuildingType.TOWER:
                    status = "Active" if workers >= 2 else "Needs 2 workers"
                    color = GREEN if workers >= 2 else RED
                    self.screen.blit(self.font.render(status, True, color), (info_x, info_y + 54))
        else:
            self.screen.blit(self.font.render("No selection", True, GRAY), (info_x, info_y))

        # Show attack-move hint (on far right)
        if self.attack_move_mode:
            hint = self.font.render("ATTACK-MOVE: Right-click", True, RED)
            self.screen.blit(hint, (info_x, info_y + 72))

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
