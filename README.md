# Cricket Combination Image Generator

Generate images for team combinations with role-grouped columns and team-colored names.

- Team X players are drawn in white
- Team Y players are drawn in black
- Columns are ordered: Wicket Keepers, Batsmen, All Rounders, Bowlers
- Background is green; title includes formation and ratio if present

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Usage

Put your combinations text into a file, e.g. `sample_input.txt`, then run:

```bash
python generate_images.py --input /workspace/sample_input.txt --outdir /workspace/output --width 1280
```

Images are written to `/workspace/output/combination_#.png`.

## Customization

- Edit `teams.py` to change Team X and Team Y rosters
- Adjust `--width` to change image width; height adjusts automatically to number of rows
- Change colors or fonts inside `render_combination_image` in `generate_images.py`
