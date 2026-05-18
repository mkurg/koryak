from __future__ import annotations

import argparse
import csv
import html
import math
import os
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote


SCREEN_W = 1920
SCREEN_H = 1080
CANVAS_H = 1320
AOI_W = 850
AOI_H = 850
POST_ONSET_MS = 2000

EFIX_RE = re.compile(
    r"^EFIX\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([-\d.]+|\.)\s+([-\d.]+|\.)\s+([-\d.]+|\.)"
)
TRIAL_VAR_RE = re.compile(r"!V\s+TRIAL_VAR\s+(\S+)\s*(.*)$")


def normalize_participant_id(value: object) -> str:
    text = str(value).strip().upper().replace("К", "K")
    match = re.search(r"K\s*0*(\d+)", text)
    if not match:
        return text
    return f"K{int(match.group(1)):02d}"


def safe_stem(value: object) -> str:
    text = str(value)
    text = re.sub(r"\.[^.]+$", "", text)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    return text.strip("._-") or "item"


def parse_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text or text in {"-", "."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: object) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def parse_coord_pair(value: object) -> tuple[float | None, float | None]:
    if value is None:
        return None, None
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(value))
    if len(nums) < 2:
        return None, None
    return float(nums[0]), float(nums[1])


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        header = f.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG file: {path}")
    return struct.unpack(">II", header[16:24])


def find_stimuli(stimuli_dir: Path) -> dict[str, Path]:
    by_name: dict[str, Path] = {}
    for path in sorted(stimuli_dir.rglob("*.png")):
        by_name[path.name] = path
    return by_name


def load_behavior(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            participant = normalize_participant_id(row.get("participant's id", ""))
            image = str(row.get("image", "")).strip()
            if participant and image:
                rows.setdefault((participant, image), row)
    return rows


def parse_asc(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    trials: dict[int, dict[str, object]] = {}
    fixations: list[dict[str, object]] = []
    block = 0
    current_block: int | None = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.rstrip("\n")

            if raw.startswith("START"):
                block += 1
                current_block = block
                parts = raw.split()
                trials[current_block] = {
                    "block": current_block,
                    "start_time": parse_int(parts[1]) if len(parts) > 1 else None,
                    "end_time": None,
                    "display_time": None,
                    "asc_file": path.name,
                    "asc_stem": path.stem,
                }
                continue

            if raw.startswith("END"):
                parts = raw.split()
                if current_block is not None and len(parts) > 1:
                    trials.setdefault(current_block, {"block": current_block})["end_time"] = parse_int(parts[1])
                continue

            if raw.startswith("MSG"):
                parts = raw.split(maxsplit=2)
                if len(parts) < 3:
                    continue
                message_time = parse_int(parts[1])
                text = parts[2]
                if current_block is None:
                    continue
                trial = trials.setdefault(current_block, {"block": current_block})
                if "DISPLAY_SENTENCE" in text:
                    trial["display_time"] = message_time
                var_match = TRIAL_VAR_RE.search(text)
                if var_match:
                    trial[var_match.group(1)] = var_match.group(2).strip()
                continue

            fix_match = EFIX_RE.match(raw)
            if fix_match and current_block is not None:
                eye, start, end, duration, x, y, pupil = fix_match.groups()
                fixations.append(
                    {
                        "block": current_block,
                        "eye": eye,
                        "start": int(start),
                        "end": int(end),
                        "duration": int(duration),
                        "x": parse_float(x),
                        "y": parse_float(y),
                        "pupil": parse_float(pupil),
                    }
                )

    return list(trials.values()), fixations


def classify_aoi(x: float | None, y: float | None, agent_coord: object, patient_coord: object) -> str:
    if x is None or y is None:
        return "other"
    ax, ay = parse_coord_pair(agent_coord)
    px, py = parse_coord_pair(patient_coord)
    in_agent = ax is not None and ay is not None and ax <= x <= ax + AOI_W and ay <= y <= ay + AOI_H
    in_patient = px is not None and py is not None and px <= x <= px + AOI_W and py <= y <= py + AOI_H
    if in_agent and not in_patient:
        return "agent"
    if in_patient and not in_agent:
        return "patient"
    return "other"


def dot_radius(duration: int, aggregate: bool = False) -> float:
    base = 3.5 if aggregate else 6.0
    scale = 0.33 if aggregate else 0.55
    maximum = 15.0 if aggregate else 28.0
    return max(base, min(maximum, base + math.sqrt(max(0, duration)) * scale))


def phase_colour(phase: str) -> str:
    if phase == "pre":
        return "#005DFF"
    if phase == "post":
        return "#FF8A00"
    return "#7A3CE8"


def phase_label(phase: str) -> str:
    if phase == "pre":
        return "before speech onset"
    if phase == "post":
        return f"first {POST_ONSET_MS} ms after speech onset"
    return "display window, no RT split"


def svg_url_for(
    stimulus_path: Path,
    svg_path: Path,
    asset_base_url: str | None = None,
    asset_root: Path | None = None,
) -> str:
    if asset_base_url:
        root = asset_root or stimulus_path.parent
        rel = os.path.relpath(stimulus_path, start=root)
        return f"{asset_base_url.rstrip('/')}/{quote(Path(rel).as_posix(), safe='/')}"
    rel = os.path.relpath(stimulus_path, start=svg_path.parent)
    return quote(Path(rel).as_posix(), safe="/")


def text(x: float, y: float, body: object, size: int = 26, weight: int = 600, fill: str = "#111") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(str(body))}</text>'
    )


def label_box(x: float, y: float, body: str, colour: str) -> list[str]:
    width = max(64, len(body) * 16 + 22)
    return [
        f'<rect x="{x:.1f}" y="{y - 30:.1f}" width="{width:.1f}" height="38" rx="6" fill="white" fill-opacity="0.86" stroke="{colour}" stroke-width="3"/>',
        text(x + 10, y - 4, body, size=24, weight=700, fill="#111"),
    ]


def draw_aoi(trial: dict[str, object]) -> list[str]:
    items: list[str] = []
    for key, label, colour in [
        ("agens", "AGENT", "#00B8D9"),
        ("patiens", "PATIENT", "#FF3B8A"),
    ]:
        x, y = parse_coord_pair(trial.get(key))
        if x is None or y is None:
            continue
        items.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{AOI_W}" height="{AOI_H}" fill="none" '
            f'stroke="{colour}" stroke-width="6" stroke-dasharray="18 12"/>'
        )
        items.extend(label_box(x + 12, max(42, y - 8), label, colour))
    return items


def draw_legend(lines: list[str], width: int = 760, x: int = 16, y: int = 1094) -> list[str]:
    line_y = y + 34
    phase_y1 = line_y + len(lines) * 31 + 8
    phase_y2 = phase_y1 + 34
    height = phase_y2 + 30 - y
    items = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="white" fill-opacity="0.92" stroke="#111" stroke-opacity="0.22"/>'
    ]
    for line in lines:
        items.append(text(x + 20, line_y, line, size=24, weight=600))
        line_y += 31
    items.extend(
        [
            f'<circle cx="{x + 26}" cy="{phase_y1}" r="11" fill="#005DFF" fill-opacity="0.64" stroke="#111" stroke-width="2"/>',
            text(x + 46, phase_y1 + 8, "blue: before speech onset", size=22, weight=500),
            f'<circle cx="{x + 26}" cy="{phase_y2}" r="11" fill="#FF8A00" fill-opacity="0.64" stroke="#111" stroke-width="2"/>',
            text(x + 46, phase_y2 + 8, f"orange: first {POST_ONSET_MS} ms after onset", size=22, weight=500),
        ]
    )
    return items


def write_trial_svg(
    svg_path: Path,
    stimulus_path: Path,
    trial: dict[str, object],
    dots: list[dict[str, object]],
    asset_base_url: str | None = None,
    asset_root: Path | None = None,
) -> None:
    href = svg_url_for(stimulus_path, svg_path, asset_base_url, asset_root)
    title = (
        f"{trial.get('participant')} / {trial.get('asc_file')} block {trial.get('block')} | "
        f"{trial.get('image')} | RT {trial.get('rt_ms') or 'NA'} ms | {len(dots)} fixations"
    )
    subtitle = "numbers show fixation order; dot size shows fixation duration"
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SCREEN_W}" height="{CANVAS_H}" viewBox="0 0 {SCREEN_W} {CANVAS_H}">',
        f'<image href="{href}" x="0" y="0" width="{SCREEN_W}" height="{SCREEN_H}" preserveAspectRatio="none"/>',
        '<rect x="0" y="0" width="1920" height="1080" fill="none" stroke="#111" stroke-width="2"/>',
        f'<rect x="0" y="{SCREEN_H}" width="{SCREEN_W}" height="{CANVAS_H - SCREEN_H}" fill="#f7f7f7"/>',
    ]
    items.extend(draw_aoi(trial))

    path_points = [(d["x"], d["y"]) for d in dots if d.get("x") is not None and d.get("y") is not None]
    if len(path_points) > 1:
        points = " ".join(f"{float(x):.1f},{float(y):.1f}" for x, y in path_points)
        items.append(
            f'<polyline points="{points}" fill="none" stroke="#111" stroke-width="4" stroke-opacity="0.36" stroke-linejoin="round"/>'
        )

    for idx, dot in enumerate(dots, start=1):
        x = dot.get("x")
        y = dot.get("y")
        if x is None or y is None:
            continue
        radius = dot_radius(int(dot.get("duration", 0)))
        colour = phase_colour(str(dot.get("phase", "unknown")))
        items.append(
            f'<circle cx="{float(x):.1f}" cy="{float(y):.1f}" r="{radius + 3:.1f}" fill="white" fill-opacity="0.84"/>'
        )
        items.append(
            f'<circle cx="{float(x):.1f}" cy="{float(y):.1f}" r="{radius:.1f}" fill="{colour}" fill-opacity="0.66" stroke="#111" stroke-width="2.5"/>'
        )
        items.append(
            f'<text x="{float(x):.1f}" y="{float(y) + 7:.1f}" text-anchor="middle" '
            f'font-family="Arial, Helvetica, sans-serif" font-size="21" font-weight="800" fill="white" '
            f'stroke="#111" stroke-width="3" paint-order="stroke">{idx}</text>'
        )

    items.extend(draw_legend([title, subtitle], width=1120))
    items.append("</svg>")
    svg_path.write_text("\n".join(items) + "\n", encoding="utf-8")


def write_aggregate_svg(
    svg_path: Path,
    stimulus_path: Path,
    image_name: str,
    dots: list[dict[str, object]],
    trial_count: int,
    asset_base_url: str | None = None,
    asset_root: Path | None = None,
) -> None:
    href = svg_url_for(stimulus_path, svg_path, asset_base_url, asset_root)
    participants = len({d["participant"] for d in dots})
    phase_counts = Counter(str(d.get("phase", "unknown")) for d in dots)
    title = f"{image_name} | {participants} participants | {trial_count} trials | {len(dots)} fixations"
    subtitle = f"pre={phase_counts.get('pre', 0)} post={phase_counts.get('post', 0)} unknown={phase_counts.get('unknown', 0)}"
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SCREEN_W}" height="{CANVAS_H}" viewBox="0 0 {SCREEN_W} {CANVAS_H}">',
        f'<image href="{href}" x="0" y="0" width="{SCREEN_W}" height="{SCREEN_H}" preserveAspectRatio="none"/>',
        '<rect x="0" y="0" width="1920" height="1080" fill="none" stroke="#111" stroke-width="2"/>',
        f'<rect x="0" y="{SCREEN_H}" width="{SCREEN_W}" height="{CANVAS_H - SCREEN_H}" fill="#f7f7f7"/>',
    ]

    representative = dots[0] if dots else {}
    items.extend(draw_aoi(representative))

    for dot in dots:
        x = dot.get("x")
        y = dot.get("y")
        if x is None or y is None:
            continue
        radius = dot_radius(int(dot.get("duration", 0)), aggregate=True)
        colour = phase_colour(str(dot.get("phase", "unknown")))
        items.append(
            f'<circle cx="{float(x):.1f}" cy="{float(y):.1f}" r="{radius + 2:.1f}" fill="white" fill-opacity="0.45"/>'
        )
        items.append(
            f'<circle cx="{float(x):.1f}" cy="{float(y):.1f}" r="{radius:.1f}" fill="{colour}" fill-opacity="0.38" stroke="#111" stroke-width="1.5" stroke-opacity="0.62"/>'
        )

    items.extend(draw_legend([title, subtitle, "dot size shows fixation duration"], width=1160))
    items.append("</svg>")
    svg_path.write_text("\n".join(items) + "\n", encoding="utf-8")


def make_index(out_dir: Path, aggregate_files: list[Path], participant_dirs: list[Path], summary: Counter) -> None:
    aggregate_links = "\n".join(
        f'<li><a href="{html.escape(path.relative_to(out_dir).as_posix())}">{html.escape(path.stem)}</a></li>'
        for path in aggregate_files[:300]
    )
    participant_links = "\n".join(
        f'<li><a href="{html.escape((path / "index.html").relative_to(out_dir).as_posix())}">{html.escape(path.name)}</a></li>'
        for path in participant_dirs
    )
    body = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Koryak gaze dot overlays</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 28px; line-height: 1.35; color: #111; }}
    code {{ background: #f3f3f3; padding: 2px 5px; border-radius: 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px 36px; }}
    li {{ margin: 3px 0; }}
  </style>
</head>
<body>
  <h1>Koryak gaze dot overlays</h1>
  <p>Blue dots are fixations before speech onset. Orange dots are fixations in the first {POST_ONSET_MS} ms after speech onset. Dot size follows fixation duration. Agent and patient AOIs are outlined on each stimulus.</p>
  <p>Generated {summary['trial_svgs']} participant-trial overlays and {summary['aggregate_svgs']} aggregate stimulus overlays from {summary['asc_files']} ASC files.</p>
  <p>Data tables: <a href="fixations_plotted.csv">fixations_plotted.csv</a>, <a href="trial_overlay_summary.csv">trial_overlay_summary.csv</a>, <a href="missing_stimuli.csv">missing_stimuli.csv</a>.</p>
  <div class="grid">
    <section>
      <h2>Aggregate by stimulus</h2>
      <ul>{aggregate_links}</ul>
    </section>
    <section>
      <h2>Participant trial folders</h2>
      <ul>{participant_links}</ul>
    </section>
  </div>
</body>
</html>
"""
    (out_dir / "index.html").write_text(body, encoding="utf-8")


def write_participant_indexes(out_dir: Path, trial_rows: list[dict[str, object]]) -> None:
    by_folder: dict[Path, list[dict[str, object]]] = defaultdict(list)
    for row in trial_rows:
        by_folder[Path(str(row["trial_svg"])).parent].append(row)

    for folder, rows in by_folder.items():
        rows = sorted(rows, key=lambda r: (str(r.get("asc_file", "")), int(r.get("block") or 0)))
        links = "\n".join(
            "<li>"
            f'<a href="{html.escape(Path(str(row["trial_svg"])).name)}">{html.escape(str(row["image"]))}</a> '
            f'block {html.escape(str(row["block"]))}, '
            f'{html.escape(str(row["n_fixations"]))} fixations, '
            f'{html.escape(str(row.get("sentence_type", "")))} / {html.escape(str(row.get("word_order", "")))}'
            "</li>"
            for row in rows
        )
        body = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(folder.name)} gaze overlays</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 28px; line-height: 1.35; color: #111; }}
    li {{ margin: 4px 0; }}
  </style>
</head>
<body>
  <h1>{html.escape(folder.name)} gaze overlays</h1>
  <p><a href="../../index.html">Back to main index</a></p>
  <ul>{links}</ul>
</body>
</html>
"""
        (out_dir / folder / "index.html").write_text(body, encoding="utf-8")


def process(args: argparse.Namespace) -> Counter:
    stimuli = find_stimuli(args.stimuli_dir)
    behavior = load_behavior(args.behavior_csv)

    out_dir = args.output_dir
    trial_dir = out_dir / "participant_trials"
    aggregate_dir = out_dir / "aggregate_by_stimulus"
    trial_dir.mkdir(parents=True, exist_ok=True)
    aggregate_dir.mkdir(parents=True, exist_ok=True)

    plotted_rows: list[dict[str, object]] = []
    trial_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []
    aggregate_dots: dict[str, list[dict[str, object]]] = defaultdict(list)
    aggregate_trials: Counter[str] = Counter()

    asc_files = sorted(args.asc_dir.glob("*.asc"))
    for asc_path in asc_files:
        participant = normalize_participant_id(asc_path.stem)
        trials, fixations = parse_asc(asc_path)
        fixations_by_block: dict[object, list[dict[str, object]]] = defaultdict(list)
        for fixation in fixations:
            fixations_by_block[fixation["block"]].append(fixation)

        participant_dir = trial_dir / safe_stem(asc_path.stem)
        participant_dir.mkdir(parents=True, exist_ok=True)

        for trial in trials:
            image = str(trial.get("image", "")).strip()
            if not image:
                continue
            if image not in stimuli:
                missing_rows.append(
                    {
                        "asc_file": asc_path.name,
                        "participant": participant,
                        "block": trial.get("block"),
                        "image": image,
                        "reason": "not found in stimuli folder",
                    }
                )
                continue

            display = parse_int(trial.get("display_time"))
            if display is None:
                continue

            practice = parse_int(trial.get("practice"))
            if args.skip_practice and practice == 1:
                continue

            behavior_row = behavior.get((participant, image), {})
            rt = parse_int(behavior_row.get("reaction time"))
            end_time = parse_int(trial.get("end_time"))
            if rt is not None:
                window_end = display + rt + args.post_onset_ms
                if end_time is not None:
                    window_end = min(window_end, end_time)
            else:
                window_end = end_time
            if window_end is None:
                continue

            dots: list[dict[str, object]] = []
            for fixation in fixations_by_block.get(trial.get("block"), []):
                x = fixation.get("x")
                y = fixation.get("y")
                if x is None or y is None:
                    continue
                if not (0 <= float(x) <= SCREEN_W and 0 <= float(y) <= SCREEN_H):
                    continue
                start = int(fixation["start"])
                end = int(fixation["end"])
                if end < display or start > window_end:
                    continue
                midpoint = (start + end) / 2
                if midpoint < display or midpoint > window_end:
                    continue
                if rt is None:
                    phase = "unknown"
                elif midpoint < display + rt:
                    phase = "pre"
                else:
                    phase = "post"
                dot = {
                    "participant": participant,
                    "asc_file": asc_path.name,
                    "asc_stem": asc_path.stem,
                    "block": trial.get("block"),
                    "trial_index": trial.get("Trial_Index_"),
                    "trial_num": trial.get("trial_num"),
                    "image": image,
                    "x": round(float(x), 2),
                    "y": round(float(y), 2),
                    "start": start,
                    "end": end,
                    "duration": fixation.get("duration"),
                    "time_from_display_ms": round(midpoint - display, 1),
                    "phase": phase,
                    "who": classify_aoi(float(x), float(y), trial.get("agens"), trial.get("patiens")),
                    "rt_ms": rt,
                    "sentence_type": behavior_row.get("sentence type", ""),
                    "word_order": behavior_row.get("word order", ""),
                    "fluency": behavior_row.get("fluency", ""),
                    "agens": trial.get("agens", ""),
                    "patiens": trial.get("patiens", ""),
                }
                dots.append(dot)

            if not dots:
                continue

            stimulus_path = stimuli[image]
            width, height = png_size(stimulus_path)
            if (width, height) != (SCREEN_W, SCREEN_H):
                raise ValueError(f"Unexpected stimulus size {width}x{height}: {stimulus_path}")

            trial.update(
                {
                    "participant": participant,
                    "image": image,
                    "rt_ms": rt,
                    "sentence_type": behavior_row.get("sentence type", ""),
                    "word_order": behavior_row.get("word order", ""),
                    "fluency": behavior_row.get("fluency", ""),
                }
            )
            trial_index = safe_stem(trial.get("Trial_Index_", trial.get("block")))
            svg_name = f"b{int(trial.get('block', 0)):03d}_t{trial_index}_{safe_stem(image)}.svg"
            svg_path = participant_dir / svg_name
            write_trial_svg(
                svg_path,
                stimulus_path,
                trial,
                dots,
                args.svg_asset_base_url,
                args.stimuli_dir,
            )

            for dot in dots:
                dot["trial_svg"] = svg_path.relative_to(out_dir).as_posix()
                plotted_rows.append(dot)
                aggregate_dots[image].append({**dot, **{"agens": trial.get("agens", ""), "patiens": trial.get("patiens", "")}})

            phase_counts = Counter(str(dot["phase"]) for dot in dots)
            who_counts = Counter(str(dot["who"]) for dot in dots)
            trial_rows.append(
                {
                    "participant": participant,
                    "asc_file": asc_path.name,
                    "block": trial.get("block"),
                    "trial_index": trial.get("Trial_Index_"),
                    "trial_num": trial.get("trial_num"),
                    "image": image,
                    "rt_ms": rt,
                    "n_fixations": len(dots),
                    "pre_fixations": phase_counts.get("pre", 0),
                    "post_fixations": phase_counts.get("post", 0),
                    "unknown_phase_fixations": phase_counts.get("unknown", 0),
                    "agent_fixations": who_counts.get("agent", 0),
                    "patient_fixations": who_counts.get("patient", 0),
                    "other_fixations": who_counts.get("other", 0),
                    "sentence_type": behavior_row.get("sentence type", ""),
                    "word_order": behavior_row.get("word order", ""),
                    "fluency": behavior_row.get("fluency", ""),
                    "trial_svg": svg_path.relative_to(out_dir).as_posix(),
                }
            )
            aggregate_trials[image] += 1

    aggregate_files: list[Path] = []
    for image, dots in sorted(aggregate_dots.items()):
        stimulus_path = stimuli[image]
        svg_path = aggregate_dir / f"{safe_stem(image)}.svg"
        write_aggregate_svg(
            svg_path,
            stimulus_path,
            image,
            dots,
            aggregate_trials[image],
            args.svg_asset_base_url,
            args.stimuli_dir,
        )
        aggregate_files.append(svg_path)

    csv_fields = [
        "participant",
        "asc_file",
        "block",
        "trial_index",
        "trial_num",
        "image",
        "x",
        "y",
        "start",
        "end",
        "duration",
        "time_from_display_ms",
        "phase",
        "who",
        "rt_ms",
        "sentence_type",
        "word_order",
        "fluency",
        "agens",
        "patiens",
        "trial_svg",
    ]
    with (out_dir / "fixations_plotted.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in csv_fields} for row in plotted_rows)

    if trial_rows:
        with (out_dir / "trial_overlay_summary.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(trial_rows[0]))
            writer.writeheader()
            writer.writerows(trial_rows)

    missing_fields = ["asc_file", "participant", "block", "image", "reason"]
    with (out_dir / "missing_stimuli.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=missing_fields)
        writer.writeheader()
        writer.writerows(missing_rows)

    readme = f"""# Koryak gaze dot overlays

Open `index.html` for links to the generated overlays.

- `participant_trials/`: one SVG per participant/run/trial.
- `aggregate_by_stimulus/`: one SVG per stimulus, pooling all plotted fixations.
- `fixations_plotted.csv`: every fixation dot with coordinates and metadata.
- `trial_overlay_summary.csv`: one row per generated trial overlay.
- `missing_stimuli.csv`: ASC trials whose PNG was not found in `stimuli/`.

Blue dots are fixations before speech onset. Orange dots are fixations in the first {POST_ONSET_MS} ms after speech onset. Dot size follows fixation duration. Numbered dots in participant-trial overlays show fixation order.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    participant_dirs = sorted([p for p in trial_dir.iterdir() if p.is_dir()])
    summary = Counter(
        {
            "asc_files": len(asc_files),
            "trial_svgs": len(trial_rows),
            "aggregate_svgs": len(aggregate_files),
            "fixations": len(plotted_rows),
            "missing_stimulus_trials": len(missing_rows),
        }
    )
    write_participant_indexes(out_dir, trial_rows)
    make_index(out_dir, aggregate_files, participant_dirs, summary)
    return summary


def main() -> None:
    global POST_ONSET_MS

    parser = argparse.ArgumentParser(description="Create Koryak stimulus gaze-dot SVG overlays from EyeLink ASC files.")
    parser.add_argument("--asc-dir", type=Path, default=Path("ASC files"))
    parser.add_argument("--stimuli-dir", type=Path, default=Path("stimuli"))
    parser.add_argument("--behavior-csv", type=Path, default=Path("Koryak stimuli - final.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/gaze_dots"))
    parser.add_argument(
        "--svg-asset-base-url",
        help="Public base URL for stimulus PNG hrefs in generated SVGs, for example a GitHub raw stimuli URL.",
    )
    parser.add_argument("--post-onset-ms", type=int, default=POST_ONSET_MS)
    parser.add_argument("--include-practice", action="store_true", help="Include practice trials when their PNG exists.")
    args = parser.parse_args()
    args.skip_practice = not args.include_practice

    POST_ONSET_MS = args.post_onset_ms

    summary = process(args)
    print(f"Wrote gaze overlays to {args.output_dir}")
    print(
        f"ASC files: {summary['asc_files']} | trial SVGs: {summary['trial_svgs']} | "
        f"aggregate SVGs: {summary['aggregate_svgs']} | fixations: {summary['fixations']} | "
        f"missing-stimulus trials: {summary['missing_stimulus_trials']}"
    )


if __name__ == "__main__":
    main()
