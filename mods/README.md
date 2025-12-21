# Mod Support Guide

This game supports mods that can override assets, unit stats, building stats, and costs.

## Creating a Mod

1. Create a folder in the `mods/` directory with your mod name
2. Create a `mod.json` file with mod metadata
3. Add optional folders for assets and data overrides

## Mod Structure

```
mods/
└── your_mod_name/
    ├── mod.json           # Required: Mod metadata
    ├── assets.json        # Optional: Asset overrides mapping
    ├── images/            # Optional: Custom images
    │   ├── unit_knight.png
    │   ├── unit_peasant.png
    │   └── ...
    └── data/              # Optional: Game data overrides
        ├── units.json
        └── buildings.json
```

## mod.json Format

```json
{
    "name": "My Mod",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "Description of your mod",
    "game_version": "1.0.0"
}
```

## Asset Naming Convention

All assets follow a clear naming pattern:

### Units
| Asset Name | Description |
|------------|-------------|
| `unit_peasant` | Worker/gatherer unit |
| `unit_knight` | Heavy infantry unit |
| `unit_cavalry` | Mounted unit |
| `unit_cannon` | Siege weapon |

### Buildings
| Asset Name | Description |
|------------|-------------|
| `building_house` | Population/gold building |
| `building_castle` | Main base/spawn point |
| `building_farm` | Food/wood production |

### Terrain
| Asset Name | Description |
|------------|-------------|
| `terrain_grass` | Basic ground tile |
| `terrain_stone` | Stone floor tile |

### Effects
| Asset Name | Description |
|------------|-------------|
| `effect_blood` | Combat damage effect |

## Overriding Assets

### Method 1: Auto-detection
Place images in `images/` with standard names:
- `unit_knight.png` will override the knight sprite
- `building_house.png` will override the house sprite

### Method 2: assets.json
Create `assets.json` for custom filenames:

```json
{
    "unit_knight": {
        "file": "my_custom_knight.png",
        "size": [48, 64],
        "description": "My custom knight"
    }
}
```

## Overriding Game Data

### units.json

Override unit stats and/or costs:

```json
{
    "stats": {
        "knight": {
            "health": 200,
            "attack": 25,
            "defense": 20,
            "speed": 2.0,
            "range": 40,
            "cooldown": 1.0
        }
    },
    "costs": {
        "knight": {
            "gold": 100,
            "food": 40
        }
    }
}
```

#### Available Unit Stats
| Stat | Description | Default (Knight) |
|------|-------------|------------------|
| `health` | Max HP | 150 |
| `attack` | Attack damage | 20 |
| `defense` | Damage reduction | 15 |
| `speed` | Movement speed | 1.8 |
| `range` | Attack range (pixels) | 35 |
| `cooldown` | Attack cooldown (seconds) | 1.2 |

### buildings.json

Override building stats, costs, and resource generation:

```json
{
    "stats": {
        "house": {
            "health": 400
        }
    },
    "costs": {
        "house": {
            "gold": 80,
            "wood": 40
        }
    },
    "generation": {
        "house": {
            "gold": 30,
            "food": 0,
            "wood": 0,
            "max_workers": 5
        }
    }
}
```

#### Generation Options
| Option | Description | Default (House) |
|--------|-------------|-----------------|
| `gold` | Gold generated per tick | 20 |
| `food` | Food generated per tick | 0 |
| `wood` | Wood generated per tick | 0 |
| `max_workers` | Maximum workers allowed | 2 |

## Tips

1. Mods are loaded in the order shown in the Mod Manager
2. Later mods override earlier ones
3. Use PNG format with transparency for best results
4. Match the default sprite sizes for best appearance
5. Use the Mod Manager (Main Menu > Mods) to enable/disable mods and change load order

## Built-in Mods

- **unlimited_workers** - Removes worker limits from all buildings (disabled by default)

## Example Mod

See `example_mod/` for a complete template with all override options.
