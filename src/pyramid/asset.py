from pathlib import Path as _Path
import pygame as _pygame
from collections.abc import Callable as _Callable
from typing import Any as _Any, Generic as _Generic, TypeVar as _TypeVar

__all__ = [
    "AssetManager",
    "BoundCache",
]


K = _TypeVar("K")  # key (usually a tuple)
V = _TypeVar("V")  # value (eg asset)
B = _TypeVar("B")  # binder


class BoundCache(_Generic[K, V, B]):
    """A cache that maps loaded values to binders and supports selective unbinding."""

    def __init__(self) -> None:
        """Initializes the internal cache and binder index structures."""
        self._cache: dict[K, V] = {}
        self._key_to_binder: dict[K, set[B]] = {}
        self._binder_to_key: dict[B, set[K]] = {}

    def clear(self) -> None:
        """Resets the cache and all bindings."""
        self._cache.clear()
        self._key_to_binder.clear()
        self._binder_to_key.clear()

    def unbind(self, binder: B) -> None:
        """Removes a binder and deallocates values no longer bound to anything."""
        if binder not in self._binder_to_key:
            return

        bound_keys = self._binder_to_key.pop(binder)

        for key in bound_keys:
            if key not in self._key_to_binder:
                continue

            self._key_to_binder[key].discard(binder)

            if self._key_to_binder[key]:
                continue  # key still has other binders

            del self._key_to_binder[key]
            self._cache.pop(key, None)

    def fetch_or_load(self, key: K, binder: B, load_func: _Callable[[], V]) -> V:
        """Returns a cached value if present, otherwise loads.
        Binds it to the given binder independently of if it is already on cache."""
        if key not in self._cache:
            self._cache[key] = load_func()

        if key not in self._key_to_binder:
            self._key_to_binder[key] = set()
        self._key_to_binder[key].add(binder)

        if binder not in self._binder_to_key:
            self._binder_to_key[binder] = set()
        self._binder_to_key[binder].add(key)

        return self._cache[key]


class AssetManager:
    """Provides singleton-like (shared cache) access to shared asset loading and binder-aware caching."""

    # justification for binder logic instead of weakref:
    #
    # weakref would be simpler to implement and use, but would make cacheing impossible
    # in some scenarios that, at first glance, don't have any problem.
    # for example, a simple and direct "screen.blit(manager.image("hero.png", self), (0,0))"
    # would cause the image to be loaded from disk every single time and never actually cached
    # because no weak reference to it was created
    #
    # with a binder logic, unloading will only occur when the developer let it happens,
    # while allowing much more control over a global .clear()

    cache = BoundCache[tuple, _Any, _Any]()

    def __init__(self, binder: _Any):
        """Creates an AssetManager instance associated with a binding owner."""
        self.binder = binder

    def image(
        self,
        path: _Path | str,
        rescale: tuple[int, int] | None = None,
    ) -> _pygame.Surface:
        """Loads an image."""
        path = _Path(path).resolve()
        key = (path, rescale)

        def load() -> _pygame.Surface:
            surf = _pygame.image.load(str(path)).convert_alpha()
            return _pygame.transform.scale(surf, rescale) if rescale else surf

        return self.cache.fetch_or_load(key, self.binder, load)

    def spritesheet(
        self,
        path: _Path | str,
        tile_size: tuple[int, int],
        rescale_tile: tuple[int, int] | None = None,
        rescale_whole: tuple[int, int] | None = None,
    ) -> list[list[_pygame.Surface]]:
        """Loads and slices a spritesheet into a matrix of surfaces."""
        path = _Path(path).resolve()
        key = (path, tile_size, rescale_tile, rescale_whole)

        def load() -> list[list[_pygame.Surface]]:
            surface = _pygame.image.load(str(path)).convert_alpha()
            if rescale_whole:
                surface = _pygame.transform.scale(surface, rescale_whole)

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
                    rect = _pygame.Rect(x, y, tile_w, tile_h)
                    tile = surface.subsurface(rect).copy()

                    if rescale_tile:
                        tile = _pygame.transform.scale(tile, rescale_tile)
                    row.append(tile)
                sprites.append(row)
            return sprites

        return self.cache.fetch_or_load(key, self.binder, load)

    def sound(self, path: _Path | str) -> _pygame.mixer.Sound:
        """Loads a sound."""
        path = _Path(path).resolve()
        key = (path,)
        return self.cache.fetch_or_load(
            key, self.binder, lambda: _pygame.mixer.Sound(str(path))
        )

    def font(self, path: _Path | str, size: int) -> _pygame.font.Font:
        """Loads a font at a specific size."""
        path = _Path(path).resolve()
        key = (path, size)
        return self.cache.fetch_or_load(
            key, self.binder, lambda: _pygame.font.Font(str(path), size)
        )
