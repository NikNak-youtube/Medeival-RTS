"""
Medieval RTS Game
A real-time strategy game with single player (vs AI) and multiplayer support.
"""

import pygame
import math
import random
import socket
import threading
import json
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
import struct

# Initialize Pygame
pygame.init()
pygame.font.init()

# =============================================================================
# CONSTANTS
# =============================================================================

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
MAP_WIDTH = 2000
MAP_HEIGHT = 2000
TILE_SIZE = 64
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 50, 50)
BLUE = (50, 50, 200)
GREEN = (50, 200, 50)
YELLOW = (200, 200, 50)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)
BROWN = (139, 90, 43)
GOLD = (255, 215, 0)
DARK_GREEN = (34, 139, 34)

# Network
DEFAULT_PORT = 5555
BUFFER_SIZE = 4096

# Game balance
STARTING_GOLD = 500
STARTING_FOOD = 200
STARTING_WOOD = 300

# Unit costs
UNIT_COSTS = {
    'peasant': {'gold': 50, 'food': 25},
    'knight': {'gold': 150, 'food': 50},
    'cavalry': {'gold': 200, 'food': 75},
    'cannon': {'gold': 300, 'food': 0}
}

# Building costs
BUILDING_COSTS = {
    'house': {'gold': 100, 'wood': 50},
    'castle': {'gold': 500, 'wood': 200},
    'farm': {'gold': 75, 'wood': 25}
}

# =============================================================================
# ENUMS
# =============================================================================

class GameState(Enum):
    MAIN_MENU = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()
    MULTIPLAYER_LOBBY = auto()
    CONNECTING = auto()
    WAITING_FOR_ACCEPT = auto()

class UnitType(Enum):
    PEASANT = auto()
    KNIGHT = auto()
    CAVALRY = auto()
    CANNON = auto()

class BuildingType(Enum):
    HOUSE = auto()
    CASTLE = auto()
    FARM = auto()

class Team(Enum):
    PLAYER = auto()
    ENEMY = auto()

# =============================================================================
# ASSET MANAGER
# =============================================================================

class AssetManager:
    """Manages loading and caching of game assets."""

    def __init__(self):
        self.images: Dict[str, pygame.Surface] = {}
        self.load_assets()

    def load_assets(self):
        """Load all game assets from the images folder."""
        base_path = "images/"

        # Load and scale assets
        asset_map = {
            'knight': ('medival_knight_PNG15938-1540327347.png', (48, 64)),
            'peasant': ('medieval-peasant-clothing-png-ujr66-mwoizzpaozyw3l2a-1145509706.png', (40, 56)),
            'horse': ('bay-sport-horse-isolated-on-transparent-background-generate-ai-free-png-4198957791.png', (64, 56)),
            'house': ('pngtree-3d-medieval-house-png-image_13118176-4238177977.png', (80, 80)),
            'castle': ('ancient-stone-castle-transparent-background_1101614-40027-3216294613.jpg', (128, 128)),
            'grass': ('tileable_grass_01-1560797743.png', (TILE_SIZE, TILE_SIZE)),
            'stone': ('Stone_Floor-2623938694.png', (TILE_SIZE, TILE_SIZE)),
            'farm': ('farmland.png', (96, 96)),
            'cannon': ('medieval-cannon-3d-elements-transparent-background-png-2980523749.png', (56, 48)),
            'blood': ('Blood-Splatter-Transparent-File-3969082743.png', (32, 32))
        }

        for name, (filename, size) in asset_map.items():
            try:
                img = pygame.image.load(base_path + filename).convert_alpha()
                self.images[name] = pygame.transform.scale(img, size)
            except pygame.error as e:
                print(f"Warning: Could not load {filename}: {e}")
                # Create placeholder
                self.images[name] = self._create_placeholder(size, name)

    def _create_placeholder(self, size: Tuple[int, int], name: str) -> pygame.Surface:
        """Create a placeholder surface for missing assets."""
        surf = pygame.Surface(size, pygame.SRCALPHA)
        color = {
            'knight': BLUE,
            'peasant': BROWN,
            'horse': BROWN,
            'house': GRAY,
            'castle': DARK_GRAY,
            'grass': GREEN,
            'stone': GRAY,
            'farm': DARK_GREEN,
            'cannon': DARK_GRAY,
            'blood': RED
        }.get(name, WHITE)
        surf.fill(color)
        return surf

    def get(self, name: str) -> pygame.Surface:
        """Get an asset by name."""
        return self.images.get(name, self._create_placeholder((32, 32), 'unknown'))

# =============================================================================
# GAME ENTITIES
# =============================================================================

@dataclass
class Unit:
    """Represents a game unit."""
    x: float
    y: float
    unit_type: UnitType
    team: Team
    health: int = 100
    max_health: int = 100
    attack: int = 10
    defense: int = 5
    speed: float = 2.0
    attack_range: int = 30
    attack_cooldown: float = 1.0
    last_attack: float = 0
    selected: bool = False
    target_x: Optional[float] = None
    target_y: Optional[float] = None
    target_unit: Optional['Unit'] = None
    target_building: Optional['Building'] = None
    uid: int = 0

    def __post_init__(self):
        stats = {
            UnitType.PEASANT: {'health': 50, 'attack': 5, 'defense': 2, 'speed': 2.5, 'range': 20},
            UnitType.KNIGHT: {'health': 150, 'attack': 20, 'defense': 15, 'speed': 1.8, 'range': 35},
            UnitType.CAVALRY: {'health': 120, 'attack': 25, 'defense': 10, 'speed': 4.0, 'range': 40},
            UnitType.CANNON: {'health': 80, 'attack': 50, 'defense': 5, 'speed': 1.0, 'range': 200}
        }
        s = stats.get(self.unit_type, stats[UnitType.PEASANT])
        self.health = self.max_health = s['health']
        self.attack = s['attack']
        self.defense = s['defense']
        self.speed = s['speed']
        self.attack_range = s['range']

    def get_rect(self) -> pygame.Rect:
        """Get unit collision rectangle."""
        size = 48 if self.unit_type == UnitType.CAVALRY else 40
        return pygame.Rect(self.x - size//2, self.y - size//2, size, size)

    def distance_to(self, other_x: float, other_y: float) -> float:
        """Calculate distance to a point."""
        return math.sqrt((self.x - other_x)**2 + (self.y - other_y)**2)

    def move_towards(self, target_x: float, target_y: float, dt: float):
        """Move towards a target position."""
        dist = self.distance_to(target_x, target_y)
        if dist > 5:
            dx = (target_x - self.x) / dist
            dy = (target_y - self.y) / dist
            self.x += dx * self.speed * dt * 60
            self.y += dy * self.speed * dt * 60
            # Clamp to map bounds
            self.x = max(20, min(MAP_WIDTH - 20, self.x))
            self.y = max(20, min(MAP_HEIGHT - 20, self.y))
        else:
            self.target_x = None
            self.target_y = None


@dataclass
class Building:
    """Represents a game building."""
    x: float
    y: float
    building_type: BuildingType
    team: Team
    health: int = 500
    max_health: int = 500
    selected: bool = False
    completed: bool = True
    build_progress: float = 100.0
    uid: int = 0

    def __post_init__(self):
        stats = {
            BuildingType.HOUSE: {'health': 300},
            BuildingType.CASTLE: {'health': 1000},
            BuildingType.FARM: {'health': 200}
        }
        s = stats.get(self.building_type, stats[BuildingType.HOUSE])
        self.health = self.max_health = s['health']

    def get_rect(self) -> pygame.Rect:
        """Get building collision rectangle."""
        sizes = {
            BuildingType.HOUSE: (80, 80),
            BuildingType.CASTLE: (128, 128),
            BuildingType.FARM: (96, 96)
        }
        w, h = sizes.get(self.building_type, (64, 64))
        return pygame.Rect(self.x - w//2, self.y - h//2, w, h)


@dataclass
class BloodEffect:
    """Visual effect for combat."""
    x: float
    y: float
    lifetime: float = 1.0
    alpha: int = 255


@dataclass
class Resources:
    """Player resources."""
    gold: int = STARTING_GOLD
    food: int = STARTING_FOOD
    wood: int = STARTING_WOOD


# =============================================================================
# CAMERA
# =============================================================================

class Camera:
    """Handles viewport and map scrolling."""

    def __init__(self, width: int, height: int):
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height
        self.speed = 10
        self.zoom = 1.0

    def update(self, keys, dt: float):
        """Update camera position based on input."""
        move_speed = self.speed * dt * 60
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.x -= move_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x += move_speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.y -= move_speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.y += move_speed

        # Edge scrolling
        mouse_x, mouse_y = pygame.mouse.get_pos()
        edge_margin = 20
        if mouse_x < edge_margin:
            self.x -= move_speed
        elif mouse_x > self.width - edge_margin:
            self.x += move_speed
        if mouse_y < edge_margin:
            self.y -= move_speed
        elif mouse_y > self.height - edge_margin:
            self.y += move_speed

        # Clamp to map bounds
        self.x = max(0, min(MAP_WIDTH - self.width, self.x))
        self.y = max(0, min(MAP_HEIGHT - self.height, self.y))

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        return (int(x - self.x), int(y - self.y))

    def screen_to_world(self, x: int, y: int) -> Tuple[float, float]:
        """Convert screen coordinates to world coordinates."""
        return (x + self.x, y + self.y)

    def is_visible(self, rect: pygame.Rect) -> bool:
        """Check if a rectangle is visible on screen."""
        screen_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        return screen_rect.colliderect(rect)


# =============================================================================
# AI BOT
# =============================================================================

class AIBot:
    """AI opponent for single player mode."""

    def __init__(self, game: 'Game'):
        self.game = game
        self.think_timer = 0
        self.think_interval = 2.0  # Think every 2 seconds
        self.aggression = 0.5
        self.build_queue: List[str] = []
        self.unit_queue: List[str] = []
        self.attack_target: Optional[Tuple[float, float]] = None
        self.state = 'building'  # building, attacking, defending
        self.difficulty = 1.0  # 0.5 = easy, 1.0 = normal, 1.5 = hard

    def update(self, dt: float):
        """Update AI logic."""
        self.think_timer += dt
        if self.think_timer >= self.think_interval / self.difficulty:
            self.think_timer = 0
            self.think()

        self.execute_orders(dt)

    def think(self):
        """AI decision making."""
        # Count units and buildings
        my_units = [u for u in self.game.units if u.team == Team.ENEMY]
        my_buildings = [b for b in self.game.buildings if b.team == Team.ENEMY]
        enemy_units = [u for u in self.game.units if u.team == Team.PLAYER]
        enemy_buildings = [b for b in self.game.buildings if b.team == Team.PLAYER]

        # Economic decisions
        self.economic_decisions(my_units, my_buildings)

        # Military decisions
        self.military_decisions(my_units, enemy_units, enemy_buildings)

    def economic_decisions(self, my_units: List[Unit], my_buildings: List[Building]):
        """Make economic decisions."""
        resources = self.game.enemy_resources

        # Build farms if low on food
        farms = len([b for b in my_buildings if b.building_type == BuildingType.FARM])
        if resources.food < 100 and farms < 3 and resources.gold >= 75:
            self.try_build_building(BuildingType.FARM)

        # Build houses for population
        houses = len([b for b in my_buildings if b.building_type == BuildingType.HOUSE])
        if houses < 4 and resources.gold >= 100:
            self.try_build_building(BuildingType.HOUSE)

        # Train peasants if low on workers
        peasants = len([u for u in my_units if u.unit_type == UnitType.PEASANT])
        if peasants < 3 and resources.gold >= 50:
            self.try_train_unit(UnitType.PEASANT)

    def military_decisions(self, my_units: List[Unit], enemy_units: List[Unit],
                          enemy_buildings: List[Building]):
        """Make military decisions."""
        resources = self.game.enemy_resources

        # Count military units
        military = [u for u in my_units if u.unit_type != UnitType.PEASANT]

        # Build military
        if len(military) < 5 and resources.gold >= 150:
            if random.random() < 0.6:
                self.try_train_unit(UnitType.KNIGHT)
            else:
                self.try_train_unit(UnitType.CAVALRY)

        # Add cannons occasionally
        if len(military) >= 3 and resources.gold >= 300 and random.random() < 0.3:
            cannons = len([u for u in my_units if u.unit_type == UnitType.CANNON])
            if cannons < 2:
                self.try_train_unit(UnitType.CANNON)

        # Attack decisions
        if len(military) >= 4:
            self.state = 'attacking'
            if enemy_buildings:
                target = random.choice(enemy_buildings)
                self.attack_target = (target.x, target.y)
            elif enemy_units:
                target = random.choice(enemy_units)
                self.attack_target = (target.x, target.y)

        # Defend if being attacked
        castle = next((b for b in self.game.buildings
                      if b.building_type == BuildingType.CASTLE and b.team == Team.ENEMY), None)
        if castle:
            nearby_enemies = [u for u in enemy_units
                            if u.distance_to(castle.x, castle.y) < 300]
            if nearby_enemies:
                self.state = 'defending'
                self.attack_target = (castle.x, castle.y)

    def try_build_building(self, building_type: BuildingType):
        """Attempt to build a building."""
        costs = {
            BuildingType.HOUSE: BUILDING_COSTS['house'],
            BuildingType.CASTLE: BUILDING_COSTS['castle'],
            BuildingType.FARM: BUILDING_COSTS['farm']
        }
        cost = costs.get(building_type, {'gold': 100, 'wood': 50})

        resources = self.game.enemy_resources
        if resources.gold >= cost['gold'] and resources.wood >= cost['wood']:
            # Find a spot near castle
            castle = next((b for b in self.game.buildings
                          if b.building_type == BuildingType.CASTLE and b.team == Team.ENEMY), None)
            if castle:
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(150, 300)
                x = castle.x + math.cos(angle) * dist
                y = castle.y + math.sin(angle) * dist
                x = max(100, min(MAP_WIDTH - 100, x))
                y = max(100, min(MAP_HEIGHT - 100, y))

                resources.gold -= cost['gold']
                resources.wood -= cost['wood']

                building = Building(x, y, building_type, Team.ENEMY)
                building.uid = self.game.next_uid()
                self.game.buildings.append(building)

    def try_train_unit(self, unit_type: UnitType):
        """Attempt to train a unit."""
        cost_map = {
            UnitType.PEASANT: UNIT_COSTS['peasant'],
            UnitType.KNIGHT: UNIT_COSTS['knight'],
            UnitType.CAVALRY: UNIT_COSTS['cavalry'],
            UnitType.CANNON: UNIT_COSTS['cannon']
        }
        cost = cost_map.get(unit_type, {'gold': 50, 'food': 25})

        resources = self.game.enemy_resources
        if resources.gold >= cost['gold'] and resources.food >= cost['food']:
            castle = next((b for b in self.game.buildings
                          if b.building_type == BuildingType.CASTLE and b.team == Team.ENEMY), None)
            if castle:
                resources.gold -= cost['gold']
                resources.food -= cost['food']

                angle = random.uniform(0, 2 * math.pi)
                x = castle.x + math.cos(angle) * 80
                y = castle.y + math.sin(angle) * 80

                unit = Unit(x, y, unit_type, Team.ENEMY)
                unit.uid = self.game.next_uid()
                self.game.units.append(unit)

    def execute_orders(self, dt: float):
        """Execute current orders for AI units."""
        if self.state == 'attacking' and self.attack_target:
            military = [u for u in self.game.units
                       if u.team == Team.ENEMY and u.unit_type != UnitType.PEASANT]
            for unit in military:
                if unit.target_unit is None and unit.target_building is None:
                    # Find nearest enemy
                    nearest_enemy = None
                    min_dist = float('inf')
                    for enemy in self.game.units:
                        if enemy.team == Team.PLAYER:
                            dist = unit.distance_to(enemy.x, enemy.y)
                            if dist < min_dist:
                                min_dist = dist
                                nearest_enemy = enemy

                    if nearest_enemy and min_dist < 200:
                        unit.target_unit = nearest_enemy
                    else:
                        unit.target_x, unit.target_y = self.attack_target


# =============================================================================
# NETWORKING
# =============================================================================

class NetworkManager:
    """Handles multiplayer networking."""

    def __init__(self, game: 'Game'):
        self.game = game
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.is_host = False
        self.peer_address: Optional[Tuple[str, int]] = None
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        self.pending_invite = False
        self.invite_from: Optional[str] = None
        self.message_queue: List[dict] = []
        self.lock = threading.Lock()

    def host_game(self, port: int = DEFAULT_PORT) -> bool:
        """Start hosting a game."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', port))
            self.socket.listen(1)
            self.socket.settimeout(0.5)
            self.is_host = True
            self.running = True
            self.receive_thread = threading.Thread(target=self._host_accept_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            return True
        except Exception as e:
            print(f"Failed to host: {e}")
            return False

    def connect_to_host(self, ip: str, port: int = DEFAULT_PORT) -> bool:
        """Connect to a hosted game."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((ip, port))
            self.peer_address = (ip, port)
            self.is_host = False

            # Send invite request
            self._send_message({'type': 'invite_request', 'from': socket.gethostname()})

            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    def wait_for_accept(self) -> Optional[bool]:
        """Wait for host to accept invite."""
        try:
            self.socket.settimeout(30)
            data = self._receive_message()
            if data and data.get('type') == 'invite_response':
                if data.get('accepted'):
                    self.connected = True
                    self.running = True
                    self.receive_thread = threading.Thread(target=self._receive_loop)
                    self.receive_thread.daemon = True
                    self.receive_thread.start()
                    return True
                else:
                    return False
        except:
            pass
        return None

    def accept_invite(self):
        """Accept a pending invite."""
        if self.pending_invite:
            self._send_message({'type': 'invite_response', 'accepted': True})
            self.connected = True
            self.pending_invite = False
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()

    def decline_invite(self):
        """Decline a pending invite."""
        if self.pending_invite:
            self._send_message({'type': 'invite_response', 'accepted': False})
            self.pending_invite = False
            self.invite_from = None

    def _host_accept_loop(self):
        """Accept incoming connections (host only)."""
        while self.running and not self.connected:
            try:
                conn, addr = self.socket.accept()
                self.socket = conn
                self.peer_address = addr

                # Wait for invite request
                data = self._receive_message()
                if data and data.get('type') == 'invite_request':
                    self.pending_invite = True
                    self.invite_from = data.get('from', addr[0])
            except socket.timeout:
                continue
            except:
                break

    def _receive_loop(self):
        """Receive messages from peer."""
        self.socket.settimeout(0.5)
        while self.running:
            try:
                data = self._receive_message()
                if data:
                    with self.lock:
                        self.message_queue.append(data)
            except socket.timeout:
                continue
            except:
                break
        self.connected = False

    def _send_message(self, data: dict):
        """Send a message to peer."""
        try:
            msg = json.dumps(data).encode('utf-8')
            length = struct.pack('!I', len(msg))
            self.socket.sendall(length + msg)
        except:
            self.connected = False

    def _receive_message(self) -> Optional[dict]:
        """Receive a message from peer."""
        try:
            length_data = self.socket.recv(4)
            if not length_data:
                return None
            length = struct.unpack('!I', length_data)[0]
            data = b''
            while len(data) < length:
                chunk = self.socket.recv(min(length - len(data), BUFFER_SIZE))
                if not chunk:
                    return None
                data += chunk
            return json.loads(data.decode('utf-8'))
        except:
            return None

    def send_game_state(self, units: List[Unit], buildings: List[Building],
                       resources: Resources):
        """Send game state to peer."""
        if not self.connected:
            return

        unit_data = [{
            'uid': u.uid,
            'x': u.x,
            'y': u.y,
            'type': u.unit_type.name,
            'team': u.team.name,
            'health': u.health
        } for u in units]

        building_data = [{
            'uid': b.uid,
            'x': b.x,
            'y': b.y,
            'type': b.building_type.name,
            'team': b.team.name,
            'health': b.health
        } for b in buildings]

        self._send_message({
            'type': 'game_state',
            'units': unit_data,
            'buildings': building_data,
            'resources': {'gold': resources.gold, 'food': resources.food, 'wood': resources.wood}
        })

    def send_action(self, action: dict):
        """Send a player action to peer."""
        if self.connected:
            self._send_message({'type': 'action', 'data': action})

    def get_messages(self) -> List[dict]:
        """Get pending messages."""
        with self.lock:
            messages = self.message_queue.copy()
            self.message_queue.clear()
        return messages

    def close(self):
        """Close the connection."""
        self.running = False
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass


# =============================================================================
# UI COMPONENTS
# =============================================================================

class Button:
    """Simple button UI component."""

    def __init__(self, x: int, y: int, width: int, height: int, text: str,
                 color: Tuple[int, int, int] = GRAY,
                 hover_color: Tuple[int, int, int] = LIGHT_GRAY):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.font = pygame.font.Font(None, 32)
        self.hovered = False

    def update(self, mouse_pos: Tuple[int, int]):
        """Update button state."""
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, screen: pygame.Surface):
        """Draw the button."""
        color = self.hover_color if self.hovered else self.color
        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)

        text_surf = self.font.render(self.text, True, BLACK)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, mouse_pos: Tuple[int, int], mouse_pressed: bool) -> bool:
        """Check if button was clicked."""
        return self.rect.collidepoint(mouse_pos) and mouse_pressed


class TextInput:
    """Simple text input UI component."""

    def __init__(self, x: int, y: int, width: int, height: int, placeholder: str = ""):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = ""
        self.placeholder = placeholder
        self.font = pygame.font.Font(None, 28)
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0

    def handle_event(self, event: pygame.event.Event):
        """Handle input events."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif event.unicode.isprintable():
                self.text += event.unicode

    def update(self, dt: float):
        """Update cursor blink."""
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible

    def draw(self, screen: pygame.Surface):
        """Draw the text input."""
        color = WHITE if self.active else LIGHT_GRAY
        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)

        display_text = self.text if self.text else self.placeholder
        text_color = BLACK if self.text else GRAY
        text_surf = self.font.render(display_text, True, text_color)
        screen.blit(text_surf, (self.rect.x + 5, self.rect.y + 8))

        if self.active and self.cursor_visible:
            cursor_x = self.rect.x + 5 + text_surf.get_width()
            pygame.draw.line(screen, BLACK, (cursor_x, self.rect.y + 5),
                           (cursor_x, self.rect.y + self.rect.height - 5), 2)


# =============================================================================
# MAIN GAME CLASS
# =============================================================================

class Game:
    """Main game class."""

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Medieval RTS")
        self.clock = pygame.time.Clock()

        # Game state
        self.state = GameState.MAIN_MENU
        self.running = True
        self.dt = 0

        # Assets
        self.assets = AssetManager()

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

        # AI
        self.ai_bot: Optional[AIBot] = None

        # Networking
        self.network = NetworkManager(self)
        self.is_multiplayer = False

        # UI
        self.font = pygame.font.Font(None, 24)
        self.large_font = pygame.font.Font(None, 48)
        self.title_font = pygame.font.Font(None, 72)

        # Menu buttons
        self.menu_buttons = [
            Button(SCREEN_WIDTH//2 - 150, 250, 300, 50, "Play vs AI"),
            Button(SCREEN_WIDTH//2 - 150, 320, 300, 50, "Host Multiplayer"),
            Button(SCREEN_WIDTH//2 - 150, 390, 300, 50, "Join Multiplayer"),
            Button(SCREEN_WIDTH//2 - 150, 460, 300, 50, "Quit")
        ]

        # Multiplayer UI
        self.ip_input = TextInput(SCREEN_WIDTH//2 - 150, 350, 300, 40, "Enter IP address")
        self.connect_button = Button(SCREEN_WIDTH//2 - 75, 410, 150, 40, "Connect")
        self.back_button = Button(SCREEN_WIDTH//2 - 75, 470, 150, 40, "Back")
        self.accept_button = Button(SCREEN_WIDTH//2 - 160, 400, 150, 40, "Accept")
        self.decline_button = Button(SCREEN_WIDTH//2 + 10, 400, 150, 40, "Decline")

        # HUD buttons
        self.hud_buttons = []

        # UID counter
        self._uid_counter = 0

        # Resource generation timer
        self.resource_timer = 0

    def next_uid(self) -> int:
        """Get next unique ID."""
        self._uid_counter += 1
        return self._uid_counter

    def init_game(self, vs_ai: bool = True):
        """Initialize a new game."""
        self.units.clear()
        self.buildings.clear()
        self.blood_effects.clear()
        self.selected_units.clear()
        self.selected_building = None

        # Reset resources
        self.player_resources = Resources()
        self.enemy_resources = Resources()

        # Reset camera
        self.camera.x = 0
        self.camera.y = 0

        # Create starting buildings and units for player
        player_castle = Building(300, MAP_HEIGHT - 300, BuildingType.CASTLE, Team.PLAYER)
        player_castle.uid = self.next_uid()
        self.buildings.append(player_castle)

        # Starting units for player
        for i in range(3):
            peasant = Unit(350 + i * 40, MAP_HEIGHT - 250, UnitType.PEASANT, Team.PLAYER)
            peasant.uid = self.next_uid()
            self.units.append(peasant)

        knight = Unit(300, MAP_HEIGHT - 200, UnitType.KNIGHT, Team.PLAYER)
        knight.uid = self.next_uid()
        self.units.append(knight)

        # Create enemy base
        enemy_castle = Building(MAP_WIDTH - 300, 300, BuildingType.CASTLE, Team.ENEMY)
        enemy_castle.uid = self.next_uid()
        self.buildings.append(enemy_castle)

        if vs_ai:
            self.ai_bot = AIBot(self)
            self.is_multiplayer = False

            # Enemy starting units
            for i in range(3):
                peasant = Unit(MAP_WIDTH - 350 - i * 40, 250, UnitType.PEASANT, Team.ENEMY)
                peasant.uid = self.next_uid()
                self.units.append(peasant)

            knight = Unit(MAP_WIDTH - 300, 200, UnitType.KNIGHT, Team.ENEMY)
            knight.uid = self.next_uid()
            self.units.append(knight)
        else:
            self.ai_bot = None
            self.is_multiplayer = True

        # Move camera to player start
        self.camera.x = 0
        self.camera.y = MAP_HEIGHT - SCREEN_HEIGHT

        self.state = GameState.PLAYING

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
                    self.finish_selection(mouse_pos)
                    self.selection_start = None
                    self.selection_rect = None

            if event.type == pygame.KEYDOWN:
                if self.state == GameState.PLAYING:
                    self.handle_game_keys(event)
                elif self.state in [GameState.MULTIPLAYER_LOBBY, GameState.CONNECTING]:
                    self.ip_input.handle_event(event)

            if self.state in [GameState.MULTIPLAYER_LOBBY, GameState.CONNECTING]:
                self.ip_input.handle_event(event)

        # Handle state-specific input
        if self.state == GameState.MAIN_MENU:
            self.handle_menu_input(mouse_pos, mouse_clicked)
        elif self.state == GameState.PLAYING:
            self.handle_game_input(mouse_pos, mouse_clicked, right_clicked)
        elif self.state == GameState.MULTIPLAYER_LOBBY:
            self.handle_lobby_input(mouse_pos, mouse_clicked)
        elif self.state == GameState.WAITING_FOR_ACCEPT:
            self.handle_waiting_input(mouse_pos, mouse_clicked)

    def handle_menu_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle main menu input."""
        for button in self.menu_buttons:
            button.update(mouse_pos)

        if clicked:
            if self.menu_buttons[0].is_clicked(mouse_pos, True):
                self.init_game(vs_ai=True)
            elif self.menu_buttons[1].is_clicked(mouse_pos, True):
                # Host multiplayer
                if self.network.host_game():
                    self.state = GameState.WAITING_FOR_ACCEPT
            elif self.menu_buttons[2].is_clicked(mouse_pos, True):
                self.state = GameState.MULTIPLAYER_LOBBY
            elif self.menu_buttons[3].is_clicked(mouse_pos, True):
                self.running = False

    def handle_lobby_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle multiplayer lobby input."""
        self.connect_button.update(mouse_pos)
        self.back_button.update(mouse_pos)

        if clicked:
            if self.connect_button.is_clicked(mouse_pos, True) and self.ip_input.text:
                if self.network.connect_to_host(self.ip_input.text):
                    self.state = GameState.CONNECTING
            elif self.back_button.is_clicked(mouse_pos, True):
                self.state = GameState.MAIN_MENU

    def handle_waiting_input(self, mouse_pos: Tuple[int, int], clicked: bool):
        """Handle waiting for player input."""
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

    def handle_game_input(self, mouse_pos: Tuple[int, int], clicked: bool,
                         right_clicked: bool):
        """Handle game input."""
        world_pos = self.camera.screen_to_world(*mouse_pos)

        # Update selection rectangle
        if self.selection_start:
            x1 = min(self.selection_start[0], mouse_pos[0])
            y1 = min(self.selection_start[1], mouse_pos[1])
            x2 = max(self.selection_start[0], mouse_pos[0])
            y2 = max(self.selection_start[1], mouse_pos[1])
            self.selection_rect = pygame.Rect(x1, y1, x2 - x1, y2 - y1)

        # Handle building placement
        if self.placing_building and clicked:
            self.place_building(world_pos)
            return

        # Right click - move/attack command
        if right_clicked and self.selected_units:
            self.issue_command(world_pos)

        # HUD interaction (check if clicking on HUD area)
        if clicked and mouse_pos[1] > SCREEN_HEIGHT - 100:
            self.handle_hud_click(mouse_pos)

    def handle_game_keys(self, event: pygame.event.Event):
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
            self.train_unit(UnitType.PEASANT)
        elif event.key == pygame.K_k:
            self.train_unit(UnitType.KNIGHT)
        elif event.key == pygame.K_c:
            self.train_unit(UnitType.CAVALRY)
        elif event.key == pygame.K_n:
            self.train_unit(UnitType.CANNON)

        # Delete selected
        elif event.key == pygame.K_DELETE:
            for unit in self.selected_units:
                if unit in self.units:
                    self.units.remove(unit)
            self.selected_units.clear()

    def handle_hud_click(self, mouse_pos: Tuple[int, int]):
        """Handle HUD button clicks."""
        hud_y = SCREEN_HEIGHT - 90
        button_size = 60

        # Unit training buttons
        buttons = [
            (50, hud_y, UnitType.PEASANT),
            (120, hud_y, UnitType.KNIGHT),
            (190, hud_y, UnitType.CAVALRY),
            (260, hud_y, UnitType.CANNON),
        ]

        for bx, by, unit_type in buttons:
            if pygame.Rect(bx, by, button_size, button_size).collidepoint(mouse_pos):
                self.train_unit(unit_type)
                return

        # Building buttons
        building_buttons = [
            (350, hud_y, BuildingType.HOUSE),
            (420, hud_y, BuildingType.FARM),
        ]

        for bx, by, building_type in building_buttons:
            if pygame.Rect(bx, by, button_size, button_size).collidepoint(mouse_pos):
                self.placing_building = building_type
                return

    def finish_selection(self, end_pos: Tuple[int, int]):
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

        # Small click = single selection, large drag = box selection
        if selection_area.width < 10 and selection_area.height < 10:
            # Single click selection
            for unit in self.units:
                if unit.team == Team.PLAYER and unit.get_rect().collidepoint(start_world):
                    unit.selected = True
                    self.selected_units.append(unit)
                    return

            # Check buildings
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

    def issue_command(self, world_pos: Tuple[float, float]):
        """Issue move/attack command to selected units."""
        # Check if clicking on enemy
        target_unit = None
        target_building = None

        for unit in self.units:
            if unit.team == Team.ENEMY and unit.get_rect().collidepoint(world_pos):
                target_unit = unit
                break

        if not target_unit:
            for building in self.buildings:
                if building.team == Team.ENEMY and building.get_rect().collidepoint(world_pos):
                    target_building = building
                    break

        for unit in self.selected_units:
            unit.target_x, unit.target_y = world_pos
            unit.target_unit = target_unit
            unit.target_building = target_building

        # Send network action
        if self.is_multiplayer and self.network.connected:
            self.network.send_action({
                'command': 'move',
                'units': [u.uid for u in self.selected_units],
                'target': world_pos,
                'target_unit': target_unit.uid if target_unit else None,
                'target_building': target_building.uid if target_building else None
            })

    def train_unit(self, unit_type: UnitType):
        """Train a new unit."""
        cost_map = {
            UnitType.PEASANT: UNIT_COSTS['peasant'],
            UnitType.KNIGHT: UNIT_COSTS['knight'],
            UnitType.CAVALRY: UNIT_COSTS['cavalry'],
            UnitType.CANNON: UNIT_COSTS['cannon']
        }
        cost = cost_map.get(unit_type, {'gold': 50, 'food': 25})

        if (self.player_resources.gold >= cost['gold'] and
            self.player_resources.food >= cost['food']):

            # Find player's castle
            castle = next((b for b in self.buildings
                          if b.building_type == BuildingType.CASTLE and b.team == Team.PLAYER), None)

            if castle:
                self.player_resources.gold -= cost['gold']
                self.player_resources.food -= cost['food']

                angle = random.uniform(0, 2 * math.pi)
                x = castle.x + math.cos(angle) * 80
                y = castle.y + math.sin(angle) * 80

                unit = Unit(x, y, unit_type, Team.PLAYER)
                unit.uid = self.next_uid()
                self.units.append(unit)

    def place_building(self, world_pos: Tuple[float, float]):
        """Place a building at the given position."""
        if not self.placing_building:
            return

        cost_map = {
            BuildingType.HOUSE: BUILDING_COSTS['house'],
            BuildingType.CASTLE: BUILDING_COSTS['castle'],
            BuildingType.FARM: BUILDING_COSTS['farm']
        }
        cost = cost_map.get(self.placing_building, {'gold': 100, 'wood': 50})

        if (self.player_resources.gold >= cost['gold'] and
            self.player_resources.wood >= cost['wood']):

            self.player_resources.gold -= cost['gold']
            self.player_resources.wood -= cost['wood']

            building = Building(world_pos[0], world_pos[1], self.placing_building, Team.PLAYER)
            building.uid = self.next_uid()
            self.buildings.append(building)

        self.placing_building = None

    def update(self):
        """Update game state."""
        self.dt = self.clock.tick(FPS) / 1000.0

        if self.state == GameState.PLAYING:
            self.update_game()
        elif self.state == GameState.CONNECTING:
            result = self.network.wait_for_accept()
            if result is True:
                self.init_game(vs_ai=False)
            elif result is False:
                self.state = GameState.MULTIPLAYER_LOBBY
        elif self.state == GameState.MULTIPLAYER_LOBBY:
            self.ip_input.update(self.dt)

    def update_game(self):
        """Update game logic."""
        keys = pygame.key.get_pressed()
        self.camera.update(keys, self.dt)

        # Update AI
        if self.ai_bot:
            self.ai_bot.update(self.dt)

        # Handle network messages
        if self.is_multiplayer:
            self.handle_network_messages()

        # Update units
        self.update_units()

        # Update blood effects
        self.update_effects()

        # Generate resources
        self.update_resources()

        # Check win/lose conditions
        self.check_game_over()

    def update_units(self):
        """Update all units."""
        current_time = time.time()

        for unit in self.units[:]:  # Copy list to allow removal
            # Movement
            if unit.target_x is not None and unit.target_y is not None:
                # Check if we should attack instead of move
                if unit.target_unit:
                    dist = unit.distance_to(unit.target_unit.x, unit.target_unit.y)
                    if dist <= unit.attack_range:
                        # Attack!
                        if current_time - unit.last_attack >= unit.attack_cooldown:
                            self.do_attack(unit, unit.target_unit)
                            unit.last_attack = current_time
                    else:
                        unit.move_towards(unit.target_unit.x, unit.target_unit.y, self.dt)
                elif unit.target_building:
                    dist = unit.distance_to(unit.target_building.x, unit.target_building.y)
                    if dist <= unit.attack_range + 50:
                        if current_time - unit.last_attack >= unit.attack_cooldown:
                            self.do_attack_building(unit, unit.target_building)
                            unit.last_attack = current_time
                    else:
                        unit.move_towards(unit.target_building.x, unit.target_building.y, self.dt)
                else:
                    unit.move_towards(unit.target_x, unit.target_y, self.dt)

            # Auto-attack nearby enemies
            if unit.target_unit is None and unit.target_building is None:
                for other in self.units:
                    if other.team != unit.team:
                        dist = unit.distance_to(other.x, other.y)
                        if dist <= unit.attack_range * 1.5:
                            unit.target_unit = other
                            break

            # Remove dead units
            if unit.health <= 0:
                self.blood_effects.append(BloodEffect(unit.x, unit.y))
                self.units.remove(unit)
                # Clear references
                for u in self.units:
                    if u.target_unit == unit:
                        u.target_unit = None

    def do_attack(self, attacker: Unit, defender: Unit):
        """Perform an attack."""
        damage = max(1, attacker.attack - defender.defense // 2)
        damage = int(damage * random.uniform(0.8, 1.2))
        defender.health -= damage

        # Small blood effect
        self.blood_effects.append(BloodEffect(defender.x, defender.y, 0.5, 128))

    def do_attack_building(self, attacker: Unit, building: Building):
        """Attack a building."""
        damage = attacker.attack
        building.health -= damage

        if building.health <= 0:
            self.buildings.remove(building)
            # Clear references
            for u in self.units:
                if u.target_building == building:
                    u.target_building = None

    def update_effects(self):
        """Update visual effects."""
        for effect in self.blood_effects[:]:
            effect.lifetime -= self.dt
            effect.alpha = int(255 * (effect.lifetime / 1.0))
            if effect.lifetime <= 0:
                self.blood_effects.remove(effect)

    def update_resources(self):
        """Update resource generation."""
        self.resource_timer += self.dt
        if self.resource_timer >= 5.0:  # Every 5 seconds
            self.resource_timer = 0

            # Generate resources from farms
            for building in self.buildings:
                if building.building_type == BuildingType.FARM:
                    if building.team == Team.PLAYER:
                        self.player_resources.food += 20
                        self.player_resources.wood += 10
                    else:
                        self.enemy_resources.food += 20
                        self.enemy_resources.wood += 10

            # Passive gold generation from houses
            for building in self.buildings:
                if building.building_type == BuildingType.HOUSE:
                    if building.team == Team.PLAYER:
                        self.player_resources.gold += 15
                    else:
                        self.enemy_resources.gold += 15

    def handle_network_messages(self):
        """Handle incoming network messages."""
        messages = self.network.get_messages()
        for msg in messages:
            if msg['type'] == 'game_state':
                # Sync enemy state
                pass  # TODO: Full sync implementation
            elif msg['type'] == 'action':
                # Apply enemy action
                data = msg['data']
                if data['command'] == 'move':
                    for unit in self.units:
                        if unit.uid in data['units'] and unit.team == Team.ENEMY:
                            unit.target_x, unit.target_y = data['target']

    def check_game_over(self):
        """Check win/lose conditions."""
        player_castle = any(b for b in self.buildings
                          if b.building_type == BuildingType.CASTLE and b.team == Team.PLAYER)
        enemy_castle = any(b for b in self.buildings
                         if b.building_type == BuildingType.CASTLE and b.team == Team.ENEMY)

        if not player_castle or not enemy_castle:
            self.state = GameState.GAME_OVER

    def draw(self):
        """Draw the game."""
        if self.state == GameState.MAIN_MENU:
            self.draw_main_menu()
        elif self.state == GameState.PLAYING:
            self.draw_game()
        elif self.state == GameState.GAME_OVER:
            self.draw_game()
            self.draw_game_over()
        elif self.state == GameState.MULTIPLAYER_LOBBY:
            self.draw_multiplayer_lobby()
        elif self.state in [GameState.WAITING_FOR_ACCEPT, GameState.CONNECTING]:
            self.draw_waiting_screen()

        pygame.display.flip()

    def draw_main_menu(self):
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

        # Instructions
        instructions = [
            "Controls:",
            "WASD/Arrow Keys - Move camera",
            "Left Click - Select units",
            "Right Click - Move/Attack",
            "H - Build House, F - Build Farm",
            "P - Train Peasant, K - Train Knight",
            "C - Train Cavalry, N - Train Cannon"
        ]

        y = 530
        for line in instructions:
            text = self.font.render(line, True, LIGHT_GRAY)
            self.screen.blit(text, (SCREEN_WIDTH // 2 - 150, y))
            y += 25

    def draw_multiplayer_lobby(self):
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

    def draw_waiting_screen(self):
        """Draw waiting for connection screen."""
        self.screen.fill(DARK_GRAY)

        if self.state == GameState.CONNECTING:
            title = self.large_font.render("Connecting...", True, WHITE)
            subtitle = self.font.render("Waiting for host to accept", True, LIGHT_GRAY)
        else:
            if self.network.pending_invite:
                title = self.large_font.render("Incoming Connection", True, WHITE)
                subtitle = self.font.render(f"Player '{self.network.invite_from}' wants to join",
                                           True, LIGHT_GRAY)
                self.accept_button.draw(self.screen)
                self.decline_button.draw(self.screen)
            else:
                title = self.large_font.render("Hosting Game", True, WHITE)
                # Get local IP
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    s.close()
                except:
                    local_ip = "127.0.0.1"
                subtitle = self.font.render(f"Your IP: {local_ip} - Waiting for players...",
                                           True, LIGHT_GRAY)

        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 250))
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 320))
        self.screen.blit(title, title_rect)
        self.screen.blit(subtitle, subtitle_rect)

        self.back_button.draw(self.screen)

    def draw_game(self):
        """Draw the game world."""
        # Draw background/terrain
        self.draw_terrain()

        # Draw buildings
        for building in self.buildings:
            self.draw_building(building)

        # Draw blood effects
        for effect in self.blood_effects:
            self.draw_effect(effect)

        # Draw units
        for unit in self.units:
            self.draw_unit(unit)

        # Draw selection rectangle
        if self.selection_rect and self.selection_rect.width > 5:
            pygame.draw.rect(self.screen, GREEN, self.selection_rect, 2)

        # Draw building placement preview
        if self.placing_building:
            self.draw_building_preview()

        # Draw HUD
        self.draw_hud()

        # Draw minimap
        self.draw_minimap()

    def draw_terrain(self):
        """Draw terrain tiles."""
        grass = self.assets.get('grass')

        start_x = int(self.camera.x // TILE_SIZE) * TILE_SIZE
        start_y = int(self.camera.y // TILE_SIZE) * TILE_SIZE

        for y in range(start_y, int(start_y + SCREEN_HEIGHT + TILE_SIZE * 2), TILE_SIZE):
            for x in range(start_x, int(start_x + SCREEN_WIDTH + TILE_SIZE * 2), TILE_SIZE):
                screen_pos = self.camera.world_to_screen(x, y)
                self.screen.blit(grass, screen_pos)

    def draw_unit(self, unit: Unit):
        """Draw a unit."""
        screen_pos = self.camera.world_to_screen(unit.x, unit.y)

        # Get appropriate sprite
        sprite_map = {
            UnitType.PEASANT: 'peasant',
            UnitType.KNIGHT: 'knight',
            UnitType.CAVALRY: 'horse',
            UnitType.CANNON: 'cannon'
        }
        sprite = self.assets.get(sprite_map.get(unit.unit_type, 'peasant'))

        # Tint enemy units red
        if unit.team == Team.ENEMY:
            sprite = sprite.copy()
            sprite.fill((255, 100, 100), special_flags=pygame.BLEND_MULT)

        # Draw sprite centered
        rect = sprite.get_rect(center=screen_pos)
        self.screen.blit(sprite, rect)

        # Draw selection indicator
        if unit.selected:
            pygame.draw.circle(self.screen, GREEN, screen_pos, 30, 2)

        # Draw health bar
        self.draw_health_bar(screen_pos, unit.health, unit.max_health, 40)

    def draw_building(self, building: Building):
        """Draw a building."""
        screen_pos = self.camera.world_to_screen(building.x, building.y)

        sprite_map = {
            BuildingType.HOUSE: 'house',
            BuildingType.CASTLE: 'castle',
            BuildingType.FARM: 'farm'
        }
        sprite = self.assets.get(sprite_map.get(building.building_type, 'house'))

        # Tint enemy buildings red
        if building.team == Team.ENEMY:
            sprite = sprite.copy()
            sprite.fill((255, 100, 100), special_flags=pygame.BLEND_MULT)

        rect = sprite.get_rect(center=screen_pos)
        self.screen.blit(sprite, rect)

        # Selection indicator
        if building.selected:
            pygame.draw.rect(self.screen, GREEN, rect.inflate(10, 10), 3)

        # Health bar
        bar_width = rect.width
        self.draw_health_bar((screen_pos[0], screen_pos[1] - rect.height // 2 - 10),
                            building.health, building.max_health, bar_width)

    def draw_effect(self, effect: BloodEffect):
        """Draw a visual effect."""
        screen_pos = self.camera.world_to_screen(effect.x, effect.y)
        blood = self.assets.get('blood').copy()
        blood.set_alpha(effect.alpha)
        rect = blood.get_rect(center=screen_pos)
        self.screen.blit(blood, rect)

    def draw_health_bar(self, pos: Tuple[int, int], health: int, max_health: int, width: int):
        """Draw a health bar."""
        bar_height = 6
        x = pos[0] - width // 2
        y = pos[1] - 25

        # Background
        pygame.draw.rect(self.screen, RED, (x, y, width, bar_height))
        # Health
        health_width = int(width * (health / max_health))
        pygame.draw.rect(self.screen, GREEN, (x, y, health_width, bar_height))
        # Border
        pygame.draw.rect(self.screen, BLACK, (x, y, width, bar_height), 1)

    def draw_building_preview(self):
        """Draw building placement preview."""
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(*mouse_pos)
        screen_pos = mouse_pos

        sprite_map = {
            BuildingType.HOUSE: 'house',
            BuildingType.CASTLE: 'castle',
            BuildingType.FARM: 'farm'
        }
        sprite = self.assets.get(sprite_map.get(self.placing_building, 'house')).copy()
        sprite.set_alpha(128)

        rect = sprite.get_rect(center=screen_pos)
        self.screen.blit(sprite, rect)

    def draw_hud(self):
        """Draw the HUD."""
        # Bottom panel
        panel_rect = pygame.Rect(0, SCREEN_HEIGHT - 100, SCREEN_WIDTH, 100)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 2)

        # Resources
        res_y = SCREEN_HEIGHT - 95
        gold_text = self.font.render(f"Gold: {self.player_resources.gold}", True, GOLD)
        food_text = self.font.render(f"Food: {self.player_resources.food}", True, GREEN)
        wood_text = self.font.render(f"Wood: {self.player_resources.wood}", True, BROWN)

        self.screen.blit(gold_text, (SCREEN_WIDTH - 300, res_y))
        self.screen.blit(food_text, (SCREEN_WIDTH - 300, res_y + 25))
        self.screen.blit(wood_text, (SCREEN_WIDTH - 300, res_y + 50))

        # Unit training buttons
        hud_y = SCREEN_HEIGHT - 90
        button_size = 60

        units = [
            (50, UnitType.PEASANT, 'peasant', f"P: {UNIT_COSTS['peasant']['gold']}g"),
            (120, UnitType.KNIGHT, 'knight', f"K: {UNIT_COSTS['knight']['gold']}g"),
            (190, UnitType.CAVALRY, 'horse', f"C: {UNIT_COSTS['cavalry']['gold']}g"),
            (260, UnitType.CANNON, 'cannon', f"N: {UNIT_COSTS['cannon']['gold']}g"),
        ]

        for bx, unit_type, sprite_name, label in units:
            rect = pygame.Rect(bx, hud_y, button_size, button_size)
            pygame.draw.rect(self.screen, GRAY, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

            sprite = pygame.transform.scale(self.assets.get(sprite_name), (40, 40))
            self.screen.blit(sprite, (bx + 10, hud_y + 5))

            label_surf = self.font.render(label, True, WHITE)
            self.screen.blit(label_surf, (bx, hud_y + 62))

        # Building buttons
        buildings = [
            (350, BuildingType.HOUSE, 'house', f"H: {BUILDING_COSTS['house']['gold']}g"),
            (420, BuildingType.FARM, 'farm', f"F: {BUILDING_COSTS['farm']['gold']}g"),
        ]

        for bx, building_type, sprite_name, label in buildings:
            rect = pygame.Rect(bx, hud_y, button_size, button_size)
            color = LIGHT_GRAY if self.placing_building == building_type else GRAY
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

            sprite = pygame.transform.scale(self.assets.get(sprite_name), (50, 50))
            self.screen.blit(sprite, (bx + 5, hud_y + 5))

            label_surf = self.font.render(label, True, WHITE)
            self.screen.blit(label_surf, (bx, hud_y + 62))

        # Selected unit info
        if self.selected_units:
            info_text = f"Selected: {len(self.selected_units)} unit(s)"
            info_surf = self.font.render(info_text, True, WHITE)
            self.screen.blit(info_surf, (520, hud_y + 20))
        elif self.selected_building:
            info_text = f"Selected: {self.selected_building.building_type.name}"
            info_surf = self.font.render(info_text, True, WHITE)
            self.screen.blit(info_surf, (520, hud_y + 20))

    def draw_minimap(self):
        """Draw the minimap."""
        minimap_size = 150
        minimap_x = SCREEN_WIDTH - minimap_size - 10
        minimap_y = 10

        # Background
        pygame.draw.rect(self.screen, DARK_GREEN,
                        (minimap_x, minimap_y, minimap_size, minimap_size))
        pygame.draw.rect(self.screen, BLACK,
                        (minimap_x, minimap_y, minimap_size, minimap_size), 2)

        scale_x = minimap_size / MAP_WIDTH
        scale_y = minimap_size / MAP_HEIGHT

        # Draw buildings
        for building in self.buildings:
            color = BLUE if building.team == Team.PLAYER else RED
            x = minimap_x + int(building.x * scale_x)
            y = minimap_y + int(building.y * scale_y)
            size = 6 if building.building_type == BuildingType.CASTLE else 4
            pygame.draw.rect(self.screen, color, (x - size//2, y - size//2, size, size))

        # Draw units
        for unit in self.units:
            color = BLUE if unit.team == Team.PLAYER else RED
            x = minimap_x + int(unit.x * scale_x)
            y = minimap_y + int(unit.y * scale_y)
            pygame.draw.circle(self.screen, color, (x, y), 2)

        # Draw camera viewport
        cam_x = minimap_x + int(self.camera.x * scale_x)
        cam_y = minimap_y + int(self.camera.y * scale_y)
        cam_w = int(SCREEN_WIDTH * scale_x)
        cam_h = int(SCREEN_HEIGHT * scale_y)
        pygame.draw.rect(self.screen, WHITE, (cam_x, cam_y, cam_w, cam_h), 1)

    def draw_game_over(self):
        """Draw game over overlay."""
        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill(BLACK)
        overlay.set_alpha(180)
        self.screen.blit(overlay, (0, 0))

        # Check who won
        player_castle = any(b for b in self.buildings
                          if b.building_type == BuildingType.CASTLE and b.team == Team.PLAYER)

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

    def run(self):
        """Main game loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()

        # Cleanup
        self.network.close()
        pygame.quit()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    game = Game()
    game.run()
