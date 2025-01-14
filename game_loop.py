import pygame

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

def run_game():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("StarCell Proof of Concept")

    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Clear screen with a background color
        screen.fill((50, 50, 50))  # Dark gray

        # Update the screen
        pygame.display.flip()
        clock.tick(60)  # Limit to 60 FPS
