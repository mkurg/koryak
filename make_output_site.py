#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


PREVIEW_EXTENSIONS = {".pdf", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".html", ".htm", ".md", ".txt", ".csv"}
LARGE_FILE_BYTES = 100 * 1024 * 1024


def humanize(value: str) -> str:
    words = value.replace("-", "_").split("_")
    acronyms = {
        "asc": "ASC",
        "av": "AV",
        "avp": "AVP",
        "apv": "APV",
        "brms": "BRMS",
        "csv": "CSV",
        "gt2": ">2",
        "gt15": ">15",
        "gt20": ">20",
        "html": "HTML",
        "le1": "LE1",
        "le3": "LE3",
        "pdf": "PDF",
        "png": "PNG",
        "rds": "RDS",
        "sol": "SOL",
        "svg": "SVG",
        "pav": "PAV",
        "pv": "PV",
    }
    out: list[str] = []
    for word in words:
        if not word:
            continue
        lower = word.lower()
        out.append(acronyms.get(lower, word.capitalize()))
    return " ".join(out)


def category_for(top_dir: str) -> str:
    lower = top_dir.lower()
    if lower.startswith("khanty"):
        return "Khanty"
    if lower.startswith("gaze") or lower.startswith("track"):
        return "Diagnostics"
    if "brms" in lower or "bayes" in lower or "model" in lower or "behavioral" in lower:
        return "Models"
    if lower.startswith("koryak"):
        return "Koryak"
    return "Other"


def file_type(ext: str) -> str:
    return {
        ".csv": "CSV",
        ".html": "HTML",
        ".htm": "HTML",
        ".log": "Log",
        ".md": "Markdown",
        ".pdf": "PDF",
        ".png": "PNG",
        ".rds": "RDS",
        ".svg": "SVG",
        ".txt": "Text",
    }.get(ext.lower(), ext.lower().lstrip(".").upper() or "File")


def should_include(path: Path, root: Path, site_filename: str) -> bool:
    rel = path.relative_to(root)
    if rel.as_posix() == site_filename:
        return False
    return not any(part.startswith(".") for part in rel.parts)


def collect_files(
    root: Path,
    site_filename: str,
    url_prefix: str = "",
    download_prefix: str = "",
    max_file_bytes: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    files: list[dict[str, object]] = []
    by_dir: dict[str, list[dict[str, object]]] = defaultdict(list)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not should_include(path, root, site_filename):
            continue
        if max_file_bytes is not None and path.stat().st_size > max_file_bytes:
            continue
        rel = path.relative_to(root)
        rel_posix = rel.as_posix()
        rel_url = quote(rel_posix)
        download_url = rel_url
        if url_prefix:
            rel_url = f"{url_prefix.rstrip('/')}/{rel_url}"
        if download_prefix:
            download_url = f"{download_prefix.rstrip('/')}/{quote(rel_posix)}"
        elif url_prefix:
            download_url = rel_url
        top_dir = rel.parts[0] if len(rel.parts) > 1 else "."
        ext = path.suffix.lower()
        stat = path.stat()
        record = {
            "path": rel_posix,
            "url": rel_url,
            "downloadUrl": download_url,
            "name": path.name,
            "dir": top_dir,
            "dirLabel": "Output root" if top_dir == "." else humanize(top_dir),
            "category": category_for(top_dir),
            "extension": ext or "[none]",
            "type": file_type(ext),
            "size": stat.st_size,
            "sizeLabel": format_bytes(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "preview": ext in PREVIEW_EXTENSIONS,
            "large": stat.st_size > LARGE_FILE_BYTES,
        }
        files.append(record)
        by_dir[top_dir].append(record)

    directories: list[dict[str, object]] = []
    for dirname, dir_files in by_dir.items():
        ext_counts = Counter(str(item["type"]) for item in dir_files)
        preview = next(
            (
                item
                for item in dir_files
                if item["extension"] in {".pdf", ".png", ".svg", ".html", ".htm"}
            ),
            dir_files[0],
        )
        directories.append(
            {
                "dir": dirname,
                "label": "Output root" if dirname == "." else humanize(dirname),
                "category": category_for(dirname),
                "fileCount": len(dir_files),
                "totalSize": sum(int(item["size"]) for item in dir_files),
                "totalSizeLabel": format_bytes(sum(int(item["size"]) for item in dir_files)),
                "types": dict(sorted(ext_counts.items())),
                "previewPath": preview["path"],
                "previewUrl": preview["url"],
                "previewName": preview["name"],
                "latest": max(str(item["modified"]) for item in dir_files),
            }
        )

    directories.sort(key=lambda item: (str(item["category"]), str(item["label"])))
    summary = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fileCount": len(files),
        "directoryCount": len(directories),
        "totalSize": sum(int(item["size"]) for item in files),
        "totalSizeLabel": format_bytes(sum(int(item["size"]) for item in files)),
        "typeCounts": dict(sorted(Counter(str(item["type"]) for item in files).items())),
        "categoryCounts": dict(sorted(Counter(str(item["category"]) for item in files).items())),
        "largeCount": sum(1 for item in files if item["large"]),
    }
    return files, directories, summary


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def render_html(
    files: list[dict[str, object]],
    directories: list[dict[str, object]],
    summary: dict[str, object],
    title: str = "Koryak Output Library",
) -> str:
    data_json = json.dumps({"files": files, "directories": directories, "summary": summary}, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d9dee7;
      --line-strong: #b9c2cf;
      --text: #1d232b;
      --muted: #5f6b7a;
      --soft: #eef2f7;
      --blue: #0077bb;
      --red: #cc3311;
      --teal: #00897b;
      --gold: #a66a00;
      --shadow: 0 10px 30px rgba(29, 35, 43, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      letter-spacing: 0;
    }}
    a {{ color: inherit; }}
    .app-header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 22px clamp(18px, 3vw, 36px);
      position: sticky;
      top: 0;
      z-index: 5;
    }}
    .header-row {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: end;
      max-width: 1680px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(24px, 2.8vw, 38px);
      line-height: 1.05;
      font-weight: 750;
    }}
    .subline {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(86px, 1fr));
      gap: 8px;
      min-width: min(560px, 44vw);
    }}
    .stat {{
      border: 1px solid var(--line);
      background: #fbfcfd;
      border-radius: 8px;
      padding: 9px 10px;
    }}
    .stat b {{ display: block; font-size: 18px; }}
    .stat span {{ color: var(--muted); font-size: 11px; text-transform: uppercase; }}
    .toolbar {{
      max-width: 1680px;
      margin: 16px auto 0;
      display: grid;
      grid-template-columns: minmax(220px, 1fr) 190px 160px 160px;
      gap: 10px;
      align-items: center;
    }}
    .field, select {{
      width: 100%;
      border: 1px solid var(--line-strong);
      background: white;
      border-radius: 8px;
      color: var(--text);
      min-height: 40px;
      padding: 0 12px;
      font: inherit;
    }}
    .layout {{
      max-width: 1680px;
      margin: 18px auto 42px;
      padding: 0 clamp(18px, 3vw, 36px);
      display: grid;
      grid-template-columns: minmax(320px, 430px) minmax(420px, 1fr);
      gap: 18px;
    }}
    .sidebar, .main-panel, .preview-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .sidebar {{
      padding: 14px;
      align-self: start;
      max-height: calc(100vh - 156px);
      overflow: auto;
      position: sticky;
      top: 138px;
    }}
    .section-title {{
      margin: 0 0 12px;
      font-size: 15px;
      font-weight: 750;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .collection-list {{
      display: grid;
      gap: 8px;
    }}
    .collection {{
      width: 100%;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
      text-align: left;
      border: 1px solid var(--line);
      border-left: 4px solid var(--blue);
      border-radius: 8px;
      background: white;
      padding: 10px 11px;
      cursor: pointer;
      color: var(--text);
      font: inherit;
      min-height: 68px;
    }}
    .collection[data-category="Khanty"] {{ border-left-color: var(--teal); }}
    .collection[data-category="Models"] {{ border-left-color: var(--gold); }}
    .collection[data-category="Diagnostics"] {{ border-left-color: var(--red); }}
    .collection.active {{
      background: var(--soft);
      border-color: var(--line-strong);
    }}
    .collection strong {{
      display: block;
      font-size: 14px;
      line-height: 1.2;
    }}
    .collection small {{
      color: var(--muted);
      display: block;
      margin-top: 4px;
      line-height: 1.25;
    }}
    .count {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      color: var(--muted);
      background: #fbfcfd;
      white-space: nowrap;
    }}
    .content-stack {{
      display: grid;
      grid-template-rows: auto minmax(420px, 1fr);
      gap: 18px;
      min-width: 0;
    }}
    .main-panel {{
      overflow: hidden;
    }}
    .panel-head {{
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
    }}
    .panel-head h2 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.15;
    }}
    .panel-head p {{
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .table-wrap {{
      overflow: auto;
      max-height: 690px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      min-width: 880px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      vertical-align: middle;
      text-align: left;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #fbfcfd;
      z-index: 1;
      color: #3b4552;
      font-size: 11px;
      text-transform: uppercase;
      font-weight: 750;
    }}
    tr:hover td {{ background: #f8fafc; }}
    .file-name {{
      font-weight: 650;
      max-width: 460px;
      overflow-wrap: anywhere;
    }}
    .file-path {{
      color: var(--muted);
      font-size: 11px;
      margin-top: 2px;
      overflow-wrap: anywhere;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 7px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fbfcfd;
      color: #3d4754;
      font-size: 11px;
      font-weight: 650;
      white-space: nowrap;
    }}
    .badge.large {{ color: #8a4f00; border-color: #d7b46f; background: #fff8e8; }}
    .actions {{
      display: flex;
      gap: 7px;
      align-items: center;
      white-space: nowrap;
    }}
    .action {{
      border: 1px solid var(--line-strong);
      background: white;
      border-radius: 8px;
      min-height: 32px;
      padding: 0 10px;
      color: var(--text);
      font: inherit;
      font-size: 12px;
      font-weight: 650;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      cursor: pointer;
    }}
    .action.primary {{
      border-color: #9ec9e8;
      background: #edf7fd;
      color: #005f95;
    }}
    .preview-panel {{
      min-height: 440px;
      overflow: hidden;
    }}
    .preview-frame {{
      height: 560px;
      background: #f0f3f7;
      border-top: 1px solid var(--line);
      display: grid;
      place-items: center;
      overflow: hidden;
    }}
    .preview-frame iframe, .preview-frame object {{
      width: 100%;
      height: 100%;
      border: 0;
      background: white;
    }}
    .preview-frame img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      background: white;
    }}
    .empty {{
      color: var(--muted);
      padding: 32px;
      text-align: center;
    }}
    .pager {{
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
      padding: 12px 18px;
      border-top: 1px solid var(--line);
      background: #fbfcfd;
      color: var(--muted);
      font-size: 13px;
    }}
    .pager button {{
      border: 1px solid var(--line-strong);
      background: white;
      border-radius: 8px;
      min-height: 32px;
      padding: 0 10px;
      color: var(--text);
      font: inherit;
      cursor: pointer;
    }}
    .pager button:disabled {{
      opacity: 0.45;
      cursor: default;
    }}
    @media (max-width: 1100px) {{
      .header-row, .toolbar, .layout {{
        grid-template-columns: 1fr;
      }}
      .stats {{
        min-width: 0;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .sidebar {{
        position: static;
        max-height: none;
      }}
    }}
  </style>
</head>
<body>
  <header class="app-header">
    <div class="header-row">
      <div>
        <h1>{title}</h1>
        <div class="subline" id="generated"></div>
      </div>
      <div class="stats" id="stats"></div>
    </div>
    <div class="toolbar">
      <input class="field" id="search" type="search" placeholder="Search outputs, folders, extensions">
      <select id="category"></select>
      <select id="type"></select>
      <select id="sort">
        <option value="dir">Folder</option>
        <option value="newest">Newest</option>
        <option value="size">Largest</option>
        <option value="type">Type</option>
      </select>
    </div>
  </header>

  <main class="layout">
    <aside class="sidebar">
      <h2 class="section-title">Collections <span class="count" id="collection-count"></span></h2>
      <div class="collection-list" id="collections"></div>
    </aside>

    <div class="content-stack">
      <section class="main-panel">
        <div class="panel-head">
          <div>
            <h2 id="table-title">All Outputs</h2>
            <p id="table-subtitle"></p>
          </div>
          <span class="count" id="match-count"></span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Folder</th>
                <th>Type</th>
                <th>Size</th>
                <th>Modified</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody id="file-rows"></tbody>
          </table>
        </div>
        <div class="pager">
          <span id="page-status"></span>
          <button id="prev-page">Previous</button>
          <button id="next-page">Next</button>
        </div>
      </section>

      <section class="preview-panel">
        <div class="panel-head">
          <div>
            <h2 id="preview-title">Preview</h2>
            <p id="preview-meta"></p>
          </div>
          <div class="actions" id="preview-actions"></div>
        </div>
        <div class="preview-frame" id="preview-frame">
          <div class="empty">Select a previewable output.</div>
        </div>
      </section>
    </div>
  </main>

  <script id="output-data" type="application/json">{data_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('output-data').textContent);
    const files = data.files;
    const directories = data.directories;
    const state = {{
      category: 'All',
      type: 'All',
      dir: 'All',
      query: '',
      sort: 'dir',
      page: 1,
      pageSize: 100,
      filtered: []
    }};

    const el = {{
      stats: document.getElementById('stats'),
      generated: document.getElementById('generated'),
      category: document.getElementById('category'),
      type: document.getElementById('type'),
      sort: document.getElementById('sort'),
      search: document.getElementById('search'),
      collections: document.getElementById('collections'),
      collectionCount: document.getElementById('collection-count'),
      tableTitle: document.getElementById('table-title'),
      tableSubtitle: document.getElementById('table-subtitle'),
      matchCount: document.getElementById('match-count'),
      rows: document.getElementById('file-rows'),
      pageStatus: document.getElementById('page-status'),
      prevPage: document.getElementById('prev-page'),
      nextPage: document.getElementById('next-page'),
      previewTitle: document.getElementById('preview-title'),
      previewMeta: document.getElementById('preview-meta'),
      previewActions: document.getElementById('preview-actions'),
      previewFrame: document.getElementById('preview-frame')
    }};

    function text(value) {{
      return String(value ?? '');
    }}

    function option(select, value, label) {{
      const item = document.createElement('option');
      item.value = value;
      item.textContent = label;
      select.appendChild(item);
    }}

    function init() {{
      el.generated.textContent = `Generated ${{data.summary.generated}} from the output folder`;
      el.stats.innerHTML = [
        ['Folders', data.summary.directoryCount],
        ['Files', data.summary.fileCount],
        ['Total size', data.summary.totalSizeLabel],
        ['Large files', data.summary.largeCount]
      ].map(([label, value]) => `<div class="stat"><b>${{value}}</b><span>${{label}}</span></div>`).join('');

      option(el.category, 'All', 'All categories');
      [...new Set(files.map(file => file.category))].sort().forEach(value => option(el.category, value, value));
      option(el.type, 'All', 'All types');
      [...new Set(files.map(file => file.type))].sort().forEach(value => option(el.type, value, value));

      el.category.addEventListener('change', () => {{ state.category = el.category.value; state.dir = 'All'; state.page = 1; render(); }});
      el.type.addEventListener('change', () => {{ state.type = el.type.value; state.page = 1; render(); }});
      el.sort.addEventListener('change', () => {{ state.sort = el.sort.value; state.page = 1; render(); }});
      el.search.addEventListener('input', () => {{ state.query = el.search.value.trim().toLowerCase(); state.page = 1; render(); }});
      el.prevPage.addEventListener('click', () => {{ state.page = Math.max(1, state.page - 1); renderFiles(); }});
      el.nextPage.addEventListener('click', () => {{ state.page += 1; renderFiles(); }});

      render();
      const firstPreview = files.find(file => file.preview && file.type === 'PDF') || files.find(file => file.preview);
      if (firstPreview) renderPreview(firstPreview);
    }}

    function render() {{
      renderCollections();
      renderFiles();
    }}

    function matchingFiles() {{
      let out = files.filter(file => {{
        if (state.category !== 'All' && file.category !== state.category) return false;
        if (state.type !== 'All' && file.type !== state.type) return false;
        if (state.dir !== 'All' && file.dir !== state.dir) return false;
        if (state.query) {{
          const haystack = `${{file.path}} ${{file.dirLabel}} ${{file.type}} ${{file.category}}`.toLowerCase();
          if (!haystack.includes(state.query)) return false;
        }}
        return true;
      }});

      out.sort((a, b) => {{
        if (state.sort === 'newest') return text(b.modified).localeCompare(text(a.modified)) || text(a.path).localeCompare(text(b.path));
        if (state.sort === 'size') return Number(b.size) - Number(a.size) || text(a.path).localeCompare(text(b.path));
        if (state.sort === 'type') return text(a.type).localeCompare(text(b.type)) || text(a.path).localeCompare(text(b.path));
        return text(a.dirLabel).localeCompare(text(b.dirLabel)) || text(a.path).localeCompare(text(b.path));
      }});
      return out;
    }}

    function renderCollections() {{
      const query = state.query;
      const visibleDirs = directories.filter(dir => {{
        if (state.category !== 'All' && dir.category !== state.category) return false;
        if (!query) return true;
        return `${{dir.label}} ${{dir.dir}} ${{dir.category}} ${{dir.previewName}}`.toLowerCase().includes(query);
      }});
      el.collectionCount.textContent = visibleDirs.length;
      const allButton = collectionButton({{ dir: 'All', label: 'All outputs', category: 'All', fileCount: files.length, totalSizeLabel: data.summary.totalSizeLabel, types: data.summary.typeCounts }});
      allButton.classList.toggle('active', state.dir === 'All');
      allButton.addEventListener('click', () => {{ state.dir = 'All'; state.page = 1; render(); }});
      el.collections.innerHTML = '';
      el.collections.appendChild(allButton);
      visibleDirs.forEach(dir => {{
        const button = collectionButton(dir);
        button.classList.toggle('active', state.dir === dir.dir);
        button.addEventListener('click', () => {{ state.dir = dir.dir; state.page = 1; render(); }});
        el.collections.appendChild(button);
      }});
    }}

    function collectionButton(dir) {{
      const button = document.createElement('button');
      button.className = 'collection';
      button.dataset.category = dir.category;
      const types = Object.entries(dir.types || {{}}).slice(0, 4).map(([type, count]) => `${{type}} ${{count}}`).join(' · ');
      button.innerHTML = `
        <span>
          <strong>${{escapeHtml(dir.label)}}</strong>
          <small>${{escapeHtml(dir.category)}} · ${{escapeHtml(dir.totalSizeLabel || '')}}${{types ? ' · ' + escapeHtml(types) : ''}}</small>
        </span>
        <span class="count">${{dir.fileCount}}</span>
      `;
      return button;
    }}

    function renderFiles() {{
      state.filtered = matchingFiles();
      const totalPages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
      state.page = Math.min(state.page, totalPages);
      const start = (state.page - 1) * state.pageSize;
      const pageRows = state.filtered.slice(start, start + state.pageSize);
      const selectedDir = state.dir === 'All' ? null : directories.find(dir => dir.dir === state.dir);

      el.tableTitle.textContent = selectedDir ? selectedDir.label : 'All Outputs';
      el.tableSubtitle.textContent = selectedDir
        ? `${{selectedDir.category}} · ${{selectedDir.fileCount}} files · ${{selectedDir.totalSizeLabel}}`
        : `${{data.summary.directoryCount}} folders · ${{data.summary.fileCount}} files · ${{data.summary.totalSizeLabel}}`;
      el.matchCount.textContent = `${{state.filtered.length}} matches`;

      el.rows.innerHTML = pageRows.map(fileRow).join('');
      el.rows.querySelectorAll('[data-preview]').forEach(button => {{
        button.addEventListener('click', () => {{
          const file = files.find(item => item.path === button.dataset.preview);
          if (file) renderPreview(file);
        }});
      }});

      const end = Math.min(start + state.pageSize, state.filtered.length);
      el.pageStatus.textContent = state.filtered.length ? `${{start + 1}}-${{end}} of ${{state.filtered.length}}` : '0 of 0';
      el.prevPage.disabled = state.page <= 1;
      el.nextPage.disabled = state.page >= totalPages;
    }}

    function fileRow(file) {{
      const previewAction = file.preview
        ? `<button class="action primary" data-preview="${{escapeAttr(file.path)}}">Preview</button>`
        : '';
      const largeBadge = file.large ? '<span class="badge large">Large</span>' : '';
      return `
        <tr>
          <td>
            <div class="file-name">${{escapeHtml(file.name)}}</div>
            <div class="file-path">${{escapeHtml(file.path)}}</div>
          </td>
          <td>${{escapeHtml(file.dirLabel)}}</td>
          <td><span class="badge">${{escapeHtml(file.type)}}</span> ${{largeBadge}}</td>
          <td>${{escapeHtml(file.sizeLabel)}}</td>
          <td>${{escapeHtml(file.modified)}}</td>
          <td>
            <div class="actions">
              ${{previewAction}}
              <a class="action" href="${{escapeAttr(file.url)}}" target="_blank" rel="noopener">Open</a>
              <a class="action" href="${{escapeAttr(file.downloadUrl || file.url)}}" download>Download</a>
            </div>
          </td>
        </tr>
      `;
    }}

    function renderPreview(file) {{
      el.previewTitle.textContent = file.name;
      el.previewMeta.textContent = `${{file.dirLabel}} · ${{file.type}} · ${{file.sizeLabel}} · ${{file.modified}}`;
      el.previewActions.innerHTML = `
        <a class="action" href="${{escapeAttr(file.url)}}" target="_blank" rel="noopener">Open</a>
        <a class="action" href="${{escapeAttr(file.downloadUrl || file.url)}}" download>Download</a>
      `;
      const ext = file.extension.toLowerCase();
      if (['.png', '.jpg', '.jpeg', '.webp', '.svg'].includes(ext)) {{
        el.previewFrame.innerHTML = `<img src="${{escapeAttr(file.url)}}" alt="${{escapeAttr(file.name)}}">`;
      }} else if (['.pdf', '.html', '.htm'].includes(ext)) {{
        el.previewFrame.innerHTML = `<iframe src="${{escapeAttr(file.url)}}" title="${{escapeAttr(file.name)}}"></iframe>`;
      }} else {{
        el.previewFrame.innerHTML = `
          <div class="empty">
            <div>${{escapeHtml(file.type)}} · ${{escapeHtml(file.sizeLabel)}}</div>
            <div class="file-path">${{escapeHtml(file.path)}}</div>
          </div>`;
      }}
    }}

    function escapeHtml(value) {{
      return text(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}

    function escapeAttr(value) {{
      return escapeHtml(value);
    }}

    init();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static browser for every file under output/.")
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--site-filename", default="index.html")
    parser.add_argument("--site-path", default="")
    parser.add_argument("--title", default="Koryak Output Library")
    parser.add_argument(
        "--url-prefix",
        default="",
        help="Optional URL prefix for generated file links, e.g. a raw GitHub output/ URL.",
    )
    parser.add_argument(
        "--download-prefix",
        default="",
        help="Optional URL prefix for download links when it should differ from preview/open links.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=0,
        help="When positive, omit files larger than this many bytes from the generated index.",
    )
    args = parser.parse_args()

    root = Path(args.output_root)
    site_path = Path(args.site_path) if args.site_path else root / args.site_filename
    files, directories, summary = collect_files(
        root,
        args.site_filename,
        args.url_prefix,
        args.download_prefix,
        max_file_bytes=args.max_file_bytes if args.max_file_bytes > 0 else None,
    )
    site_path.parent.mkdir(parents=True, exist_ok=True)
    site_path.write_text(render_html(files, directories, summary, title=args.title), encoding="utf-8")
    print(site_path)


if __name__ == "__main__":
    main()
