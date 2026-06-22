from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import pygame

__all__ = [
    "ImageScaleMode",
    "PanelOrientation",
    "UIAlignmentH",
    "UIAlignmentV",
    "UIButton",
    "UIElement",
    "UIImage",
    "UIPanel",
    "UISize",
    "UIStyle",
    "UITextBox",
    "UITextElement",
]


# Type aliases to keep signatures clean
ColorRGBA = tuple[int, int, int, int]
LineItem = tuple[pygame.Surface | str, int, int, bool]
LineLayout = tuple[list[LineItem], int, int]
TextSource = str | Callable[[], str]


class UIAlignmentH(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class UIAlignmentV(StrEnum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


class UISize(StrEnum):
    AUTO = "auto"


class ImageScaleMode(StrEnum):
    NONE = "none"  # stay the same size
    FIT = "fit"  # rescale keeping aspect ratio
    STRETCH = "stretch"  # stretch to fill the area


class PanelOrientation(StrEnum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


@dataclass
class UIStyle:
    """Groups styling configuration for UI components, including fonts (if applicable), colors, borders, and alignment."""

    font: pygame.font.Font | None = None
    text_color: ColorRGBA = (255, 255, 255, 255)
    bg_color: ColorRGBA | None = (0, 0, 0, 100)
    hover_color: ColorRGBA = (70, 70, 70, 100)
    border_color: ColorRGBA | None = (255, 255, 255, 255)
    border_width: int = 1
    padding: int | tuple[int, int, int, int] = 4  # top, right, bottom, left
    align_h: UIAlignmentH = UIAlignmentH.CENTER
    align_v: UIAlignmentV = UIAlignmentV.CENTER
    line_spacing: int = 4


class UIElement(ABC):
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

        self.absolute_rect = pygame.Rect(0, 0, self.width, self.height)

    @abstractmethod
    def update_dimensions(self) -> None:
        """Update self.width and self.height based on content and requested size."""
        pass

    def prepare_base_surface(
        self, w: int, h: int, bg_override: ColorRGBA | None = None
    ) -> pygame.Surface:
        """Generates a standard background canvas with optional borders applied."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        bg = bg_override if bg_override is not None else self.style.bg_color
        if bg:
            surf.fill(bg)

        if self.style.border_color and self.style.border_width > 0:
            pygame.draw.rect(
                surf,
                self.style.border_color,
                (0, 0, w, h),
                self.style.border_width,
            )
        return surf

    def handle_event(
        self, event: pygame.event.Event, mouse_pos: tuple[int, int]
    ) -> None:
        """Handles a Pygame event for this UI element."""
        pass

    @abstractmethod
    def render(self, topleft: tuple[int, int]) -> tuple[pygame.Surface, pygame.Rect]:
        """Renders the UI element at the requested position and returns its surface and rect."""
        pass


class UITextElement(UIElement, ABC):
    """Base class for text-based UI elements that calculate layout and render multiline text."""

    def __init__(
        self,
        text: TextSource,
        style: UIStyle,
        width: int | UISize = UISize.AUTO,
        height: int | UISize = UISize.AUTO,
        inline_surfaces: dict[str, pygame.Surface] | None = None,
    ):
        if style.font is None:
            raise ValueError(
                "UITextElement implementations require a valid pygame.font.Font in UIStyle."
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
        assert not (font is None)
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

    def draw_text_layout(self, bg_override: ColorRGBA | None = None) -> pygame.Surface:
        """Draws the text with inline surfaces and alignment into the prepared surface."""

        assert not (self.style.font is None)
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
                if is_surface and isinstance(item, pygame.Surface):
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
        on_click: Callable[[], None] | None = None,
        inline_surfaces: dict[str, pygame.Surface] | None = None,
    ):
        super().__init__(text, style, width, height, inline_surfaces)
        self.on_click = on_click
        self.is_hovered = False

    def render(self, topleft: tuple[int, int]) -> tuple[pygame.Surface, pygame.Rect]:
        self.absolute_rect.topleft = topleft
        current_bg = self.style.hover_color if self.is_hovered else self.style.bg_color
        button_surf = self.draw_text_layout(bg_override=current_bg)
        return button_surf, self.absolute_rect

    def handle_event(
        self, event: pygame.event.Event, mouse_pos: tuple[int, int]
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


class UITextBox(UITextElement):
    """Simple text box element that renders text to a surface."""

    def render(self, topleft: tuple[int, int]) -> tuple[pygame.Surface, pygame.Rect]:
        self.absolute_rect.topleft = topleft
        box_surf = self.draw_text_layout()
        return box_surf, self.absolute_rect


class UIImage(UIElement):
    """Element displaying an image with optional fitting, stretching, or no scaling."""

    def __init__(
        self,
        image: pygame.Surface,
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

    def render(self, topleft: tuple[int, int]) -> tuple[pygame.Surface, pygame.Rect]:
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

                clip_rect = pygame.Rect(pad_left, pad_top, usable_w, usable_h)
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
                    render_img = pygame.transform.scale(
                        self.original_image, (new_w, new_h)
                    )
                    cx = pad_left + (usable_w - new_w) // 2
                    cy = pad_top + (usable_h - new_h) // 2
                    surf.blit(render_img, (cx, cy))

            case ImageScaleMode.STRETCH:
                render_img = pygame.transform.scale(
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
        self.rect = pygame.Rect(x, y, 0, 0)
        self.spacing = spacing
        self.orientation = orientation
        self.bg_color = bg_color
        self.padding = padding
        self.children: list[UIElement] = []

    def add_child(self, child: UIElement) -> None:
        self.children.append(child)

    def handle_event(
        self, event: pygame.event.Event, mouse_pos: tuple[int, int]
    ) -> None:
        for child in self.children:
            child.handle_event(event, mouse_pos)

    def render(self, surface: pygame.Surface) -> None:
        for child in self.children:
            child.update_dimensions()

        current_x = self.rect.x + self.padding
        current_y = self.rect.y + self.padding

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
