#!/usr/bin/env python3
"""Render the 1024x1024 'The World Today' editorial front page PNG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

CANVAS_SIZE = 1024
OUTER_MARGIN = 32
COLUMN_GAP = 16


@dataclass(frozen=True)
class Palette:
    page_bg: tuple[int, int, int] = (11, 15, 23)
    card_bg: tuple[int, int, int] = (16, 22, 33)
    card_border: tuple[int, int, int] = (40, 50, 66)
    scrim_rgb: tuple[int, int, int] = (10, 14, 22)
    accent_gold: tuple[int, int, int] = (232, 188, 64)
    ink_white: tuple[int, int, int] = (247, 249, 252)
    ink_body: tuple[int, int, int] = (212, 220, 232)
    ink_muted: tuple[int, int, int] = (145, 156, 173)
    footer_rule: tuple[int, int, int] = (58, 69, 88)


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x2 - 1, self.y2 - 1)

    def split_columns(self, gap: int) -> tuple[Rect, Rect]:
        col_w = (self.w - gap) // 2
        left = Rect(self.x, self.y, col_w, self.h)
        right = Rect(self.x + col_w + gap, self.y, self.w - col_w - gap, self.h)
        return left, right


@dataclass(frozen=True)
class PanelStory:
    image_file: str
    focal: tuple[float, float]
    kicker: str
    headline: str
    body: str


@dataclass(frozen=True)
class BriefStory:
    kicker: str
    headline: str


FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "masthead": (
        "/usr/share/fonts/truetype/noto/NotoSans-SemiCondensedBlack.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "display": (
        "/usr/share/fonts/truetype/noto/NotoSans-SemiCondensedExtraBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-CondensedBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "bold": (
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "semibold": (
        "/usr/share/fonts/truetype/noto/NotoSans-SemiBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "regular": (
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
}


class FontBank:
    """Resolves and caches TrueType fonts by semantic role and pixel size."""

    def __init__(self, candidates: dict[str, tuple[str, ...]]) -> None:
        self._resolved: dict[str, str] = {}
        for role, paths in candidates.items():
            found = next((p for p in paths if Path(p).is_file()), None)
            if found is None:
                raise FileNotFoundError(f"No font found for role '{role}': {paths}")
            self._resolved[role] = found
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def get(self, role: str, size: int) -> ImageFont.FreeTypeFont:
        key = (role, size)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(self._resolved[role], size=size)
        return self._cache[key]


def cover_crop(
    source: Image.Image,
    target_w: int,
    target_h: int,
    focal: tuple[float, float] = (0.5, 0.5),
) -> Image.Image:
    """Resize and crop an image to fill (target_w, target_h) around focal point."""
    src_w, src_h = source.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        crop_h = src_h
        crop_w = int(round(src_h * target_ratio))
    else:
        crop_w = src_w
        crop_h = int(round(src_w / target_ratio))

    fx, fy = focal
    left = int(round((src_w - crop_w) * fx))
    top = int(round((src_h - crop_h) * fy))
    left = max(0, min(src_w - crop_w, left))
    top = max(0, min(src_h - crop_h, top))

    cropped = source.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)


def apply_bottom_scrim(
    photo: Image.Image,
    start_frac: float,
    solid_frac: float,
    max_alpha: int,
    scrim_rgb: tuple[int, int, int],
    power: float = 1.35,
) -> Image.Image:
    """Composite a smooth bottom-to-top dark scrim over an RGB photo.

    The opacity ramps from 0 at start_frac up to max_alpha at solid_frac and
    holds at max_alpha through the bottom edge for high text contrast.
    """
    w, h = photo.size
    start_y = int(round(h * start_frac))
    solid_y = max(start_y + 1, int(round(h * solid_frac)))
    span = solid_y - start_y

    # Build a 1-pixel-wide vertical alpha ramp and stretch it horizontally.
    ramp = Image.new("L", (1, h), 0)
    ramp_px = ramp.load()
    for y in range(start_y, h):
        if y >= solid_y:
            alpha = max_alpha
        else:
            t = (y - start_y) / span
            alpha = int(round(max_alpha * (t**power)))
        ramp_px[0, y] = max(0, min(255, alpha))
    alpha_mask = ramp.resize((w, h), Image.Resampling.NEAREST)

    overlay = Image.new("RGBA", (w, h), (*scrim_rgb, 0))
    overlay.putalpha(alpha_mask)

    composited = Image.alpha_composite(photo.convert("RGBA"), overlay)
    return composited.convert("RGB")


def wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Wrap text on word boundaries so each line fits within max_width."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        trial = " ".join((*current, word))
        if not current or draw.textlength(trial, font=font) <= max_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))
    return lines


def fit_single_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    fonts: FontBank,
    role: str,
    max_size: int,
    min_size: int,
    max_width: int,
) -> ImageFont.FreeTypeFont:
    """Choose the largest font size in [min_size, max_size] fitting on one line."""
    for size in range(max_size, min_size - 1, -1):
        candidate = fonts.get(role, size)
        if draw.textlength(text, font=candidate) <= max_width:
            return candidate
    return fonts.get(role, min_size)


def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: Iterable[str],
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    line_step: int,
) -> int:
    """Draw lines starting at (x, y) and return y after the last line."""
    cursor_y = y
    for line in lines:
        draw.text((x, cursor_y), line, font=font, fill=fill)
        cursor_y += line_step
    return cursor_y


def render_masthead(
    draw: ImageDraw.ImageDraw,
    fonts: FontBank,
    palette: Palette,
    bounds: Rect,
) -> None:
    title_font = fonts.get("masthead", 56)
    draw.text((bounds.x, bounds.y - 2), "THE WORLD TODAY", font=title_font, fill=palette.ink_white)

    sub_y = bounds.y + 62
    tagline_font = fonts.get("bold", 15)
    date_font = fonts.get("bold", 18)

    draw.text(
        (bounds.x, sub_y + 3),
        "THE DAY IN ONE PICTURE",
        font=tagline_font,
        fill=palette.accent_gold,
    )

    date_text = "TUESDAY 24 NOVEMBER 2026"
    date_w = draw.textlength(date_text, font=date_font)
    draw.text(
        (bounds.x2 - date_w, sub_y),
        date_text,
        font=date_font,
        fill=palette.ink_white,
    )

    rule_y = bounds.y2 - 3
    draw.rectangle((bounds.x, rule_y, bounds.x2 - 1, rule_y + 2), fill=palette.accent_gold)


def render_hero(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    fonts: FontBank,
    palette: Palette,
    bounds: Rect,
    assets_dir: Path,
) -> None:
    inner = Rect(bounds.x + 1, bounds.y + 1, bounds.w - 2, bounds.h - 2)
    with Image.open(assets_dir / "hero-refinery.jpg") as raw:
        photo = cover_crop(raw.convert("RGB"), inner.w, inner.h, focal=(0.5, 0.28))

    scrimmed = apply_bottom_scrim(
        photo,
        start_frac=0.38,
        solid_frac=0.80,
        max_alpha=240,
        scrim_rgb=palette.scrim_rgb,
        power=1.35,
    )
    canvas.paste(scrimmed, (inner.x, inner.y))
    draw.rectangle(bounds.box, outline=palette.card_border, width=1)

    pad_x = 22
    text_x = inner.x + pad_x
    text_w = inner.w - 2 * pad_x

    kicker = "MOSCOW · OIL WAR"
    headline = "PUTIN VOWS RETALIATION OVER REFINERY STRIKES"
    subline = (
        "Putin says Ukraine keeps striking Russian oil refineries despite President Trump's "
        'requests to stop, warning "retaliatory measures are inevitable"; Kyiv replies: '
        '"Stop complaining. End the war." Ukrainian drones have cut Russian refining output '
        "by about 45% since late October."
    )

    kicker_font = fonts.get("bold", 15)
    headline_font = fit_single_line(draw, headline, fonts, "display", 36, 26, text_w - 12)
    sub_font = fonts.get("regular", 16)

    sub_lines = wrap_lines(draw, subline, sub_font, min(text_w, 780))
    sub_step = 23
    sub_block_h = len(sub_lines) * sub_step

    bottom_pad = 18
    sub_y = inner.y2 - bottom_pad - sub_block_h
    headline_y = sub_y - 48
    kicker_y = headline_y - 25

    draw.text((text_x, kicker_y), kicker, font=kicker_font, fill=palette.accent_gold)
    draw.text((text_x, headline_y), headline, font=headline_font, fill=palette.ink_white)
    draw_lines(draw, sub_lines, text_x, sub_y, sub_font, palette.ink_body, sub_step)


def render_panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    fonts: FontBank,
    palette: Palette,
    bounds: Rect,
    story: PanelStory,
    assets_dir: Path,
) -> None:
    draw.rectangle(bounds.box, fill=palette.card_bg, outline=palette.card_border, width=1)

    photo_h = 148
    photo_rect = Rect(bounds.x + 1, bounds.y + 1, bounds.w - 2, photo_h)
    with Image.open(assets_dir / story.image_file) as raw:
        photo = cover_crop(raw.convert("RGB"), photo_rect.w, photo_rect.h, focal=story.focal)

    faded = apply_bottom_scrim(
        photo,
        start_frac=0.65,
        solid_frac=0.98,
        max_alpha=250,
        scrim_rgb=palette.card_bg,
        power=1.4,
    )
    canvas.paste(faded, (photo_rect.x, photo_rect.y))

    pad_x = 16
    text_x = bounds.x + pad_x
    text_w = bounds.w - 2 * pad_x

    kicker_font = fonts.get("bold", 13)
    headline_font = fit_single_line(draw, story.headline, fonts, "display", 21, 15, text_w)
    body_font = fonts.get("regular", 14)

    kicker_y = photo_rect.y2 - 2
    headline_y = kicker_y + 20
    body_y = headline_y + 29

    draw.text((text_x, kicker_y), story.kicker, font=kicker_font, fill=palette.accent_gold)
    draw.text((text_x, headline_y), story.headline, font=headline_font, fill=palette.ink_white)

    body_lines = wrap_lines(draw, story.body, body_font, text_w)
    draw_lines(draw, body_lines, text_x, body_y, body_font, palette.ink_body, line_step=19)


def render_brief_strip(
    draw: ImageDraw.ImageDraw,
    fonts: FontBank,
    palette: Palette,
    bounds: Rect,
    brief: BriefStory,
) -> None:
    draw.rectangle(bounds.box, fill=palette.card_bg, outline=palette.card_border, width=1)
    draw.rectangle(
        (bounds.x, bounds.y, bounds.x2 - 1, bounds.y + 3),
        fill=palette.accent_gold,
    )

    pad_x = 16
    text_x = bounds.x + pad_x
    text_w = bounds.w - 2 * pad_x

    kicker_font = fonts.get("bold", 12)
    headline_font = fonts.get("bold", 17)

    kicker_y = bounds.y + 13
    headline_y = kicker_y + 20

    draw.text((text_x, kicker_y), brief.kicker, font=kicker_font, fill=palette.accent_gold)
    lines = wrap_lines(draw, brief.headline, headline_font, text_w - 8)
    draw_lines(draw, lines, text_x, headline_y, headline_font, palette.ink_white, line_step=23)


def render_footer(
    draw: ImageDraw.ImageDraw,
    fonts: FontBank,
    palette: Palette,
    bounds: Rect,
    text: str,
) -> None:
    draw.line((bounds.x, bounds.y, bounds.x2 - 1, bounds.y), fill=palette.footer_rule, width=1)
    footer_font = fit_single_line(draw, text, fonts, "regular", 13, 10, bounds.w)
    draw.text((bounds.x, bounds.y + 12), text, font=footer_font, fill=palette.ink_muted)


def compose_front_page(assets_dir: Path, output_path: Path) -> None:
    palette = Palette()
    fonts = FontBank(FONT_CANDIDATES)

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), palette.page_bg)
    draw = ImageDraw.Draw(canvas)

    content_w = CANVAS_SIZE - 2 * OUTER_MARGIN

    masthead_rect = Rect(OUTER_MARGIN, 18, content_w, 94)
    hero_rect = Rect(OUTER_MARGIN, 124, content_w, 404)
    panels_rect = Rect(OUTER_MARGIN, 542, content_w, 308)
    briefs_rect = Rect(OUTER_MARGIN, 864, content_w, 94)
    footer_rect = Rect(OUTER_MARGIN, 974, content_w, 34)

    render_masthead(draw, fonts, palette, masthead_rect)
    render_hero(canvas, draw, fonts, palette, hero_rect, assets_dir)

    left_panel_rect, right_panel_rect = panels_rect.split_columns(COLUMN_GAP)
    left_story = PanelStory(
        image_file="panel-chess.jpg",
        focal=(0.5, 0.55),
        kicker="GENEVA · WORLD CHESS CHAMPIONSHIP",
        headline="GAME 1 ENDS IN 38-MOVE DRAW",
        body=(
            "Sindarov (White) and champion Gukesh drew their Berlin Defence opener in "
            "38 moves; Gukesh held firm despite trailing by 50 minutes on the clock, and "
            "a mistaken draw claim cost Sindarov a two-minute penalty. Score 0.5-0.5; "
            "Game 2 is Wednesday with Gukesh White."
        ),
    )
    right_story = PanelStory(
        image_file="panel-gaza.jpg",
        focal=(0.5, 0.48),
        kicker="GAZA CITY · AIRSTRIKE",
        headline="ISRAELI STRIKE KILLS HAMAS SECURITY CHIEF",
        body=(
            "An Israeli airstrike on Gaza City killed Naeem Abu Nahel, director of "
            "Hamas's internal security apparatus, two months after he took the post; "
            "both sides confirmed his death."
        ),
    )
    render_panel(canvas, draw, fonts, palette, left_panel_rect, left_story, assets_dir)
    render_panel(canvas, draw, fonts, palette, right_panel_rect, right_story, assets_dir)

    left_brief_rect, right_brief_rect = briefs_rect.split_columns(COLUMN_GAP)
    render_brief_strip(
        draw,
        fonts,
        palette,
        left_brief_rect,
        BriefStory(
            kicker="NEPAL · EARTHQUAKE",
            headline="NEPAL: MAGNITUDE 5.6 QUAKE SHAKES KOSHI PROVINCE NEAR CHINA BORDER",
        ),
    )
    render_brief_strip(
        draw,
        fonts,
        palette,
        right_brief_rect,
        BriefStory(
            kicker="WALL STREET · MARKETS",
            headline="WALL STREET SURGES AS HUANG RETURNS TO NVIDIA — NASDAQ JUMPS 6.51%",
        ),
    )

    footer_text = (
        'IRAN VOWS TO RESIST US NAVAL BLOCKADE WITH "ALL ITS TOOLS"; '
        "SINGER PARASTOO AHMADI FLOGGED 74 TIMES"
    )
    render_footer(draw, fonts, palette, footer_rect, footer_text)

    canvas.save(output_path, format="PNG", optimize=True, compress_level=9)


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    compose_front_page(repo_root / "assets", repo_root / "entry.png")


if __name__ == "__main__":
    main()
