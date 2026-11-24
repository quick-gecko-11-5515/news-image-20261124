#!/usr/bin/env python3
"""Deterministic front-page composer for The World Today — Tuesday 24 November 2026.

Renders a 1024x1024 newspaper front page to `entry.png` next to this script,
combining editorial photography assets with typographic layout validation,
gradient scrims, and deterministic PNG compression under 1 MiB.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

REPO_DIR = Path(__file__).resolve().parent
ASSETS_DIR = REPO_DIR / "assets"
OUTPUT_PNG = REPO_DIR / "entry.png"

CANVAS_SIZE = 1024
MAX_PNG_BYTES = 1_048_576

FONT_DIR = Path("/usr/share/fonts/truetype/noto")
FONT_MAP = {
    "black": FONT_DIR / "NotoSans-Black.ttf",
    "extrabold": FONT_DIR / "NotoSans-ExtraBold.ttf",
    "bold": FONT_DIR / "NotoSans-Bold.ttf",
    "semibold": FONT_DIR / "NotoSans-SemiBold.ttf",
    "medium": FONT_DIR / "NotoSans-Medium.ttf",
    "regular": FONT_DIR / "NotoSans-Regular.ttf",
}

# Editorial dark-slate broadsheet palette
PALETTE = {
    "bg": (11, 15, 22),
    "card": (18, 24, 34),
    "card_border": (40, 50, 66),
    "gold": (222, 182, 62),
    "masthead": (246, 248, 252),
    "white": (255, 255, 255),
    "date": (234, 240, 248),
    "body": (224, 231, 240),
    "brief": (242, 246, 252),
    "rule": (74, 86, 104),
    "footer": (176, 188, 204),
    "scrim": (7, 10, 16),
}

# Verified news content for Tuesday 24 November 2026
EDITION_DATE = "TUESDAY 24 NOVEMBER 2026"
HERO_KICKER = "MEDITERRANEAN · NAVAL WARFARE"
HERO_HEADLINE = "UKRAINE WAR REACHES THE MEDITERRANEAN"
HERO_SUBLINE = (
    "President Zelenskyy confirms Ukraine sank Russia's corvette Merkury off "
    "Benghazi, Libya, with seven sea drones; the cargo ship MV Angara was also "
    "hit — the war's reach now extends far beyond the Black Sea."
)

LEFT_KICKER = "GENEVA · WORLD CHESS CHAMPIONSHIP"
LEFT_HEADLINE = "WORLD CHESS TITLE MATCH BEGINS"
LEFT_BODY = (
    "Defending champion Gukesh of India faces challenger Sindarov of Uzbekistan "
    "in Game 1 of the World Chess Championship in Geneva today."
)

RIGHT_KICKER = "BRUSSELS · EUROPEAN COMMISSION"
RIGHT_HEADLINE = "EU PROPOSES 22ND RUSSIA SANCTIONS"
RIGHT_BODY = (
    "The European Commission's new package would ban Russian teams and athletes "
    "from EU events and targets banks and crypto platforms."
)

BRIEFS = [
    ("EUROPE · PROTESTS", "LISBON: THOUSANDS MARCH OVER COST OF LIVING"),
    ("UKRAINE · AIR STRIKES", "RUSSIAN DRONES STRIKE KYIV REGION; SEVERAL MISSING"),
]

FOOTER_LINE = "COP31 AFTERMATH: ANTALYA TALKS ENDED WITHOUT A DEAL"


@dataclass(frozen=True)
class Rect:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


class LayoutValidator:
    """Tracks every rendered text box to catch clipping or overlaps."""

    def __init__(self) -> None:
        self.boxes: list[tuple[str, tuple[int, int, int, int]]] = []
        self.issues: list[str] = []

    def draw_text(
        self,
        draw: ImageDraw.ImageDraw,
        name: str,
        x: int,
        y: int,
        text: str,
        fnt: ImageFont.FreeTypeFont,
        fill: tuple[int, int, int],
        bounds: Rect,
        align_right: bool = False,
    ) -> tuple[int, int, int, int]:
        if align_right:
            raw = draw.textbbox((0, y), text, font=fnt)
            x = bounds.x1 - raw[2]
        bbox = draw.textbbox((x, y), text, font=fnt)
        if bbox[0] < bounds.x0:
            x += bounds.x0 - bbox[0]
            bbox = draw.textbbox((x, y), text, font=fnt)

        overflows = []
        if bbox[0] < bounds.x0:
            overflows.append(f"left={bbox[0]}<{bounds.x0}")
        if bbox[1] < bounds.y0:
            overflows.append(f"top={bbox[1]}<{bounds.y0}")
        if bbox[2] > bounds.x1:
            overflows.append(f"right={bbox[2]}>{bounds.x1}")
        if bbox[3] > bounds.y1:
            overflows.append(f"bottom={bbox[3]}>{bounds.y1}")
        if overflows:
            self.issues.append(f"CLIP {name}: {', '.join(overflows)} ({bbox})")

        for other_name, ob in self.boxes:
            if bbox[0] < ob[2] and bbox[2] > ob[0] and bbox[1] < ob[3] and bbox[3] > ob[1]:
                self.issues.append(f"OVERLAP {name} vs {other_name}: {bbox} / {ob}")

        self.boxes.append((name, bbox))
        draw.text((x, y), text, font=fnt, fill=fill)
        return bbox


def load_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_MAP[weight]
    return ImageFont.truetype(str(path), size)


def fit_cover(
    img: Image.Image,
    target_w: int,
    target_h: int,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
    zoom: float = 1.0,
) -> Image.Image:
    """Resize preserving aspect ratio to completely cover target_w x target_h."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h) * zoom
    scaled_w = max(target_w, round(src_w * scale))
    scaled_h = max(target_h, round(src_h * scale))
    resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    left = round((scaled_w - target_w) * focus_x)
    top = round((scaled_h - target_h) * focus_y)
    left = max(0, min(left, scaled_w - target_w))
    top = max(0, min(top, scaled_h - target_h))
    return resized.crop((left, top, left + target_w, top + target_h))


def build_gradient_scrim(
    width: int,
    height: int,
    fade_start_ratio: float,
    solid_start_ratio: float,
    peak_alpha: int,
    rgb: tuple[int, int, int],
) -> Image.Image:
    """Create a smooth vertical gradient scrim for legibility over photos."""
    strip = Image.new("RGBA", (1, height), (rgb[0], rgb[1], rgb[2], 0))
    fade_y = round(height * fade_start_ratio)
    solid_y = round(height * solid_start_ratio)
    for y in range(height):
        if y < fade_y:
            alpha = 0
        elif y < solid_y:
            t = (y - fade_y) / max(1, solid_y - fade_y)
            # Smoothstep ease-in-out
            eased = t * t * (3.0 - 2.0 * t)
            alpha = round(peak_alpha * eased)
        else:
            alpha = peak_alpha
        strip.putpixel((0, y), (rgb[0], rgb[1], rgb[2], alpha))
    return strip.resize((width, height), Image.Resampling.NEAREST)


def wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Greedy pixel-width word wrapper."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        width = draw.textbbox((0, 0), trial, font=fnt)[2]
        if current and width > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def wrap_balanced(
    draw: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Wrap words to max_width while balancing line widths to prevent orphan words."""
    greedy = wrap_lines(draw, text, fnt, max_width)
    target_lines = len(greedy)
    if target_lines <= 1:
        return greedy

    words = text.split()
    n = len(words)

    def line_width(start: int, end: int) -> int:
        return draw.textbbox((0, 0), " ".join(words[start:end]), font=fnt)[2]

    # Dynamic programming minimizing sum of squared slack across exactly target_lines
    inf = 10**18
    dp: list[list[int]] = [[inf] * (n + 1) for _ in range(target_lines + 1)]
    parent: list[list[int]] = [[-1] * (n + 1) for _ in range(target_lines + 1)]
    dp[0][0] = 0

    for line_idx in range(1, target_lines + 1):
        for end in range(line_idx, n + 1):
            for start in range(line_idx - 1, end):
                if dp[line_idx - 1][start] == inf:
                    continue
                w = line_width(start, end)
                if w > max_width:
                    continue
                slack = max_width - w
                # Extra penalty for a 1-word final line
                orphan_penalty = 500_000 if (line_idx == target_lines and end - start == 1) else 0
                cost = dp[line_idx - 1][start] + slack * slack + orphan_penalty
                if cost < dp[line_idx][end]:
                    dp[line_idx][end] = cost
                    parent[line_idx][end] = start

    if dp[target_lines][n] >= inf:
        return greedy

    result: list[str] = []
    pos = n
    for line_idx in range(target_lines, 0, -1):
        prev = parent[line_idx][pos]
        result.append(" ".join(words[prev:pos]))
        pos = prev
    result.reverse()
    return result


def draw_panel_photo(
    canvas: Image.Image,
    asset_name: str,
    rect: Rect,
    focus_y: float,
    fade_start: float,
    solid_start: float,
    peak_alpha: int,
    zoom: float = 1.0,
) -> None:
    photo = Image.open(ASSETS_DIR / asset_name).convert("RGBA")
    cropped = fit_cover(
        photo,
        rect.width,
        rect.height,
        focus_x=0.5,
        focus_y=focus_y,
        zoom=zoom,
    )
    scrim = build_gradient_scrim(
        rect.width,
        rect.height,
        fade_start_ratio=fade_start,
        solid_start_ratio=solid_start,
        peak_alpha=peak_alpha,
        rgb=PALETTE["scrim"],
    )
    blended = Image.alpha_composite(cropped, scrim)
    canvas.paste(blended, (rect.x0, rect.y0))


def draw_paragraph(
    draw: ImageDraw.ImageDraw,
    validator: LayoutValidator,
    prefix: str,
    x: int,
    start_y: int,
    line_step: int,
    lines: Iterable[str],
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    bounds: Rect,
) -> int:
    y = start_y
    for idx, line in enumerate(lines, start=1):
        validator.draw_text(draw, f"{prefix}.{idx}", x, y, line, fnt, fill, bounds)
        y += line_step
    return y


def compose_front_page() -> list[str]:
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), PALETTE["bg"] + (255,))
    validator = LayoutValidator()

    margin = 32
    gutter = 16
    full_w = CANVAS_SIZE - 2 * margin  # 960
    half_w = (full_w - gutter) // 2  # 472

    hero_rect = Rect(margin, 122, margin + full_w, 534)  # 960x412
    left_rect = Rect(margin, 548, margin + half_w, 836)  # 472x288
    right_rect = Rect(margin + half_w + gutter, 548, margin + full_w, 836)  # 472x288

    # Paste photography with refined framing and smooth bottom scrims
    draw_panel_photo(
        canvas,
        "hero-mediterranean.jpg",
        hero_rect,
        focus_y=0.34,
        fade_start=0.56,
        solid_start=0.74,
        peak_alpha=236,
        zoom=1.0,
    )
    draw_panel_photo(
        canvas,
        "panel-chess.jpg",
        left_rect,
        focus_y=0.68,
        fade_start=0.50,
        solid_start=0.66,
        peak_alpha=240,
        zoom=1.10,
    )
    draw_panel_photo(
        canvas,
        "panel-eu-sanctions.jpg",
        right_rect,
        focus_y=0.70,
        fade_start=0.50,
        solid_start=0.66,
        peak_alpha=240,
        zoom=1.10,
    )

    draw = ImageDraw.Draw(canvas)

    # Subtle framing borders around the three photo panels
    for rect in (hero_rect, left_rect, right_rect):
        draw.rectangle(
            [rect.x0, rect.y0, rect.x1 - 1, rect.y1 - 1],
            outline=PALETTE["card_border"],
            width=1,
        )

    # Masthead
    masthead_rect = Rect(margin, 14, margin + full_w, 112)
    validator.draw_text(
        draw,
        "masthead.title",
        margin,
        17,
        "THE WORLD TODAY",
        load_font("black", 52),
        PALETTE["masthead"],
        masthead_rect,
    )
    validator.draw_text(
        draw,
        "masthead.tagline",
        margin,
        82,
        "THE DAY IN ONE PICTURE",
        load_font("bold", 17),
        PALETTE["gold"],
        masthead_rect,
    )
    validator.draw_text(
        draw,
        "masthead.date",
        margin,
        79,
        EDITION_DATE,
        load_font("extrabold", 20),
        PALETTE["date"],
        masthead_rect,
        align_right=True,
    )
    draw.rectangle([margin, 110, margin + full_w, 113], fill=PALETTE["gold"])

    # Hero caption block — anchored cleanly near the bottom of the hero frame
    hero_text_bounds = Rect(hero_rect.x0 + 22, hero_rect.y0 + 258, hero_rect.x1 - 22, hero_rect.y1 - 14)
    validator.draw_text(
        draw,
        "hero.kicker",
        hero_text_bounds.x0,
        390,
        HERO_KICKER,
        load_font("bold", 16),
        PALETTE["gold"],
        hero_text_bounds,
    )
    validator.draw_text(
        draw,
        "hero.headline",
        hero_text_bounds.x0,
        414,
        HERO_HEADLINE,
        load_font("extrabold", 35),
        PALETTE["white"],
        hero_text_bounds,
    )
    hero_sub_font = load_font("regular", 18)
    hero_lines = wrap_balanced(draw, HERO_SUBLINE, hero_sub_font, hero_text_bounds.width)
    draw_paragraph(
        draw,
        validator,
        "hero.sub",
        hero_text_bounds.x0,
        464,
        26,
        hero_lines,
        hero_sub_font,
        PALETTE["body"],
        hero_text_bounds,
    )

    # Secondary side panels
    panel_specs = [
        ("left", left_rect, LEFT_KICKER, LEFT_HEADLINE, LEFT_BODY),
        ("right", right_rect, RIGHT_KICKER, RIGHT_HEADLINE, RIGHT_BODY),
    ]
    panel_kicker_font = load_font("bold", 12)
    panel_head_font = load_font("extrabold", 20)
    panel_body_font = load_font("regular", 14)

    for tag, rect, kicker, headline, body in panel_specs:
        inner = Rect(rect.x0 + 16, rect.y0 + 156, rect.x1 - 16, rect.y1 - 10)
        validator.draw_text(
            draw,
            f"{tag}.kicker",
            inner.x0,
            rect.y0 + 162,
            kicker,
            panel_kicker_font,
            PALETTE["gold"],
            inner,
        )
        validator.draw_text(
            draw,
            f"{tag}.headline",
            inner.x0,
            rect.y0 + 181,
            headline,
            panel_head_font,
            PALETTE["white"],
            inner,
        )
        body_lines = wrap_balanced(draw, body, panel_body_font, inner.width)
        draw_paragraph(
            draw,
            validator,
            f"{tag}.body",
            inner.x0,
            rect.y0 + 213,
            20,
            body_lines,
            panel_body_font,
            PALETTE["body"],
            inner,
        )

    # Briefs strip (two aligned columns matching the side-panel grid)
    brief_top = 852
    brief_bottom = 954
    brief_label_font = load_font("bold", 13)
    brief_text_font = load_font("bold", 18)

    for idx, (label, headline) in enumerate(BRIEFS):
        bx0 = margin + idx * (half_w + gutter)
        bx1 = bx0 + half_w
        card = Rect(bx0, brief_top, bx1, brief_bottom)
        draw.rectangle(card.as_tuple(), fill=PALETTE["card"], outline=PALETTE["card_border"], width=1)
        draw.rectangle([bx0, brief_top, bx1, brief_top + 3], fill=PALETTE["gold"])

        inner = Rect(bx0 + 16, brief_top + 10, bx1 - 16, brief_bottom - 10)
        validator.draw_text(
            draw,
            f"brief{idx + 1}.label",
            inner.x0,
            brief_top + 13,
            label,
            brief_label_font,
            PALETTE["gold"],
            inner,
        )
        wrapped = wrap_balanced(draw, headline, brief_text_font, inner.width)
        draw_paragraph(
            draw,
            validator,
            f"brief{idx + 1}.text",
            inner.x0,
            brief_top + 38,
            24,
            wrapped,
            brief_text_font,
            PALETTE["brief"],
            inner,
        )

    # Footer aftermath strip
    draw.rectangle([margin, 968, margin + full_w, 969], fill=PALETTE["rule"])
    footer_rect = Rect(margin, 972, margin + full_w, 1012)
    validator.draw_text(
        draw,
        "footer.aftermath",
        margin,
        981,
        FOOTER_LINE,
        load_font("medium", 13),
        PALETTE["footer"],
        footer_rect,
    )

    # Save deterministic PNG under 1 MiB
    rgb = canvas.convert("RGB")
    rgb.save(OUTPUT_PNG, format="PNG", optimize=True)
    size = OUTPUT_PNG.stat().st_size
    print(f"RGB PNG size: {size} bytes")
    if size > MAX_PNG_BYTES:
        quantized = rgb.quantize(
            colors=256,
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        quantized.save(OUTPUT_PNG, format="PNG", optimize=True)
        size = OUTPUT_PNG.stat().st_size
        print(f"Quantized 256-color PNG size: {size} bytes")

    return validator.issues


def main() -> int:
    issues = compose_front_page()
    if issues:
        for item in issues:
            print(f"LAYOUT ISSUE: {item}")
        return 1
    print("Layout validation passed with 0 issues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
