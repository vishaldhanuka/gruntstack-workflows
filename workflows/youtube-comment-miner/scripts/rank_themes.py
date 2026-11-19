#!/usr/bin/env python3
"""
Count and rank the themes the AI found in the comments.

The AI reads the comments and writes tags.csv: one row per comment it tagged,
with the theme it belongs to and what kind of comment it is. This script does
the counting, because a tally has to be exact:

  votes    = comments in the theme + the likes on them. A like is someone else
             saying "me too", so it counts the same as writing the comment.
  comments = how many people raised it
  videos   = on how many different videos it came up

It refuses tags for comment ids that aren't in comments.csv, so a theme can't
be built on a quote that doesn't exist.

tags.csv columns (header required):
    comment_id,theme,type
    UgzX...,Setting up conversion tracking,question

type is one of: question, request, objection, complaint, praise, other.
Tag a comment "skip" as its theme to leave it out (spam, jokes, off topic).

Usage:
    python rank_themes.py comments.csv tags.csv --out themes
    -> themes.csv (one row per theme) and themes.xlsx (Themes + Comments sheets)

The .xlsx needs openpyxl (pip install openpyxl). Without it you still get the CSV.
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

TYPES = {"question", "request", "objection", "complaint", "praise", "other"}


def read_csv(path, need):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if rows and not need <= set(rows[0]):
        raise SystemExit(f"{path} needs columns: {', '.join(sorted(need))}. Found: {', '.join(rows[0])}")
    return rows


def main():
    ap = argparse.ArgumentParser(description="Rank comment themes by votes.")
    ap.add_argument("comments")
    ap.add_argument("tags")
    ap.add_argument("--out", default="themes")
    ap.add_argument("--quotes", type=int, default=3, help="example quotes per theme (default 3)")
    args = ap.parse_args()

    comments = {r["comment_id"]: r for r in read_csv(args.comments, {"comment_id", "text", "likes", "video_id"})}
    tags = read_csv(args.tags, {"comment_id", "theme", "type"})

    errors, seen = [], set()
    for i, t in enumerate(tags, start=2):
        cid, theme, kind = t["comment_id"].strip(), t["theme"].strip(), t["type"].strip().lower()
        t["comment_id"], t["theme"], t["type"] = cid, theme, kind
        if cid not in comments:
            errors.append(f"line {i}: comment_id {cid!r} is not in {args.comments}")
        if cid in seen:
            errors.append(f"line {i}: comment_id {cid!r} is tagged twice")
        seen.add(cid)
        if not theme:
            errors.append(f"line {i}: empty theme")
        if theme.lower() != "skip" and kind not in TYPES:
            errors.append(f"line {i}: type {kind!r} must be one of {', '.join(sorted(TYPES))}")
    if errors:
        print(f"Fix {args.tags} first:", file=sys.stderr)
        for e in errors[:30]:
            print("  " + e, file=sys.stderr)
        if len(errors) > 30:
            print(f"  ...and {len(errors) - 30} more", file=sys.stderr)
        sys.exit(1)

    groups = defaultdict(list)
    skipped = 0
    for t in tags:
        if t["theme"].lower() == "skip":
            skipped += 1
            continue
        groups[t["theme"]].append({**comments[t["comment_id"]], "type": t["type"]})

    def likes(c):
        try:
            return int(c["likes"])
        except (TypeError, ValueError):
            return 0

    themes = []
    for name, items in groups.items():
        items.sort(key=likes, reverse=True)
        kinds = Counter(c["type"] for c in items)
        themes.append({
            "theme": name,
            "votes": len(items) + sum(likes(c) for c in items),
            "comments": len(items),
            "likes": sum(likes(c) for c in items),
            "videos": len({c["video_id"] for c in items}),
            "main_type": kinds.most_common(1)[0][0],
            "types": ", ".join(f"{k} {n}" for k, n in kinds.most_common()),
            "quotes": [c["text"] for c in items[: args.quotes]],
            "items": items,
        })
    themes.sort(key=lambda t: (t["votes"], t["comments"]), reverse=True)
    for rank, t in enumerate(themes, start=1):
        t["rank"] = rank

    qcols = [f"quote_{i}" for i in range(1, args.quotes + 1)]
    cols = ["rank", "theme", "votes", "comments", "likes", "videos", "main_type", "types"] + qcols
    with open(f"{args.out}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for t in themes:
            w.writerow([t[c] for c in cols[:8]] + (t["quotes"] + [""] * args.quotes)[: args.quotes])

    xlsx = False
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError:
        print("openpyxl not installed, so no .xlsx. The CSV has everything.")
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Themes"
        ws.append(cols)
        for t in themes:
            ws.append([t[c] for c in cols[:8]] + (t["quotes"] + [""] * args.quotes)[: args.quotes])
        ws2 = wb.create_sheet("Comments")
        ccols = ["theme", "type", "likes", "replies", "video_title", "published", "text", "comment_id", "video_id"]
        ws2.append(ccols)
        for t in themes:
            for c in t["items"]:
                ws2.append([t["theme"], c["type"], likes(c), int(c.get("replies") or 0), c.get("video_title", ""),
                            c.get("published", ""), c["text"], c["comment_id"], c["video_id"]])
        widths = {"Themes": [6, 40, 8, 10, 8, 8, 12, 30] + [60] * args.quotes,
                  "Comments": [36, 10, 7, 8, 40, 11, 80, 28, 13]}
        for sheet in (ws, ws2):
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            sheet.freeze_panes = "A2"
            for i, wdt in enumerate(widths[sheet.title], start=1):
                sheet.column_dimensions[sheet.cell(1, i).column_letter].width = wdt
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
        wb.save(f"{args.out}.xlsx")
        xlsx = True

    tagged = len(tags) - skipped
    print(f"{len(comments)} comments, {tagged} tagged into {len(themes)} themes, {skipped} skipped, "
          f"{len(comments) - len(tags)} not tagged.")
    for t in themes[:10]:
        print(f"  {t['rank']:>2}. {t['theme'][:50]:<50} votes {t['votes']:>5}  comments {t['comments']:>4}  "
              f"videos {t['videos']:>2}  {t['main_type']}")
    print(f"Saved {args.out}.csv" + (f" and {args.out}.xlsx" if xlsx else ""))


if __name__ == "__main__":
    main()
