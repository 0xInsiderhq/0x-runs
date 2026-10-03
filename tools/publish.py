#!/usr/bin/env python3
"""Publish one model run to this repo in one go.

Drop everything from a run into inbox/ (zips with the model's code, videos,
images, the prompt, a README if you have one), then run:

    python tools/publish.py

It asks for a short name, model and date if you did not pass them, files the
inbox into runs/<date>_<name>/, writes run.json, rebuilds the index in the root
README, commits and pushes. Standard library only. Uses ffmpeg if it is on PATH
to shrink videos that are too heavy for GitHub.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
RUNS = ROOT / "runs"
TEMPLATE = ROOT / "templates" / "run_README.md"
INDEX_START, INDEX_END = "<!-- runs:start -->", "<!-- runs:end -->"

VIDEO = {".mp4", ".mov", ".webm", ".mkv"}
IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
AUDIO = {".wav", ".mp3", ".flac", ".m4a"}
MAX_MB = 45          # GitHub warns at 50 MB and refuses files over 100 MB
TARGET_MB = 20


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return text.strip("-") or "run"


def ask(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    value = input(f"{label}{hint}: ").strip()
    return value or default


def size_mb(path: Path) -> float:
    return path.stat().st_size / 1_048_576


def shrink_video(src: Path, dst: Path) -> bool:
    """Re-encode to roughly TARGET_MB. Returns False if ffmpeg is missing or fails."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return False
    try:
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(src)], text=True).strip())
    except Exception:
        return False
    kbps = max(400, int(TARGET_MB * 8192 / max(dur, 1)) - 160)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:v", "libx264",
           "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.5)}k", "-bufsize", f"{kbps * 2}k",
           "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(dst)]
    return subprocess.run(cmd).returncode == 0 and dst.exists()


def file_inbox(run_dir: Path) -> list[str]:
    notes = []
    for item in sorted(INBOX.iterdir()):
        if item.name.startswith("."):
            continue
        ext = item.suffix.lower()
        name = item.name.lower()
        if item.is_dir():
            shutil.copytree(item, run_dir / "files" / item.name, dirs_exist_ok=True)
            notes.append(f"folder {item.name} -> files/")
        elif ext == ".zip":
            dest = run_dir / "code"
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(item) as z:
                z.extractall(dest)
            notes.append(f"{item.name} unpacked -> code/")
        elif name in {"readme.md", "report.md"}:
            shutil.copy2(item, run_dir / "README.md")
            notes.append(f"{item.name} -> README.md")
        elif name.startswith("prompt") and ext in {".md", ".txt"}:
            shutil.copy2(item, run_dir / "prompt.md")
            notes.append(f"{item.name} -> prompt.md")
        elif ext in VIDEO:
            dest = run_dir / "media" / item.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if size_mb(item) > MAX_MB:
                small = dest.with_name(dest.stem + "_web.mp4")
                if shrink_video(item, small):
                    notes.append(f"{item.name} {size_mb(item):.0f} MB -> media/{small.name} {size_mb(small):.0f} MB")
                else:
                    notes.append(f"SKIPPED {item.name}: {size_mb(item):.0f} MB and no ffmpeg to shrink it")
            else:
                shutil.copy2(item, dest)
                notes.append(f"{item.name} -> media/")
        elif ext in IMAGE or ext in AUDIO:
            dest = run_dir / "media" / item.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            notes.append(f"{item.name} -> media/")
        else:
            dest = run_dir / "files" / item.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            notes.append(f"{item.name} -> files/")
    return notes


def write_readme(run_dir: Path, meta: dict) -> None:
    readme = run_dir / "README.md"
    if readme.exists():
        return
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, value in meta.items():
        text = text.replace("{{" + key + "}}", str(value))
    media_dir = run_dir / "media"
    media = sorted(p.name for p in media_dir.glob("*")) if media_dir.exists() else []
    text = text.replace("{{media}}", "\n".join(f"- [`{m}`](media/{m})" for m in media) or "- none yet")
    has_prompt = (run_dir / "prompt.md").exists()
    text = text.replace("{{prompt}}", "See [prompt.md](prompt.md)." if has_prompt else "Not added yet.")
    readme.write_text(text, encoding="utf-8")


def rebuild_index() -> None:
    rows = ["| date | run | model | headline |", "|---|---|---|---|"]
    for meta_file in sorted(RUNS.glob("*/run.json"), reverse=True):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        folder = meta_file.parent.name
        rows.append(f"| {meta.get('date', '')} | [{meta.get('title', folder)}](runs/{folder}/) | "
                    f"{meta.get('model', '')} | {meta.get('headline', '')} |")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if INDEX_START in text and INDEX_END in text:
        a = text.index(INDEX_START) + len(INDEX_START)
        b = text.index(INDEX_END)
        text = text[:a] + "\n" + "\n".join(rows) + "\n" + text[b:]
        readme.write_text(text, encoding="utf-8")


def git(*args: str) -> int:
    return subprocess.run(["git", *args], cwd=ROOT).returncode


def clear_inbox() -> None:
    for item in INBOX.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description="File the inbox as a new run and push it.")
    ap.add_argument("--name", help="short name, e.g. cyberpunk-ceiling")
    ap.add_argument("--title", help="human title for the index")
    ap.add_argument("--model", help="e.g. Claude Sonnet 5.5, Max")
    ap.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--headline", default="", help="one line result for the index")
    ap.add_argument("--no-push", action="store_true", help="commit but do not push")
    ap.add_argument("--index-only", action="store_true", help="only rebuild the README index")
    args = ap.parse_args()

    if args.index_only:
        rebuild_index()
        print("index rebuilt")
        return 0

    INBOX.mkdir(exist_ok=True)
    if not any(p for p in INBOX.iterdir() if not p.name.startswith(".")):
        print("inbox/ is empty, nothing to publish")
        return 1

    date = args.date or ask("Date (YYYY-MM-DD)", dt.date.today().isoformat())
    name = slugify(args.name or ask("Short name, e.g. cyberpunk-ceiling"))
    title = args.title or ask("Title for the index", name.replace("-", " "))
    model = args.model or ask("Model and effort, e.g. Claude Sonnet 5.5, Max")
    headline = args.headline or ask("One line result (optional)", "")

    run_dir = RUNS / f"{date}_{name}"
    if run_dir.exists():
        print(f"{run_dir.name} already exists, adding the new files to it")
    run_dir.mkdir(parents=True, exist_ok=True)

    notes = file_inbox(run_dir)
    meta = {"date": date, "title": title, "model": model, "headline": headline, "folder": run_dir.name}
    meta_file = run_dir / "run.json"
    old = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    old.update({k: v for k, v in meta.items() if v})
    meta_file.write_text(json.dumps(old, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_readme(run_dir, old)
    rebuild_index()

    print("\nFiled:")
    for n in notes:
        print("  " + n)

    git("add", "-A")
    if git("commit", "-m", f"run: {run_dir.name}") != 0:
        print("nothing new to commit")
        return 0
    clear_inbox()
    if args.no_push:
        print("committed, not pushed (--no-push)")
        return 0
    if git("push") != 0:
        print("push failed. Check that the remote is set: git remote -v")
        return 1
    print(f"\nPublished runs/{run_dir.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
