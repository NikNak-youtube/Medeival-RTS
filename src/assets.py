"""
Asset management with mod support.

ASSET NAMING CONVENTION:
========================
All assets follow a clear naming pattern for easy identification:

UNITS:
  - unit_peasant.png      : Worker/gatherer unit
  - unit_knight.png       : Heavy infantry unit
  - unit_cavalry.png      : Mounted unit (horse + rider)
  - unit_cannon.png       : Siege weapon

BUILDINGS:
  - building_house.png    : Population/gold building
  - building_castle.png   : Main base/spawn point
  - building_farm.png     : Food/wood production

TERRAIN:
  - terrain_grass.png     : Basic ground tile
  - terrain_stone.png     : Stone floor tile

EFFECTS:
  - effect_blood.png      : Combat damage effect

MOD SUPPORT:
============
To create a mod, create a folder in the 'mods' directory with:
  - mod.json              : Mod configuration file
  - images/               : Override images (use same naming convention)
  - data/                 : Override game data (units.json, buildings.json)

See mods/example_mod for a template.
"""

import pygame
import json
import os
from typing import Dict, Tuple, Optional, List
from .constants import TILE_SIZE, UNIT_STATS, UNIT_COSTS, BUILDING_STATS, BUILDING_COSTS


# =============================================================================
# ASSET REGISTRY - Maps logical names to actual filenames
# =============================================================================

DEFAULT_ASSET_REGISTRY = {
    # Units
    'unit_peasant': {
        'file': 'medieval-peasant-clothing-png-ujr66-mwoizzpaozyw3l2a-1145509706.png',
        'size': (40, 56),
        'description': 'Peasant worker unit'
    },
    'unit_knight': {
        'file': 'medival_knight_PNG15938-1540327347.png',
        'size': (48, 64),
        'description': 'Knight infantry unit'
    },
    'unit_cavalry': {
        'file': 'bay-sport-horse-isolated-on-transparent-background-generate-ai-free-png-4198957791.png',
        'size': (64, 56),
        'description': 'Cavalry mounted unit'
    },
    'unit_cannon': {
        'file': 'medieval-cannon-3d-elements-transparent-background-png-2980523749.png',
        'size': (56, 48),
        'description': 'Cannon siege weapon'
    },

    # Buildings
    'building_house': {
        'file': 'pngtree-3d-medieval-house-png-image_13118176-4238177977.png',
        'size': (80, 80),
        'description': 'House - generates gold'
    },
    'building_castle': {
        'file': 'ancient-stone-castle-transparent-background_1101614-40027-3216294613.jpg',
        'size': (128, 128),
        'description': 'Castle - main base'
    },
    'building_farm': {
        'file': 'farmland.png',
        'size': (96, 96),
        'description': 'Farm - generates food and wood'
    },

    # Terrain
    'terrain_grass': {
        'file': 'tileable_grass_01-1560797743.png',
        'size': (TILE_SIZE, TILE_SIZE),
        'description': 'Grass terrain tile'
    },
    'terrain_stone': {
        'file': 'Stone_Floor-2623938694.png',
        'size': (TILE_SIZE, TILE_SIZE),
        'description': 'Stone floor tile'
    },

    # Effects
    'effect_blood': {
        'file': 'Blood-Splatter-Transparent-File-3969082743.png',
        'size': (32, 32),
        'description': 'Blood splatter effect'
    }
}


# =============================================================================
# MOD MANAGER
# =============================================================================

class ModManager:
    """Manages loading and applying game mods."""

    def __init__(self, mods_directory: str = "mods"):
        self.mods_directory = mods_directory
        self.loaded_mods: List[dict] = []
        self.asset_overrides: Dict[str, dict] = {}
        self.unit_stat_overrides: Dict[str, dict] = {}
        self.unit_cost_overrides: Dict[str, dict] = {}
        self.building_stat_overrides: Dict[str, dict] = {}
        self.building_cost_overrides: Dict[str, dict] = {}

    def discover_mods(self) -> List[str]:
        """Discover available mods in the mods directory."""
        mods = []
        if not os.path.exists(self.mods_directory):
            return mods

        for item in os.listdir(self.mods_directory):
            mod_path = os.path.join(self.mods_directory, item)
            mod_json = os.path.join(mod_path, "mod.json")
            if os.path.isdir(mod_path) and os.path.exists(mod_json):
                mods.append(item)
        return mods

    def load_mod(self, mod_name: str) -> bool:
        """Load a specific mod."""
        mod_path = os.path.join(self.mods_directory, mod_name)
        mod_json_path = os.path.join(mod_path, "mod.json")

        if not os.path.exists(mod_json_path):
            print(f"Mod '{mod_name}' has no mod.json")
            return False

        try:
            with open(mod_json_path, 'r') as f:
                mod_config = json.load(f)

            mod_config['_path'] = mod_path
            self.loaded_mods.append(mod_config)

            # Load asset overrides
            self._load_asset_overrides(mod_path, mod_config)

            # Load data overrides
            self._load_data_overrides(mod_path)

            print(f"Loaded mod: {mod_config.get('name', mod_name)} v{mod_config.get('version', '1.0')}")
            return True

        except Exception as e:
            print(f"Failed to load mod '{mod_name}': {e}")
            return False

    def load_all_mods(self):
        """Load all discovered mods."""
        for mod_name in self.discover_mods():
            self.load_mod(mod_name)

    def _load_asset_overrides(self, mod_path: str, mod_config: dict):
        """Load asset overrides from a mod."""
        images_path = os.path.join(mod_path, "images")
        if not os.path.exists(images_path):
            return

        # Check for assets.json which maps asset names to files
        assets_json = os.path.join(mod_path, "assets.json")
        if os.path.exists(assets_json):
            with open(assets_json, 'r') as f:
                custom_assets = json.load(f)
            for asset_name, asset_data in custom_assets.items():
                # Skip comments and non-dict entries
                if asset_name.startswith('_') or not isinstance(asset_data, dict):
                    continue
                asset_data['_mod_path'] = images_path
                self.asset_overrides[asset_name] = asset_data
        else:
            # Auto-detect based on naming convention
            for filename in os.listdir(images_path):
                if filename.endswith(('.png', '.jpg', '.jpeg')):
                    # Extract asset name from filename (e.g., unit_knight.png -> unit_knight)
                    asset_name = os.path.splitext(filename)[0]
                    if asset_name in DEFAULT_ASSET_REGISTRY:
                        self.asset_overrides[asset_name] = {
                            'file': filename,
                            'size': DEFAULT_ASSET_REGISTRY[asset_name]['size'],
                            '_mod_path': images_path
                        }

    def _load_data_overrides(self, mod_path: str):
        """Load game data overrides from a mod."""
        data_path = os.path.join(mod_path, "data")
        if not os.path.exists(data_path):
            return

        # Load unit overrides
        units_json = os.path.join(data_path, "units.json")
        if os.path.exists(units_json):
            with open(units_json, 'r') as f:
                units_data = json.load(f)
            if 'stats' in units_data and isinstance(units_data['stats'], dict):
                # Filter out comment keys (starting with _)
                for key, value in units_data['stats'].items():
                    if not key.startswith('_') and isinstance(value, dict):
                        self.unit_stat_overrides[key] = value
            if 'costs' in units_data and isinstance(units_data['costs'], dict):
                for key, value in units_data['costs'].items():
                    if not key.startswith('_') and isinstance(value, dict):
                        self.unit_cost_overrides[key] = value

        # Load building overrides
        buildings_json = os.path.join(data_path, "buildings.json")
        if os.path.exists(buildings_json):
            with open(buildings_json, 'r') as f:
                buildings_data = json.load(f)
            if 'stats' in buildings_data and isinstance(buildings_data['stats'], dict):
                for key, value in buildings_data['stats'].items():
                    if not key.startswith('_') and isinstance(value, dict):
                        self.building_stat_overrides[key] = value
            if 'costs' in buildings_data and isinstance(buildings_data['costs'], dict):
                for key, value in buildings_data['costs'].items():
                    if not key.startswith('_') and isinstance(value, dict):
                        self.building_cost_overrides[key] = value

    def get_asset_info(self, asset_name: str) -> dict:
        """Get asset info, checking mod overrides first."""
        if asset_name in self.asset_overrides:
            return self.asset_overrides[asset_name]
        return DEFAULT_ASSET_REGISTRY.get(asset_name, {})

    def get_unit_stats(self, unit_type: str) -> dict:
        """Get unit stats with mod overrides applied."""
        base_stats = UNIT_STATS.get(unit_type, {}).copy()
        if unit_type in self.unit_stat_overrides:
            base_stats.update(self.unit_stat_overrides[unit_type])
        return base_stats

    def get_unit_costs(self, unit_type: str) -> dict:
        """Get unit costs with mod overrides applied."""
        base_costs = UNIT_COSTS.get(unit_type, {}).copy()
        if unit_type in self.unit_cost_overrides:
            base_costs.update(self.unit_cost_overrides[unit_type])
        return base_costs

    def get_building_stats(self, building_type: str) -> dict:
        """Get building stats with mod overrides applied."""
        base_stats = BUILDING_STATS.get(building_type, {}).copy()
        if building_type in self.building_stat_overrides:
            base_stats.update(self.building_stat_overrides[building_type])
        return base_stats

    def get_building_costs(self, building_type: str) -> dict:
        """Get building costs with mod overrides applied."""
        base_costs = BUILDING_COSTS.get(building_type, {}).copy()
        if building_type in self.building_cost_overrides:
            base_costs.update(self.building_cost_overrides[building_type])
        return base_costs


# =============================================================================
# ASSET MANAGER
# =============================================================================

class AssetManager:
    """Manages loading and caching of game assets with mod support."""

    def __init__(self, base_path: str = "images", mod_manager: Optional[ModManager] = None):
        self.base_path = base_path
        self.mod_manager = mod_manager or ModManager()
        self.images: Dict[str, pygame.Surface] = {}
        self._placeholder_colors = {
            'unit_knight': (50, 50, 200),
            'unit_peasant': (139, 90, 43),
            'unit_cavalry': (139, 90, 43),
            'unit_cannon': (64, 64, 64),
            'building_house': (128, 128, 128),
            'building_castle': (64, 64, 64),
            'building_farm': (34, 139, 34),
            'terrain_grass': (50, 200, 50),
            'terrain_stone': (128, 128, 128),
            'effect_blood': (200, 50, 50)
        }

    def load_all_assets(self):
        """Load all game assets."""
        for asset_name in DEFAULT_ASSET_REGISTRY.keys():
            self._load_asset(asset_name)

    def _load_asset(self, asset_name: str):
        """Load a single asset, checking mod overrides first."""
        asset_info = self.mod_manager.get_asset_info(asset_name)

        if not asset_info:
            self.images[asset_name] = self._create_placeholder(asset_name, (32, 32))
            return

        # Determine file path
        if '_mod_path' in asset_info:
            file_path = os.path.join(asset_info['_mod_path'], asset_info['file'])
        else:
            file_path = os.path.join(self.base_path, asset_info['file'])

        size = asset_info.get('size', (64, 64))

        try:
            img = pygame.image.load(file_path).convert_alpha()
            self.images[asset_name] = pygame.transform.scale(img, size)
        except pygame.error as e:
            print(f"Warning: Could not load '{asset_name}' from {file_path}: {e}")
            self.images[asset_name] = self._create_placeholder(asset_name, size)

    def _create_placeholder(self, asset_name: str, size: Tuple[int, int]) -> pygame.Surface:
        """Create a placeholder surface for missing assets."""
        surf = pygame.Surface(size, pygame.SRCALPHA)
        color = self._placeholder_colors.get(asset_name, (255, 255, 255))
        surf.fill(color)
        return surf

    def get(self, asset_name: str) -> pygame.Surface:
        """Get an asset by name."""
        if asset_name not in self.images:
            self._load_asset(asset_name)
        return self.images.get(asset_name, self._create_placeholder(asset_name, (32, 32)))

    def get_scaled(self, asset_name: str, size: Tuple[int, int]) -> pygame.Surface:
        """Get an asset scaled to a specific size."""
        base = self.get(asset_name)
        return pygame.transform.scale(base, size)

    def reload_assets(self):
        """Reload all assets (useful after loading new mods)."""
        self.images.clear()
        self.load_all_assets()


# =============================================================================
# ASSET NAME MAPPINGS (for backward compatibility and convenience)
# =============================================================================

# Maps game entity types to asset names
UNIT_ASSET_MAP = {
    'PEASANT': 'unit_peasant',
    'KNIGHT': 'unit_knight',
    'CAVALRY': 'unit_cavalry',
    'CANNON': 'unit_cannon'
}

BUILDING_ASSET_MAP = {
    'HOUSE': 'building_house',
    'CASTLE': 'building_castle',
    'FARM': 'building_farm'
}


def get_unit_asset_name(unit_type) -> str:
    """Get the asset name for a unit type."""
    if hasattr(unit_type, 'name'):
        return UNIT_ASSET_MAP.get(unit_type.name, 'unit_peasant')
    return UNIT_ASSET_MAP.get(str(unit_type).upper(), 'unit_peasant')


def get_building_asset_name(building_type) -> str:
    """Get the asset name for a building type."""
    if hasattr(building_type, 'name'):
        return BUILDING_ASSET_MAP.get(building_type.name, 'building_house')
    return BUILDING_ASSET_MAP.get(str(building_type).upper(), 'building_house')
