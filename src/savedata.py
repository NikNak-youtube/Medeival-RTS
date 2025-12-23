"""
Save data management for player statistics, keybind presets, and settings.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

import pygame

# Default save directory
SAVE_DIR = Path("savedata")

# Default keybind presets
DEFAULT_KEYBINDS = {
    'train_peasant': pygame.K_p,
    'train_knight': pygame.K_k,
    'train_cavalry': pygame.K_c,
    'train_cannon': pygame.K_n,
    'attack_move': pygame.K_a,
    'stop': pygame.K_s,
    'heal_toggle': pygame.K_h,
    'grid_snap': pygame.K_g,
    'deconstruct': pygame.K_x,
}

KEYBIND_PRESETS = {
    'default': {
        'train_peasant': pygame.K_p,
        'train_knight': pygame.K_k,
        'train_cavalry': pygame.K_c,
        'train_cannon': pygame.K_n,
        'attack_move': pygame.K_a,
        'stop': pygame.K_s,
        'heal_toggle': pygame.K_h,
        'grid_snap': pygame.K_g,
        'deconstruct': pygame.K_x,
    },
    'wasd': {
        'train_peasant': pygame.K_1,
        'train_knight': pygame.K_2,
        'train_cavalry': pygame.K_3,
        'train_cannon': pygame.K_4,
        'attack_move': pygame.K_a,
        'stop': pygame.K_s,
        'heal_toggle': pygame.K_h,
        'grid_snap': pygame.K_g,
        'deconstruct': pygame.K_x,
    },
    'moba': {
        'train_peasant': pygame.K_q,
        'train_knight': pygame.K_w,
        'train_cavalry': pygame.K_e,
        'train_cannon': pygame.K_r,
        'attack_move': pygame.K_a,
        'stop': pygame.K_s,
        'heal_toggle': pygame.K_t,
        'grid_snap': pygame.K_g,
        'deconstruct': pygame.K_d,
    },
}


class SaveDataManager:
    """Manages saving and loading of player statistics and settings."""

    def __init__(self, save_dir: str = "savedata"):
        self.save_dir = Path(save_dir)
        self.stats_file = self.save_dir / "stats.json"
        self.keybinds_file = self.save_dir / "keybinds.json"
        self.settings_file = self.save_dir / "settings.json"

        # Player statistics
        self.stats: Dict[str, Any] = {
            # Singleplayer vs AI
            'sp_wins': 0,
            'sp_losses': 0,
            'sp_games_played': 0,
            # Multiplayer
            'mp_wins': 0,
            'mp_losses': 0,
            'mp_games_played': 0,
            # Raid mode
            'raid_games_played': 0,
            'raid_highest_wave': 0,
            'raid_total_waves_survived': 0,
            'raid_highscores': {
                'easy': 0,
                'normal': 0,
                'hard': 0,
            },
            # General stats
            'total_units_trained': 0,
            'total_buildings_built': 0,
            'total_enemies_killed': 0,
            'total_playtime_seconds': 0,
        }

        # Keybind settings
        self.keybinds: Dict[str, int] = DEFAULT_KEYBINDS.copy()
        self.current_preset: str = 'default'

        # Game settings
        self.settings: Dict[str, Any] = {
            'fullscreen': False,
            'vsync': False,
            'sound_enabled': True,
            'grid_snap': False,
            'resolution_index': 0,
            'last_difficulty': 'normal',
            'last_raid_difficulty': 'normal',
        }

        # Ensure save directory exists
        self._ensure_save_dir()

        # Load existing data
        self.load_all()

    def _ensure_save_dir(self):
        """Create the save directory if it doesn't exist."""
        if not self.save_dir.exists():
            self.save_dir.mkdir(parents=True)

    def load_all(self):
        """Load all save data."""
        self.load_stats()
        self.load_keybinds()
        self.load_settings()

    def save_all(self):
        """Save all data."""
        self.save_stats()
        self.save_keybinds()
        self.save_settings()

    # Stats management
    def load_stats(self):
        """Load player statistics from file."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults (in case new stats were added)
                    for key, value in loaded.items():
                        if key in self.stats:
                            if isinstance(value, dict) and isinstance(self.stats[key], dict):
                                self.stats[key].update(value)
                            else:
                                self.stats[key] = value
            except (json.JSONDecodeError, IOError):
                pass  # Use defaults

    def save_stats(self):
        """Save player statistics to file."""
        self._ensure_save_dir()
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except IOError:
            pass  # Silently fail

    def record_sp_win(self):
        """Record a singleplayer win."""
        self.stats['sp_wins'] += 1
        self.stats['sp_games_played'] += 1
        self.save_stats()

    def record_sp_loss(self):
        """Record a singleplayer loss."""
        self.stats['sp_losses'] += 1
        self.stats['sp_games_played'] += 1
        self.save_stats()

    def record_mp_win(self):
        """Record a multiplayer win."""
        self.stats['mp_wins'] += 1
        self.stats['mp_games_played'] += 1
        self.save_stats()

    def record_mp_loss(self):
        """Record a multiplayer loss."""
        self.stats['mp_losses'] += 1
        self.stats['mp_games_played'] += 1
        self.save_stats()

    def record_raid_game(self, wave_reached: int, difficulty: str):
        """Record a raid game result."""
        self.stats['raid_games_played'] += 1
        self.stats['raid_total_waves_survived'] += wave_reached

        if wave_reached > self.stats['raid_highest_wave']:
            self.stats['raid_highest_wave'] = wave_reached

        difficulty_key = difficulty.lower()
        if difficulty_key in self.stats['raid_highscores']:
            if wave_reached > self.stats['raid_highscores'][difficulty_key]:
                self.stats['raid_highscores'][difficulty_key] = wave_reached

        self.save_stats()

    def record_unit_trained(self, count: int = 1):
        """Record units trained."""
        self.stats['total_units_trained'] += count

    def record_building_built(self, count: int = 1):
        """Record buildings built."""
        self.stats['total_buildings_built'] += count

    def record_enemy_killed(self, count: int = 1):
        """Record enemies killed."""
        self.stats['total_enemies_killed'] += count

    def add_playtime(self, seconds: float):
        """Add to total playtime."""
        self.stats['total_playtime_seconds'] += int(seconds)

    def get_playtime_formatted(self) -> str:
        """Get formatted playtime string."""
        total_seconds = self.stats['total_playtime_seconds']
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    # Keybind management
    def load_keybinds(self):
        """Load keybinds from file."""
        if self.keybinds_file.exists():
            try:
                with open(self.keybinds_file, 'r') as f:
                    data = json.load(f)
                    if 'keybinds' in data:
                        # Convert string keys back to pygame constants
                        for action, key in data['keybinds'].items():
                            if action in self.keybinds:
                                self.keybinds[action] = key
                    if 'preset' in data:
                        self.current_preset = data['preset']
            except (json.JSONDecodeError, IOError):
                pass

    def save_keybinds(self):
        """Save keybinds to file."""
        self._ensure_save_dir()
        try:
            data = {
                'keybinds': self.keybinds,
                'preset': self.current_preset,
            }
            with open(self.keybinds_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    def apply_preset(self, preset_name: str) -> bool:
        """Apply a keybind preset."""
        if preset_name in KEYBIND_PRESETS:
            self.keybinds = KEYBIND_PRESETS[preset_name].copy()
            self.current_preset = preset_name
            self.save_keybinds()
            return True
        return False

    def get_preset_names(self) -> list:
        """Get list of available preset names."""
        return list(KEYBIND_PRESETS.keys())

    def set_keybind(self, action: str, key: int):
        """Set a single keybind."""
        if action in self.keybinds:
            self.keybinds[action] = key
            self.current_preset = 'custom'
            self.save_keybinds()

    def reset_keybinds(self):
        """Reset keybinds to default."""
        self.keybinds = DEFAULT_KEYBINDS.copy()
        self.current_preset = 'default'
        self.save_keybinds()

    # Settings management
    def load_settings(self):
        """Load game settings from file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                    for key, value in loaded.items():
                        if key in self.settings:
                            self.settings[key] = value
            except (json.JSONDecodeError, IOError):
                pass

    def save_settings(self):
        """Save game settings to file."""
        self._ensure_save_dir()
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except IOError:
            pass

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any):
        """Set a setting value."""
        self.settings[key] = value
        self.save_settings()
