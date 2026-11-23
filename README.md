# Ware_House_Robot

A 2D, top-down multi-robot warehouse simulation with a Master AI coordinator for
inbound storage and outbound retrieval. It is an evolving foundation for
reinforcement-learning experiments.

## Setup and run

Install Python 3, install Pygame, then run:

```bash
python -m pip install pygame
python main.py
```

## Architecture

- `warehouse_map.py` defines the grid, shelves, storage, and warehouse zones.
- `robot.py` implements robot movement and task execution.
- `master_ai.py` coordinates orders, robot assignments, and A* routing.
- `main.py` runs the Pygame simulation and renders controls and metrics.

See [CHANGELOG.md](CHANGELOG.md) for build progress and planned milestones.
