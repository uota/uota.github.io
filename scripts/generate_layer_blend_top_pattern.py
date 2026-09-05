"""Generate a transparent Top layer for comparing paint-software blend modes.

The image intentionally contains several kinds of input at once:

* a grayscale gradient for checking contrast and midpoint behavior
* neutral gray and RGB/CMY swatches
* repeated shapes with different alpha values
* soft shadows, highlights, color washes, and fine diagonal lines

The generated PNG is an RGBA layer.  A checkerboard preview is also written so
that the transparent regions are easy to inspect outside an image editor.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "assets" / "images" / "layer-blend-top-pattern.png"


def composite(destination: Image.Image, source: Image.Image) -> None:
    """Composite source over destination in place."""

    destination.alpha_composite(source)


def draw_gradient_panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
) -> None:
    """Draw a black-to-white gradient whose opacity rises from top to bottom."""

    left, top, right, bottom = box
    panel = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    pixels = panel.load()
    width, height = panel.size

    for y in range(height):
        opacity = round(35 + 215 * y / max(height - 1, 1))
        for x in range(width):
            value = round(255 * x / max(width - 1, 1))
            pixels[x, y] = (value, value, value, opacity)

    image.alpha_composite(panel, (left, top))


def draw_alpha_steps(image: Image.Image, origin: tuple[int, int]) -> None:
    """Draw the same black shape at four different opacities."""

    x0, y0 = origin
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    size = 118
    gap = 22

    for index, opacity in enumerate((48, 96, 160, 224)):
        left = x0 + index * (size + gap)
        draw.ellipse((left, y0, left + size, y0 + size), fill=(20, 20, 24, opacity))

    composite(image, layer)


def draw_color_swatches(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    """Draw RGB and CMY swatches with a small amount of transparency."""

    left, top, right, bottom = box
    swatches = (
        (235, 44, 58),
        (42, 188, 103),
        (50, 118, 230),
        (32, 200, 211),
        (219, 62, 184),
        (245, 196, 54),
    )
    width = (right - left) // len(swatches)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    for index, color in enumerate(swatches):
        x1 = left + index * width
        x2 = right if index == len(swatches) - 1 else x1 + width
        draw.rectangle((x1, top, x2, bottom), fill=(*color, 218))

    composite(image, layer)


def draw_soft_shapes(image: Image.Image) -> None:
    """Add blurred shadows, highlights, and colored washes."""

    shadows = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadows)
    shadow_draw.ellipse((466, 322, 770, 560), fill=(10, 13, 20, 170))
    shadow_draw.ellipse((600, 270, 914, 500), fill=(10, 13, 20, 100))
    shadows = shadows.filter(ImageFilter.GaussianBlur(24))
    composite(image, shadows)

    washes = Image.new("RGBA", image.size, (0, 0, 0, 0))
    wash_draw = ImageDraw.Draw(washes)
    wash_draw.ellipse((764, 310, 1014, 560), fill=(34, 196, 224, 130))
    wash_draw.ellipse((880, 315, 1130, 565), fill=(222, 56, 175, 125))
    wash_draw.ellipse((820, 418, 1070, 668), fill=(245, 193, 45, 120))
    washes = washes.filter(ImageFilter.GaussianBlur(10))
    composite(image, washes)

    highlights = Image.new("RGBA", image.size, (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlights)
    highlight_draw.ellipse((1010, 280, 1184, 454), fill=(255, 255, 255, 190))
    highlight_draw.ellipse((1060, 470, 1228, 638), fill=(255, 255, 255, 145))
    highlights = highlights.filter(ImageFilter.GaussianBlur(18))
    composite(image, highlights)


def draw_fine_lines(image: Image.Image) -> None:
    """Add high-frequency black and white detail for edge/texture testing."""

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    for offset in range(-80, 430, 24):
        draw.line((430 + offset, 682, 690 + offset, 410), fill=(255, 255, 255, 135), width=7)
        draw.line((442 + offset, 682, 702 + offset, 410), fill=(18, 22, 30, 120), width=7)

    composite(image, layer)


def checkerboard(size: tuple[int, int], tile: int = 32) -> Image.Image:
    """Return a neutral checkerboard for previewing transparency."""

    width, height = size
    preview = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(preview)

    for y in range(0, height, tile):
        for x in range(0, width, tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(210, 210, 210, 255))

    return preview


def build_pattern(width: int, height: int) -> Image.Image:
    """Build the transparent Top layer at the requested size."""

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # The top row is deliberately crisp: neutral values and saturated colors
    # make mode differences easier to spot in a comparison grid.
    margin_x = round(width * 0.035)
    margin_y = round(height * 0.05)
    panel_height = round(height * 0.29)
    draw_gradient_panel(image, (margin_x, margin_y, round(width * 0.29), margin_y + panel_height))

    neutral = Image.new("RGBA", image.size, (0, 0, 0, 0))
    neutral_draw = ImageDraw.Draw(neutral)
    neutral_draw.rectangle(
        (round(width * 0.32), margin_y, round(width * 0.54), margin_y + panel_height),
        fill=(128, 128, 128, 220),
    )
    composite(image, neutral)

    draw_color_swatches(
        image,
        (round(width * 0.57), margin_y, round(width * 0.965), margin_y + panel_height),
    )

    # The lower part mixes opacity, soft forms, texture, and light.
    draw_alpha_steps(image, (round(width * 0.05), round(height * 0.49)))
    draw_soft_shapes(image)
    draw_fine_lines(image)

    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"path for the RGBA PNG (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--width", type=int, default=1280, help="output width in pixels")
    parser.add_argument("--height", type=int, default=720, help="output height in pixels")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        raise SystemExit("width and height must be positive")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    pattern = build_pattern(args.width, args.height)
    pattern.save(output, format="PNG", optimize=True)

    preview = checkerboard(pattern.size)
    preview.alpha_composite(pattern)
    preview_path = output.with_name(f"{output.stem}-preview{output.suffix}")
    preview.save(preview_path, format="PNG", optimize=True)

    print(f"RGBA layer: {output}")
    print(f"Preview:    {preview_path}")
    print(f"Size:       {args.width}x{args.height}")


if __name__ == "__main__":
    main()
