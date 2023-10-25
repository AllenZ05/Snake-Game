import pygame
import sys

pygame.init()
screen = pygame.display.set_mode((500, 500)) #sets screen size
clock = pygame.time.Clock() #create clock object to limit fps

while True:
    # Draw our elements
    for event in pygame.event.get():
        if event.type == pygame.QUIT: #user clicks x to close window
            pygame.quit()
            sys.quit()
    pygame.display.update()
    clock.tick(60) #limits fps to 60
