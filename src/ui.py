from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Union, Any
import pygame

pygame.init()

# type aliases to keep signatures clean
ColorRGBA = Tuple[int, int, int, int]
LineItem = Tuple[Union[pygame.Surface, str], int, int, bool]
LineLayout = Tuple[List[LineItem], int, int]
TextSource = Union[str, Callable[[], str]]


@dataclass
class UIStyle:
    """Groups styling configuration to prevent parameter bloat on individual elements."""

    font: pygame.font.Font
    text_color: ColorRGBA = (255, 255, 255, 255)
    bg_color: Optional[ColorRGBA] = (0, 0, 0, 100)
    hover_color: ColorRGBA = (70, 70, 70, 100)
    border_color: Optional[ColorRGBA] = (255, 255, 255, 255)
    border_width: int = 1
    padding: Union[int, Tuple[int, int, int, int]] = 4  # top, right, bottom, left
    align_h: str = "center"
    align_v: str = "center"
    line_spacing: int = 4


class UIElement(ABC):
    """Base framework component tracking dimensions, style settings, and the low-level rendering loop."""

    def __init__(
        self,
        width: Union[int, str],
        height: Union[int, str],
        style: UIStyle,
    ):
        self.requested_width = width
        self.requested_height = height
        self.style = style

        self.width: int = 0 if width == "auto" else int(width)
        self.height: int = 0 if height == "auto" else int(height)

        self.padding: Tuple[int, int, int, int]
        if isinstance(style.padding, int):
            self.padding = (
                style.padding,
                style.padding,
                style.padding,
                style.padding,
            )
        else:
            self.padding = style.padding

        self.absolute_rect = pygame.Rect(0, 0, self.width, self.height)

    def _get_active_text(self, text_source: TextSource) -> str:
        """Helper to resolve either a static string or a dynamic callable into a string."""
        if callable(text_source):
            return str(text_source())
        return str(text_source)

    def calculate_layout(
        self, text: TextSource, inline_surfaces: Dict[str, pygame.Surface]
    ) -> Tuple[List[LineLayout], int, int, int]:
        """Calculates textual layout matrices, line breaks, and bounding constraints."""
        resolved_text = self._get_active_text(text)

        pad_top, pad_right, pad_bottom, pad_left = self.padding
        font = self.style.font
        space_width = font.size(" ")[0]

        max_usable_w = (
            self.width - pad_left - pad_right
            if self.requested_width != "auto"
            else float("inf")
        )

        words = resolved_text.split(" ")
        lines: List[List[LineItem]] = []
        current_line: List[LineItem] = []
        current_width = 0

        for word in words:
            if word in inline_surfaces:
                item_surf = inline_surfaces[word]
                item_w, item_h = item_surf.get_size()
                if current_width + item_w > max_usable_w and current_line:
                    lines.append(current_line)
                    current_line, current_width = [], 0
                current_line.append((item_surf, item_w, item_h, True))
                current_width += item_w + space_width
            else:
                word_w, word_h = font.size(word)
                if current_width + word_w > max_usable_w and current_line:
                    lines.append(current_line)
                    current_line, current_width = [], 0
                current_line.append((word, word_w, word_h, False))
                current_width += word_w + space_width

        if current_line:
            lines.append(current_line)

        line_data: List[LineLayout] = []
        total_text_height = 0
        max_line_width = 0

        for line in lines:
            if not line:
                continue
            max_h = max(item[2] for item in line)
            line_w = sum(item[1] for item in line) + (space_width * (len(line) - 1))
            max_line_width = max(max_line_width, line_w)
            line_data.append((line, line_w, max_h))
            total_text_height += max_h + self.style.line_spacing

        if total_text_height > 0:
            total_text_height -= self.style.line_spacing

        final_w = (
            max_line_width + pad_left + pad_right
            if self.requested_width == "auto"
            else self.width
        )
        final_h = (
            total_text_height + pad_top + pad_bottom
            if self.requested_height == "auto"
            else self.height
        )

        self.width, self.height = final_w, final_h
        self.absolute_rect.size = (final_w, final_h)

        return line_data, total_text_height, final_w, final_h

    def draw_base_layout(
        self,
        text: TextSource,
        inline_surfaces: Dict[str, pygame.Surface],
        bg_override: Optional[ColorRGBA] = None,
    ) -> pygame.Surface:
        """Executes rendering logic into a finalized surface buffer canvas."""
        line_data, total_text_height, w, h = self.calculate_layout(
            text, inline_surfaces
        )

        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        bg = bg_override if bg_override is not None else self.style.bg_color
        if bg:
            surf.fill(bg)

        pad_top, _, _, pad_left = self.padding
        usable_width = max(0, w - pad_left - self.padding[1])
        usable_height = max(0, h - pad_top - self.padding[2])

        match self.style.align_v:
            case "center":
                y_offset = pad_top + (usable_height - total_text_height) // 2
            case "bottom":
                y_offset = pad_top + (usable_height - total_text_height)
            case "top" | _:
                y_offset = pad_top

        for line, line_w, max_h in line_data:
            match self.style.align_h:
                case "center":
                    x_offset = pad_left + (usable_width - line_w) // 2
                case "right":
                    x_offset = pad_left + (usable_width - line_w)
                case "left" | _:
                    x_offset = pad_left

            for item, item_w, item_h, is_surface in line:
                item_y = y_offset + (max_h - item_h) // 2
                if is_surface and isinstance(item, pygame.Surface):
                    surf.blit(item, (x_offset, item_y))
                elif isinstance(item, str):
                    txt_surf = self.style.font.render(item, True, self.style.text_color)
                    surf.blit(txt_surf, (x_offset, item_y))
                x_offset += item_w + self.style.font.size(" ")[0]

            y_offset += max_h + self.style.line_spacing

        if self.style.border_color and self.style.border_width > 0:
            pygame.draw.rect(
                surf,
                self.style.border_color,
                (0, 0, w, h),
                self.style.border_width,
            )

        return surf

    def handle_event(
        self, event: pygame.event.Event, mouse_pos: Tuple[int, int]
    ) -> None:
        pass

    @abstractmethod
    def render(self, topleft: Tuple[int, int]) -> Tuple[pygame.Surface, pygame.Rect]:
        pass


class UIButton(UIElement):

    def __init__(
        self,
        text: TextSource,
        style: UIStyle,
        width: Union[int, str] = "auto",
        height: Union[int, str] = "auto",
        on_click: Optional[Callable[[], None]] = None,
        inline_surfaces: Optional[Dict[str, pygame.Surface]] = None,
    ):
        super().__init__(width, height, style)
        self.text = text
        self.on_click = on_click
        self.inline_surfaces = inline_surfaces if inline_surfaces else {}
        self.is_hovered = False

    def render(self, topleft: Tuple[int, int]) -> Tuple[pygame.Surface, pygame.Rect]:
        self.absolute_rect.topleft = topleft
        current_bg = self.style.hover_color if self.is_hovered else self.style.bg_color

        button_surf = self.draw_base_layout(
            self.text, self.inline_surfaces, bg_override=current_bg
        )
        return button_surf, self.absolute_rect

    def handle_event(
        self, event: pygame.event.Event, mouse_pos: Tuple[int, int]
    ) -> None:
        match event.type:
            case pygame.MOUSEMOTION:
                previously_hovered = self.is_hovered
                self.is_hovered = self.absolute_rect.collidepoint(mouse_pos)

                if self.is_hovered != previously_hovered:
                    if self.is_hovered:
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                    else:
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

            case pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and self.is_hovered and self.on_click:
                    self.on_click()


class UITextBox(UIElement):

    def __init__(
        self,
        text: TextSource,
        style: UIStyle,
        width: Union[int, str] = "auto",
        height: Union[int, str] = "auto",
        inline_surfaces: Optional[Dict[str, pygame.Surface]] = None,
    ):
        super().__init__(width, height, style)
        self.text = text
        self.inline_surfaces = inline_surfaces if inline_surfaces else {}

    def render(self, topleft: Tuple[int, int]) -> Tuple[pygame.Surface, pygame.Rect]:
        self.absolute_rect.topleft = topleft
        box_surf = self.draw_base_layout(self.text, self.inline_surfaces)
        return box_surf, self.absolute_rect


class UIPanel:
    """Container tracking and laying out collections of custom child nodes uniformly."""

    def __init__(
        self,
        x: int,
        y: int,
        spacing: int = 10,
        orientation: str = "vertical",
        bg_color: Optional[ColorRGBA] = None,
        padding: int = 10,
    ):
        self.rect = pygame.Rect(x, y, 0, 0)
        self.spacing = spacing
        self.orientation = orientation
        self.bg_color = bg_color
        self.padding = padding
        self.children: List[UIElement] = []

    def add_child(self, child: UIElement) -> None:
        self.children.append(child)

    def handle_event(
        self, event: pygame.event.Event, mouse_pos: Tuple[int, int]
    ) -> None:
        for child in self.children:
            child.handle_event(event, mouse_pos)

    def render(self, surface: pygame.Surface) -> None:
        # dynamic check across any element supporting layout calculation via text
        for child in self.children:
            if hasattr(child, "text") and hasattr(child, "calculate_layout"):
                child.calculate_layout(
                    child.text, getattr(child, "inline_surfaces", {})
                )

        current_x = self.rect.x + self.padding
        current_y = self.rect.y + self.padding

        max_w = 0
        max_h = 0

        child_positions = []
        for child in self.children:
            child_positions.append((current_x, current_y))
            if self.orientation == "vertical":
                current_y += child.height + self.spacing
                max_w = max(max_w, child.width)
            else:
                current_x += child.width + self.spacing
                max_h = max(max_h, child.height)

        if self.orientation == "vertical":
            self.rect.width = max_w + (self.padding * 2)
            self.rect.height = (
                (current_y - self.spacing - self.rect.y) + self.padding
                if self.children
                else self.padding * 2
            )
        else:
            self.rect.height = max_h + (self.padding * 2)
            self.rect.width = (
                (current_x - self.spacing - self.rect.x) + self.padding
                if self.children
                else self.padding * 2
            )

        if self.bg_color:
            panel_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            panel_surf.fill(self.bg_color)
            surface.blit(panel_surf, self.rect.topleft)

        for child, pos in zip(self.children, child_positions):
            c_surf, c_rect = child.render(topleft=pos)
            surface.blit(c_surf, c_rect)
