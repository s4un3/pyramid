import pygame
import sys

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from scene import Scene


class SceneHandler:
    def __init__(
        self,
        canvas: pygame.Surface,
        max_frame_time_ms: int,
        phys_dt_ms: int,
        graphic_framerate: float,
    ):
        self._scene_stack: list[Scene] = []
        self._accumulator: int = 0
        self._clock = pygame.time.Clock()
        self._screen = pygame.display.get_surface()
        self._events = []
        self.dt: int = 0

        self.canvas = canvas
        self.max_frame_time_ms = max_frame_time_ms
        self.phys_dt_ms: int = phys_dt_ms
        self.graphic_framerate: float = graphic_framerate

        self.post_processing: list[Callable[[], None]] = []

    @property
    def top(self) -> None | Scene:
        if not self._scene_stack:
            return None
        return self._scene_stack[0]

    def _init_scene(self, scene: Scene):
        scene.handler = self
        if not hasattr(scene, "canvas") or not scene.canvas:
            scene.canvas = scene.create_canvas()
        scene.enter()

    def push(self, scene: Scene):
        if self.top:
            self.top.lose_top()
        self._scene_stack.insert(0, scene)
        self._init_scene(scene)

    def pop(self):
        if self.top:

            self.top.exit()
            self._scene_stack.pop(0)

            if self.top:
                self.top.regain_top()

    def pop_index(self, i: int):
        if not self.top:
            return
        if self.top is self._scene_stack[i]:
            self.pop()
            return
        scene = self._scene_stack[i]
        scene.exit()
        self._scene_stack.remove(scene)

    def insert_index(self, i: int, scene: Scene):
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
        while self.top:
            self.pop()

    @staticmethod
    def _blit_center_fit(source_surf: pygame.Surface, target_surf: pygame.Surface):
        src_w, src_h = source_surf.get_size()
        tgt_w, tgt_h = target_surf.get_size()

        scale_factor = min(tgt_w / src_w, tgt_h / src_h)
        new_w = int(src_w * scale_factor)
        new_h = int(src_h * scale_factor)

        scaled_surf = pygame.transform.smoothscale(source_surf, (new_w, new_h))

        tgt_rect = target_surf.get_rect()
        scaled_rect = scaled_surf.get_rect(center=tgt_rect.center)

        target_surf.blit(scaled_surf, scaled_rect.topleft)

    def _step(self, dt, _phys_dt: int):
        self._accumulator += min(self.max_frame_time_ms, dt)

        events = pygame.event.get()

        is_resizing = False

        for event in events:
            if event.type == pygame.QUIT:
                self.end()
            elif event.type in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED):
                is_resizing = True
                self._screen = pygame.display.get_surface()

        self.canvas.fill(0)

        consumed = False
        for scene in self._scene_stack:
            if scene.handle_events(events, on_top=scene is self.top, consumed=consumed):
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

    def run(self):
        try:
            while True:
                self.dt = self._clock.tick(self.graphic_framerate)
                self._step(self.dt, self.phys_dt_ms)
                self._screen.fill(0)
                self._blit_center_fit(self.canvas, self._screen)
                pygame.display.flip()
        except KeyboardInterrupt as e:
            self.end()

    def end(self):
        self.clear()
        sys.exit()
