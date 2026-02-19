#!/usr/bin/env python3
"""Backfill ContentStore from existing blog files.

Scans insights/blog/ for weekly, thematic, daily-social, and reading-list
content and creates ContentStore records. Also links images and platform
variants (ghost, twitter, linkedin, slack).

Usage:
    uv run python scripts/backfill_content_store.py --output ./insights
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def parse_ghost_meta(content: str) -> dict:
    """Extract ghost-meta JSON from HTML comment."""
    match = re.search(r"<!--\s*ghost-meta:\s*({.*?})\s*-->", content)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


def parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    front = content[3:end].strip()
    body = content[end + 3:].strip()
    meta: dict = {}
    for line in front.split("\n"):
        if ":" in line and not line.startswith("  "):
            key, val = line.split(":", 1)
            val = val.strip().strip('"').strip("'")
            if val.startswith("["):
                try:
                    meta[key.strip()] = json.loads(val)
                except json.JSONDecodeError:
                    meta[key.strip()] = val
            else:
                meta[key.strip()] = val
        elif line.startswith("  - "):
            # YAML list item
            last_key = list(meta.keys())[-1] if meta else None
            if last_key:
                if not isinstance(meta[last_key], list):
                    meta[last_key] = []
                meta[last_key].append(line.strip("  - ").strip())
    return meta, body


def find_images_for_slug(images_dir: Path, slug: str) -> list[dict]:
    """Find images matching a slug prefix."""
    if not images_dir.exists():
        return []
    images = []
    for f in sorted(images_dir.iterdir()):
        if not f.suffix == ".png":
            continue
        name = f.stem
        # Match patterns: slug-hero, slug-1, slug-2, slug-inline-1, etc.
        # Also match short prefixes like "w06" for "weekly-2026-W06"
        week_match = re.search(r"W(\d{2})$", slug)
        short_prefix = f"w{week_match.group(1)}" if week_match else None
        if (
            name.startswith(slug)
            or name.startswith(slug.replace("weekly-", "w"))
            or (short_prefix and name.startswith(short_prefix))
        ):
            role = "hero" if "hero" in name else "inline"
            images.append({
                "filename": f.name,
                "role": role,
                "prompt": "",
                "relative_path": f"blog/images/{f.name}",
            })
    return images


def backfill(output_dir: Path) -> None:
    store_path = output_dir / ".distill-content-store.json"
    store: dict = {}
    if store_path.exists():
        store = json.loads(store_path.read_text(encoding="utf-8"))

    blog_dir = output_dir / "blog"
    images_dir = blog_dir / "images"
    added = 0

    # --- Weekly posts ---
    for variant_dir in ["ghost/weekly", "markdown/weekly"]:
        weekly_dir = blog_dir / variant_dir
        if not weekly_dir.exists():
            continue
        for f in sorted(weekly_dir.glob("*.md")):
            slug = f.stem
            if slug in store:
                continue
            content = f.read_text(encoding="utf-8")
            meta = parse_ghost_meta(content)
            if not meta:
                fm, body = parse_yaml_frontmatter(content)
                meta = fm
                content = body

            # Strip ghost-meta comment from body
            body = re.sub(r"<!--\s*ghost-meta:.*?-->\s*", "", content).strip()

            # Collect platform variants
            platforms: dict = {}

            # Ghost version
            ghost_file = blog_dir / "ghost" / "weekly" / f"{slug}.md"
            if ghost_file.exists():
                ghost_content = ghost_file.read_text(encoding="utf-8")
                ghost_body = re.sub(r"<!--\s*ghost-meta:.*?-->\s*", "", ghost_content).strip()
                platforms["ghost"] = {
                    "platform": "ghost",
                    "content": ghost_body,
                    "published": False,
                    "published_at": None,
                    "external_id": "",
                }

            # Find matching images
            images = find_images_for_slug(images_dir, slug)

            # Extract date from slug (weekly-2026-W06 -> 2026-02-02)
            date_match = re.search(r"(\d{4})-W(\d{2})", slug)
            created = ""
            if date_match:
                year, week = int(date_match.group(1)), int(date_match.group(2))
                try:
                    d = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%W-%w")
                    created = d.strftime("%Y-%m-%d")
                except ValueError:
                    created = meta.get("date", "")
            else:
                created = str(meta.get("date", ""))

            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            store[slug] = {
                "slug": slug,
                "content_type": "weekly",
                "title": meta.get("title", slug),
                "body": body,
                "status": "draft",
                "created_at": created,
                "source_dates": [],
                "tags": tags,
                "images": images,
                "platforms": platforms,
                "chat_history": [],
                "metadata": {},
                "file_path": str(f.relative_to(output_dir)),
            }
            added += 1

    # --- Thematic posts ---
    for variant_dir in ["ghost/themes", "markdown/themes"]:
        themes_dir = blog_dir / variant_dir
        if not themes_dir.exists():
            continue
        for f in sorted(themes_dir.glob("*.md")):
            slug = f.stem
            if slug in store:
                continue
            content = f.read_text(encoding="utf-8")
            meta = parse_ghost_meta(content)
            if not meta:
                fm, body = parse_yaml_frontmatter(content)
                meta = fm
                content = body

            body = re.sub(r"<!--\s*ghost-meta:.*?-->\s*", "", content).strip()

            platforms = {}
            ghost_file = blog_dir / "ghost" / "themes" / f"{slug}.md"
            if ghost_file.exists():
                ghost_content = ghost_file.read_text(encoding="utf-8")
                ghost_body = re.sub(r"<!--\s*ghost-meta:.*?-->\s*", "", ghost_content).strip()
                platforms["ghost"] = {
                    "platform": "ghost",
                    "content": ghost_body,
                    "published": False,
                    "published_at": None,
                    "external_id": "",
                }

            images = find_images_for_slug(images_dir, slug)
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            store[slug] = {
                "slug": slug,
                "content_type": "thematic",
                "title": meta.get("title", slug),
                "body": body,
                "status": "draft",
                "created_at": str(meta.get("date", "")),
                "source_dates": [],
                "tags": tags,
                "images": images,
                "platforms": platforms,
                "chat_history": [],
                "metadata": {},
                "file_path": str(f.relative_to(output_dir)),
            }
            added += 1

    # --- Daily social posts ---
    social_dir = blog_dir / "daily-social"
    if social_dir.exists():
        # Find base posts (no platform suffix)
        base_pattern = re.compile(r"^daily-social-(\d{4}-\d{2}-\d{2})\.md$")
        for f in sorted(social_dir.glob("daily-social-*.md")):
            m = base_pattern.match(f.name)
            if not m:
                continue
            date_str = m.group(1)
            slug = f"daily-social-{date_str}"
            if slug in store:
                continue

            body = f.read_text(encoding="utf-8").strip()

            # Collect platform variants
            platforms = {}
            for plat in ["twitter", "linkedin", "slack"]:
                plat_file = social_dir / f"daily-social-{date_str}-{plat}.md"
                if plat_file.exists():
                    plat_key = "x" if plat == "twitter" else plat
                    platforms[plat_key] = {
                        "platform": plat_key,
                        "content": plat_file.read_text(encoding="utf-8").strip(),
                        "published": False,
                        "published_at": None,
                        "external_id": "",
                    }

            store[slug] = {
                "slug": slug,
                "content_type": "daily_social",
                "title": f"Daily Social {date_str}",
                "body": body,
                "status": "draft",
                "created_at": date_str,
                "source_dates": [date_str],
                "tags": ["daily-social"],
                "images": [],
                "platforms": platforms,
                "chat_history": [],
                "metadata": {},
                "file_path": str(f.relative_to(output_dir)),
            }
            added += 1

    # Save
    store_path.write_text(json.dumps(store, indent=2), encoding="utf-8")
    total = len(store)
    print(f"Backfilled {added} new records ({total} total in ContentStore)")
    for slug, record in sorted(store.items()):
        plats = ", ".join(record.get("platforms", {}).keys()) or "none"
        imgs = len(record.get("images", []))
        print(f"  {slug}: {record['content_type']} | platforms: {plats} | images: {imgs}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill ContentStore")
    parser.add_argument("--output", required=True, help="Output directory (insights/)")
    args = parser.parse_args()
    backfill(Path(args.output))
