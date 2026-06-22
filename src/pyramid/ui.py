from abc import ABC as _ABC, abstractmethod as _abstractmethod
from collections.abc import Callable as _Callable
from dataclasses import dataclass as _dataclass
from enum import StrEnum as _StrEnum
import pygame as _pygame

__all__ = [
    "ImageScaleMode",
    "PanelOrientation",
    "UIAlignmentH",
    "UIAlignmentV",
    "UIButton",
    "UIElement",
    "UIImage",
    "UIPanel",
    "UIScrollPanel",
    "UISize",
    "UIStyle",
    "UITextBox",
    "UITextElement",
]


# Type aliases to keep signatures clean
ColorRGBA = tuple[int, int, int, int]
LineItem = tuple[_pygame.Surface | str, int, int, bool]
LineLayout = tuple[list[LineItem], int, int]
TextSource = str | _Callable[[], str]


class UIAlignmentH(_StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class UIAlignmentV(_StrEnum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


class UISize(_StrEnum):
    AUTO = "auto"


class ImageScaleMode(_StrEnum):
    NONE = "none"  # stay the same size
    FIT = "fit"  # rescale keeping aspect ratio
    STRETCH = "stretch"  # stretch to fill the area


class PanelOrientation(_StrEnum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


@_dataclass
class UIStyle:
    """Groups styling configuration for UI components, including fonts (if applicable), colors, borders, and alignment."""

    font: _pygame.font.Font | None = None
    text_color: ColorRGBA = (255, 255, 255, 255)
    bg_color: ColorRGBA | None = (0, 0, 0, 100)
    hover_color: ColorRGBA = (70, 70, 70, 100)
    border_color: ColorRGBA | None = (255, 255, 255, 255)
    border_width: int = 1
    padding: int | tuple[int, int, int, int] = 4  # top, right, bottom, left
    align_h: UIAlignmentH = UIAlignmentH.CENTER
    align_v: UIAlignmentV = UIAlignmentV.CENTER
    line_spacing: int = 4


class UIElement(_ABC):
    """Abstract base class for UI elements supporting layout, rendering, and event handling."""

    def __init__(
        self,
        style: UIStyle,
        width: int | UISize = UISize.AUTO,
        height: int | UISize = UISize.AUTO,
    ):
        self.requested_width = width
        self.requested_height = height
        self.style = style

        self.width: int = 0 if width == UISize.AUTO else int(width)
        self.height: int = 0 if height == UISize.AUTO else int(height)

        if isinstance(style.padding, int):
            self.padding = (style.padding,) * 4
        else:
            self.padding = style.padding

        self.absolute_rect = _pygame.Rect(0, 0, self.width, self.height)

    @_abstractmethod
    def update_dimensions(self) -> None:
        """Update self.width and self.height based on content and requested size."""
        pass

    def prepare_base_surface(
        self, w: int, h: int, bg_override: ColorRGBA | None = None
    ) -> _pygame.Surface:
        """Generates a standard background canvas with optional borders applied."""
        surf = _pygame.Surface((w, h), _pygame.SRCALPHA)
        bg = bg_override if bg_override is not None else self.style.bg_color
        if bg:
            surf.fill(bg)

        if self.style.border_color and self.style.border_width > 0:
            _pygame.draw.rect(
                surf,
                self.style.border_color,
                (0, 0, w, h),
                self.style.border_width,
            )
        return surf

    def handle_event(
        self, event: _pygame.event.Event, mouse_pos: tuple[int, int]
    ) -> None:
        """Handles a Pygame event for this UI element."""
        pass

    @_abstractmethod
    def render(self, topleft: tuple[int, int]) -> tuple[_pygame.Surface, _pygame.Rect]:
        """Renders the UI element at the requested position and returns its surface and rect."""
        pass


class UITextElement(UIElement, _ABC):
    """Base class for text-based UI elements that calculate layout and render multiline text."""

    def __init__(
        self,
        text: TextSource,
        style: UIStyle,
        width: int | UISize = UISize.AUTO,
        height: int | UISize = UISize.AUTO,
        inline_surfaces: dict[str, _pygame.Surface] | None = None,
    ):
        if style.font is None:
            raise ValueError(
                "UITextElement implementations require a valid _pygame.font.Font in UIStyle."
            )
        super().__init__(style, width, height)
        self.text = text
        self.inline_surfaces = inline_surfaces if inline_surfaces else {}
        self._cached_line_data: list[LineLayout] = []
        self._cached_text_height: int = 0

    def _get_active_text(self) -> str:
        """Resolves either literal text or a callable text source to a string."""
        if isinstance(self.text, str):
            return str(self.text)
        return str(self.text())

    def update_dimensions(self) -> None:
        """Calculates textual layout dimensions, structural wraps, and bounding boxes."""
        resolved_text = self._get_active_text()
        pad_top, pad_right, pad_bottom, pad_left = self.padding
        font = self.style.font
        assert font is not None
        space_width = font.size(" ")[0]

        max_usable_w = (
            self.width - pad_left - pad_right
            if self.requested_width != UISize.AUTO
            else float("inf")
        )

        words = resolved_text.split(" ")
        lines: list[list[LineItem]] = []
        current_line: list[LineItem] = []
        current_width = 0

        for word in words:
            if word in self.inline_surfaces:
                item_surf = self.inline_surfaces[word]
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

        self._cached_line_data = []
        self._cached_text_height = 0
        max_line_width = 0

        for line in lines:
            if not line:
                continue
            max_h = max(item[2] for item in line)
            line_w = sum(item[1] for item in line) + (space_width * (len(line) - 1))
            max_line_width = max(max_line_width, line_w)
            self._cached_line_data.append((line, line_w, max_h))
            self._cached_text_height += max_h + self.style.line_spacing

        if self._cached_text_height > 0:
            self._cached_text_height -= self.style.line_spacing

        self.width = (
            max_line_width + pad_left + pad_right
            if self.requested_width == UISize.AUTO
            else int(self.requested_width)
        )
        self.height = (
            self._cached_text_height + pad_top + pad_bottom
            if self.requested_height == UISize.AUTO
            else int(self.requested_height)
        )
        self.absolute_rect.size = (self.width, self.height)

    def draw_text_layout(self, bg_override: ColorRGBA | None = None) -> _pygame.Surface:
        """Draws the text with inline surfaces and alignment into the prepared surface."""

        assert self.style.font is not None
        surf = self.prepare_base_surface(self.width, self.height, bg_override)
        pad_top, pad_right, pad_bottom, pad_left = self.padding

        usable_width = max(0, self.width - pad_left - pad_right)
        usable_height = max(0, self.height - pad_top - pad_bottom)

        match self.style.align_v:
            case UIAlignmentV.CENTER:
                y_offset = pad_top + (usable_height - self._cached_text_height) // 2
            case UIAlignmentV.BOTTOM:
                y_offset = pad_top + (usable_height - self._cached_text_height)
            case UIAlignmentV.TOP | _:
                y_offset = pad_top

        for line, line_w, max_h in self._cached_line_data:
            match self.style.align_h:
                case UIAlignmentH.CENTER:
                    x_offset = pad_left + (usable_width - line_w) // 2
                case UIAlignmentH.RIGHT:
                    x_offset = pad_left + (usable_width - line_w)
                case UIAlignmentH.LEFT | _:
                    x_offset = pad_left

            for item, item_w, item_h, is_surface in line:
                item_y = y_offset + (max_h - item_h) // 2
                if is_surface and isinstance(item, _pygame.Surface):
                    surf.blit(item, (x_offset, item_y))
                elif isinstance(item, str):
                    txt_surf = self.style.font.render(item, True, self.style.text_color)
                    surf.blit(txt_surf, (x_offset, item_y))
                x_offset += item_w + self.style.font.size(" ")[0]

            y_offset += max_h + self.style.line_spacing

        return surf


class UIButton(UITextElement):
    """Button element that renders styled text and supports hover/click input."""

    def __init__(
        self,
        text: TextSource,
        style: UIStyle,
        width: int | UISize = UISize.AUTO,
        height: int | UISize = UISize.AUTO,
        on_click: _Callable[[], None] | None = None,
        inline_surfaces: dict[str, _pygame.Surface] | None = None,
    ):
        super().__init__(text, style, width, height, inline_surfaces)
        self.on_click = on_click
        self.is_hovered = False

    def render(self, topleft: tuple[int, int]) -> tuple[_pygame.Surface, _pygame.Rect]:
        self.absolute_rect.topleft = topleft
        current_bg = self.style.hover_color if self.is_hovered else self.style.bg_color
        button_surf = self.draw_text_layout(bg_override=current_bg)
        return button_surf, self.absolute_rect

    def handle_event(
        self, event: _pygame.event.Event, mouse_pos: tuple[int, int]
    ) -> None:
        match event.type:
            case _pygame.MOUSEMOTION:
                previously_hovered = self.is_hovered
                self.is_hovered = self.absolute_rect.collidepoint(mouse_pos)

                if self.is_hovered != previously_hovered:
                    if self.is_hovered:
                        _pygame.mouse.set_cursor(_pygame.SYSTEM_CURSOR_HAND)
                    else:
                        _pygame.mouse.set_cursor(_pygame.SYSTEM_CURSOR_ARROW)

            case _pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and self.is_hovered and self.on_click:
                    self.on_click()


class UITextBox(UITextElement):
    """Simple text box element that renders text to a surface."""

    def render(self, topleft: tuple[int, int]) -> tuple[_pygame.Surface, _pygame.Rect]:
        self.absolute_rect.topleft = topleft
        box_surf = self.draw_text_layout()
        return box_surf, self.absolute_rect


class UIImage(UIElement):
    """Element displaying an image with optional fitting, stretching, or no scaling."""

    def __init__(
        self,
        image: _pygame.Surface,
        width: int | UISize = UISize.AUTO,
        height: int | UISize = UISize.AUTO,
        scale_mode: ImageScaleMode = ImageScaleMode.FIT,
        style: UIStyle | None = None,
    ):
        super().__init__(style or UIStyle(font=None), width, height)
        self.original_image = image
        self.scale_mode = scale_mode

    def update_dimensions(self) -> None:
        pad_top, pad_right, pad_bottom, pad_left = self.padding
        img_w, img_h = self.original_image.get_size()

        self.width = (
            img_w + pad_left + pad_right
            if self.requested_width == UISize.AUTO
            else int(self.requested_width)
        )
        self.height = (
            img_h + pad_top + pad_bottom
            if self.requested_height == UISize.AUTO
            else int(self.requested_height)
        )
        self.absolute_rect.size = (self.width, self.height)

    def render(self, topleft: tuple[int, int]) -> tuple[_pygame.Surface, _pygame.Rect]:
        self.absolute_rect.topleft = topleft
        surf = self.prepare_base_surface(self.width, self.height)

        pad_top, pad_right, pad_bottom, pad_left = self.padding
        usable_w = max(0, self.width - pad_left - pad_right)
        usable_h = max(0, self.height - pad_top - pad_bottom)

        if usable_w <= 0 or usable_h <= 0:
            return surf, self.absolute_rect

        img_w, img_h = self.original_image.get_size()

        match self.scale_mode:
            case ImageScaleMode.NONE:
                cx = pad_left + (usable_w - img_w) // 2
                cy = pad_top + (usable_h - img_h) // 2

                clip_rect = _pygame.Rect(pad_left, pad_top, usable_w, usable_h)
                surf.blit(self.original_image, (cx, cy), area=clip_rect.move(-cx, -cy))

            case ImageScaleMode.FIT:
                aspect_ratio = img_w / img_h
                if usable_w / usable_h > aspect_ratio:
                    new_h = usable_h
                    new_w = int(usable_h * aspect_ratio)
                else:
                    new_w = usable_w
                    new_h = int(usable_w / aspect_ratio)

                if new_w > 0 and new_h > 0:
                    render_img = _pygame.transform.scale(
                        self.original_image, (new_w, new_h)
                    )
                    cx = pad_left + (usable_w - new_w) // 2
                    cy = pad_top + (usable_h - new_h) // 2
                    surf.blit(render_img, (cx, cy))

            case ImageScaleMode.STRETCH:
                render_img = _pygame.transform.scale(
                    self.original_image, (usable_w, usable_h)
                )
                surf.blit(render_img, (pad_left, pad_top))

        return surf, self.absolute_rect


class UIPanel:
    """Container for arranging UI elements in a row or column with padding and spacing."""

    def __init__(
        self,
        x: int,
        y: int,
        spacing: int = 10,
        orientation: PanelOrientation = PanelOrientation.VERTICAL,
        bg_color: ColorRGBA | None = None,
        padding: int = 10,
    ):
        self.rect = _pygame.Rect(x, y, 0, 0)
        self.spacing = spacing
        self.orientation = orientation
        self.bg_color = bg_color
        self.padding = padding
        self.children: list[UIElement] = []

    def add_child(self, child: UIElement) -> None:
        self.children.append(child)

    def handle_event(
        self, event: _pygame.event.Event, mouse_pos: tuple[int, int]
    ) -> None:
        local_mouse_pos = (mouse_pos[0] - self.rect.x, mouse_pos[1] - self.rect.y)
        for child in self.children:
            child.handle_event(event, local_mouse_pos)

    def render(
        self, topleft: tuple[int, int] | None = None
    ) -> tuple[_pygame.Surface, _pygame.Rect]:
        if topleft is not None:
            self.rect.topleft = topleft

        for child in self.children:
            child.update_dimensions()

        current_x = self.padding
        current_y = self.padding

        max_w = 0
        max_h = 0

        child_positions = []
        for child in self.children:
            child_positions.append((current_x, current_y))
            if self.orientation == PanelOrientation.VERTICAL:
                current_y += child.height + self.spacing
                max_w = max(max_w, child.width)
            else:
                current_x += child.width + self.spacing
                max_h = max(max_h, child.height)

        if self.orientation == PanelOrientation.VERTICAL:
            self.rect.width = max_w + (self.padding * 2)
            self.rect.height = (
                current_y - self.spacing + self.padding
                if self.children
                else self.padding * 2
            )
        else:
            self.rect.height = max_h + (self.padding * 2)
            self.rect.width = (
                current_x - self.spacing + self.padding
                if self.children
                else self.padding * 2
            )

        panel_surf = _pygame.Surface(self.rect.size, _pygame.SRCALPHA)
        if self.bg_color:
            panel_surf.fill(self.bg_color)

        for child, pos in zip(self.children, child_positions):
            c_surf, _ = child.render(topleft=pos)
            panel_surf.blit(c_surf, pos)

        return panel_surf, self.rect


class UIScrollPanel(UIPanel):
    """Scrollable panel container that supports mouse-wheel scrolling.

    The scroll direction and maximum scroll distance are configurable.
    If max_scroll_distance is `UISize.AUTO`, the panel calculates its own maximum
    scroll range from content size and visible viewport size.
    """

    def __init__(
        self,
        x: int,
        y: int,
        width: int | UISize = UISize.AUTO,
        height: int | UISize = UISize.AUTO,
        spacing: int = 10,
        orientation: PanelOrientation = PanelOrientation.VERTICAL,
        scroll_direction: PanelOrientation | None = None,
        max_scroll_distance: int | UISize = UISize.AUTO,
        step: int = 20,
        scroll_inverted: bool = False,
        bg_color: ColorRGBA | None = None,
        padding: int = 10,
    ):
        super().__init__(x, y, spacing, orientation, bg_color, padding)
        self.requested_width = width
        self.requested_height = height
        self.width = 0 if width == UISize.AUTO else int(width)
        self.height = 0 if height == UISize.AUTO else int(height)
        self.scroll_direction = scroll_direction or orientation
        self.max_scroll_distance = max_scroll_distance
        self.scroll_inverted = scroll_inverted
        self.scroll_offset = 0
        self.step = step

    def _resolve_max_scroll(self, content_w: int, content_h: int) -> int:
        if self.max_scroll_distance == UISize.AUTO:
            viewport_size = self.height if self.scroll_direction == PanelOrientation.VERTICAL else self.width
            content_size = content_h if self.scroll_direction == PanelOrientation.VERTICAL else content_w
            return max(0, content_size - viewport_size)
        return max(0, int(self.max_scroll_distance))

    def update_dimensions(self) -> None:
        for child in self.children:
            child.update_dimensions()

        current_x = self.padding
        current_y = self.padding
        max_w = 0
        max_h = 0

        for child in self.children:
            if self.orientation == PanelOrientation.VERTICAL:
                max_w = max(max_w, child.width)
                current_y += child.height + self.spacing
            else:
                max_h = max(max_h, child.height)
                current_x += child.width + self.spacing

        content_w = max_w if self.orientation == PanelOrientation.VERTICAL else max(0, current_x - self.spacing - self.padding)
        content_h = max(0, current_y - self.spacing - self.padding) if self.orientation == PanelOrientation.VERTICAL else max_h

        self.width = content_w + (self.padding * 2) if self.requested_width == UISize.AUTO else int(self.requested_width)
        self.height = content_h + (self.padding * 2) if self.requested_height == UISize.AUTO else int(self.requested_height)
        self.rect.size = (self.width, self.height)
        self.max_scroll_distance = self._resolve_max_scroll(content_w, content_h)
        self.scroll_offset = min(self.scroll_offset, self.max_scroll_distance)

    def _apply_scroll_event(self, event: _pygame.event.Event) -> None:
        if event.type == _pygame.MOUSEWHEEL:
            delta = (event.y + event.x)
        else:
            return

        if self.scroll_inverted:
            delta = -delta

        self.scroll_offset = min(
            max(self.scroll_offset - delta * self.step, 0),
            self.max_scroll_distance,
        )

    def handle_event(
        self, event: _pygame.event.Event, mouse_pos: tuple[int, int]
    ) -> None:
        if not self.rect.collidepoint(mouse_pos):
            return

        if event.type in (_pygame.MOUSEWHEEL, _pygame.MOUSEBUTTONDOWN):
            self._apply_scroll_event(event)

        local_mouse_pos = (mouse_pos[0] - self.rect.x, mouse_pos[1] - self.rect.y)
        for child in self.children:
            child.handle_event(event, local_mouse_pos)

    def render(
        self, topleft: tuple[int, int] | None = None
    ) -> tuple[_pygame.Surface, _pygame.Rect]:
        if topleft is not None:
            self.rect.topleft = topleft

        self.update_dimensions()

        current_x = self.padding
        current_y = self.padding
        child_positions: list[tuple[int, int]] = []

        for child in self.children:
            child_positions.append((current_x, current_y))
            if self.orientation == PanelOrientation.VERTICAL:
                current_y += child.height + self.spacing
            else:
                current_x += child.width + self.spacing

        panel_surf = _pygame.Surface(self.rect.size, _pygame.SRCALPHA)
        if self.bg_color:
            panel_surf.fill(self.bg_color)

        for child, pos in zip(self.children, child_positions):
            render_pos = (
                pos[0] - self.scroll_offset if self.scroll_direction == PanelOrientation.HORIZONTAL else pos[0],
                pos[1] - self.scroll_offset if self.scroll_direction == PanelOrientation.VERTICAL else pos[1],
            )
            c_surf, _ = child.render(topleft=render_pos)
            panel_surf.blit(c_surf, render_pos)

        return panel_surf, self.rect
