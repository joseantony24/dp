import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import click
from PIL import Image, ImageDraw, ImageFont


# Fixed canvas size to match requested portrait layout
CANVAS_WIDTH = 1220
CANVAS_HEIGHT = 2712

# Four cricket roles in column order
ROLE_ORDER = ["WK", "BAT", "ALL", "BOWL"]


@dataclass
class Combination:
    title: str
    roles: Dict[str, List[str]]  # role -> players
    formation: str | None
    ratio: str | None


def build_team_lookup(team_x: List[dict], team_y: List[dict]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for player in team_x:
        lookup[player["name"].strip().upper()] = "x"
    for player in team_y:
        lookup[player["name"].strip().upper()] = "y"
    return lookup


def _shorten_title(raw_first_line: str) -> str:
    """Extract just "Combination N" from noisy titles."""
    m = re.search(r"\bCombination\s+([0-9]+)\b", raw_first_line, flags=re.IGNORECASE)
    if m:
        return f"Combination {m.group(1)}"
    return raw_first_line.strip()


def parse_combinations(raw_text: str) -> List[Combination]:
    """Parse multiple combinations from the textarea-style input."""
    blocks = re.split(r"\n+={5,}\n+", raw_text.strip(), flags=re.MULTILINE)
    combinations: List[Combination] = []

    player_line_re = re.compile(r"^([A-Za-z0-9]+)\s*[-–]\s*(WK|BAT|ALL|BOWL)$", re.IGNORECASE)

    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        title = _shorten_title(lines[0])
        roles: Dict[str, List[str]] = {r: [] for r in ROLE_ORDER}
        formation: str | None = None
        ratio: str | None = None

        for ln in lines[1:]:
            if ln.lower().startswith("combination :"):
                formation = ln.split(":", 1)[1].strip()
                continue
            if ln.lower().startswith("ratio:"):
                ratio = ln.split(":", 1)[1].strip()
                continue

            m = player_line_re.match(ln.replace("—", "-").replace("–", "-"))
            if m:
                name, role = m.group(1).upper(), m.group(2).upper()
                roles[role].append(name)

        combinations.append(Combination(title=title, roles=roles, formation=formation, ratio=ratio))

    return combinations


def _load_font(preferred_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a good TTF font; fall back to PIL default if unavailable."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, preferred_size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, stroke_width: int = 0) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def render_combination_image(
    comb: Combination,
    team_lookup: Dict[str, str],
    out_path: str,
) -> None:
    """Render one combination in the desired portrait layout."""

    # Canvas and drawing context
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), color=(18, 102, 14))
    draw = ImageDraw.Draw(img)

    # Typography
    title_font = _load_font(80)
    header_font = _load_font(40)
    player_font = _load_font(48)
    small_font = _load_font(34)

    # Layout metrics
    top_margin = 40
    title_y = top_margin
    legend_top = title_y + 120
    sections_top = legend_top + 140
    side_padding = 28
    footer_height = 80

    # Title (centered) — only "Combination N"
    title_text = comb.title
    tw, th = _text_size(draw, title_text, title_font, stroke_width=2)
    draw.text(((CANVAS_WIDTH - tw) // 2, title_y), title_text, font=title_font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))

    # Legend (top-right)
    legend_x = CANVAS_WIDTH - side_padding - 420
    box = [legend_x, legend_top, CANVAS_WIDTH - side_padding, legend_top + 112]
    draw.rectangle(box, fill=(0, 0, 0))
    draw.text((legend_x + 16, legend_top + 10), "Legend:", font=small_font, fill=(255, 255, 255))
    draw.rectangle([legend_x + 16, legend_top + 54, legend_x + 16 + 56, legend_top + 54 + 36], fill=(255, 255, 255))
    draw.text((legend_x + 16 + 66, legend_top + 50), "Team X", font=small_font, fill=(255, 255, 255))
    draw.rectangle([legend_x + 200, legend_top + 54, legend_x + 200 + 56, legend_top + 54 + 36], fill=(0, 0, 0))
    draw.text((legend_x + 200 + 66, legend_top + 50), "Team Y", font=small_font, fill=(255, 255, 255))

    # Sectioned layout: for each role, draw heading then chips that wrap horizontally
    y_cursor = sections_top
    usable_width = CANVAS_WIDTH - side_padding * 2
    chip_w, chip_h = 260, 66
    gap_x, gap_y = 18, 22

    def draw_role_section(role_key: str, y: int) -> int:
        role_label = {"WK": "WICKET KEEPERS", "BAT": "BATSMEN", "ALL": "ALL ROUNDERS", "BOWL": "BOWLERS"}[role_key]
        # Role heading
        hw, hh = _text_size(draw, role_label, header_font)
        draw.text((side_padding, y), role_label, font=header_font, fill=(255, 255, 255))
        y += hh + 18

        # Wrap chips on one or two rows as needed
        names = comb.roles.get(role_key, [])
        if not names:
            return y + 10

        # Compute how many chips fit per row
        per_row = max(1, (usable_width + gap_x) // (chip_w + gap_x))
        row = 0
        col = 0
        for name in names:
            x = side_padding + col * (chip_w + gap_x)
            cy = y + row * (chip_h + gap_y)

            team_id = team_lookup.get(name.upper(), "x")
            chip_fill = (255, 255, 255) if team_id == "x" else (0, 0, 0)
            chip_outline = (0, 0, 0) if team_id == "x" else (255, 255, 255)
            draw.rounded_rectangle([x, cy, x + chip_w, cy + chip_h], radius=12, fill=chip_fill, outline=chip_outline, width=3)

            text_fill = (0, 0, 0) if team_id == "x" else (255, 255, 255)
            tw2, th2 = _text_size(draw, name, player_font)
            draw.text((x + (chip_w - tw2) // 2, cy + (chip_h - th2) // 2 - 2), name, font=player_font, fill=text_fill)

            col += 1
            if col >= per_row:
                col = 0
                row += 1

        # Advance y past last row of chips
        y += (row + 1) * (chip_h + gap_y)
        y += 24  # extra spacing before next section
        return y

    # Draw each role section stacked vertically
    for role in ROLE_ORDER:
        y_cursor = draw_role_section(role, y_cursor)

    player_bottom = y_cursor
    # Footer divider line
    draw.line([(side_padding, player_bottom), (CANVAS_WIDTH - side_padding, player_bottom)], fill=(255, 255, 255), width=3)

    # Footer information: Combination pattern and optional ratio
    footer_text = []
    if comb.formation:
        footer_text.append(f"Combination : {comb.formation}")
    if comb.ratio:
        footer_text.append(f"Ratio : {comb.ratio}")
    info = "  |  ".join(footer_text)
    if info:
        iw, ih = _text_size(draw, info, small_font)
        draw.text(((CANVAS_WIDTH - iw) // 2, player_bottom + (footer_height - ih) // 2), info, font=small_font, fill=(255, 255, 255))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


@click.command()
@click.option("--input", "input_path", type=click.Path(exists=True, dir_okay=False, readable=True), required=True, help="Path to combinations text file")
@click.option("--outdir", type=click.Path(file_okay=False, writable=True), default="/workspace/output", show_default=True)
@click.option("--prefix", type=str, default="combination_", show_default=True)
def main(input_path: str, outdir: str, prefix: str) -> None:
    """Generate one 1220x2712 PNG per combination with the requested styling."""
    from teams import team_x, team_y  # type: ignore

    team_lookup = build_team_lookup(team_x, team_y)
    with open(input_path, "r", encoding="utf-8") as f:
        raw = f.read()

    combinations = parse_combinations(raw)
    if not combinations:
        raise SystemExit("No combinations found in input.")

    os.makedirs(outdir, exist_ok=True)
    for idx, comb in enumerate(combinations, start=1):
        out_path = os.path.join(outdir, f"{prefix}{idx}.png")
        render_combination_image(comb, team_lookup, out_path)
        click.echo(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

