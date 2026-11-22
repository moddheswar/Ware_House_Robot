"""Static map and rendering for the top-down warehouse simulation."""

from __future__ import annotations

import pygame

from config import COLORS, FPS, GRID_HEIGHT, GRID_WIDTH, TILE_SIZE

WALL = "wall"
FLOOR = "floor"
SHELF = "shelf"
INBOUND = "inbound"
OUTBOUND = "outbound"
HOME = "home"


class WarehouseMap:
    """Grid layout, storage contents, and drawing for the warehouse."""

    def __init__(self) -> None:
        self.tiles = [[FLOOR for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.walkable = [[True for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.storage: list[list[str | None]] = [
            [None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)
        ]
        self.shelf_cells: set[tuple[int, int]] = set()
        self.inbound_dock: set[tuple[int, int]] = set()
        self.outbound_dropoff: set[tuple[int, int]] = set()
        self.robot_home: set[tuple[int, int]] = set()

        self._build_layout()

    def _build_layout(self) -> None:
        for x in range(GRID_WIDTH):
            self._set_tile(x, 0, WALL, walkable=False)
            self._set_tile(x, GRID_HEIGHT - 1, WALL, walkable=False)
        for y in range(GRID_HEIGHT):
            self._set_tile(0, y, WALL, walkable=False)
            self._set_tile(GRID_WIDTH - 1, y, WALL, walkable=False)

        for y in range(3, 8):
            for x in range(1, 4):
                self._set_tile(x, y, INBOUND)
                self.inbound_dock.add((x, y))
            for x in range(GRID_WIDTH - 4, GRID_WIDTH - 1):
                self._set_tile(x, y, OUTBOUND)
                self.outbound_dropoff.add((x, y))

        for y in range(14, GRID_HEIGHT - 1):
            for x in range(8, 16):
                self._set_tile(x, y, HOME)
                self.robot_home.add((x, y))

        # Shelf rows are separated by clear horizontal aisles. Side corridors
        # remain open so robots can move between aisle rows.
        for y in (3, 6, 9, 12):
            for x in range(6, 18):
                self._set_tile(x, y, SHELF, walkable=False)
                self.shelf_cells.add((x, y))

    def _set_tile(self, x: int, y: int, tile: str, walkable: bool = True) -> None:
        self.tiles[y][x] = tile
        self.walkable[y][x] = walkable

    def draw(self, surface: pygame.Surface) -> None:
        """Render the grid, storage, and marked warehouse zones."""
        shelf_font = pygame.font.Font(None, 18)
        zone_font = pygame.font.Font(None, 22)
        tile_colors = {
            FLOOR: COLORS["FLOOR"],
            WALL: COLORS["WALL"],
            SHELF: COLORS["SHELF"],
            INBOUND: COLORS["INBOUND"],
            OUTBOUND: COLORS["OUTBOUND"],
            HOME: COLORS["HOME"],
        }

        for y, row in enumerate(self.tiles):
            for x, tile in enumerate(row):
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(surface, tile_colors[tile], rect)

                if tile == SHELF:
                    self._draw_shelf(surface, x, y, rect, shelf_font)
                pygame.draw.rect(surface, COLORS["GRID"], rect, 1)

        self._draw_zone_label(surface, "INBOUND", self.inbound_dock, zone_font)
        self._draw_zone_label(surface, "OUT", self.outbound_dropoff, zone_font)
        self._draw_zone_label(surface, "HOME", self.robot_home, zone_font)

    def _draw_shelf(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        rect: pygame.Rect,
        font: pygame.font.Font,
    ) -> None:
        pygame.draw.rect(surface, COLORS["SHELF_EDGE"], rect, 2)
        container_type = self.storage[y][x]
        if container_type is None:
            marker_color = COLORS["EMPTY_STORAGE"]
            count = "0"
        else:
            marker_color = COLORS[container_type]
            count = "1"

        marker = rect.inflate(-12, -12)
        pygame.draw.rect(surface, marker_color, marker, border_radius=4)
        label = font.render(count, True, COLORS["TEXT"])
        surface.blit(label, label.get_rect(center=rect.center))

    def _draw_zone_label(
        self,
        surface: pygame.Surface,
        text: str,
        cells: set[tuple[int, int]],
        font: pygame.font.Font,
    ) -> None:
        if not cells:
            return
        center_x = sum(x for x, _ in cells) / len(cells)
        center_y = sum(y for _, y in cells) / len(cells)
        label = font.render(text, True, COLORS["TEXT"])
        center = (
            round((center_x + 0.5) * TILE_SIZE),
            round((center_y + 0.5) * TILE_SIZE),
        )
        surface.blit(label, label.get_rect(center=center))


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode(
        (GRID_WIDTH * TILE_SIZE, GRID_HEIGHT * TILE_SIZE)
    )
    pygame.display.set_caption("Warehouse Map")
    clock = pygame.time.Clock()
    warehouse = WarehouseMap()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill(COLORS["BACKGROUND"])
        warehouse.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
