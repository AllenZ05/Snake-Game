"""Classic Snake game built with pygame.

Pick a map size, apple count, speed, and wall mode from the menu; the
round starts on your first direction key. Steer with WASD or the arrow
keys, eat apples to grow, and avoid your own tail — and the walls,
unless they wrap. Space/P pauses, Esc returns to the menu.
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
WALL_MODES = ("Solid", "Wrap")
MENU_SIZE = (640, 720)
HUD_HEIGHT = 60
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


def set_display_mode(width: int, height: int) -> pygame.Surface:
    try:
        return pygame.display.set_mode((width, height), vsync=1)
    except pygame.error:
        return pygame.display.set_mode((width, height))


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
        self.eaten = False

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
        self.reset(MAP_SIZES["Medium"], wrap=False)

    def reset(self, cell_number: int, wrap: bool) -> None:
        self.cell_number = cell_number
        self.wrap = wrap
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
        if self.wrap:
            new_head = Vector2(new_head.x % self.cell_number,
                               new_head.y % self.cell_number)
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
        for index in range(2, len(self.body) - 1):
            screen.blit(self._body_image(index), self._cell_rect(self.body[index]))
        self._draw_neck(screen, t)
        self._draw_tail(screen, t)
        self._draw_head(screen, t)

    def _cell_rect(self, pos: Vector2) -> pygame.Rect:
        return pygame.Rect(round(pos.x * CELL_SIZE), round(pos.y * CELL_SIZE),
                           CELL_SIZE, CELL_SIZE)

    def _offset(self, a: Vector2, b: Vector2) -> tuple[float, float]:
        """Offset from b to its neighbor a, normalized across the wrap seam."""
        diff = a - b
        if self.wrap:
            if abs(diff.x) > 1:
                diff.x -= self.cell_number * (1 if diff.x > 0 else -1)
            if abs(diff.y) > 1:
                diff.y -= self.cell_number * (1 if diff.y > 0 else -1)
        return (diff.x, diff.y)

    def _body_image(self, index: int) -> pygame.Surface:
        to_previous = self._offset(self.body[index + 1], self.body[index])
        to_next = self._offset(self.body[index - 1], self.body[index])
        return self.body_images[frozenset({to_previous, to_next})]

    def _draw_neck(self, screen: pygame.Surface, t: float) -> None:
        """Draw the segment behind the head, trimming its leading edge while
        the head's rounded cap is still sliding over it — otherwise the tube's
        square end pokes out around the cap at the start of every step."""
        rect = self._cell_rect(self.body[1])
        area = pygame.Rect(0, 0, CELL_SIZE, CELL_SIZE)
        trim = max(0, CELL_SIZE // 2 - round(t * CELL_SIZE))
        dx, dy = self._offset(self.body[0], self.body[1])
        if dx > 0:
            area.width -= trim
        elif dx < 0:
            area.left += trim
            area.width -= trim
            rect.left += trim
        elif dy > 0:
            area.height -= trim
        else:
            area.top += trim
            area.height -= trim
            rect.top += trim
        screen.blit(self._body_image(1), rect, area)

    def _slide_blit(self, screen: pygame.Surface, image: pygame.Surface,
                    start: Vector2, end: Vector2, t: float) -> None:
        """Slide a sprite from start to end; when the step crosses the wrap
        seam, draw it exiting one edge and entering the opposite one."""
        step = Vector2(self._offset(end, start))
        if start + step == end:
            screen.blit(image, self._cell_rect(start.lerp(end, t)))
        else:
            screen.blit(image, self._cell_rect(start.lerp(start + step, t)))
            screen.blit(image, self._cell_rect((end - step).lerp(end, t)))

    def _draw_head(self, screen: pygame.Surface, t: float) -> None:
        image = self.head_images[(-self.direction.x, -self.direction.y)]
        self._slide_blit(screen, image, self.body[1], self.body[0], t)

    def _draw_tail(self, screen: pygame.Surface, t: float) -> None:
        tail = self.body[-1]
        if self.prev_tail == tail:  # the snake just grew; the tail hasn't moved
            relation = self._offset(self.body[-2], tail)
            screen.blit(self.tail_images[relation], self._cell_rect(tail))
            return
        # Cover the tail cell with the body piece that occupied it last tick,
        # then slide the tail sprite over it from the vacated cell.
        to_prev = self._offset(self.prev_tail, tail)
        to_next = self._offset(self.body[-2], tail)
        underlay = self.body_images[frozenset({to_prev, to_next})]
        screen.blit(underlay, self._cell_rect(tail))
        slide = self._offset(tail, self.prev_tail)
        self._slide_blit(screen, self.tail_images[slide], self.prev_tail, tail, t)


class Game:
    def __init__(self) -> None:
        pygame.display.set_caption("Snake")
        self.screen = set_display_mode(*MENU_SIZE)
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
        self.walls_name = "Solid"
        self.cell_number = MAP_SIZES[self.map_name]
        self.board_pixels = self.cell_number * CELL_SIZE
        self.board_surface = pygame.Surface((self.board_pixels, self.board_pixels))
        self.move_interval = SPEEDS[self.speed_name]
        self.last_move_time = 0

        self.state = "menu"  # "menu" | "ready" | "playing" | "paused" | "game_over"
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
        key = f"{self.map_name}-{self.apple_count}-{self.speed_name}"
        if self.walls_name != "Solid":  # Solid omitted so older saved scores keep working
            key += f"-{self.walls_name}"
        return key

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
        elif self.state == "ready":
            if event.type == pygame.KEYDOWN:
                if event.key in KEY_DIRECTIONS:
                    self.snake.queue_turn(KEY_DIRECTIONS[event.key])
                    self.last_move_time = pygame.time.get_ticks()
                    self.state = "playing"
                elif event.key == pygame.K_ESCAPE:
                    self.open_menu()
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
                elif group == "speed":
                    self.speed_name = value
                else:
                    self.walls_name = value
                return
        if self.play_button and self.play_button.collidepoint(pos):
            self.start_game()

    def start_game(self) -> None:
        self.cell_number = MAP_SIZES[self.map_name]
        self.board_pixels = self.cell_number * CELL_SIZE
        self.screen = set_display_mode(self.board_pixels, HUD_HEIGHT + self.board_pixels)
        self.board_surface = pygame.Surface((self.board_pixels, self.board_pixels))
        self.snake.reset(self.cell_number, wrap=self.walls_name == "Wrap")
        self.fruits = [Fruit(self.apple_image) for _ in range(self.apple_count)]
        for fruit in self.fruits:
            fruit.randomize(self.occupied_cells(), self.cell_number)
        self.move_interval = SPEEDS[self.speed_name]
        self.state = "ready"  # the first direction key starts the round

    def open_menu(self) -> None:
        self.screen = set_display_mode(*MENU_SIZE)
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
        self.respawn_eaten_fruits()
        if self.state != "playing":  # eating the last apple on a full board won
            return
        self.snake.move()
        self.check_fruit()
        self.check_fail()

    def check_fruit(self) -> None:
        for fruit in self.fruits:
            if self.snake.head == fruit.pos:
                self.snake.grow()
                fruit.eaten = True
                break

    def respawn_eaten_fruits(self) -> None:
        # Deferred one tick so the apple stays visible while the mouth
        # slides over it, instead of vanishing a full cell early.
        for fruit in list(self.fruits):
            if not fruit.eaten:
                continue
            fruit.eaten = False
            if not fruit.randomize(self.occupied_cells(), self.cell_number):
                # Board is full: retire this fruit; winning = eating the last one.
                self.fruits.remove(fruit)
                if not self.fruits:
                    self.end_game(won=True)

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
        elif self.state in ("ready", "playing", "paused"):
            if self.state == "ready":
                t = 1.0  # the snake rests fully in its cells until the round starts
            else:
                now = self.pause_start if self.state == "paused" else pygame.time.get_ticks()
                t = min((now - self.last_move_time) / self.move_interval, 1.0)
            board = self.board_surface
            board.fill(GRASS_LIGHT)
            self.draw_grass(board)
            for fruit in self.fruits:
                fruit.draw(board)
            self.snake.draw(board, t)
            self.draw_hud()
            self.screen.blit(board, (0, HUD_HEIGHT))
            if self.state == "paused":
                self.draw_pause_overlay()
        else:
            self.draw_death_screen()

    def draw_menu(self) -> None:
        self.screen.fill(GRASS_LIGHT)
        center_x = MENU_SIZE[0] // 2

        title = self.title_font.render("Snake", True, TEXT_GREEN)
        self.screen.blit(title, title.get_rect(center=(center_x, 70)))

        self.menu_buttons.clear()
        self._draw_option_row("Map Size", 140, "map", list(MAP_SIZES), self.map_name)
        self._draw_option_row("Apples", 245, "apples", list(APPLE_COUNTS), self.apple_count)
        self._draw_option_row("Speed", 350, "speed", list(SPEEDS), self.speed_name)
        self._draw_option_row("Walls", 455, "walls", list(WALL_MODES), self.walls_name)

        self.play_button = self._draw_button("Play", (center_x, 585), selected=True)
        high_score = self.score_font.render(f"High Score: {self.high_score}", True, TEXT_GREEN)
        self.screen.blit(high_score, high_score.get_rect(center=(center_x, 645)))
        hint = self.hint_font.render(
            "WASD / Arrows to move  -  Space to pause  -  Esc for menu", True, TEXT_GREEN)
        self.screen.blit(hint, hint.get_rect(center=(center_x, 685)))

    def _draw_option_row(self, label: str, y: int, group: str,
                         options: list, selected: str | int) -> None:
        label_surface = self.score_font.render(label, True, TEXT_GREEN)
        self.screen.blit(label_surface, label_surface.get_rect(center=(MENU_SIZE[0] // 2, y)))

        spacing = 150
        start_x = MENU_SIZE[0] // 2 - spacing * (len(options) - 1) // 2
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

    def draw_grass(self, surface: pygame.Surface) -> None:
        for row in range(self.cell_number):
            for col in range(row % 2, self.cell_number, 2):
                rect = pygame.Rect(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(surface, GRASS_DARK, rect)

    def draw_hud(self) -> None:
        pygame.draw.rect(self.screen, TEXT_GREEN,
                         pygame.Rect(0, 0, self.board_pixels, HUD_HEIGHT))
        apple_rect = self.apple_image.get_rect(midleft=(12, HUD_HEIGHT // 2))
        self.screen.blit(self.apple_image, apple_rect)
        score = self.score_font.render(str(self.score), True, WHITE)
        self.screen.blit(score, score.get_rect(midleft=(apple_rect.right + 6,
                                                        HUD_HEIGHT // 2)))
        best = self.score_font.render(f"Best: {self.high_score}", True, WHITE)
        self.screen.blit(best, best.get_rect(midright=(self.board_pixels - 16,
                                                       HUD_HEIGHT // 2)))

    def draw_pause_overlay(self) -> None:
        center_x, center_y = self.screen.get_rect().center
        title = self.title_font.render("Paused", True, WHITE)
        hint = self.score_font.render("Space to resume  -  Esc for menu", True, WHITE)
        title_rect = title.get_rect(center=(center_x, center_y - 22))
        hint_rect = hint.get_rect(center=(center_x, center_y + 22))
        panel = title_rect.union(hint_rect).inflate(50, 36)
        pygame.draw.rect(self.screen, TEXT_GREEN, panel, border_radius=16)
        self.screen.blit(title, title_rect)
        self.screen.blit(hint, hint_rect)

    def draw_death_screen(self) -> None:
        self.screen.fill(DEATH_SCREEN_BG)
        width, height = self.screen.get_size()
        center_x = width // 2

        title = self.title_font.render("You Win!" if self.won else "Game Over", True, WHITE)
        score = self.score_font.render(f"Your Score: {self.score}", True, WHITE)
        high_score = self.score_font.render(f"High Score: {self.high_score}", True, WHITE)
        play_again = self.score_font.render("Play Again", True, WHITE)
        menu = self.score_font.render("Menu", True, WHITE)

        self.screen.blit(title, title.get_rect(center=(center_x, height // 4)))
        self.screen.blit(score, score.get_rect(center=(center_x, height // 3)))
        self.screen.blit(high_score,
                         high_score.get_rect(center=(center_x, height // 2)))

        button_y = height * 3 // 4
        play_again_rect = play_again.get_rect(center=(center_x - 90, button_y))
        menu_rect = menu.get_rect(center=(center_x + 90, button_y))
        self.play_again_button = play_again_rect.inflate(40, 20)
        self.menu_button = menu_rect.inflate(40, 20)

        self.screen.blit(play_again, play_again_rect)
        self.screen.blit(menu, menu_rect)
        pygame.draw.rect(self.screen, WHITE, self.play_again_button, 2)
        pygame.draw.rect(self.screen, WHITE, self.menu_button, 2)

        hint = self.hint_font.render("Space to replay  -  Esc for menu", True, WHITE)
        self.screen.blit(hint, hint.get_rect(center=(center_x, height - 30)))


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    Game().run()


if __name__ == "__main__":
    main()
