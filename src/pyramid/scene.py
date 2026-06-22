from abc import ABC as _ABC
from typing import Type as _Type
import pygame as _pygame
from collections.abc import Callable as _Callable

__all__ = [
    "Context",
    "Scene",
    "SceneHaltSignal",
    "SceneManager",
]


class SceneHaltSignal(Exception):
    """Raised by a Scene to signal a halt of the game/simulation"""

    pass


class Context(_ABC):
    """Abstract class for data transfer between scenes."""

    pass


class SceneManager:
    """Manages a stack of scenes, fixed-step updates, rendering, and input routing."""

    def __init__(
        self,
        max_frame_time_ms: int,
        phys_dt_ms: int,
        graphic_framerate: float,
        canvas: _pygame.Surface | None = None,
    ):
        """Initializes scene timing and canvas state for the manager."""
        self._scene_stack: list[Scene] = []
        self._accumulator: int = 0
        self._clock = _pygame.time.Clock()
        self._screen = _pygame.display.get_surface()
        if self._screen is None:
            raise RuntimeError(
                "Display was not initialized. Call 'pygame.display.set_mode' before creating a SceneManager."
            )
        self._events = []
        self.dt: int = 0

        self.canvas = _pygame.Surface(Scene.STD_SIZE) if canvas is None else canvas
        self.max_frame_time_ms = max_frame_time_ms
        self.phys_dt_ms: int = phys_dt_ms
        self.graphic_framerate: float = graphic_framerate

        self.post_processing: list[_Callable[[], None]] = []

        self.ctx: dict[_Type[Context], Context] = {}

    @property
    def top(self) -> None | Scene:
        if not self._scene_stack:
            return None
        return self._scene_stack[0]

    def _init_scene(self, scene: Scene):
        """Prepares a scene before it becomes active in the scene stack."""
        scene.manager = self
        if not hasattr(scene, "canvas") or not scene.canvas:
            scene.canvas = scene.create_canvas()
        scene.enter()

    def push(self, scene: Scene):
        """Pushes a new scene onto the stack, pausing the current top scene."""
        if self.top:
            self.top.lose_top()
        self._scene_stack.insert(0, scene)
        self._init_scene(scene)

    def pop(self):
        """Removes the current top scene and restores the next scene below it."""
        if self.top is None:
            return

        self.top.exit()
        self._scene_stack.pop(0)

        if self.top:
            self.top.regain_top()

    def pop_index(self, i: int):
        """Removes a scene by index from the stack, handling top removal if needed."""
        if not self.top:
            return
        if self.top is self._scene_stack[i]:
            self.pop()
            return
        scene = self._scene_stack[i]
        scene.exit()
        self._scene_stack.remove(scene)

    def insert_index(self, i: int, scene: Scene):
        """Inserts a scene at the specified index in the stack."""
        if i == len(self._scene_stack):
            self.push(scene)
            return
        if i > len(self._scene_stack):
            raise IndexError(
                "Index for insertion is too big (greater than current stack length)"
            )
        self._scene_stack.insert(i, scene)
        self._init_scene(scene)

    def clear(self):
        """Clears the entire scene stack, exiting each scene in order."""
        while self.top:
            self.pop()

    @staticmethod
    def _blit_center_fit(source_surf: _pygame.Surface, target_surf: _pygame.Surface):
        """Blits the source surface centered and scaled to fit inside the target surface."""
        src_w, src_h = source_surf.get_size()
        tgt_w, tgt_h = target_surf.get_size()

        scale_factor = min(tgt_w / src_w, tgt_h / src_h)
        new_w = int(src_w * scale_factor)
        new_h = int(src_h * scale_factor)

        scaled_surf = _pygame.transform.smoothscale(source_surf, (new_w, new_h))

        tgt_rect = target_surf.get_rect()
        scaled_rect = scaled_surf.get_rect(center=tgt_rect.center)

        target_surf.blit(scaled_surf, scaled_rect.topleft)

    def _step(self, dt, _phys_dt: int):
        """Performs one frame's event handling, physics updates, and scene drawing."""
        self._accumulator += min(self.max_frame_time_ms, dt)

        events = _pygame.event.get()

        is_resizing = False

        for event in events:
            if event.type == _pygame.QUIT:
                self.end("Window closed by the 'quit' button.")
            elif event.type in (_pygame.VIDEORESIZE, _pygame.WINDOWRESIZED):
                is_resizing = True
                self._screen = _pygame.display.get_surface()

        self.canvas.fill(0)

        consumed = False
        for scene in self._scene_stack:
            mouse_pos = self.screen_to_scene(_pygame.mouse.get_pos(), scene)

            if scene.handle_events(
                events,
                (int(mouse_pos[0]), int(mouse_pos[1])),
                on_top=scene is self.top,
                consumed=consumed,
            ):
                # returned True: mark events as consumed
                consumed = True

        while self._accumulator >= _phys_dt:
            self._accumulator -= _phys_dt

            for scene in self._scene_stack:
                scene.update(_phys_dt, on_top=scene is self.top)

        if not is_resizing:
            for scene in reversed(self._scene_stack):
                scene.draw(on_top=scene is self.top, alpha=self._accumulator / _phys_dt)
                if not scene.bypass_canvas:
                    self.canvas.blit(scene.canvas, scene.blit_pos)

        for func in self.post_processing:
            func()

    def run(self, raise_on_halt: bool = True) -> SceneHaltSignal:
        """Starts the main loop and manages scene execution until halted."""
        try:
            while True:
                if not self._scene_stack:
                    self.end("Empty scene stack.")
                self.dt = self._clock.tick(self.graphic_framerate)
                self._step(self.dt, self.phys_dt_ms)
                self._screen.fill(0)
                self._blit_center_fit(self.canvas, self._screen)
                _pygame.display.flip()
        except (KeyboardInterrupt, SceneHaltSignal) as e:
            self.clear()
            if isinstance(e, KeyboardInterrupt):
                raise
            if raise_on_halt:
                raise
            return e  # if recovery of the message is needed

    def end(self, message: str):
        """Terminates the scene loop by raising a halt signal with a message."""
        raise SceneHaltSignal(message)

    def _get_canvas_scale_and_offset(self) -> tuple[float, tuple[int, int]]:
        """Calculates scaling and letterbox offset between the manager canvas and screen."""
        src_w, src_h = self.canvas.get_size()
        tgt_w, tgt_h = self._screen.get_size()

        scale_factor = min(tgt_w / src_w, tgt_h / src_h)

        new_w = int(src_w * scale_factor)
        new_h = int(src_h * scale_factor)

        offset_x = (tgt_w - new_w) // 2
        offset_y = (tgt_h - new_h) // 2

        return scale_factor, (offset_x, offset_y)

    def screen_to_scene(
        self, screen_pos: tuple[int, int], scene: Scene
    ) -> tuple[float, float]:
        """Translates a coordinate from the window/screen space
        to the local coordinate system of a specific scene."""
        scale, (off_x, off_y) = self._get_canvas_scale_and_offset()

        canvas_x = (screen_pos[0] - off_x) / scale
        canvas_y = (screen_pos[1] - off_y) / scale

        scene_x = canvas_x - scene.blit_pos[0]
        scene_y = canvas_y - scene.blit_pos[1]

        return (scene_x, scene_y)

    def scene_to_screen(
        self, scene_pos: tuple[int, int] | tuple[float, float], scene: Scene
    ) -> tuple[int, int]:
        """Translates a local coordinate from a specific scene to
        global screen/window coordinates."""
        scale, (off_x, off_y) = self._get_canvas_scale_and_offset()

        canvas_x = scene_pos[0] + scene.blit_pos[0]
        canvas_y = scene_pos[1] + scene.blit_pos[1]

        screen_x = int(canvas_x * scale + off_x)
        screen_y = int(canvas_y * scale + off_y)

        return (screen_x, screen_y)


class Scene(_ABC):
    """Abstract base class for game scenes, providing lifecycle hooks and drawing behavior."""

    # even if it is an _ABC, all current methods can be safelly left unimplemented (use default)

    # class values to act as defaults
    bypass_canvas = False
    blit_pos = (0, 0)

    # standard size for canvases
    STD_SIZE = (1920, 1080)

    def __init__(
        self,
        canvas: _pygame.Surface | None = None,
        blit_pos: tuple[int, int] = (0, 0),
        bypass_canvas: bool = False,
    ):
        """Initializes the base scene with optional canvas, blit position, and bypass behavior.

        `canvas` is the internal surface this scene draws onto. If left as None, a new surface of size STD_SIZE will be created.

        Set `bypass_canvas` to True to skip the SceneManager blitting this scene's canvas to the main window.
        Useful if the scene doesn't draw anything, or modifies the manager's canvas or screen directly
        """

        self.canvas: _pygame.Surface
        if canvas is not None:
            self.canvas = canvas
        else:
            self.canvas = self.create_canvas()

        self.bypass_canvas: bool = bypass_canvas
        self.blit_pos: tuple[int, int] = blit_pos

        self.manager: SceneManager

    def enter(self) -> None:
        """Called once when the scene is activated by the manager."""
        pass

    def exit(self) -> None:
        """Called when the scene is removed from the manager and will no longer run."""
        pass

    def lose_top(self) -> None:
        """Called when this scene loses top-stack focus because another scene is pushed above it."""
        pass

    def regain_top(self) -> None:
        """Called when this scene regains top-stack focus after scenes above it are popped."""
        pass

    def update(
        self,
        dt: int,
        on_top: bool,
    ) -> bool | None:
        """Updates the scene's game logic with a fixed time step."""
        pass

    def draw(self, on_top: bool, alpha: float) -> None:
        """Renders the scene contents to its own canvas, optionally using interpolation (alpha)."""
        pass

    def handle_events(
        self,
        events: list[_pygame.event.Event],
        mouse_pos: tuple[int, int],
        on_top: bool,
        consumed: bool,
    ) -> bool:
        """Handle events, like key and mouse presses (not continuous)

        `mouse_pos` is already in the canvas' coordinate system.

        Will mark events as consumed for scenes below it if True is returned"""
        return False

    def create_canvas(self) -> _pygame.Surface:
        return _pygame.Surface(Scene.STD_SIZE)
