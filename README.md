# Medieval RTS

A real-time strategy game built with Python and Pygame, featuring single-player AI battles and multiplayer support.

## Features

- **Single Player**: Battle against an AI opponent with 4 difficulty levels
- **Multiplayer**: Host or join games via IP address
- **Resource Management**: Gather gold, food, and wood to build your army
- **Building Construction**: Place buildings and assign peasants to construct them
- **Unit Production**: Train peasants, knights, cavalry, and cannons
- **Mod Support**: Customize units, buildings, and assets via JSON mods

## Installation

### Requirements
- Python 3.10+
- Pygame 2.0+

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd "Medieval RTS"

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install pygame

# Run the game
python game.py
```

## How to Play

### Objective
Destroy the enemy's castle while protecting your own.

### Controls

All actions can be performed via mouse clicks on the HUD buttons OR keyboard shortcuts:

| Action | Keyboard | Mouse |
|--------|----------|-------|
| Move Camera | WASD / Arrow Keys | Move mouse to screen edge |
| Select Units | Left Click / Drag Box | Click unit or drag selection |
| Move/Attack | Right Click | Click on ground/enemy |
| Train Peasant | P | Click Peasant button |
| Train Knight | K | Click Knight button |
| Train Cavalry | C | Click Cavalry button |
| Train Cannon | N | Click Cannon button |
| Build House | H | Click House button |
| Build Farm | F | Click Farm button |
| Build Tower | T | Click Tower button |
| Attack-Move | A + Right Click | Click ATK button, then right-click |
| Stop/Cancel | S | Click STP button |
| Deconstruct | X | Click DEL button (with building selected) |
| Toggle Fullscreen | F11 | Settings menu |
| Return to Menu | ESC | Click ESC button |

### Resources

| Resource | Source | Used For |
|----------|--------|----------|
| **Gold** | Houses (with workers) | All units and buildings |
| **Food** | Farms (with workers) | Units (consumed over time) |
| **Wood** | Farms (with workers) | Buildings and Cannons |

### Units

| Unit | Cost | Stats | Role |
|------|------|-------|------|
| **Peasant** | 50g, 25f | Low HP/attack, fast | Workers, construction |
| **Knight** | 150g, 50f | High HP/defense, slow | Heavy infantry |
| **Cavalry** | 200g, 75f | Medium HP, very fast | Rapid assault |
| **Cannon** | 300g, 100w | Low HP, high range/damage | Siege, long-range |

### Buildings

| Building | Cost | Build Time | Function |
|----------|------|------------|----------|
| **Castle** | N/A | N/A | Starting building, trains units |
| **House** | 100g, 50w | 10s | Generates gold (max 2 workers) |
| **Farm** | 75g, 25w | 8s | Generates food & wood (max 3 workers) |
| **Tower** | 200g, 100w | 15s | Defensive structure, attacks enemies (requires 2 workers) |

### Mechanics

#### Building Construction
1. Click a building button (H for House, F for Farm, T for Tower)
2. Click on the map to place the foundation
3. Select a peasant and right-click on the foundation
4. The peasant will construct the building (progress bar shown)
5. Multiple peasants build faster (with diminishing returns)

#### Worker Assignment
- Right-click a peasant on a **completed** building to assign them as a worker
- Workers generate resources every 5 seconds
- Yellow circle indicator shows actively working peasants

#### Food Consumption
- Every 10 seconds, each unit consumes 2 food
- If food runs out, units take 5 damage per tick (starvation)
- Build farms and assign workers to produce food!

#### Attack-Move
- Press A (or click ATK), then right-click a destination
- Units will move toward the target, attacking any enemies along the way
- Red circle shows units in attack-move mode

#### Deconstruction
- Select a building (not castle) and press X (or click DEL)
- Returns 70% of resources (scaled by building health)

#### Auto-Attack
- Military units (Knight, Cavalry, Cannon) automatically engage nearby enemies
- Attack range: 3x their weapon range for auto-aggro

#### Towers

- Towers are defensive buildings that automatically attack nearby enemies
- Requires **2 peasant workers** assigned to operate
- High damage (60), long range (250), but only 70% hit chance
- Build towers to defend your base from enemy attacks

### Difficulty Levels

| Difficulty | AI Speed | Resources | Aggression | Max Military |
|------------|----------|-----------|------------|--------------|
| **Easy** | 0.5x | 0.8x | Low | 5 units |
| **Normal** | 1.0x | 1.0x | Medium | 8 units |
| **Hard** | 1.5x | 1.2x | High | 12 units |
| **Brutal** | 2.0x | 1.5x | Very High | 20 units |

### Multiplayer

1. **Host**: Click "Host Multiplayer" and share your IP address
2. **Join**: Click "Join Multiplayer", enter host's IP, click Connect
3. Host must click "Accept" when a player connects

## Project Structure

```
Medieval RTS/
├── game.py              # Main entry point
├── src/
│   ├── __init__.py      # Package init
│   ├── constants.py     # Game settings, costs, enums
│   ├── entities.py      # Unit, Building, Resources, Effects
│   ├── game.py          # Main Game class, game loop
│   ├── ai.py            # AI opponent logic
│   ├── network.py       # Multiplayer networking
│   ├── camera.py        # Camera/viewport handling
│   ├── assets.py        # Asset loading, mod support
│   └── ui.py            # UI components (buttons, HUD)
├── images/              # Game sprites and textures
├── mods/                # Mod folder
│   ├── README.md        # Mod documentation
│   └── example_mod/     # Example mod template
└── venv/                # Python virtual environment
```

## Codebase Overview

### Core Classes

#### `Game` (src/game.py)
Main game controller handling:
- Game state machine (menu, playing, game over, etc.)
- Event handling (mouse, keyboard)
- Update loop (units, buildings, AI, resources)
- Rendering (terrain, entities, HUD, minimap)

#### `Unit` (src/entities.py)
Represents game units with:
- Position, health, attack/defense stats
- Movement and targeting
- Worker assignment (for peasants)
- Attack-move support

#### `Building` (src/entities.py)
Represents structures with:
- Construction progress system
- Worker slots for resource generation
- Health and damage handling

#### `AIBot` (src/ai.py)
Computer opponent with:
- State machine (building, attacking, defending)
- Economic decisions (build farms, houses)
- Military decisions (train units, attack)
- Difficulty-scaled behavior

#### `AssetManager` (src/assets.py)
Handles:
- Image loading and caching
- Asset scaling
- Mod asset overrides

### Key Constants (src/constants.py)

```python
# Display
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
MAP_WIDTH = 2000
MAP_HEIGHT = 2000

# Resources
STARTING_GOLD = 500
STARTING_FOOD = 200
STARTING_WOOD = 300

# Timing
RESOURCE_TICK_INTERVAL = 5.0  # seconds
FOOD_CONSUMPTION_INTERVAL = 10.0  # seconds
```

## Modding

Create mods in the `mods/` folder. Each mod needs:

```
mods/your_mod/
├── mod.json           # Mod metadata
├── assets.json        # Asset overrides (optional)
└── data/
    ├── units.json     # Unit stat overrides (optional)
    └── buildings.json # Building stat overrides (optional)
```

### Example mod.json
```json
{
  "name": "My Mod",
  "version": "1.0.0",
  "description": "A custom mod"
}
```

### Example units.json
```json
{
  "knight": {
    "health": 200,
    "attack": 30,
    "defense": 20,
    "speed": 2.0
  }
}
```

See `mods/example_mod/` for a complete template.

## Assets

The game uses these image assets from the `images/` folder:

| Asset | File | Used For |
|-------|------|----------|
| Grass terrain | tileable_grass_01-*.png | Map background |
| Castle | ancient-stone-castle-*.jpg | Castle building |
| House | pngtree-3d-medieval-house-*.png | House building |
| Farm | farmland.png | Farm building |
| Peasant | medieval-peasant-clothing-*.png | Peasant unit |
| Knight | medival_knight_PNG*.png | Knight unit |
| Cavalry | bay-sport-horse-*.png | Cavalry unit |
| Cannon | medieval-cannon-3d-*.png | Cannon unit |
| Blood | Blood-Splatter-*.png | Combat effects |

## License

This project is provided as-is for educational purposes.

## Troubleshooting

### "No module named 'pygame'"
Make sure you've activated the virtual environment and installed pygame:
```bash
source venv/bin/activate
pip install pygame
```

### Game runs slowly
- Reduce the map size in `src/constants.py`
- Close other applications
- The game targets 60 FPS

### Multiplayer not connecting
- Ensure both players are on the same network or have proper port forwarding
- Default port is 5555
- Check firewall settings
