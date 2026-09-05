"""Generate a square, W3C-style test image for blend-mode comparisons.

The upper half is a full-spectrum rainbow gradient and the lower half is a
black-to-white grayscale gradient.  Keeping the image deliberately simple
makes the characteristic changes of each blend mode easy to compare.
"""

from __future__ import annotations

import argparse
import colorsys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "assets" / "images" / "layer-blend-top-pattern.png"


def build_pattern(size: int) -> Image.Image:
    """Return an opaque square with a rainbow and grayscale gradient."""

    image = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    pixels = image.load()
    split = size // 2

    for x in range(size):
        position = x / max(size - 1, 1)
        red, green, blue = colorsys.hsv_to_rgb(position, 1.0, 1.0)
        rainbow = (round(red * 255), round(green * 255), round(blue * 255), 255)
        gray = round(position * 255)
        grayscale = (gray, gray, gray, 255)

        for y in range(split):
            pixels[x, y] = rainbow
        for y in range(split, size):
            pixels[x, y] = grayscale

    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"path for the PNG (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--size", type=int, default=1024, help="square image size in pixels")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.size <= 0:
        raise SystemExit("size must be positive")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    pattern = build_pattern(args.size)
    pattern.save(output, format="PNG", optimize=True)

    # Keep a predictable preview path for review workflows.  This pattern is
    # fully opaque, so the preview is intentionally identical to the source.
    preview_path = output.with_name(f"{output.stem}-preview{output.suffix}")
    pattern.save(preview_path, format="PNG", optimize=True)

    print(f"PNG:     {output}")
    print(f"Preview: {preview_path}")
    print(f"Size:    {args.size}x{args.size}")


if __name__ == "__main__":
    main()
