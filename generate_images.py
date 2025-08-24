import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import click
from PIL import Image, ImageDraw, ImageFont

# Roles in the display order
ROLE_ORDER = ["WK", "BAT", "ALL", "BOWL"]


@dataclass
class Combination:
    title: str
    roles: Dict[str, List[str]]  # role -> list of player names
    formation: str | None
    ratio: str | None


def build_team_lookup(team_x: List[dict], team_y: List[dict]) -> Dict[str, str]:
    """Return mapping playerName -> teamId ('x' or 'y')."""
    lookup: Dict[str, str] = {}
    for player in team_x:
        lookup[player["name"].strip()] = "x"
    for player in team_y:
        lookup[player["name"].strip()] = "y"
    return lookup


def parse_combinations(raw_text: str) -> List[Combination]:
    """Parse the provided multi-combination text into structured data.

    The parser is robust to extra blank lines. Player lines are of the form
    "A3-WK" or "B10-BOWL". We do not rely on blank lines to determine role; the
    role suffix determines the bucket. We stop reading a block when we hit a
    line starting with "Combination :" or "Ratio:" or a line of '='.
    """
    blocks = re.split(r"\n+={5,}\n+", raw_text.strip(), flags=re.MULTILINE)
    combinations: List[Combination] = []

    player_line_re = re.compile(r"^([A-Za-z0-9]+)\s*[-–]\s*(WK|BAT|ALL|BOWL)$", re.IGNORECASE)

    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0]
        roles: Dict[str, List[str]] = {r: [] for r in ROLE_ORDER}
        formation: str | None = None
        ratio: str | None = None

        for ln in lines[1:]:
            # Stop parsing players once summary lines begin
            if ln.lower().startswith("combination :"):
                formation = ln.split(":", 1)[1].strip()
                continue
            if ln.lower().startswith("ratio:"):
                ratio = ln.split(":", 1)[1].strip()
                continue

            m = player_line_re.match(ln.replace("—", "-").replace("–", "-"))
            if m:
                name, role = m.group(1).upper(), m.group(2).upper()
                if role in roles:
                    roles[role].append(name)
                else:
                    # Ignore unknown roles; keeps parser tolerant
                    pass

        combinations.append(Combination(title=title, roles=roles, formation=formation, ratio=ratio))

    return combinations


def _load_font(preferred_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a good TTF font; fall back to PIL's default if not available."""
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
    """Measure text size using textbbox (Pillow 10+ compatible)."""
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def render_combination_image(
    comb: Combination,
    team_lookup: Dict[str, str],
    out_path: str,
    image_width: int = 1280,
    cell_height: int = 54,
    header_height: int = 120,
    footer_height: int = 40,
    column_padding: int = 24,
    bg_color: Tuple[int, int, int] = (22, 122, 17),  # lush green
) -> None:
    """Render one combination to an image file."""
    # Calculate rows needed
    num_rows = max(len(comb.roles[role]) for role in ROLE_ORDER)
    image_height = header_height + num_rows * cell_height + footer_height

    img = Image.new("RGB", (image_width, image_height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Fonts
    title_font = _load_font(40)
    header_font = _load_font(28)
    player_font = _load_font(30)
    small_font = _load_font(22)

    # Title at top
    title_text_parts = [comb.title]
    meta = []
    if comb.formation:
        meta.append(f"Formation {comb.formation}")
    if comb.ratio:
        meta.append(f"Ratio {comb.ratio}")
    if meta:
        title_text_parts.append(" | ".join(meta))
    title_text = "  –  ".join(title_text_parts)

    # Centered title
    tw, th = _text_size(draw, title_text, title_font)
    draw.text(((image_width - tw) // 2, 16), title_text, font=title_font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))

    # Legend (top-right)
    legend_y = 16 + th + 8
    draw.rectangle([image_width - 300, legend_y - 6, image_width - 16, legend_y + 60], fill=(0, 0, 0, 40))
    draw.text((image_width - 288, legend_y), "Legend:", font=small_font, fill=(255, 255, 255))
    draw.text((image_width - 288, legend_y + 26), "Team X = White", font=small_font, fill=(255, 255, 255))
    # Second legend line for Team Y
    draw.text((image_width - 288, legend_y + 26 + 24), "Team Y = Black", font=small_font, fill=(0, 0, 0))

    # Column positions
    num_cols = len(ROLE_ORDER)
    col_width = (image_width - (num_cols + 1) * column_padding) // num_cols
    col_x = [column_padding + i * (col_width + column_padding) for i in range(num_cols)]

    # Column headers
    for idx, role in enumerate(ROLE_ORDER):
        x = col_x[idx]
        header_box = [x - 4, header_height - 44, x + col_width + 4, header_height - 8]
        draw.rectangle(header_box, outline=(245, 245, 245), width=2, fill=(18, 92, 14))
        header_text = {"WK": "WICKET KEEPERS", "BAT": "BATSMEN", "ALL": "ALL ROUNDERS", "BOWL": "BOWLERS"}[role]
        hw, hh = _text_size(draw, header_text, header_font)
        draw.text((x + (col_width - hw) // 2, header_height - 40), header_text, font=header_font, fill=(255, 255, 255))

    # Player rows
    for row in range(num_rows):
        y = header_height + row * cell_height
        for cidx, role in enumerate(ROLE_ORDER):
            x = col_x[cidx]
            names = comb.roles.get(role, [])
            name = names[row] if row < len(names) else ""
            # Cell background banding for readability
            if row % 2 == 0:
                draw.rectangle([x, y, x + col_width, y + cell_height], fill=(24, 104, 19))
            else:
                draw.rectangle([x, y, x + col_width, y + cell_height], fill=(28, 118, 22))

            if name:
                team_id = team_lookup.get(name, "x")
                fill = (255, 255, 255) if team_id == "x" else (0, 0, 0)
                stroke = (0, 0, 0) if team_id == "x" else (255, 255, 255)
                text = name
                tw, th = _text_size(draw, text, player_font)
                draw.text((x + 16, y + (cell_height - th) // 2), text, font=player_font, fill=fill, stroke_width=2, stroke_fill=stroke)

    # Footer divider
    draw.line([(column_padding, image_height - footer_height), (image_width - column_padding, image_height - footer_height)], fill=(255, 255, 255), width=2)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


@click.command()
@click.option("--input", "input_path", type=click.Path(exists=True, dir_okay=False, readable=True), required=True, help="Path to text file containing combinations.")
@click.option("--outdir", type=click.Path(file_okay=False, writable=True), default="/workspace/output", show_default=True)
@click.option("--width", "image_width", type=int, default=1280, show_default=True)
@click.option("--prefix", type=str, default="combination_", show_default=True)
@click.option("--open", "open_after", is_flag=True, help="Open the output directory after generation (if supported).")
def main(input_path: str, outdir: str, image_width: int, prefix: str, open_after: bool) -> None:
    """Generate one image per combination in the input file."""
    # Import teams from local teams.py
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
        render_combination_image(comb, team_lookup, out_path, image_width=image_width)
        click.echo(f"Wrote {out_path}")

    if open_after:
        try:
            if os.name == "posix":
                os.system(f"xdg-open '{outdir}' >/dev/null 2>&1 &")
            elif os.name == "nt":
                os.system(f"start {outdir}")
        except Exception:
            pass


if __name__ == "__main__":
    main()