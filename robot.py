"""Robot behavior for the warehouse simulation."""

from __future__ import annotations

import pygame

from config import COLORS, TILE_SIZE
from warehouse_map import WarehouseMap


class Robot:
    """A single robot that follows routes assigned by the Master AI."""

    IDLE = "IDLE"
    MOVING_TO_PICK = "MOVING_TO_PICK"
    MOVING_TO_DROP = "MOVING_TO_DROP"
    RETURNING = "RETURNING"

    STATE_COLORS = {
        IDLE: (115, 123, 132),
        MOVING_TO_PICK: (46, 139, 87),
        MOVING_TO_DROP: (218, 139, 48),
        RETURNING: (117, 91, 166),
    }

    def __init__(self, robot_id: int, x: int, y: int) -> None:
        self.id = robot_id
        self.x = x
        self.y = y
        self.state = self.IDLE
        self.carrying: str | None = None
        self.path: list[tuple[int, int]] = []
        self.wait_ticks = 0
        self.stuck_ticks = 0
        self.total_wait_ticks = 0
        self.total_distance = 0
        self.last_position: tuple[int, int] | None = None
        self.needs_repath = False

        self.target_pickup: tuple[int, int] | None = None
        self.target_dropoff: tuple[int, int] | None = None
        self.target_return: tuple[int, int] | None = None
        self._assigned_container_type: str | None = None

    def assign_task(
        self,
        target_pickup: tuple[int, int],
        target_dropoff: tuple[int, int],
        path_to_pickup: list[tuple[int, int]],
        container_type: str,
    ) -> None:
        """Store a task and its initial route supplied by the Master AI."""
        self.target_pickup = target_pickup
        self.target_dropoff = target_dropoff
        self.path = list(path_to_pickup)
        self._assigned_container_type = container_type
        self.carrying = None
        self.wait_ticks = 0
        self.stuck_ticks = 0
        self.needs_repath = False
        self.target_return = None
        self.state = self.MOVING_TO_PICK

    def step(self, warehouse_map: WarehouseMap, all_robots: list[Robot]) -> None:
        """Advance one tile, yielding or waiting when the next step is blocked."""
        self._handle_arrival(warehouse_map)

        if self.state == self.IDLE:
            return

        if not self.path:
            return

        next_x, next_y = self.path[0]
        next_position = (next_x, next_y)
        occupied = any(
            robot is not self and (robot.x, robot.y) == next_position
            for robot in all_robots
        )
        adjacent = abs(next_x - self.x) + abs(next_y - self.y) == 1
        walkable = (
            0 <= next_x < len(warehouse_map.walkable[0])
            and 0 <= next_y < len(warehouse_map.walkable)
            and warehouse_map.walkable[next_y][next_x]
        )
        if occupied or not adjacent or not walkable:
            self._record_blocked_step()
            if self.stuck_ticks >= 4 and self._try_side_step(
                warehouse_map, all_robots
            ):
                self._handle_arrival(warehouse_map)
            if not walkable or not adjacent:
                self.needs_repath = True
            return

        self._move_to(next_position)
        self.path.pop(0)
        self._handle_arrival(warehouse_map)

    def _record_blocked_step(self) -> None:
        self.wait_ticks += 1
        self.stuck_ticks += 1
        self.total_wait_ticks += 1

    def _try_side_step(
        self, warehouse_map: WarehouseMap, all_robots: list[Robot]
    ) -> bool:
        preferred = self.path[0] if self.path else (self.x, self.y)
        candidates = []
        for position in (
            (self.x + 1, self.y),
            (self.x - 1, self.y),
            (self.x, self.y + 1),
            (self.x, self.y - 1),
        ):
            x, y = position
            if (
                position == self.last_position
                or not (0 <= x < len(warehouse_map.walkable[0]))
                or not (0 <= y < len(warehouse_map.walkable))
                or not warehouse_map.walkable[y][x]
                or any(
                    robot is not self and (robot.x, robot.y) == position
                    for robot in all_robots
                )
            ):
                continue
            distance = abs(x - preferred[0]) + abs(y - preferred[1])
            candidates.append((distance, position))

        if not candidates:
            return False
        _, position = min(candidates)
        self._move_to(position)
        self.needs_repath = True
        return True

    def _move_to(self, position: tuple[int, int]) -> None:
        self.last_position = (self.x, self.y)
        self.x, self.y = position
        self.total_distance += 1
        self.wait_ticks = 0
        self.stuck_ticks = 0

    def _handle_arrival(self, warehouse_map: WarehouseMap) -> None:
        position = (self.x, self.y)
        if self.state == self.MOVING_TO_PICK and position == self.target_pickup:
            self.carrying = self._assigned_container_type
            if position in warehouse_map.shelf_cells:
                warehouse_map.storage[self.y][self.x] = None
            self.state = self.MOVING_TO_DROP
        elif self.state == self.MOVING_TO_DROP and position == self.target_dropoff:
            self.carrying = None
            self.path.clear()
            self.target_pickup = None
            self.target_dropoff = None
            self._assigned_container_type = None
            self.state = self.RETURNING
        elif self.state == self.RETURNING and (
            position == self.target_return
            or (self.target_return is None and position in warehouse_map.robot_home)
        ):
            self.path.clear()
            self.target_return = None
            self.state = self.IDLE

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the robot, its ID, state color, and carried-container marker."""
        center = (
            self.x * TILE_SIZE + TILE_SIZE // 2,
            self.y * TILE_SIZE + TILE_SIZE // 2,
        )
        radius = TILE_SIZE // 3
        pygame.draw.circle(surface, self.STATE_COLORS[self.state], center, radius)
        pygame.draw.circle(surface, COLORS["SHELF_EDGE"], center, radius, 2)

        id_font = pygame.font.Font(None, 18)
        id_label = id_font.render(str(self.id), True, COLORS["TEXT"])
        surface.blit(id_label, id_label.get_rect(center=center))

        if self.carrying is not None:
            container_color = COLORS.get(self.carrying, COLORS["TEXT"])
            indicator = pygame.Rect(0, 0, 12, 12)
            indicator.center = (center[0] + radius - 2, center[1] - radius + 2)
            pygame.draw.rect(surface, container_color, indicator, border_radius=2)
