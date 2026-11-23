"""Interactive Pygame entry point for the warehouse robot simulation."""

from __future__ import annotations

from dataclasses import dataclass
import random

import pygame

from config import (
    COLORS,
    CONTAINER_TYPES,
    FPS,
    GRID_HEIGHT,
    GRID_WIDTH,
    ROBOT_COUNT,
    TILE_SIZE,
)
from master_ai import MasterAI
from robot import Robot
from warehouse_map import WarehouseMap

HUD_WIDTH = 380
WINDOW_WIDTH = GRID_WIDTH * TILE_SIZE + HUD_WIDTH
WINDOW_HEIGHT = GRID_HEIGHT * TILE_SIZE

PANEL_COLOR = (34, 40, 47)
BUTTON_COLOR = (62, 72, 82)
BUTTON_HOVER_COLOR = (82, 96, 108)
BUTTON_TEXT_COLOR = (248, 248, 248)


@dataclass
class Button:
    label: str
    rect: pygame.Rect
    action: str


class WarehouseSimulation:
    """Owns the simulation state, HUD controls, and Pygame event loop."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Warehouse Robot Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 23)
        self.small_font = pygame.font.Font(None, 20)
        self.title_font = pygame.font.Font(None, 30)
        self.random = random.Random()

        self.speed_options = (1, 2, 5)
        self.speed_index = 0
        self.paused = False
        self.running = True
        self.frame_count = 0
        self.reset_world()
        self.buttons = self._create_buttons()

    @property
    def speed(self) -> int:
        return self.speed_options[self.speed_index]

    def reset_world(self) -> None:
        self.warehouse_map = WarehouseMap()
        home_cells = sorted(self.warehouse_map.robot_home)
        self.robots = [
            Robot(robot_id, x, y)
            for robot_id, (x, y) in enumerate(home_cells[:ROBOT_COUNT], start=1)
        ]
        self.master_ai = MasterAI()

    def _create_buttons(self) -> list[Button]:
        panel_x = GRID_WIDTH * TILE_SIZE
        left_x = panel_x + 16
        right_x = panel_x + 194
        button_width = 170
        button_height = 34
        buttons = []

        for row, container_type in enumerate(CONTAINER_TYPES):
            y = 72 + row * 39
            inbound_key = row + 1
            outbound_key = ("Q", "W", "E")[row]
            buttons.append(
                Button(
                    f"Send 3 {container_type} [{inbound_key}]",
                    pygame.Rect(left_x, y, button_width, button_height),
                    f"send_{container_type}",
                )
            )
            buttons.append(
                Button(
                    f"Request 2 {container_type} [{outbound_key}]",
                    pygame.Rect(right_x, y, button_width, button_height),
                    f"request_{container_type}",
                )
            )

        full_width = HUD_WIDTH - 32
        buttons.extend(
            [
                Button(
                    "Stress Test (10 Random) [T]",
                    pygame.Rect(left_x, 192, full_width, button_height),
                    "stress",
                ),
                Button(
                    "Speed: 1x [S]",
                    pygame.Rect(left_x, 233, full_width, button_height),
                    "speed",
                ),
                Button(
                    "Pause [SPACE]",
                    pygame.Rect(left_x, 274, button_width, button_height),
                    "pause",
                ),
                Button(
                    "Reset [R]",
                    pygame.Rect(right_x, 274, button_width, button_height),
                    "reset",
                ),
            ]
        )
        return buttons

    def _refresh_button_labels(self) -> None:
        for button in self.buttons:
            if button.action == "speed":
                button.label = f"Speed: {self.speed}x [S]"
            elif button.action == "pause":
                button.label = "Resume [SPACE]" if self.paused else "Pause [SPACE]"

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button.rect.collidepoint(event.pos):
                    self._perform_action(button.action)
                    break

    def _handle_key(self, key: int) -> None:
        key_actions = {
            pygame.K_1: "send_RED",
            pygame.K_2: "send_BLUE",
            pygame.K_3: "send_GREEN",
            pygame.K_q: "request_RED",
            pygame.K_w: "request_BLUE",
            pygame.K_e: "request_GREEN",
            pygame.K_t: "stress",
            pygame.K_s: "speed",
            pygame.K_SPACE: "pause",
            pygame.K_r: "reset",
            pygame.K_ESCAPE: "quit",
        }
        action = key_actions.get(key)
        if action is not None:
            self._perform_action(action)

    def _perform_action(self, action: str) -> None:
        if action == "quit":
            self.running = False
        elif action.startswith("send_"):
            container_type = action.removeprefix("send_")
            for _ in range(3):
                self.master_ai.add_inbound_order(container_type)
        elif action.startswith("request_"):
            container_type = action.removeprefix("request_")
            for _ in range(2):
                self.master_ai.add_outbound_order(
                    container_type, self.warehouse_map
                )
        elif action == "stress":
            for _ in range(10):
                container_type = self.random.choice(CONTAINER_TYPES)
                if self.random.random() < 0.5:
                    self.master_ai.add_inbound_order(container_type)
                else:
                    self.master_ai.add_outbound_order(
                        container_type, self.warehouse_map
                    )
        elif action == "speed":
            self.speed_index = (self.speed_index + 1) % len(self.speed_options)
        elif action == "pause":
            self.paused = not self.paused
        elif action == "reset":
            self.reset_world()
            self.paused = False
            self.speed_index = 0

    def _step_simulation(self) -> None:
        self.master_ai.dispatch(self.robots, self.warehouse_map)
        for robot in self.robots:
            robot.step(self.warehouse_map, self.robots)

    def draw(self) -> None:
        self.screen.fill(COLORS["BACKGROUND"])
        self.warehouse_map.draw(self.screen)
        for robot in self.robots:
            robot.draw(self.screen)
        self._draw_hud()
        pygame.display.flip()

    def _draw_hud(self) -> None:
        panel_x = GRID_WIDTH * TILE_SIZE
        panel = pygame.Rect(panel_x, 0, HUD_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel)
        pygame.draw.line(
            self.screen, COLORS["GRID"], (panel_x, 0), (panel_x, WINDOW_HEIGHT), 2
        )

        self._draw_text("WAREHOUSE CONTROL", panel_x + 16, 14, self.title_font)
        status = "PAUSED" if self.paused else f"RUNNING  |  {self.speed}x"
        self._draw_text(status, panel_x + 18, 44, self.small_font, (205, 214, 222))

        mouse_position = pygame.mouse.get_pos()
        self._refresh_button_labels()
        for button in self.buttons:
            color = (
                BUTTON_HOVER_COLOR
                if button.rect.collidepoint(mouse_position)
                else BUTTON_COLOR
            )
            pygame.draw.rect(self.screen, color, button.rect, border_radius=5)
            pygame.draw.rect(
                self.screen, (104, 116, 128), button.rect, 1, border_radius=5
            )
            label = self.small_font.render(button.label, True, BUTTON_TEXT_COLOR)
            self.screen.blit(label, label.get_rect(center=button.rect.center))

        active_count = sum(robot.state != Robot.IDLE for robot in self.robots)
        idle_count = len(self.robots) - active_count
        deadlocked = sum(robot.wait_ticks > 20 for robot in self.robots)
        shelf_count = len(self.warehouse_map.shelf_cells)
        occupied = sum(
            self.warehouse_map.storage[y][x] is not None
            for x, y in self.warehouse_map.shelf_cells
        )
        occupancy = 100 * occupied / shelf_count if shelf_count else 0.0
        stats_y = 324

        self._draw_text("LIVE METRICS", panel_x + 16, stats_y, self.font)
        self._draw_text(
            f"Robots: {active_count} active  |  {idle_count} idle",
            panel_x + 18,
            stats_y + 27,
            self.small_font,
        )
        self._draw_text(
            f"Queues: in {len(self.master_ai.inbound_orders)}  |  "
            f"ready {len(self.master_ai.outbound_orders)}  |  "
            f"stock wait {len(self.master_ai.waiting_outbound_orders)}",
            panel_x + 18,
            stats_y + 51,
            self.small_font,
        )
        self._draw_text(
            f"Blocked/wait ticks: {self.master_ai.total_wait_ticks}",
            panel_x + 18,
            stats_y + 75,
            self.small_font,
        )
        self._draw_text(
            f"Deadlocked (>20): {deadlocked}",
            panel_x + 18,
            stats_y + 99,
            self.small_font,
        )
        self._draw_text(
            f"Shelf occupancy: {occupied}/{shelf_count} ({occupancy:.1f}%)",
            panel_x + 18,
            stats_y + 123,
            self.small_font,
        )
        self._draw_text(
            f"Completed: in {self.master_ai.completed_inbound}  |  "
            f"out {self.master_ai.completed_outbound}",
            panel_x + 18,
            stats_y + 147,
            self.small_font,
        )
        self._draw_text(
            f"Average task time: {self.master_ai.avg_task_time:.1f} ticks",
            panel_x + 18,
            stats_y + 171,
            self.small_font,
        )

        self._draw_text("ROBOT STATUS", panel_x + 16, stats_y + 206, self.font)
        for index, robot in enumerate(self.robots):
            y = stats_y + 235 + index * 25
            state_color = Robot.STATE_COLORS[robot.state]
            pygame.draw.circle(self.screen, state_color, (panel_x + 25, y + 7), 6)
            cargo = f" carrying {robot.carrying}" if robot.carrying else ""
            self._draw_text(
                f"Robot {robot.id}: {robot.state}{cargo}  wait {robot.wait_ticks}",
                panel_x + 39,
                y,
                self.small_font,
            )

    def _draw_text(
        self,
        text: str,
        x: int,
        y: int,
        font: pygame.font.Font,
        color: tuple[int, int, int] = BUTTON_TEXT_COLOR,
    ) -> None:
        self.screen.blit(font.render(text, True, color), (x, y))

    def run(self, max_frames: int | None = None) -> None:
        try:
            while self.running and (max_frames is None or self.frame_count < max_frames):
                for event in pygame.event.get():
                    self.handle_event(event)

                if not self.paused:
                    for _ in range(self.speed):
                        self._step_simulation()

                self.draw()
                self.clock.tick(FPS)
                self.frame_count += 1
        finally:
            pygame.quit()


def main() -> None:
    WarehouseSimulation().run()


if __name__ == "__main__":
    main()
