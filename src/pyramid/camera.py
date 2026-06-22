import pygame as _pygame

__all__ = [
    "Camera2D",
]


class Camera2D:
    """2D camera helper for queued rendering, culling, and parallax effects."""

    def __init__(
        self,
        target: _pygame.Surface,
        cache_precision: int = 2,
        smooth: bool = False,
    ):
        """Initializes the camera with a render target and optional scaling cache settings (cache is used for parallax)."""
        self.target = target
        self._half_width = target.get_width() / 2
        self._half_height = target.get_height() / 2
        self._screen_rect = target.get_rect()
        self.render_queue = []

        self._scale_cache: dict[tuple[_pygame.Surface, float], _pygame.Surface] = {}
        self.cache_precision = cache_precision
        self.smooth = smooth

    def clear_cache(self):
        """Manually clear the cache if changing levels or scenes to free memory."""
        self._scale_cache.clear()

    def clear_queue(self):
        """Clears the drawing queue."""
        self.render_queue.clear()

    def render(self):
        """Sorts the queue by depth (back-to-front), draws everything and clears the queue."""
        self.render_queue.sort(key=lambda item: item[0], reverse=True)

        for item in self.render_queue:
            _, (source, dest) = item
            self.target.blit(source, dest)

        self.clear_queue()

    def simple(
        self,
        camera_pos: _pygame.Vector2 | tuple[float, float],
        source: _pygame.Surface,
        position: _pygame.Vector2 | tuple[float, float],
        distance: float = 0,
        max_distance: float = float("inf"),
    ):
        """Queues a surface for rendering using a simple camera offset and depth sorting.

        Depth sorting is only relevant here if mixed with other queueing methods."""
        if distance > max_distance:
            return

        dest_pos = (
            _pygame.Vector2(position)
            - _pygame.Vector2(camera_pos)
            + _pygame.Vector2(self._half_width, self._half_height)
        )

        dest_rect = source.get_rect(topleft=(int(dest_pos.x), int(dest_pos.y)))
        if not self._screen_rect.colliderect(dest_rect):
            return

        self.render_queue.append((distance, (source, dest_rect)))

    def parallax(
        self,
        camera_pos: _pygame.Vector3 | tuple[float, float, float],
        source: _pygame.Surface,
        position: _pygame.Vector3 | tuple[float, float, float],
        zmult: float = 1,
        proximity_limit: float = 0.01,
        max_distance: float = float("inf"),
    ):
        """Queues a surface with perspective scaling based on its z-distance.

        `zmult` acts similarly to a FOV."""
        rel_pos = _pygame.Vector3(position) - _pygame.Vector3(camera_pos)

        if rel_pos.z <= proximity_limit or rel_pos.z > max_distance:
            return

        scale = zmult / rel_pos.z

        screen_x = self._half_width + (rel_pos.x * scale)
        screen_y = self._half_height + (rel_pos.y * scale)

        q_scale = round(scale, self.cache_precision)

        if q_scale <= 0:
            return

        cache_key = (source, q_scale)
        scaled_source = self._scale_cache.get(cache_key)

        if scaled_source is None:
            try:
                scale = (
                    _pygame.transform.smoothscale_by
                    if self.smooth
                    else _pygame.transform.scale_by
                )
                scaled_source = scale(source, q_scale)
                self._scale_cache[cache_key] = scaled_source
            except _pygame.error:
                return

        dest_rect = scaled_source.get_rect()
        dest_rect.center = (int(screen_x), int(screen_y))

        if not self._screen_rect.colliderect(dest_rect):
            return

        self.render_queue.append((rel_pos.z, (scaled_source, dest_rect)))

    def halfparallax(
        self,
        camera_pos: _pygame.Vector3 | tuple[float, float, float],
        source: _pygame.Surface,
        position: _pygame.Vector3 | tuple[float, float, float],
        zmult: float = 1,
        proximity_limit: float = 0.01,
        max_distance: float = float("inf"),
    ):
        """Queues a surface with parallax projection without scaling."""
        rel_pos = _pygame.Vector3(position) - _pygame.Vector3(camera_pos)

        if rel_pos.z <= proximity_limit or rel_pos.z > max_distance:
            return

        scale = zmult / rel_pos.z

        screen_x = self._half_width + (rel_pos.x * scale)
        screen_y = self._half_height + (rel_pos.y * scale)

        dest_rect = source.get_rect(center=(int(screen_x), int(screen_y)))

        if not self._screen_rect.colliderect(dest_rect):
            return

        self.render_queue.append((rel_pos.z, (source, dest_rect)))
