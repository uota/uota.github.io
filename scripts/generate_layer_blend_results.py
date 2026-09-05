"""Generate 1024px WebP examples for every blend mode in the article.

The script uses the fruit photograph as C_base and the rainbow/grayscale image
as C_top.  Both inputs are opaque, so the generated files show C_mode directly.
The 16 W3C modes follow Compositing and Blending Level 1; the remaining modes
follow the simplified equations printed in the article.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "assets" / "images" / "layer-blend-base-fruit.webp"
DEFAULT_TOP = ROOT / "assets" / "images" / "layer-blend-top-pattern.webp"
DEFAULT_OUTPUT_DIR = ROOT / "assets" / "images" / "layer-blend-results"

MODE_NAMES = (
    ("normal", "通常"),
    ("darken", "比較（暗）"),
    ("multiply", "乗算"),
    ("color-burn", "焼き込みカラー"),
    ("lighten", "比較（明）"),
    ("screen", "スクリーン"),
    ("color-dodge", "覆い焼きカラー"),
    ("overlay", "オーバーレイ"),
    ("soft-light", "ソフトライト"),
    ("hard-light", "ハードライト"),
    ("difference", "差の絶対値"),
    ("exclusion", "除外"),
    ("hue", "色相"),
    ("saturation", "彩度"),
    ("color", "カラー"),
    ("luminosity", "輝度"),
    ("add", "加算"),
    ("linear-burn", "焼き込み（リニア）"),
    ("subtract", "減算"),
    ("divide", "除算"),
    ("darker-color", "カラー比較（暗）"),
    ("lighter-color", "カラー比較（明）"),
    ("vivid-light", "ビビッドライト"),
    ("linear-light", "リニアライト"),
    ("pin-light", "ピンライト"),
    ("hard-mix", "ハードミックス"),
)


def clamp(value: np.ndarray) -> np.ndarray:
    return np.clip(value, 0.0, 1.0)


def color_burn(base: np.ndarray, top: np.ndarray) -> np.ndarray:
    """W3C color-burn, including its endpoint rules."""

    with np.errstate(divide="ignore", invalid="ignore"):
        result = 1.0 - np.minimum(1.0, (1.0 - base) / top)
    result = np.where(top == 0.0, 0.0, result)
    return np.where(base == 1.0, 1.0, result)


def color_dodge(base: np.ndarray, top: np.ndarray) -> np.ndarray:
    """W3C color-dodge, including its endpoint rules."""

    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.minimum(1.0, base / (1.0 - top))
    result = np.where(top == 1.0, 1.0, result)
    return np.where(base == 0.0, 0.0, result)


def soft_light(base: np.ndarray, top: np.ndarray) -> np.ndarray:
    """W3C soft-light."""

    g = np.where(
        base <= 0.25,
        ((16.0 * base - 12.0) * base + 4.0) * base,
        np.sqrt(base),
    )
    return np.where(
        top <= 0.5,
        base - (1.0 - 2.0 * top) * base * (1.0 - base),
        base + (2.0 * top - 1.0) * (g - base),
    )


def luminosity(color: np.ndarray) -> np.ndarray:
    """W3C Lum(C), expressed in the blending color space."""

    return 0.30 * color[..., 0] + 0.59 * color[..., 1] + 0.11 * color[..., 2]


def saturation(color: np.ndarray) -> np.ndarray:
    """W3C Sat(C)."""

    return color.max(axis=-1) - color.min(axis=-1)


def clip_color(color: np.ndarray) -> np.ndarray:
    """W3C ClipColor(C), preserving luminance while returning RGB to range."""

    lum = luminosity(color)[..., None]
    minimum = color.min(axis=-1)[..., None]
    clipped = color.copy()

    below = minimum < 0.0
    below_factor = np.ones_like(lum)
    below_denominator = lum - minimum
    valid_below = below & (below_denominator > 1e-8)
    np.divide(lum, below_denominator, out=below_factor, where=valid_below)
    corrected_below = lum + (clipped - lum) * below_factor
    clipped = np.where(valid_below, corrected_below, clipped)
    # A neutral color below zero has no chroma to preserve; it maps to black.
    clipped = np.where(below & ~valid_below, 0.0, clipped)

    maximum = clipped.max(axis=-1)[..., None]
    above = maximum > 1.0
    above_factor = np.ones_like(lum)
    above_denominator = maximum - lum
    valid_above = above & (above_denominator > 1e-8)
    np.divide(1.0 - lum, above_denominator, out=above_factor, where=valid_above)
    corrected_above = lum + (clipped - lum) * above_factor
    clipped = np.where(valid_above, corrected_above, clipped)
    # Likewise, a neutral color above one maps to white.
    clipped = np.where(above & ~valid_above, 1.0, clipped)
    return clipped


def set_luminosity(color: np.ndarray, target_luminosity: np.ndarray) -> np.ndarray:
    return clip_color(color + (target_luminosity - luminosity(color))[..., None])


def set_saturation(color: np.ndarray, target_saturation: np.ndarray) -> np.ndarray:
    """W3C SetSat(C, s), vectorized without changing channel ordering."""

    minimum = color.min(axis=-1)[..., None]
    maximum = color.max(axis=-1)[..., None]
    span = maximum - minimum
    scale = np.zeros_like(target_saturation[..., None])
    np.divide(target_saturation[..., None], span, out=scale, where=span > 0.0)
    return (color - minimum) * scale


def non_separable_mode(name: str, base: np.ndarray, top: np.ndarray) -> np.ndarray:
    if name == "hue":
        return set_luminosity(set_saturation(top, saturation(base)), luminosity(base))
    if name == "saturation":
        return set_luminosity(set_saturation(base, saturation(top)), luminosity(base))
    if name == "color":
        return set_luminosity(top, luminosity(base))
    if name == "luminosity":
        return set_luminosity(base, luminosity(top))
    raise ValueError(f"unknown non-separable mode: {name}")


def blend(name: str, base: np.ndarray, top: np.ndarray) -> np.ndarray:
    """Return C_mode for a named blend mode, using values normalized to 0..1."""

    if name == "normal":
        return top
    if name == "darken":
        return np.minimum(base, top)
    if name == "multiply":
        return base * top
    if name == "color-burn":
        return color_burn(base, top)
    if name == "lighten":
        return np.maximum(base, top)
    if name == "screen":
        return 1.0 - (1.0 - base) * (1.0 - top)
    if name == "color-dodge":
        return color_dodge(base, top)
    if name == "overlay":
        return np.where(
            base < 0.5,
            2.0 * base * top,
            1.0 - 2.0 * (1.0 - base) * (1.0 - top),
        )
    if name == "soft-light":
        return soft_light(base, top)
    if name == "hard-light":
        return np.where(
            top < 0.5,
            2.0 * base * top,
            1.0 - 2.0 * (1.0 - base) * (1.0 - top),
        )
    if name == "difference":
        return np.abs(base - top)
    if name == "exclusion":
        return base + top - 2.0 * base * top
    if name in {"hue", "saturation", "color", "luminosity"}:
        return non_separable_mode(name, base, top)
    if name == "add":
        return clamp(base + top)
    if name == "linear-burn":
        return clamp(base + top - 1.0)
    if name == "subtract":
        return clamp(base - top)
    if name == "divide":
        # The article leaves the zero-divisor rule to implementations.  For
        # this visual example, a zero divisor saturates the channel to white.
        result = np.ones_like(base)
        np.divide(base, top, out=result, where=top > 0.0)
        return clamp(result)
    if name == "darker-color":
        choose_base = base.sum(axis=-1) < top.sum(axis=-1)
        return np.where(choose_base[..., None], base, top)
    if name == "lighter-color":
        choose_base = base.sum(axis=-1) > top.sum(axis=-1)
        return np.where(choose_base[..., None], base, top)
    if name == "vivid-light":
        return np.where(top < 0.5, color_burn(base, 2.0 * top), color_dodge(base, 2.0 * (top - 0.5)))
    if name == "linear-light":
        return clamp(base + 2.0 * top - 1.0)
    if name == "pin-light":
        return np.where(top < 0.5, np.minimum(base, 2.0 * top), np.maximum(base, 2.0 * top - 1.0))
    if name == "hard-mix":
        return np.where(base + top < 1.0, 0.0, 1.0)
    raise ValueError(f"unknown blend mode: {name}")


def load_input(path: Path, size: int) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(f"input image not found: {path}")
    image = Image.open(path).convert("RGB")
    image = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.float32) / 255.0


def save_webp(color: np.ndarray, output: Path, quality: int) -> None:
    pixels = np.rint(clamp(color) * 255.0).astype(np.uint8)
    Image.fromarray(pixels, mode="RGB").save(output, format="WEBP", quality=quality, method=6)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE, help="Base image (WebP)")
    parser.add_argument("--top", type=Path, default=DEFAULT_TOP, help="Top image (WebP)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="result directory")
    parser.add_argument("--size", type=int, default=1024, help="square output size in pixels")
    parser.add_argument("--quality", type=int, default=90, help="WebP quality from 0 to 100")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.size <= 0:
        raise SystemExit("size must be positive")
    if not 0 <= args.quality <= 100:
        raise SystemExit("quality must be between 0 and 100")

    base = load_input(args.base.resolve(), args.size)
    top = load_input(args.top.resolve(), args.size)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for slug, label in MODE_NAMES:
        output = output_dir / f"{slug}.webp"
        save_webp(blend(slug, base, top), output, args.quality)
        print(f"{label}: {output}")


if __name__ == "__main__":
    main()
