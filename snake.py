"""Classic Snake game built with pygame.

Pick a map size, apple count, speed, and wall mode from the menu; the
round starts on your first direction key. Steer with WASD or the arrow
keys, eat apples to grow, and avoid your own tail — and the walls,
unless they wrap. Space/P pauses, Esc returns to the menu.
"""

from __future__ import annotations

import json
import math
import random
import tempfile
from collections import deque
from pathlib import Path

import pygame
from pygame.math import Vector2

from display import GameDisplay
from ui import GameUI, HUD_HEIGHT, VIEW_SIZE

BASE_DIR = Path(__file__).resolve().parent
GRAPHICS_DIR = BASE_DIR / "Graphics"
SOUND_DIR = BASE_DIR / "Sound"
HIGH_SCORES_FILE = BASE_DIR / "high_scores.json"
SETTINGS_FILE = BASE_DIR / "settings.json"

CELL_SIZE = 40
# Half the quarter-circle arc the tube's centerline traces through a bend
# cell; the tail tip rests at the arc's midpoint while rounding a corner.
HALF_ARC = math.pi * CELL_SIZE / 8
MAP_SIZES = {"Small": 12, "Medium": 16, "Large": 20}
APPLE_COUNTS = (1, 3, 5, 7)
SPEEDS = {"Slow": 200, "Normal": 150, "Fast": 100}  # ms per move
WALL_MODES = ("Solid", "Wrap")
FPS = 60
STARTING_LENGTH = 3
VOLUMES = {"Off": 0.0, "Quiet": 0.3, "On": 0.7}
OPTIONS = {
    "map_name": tuple(MAP_SIZES),
    "apple_count": APPLE_COUNTS,
    "speed_name": tuple(SPEEDS),
    "walls_name": WALL_MODES,
    "volume_name": tuple(VOLUMES),
    "motion_name": ("Full", "Reduced"),
}

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
    loaded = pygame.image.load(GRAPHICS_DIR / name)
    # Explicit RGBA conversion also works with SDL2 windows, which do not
    # install a pygame.display surface for convert_alpha() to consult.
    image = pygame.Surface(loaded.get_size(), pygame.SRCALPHA, 32)
    image.blit(loaded, (0, 0))
    return image


def load_high_scores() -> dict[str, int]:
    data = load_json(HIGH_SCORES_FILE)
    return {key: value for key, value in data.items()
            if isinstance(key, str) and type(value) is int and value >= 0}


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_json(path: Path, data: dict) -> bool:
    """Replace a complete file atomically; unavailable storage isn't fatal."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, delete=False,
                                         prefix=path.name + ".") as output:
            temporary = Path(output.name)
            json.dump(data, output, indent=2)
            output.write("\n")
        temporary.replace(path)
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def save_high_scores(high_scores: dict[str, int]) -> bool:
    return save_json(HIGH_SCORES_FILE, high_scores)


class Fruit:
    def __init__(self, image: pygame.Surface) -> None:
        self.image = image
        self.pos = Vector2(-1, -1)

    def randomize(self, occupied: list[Vector2], cell_number: int) -> bool:
        """Move to a random unoccupied cell; False if the board is full."""
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
        self._load_images()
        self.reset(MAP_SIZES["Medium"], wrap=False)

    def reset(self, cell_number: int, wrap: bool) -> None:
        self.cell_number = cell_number
        self.wrap = wrap
        mid = cell_number // 2
        self.body = [Vector2(5, mid), Vector2(4, mid), Vector2(3, mid)]
        self.prev_tail = self.body[-1]
        self.direction = RIGHT
        self.tail_dir = (self.direction.x, self.direction.y)
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
        # The rows/columns the straight tube spans; end trimming stays inside
        # this band so corner pieces keep their outer curve.
        self.tube_rows = self.body_images[
            frozenset({(-1, 0), (1, 0)})].get_bounding_rect()
        self.tube_columns = self.body_images[
            frozenset({(0, -1), (0, 1)})].get_bounding_rect()
        # The bend-rounding tail tip: a disc mirrored from the tail sprite's
        # own cap, resting tip_center_pull behind the center of its cell.
        self.tip_radius = self.tube_rows.height // 2
        tail_bounds = self.tail_images[(1, 0)].get_bounding_rect()
        self.tip_center_pull = (CELL_SIZE // 2
                                - tail_bounds.left - self.tip_radius)
        cap = self.tail_images[(1, 0)].subsurface(
            (tail_bounds.left, self.tube_rows.y,
             self.tip_radius, self.tube_rows.height))
        self.tip_image = pygame.Surface(
            (2 * self.tip_radius, self.tube_rows.height), pygame.SRCALPHA)
        self.tip_image.blit(cap, (0, 0))
        self.tip_image.blit(pygame.transform.flip(cap, True, False),
                            (self.tip_radius, 0))

    @property
    def head(self) -> Vector2:
        return self.body[0]

    def queue_turn(self, new_direction: Vector2) -> None:
        """Buffer up to two turns, one per tick, each validated against the
        direction it will apply on so the snake can never reverse into itself."""
        reference = self.pending_turns[-1] if self.pending_turns else self.direction
        if len(self.pending_turns) < 2 and new_direction not in (reference, -reference):
            self.pending_turns.append(new_direction)

    def move(self) -> None:
        if self.pending_turns:
            self.direction = self.pending_turns.popleft()
        if self.body[-1] != self.prev_tail:  # unchanged means the snake grew
            self.tail_dir = self._offset(self.body[-1], self.prev_tail)
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

    def draw(self, screen: pygame.Surface, t: float) -> None:
        # Only the two ends move between ticks: the middle draws statically
        # while the head and tail slide, smoothing the grid steps.
        for index in range(2, len(self.body) - 1):
            screen.blit(self._body_image(index), self._cell_rect(self.body[index]))
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

    def _trim_tube_end(self, piece: pygame.Surface, side: tuple[float, float],
                       trim: int) -> pygame.Surface:
        """Copy of a body piece with `trim` pixels of tube erased on the cell
        edge facing `side`; only the tube band is touched so curves survive."""
        if trim <= 0:
            return piece
        piece = piece.copy()
        dx, dy = side
        if dx:
            band = self.tube_rows
            hole = pygame.Rect(CELL_SIZE - trim if dx > 0 else 0, band.y,
                               trim, band.height)
        else:
            band = self.tube_columns
            hole = pygame.Rect(band.x, CELL_SIZE - trim if dy > 0 else 0,
                               band.width, trim)
        piece.fill((0, 0, 0, 0), hole)
        return piece

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

    def _bend_geometry(self, rect: pygame.Rect, s_in: tuple[float, float],
                       s_out: tuple[float, float]):
        """Pivot corner and sweep sense for a 90-degree bend entered through
        side `s_in` of the cell and left through side `s_out`."""
        pivot = Vector2(rect.left if s_in[0] + s_out[0] < 0 else rect.right,
                        rect.top if s_in[1] + s_out[1] < 0 else rect.bottom)
        start = Vector2(-s_out[0], -s_out[1])  # along the entering edge
        sign = 1 if start.rotate(90) == Vector2(-s_in[0], -s_in[1]) else -1
        return pivot, start, sign

    def _erase_sector(self, piece: pygame.Surface, local_pivot: Vector2,
                      start: Vector2, sign: int, lo: float, hi: float) -> None:
        """Erase the sector of a corner piece between angles lo and hi,
        measured from the entering edge around the bend's pivot."""
        points = [local_pivot] + [
            local_pivot + start.rotate(sign * (lo + (hi - lo) * k / 3))
            * 2 * CELL_SIZE for k in range(4)]
        pygame.draw.polygon(piece, (0, 0, 0, 0), points)

    def _blit_tip(self, screen: pygame.Surface, center: Vector2) -> None:
        screen.blit(self.tip_image, self.tip_image.get_rect(
            center=(round(center.x), round(center.y))))

    def _bend_point(self, cell: Vector2, s_in: tuple[float, float],
                    s_out: tuple[float, float], deg: float) -> Vector2:
        """Point on a bend cell's centerline arc, `deg` degrees past the
        midpoint of its entering edge."""
        pivot, start, sign = self._bend_geometry(self._cell_rect(cell),
                                                 s_in, s_out)
        return pivot + (start * (CELL_SIZE // 2)).rotate(sign * deg)

    def _consume_entry(self, screen: pygame.Surface, cell: Vector2,
                       s_in: tuple[float, float], s_out: tuple[float, float],
                       reach: float) -> None:
        """Draw cell's body piece erased behind the tail tip, whose center
        has travelled `reach` along the centerline from the entering edge: a
        straight tube is cut square there, a corner at the matching angle of
        its arc. The tip's disc caps the cut in both cases."""
        piece = self.body_images[frozenset({s_in, s_out})]
        rect = self._cell_rect(cell)
        if s_out == (-s_in[0], -s_in[1]):
            piece = self._trim_tube_end(piece, s_in, max(0, round(reach)))
        elif reach > 0:
            piece = piece.copy()
            pivot, start, sign = self._bend_geometry(rect, s_in, s_out)
            self._erase_sector(
                piece, pivot - Vector2(rect.topleft), start, sign, 0,
                math.degrees(reach / (CELL_SIZE // 2)))
        screen.blit(piece, rect)

    def _head_sweep(self, screen: pygame.Surface, t: float,
                    to_back: tuple[float, float],
                    to_front: tuple[float, float]) -> None:
        """Rotate the head 90 degrees about the bend's inner corner while the
        corner piece grows in behind it, erased a few degrees behind its base
        so the piece's edge stays hidden under it."""
        rect = self._cell_rect(self.body[1])
        pivot, start, sign = self._bend_geometry(rect, to_back, to_front)
        angle = 90 * t
        piece = self.body_images[frozenset({to_back, to_front})].copy()
        self._erase_sector(piece, pivot - Vector2(rect.topleft), start, sign,
                           angle + 3, 96)
        screen.blit(piece, rect)
        # transform.rotate and Vector2.rotate spin opposite ways on a y-down
        # screen, hence the mismatched signs.
        rotated = pygame.transform.rotate(self.head_images[to_back],
                                          -sign * angle)
        center = pivot + (Vector2(rect.center) - pivot).rotate(sign * angle)
        screen.blit(rotated, rotated.get_rect(
            center=(round(center.x), round(center.y))))
        landing = self.body[1] + Vector2(to_front)
        if landing != self.body[0]:  # the bend straddles the wrap seam
            shift = (self.body[0] - landing) * CELL_SIZE
            screen.blit(rotated, rotated.get_rect(center=(
                round(center.x + shift.x), round(center.y + shift.y))))

    def _tail_sweep(self, screen: pygame.Surface, t: float,
                    to_next: tuple[float, float],
                    slide: tuple[float, float]) -> None:
        """The tail is rounding the bend it just vacated: its tip disc picks
        up at the arc's midpoint, follows the tube's centerline around the
        corner and runs on into the landing cell. Both cells are erased
        exactly up to the tip, so the disc caps a clean tube throughout."""
        tail = self.body[-1]
        landing = self.prev_tail + Vector2(slide)  # tail, but unwrapped
        s_in = (-self.tail_dir[0], -self.tail_dir[1])
        back = (-slide[0], -slide[1])
        into_landing = (HALF_ARC if to_next != slide  # zigzag: next arc's half
                        else CELL_SIZE // 2 - self.tip_center_pull)
        s = (HALF_ARC + into_landing) * t
        self._consume_entry(screen, self.prev_tail, s_in, slide, HALF_ARC + s)
        self._consume_entry(screen, tail, back, to_next, s - HALF_ARC)
        if s <= HALF_ARC:  # still rounding the bend
            center = self._bend_point(self.prev_tail, s_in, slide,
                                      45 + math.degrees(s / (CELL_SIZE // 2)))
        elif to_next != slide:  # crossing into the zigzag's next bend
            center = self._bend_point(landing, back, to_next, math.degrees(
                (s - HALF_ARC) / (CELL_SIZE // 2)))
        else:
            center = (Vector2(self._cell_rect(landing).center)
                      + Vector2(slide) * (s - HALF_ARC - CELL_SIZE // 2))
        self._blit_tip(screen, center)
        if landing != tail:  # the bend straddles the wrap seam
            self._blit_tip(screen, center + (tail - landing) * CELL_SIZE)

    def _draw_head(self, screen: pygame.Surface, t: float) -> None:
        # Also draws the piece behind the head: trimmed under the sliding cap
        # when straight, growing in behind the sweep on a turn.
        to_front = self._offset(self.body[0], self.body[1])
        to_back = self._offset(self.body[2], self.body[1])
        if to_back == (-to_front[0], -to_front[1]):
            trim = max(0, CELL_SIZE // 2 - round(t * CELL_SIZE))
            piece = self._trim_tube_end(self._body_image(1), to_front, trim)
            screen.blit(piece, self._cell_rect(self.body[1]))
            image = self.head_images[(-self.direction.x, -self.direction.y)]
            self._slide_blit(screen, image, self.body[1], self.body[0], t)
        else:
            self._head_sweep(screen, t, to_back, to_front)

    def _draw_tail(self, screen: pygame.Surface, t: float) -> None:
        tail = self.body[-1]
        if self.prev_tail == tail:  # the snake just grew; the tail hasn't moved
            relation = self._offset(self.body[-2], tail)
            if relation == self.tail_dir:
                screen.blit(self.tail_images[relation], self._cell_rect(tail))
            else:  # resting mid-bend, parked at the arc's midpoint
                s_in = (-self.tail_dir[0], -self.tail_dir[1])
                self._consume_entry(screen, tail, s_in, relation, HALF_ARC)
                self._blit_tip(screen,
                               self._bend_point(tail, s_in, relation, 45))
            return
        # Cover the tail cell with last tick's body piece, cut back to the
        # advancing cap, and slide the tail sprite over it.
        to_prev = self._offset(self.prev_tail, tail)
        to_next = self._offset(self.body[-2], tail)
        slide = self._offset(tail, self.prev_tail)
        if slide != self.tail_dir:
            self._tail_sweep(screen, t, to_next, slide)
        elif to_next == slide:  # straight ahead
            self._consume_entry(screen, tail, to_prev, to_next,
                                round(t * CELL_SIZE) - CELL_SIZE // 2
                                - self.tip_center_pull)
            self._slide_blit(screen, self.tail_images[slide],
                             self.prev_tail, tail, t)
        else:
            # Arriving at a bend: the tip runs straight to the corner's edge,
            # then along the centerline arc to its midpoint, where next
            # tick's sweep picks it up. The straight sprite is clipped to the
            # vacated cell so it can't bury the curve; on the arc the disc
            # takes over as the tip.
            run = CELL_SIZE // 2 + self.tip_center_pull
            s = (run + HALF_ARC) * t
            self._consume_entry(screen, tail, to_prev, to_next, s - run)
            if s <= run:
                clip = screen.get_clip()
                screen.set_clip(self._cell_rect(self.prev_tail))
                self._slide_blit(screen, self.tail_images[slide],
                                 self.prev_tail, tail, s / CELL_SIZE)
                screen.set_clip(clip)
            else:
                center = self._bend_point(tail, to_prev, to_next,
                                          math.degrees((s - run)
                                                       / (CELL_SIZE // 2)))
                self._blit_tip(screen, center)
                entered = self.prev_tail + Vector2(slide)
                if entered != tail:  # arrived across the wrap seam
                    self._blit_tip(screen,
                                   center + (entered - tail) * CELL_SIZE)


class Game:
    def __init__(self) -> None:
        self.display = GameDisplay(VIEW_SIZE)
        self.screen = self.display.surface
        self.clock = pygame.time.Clock()
        self.ui = GameUI()
        self.apple_image = pygame.transform.scale(load_image("apple.png"),
                                                  (CELL_SIZE, CELL_SIZE))
        self.display.set_icon(self.apple_image)
        self.snake = Snake()
        self.crunch_sound = None
        if pygame.mixer.get_init():
            try:
                self.crunch_sound = pygame.mixer.Sound(SOUND_DIR / "crunch.wav")
            except (pygame.error, OSError):
                pass
        self.high_scores = load_high_scores()
        self.scores_dirty = False
        self.settings_dirty = False
        defaults = {"map_name": "Medium", "apple_count": 1,
                    "speed_name": "Normal", "walls_name": "Solid",
                    "volume_name": "On",
                    "motion_name": "Full"}
        settings = load_json(SETTINGS_FILE)
        for name, default in defaults.items():
            value = settings.get(name, default)
            valid = type(value) is type(default) and value in OPTIONS[name]
            setattr(self, name, value if valid else default)
        self.previous_volume = "On"
        self.cell_number = MAP_SIZES[self.map_name]
        self.board_pixels = self.cell_number * CELL_SIZE
        self.board_surface = pygame.Surface((self.board_pixels, self.board_pixels))
        self.fruits: list[Fruit] = []
        self.apples_eaten = 0
        self.move_interval = SPEEDS[self.speed_name]
        self.last_move_time = 0
        self.pause_start = 0
        self.state = "menu"
        self.state_changed = pygame.time.get_ticks()
        self.won = False
        self.new_best = False
        self.round_best = 0
        self.round_key: str | None = None
        self.death_reason = ""
        self.bite_fruit: Fruit | None = None
        self.score_time = -1000
        self.effects: list[tuple[Vector2, int]] = []
        self.focus_index = 0
        self.keyboard_focus = False
        self.pressed_action = None
        self.running = True

    @property
    def score(self) -> int:
        return self.apples_eaten

    @property
    def mode_key(self) -> str:
        key = f"{self.map_name}-{self.apple_count}-{self.speed_name}"
        if self.walls_name != "Solid":  # Preserve existing score-file keys.
            key += f"-{self.walls_name}"
        return key

    @property
    def high_score(self) -> int:
        return self.high_scores.get(self.mode_key, 0)

    @property
    def save_warning(self) -> str:
        if self.scores_dirty:
            return "Your best score could not be saved."
        if self.settings_dirty:
            return "Your settings could not be saved."
        return ""

    @property
    def reduced_motion(self) -> bool:
        return self.motion_name == "Reduced"

    @property
    def focus_groups(self) -> tuple[str, ...]:
        if self.state == "menu":
            return (*OPTIONS, "play")
        if self.state in ("paused", "game_over"):
            return ("primary", "menu")
        if self.state == "ready":
            return ("sound", "menu")
        return ("sound", "pause")

    @property
    def focused_group(self) -> str | None:
        return self.focus_groups[self.focus_index] if self.keyboard_focus else None

    def occupied_cells(self) -> list[Vector2]:
        return self.snake.body + [fruit.pos for fruit in self.fruits]

    def change_state(self, state: str) -> None:
        self.state = state
        self.state_changed = pygame.time.get_ticks()
        self.focus_index = 0
        self.pressed_action = None
        self.ui.buttons.clear()

    def save_settings(self) -> None:
        settings = {name: getattr(self, name) for name in OPTIONS}
        self.settings_dirty = not save_json(SETTINGS_FILE, settings)

    def remember_score(self) -> None:
        if self.round_key and self.score > self.high_scores.get(self.round_key, 0):
            self.high_scores[self.round_key] = self.score
            self.scores_dirty = True
        if self.scores_dirty:
            self.scores_dirty = not save_high_scores(self.high_scores)

    def run(self) -> None:
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle_event(event)
                if not self.running:
                    break
                self.advance(pygame.time.get_ticks())
                self.draw()
                self.display.present()
                self.clock.tick(FPS)
        finally:
            self.remember_score()
            if self.settings_dirty:
                self.save_settings()
            self.display.close()
            pygame.quit()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type in (pygame.QUIT, pygame.WINDOWCLOSE):
            self.remember_score()
            self.running = False
            return
        if event.type == pygame.WINDOWFOCUSLOST:
            self.pressed_action = None
            if self.state == "playing":
                self.pause()
            return
        if event.type == pygame.MOUSEMOTION:
            self.keyboard_focus = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.keyboard_focus = False
            self.pressed_action = self.ui.hit_test(event.pos, self.display.size)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            action = self.ui.hit_test(event.pos, self.display.size)
            if action is not None and action == self.pressed_action:
                self.activate(action)
            self.pressed_action = None
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if key == pygame.K_m:
            self.toggle_sound()
            return
        if key == pygame.K_TAB:
            step = -1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1
            self.move_focus(step)
            return
        if self.state == "menu":
            if key in (pygame.K_UP, pygame.K_DOWN):
                self.move_focus(-1 if key == pygame.K_UP else 1)
            elif key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.keyboard_focus = True
                self.cycle_option(-1 if key == pygame.K_LEFT else 1)
            elif key == pygame.K_RETURN:
                self.start_game()
            elif key == pygame.K_SPACE:
                if self.focused_group in OPTIONS:
                    self.cycle_option(1)
                else:
                    self.start_game()
        elif self.state == "ready":
            if key in KEY_DIRECTIONS:
                direction = KEY_DIRECTIONS[key]
                if direction != -self.snake.direction:
                    self.snake.queue_turn(direction)
                    self.last_move_time = pygame.time.get_ticks()
                    self.change_state("playing")
                    self.begin_step()
            elif key == pygame.K_ESCAPE:
                self.open_menu()
            elif key == pygame.K_RETURN and self.focused_group:
                self.activate((self.focused_group,))
        elif self.state == "playing":
            if key in KEY_DIRECTIONS:
                self.snake.queue_turn(KEY_DIRECTIONS[key])
            elif key in (pygame.K_SPACE, pygame.K_p):
                self.pause()
            elif key == pygame.K_ESCAPE:
                self.open_menu()
            elif key == pygame.K_RETURN and self.focused_group:
                self.activate((self.focused_group,))
        else:
            if key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                self.move_focus(-1 if key in (pygame.K_LEFT, pygame.K_UP) else 1)
            elif key == pygame.K_ESCAPE:
                self.open_menu()
            elif key == pygame.K_RETURN:
                self.activate((self.focused_group or "primary",))
            elif key == pygame.K_SPACE or (key == pygame.K_p and self.state == "paused"):
                self.activate(("primary",))

    def move_focus(self, step: int) -> None:
        if not self.keyboard_focus:
            self.focus_index = 0 if step > 0 else len(self.focus_groups) - 1
        else:
            self.focus_index = (self.focus_index + step) % len(self.focus_groups)
        self.keyboard_focus = True

    def cycle_option(self, step: int) -> None:
        group = self.focused_group
        if group in OPTIONS:
            values = OPTIONS[group]
            value = values[(values.index(getattr(self, group)) + step) % len(values)]
            self.activate(("option", group, value))

    def activate(self, action: tuple) -> None:
        command = action[0]
        if command == "option" and self.state == "menu":
            _, group, value = action
            setattr(self, group, value)
            self.focus_index = self.focus_groups.index(group)
            self.save_settings()
        elif command == "play":
            self.start_game()
        elif command == "sound":
            self.toggle_sound()
        elif command == "pause" and self.state == "playing":
            self.pause()
        elif command == "primary":
            if self.state == "paused":
                self.resume()
            elif self.state == "game_over":
                self.start_game()
        elif command == "menu":
            self.open_menu()

    def toggle_sound(self) -> None:
        if self.volume_name == "Off":
            self.volume_name = self.previous_volume
        else:
            self.previous_volume = self.volume_name
            self.volume_name = "Off"
        if self.crunch_sound:
            self.crunch_sound.set_volume(VOLUMES[self.volume_name])
        self.save_settings()

    def start_game(self) -> None:
        self.cell_number = MAP_SIZES[self.map_name]
        self.board_pixels = self.cell_number * CELL_SIZE
        self.screen = self.display.resize((self.board_pixels, HUD_HEIGHT + self.board_pixels))
        self.board_surface = pygame.Surface((self.board_pixels, self.board_pixels))
        self.snake.reset(self.cell_number, wrap=self.walls_name == "Wrap")
        self.fruits = []
        for _ in range(self.apple_count):
            fruit = Fruit(self.apple_image)
            fruit.randomize(self.occupied_cells(), self.cell_number)
            self.fruits.append(fruit)
        self.apples_eaten = 0
        self.round_key = self.mode_key
        self.round_best = self.high_score
        self.new_best = False
        self.won = False
        self.death_reason = ""
        self.bite_fruit = None
        self.effects.clear()
        self.score_time = -1000
        self.move_interval = SPEEDS[self.speed_name]
        self.change_state("ready")

    def open_menu(self) -> None:
        self.remember_score()
        self.screen = self.display.resize(VIEW_SIZE)
        self.change_state("menu")

    def pause(self) -> None:
        now = pygame.time.get_ticks()
        self.advance(now)
        if self.state == "playing":
            self.pause_start = now
            self.change_state("paused")

    def resume(self) -> None:
        elapsed = pygame.time.get_ticks() - self.pause_start
        self.last_move_time += elapsed
        self.score_time += elapsed
        self.effects = [(pos, start + elapsed) for pos, start in self.effects]
        self.change_state("playing")

    def begin_step(self) -> None:
        """Schedule one legal move. Rendering interpolates toward its result."""
        direction = (self.snake.pending_turns[0] if self.snake.pending_turns
                     else self.snake.direction)
        target = self.snake.head + direction
        if self.snake.wrap:
            target = Vector2(target.x % self.cell_number, target.y % self.cell_number)
        self.bite_fruit = next((f for f in self.fruits if f.pos == target), None)
        occupied = self.snake.body if self.bite_fruit else self.snake.body[:-1]
        if not (0 <= target.x < self.cell_number and 0 <= target.y < self.cell_number):
            self.death_reason = "The edge got you. Another go?"
            self.end_game(won=False)
        elif target in occupied:
            self.death_reason = "A little too close to your tail."
            self.end_game(won=False)
        else:
            if self.bite_fruit:
                self.snake.grow()
            self.snake.move()

    def finish_step(self, now: int) -> None:
        """Commit the bite only when the visible head reaches the apple."""
        fruit = self.bite_fruit
        if fruit is None:
            return
        self.bite_fruit = None
        self.apples_eaten += 1
        self.score_time = now
        self.effects.append((fruit.pos.copy(), now))
        if self.crunch_sound and VOLUMES[self.volume_name] > 0:
            self.crunch_sound.set_volume(VOLUMES[self.volume_name])
            self.crunch_sound.play()
        self.fruits.remove(fruit)
        self.remember_score()
        if len(self.snake.body) == self.cell_number ** 2:
            self.end_game(won=True)
        elif fruit.randomize(self.occupied_cells(), self.cell_number):
            self.fruits.append(fruit)

    def advance(self, now: int) -> None:
        if self.state != "playing":
            return
        # Keep fractional time between ticks. Bound catch-up after a long stall.
        self.last_move_time = max(self.last_move_time, now - 4 * self.move_interval)
        while self.state == "playing" and now - self.last_move_time >= self.move_interval:
            self.finish_step(now)
            if self.state != "playing":
                break
            self.last_move_time += self.move_interval
            self.begin_step()

    def end_game(self, won: bool) -> None:
        self.won = won
        self.new_best = self.score > self.round_best
        self.remember_score()
        self.change_state("game_over")

    def draw(self) -> None:
        self.screen = self.display.sync()
        now = self.pause_start if self.state == "paused" else pygame.time.get_ticks()
        progress = (min(max((now - self.last_move_time) / self.move_interval, 0), 1)
                    if self.state in ("playing", "paused") else 1.0)
        self.ui.draw(self, progress, now)


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    Game().run()


if __name__ == "__main__":
    main()
