from pathlib import Path
from typing import Any, Self, Callable
import pygame


class AssetManager:
    _instance: Self | None = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self) -> None:
        self._cache: dict[tuple, Any] = {}

    def _get_cached_or_load(self, key: tuple, load_func: Callable) -> Any:
        if key in self._cache:
            return self._cache[key]

        asset = load_func()
        self._cache[key] = asset
        return asset

    def image(
        self, path: Path | str, rescale: tuple[int, int] | None = None
    ) -> pygame.Surface:
        "Loads a single image."
        path = Path(path).resolve()
        key = (path, rescale)

        def load():
            surf = pygame.image.load(str(path)).convert_alpha()
            return pygame.transform.scale(surf, rescale) if rescale else surf

        return self._get_cached_or_load(key, load)

    def spritesheet(
        self,
        path: Path | str,
        tile_size: tuple[int, int],
        rescale_tile: tuple[int, int] | None = None,
        rescale_whole: tuple[int, int] | None = None,
    ) -> list[list[pygame.Surface]]:
        """Slices a spritesheet into a matrix of surfaces."""
        path = Path(path).resolve()
        key = (path, tile_size, rescale_tile, rescale_whole)

        def load():
            surface = pygame.image.load(str(path)).convert_alpha()
            if rescale_whole:
                surface = pygame.transform.scale(surface, rescale_whole)

            tile_w, tile_h = tile_size
            surf_w, surf_h = surface.get_size()

            cols = surf_w // tile_w
            rows = surf_h // tile_h

            sprites = []
            for r in range(rows):
                row = []
                for c in range(cols):
                    x = c * tile_w
                    y = r * tile_h

                    rect = pygame.Rect(x, y, tile_w, tile_h)
                    tile = surface.subsurface(rect).copy()

                    if rescale_tile:
                        tile = pygame.transform.scale(tile, rescale_tile)

                    row.append(tile)
                sprites.append(row)

            return sprites

        return self._get_cached_or_load(key, load)

    def sound(self, path: Path | str) -> pygame.mixer.Sound:
        """Loads a sound effect or music track."""
        path = Path(path).resolve()
        key = (path,)
        return self._get_cached_or_load(key, lambda: pygame.mixer.Sound(str(path)))

    def font(self, path: Path | str, size: int) -> pygame.font.Font:
        """Loads a font at a specific size."""
        path = Path(path).resolve()
        key = (path, size)
        return self._get_cached_or_load(key, lambda: pygame.font.Font(str(path), size))
