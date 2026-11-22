"""Order dispatch and A* routing for the warehouse robots."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
from typing import Literal

from robot import Robot
from warehouse_map import WarehouseMap


@dataclass
class _ActiveTask:
    direction: Literal["inbound", "outbound"]
    shelf: tuple[int, int]
    container_type: str
    started_at: int
    pickup_goal: tuple[int, int]
    dropoff_goal: tuple[int, int]
    picked_up: bool = False
    completed: bool = False
    return_goal: tuple[int, int] | None = None


class MasterAI:
    """Coordinates inbound storage and outbound retrieval tasks."""

    def __init__(self) -> None:
        self.inbound_orders: deque[str] = deque()
        self.outbound_orders: deque[str] = deque()

        self.completed_inbound = 0
        self.completed_outbound = 0
        self.total_wait_ticks = 0
        self.avg_task_time = 0.0

        self._tick = 0
        self._total_completed_task_ticks = 0
        self._completed_task_count = 0
        self._active_tasks: dict[Robot, _ActiveTask] = {}
        self._reserved_shelves: set[tuple[int, int]] = set()
        self._goal_reservations: dict[Robot, set[tuple[int, int]]] = {}
        self._last_robot_wait_ticks: dict[Robot, int] = {}

    def add_inbound_order(self, container_type: str) -> None:
        """Queue a container that has arrived at the inbound dock."""
        self.inbound_orders.append(container_type)

    def add_outbound_order(self, container_type: str) -> None:
        """Queue a request for a container type."""
        self.outbound_orders.append(container_type)

    @staticmethod
    def compute_path(
        start: tuple[int, int],
        goal: tuple[int, int],
        warehouse_map: WarehouseMap,
        all_robots: list[Robot] | None = None,
        active_robot: Robot | None = None,
    ) -> list[tuple[int, int]]:
        """Return A* steps after start, or [] when already at goal/unreachable."""
        height = len(warehouse_map.walkable)
        if height == 0:
            return []

        def is_walkable(position: tuple[int, int]) -> bool:
            x, y = position
            return (
                0 <= y < height
                and 0 <= x < len(warehouse_map.walkable[y])
                and warehouse_map.walkable[y][x]
            )

        if start == goal or not is_walkable(start) or not is_walkable(goal):
            return []

        occupied_costs: dict[tuple[int, int], int] = {}
        for robot in all_robots or ():
            if robot is active_robot:
                continue
            position = (robot.x, robot.y)
            occupied_costs[position] = 8
            if robot.stuck_ticks > 0:
                occupied_costs[position] += 20

        frontier: list[tuple[int, int, tuple[int, int]]] = []
        sequence = 0
        heuristic = abs(goal[0] - start[0]) + abs(goal[1] - start[1])
        heapq.heappush(frontier, (heuristic, sequence, start))
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        cost_so_far = {start: 0}
        visited: set[tuple[int, int]] = set()

        while frontier:
            _, _, current = heapq.heappop(frontier)
            if current in visited:
                continue
            visited.add(current)
            if current == goal:
                break

            x, y = current
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not is_walkable(neighbor):
                    continue
                new_cost = cost_so_far[current] + 1 + occupied_costs.get(neighbor, 0)
                if new_cost >= cost_so_far.get(neighbor, float("inf")):
                    continue

                cost_so_far[neighbor] = new_cost
                came_from[neighbor] = current
                estimate = abs(goal[0] - neighbor[0]) + abs(goal[1] - neighbor[1])
                sequence += 1
                heapq.heappush(
                    frontier, (new_cost + estimate, sequence, neighbor)
                )

        if goal not in came_from:
            return []

        path = []
        current: tuple[int, int] | None = goal
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path[1:]

    def dispatch(self, robots: list[Robot], warehouse_map: WarehouseMap) -> None:
        """Update tasks and metrics, then assign work to idle robots."""
        self._tick += 1
        self._update_wait_metrics(robots)
        self._update_active_tasks(robots, warehouse_map)
        self._refresh_displaced_robots(robots, warehouse_map)
        self._reroute_stuck_robots(robots, warehouse_map)

        for robot in robots:
            if robot.state != Robot.IDLE:
                continue
            if self._dispatch_inbound(robot, robots, warehouse_map):
                continue
            self._dispatch_outbound(robot, robots, warehouse_map)

    def _update_wait_metrics(self, robots: list[Robot]) -> None:
        for robot in robots:
            current_wait = robot.total_wait_ticks
            previous_wait = self._last_robot_wait_ticks.get(robot, 0)
            self.total_wait_ticks += max(0, current_wait - previous_wait)
            self._last_robot_wait_ticks[robot] = current_wait

    def _update_active_tasks(
        self, robots: list[Robot], warehouse_map: WarehouseMap
    ) -> None:
        for robot in robots:
            task = self._active_tasks.get(robot)
            if task is None:
                continue

            if not task.picked_up and robot.state == Robot.MOVING_TO_DROP:
                task.picked_up = True
                self._release_goal(robot, task.pickup_goal)
                if task.direction == "outbound":
                    warehouse_map.storage[task.shelf[1]][task.shelf[0]] = None
                    self._reserved_shelves.discard(task.shelf)
                robot.path = self.compute_path(
                    (robot.x, robot.y),
                    task.dropoff_goal,
                    warehouse_map,
                    robots,
                    robot,
                )
                robot.needs_repath = not robot.path and (
                    (robot.x, robot.y) != task.dropoff_goal
                )

            if robot.state == Robot.RETURNING and not task.completed:
                task.completed = True
                if task.direction == "inbound":
                    warehouse_map.storage[task.shelf[1]][task.shelf[0]] = (
                        task.container_type
                    )
                    self.completed_inbound += 1
                else:
                    self.completed_outbound += 1

                self._total_completed_task_ticks += self._tick - task.started_at
                self._completed_task_count += 1
                self.avg_task_time = (
                    self._total_completed_task_ticks / self._completed_task_count
                )
                self._reserved_shelves.discard(task.shelf)
                self._release_goal(robot, task.dropoff_goal)
                self._assign_return_path(robot, task, robots, warehouse_map)

            if (
                robot.state == Robot.RETURNING
                and task.completed
                and task.return_goal is None
            ):
                self._assign_return_path(robot, task, robots, warehouse_map)

            if task.completed and robot.state == Robot.IDLE:
                if task.return_goal is not None:
                    self._release_goal(robot, task.return_goal)
                self._active_tasks.pop(robot, None)

    def _assign_return_path(
        self,
        robot: Robot,
        task: _ActiveTask,
        robots: list[Robot],
        warehouse_map: WarehouseMap,
    ) -> None:
        occupied_positions = {
            (other.x, other.y) for other in robots if other is not robot
        }
        home_cells = [
            cell
            for cell in sorted(warehouse_map.robot_home)
            if cell not in occupied_positions and self._goal_available(robot, cell)
        ]
        routes = []
        for home_cell in home_cells:
            path = self.compute_path(
                (robot.x, robot.y), home_cell, warehouse_map, robots, robot
            )
            if path or (robot.x, robot.y) == home_cell:
                routes.append((len(path), home_cell, path))

        if not routes:
            return
        _, home_cell, path = min(routes)
        task.return_goal = home_cell
        robot.target_return = home_cell
        robot.path = path
        robot.needs_repath = False
        self._reserve_goals(robot, home_cell)

    def _refresh_displaced_robots(
        self, robots: list[Robot], warehouse_map: WarehouseMap
    ) -> None:
        for robot in robots:
            if not robot.needs_repath:
                continue
            target = self._current_target(robot)
            if target is None:
                continue
            path = self.compute_path(
                (robot.x, robot.y), target, warehouse_map, robots, robot
            )
            if path or (robot.x, robot.y) == target:
                robot.path = path
                robot.needs_repath = False
                robot.stuck_ticks = 0
                robot.wait_ticks = 0

    def _reroute_stuck_robots(
        self, robots: list[Robot], warehouse_map: WarehouseMap
    ) -> None:
        for robot in robots:
            if robot.stuck_ticks < 8 or not robot.path:
                continue
            target = self._current_target(robot)
            if target is None:
                continue

            blocking_position = robot.path[0]
            blockers = [
                other
                for other in robots
                if other is not robot
                and (other.x, other.y) == blocking_position
                and other.stuck_ticks >= 8
                and other.path
            ]
            candidates = [robot, *blockers]
            yielder = min(candidates, key=lambda item: (len(item.path), item.id))
            if yielder is not robot:
                continue

            path = self.compute_path(
                (robot.x, robot.y), target, warehouse_map, robots, robot
            )
            if path or (robot.x, robot.y) == target:
                robot.path = path
                robot.stuck_ticks = 0
                robot.wait_ticks = 0
                robot.needs_repath = False

    @staticmethod
    def _current_target(robot: Robot) -> tuple[int, int] | None:
        if robot.state == Robot.MOVING_TO_PICK:
            return robot.target_pickup
        if robot.state == Robot.MOVING_TO_DROP:
            return robot.target_dropoff
        if robot.state == Robot.RETURNING:
            return robot.target_return
        return None

    def _dispatch_inbound(
        self,
        robot: Robot,
        robots: list[Robot],
        warehouse_map: WarehouseMap,
    ) -> bool:
        if not self.inbound_orders:
            return False

        container_type = self.inbound_orders[0]
        robot_start = (robot.x, robot.y)
        robot_tree = self._bfs_tree(robot_start, warehouse_map)
        dock_trees = {
            dock: self._bfs_tree(dock, warehouse_map)
            for dock in warehouse_map.inbound_dock
        }
        best: tuple[int, tuple[int, int], tuple[int, int], tuple[int, int]] | None = None

        for shelf in sorted(warehouse_map.shelf_cells - self._reserved_shelves):
            if warehouse_map.storage[shelf[1]][shelf[0]] is not None:
                continue
            for shelf_access in self._shelf_access_cells(shelf, warehouse_map):
                if not self._goal_available(robot, shelf_access):
                    continue
                for dock in sorted(warehouse_map.inbound_dock):
                    if not self._goal_available(robot, dock):
                        continue
                    dock_distance = robot_tree[1].get(dock)
                    shelf_distance = dock_trees[dock][1].get(shelf_access)
                    if dock_distance is None or shelf_distance is None:
                        continue
                    distance = dock_distance + shelf_distance
                    if best is None or distance < best[0]:
                        best = (distance, shelf, dock, shelf_access)

        if best is None:
            return False

        _, shelf, dock, shelf_access = best
        path = self.compute_path(robot_start, dock, warehouse_map, robots, robot)
        if not path and robot_start != dock:
            return False

        self.inbound_orders.popleft()
        self._reserved_shelves.add(shelf)
        robot.assign_task(dock, shelf_access, path, container_type)
        self._active_tasks[robot] = _ActiveTask(
            "inbound",
            shelf,
            container_type,
            self._tick,
            dock,
            shelf_access,
        )
        self._reserve_goals(robot, dock, shelf_access)
        return True

    def _dispatch_outbound(
        self,
        robot: Robot,
        robots: list[Robot],
        warehouse_map: WarehouseMap,
    ) -> bool:
        if not self.outbound_orders:
            return False

        container_type = self.outbound_orders[0]
        robot_start = (robot.x, robot.y)
        robot_tree = self._bfs_tree(robot_start, warehouse_map)
        shelf_trees: dict[
            tuple[int, int],
            tuple[
                dict[tuple[int, int], tuple[int, int] | None],
                dict[tuple[int, int], int],
            ],
        ] = {}
        best: tuple[int, tuple[int, int], tuple[int, int], tuple[int, int]] | None = None

        for shelf in sorted(warehouse_map.shelf_cells - self._reserved_shelves):
            if warehouse_map.storage[shelf[1]][shelf[0]] != container_type:
                continue
            for shelf_access in self._shelf_access_cells(shelf, warehouse_map):
                if not self._goal_available(robot, shelf_access):
                    continue
                shelf_tree = shelf_trees.get(shelf_access)
                if shelf_tree is None:
                    shelf_tree = self._bfs_tree(shelf_access, warehouse_map)
                    shelf_trees[shelf_access] = shelf_tree
                robot_distance = robot_tree[1].get(shelf_access)
                if robot_distance is None:
                    continue
                for dock in sorted(warehouse_map.outbound_dropoff):
                    if not self._goal_available(robot, dock):
                        continue
                    dock_distance = shelf_tree[1].get(dock)
                    if dock_distance is None:
                        continue
                    distance = robot_distance + dock_distance
                    if best is None or distance < best[0]:
                        best = (distance, shelf, shelf_access, dock)

        if best is None:
            return False

        _, shelf, shelf_access, dock = best
        path = self.compute_path(
            robot_start, shelf_access, warehouse_map, robots, robot
        )
        if not path and robot_start != shelf_access:
            return False

        self.outbound_orders.popleft()
        self._reserved_shelves.add(shelf)
        robot.assign_task(shelf_access, dock, path, container_type)
        self._active_tasks[robot] = _ActiveTask(
            "outbound",
            shelf,
            container_type,
            self._tick,
            shelf_access,
            dock,
        )
        self._reserve_goals(robot, shelf_access, dock)
        return True

    @staticmethod
    def _bfs_tree(
        start: tuple[int, int], warehouse_map: WarehouseMap
    ) -> tuple[
        dict[tuple[int, int], tuple[int, int] | None],
        dict[tuple[int, int], int],
    ]:
        """Build shortest unweighted routes from one cell to all reachable cells."""
        height = len(warehouse_map.walkable)
        width = len(warehouse_map.walkable[0]) if height else 0
        x, y = start
        if (
            not (0 <= x < width and 0 <= y < height)
            or not warehouse_map.walkable[y][x]
        ):
            return {}, {}

        parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        distances = {start: 0}
        frontier = deque([start])
        while frontier:
            current_x, current_y = frontier.popleft()
            for neighbor in (
                (current_x + 1, current_y),
                (current_x - 1, current_y),
                (current_x, current_y + 1),
                (current_x, current_y - 1),
            ):
                neighbor_x, neighbor_y = neighbor
                if (
                    not (0 <= neighbor_x < width and 0 <= neighbor_y < height)
                    or not warehouse_map.walkable[neighbor_y][neighbor_x]
                    or neighbor in parents
                ):
                    continue
                parents[neighbor] = (current_x, current_y)
                distances[neighbor] = distances[(current_x, current_y)] + 1
                frontier.append(neighbor)
        return parents, distances

    @staticmethod
    def _path_from_tree(
        goal: tuple[int, int],
        parents: dict[tuple[int, int], tuple[int, int] | None],
    ) -> list[tuple[int, int]]:
        if goal not in parents:
            return []
        path = []
        current: tuple[int, int] | None = goal
        while current is not None:
            path.append(current)
            current = parents[current]
        path.reverse()
        return path[1:]

    @staticmethod
    def _shelf_access_cells(
        shelf: tuple[int, int], warehouse_map: WarehouseMap
    ) -> list[tuple[int, int]]:
        x, y = shelf
        height = len(warehouse_map.walkable)
        width = len(warehouse_map.walkable[0]) if height else 0
        neighbors = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        return [
            position
            for position in neighbors
            if 0 <= position[0] < width
            and 0 <= position[1] < height
            and warehouse_map.walkable[position[1]][position[0]]
        ]

    def _goal_available(self, robot: Robot, goal: tuple[int, int]) -> bool:
        return all(
            other is robot or goal not in goals
            for other, goals in self._goal_reservations.items()
        )

    def _reserve_goals(self, robot: Robot, *goals: tuple[int, int]) -> None:
        self._goal_reservations.setdefault(robot, set()).update(goals)

    def _release_goal(self, robot: Robot, goal: tuple[int, int]) -> None:
        goals = self._goal_reservations.get(robot)
        if goals is None:
            return
        goals.discard(goal)
        if not goals:
            self._goal_reservations.pop(robot, None)
