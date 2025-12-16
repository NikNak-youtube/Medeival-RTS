"""
Camera and viewport handling.
"""

import pygame
from typing import Tuple

from .constants import MAP_WIDTH, MAP_HEIGHT


class Camera:
    """Handles viewport and map scrolling."""

    def __init__(self, width: int, height: int):
        """
        Initialize camera.

        Args:
            width: Viewport width (screen width)
            height: Viewport height (screen height)
        """
        self.x = 0.0
        self.y = 0.0
        self.width = width
        self.height = height
        self.speed = 10.0
        self.edge_scroll_margin = 20
        self.edge_scroll_enabled = True

    def update(self, keys, dt: float, mouse_pos: Tuple[int, int] = None):
        """
        Update camera position based on input.

        Args:
            keys: Pygame key state from pygame.key.get_pressed()
            dt: Delta time in seconds
            mouse_pos: Optional mouse position for edge scrolling
        """
        move_speed = self.speed * dt * 60

        # Keyboard scrolling
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.x -= move_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x += move_speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.y -= move_speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.y += move_speed

        # Edge scrolling
        if self.edge_scroll_enabled and mouse_pos:
            mouse_x, mouse_y = mouse_pos
            if mouse_x < self.edge_scroll_margin:
                self.x -= move_speed
            elif mouse_x > self.width - self.edge_scroll_margin:
                self.x += move_speed
            if mouse_y < self.edge_scroll_margin:
                self.y -= move_speed
            elif mouse_y > self.height - self.edge_scroll_margin:
                self.y += move_speed

        # Clamp to map bounds
        self.clamp_to_map()

    def clamp_to_map(self):
        """Clamp camera position to map boundaries."""
        self.x = max(0, min(MAP_WIDTH - self.width, self.x))
        self.y = max(0, min(MAP_HEIGHT - self.height, self.y))

    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """
        Convert world coordinates to screen coordinates.

        Args:
            world_x: X position in world space
            world_y: Y position in world space

        Returns:
            Tuple of (screen_x, screen_y)
        """
        return (int(world_x - self.x), int(world_y - self.y))

    def screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """
        Convert screen coordinates to world coordinates.

        Args:
            screen_x: X position on screen
            screen_y: Y position on screen

        Returns:
            Tuple of (world_x, world_y)
        """
        return (screen_x + self.x, screen_y + self.y)

    def is_rect_visible(self, rect: pygame.Rect) -> bool:
        """
        Check if a world-space rectangle is visible on screen.

        Args:
            rect: Rectangle in world coordinates

        Returns:
            True if any part of rect is visible
        """
        screen_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        return screen_rect.colliderect(rect)

    def is_point_visible(self, x: float, y: float, margin: int = 50) -> bool:
        """
        Check if a world-space point is visible on screen.

        Args:
            x: X position in world space
            y: Y position in world space
            margin: Extra margin around screen bounds

        Returns:
            True if point is visible
        """
        return (self.x - margin <= x <= self.x + self.width + margin and
                self.y - margin <= y <= self.y + self.height + margin)

    def center_on(self, x: float, y: float):
        """
        Center camera on a world position.

        Args:
            x: World X position to center on
            y: World Y position to center on
        """
        self.x = x - self.width / 2
        self.y = y - self.height / 2
        self.clamp_to_map()

    def move_to(self, x: float, y: float):
        """
        Move camera to a specific position (top-left corner).

        Args:
            x: World X position for top-left
            y: World Y position for top-left
        """
        self.x = x
        self.y = y
        self.clamp_to_map()

    def get_viewport_rect(self) -> pygame.Rect:
        """Get the current viewport as a rectangle in world coordinates."""
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def get_visible_area(self) -> Tuple[int, int, int, int]:
        """
        Get the visible area bounds.

        Returns:
            Tuple of (left, top, right, bottom) in world coordinates
        """
        return (int(self.x), int(self.y),
                int(self.x + self.width), int(self.y + self.height))
