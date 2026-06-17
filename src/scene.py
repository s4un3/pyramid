from abc import ABC
import pygame

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scene_handler import SceneHandler


class Scene(ABC):
    # class values to act as defaults
    bypass_canvas = False
    blit_pos = (0, 0)

    # standard size for canvases
    STD_SIZE = (1920, 1080)

    def __init__(
        self,
        canvas: pygame.Surface | None = None,
        blit_pos: tuple[int, int] = (0, 0),
        bypass_canvas: bool = False,
    ):
        """
        Initializes the base Scene.

        `canvas` is the internal surface this scene draws onto. You can use a fixed size surface and the handler will rescale and center it for you

        Set `bypass_canvas` to True to skip the SceneHandler blitting this scene's canvas to the main window.
        Useful if the scene doesn't draw anything, or modifies the handler's canvas or screen directly
        """

        self.canvas: pygame.Surface
        if not (canvas is None):
            self.canvas = canvas

        self.bypass_canvas: bool = bypass_canvas
        self.blit_pos: tuple[int, int] = blit_pos

        self.handler: SceneHandler

    def enter(self) -> None:
        "Called when the scene is first pushed onto the handler's stack"
        pass

    def exit(self) -> None:
        "Called when the scene is permanently popped off the handler's stack"
        pass

    def lose_top(self) -> None:
        "Called when another scene is pushed on top of this one"
        pass

    def regain_top(self) -> None:
        "Called when all the scenes above this one are popped, making this scene active again"
        pass

    def update(
        self,
        dt: int,
        on_top: bool,
    ) -> bool | None:
        "Processes game logic and physics for the scene"
        pass

    def draw(self, on_top: bool, alpha: float) -> None:
        """Renders the scene to its own `self.canvas`

        `alpha` is the proportion of physics frames passed since the last update. Useful for interpolation
        """
        pass

    def handle_events(
        self, events: list[pygame.event.Event], on_top: bool, consumed: bool
    ) -> bool | None:
        """Handle events, like key and mouse presses (not continuous)

        Will mark events as consumed for scenes below it unless True is returned"""
        pass

    def generate_canvas(self):
        self.canvas = pygame.Surface(Scene.STD_SIZE)
