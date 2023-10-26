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
        pygame.draw.rect(screen, (126, 166, 114), fruit_rect)
        
    def randomize(self):
        self.x = random.randint(0, cell_number - 1)
        self.y = random.randint(0, cell_number - 1)
        self.pos = Vector2(self.x, self.y)


class SNAKE:
    def __init__(self):
        self.body = [Vector2(5, 10), Vector2(6, 10), Vector2(7, 10)]
        self.direction = Vector2(1, 0)
        self.new_block = False

    def draw_snake(self):
        for block in self.body:
            x_snake = int(block.x * cell_size)
            y_snake = int(block.y * cell_size)
            block_rect = pygame.Rect(x_snake, y_snake, cell_size, cell_size)
            pygame.draw.rect(screen, (183, 111, 122), block_rect)

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


class MAIN:
    def __init__(self):
        self.fruit = FRUIT()
        self.snake = SNAKE()

    def update(self):
        self.snake.move_snake()
        self.check_collision()

    def draw_elements(self):
        self.fruit.draw_fruit()
        self.snake.draw_snake()

    def check_collision(self):
        if self.fruit.pos == self.snake.body[0]:
            self.fruit.randomize()
            self.snake.add_block()


pygame.init()
cell_size = 40
cell_number = 20
screen = pygame.display.set_mode((cell_number * cell_size, cell_number * cell_size))
clock = pygame.time.Clock()

SCREEN_UPDATE = pygame.USEREVENT
pygame.time.set_timer(SCREEN_UPDATE, 150)

main_game = MAIN()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == SCREEN_UPDATE:
            main_game.update()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP or event.key == pygame.K_w:
                main_game.snake.direction = Vector2(0, -1)
            if event.key == pygame.K_DOWN or event.key == pygame.K_s:
                main_game.snake.direction = Vector2(0, 1)
            if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                main_game.snake.direction = Vector2(1, 0)
            if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                main_game.snake.direction = Vector2(-1, 0)

    screen.fill((175, 220, 75))
    main_game.draw_elements()
    pygame.display.update()
    clock.tick(60)
