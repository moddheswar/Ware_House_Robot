"""Shared configuration for the warehouse simulation."""

GRID_WIDTH = 24
GRID_HEIGHT = 18
TILE_SIZE = 40
FPS = 30

ROBOT_COUNT = 6
CONTAINER_TYPES = ["RED", "BLUE", "GREEN"]

COLORS = {
    "BACKGROUND": (24, 28, 34),
    "FLOOR": (215, 219, 222),
    "GRID": (184, 190, 195),
    "WALL": (65, 72, 79),
    "SHELF": (121, 92, 63),
    "SHELF_EDGE": (82, 61, 43),
    "INBOUND": (75, 145, 105),
    "OUTBOUND": (72, 126, 179),
    "HOME": (155, 151, 92),
    "TEXT": (245, 245, 245),
    "EMPTY_STORAGE": (174, 178, 181),
    "RED": (214, 67, 67),
    "BLUE": (61, 115, 208),
    "GREEN": (65, 163, 91),
}
