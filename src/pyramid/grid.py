from typing import TypeVar, Generic, Generator
import pygame

K = TypeVar("K")


class GridManager(Generic[K]):
    def __init__(
        self,
        cols: int,
        rows: int,
        cell_size: int,
        offset: tuple[int, int] | None = None,
        spacing: int = 0,
    ):
        self.cols = cols
        self.rows = rows
        self.cell_size = cell_size
        self.offset = (0, 0) if offset is None else offset
        self.spacing = spacing

        self._matrix: list[list[K | None]] = [
            [None for _ in range(cols)] for _ in range(rows)
        ]
        self._occupied_cells: dict[tuple[int, int], K] = {}

    def grid_to_pixel(self, col: int, row: int) -> tuple[int, int]:
        """Converts grid coordinates (col, row) to screen pixel coordinates (x, y)."""
        x = self.offset[0] + col * (self.cell_size + self.spacing)
        y = self.offset[1] + row * (self.cell_size + self.spacing)
        return x, y

    def pixel_to_grid(self, coord: tuple[int, int]) -> tuple[int, int] | None:
        """Converts screen pixel coordinates (x, y) to grid coordinates (col, row)."""
        adj_x = coord[0] - self.offset[0]
        adj_y = coord[1] - self.offset[1]

        slot_width = self.cell_size + self.spacing

        if self.spacing > 0:
            if (adj_x % slot_width > self.cell_size) or (
                adj_y % slot_width > self.cell_size
            ):
                return None

        col = adj_x // slot_width
        row = adj_y // slot_width

        if 0 <= col < self.cols and 0 <= row < self.rows:
            return col, row
        return None

    def get_cell_rect(self, col: int, row: int) -> pygame.Rect:
        """Returns a Pygame Rect for the specified cell."""
        x, y = self.grid_to_pixel(col, row)
        return pygame.Rect(x, y, self.cell_size, self.cell_size)

    def get_by_grid(self, col: int, row: int) -> K | None:
        """Gets the item at the specified grid column and row."""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self._matrix[row][col]
        return None

    def set_by_grid(self, col: int, row: int, value: K | None) -> bool:
        """Sets or clears an item at (col, row) and updates tracking."""
        if not (0 <= col < self.cols and 0 <= row < self.rows):
            return False

        self._matrix[row][col] = value
        coord = (col, row)

        if value is not None:
            self._occupied_cells[coord] = value
        else:
            self._occupied_cells.pop(coord, None)
        return True

    def get_by_pixel(self, pixel_x: int, pixel_y: int) -> K | None:
        """Gets the item located at the absolute screen pixel coordinates."""
        grid_pos = self.pixel_to_grid((pixel_x, pixel_y))
        return self.get_by_grid(*grid_pos) if grid_pos else None

    def set_by_pixel(self, pixel_x: int, pixel_y: int, value: K | None) -> bool:
        """Sets an item at the absolute screen pixel position."""
        grid_pos = self.pixel_to_grid((pixel_x, pixel_y))
        return self.set_by_grid(grid_pos[0], grid_pos[1], value) if grid_pos else False

    def clear(self):
        """Clears the grid completely."""
        self._matrix = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self._occupied_cells.clear()

    def items(self) -> Generator[tuple[tuple[int, int], K], None, None]:
        """Yields ((col, row), value) for all active (not None) elements."""
        for coord, val in self._occupied_cells.items():
            yield coord, val
