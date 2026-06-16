import pygame
from src.scene_handler import SceneHandler
from src.scene import Scene
import random


class Test_Scene(Scene):
    def handle_events(self, events: list[pygame.event.Event], on_top: bool) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self.canvas.fill(
                    (
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255),
                    )
                )


pygame.init()
screen = pygame.display.set_mode((800, 600), pygame.RESIZABLE)

h = SceneHandler(pygame.Surface((1920, 1080)), 1000, int(1000 / 120), 60)
h.push(Test_Scene())

h.run()
