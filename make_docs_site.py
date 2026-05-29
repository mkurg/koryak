#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from make_output_site import collect_files, format_bytes, render_html


def render_landing(output_summary: dict[str, object], docs_dir: Path) -> str:
    overlay_count = len(list((docs_dir / "participant_trials").rglob("*.svg"))) if (docs_dir / "participant_trials").exists() else 0
    stimulus_count = len(list((docs_dir / "aggregate_by_stimulus").glob("*.svg"))) if (docs_dir / "aggregate_by_stimulus").exists() else 0
    docs_size = sum(path.stat().st_size for path in docs_dir.rglob("*") if path.is_file() and not path.name.startswith("."))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Koryak Project Sites</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d9dee7;
      --text: #1d232b;
      --muted: #5f6b7a;
      --blue: #0077bb;
      --teal: #00897b;
      --red: #cc3311;
      --shadow: 0 12px 34px rgba(29, 35, 43, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      letter-spacing: 0;
    }}
    main {{
      width: min(1120px, calc(100% - 40px));
      margin: 0 auto;
      padding: 54px 0;
    }}
    header {{
      margin-bottom: 28px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(30px, 5vw, 54px);
      line-height: 1;
      font-weight: 780;
    }}
    .lead {{
      margin: 14px 0 0;
      color: var(--muted);
      font-size: 17px;
      max-width: 780px;
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-top: 26px;
    }}
    .card {{
      min-height: 300px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 24px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      text-decoration: none;
      color: inherit;
      position: relative;
      overflow: hidden;
    }}
    .card::before {{
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 5px;
      background: var(--blue);
    }}
    .card.overlay::before {{ background: var(--teal); }}
    .eyebrow {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 740;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    h2 {{
      margin: 10px 0 0;
      font-size: 28px;
      line-height: 1.1;
    }}
    p {{
      margin: 16px 0 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 22px;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfd;
    }}
    .stat b {{
      display: block;
      font-size: 19px;
    }}
    .stat span {{
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }}
    .cta {{
      display: inline-flex;
      align-items: center;
      width: max-content;
      min-height: 40px;
      padding: 0 14px;
      border-radius: 8px;
      border: 1px solid #9ec9e8;
      background: #edf7fd;
      color: #005f95;
      font-weight: 720;
      margin-top: 22px;
    }}
    .overlay .cta {{
      border-color: #9edbd3;
      background: #ecfbf8;
      color: #006b61;
    }}
    footer {{
      margin-top: 22px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 780px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Koryak Project Sites</h1>
      <p class="lead">Two static pages are available from this GitHub Pages root: the structured output library and the gaze-dot overlay browser.</p>
    </header>

    <section class="grid">
      <a class="card" href="output-library.html">
        <div>
          <div class="eyebrow">Output Browser</div>
          <h2>All Analysis Outputs</h2>
          <p>Search, preview, open, and download plots, model summaries, CSV tables, and PDFs generated under the repository output folder.</p>
          <div class="stats">
            <div class="stat"><b>{output_summary["directoryCount"]}</b><span>Folders</span></div>
            <div class="stat"><b>{output_summary["fileCount"]}</b><span>Files</span></div>
            <div class="stat"><b>{output_summary["totalSizeLabel"]}</b><span>Indexed</span></div>
          </div>
        </div>
        <span class="cta">Open output library</span>
      </a>

      <a class="card overlay" href="gaze-dot-overlays.html">
        <div>
          <div class="eyebrow">Eye Tracking</div>
          <h2>Koryak Gaze Dot Overlays</h2>
          <p>Browse participant-trial and aggregate stimulus overlays with pre-onset and post-onset fixation dots over the stimulus images.</p>
          <div class="stats">
            <div class="stat"><b>{overlay_count}</b><span>Trial SVGs</span></div>
            <div class="stat"><b>{stimulus_count}</b><span>Stimulus SVGs</span></div>
            <div class="stat"><b>{format_bytes(docs_size)}</b><span>Docs assets</span></div>
          </div>
        </div>
        <span class="cta">Open gaze overlays</span>
      </a>
    </section>

    <footer>Generated for the repository GitHub Pages configuration that serves from <code>/docs</code>.</footer>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GitHub Pages site served from docs/.")
    parser.add_argument("--docs-dir", default="docs")
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--raw-output-prefix", default="https://raw.githubusercontent.com/mkurg/koryak/main/output/")
    parser.add_argument("--download-output-prefix", default="https://github.com/mkurg/koryak/raw/main/output/")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".nojekyll").write_text("", encoding="utf-8")

    overlay_source = Path(args.output_root) / "gaze_dots" / "index.html"
    if overlay_source.exists():
        shutil.copyfile(overlay_source, docs_dir / "gaze-dot-overlays.html")
    elif (docs_dir / "index.html").exists() and "Koryak gaze dot overlays" in (docs_dir / "index.html").read_text(encoding="utf-8"):
        shutil.copyfile(docs_dir / "index.html", docs_dir / "gaze-dot-overlays.html")

    files, directories, summary = collect_files(
        Path(args.output_root),
        site_filename="index.html",
        url_prefix=args.raw_output_prefix,
        download_prefix=args.download_output_prefix,
        max_file_bytes=100 * 1024 * 1024,
    )
    (docs_dir / "output-library.html").write_text(
        render_html(files, directories, summary, title="Koryak Output Library"),
        encoding="utf-8",
    )
    (docs_dir / "index.html").write_text(render_landing(summary, docs_dir), encoding="utf-8")

    print(docs_dir / "index.html")
    print(docs_dir / "output-library.html")
    print(docs_dir / "gaze-dot-overlays.html")


if __name__ == "__main__":
    main()
