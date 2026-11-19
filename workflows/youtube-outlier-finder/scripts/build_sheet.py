#!/usr/bin/env python3
"""
Put the outliers and the AI's ideas into one sheet, after checking the ideas.

The AI reads outliers.csv, works out why each top video beat its channel, and
writes ideas.csv: one row per video it chose, with the pattern behind it and
up to three ideas of your own built on that pattern.

ideas.csv columns (header required):
    video_id,pattern,idea_1,idea_2,idea_3

This script checks what a person would miss in a long sheet:
  - every video_id is one of the outliers (no ideas built on a video that isn't there)
  - titles fit YouTube's 100 character limit, with a warning past 70, where
    search results start to cut them off (skipped with --mode hooks)
  - no idea is a near copy of the source title: borrow the pattern, not the words

Usage:
    python build_sheet.py outliers.csv ideas.csv --out outliers-and-ideas
    python build_sheet.py outliers.csv ideas.csv --mode hooks   # ideas are ad hooks, not titles

Writes <out>.csv and <out>.xlsx (needs openpyxl: pip install openpyxl). The
sheet holds every outlier; those without ideas just have empty idea columns.
"""

import argparse
import csv
import re
import sys
from difflib import SequenceMatcher

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

TITLE_MAX = 100
TITLE_SOFT = 70
COPY_LIMIT = 0.8


def words(s):
    return " ".join(re.findall(r"[a-z0-9$%']+", s.lower()))


def similar(a, b):
    a, b = words(a), words(b)
    return max(SequenceMatcher(None, a, b).ratio(), SequenceMatcher(None, b, a).ratio())


def read_csv(path, need):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if rows and not need <= set(rows[0]):
        raise SystemExit(f"{path} needs columns: {', '.join(sorted(need))}. Found: {', '.join(rows[0])}")
    return rows


def main():
    ap = argparse.ArgumentParser(description="Check ideas and merge them with the outliers.")
    ap.add_argument("outliers")
    ap.add_argument("ideas")
    ap.add_argument("--out", default="outliers-and-ideas")
    ap.add_argument("--mode", choices=["titles", "hooks"], default="titles")
    args = ap.parse_args()

    outliers = read_csv(args.outliers, {"video_id", "title", "score", "views", "url"})
    by_id = {r["video_id"]: r for r in outliers}
    ideas = read_csv(args.ideas, {"video_id", "pattern", "idea_1"})

    errors, warnings, merged = [], [], {}
    for i, row in enumerate(ideas, start=2):
        vid = (row.get("video_id") or "").strip()
        if vid not in by_id:
            errors.append(f"line {i}: video_id {vid!r} is not in {args.outliers}")
            continue
        if vid in merged:
            errors.append(f"line {i}: video_id {vid!r} appears twice")
            continue
        if not (row.get("pattern") or "").strip():
            errors.append(f"line {i}: empty pattern for {vid}")
        texts = [(row.get(f"idea_{n}") or "").strip() for n in (1, 2, 3)]
        if not any(texts):
            errors.append(f"line {i}: no ideas for {vid}")
        source = by_id[vid]["title"]
        for n, t in enumerate(texts, start=1):
            if not t:
                continue
            if args.mode == "titles":
                if len(t) > TITLE_MAX:
                    errors.append(f"line {i} idea_{n}: {len(t)} characters, YouTube allows {TITLE_MAX}: {t}")
                elif len(t) > TITLE_SOFT:
                    warnings.append(f"line {i} idea_{n}: {len(t)} characters, may be cut off in search: {t}")
            sim = similar(t, source)
            if sim >= COPY_LIMIT:
                errors.append(f"line {i} idea_{n}: {sim:.0%} the same as the source title. "
                              f"Rewrite it for your audience.\n      source: {source}\n      idea:   {t}")
        merged[vid] = {"pattern": row["pattern"].strip(), "idea_1": texts[0], "idea_2": texts[1], "idea_3": texts[2]}

    for w in warnings:
        print("Warning: " + w)
    if errors:
        print(f"Fix {args.ideas} first:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        sys.exit(1)

    extra = ["pattern", "idea_1", "idea_2", "idea_3"]
    cols = list(outliers[0].keys()) if outliers else []
    front = [c for c in ["rank", "score", "views", "channel_median", "title", "channel"] if c in cols]
    rest = [c for c in cols if c not in front]
    order = front + extra + rest

    rows = []
    for r in outliers:
        rows.append({**r, **merged.get(r["video_id"], {k: "" for k in extra})})

    with open(f"{args.out}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=order)
        w.writeheader()
        w.writerows(rows)

    xlsx = False
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError:
        print("openpyxl not installed, so no .xlsx. The CSV has everything.")
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Outliers"
        ws.append(order)
        numeric = {"rank", "score", "views", "channel_median", "median_from", "views_per_day", "age_days",
                   "subscribers", "minutes", "likes", "comments"}
        for r in rows:
            out = []
            for c in order:
                v = r.get(c, "")
                if c in numeric and v not in ("", None):
                    try:
                        v = float(v) if "." in str(v) else int(v)
                    except ValueError:
                        pass
                out.append(v)
            ws.append(out)
        widths = {"title": 50, "channel": 22, "pattern": 45, "idea_1": 45, "idea_2": 45, "idea_3": 45,
                  "url": 30, "description": 60}
        for i, c in enumerate(order, start=1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = widths.get(c, 11)
            ws.cell(1, i).font = Font(bold=True)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
        wb.save(f"{args.out}.xlsx")
        xlsx = True

    print(f"{len(merged)} of {len(outliers)} outliers have ideas. Saved {args.out}.csv"
          + (f" and {args.out}.xlsx" if xlsx else ""))


if __name__ == "__main__":
    main()
