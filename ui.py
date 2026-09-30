"""Original game layout, with text drawn at the display's pixel density."""

from __future__ import annotations

import math

import pygame

VIEW_SIZE = (640, 720)
HUD_HEIGHT = 60
GRASS_LIGHT = (175, 220, 75)
GRASS_DARK = (167, 209, 61)
INK = (56, 74, 12)
WHITE = (255, 255, 255)


class GameUI:
    def __init__(self) -> None:
        self.target = None
        self.fonts = {}
        self.buttons: list[tuple[tuple, pygame.Rect]] = []
        self.board_cache = {}
        self.pointer = (-1, -1)
        self.pixel_scale = (1.0, 1.0)

    def font(self, size, bold=False):
        pixel_size = round(size * self.pixel_scale[1])
        key = (pixel_size, bold)
        if key not in self.fonts:
            font = pygame.font.Font(None, pixel_size)
            font.set_bold(bold)
            self.fonts[key] = font
        return self.fonts[key]

    def text(self, label, pos, size=24, color=INK, bold=False, anchor="center"):
        # Rasterize the font at the actual backing resolution. Turning off
        # antialiasing cannot fix a low-resolution window enlarged by the OS.
        image = self.font(size, bold).render(str(label), True, color)
        rect = image.get_rect(**{anchor: self.pixel_point(pos)})
        self.target.blit(image, rect)
        return rect

    def pixel_point(self, point):
        return tuple(round(value * scale) for value, scale in zip(point, self.pixel_scale))

    def pixel_rect(self, rect):
        rect = pygame.Rect(rect)
        left, top = self.pixel_point(rect.topleft)
        right, bottom = self.pixel_point(rect.bottomright)
        return pygame.Rect(left, top, right - left, bottom - top)

    def rectangle(self, color, rect, width=0, radius=0):
        scale = min(self.pixel_scale)
        pygame.draw.rect(self.target, color, self.pixel_rect(rect),
                         round(width * scale), border_radius=round(radius * scale))

    def blit_artwork(self, surface, pos):
        destination = self.pixel_rect(pygame.Rect(pos, surface.get_size()))
        if destination.size != surface.get_size():
            # Preserve the original sprite pixels with nearest-neighbor
            # replication on Retina; don't blur the artwork with filtering.
            surface = pygame.transform.scale(surface, destination.size)
        self.target.blit(surface, destination)

    def hit_test(self, pos, size):
        # SDL mouse events use window coordinates, not Retina backing pixels.
        if not pygame.Rect((0, 0), size).collidepoint(pos):
            return None
        return next((action for action, rect in reversed(self.buttons)
                     if rect.collidepoint(pos)), None)

    def button(self, game, rect, label, action, *, selected=False,
               primary=False, group=None, size=24):
        rect = pygame.Rect(rect)
        self.buttons.append((action, rect))
        hovered = rect.collidepoint(self.pointer) and not game.keyboard_focus
        pressed = hovered and game.pressed_action == action
        focused = game.focused_group == (group or action[0])
        if action[0] == "option":
            focused = focused and selected
        dark = game.state != "menu"
        filled = primary or selected
        if dark:
            fill, color = (GRASS_LIGHT, INK) if filled else (INK, WHITE)
            border = GRASS_LIGHT
        else:
            fill, color = (INK, GRASS_LIGHT) if filled else (GRASS_LIGHT, INK)
            border = INK
        if hovered:
            fill = tuple(min(255, component + 12) for component in fill)
        if pressed:
            fill = tuple(max(0, component - 18) for component in fill)
        self.rectangle(fill, rect, radius=7)
        self.rectangle(border, rect, 1, radius=7)
        if focused:
            self.rectangle(WHITE if dark else INK, rect.inflate(6, 6), 2, radius=10)
        self.text(label, (rect.centerx, rect.centery + int(pressed)), size, color)

    def option_row(self, game, label, group, values, y):
        self.text(label, (320, y), 28)
        width = min(132, (420 - (len(values) - 1) * 12) // len(values))
        start = 320 - (len(values) * width + (len(values) - 1) * 12) // 2
        for index, value in enumerate(values):
            self.button(game, (start + index * (width + 12), y + 24, width, 44),
                        str(value), ("option", group, value),
                        selected=getattr(game, group) == value, group=group)

    def draw(self, game, progress, now):
        # Layout remains in the original window coordinates; text and shapes
        # are drawn directly into the full-resolution physical framebuffer.
        self.target = game.screen
        self.pixel_scale = game.display.pixel_scale
        self.buttons.clear()
        self.pointer = pygame.mouse.get_pos()
        self.target.fill(GRASS_LIGHT)
        if game.state == "menu":
            self.draw_menu(game)
        else:
            self.draw_game(game, progress, now)
        if game.save_warning:
            width, height = game.display.size
            self.rectangle(INK, (0, height - 28, width, 28))
            self.text(game.save_warning, (width // 2, height - 14), 20, WHITE)

    def draw_menu(self, game):
        self.text("Snake", (320, 70), 50)
        self.option_row(game, "Map Size", "map_name", ("Small", "Medium", "Large"), 140)
        self.option_row(game, "Apples", "apple_count", (1, 3, 5, 7), 236)
        self.option_row(game, "Speed", "speed_name", ("Slow", "Normal", "Fast"), 332)
        self.option_row(game, "Walls", "walls_name", ("Solid", "Wrap"), 428)
        volume = ("Off", "Quiet", "On")
        next_volume = volume[(volume.index(game.volume_name) + 1) % len(volume)]
        self.button(game, (176, 520, 138, 32), f"Sound: {game.volume_name}",
                    ("option", "volume_name", next_volume), group="volume_name", size=22,
                    selected=game.focused_group == "volume_name")
        next_motion = "Reduced" if game.motion_name == "Full" else "Full"
        self.button(game, (326, 520, 138, 32),
                    "Effects: " + ("On" if game.motion_name == "Full" else "Reduced"),
                    ("option", "motion_name", next_motion), group="motion_name", size=22,
                    selected=game.focused_group == "motion_name")
        self.button(game, (210, 577, 220, 48), "Play", ("play",), primary=True, size=30)
        self.text(f"High Score: {game.high_score}", (320, 650), 26)
        self.text("WASD / Arrows to move  ·  Space to pause  ·  Esc for menu", (320, 684), 22)
        self.text("Tab: options  ·  Left / right: change  ·  Enter: play  ·  M: sound",
                  (320, 706), 20)

    def draw_game(self, game, progress, now):
        width, height = game.display.size
        self.draw_board(game, progress, now)
        self.blit_artwork(game.board_surface, (0, HUD_HEIGHT))
        self.rectangle(INK, (0, 0, width, HUD_HEIGHT))
        self.blit_artwork(game.apple_image, (12, 10))
        self.text(game.score, (58, 30), 30, WHITE, anchor="midleft")
        self.text(f"Best: {game.high_score}", (width - 16, 30), 30, WHITE, anchor="midright")
        self.button(game, (width // 2 - 116, 13, 112, 34),
                    "Unmute (M)" if game.volume_name == "Off" else "Mute (M)", ("sound",), size=22)
        self.button(game, (width // 2 + 6, 13, 106, 34),
                    "Menu (Esc)" if game.state == "ready" else "Pause (P)",
                    ("menu",) if game.state == "ready" else ("pause",), size=22)
        if game.state == "ready":
            rect = pygame.Rect(0, 0, 370, 44)
            rect.midbottom = (width // 2, height - 22)
            self.rectangle(INK, rect, radius=8)
            self.text("Press WASD or an arrow key to start", rect.center, 24, WHITE)
        elif game.state in ("paused", "game_over"):
            self.draw_overlay(game)

    def draw_board(self, game, progress, now):
        if game.cell_number not in self.board_cache:
            grass = pygame.Surface((game.board_pixels, game.board_pixels))
            grass.fill(GRASS_LIGHT)
            for row in range(game.cell_number):
                for col in range(row % 2, game.cell_number, 2):
                    pygame.draw.rect(grass, GRASS_DARK, (col * 40, row * 40, 40, 40))
            self.board_cache[game.cell_number] = grass
        board = game.board_surface
        board.blit(self.board_cache[game.cell_number], (0, 0))
        for fruit in game.fruits:
            fruit.draw(board)
        game.snake.draw(board, progress)
        game.effects = [(pos, start) for pos, start in game.effects if now - start < 300]
        if game.reduced_motion or not game.effects:
            return
        particles = pygame.Surface(board.get_size(), pygame.SRCALPHA)
        for pos, start in game.effects:
            age = max(0, (now - start) / 300)
            center = (pos + pygame.Vector2(.5, .5)) * 40
            for index in range(5):
                angle = index * math.tau / 5
                point = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * (15 + age * 12)
                pygame.draw.circle(particles, (*WHITE, round(180 * (1 - age))),
                                   (round(point.x), round(point.y)), 2)
        board.blit(particles, (0, 0))

    def draw_overlay(self, game):
        self.buttons.clear()
        width, height = game.display.size
        paused = game.state == "paused"
        card = pygame.Rect(0, 0, min(width - 48, 400), 210 if paused else 296)
        card.center = (width // 2, (height + HUD_HEIGHT) // 2)
        self.rectangle(INK, card, radius=14)
        title = "Paused" if paused else "You Win!" if game.won else "Game Over"
        self.text(title, (card.centerx, card.y + 40), 44, WHITE)
        if paused:
            self.text("Space / P to resume", (card.centerx, card.y + 85), 26, WHITE)
            button_y = card.y + 117
            self.text("Esc for menu", (card.centerx, card.bottom - 24), 20, WHITE)
        else:
            self.text(f"Your Score: {game.score}", (card.centerx, card.y + 92), 32, WHITE)
            self.text(f"High Score: {game.high_score}", (card.centerx, card.y + 132), 26, WHITE)
            if game.new_best:
                self.text("New high score!", (card.centerx, card.y + 170), 24, GRASS_LIGHT)
            button_y = card.y + 207
            self.text("Space to replay  ·  Esc for menu", (card.centerx, card.bottom - 22), 20, WHITE)
        self.button(game, (card.centerx - 162, button_y, 180, 44),
                    "Resume" if paused else "Play Again", ("primary",), primary=True)
        self.button(game, (card.centerx + 30, button_y, 132, 44), "Menu", ("menu",))
