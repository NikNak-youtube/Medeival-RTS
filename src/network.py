"""
Networking for multiplayer support.
"""

import socket
import threading
import json
import struct
from typing import Optional, Tuple, List, TYPE_CHECKING

from .constants import DEFAULT_PORT, BUFFER_SIZE

if TYPE_CHECKING:
    from .game import Game


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

        # Invite system
        self.pending_invite = False
        self.invite_from: Optional[str] = None

        # Message queue
        self.message_queue: List[dict] = []
        self.lock = threading.Lock()

        # Connection state for async connect
        self.connecting = False
        self.connect_result: Optional[bool] = None
        self.connect_thread: Optional[threading.Thread] = None

    # =========================================================================
    # HOST FUNCTIONS
    # =========================================================================

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

            # Start accept thread
            self.receive_thread = threading.Thread(target=self._host_accept_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            return True
        except Exception as e:
            print(f"Failed to host: {e}")
            return False

    def _host_accept_loop(self):
        """Accept incoming connections (host only)."""
        listen_socket = self.socket  # Keep reference to listening socket
        while self.running and not self.connected:
            try:
                conn, addr = listen_socket.accept()
                self.socket = conn  # Replace with connection socket
                self.peer_address = addr

                # Wait for invite request
                data = self._receive_message()
                if data and data.get('type') == 'invite_request':
                    self.pending_invite = True
                    self.invite_from = data.get('from', addr[0])
                # Exit loop after accepting a connection
                break
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Accept error: {e}")
                break
        # Close the listening socket since we no longer need it
        try:
            if listen_socket and listen_socket != self.socket:
                listen_socket.close()
        except:
            pass

    def accept_invite(self):
        """Accept a pending invite."""
        if self.pending_invite:
            self._send_message({'type': 'invite_response', 'accepted': True})
            self.connected = True
            self.pending_invite = False
            self._start_receive_loop()

    def decline_invite(self):
        """Decline a pending invite."""
        if self.pending_invite:
            self._send_message({'type': 'invite_response', 'accepted': False})
            self.pending_invite = False
            self.invite_from = None

    # =========================================================================
    # CLIENT FUNCTIONS
    # =========================================================================

    def connect_to_host(self, ip: str, port: int = DEFAULT_PORT) -> bool:
        """Start connecting to a hosted game (non-blocking)."""
        if self.connecting:
            return False

        self.connecting = True
        self.connect_result = None

        # Start connection in background thread
        self.connect_thread = threading.Thread(
            target=self._connect_thread, args=(ip, port)
        )
        self.connect_thread.daemon = True
        self.connect_thread.start()

        return True

    def _connect_thread(self, ip: str, port: int):
        """Background thread for connecting and waiting for accept."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((ip, port))
            self.peer_address = (ip, port)
            self.is_host = False

            # Send invite request
            hostname = socket.gethostname()
            self._send_message({'type': 'invite_request', 'from': hostname})

            # Wait for response
            self.socket.settimeout(30)
            data = self._receive_message()
            if data and data.get('type') == 'invite_response':
                if data.get('accepted'):
                    self.connected = True
                    self.running = True
                    self._start_receive_loop()
                    self.connect_result = True
                else:
                    self.connect_result = False
            else:
                self.connect_result = False
        except socket.timeout:
            self.connect_result = False
        except Exception as e:
            print(f"Connect error: {e}")
            self.connect_result = False
        finally:
            self.connecting = False

    def get_connect_status(self) -> Optional[bool]:
        """Check connection status. Returns True/False when done, None if still connecting."""
        if self.connecting:
            return None
        return self.connect_result

    def wait_for_accept(self) -> Optional[bool]:
        """Check if connection was accepted (non-blocking now)."""
        return self.get_connect_status()

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    def _start_receive_loop(self):
        """Start the receive loop thread."""
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()

    def _receive_loop(self):
        """Receive messages from peer."""
        print("[NET] Receive loop started")
        self.socket.settimeout(0.5)
        while self.running:
            try:
                data = self._receive_message()
                if data:
                    print(f"[NET] Received: {data.get('type', 'unknown')} - {data.get('data', {}).get('command', '')}")
                    with self.lock:
                        self.message_queue.append(data)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Receive error: {e}")
                break
        print("[NET] Receive loop ended")
        self.connected = False

    def _send_message(self, data: dict):
        """Send a message to peer."""
        try:
            msg = json.dumps(data).encode('utf-8')
            length = struct.pack('!I', len(msg))
            self.socket.sendall(length + msg)
        except Exception as e:
            print(f"Send error: {e}")
            self.connected = False

    def _receive_message(self) -> Optional[dict]:
        """Receive a message from peer."""
        try:
            # Read message length
            length_data = self.socket.recv(4)
            if not length_data:
                return None
            length = struct.unpack('!I', length_data)[0]

            # Read message body
            data = b''
            while len(data) < length:
                chunk = self.socket.recv(min(length - len(data), BUFFER_SIZE))
                if not chunk:
                    return None
                data += chunk

            return json.loads(data.decode('utf-8'))
        except socket.timeout:
            raise
        except Exception as e:
            print(f"Receive message error: {e}")
            return None

    def get_messages(self) -> List[dict]:
        """Get pending messages from queue."""
        with self.lock:
            messages = self.message_queue.copy()
            self.message_queue.clear()
        return messages

    # =========================================================================
    # GAME STATE SYNC
    # =========================================================================

    def send_game_state(self, units: list, buildings: list, resources):
        """Send full game state to peer."""
        if not self.connected:
            return

        unit_data = [u.to_dict() for u in units]
        building_data = [b.to_dict() for b in buildings]

        self._send_message({
            'type': 'game_state',
            'units': unit_data,
            'buildings': building_data,
            'resources': {
                'gold': resources.gold,
                'food': resources.food,
                'wood': resources.wood
            }
        })

    def send_action(self, action: dict):
        """Send a player action to peer."""
        if self.connected:
            print(f"[NET] Sending action: {action.get('command', 'unknown')}")
            self._send_message({'type': 'action', 'data': action})
        else:
            print(f"[NET] Cannot send - not connected")

    def send_unit_command(self, unit_uids: List[int], target_pos: Tuple[float, float],
                         target_unit_uid: Optional[int] = None,
                         target_building_uid: Optional[int] = None):
        """Send a unit command to peer."""
        self.send_action({
            'command': 'move',
            'units': unit_uids,
            'target': target_pos,
            'target_unit': target_unit_uid,
            'target_building': target_building_uid
        })

    def send_train_unit(self, unit_type: str):
        """Send unit training command."""
        self.send_action({
            'command': 'train',
            'unit_type': unit_type
        })

    def send_build_building(self, building_type: str, x: float, y: float):
        """Send building placement command."""
        self.send_action({
            'command': 'build',
            'building_type': building_type,
            'x': x,
            'y': y
        })

    def send_assign_worker(self, unit_uid: int, building_uid: Optional[int]):
        """Send worker assignment command."""
        self.send_action({
            'command': 'assign_worker',
            'unit': unit_uid,
            'building': building_uid
        })

    def send_unit_death(self, unit_uid: int):
        """Send unit death notification."""
        self.send_action({
            'command': 'unit_death',
            'unit': unit_uid
        })

    def send_building_destroyed(self, building_uid: int):
        """Send building destruction notification."""
        self.send_action({
            'command': 'building_destroyed',
            'building': building_uid
        })

    def send_unit_damage(self, unit_uid: int, new_health: int):
        """Send unit damage update."""
        self.send_action({
            'command': 'unit_damage',
            'unit': unit_uid,
            'health': new_health
        })

    def send_building_damage(self, building_uid: int, new_health: int):
        """Send building damage update."""
        self.send_action({
            'command': 'building_damage',
            'building': building_uid,
            'health': new_health
        })

    def send_building_progress(self, building_uid: int, progress: float, completed: bool):
        """Send building construction progress update."""
        self.send_action({
            'command': 'building_progress',
            'building': building_uid,
            'progress': progress,
            'completed': completed
        })

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_local_ip(self) -> str:
        """Get local IP address for display."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def close(self):
        """Close the connection."""
        self.running = False
        self.connected = False
        self.connecting = False
        self.connect_result = None
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.socket = None
