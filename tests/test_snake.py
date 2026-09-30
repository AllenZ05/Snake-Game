"""Headless regression checks. Run: python -m unittest discover -s tests -v."""

from ui import GRASS_DARK, GRASS_LIGHT, HUD_HEIGHT, INK, VIEW_SIZE
import snake
import pygame
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"


def cycle_for(size):
    """A Hamiltonian cycle on an even square, used to reach full-board states."""
    cycle = [(x, 0) for x in range(size)]
    for y in range(1, size):
        columns = range(size - 1, 0, -1) if y % 2 else range(1, size)
        cycle.extend((x, y) for x in columns)
    cycle.extend((0, y) for y in range(size - 1, 0, -1))
    return cycle


class GameTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        for name, path in (("HIGH_SCORES_FILE", root / "scores.json"),
                           ("SETTINGS_FILE", root / "settings.json")):
            patcher = patch.object(snake, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        random.seed(12)
        self.game = snake.Game()

    def tearDown(self):
        pygame.quit()

    def key(self, key, now=1000, **extra):
        with patch("pygame.time.get_ticks", return_value=now):
            self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, **extra))

    def begin(self, now=1000):
        self.game.start_game()
        self.key(pygame.K_RIGHT, now)

    def test_all_modes_have_valid_spawns_and_render_every_state(self):
        g = self.game
        keys = set()
        for size in snake.MAP_SIZES:
            for apples in snake.APPLE_COUNTS:
                for speed in snake.SPEEDS:
                    for walls in snake.WALL_MODES:
                        with self.subTest(size=size, apples=apples, speed=speed, walls=walls):
                            g.map_name, g.apple_count = size, apples
                            g.speed_name, g.walls_name = speed, walls
                            g.start_game()
                            occupied = [tuple(v) for v in g.occupied_cells()]
                            self.assertEqual(len(occupied), len(set(occupied)))
                            self.assertEqual(len(g.fruits), apples)
                            keys.add(g.mode_key)
                            for state in ("ready", "paused", "game_over"):
                                g.state = state
                                g.draw()
        self.assertEqual(len(keys), 54)

    def test_first_input_preserves_the_visible_snake_position(self):
        g = self.game
        g.start_game()
        g.fruits[0].pos = pygame.Vector2(0, 0)
        before = pygame.Surface(g.board_surface.get_size(), pygame.SRCALPHA)
        after = before.copy()
        g.snake.draw(before, 1)
        self.key(pygame.K_RIGHT)
        g.snake.draw(after, 0)
        self.assertEqual(pygame.image.tostring(before, "RGBA"),
                         pygame.image.tostring(after, "RGBA"))

    def test_bite_sound_score_and_record_commit_on_arrival(self):
        g = self.game
        g.start_game()
        g.fruits[0].pos = g.snake.head + snake.RIGHT
        g.crunch_sound = Mock()
        self.key(pygame.K_RIGHT)
        self.assertEqual(g.score, 0)
        g.crunch_sound.play.assert_not_called()
        g.advance(1149)
        self.assertEqual(g.score, 0)
        g.advance(1150)
        self.assertEqual(g.score, 1)
        self.assertEqual(len(g.snake.body), 4)
        g.crunch_sound.play.assert_called_once()
        self.assertEqual(snake.load_high_scores()[g.mode_key], 1)

    def test_full_board_wins_with_exact_score_for_one_and_five_apples(self):
        g = self.game
        for apples in (1, 5):
            with self.subTest(apples=apples):
                g.map_name = "Small"
                g.apple_count = apples
                g.start_game()
                cycle = cycle_for(12)
                g.snake.body = [pygame.Vector2(p) for p in reversed(cycle[:-apples])]
                g.snake.prev_tail = g.snake.body[-1]
                g.snake.direction = snake.UP
                g.apples_eaten = len(g.snake.body) - snake.STARTING_LENGTH
                for fruit, pos in zip(g.fruits, cycle[-apples:]):
                    fruit.pos = pygame.Vector2(pos)
                self.key(pygame.K_UP)
                for step in range(apples):
                    g.advance(1000 + (step + 1) * g.move_interval)
                self.assertTrue(g.won)
                self.assertEqual(g.state, "game_over")
                self.assertEqual(g.score, 141)
                self.assertEqual(len(g.snake.body), 144)
                self.assertFalse(g.fruits)
                g.draw()

    def test_record_is_not_assigned_to_a_different_menu_mode(self):
        g = self.game
        g.start_game()
        g.apples_eaten = 9
        original = g.mode_key
        g.open_menu()
        g.map_name = "Small"
        g.handle_event(pygame.event.Event(pygame.QUIT))
        scores = snake.load_high_scores()
        self.assertEqual(scores[original], 9)
        self.assertNotIn(g.mode_key, scores)

    def test_quitting_during_a_round_saves_the_record(self):
        self.begin()
        self.game.apples_eaten = 7
        self.game.handle_event(pygame.event.Event(pygame.QUIT))
        self.assertFalse(self.game.running)
        self.assertEqual(snake.load_high_scores()[self.game.mode_key], 7)

    def test_pause_on_focus_loss_preserves_interpolation(self):
        g = self.game
        self.begin()
        with patch("pygame.time.get_ticks", return_value=1060):
            g.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertEqual(g.state, "paused")
        self.assertEqual(g.pause_start - g.last_move_time, 60)
        self.key(pygame.K_SPACE, 4060)
        self.assertEqual(g.state, "playing")
        self.assertEqual(4060 - g.last_move_time, 60)

    def test_pause_preserves_sprite_colors_across_repeated_frames(self):
        g = self.game
        g.start_game()
        g.snake.body = [pygame.Vector2(p) for p in ((5, 1), (4, 1), (3, 1))]
        g.snake.prev_tail = g.snake.body[-1]
        g.fruits[0].pos = pygame.Vector2(12, 13)
        self.key(pygame.K_RIGHT, 1000)
        with patch("pygame.time.get_ticks", return_value=1075):
            g.draw()
            playing = g.screen.copy()
            g.pause()
        regions = [pygame.Rect(0, HUD_HEIGHT, g.board_pixels, 120),
                   pygame.Rect(12 * 40, 13 * 40 + HUD_HEIGHT, 40, 40)]
        for now in (1075, 2000, 10000):
            with patch("pygame.time.get_ticks", return_value=now):
                g.draw()
            for region in regions:
                self.assertEqual(pygame.image.tostring(playing.subsurface(region), "RGB"),
                                 pygame.image.tostring(g.screen.subsurface(region), "RGB"))

    def test_retina_text_uses_new_glyph_pixels_instead_of_enlarging_a_bitmap(self):
        ui = self.game.ui
        ui.target = pygame.Surface((300, 60))
        ui.target.fill(GRASS_LIGHT)
        ui.text("Pause (P)", (150, 30), 22)
        enlarged = pygame.transform.scale(ui.target, (600, 120))
        ui.target = pygame.Surface((600, 120))
        ui.target.fill(GRASS_LIGHT)
        ui.pixel_scale = (2, 2)
        rect = ui.text("Pause (P)", (150, 30), 22)
        self.assertEqual(rect.center, (300, 60))
        self.assertEqual(ui.font(22).get_height(), pygame.font.Font(None, 44).get_height())
        self.assertNotEqual(pygame.image.tostring(ui.target, "RGB"),
                            pygame.image.tostring(enlarged, "RGB"))

    def test_game_over_and_win_keep_original_sprite_colors(self):
        g = self.game
        g.start_game()
        g.snake.body = [pygame.Vector2(p) for p in ((5, 1), (4, 1), (3, 1))]
        g.snake.prev_tail = g.snake.body[-1]
        g.fruits[0].pos = pygame.Vector2(12, 13)
        g.state = "playing"
        g.last_move_time = 0
        with patch("pygame.time.get_ticks", return_value=1000):
            g.draw()
        playing = g.screen.copy()
        regions = [(0, HUD_HEIGHT, g.board_pixels, 120),
                   (12 * 40, 13 * 40 + HUD_HEIGHT, 40, 40)]
        for won in (False, True):
            g.end_game(won)
            g.draw()
            for region in regions:
                self.assertEqual(pygame.image.tostring(playing.subsurface(region), "RGB"),
                                 pygame.image.tostring(g.screen.subsurface(region), "RGB"))

    def test_retina_keeps_mouse_targets_in_window_coordinates(self):
        g = self.game
        g.display.surface = pygame.Surface((VIEW_SIZE[0] * 2, VIEW_SIZE[1] * 2))
        g.draw()
        self.assertEqual(g.ui.pixel_scale, (2, 2))
        _, rect = next((a, r) for a, r in g.ui.buttons if a == ("play",))
        for event_type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            g.handle_event(pygame.event.Event(event_type, button=1, pos=rect.center))
        self.assertEqual(g.state, "ready")

    def test_retina_preserves_sprite_pixels_and_game_layout(self):
        g = self.game
        g.start_game()
        g.state = "playing"
        g.last_move_time = 0
        width, height = g.display.size
        g.display.surface = pygame.Surface((width * 2, height * 2))
        with patch("pygame.time.get_ticks", return_value=1000):
            g.draw()
        actual = g.screen.subsurface((0, HUD_HEIGHT * 2, width * 2, g.board_pixels * 2))
        expected = pygame.transform.scale(g.board_surface, actual.get_size())
        self.assertEqual(pygame.image.tostring(actual, "RGB"),
                         pygame.image.tostring(expected, "RGB"))
        self.assertEqual(g.display.size, (640, 700))

    def test_header_shortcuts_fit_small_board_and_match_key_bindings(self):
        g = self.game
        g.map_name = "Small"
        self.begin()
        with patch.object(g.ui, "button", wraps=g.ui.button) as button:
            g.draw()
        labels = [call.args[2] for call in button.call_args_list]
        self.assertIn("Mute (M)", labels)
        self.assertIn("Pause (P)", labels)
        for call in button.call_args_list:
            rect, label = pygame.Rect(call.args[1]), call.args[2]
            self.assertLessEqual(g.ui.font(call.kwargs["size"]).size(label)[0], rect.w - 8)
        self.key(pygame.K_m)
        self.assertEqual(g.volume_name, "Off")
        self.key(pygame.K_p, 1060)
        self.assertEqual(g.state, "paused")
        self.key(pygame.K_p, 2060)
        self.assertEqual(g.state, "playing")

    def test_tick_remainder_is_preserved(self):
        self.begin()
        self.game.advance(1167)
        self.assertEqual(self.game.last_move_time, 1150)

    def test_wall_collision_keeps_the_last_valid_board(self):
        g = self.game
        g.start_game()
        g.snake.body = [pygame.Vector2(15, 5), pygame.Vector2(14, 5), pygame.Vector2(13, 5)]
        g.snake.prev_tail = g.snake.body[-1]
        before = [v.copy() for v in g.snake.body]
        self.key(pygame.K_RIGHT)
        self.assertEqual(g.state, "game_over")
        self.assertEqual(g.snake.body, before)
        g.draw()

    def test_moving_into_a_departing_tail_is_legal(self):
        g = self.game
        g.start_game()
        g.snake.body = [pygame.Vector2(p) for p in ((2, 2), (2, 3), (1, 3), (1, 2))]
        g.snake.prev_tail = g.snake.body[-1]
        g.snake.direction = snake.UP
        g.fruits[0].pos = pygame.Vector2(9, 9)
        self.key(pygame.K_LEFT)
        self.assertEqual(g.state, "playing")
        self.assertEqual(g.snake.head, pygame.Vector2(1, 2))

    def test_wrap_and_buffered_turns(self):
        g = self.game
        g.walls_name = "Wrap"
        g.start_game()
        g.snake.body = [pygame.Vector2(15, 5), pygame.Vector2(14, 5), pygame.Vector2(13, 5)]
        g.snake.prev_tail = g.snake.body[-1]
        self.key(pygame.K_RIGHT)
        self.assertEqual(g.snake.head, pygame.Vector2(0, 5))
        g.snake.queue_turn(snake.LEFT)
        self.assertFalse(g.snake.pending_turns)
        g.snake.queue_turn(snake.UP)
        g.snake.queue_turn(snake.LEFT)
        g.snake.queue_turn(snake.DOWN)
        self.assertEqual(len(g.snake.pending_turns), 2)
        for time in (1050, 1150, 1200, 1300, 1375):
            g.advance(time)
            with patch("pygame.time.get_ticks", return_value=time):
                g.draw()
        self.assertEqual(g.snake.direction, snake.LEFT)
        self.assertEqual(g.state, "playing")

    def test_continuous_turns_and_growth_render_without_invalid_segments(self):
        g = self.game
        g.map_name = "Small"
        g.apple_count = 5
        g.start_game()
        cycle = cycle_for(12)
        g.snake.body = [pygame.Vector2(p) for p in reversed(cycle[:3])]
        g.snake.prev_tail = g.snake.body[-1]
        for fruit in g.fruits:
            fruit.randomize(g.occupied_cells(), g.cell_number)
        self.key(pygame.K_RIGHT)
        for step in range(600):
            index = cycle.index(tuple(g.snake.head))
            target = pygame.Vector2(cycle[(index + 1) % len(cycle)])
            g.snake.queue_turn(target - g.snake.head)
            for progress in (0, .25, .5, .75, 1):
                g.snake.draw(g.board_surface, progress)
            g.advance(1000 + (step + 1) * g.move_interval)
            self.assertEqual(g.state, "playing")
            self.assertEqual(len(g.snake.body), len(set(map(tuple, g.snake.body))))
        self.assertGreater(g.score, 20)

    def test_self_collision_and_muted_bite(self):
        g = self.game
        g.start_game()
        g.volume_name = "Off"
        g.crunch_sound = Mock()
        g.fruits[0].pos = g.snake.head + snake.RIGHT
        self.key(pygame.K_RIGHT)
        g.advance(1150)
        self.assertEqual(g.score, 1)
        g.crunch_sound.play.assert_not_called()
        g.snake.body = [pygame.Vector2(p) for p in ((2, 2), (2, 3), (1, 3), (1, 2), (1, 1))]
        g.snake.direction = snake.UP
        g.snake.pending_turns.clear()
        g.snake.queue_turn(snake.LEFT)
        g.begin_step()
        self.assertEqual(g.state, "game_over")
        self.assertFalse(g.won)

    def test_keyboard_menu_and_native_mouse_controls(self):
        g = self.game
        self.key(pygame.K_TAB)
        self.key(pygame.K_RIGHT)
        self.assertEqual(g.map_name, "Large")
        self.assertEqual(snake.load_json(snake.SETTINGS_FILE)["map_name"], "Large")
        g.draw()
        action, rect = next((a, r) for a, r in g.ui.buttons if a == ("play",))
        pos = rect.center
        self.assertEqual(g.ui.hit_test(pos, VIEW_SIZE), action)
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0)))
        self.assertEqual(g.state, "menu")
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))
        self.assertEqual(g.state, "ready")

    def test_board_and_original_head_sprite_reach_screen_without_resampling(self):
        g = self.game
        for name, cells in snake.MAP_SIZES.items():
            with self.subTest(size=name):
                g.map_name = name
                g.start_game()
                g.fruits[0].pos = pygame.Vector2(0, 0)
                g.state = "playing"
                g.last_move_time = 0
                with patch("pygame.time.get_ticks", return_value=1000):
                    g.draw()
                self.assertEqual(g.screen.get_size(), (cells * 40, cells * 40 + HUD_HEIGHT))
                visible = g.screen.subsurface((0, HUD_HEIGHT, cells * 40, cells * 40))
                self.assertEqual(pygame.image.tostring(visible, "RGB"),
                                 pygame.image.tostring(g.board_surface, "RGB"))
                head = g.snake.head
                expected = pygame.Surface((40, 40))
                expected.fill(GRASS_DARK if (int(head.x + head.y) % 2 == 0) else GRASS_LIGHT)
                expected.blit(pygame.image.load(snake.GRAPHICS_DIR / "head_right.png"), (0, 0))
                actual = visible.subsurface((int(head.x * 40), int(head.y * 40), 40, 40))
                self.assertEqual(pygame.image.tostring(actual, "RGB"),
                                 pygame.image.tostring(expected, "RGB"))

    def test_bad_scores_and_settings_recover_safely(self):
        for data in ("null", "[]", "broken", '{"bad": -2, "boolean": true, "text": "9", "ok": 7}'):
            snake.HIGH_SCORES_FILE.write_text(data)
            scores = snake.load_high_scores()
            self.assertTrue(all(type(v) is int and v >= 0 for v in scores.values()))
        self.assertEqual(scores, {"ok": 7})
        snake.SETTINGS_FILE.write_text('{"map_name": [], "apple_count": true, "volume_name": "bad"}')
        g = snake.Game()
        self.assertEqual((g.map_name, g.apple_count, g.volume_name), ("Medium", 1, "On"))

    def test_failed_save_preserves_previous_file_and_retries(self):
        g = self.game
        g.start_game()
        snake.save_high_scores({g.mode_key: 4})
        g.apples_eaten = 8
        with patch.object(Path, "replace", side_effect=OSError("read only")):
            g.remember_score()
        self.assertTrue(g.scores_dirty)
        self.assertEqual(snake.load_high_scores()[g.mode_key], 4)
        self.assertEqual(len(list(snake.HIGH_SCORES_FILE.parent.iterdir())), 1)
        g.remember_score()
        self.assertFalse(g.scores_dirty)
        self.assertEqual(snake.load_high_scores()[g.mode_key], 8)

    def test_missing_audio_and_muting_are_safe(self):
        pygame.mixer.quit()
        g = snake.Game()
        self.assertIsNone(g.crunch_sound)
        g.toggle_sound()
        self.assertEqual(g.volume_name, "Off")
        g.toggle_sound()
        self.assertEqual(g.volume_name, "On")
        g.draw()


if __name__ == "__main__":
    unittest.main()
