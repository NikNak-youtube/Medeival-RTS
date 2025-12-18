"""
UI components: Buttons, Text Input, HUD elements.
"""

import pygame
from typing import Tuple, Optional, Callable

from . import constants
from .constants import (
    WHITE, BLACK, GRAY, LIGHT_GRAY, DARK_GRAY, RED, GREEN, GOLD, BROWN,
    UNIT_COSTS, BUILDING_COSTS
)


# =============================================================================
# BUTTON
# =============================================================================

class Button:
    """Simple button UI component."""

    def __init__(self, x: int, y: int, width: int, height: int, text: str,
                 color: Tuple[int, int, int] = GRAY,
                 hover_color: Tuple[int, int, int] = LIGHT_GRAY,
                 text_color: Tuple[int, int, int] = BLACK,
                 font_size: int = 32):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.font = pygame.font.Font(None, font_size)
        self.hovered = False
        self.enabled = True
        self.visible = True

    def update(self, mouse_pos: Tuple[int, int]):
        """Update button hover state."""
        if self.visible and self.enabled:
            self.hovered = self.rect.collidepoint(mouse_pos)
        else:
            self.hovered = False

    def draw(self, screen: pygame.Surface):
        """Draw the button."""
        if not self.visible:
            return

        color = self.hover_color if self.hovered else self.color
        if not self.enabled:
            color = DARK_GRAY

        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)

        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, mouse_pos: Tuple[int, int], mouse_pressed: bool) -> bool:
        """Check if button was clicked."""
        return (self.visible and self.enabled and
                self.rect.collidepoint(mouse_pos) and mouse_pressed)


# =============================================================================
# TEXT INPUT
# =============================================================================

class TextInput:
    """Simple text input UI component."""

    def __init__(self, x: int, y: int, width: int, height: int,
                 placeholder: str = "", font_size: int = 28):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = ""
        self.placeholder = placeholder
        self.font = pygame.font.Font(None, font_size)
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0.0
        self.max_length = 50

    def handle_event(self, event: pygame.event.Event):
        """Handle input events."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif event.unicode.isprintable() and len(self.text) < self.max_length:
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
            pygame.draw.line(screen, BLACK,
                           (cursor_x, self.rect.y + 5),
                           (cursor_x, self.rect.y + self.rect.height - 5), 2)

    def clear(self):
        """Clear the input text."""
        self.text = ""


# =============================================================================
# HUD BUTTON (Icon-based)
# =============================================================================

class HUDButton:
    """HUD button with icon support."""

    def __init__(self, x: int, y: int, size: int, icon: Optional[pygame.Surface] = None,
                 label: str = "", hotkey: str = ""):
        self.rect = pygame.Rect(x, y, size, size)
        self.icon = icon
        self.label = label
        self.hotkey = hotkey
        self.hovered = False
        self.enabled = True
        self.selected = False
        self.font = pygame.font.Font(None, 20)

    def set_icon(self, icon: pygame.Surface):
        """Set button icon."""
        # Scale to fit
        icon_size = self.rect.width - 10
        self.icon = pygame.transform.scale(icon, (icon_size, icon_size))

    def update(self, mouse_pos: Tuple[int, int]):
        """Update button state."""
        self.hovered = self.enabled and self.rect.collidepoint(mouse_pos)

    def draw(self, screen: pygame.Surface):
        """Draw the HUD button."""
        # Background
        if self.selected:
            color = LIGHT_GRAY
        elif self.hovered:
            color = (160, 160, 160)
        else:
            color = GRAY

        if not self.enabled:
            color = DARK_GRAY

        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)

        # Icon
        if self.icon:
            icon_rect = self.icon.get_rect(center=self.rect.center)
            screen.blit(self.icon, icon_rect)

        # Label below button
        if self.label:
            label_surf = self.font.render(self.label, True, WHITE)
            screen.blit(label_surf, (self.rect.x, self.rect.bottom + 2))

    def is_clicked(self, mouse_pos: Tuple[int, int], clicked: bool) -> bool:
        """Check if clicked."""
        return self.enabled and self.rect.collidepoint(mouse_pos) and clicked


# =============================================================================
# HEALTH BAR
# =============================================================================

def draw_health_bar(screen: pygame.Surface, pos: Tuple[int, int],
                   health: int, max_health: int, width: int,
                   height: int = 6, y_offset: int = -25):
    """
    Draw a health bar.

    Args:
        screen: Surface to draw on
        pos: Center position (x, y)
        health: Current health
        max_health: Maximum health
        width: Bar width in pixels
        height: Bar height in pixels
        y_offset: Vertical offset from pos
    """
    x = pos[0] - width // 2
    y = pos[1] + y_offset

    # Background (red)
    pygame.draw.rect(screen, RED, (x, y, width, height))

    # Health (green)
    health_width = int(width * (health / max_health))
    if health_width > 0:
        pygame.draw.rect(screen, GREEN, (x, y, health_width, height))

    # Border
    pygame.draw.rect(screen, BLACK, (x, y, width, height), 1)


# =============================================================================
# MINIMAP
# =============================================================================

class Minimap:
    """Minimap display."""

    def __init__(self, x: int, y: int, size: int, map_width: int, map_height: int):
        self.rect = pygame.Rect(x, y, size, size)
        self.map_width = map_width
        self.map_height = map_height
        self.scale_x = size / map_width
        self.scale_y = size / map_height
        self.background_color = (34, 100, 34)

    def draw(self, screen: pygame.Surface, units: list, buildings: list,
            camera_rect: pygame.Rect, player_team, enemy_team):
        """
        Draw the minimap.

        Args:
            screen: Surface to draw on
            units: List of units to display
            buildings: List of buildings to display
            camera_rect: Current camera viewport rectangle
            player_team: Team enum for player
            enemy_team: Team enum for enemy
        """
        # Background
        pygame.draw.rect(screen, self.background_color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)

        # Draw buildings
        for building in buildings:
            color = (50, 50, 200) if building.team == player_team else (200, 50, 50)
            x = self.rect.x + int(building.x * self.scale_x)
            y = self.rect.y + int(building.y * self.scale_y)
            size = 6 if building.building_type.name == 'CASTLE' else 4
            pygame.draw.rect(screen, color,
                           (x - size // 2, y - size // 2, size, size))

        # Draw units with different sizes based on unit type
        for unit in units:
            color = (50, 50, 200) if unit.team == player_team else (200, 50, 50)
            x = self.rect.x + int(unit.x * self.scale_x)
            y = self.rect.y + int(unit.y * self.scale_y)
            # Different sizes for different unit types
            unit_type_name = unit.unit_type.name
            if unit_type_name == 'PEASANT':
                radius = 1
            elif unit_type_name == 'KNIGHT':
                radius = 2
            elif unit_type_name == 'CAVALRY':
                radius = 3
            elif unit_type_name == 'CANNON':
                radius = 4
            else:
                radius = 2
            pygame.draw.circle(screen, color, (x, y), radius)

        # Draw camera viewport
        cam_x = self.rect.x + int(camera_rect.x * self.scale_x)
        cam_y = self.rect.y + int(camera_rect.y * self.scale_y)
        cam_w = int(camera_rect.width * self.scale_x)
        cam_h = int(camera_rect.height * self.scale_y)
        pygame.draw.rect(screen, WHITE, (cam_x, cam_y, cam_w, cam_h), 1)

    def get_world_pos(self, screen_pos: Tuple[int, int]) -> Optional[Tuple[float, float]]:
        """
        Convert minimap click to world position.

        Args:
            screen_pos: Screen position of click

        Returns:
            World position or None if click was outside minimap
        """
        if not self.rect.collidepoint(screen_pos):
            return None

        rel_x = screen_pos[0] - self.rect.x
        rel_y = screen_pos[1] - self.rect.y

        world_x = rel_x / self.scale_x
        world_y = rel_y / self.scale_y

        return (world_x, world_y)


# =============================================================================
# RESOURCE DISPLAY
# =============================================================================

class ResourceDisplay:
    """Display for player resources."""

    def __init__(self, x: int, y: int, font_size: int = 24, spacing: int = 25):
        self.x = x
        self.y = y
        self.font = pygame.font.Font(None, font_size)
        self.spacing = spacing

    def draw(self, screen: pygame.Surface, gold: int, food: int, wood: int):
        """Draw resource values."""
        resources = [
            (f"Gold: {gold}", GOLD),
            (f"Food: {food}", GREEN),
            (f"Wood: {wood}", BROWN)
        ]

        for i, (text, color) in enumerate(resources):
            text_surf = self.font.render(text, True, color)
            screen.blit(text_surf, (self.x, self.y + i * self.spacing))


# =============================================================================
# SELECTION INFO
# =============================================================================

class SelectionInfo:
    """Display info about selected units/buildings."""

    def __init__(self, x: int, y: int, font_size: int = 24):
        self.x = x
        self.y = y
        self.font = pygame.font.Font(None, font_size)

    def draw(self, screen: pygame.Surface, selected_units: list,
            selected_building=None):
        """Draw selection information."""
        if selected_units:
            text = f"Selected: {len(selected_units)} unit(s)"
            if len(selected_units) == 1:
                unit = selected_units[0]
                text += f" - {unit.unit_type.name} HP: {unit.health}/{unit.max_health}"
        elif selected_building:
            text = f"Selected: {selected_building.building_type.name}"
            text += f" HP: {selected_building.health}/{selected_building.max_health}"
        else:
            return

        text_surf = self.font.render(text, True, WHITE)
        screen.blit(text_surf, (self.x, self.y))


# =============================================================================
# TOOLTIP
# =============================================================================

class Tooltip:
    """Tooltip display for hovering over elements."""

    def __init__(self):
        self.font = pygame.font.Font(None, 22)
        self.padding = 5
        self.visible = False
        self.text = ""
        self.pos = (0, 0)

    def show(self, text: str, pos: Tuple[int, int]):
        """Show tooltip with text at position."""
        self.text = text
        self.pos = pos
        self.visible = True

    def hide(self):
        """Hide tooltip."""
        self.visible = False

    def draw(self, screen: pygame.Surface):
        """Draw tooltip if visible."""
        if not self.visible or not self.text:
            return

        text_surf = self.font.render(self.text, True, BLACK)
        width = text_surf.get_width() + self.padding * 2
        height = text_surf.get_height() + self.padding * 2

        # Position tooltip (adjust if off screen)
        x = self.pos[0]
        y = self.pos[1] - height - 5

        if x + width > constants.SCREEN_WIDTH:
            x = constants.SCREEN_WIDTH - width
        if y < 0:
            y = self.pos[1] + 20

        # Background
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (255, 255, 220), rect)
        pygame.draw.rect(screen, BLACK, rect, 1)

        # Text
        screen.blit(text_surf, (x + self.padding, y + self.padding))
