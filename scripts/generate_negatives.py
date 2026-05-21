"""
Generate synthetic negative eval images for vexilloscope.

Produces 600 512x512 PNGs in data/generated/negative_eval/:
  solid_color/  (100)  flat single-color fills
  gradient/     (100)  linear gradients
  stripes/      (150)  random stripe patterns
  noise/        (100)  Gaussian/salt-and-pepper/random noise
  geometric/    (150)  circles, crosses, stars, triangles, rectangles on backgrounds

Usage:
    python scripts/generate_negatives.py [--output data/generated/negative_eval]
                                         [--seed 42]
                                         [--count-stripes 150]
                                         [--count-geometric 150]
                                         [--count-other 100]
"""

import argparse
import math
import random
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow>=9.0", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "data" / "generated" / "negative_eval"
SIZE = 512

WEB_COLORS = [
    (255, 0, 0), (0, 128, 0), (0, 0, 255), (255, 255, 0),
    (0, 255, 255), (255, 0, 255), (255, 165, 0), (128, 0, 128),
    (0, 0, 128), (0, 128, 128), (128, 128, 0), (128, 0, 0),
    (0, 255, 0), (0, 255, 255), (192, 192, 192), (255, 0, 255),
]


def _rand_rgb(rng: random.Random) -> tuple:
    return (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))


def _hue_to_rgb(hue: float) -> tuple:
    """Convert hue (0..1) to saturated RGB."""
    h = hue * 6.0
    i = int(h)
    f = h - i
    q = int((1.0 - f) * 255)
    t = int(f * 255)
    sectors = [
        (255, t, 0), (q, 255, 0), (0, 255, t),
        (0, q, 255), (t, 0, 255), (255, 0, q),
    ]
    return sectors[i % 6]


def gen_solid_color(rng: random.Random, n: int, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    fixed = [(255, 255, 255), (0, 0, 0), (128, 128, 128)] + WEB_COLORS
    for idx in range(n):
        if idx < len(fixed):
            color = fixed[idx]
        else:
            color = _rand_rgb(rng)
        img = Image.new("RGB", (SIZE, SIZE), color)
        img.save(out_dir / f"{idx:04d}.png")
    return n


def gen_gradient(rng: random.Random, n: int, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    orientations = ["horizontal", "vertical", "diagonal"]
    for idx in range(n):
        h1 = rng.random()
        h2 = rng.random()
        c1 = _hue_to_rgb(h1)
        c2 = _hue_to_rgb(h2)
        orient = orientations[idx % len(orientations)]
        img = Image.new("RGB", (SIZE, SIZE))
        pixels = img.load()
        for y in range(SIZE):
            for x in range(SIZE):
                if orient == "horizontal":
                    t = x / (SIZE - 1)
                elif orient == "vertical":
                    t = y / (SIZE - 1)
                else:
                    t = (x + y) / (2 * (SIZE - 1))
                r = int(c1[0] + t * (c2[0] - c1[0]))
                g = int(c1[1] + t * (c2[1] - c1[1]))
                b = int(c1[2] + t * (c2[2] - c1[2]))
                pixels[x, y] = (r, g, b)
        img.save(out_dir / f"{idx:04d}.png")
    return n


def gen_stripes(rng: random.Random, n: int, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    orientations = ["horizontal", "vertical", "diagonal"]
    for idx in range(n):
        n_stripes = rng.randint(2, 8)
        orient = rng.choice(orientations)
        colors = [_rand_rgb(rng) for _ in range(n_stripes)]
        proportions = [rng.random() + 0.1 for _ in range(n_stripes)]
        total = sum(proportions)
        proportions = [p / total for p in proportions]
        img = Image.new("RGB", (SIZE, SIZE))
        pixels = img.load()
        for y in range(SIZE):
            for x in range(SIZE):
                if orient == "horizontal":
                    t = y / SIZE
                elif orient == "vertical":
                    t = x / SIZE
                else:
                    t = ((x + y) / (2 * SIZE)) % 1.0
                cumulative = 0.0
                chosen = colors[-1]
                for k, prop in enumerate(proportions):
                    cumulative += prop
                    if t <= cumulative:
                        chosen = colors[k]
                        break
                pixels[x, y] = chosen
        img.save(out_dir / f"{idx:04d}.png")
    return n


def gen_noise(rng: random.Random, n: int, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    import struct

    def clamp(v): return max(0, min(255, int(v)))

    gaussian_configs = [
        ((255, 255, 255), 30), ((128, 128, 128), 30), ((0, 0, 0), 30),
        ((255, 255, 255), 60), ((128, 128, 128), 60), ((0, 0, 0), 60),
        ((255, 255, 255), 90), ((128, 128, 128), 90), ((0, 0, 0), 90),
    ]
    sp_configs = [
        ((128, 128, 128), 0.05), ((128, 128, 128), 0.15), ((128, 128, 128), 0.30),
    ]

    for idx in range(n):
        img = Image.new("RGB", (SIZE, SIZE))
        pixels = img.load()
        gauss_count = len(gaussian_configs)
        sp_count = len(sp_configs)

        if idx < gauss_count:
            bg, sigma = gaussian_configs[idx]
            for y in range(SIZE):
                for x in range(SIZE):
                    r = clamp(bg[0] + rng.gauss(0, sigma))
                    g = clamp(bg[1] + rng.gauss(0, sigma))
                    b = clamp(bg[2] + rng.gauss(0, sigma))
                    pixels[x, y] = (r, g, b)
        elif idx < gauss_count + sp_count:
            bg, density = sp_configs[idx - gauss_count]
            for y in range(SIZE):
                for x in range(SIZE):
                    v = rng.random()
                    if v < density / 2:
                        pixels[x, y] = (0, 0, 0)
                    elif v < density:
                        pixels[x, y] = (255, 255, 255)
                    else:
                        pixels[x, y] = bg
        else:
            for y in range(SIZE):
                for x in range(SIZE):
                    pixels[x, y] = _rand_rgb(rng)

        img.save(out_dir / f"{idx:04d}.png")
    return n


def _contrasting_color(bg: tuple) -> tuple:
    """Return black or white, whichever has more contrast with bg."""
    lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    return (0, 0, 0) if lum > 128 else (255, 255, 255)


def _draw_five_star(draw: ImageDraw.Draw, cx: float, cy: float, r: float, color: tuple):
    """Draw a filled five-pointed star centered at (cx,cy) with circumradius r."""
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * 0.382
        points.append((cx + radius * math.cos(angle), cy - radius * math.sin(angle)))
    draw.polygon(points, fill=color)


def _draw_cross(draw: ImageDraw.Draw, cx: float, cy: float, r: float, color: tuple):
    arm = r * 0.35
    shaft = r * 0.9
    draw.rectangle([cx - arm, cy - shaft, cx + arm, cy + shaft], fill=color)
    draw.rectangle([cx - shaft, cy - arm, cx + shaft, cy + arm], fill=color)


def _draw_equilateral_triangle(draw: ImageDraw.Draw, cx: float, cy: float, r: float, color: tuple):
    pts = []
    for i in range(3):
        angle = math.pi / 2 + i * 2 * math.pi / 3
        pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    draw.polygon(pts, fill=color)


def gen_geometric(rng: random.Random, n: int, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    shape_types = ["circle", "cross", "star", "triangle", "rectangle"]

    for idx in range(n):
        # Background: solid or simple gradient
        if rng.random() < 0.5:
            bg_color = _rand_rgb(rng)
            img = Image.new("RGB", (SIZE, SIZE), bg_color)
        else:
            h1, h2 = rng.random(), rng.random()
            c1, c2 = _hue_to_rgb(h1), _hue_to_rgb(h2)
            img = Image.new("RGB", (SIZE, SIZE))
            px = img.load()
            orient = rng.choice(["horizontal", "vertical"])
            for y in range(SIZE):
                for x in range(SIZE):
                    t = (x / (SIZE - 1)) if orient == "horizontal" else (y / (SIZE - 1))
                    r = int(c1[0] + t * (c2[0] - c1[0]))
                    g = int(c1[1] + t * (c2[1] - c1[1]))
                    b = int(c1[2] + t * (c2[2] - c1[2]))
                    px[x, y] = (r, g, b)
            bg_color = (
                int(c1[0] * 0.5 + c2[0] * 0.5),
                int(c1[1] * 0.5 + c2[1] * 0.5),
                int(c1[2] * 0.5 + c2[2] * 0.5),
            )

        draw = ImageDraw.Draw(img)
        fg_color = _contrasting_color(bg_color)

        n_shapes = rng.randint(1, 2)
        for _ in range(n_shapes):
            shape = rng.choice(shape_types)
            cx = rng.uniform(SIZE * 0.2, SIZE * 0.8)
            cy = rng.uniform(SIZE * 0.2, SIZE * 0.8)
            r = rng.uniform(SIZE * 0.08, SIZE * 0.25)

            if shape == "circle":
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fg_color)
            elif shape == "cross":
                _draw_cross(draw, cx, cy, r, fg_color)
            elif shape == "star":
                _draw_five_star(draw, cx, cy, r, fg_color)
            elif shape == "triangle":
                _draw_equilateral_triangle(draw, cx, cy, r, fg_color)
            elif shape == "rectangle":
                w = rng.uniform(r * 0.5, r * 2.0)
                h = rng.uniform(r * 0.5, r * 2.0)
                draw.rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], fill=fg_color)

        img.save(out_dir / f"{idx:04d}.png")
    return n


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic negative eval images.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count-stripes", type=int, default=150)
    parser.add_argument("--count-geometric", type=int, default=150)
    parser.add_argument("--count-other", type=int, default=100)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.output)

    recipes = [
        ("solid_color", args.count_other, gen_solid_color),
        ("gradient",    args.count_other, gen_gradient),
        ("stripes",     args.count_stripes, gen_stripes),
        ("noise",       args.count_other, gen_noise),
        ("geometric",   args.count_geometric, gen_geometric),
    ]

    total = 0
    for name, count, fn in recipes:
        sub = out / name
        n = fn(rng, count, sub)
        total += n
        print(f"  {name}: {n} images -> {sub}")

    print(f"Done. {total} images total in {out}")


if __name__ == "__main__":
    main()
