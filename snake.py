"""Classic Snake game built with pygame.

Pick a map size, apple count, and speed from the menu, steer with WASD
or the arrow keys, eat apples to grow, and avoid the walls and your own
tail. Space/P pauses, Esc returns to the menu.
"""

from __future__ import annotations

import json
import random
import sys
from collections import deque
from pathlib import Path

import pygame
from pygame.math import Vector2

BASE_DIR = Path(__file__).resolve().parent
GRAPHICS_DIR = BASE_DIR / "Graphics"
SOUND_DIR = BASE_DIR / "Sound"
HIGH_SCORES_FILE = BASE_DIR / "high_scores.json"

CELL_SIZE = 40
MAP_SIZES = {"Small": 12, "Medium": 16, "Large": 20}
APPLE_COUNTS = (1, 3, 5)
SPEEDS = {"Slow": 200, "Normal": 150, "Fast": 100}  # ms per move
MENU_WINDOW_SIZE = 640
FPS = 60
STARTING_LENGTH = 3

GRASS_LIGHT = (175, 220, 75)
GRASS_DARK = (167, 209, 61)
TEXT_GREEN = (56, 74, 12)
DEATH_SCREEN_BG = (50, 50, 50)
WHITE = (255, 255, 255)

UP = Vector2(0, -1)
DOWN = Vector2(0, 1)
LEFT = Vector2(-1, 0)
RIGHT = Vector2(1, 0)

KEY_DIRECTIONS = {
    pygame.K_UP: UP, pygame.K_w: UP,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
}


def load_image(name: str) -> pygame.Surface:
    return pygame.image.load(GRAPHICS_DIR / name).convert_alpha()


def set_display_mode(size: int) -> pygame.Surface:
    try:
        return pygame.display.set_mode((size, size), vsync=1)
    except pygame.error:
        return pygame.display.set_mode((size, size))


def load_high_scores() -> dict[str, int]:
    try:
        return json.loads(HIGH_SCORES_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_high_scores(high_scores: dict[str, int]) -> None:
    HIGH_SCORES_FILE.write_text(json.dumps(high_scores))


class Fruit:
    def __init__(self, image: pygame.Surface) -> None:
        self.image = image
        self.pos = Vector2(-1, -1)

    def randomize(self, occupied: list[Vector2], cell_number: int) -> bool:
        """Move the fruit to a random cell not covered by the snake or another fruit.

        Returns False if the board has no free cell left.
        """
        taken = {(int(v.x), int(v.y)) for v in occupied}
        free = [(x, y) for x in range(cell_number) for y in range(cell_number)
                if (x, y) not in taken]
        if not free:
            return False
        self.pos = Vector2(random.choice(free))
        return True

    def draw(self, screen: pygame.Surface) -> None:
        rect = pygame.Rect(int(self.pos.x * CELL_SIZE), int(self.pos.y * CELL_SIZE),
                           CELL_SIZE, CELL_SIZE)
        screen.blit(self.image, rect)


class Snake:
    def __init__(self) -> None:
        self.crunch_sound = pygame.mixer.Sound(SOUND_DIR / "crunch.wav")
        self._load_images()
        self.reset(MAP_SIZES["Medium"])

    def reset(self, cell_number: int) -> None:
        mid = cell_number // 2
        self.body = [Vector2(5, mid), Vector2(4, mid), Vector2(3, mid)]
        self.prev_tail = self.body[-1]
        self.direction = RIGHT
        self.pending_turns: deque[Vector2] = deque()
        self.grow_pending = False

    def _load_images(self) -> None:
        # Sprites are keyed by the offset from the head/tail to its neighbor,
        # and body pieces by the pair of offsets to both neighbors.
        self.head_images = {
            (0, 1): load_image("head_up.png"),
            (0, -1): load_image("head_down.png"),
            (-1, 0): load_image("head_right.png"),
            (1, 0): load_image("head_left.png"),
        }
        self.tail_images = {
            (0, -1): load_image("tail_up.png"),
            (0, 1): load_image("tail_down.png"),
            (1, 0): load_image("tail_right.png"),
            (-1, 0): load_image("tail_left.png"),
        }
        self.body_images = {
            frozenset({(0, -1), (0, 1)}): load_image("body_vertical.png"),
            frozenset({(-1, 0), (1, 0)}): load_image("body_horizontal.png"),
            frozenset({(0, -1), (1, 0)}): load_image("b_up_right.png"),
            frozenset({(0, -1), (-1, 0)}): load_image("b_up_left.png"),
            frozenset({(0, 1), (1, 0)}): load_image("b_right_down.png"),
            frozenset({(0, 1), (-1, 0)}): load_image("b_left_down.png"),
        }

    @property
    def head(self) -> Vector2:
        return self.body[0]

    def queue_turn(self, new_direction: Vector2) -> None:
        """Buffer up to two turns, applied one per movement tick.

        Each turn is validated against the direction the snake will actually
        be moving when it applies, so rapid key presses can never reverse the
        snake into its own neck.
        """
        reference = self.pending_turns[-1] if self.pending_turns else self.direction
        if len(self.pending_turns) < 2 and new_direction not in (reference, -reference):
            self.pending_turns.append(new_direction)

    def move(self) -> None:
        if self.pending_turns:
            self.direction = self.pending_turns.popleft()
        self.prev_tail = self.body[-1]
        new_head = self.head + self.direction
        if self.grow_pending:
            self.body = [new_head] + self.body
            self.grow_pending = False
        else:
            self.body = [new_head] + self.body[:-1]

    def grow(self) -> None:
        self.grow_pending = True
        self.crunch_sound.play()

    def draw(self, screen: pygame.Surface, t: float) -> None:
        # Between ticks only the head and tail change cells, so the middle
        # segments draw statically while the two ends slide between cells,
        # turning discrete grid steps into continuous motion.
        for index in range(1, len(self.body) - 1):
            screen.blit(self._body_image(index), self._cell_rect(self.body[index]))
        self._draw_tail(screen, t)
        self._draw_head(screen, t)

    def _cell_rect(self, pos: Vector2) -> pygame.Rect:
        return pygame.Rect(round(pos.x * CELL_SIZE), round(pos.y * CELL_SIZE),
                           CELL_SIZE, CELL_SIZE)

    def _body_image(self, index: int) -> pygame.Surface:
        to_previous = self.body[index + 1] - self.body[index]
        to_next = self.body[index - 1] - self.body[index]
        return self.body_images[frozenset({(to_previous.x, to_previous.y),
                                           (to_next.x, to_next.y)})]

    def _draw_head(self, screen: pygame.Surface, t: float) -> None:
        relation = self.body[1] - self.body[0]
        pos = self.body[1].lerp(self.body[0], t)
        screen.blit(self.head_images[(relation.x, relation.y)], self._cell_rect(pos))

    def _draw_tail(self, screen: pygame.Surface, t: float) -> None:
        tail = self.body[-1]
        if self.prev_tail == tail:  # the snake just grew; the tail hasn't moved
            relation = self.body[-2] - tail
            screen.blit(self.tail_images[(relation.x, relation.y)], self._cell_rect(tail))
            return
        # Cover the tail cell with the body piece that occupied it last tick,
        # then slide the tail sprite over it from the vacated cell.
        to_prev = self.prev_tail - tail
        to_next = self.body[-2] - tail
        underlay = self.body_images[frozenset({(to_prev.x, to_prev.y),
                                               (to_next.x, to_next.y)})]
        screen.blit(underlay, self._cell_rect(tail))
        slide = tail - self.prev_tail
        pos = self.prev_tail.lerp(tail, t)
        screen.blit(self.tail_images[(slide.x, slide.y)], self._cell_rect(pos))


class Game:
    def __init__(self) -> None:
        pygame.display.set_caption("Snake")
        self.screen = set_display_mode(MENU_WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.score_font = pygame.font.Font(None, 30)
        self.title_font = pygame.font.Font(None, 50)
        self.hint_font = pygame.font.Font(None, 24)

        self.apple_image = pygame.transform.scale(load_image("apple.png"),
                                                  (CELL_SIZE, CELL_SIZE))
        self.snake = Snake()
        self.fruits: list[Fruit] = []
        self.high_scores = load_high_scores()

        self.map_name = "Medium"
        self.apple_count = 1
        self.speed_name = "Normal"
        self.cell_number = MAP_SIZES[self.map_name]
        self.board_pixels = self.cell_number * CELL_SIZE
        self.move_interval = SPEEDS[self.speed_name]
        self.last_move_time = 0

        self.state = "menu"  # "menu" | "playing" | "paused" | "game_over"
        self.won = False
        self.pause_start = 0
        self.menu_buttons: dict[tuple[str, str | int], pygame.Rect] = {}
        self.play_button: pygame.Rect | None = None
        self.play_again_button: pygame.Rect | None = None
        self.menu_button: pygame.Rect | None = None

    @property
    def score(self) -> int:
        # grow_pending counts the just-eaten apple before the body extends next tick.
        return len(self.snake.body) + self.snake.grow_pending - STARTING_LENGTH

    @property
    def mode_key(self) -> str:
        return f"{self.map_name}-{self.apple_count}-{self.speed_name}"

    @property
    def high_score(self) -> int:
        return self.high_scores.get(self.mode_key, 0)

    def occupied_cells(self) -> list[Vector2]:
        return self.snake.body + [fruit.pos for fruit in self.fruits]

    def run(self) -> None:
        while True:
            for event in pygame.event.get():
                self.handle_event(event)
            if self.state == "playing":
                now = pygame.time.get_ticks()
                if now - self.last_move_time >= self.move_interval:
                    self.last_move_time = now
                    self.update()
            self.draw()
            pygame.display.update()
            self.clock.tick(FPS)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if self.state == "menu":
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_menu_click(event.pos)
        elif self.state == "playing":
            if event.type == pygame.KEYDOWN:
                if event.key in KEY_DIRECTIONS:
                    self.snake.queue_turn(KEY_DIRECTIONS[event.key])
                elif event.key in (pygame.K_SPACE, pygame.K_p):
                    self.pause()
                elif event.key == pygame.K_ESCAPE:
                    self.open_menu()
        elif self.state == "paused":
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_p):
                    self.resume()
                elif event.key == pygame.K_ESCAPE:
                    self.open_menu()
        else:  # game over
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.play_again_button and self.play_again_button.collidepoint(event.pos):
                    self.start_game()
                elif self.menu_button and self.menu_button.collidepoint(event.pos):
                    self.open_menu()
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.start_game()
                elif event.key == pygame.K_ESCAPE:
                    self.open_menu()

    def handle_menu_click(self, pos: tuple[int, int]) -> None:
        for (group, value), rect in self.menu_buttons.items():
            if rect.collidepoint(pos):
                if group == "map":
                    self.map_name = value
                elif group == "apples":
                    self.apple_count = value
                else:
                    self.speed_name = value
                return
        if self.play_button and self.play_button.collidepoint(pos):
            self.start_game()

    def start_game(self) -> None:
        self.cell_number = MAP_SIZES[self.map_name]
        self.board_pixels = self.cell_number * CELL_SIZE
        self.screen = set_display_mode(self.board_pixels)
        self.snake.reset(self.cell_number)
        self.fruits = [Fruit(self.apple_image) for _ in range(self.apple_count)]
        for fruit in self.fruits:
            fruit.randomize(self.occupied_cells(), self.cell_number)
        self.move_interval = SPEEDS[self.speed_name]
        self.last_move_time = pygame.time.get_ticks()
        self.state = "playing"

    def open_menu(self) -> None:
        self.screen = set_display_mode(MENU_WINDOW_SIZE)
        self.state = "menu"

    def pause(self) -> None:
        self.pause_start = pygame.time.get_ticks()
        self.state = "paused"

    def resume(self) -> None:
        # Shift the move timer by the paused duration so the snake resumes
        # exactly where it froze instead of jumping a cell.
        self.last_move_time += pygame.time.get_ticks() - self.pause_start
        self.state = "playing"

    def update(self) -> None:
        self.snake.move()
        self.check_fruit()
        self.check_fail()

    def check_fruit(self) -> None:
        for fruit in self.fruits:
            if self.snake.head == fruit.pos:
                self.snake.grow()
                if not fruit.randomize(self.occupied_cells(), self.cell_number):
                    # Board is full: retire this fruit; winning = eating the last one.
                    self.fruits.remove(fruit)
                    if not self.fruits:
                        self.end_game(won=True)
                break

    def check_fail(self) -> None:
        head = self.snake.head
        hit_wall = not (0 <= head.x < self.cell_number and 0 <= head.y < self.cell_number)
        hit_self = head in self.snake.body[1:]
        if hit_wall or hit_self:
            self.end_game(won=False)

    def end_game(self, won: bool) -> None:
        self.state = "game_over"
        self.won = won
        if self.score > self.high_score:
            self.high_scores[self.mode_key] = self.score
            save_high_scores(self.high_scores)

    def draw(self) -> None:
        if self.state == "menu":
            self.draw_menu()
        elif self.state in ("playing", "paused"):
            now = self.pause_start if self.state == "paused" else pygame.time.get_ticks()
            t = min((now - self.last_move_time) / self.move_interval, 1.0)
            self.screen.fill(GRASS_LIGHT)
            self.draw_grass()
            for fruit in self.fruits:
                fruit.draw(self.screen)
            self.snake.draw(self.screen, t)
            self.draw_score()
            if self.state == "paused":
                self.draw_pause_overlay()
        else:
            self.draw_death_screen()

    def draw_menu(self) -> None:
        self.screen.fill(GRASS_LIGHT)
        center_x = MENU_WINDOW_SIZE // 2

        title = self.title_font.render("Snake", True, TEXT_GREEN)
        self.screen.blit(title, title.get_rect(center=(center_x, 75)))

        self.menu_buttons.clear()
        self._draw_option_row("Map Size", 150, "map", list(MAP_SIZES), self.map_name)
        self._draw_option_row("Apples", 270, "apples", list(APPLE_COUNTS), self.apple_count)
        self._draw_option_row("Speed", 390, "speed", list(SPEEDS), self.speed_name)

        self.play_button = self._draw_button("Play", (center_x, 520), selected=True)
        high_score = self.score_font.render(f"High Score: {self.high_score}", True, TEXT_GREEN)
        self.screen.blit(high_score, high_score.get_rect(center=(center_x, 585)))
        hint = self.hint_font.render(
            "WASD / Arrows to move  -  Space to pause  -  Esc for menu", True, TEXT_GREEN)
        self.screen.blit(hint, hint.get_rect(center=(center_x, 618)))

    def _draw_option_row(self, label: str, y: int, group: str,
                         options: list, selected: str | int) -> None:
        label_surface = self.score_font.render(label, True, TEXT_GREEN)
        self.screen.blit(label_surface, label_surface.get_rect(center=(MENU_WINDOW_SIZE // 2, y)))

        spacing = 150
        start_x = MENU_WINDOW_SIZE // 2 - spacing * (len(options) - 1) // 2
        for i, value in enumerate(options):
            center = (start_x + i * spacing, y + 45)
            self.menu_buttons[(group, value)] = self._draw_button(
                str(value), center, selected=value == selected)

    def _draw_button(self, text: str, center: tuple[int, int], selected: bool) -> pygame.Rect:
        text_color = GRASS_LIGHT if selected else TEXT_GREEN
        surface = self.score_font.render(text, True, text_color)
        text_rect = surface.get_rect(center=center)
        button_rect = text_rect.inflate(36, 18)
        if selected:
            pygame.draw.rect(self.screen, TEXT_GREEN, button_rect)
        self.screen.blit(surface, text_rect)
        pygame.draw.rect(self.screen, TEXT_GREEN, button_rect, 2)
        return button_rect

    def draw_grass(self) -> None:
        for row in range(self.cell_number):
            for col in range(row % 2, self.cell_number, 2):
                rect = pygame.Rect(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(self.screen, GRASS_DARK, rect)

    def draw_score(self) -> None:
        score_surface = self.score_font.render(str(self.score), True, TEXT_GREEN)
        score_rect = score_surface.get_rect(center=(self.board_pixels - 40,
                                                    self.board_pixels - 40))
        apple_rect = self.apple_image.get_rect(midright=(score_rect.left, score_rect.centery))
        bg_rect = pygame.Rect(apple_rect.left, apple_rect.top,
                              apple_rect.width + score_rect.width + 4, apple_rect.height + 4)

        pygame.draw.rect(self.screen, GRASS_DARK, bg_rect)
        self.screen.blit(score_surface, score_rect)
        self.screen.blit(self.apple_image, apple_rect)
        pygame.draw.rect(self.screen, TEXT_GREEN, bg_rect, 2)

    def draw_pause_overlay(self) -> None:
        overlay = pygame.Surface((self.board_pixels, self.board_pixels), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        self.screen.blit(overlay, (0, 0))

        title = self.title_font.render("Paused", True, WHITE)
        hint = self.score_font.render("Space to resume  -  Esc for menu", True, WHITE)
        center_x = self.board_pixels // 2
        self.screen.blit(title, title.get_rect(center=(center_x, self.board_pixels // 2 - 25)))
        self.screen.blit(hint, hint.get_rect(center=(center_x, self.board_pixels // 2 + 25)))

    def draw_death_screen(self) -> None:
        self.screen.fill(DEATH_SCREEN_BG)
        center_x = self.board_pixels // 2

        title = self.title_font.render("You Win!" if self.won else "Game Over", True, WHITE)
        score = self.score_font.render(f"Your Score: {self.score}", True, WHITE)
        high_score = self.score_font.render(f"High Score: {self.high_score}", True, WHITE)
        play_again = self.score_font.render("Play Again", True, WHITE)
        menu = self.score_font.render("Menu", True, WHITE)

        self.screen.blit(title, title.get_rect(center=(center_x, self.board_pixels // 4)))
        self.screen.blit(score, score.get_rect(center=(center_x, self.board_pixels // 3)))
        self.screen.blit(high_score,
                         high_score.get_rect(center=(center_x, self.board_pixels // 2)))

        button_y = self.board_pixels * 3 // 4
        play_again_rect = play_again.get_rect(center=(center_x - 90, button_y))
        menu_rect = menu.get_rect(center=(center_x + 90, button_y))
        self.play_again_button = play_again_rect.inflate(40, 20)
        self.menu_button = menu_rect.inflate(40, 20)

        self.screen.blit(play_again, play_again_rect)
        self.screen.blit(menu, menu_rect)
        pygame.draw.rect(self.screen, WHITE, self.play_again_button, 2)
        pygame.draw.rect(self.screen, WHITE, self.menu_button, 2)

        hint = self.hint_font.render("Space to replay  -  Esc for menu", True, WHITE)
        self.screen.blit(hint, hint.get_rect(center=(center_x, self.board_pixels - 30)))


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    Game().run()


if __name__ == "__main__":
    main()
