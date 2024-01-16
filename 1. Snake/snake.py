import pygame
import sys
import random
from pygame.math import Vector2


class FRUIT:
    def __init__(self):
        self.randomize()

    def draw_fruit(self):
        x_fruit = int(self.pos.x * cell_size)
        y_fruit = int(self.pos.y * cell_size)
        fruit_rect = pygame.Rect(x_fruit, y_fruit, cell_size, cell_size)
        screen.blit(apple, fruit_rect)

    def randomize(self):
        self.x = random.randint(0, cell_number - 1)
        self.y = random.randint(0, cell_number - 1)
        self.pos = Vector2(self.x, self.y)


class SNAKE:
    def __init__(self):
        self.body = [Vector2(5, 10), Vector2(4, 10), Vector2(3, 10)]
        self.direction = Vector2(1, 0)
        self.new_block = False

        self.snake_design()
        self.crunch_sound = pygame.mixer.Sound('Sound/crunch.wav')

    def snake_design(self):
        self.head_up = pygame.image.load('Graphics/head_up.png').convert_alpha()
        self.head_down = pygame.image.load('Graphics/head_down.png').convert_alpha()
        self.head_right = pygame.image.load('Graphics/head_right.png').convert_alpha()
        self.head_left = pygame.image.load('Graphics/head_left.png').convert_alpha()

        self.tail_up = pygame.image.load('Graphics/tail_up.png').convert_alpha()
        self.tail_down = pygame.image.load('Graphics/tail_down.png').convert_alpha()
        self.tail_right = pygame.image.load('Graphics/tail_right.png').convert_alpha()
        self.tail_left = pygame.image.load('Graphics/tail_left.png').convert_alpha()

        self.body_vertical = pygame.image.load('Graphics/body_vertical.png').convert_alpha()
        self.body_horizontal = pygame.image.load('Graphics/body_horizontal.png').convert_alpha()

        self.b_up_right = pygame.image.load('Graphics/b_up_right.png').convert_alpha()
        self.b_up_left = pygame.image.load('Graphics/b_up_left.png').convert_alpha()
        self.b_right_down = pygame.image.load('Graphics/b_right_down.png').convert_alpha()
        self.b_left_down = pygame.image.load('Graphics/b_left_down.png').convert_alpha()

    def draw_snake(self):
        self.update_head_graphics()
        self.update_tail_graphics()

        for index, block in enumerate(self.body):
            x_snake = int(block.x * cell_size)
            y_snake = int(block.y * cell_size)
            block_rect = pygame.Rect(x_snake, y_snake, cell_size, cell_size)

            if index == 0:
                screen.blit(self.head, block_rect)
            elif index == len(self.body) - 1:
                screen.blit(self.tail, block_rect)
            else:
                previous_block = self.body[index + 1] - block
                next_block = self.body[index - 1] - block
                if previous_block.x == next_block.x:
                    screen.blit(self.body_vertical, block_rect)
                elif previous_block.y == next_block.y:
                    screen.blit(self.body_horizontal, block_rect)
                else:
                    if previous_block.x == 1 and next_block.y == -1 or previous_block.y == -1 and next_block.x == 1:
                        screen.blit(self.b_up_right, block_rect)
                    elif previous_block.x == -1 and next_block.y == -1 or previous_block.y == -1 and next_block.x == -1:
                        screen.blit(self.b_up_left, block_rect)
                    elif previous_block.x == 1 and next_block.y == 1 or previous_block.y == 1 and next_block.x == 1:
                        screen.blit(self.b_right_down, block_rect)
                    elif previous_block.x == -1 and next_block.y == 1 or previous_block.y == 1 and next_block.x == -1:
                        screen.blit(self.b_left_down, block_rect)

    def update_head_graphics(self):
        head_relation = self.body[1] - self.body[0]
        if head_relation == Vector2(0, 1):
            self.head = self.head_up
        elif head_relation == Vector2(0, -1):
            self.head = self.head_down
        elif head_relation == Vector2(-1, 0):
            self.head = self.head_right
        elif head_relation == Vector2(1, 0):
            self.head = self.head_left

    def update_tail_graphics(self):
        tail_relation = self.body[-2] - self.body[-1]
        if tail_relation == Vector2(0, -1):
            self.tail = self.tail_up
        elif tail_relation == Vector2(0, 1):
            self.tail = self.tail_down
        elif tail_relation == Vector2(1, 0):
            self.tail = self.tail_right
        elif tail_relation == Vector2(-1, 0):
            self.tail = self.tail_left

    def move_snake(self):
        if self.new_block == True:
            body_copy = self.body[:]
            body_copy.insert(0, body_copy[0] + self.direction)
            self.body = body_copy[:]
            self.new_block = False
        else:
            body_copy = self.body[:-1]
            body_copy.insert(0, body_copy[0] + self.direction)
            self.body = body_copy[:]

    def add_block(self):
        self.new_block = True

    def play_crunch_sound(self):
        self.crunch_sound.play()

    def reset(self):
        self.body = [Vector2(5, 10), Vector2(4, 10), Vector2(3, 10)]
        self.direction = Vector2(0, 0)


class MAIN:
    def __init__(self):
        self.fruit = FRUIT()
        self.snake = SNAKE()
        self.game_over = False
        while self.fruit.pos in self.snake.body:
            self.fruit.randomize()

    def update(self):
        self.snake.move_snake()
        self.check_collision()
        self.check_fail()

    def draw_elements(self):
        self.draw_grass()
        self.fruit.draw_fruit()
        self.snake.draw_snake()
        self.draw_score()

    def check_collision(self):
        if self.fruit.pos == self.snake.body[0]:
            self.fruit.randomize()
            self.snake.add_block()
            self.snake.play_crunch_sound()

    def check_fail(self):
        if not 0 <= self.snake.body[0].x < cell_number or not 0 <= self.snake.body[0].y < cell_number:
            print("Game over: Snake hit the wall.")
            self.game_over = True
        elif self.snake.direction != Vector2(0, 0):
            for block in self.snake.body[1:]:
                if block == self.snake.body[0]:
                    print("Game over: Snake hit itself.")
                    self.game_over = True

    def draw_grass(self):
        grass_color = (167, 209, 61)
        for row in range(cell_number):
            for col in range(cell_number):
                grass_rect = pygame.Rect(col * cell_size, row * cell_size, cell_size, cell_size)
                if (row + col) % 2 == 0:
                    pygame.draw.rect(screen, grass_color, grass_rect)

    def draw_score(self):
        score_text = str(len(self.snake.body) - 3)
        score_surface = game_font.render(score_text, True, (56, 74, 12))
        score_x = int(cell_size * cell_number - 40)
        score_y = int(cell_size * cell_number - 40)
        score_rect = score_surface.get_rect(center=(score_x, score_y))
        apple_rect = apple.get_rect(midright=(score_rect.left, score_rect.centery))
        bg_score_rect = pygame.Rect(apple_rect.left, apple_rect.top, apple_rect.width +
                                    score_rect.width + 4, apple_rect.height + 4)

        pygame.draw.rect(screen, (167, 209, 61), bg_score_rect)
        screen.blit(score_surface, score_rect)
        screen.blit(apple, apple_rect)
        pygame.draw.rect(screen, (56, 74, 12), bg_score_rect, 2)


def save_high_score(high_score):
    with open("high_score.txt", "w") as f:
        f.write(str(high_score))


def load_high_score():
    try:
        with open("high_score.txt", "r") as f:
            return int(f.read())
    except FileNotFoundError:
        return 0


high_score = load_high_score()

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
cell_size = 40
cell_number = 20
screen = pygame.display.set_mode((cell_number * cell_size, cell_number * cell_size))
clock = pygame.time.Clock()

apple = pygame.image.load('Graphics/apple.png').convert_alpha()
apple = pygame.transform.scale(apple, (cell_size, cell_size))

SCREEN_UPDATE = pygame.USEREVENT
pygame.time.set_timer(SCREEN_UPDATE, 150)

main_game = MAIN()

screen_width = cell_number * cell_size
screen_height = cell_number * cell_size

game_font = pygame.font.Font(None, 30)
main_font = pygame.font.Font(None, 50)


def draw_death_screen(score, high_score):
    screen.fill((50, 50, 50))

    game_over_surface = main_font.render('Game Over', True, (255, 255, 255))
    score_surface = game_font.render(f'Your Score: {score}', True, (255, 255, 255))
    high_score_surface = game_font.render(f'High Score: {high_score}', True, (255, 255, 255))
    play_again_surface = game_font.render('Play Again', True, (255, 255, 255))

    game_over_rect = game_over_surface.get_rect(center=(screen_width / 2, screen_height / 4))
    score_rect = score_surface.get_rect(center=(screen_width / 2, screen_height / 3))
    high_score_rect = high_score_surface.get_rect(center=(screen_width / 2, screen_height / 2))
    play_again_rect = play_again_surface.get_rect(center=(screen_width / 2, screen_height * 3/4))

    play_again_rect.inflate_ip(40, 20)

    play_again_text_x = play_again_rect.x + (play_again_rect.width - play_again_surface.get_width()) // 2
    play_again_text_y = play_again_rect.y + (play_again_rect.height - play_again_surface.get_height()) // 2

    screen.blit(game_over_surface, game_over_rect)
    screen.blit(score_surface, score_rect)
    screen.blit(high_score_surface, high_score_rect)
    screen.blit(play_again_surface, (play_again_text_x, play_again_text_y))

    pygame.draw.rect(screen, (255, 255, 255), play_again_rect, 2)

    return play_again_rect


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if main_game.game_over:
            play_again_button = draw_death_screen(len(main_game.snake.body) - 3, high_score)
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                if play_again_button.collidepoint(mouse_pos):
                    current_score = len(main_game.snake.body) - 3
                    if current_score > high_score:
                        high_score = current_score
                        save_high_score(high_score)
                    main_game = MAIN()
        else:
            if event.type == SCREEN_UPDATE:
                main_game.update()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    if main_game.snake.direction.y != 1:
                        main_game.snake.direction = Vector2(0, -1)
                if event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    if main_game.snake.direction.y != -1:
                        main_game.snake.direction = Vector2(0, 1)
                if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    if main_game.snake.direction.x != -1:
                        main_game.snake.direction = Vector2(1, 0)
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    if main_game.snake.direction.x != 1:
                        main_game.snake.direction = Vector2(-1, 0)

    if not main_game.game_over:
        screen.fill((175, 220, 75))
        main_game.draw_elements()
    else:
        draw_death_screen(len(main_game.snake.body) - 3, high_score)

    pygame.display.update()
    clock.tick(60)
